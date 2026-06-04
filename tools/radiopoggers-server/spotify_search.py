"""Busca faixas por nome/artista para o bot Discord."""

from __future__ import annotations

import base64
import os
import re
import unicodedata
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

SPOTIFY_API = "https://api.spotify.com/v1"
SPOTIFY_TOKEN_URL = "https://accounts.spotify.com/api/token"
DATA_DIR = Path(__file__).resolve().parents[2] / "data"
SPOTIFY_CREDENTIALS_FILE = DATA_DIR / "spotify-api-credentials.txt"


def normalize_text(value: str) -> str:
    text = unicodedata.normalize("NFKD", value or "")
    text = "".join(char for char in text if not unicodedata.combining(char))
    text = text.lower()
    text = re.sub(r"[()\[\]]", " ", text)
    text = re.sub(r"\b(feat|ft|remaster|remastered|radio edit|explicit|clean)\b", " ", text)
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _read_spotify_credentials_file() -> tuple[str, str]:
    if not SPOTIFY_CREDENTIALS_FILE.exists():
        return "", ""

    client_id = ""
    client_secret = ""
    plain_values: list[str] = []

    for line in SPOTIFY_CREDENTIALS_FILE.read_text(encoding="utf-8").splitlines():
        cleaned = line.strip()
        if not cleaned or cleaned.startswith("#"):
            continue
        if "=" in cleaned:
            key, _, value = cleaned.partition("=")
            normalized_key = key.strip().upper().replace("-", "_")
            normalized_value = value.strip().strip('"').strip("'")
            if normalized_key in {"SPOTIFY_CLIENT_ID", "CLIENT_ID"}:
                client_id = normalized_value
            elif normalized_key in {"SPOTIFY_CLIENT_SECRET", "CLIENT_SECRET"}:
                client_secret = normalized_value
            continue
        plain_values.append(cleaned)

    if not client_id and plain_values:
        client_id = plain_values[0]
    if not client_secret and len(plain_values) >= 2:
        client_secret = plain_values[1]
    return client_id, client_secret


def spotify_credentials() -> tuple[str, str]:
    client_id = os.environ.get("SPOTIFY_CLIENT_ID", "").strip()
    client_secret = os.environ.get("SPOTIFY_CLIENT_SECRET", "").strip()
    if client_id and client_secret:
        return client_id, client_secret

    file_id, file_secret = _read_spotify_credentials_file()
    return file_id, file_secret


def spotify_credentials_configured() -> bool:
    client_id, client_secret = spotify_credentials()
    return bool(client_id and client_secret)


def spotify_access_token() -> str:
    client_id, client_secret = spotify_credentials()
    if not client_id or not client_secret:
        raise RuntimeError(
            "Busca Spotify indisponivel. Defina SPOTIFY_CLIENT_ID e SPOTIFY_CLIENT_SECRET "
            "no ambiente ou em data/spotify-api-credentials.txt "
            "(veja data/spotify-api-credentials.example.txt)."
        )

    auth = base64.b64encode(f"{client_id}:{client_secret}".encode("utf-8")).decode("ascii")
    payload = urlencode({"grant_type": "client_credentials"}).encode("utf-8")
    request = Request(
        SPOTIFY_TOKEN_URL,
        data=payload,
        method="POST",
        headers={
            "Authorization": f"Basic {auth}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
    )
    with urlopen(request, timeout=20) as response:
        data = __import__("json").loads(response.read().decode("utf-8"))
    token = str(data.get("access_token") or "").strip()
    if not token:
        raise RuntimeError("Spotify nao retornou access token.")
    return token


def spotify_request(path: str, token: str) -> dict[str, Any]:
    request = Request(
        f"{SPOTIFY_API}{path}",
        headers={"Authorization": f"Bearer {token}"},
    )
    with urlopen(request, timeout=20) as response:
        payload = response.read().decode("utf-8")
    data = __import__("json").loads(payload)
    return data if isinstance(data, dict) else {}


def score_local_track(query_key: str, track: dict[str, Any]) -> int:
    artists = track.get("artists") if isinstance(track.get("artists"), list) else []
    artist_text = normalize_text(", ".join(str(item) for item in artists))
    title_text = normalize_text(str(track.get("title") or ""))
    album_text = normalize_text(str(track.get("album") or ""))
    haystack = f"{artist_text} {title_text} {album_text}".strip()

    if not query_key:
        return 0

    score = 0
    if query_key == title_text:
        score += 300
    if query_key == artist_text:
        score += 260
    if query_key in title_text:
        score += 180
    if query_key in artist_text:
        score += 140
    if query_key in haystack:
        score += 80

    query_words = [word for word in query_key.split() if len(word) >= 2]
    if query_words:
        matched = sum(1 for word in query_words if word in haystack)
        score += matched * 25
        if matched == len(query_words):
            score += 40

    if str(track.get("status") or "").lower() == "ready":
        score += 20
    return score


def find_best_local_track(query: str) -> dict[str, Any] | None:
    from server import filter_library_tracks, load_library_catalog

    query_key = normalize_text(query)
    if not query_key:
        return None

    catalog = load_library_catalog(refresh=False)
    tracks = catalog.get("tracks") if isinstance(catalog.get("tracks"), list) else []
    candidates, _total = filter_library_tracks(tracks, query=query, limit=40)
    ready = [
        track for track in candidates
        if isinstance(track, dict)
        and str(track.get("status") or "").lower() == "ready"
        and str(track.get("local_file") or "").strip()
    ]
    if not ready:
        ready = [
            track for track in tracks
            if isinstance(track, dict)
            and str(track.get("status") or "").lower() == "ready"
            and score_local_track(query_key, track) >= 80
        ]

    if not ready:
        return None

    best = max(ready, key=lambda track: score_local_track(query_key, track))
    if score_local_track(query_key, best) < 60:
        return None

    artists = best.get("artists") if isinstance(best.get("artists"), list) else []
    return {
        "source": "library",
        "track_id": str(best.get("id") or best.get("spotify_id") or "").strip(),
        "spotify_url": str(best.get("spotify_url") or "").strip(),
        "title": str(best.get("title") or ""),
        "artist": ", ".join(str(item) for item in artists if item),
        "score": score_local_track(query_key, best),
    }


def score_spotify_track(query_key: str, track: dict[str, Any]) -> int:
    artists = [artist.get("name", "") for artist in track.get("artists") or [] if artist.get("name")]
    artist_text = normalize_text(", ".join(artists))
    title_text = normalize_text(str(track.get("name") or ""))
    haystack = f"{artist_text} {title_text}".strip()
    popularity = int(track.get("popularity") or 0)

    score = score_local_track(
        query_key,
        {"title": track.get("name"), "artists": artists, "album": "", "status": "ready"},
    )
    score += int(popularity * 0.8)

    if query_key == artist_text:
        score += popularity
    if query_key in artist_text and query_key not in title_text:
        score += min(popularity, 80)

    if query_key in haystack:
        score += 10
    return score


def search_spotify_track(query: str, limit: int = 10) -> dict[str, Any] | None:
    query_key = normalize_text(query)
    if not query_key:
        return None

    token = spotify_access_token()
    params = urlencode({
        "q": query.strip(),
        "type": "track",
        "limit": max(min(limit, 10), 1),
        "market": "BR",
    })
    data = spotify_request(f"/search?{params}", token)
    items = data.get("tracks", {}).get("items") if isinstance(data.get("tracks"), dict) else []
    tracks = [item for item in items if isinstance(item, dict) and item.get("id")]
    if not tracks:
        return None

    best = max(tracks, key=lambda track: score_spotify_track(query_key, track))
    artists = [artist.get("name", "") for artist in best.get("artists") or [] if artist.get("name")]
    spotify_url = (best.get("external_urls") or {}).get("spotify") or f"https://open.spotify.com/track/{best.get('id')}"
    return {
        "source": "spotify_search",
        "track_id": str(best.get("id") or ""),
        "spotify_url": spotify_url,
        "title": str(best.get("name") or ""),
        "artist": ", ".join(artists),
        "popularity": int(best.get("popularity") or 0),
        "score": score_spotify_track(query_key, best),
    }


def resolve_play_query(query: str) -> dict[str, Any]:
    raw = str(query or "").strip()
    if not raw:
        raise ValueError("Informe o nome da musica ou do artista.")

    local = find_best_local_track(raw)
    if local and local.get("track_id"):
        return local

    try:
        remote = search_spotify_track(raw)
        if remote and remote.get("spotify_url"):
            return remote
    except Exception as error:
        if local:
            return local
        raise RuntimeError(
            f"Nao achei na biblioteca local e a busca Spotify falhou: {error}"
        ) from error

    if local:
        return local

    raise RuntimeError(f"Nenhuma faixa encontrada para: {raw}")
