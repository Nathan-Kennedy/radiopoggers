$ErrorActionPreference = "Stop"
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$html = Join-Path $root "data\narrator-voice-tests\expressive\index.html"
if (-not (Test-Path $html)) {
  throw "Rode primeiro: .\scripts\generate-francisca-expressive-samples.py"
}
Start-Process $html
