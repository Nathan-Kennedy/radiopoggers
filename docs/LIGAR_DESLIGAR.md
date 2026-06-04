# Ligar e desligar a RadioPoggers

Guia rapido de comandos para subir ou parar **tudo** que faz o site, a API, a Miku, o AzuraCast e o stream funcionarem.

## Visao geral dos servicos

| Servico | Porta | O que faz |
| --- | --- | --- |
| **Docker Desktop** | — | Engine para containers |
| **AzuraCast** | 80, 443, 8000+ | Radio, AutoDJ, stream MP3/HLS |
| **API local** | 8765 | Now Playing, biblioteca, Spotify, votacao, Miku |
| **VOICEVOX** | 50021 | Voz da narradora Miku (opcional) |
| **Frontend** | 5500 | Site `http://localhost:5500/frontend/` |
| **Bot Discord** | — | Ponte de voz + comandos `/play` (processo separado) |

---

## Ligar tudo (ordem recomendada)

### 1. Docker Desktop

Abra o **Docker Desktop** e espere ficar **Running**.

```powershell
docker ps
```

Deve listar o container `azuracast` (se ja instalou).

### 2. Atalho — ligar tudo (recomendado)

Confere **WSL + Docker + pasta AzuraCast**, sobe AzuraCast, VOICEVOX, API, site HTTP/HTTPS e bot Discord em **segundo plano** (janelas ocultas; logs em `data/logs/`):

```powershell
cd "C:\Projetos Dev\RadioPoggers"
.\scripts\start-full-stack.ps1 -OpenBrowser
```

Desligar **tudo** (API, site, VOICEVOX, bot sai da call, AzuraCast):

```powershell
.\scripts\stop-full-stack.ps1
```

Pule AzuraCast se o Docker/AzuraCast ja estiver rodando:

```powershell
.\scripts\start-full-stack.ps1 -SkipAzuraCast -OpenBrowser
```

Sem Miku (so edge-tts na API):

```powershell
.\scripts\start-full-stack.ps1 -SkipVoiceVox -OpenBrowser
```

Sem bot Discord:

```powershell
.\scripts\start-full-stack.ps1 -SkipDiscordBot -OpenBrowser
```

### 3. Passo a passo manual (controle total)

```powershell
cd "C:\Projetos Dev\RadioPoggers"

# Ambiente
.\scripts\check-env.ps1

# AzuraCast (WSL + Docker)
.\scripts\start-radio.ps1

# VOICEVOX para Miku (terminal separado ou deixe start-local-api subir)
.\scripts\start-voicevox-engine.ps1

# API local (terminal 1 — deixa aberto)
.\scripts\start-local-api.ps1

# Frontend (terminal 2 — deixa aberto)
.\scripts\serve-frontend.ps1 -Open

# Bot Discord (terminal 3 — opcional, deixa aberto)
.\scripts\start-discord-bot.ps1
```

### 4. Conferir no navegador

| URL | Esperado |
| --- | --- |
| `http://localhost:5500/frontend/` | Player **RADIO NO GRALE** |
| `http://127.0.0.1:8765/api/health` | JSON com API ok |
| `http://localhost` | Painel AzuraCast |
| `http://localhost/hls/radio-no-grale/live.m3u8` | Playlist HLS |

Use **Ctrl+F5** no site apos atualizar codigo ou service worker.

### 5. Testes automaticos

```powershell
.\scripts\test-radiopoggers.ps1
```

Ou:

```powershell
python scripts\test-radiopoggers-api.py
```

---

## Desligar tudo

### Atalho — um comando

```powershell
cd "C:\Projetos Dev\RadioPoggers"
.\scripts\stop-full-stack.ps1
```

Ordem: servicos locais (API **8765**, site **5500/5443**, VOICEVOX) → bot Discord (sai da call) → AzuraCast (`docker stop` com fallback se `docker.sh` falhar).

### Passo a passo manual

```powershell
.\scripts\stop-local-stack.ps1
.\scripts\stop-discord-bot.ps1
.\scripts\stop-radio.ps1
```

Alternativa: encerre os processos com `.\scripts\stop-full-stack.ps1` (nao precisa fechar janelas visiveis).

### Parar Docker Desktop (opcional)

Feche o app **Docker Desktop** ou:

```powershell
docker stop azuracast
```

(Nao apague a pasta `~\azuracast` sem backup.)

---

## Bot Discord (ponte de voz)

| Acao | Comando |
| --- | --- |
| Ligar | `.\scripts\start-discord-bot.ps1` |
| Desligar | `.\scripts\stop-discord-bot.ps1` |
| Reiniciar | `.\scripts\restart-discord-bot.ps1` |
| Reiniciar (segundo plano) | `.\scripts\restart-discord-bot.ps1 -NewWindow` |

- **Desligar** mata todas as instancias (`taskkill /T`) e tira o bot das calls.
- **Ligar** verifica processos antigos antes de subir uma instancia nova.
- Apos **reiniciar o bot**, quem estava na call precisa **`/play`** de novo.

Documentacao completa: **`docs/DISCORD_BOT.md`**.

---

## Comandos Docker uteis

```powershell
# Ver containers
docker ps -a

# Logs da radio
docker logs --tail 80 azuracast

# Reiniciar so a estacao (dentro do container)
docker exec azuracast bash -lc "cd /var/azuracast/www && php backend/bin/console azuracast:radio:restart radio-no-grale"

# Sync manual de metadados Now Playing
.\scripts\sync-nowplaying.ps1

# Corrigir playlist + avoid_duplicates
.\scripts\fix-azuracast-station.ps1
```

---

## Apos reiniciar o PC

1. Abrir **Docker Desktop** (aguardar Running).
2. `.\scripts\start-radio.ps1` (se `docker ps` nao mostrar azuracast).
3. `.\scripts\start-full-stack.ps1 -SkipAzuraCast -OpenBrowser`  
   **ou** os dois terminais: `start-local-api.ps1` + `serve-frontend.ps1 -Open`.
4. Ctrl+F5 em `http://localhost:5500/frontend/`.

---

## Variaveis e arquivos importantes

| Item | Caminho / comando |
| --- | --- |
| Config do site | `frontend/config.js` |
| API key AzuraCast (skip/pedidos) | `data/azuracast-api-key.txt` |
| Token bot Discord | `data/discord-bot-token.txt` |
| Credenciais Spotify (busca `/play musica:`) | `data/spotify-api-credentials.txt` |
| Config bot Discord | `data/discord-bot-config.json` |
| Manifesto playlists | `data/spotify-imported.json` |
| Catalogo global | `data/library-catalog.json` |
| Habilitar HLS | `.\scripts\enable-azuracast-hls.ps1` |

API manual (se o script PowerShell falhar):

```powershell
cd "C:\Projetos Dev\RadioPoggers"
$env:RADIOPOGGERS_MIKU_TTS = "voicevox"
python tools\radiopoggers-server\server.py
```

---

## Troubleshooting rapido

| Problema | Acao |
| --- | --- |
| Site sem biblioteca / votacao | API na 8765? `.\scripts\start-local-api.ps1` |
| Porta 8765 ocupada | `.\scripts\stop-local-stack.ps1` e suba de novo |
| Stream mudo / travado | HLS ligado? Ctrl+F5; `enable-azuracast-hls.ps1` |
| Painel AzuraCast desatualizado | `.\scripts\sync-nowplaying.ps1` |
| Miku sem voz anime | `.\scripts\start-voicevox-engine.ps1` antes da API |
| Bot Discord duplicado / sem voz | `.\scripts\stop-discord-bot.ps1` → `start-discord-bot.ps1` |
| Bot saiu da call sozinho | Normal apos 30 s sozinho (`alone_leave_seconds` no config) |

Documentacao completa: **`docs/GUIA_COMPLETO.md`**, **`docs/RUNBOOK_ATUAL.md`**, **`docs/DISCORD_BOT.md`**.
