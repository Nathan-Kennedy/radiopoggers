# Funcoes compartilhadas: start/stop do stack completo (Docker, AzuraCast, API, site, Discord).

. (Join-Path $PSScriptRoot "process-lib.ps1")

function Get-StackProjectRoot {
  param([string]$ScriptsDir = $PSScriptRoot)
  return Split-Path $ScriptsDir -Parent
}

function Invoke-StackWslCommand {
  param(
    [string]$Command,
    [string]$Distro = "Ubuntu-24.04"
  )

  if ($Distro.Trim().Length -gt 0) {
    wsl -d $Distro -- bash -lc $Command
  }
  else {
    wsl -- bash -lc $Command
  }
}

function Test-StackWslDistro {
  param([string]$Distro = "Ubuntu-24.04")

  if (-not (Get-Command wsl -ErrorAction SilentlyContinue)) {
    return @{ Ok = $false; Message = "WSL nao encontrado. Instale WSL2 (Ubuntu-24.04)." }
  }

  # wsl -l -v no PowerShell pode vir em UTF-16 (caracteres intercalados com \0).
  $list = (wsl -l -v 2>&1 | Out-String) -replace "`0", ""
  if ($list -notmatch [regex]::Escape($Distro)) {
    return @{
      Ok = $false
      Message = "Distro WSL '$Distro' nao encontrada. Rode: wsl -l -v"
    }
  }

  try {
    Invoke-StackWslCommand -Distro $Distro -Command "echo radiopoggers-wsl-ok" | Out-Null
    if ($LASTEXITCODE -ne 0) {
      return @{ Ok = $false; Message = "WSL '$Distro' nao responde. Abra o Ubuntu uma vez ou reinicie WSL." }
    }
  }
  catch {
    return @{ Ok = $false; Message = "Falha ao executar WSL '$Distro': $_" }
  }

  return @{ Ok = $true; Message = "" }
}

function Test-StackDockerEngine {
  if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    return @{
      Ok = $false
      Message = "Comando 'docker' nao encontrado. Instale o Docker Desktop."
    }
  }

  $null = docker version 2>&1
  if ($LASTEXITCODE -ne 0) {
    return @{
      Ok = $false
      Message = @(
        "Docker Desktop nao esta rodando ou nao responde.",
        "Abra o Docker Desktop, espere ficar 'Running' e tente de novo.",
        "Teste manual: docker ps"
      ) -join " "
    }
  }

  $psOut = docker ps --format "{{.Names}}" 2>&1
  if ($LASTEXITCODE -ne 0) {
    return @{
      Ok = $false
      Message = "docker ps falhou. Verifique Docker Desktop / integracao WSL2."
    }
  }

  return @{ Ok = $true; Message = ""; ContainerNames = @($psOut -split "`n" | Where-Object { $_.Trim() }) }
}

function Test-StackAzuraCastInstall {
  param(
    [string]$AzuraCastPath = "/mnt/c/Projetos Dev/RadioPoggers/~/azuracast",
    [string]$Distro = "Ubuntu-24.04"
  )

  $cmd = "test -d '$AzuraCastPath' && test -f '$AzuraCastPath/docker.sh' && echo OK"
  try {
    $out = Invoke-StackWslCommand -Distro $Distro -Command $cmd 2>&1 | Out-String
    if ($LASTEXITCODE -ne 0 -or $out -notmatch "OK") {
      return @{
        Ok = $false
        Message = @(
          "AzuraCast nao encontrado em '$AzuraCastPath' (docker.sh ausente).",
          "Instale com: .\scripts\install-azuracast-wsl.ps1"
        ) -join " "
      }
    }
  }
  catch {
    return @{ Ok = $false; Message = "Nao consegui verificar pasta AzuraCast no WSL: $_" }
  }

  return @{ Ok = $true; Message = "" }
}

function Test-StackAzuraCastContainer {
  param([string]$ContainerName = "azuracast")

  $status = docker inspect -f "{{.State.Status}}" $ContainerName 2>&1
  if ($LASTEXITCODE -ne 0) {
    return @{ Running = $false; Status = "missing" }
  }
  return @{ Running = ($status -eq "running"); Status = $status.Trim() }
}

function Test-StackAzuraCastHttp {
  param(
    [string]$Url = "http://127.0.0.1/",
    [int]$TimeoutSeconds = 8
  )

  try {
    $resp = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec $TimeoutSeconds
    return @{ Ok = ($resp.StatusCode -ge 200 -and $resp.StatusCode -lt 500); StatusCode = $resp.StatusCode }
  }
  catch {
    return @{ Ok = $false; StatusCode = 0; Error = $_.Exception.Message }
  }
}

function Assert-StackDockerReady {
  param(
    [switch]$RequireAzuraCast,
    [string]$AzuraCastPath = "/mnt/c/Projetos Dev/RadioPoggers/~/azuracast",
    [string]$Distro = "Ubuntu-24.04"
  )

  Write-Host "Verificando ambiente (WSL + Docker)..."
  Write-Host ""

  $wsl = Test-StackWslDistro -Distro $Distro
  if (-not $wsl.Ok) {
    throw $wsl.Message
  }
  Write-Host "[ok] WSL '$Distro'"

  $docker = Test-StackDockerEngine
  if (-not $docker.Ok) {
    throw $docker.Message
  }
  Write-Host "[ok] Docker Desktop respondendo (docker ps)"

  if ($RequireAzuraCast) {
    $install = Test-StackAzuraCastInstall -AzuraCastPath $AzuraCastPath -Distro $Distro
    if (-not $install.Ok) {
      throw $install.Message
    }
    Write-Host "[ok] AzuraCast instalado em WSL ($AzuraCastPath)"

    $container = Test-StackAzuraCastContainer
    if ($container.Running) {
      Write-Host "[ok] Container 'azuracast' ja esta rodando"
    }
    else {
      Write-Host "[info] Container azuracast ainda nao esta up (sera iniciado em seguida)"
    }
  }

  Write-Host ""
}

function Test-StackPortListening {
  param([int]$Port)
  return [bool](Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue)
}

function Test-StackLocalApiHttp {
  param(
    [string]$Url = "http://127.0.0.1:8765/api/health",
    [int]$TimeoutSeconds = 3
  )

  try {
    $resp = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec $TimeoutSeconds
    return @{ Ok = ($resp.StatusCode -ge 200 -and $resp.StatusCode -lt 500); StatusCode = $resp.StatusCode }
  }
  catch {
    return @{ Ok = $false; StatusCode = 0; Error = $_.Exception.Message }
  }
}

function Start-StackLocalApi {
  param([string]$ScriptsDir = $PSScriptRoot)

  if (Test-StackPortListening -Port 8765) {
    Write-Host "[ok] API local ja ativa na porta 8765"
    return
  }

  $projectRoot = Get-StackProjectRoot -ScriptsDir $ScriptsDir
  $apiScript = Join-Path $ScriptsDir "start-local-api.ps1"
  $escaped = $apiScript -replace "'", "''"
  Write-Host "Iniciando API local (segundo plano, janela oculta)..."
  Start-HiddenPowerShellScript `
    -Command "& '$escaped'" `
    -WorkingDirectory $projectRoot `
    -ProjectRoot $projectRoot `
    -LogName "local-api"
  Write-Host "  Log: data\logs\local-api.log"
}

function Wait-StackLocalApiReady {
  param(
    [int]$TimeoutSeconds = 90,
    [string]$HealthUrl = "http://127.0.0.1:8765/api/health"
  )

  Write-Host "Aguardando API local / estante (ate ${TimeoutSeconds}s)..."
  $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
  while ((Get-Date) -lt $deadline) {
    $health = Test-StackLocalApiHttp -Url $HealthUrl
    if ($health.Ok) {
      Write-Host "[ok] API local respondendo - estante e votacao disponiveis"
      return $true
    }
    Start-Sleep -Milliseconds 500
  }

  Write-Host "[aviso] API local nao respondeu. Estante ficara offline ate subir:"
  Write-Host "        .\scripts\start-local-api.ps1  (depois Ctrl+F5 no site)"
  return $false
}

function Wait-StackAzuraCastReady {
  param(
    [int]$TimeoutSeconds = 180,
    [string]$HttpUrl = "http://127.0.0.1/"
  )

  Write-Host "Aguardando AzuraCast ficar pronto (ate ${TimeoutSeconds}s)..."
  $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
  while ((Get-Date) -lt $deadline) {
    $container = Test-StackAzuraCastContainer
    if ($container.Running) {
      $http = Test-StackAzuraCastHttp -Url $HttpUrl -TimeoutSeconds 5
      if ($http.Ok) {
        Write-Host "[ok] AzuraCast respondendo em $HttpUrl"
        return $true
      }
    }
    Start-Sleep -Seconds 3
  }

  Write-Host "[aviso] AzuraCast pode ainda estar subindo. Confira http://localhost no navegador."
  return $false
}

function Stop-StackAzuraCast {
  param(
    [string]$AzuraCastPath = "/mnt/c/Projetos Dev/RadioPoggers/~/azuracast",
    [string]$Distro = "Ubuntu-24.04",
    [switch]$Quiet
  )

  if (-not $Quiet) {
    Write-Host "Parando AzuraCast..."
  }

  $stopped = $false
  $composeTemplate = @'
cd 'AZURACAST_PATH' && (./docker.sh down 2>/dev/null || ./docker.sh stop 2>/dev/null || true)
'@
  $composeCmd = $composeTemplate -replace 'AZURACAST_PATH', ($AzuraCastPath -replace "'", "'\''")
  try {
    Invoke-StackWslCommand -Distro $Distro -Command $composeCmd 2>&1 | Out-Null
    if ($LASTEXITCODE -eq 0) {
      $stopped = $true
    }
  }
  catch {
    if (-not $Quiet) {
      Write-Host "  [aviso] docker.sh down/stop falhou: $_"
    }
  }

  foreach ($name in @("azuracast", "azuracast_updater")) {
    $null = docker stop $name 2>&1
    if ($LASTEXITCODE -eq 0) {
      $stopped = $true
      if (-not $Quiet) {
        Write-Host "  [ok] Container $name parado"
      }
    }
  }

  $left = Test-StackAzuraCastContainer
  if ($left.Running -and -not $Quiet) {
    Write-Host "  [aviso] Container azuracast ainda aparece rodando"
    return $false
  }

  if (-not $Quiet) {
    Write-Host "[ok] AzuraCast parado"
  }
  return $true
}
