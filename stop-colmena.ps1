# ============================================================================
#  Detiene los servicios de Aurora. PostgreSQL se deja corriendo por
#  defecto (es un servicio, no molesta). Usa -All para detenerlo tambien.
# ============================================================================
param([switch]$All)

$ErrorActionPreference = "SilentlyContinue"

$Order = @("colmena-tunnel", "colmena-frontend", "colmena-backend")
if ($All) { $Order += "colmena-postgres" }

foreach ($s in $Order) {
    $svc = Get-Service -Name $s -ErrorAction SilentlyContinue
    if (-not $svc) { Write-Host "$s no instalado"; continue }
    if ($svc.Status -eq 'Running') {
        Stop-Service $s -Force
        Write-Host "Detenido $s"
    } else {
        Write-Host "$s ya estaba detenido"
    }
}

$pidFile = Join-Path $PSScriptRoot "run\cloudflared.pid"
if (Test-Path $pidFile) {
    $tunnelPid = Get-Content $pidFile -ErrorAction SilentlyContinue
    $tunnelProcess = Get-Process -Id $tunnelPid -ErrorAction SilentlyContinue
    if ($tunnelProcess -and $tunnelProcess.ProcessName -eq 'cloudflared') {
        Stop-Process -Id $tunnelProcess.Id -Force
        Write-Host "Detenido tunnel temporal Aurora"
    }
    Remove-Item -LiteralPath $pidFile -Force -ErrorAction SilentlyContinue
}
