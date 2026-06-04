# Funcoes compartilhadas: start / stop / restart do bot Discord.

. (Join-Path $PSScriptRoot "process-lib.ps1")

function Get-DiscordBotProjectRoot {
  param([string]$ScriptsDir = $PSScriptRoot)
  return Split-Path $ScriptsDir -Parent
}

function Get-DiscordBotPidFile {
  param([string]$ProjectRoot = (Get-DiscordBotProjectRoot))
  return Join-Path $ProjectRoot "data\discord-bot.pid"
}

function Get-DiscordBotShutdownFile {
  param([string]$ProjectRoot = (Get-DiscordBotProjectRoot))
  return Join-Path $ProjectRoot "data\discord-bot.shutdown"
}

function Request-DiscordBotGracefulShutdown {
  param(
    [string]$ProjectRoot = (Get-DiscordBotProjectRoot),
    [switch]$Quiet
  )

  $shutdownFile = Get-DiscordBotShutdownFile -ProjectRoot $ProjectRoot
  $dir = Split-Path $shutdownFile -Parent
  if (-not (Test-Path $dir)) {
    New-Item -ItemType Directory -Path $dir -Force | Out-Null
  }
  Set-Content -Path $shutdownFile -Value (Get-Date).ToString("o") -Encoding utf8 -NoNewline
  if (-not $Quiet) {
    Write-Host "  Pedindo ao bot sair das calls no Discord..."
  }
}

function Clear-DiscordBotShutdownFile {
  param([string]$ProjectRoot = (Get-DiscordBotProjectRoot))

  $shutdownFile = Get-DiscordBotShutdownFile -ProjectRoot $ProjectRoot
  if (Test-Path $shutdownFile) {
    Remove-Item $shutdownFile -Force -ErrorAction SilentlyContinue
  }
}

function Test-DiscordBotCommandLine {
  param(
    [string]$CommandLine,
    [string]$ProjectRoot = ""
  )

  if (-not $CommandLine) { return $false }

  $normalized = $CommandLine -replace '\\', '/'

  if ($normalized -match 'discord-bot/bot\.py') { return $true }
  if ($normalized -match 'RadioPoggers' -and $normalized -match 'bot\.py' -and $normalized -notmatch 'server\.py') {
    return $true
  }

  # Instancias antigas: cwd em tools/discord-bot, linha de comando so "bot.py"
  if ($normalized -match '(^|[\s"])bot\.py(\s|"|$)') {
    return $true
  }

  if ($ProjectRoot -and $normalized -match [regex]::Escape(($ProjectRoot -replace '\\', '/')) -and $normalized -match 'bot\.py') {
    return $true
  }

  return $false
}

function Get-DiscordBotProcessIds {
  param([string]$ProjectRoot = (Get-DiscordBotProjectRoot))

  $ids = New-Object 'System.Collections.Generic.HashSet[int]'
  $pidFile = Get-DiscordBotPidFile -ProjectRoot $ProjectRoot

  if (Test-Path $pidFile) {
    $raw = (Get-Content $pidFile -ErrorAction SilentlyContinue | Select-Object -First 1).Trim()
    if ($raw -match '^\d+$') {
      [void]$ids.Add([int]$raw)
    }
  }

  $names = @('python.exe', 'py.exe', 'python3.exe')
  foreach ($name in $names) {
    Get-CimInstance Win32_Process -Filter "Name='$name'" -ErrorAction SilentlyContinue |
      Where-Object { Test-DiscordBotCommandLine -CommandLine $_.CommandLine -ProjectRoot $ProjectRoot } |
      ForEach-Object { [void]$ids.Add([int]$_.ProcessId) }
  }

  return @($ids | Sort-Object)
}

function Get-DiscordBotProcesses {
  param([string]$ProjectRoot = (Get-DiscordBotProjectRoot))

  $result = @()
  foreach ($procId in (Get-DiscordBotProcessIds -ProjectRoot $ProjectRoot)) {
    try {
      $proc = Get-Process -Id $procId -ErrorAction Stop
      $result += $proc
    }
    catch {
      # PID obsoleto no arquivo .pid ou processo ja encerrado.
    }
  }
  return $result
}

function Clear-DiscordBotPidFile {
  param([string]$ProjectRoot = (Get-DiscordBotProjectRoot))

  $pidFile = Get-DiscordBotPidFile -ProjectRoot $ProjectRoot
  if (Test-Path $pidFile) {
    Remove-Item $pidFile -Force -ErrorAction SilentlyContinue
  }
}

function Stop-DiscordBotProcessTree {
  param(
    [int]$ProcessId,
    [switch]$Quiet
  )

  if ($ProcessId -le 0) { return $false }

  if (-not $Quiet) {
    Write-Host "  Encerrando PID $ProcessId (arvore de processos)..."
  }

  & taskkill.exe /PID $ProcessId /T /F 2>$null | Out-Null
  if ($LASTEXITCODE -eq 0) { return $true }

  try {
    Stop-Process -Id $ProcessId -Force -ErrorAction Stop
    return $true
  }
  catch {
    if (-not $Quiet) {
      Write-Host "  [aviso] Nao consegui encerrar PID ${ProcessId}: $_"
    }
    return $false
  }
}

function Stop-AllDiscordBotProcesses {
  param(
    [string]$ProjectRoot = (Get-DiscordBotProjectRoot),
    [switch]$Quiet
  )

  $processes = Get-DiscordBotProcesses -ProjectRoot $ProjectRoot
  if (-not $processes -and -not $Quiet) {
    Write-Host "[ok] Nenhum processo do bot Discord encontrado."
  }

  foreach ($proc in $processes) {
    Stop-DiscordBotProcessTree -ProcessId $proc.Id -Quiet:$Quiet
  }

  Clear-DiscordBotPidFile -ProjectRoot $ProjectRoot
}

function Wait-DiscordBotProcessesExit {
  param(
    [string]$ProjectRoot = (Get-DiscordBotProjectRoot),
    [int]$TimeoutSeconds = 20,
    [switch]$Quiet
  )

  $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
  while ((Get-Date) -lt $deadline) {
    $left = Get-DiscordBotProcesses -ProjectRoot $ProjectRoot
    if (-not $left) {
      if (-not $Quiet) {
        Write-Host "[ok] Todos os processos do bot encerrados."
      }
      return $true
    }
    Start-Sleep -Milliseconds 400
  }

  $still = Get-DiscordBotProcesses -ProjectRoot $ProjectRoot
  if ($still -and -not $Quiet) {
    Write-Host "[aviso] Ainda restam $($still.Count) processo(s) do bot:"
    foreach ($proc in $still) {
      Write-Host "  PID $($proc.Id) ($($proc.ProcessName))"
    }
  }
  return (-not $still)
}

function Ensure-DiscordBotStopped {
  param(
    [string]$ProjectRoot = (Get-DiscordBotProjectRoot),
    [int]$GracefulSeconds = 18,
    [int]$TimeoutSeconds = 20,
    [switch]$Quiet
  )

  if (-not $Quiet) {
    Write-Host "Encerrando instancias do bot Discord (sai da call antes de matar o processo)..."
  }

  $running = Get-DiscordBotProcesses -ProjectRoot $ProjectRoot
  if ($running) {
    Request-DiscordBotGracefulShutdown -ProjectRoot $ProjectRoot -Quiet:$Quiet
    $graceOk = Wait-DiscordBotProcessesExit -ProjectRoot $ProjectRoot -TimeoutSeconds $GracefulSeconds -Quiet:$Quiet
    if (-not $graceOk) {
      if (-not $Quiet) {
        Write-Host "  Encerramento forcado (processo nao respondeu a tempo)..."
      }
      Stop-AllDiscordBotProcesses -ProjectRoot $ProjectRoot -Quiet:$Quiet
      $graceOk = Wait-DiscordBotProcessesExit -ProjectRoot $ProjectRoot -TimeoutSeconds $TimeoutSeconds -Quiet:$Quiet
    }
  }
  else {
    $graceOk = $true
    if (-not $Quiet) {
      Write-Host "[ok] Nenhum processo do bot Discord encontrado."
    }
  }

  if (-not $graceOk) {
    if (-not $Quiet) {
      Write-Host "Tentando encerrar processos restantes..."
    }
    Stop-AllDiscordBotProcesses -ProjectRoot $ProjectRoot -Quiet:$Quiet
    $graceOk = Wait-DiscordBotProcessesExit -ProjectRoot $ProjectRoot -TimeoutSeconds 8 -Quiet:$Quiet
  }

  Clear-DiscordBotPidFile -ProjectRoot $ProjectRoot
  Clear-DiscordBotShutdownFile -ProjectRoot $ProjectRoot
  return $graceOk
}

function Test-DiscordBotRunning {
  param([string]$ProjectRoot = (Get-DiscordBotProjectRoot))
  return [bool](Get-DiscordBotProcesses -ProjectRoot $ProjectRoot)
}

function Start-DiscordBotInNewWindow {
  param(
    [string]$ProjectRoot = (Get-DiscordBotProjectRoot),
    [string]$ScriptsDir = ""
  )

  if (-not $ScriptsDir) {
    $ScriptsDir = Join-Path $ProjectRoot "scripts"
  }

  $startScript = Join-Path $ScriptsDir "start-discord-bot.ps1"
  if (-not (Test-Path $startScript)) {
    throw "Script nao encontrado: $startScript"
  }

  $escapedScript = $startScript -replace "'", "''"
  Start-HiddenPowerShellScript `
    -Command "& '$escapedScript'" `
    -WorkingDirectory $ProjectRoot `
    -ProjectRoot $ProjectRoot `
    -LogName "discord-bot"
}

function Wait-DiscordBotReady {
  param(
    [string]$ProjectRoot = (Get-DiscordBotProjectRoot),
    [int]$TimeoutSeconds = 45
  )

  $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
  while ((Get-Date) -lt $deadline) {
    if (Test-DiscordBotRunning -ProjectRoot $ProjectRoot) {
      return $true
    }
    Start-Sleep -Milliseconds 500
  }
  return $false
}
