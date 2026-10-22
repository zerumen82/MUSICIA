function ConvertTo-EngineCreationStamp($Value) {
    if ($null -eq $Value) { return $null }
    if ($Value -is [datetime]) {
        return [pscustomobject]@{
            ticks = [long]$Value.ToUniversalTime().Ticks
            precise = $true
        }
    }

    $text = ([string]$Value).Trim()
    if (-not $text) { return $null }
    $parsed = [datetime]::MinValue
    $invariant = [Globalization.CultureInfo]::InvariantCulture
    if ([datetime]::TryParseExact(
        $text, 'o', $invariant,
        [Globalization.DateTimeStyles]::RoundtripKind, [ref]$parsed
    )) {
        return [pscustomobject]@{
            ticks = [long]$parsed.ToUniversalTime().Ticks
            precise = $true
        }
    }

    $styles = [Globalization.DateTimeStyles]::AssumeLocal -bor
        [Globalization.DateTimeStyles]::AllowWhiteSpaces
    $cultures = @(
        [Globalization.CultureInfo]::CurrentCulture,
        [Globalization.CultureInfo]::GetCultureInfo('en-US'),
        [Globalization.CultureInfo]::GetCultureInfo('es-ES'),
        $invariant
    )
    $matches = [System.Collections.Generic.HashSet[long]]::new()
    foreach ($culture in $cultures) {
        $parsed = [datetime]::MinValue
        if ([datetime]::TryParse($text, $culture, $styles, [ref]$parsed)) {
            [void]$matches.Add([long]$parsed.ToUniversalTime().Ticks)
        }
    }
    if ($matches.Count -ne 1) { return $null }
    return [pscustomobject]@{
        ticks = [long]@($matches)[0]
        precise = $false
    }
}

function Test-EngineCreationDate($Recorded, $Actual) {
    $recorded = ConvertTo-EngineCreationStamp $Recorded
    $actual = ConvertTo-EngineCreationStamp $Actual
    if ($null -eq $recorded -or $null -eq $actual) { return $false }
    if ($recorded.precise -and $actual.precise) {
        return [long]$recorded.ticks -eq [long]$actual.ticks
    }
    $ticksPerSecond = [timespan]::TicksPerSecond
    $recordedSecond = [long]$recorded.ticks - ([long]$recorded.ticks % $ticksPerSecond)
    $actualSecond = [long]$actual.ticks - ([long]$actual.ticks % $ticksPerSecond)
    return $recordedSecond -eq $actualSecond
}

function Format-EngineCreationDate([datetime]$Value) {
    $Value.ToUniversalTime().ToString(
        'o', [Globalization.CultureInfo]::InvariantCulture
    )
}

function Test-EngineProcessSnapshot($Expected, $Actual) {
    return $null -ne $Expected -and $null -ne $Actual -and
        [int]$Expected.ProcessId -eq [int]$Actual.ProcessId -and
        [int]$Expected.ParentProcessId -eq [int]$Actual.ParentProcessId -and
        (Test-EngineCreationDate $Expected.CreationDate $Actual.CreationDate) -and
        [bool]$Expected.ExecutablePath -and [bool]$Expected.CommandLine -and
        [string]::Equals([string]$Expected.ExecutablePath, [string]$Actual.ExecutablePath,
            [StringComparison]::OrdinalIgnoreCase) -and
        [string]$Expected.CommandLine -ceq [string]$Actual.CommandLine
}

function Get-EngineCommandArguments([string]$CommandLine) {
    if ($CommandLine -notmatch '^\s*(?:"[^"]+"|\S+)\s+(?<arguments>.+?)\s*$') {
        throw 'No se pudieron acreditar los argumentos del motor; se preserva el proceso.'
    }
    return $Matches.arguments
}

function Test-EngineConsoleHost($Process, $RootProcess) {
    $systemExecutable = Join-Path ([Environment]::GetFolderPath('System')) 'conhost.exe'
    $rootStamp = ConvertTo-EngineCreationStamp $RootProcess.CreationDate
    $stamp = ConvertTo-EngineCreationStamp $Process.CreationDate
    if ([string]$Process.Name -ine 'conhost.exe' -or
        [int]$Process.ParentProcessId -ne [int]$RootProcess.ProcessId -or
        -not $rootStamp -or -not $stamp -or -not $stamp.precise -or
        $stamp.ticks -lt $rootStamp.ticks -or
        -not [string]::Equals([string]$Process.ExecutablePath, $systemExecutable,
            [StringComparison]::OrdinalIgnoreCase)) { return $false }
    $executablePattern = '(?:' + [regex]::Escape($systemExecutable) + '|' +
        [regex]::Escape(('\??\' + $systemExecutable)) + ')'
    return [string]$Process.CommandLine -imatch ('^"?' + $executablePattern + '"?\s+0x[0-9a-f]+\s*$')
}

function Get-VerifiedEngineProcesses($RootProcess, [ref]$ConsoleHosts) {
    $rootPid = [int]$RootProcess.ProcessId
    $current = Get-CimInstance Win32_Process -Filter "ProcessId = $rootPid" -ErrorAction Stop
    if (-not (Test-EngineProcessSnapshot $RootProcess $current)) {
        throw "La identidad del PID $rootPid cambió antes de preparar la parada."
    }
    $allChildren = @(Get-CimInstance Win32_Process -Filter "ParentProcessId = $rootPid" -ErrorAction Stop)
    $hosts = @($allChildren | Where-Object { Test-EngineConsoleHost $_ $RootProcess })
    if ($ConsoleHosts) { $ConsoleHosts.Value = $hosts }
    $children = @($allChildren | Where-Object { -not (Test-EngineConsoleHost $_ $RootProcess) })
    if ($children.Count -gt 1) {
        $detail = $children | Select-Object ProcessId, ParentProcessId, CreationDate, ExecutablePath, CommandLine |
            ConvertTo-Json -Compress
        throw "Descendencia ambigua del PID $rootPid; se preserva el motor: $detail"
    }
    if ($children.Count -eq 1) {
        # Windows venv launchers delegate to the interpreter specified by home.
        # Parentage alone cannot establish ownership of an arbitrary child.
        $scriptsDirectory = Split-Path -Parent ([string]$RootProcess.ExecutablePath)
        if ((Split-Path -Leaf $scriptsDirectory) -ine 'Scripts' -or
            (Split-Path -Leaf ([string]$RootProcess.ExecutablePath)) -ine 'python.exe') {
            throw 'El proceso padre no es un launcher venv verificable; se preserva el motor.'
        }
        $venvConfig = Join-Path (Split-Path -Parent $scriptsDirectory) 'pyvenv.cfg'
        $homes = @(Get-Content -LiteralPath $venvConfig -ErrorAction Stop | ForEach-Object {
            if ($_ -match '^\s*home\s*=\s*(.+?)\s*$') { $Matches[1] }
        })
        if ($homes.Count -ne 1 -or -not [System.IO.Path]::IsPathRooted($homes[0])) {
            throw 'No se pudo acreditar el intérprete base del venv; se preserva el motor.'
        }
        $baseExecutable = [System.IO.Path]::GetFullPath((Join-Path $homes[0] 'python.exe'))
        $child = $children[0]
        $rootStamp = ConvertTo-EngineCreationStamp $RootProcess.CreationDate
        $childStamp = ConvertTo-EngineCreationStamp $child.CreationDate
        if (-not $rootStamp -or -not $childStamp -or -not $rootStamp.precise -or
            -not $childStamp.precise -or $childStamp.ticks -lt $rootStamp.ticks -or
            [int]$child.ParentProcessId -ne $rootPid -or
            -not [string]::Equals([string]$child.ExecutablePath, $baseExecutable,
                [StringComparison]::OrdinalIgnoreCase) -or
            (Get-EngineCommandArguments $child.CommandLine) -cne
                (Get-EngineCommandArguments $RootProcess.CommandLine)) {
            throw "No se pudo acreditar el hijo del PID $rootPid; se preserva el motor."
        }
        $childPid = [int]$child.ProcessId
        if (@(Get-CimInstance Win32_Process -Filter "ParentProcessId = $childPid" -ErrorAction Stop).Count) {
            throw "Descendencia inesperada del intérprete $childPid; se preserva el motor."
        }
        $child
    }
    $RootProcess
}

function Wait-EngineProcessExit($Expected, [datetime]$Deadline) {
    $targetPid = [int]$Expected.ProcessId
    do {
        $current = Get-CimInstance Win32_Process -Filter "ProcessId = $targetPid" -ErrorAction Stop
        if (-not $current) { return }
        $expectedStamp = ConvertTo-EngineCreationStamp $Expected.CreationDate
        $currentStamp = ConvertTo-EngineCreationStamp $current.CreationDate
        if ($expectedStamp -and $currentStamp -and $expectedStamp.precise -and
            $currentStamp.precise -and $expectedStamp.ticks -ne $currentStamp.ticks) {
            throw "El PID $targetPid fue reutilizado durante la parada; se preserva el registro."
        }
        if ((Get-Date) -ge $Deadline) {
            $detail = $current | Select-Object ProcessId, ParentProcessId, CreationDate, ExecutablePath, CommandLine |
                ConvertTo-Json -Compress
            throw "No se pudo acreditar la salida del PID ${targetPid}: $detail"
        }
        Start-Sleep -Milliseconds 250
    } while ($true)
}

function Stop-VerifiedEngineProcesses($RootProcess, [int]$TimeoutSeconds, [scriptblock]$PortOpen) {
    $consoleHosts = @()
    $processes = @(Get-VerifiedEngineProcesses $RootProcess ([ref]$consoleHosts))
    $deadline = (Get-Date).AddSeconds([Math]::Max(1, $TimeoutSeconds))
    # Capture and validate the complete pair before sending any signal. Stop the
    # interpreter first so a disappearing launcher never hides a live child.
    $hasStoppedProcess = $false
    foreach ($expected in $processes) {
        $targetPid = [int]$expected.ProcessId
        do {
            $current = Get-CimInstance Win32_Process -Filter "ProcessId = $targetPid" -ErrorAction Stop
            if (-not $current) { break }
            $pending = -not (Test-EngineProcessSnapshot $expected $current)
            if ($pending -and -not $hasStoppedProcess) {
                throw "La identidad del PID $targetPid cambió; se preserva el proceso."
            }
            $children = @(Get-CimInstance Win32_Process -Filter "ParentProcessId = $targetPid" -ErrorAction Stop)
            foreach ($child in $children) {
                $known = @(@($processes) + @($consoleHosts) | Where-Object {
                    [int]$_.ProcessId -eq [int]$child.ProcessId
                })
                if ($known.Count -ne 1) {
                    $detail = $child | Select-Object ProcessId, ParentProcessId, CreationDate, ExecutablePath, CommandLine |
                        ConvertTo-Json -Compress
                    throw "Descendencia no acreditada del PID ${targetPid}; se preserva el proceso: $detail"
                }
                if (-not (Test-EngineProcessSnapshot $known[0] $child)) { $pending = $true }
            }
            if (-not $pending) { break }
            if ((Get-Date) -ge $deadline) {
                $detail = @($current) + @($children) |
                    Select-Object ProcessId, ParentProcessId, CreationDate, ExecutablePath, CommandLine |
                    ConvertTo-Json -Compress
                throw "No se pudo acreditar identidad/descendencia del PID $targetPid antes de señalarlo: $detail"
            }
            Start-Sleep -Milliseconds 250
        } while ($true)
        if (-not $current) { continue }
        if ((Get-Date) -ge $deadline) {
            throw "Tiempo agotado antes de señalar el PID $targetPid; se preserva el registro."
        }
        try {
            Stop-Process -Id $targetPid -Force -ErrorAction Stop
        } catch {
            # A venv launcher can exit itself when its interpreter exits.
            $remaining = Get-CimInstance Win32_Process -Filter "ProcessId = $targetPid" -ErrorAction Stop
            if ($remaining) { throw "No se pudo detener el PID verificado ${targetPid}: $_" }
        }
        $hasStoppedProcess = $true
        # Stop-Process returns before CIM has necessarily removed the exiting
        # interpreter. Wait before revalidating its launcher or console host.
        Wait-EngineProcessExit $expected $deadline
    }
    do {
        $alive = $false
        foreach ($expected in $processes) {
            $targetPid = [int]$expected.ProcessId
            $current = Get-CimInstance Win32_Process -Filter "ProcessId = $targetPid" -ErrorAction Stop
            if ($current) {
                if (-not (Test-EngineProcessSnapshot $expected $current)) {
                    # CIM can briefly expose a terminating PID without its
                    # executable/command line. No further signals are sent in
                    # this loop; incomplete metadata means await confirmation.
                    $expectedStamp = ConvertTo-EngineCreationStamp $expected.CreationDate
                    $currentStamp = ConvertTo-EngineCreationStamp $current.CreationDate
                    if ($expectedStamp -and $currentStamp -and $expectedStamp.precise -and
                        $currentStamp.precise -and $expectedStamp.ticks -ne $currentStamp.ticks) {
                        throw "El PID $targetPid fue reutilizado durante la parada; se preserva el registro."
                    }
                }
                $alive = $true
            }
        }
        $portBusy = [bool](& $PortOpen)
        if (-not $alive -and -not $portBusy) { return }
        if ((Get-Date) -ge $deadline) { break }
        Start-Sleep -Milliseconds 250
    } while ($true)
    if ($alive) { throw 'Tiempo agotado: no se pudo acreditar la salida de todos los PID del motor.' }
    throw 'Los PID Musicia terminaron, pero el puerto sigue ocupado; no se toca su propietario.'
}
