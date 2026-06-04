param(
  [string]$ApiBase = "http://127.0.0.1:8765"
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$testScript = Join-Path $projectRoot "scripts\test-radiopoggers-api.py"

$env:RADIOPOGGERS_TEST_API = $ApiBase
python $testScript
exit $LASTEXITCODE
