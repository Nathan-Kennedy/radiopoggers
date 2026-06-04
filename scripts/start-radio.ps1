param(
  [string]$AzuraCastPath = "/mnt/c/Projetos Dev/RadioPoggers/~/azuracast",
  [string]$Distro = "Ubuntu-24.04"
)

$ErrorActionPreference = "Stop"

function Invoke-WslCommand {
  param([string]$Command)

  if ($Distro.Trim().Length -gt 0) {
    wsl -d $Distro -- bash -lc $Command
  }
  else {
    wsl -- bash -lc $Command
  }
}

Write-Host "Iniciando AzuraCast em $AzuraCastPath..."
Invoke-WslCommand "cd '$AzuraCastPath' && ./docker.sh up"
Write-Host "RadioPoggers iniciada. Painel: http://localhost"

