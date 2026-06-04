param(
  [switch]$NewWindow,
  [int]$WaitSeconds = 20
)

$ErrorActionPreference = "Stop"
$scriptsDir = $PSScriptRoot
$projectRoot = Split-Path $scriptsDir -Parent

. (Join-Path $scriptsDir "discord-bot-lib.ps1")

Write-Host "RADIO NO GRALE - reiniciando bot Discord..."
Write-Host ""

& (Join-Path $scriptsDir "stop-discord-bot.ps1") -WaitSeconds $WaitSeconds
if ($LASTEXITCODE -ne 0) {
  throw "Nao foi possivel encerrar todas as instancias antigas do bot."
}

Start-Sleep -Seconds 2

if ($NewWindow) {
  Write-Host "Subindo bot em segundo plano (janela oculta)..."
  Start-DiscordBotInNewWindow -ProjectRoot $projectRoot -ScriptsDir $scriptsDir
  if (Wait-DiscordBotReady -ProjectRoot $projectRoot -TimeoutSeconds 45) {
    $pidFile = Get-DiscordBotPidFile -ProjectRoot $projectRoot
    $botPid = if (Test-Path $pidFile) {
      (Get-Content $pidFile -ErrorAction SilentlyContinue | Select-Object -First 1).Trim()
    } else {
      (Get-DiscordBotProcessIds -ProjectRoot $projectRoot | Select-Object -First 1)
    }
    Write-Host "Bot online (PID $botPid). Quem estava na call precisa usar /play de novo."
  }
  else {
    Write-Host "[aviso] Bot ainda nao apareceu apos 45s. Veja data\logs\discord-bot.log ou rode .\scripts\start-discord-bot.ps1"
  }
}
else {
  & (Join-Path $scriptsDir "start-discord-bot.ps1")
}
