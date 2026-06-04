$ErrorActionPreference = "Continue"

function Test-Command {
  param([string]$Name)
  $command = Get-Command $Name -ErrorAction SilentlyContinue
  if ($command) {
    Write-Host "[ok] $Name -> $($command.Source)"
    return $true
  }

  Write-Host "[faltando] $Name"
  return $false
}

Write-Host "RadioPoggers - checagem local"
Write-Host ""

$pythonOk = (Test-Command "python") -or (Test-Command "py")
$spotdlOk = Test-Command "spotdl"
$dockerOk = Test-Command "docker"
$wslOk = Test-Command "wsl"

Write-Host ""
if ($pythonOk) {
  Write-Host "[ok] Frontend pode ser servido com scripts\serve-frontend.ps1"
}
else {
  Write-Host "[acao] Instale Python para usar o servidor estatico local sem npm."
}

if ($spotdlOk) {
  Write-Host "[ok] API local consegue baixar playlists pelo spotdl."
}
else {
  Write-Host "[acao] Para baixar playlist pelo frontend, rode: python -m pip install --upgrade spotdl"
}

if ($dockerOk -and $wslOk) {
  Write-Host "[ok] Ambiente parece pronto para AzuraCast em Docker/WSL2."
}
else {
  Write-Host "[acao] Para AzuraCast, instale Docker Desktop e habilite WSL2."
}

