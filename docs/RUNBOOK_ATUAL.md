# Runbook Atual da RadioPoggers / Alta Cupula

Este documento registra o estado atual que esta funcionando no PC: URLs, scripts, configuracoes, fluxos do frontend e da API local, e solucoes para problemas comuns.

## Estado Atual

Ambiente validado:

- Windows com Docker Desktop rodando.
- WSL2 com distro `Ubuntu-24.04`.
- AzuraCast instalado e rodando em Docker (`azuracast`, `azuracast_updater`).
- Frontend local em HTML/CSS/JS puro (marca **RADIO NO GRALE**, logo **RG**).
- API local Python em `http://127.0.0.1:8765` com sync automatico de Now Playing, **voice drop**, **narradora Miku** (global) e **Hoshino** (Gemini, opt-in no player).
- Estacao no AzuraCast: `RADIO NO GRALE`.
- Shortcode: `radio-no-grale`.
- ID numerico da estacao (API): `1`.
- Stream MP3 (fallback): `http://localhost/listen/radio-no-grale/radio.mp3`.
- Stream HLS (player web): `http://localhost/hls/radio-no-grale/live.m3u8`.
- Playlist Linkin Park importada: **44 faixas prontas** em `data/spotify-imported.json`.
- Bot Discord opcional: ponte de voz com Miku + ouvintes, comandos `/play`, sync AzuraCast via API.

## URLs Importantes

| Uso | URL |
| --- | --- |
| Painel AzuraCast | `http://localhost` |
| Pagina publica da radio | `http://localhost/public/radio-no-grale` |
| Stream MP3 | `http://localhost/listen/radio-no-grale/radio.mp3` |
| Stream HLS (recomendado no site) | `http://localhost/hls/radio-no-grale/live.m3u8` |
| Now Playing (correto) | `http://localhost/api/nowplaying/1` |
| Now Playing (lista) | `http://localhost/api/nowplaying` |
| Now Playing static | `http://localhost/api/nowplaying_static/radio-no-grale.json` |
| Frontend Alta Cupula | `http://localhost:5500/frontend/` |
| API local | `http://127.0.0.1:8765` |
| Health API local | `http://127.0.0.1:8765/api/health` |
| Manifesto | `http://127.0.0.1:8765/api/manifest` |
| Now Playing enriquecido | `http://127.0.0.1:8765/api/nowplaying` |
| Voice drop ativo | `http://127.0.0.1:8765/api/voice-drop/active` |
| Status Miku | `http://127.0.0.1:8765/api/miku/status` |
| Status Hoshino | `http://127.0.0.1:8765/api/hoshino/status` |

**Importante:** a URL `http://localhost/api/nowplaying/radio-no-grale` retorna **404** nesta instalacao. Use `/api/nowplaying/1` ou a API local.

## Portas em Uso

| Porta | Processo |
| --- | --- |
| `80` | AzuraCast HTTP |
| `443` | AzuraCast HTTPS |
| `2022` | SFTP AzuraCast |
| `8000+` | Streams Icecast |
| `5500` | Frontend estatico |
| `8765` | API local RadioPoggers |

## Marca e Interface (Frontend)

Identidade visual atual:

- Nome exibido: **RADIO NO GRALE** (logo **RG** no header).
- Tagline: **A RADIO MAIS POGGERS DE RONDONIA STATE OF BRAZIL**.
- Estilo: rock/industrial — preto, vermelho, tipografia Bebas Neue + IBM Plex Mono.
- Player com capa, metadados, **barra de progresso** (elapsed/duration), controles Play/Som/Volume.
- Stream principal: **HLS** (`hls.js`); MP3 como fallback.
- Fundo ASCII: **toca** com musica, **sentado** ao pausar (online), **off** (macaco) quando transmissao offline ou API NP inacessivel.
- Luz reativa: **canvas de ondas** (estilo NCS, vermelho rock) no canto inferior direito.
- **Voice drop:** gravacao pelo mic, barras reativas, efeito de locucao FM, ducking sidechain na musica.
- **Narradora Miku:** locucoes automaticas VOICEVOX; legenda digitada + ASCII falando no `#streamMessage` (ver `docs/MIKU_NARRATOR.md` e `docs/MELHORIAS_PLAYER_E_MIKU.md`).
- **Narradora Hoshino:** opt-in no modal **Narradora**; Gemini Kore; legenda roxa + ASCII `hoshino falando.json` (ver `docs/HOSHINO_NARRATOR.md`).
- **Votacao ao vivo:** skip, pedidos e Spotify pos-import com democracia rock (ver `docs/VOTACAO_OUVINTES.md`).
- Historico de faixas (sem botoes Demo/Atualizar — atualizacao automatica a cada 3s).
- Secao **Playlist importada**: campo Spotify + botao **Tocar** (nao "Baixar").
- Secao **Biblioteca local** (estante de discos): busca, filtros, preview local, pedido na radio e playlist pessoal.
- Estante **atualiza sozinha** durante import Spotify (poll do job + `libraryAutoRefreshMs`) e ao fim do sync (`rebuild_library_catalog`).

Comportamento do frontend:

- Poll de Now Playing a cada **3 segundos** via API local.
- Contador de progresso recalculado com `played_at` quando disponivel.
- **Sincronia com o audio:** compensacao automatica da latencia HLS (`liveSyncPosition` / `hls.latency`) para o contador acompanhar o que voce ouve, nao so o relogio do servidor.
- Ao importar playlist: formulario **bloqueia** ate terminar (evita sobrecarga).
- `reloadOnTrackChange: false` — nao recarrega a pagina inteira a cada faixa.
- Manifesto carregado automaticamente ao abrir (`/api/manifest` ou `data/spotify-imported.json`).

Arquivo de config:

```text
frontend/config.js
```

Valores atuais:

```js
window.RADIOPOGGERS_CONFIG = {
  azuracastBaseUrl: "http://localhost",
  azuracastPanelUrl: "http://localhost",
  stationShortcode: "radio-no-grale",
  stationId: 1,
  streamUrl: "http://localhost/listen/radio-no-grale/radio.mp3",
  streamMode: "hls",
  hlsUrl: "http://localhost/hls/radio-no-grale/live.m3u8",
  nowPlayingMode: "auto",
  demoMode: "auto",
  localApiUrl: "http://127.0.0.1:8765",
  spotifyManifestUrl: "../data/spotify-imported.json",
  pollIntervalMs: 3000,
  reloadOnTrackChange: false,
  stationDisplayName: "RADIO NO GRALE",
  mikuNarratorEnabled: true,
  mikuVoiceDetuneCents: 0,
  hoshinoVoicePlaybackRate: 1.13,
  libraryAutoRefreshMs: 15000,
  streamProgressLatencySec: 0,
  streamProgressLatencyFallbackSec: 4,
  asciiColorMode: "mono"
};
```

- **`streamProgressLatencySec`:** `0` = auto (mede latencia HLS). Valor fixo em segundos se quiser calibrar manualmente.
- **`streamProgressLatencyFallbackSec`:** atraso padrao quando HLS ainda nao mediu (MP3 ou inicio do play).

Detalhes de voice drop, Miku, HLS e ducking: **`docs/MELHORIAS_PLAYER_E_MIKU.md`**.

## API Local (`tools/radiopoggers-server/server.py`)

Endpoints:

| Metodo | Rota | Funcao |
| --- | --- | --- |
| GET | `/api/health` | Status da API |
| GET | `/api/manifest` | Manifesto com rescan de arquivos locais |
| GET | `/api/nowplaying` | Now Playing enriquecido |
| GET | `/api/library` | Catalogo global com busca/filtros (cache; `?refresh=1` forca rebuild) |
| GET | `/api/library/meta` | Revisao do catalogo |
| GET | `/api/library/filters` | Artistas e albuns para filtros |
| GET | `/api/import-spotify/inspect` | Playlist ja importada? (evita redownload) |
| GET | `/api/import-spotify/status` | Status do job de import |
| GET | `/api/library/preview/{track_id}` | Preview local de MP3 |
| POST | `/api/library/request` | Pedido de faixa na fila AzuraCast |
| POST | `/api/import-spotify` | spotdl + manifesto + sync AzuraCast |
| POST | `/api/voice-drop` | Upload de chamada gravada (ouvinte) |
| GET | `/api/voice-drop/active` | Chamada/locucao ativa para o player |
| GET | `/api/voice-drop/file/{id}` | Arquivo de audio do drop |
| GET | `/api/miku/status` | Status TTS / VOICEVOX / katakana |
| POST | `/api/miku/narrate` | Gera locucao Miku manual (debug) |
| GET | `/api/hoshino/status` | Status Gemini / Kore |
| POST | `/api/hoshino/narrate` | Gera locucao Hoshino (cliente opt-in) |
| POST | `/api/audience/heartbeat` | Presenca ouvinte ouvindo |
| GET | `/api/audience/count` | Ouvintes elegiveis para votacao |
| POST | `/api/vote/start` | Abre votacao coletiva |
| POST | `/api/vote/cast` | Registra voto sim/nao |
| POST | `/api/vote/execute-direct` | Acao imediata (1 ouvinte) |
| GET | `/api/vote/active` | Votacao ativa |
| GET | `/api/vote/events` | SSE de votacao |

Modulos auxiliares:

- `tools/radiopoggers-server/miku_narrator.py` — locucoes automaticas Miku.
- `tools/radiopoggers-server/hoshino_narrator.py` — templates e TTS Hoshino (Gemini).
- `tools/radiopoggers-server/gemini_narrator.py` — cliente Gemini TTS.
- `tools/radiopoggers-server/pt_katakana.py` — portugues → katakana para VOICEVOX.

Now Playing enriquecido inclui `voice_drop` e metadados Miku quando aplicavel.

Fluxo:

1. Busca AzuraCast em `/api/nowplaying/1` (live), depois static.
2. Se metadados **stale** (faixa no fim, "Estacao Offline", titulo divergente), usa **`song_history`** do MariaDB (`timestamp_end IS NULL`).
3. Fallback: fila `station_queue` (somente faixas `imported/` ja iniciadas, nao agendadas no futuro).
4. Cruza com `data/spotify-imported.json` para capa/Spotify URL.
5. **Sync automatico** a cada 20s quando AzuraCast esta desatualizado (`azuracast:sync:nowplaying:station`).

Manifesto:

- Arquivo principal: `data/spotify-imported.json` (ultima importacao).
- Catalogo global: `data/library-catalog.json` (todas as faixas `ready`, deduplicadas).
- `/api/manifest` reescaneia `library/Inbox`, `library/Managed` e `Spotdl` e marca faixas existentes como `ready`.
- **Nao use** `spotify-linkin-park.json` como fonte principal (e metadata-only, tudo pendente).

Biblioteca local (frontend):

1. Painel **Estante de discos** carrega `GET /api/library` (fallback JSON estatico se API lenta).
2. **Ouvir** toca preview via `/api/library/preview/{track_id}` — **`probeLocalApiBase()`** resolve LAN vs `127.0.0.1`.
3. **Pedir** em cada faixa (estante + Minha playlist) → votacao → **Tocar ja** ou **Na fila**.
4. **+ Lista** salva selecao em `localStorage`.
5. Requer `data/azuracast-api-key.txt` + **`start-local-api.ps1`** (nao so `python server.py` se precisar de Pedir/preview na LAN).
6. Ver **`docs/LOCAL_LIBRARY.md`** para troubleshooting preview/pedidos.

Variaveis de ambiente opcionais:

```text
RADIOPOGGERS_STATION=radio-no-grale
RADIOPOGGERS_STATION_ID=1
RADIOPOGGERS_NOWPLAYING_SYNC_SECONDS=20
RADIOPOGGERS_AZURACAST_CONTAINER=azuracast
RADIOPOGGERS_AZURACAST_BASE_URL=http://localhost
RADIOPOGGERS_AZURACAST_API_KEY=...   # ou data/azuracast-api-key.txt
RADIOPOGGERS_VOICE_DROP_DELIVERY_GRACE_SEC=90
RADIOPOGGERS_MIKU_TRACK_CHANGE_DELAY_SEC=10
```

## Scripts PowerShell

| Script | Funcao |
| --- | --- |
| `scripts/start-radio.ps1` | Sobe AzuraCast via WSL (`docker.sh up`) |
| `scripts/stop-radio.ps1` | Para AzuraCast |
| `scripts/serve-frontend.ps1` | Serve frontend na porta 5500 |
| `scripts/start-local-api.ps1` | API local na porta 8765 (+ tenta VOICEVOX) |
| `scripts/start-voicevox-engine.ps1` | Sobe VOICEVOX Engine headless :50021 |
| `scripts/install-voicevox-miku.ps1` | Guia/instalacao VOICEVOX para Miku |
| `scripts/install-miku-narrator.ps1` | Fallback edge-tts para Miku |
| `scripts/enable-azuracast-hls.ps1` | Habilita HLS no AzuraCast (player web) |
| `scripts/open-radio.ps1` | Abre URLs no navegador |
| `scripts/check-env.ps1` | Verifica Python, Docker, etc. |
| `scripts/sync-nowplaying.ps1` | Sync manual de metadados Now Playing |
| `scripts/fix-azuracast-station.ps1` | Corrige playlist + sync + restart da radio |
| `scripts/start-full-stack.ps1` | Sobe AzuraCast + API + frontend (atalho) |
| `scripts/stop-local-stack.ps1` | Para API, frontend e VOICEVOX (portas) |
| `scripts/start-discord-bot.ps1` | Bot Discord (mata instancias antigas antes de subir) |
| `scripts/stop-discord-bot.ps1` | Para todas as instancias do bot (sai das calls) |
| `scripts/restart-discord-bot.ps1` | Stop + start do bot (`-NewWindow` opcional) |
| `scripts/test-radiopoggers.ps1` | Testes HTTP automaticos da stack |

Ferramenta auxiliar:

```text
tools/query_azuracast_db.py
```

Executa SQL no MariaDB do container (ex.: conferir `avoid_duplicates`).

## Como Ligar e Desligar Tudo

Guia dedicado com todos os comandos (Docker, WSL, terminais, testes):

**`docs/LIGAR_DESLIGAR.md`**

Resumo apos reiniciar o PC:

1. Abra o **Docker Desktop**.
2. `docker ps` — deve aparecer `azuracast`; senao `.\scripts\start-radio.ps1`
3. Atalho: `.\scripts\start-full-stack.ps1 -SkipAzuraCast -OpenBrowser`  
   **ou** manual: `start-local-api.ps1` + `serve-frontend.ps1 -Open`
4. `http://localhost:5500/frontend/` — **Ctrl+F5** se cache antigo.

Desligar locais: `.\scripts\stop-local-stack.ps1`  
Desligar radio: `.\scripts\stop-radio.ps1`

Testes: `.\scripts\test-radiopoggers.ps1`

Se `start-local-api.ps1` falhar por encoding no PowerShell, suba a API manualmente:

```powershell
$env:RADIOPOGGERS_MIKU_TTS = "voicevox"
$env:RADIOPOGGERS_MIKU_REQUIRE_VOICEVOX = "1"
python tools\radiopoggers-server\server.py
```

Dependencia spotdl:

```powershell
python -m pip install --upgrade spotdl
```

## Estacao no AzuraCast

```text
Nome: RADIO NO GRALE
Shortcode: radio-no-grale
ID: 1
Descricao: A RADIO MAIS POGGERS DE RONDONIA STATE OF BRAZIL
Genero: SOU DO ROCK
Fuso: America/Porto_Velho
Transmissao: Icecast + Liquidsoap AutoDJ
Playlist padrao: default
Midia importada: imported/*.mp3
```

### Playlist `default` — configuracao critica

Com shuffle e muitas faixas do **mesmo artista** (Linkin Park), o AzuraCast pode travar metadados se **evitar duplicatas** estiver ligado.

**Correcao aplicada:**

```sql
UPDATE station_playlists SET avoid_duplicates = 0 WHERE id = 1;
```

Script automatico:

```powershell
.\scripts\fix-azuracast-station.ps1
```

No painel: **Playlists → default → Edit** → desmarque **Avoid Duplicate Artists/Titles**.

## Fluxo Spotify pelo Frontend (botao Tocar)

1. Cole link de playlist ou faixa Spotify.
2. Clique **Tocar**.
3. Frontend valida URL e **bloqueia** o formulario ate concluir.
4. POST para `http://127.0.0.1:8765/api/import-spotify`.
5. API executa `spotdl download` → `library/Inbox/Spotdl` (ou reutiliza faixas do catalogo).
6. Gera/atualiza `data/spotify-imported.json`, `.m3u` e `data/library-catalog.json`.
7. Copia MP3 para AzuraCast (`imported/`), vincula playlist `default`, reinicia radio.
8. Define `avoid_duplicates = 0` na importacao.
9. **Estante de discos** no site atualiza automaticamente (fases `catalog`, `sync`, `done` do job + refresh final).

Aviso exibido durante download:

```text
Baixando playlist... pode levar varios minutos. Aguarde e nao envie outro link.
```

## Caminhos Importantes

```text
C:\Projetos Dev\RadioPoggers
C:\Projetos Dev\RadioPoggers\~\azuracast          AzuraCast Docker
library\Inbox                                      Entrada manual
library\Inbox\Spotdl                               Downloads spotdl
library\Managed                                    Biblioteca organizada
data\spotify-imported.json                         Manifesto da ultima importacao
data\library-catalog.json                          Catalogo global deduplicado
data\spotify-imported.m3u                          Playlist M3U gerada
frontend\config.js                                 Config do site
tools\radiopoggers-server\server.py                  API local
```

## Testes automaticos

```powershell
.\scripts\test-radiopoggers.ps1
# ou: python scripts\test-radiopoggers-api.py
```

Valida API, biblioteca, preview, votacao, inspect Spotify, AzuraCast, HLS, frontend e assets ASCII.

## Testes Rapidos (manual)

API local:

```powershell
python -c "import json,urllib.request; d=json.load(urllib.request.urlopen('http://127.0.0.1:8765/api/health')); print(d)"
python -c "import json,urllib.request; d=json.load(urllib.request.urlopen('http://127.0.0.1:8765/api/nowplaying')); print(d['now_playing']['song']['title'], d.get('radio_poggers_metadata'))"
```

AzuraCast live vs static:

```powershell
python -c "import json,urllib.request; live=json.load(urllib.request.urlopen('http://localhost/api/nowplaying/1')); static=json.load(urllib.request.urlopen('http://localhost/api/nowplaying_static/radio-no-grale.json')); print('live',live['now_playing']['song']['title']); print('static',static['now_playing']['song']['title'])"
```

Stream MP3:

```powershell
python -c "import urllib.request; r=urllib.request.urlopen('http://localhost/listen/radio-no-grale/radio.mp3',timeout=8); print(r.status,r.headers.get('content-type'))"
```

Stream HLS:

```powershell
python -c "import urllib.request; r=urllib.request.urlopen('http://localhost/hls/radio-no-grale/live.m3u8',timeout=8); print(r.status,r.headers.get('content-type'))"
```

### Habilitar HLS no AzuraCast (recomendado para o site)

O player web usa **HLS + hls.js** (`streamMode: "hls"`) para evitar travamentos do MP3 ao vivo no Chrome.

```powershell
.\scripts\enable-azuracast-hls.ps1
```

Depois **Ctrl+F5** no site. Confira `frontend/config.js`:

```js
streamMode: "hls",
hlsUrl: "http://localhost/hls/radio-no-grale/live.m3u8",
```

## Problemas e Solucoes

### Painel AzuraCast mostra faixa errada ou "Estacao Offline" (audio toca normal)

O stream (Liquidsoap) e os metadados (Now Playing) sao **independentes**. O painel pode congelar no ultimo segundo da faixa anterior.

Solucao:

```powershell
.\scripts\sync-nowplaying.ps1
```

Depois **F5** no painel. A API local tenta sync automatico a cada 20s. Confirme `avoid_duplicates = 0` na playlist.

### Site mostra musica diferente do painel AzuraCast

Normal quando AzuraCast esta stale. O site usa a **API local**, que le `song_history` e corrige. Com sync + fix da playlist, ambos convergem.

### Frontend mostra tudo pendente na playlist

Verifique se carrega `spotify-imported.json`, nao `spotify-linkin-park.json`. API local deve estar ligada. Manifesto na API reescaneia disco e atualiza status `ready`.

### Player / contador travados

- Use **Ctrl+F5**.
- Confirme API local rodando.
- Endpoint correto: `/api/nowplaying/1`, nao `/api/nowplaying/radio-no-grale`.

### Metadados nao atualizam sozinhos

Rode uma vez:

```powershell
.\scripts\fix-azuracast-station.ps1
```

Mantenha API local ligada (thread de sync). Verifique logs:

```powershell
docker logs --tail 50 azuracast
```

Warnings comuns:

```text
Playlist "default" did not return a playable track
Duplicate prevention yielded no playable song
```

→ `avoid_duplicates = 0` e faixas em `imported/` na playlist `default`.

### API local nao responde / porta 8765 ocupada

```powershell
.\scripts\start-local-api.ps1
```

Se porta ocupada, mate processo antigo ou reinicie o script.

**Importante:** `python tools\radiopoggers-server\server.py` sozinho escuta em `127.0.0.1` e **nao** carrega `azuracast-api-key.txt` automaticamente. Para Pedir na estante + celular na LAN, use **`start-local-api.ps1`**.

### Preview Ouvir falha mas estante lista faixas

- Lista pode vir de `library-catalog.json` estatico; preview **exige** API.
- Confira `probeLocalApiBase`: health em `http://127.0.0.1:8765/api/health`.
- Ctrl+F5 apos subir API.

### Botoes Pedir desabilitados

- Crie `data/azuracast-api-key.txt` e reinicie **`start-local-api.ps1`**.
- Health deve mostrar `azuracast.requests_available: true`.

### `Queue is empty`

Playlist `default` sem midia tocavel. Reimporte ou vincule arquivos `imported/` via sync do frontend.

### Bot Discord sem voz / duplicado / `davey`

```powershell
.\scripts\stop-discord-bot.ps1
.\scripts\start-discord-bot.ps1
```

No Discord: `/play` de novo na call. Ver **`docs/DISCORD_BOT.md`**.

### `/play musica:` — faixa na biblioteca, erro AzuraCast

A API tenta sync leve automatico. Confira Docker + `data/azuracast-api-key.txt`. Persistindo: `.\scripts\fix-azuracast-station.ps1`.

### `/play musica:` — busca Spotify falhou

Crie `data/spotify-api-credentials.txt` (veja `spotify-api-credentials.example.txt`) e reinicie a API.

## Comandos Uteis

```powershell
docker ps
docker logs --tail 120 azuracast
.\scripts\sync-nowplaying.ps1
.\scripts\fix-azuracast-station.ps1
python tools\query_azuracast_db.py "SELECT id, name, avoid_duplicates FROM station_playlists;"
docker exec azuracast bash -lc "cd /var/azuracast/www && php backend/bin/console azuracast:radio:restart radio-no-grale"
.\scripts\stop-discord-bot.ps1
.\scripts\restart-discord-bot.ps1 -NewWindow
```

## O Que Nao Fazer

- Nao apagar `~\azuracast` sem backup.
- Nao mudar shortcode sem atualizar `frontend/config.js`.
- Nao commitar credenciais Spotify.
- Nao enviar multiplos links Spotify enquanto importacao roda.
- Nao usar spotdl sem direito de baixar/transmitir cada faixa.
- Nao confiar em `/api/nowplaying/radio-no-grale` (404 nesta instalacao).

## Historico de Melhorias (sessao recente)

Indice completo de funcionalidades: **`docs/GUIA_COMPLETO.md`**.  
Ligar/desligar: **`docs/LIGAR_DESLIGAR.md`**.

Registro do que foi implementado e ajustado. Documentacao do player e Miku: **`docs/MELHORIAS_PLAYER_E_MIKU.md`**.

### Infra e Now Playing (base)

- API Now Playing: endpoint por ID, sync auto, fonte `song_history`, fila corrigida.
- Manifesto: rescan local, `spotify-imported.json` como principal.
- AzuraCast: `avoid_duplicates` desligado, scripts de sync/fix.
- HLS habilitado no AzuraCast; player web com **hls.js** (`streamMode: "hls"`).

### Frontend e audio

- Marca **RADIO NO GRALE** (logo RG), UI rock, progresso, ASCII play/idle/off-air.
- Biblioteca: cache, preview local, pedido com votacao, inspect Spotify sem redownload.
- Canvas de ondas reativas no canto inferior direito.
- Grafo Web Audio lazy no Play (corrige stream mudo).
- Ducking **sidechain** real na musica durante voice drop e locucao Miku.
- Voice drop: mic estilo WhatsApp, `applyBroadcastVoiceEffect`, upload via API.
- Botao Tocar com lock; remocao de botoes dev (Demo, Atualizar, Carregar).
- Player: titulo/artista/capa atualizam via poll 3s; contador com `played_at`.

### Narradora Miku

- VOICEVOX local com speakers normais (menos agudo).
- Transliteracao **PT → katakana** (`pt_katakana.py`) para portugues nitido com sotaque japones.
- Katakana continuo (sem pausa entre palavras); prosodia ajustada.
- Locucao em toda troca de faixa + bumper ~58% no meio da musica.
- EQ de locucao variante `miku` no frontend.
- **Legenda digitada** + ASCII falando no player; voice_drop com campo `caption` e TTL estendido na API.

Guias: `docs/MIKU_NARRATOR.md`, `docs/HOSHINO_NARRATOR.md`, `docs/MELHORIAS_PLAYER_E_MIKU.md`.

### Hoshino + estante (jun/2026)

- Modal **Narradora** (Miku vs Hoshino); `localStorage` `radiopoggers_narrator`.
- Hoshino: Gemini Kore, scheduler no cliente, legenda roxa, ASCII **`hoshino falando.json`** (pequeno, celula 3px).
- Tuning voz: risadas ~22%, speed MP3 1.06 + playback 1.13, EQ Hoshino mais seco.
- Preview estante: `probeLocalApiBase`, fix `refreshLibraryTrackUi`, play apos `canplay`.
- Pedir por faixa; chave AzuraCast via `start-local-api.ps1`.
- `start-radio.ps1`: `docker.sh up` (correcao do comando `start` inexistente).
- Service worker cache **v24+** (`sw.js`).

### Bot Discord (jun/2026)

- Ponte de voz: stream AzuraCast + mixer PCM (Miku + ouvintes, ducking, sem Hoshino).
- Comandos globais: `/play`, `/play musica:`, `/skip`, `/stop`, `/tocando`.
- API `discord_bridge`: resolve-query, play-track, sync AzuraCast leve ao pedir faixa da biblioteca.
- Busca local com titulos entre parenteses; credenciais Spotify em `data/spotify-api-credentials.txt`.
- Scripts: `start-discord-bot.ps1`, `stop-discord-bot.ps1`, `restart-discord-bot.ps1`, `discord-bot-lib.ps1`.
- Auto-saida da call apos 30 s sozinho; watchdog religa stream mudo; instancia unica (`davey` + PyNaCl).

Guia: **`docs/DISCORD_BOT.md`**.
