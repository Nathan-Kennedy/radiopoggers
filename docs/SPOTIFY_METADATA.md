# Spotify Metadata Only

Esta integracao organiza metadados e pareia arquivos locais. O **frontend** usa o fluxo completo via API local + spotdl (botao **Tocar**). Este script e usado por dentro da API quando ha credenciais Spotify.

Documentacao operacional: `RUNBOOK_ATUAL.md`.

## Fluxo pelo frontend (recomendado)

1. `.\scripts\start-local-api.ps1` + `.\scripts\serve-frontend.ps1`
2. Cole link Spotify no site → **Tocar**
3. spotdl baixa MP3 → manifesto `data/spotify-imported.json` → sync AzuraCast → **`data/library-catalog.json`**
4. Estante de discos no site atualiza sozinha (poll do job + refresh final); status `ready` / `pendente` via `/api/manifest` e `/api/library/meta`

Sem credenciais Spotify (`SPOTIFY_CLIENT_ID` / `SECRET` no ambiente ou `data/spotify-api-credentials.txt`), a API ainda gera manifesto a partir dos arquivos do spotdl (`build_download_manifest`) — a estante funciona normalmente. O bot Discord `/play musica:` usa o mesmo arquivo de credenciais para busca fora da biblioteca.

Manifesto principal: **`data/spotify-imported.json`**.  
Nao use `data/spotify-linkin-park.json` como fonte do site (apenas metadata de teste, tudo pendente).

Durante importacao o frontend **bloqueia** novo envio ate concluir.

## O que ela faz

- Le link de faixa ou playlist do Spotify.
- Busca metadados pela Spotify Web API.
- Salva titulo, artistas, album, duracao, link oficial e URL de capa.
- Varre uma ou mais pastas de audio local.
- Reutiliza arquivos ja encontrados em importacoes anteriores.
- Organiza arquivos em `Artista/Album/Faixa.ext` quando voce passa `--organize-to`.
- Gera playlist `.m3u` somente com faixas prontas.
- Marca itens sem arquivo local como pendentes.

## O que ela nao faz

- Nao baixa musica.
- Nao baixa preview.
- Nao extrai audio.
- Nao grava capas localmente.
- Nao envia nada automaticamente para o AzuraCast.
- Nao busca audio em fontes de terceiros.

## Credenciais

Crie um app no painel Spotify for Developers.

**Opcao A — arquivo (API local + bot Discord):**

```text
data/spotify-api-credentials.txt
```

Duas linhas (`client_id` e `client_secret`) ou `SPOTIFY_CLIENT_ID=...` / `SPOTIFY_CLIENT_SECRET=...`.  
Veja `data/spotify-api-credentials.example.txt`. Reinicie `start-local-api.ps1` apos criar.

**Opcao B — variaveis de ambiente:**

```powershell
$env:SPOTIFY_CLIENT_ID="seu_client_id"
$env:SPOTIFY_CLIENT_SECRET="seu_client_secret"
```

Esses valores nao devem ser salvos no repositorio.

## Uso

Faixa:

```powershell
python tools\spotify-metadata\spotify_metadata.py "https://open.spotify.com/track/ID_DA_FAIXA" --out data\spotify-track.json
```

Playlist publica:

```powershell
python tools\spotify-metadata\spotify_metadata.py "https://open.spotify.com/playlist/ID_DA_PLAYLIST" --out data\spotify-playlist.json
```

Playlist com biblioteca local:

```powershell
python tools\spotify-metadata\spotify_metadata.py `
  "https://open.spotify.com/playlist/ID_DA_PLAYLIST" `
  --library "D:\RadioPoggersLibrary\Inbox" `
  --library "D:\RadioPoggersLibrary\Managed" `
  --organize-to "D:\RadioPoggersLibrary\Managed" `
  --out "D:\RadioPoggersLibrary\Manifests\playlist.json" `
  --m3u "D:\RadioPoggersLibrary\Playlists\playlist.m3u"
```

## Pareamento com audio local

Depois de gerar o JSON:

1. Coloque seus arquivos autorizados em uma pasta `Inbox`.
2. Rode o importador com `--library Inbox --library Managed`.
3. O script copia os arquivos encontrados para `Managed/Artista/Album/`.
4. O JSON mostra `ready` para o que ja existe e `pending_local_audio` para o que falta.
5. Itens sem arquivo local nao devem tocar.

Veja tambem `LOCAL_LIBRARY.md`.

## Observacao sobre capas

URLs de imagens retornadas pelo Spotify podem expirar. Para uma operacao profissional, prefira capas vindas do AzuraCast ou de arquivos locais com metadados embutidos, desde que voce tenha direito de uso.

