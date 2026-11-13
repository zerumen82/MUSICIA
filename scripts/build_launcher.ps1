# Compila el lanzador Musicia.exe (Windows, sin instalar nada).
#
# La versión sale de frontend/package.json: un solo sitio donde se cambia.
# El EXE lleva esa versión en sus propiedades de archivo, así que Windows
# la muestra en la pestaña de detalles.
#
#   powershell -ExecutionPolicy Bypass -File scripts\build_launcher.ps1
#
# El EXE NO arranca la app: solo ejecuta scripts\open_musicia.ps1.

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$launcher = Join-Path $root 'scripts\launcher'
$csc = Join-Path $env:WINDIR 'Microsoft.NET\Framework64\v4.0.30319\csc.exe'
$icon = Join-Path $root 'frontend\build\icon.ico'
$exe = Join-Path $root 'Musicia.exe'
$generated = Join-Path $launcher 'AssemblyInfo.cs'

if (-not (Test-Path $csc)) { throw "No se encontró el compilador de .NET: $csc" }
if (-not (Test-Path $icon)) { throw "No se encontró el icono: $icon" }

$pkg = Get-Content (Join-Path $root 'frontend\package.json') -Raw | ConvertFrom-Json
$version = [string]$pkg.version
if (-not $version) { throw 'frontend/package.json no declara versión.' }

# El archivo de atributos se genera: la versión no vive escrita en el código.
@"
// Generado por scripts\build_launcher.ps1. No editar a mano.
using System.Reflection;

[assembly: AssemblyTitle("Musicia")]
[assembly: AssemblyProduct("Musicia")]
[assembly: AssemblyDescription("Lanzador de Musicia: música con IA en local.")]
[assembly: AssemblyCompany("Musicia")]
[assembly: AssemblyVersion("$version")]
[assembly: AssemblyFileVersion("$version")]
"@ | Set-Content -Path $generated -Encoding UTF8

& $csc /target:winexe /optimize+ /nologo "/out:$exe" /r:System.Windows.Forms.dll "/win32icon:$icon" $generated (Join-Path $launcher 'Launcher.cs')
if ($LASTEXITCODE -ne 0) { throw "csc terminó con $LASTEXITCODE" }

$info = (Get-Item $exe).VersionInfo
# Get-FileHash no existe en todos los PowerShell soportados (en este equipo
# devuelve "no se reconoce"): el hash se calcula con .NET, sin módulos.
$sha = [System.Security.Cryptography.SHA256]::Create()
$stream = [System.IO.File]::OpenRead($exe)
try { $hash = ([BitConverter]::ToString($sha.ComputeHash($stream))).Replace('-', '') }
finally { $stream.Dispose(); $sha.Dispose() }
Write-Host "EXE           : $exe"
Write-Host "Tamaño        : $((Get-Item $exe).Length) bytes"
Write-Host "FileVersion   : $($info.FileVersion)"
Write-Host "ProductVersion: $($info.ProductVersion)"
Write-Host "SHA-256       : $hash"
