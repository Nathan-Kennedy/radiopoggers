$ErrorActionPreference = "Stop"
$scriptsDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = Split-Path -Parent $scriptsDir
$reqFile = Join-Path $projectRoot "tools\radiopoggers-server\requirements-expressive-narrator.txt"

Write-Host "Gerando efeitos (risada, bocejo, suspiro) com ChatTTS..."
Write-Host "Primeira vez baixa ~1-2 GB. Pode demorar varios minutos."
Write-Host ""

python -m pip install torch torchaudio --index-url https://download.pytorch.org/whl/cpu -q
python -m pip install -r $reqFile -q

Push-Location $projectRoot
try {
  python (Join-Path $scriptsDir "generate-narrator-sfx.py")
}
finally {
  Pop-Location
}
