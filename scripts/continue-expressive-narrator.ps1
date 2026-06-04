$ErrorActionPreference = "Stop"
$scriptsDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Write-Host "Continuando Francisca expressiva (espera o ChatTTS terminar)..."
python (Join-Path $scriptsDir "continue-expressive-narrator.py")
