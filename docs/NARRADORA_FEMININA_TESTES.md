# Narradora feminina — testes de voz (separado da Miku)

Cinco amostras de locutora feminina (charmosa, sedutora, animada) para você escolher antes de integrar no player.

## Gerar os áudios

```powershell
.\scripts\generate-female-narrator-samples.ps1
```

Requisito: `edge-tts` (instalado automaticamente pelo script).

## Onde estão os arquivos

| Item | Caminho |
|------|---------|
| **Pasta principal** | `data/narrator-voice-tests/` |
| **Player HTML** | `data/narrator-voice-tests/index.html` |
| **Metadados** | `data/narrator-voice-tests/manifest.json` |

### Os 5 MP3

1. `01-francisca-locutora-quente.mp3` — Francisca (BR), locutora FM quente  
2. `02-thalita-animada-brilhante.mp3` — Thalita (BR), animada e brilhante  
3. `03-raquel-elegante-sedutora.mp3` — Raquel (PT), elegante sedutora  
4. `04-ava-multilingual-ousada.mp3` — Ava multilingual, ousada  
5. `05-emma-multilingual-suave.mp3` — Emma multilingual, suave  

## Ouvir no navegador

Com o frontend servindo na porta 5500:

http://127.0.0.1:5500/data/narrator-voice-tests/index.html

## Texto de exemplo (todas as vozes)

> Olá, ouvinte lindo! Você sintonizou na Rádio no Grale, a Alta Cúpula que não te deixa ficar parado! … Hã-hã!

## Próximo passo (depois da sua escolha)

Diga qual arquivo (01–05) você prefere; aí integramos como segunda narradora no site, sem alterar a Miku.
