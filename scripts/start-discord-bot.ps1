$ErrorActionPreference = "Stop"

. (Join-Path $PSScriptRoot "discord-bot-lib.ps1")

$projectRoot = Get-DiscordBotProjectRoot -ScriptsDir $PSScriptRoot
$botDir = Join-Path $projectRoot "tools\discord-bot"
$tokenFile = Join-Path $projectRoot "data\discord-bot-token.txt"
$configFile = Join-Path $projectRoot "data\discord-bot-config.json"
$configExample = Join-Path $projectRoot "data\discord-bot-config.example.json"

if (-not (Test-Path $configFile)) {
  Copy-Item $configExample $configFile
  Write-Host "Criei data\discord-bot-config.json a partir do exemplo. Ajuste as URLs se precisar."
}

if (-not (Test-Path $tokenFile)) {
  Write-Host ""
  Write-Host "FALTA O TOKEN DO BOT."
  Write-Host "1. Discord Developer Portal -> Bot -> Reset Token"
  Write-Host "2. Salve em data\discord-bot-token.txt"
  Write-Host "   (veja data/discord-bot-token.example.txt)"
  Write-Host ""
  throw "Token ausente: data\discord-bot-token.txt"
}

function Resolve-BotPython {
  $candidates = @(
    "$env:LocalAppData\Programs\Python\Python312\python.exe",
    "$env:LocalAppData\Programs\Python\Python313\python.exe"
  )
  foreach ($path in $candidates) {
    if (Test-Path $path) { return $path }
  }
  $fromPath = Get-Command python -All -ErrorAction SilentlyContinue |
    Where-Object { $_.Source -and ($_.Source -notmatch 'WindowsApps') } |
    Select-Object -ExpandProperty Source -First 1
  if ($fromPath) { return $fromPath }
  throw "Python nao encontrado. Instale Python 3.12+ e marque Add to PATH."
}

if (Test-DiscordBotRunning -ProjectRoot $projectRoot) {
  Write-Host "Encontradas instancias antigas do bot (podem estar em call). Encerrando antes de subir a nova..."
  $clean = Ensure-DiscordBotStopped -ProjectRoot $projectRoot -TimeoutSeconds 20
  if (-not $clean) {
    throw "Ainda ha processos do bot Discord. Rode .\scripts\stop-discord-bot.ps1 e tente de novo."
  }
  Start-Sleep -Seconds 2
}
else {
  Clear-DiscordBotPidFile -ProjectRoot $projectRoot
}

$python = Resolve-BotPython
Write-Host "Python do bot: $python"

Write-Host "Instalando dependencias do bot (discord.py, davey, PyNaCl)..."
& $python -m pip install -r (Join-Path $botDir "requirements.txt") -q
& $python -c "import davey, nacl; from discord.voice_client import VoiceClient; import sys; 
assert not VoiceClient.warn_dave and not VoiceClient.warn_nacl, 'davey/PyNaCl indisponivel'; 
print('Dependencias de voz OK.')"

Write-Host ""
Write-Host "Iniciando bot Discord da RADIO NO GRALE..."
Write-Host "  API:     http://127.0.0.1:8765 (start-local-api.ps1)"
Write-Host "  Stream:  leia stream_url em data\discord-bot-config.json"
Write-Host "  FFmpeg:  obrigatorio no PATH para /play no canal de voz"
Write-Host "  Config:  data\discord-bot-config.json"
Write-Host "  Parar:   .\scripts\stop-discord-bot.ps1"
Write-Host "  Reinici: .\scripts\restart-discord-bot.ps1"
Write-Host ""
Write-Host "Se alguem ja estava na call, use /play de novo apos reiniciar o bot."
Write-Host "Pressione Ctrl+C para parar."

Push-Location $botDir
$prevErrorAction = $ErrorActionPreference
$ErrorActionPreference = "Continue"
try {
  # Python logging vai para stderr; com Stop o PowerShell matava o bot e ele ficava offline no Discord.
  & $python bot.py 2>&1 | ForEach-Object { Write-Host $_ }
  if ($LASTEXITCODE -and $LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
  }
}
finally {
  $ErrorActionPreference = $prevErrorAction
  Pop-Location
  Clear-DiscordBotPidFile -ProjectRoot $projectRoot
}
