$ErrorActionPreference = "Stop"

$root = Split-Path $PSScriptRoot -Parent
$requirements = Join-Path $root "tools\radiopoggers-server\requirements-miku.txt"

Write-Host "RadioPoggers - instalando dependencias da narradora Miku"
Write-Host ""

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
  Write-Host "[erro] Python nao encontrado."
  exit 1
}

python -m pip install --upgrade pip
python -m pip install -r $requirements

Write-Host ""
Write-Host "[ok] edge-tts instalado (fallback temporario — NAO e a voz Miku)."
Write-Host ""
Write-Host "Para voz estilo Miku COM ENTONACAO (gratis, local, recomendado):"
Write-Host "  .\scripts\install-voicevox-miku.ps1"
Write-Host ""
Write-Host "Resumo:"
Write-Host "  - Vocaloid oficial da Miku = pago (Crypton)"
Write-Host "  - VOICEVOX Song = gratis, entonacao anime/idol, roda na sua maquina"
Write-Host "  - Deixe o engine aberto em http://127.0.0.1:50021"
Write-Host ""
Write-Host "Opcional — so VOICEVOX, sem fallback edge:"
Write-Host '  $env:RADIOPOGGERS_MIKU_TTS = "voicevox"'
Write-Host '  $env:RADIOPOGGERS_MIKU_REQUIRE_VOICEVOX = "1"'
Write-Host ""
Write-Host "Alternativa Piper (PT-BR local):"
Write-Host "  `$env:RADIOPOGGERS_PIPER_BIN = 'C:\\caminho\\piper.exe'"
Write-Host "  `$env:RADIOPOGGERS_PIPER_MODEL = 'C:\\caminho\\pt_BR-faber-medium.onnx'"
Write-Host ""
Write-Host "Reinicie a API: .\\scripts\\start-local-api.ps1"
