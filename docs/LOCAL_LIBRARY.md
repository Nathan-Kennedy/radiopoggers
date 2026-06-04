# Biblioteca Local Organizada

Fluxo integrado com a **API local** e o frontend **Alta Cupula**. Audio vem do spotdl (via botao Tocar) ou de arquivos colocados manualmente em `library/`.

## Estrutura no projeto

```text
RadioPoggers/
  library/Inbox/              Entrada manual + Spotdl/
  library/Inbox/Spotdl/       Downloads do spotdl (por playlist/faixa)
  library/Managed/            Organizacao opcional Artista/Album
  data/spotify-imported.json  Manifesto da ultima importacao
  data/spotify-imported.m3u   Playlist M3U das faixas prontas
  data/library-catalog.json   Catalogo global deduplicado (gerado pela API)
```

## Catalogo global (`library-catalog.json`)

A API mantem um indice unico de todas as faixas `ready` encontradas em `library/`, no manifesto atual e nos arquivos `data/spotdl-*.spotdl`.

Deduplicacao (ordem):

1. `spotify_id`
2. `isrc`
3. artista + titulo normalizados
4. caminho local unico (uma entrada por arquivo fisico)

Ao importar uma nova playlist, a API:

- Reaproveita faixas ja existentes no catalogo (mensagem `reused_existing`)
- Pula o spotdl quando todas as faixas ja existem (reimportacao da mesma playlist)
- Aponta o manifesto para o melhor arquivo local (`Managed` > `Spotdl` > `Inbox`)
- Sincroniza o AzuraCast sem copiar duplicatas (nome estavel `{spotify_id}.mp3` quando disponivel)

## Manifesto e status

A API em `/api/manifest`:

- Le `data/spotify-imported.json` (ultima playlist importada)
- Reescaneia pastas de audio e marca como **`ready`** o que existir em disco
- Atualiza contadores `ready` / `pending_local_audio`

Status:

| Status | Significado |
| --- | --- |
| `ready` | Arquivo local encontrado |
| `pending_local_audio` | Metadado Spotify sem MP3 local |

## Endpoints da biblioteca local

| Metodo | Rota | Funcao |
| --- | --- | --- |
| GET | `/api/library` | Lista paginada com `q`, `artist`, `album`, `limit`, `offset` |
| GET | `/api/library/filters` | Artistas e albuns distintos para filtros |
| GET | `/api/library/preview/{track_id}` | Preview local do MP3 (nao altera o stream) |
| POST | `/api/library/request` | Body `{ "track_id": "..." }` — pedido na fila AzuraCast |

Pedidos na radio exigem:

- Faixa ja sincronizada em `imported/` (use **Tocar** antes)
- `data/azuracast-api-key.txt` (copie de `azuracast-api-key.example.txt`)
- Estacao com `enable_requests=1` — rode `.\scripts\fix-azuracast-station.ps1` se pedidos falharem

**Tocar ja** (apos votacao sim) usa play imediato no AzuraCast (`files/batch`, `do: immediate`), nao apenas request+skip.

## Frontend — painel Estante de discos

No site Alta Cupula:

- Busca por texto, filtro por artista/album
- **Ouvir** — preview local (player separado do stream da radio)
- **Pedir** — em **cada faixa** da estante e em **Minha playlist** (votacao → Tocar ja / Na fila)
- **+ Lista** — monta playlist pessoal em `localStorage` (`radiopoggers_custom_playlist`)
- **Atualizacao automatica:** durante import Spotify o frontend faz poll do job e chama `refreshLibraryShelf`; watcher a cada `libraryAutoRefreshMs` (15s) compara revisao via `/api/library/meta`

### Preview local (Ouvir)

Requisitos:

1. API respondendo em `GET /api/library/preview/{track_id}` (MP3 com suporte a Range).
2. Preferir **`.\scripts\start-local-api.ps1`** (porta 8765 em `0.0.0.0`, carrega chaves de `data/`).

**Resolucao automatica da URL da API (jun/2026):** se `frontend/config.js` aponta `localApiUrl` para IP da LAN mas a API so escuta em `127.0.0.1`, o player usa `probeLocalApiBase()` para achar a API (config → hostname da pagina → `127.0.0.1`). Estado em `state.resolvedLocalApiBase`; helper `localApiBase()` no `app.js`.

Outros fixes no preview:

- Reproducao so apos evento **`canplay`** (nao dispara `play()` antes do buffer).
- `stopShelfPreview` chama **`refreshLibraryTrackUi()`** (corrige ReferenceError antigo).

Se a lista vem do JSON estatico mas Ouvir falha: API offline — suba `start-local-api.ps1` e **Ctrl+F5**.

### Pedir na radio

- Chave em **`data/azuracast-api-key.txt`** (nao commitar). Reinicie a API apos salvar.
- Health: `GET /api/health` → `azuracast.requests_available === true` habilita botoes Pedir.
- Estacao: `enable_requests=1` (`fix-azuracast-station.ps1`).
- Cooldown entre pular/pedir/zerar playlist: `voteActionCooldownSec` (padrao 45s).

## Sync com AzuraCast

Apos importacao pelo frontend, a API:

1. Copia MP3 para `/var/azuracast/stations/radio-no-grale/media/imported/`
2. Vincula faixas a playlist `default`
3. Define `avoid_duplicates = 0` (importante para shuffle com mesmo artista)
4. Reinicia a estacao e sync Now Playing

Script manual equivalente:

```powershell
.\scripts\fix-azuracast-station.ps1
```

## Nome de arquivos para matching

O matching funciona melhor quando os arquivos locais usam um destes formatos:

```text
Artista - Nome da Musica.mp3
01 - Artista - Nome da Musica.flac
Nome da Musica.m4a
```

O melhor formato e:

```text
Artista - Nome da Musica.ext
```

## Como usar com AzuraCast

**Metodo principal (frontend):**

1. API local + site abertos.
2. Link Spotify → **Tocar**.
3. Aguarde sync; confira lista em Playlist importada ou Biblioteca local.

**Metodo manual:**

1. Envie arquivos para `library/Inbox` ou use spotdl.
2. Rode importacao pelo frontend ou API POST `/api/import-spotify`.
3. Ou envie pelo painel AzuraCast → Midia → playlist `default`.

Use `data/spotify-imported.m3u` como referencia de ordem da ultima importacao.

## Limites

Sem dependencias externas, o script nao le tags ID3/FLAC internamente. Ele usa nome de arquivo, caminho, tamanho e SHA-256. Se quiser matching por metadados embutidos no futuro, podemos adicionar uma ferramenta opcional, mas isso exigiria uma dependencia externa ou chamada a uma ferramenta instalada no sistema.

