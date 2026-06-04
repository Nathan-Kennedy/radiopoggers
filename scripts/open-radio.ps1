$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Start-Process "http://localhost"
Start-Process "http://localhost:5500/frontend/"

Write-Host "Abrindo painel do AzuraCast e frontend da RadioPoggers."

