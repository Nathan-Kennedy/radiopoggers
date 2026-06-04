$ErrorActionPreference = "Stop"
$scriptsDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = Split-Path -Parent $scriptsDir

Write-Host "Narradora feminina - gerando 5 amostras (edge-tts)..."
Write-Host ""

$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) { $python = Get-Command py -ErrorAction SilentlyContinue }
if (-not $python) { throw "Python nao encontrado." }

python -m pip install "edge-tts>=6.1.12" -q

Push-Location $projectRoot
try {
  if ($python.Name -eq "py.exe" -or $python.Name -eq "py") {
    py (Join-Path $scriptsDir "generate-female-narrator-samples.py")
  }
  else {
    python (Join-Path $scriptsDir "generate-female-narrator-samples.py")
  }
}
finally {
  Pop-Location
}

$outDir = Join-Path $projectRoot "data\narrator-voice-tests"
if (Test-Path (Join-Path $outDir "index.html")) {
  Write-Host ""
  Write-Host "Ouvir no navegador:"
  Write-Host "  http://127.0.0.1:5500/data/narrator-voice-tests/index.html"
  Start-Process "http://127.0.0.1:5500/data/narrator-voice-tests/index.html"
}
