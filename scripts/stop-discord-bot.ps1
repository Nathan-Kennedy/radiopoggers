param(
  [int]$WaitSeconds = 20,
  [switch]$Quiet
)

$ErrorActionPreference = "Continue"

. (Join-Path $PSScriptRoot "discord-bot-lib.ps1")

if (-not $Quiet) {
  Write-Host "RADIO NO GRALE - desligando bot Discord..."
  Write-Host '  Pede saida da call no Discord e so depois encerra o processo.'
  Write-Host ""
}

$stopped = Ensure-DiscordBotStopped -TimeoutSeconds $WaitSeconds -Quiet:$Quiet

if (-not $Quiet) {
  if ($stopped) {
    Write-Host ""
    Write-Host "Bot Discord desligado."
    Write-Host "Para ligar de novo: .\scripts\start-discord-bot.ps1"
  }
  else {
    Write-Host ""
    Write-Host "Alguns processos podem ter ficado presos. Tente de novo ou reinicie o PC."
    exit 1
  }
}

exit 0
