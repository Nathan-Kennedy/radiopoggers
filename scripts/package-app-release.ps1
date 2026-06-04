# Empacota release do app para GitHub (zip Windows + APK + SHA256).
param(
  [switch]$SkipBuild
)

$ErrorActionPreference = "Stop"
$root = Split-Path $PSScriptRoot -Parent
$appDir = Join-Path $root "apps\radiopoggers_app"
$outDir = Join-Path $root "dist\app-release"
$stageDir = Join-Path $outDir "windows-stage"

& (Join-Path $root "scripts\sync-app-assets.ps1")

if (-not $SkipBuild) {
  if (-not (Get-Command flutter -ErrorAction SilentlyContinue)) {
    throw "Flutter nao encontrado no PATH."
  }
  Push-Location $appDir
  try {
    flutter pub get
    if (-not (Test-Path (Join-Path $appDir "windows"))) {
      flutter create . --platforms=windows,android
    }
    # Release publica: sem IP Radmin no binario (use --dart-define=RADIOPOGGERS_RADMIN_HOST=... so na sua maquina).
    flutter build windows --release
    flutter build apk --release
  }
  finally {
    Pop-Location
  }
}

$winRelease = Join-Path $appDir "build\windows\x64\runner\Release"
$apk = Join-Path $appDir "build\app\outputs\flutter-apk\app-release.apk"

if (-not (Test-Path $winRelease)) {
  throw "Build Windows nao encontrado: $winRelease"
}
if (-not (Test-Path $apk)) {
  throw "APK nao encontrado: $apk"
}

New-Item -ItemType Directory -Force -Path $outDir | Out-Null
if (Test-Path $stageDir) { Remove-Item $stageDir -Recurse -Force }
New-Item -ItemType Directory -Force -Path $stageDir | Out-Null

# Copia só o necessario para rodar — sem PDB (caminhos locais), sem pastas acidentais.
$excludeExt = @(".pdb", ".ilk", ".exp", ".lib")
Get-ChildItem $winRelease -File | ForEach-Object {
  if ($excludeExt -contains $_.Extension.ToLower()) { return }
  Copy-Item $_.FullName -Destination $stageDir
}
$dataDir = Join-Path $winRelease "data"
if (Test-Path $dataDir) {
  Copy-Item $dataDir -Destination (Join-Path $stageDir "data") -Recurse
}

$zipName = "RadioPoggers-Windows-x64.zip"
$zipPath = Join-Path $outDir $zipName
if (Test-Path $zipPath) { Remove-Item $zipPath -Force }
Compress-Archive -Path (Join-Path $stageDir "*") -DestinationPath $zipPath -Force

$apkDest = Join-Path $outDir "RadioPoggers-android.apk"
Copy-Item $apk $apkDest -Force

# Verificacao basica: nao deve haver chaves de API no pacote.
$forbidden = @(
  "gemini-api-key",
  "discord-bot-token",
  "azuracast-api-key",
  "spotify-api-credentials",
  "BEGIN PRIVATE KEY",
  "sk-",
  "api_key"
)
$scanRoot = @($stageDir, $apkDest)
foreach ($pattern in $forbidden) {
  foreach ($dir in $scanRoot) {
    if (-not (Test-Path $dir)) { continue }
    $hits = Get-ChildItem $dir -Recurse -File -ErrorAction SilentlyContinue |
      Where-Object { $_.Extension -match '\.(txt|json|env|pem|key|pfx)$' } |
      Select-String -Pattern $pattern -SimpleMatch -ErrorAction SilentlyContinue
    if ($hits) {
      throw "Possivel vazamento no pacote ($pattern). Revise antes de publicar."
    }
  }
}

$hashWin = (Get-FileHash $zipPath -Algorithm SHA256).Hash.ToLower()
$hashApk = (Get-FileHash $apkDest -Algorithm SHA256).Hash.ToLower()
$sums = @(
  "$hashWin  $zipName"
  "$hashApk  RadioPoggers-android.apk"
) -join "`n"
Set-Content -Path (Join-Path $outDir "SHA256SUMS.txt") -Value $sums -Encoding utf8

Write-Host ""
Write-Host "[ok] Release em: $outDir"
Write-Host "  $zipName"
Write-Host "  RadioPoggers-android.apk"
Write-Host "  SHA256SUMS.txt"
Write-Host "  (sem .pdb; IP Radmin nao embutido salvo dart-define privado)"
