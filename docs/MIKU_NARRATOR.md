# Narradora Miku (Radio no Grale)

Locutora automatica integrada ao player: vinhetas na troca de faixa e bumpers ocasionais no meio da musica, com voz estilo anime via **VOICEVOX** e portugues legivel via **katakana**.

**Nota:** A Miku e a narradora **global** da radio (todos os ouvintes). A segunda narradora **Hoshino** (voz Kore / Gemini) e opt-in por navegador — guia completo em **`docs/HOSHINO_NARRATOR.md`** (tuning voz, ASCII legenda, variaveis, troubleshooting).

Visao geral das demais melhorias do site: **`docs/MELHORIAS_PLAYER_E_MIKU.md`**. Registro consolidado: **`docs/GUIA_COMPLETO.md`**, **`docs/RUNBOOK_ATUAL.md`**.

## A voz "verdadeira" da Miku e gratis?

**Nao.** A Hatsune Miku oficial (Vocaloid, Crypton Future Media) e paga e protegida por copyright.

**Caminho gratis e legal:** [VOICEVOX Engine](https://voicevox.hiroshiba.jp/) — TTS local com vozes anime, entonacao ajustavel (speed, pitch, pausas). E o mais proximo de "Miku de verdade" rodando na sua maquina.

## Instalacao recomendada

```powershell
.\scripts\install-voicevox-miku.ps1
.\scripts\start-voicevox-engine.ps1
.\scripts\start-local-api.ps1
```

1. Instale o **VOICEVOX Engine** (winget: `HiroshibaKazuyuki.VOICEVOX.CPU` ou instalador oficial).
2. Confirme: http://127.0.0.1:50021/version
3. A API detecta o engine e define `RADIOPOGGERS_MIKU_TTS=voicevox` ao subir (`start-local-api.ps1`).

### Forcar so VOICEVOX (sem edge-tts)

```powershell
$env:RADIOPOGGERS_MIKU_TTS = "voicevox"
$env:RADIOPOGGERS_MIKU_REQUIRE_VOICEVOX = "1"
```

## Como a voz funciona hoje

### Speakers VOICEVOX (ordem automatica)

Prioridade para vozes **normais** — portugues com sotaque japones, sem tom idol agudo:

| ID | Voz |
| --- | --- |
| 2 | 四国めたん ノーマル |
| 8 | 春日部つむぎ ノーマル |
| 3002 | 四国めたん ノーマル (Song) |
| 3003 | ずんだもん ノーマル (Song) |
| 3000 / 3001 | fallback amaama (Song) |

Fixar um speaker:

```powershell
$env:RADIOPOGGERS_VOICEVOX_SPEAKER = "8"
```

`0` (padrao) = usa a lista de fallbacks acima.

### Portugues nitido: katakana (`pt_katakana.py`)

OpenJTalk (motor do VOICEVOX) nao le bem texto em alfabeto latino. Antes da sintese, o servidor converte o portugues para **katakana**:

- Palavras dos templates → lexicon (ex.: `voce` → ヴォセ, `ouvindo` → オウヴィンドウ).
- Titulo e artista → transliteracao silabica PT-BR.
- **Sem espacos entre palavras** no katakana (evita pausa robotica).
- Pausas naturais so na pontuacao: `,` `!` `.` viram `、` `！` `。`

Desligar (nao recomendado):

```powershell
$env:RADIOPOGGERS_MIKU_KATAKANA_PT = "0"
```

O texto exibido na API (`text`) continua em portugues; `tts_text` traz o katakana enviado ao VOICEVOX.

### Prosodia VOICEVOX

Presets em `miku_narrator.py` (`VOICEVOX_PROSODY`):

| Momento | Quando | Destaque |
| --- | --- | --- |
| `track_change` | Troca de faixa | `speedScale` 0,98, entonacao levemente expressiva |
| `mid_track` | Bumper no meio | Um pouco mais calmo (`speedScale` 0,96) |

Valores atuais: pitch levemente negativo, `pauseLengthScale` abaixo de 1, sem boost de mora agudo.

### Player (frontend)

- Mesma cadeia de locucao que voice drop, variante **`miku`** (EQ mais suave, reforco de intelligibilidade).
- Ducking **sidechain** na musica enquanto a Miku fala.
- Config: `mikuNarratorEnabled`, `mikuVoiceDetuneCents` em `frontend/config.js`.
- **Legenda:** `#streamMessage` exibe o texto de `voice_drop.caption` digitado em tempo real, com ASCII animado (`ascii-frames falando.json`) ao lado.
- **Ciclo visual:** entrada suave → fala sincronizada → **5 s** extra com texto completo → saida animada → “Tocando ao vivo.”

## Locucoes

- **Toda troca de musica:** vinheta (templates em `miku_narrator.py`), com **~10 s de espera** apos detectar a troca (`RADIOPOGGERS_MIKU_TRACK_CHANGE_DELAY_SEC`, padrao `10`).
- **Durante a musica (~58% das faixas elegiveis):** bumper se faixa ≥ 48 s e cooldown 22 s.
- Nao sobrepoe voice drop de ouvinte ativo.
- O servidor envia **`caption`** em portugues no `voice_drop` para a legenda do player.

Variaveis:

| Variavel | Padrao | Descricao |
| --- | --- | --- |
| `RADIOPOGGERS_MIKU_MID_TRACK_CHANCE` | `0.58` | Probabilidade do bumper no meio |
| `RADIOPOGGERS_MIKU_MID_COOLDOWN_SEC` | `22` | Intervalo minimo entre bumpers |
| `RADIOPOGGERS_MIKU_MIN_TRACK_SECONDS` | `48` | Faixa minima para bumper |
| `RADIOPOGGERS_MIKU_TRACK_CHANGE_DELAY_SEC` | `10` | Espera apos troca de faixa antes da Miku falar |
| `RADIOPOGGERS_VOICE_DROP_DELIVERY_GRACE_SEC` | `90` | Tempo que o drop fica na API para o poll do player |
| `RADIOPOGGERS_MIKU_STATION_NAME` | `RADIO NO GRALE` | Nome na locucao |
| `RADIOPOGGERS_MIKU_TAGLINE` | `RONDONIA STATE OF BRAZIL` | Tagline nos templates |

## Fallback edge-tts

```powershell
.\scripts\install-miku-narrator.ps1
python -m pip install edge-tts
```

Funciona imediato, mas e voz Microsoft generica — **nao e Miku** e sem sotaque japones.

## Variaveis de ambiente (TTS)

| Variavel | Padrao | Descricao |
| --- | --- | --- |
| `RADIOPOGGERS_MIKU_TTS` | `auto` | `voicevox`, `piper`, `edge`, `auto` |
| `RADIOPOGGERS_MIKU_REQUIRE_VOICEVOX` | `0` | `1` = falha se VOICEVOX offline |
| `RADIOPOGGERS_MIKU_KATAKANA_PT` | `1` | `0` = envia texto latino ao VOICEVOX |
| `RADIOPOGGERS_VOICEVOX_SPEAKER` | `0` | `0` = fallbacks automaticos |
| `RADIOPOGGERS_VOICEVOX_URL` | `http://127.0.0.1:50021` | API do engine |
| `RADIOPOGGERS_MIKU_NARRATOR` | `1` | `0` = desliga no servidor |

## API

```powershell
Invoke-RestMethod http://127.0.0.1:8765/api/miku/status
Invoke-RestMethod http://127.0.0.1:8765/api/health
```

POST manual (debug):

```powershell
Invoke-RestMethod -Method POST -Uri http://127.0.0.1:8765/api/miku/narrate `
  -ContentType "application/json" `
  -Body '{"title":"Teste","artist":"Banda","moment":"track_change"}'
```

## Arquivos

```text
tools/radiopoggers-server/miku_narrator.py   Templates, TTS, prosodia, agendamento
tools/radiopoggers-server/pt_katakana.py     Conversao PT-BR → katakana
frontend/assets/ascii-frames falando.json    ASCII na legenda (player)
frontend/app.js                              Legenda + sync com audio
scripts/start-voicevox-engine.ps1
scripts/install-voicevox-miku.ps1
scripts/install-miku-narrator.ps1
data/voice-drops/                            WAVs gerados (Miku + ouvintes)
```
