param(

  [string]$AzuraCastPath = "/mnt/c/Projetos Dev/RadioPoggers/~/azuracast",

  [string]$Distro = "Ubuntu-24.04"

)



$ErrorActionPreference = "Stop"



. (Join-Path $PSScriptRoot "stack-lib.ps1")



Write-Host "Parando AzuraCast em $AzuraCastPath..."

if (-not (Stop-StackAzuraCast -AzuraCastPath $AzuraCastPath -Distro $Distro)) {

  exit 1

}

Write-Host "RadioPoggers parada."

