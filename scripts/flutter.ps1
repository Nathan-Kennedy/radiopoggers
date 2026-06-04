# Atalho: sempre usa o Flutter em %LOCALAPPDATA%\flutter (mesmo se o PATH ainda nao atualizou).
$ErrorActionPreference = "Stop"
$flutterBat = Join-Path $env:LOCALAPPDATA "flutter\bin\flutter.bat"
if (-not (Test-Path $flutterBat)) {
  Write-Host "Flutter nao encontrado. Rode: .\scripts\install-flutter.ps1"
  exit 1
}
& $flutterBat @args
exit $LASTEXITCODE
