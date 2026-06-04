# Build release do app Flutter para Windows.
$ErrorActionPreference = "Stop"
$root = Split-Path $PSScriptRoot -Parent
$appDir = Join-Path $root "apps\radiopoggers_app"

& (Join-Path $root "scripts\sync-app-assets.ps1")

if (-not (Get-Command flutter -ErrorAction SilentlyContinue)) {
  throw "Flutter nao encontrado no PATH."
}

if (-not (Test-Path (Join-Path $appDir "windows"))) {
  Push-Location $appDir
  try { flutter create . --platforms=windows,android }
  finally { Pop-Location }
}

Push-Location $appDir
try {
  flutter pub get
  flutter build windows --release
  Write-Host ""
  Write-Host "[ok] Executavel em:"
  Write-Host "  $appDir\build\windows\x64\runner\Release\radiopoggers_app.exe"
}
finally {
  Pop-Location
}
