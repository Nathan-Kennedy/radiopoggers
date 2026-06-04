# Build APK do app Flutter para Android.
$ErrorActionPreference = "Stop"
$root = Split-Path $PSScriptRoot -Parent
$appDir = Join-Path $root "apps\radiopoggers_app"

& (Join-Path $root "scripts\sync-app-assets.ps1")

if (-not (Get-Command flutter -ErrorAction SilentlyContinue)) {
  throw "Flutter nao encontrado no PATH."
}

if (-not (Test-Path (Join-Path $appDir "android"))) {
  Push-Location $appDir
  try { flutter create . --platforms=android }
  finally { Pop-Location }
}

Push-Location $appDir
try {
  flutter pub get
  flutter build apk --release
  Write-Host ""
  Write-Host "[ok] APK em:"
  Write-Host "  $appDir\build\app\outputs\flutter-apk\app-release.apk"
}
finally {
  Pop-Location
}
