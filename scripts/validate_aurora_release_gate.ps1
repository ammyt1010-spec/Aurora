#requires -Version 5.1
<#
.SYNOPSIS
  AURORA Professional: validación local no destructiva de la rama actual.
.DESCRIPTION
  Ejecuta las suites completas de backend, la revisión de migraciones Alembic,
  Vitest, ESLint y build de Vite. Registra la transcripción en TEMP.
  No fusiona ramas, no aplica migraciones ni altera datos productivos.
.EXAMPLE
  powershell -ExecutionPolicy Bypass -File .\scripts\validate_aurora_release_gate.ps1
.EXAMPLE
  powershell -ExecutionPolicy Bypass -File .\scripts\validate_aurora_release_gate.ps1 -CheckRunningUI
#>
param([switch]$CheckRunningUI)

$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$backend = Join-Path $root "backend"
$frontend = Join-Path $root "frontend"
$python = Join-Path $backend ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) { throw "No se encontró Python venv: $python" }

$npmCommand = Get-Command npm.cmd -ErrorAction SilentlyContinue
if ($npmCommand) {
    $npm = $npmCommand.Source
} else {
    $npm = "D:\APPTHESIS\.tools\node-v24.18.0-win-x64\npm.cmd"
    if (-not (Test-Path $npm)) { throw "No se encontró npm.cmd. Instala Node o agrega npm a PATH." }
}

$log = Join-Path $env:TEMP ("aurora-validation-{0}.log" -f (Get-Date -Format "yyyyMMdd-HHmmss"))
function Run-Step {
    param([string]$Name, [string]$Directory, [string]$Executable, [string[]]$CommandArguments)
    Write-Host ""
    Write-Host ("==== {0} ====" -f $Name) -ForegroundColor Cyan
    Push-Location $Directory
    try {
        & $Executable @CommandArguments
        if ($LASTEXITCODE -ne 0) {
            throw ("El paso {0} falló con código {1}" -f $Name, $LASTEXITCODE)
        }
        Write-Host ("APROBADO: {0}" -f $Name) -ForegroundColor Green
    } finally {
        Pop-Location
    }
}

Start-Transcript -Path $log -Force | Out-Null
try {
    Write-Host "AURORA Professional - release gate local" -ForegroundColor Cyan
    Write-Host "Repositorio: $root"
    Write-Host "Rama y commit:"
    & git -C $root log -1 --format="%h %s"
    & git -C $root status --short

    Run-Step "Backend unitarias + integración" $backend $python @("-m", "pytest", "app/tests/unit", "app/tests/integration", "-q")
    Run-Step "Estado migraciones Alembic (solo lectura)" $backend $python @("-m", "alembic", "current")
    Run-Step "Frontend Vitest" $frontend $npm @("test")
    Run-Step "Frontend ESLint" $frontend $npm @("run", "lint")
    Run-Step "Frontend Vite build" $frontend $npm @("run", "build")

    if ($CheckRunningUI) {
        Write-Host "==== HTTP smoke ====" -ForegroundColor Cyan
        $api = Invoke-WebRequest -Uri "http://127.0.0.1:8003/health" -UseBasicParsing -TimeoutSec 10
        $ui = Invoke-WebRequest -Uri "http://127.0.0.1:5177/" -UseBasicParsing -TimeoutSec 10
        if ($api.StatusCode -ne 200 -or $ui.StatusCode -ne 200) {
            throw "Health HTTP no satisfactorio"
        }
        Write-Host "APROBADO: backend 8003 y frontend 5177" -ForegroundColor Green
    }
    Write-Host ""
    Write-Host "GATE LOCAL APROBADO. Revisar también navegador, privacidad y PDF/DOCX reales." -ForegroundColor Green
} finally {
    Stop-Transcript | Out-Null
    Write-Host "Registro local: $log"
}
