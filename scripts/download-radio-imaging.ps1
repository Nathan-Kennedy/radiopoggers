# Baixa imaging/stingers Mixkit (licença gratuita) para o app.
$ErrorActionPreference = "Stop"
$root = Split-Path $PSScriptRoot -Parent
python (Join-Path $PSScriptRoot "download-radio-imaging.py")
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
Write-Host "[ok] Rode Hot Restart no Flutter apos o download."
