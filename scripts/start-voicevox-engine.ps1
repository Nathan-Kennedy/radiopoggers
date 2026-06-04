$ErrorActionPreference = "Continue"

$engineCandidates = @(
  "$env:LOCALAPPDATA\Microsoft\WinGet\Packages\HiroshibaKazuyuki.VOICEVOX.CPU_Microsoft.Winget.Source_8wekyb3d8bbwe\VOICEVOX\vv-engine\run.exe",
  "$env:LOCALAPPDATA\Microsoft\WinGet\Packages\HiroshibaKazuyuki.VOICEVOX_Microsoft.Winget.Source_8wekyb3d8bbwe\VOICEVOX\vv-engine\run.exe"
)

try {
  $version = Invoke-RestMethod -Uri "http://127.0.0.1:50021/version" -TimeoutSec 2
  Write-Host "[ok] VOICEVOX Engine ja esta rodando: $version"
  exit 0
}
catch {
  # continua para tentar subir
}

$engine = $engineCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $engine) {
  $cmd = Get-Command VOICEVOX -ErrorAction SilentlyContinue
  if ($cmd) {
    $engineDir = Split-Path $cmd.Source -Parent
    $engine = Join-Path $engineDir "vv-engine\run.exe"
  }
}

if (-not (Test-Path $engine)) {
  Write-Host "[erro] Engine nao encontrado. Rode: winget install HiroshibaKazuyuki.VOICEVOX.CPU"
  exit 1
}

Write-Host "Iniciando VOICEVOX Engine em http://127.0.0.1:50021 ..."
Start-Process -FilePath $engine -ArgumentList "--host", "127.0.0.1", "--port", "50021" -WindowStyle Hidden

for ($attempt = 0; $attempt -lt 20; $attempt += 1) {
  Start-Sleep -Seconds 1
  try {
    $version = Invoke-RestMethod -Uri "http://127.0.0.1:50021/version" -TimeoutSec 2
    Write-Host "[ok] VOICEVOX Engine ativo: $version"
    exit 0
  }
  catch {
    continue
  }
}

Write-Host "[erro] Engine nao respondeu em :50021"
exit 1
