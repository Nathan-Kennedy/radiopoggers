$ErrorActionPreference = "Stop"

$station = if ($env:RADIOPOGGERS_STATION) { $env:RADIOPOGGERS_STATION } else { "radio-no-grale" }
$container = if ($env:RADIOPOGGERS_AZURACAST_CONTAINER) { $env:RADIOPOGGERS_AZURACAST_CONTAINER } else { "azuracast" }
$projectRoot = Split-Path $PSScriptRoot -Parent

Write-Host "Ajustando playlist do AzuraCast (permitir artistas repetidos)..."
python "$projectRoot\tools\query_azuracast_db.py" "UPDATE station_playlists SET avoid_duplicates = 0 WHERE id = 1;"

Write-Host "Habilitando pedidos de musica na estacao (estante / Tocar ja)..."
python "$projectRoot\tools\query_azuracast_db.py" "UPDATE station SET enable_requests = 1, request_threshold = 0, request_delay = 0 WHERE id = 1;"

Write-Host "Sincronizando Now Playing..."
docker exec $container bash -lc "cd /var/azuracast/www && php backend/bin/console azuracast:sync:nowplaying:station $station"

Write-Host "Reiniciando radio..."
docker exec $container bash -lc "cd /var/azuracast/www && php backend/bin/console azuracast:radio:restart $station"

Write-Host "Concluido. Atualize o painel do AzuraCast com F5."
