# Inicia scripts PowerShell em segundo plano (janela oculta) com log opcional.

function Ensure-StackLogsDir {
  param([string]$ProjectRoot)

  $dir = Join-Path $ProjectRoot "data\logs"
  if (-not (Test-Path $dir)) {
    New-Item -ItemType Directory -Path $dir -Force | Out-Null
  }
  return $dir
}

function Start-HiddenPowerShellScript {
  param(
    [Parameter(Mandatory = $true)]
    [string]$Command,
    [string]$WorkingDirectory = "",
    [string]$ProjectRoot = "",
    [string]$LogName = ""
  )

  if (-not $WorkingDirectory) {
    $WorkingDirectory = if ($ProjectRoot) { $ProjectRoot } else { (Get-Location).Path }
  }
  if (-not $ProjectRoot) {
    $ProjectRoot = $WorkingDirectory
  }

  $argList = @("-NoExit", "-ExecutionPolicy", "Bypass", "-Command")
  if ($LogName) {
    $logFile = Join-Path (Ensure-StackLogsDir -ProjectRoot $ProjectRoot) "$LogName.log"
    $escapedLog = ($logFile -replace '\\', '/') -replace "'", "''"
    $argList += "& { `$ErrorActionPreference = 'Continue'; $Command *>&1 | Tee-Object -FilePath '$escapedLog' -Append }"
  }
  else {
    $argList += $Command
  }

  Start-Process -FilePath "powershell.exe" `
    -WorkingDirectory $WorkingDirectory `
    -WindowStyle Hidden `
    -ArgumentList $argList | Out-Null
}
