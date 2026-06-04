param(
  [string]$Distro = "Ubuntu-24.04",
  [string]$InstallDir = "~/azuracast"
)

$ErrorActionPreference = "Stop"

Write-Host "Preparando AzuraCast em $Distro..."
Write-Host "Diretorio WSL: $InstallDir"

$projectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$scriptPath = Join-Path $projectRoot "scripts\install-azuracast-wsl.sh"
$wslScriptPath = (wsl -d $Distro -- wslpath -a "$scriptPath").Trim()
$bootstrap = "tr -d '\r' < '$wslScriptPath' > /tmp/radiopoggers-install-azuracast.sh && bash /tmp/radiopoggers-install-azuracast.sh '$InstallDir'"

wsl -d $Distro -- bash -lc $bootstrap

if ($LASTEXITCODE -ne 0) {
  throw "Instalacao do AzuraCast falhou com codigo $LASTEXITCODE."
}

