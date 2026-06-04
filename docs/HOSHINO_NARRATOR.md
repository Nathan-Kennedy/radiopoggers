# Narradora Hoshino (Gemini Kore)

Segunda narradora do player — voz **Kore** via Google Gemini TTS, escolha **por navegador** (nao altera a locucao global da Miku).

**Relacionado:** Miku global → `docs/MIKU_NARRATOR.md` · Player/votacao → `docs/MELHORIAS_PLAYER_E_MIKU.md` · Runbook → `docs/RUNBOOK_ATUAL.md`

---

## Escolha no player

1. Botao **Narradora** ao lado de **Pular faixa**
2. Modal fullscreen (ate ~920px): **Miku** (azul, global) ou **Hoshino** (roxo, so pra voce)
3. Preferencia salva em `localStorage` (`radiopoggers_narrator`: `miku` | `hoshino`)
4. Cards do modal **sem** subtitulos tipo "Anime · VOICEVOX" / "Sedutora · Kore"

## Comportamento

| Aspecto | Miku (padrao) | Hoshino |
|---------|---------------|---------|
| Motor | VOICEVOX / edge (servidor) | Gemini TTS Kore (API) |
| Escopo | Todos os ouvintes | So este navegador |
| Drops globais | Toca `voice_drop` da Miku | **Ignora** drops da Miku |
| Timing | Servidor agenda | Cliente segue `narrator_hints` do now playing |
| Legenda | ASCII `falando.json` + badge azul | ASCII **`hoshino falando.json`** + badge roxo |
| Votacao | Miku narra resultado (global) | Hoshino narra so quem escolheu Hoshino |

Momentos espelhados da Miku: `track_change`, `mid_track`, `mid_info`, todos os `vote_*` em `hoshino_narrator.py`.

---

## API

| Metodo | Rota | Funcao |
|--------|------|--------|
| GET | `/api/hoshino/status` | Key Gemini, voz Kore, modelos |
| POST | `/api/hoshino/narrate` | Mesmo corpo de `/api/miku/narrate` |
| GET | `/api/nowplaying` | Inclui `narrator_hints` e `hoshino_narrator` |

Geracao: `generate_hoshino_narration()` → MP3 via `gemini_narrator.synthesize_gemini_mp3()` → voice drop com `listener_id: hoshino-narrator` e **`register_active=False`** (nao sobrescreve drop global da Miku).

Dependencias: `tools/radiopoggers-server/requirements-gemini-narrator.txt` (`google-genai`, `pydub`).

---

## Configuracao

| Variavel | Default | Efeito |
|----------|---------|--------|
| `RADIOPOGGERS_HOSHINO_NARRATOR` | `1` | Liga/desliga rotas Hoshino |
| `RADIOPOGGERS_HOSHINO_VOICE` | `Kore` | Voz Gemini |
| `RADIOPOGGERS_HOSHINO_STYLE_PROMPT` | locutora FM calorosa; evita auto-seducao | Persona TTS base |
| `RADIOPOGGERS_HOSHINO_MAX_SECONDS` | `28` | Limite estimado |
| `RADIOPOGGERS_HOSHINO_LAUGH_CHANCE` | `0.22` | Probabilidade de manter **uma** risada no texto |
| `RADIOPOGGERS_HOSHINO_IDOL_CHANCE` | `0.22` | Chance de frase estilo idol (se-gre-do, Yatta, etc.) |
| `RADIOPOGGERS_HOSHINO_SPEED_FACTOR` | `1.0` | **Desligado** — 1.0 preserva timbre natural |

API key Gemini: `data/gemini-api-key.txt` (veja `data/gemini-api-key.example.txt`). **Nao commitar.**

Frontend (`frontend/app.js` / `frontend/config.js`):

| Chave | Default | Efeito |
|-------|---------|--------|
| `hoshinoVoicePlaybackRate` | `1.0` | So aplica se > 1 (evita mudar tom da voz) |

---

## Tom e frases (jun/2026)

- Templates reescritos: **locutora de radio**, nao frases de seducao sobre si mesma ("seducao no ar", "alerta sedutor", "ouvinte lindo", etc. removidos).
- Cada locucao sorteia variante de tom no prompt: **divertida**, **suave** ou **direta** (`HOSHINO_STYLE_VARIANTS`).
- Mix de `[laughing]` (animada), `[sigh]` / `[short pause]` (suave) — `[whispering]` raro.
- **Vibe idol (~22%):** frases tipo “isso é se-gre-do”, “Yatta!”, missão de idol — pool `_IDOL_*` via `RADIOPOGGERS_HOSHINO_IDOL_CHANCE`.

---

## Voz — processamento

### Risadas (`_moderate_hoshino_expressiveness`)

- Remove `[laughing]` da maioria das frases; restaura em ~22% quando o template tinha risada.

### Audio no player

Variante `hoshino` em `applyBroadcastVoiceEffect()` — EQ mais suave que voice drop generico; brilho roxo na legenda.

**Velocidade:** aceleracao artificial **desativada** (speed 1.0) — alterar `playbackRate` ou `HOSHINO_SPEED_FACTOR` muda o timbre da Kore.

---

## Tags expressivas (Gemini)

`[laughing]`, `[sigh]`, `[whispering]`, `[short pause]`, `[medium pause]`, `[long pause]`

Templates em `tools/radiopoggers-server/hoshino_narrator.py`.

---

## ASCII na legenda

| Uso | Asset | Celula |
|-----|-------|--------|
| **Legenda falando** | `frontend/assets/ascii-frames hoshino falando.json` | `MIKU_CELL = 3` (igual Miku) |
| Modal picker (card Hoshino) | `frontend/assets/ascii-frames hoshino.json` | `PICKER_CELL = 4` |

Implementacao: `frontend/ascii-guitarist.js` → `RADIOPOGGERS_ASCII_HOSHINO_CAPTION_PAINT` · animacao no painel `#streamMessage` via `paintMikuCaptionAsciiFrame()` em `app.js`.

GIF de referencia: `frontend/assets/ascii-animation hoshino falando.gif`.

Service worker: incluir `ascii-frames%20hoshino%20falando.json` (cache `sw.js` v24+).

---

## Arquivos principais

```text
tools/radiopoggers-server/hoshino_narrator.py   Templates + moderacao + speed MP3
tools/radiopoggers-server/gemini_narrator.py      Cliente Gemini TTS
tools/radiopoggers-server/server.py               Rotas /api/hoshino/*
tools/radiopoggers-server/vote_system.py          narrator_moment na votacao fechada
frontend/app.js                                 Picker, scheduler, playback, legenda
frontend/ascii-guitarist.js                     Frames caption + picker
frontend/styles.css                             Modal narradoras, tema roxo Hoshino
frontend/index.html                             #narratorPickerModal, botoes
data/gemini-api-key.txt                         Chave (nao commitar)
```

---

## Teste manual

1. Player com Miku default — vinheta global continua normal.
2. Escolher Hoshino — ouvir Kore; **sem** audio Miku sobreposto.
3. Legenda: badge **HOSHINO · NO AR** + ASCII **falando** pequeno (lado esquerdo).
4. Recarregar — preferencia persiste.
5. Outro navegador com Miku — sem conflito.
6. Apos mudar `hoshino_narrator.py`: reiniciar API. Apos mudar `app.js` / ASCII: **Ctrl+F5**.

Amostras de voz: `data/narrator-voice-tests/gemini/` (script `generate-gemini-narrator-samples.ps1`).

---

## Problemas comuns

| Sintoma | Causa provavel | Acao |
|---------|----------------|------|
| Hoshino nao fala | Key Gemini ausente | `data/gemini-api-key.txt` + reiniciar API |
| Muito lenta | Ritmo natural da Kore | Nao subir speed (muda timbre); ajustar templates/prompt |
| Muito risada | Template aleatorio | Reduzir `RADIOPOGGERS_HOSHINO_LAUGH_CHANCE` (ex. 0.15) |
| ASCII antigo na legenda | Cache SW | Ctrl+F5; confira `sw.js` CACHE_NAME |
| Miku e Hoshino juntas | Hoshino nao selecionada | So um narrador por navegador; drops Miku filtrados se Hoshino ativa |
