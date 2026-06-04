$ErrorActionPreference = "Stop"
$scriptsDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = Split-Path -Parent $scriptsDir
$keyFile = Join-Path $projectRoot "data\gemini-api-key.txt"
$example = Join-Path $projectRoot "data\gemini-api-key.example.txt"

if (-not (Test-Path $keyFile)) {
  Write-Host ""
  Write-Host "API key Gemini nao encontrada."
  Write-Host "1. Abra https://aistudio.google.com/apikey"
  Write-Host "2. Copie a key para: data\gemini-api-key.txt"
  Write-Host "   (modelo em data\gemini-api-key.example.txt)"
  Write-Host ""
  if (-not (Test-Path $keyFile) -and (Test-Path $example)) {
    Write-Host "Crie o arquivo agora e rode de novo este script."
  }
  exit 1
}

Write-Host "Gemini TTS - instalando dependencias..."
python -m pip install -r (Join-Path $projectRoot "tools\radiopoggers-server\requirements-gemini-narrator.txt") -q

Push-Location $projectRoot
try {
  python (Join-Path $scriptsDir "generate-gemini-narrator-samples.py")
}
finally {
  Pop-Location
}

$html = Join-Path $projectRoot "data\narrator-voice-tests\gemini\index.html"
if (Test-Path $html) {
  Start-Process $html
}
