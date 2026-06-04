param(
  [string[]]$ExtraHosts = @(),
  [switch]$Force
)

$ErrorActionPreference = "Stop"

$scriptsDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = Split-Path -Parent $scriptsDir
$sslDir = Join-Path $projectRoot "data\dev-ssl"
$certFile = Join-Path $sslDir "radiopoggers.crt"
$keyFile = Join-Path $sslDir "radiopoggers.key"
$configJs = Join-Path $projectRoot "frontend\config.js"

function Get-ConfigHost {
  if (-not (Test-Path $configJs)) {
    return ""
  }
  $raw = Get-Content $configJs -Raw -ErrorAction SilentlyContinue
  if ($raw -match 'azuracastBaseUrl:\s*"https?://([^"/]+)"') {
    return $Matches[1].Trim()
  }
  return ""
}

$hosts = [System.Collections.Generic.List[string]]::new()
foreach ($value in @("localhost", "127.0.0.1")) {
  if (-not $hosts.Contains($value)) {
    [void]$hosts.Add($value)
  }
}

$lanIp = (
  Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
  Where-Object {
    $_.IPAddress -match '^192\.168\.' -or $_.IPAddress -match '^10\.' -or $_.IPAddress -match '^172\.(1[6-9]|2[0-9]|3[0-1])\.'
  } |
  Sort-Object -Property InterfaceMetric |
  Select-Object -First 1 -ExpandProperty IPAddress
)
if ($lanIp -and -not $hosts.Contains($lanIp)) {
  [void]$hosts.Add($lanIp)
}

Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
  Where-Object { $_.IPAddress -match '^26\.' } |
  ForEach-Object {
    if (-not $hosts.Contains($_.IPAddress)) {
      [void]$hosts.Add($_.IPAddress)
    }
  }

$configHost = Get-ConfigHost
if ($configHost -and -not $hosts.Contains($configHost)) {
  [void]$hosts.Add($configHost)
}

$hostsFile = Join-Path $projectRoot "data\dev-access-hosts.txt"
if (Test-Path $hostsFile) {
  Get-Content $hostsFile | ForEach-Object {
    $line = $_.Trim()
    if ($line -and -not $line.StartsWith("#") -and -not $hosts.Contains($line)) {
      [void]$hosts.Add($line)
    }
  }
}

foreach ($value in $ExtraHosts) {
  $line = [string]$value
  if ($line -and -not $hosts.Contains($line)) {
    [void]$hosts.Add($line)
  }
}

New-Item -ItemType Directory -Force -Path $sslDir | Out-Null

$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) {
  $python = Get-Command py -ErrorAction SilentlyContinue
}
if (-not $python) {
  throw "Python nao encontrado para gerar certificado dev."
}

$hostArg = ($hosts -join ",")
$pyScript = Join-Path $scriptsDir "generate-dev-ssl.py"
$pyArgs = @($pyScript, "--ensure", "--hosts", $hostArg)
if ($Force) {
  $pyArgs += "--force"
}

if ($python.Name -eq "py.exe" -or $python.Name -eq "py") {
  & py @pyArgs
}
else {
  & python @pyArgs
}

if (-not ((Test-Path $certFile) -and (Test-Path $keyFile))) {
  throw "Falha ao gerar radiopoggers.crt e radiopoggers.key em data\dev-ssl\"
}

Write-Host "Certificado dev pronto: data\dev-ssl\radiopoggers.crt"
Write-Host "  Hosts no certificado: $($hosts -join ', ')"
Write-Host "  Amigos Radmin: https://<seu-ip-radmin>:5443/frontend/ (aceitar certificado 1x)"
