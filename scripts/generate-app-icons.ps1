# Gera icones Android (mipmap) e Windows (.ico) a partir de frontend/assets/icons/icon.png
$ErrorActionPreference = "Stop"
$root = Split-Path $PSScriptRoot -Parent
$icon = Join-Path $root "frontend\assets\icons\icon.png"
$appDir = Join-Path $root "apps\radiopoggers_app"

if (-not (Test-Path $icon)) {
  throw "Icone nao encontrado: $icon"
}

if (-not (Get-Command flutter -ErrorAction SilentlyContinue)) {
  throw "Flutter nao encontrado no PATH."
}

Push-Location $appDir
try {
  flutter pub get
  dart run flutter_launcher_icons
  Write-Host ""
  Write-Host "[ok] Icones gerados para Android e Windows."
  Write-Host "  Fonte: $icon"
}
finally {
  Pop-Location
}
