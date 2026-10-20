$ErrorActionPreference = "Stop"

# ============================================================================
#  Arranca los servicios de Aurora y muestra la URL publica del tunnel.
#  Requiere haber corrido install-colmena-services.ps1 UNA vez (como admin).
#  Los servicios corren fuera de tu sesion: puedes cerrar SSH sin problema.
# ============================================================================

$LogDir  = "D:\Colmena2.0\logs"
$Tunnel  = "colmena-tunnel"
$Order   = @("colmena-postgres", "colmena-backend", "colmena-frontend")

foreach ($s in $Order) {
    $svc = Get-Service -Name $s -ErrorAction SilentlyContinue
    if (-not $svc) {
        Write-Host "Servicio '$s' no instalado." -ForegroundColor Red
        Write-Host "Corre primero (como administrador):  .\install-colmena-services.ps1" -ForegroundColor Red
        exit 1
    }
}

foreach ($s in $Order) {
    $svc = Get-Service -Name $s
    if ($svc.Status -ne 'Running') {
        Start-Service $s
        Write-Host "Iniciado  $s" -ForegroundColor Green
    } else {
        Write-Host "Ya activo $s"
    }
}

# El túnel puede estar instalado como servicio o ejecutarse en modo revisión.
# El segundo camino permite publicar la demo sin credenciales de administrador.
$t = Get-Service -Name $Tunnel -ErrorAction SilentlyContinue
$log = "$LogDir\$Tunnel.log"
if ($t -and $t.StartType -ne 'Disabled') {
    if ($t.Status -eq 'Running') { Stop-Service $Tunnel; Start-Sleep -Seconds 1 }
    if (Test-Path $log) { Clear-Content $log -ErrorAction SilentlyContinue }
    Start-Service $Tunnel
    Write-Host "Iniciado  $Tunnel" -ForegroundColor Green
} else {
    $cloudflared = (Get-Command cloudflared -ErrorAction Stop).Source
    $runDir = Join-Path $PSScriptRoot "run"
    $pidFile = Join-Path $runDir "cloudflared.pid"
    $log = Join-Path $LogDir "aurora-tunnel.err.log"
    New-Item -ItemType Directory -Force -Path $runDir | Out-Null
    if (Test-Path $pidFile) {
        $previousPid = Get-Content $pidFile -ErrorAction SilentlyContinue
        $previous = Get-Process -Id $previousPid -ErrorAction SilentlyContinue
        if ($previous -and $previous.ProcessName -eq 'cloudflared') { Stop-Process -Id $previous.Id -Force }
    }
    if (Test-Path $log) { Clear-Content $log -ErrorAction SilentlyContinue }
    $tunnelProcess = Start-Process -FilePath $cloudflared `
        -ArgumentList "tunnel", "--url", "http://127.0.0.1:5175", "--no-autoupdate" `
        -WorkingDirectory $PSScriptRoot -WindowStyle Hidden -PassThru `
        -RedirectStandardOutput (Join-Path $LogDir "aurora-tunnel.out.log") `
        -RedirectStandardError $log
    Set-Content -Path $pidFile -Value $tunnelProcess.Id
    Write-Host "Iniciado  tunnel temporal Aurora" -ForegroundColor Green
}

Write-Host ""
Write-Host "Esperando la URL publica del tunnel..."
$tunnelUrl = $null
for ($i = 0; $i -lt 30; $i++) {
    Start-Sleep -Seconds 1
    if (Test-Path $log) {
        $m = Select-String -Path $log -Pattern 'https://[a-zA-Z0-9\-]+\.trycloudflare\.com' -ErrorAction SilentlyContinue |
             Select-Object -Last 1
        if ($m) { $tunnelUrl = $m.Matches[0].Value; break }
    }
}

Write-Host ""
if ($tunnelUrl) {
    Write-Host "=====================================================" -ForegroundColor Green
    Write-Host " Aurora corriendo como servicios de Windows."
    Write-Host " URL publica:    $tunnelUrl"
    Write-Host " Backend local:  http://localhost:8002/docs"
    Write-Host " Frontend local: http://localhost:5175"
    Write-Host "=====================================================" -ForegroundColor Green
} else {
    Write-Host "No se detecto la URL del tunnel a tiempo. Revisa $log" -ForegroundColor Yellow
}
Write-Host ""
Write-Host "Logs en: $LogDir     Detener: .\stop-colmena.ps1"
