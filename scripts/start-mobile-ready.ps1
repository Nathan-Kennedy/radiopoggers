# Sobe API + HTTP + HTTPS para o celular (microfone e capas).
# Servicos rodam em segundo plano (janelas ocultas). Logs em data\logs\

$ErrorActionPreference = "Stop"
$scriptsDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = Split-Path -Parent $scriptsDir

. (Join-Path $scriptsDir "process-lib.ps1")

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

$configJs = Join-Path $projectRoot "frontend\config.js"
$remoteHost = ""
if (Test-Path $configJs) {
  $raw = Get-Content $configJs -Raw -ErrorAction SilentlyContinue
  if ($raw -match 'azuracastBaseUrl:\s*"https?://([^"/]+)"') {
    $remoteHost = $Matches[1].Trim()
  }
}

& (Join-Path $scriptsDir "ensure-dev-ssl.ps1") | Out-Null

function Test-PortListening([int]$Port) {
  return [bool](Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue)
}

function Start-IfNotListening([int]$Port, [string]$ScriptName, [string]$label) {
  if (Test-PortListening $Port) {
    Write-Host "[ok] $label ja ativo na porta $Port"
    return
  }
  Write-Host "[subindo] $label (segundo plano)..."
  $scriptPath = Join-Path $scriptsDir $ScriptName
  $escaped = $scriptPath -replace "'", "''"
  $logName = ($ScriptName -replace '\.ps1$', '') -replace 'start-', ''
  Start-HiddenPowerShellScript `
    -Command "& '$escaped'" `
    -WorkingDirectory $projectRoot `
    -ProjectRoot $projectRoot `
    -LogName $logName
}

Write-Host "RadioPoggers - preparando acesso celular (IP $lanIp)"
Write-Host ""

Start-IfNotListening -Port 8765 -ScriptName "start-local-api.ps1" -label "API"
Start-Sleep -Seconds 2
if (-not (Test-PortListening 5500)) {
  Write-Host "[subindo] Frontend HTTP (segundo plano)..."
  $serveScript = Join-Path $scriptsDir "serve-frontend.ps1"
  $serveEscaped = $serveScript -replace "'", "''"
  Start-HiddenPowerShellScript `
    -Command "& '$serveEscaped' -NoHttps" `
    -WorkingDirectory $projectRoot `
    -ProjectRoot $projectRoot `
    -LogName "frontend-http"
}
else {
  Write-Host "[ok] Frontend HTTP ja ativo na porta 5500"
}

Start-Sleep -Seconds 1
Start-IfNotListening -Port 5443 -ScriptName "start-frontend-https.ps1" -label "Frontend HTTPS"

Write-Host ""
Write-Host "Aguardando servicos (ate 15s)..."
$deadline = (Get-Date).AddSeconds(15)
while ((Get-Date) -lt $deadline) {
  if ((Test-PortListening 8765) -and (Test-PortListening 5500) -and (Test-PortListening 5443)) {
    break
  }
  Start-Sleep -Milliseconds 500
}

& (Join-Path $scriptsDir "test-https-frontend.ps1") -LanIp $lanIp

Write-Host ""
Write-Host "=== No celular / Radmin (microfone) ==="
if ($remoteHost) {
  Write-Host "  Ouvir + microfone: https://${remoteHost}:5443/frontend/"
}
Write-Host "  Wi-Fi local:       http://${lanIp}:5500/frontend/"
Write-Host "  Microfone HTTPS:   https://${lanIp}:5443/frontend/"
Write-Host "  Aceite o certificado (Avancado -> Continuar) e permita o microfone."
Write-Host "  Firewall Admin:    .\scripts\open-lan-firewall.ps1"
Write-Host ""
Write-Host "Se HTTPS travar: PowerShell Admin -> .\scripts\open-lan-firewall.ps1"
