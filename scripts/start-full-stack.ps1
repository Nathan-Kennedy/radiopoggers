param(
  [string]$AzuraCastPath = "/mnt/c/Projetos Dev/RadioPoggers/~/azuracast",
  [string]$Distro = "Ubuntu-24.04",
  [switch]$SkipAzuraCast,
  [switch]$SkipVoiceVox,
  [switch]$SkipDiscordBot,
  [switch]$OpenBrowser
)

$ErrorActionPreference = "Stop"
$scriptsDir = $PSScriptRoot
$projectRoot = Split-Path $scriptsDir -Parent

. (Join-Path $scriptsDir "stack-lib.ps1")
. (Join-Path $scriptsDir "discord-bot-lib.ps1")

Write-Host "RADIO NO GRALE - ligando stack completo..."
Write-Host ""

if (-not $SkipAzuraCast) {
  Assert-StackDockerReady -RequireAzuraCast -AzuraCastPath $AzuraCastPath -Distro $Distro
}
else {
  Assert-StackDockerReady
  Write-Host "[info] AzuraCast pulado (-SkipAzuraCast). API/site vao usar stream ja existente."
  Write-Host ""
}

$step = 1
$totalSteps = 6
if ($SkipAzuraCast) { $totalSteps-- }
if ($SkipVoiceVox) { $totalSteps-- }
if ($SkipDiscordBot) { $totalSteps-- }

if (-not $SkipAzuraCast) {
  $container = Test-StackAzuraCastContainer
  if ($container.Running) {
    Write-Host "$step/$totalSteps AzuraCast - ja rodando, conferindo painel..."
    Wait-StackAzuraCastReady -TimeoutSeconds 30 | Out-Null
  }
  else {
    Write-Host "$step/$totalSteps AzuraCast (Docker via WSL)..."
    & (Join-Path $scriptsDir "start-radio.ps1") -AzuraCastPath $AzuraCastPath -Distro $Distro
    Wait-StackAzuraCastReady -TimeoutSeconds 180 | Out-Null
  }
  $step++
}
else {
  Write-Host "$step/$totalSteps AzuraCast - pulado."
  $step++
}

if (-not $SkipVoiceVox) {
  Write-Host "$step/$totalSteps VOICEVOX (Miku)..."
  & (Join-Path $scriptsDir "start-voicevox-engine.ps1") | Out-Null
  $step++
}

Write-Host "$step/$totalSteps API local (estante, votacao, Miku)..."
Start-StackLocalApi -ScriptsDir $scriptsDir
Wait-StackLocalApiReady -TimeoutSeconds 90 | Out-Null
$step++

Write-Host "$step/$totalSteps Frontend HTTP (segundo plano, janela oculta)..."
$serveScript = Join-Path $scriptsDir "serve-frontend.ps1"
$serveEscaped = $serveScript -replace "'", "''"
$serveCmd = "& '$serveEscaped'"
if ($OpenBrowser) {
  $serveCmd += " -Open"
}
Start-HiddenPowerShellScript `
  -Command $serveCmd `
  -WorkingDirectory $projectRoot `
  -ProjectRoot $projectRoot `
  -LogName "frontend-http"
Write-Host "  Log: data\logs\frontend-http.log"
$step++

Write-Host "$step/$totalSteps Frontend HTTPS (celular / microfone, segundo plano)..."
$httpsScript = Join-Path $scriptsDir "start-frontend-https.ps1"
$httpsEscaped = $httpsScript -replace "'", "''"
Start-HiddenPowerShellScript `
  -Command "& '$httpsEscaped'" `
  -WorkingDirectory $projectRoot `
  -ProjectRoot $projectRoot `
  -LogName "frontend-https"
Write-Host "  Log: data\logs\frontend-https.log"
$step++

if (-not $SkipDiscordBot) {
  $tokenFile = Join-Path $projectRoot "data\discord-bot-token.txt"
  if (-not (Test-Path $tokenFile)) {
    Write-Host ""
    Write-Host "[aviso] Bot Discord nao iniciado: falta data\discord-bot-token.txt"
    Write-Host "        Depois rode: .\scripts\start-discord-bot.ps1"
  }
  else {
    Write-Host "$step/$totalSteps Bot Discord (segundo plano, janela oculta)..."
    Start-DiscordBotInNewWindow -ProjectRoot $projectRoot -ScriptsDir $scriptsDir
  }
}

Write-Host ""
Write-Host "Stack iniciado."
Write-Host "  Site:    http://localhost:5500/frontend/"
Write-Host "  HTTPS:   https://localhost:5443/frontend/  (microfone no celular)"
Write-Host "  API:     http://127.0.0.1:8765/api/health  (estante / votacao)"
Write-Host "  Painel:  http://localhost"
if (-not (Test-StackLocalApiHttp).Ok) {
  Write-Host ""
  Write-Host "  [aviso] API ainda offline - estante pede Ctrl+F5 apos .\scripts\start-local-api.ps1"
}
Write-Host ""
Write-Host "Logs (servicos em segundo plano): data\logs\"
Write-Host "Desligar tudo: .\scripts\stop-full-stack.ps1"
Write-Host "Testes:        .\scripts\test-radiopoggers.ps1"
