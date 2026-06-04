$ErrorActionPreference = "Stop"

$station = if ($env:RADIOPOGGERS_STATION) { $env:RADIOPOGGERS_STATION } else { "radio-no-grale" }
$container = if ($env:RADIOPOGGERS_AZURACAST_CONTAINER) { $env:RADIOPOGGERS_AZURACAST_CONTAINER } else { "azuracast" }

Write-Host "Sincronizando metadados Now Playing da estacao '$station'..."
docker exec $container bash -lc "cd /var/azuracast/www && php backend/bin/console azuracast:sync:nowplaying:station $station"
Write-Host "Concluido."
Write-Host "Se o painel ainda mostrar faixa antiga: F5 no AzuraCast."
Write-Host "Se voltar a travar no fim da musica: Playlists > default > permitir artistas duplicados."
