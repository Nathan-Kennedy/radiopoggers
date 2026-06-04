# Votacao em tempo real (Radio no Grale)

Sistema de democracia rock no player: skip, pedidos da estante e destino pos-import Spotify passam por voto quando ha **2 ou mais ouvintes ouvindo** (site aberto + stream tocando).

## Regras

| Situacao | Comportamento |
| --- | --- |
| 1 ouvinte no site (solo) | Overlay ~6s; **proposer** pode votar mesmo com radio pausada (ex.: apos preview na estante) |
| 2+ ouvintes no site | Overlay coletivo (~20s configuravel) com sorteio em empate |
| **Pular faixa** sozinho | Modal direto rapido (excecao) |
| **Pedir na estante** / **Spotify pos-import** | Sempre overlay de votacao (Tocar ja / Na fila), nunca so modal direto |
| Contagem | `sim` vs `nao + quem nao votou` (abstencao conta como nao) |
| Empate exato | Sorteio server-side + animacao rock no frontend |
| Resultado | Executa acao no AzuraCast; **Miku** fala frase especifica |

## Quem conta como ouvinte elegivel

- Heartbeat `POST /api/audience/heartbeat` com `listener_id` + `playing: true`
- Stream **nao pausado** (demo ou HLS/MP3)
- Expira em ~35s sem heartbeat

## Tipos de votacao

| type | Gatilho | Sim (yes) | Nao (no) |
| --- | --- | --- | --- |
| `skip_track` | Botao **Pular faixa** no player | Pula faixa (`/backend/skip`) | Nada |
| `library_request` | Botao **Pedir** na estante | **Tocar ja:** play imediato (`files/batch`, `do: immediate`) | **Na fila:** request AzuraCast (sem pular) |
| `spotify_import` | Apos import Spotify OK | Request 1a faixa + skip | Import feito; nao pula |

## Endpoints

| Metodo | Rota | Funcao |
| --- | --- | --- |
| POST | `/api/audience/heartbeat` | Presenca ouvindo |
| GET | `/api/audience/count` | `{ eligible, total_on_site }` |
| POST | `/api/vote/start` | Abre votacao (2+ ouvintes) |
| POST | `/api/vote/cast` | Voto `{ vote_id, listener_id, choice }` |
| POST | `/api/vote/execute-direct` | Acao imediata (1 ouvinte) |
| GET | `/api/vote/active` | Estado da votacao |
| GET | `/api/vote/events` | SSE tempo real |

`/api/nowplaying` inclui `audience_vote` e `audience`.

## Frontend (`frontend/config.js`)

```js
voteEnabled: true,
voteDurationSec: 20,
voteSoloDurationSec: 6,
audienceHeartbeatMs: 12000,
```

## Variaveis de ambiente

| Variavel | Padrao | Descricao |
| --- | --- | --- |
| `RADIOPOGGERS_VOTE_ENABLED` | `1` | Liga/desliga |
| `RADIOPOGGERS_VOTE_DURATION_SEC` | `45` | Duracao da votacao |
| `RADIOPOGGERS_AUDIENCE_TTL_SEC` | `35` | TTL do heartbeat |
| `RADIOPOGGERS_VOTE_LOTTERY_SEC` | `3.5` | Tempo do sorteio no servidor |
| `RADIOPOGGERS_AZURACAST_API_KEY` | — | Obrigatoria para skip, pedidos e **Tocar ja** (batch immediate) |

## Tocar ja vs Na fila (estante)

- **Tocar ja (sim):** a API resolve o caminho da midia no AzuraCast e chama `PUT /api/station/{id}/files/batch` com `"do": "immediate"` — toca a faixa pedida de verdade, sem depender de request+skip na ordem errada.
- **Na fila (nao):** enfileira via request AzuraCast; a faixa atual continua no ar ate a fila rodar.
- Exige faixa ja sincronizada em `imported/` (use **Tocar** no Spotify antes) e `data/azuracast-api-key.txt`.
- `fix-azuracast-station.ps1` define `enable_requests=1`, `request_threshold=0`, `request_delay=0`.

## Miku

Momentos novos em `miku_narrator.py`: `vote_skip_yes`, `vote_skip_no`, `vote_skip_lottery_yes`, `vote_skip_lottery_no`, `vote_spotify_now`, `vote_spotify_queue`, `vote_library_now`, `vote_library_queue`.

## Arquivos

```text
tools/radiopoggers-server/vote_system.py
tools/radiopoggers-server/server.py          (skip, execucao, endpoints)
frontend/app.js                            (overlay, SSE, heartbeat)
frontend/index.html                        (UI votacao)
frontend/styles.css                        (estilo rock + sorteio)
```

## Teste rapido

```powershell
Invoke-RestMethod http://127.0.0.1:8765/api/audience/count
Invoke-RestMethod -Method POST -Uri http://127.0.0.1:8765/api/audience/heartbeat `
  -ContentType "application/json" `
  -Body '{"listener_id":"test-1","playing":true}'
```

Com 2 heartbeats `playing: true` de IDs diferentes, abra o site e use **Pular faixa** ou **Pedir** na estante.
