param(
  [int[]]$Ports = @(8765, 5500, 5443, 50021)
)

$ErrorActionPreference = "Continue"

function Stop-PortListener {
  param([int]$Port)

  $connections = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
  if (-not $connections) {
    Write-Host "[ok] Porta $Port - nada escutando."
    return
  }

  $pids = $connections.OwningProcess | Sort-Object -Unique
  foreach ($procId in $pids) {
    try {
      $proc = Get-Process -Id $procId -ErrorAction Stop
      Write-Host "[parando] Porta $Port - PID $procId ($($proc.ProcessName))"
      Stop-Process -Id $procId -Force -ErrorAction Stop
    }
    catch {
      Write-Host "[aviso] Nao consegui parar PID $procId na porta $Port : $_"
    }
  }
}

Write-Host "RadioPoggers - parando servicos locais (API, frontend, VOICEVOX)..."
foreach ($port in $Ports) {
  Stop-PortListener -Port $port
}
Write-Host "Concluido. AzuraCast/Docker nao foram parados (use .\scripts\stop-full-stack.ps1 ou stop-radio.ps1)."
