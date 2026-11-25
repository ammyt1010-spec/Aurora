# Starts the permanent AURORA public targets after Windows sign-in.
$ErrorActionPreference = 'Stop'
$workspace = Split-Path -Parent $PSScriptRoot
$backend = Join-Path $workspace 'backend'
$settingsFile = Join-Path $backend '.env.public'
$python = Join-Path $backend '.venv\Scripts\python.exe'
$node = 'D:\APPTHESIS\.tools\node-v24.18.0-win-x64\node.exe'
if (-not (Test-Path -LiteralPath $node)) { $node = (Get-Command node -ErrorAction Stop).Source }
if (-not (Test-Path -LiteralPath $python)) { throw 'Falta el entorno Python de AURORA.' }
if (-not (Test-Path -LiteralPath $settingsFile)) { throw 'Falta la configuración privada de AURORA.' }

$publicEnvironment = @{}
Get-Content -LiteralPath $settingsFile | Where-Object { $_ -match '^[A-Z_]+=' } | ForEach-Object {
  $parts = $_ -split '=', 2
  $publicEnvironment[$parts[0]] = $parts[1]
}

if (-not (Get-NetTCPConnection -LocalAddress 127.0.0.1 -LocalPort 8004 -State Listen -ErrorAction SilentlyContinue)) {
  Start-Process -FilePath $python -ArgumentList @('-m','uvicorn','app.main:app','--host','127.0.0.1','--port','8004') `
    -WorkingDirectory $backend -Environment $publicEnvironment -WindowStyle Hidden `
    -RedirectStandardOutput (Join-Path $env:TEMP 'aurora-public-api.out.log') `
    -RedirectStandardError (Join-Path $env:TEMP 'aurora-public-api.err.log')
}
if (-not (Get-NetTCPConnection -LocalAddress 127.0.0.1 -LocalPort 8090 -State Listen -ErrorAction SilentlyContinue)) {
  Start-Process -FilePath $node -ArgumentList @(Join-Path $PSScriptRoot 'aurora-public-server.mjs') `
    -WorkingDirectory $workspace -Environment @{ AURORA_PUBLIC_PORT='8090'; AURORA_PUBLIC_API_PORT='8004' } `
    -WindowStyle Hidden -RedirectStandardOutput (Join-Path $env:TEMP 'aurora-public-web.out.log') `
    -RedirectStandardError (Join-Path $env:TEMP 'aurora-public-web.err.log')
}
if (-not (Get-NetTCPConnection -LocalAddress 127.0.0.1 -LocalPort 8302 -State Listen -ErrorAction SilentlyContinue)) {
  Start-Process -FilePath $node -ArgumentList @(Join-Path $PSScriptRoot 'aurora-public-server.mjs') `
    -WorkingDirectory $workspace -Environment @{ AURORA_PUBLIC_PORT='8302'; AURORA_PUBLIC_API_PORT='8004'; AURORA_PUBLIC_BASE_PATH='' } `
    -WindowStyle Hidden -RedirectStandardOutput (Join-Path $env:TEMP 'aurora-domain-web.out.log') `
    -RedirectStandardError (Join-Path $env:TEMP 'aurora-domain-web.err.log')
}
