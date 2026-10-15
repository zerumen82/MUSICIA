<# Capture the existing verifier window during the real final CPU decode. #>
param(
    [Parameter(Mandatory=$true)][int]$WindowProcessId,
    [Parameter(Mandatory=$true)][string]$JobId,
    [Parameter(Mandatory=$true)][string]$OutputDirectory,
    [string]$Api = 'http://127.0.0.1:8000'
)
$ErrorActionPreference = 'Stop'
if (([uri]$Api).Host -notin @('127.0.0.1','localhost')) { throw 'Local API required' }
$processInfo = Get-CimInstance Win32_Process -Filter "ProcessId = $WindowProcessId"
if (-not $processInfo -or $processInfo.Name -ne 'electron.exe' -or $processInfo.CommandLine -notmatch 'probe_plan_completion_ui\.cjs') {
    throw 'PID is not the existing Musicia verification window'
}
function Decode-State {
    $state = Invoke-RestMethod -Uri ($Api + '/audio/remix/ai/' + $JobId) -TimeoutSec 10
    if ($state.status -ne 'running' -or $state.phase -ne 'Convirtiendo a audio' -or
        $null -ne $state.progress_ratio -or $state.engine_progress -ne 0.8) {
        throw 'The expected final decode phase (running, null display progress, raw 0.8) is not active'
    }
    return $state
}
$before = Decode-State
Add-Type -AssemblyName System.Drawing
if (-not ('MusiciaDecodeCaptureNative' -as [type])) {
    Add-Type @'
using System;
using System.Runtime.InteropServices;
public static class MusiciaDecodeCaptureNative {
    [StructLayout(LayoutKind.Sequential)] public struct Rect { public int Left, Top, Right, Bottom; }
    [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out Rect r);
    [DllImport("user32.dll")] public static extern bool GetClientRect(IntPtr h, out Rect r);
    [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr h);
    [DllImport("user32.dll")] public static extern bool PrintWindow(IntPtr h, IntPtr dc, uint flags);
}
'@
}
$window = Get-Process -Id $WindowProcessId
$handle = $window.MainWindowHandle
if ($handle -eq [IntPtr]::Zero -or -not [MusiciaDecodeCaptureNative]::IsWindowVisible($handle) -or [string]::IsNullOrWhiteSpace($window.MainWindowTitle)) {
    throw 'The verifier window is not visible with a real title'
}
$bounds = New-Object MusiciaDecodeCaptureNative+Rect
$client = New-Object MusiciaDecodeCaptureNative+Rect
if (-not [MusiciaDecodeCaptureNative]::GetWindowRect($handle,[ref]$bounds) -or
    -not [MusiciaDecodeCaptureNative]::GetClientRect($handle,[ref]$client)) { throw 'Window geometry unavailable' }
$width = $bounds.Right - $bounds.Left
$height = $bounds.Bottom - $bounds.Top
if ($width -le 0 -or $height -le 0 -or $client.Right -le 0 -or $client.Bottom -le 0) { throw 'Empty window geometry' }
$bitmap = New-Object System.Drawing.Bitmap($width,$height)
$graphics = [System.Drawing.Graphics]::FromImage($bitmap)
function Frame-Has-Pixels {
    # Sample inside the client body: a rendered title bar alone must not
    # turn a black Chromium client frame into screenshot evidence.
    for ($x=[int]($width / 10); $x -lt [int]($width * 0.9); $x += [Math]::Max(1,[int]($width / 100))) {
        for ($y=[int]($height / 10); $y -lt [int]($height * 0.9); $y += [Math]::Max(1,[int]($height / 100))) {
            $pixel = $bitmap.GetPixel($x,$y)
            if ([Math]::Max($pixel.R,[Math]::Max($pixel.G,$pixel.B)) -gt 4) { return $true }
        }
    }
    return $false
}
try {
    $dc = $graphics.GetHdc()
    try { $printed = [MusiciaDecodeCaptureNative]::PrintWindow($handle,$dc,2) }
    finally { $graphics.ReleaseHdc($dc) }
    $method = 'PrintWindow'
    if (-not $printed -or -not (Frame-Has-Pixels)) {
        $graphics.CopyFromScreen($bounds.Left,$bounds.Top,0,0,(New-Object System.Drawing.Size($width,$height)))
        $method = 'CopyFromScreen-window-rectangle'
    }
    if (-not (Frame-Has-Pixels)) { throw 'Captured frame is black; no screenshot evidence saved' }
    $after = Decode-State
    $null = New-Item -ItemType Directory -Path $OutputDirectory -Force
    $target = Join-Path $OutputDirectory 'decode-final-live.png'
    $bitmap.Save($target,[System.Drawing.Imaging.ImageFormat]::Png)
    $evidence = @{ status='PASS'; captured_at=(Get-Date).ToString('o'); process_id=$WindowProcessId;
        title=$window.MainWindowTitle; method=$method; image=$target; before=$before; after=$after;
        bounds=@{left=$bounds.Left;top=$bounds.Top;width=$width;height=$height} }
    $evidence | ConvertTo-Json -Depth 30 | Set-Content -LiteralPath (Join-Path $OutputDirectory 'decode-final-live.json') -Encoding utf8
    Write-Output "CAPTURE=PASS IMAGE=$target"
} finally { $graphics.Dispose(); $bitmap.Dispose() }
