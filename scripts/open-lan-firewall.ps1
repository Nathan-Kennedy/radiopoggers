# Abre portas da RadioPoggers no firewall do Windows (Wi-Fi, Radmin VPN, etc.).
# Execute como Administrador: clique direito no PowerShell -> Executar como administrador
#   cd "c:\Projetos Dev\RadioPoggers"
#   .\scripts\open-lan-firewall.ps1

param(
  [int[]]$Ports = @(80, 5500, 5443, 8765)
)

$ErrorActionPreference = "Stop"

$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(
  [Security.Principal.WindowsBuiltInRole]::Administrator
)

if (-not $isAdmin) {
  Write-Host "ERRO: este script precisa ser executado como Administrador."
  Write-Host "Sem isso, o celular/Radmin fica carregando infinito nas portas bloqueadas (especialmente 5443)."
  Write-Host ""
  Write-Host "1. Abra PowerShell como Administrador"
  Write-Host "2. cd `"$((Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)))`""
  Write-Host "3. .\scripts\open-lan-firewall.ps1"
  exit 1
}

foreach ($port in $Ports) {
  $ruleName = "RadioPoggers TCP $port"
  $existing = Get-NetFirewallRule -DisplayName $ruleName -ErrorAction SilentlyContinue
  if ($existing) {
    Set-NetFirewallRule -DisplayName $ruleName -Profile Any -Enabled True -ErrorAction SilentlyContinue | Out-Null
    Write-Host "[ok] Regra atualizada (perfil Any): $ruleName"
    continue
  }

  New-NetFirewallRule `
    -DisplayName $ruleName `
    -Direction Inbound `
    -Action Allow `
    -Protocol TCP `
    -LocalPort $port `
    -Profile Any | Out-Null

  Write-Host "[criada] $ruleName (entrada TCP $port, todos os perfis incl. Radmin)"
}

Write-Host ""
Write-Host "Portas liberadas: $($Ports -join ', ')"
Write-Host "Radmin + microfone: https://<seu-ip-radmin>:5443/frontend/"
