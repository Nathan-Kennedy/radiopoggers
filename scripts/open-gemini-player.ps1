$ErrorActionPreference = "Stop"
$html = Join-Path (Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)) "data\narrator-voice-tests\gemini\index.html"
if (-not (Test-Path $html)) {
  throw "Rode primeiro: .\scripts\generate-gemini-narrator-samples.ps1"
}
Start-Process $html
