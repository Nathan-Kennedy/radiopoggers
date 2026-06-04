param(
  [string]$LanIp = "",
  [string]$RemoteHost = "",
  [int]$HttpsPort = 5443
)

$ErrorActionPreference = "Continue"

$projectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$configJs = Join-Path $projectRoot "frontend\config.js"

if (-not $LanIp) {
  $LanIp = (
    Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
    Where-Object {
      $_.IPAddress -match '^192\.168\.' -or $_.IPAddress -match '^10\.' -or $_.IPAddress -match '^172\.(1[6-9]|2[0-9]|3[0-1])\.'
    } |
    Sort-Object -Property InterfaceMetric |
    Select-Object -First 1 -ExpandProperty IPAddress
  )
}

if (-not $RemoteHost -and (Test-Path $configJs)) {
  $raw = Get-Content $configJs -Raw -ErrorAction SilentlyContinue
  if ($raw -match 'azuracastBaseUrl:\s*"https?://([^"/]+)"') {
    $RemoteHost = $Matches[1].Trim()
  }
}

$radminIps = @(
  Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
  Where-Object { $_.IPAddress -match '^26\.' } |
  Select-Object -ExpandProperty IPAddress
)

Write-Host "=== Diagnostico HTTPS RadioPoggers (porta $HttpsPort) ==="
Write-Host ""

$listen = Get-NetTCPConnection -LocalPort $HttpsPort -State Listen -ErrorAction SilentlyContinue
if ($listen) {
  Write-Host "[ok] Servidor escutando em 0.0.0.0:$HttpsPort (PID $($listen.OwningProcess | Select-Object -First 1))"
}
else {
  Write-Host "[FALHA] Nada escutando na porta $HttpsPort."
  Write-Host "        Rode: .\scripts\start-frontend-https.ps1"
  Write-Host "        Ou:  .\scripts\serve-frontend.ps1  (sobe HTTP + HTTPS junto)"
}

$rule = Get-NetFirewallRule -DisplayName "RadioPoggers TCP $HttpsPort" -ErrorAction SilentlyContinue
if ($rule) {
  $profiles = (Get-NetFirewallRule -DisplayName "RadioPoggers TCP $HttpsPort" | Get-NetFirewallProfile -ErrorAction SilentlyContinue).Name -join ", "
  Write-Host "[ok] Regra de firewall para porta $HttpsPort (perfis: $profiles)"
}
else {
  Write-Host "[AVISO] Firewall pode bloquear Radmin/celular. Como Admin: .\scripts\open-lan-firewall.ps1"
}

$targets = @("127.0.0.1")
if ($LanIp) { $targets += $LanIp }
if ($RemoteHost) { $targets += $RemoteHost }
$targets += $radminIps
$targets = $targets | Select-Object -Unique

foreach ($hostName in $targets) {
  if (-not $hostName) { continue }
  $url = "https://${hostName}:$HttpsPort/frontend/index.html"
  $curl = Get-Command curl.exe -ErrorAction SilentlyContinue
  if ($curl) {
    $code = & curl.exe -k -m 8 -s -o NUL -w "%{http_code}" $url 2>$null
    if ($code -eq "200") {
      Write-Host "[ok] $url -> HTTP 200"
    }
    else {
      Write-Host "[FALHA] $url -> HTTP $code (servidor, certificado ou firewall)"
    }
  }
  else {
    Write-Host "[?] Instale curl ou teste manualmente: $url"
  }
}

$certPath = Join-Path $projectRoot "data\dev-ssl\radiopoggers.crt"
if ((Test-Path $certPath) -and $RemoteHost) {
  $openssl = Get-Command openssl -ErrorAction SilentlyContinue
  if (-not $openssl) {
    $gitOpenSsl = "C:\Program Files\Git\usr\bin\openssl.exe"
    if (Test-Path $gitOpenSsl) { $openssl = $gitOpenSsl }
  }
  if ($openssl) {
    $san = & $openssl x509 -in $certPath -noout -ext subjectAltName 2>$null
    if ($san -match [regex]::Escape($RemoteHost)) {
      Write-Host "[ok] Certificado inclui $RemoteHost no SAN"
    }
    else {
      Write-Host "[FALHA] Certificado NAO inclui $RemoteHost. Rode: .\scripts\ensure-dev-ssl.ps1 -Force"
    }
  }
}

Write-Host ""
if ($RemoteHost) {
  Write-Host "Amigos no Radmin (microfone):"
  Write-Host "  https://${RemoteHost}:$HttpsPort/frontend/"
  Write-Host "  1) Aceite o certificado (Avancado -> Continuar)"
  Write-Host "  2) Permita o microfone quando o Chrome pedir"
}
