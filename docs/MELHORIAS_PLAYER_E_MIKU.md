# Melhorias do player, voice drop e narradora Miku

Registro das mudancas implementadas no frontend, na API local e nos scripts — alem do que ja estava no runbook base (Now Playing, sync AzuraCast, import Spotify).

## Resumo

| Area | O que mudou |
| --- | --- |
| Marca | Logo **RG** + nome **RADIO NO GRALE** no site (`frontend/config.js`, header) |
| Stream | Player principal em **HLS** (`hls.js`); MP3 como fallback |
| Voice drop | Chamadas de ouvinte com mic, EQ de radio, ducking sidechain real |
| Miku | Locutora automatica VOICEVOX, portugues via **katakana**, legenda + ASCII falando |
| Hoshino | Segunda narradora **opt-in** (Gemini Kore), legenda roxa + ASCII hoshino falando |
| Visual | ASCII guitarrista (play/idle/off-air), ondas reativas no canto inferior direito |
| Audio | Grafo Web Audio inicializado no Play (corrige stream mudo) |
| Votacao | Skip, pedidos e Spotify pos-import; sorteio rock; Miku narra resultado |

Guia completo Miku: `docs/MIKU_NARRATOR.md` · Hoshino: `docs/HOSHINO_NARRATOR.md` · Votacao: `docs/VOTACAO_OUVINTES.md`.

---

## Narradora Hoshino (jun/2026)

Segunda locutora **por navegador** — nao substitui a Miku global.

| Item | Detalhe |
| --- | --- |
| Escolha | Modal **Narradora** → `localStorage` `radiopoggers_narrator` |
| TTS | Gemini Kore (`hoshino_narrator.py`, `gemini_narrator.py`) |
| Key | `data/gemini-api-key.txt` |
| Legenda | Badge roxo + ASCII `ascii-frames hoshino falando.json` (celula 3px, igual Miku) |
| Audio | Variant EQ `hoshino` mais seco; `hoshinoVoicePlaybackRate: 1.13` |
| Servidor | `RADIOPOGGERS_HOSHINO_SPEED_FACTOR=1.06` acelera MP3 antes do envio |
| Voz | Menos `[laughing]` (~22%), pausas curtas, menos `[whispering]` |

Quem escolhe Hoshino **nao ouve** drops globais da Miku; o cliente gera locucoes via `POST /api/hoshino/narrate` seguindo `narrator_hints`.

Arquivos: `frontend/app.js` (scheduler, playback, modal), `ascii-guitarist.js`, `styles.css`, `index.html`.

---

## Marca e configuracao

Arquivo: `frontend/config.js`

```js
stationDisplayName: "RADIO NO GRALE",
mikuNarratorEnabled: true,
mikuVoiceDetuneCents: 0,
streamMode: "hls",
hlsUrl: "http://localhost/hls/radio-no-grale/live.m3u8",
```

- **`mikuNarratorEnabled`**: liga/desliga reproducao das locucoes da Miku no player.
- **`mikuVoiceDetuneCents`**: ajuste fino de tom na reproducao (0 = padrao; negativo = mais grave).
- O header do site exibe **RG** + **RADIO NO GRALE** (tagline Rondonia mantida).

---

## Player HLS

**Problema:** MP3 ao vivo no Chrome podia travar ou ficar instavel.

**Solucao:**

1. Habilitar HLS no AzuraCast: `.\scripts\enable-azuracast-hls.ps1`
2. Frontend usa `streamMode: "hls"` e carrega **hls.js** (`frontend/app.js`).
3. URL: `http://localhost/hls/radio-no-grale/live.m3u8`
4. MP3 (`streamUrl`) permanece como backup.

Apos mudar config ou HLS no AzuraCast: **Ctrl+F5** no navegador.

### Contador de progresso alinhado ao audio

O metadata (`played_at`) reflete o relogio do servidor; o HLS chega atrasado no navegador. O player:

1. Mede a latencia HLS (`hls.latency` ou `liveSyncPosition - currentTime`).
2. Subtrai esse atraso do elapsed exibido (barra + `0:00`).
3. Suaviza a medida para evitar pulos bruscos.

Config em `frontend/config.js`:

- `streamProgressLatencySec: 0` — auto (padrao).
- `streamProgressLatencyFallbackSec: 4` — fallback antes da medicao HLS.

---

## Grafo de audio e ducking (sidechain)

**Problema:** stream ficava mudo porque o grafo Web Audio era criado com `AudioContext` suspenso no load da pagina.

**Solucao:**

- Inicializacao **lazy** do grafo de ducking no primeiro **Play** (`ensureStreamDuckGraphReady()`).
- `ctx.resume()` antes de tocar stream ou voice drop.

**Ducking na musica:**

- Antes: apenas baixava volume fixo do `<audio>`.
- Agora: **sidechain real** — `duckGain` no stream segue o envelope da voz (analyser no voice drop / locucao Miku).
- Parametros em `frontend/app.js`: ataque, release e alvo dinamico conforme nivel da voz.

Funciona para:

- Chamadas de ouvinte (voice drop gravado no mic).
- Locucoes da Miku (`listener_id: miku-narrator`).

---

## Voice drop (chamada no ar)

### Frontend

- Painel de gravacao estilo **WhatsApp**: barras reativas ao microfone (`#voiceDropWave`).
- Gravacao → `applyBroadcastVoiceEffect()` (EQ + compressao + sala leve) → upload.
- Reproducao com ducking sidechain; quem enviou nao ouve de novo (`skipIfSender`).
- Textos de status no tom da radio (sem mencionar “musica abaixando”).

### Cadeia `applyBroadcastVoiceEffect`

Filtros broadcast (highpass, warmth, presence, de-ess, limiter, soft clip, reverb curto). Usada nas **chamadas de ouvinte**.

A **Miku** usa a mesma cadeia com variante **`variant: "miku"`** — EQ mais suave (menos agudos estourados, reforco na faixa de intelligibilidade ~2,8 kHz).

### API local

| Metodo | Rota | Funcao |
| --- | --- | --- |
| POST | `/api/voice-drop` | Recebe audio (WAV/WEBM); header `X-Listener-Id`, `X-Duration-Ms` |
| GET | `/api/voice-drop/active` | Drop ativo para todos os ouvintes |
| GET | `/api/voice-drop/file/{id}` | Arquivo de audio |

Arquivos em `data/voice-drops/`. O campo `voice_drop` vem em `/api/nowplaying` para o poll do frontend.

Campos uteis no `voice_drop`:

| Campo | Descricao |
| --- | --- |
| `id` | Identificador unico do drop |
| `listener_id` | `miku-narrator` ou ID do ouvinte |
| `url` | Caminho relativo `/api/voice-drop/file/{id}` |
| `duration_ms` | Duracao do audio |
| `caption` | Texto em portugues da locucao Miku (legenda no player) |
| `expires_at` | TTL na API para o poll pegar o drop |

**Entrega ao player:** o drop permanece disponivel na API por `duracao + RADIOPOGGERS_VOICE_DROP_DELIVERY_GRACE_SEC` (padrao **90 s**), nao apenas pelo tempo do audio — evita perder a locucao quando o poll demora ou o download falha uma vez.

Variavel:

```text
RADIOPOGGERS_VOICE_DROP_DELIVERY_GRACE_SEC=90
```

---

## Narradora Miku

Documentacao detalhada: **`docs/MIKU_NARRATOR.md`**.

### Comportamento

- **Toda troca de faixa:** locucao automatica (templates criativos PT).
- **Meio da faixa (~58%):** bumper ocasional se a faixa tiver ≥ 48 s e cooldown respeitado.
- Agendamento no servidor em `maybe_schedule_miku_narration()` ao servir `/api/nowplaying`.
- Sintese em background (thread); resultado vira voice drop com `listener_id: miku-narrator` e campo **`caption`** (texto PT para a legenda).
- **Delay na troca:** ~**10 s** apos detectar nova faixa (`RADIOPOGGERS_MIKU_TRACK_CHANGE_DELAY_SEC`) para nao falar em cima do inicio.
- Deteccao de troca usa `sh_id`, `song_id`, `played_at`, titulo e artista (`build_track_key`).

### TTS (prioridade)

1. **VOICEVOX** (recomendado) — local, gratis, voz anime + entonacao.
2. Piper (se configurado).
3. edge-tts (fallback generico PT-BR).

Scripts:

```powershell
.\scripts\install-voicevox-miku.ps1      # instala/engine VOICEVOX
.\scripts\start-voicevox-engine.ps1      # sobe engine headless :50021
.\scripts\install-miku-narrator.ps1        # fallback edge-tts
.\scripts\start-local-api.ps1              # tenta VOICEVOX + define env Miku
```

### Voz e entonacao (estado atual)

Evolucao aplicada nesta sessao:

1. **Menos agudo:** speakers **ノーマル** primeiro (`2`, `8`, `3002`, `3003`); evita tom amaama/idol fino.
2. **Prosodia VOICEVOX:** `pitchScale` levemente negativo, `intonationScale` ~1,05–1,08, sem `moraPitchBoost`.
3. **Portugues nitido:** modulo `tools/radiopoggers-server/pt_katakana.py` converte texto PT → **katakana** antes do VOICEVOX (OpenJTalk nao le bem latino).
4. **Fala fluida:** palavras em katakana **sem espacos** entre si; pausa so em `、。！` (virgula/ponto/exclamacao mapeados da pontuacao PT).
5. **Ritmo:** `speedScale` ~0,96–0,98; `pauseLengthScale` ~0,88–0,90; fonemas pre/post curtos.

Lexicon fixo para frases da Miku + transliteracao silabica para titulos/artistas desconhecidos.

Desativar katakana (nao recomendado):

```powershell
$env:RADIOPOGGERS_MIKU_KATAKANA_PT = "0"
```

### Endpoints Miku

| Metodo | Rota | Funcao |
| --- | --- | --- |
| GET | `/api/miku/status` | Backend TTS, VOICEVOX, `katakana_portuguese` |
| POST | `/api/miku/narrate` | Gera locucao manual (debug) |

Health agregado: `GET /api/health` inclui bloco `miku`.

### Player — legenda e ASCII falando

Enquanto a locucao toca:

- `#streamMessage` vira painel **MIKU · NO AR** com texto digitado sincronizado ao audio (`voice_drop.caption`).
- Canvas ASCII pequeno ao lado (`assets/ascii-frames falando.json`, 28 frames, `RADIOPOGGERS_ASCII_MIKU_PAINT`).
- Entrada suave (fade + slide do texto); apos a voz, **+5 s** visivel; saida animada antes de voltar “Tocando ao vivo.”
- Ducking sidechain na musica; variante EQ `miku` na reproducao.

Config: `mikuNarratorEnabled: true` em `frontend/config.js` (desliga voz + legenda no player).

---

## Visual e ASCII

### Guitarrista ASCII (fundo do player)

- Arquivo: `frontend/ascii-guitarist.js` + `frontend/assets/ascii-frames.json`.
- **Musica tocando:** animacao de tocar.
- **Pausado:** animacao **idle/sentado**.
- **Offline:** `ascii-frames off.json` ou GIF fallback.
- Modo cor: `asciiColorMode: "mono"` em `config.js`.

### ASCII Miku na legenda (so durante locucao)

- Frames: `frontend/assets/ascii-frames falando.json`
- Carregados em `ascii-guitarist.js` junto com play/idle/off.
- Independente do guitarrista de fundo — nao altere esses frames se a animacao da Miku ja estiver boa.

### Luz reativa (ondas)

- Substituiu indicador tipo “bola” por **canvas** no canto **inferior direito** (`#audioPulseCanvas`).
- Ondas estilo NCS, paleta vermelha rock, reativas ao audio do stream.
- CSS: `.audio-pulse-light` em `frontend/styles.css`.

---

## Arquivos novos ou centrais

```text
tools/radiopoggers-server/miku_narrator.py   Locucoes + TTS + prosodia VOICEVOX
tools/radiopoggers-server/pt_katakana.py     PT-BR → katakana para VOICEVOX
frontend/assets/ascii-frames falando.json    ASCII Miku na legenda
scripts/start-voicevox-engine.ps1
scripts/install-voicevox-miku.ps1
scripts/install-miku-narrator.ps1
scripts/enable-azuracast-hls.ps1
data/voice-drops/                            Drops gravados + locucoes Miku
```

---

## Operacao rapida (depois de reiniciar o PC)

```powershell
# 1. Docker + AzuraCast (se necessario)
.\scripts\start-radio.ps1

# 2. VOICEVOX + API local (Miku)
.\scripts\start-voicevox-engine.ps1
$env:RADIOPOGGERS_MIKU_TTS = "voicevox"
$env:RADIOPOGGERS_MIKU_REQUIRE_VOICEVOX = "1"
cd "c:\Projetos Dev\RadioPoggers"
python tools\radiopoggers-server\server.py

# 3. Frontend
.\scripts\serve-frontend.ps1 -Open
```

Confirme:

```powershell
Invoke-RestMethod http://127.0.0.1:8765/api/miku/status
Invoke-RestMethod http://127.0.0.1:8765/api/health
```

Esperado: `resolved_backend: voicevox`, `katakana_portuguese: true`.

---

## Votacao em tempo real

**Regras:** 1 ouvinte elegivel (site + stream tocando) executa na hora; 2+ abrem votacao (~45s); abstencao conta como nao; empate dispara sorteio server-side com animacao rock.

**Frontend:** heartbeat a cada ~12s, overlay no player, SSE com fallback poll, botao **Pular faixa**, **Pedir** e pos-import Spotify passam pelo fluxo de voto.

**Backend:** `tools/radiopoggers-server/vote_system.py` + endpoints em `server.py`; skip via AzuraCast `/backend/skip`.

Config em `frontend/config.js`:

```js
voteEnabled: true,
voteDurationSec: 45,
audienceHeartbeatMs: 12000,
```

Variaveis: `RADIOPOGGERS_VOTE_ENABLED`, `RADIOPOGGERS_VOTE_DURATION_SEC`, `RADIOPOGGERS_AUDIENCE_TTL_SEC`, `RADIOPOGGERS_AZURACAST_API_KEY`.

---

## Problemas comuns

### Miku nao fala

- VOICEVOX em http://127.0.0.1:50021/version
- API com `RADIOPOGGERS_MIKU_TTS=voicevox`
- `mikuNarratorEnabled: true` no config
- Stream **tocando** no player (locucao Miku so toca com audio ao vivo ativo)
- Reinicie a API apos mudar `miku_narrator.py` ou `pt_katakana.py`
- Confira logs `[Miku/track_change]` no terminal da API — se aparecer drop mas nao ouvir, **Ctrl+F5** no site

### Legenda piscando ou sumindo rapido

- Versao atual atualiza so o bloco de texto (nao remonta o painel inteiro a cada letra).
- Painel fica +5 s apos a voz antes da saida animada.
- Se persistir, limpe cache (**Ctrl+F5**) — service worker em `sw.js` (v14+).

### Stream mudo ao dar Play

- Clique Play de novo apos permitir audio no navegador.
- Confirme HLS respondendo (`live.m3u8`).
- Ctrl+F5 se service worker cachear JS antigo.

### Voice drop xiado / travando

- Versao atual processa offline e limita tail de sala; se persistir, grave mais perto do mic e evite ganho alto.

### Locucao com pausa entre cada palavra

- Corrigido: katakana continuo sem espacos. Se voltar, confira que a API foi reiniciada com `pt_katakana.py` atual.

---

## Historico de ajustes finos (Miku)

| Pedido | Ajuste |
| --- | --- |
| Tom muito agudo | Speakers normais + pitch/intonacao reduzidos |
| Portugues ilegivel | Transliteracao PT → katakana |
| Pausas entre palavras | Remover espacos no katakana; pausa so na pontuacao |
| Intonacao bonita + PT claro | katakana continuo + prosodia equilibrada + EQ `variant: miku` |
| Miku silenciosa na troca AutoDJ | TTL do voice_drop estendido (90 s); retry no frontend; `played_at` na deteccao |
| Legenda digitada | `voice_drop.caption` + painel `#streamMessage` + ASCII falando |
| Entrada/saida seca | Animacoes CSS + hold 5 s apos a voz |

---

## Historico de ajustes finos (Hoshino, jun/2026)

| Pedido | Ajuste |
| --- | --- |
| Risada em todo audio | `_moderate_hoshino_expressiveness` + `HOSHINO_LAUGH_CHANCE=0.22` |
| Voz lenta | Speed MP3 1.06 + `hoshinoVoicePlaybackRate` 1.13; pausas/whisper reduzidos |
| Muito efeito na voz | EQ variant `hoshino` suavizado (warmth, presence, room, saturacao) |
| ASCII legenda errado | Trocado para `ascii-frames hoshino falando.json` (picker continua `hoshino.json`) |
| Modal apertado | Largura ate ~920px; removidos subtitulos dos cards |

---

## Estante — preview e Pedir (jun/2026)

| Pedido | Ajuste |
| --- | --- |
| Ouvir nao funciona (LAN vs 127.0.0.1) | `probeLocalApiBase()` + `localApiBase()` |
| Preview quebra ao parar | Fix `refreshLibraryTrackUi()` (typo antigo) |
| Play antes de carregar | Aguarda `canplay` |
| Pedir desabilitado | `azuracast-api-key.txt` + `start-local-api.ps1` |
| Pedir so 1a da lista | Botao **Pedir** em cada faixa (estante + Minha playlist) |

Ver `docs/LOCAL_LIBRARY.md`.
