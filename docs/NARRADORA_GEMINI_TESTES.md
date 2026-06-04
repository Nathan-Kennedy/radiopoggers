# Narradora via Google Gemini TTS

O **Gemini TTS** (modelo `gemini-2.5-flash-preview-tts`) suporta:

- **Português Brasil** (`pt-BR`)
- **30 vozes** predefinidas (femininas: Kore, Aoede, Despina, Sulafat, Leda…)
- **Risadas reais** com `[laughing]` (nao fala a palavra "laugh")
- Suspiros `[sigh]`, pausas `[short pause]`, sussurro `[whispering]`, etc.
- Controle por **prompt de estilo** ("locutora sedutora de radio FM")

Funciona com **API key do Google AI Studio** (plano Pro inclui quota de API).

## Configurar

1. Crie a key em https://aistudio.google.com/apikey  
2. Salve em `data/gemini-api-key.txt` (uma linha, sem aspas)  
   Modelo: `data/gemini-api-key.example.txt`

## Gerar amostras

```powershell
.\scripts\generate-gemini-narrator-samples.ps1
```

Gera **8 MP3** em `data/narrator-voice-tests/gemini/`:

| Arquivo | Conteudo |
|---------|----------|
| `kore-vinheta-radio.mp3` … `leda-vinheta-radio.mp3` | 5 vozes femininas, mesma vinheta |
| `kore-expressivo-risada.mp3` | Foco em risada |
| `kore-expressivo-madrugada.mp3` | Suspiro + tom intimo |
| `kore-expressivo-pacote.mp3` | Vinheta completa |

## Ouvir

```powershell
.\scripts\open-gemini-player.ps1
```

Ou abra `data/narrator-voice-tests/gemini/index.html` no Explorer (funciona **sem** servidor :5500).

## Codigo

- `tools/radiopoggers-server/gemini_narrator.py` — modulo reutilizavel
- Separado da Miku e da Francisca/ChatTTS

Depois de escolher voz, integramos no site.
