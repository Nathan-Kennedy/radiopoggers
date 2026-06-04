# Sobe API local (se necessario) e executa o app Flutter no Windows.
$ErrorActionPreference = "Stop"
$scriptsDir = $PSScriptRoot
$root = Split-Path $scriptsDir -Parent

. (Join-Path $scriptsDir "process-lib.ps1")
$appDir = Join-Path $root "apps\radiopoggers_app"

& (Join-Path $root "scripts\sync-app-assets.ps1")

$flutterBin = Join-Path $env:LOCALAPPDATA "flutter\bin"
if (Test-Path (Join-Path $flutterBin "flutter.bat")) {
  $env:Path = "$flutterBin;" + $env:Path
}
$flutter = Get-Command flutter -ErrorAction SilentlyContinue
if (-not $flutter) {
  Write-Host "Flutter nao encontrado. Instalando em %LOCALAPPDATA%\flutter ..."
  & (Join-Path $root "scripts\install-flutter.ps1")
  $env:Path = "$flutterBin;" + $env:Path
  $flutter = Get-Command flutter -ErrorAction SilentlyContinue
  if (-not $flutter) {
    Write-Host "Reabra o terminal e rode: .\scripts\install-flutter.ps1"
    exit 1
  }
}

if (-not (Test-Path (Join-Path $appDir "windows"))) {
  Write-Host "Gerando pastas de plataforma (flutter create)..."
  Push-Location $appDir
  try {
    flutter create . --platforms=windows,android
  }
  finally {
    Pop-Location
  }
}

$apiUp = $false
try {
  $r = Invoke-WebRequest -Uri "http://127.0.0.1:8765/api/health" -UseBasicParsing -TimeoutSec 2
  $apiUp = $r.StatusCode -eq 200
}
catch {}

if (-not $apiUp) {
  Write-Host "Subindo API local em segundo plano..."
  $apiScript = Join-Path $scriptsDir "start-local-api.ps1"
  $escaped = $apiScript -replace "'", "''"
  Start-HiddenPowerShellScript `
    -Command "& '$escaped'" `
    -WorkingDirectory $root `
    -ProjectRoot $root `
    -LogName "local-api"
  Start-Sleep -Seconds 4
}

Push-Location $appDir
try {
  flutter pub get
  flutter run -d windows
}
finally {
  Pop-Location
}
