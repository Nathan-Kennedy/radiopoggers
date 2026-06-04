# Rode da raiz do repo: .\scripts\flutter-pub-get.ps1
$ErrorActionPreference = "Stop"
$root = Split-Path $PSScriptRoot -Parent
$app = Join-Path $root "apps\radiopoggers_app"
if (-not (Test-Path (Join-Path $app "pubspec.yaml"))) {
  Write-Error "pubspec.yaml nao encontrado em $app"
}
Push-Location $app
try {
  flutter pub get
  if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
  Write-Host "[ok] Dependencias em $app"
}
finally {
  Pop-Location
}
