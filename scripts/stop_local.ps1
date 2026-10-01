<#
Detiene los procesos locales de Musicia (motor ACE-Step y API).
#>
$ErrorActionPreference = 'SilentlyContinue'

$objetivos = @(
    @{ Nombre = 'Musicia API';  Filtro = 'main.py' },
    @{ Nombre = 'ACE-Step';    Filtro = 'acestep.api_server' }
)

foreach ($objetivo in $objetivos) {
    $procesos = Get-CimInstance Win32_Process -Filter "Name = 'python.exe'" |
        Where-Object { $_.CommandLine -like "*$($objetivo.Filtro)*" }

    if (-not $procesos) {
        Write-Host "[$($objetivo.Nombre)] no estaba corriendo"
        continue
    }
    foreach ($proceso in $procesos) {
        Stop-Process -Id $proceso.ProcessId -Force
        Write-Host "[$($objetivo.Nombre)] detenido (PID $($proceso.ProcessId))"
    }
}