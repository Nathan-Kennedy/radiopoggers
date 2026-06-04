# Francisca expressiva — pt-BR natural com risadas e efeitos

A voz **Francisca** (edge-tts, pt-BR) sozinha nao faz risadas naturais — escrever "ha ha" soa robotico.

## Solucao: motor hibrido

| Parte | Motor | Papel |
|-------|--------|--------|
| Fala em portugues | **edge-tts** `pt-BR-FranciscaNeural` | Locutora BR sedutora |
| Risadas, bocejos, suspiros | **ChatTTS** | Sons nao-verbais naturais |

Codigo: `tools/radiopoggers-server/expressive_francisca.py`

## Instalar e gerar amostras

```powershell
.\scripts\install-expressive-narrator.ps1
```

Saida: `data/narrator-voice-tests/expressive/`

Player: http://127.0.0.1:5500/data/narrator-voice-tests/expressive/index.html

## Marcadores no roteiro

```
Olá ouvinte! {breath} Você está na Rádio no Grale. {pause:400ms}
{laugh:soft} Vira o volume! {yawn} {laugh:full}
```

| Marcador | Efeito |
|----------|--------|
| `{pause}` / `{pause:500ms}` | Silencio |
| `{laugh}` / `{laugh:soft}` / `{laugh:full}` | Risada |
| `{yawn}` | Bocejo |
| `{sigh}` | Suspiro |
| `{breath}` | Respiracao curta |

## Proximo passo

Depois de ouvir as 3 vinhetas em `expressive/`, diga qual prefere (v1, v2 ou v3) para integrarmos no site como narradora oficial (separada da Miku).
