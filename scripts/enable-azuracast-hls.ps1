param(
  [int]$StationId = 1,
  [string]$StationShortcode = "radio-no-grale",
  [int]$HlsBitrate = 128,
  [string]$Container = $(if ($env:RADIOPOGGERS_AZURACAST_CONTAINER) { $env:RADIOPOGGERS_AZURACAST_CONTAINER } else { "azuracast" })
)

$ErrorActionPreference = "Stop"

$projectRoot = Split-Path $PSScriptRoot -Parent
$queryDb = Join-Path $projectRoot "tools\query_azuracast_db.py"

Write-Host "Habilitando HLS na estacao $StationId ($StationShortcode)..."

python $queryDb "UPDATE station SET enable_hls = 1, needs_restart = 1 WHERE id = $StationId;"
python $queryDb "INSERT INTO station_hls_streams (station_id, name, format, bitrate, listeners) SELECT $StationId, 'aac_${HlsBitrate}', 'aac', $HlsBitrate, 0 WHERE NOT EXISTS (SELECT 1 FROM station_hls_streams WHERE station_id = $StationId);"
python $queryDb "UPDATE station SET backend_config = JSON_SET(COALESCE(backend_config, '{}'), '$.hls_is_default', true, '$.hls_enable_on_public_player', true, '$.hls_segments_in_playlist', 8, '$.hls_segments_overhead', 3), needs_restart = 1 WHERE id = $StationId;"

Write-Host "Reiniciando radio..."
docker exec $Container bash -lc "cd /var/azuracast/www && php backend/bin/console azuracast:radio:restart $StationShortcode"

Write-Host "Sincronizando Now Playing..."
docker exec $Container bash -lc "cd /var/azuracast/www && php backend/bin/console azuracast:sync:nowplaying:station $StationShortcode"

$hlsUrl = "http://localhost/hls/$StationShortcode/live.m3u8"
Write-Host ""
Write-Host "HLS habilitado."
Write-Host "URL: $hlsUrl"
Write-Host "frontend/config.js: streamMode = 'hls' e hlsUrl apontando para essa URL."

try {
  $response = Invoke-WebRequest -Uri $hlsUrl -Method Head -TimeoutSec 15 -UseBasicParsing
  Write-Host "Teste HTTP: $($response.StatusCode)"
}
catch {
  Write-Host "Aviso: nao consegui validar $hlsUrl ainda. Aguarde ~30s e tente de novo."
  Write-Host $_.Exception.Message
}
