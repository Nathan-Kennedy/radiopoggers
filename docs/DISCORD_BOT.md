# Bot Discord — RADIO NO GRALE (ponte de audio)

Bot de musica conectado à **radio real** (AzuraCast + API local `:8765`). No Discord ele **mistura** o stream da radio com voice drops da API (Miku + gravacoes de ouvintes), com **ducking** e efeito de locucao — espelhando o site, **sem alterar o frontend**.

Hoshino **nao** toca no Discord (so Miku + ouvintes).

---

## Ligar, desligar e reiniciar

| Acao | Comando |
| --- | --- |
| **Ligar** | `.\scripts\start-discord-bot.ps1` |
| **Desligar** | `.\scripts\stop-discord-bot.ps1` |
| **Reiniciar** | `.\scripts\restart-discord-bot.ps1` |
| **Reiniciar (segundo plano)** | `.\scripts\restart-discord-bot.ps1 -NewWindow` (janela oculta; log em `data/logs/discord-bot.log`) |

### O que os scripts fazem

- **`stop-discord-bot.ps1`** — cria `data/discord-bot.shutdown` para o bot **sair da call** (`disconnect`) e fechar o gateway; espera ate ~18s; se nao responder, `taskkill /T` nas instancias (`discord-bot.pid` + `python` com `bot.py`).
- **`start-discord-bot.ps1`** — antes de subir, **verifica e mata** instancias antigas; limpa `discord-bot.pid`; instala deps (`discord.py`, `davey`, `PyNaCl`); sobe **uma** instancia.
- **`restart-discord-bot.ps1`** — stop completo → espera → start.

Logica compartilhada: `scripts/discord-bot-lib.ps1`.

### Apos reiniciar o bot

| O que reiniciou | Precisa `/play` de novo? |
| --- | --- |
| So a API (`start-local-api.ps1`) | Nao (se o bot ja estava na call) |
| Bot ou `restart-discord-bot.ps1` | **Sim** — conexao de voz cai ao encerrar o processo |
| Mudou codigo do mixer (Miku/ducking) | **Sim** — `/stop` + `/play` ou reinicie o bot |

Quem estava ouvindo na call precisa **`/play`** de novo para o bot voltar ao canal com audio.

---

## Comandos slash

| Comando | O que faz |
| --- | --- |
| `/play` | Voce em canal de voz → bot entra e toca a radio (Miku + chamadas). |
| `/play musica:<texto ou link Spotify>` | Busca na biblioteca / Spotify, coloca na frente da fila e toca. |
| `/skip` / `/pular` | Pula musica **na hora** (sem votacao). |
| `/stop` / `/parar` | Para audio e sai do canal de voz. |
| `/tocando` | Embed com musica atual. |
| `/ouvir` / `/site` | Links do player. |

---

## Adicionar o bot ao servidor (gameplaysSsSsSs)

O convite `https://discord.gg/r3BN7Azna` e para **pessoas** entrarem no grupo. O bot entra com outro link (OAuth), gerado assim:

```powershell
.\scripts\discord-bot-invite-url.ps1 -InviteCode r3BN7Azna -OpenBrowser
```

Ou abra direto (servidor **gameplaysSsSsSs**, ID `471693390451572766`):

https://discord.com/oauth2/authorize?client_id=1511939007788093531&permissions=2152282368&scope=bot%20applications.commands&guild_id=471693390451572766&disable_guild_select=true

Quem clica precisa permissao **Gerenciar servidor** (ou equivalente) no Discord. Depois: `.\scripts\start-discord-bot.ps1` e `/play` num canal de voz.

---

## Requisitos

- **FFmpeg** no PATH (`ffmpeg -version`)
- API local `:8765` + AzuraCast rodando (`start-local-api.ps1`, `start-radio.ps1`)
- Token em `data/discord-bot-token.txt`
- Config em `data/discord-bot-config.json`
- Permissoes do bot: **Conectar**, **Falar**, Enviar mensagens, Embed links
- Python **3.12+** com `davey` + `PyNaCl` (o script de start instala)

### Credenciais Spotify (busca `/play musica:` fora da biblioteca)

Copie `data/spotify-api-credentials.example.txt` → `data/spotify-api-credentials.txt` (client_id + client_secret).  
Faixas **ja no catalogo local** funcionam sem isso. Reinicie a API apos criar o arquivo.

---

## Subir stack minima (Discord + radio)

```powershell
cd "C:\Projetos Dev\RadioPoggers"
.\scripts\start-local-api.ps1      # terminal 1
.\scripts\start-discord-bot.ps1    # terminal 2
```

No Discord: entre em um canal de voz → `/play`.

---

## Comportamento no Discord (jun/2026)

### Audio

- **Mesma fonte que o site quando possivel:** `discord_stream_mode: "hls"` + `stream_hls_url_local` (igual `streamMode: "hls"` no frontend). MP3 (`stream_url_local`) continua como fallback com `discord_stream_mode: "mp3"`.
- Jitter buffer (~12 s), **warmup**, **pump Opus** 20 ms, FEC/packet-loss, leitura anti-rajada.
- **Miku** + gravacoes de ouvintes via poll em `/api/voice-drop/active` e `/api/nowplaying`.
- **Ducking**: radio abaixa ~10% enquanto a Miku fala (igual ideia do site).
- Ganho moderado na voz; equilibrio vem do ducking, nao de boost extremo.
- Decode de drops em thread separada; locks separados radio/voz (evita audio picotado).

### Status na lista de membros

O bot mostra **`/play · Artista — Musica`** (ouvindo), para o comando ficar visivel como nos outros bots (ex.: `.help`, `m!help`).

### Status na lista de membros

O bot mostra **`/play · Artista — Musica`** (ouvindo), para o comando ficar visivel como nos outros bots (ex.: `.help`, `m!help`).

### Automacoes

- **Sai sozinho da call** apos `alone_leave_seconds` (padrao **30 s**) se so o bot estiver no canal (`alone_leave_seconds` em `discord-bot-config.json`).
- **Watchdog de stream**: se o bot esta na call mas parou de tocar, religa apos ~15 s.
- **`/play musica:`** — busca local (titulos com parenteses, ex. "minha deusa"); se a faixa nao estiver no AzuraCast, **sync automatico** leve (sem reiniciar a radio inteira).

---

## API Discord (so bot — site nao usa)

| Metodo | Endpoint | Funcao |
| --- | --- | --- |
| GET | `/api/discord/resolve-query?q=` | Resolve busca biblioteca / Spotify |
| POST | `/api/discord/play-track` | Toca faixa do catalogo **agora** |
| POST | `/api/discord/play-spotify` | Toca se importada; senao `need_import: true` |
| POST | `/api/discord/skip` | Pula faixa na radio |

---

## Config (`data/discord-bot-config.json`)

```json
{
  "application_id": "...",
  "api_base_url": "http://127.0.0.1:8765",
  "stream_url_local": "http://127.0.0.1/listen/radio-no-grale/radio.mp3",
  "alone_leave_seconds": 30,
  "guild_ids": []
}
```

Comandos slash sao **globais** (aparecem em todo servidor com o bot). `guild_ids` so limpa duplicatas antigas no sync.

---

## Arquivos do bot

```text
tools/discord-bot/bot.py           — comandos slash, watchdogs
tools/discord-bot/voice_player.py  — conexao de voz
tools/discord-bot/voice_mixer.py   — radio + Miku + ducking
tools/discord-bot/radio_api.py     — cliente HTTP da API
tools/discord-bot/runtime_guard.py — instancia unica + davey/PyNaCl
data/discord-bot-token.txt
data/discord-bot-config.json
data/discord-bot.pid               — PID da instancia ativa (nao commitar)
data/discord-bot.shutdown          — pedido de desligamento gracioso (nao commitar)
```

---

## Seguranca

- Nunca commite `discord-bot-token.txt`
- Se vazar token: **Redefinir token** no [Discord Developer Portal](https://discord.com/developers/applications)

---

## Troubleshooting

| Problema | Acao |
| --- | --- |
| `davey library needed` | Use `start-discord-bot.ps1` (Python 3.12 + deps). Mate duplicatas: `stop-discord-bot.ps1` |
| Bot duplicado / comandos 2x | `stop-discord-bot.ps1` → `start-discord-bot.ps1` |
| Sem audio na call apos restart | `/play` de novo |
| Miku baixa / radio alta | Reinicie bot (`restart-discord-bot.ps1`) + `/play` (carrega mixer novo) |
| `/play musica:` falha Spotify | Crie `data/spotify-api-credentials.txt` |
| Faixa na biblioteca, erro AzuraCast | Sync auto na API; confira Docker; `fix-azuracast-station.ps1` se persistir |
| Bot mudo intermitente | Watchdog religa; confira FFmpeg e stream AzuraCast |

Ver tambem: **`docs/LIGAR_DESLIGAR.md`**, **`docs/RUNBOOK_ATUAL.md`**.
