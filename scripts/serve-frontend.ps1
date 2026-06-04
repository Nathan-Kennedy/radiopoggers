param(
  [int]$Port = 5500,
  [int]$HttpsPort = 5443,
  [switch]$Open,
  [switch]$NoHttps
)

$ErrorActionPreference = "Stop"

$scriptsDir = Split-Path -Parent $MyInvocation.MyCommand.Path
. (Join-Path $scriptsDir "process-lib.ps1")

$projectRoot = Split-Path -Parent $scriptsDir
$frontendPath = Join-Path $projectRoot "frontend"

if (-not (Test-Path $frontendPath)) {
  throw "Nao encontrei a pasta frontend em $frontendPath"
}

$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) {
  $python = Get-Command py -ErrorAction SilentlyContinue
}

if (-not $python) {
  throw "Python nao encontrado. Instale Python ou use outro servidor estatico para a pasta do projeto."
}

$lanIp = (
  Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
  Where-Object {
    $_.IPAddress -match '^192\.168\.' -or $_.IPAddress -match '^10\.' -or $_.IPAddress -match '^172\.(1[6-9]|2[0-9]|3[0-1])\.'
  } |
  Sort-Object -Property InterfaceMetric |
  Select-Object -First 1 -ExpandProperty IPAddress
)

$url = "http://localhost:$Port/frontend/"
Write-Host "Servindo RadioPoggers em $url"
if ($lanIp) {
  Write-Host "  Celular (mesma Wi-Fi): http://${lanIp}:$Port/frontend/"
  if (-not $NoHttps) {
    Write-Host "  Microfone no celular: https://${lanIp}:$HttpsPort/frontend/"
  }
}
Write-Host "Raiz servida: $projectRoot"
Write-Host "Pressione Ctrl+C para parar."

if (-not $NoHttps) {
  $httpsListen = Get-NetTCPConnection -LocalPort $HttpsPort -State Listen -ErrorAction SilentlyContinue
  if (-not $httpsListen) {
    Write-Host ""
    Write-Host "Subindo HTTPS (microfone) na porta $HttpsPort em segundo plano..."
    $httpsScript = Join-Path $scriptsDir "start-frontend-https.ps1"
    $httpsEscaped = $httpsScript -replace "'", "''"
    Start-HiddenPowerShellScript `
      -Command "& '$httpsEscaped' -Port $HttpsPort -SkipFirewallHint" `
      -WorkingDirectory $projectRoot `
      -ProjectRoot $projectRoot `
      -LogName "frontend-https"
    Start-Sleep -Seconds 2
    $httpsListen = Get-NetTCPConnection -LocalPort $HttpsPort -State Listen -ErrorAction SilentlyContinue
    if ($httpsListen) {
      Write-Host "[ok] HTTPS ativo na porta $HttpsPort"
    }
    else {
      Write-Host "[aviso] HTTPS nao subiu. Rode manualmente: .\scripts\start-frontend-https.ps1"
      Write-Host "        Celular travando? Firewall Admin: .\scripts\open-lan-firewall.ps1"
    }
  }
  else {
    Write-Host "[ok] HTTPS ja ativo na porta $HttpsPort"
  }
}

if ($Open) {
  Start-Process $url
}

Push-Location $projectRoot
try {
  if ($python.Name -eq "py.exe" -or $python.Name -eq "py") {
    py -m http.server $Port --bind 0.0.0.0
  }
  else {
    python -m http.server $Port --bind 0.0.0.0
  }
}
finally {
  Pop-Location
}

