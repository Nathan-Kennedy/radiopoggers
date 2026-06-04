param(
  [string]$AzuraCastPath = "/mnt/c/Projetos Dev/RadioPoggers/~/azuracast",
  [string]$Distro = "Ubuntu-24.04",
  [switch]$SkipDiscordBot,
  [switch]$SkipAzuraCast,
  [switch]$Quiet
)

$ErrorActionPreference = "Continue"

. (Join-Path $PSScriptRoot "stack-lib.ps1")

if (-not $Quiet) {
  Write-Host "RADIO NO GRALE - desligando stack completo..."
  Write-Host ""
}

$ok = $true

if (-not $Quiet) {
  Write-Host "1/3 Servicos locais (API, site, VOICEVOX)..."
}
& (Join-Path $PSScriptRoot "stop-local-stack.ps1")
if ($LASTEXITCODE -ne 0) { $ok = $false }

if (-not $SkipDiscordBot) {
  if (-not $Quiet) {
    Write-Host ""
    Write-Host "2/3 Bot Discord (sai da call)..."
  }
  & (Join-Path $PSScriptRoot "stop-discord-bot.ps1") -Quiet:$Quiet
  if ($LASTEXITCODE -ne 0) { $ok = $false }
}
elseif (-not $Quiet) {
  Write-Host ""
  Write-Host "2/3 Bot Discord - pulado (-SkipDiscordBot)."
}

if (-not $SkipAzuraCast) {
  if (-not $Quiet) {
    Write-Host ""
    Write-Host "3/3 AzuraCast (Docker)..."
  }
  if (-not (Stop-StackAzuraCast -AzuraCastPath $AzuraCastPath -Distro $Distro -Quiet:$Quiet)) {
    $ok = $false
  }
}
elseif (-not $Quiet) {
  Write-Host ""
  Write-Host "3/3 AzuraCast - pulado (-SkipAzuraCast)."
}

if (-not $Quiet) {
  Write-Host ""
  if ($ok) {
    Write-Host "Stack desligado."
    Write-Host "Para ligar de novo: .\scripts\start-full-stack.ps1 -OpenBrowser"
  }
  else {
    Write-Host "Desligamento concluido com avisos. Revise as mensagens acima."
    exit 1
  }
}

exit 0
