# Copia assets ASCII e amostras do frontend para o app Flutter.
$ErrorActionPreference = "Stop"
$root = Split-Path $PSScriptRoot -Parent
$app = Join-Path $root "apps\radiopoggers_app"
$asciiSrc = Join-Path $root "frontend\assets"
$asciiDst = Join-Path $app "assets\ascii"

New-Item -ItemType Directory -Force -Path $asciiDst, `
  (Join-Path $app "assets\narrator_samples\miku"), `
  (Join-Path $app "assets\narrator_samples\hoshino"), `
  (Join-Path $app "assets\fonts"), `
  (Join-Path $app "assets\img"), `
  (Join-Path $app "assets\radio_imaging") | Out-Null

$frames = @(
  "ascii-frames.json",
  "ascii-frames sentado.json",
  "ascii-frames off.json",
  "ascii-frames falando.json",
  "ascii-frames hoshino falando.json",
  "ascii-frames miku.json",
  "ascii-frames hoshino.json"
)
foreach ($f in $frames) {
  Copy-Item (Join-Path $asciiSrc $f) (Join-Path $asciiDst $f) -Force
}
Copy-Item (Join-Path $asciiSrc "narrator-samples\manifest.json") (Join-Path $app "assets\narrator_samples\manifest.json") -Force
Copy-Item (Join-Path $asciiSrc "narrator-samples\miku\*") (Join-Path $app "assets\narrator_samples\miku\") -Force
Copy-Item (Join-Path $asciiSrc "narrator-samples\hoshino\*") (Join-Path $app "assets\narrator_samples\hoshino\") -Force
Copy-Item (Join-Path $root "frontend\assets\fonts\Inter-Regular.ttf") (Join-Path $app "assets\fonts\Inter-Regular.ttf") -Force
Copy-Item (Join-Path $root "frontend\assets\img\cover-fallback.svg") (Join-Path $app "assets\img\cover-fallback.svg") -Force
$imagingSrc = Join-Path $root "assets\radio_imaging"
$imagingDst = Join-Path $app "assets\radio_imaging"
if (Test-Path $imagingSrc) {
  Copy-Item (Join-Path $imagingSrc "*") $imagingDst -Force -Recurse
} else {
  Write-Host "[aviso] Rode .\scripts\download-radio-imaging.ps1 para baixar os stingers."
}
Write-Host "[ok] Assets sincronizados em $app"
