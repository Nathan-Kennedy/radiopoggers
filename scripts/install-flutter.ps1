# Instala Flutter SDK (stable) em %LOCALAPPDATA%\flutter e adiciona ao PATH do usuario.
$ErrorActionPreference = "Stop"
$flutterRoot = Join-Path $env:LOCALAPPDATA "flutter"
$flutterBin = Join-Path $flutterRoot "bin"

if (-not (Test-Path (Join-Path $flutterBin "flutter.bat"))) {
  if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    throw "Git nao encontrado. Instale Git for Windows primeiro."
  }
  Write-Host "Clonando Flutter stable em $flutterRoot ..."
  if (Test-Path $flutterRoot) {
    Remove-Item $flutterRoot -Recurse -Force
  }
  git clone https://github.com/flutter/flutter.git -b stable --depth 1 $flutterRoot
}

$env:Path = "$flutterBin;" + [Environment]::GetEnvironmentVariable("Path", "User")
if ($env:Path -notlike "*$flutterBin*") {
  [Environment]::SetEnvironmentVariable(
    "Path",
    "$flutterBin;" + [Environment]::GetEnvironmentVariable("Path", "User"),
    "User"
  )
  Write-Host "[ok] PATH do usuario atualizado: $flutterBin"
}

& (Join-Path $flutterBin "flutter.bat") config --enable-windows-desktop | Out-Null
& (Join-Path $flutterBin "flutter.bat") --version
Write-Host ""
Write-Host "Feche e reabra o terminal (ou o Cursor) para o PATH valer em novas sessoes."
Write-Host "Depois: .\scripts\start-app-dev.ps1"
