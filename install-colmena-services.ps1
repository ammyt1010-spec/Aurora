#Requires -RunAsAdministrator
$ErrorActionPreference = "Stop"

# ============================================================================
#  Instala Aurora como servicios de Windows (se ejecuta UNA sola vez).
#  Correr en una consola PowerShell "Ejecutar como administrador".
#
#  Los servicios NO dependen de tu sesion: al cerrar SSH siguen corriendo.
#  Todos arrancan solos al bootear la maquina (Automatic).
#
#  Servicios que crea:
#    colmena-postgres   -> PostgreSQL (via pg_ctl register)
#    colmena-backend    -> uvicorn app.main:app  (puerto 8002)
#    colmena-frontend   -> vite                  (puerto 5175)
#    colmena-tunnel     -> cloudflared quick tunnel -> localhost:5175
# ============================================================================

# --- rutas (ajusta si cambian) ---------------------------------------------
$PgCtl    = "D:\APPTHESIS\.tools\pgsql\bin\pg_ctl.exe"
$PgData   = "D:\APPTHESIS\.tools\pgsql\data"
$Backend  = "D:\Colmena2.0\backend"
$Frontend = "D:\Colmena2.0\frontend"
$LogDir   = "D:\Colmena2.0\logs"

$PgSvc       = "colmena-postgres"
$BackendSvc  = "colmena-backend"
$FrontendSvc = "colmena-frontend"
$TunnelSvc   = "colmena-tunnel"

New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

# --- localizar binarios ----------------------------------------------------
function Resolve-Bin($name, $hint) {
    $c = Get-Command $name -ErrorAction SilentlyContinue
    if (-not $c) { throw "'$name' no esta en el PATH. $hint" }
    return $c.Source
}

# nssm: primero una copia local del proyecto, luego el PATH
$LocalNssm = Join-Path $PSScriptRoot ".tools\nssm.exe"
if (Test-Path $LocalNssm) {
    $Nssm = $LocalNssm
} else {
    $c = Get-Command nssm -ErrorAction SilentlyContinue
    if (-not $c) {
        throw "No se encontro nssm. Descargalo con el bloque del README a $LocalNssm, o instala con 'winget install --id NSSM.NSSM -e'."
    }
    $Nssm = $c.Source
}
Write-Host "  nssm: $Nssm"

$Cloudflared = Resolve-Bin "cloudflared" "Descargalo de https://github.com/cloudflare/cloudflared/releases/latest"
$Node        = Resolve-Bin "node"        "Instala Node.js (el instalador lo agrega al PATH de la maquina)."
$Poetry      = Resolve-Bin "poetry"      "Instala poetry: https://python-poetry.org/docs/#installation"

if (-not (Test-Path $PgCtl))  { throw "No existe $PgCtl" }
if (-not (Test-Path $PgData)) { throw "No existe $PgData" }
if (-not (Test-Path (Join-Path $Backend ".env"))) {
    Write-Host "AVISO: no hay $Backend\.env - el backend puede fallar al leer la config/DB." -ForegroundColor Yellow
}

# ============================================================================
#  1) PostgreSQL como servicio
# ============================================================================
Write-Host "[1/4] PostgreSQL..." -ForegroundColor Cyan
$pg = Get-Service -Name $PgSvc -ErrorAction SilentlyContinue
if (-not $pg) {
    # si quedo corriendo en modo standalone (pg_ctl start), detenerlo antes de registrar
    & $PgCtl -D $PgData status *> $null
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  deteniendo instancia standalone previa..."
        & $PgCtl -D $PgData stop -m fast
        Start-Sleep -Seconds 2
    }
    & $PgCtl register -N $PgSvc -D $PgData -S auto
    Start-Sleep -Seconds 1
    Write-Host "  servicio $PgSvc registrado."
} else {
    Write-Host "  servicio $PgSvc ya existe."
}
Set-Service -Name $PgSvc -StartupType Automatic
try { Start-Service $PgSvc } catch {
    Write-Host "  no se pudo iniciar $PgSvc. Si es por permisos, da control total sobre" -ForegroundColor Yellow
    Write-Host "  $PgData a la cuenta 'NT AUTHORITY\NetworkService' y reintenta." -ForegroundColor Yellow
    throw
}

# ============================================================================
#  2) Backend: venv in-project para no depender de poetry en el servicio
# ============================================================================
Write-Host "[2/4] Backend (venv + servicio)..." -ForegroundColor Cyan
Push-Location $Backend
& $Poetry config virtualenvs.in-project true --local
& $Poetry install
Pop-Location

$PyExe = Join-Path $Backend ".venv\Scripts\python.exe"
if (-not (Test-Path $PyExe)) { throw "No se creo el venv: $PyExe" }

# ============================================================================
#  3) Frontend: node_modules
# ============================================================================
$ViteJs = Join-Path $Frontend "node_modules\vite\bin\vite.js"
if (-not (Test-Path $ViteJs)) {
    Write-Host "[3/4] Frontend: npm install..." -ForegroundColor Cyan
    Push-Location $Frontend
    npm install
    Pop-Location
}
if (-not (Test-Path $ViteJs)) { throw "No se instalo vite: $ViteJs" }

# ============================================================================
#  helper NSSM
# ============================================================================
function Install-NssmService {
    param($Name, $App, $Params, $Dir, $DependsOn)

    $svc = Get-Service -Name $Name -ErrorAction SilentlyContinue
    if ($svc) {
        Write-Host "  recreando servicio $Name..."
        & $Nssm stop $Name confirm *> $null
        & $Nssm remove $Name confirm | Out-Null
        Start-Sleep -Seconds 1
    }

    & $Nssm install $Name $App $Params
    & $Nssm set $Name AppDirectory $Dir
    & $Nssm set $Name Start SERVICE_AUTO_START
    & $Nssm set $Name AppStdout "$LogDir\$Name.log"
    & $Nssm set $Name AppStderr "$LogDir\$Name.log"
    & $Nssm set $Name AppStdoutCreationDisposition 4   # append
    & $Nssm set $Name AppStderrCreationDisposition 4
    & $Nssm set $Name AppRotateFiles 1
    & $Nssm set $Name AppRotateOnline 1
    & $Nssm set $Name AppRotateBytes 10485760
    & $Nssm set $Name AppExit Default Restart
    & $Nssm set $Name AppRestartDelay 5000
    & $Nssm set $Name AppStopMethodConsole 3000
    if ($DependsOn) { & $Nssm set $Name DependOnService $DependsOn }
}

# ============================================================================
#  2b) servicio backend
# ============================================================================
Install-NssmService -Name $BackendSvc -App $PyExe `
    -Params "-m uvicorn app.main:app --host 0.0.0.0 --port 8002" `
    -Dir $Backend -DependsOn $PgSvc

# ============================================================================
#  3b) servicio frontend
# ============================================================================
Install-NssmService -Name $FrontendSvc -App $Node `
    -Params "`"$ViteJs`" --host 0.0.0.0 --port 5175 --strictPort" `
    -Dir $Frontend

# ============================================================================
#  4) servicio cloudflared
# ============================================================================
Write-Host "[4/4] Cloudflare Tunnel..." -ForegroundColor Cyan
Install-NssmService -Name $TunnelSvc -App $Cloudflared `
    -Params "tunnel --url http://localhost:5175 --no-autoupdate" `
    -Dir $LogDir

Write-Host ""
Write-Host "=====================================================" -ForegroundColor Green
Write-Host " Servicios instalados. Ahora usa:"
Write-Host "   .\start-colmena.ps1   -> arranca todo y muestra la URL"
Write-Host "   .\stop-colmena.ps1    -> detiene todo"
Write-Host " Sobreviven al cierre de SSH y al reinicio de la maquina."
Write-Host "=====================================================" -ForegroundColor Green
