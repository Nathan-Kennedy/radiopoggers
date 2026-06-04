param(
  [int]$Port = 8765
)

$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$serverPath = Join-Path $projectRoot "tools\radiopoggers-server\server.py"

if (-not (Test-Path $serverPath)) {
  throw "Nao encontrei $serverPath"
}

$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) {
  $python = Get-Command py -ErrorAction SilentlyContinue
}

if (-not $python) {
  throw "Python nao encontrado."
}

$env:RADIOPOGGERS_API_PORT = "$Port"
$env:RADIOPOGGERS_API_HOST = "0.0.0.0"

$lanIp = (
  Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
  Where-Object {
    $_.IPAddress -match '^192\.168\.' -or $_.IPAddress -match '^10\.' -or $_.IPAddress -match '^172\.(1[6-9]|2[0-9]|3[0-1])\.'
  } |
  Sort-Object -Property InterfaceMetric |
  Select-Object -First 1 -ExpandProperty IPAddress
)
if (-not $lanIp) {
  $lanIp = "127.0.0.1"
}
$env:RADIOPOGGERS_PUBLIC_AZURACAST_URL = "http://${lanIp}"

$spotifyCredentialsFile = Join-Path $projectRoot "data\spotify-api-credentials.txt"
if (Test-Path $spotifyCredentialsFile) {
  $spotifyClientId = ""
  $spotifyClientSecret = ""
  Get-Content $spotifyCredentialsFile -ErrorAction SilentlyContinue | ForEach-Object {
    $line = $_.Trim()
    if (-not $line -or $line.StartsWith("#")) { return }
    if ($line -match '^(?i)(SPOTIFY_)?CLIENT_ID\s*=\s*(.+)$') {
      $spotifyClientId = $Matches[2].Trim().Trim('"').Trim("'")
      return
    }
    if ($line -match '^(?i)(SPOTIFY_)?CLIENT_SECRET\s*=\s*(.+)$') {
      $spotifyClientSecret = $Matches[2].Trim().Trim('"').Trim("'")
      return
    }
    if (-not $spotifyClientId) {
      $spotifyClientId = $line
      return
    }
    if (-not $spotifyClientSecret) {
      $spotifyClientSecret = $line
    }
  }
  if ($spotifyClientId) { $env:SPOTIFY_CLIENT_ID = $spotifyClientId }
  if ($spotifyClientSecret) { $env:SPOTIFY_CLIENT_SECRET = $spotifyClientSecret }
  if ($spotifyClientId -and $spotifyClientSecret) {
    Write-Host "Spotify: credenciais carregadas de data\spotify-api-credentials.txt (busca /play no Discord)."
  }
  else {
    Write-Host "Spotify: AVISO - data\spotify-api-credentials.txt incompleto (precisa client_id + client_secret)."
  }
}
else {
  Write-Host "Spotify: AVISO - busca /play no Discord exige data\spotify-api-credentials.txt (veja spotify-api-credentials.example.txt)."
}

$azuracastKeyFile = Join-Path $projectRoot "data\azuracast-api-key.txt"
if (Test-Path $azuracastKeyFile) {
  $azuracastKey = Get-Content $azuracastKeyFile -ErrorAction SilentlyContinue |
    Where-Object { $_ -and -not $_.StartsWith("#") } |
    Select-Object -First 1
  if ($azuracastKey) {
    $env:RADIOPOGGERS_AZURACAST_API_KEY = $azuracastKey.Trim()
    Write-Host "AzuraCast: API key carregada de data\azuracast-api-key.txt (skip e pedidos)."
  }
}
else {
  Write-Host 'AzuraCast: AVISO - pular faixa e pedidos exigem data\azuracast-api-key.txt (veja azuracast-api-key.example.txt).'
}

$voicevoxScript = Join-Path (Split-Path -Parent $MyInvocation.MyCommand.Path) "start-voicevox-engine.ps1"
if (Test-Path $voicevoxScript) {
  & $voicevoxScript | Out-Null
}

try {
  Invoke-RestMethod -Uri "http://127.0.0.1:50021/version" -TimeoutSec 2 | Out-Null
  $env:RADIOPOGGERS_MIKU_TTS = "voicevox"
  $env:RADIOPOGGERS_MIKU_REQUIRE_VOICEVOX = "1"
  Write-Host "Miku: VOICEVOX ativo (voz anime + entonacao)."
}
catch {
  Write-Host "Miku: VOICEVOX offline - fallback edge-tts se instalado."
}

Write-Host "Iniciando API local da RadioPoggers em http://0.0.0.0:$Port"
Write-Host "  PC:      http://127.0.0.1:$Port/api/health"
Write-Host "  Celular: http://${lanIp}:$Port/api/health  (mesma Wi-Fi)"
Write-Host "  Capas no celular: reinicie esta API apos mudar IP; art usa http://${lanIp}"
Write-Host "  Microfone celular: https://${lanIp}:5443/frontend/  (.\scripts\start-frontend-https.ps1)"
Write-Host "Pressione Ctrl+C para parar."

Push-Location $projectRoot
try {
  if ($python.Name -eq "py.exe" -or $python.Name -eq "py") {
    py $serverPath
  }
  else {
    python $serverPath
  }
}
finally {
  Pop-Location
}

