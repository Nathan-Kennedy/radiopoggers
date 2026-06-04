# Spotify Metadata Tool

Ferramenta Python sem dependencias externas para gerar uma lista de referencia a partir de links do Spotify e parear com audio local.

Ela usa apenas a Spotify Web API e salva metadados em JSON. Audio nunca e baixado.

## Exemplo

```powershell
$env:SPOTIFY_CLIENT_ID="seu_client_id"
$env:SPOTIFY_CLIENT_SECRET="seu_client_secret"
python tools\spotify-metadata\spotify_metadata.py "https://open.spotify.com/playlist/ID" --out data\spotify-playlist.json
```

## Exemplo com biblioteca local

```powershell
python tools\spotify-metadata\spotify_metadata.py `
  "https://open.spotify.com/playlist/ID" `
  --library "D:\RadioPoggersLibrary\Inbox" `
  --library "D:\RadioPoggersLibrary\Managed" `
  --organize-to "D:\RadioPoggersLibrary\Managed" `
  --out "D:\RadioPoggersLibrary\Manifests\playlist.json" `
  --m3u "D:\RadioPoggersLibrary\Playlists\playlist.m3u"
```

Use `Managed` como biblioteca nas proximas importacoes para reaproveitar musicas ja organizadas.

## Argumentos principais

- `--library`: pasta com arquivos locais. Pode repetir.
- `--organize-to`: copia faixas encontradas para `Artista/Album/Faixa.ext`.
- `--m3u`: gera playlist com faixas `ready`.
- `--skip-hashes`: pula SHA-256 para ser mais rapido, com deduplicacao menos forte.

## Saida

Cada item sai assim:

```json
{
  "spotify_id": "id",
  "spotify_url": "https://open.spotify.com/track/id",
  "title": "Nome",
  "artists": ["Artista"],
  "album": "Album",
  "duration_ms": 180000,
  "cover_url": "https://i.scdn.co/image/...",
  "local_file": "D:\\RadioPoggersLibrary\\Managed\\Artista\\Album\\01 - Nome.mp3",
  "status": "ready",
  "match": {
    "score": 100,
    "reason": "artist_title_exact",
    "source_file": "D:\\RadioPoggersLibrary\\Inbox\\Artista - Nome.mp3",
    "sha256": "..."
  }
}
```

Itens sem arquivo local ficam com:

```json
{
  "local_file": "",
  "status": "pending_local_audio"
}
```

