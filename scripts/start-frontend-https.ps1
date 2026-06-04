param(
  [int]$Port = 5443,
  [switch]$Open,
  [switch]$SkipFirewallHint
)

$ErrorActionPreference = "Stop"

$scriptsDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = Split-Path -Parent $scriptsDir

& (Join-Path $scriptsDir "ensure-dev-ssl.ps1") | Out-Null

$configJs = Join-Path $projectRoot "frontend\config.js"
$remoteHost = ""
if (Test-Path $configJs) {
  $raw = Get-Content $configJs -Raw -ErrorAction SilentlyContinue
  if ($raw -match 'azuracastBaseUrl:\s*"https?://([^"/]+)"') {
    $remoteHost = $Matches[1].Trim()
  }
}

$alreadyListening = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
if ($alreadyListening) {
  Write-Host "HTTPS ja esta ativo na porta $Port (PID $($alreadyListening.OwningProcess | Select-Object -First 1))."
  if (-not $SkipFirewallHint) {
    & (Join-Path $scriptsDir "test-https-frontend.ps1") -HttpsPort $Port
  }
  if ($Open) {
    Start-Process "https://localhost:$Port/frontend/"
  }
  exit 0
}

$lanIp = (
  Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
  Where-Object {
    $_.IPAddress -match '^192\.168\.' -or $_.IPAddress -match '^10\.' -or $_.IPAddress -match '^172\.(1[6-9]|2[0-9]|3[0-1])\.'
  } |
  Sort-Object -Property InterfaceMetric |
  Select-Object -First 1 -ExpandProperty IPAddress
)

$firewallRule = Get-NetFirewallRule -DisplayName "RadioPoggers TCP $Port" -ErrorAction SilentlyContinue
if (-not $firewallRule -and -not $SkipFirewallHint) {
  Write-Host ""
  Write-Host "AVISO: porta $Port pode estar bloqueada no firewall do Windows."
  Write-Host "  No celular isso parece 'carregando infinito'."
  Write-Host "  Como Administrador: .\scripts\open-lan-firewall.ps1"
  Write-Host ""
}

$env:RADIOPOGGERS_HTTPS_PORT = "$Port"
$url = "https://localhost:$Port/frontend/"
Write-Host "Frontend HTTPS em $url"
if ($lanIp) {
  Write-Host "  Celular (microfone): https://${lanIp}:$Port/frontend/"
}
if ($remoteHost -and $remoteHost -ne $lanIp) {
  Write-Host "  Radmin / amigos (microfone): https://${remoteHost}:$Port/frontend/"
}
if ($lanIp -or $remoteHost) {
  Write-Host "  Aceite o certificado autoassinado na 1a visita (Avancado -> Continuar)."
}

if ($Open) {
  Start-Process $url
}

$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) {
  $python = Get-Command py -ErrorAction SilentlyContinue
}
if (-not $python) {
  throw "Python nao encontrado."
}

Push-Location $projectRoot
try {
  if ($python.Name -eq "py.exe" -or $python.Name -eq "py") {
    py (Join-Path $scriptsDir "serve-frontend-https.py")
  }
  else {
    python (Join-Path $scriptsDir "serve-frontend-https.py")
  }
}
finally {
  Pop-Location
}
