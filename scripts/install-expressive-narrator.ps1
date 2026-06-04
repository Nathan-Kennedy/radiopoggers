param(
  [switch]$SkipSamples
)

$ErrorActionPreference = "Stop"
$scriptsDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = Split-Path -Parent $scriptsDir
$reqFile = Join-Path $projectRoot "tools\radiopoggers-server\requirements-expressive-narrator.txt"

Write-Host "Instalando narradora expressiva Francisca (edge-tts + ChatTTS)..."
Write-Host "Primeira instalacao pode demorar (PyTorch + modelos)."
Write-Host ""

$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) { $python = Get-Command py -ErrorAction SilentlyContinue }
if (-not $python) { throw "Python nao encontrado." }

python -m pip install --upgrade pip -q
python -m pip install torch torchaudio --index-url https://download.pytorch.org/whl/cpu -q
python -m pip install -r $reqFile -q

$ffmpeg = Get-Command ffmpeg -ErrorAction SilentlyContinue
if (-not $ffmpeg) {
  Write-Host "AVISO: ffmpeg nao encontrado no PATH. pydub precisa dele para MP3."
  Write-Host "  Instale: winget install Gyan.FFmpeg"
}

Write-Host ""
if (-not $SkipSamples) {
  Write-Host "Dependencias OK. Gerando amostras..."
  Write-Host ""
  Push-Location $projectRoot
  try {
    python (Join-Path $scriptsDir "generate-narrator-sfx.py")
    python (Join-Path $scriptsDir "generate-francisca-expressive-samples.py")
  }
  finally {
    Pop-Location
  }
}
else {
  Write-Host "Dependencias OK."
}
