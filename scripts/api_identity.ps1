# Pure API ownership predicates. Loading this file never signals a process.

function Get-MusiciaApiScriptArgument([string]$CommandLine) {
    if (-not $CommandLine) { return $null }
    # Python executes the first script argument, optionally after -u. A path
    # mentioned after -c/-m or in later arguments does not establish ownership.
    $match = [regex]::Match($CommandLine,
        '^\s*(?:"(?<exe>[^"]+)"|(?<exe>[^"\s]+))\s+(?:-u\s+)?(?:"(?<script>[^"]+)"|(?<script>[^"\s]+))(?=\s|$)')
    if (-not $match.Success) { return $null }
    $executable = $match.Groups['exe'].Value.Replace('/', '\')
    if ([IO.Path]::GetFileName($executable) -notin @('python.exe', 'pythonw.exe')) {
        return $null
    }
    return $match.Groups['script'].Value
}

function Test-MusiciaApiCommandLine([string]$CommandLine, [string]$ProjectRoot) {
    $script = Get-MusiciaApiScriptArgument $CommandLine
    # IsPathRooted also accepts drive-relative paths such as C:backend/main.py.
    # Only drive-absolute or UNC paths are unambiguous on Windows.
    $absolute = '^(?:[A-Za-z]:[\\/]|\\\\[^\\/]+[\\/][^\\/]+[\\/])'
    if (-not $script -or $script -notmatch $absolute -or
        -not $ProjectRoot -or $ProjectRoot -notmatch $absolute) {
        return $false
    }
    try {
        $actual = [IO.Path]::GetFullPath($script.Replace('/', '\'))
        $expected = [IO.Path]::GetFullPath((Join-Path $ProjectRoot 'backend\main.py'))
    } catch {
        return $false
    }
    return [string]::Equals($actual, $expected, [StringComparison]::OrdinalIgnoreCase)
}

function Get-MusiciaApiCreationTicks($Value) {
    if ($Value -is [datetime]) { return [long]$Value.ToUniversalTime().Ticks }
    if ($Value -is [datetimeoffset]) { return [long]$Value.UtcTicks }
    if ($null -eq $Value) { return $null }
    $parsed = [datetime]::MinValue
    if ([datetime]::TryParseExact([string]$Value, 'o',
        [Globalization.CultureInfo]::InvariantCulture,
        [Globalization.DateTimeStyles]::RoundtripKind, [ref]$parsed)) {
        return [long]$parsed.ToUniversalTime().Ticks
    }
    return $null
}

function Test-MusiciaApiProcess($Process, [string]$ProjectRoot) {
    if ($null -eq $Process -or -not $Process.ExecutablePath -or
        -not $Process.CommandLine -or $null -eq $Process.CreationDate) {
        return $false
    }
    try {
        if ([int]$Process.ProcessId -le 0) { return $false }
        $name = [IO.Path]::GetFileName(([string]$Process.ExecutablePath).Replace('/', '\'))
        if ($name -notin @('python.exe', 'pythonw.exe')) { return $false }
        if ($null -eq (Get-MusiciaApiCreationTicks $Process.CreationDate)) { return $false }
        return Test-MusiciaApiCommandLine ([string]$Process.CommandLine) $ProjectRoot
    } catch {
        return $false
    }
}

function Test-MusiciaApiProcessSnapshot($Expected, $Actual, [string]$ProjectRoot) {
    if (-not (Test-MusiciaApiProcess $Expected $ProjectRoot) -or
        -not (Test-MusiciaApiProcess $Actual $ProjectRoot)) {
        return $false
    }
    return [int]$Expected.ProcessId -eq [int]$Actual.ProcessId -and
        (Get-MusiciaApiCreationTicks $Expected.CreationDate) -eq
            (Get-MusiciaApiCreationTicks $Actual.CreationDate) -and
        [string]::Equals([string]$Expected.ExecutablePath, [string]$Actual.ExecutablePath,
            [StringComparison]::OrdinalIgnoreCase) -and
        [string]$Expected.CommandLine -ceq [string]$Actual.CommandLine
}
