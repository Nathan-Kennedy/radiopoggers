$ErrorActionPreference = "Stop"
$projectRoot = Split-Path $PSScriptRoot -Parent
python "$projectRoot\scripts\reset-radio-linkin-park.py"
