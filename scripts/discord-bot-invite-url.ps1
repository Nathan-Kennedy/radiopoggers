# Gera o link OAuth para adicionar o bot RADIO NO GRALE a um servidor Discord.
param(
  [string]$InviteCode = "r3BN7Azna",
  [string]$GuildId = "",
  [switch]$OpenBrowser
)

$ErrorActionPreference = "Stop"
$root = Split-Path $PSScriptRoot -Parent
$configFile = Join-Path $root "data\discord-bot-config.json"
$config = Get-Content $configFile -Raw | ConvertFrom-Json
$clientId = $config.application_id

# Conectar + Falar + Ver canais + Mensagens + Embed + Comandos slash
$permissions = [uint64]2152282368

if (-not $GuildId -and $InviteCode) {
  $code = $InviteCode -replace '^https?://(www\.)?discord\.gg/', '' -replace '/$', ''
  Write-Host "Resolvendo convite $code ..."
  $invite = Invoke-RestMethod -Uri "https://discord.com/api/v10/invites/$code" -Headers @{"User-Agent"="RadioPoggers"} -TimeoutSec 15
  $GuildId = $invite.guild_id
  if ($invite.guild.name) {
    Write-Host "Servidor: $($invite.guild.name) (ID $GuildId)"
  }
}

$query = @{
  client_id = $clientId
  permissions = $permissions
  scope = "bot applications.commands"
}
if ($GuildId) {
  $query.guild_id = $GuildId
  $query.disable_guild_select = "true"
}

$uri = "https://discord.com/oauth2/authorize?" + (($query.GetEnumerator() | ForEach-Object { "$($_.Key)=$($_.Value)" }) -join "&")
Write-Host ""
Write-Host "Link para ADICIONAR O BOT (voce precisa ser Admin do servidor):"
Write-Host $uri
Write-Host ""
Write-Host "Convite de PESSOAS para entrar no grupo (nao e o bot):"
Write-Host "https://discord.gg/$($InviteCode -replace '^https?://(www\.)?discord\.gg/', '')"
Write-Host ""

if ($OpenBrowser) {
  Start-Process $uri
}
