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
