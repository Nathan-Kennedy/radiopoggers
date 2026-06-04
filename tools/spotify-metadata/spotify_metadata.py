#!/usr/bin/env python3
"""
Exporta metadados Spotify e pareia com uma biblioteca local.

Este script nao baixa audio, previews ou capas. Ele consulta a Spotify Web API,
varre pastas locais autorizadas, evita duplicados e gera manifests/playlists.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
import shutil
import sys
import time
import unicodedata
from hashlib import sha256
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


API_BASE = "https://api.spotify.com/v1"
TOKEN_URL = "https://accounts.spotify.com/api/token"
AUDIO_EXTENSIONS = {".mp3", ".flac", ".wav", ".m4a", ".aac", ".ogg", ".opus"}
CHUNK_SIZE = 1024 * 1024
FIXTURE_FALLBACKS = {
    "37i9dQZF1DZ06evO47cwRq": Path("data/spotify-linkin-park.sample.json"),
}


def parse_spotify_ref(value: str) -> tuple[str, str]:
    patterns = [
        r"open\.spotify\.com/(?P<kind>track|playlist)/(?P<id>[A-Za-z0-9]+)",
        r"spotify:(?P<kind>track|playlist):(?P<id>[A-Za-z0-9]+)",
    ]

    for pattern in patterns:
        match = re.search(pattern, value)
        if match:
            return match.group("kind"), match.group("id")

    raise ValueError("Informe um link/URI Spotify de track ou playlist.")


def request_json(url: str, headers: dict[str, str] | None = None, data: bytes | None = None) -> dict[str, Any]:
    request = Request(url, headers=headers or {}, data=data)

    try:
        with urlopen(request, timeout=25) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        body = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Spotify retornou HTTP {error.code}: {body}") from error
    except URLError as error:
        raise RuntimeError(f"Falha de rede ao chamar Spotify: {error}") from error


def get_access_token(client_id: str, client_secret: str) -> str:
    auth = base64.b64encode(f"{client_id}:{client_secret}".encode("utf-8")).decode("ascii")
    payload = urlencode({"grant_type": "client_credentials"}).encode("utf-8")
    data = request_json(
        TOKEN_URL,
        headers={
            "Authorization": f"Basic {auth}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        data=payload,
    )

    token = data.get("access_token")
    if not token:
        raise RuntimeError("Token Spotify nao foi retornado.")

    return token


def best_cover(images: list[dict[str, Any]]) -> str:
    if not images:
        return ""

    sorted_images = sorted(images, key=lambda item: item.get("width") or 0, reverse=True)
    return sorted_images[0].get("url", "")


def normalize_track(track: dict[str, Any]) -> dict[str, Any] | None:
    if not track or track.get("type") != "track":
        return None

    album = track.get("album") or {}
    artists = [artist.get("name", "") for artist in track.get("artists", []) if artist.get("name")]
    spotify_url = (track.get("external_urls") or {}).get("spotify", "")
    external_ids = track.get("external_ids") or {}

    return {
        "spotify_id": track.get("id", ""),
        "isrc": external_ids.get("isrc", ""),
        "spotify_url": spotify_url,
        "title": track.get("name", ""),
        "artists": artists,
        "album": album.get("name", ""),
        "duration_ms": track.get("duration_ms", 0),
        "track_number": track.get("track_number", 0),
        "disc_number": track.get("disc_number", 0),
        "cover_url": best_cover(album.get("images") or []),
        "local_file": "",
        "status": "pending_local_audio",
        "match": None,
    }


def get_track(token: str, track_id: str, market: str) -> list[dict[str, Any]]:
    query = urlencode({"market": market}) if market else ""
    url = f"{API_BASE}/tracks/{track_id}" + (f"?{query}" if query else "")
    data = request_json(url, headers={"Authorization": f"Bearer {token}"})
    item = normalize_track(data)
    return [item] if item else []


def get_playlist_tracks(token: str, playlist_id: str, market: str) -> list[dict[str, Any]]:
    fields = (
        "items(track(id,type,name,duration_ms,track_number,disc_number,external_ids,"
        "external_urls,album(name,images),artists(name))),next,total"
    )
    params = {
        "limit": 100,
        "fields": fields,
    }
    if market:
        params["market"] = market

    url = f"{API_BASE}/playlists/{playlist_id}/tracks?{urlencode(params)}"
    items: list[dict[str, Any]] = []

    while url:
        data = request_json(url, headers={"Authorization": f"Bearer {token}"})

        for entry in data.get("items", []):
            item = normalize_track(entry.get("track"))
            if item:
                items.append(item)

        url = data.get("next")

    return items


def normalize_text(value: str) -> str:
    text = unicodedata.normalize("NFKD", value or "")
    text = "".join(char for char in text if not unicodedata.combining(char))
    text = text.lower()
    text = re.sub(r"\([^)]*\)|\[[^]]*]", " ", text)
    text = re.sub(r"\b(feat|ft|remaster|remastered|radio edit|explicit|clean)\b", " ", text)
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def safe_path_part(value: str, fallback: str) -> str:
    text = value.strip() or fallback
    text = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", text)
    text = re.sub(r"\s+", " ", text).strip(" .")
    return text[:120] or fallback


def file_sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(CHUNK_SIZE), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_filename(path: Path) -> dict[str, str]:
    stem = path.stem
    clean = re.sub(r"^\d+[\s._-]+", "", stem).strip()

    if " - " in clean:
        artist, title = clean.split(" - ", 1)
    else:
        artist, title = "", clean

    return {
        "artist": artist.strip(),
        "title": title.strip(),
        "artist_key": normalize_text(artist),
        "title_key": normalize_text(title),
        "full_key": normalize_text(f"{artist} {title}"),
    }


def scan_library(paths: list[Path], include_hashes: bool) -> dict[str, Any]:
    files: list[dict[str, Any]] = []
    by_hash: dict[str, dict[str, Any]] = {}
    duplicate_files: list[dict[str, str]] = []

    for root in paths:
        if not root.exists():
            continue

        for path in root.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in AUDIO_EXTENSIONS:
                continue

            parsed = parse_filename(path)
            item = {
                "path": str(path.resolve()),
                "name": path.name,
                "extension": path.suffix.lower(),
                "size": path.stat().st_size,
                "artist_key": parsed["artist_key"],
                "title_key": parsed["title_key"],
                "full_key": parsed["full_key"],
                "sha256": "",
            }

            if include_hashes:
                item["sha256"] = file_sha256(path)
                if item["sha256"] in by_hash:
                    duplicate_files.append({
                        "path": item["path"],
                        "duplicate_of": by_hash[item["sha256"]]["path"],
                        "reason": "same_sha256",
                    })
                    continue

                by_hash[item["sha256"]] = item

            files.append(item)

    return {
        "files": files,
        "duplicate_files": duplicate_files,
    }


def score_candidate(track: dict[str, Any], file_item: dict[str, Any]) -> tuple[int, str]:
    title_key = normalize_text(track.get("title", ""))
    artist_keys = [normalize_text(artist) for artist in track.get("artists", [])]
    primary_artist = artist_keys[0] if artist_keys else ""
    file_title = file_item.get("title_key", "")
    file_artist = file_item.get("artist_key", "")
    file_full = file_item.get("full_key", "")

    if title_key and primary_artist and title_key == file_title and primary_artist == file_artist:
        return 100, "artist_title_exact"

    if title_key and primary_artist and title_key in file_full and primary_artist in file_full:
        return 92, "artist_title_in_filename"

    if title_key and title_key == file_title:
        return 74, "title_exact"

    if title_key and title_key in file_full:
        return 60, "title_in_filename"

    return 0, "no_match"


def match_tracks_to_library(tracks: list[dict[str, Any]], library_files: list[dict[str, Any]]) -> None:
    used_paths: set[str] = set()

    for track in tracks:
        best_score = 0
        best_reason = "no_match"
        best_file: dict[str, Any] | None = None

        for file_item in library_files:
            if file_item["path"] in used_paths:
                continue

            score, reason = score_candidate(track, file_item)
            if score > best_score:
                best_score = score
                best_reason = reason
                best_file = file_item

        if best_file and best_score >= 60:
            used_paths.add(best_file["path"])
            track["local_file"] = best_file["path"]
            track["status"] = "ready"
            track["match"] = {
                "score": best_score,
                "reason": best_reason,
                "source_file": best_file["path"],
                "sha256": best_file.get("sha256", ""),
            }


def organize_tracks(tracks: list[dict[str, Any]], target_root: Path) -> None:
    target_root.mkdir(parents=True, exist_ok=True)

    for track in tracks:
        source = Path(track.get("local_file") or "")
        if track.get("status") != "ready" or not source.exists():
            continue

        artist = safe_path_part((track.get("artists") or ["Artista Desconhecido"])[0], "Artista Desconhecido")
        album = safe_path_part(track.get("album") or "Singles", "Singles")
        title = safe_path_part(track.get("title") or source.stem, source.stem)
        number = int(track.get("track_number") or 0)
        prefix = f"{number:02d} - " if number > 0 else ""
        destination_dir = target_root / artist / album
        destination = destination_dir / f"{prefix}{title}{source.suffix.lower()}"

        destination_dir.mkdir(parents=True, exist_ok=True)

        if destination.exists():
            if file_sha256(destination) == file_sha256(source):
                track["local_file"] = str(destination.resolve())
                track["match"]["organized_file"] = str(destination.resolve())
                track["match"]["organize_action"] = "reused_existing_copy"
                continue

            suffix = source.suffix.lower()
            destination = destination_dir / f"{prefix}{title} - {source.stat().st_size}{suffix}"

        shutil.copy2(source, destination)
        track["local_file"] = str(destination.resolve())
        track["match"]["organized_file"] = str(destination.resolve())
        track["match"]["organize_action"] = "copied"


def dedupe_spotify_tracks(tracks: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    duplicates: list[dict[str, Any]] = []

    for position, track in enumerate(tracks, start=1):
        key = track.get("spotify_id") or f"{normalize_text(track.get('title', ''))}:{normalize_text(' '.join(track.get('artists', [])))}"
        track["playlist_position"] = position

        if key in seen:
            duplicate = dict(track)
            duplicate["status"] = "duplicate_spotify_item"
            duplicates.append(duplicate)
            continue

        seen.add(key)
        unique.append(track)

    return unique, duplicates


def write_m3u(path: Path, tracks: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["#EXTM3U"]

    for track in tracks:
        local_file = track.get("local_file")
        if track.get("status") != "ready" or not local_file:
            continue

        duration = int((track.get("duration_ms") or 0) / 1000)
        artist = ", ".join(track.get("artists") or [])
        title = track.get("title", "")
        lines.append(f"#EXTINF:{duration},{artist} - {title}".rstrip())
        lines.append(local_file)

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def load_fixture_tracks(spotify_id: str) -> tuple[list[dict[str, Any]], dict[str, Any]] | None:
    fixture = FIXTURE_FALLBACKS.get(spotify_id)
    if not fixture or not fixture.exists():
        return None

    payload = json.loads(fixture.read_text(encoding="utf-8"))
    return payload.get("items", []), payload.get("source", {})


def write_output(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Exporta metadados Spotify e pareia com audio local.")
    parser.add_argument("spotify_link", help="Link ou URI de track/playlist do Spotify.")
    parser.add_argument("--out", default="data/spotify-metadata.json", help="Arquivo JSON de saida.")
    parser.add_argument("--market", default="BR", help="Mercado Spotify usado na consulta. Padrao: BR.")
    parser.add_argument(
        "--library",
        action="append",
        default=[],
        help="Pasta local com audios autorizados. Pode ser usado mais de uma vez.",
    )
    parser.add_argument(
        "--organize-to",
        default="",
        help="Copia faixas encontradas para Artista/Album/Faixa dentro desta pasta.",
    )
    parser.add_argument(
        "--m3u",
        default="",
        help="Gera playlist M3U somente com faixas locais prontas.",
    )
    parser.add_argument(
        "--skip-hashes",
        action="store_true",
        help="Nao calcula SHA-256 dos arquivos locais. Mais rapido, mas deduplica pior.",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    client_id = os.environ.get("SPOTIFY_CLIENT_ID", "").strip()
    client_secret = os.environ.get("SPOTIFY_CLIENT_SECRET", "").strip()

    try:
        kind, spotify_id = parse_spotify_ref(args.spotify_link)
        source_override: dict[str, Any] = {}

        if not client_id or not client_secret:
            fixture = load_fixture_tracks(spotify_id)
            if not fixture:
                print("Defina SPOTIFY_CLIENT_ID e SPOTIFY_CLIENT_SECRET no ambiente.", file=sys.stderr)
                return 2

            raw_tracks, source_override = fixture
            print("Usando fixture local de teste porque as credenciais Spotify nao foram definidas.")
        else:
            token = get_access_token(client_id, client_secret)

            if kind == "track":
                raw_tracks = get_track(token, spotify_id, args.market)
            else:
                raw_tracks = get_playlist_tracks(token, spotify_id, args.market)

        tracks, duplicate_spotify_items = dedupe_spotify_tracks(raw_tracks)
        library_paths = [Path(path) for path in args.library]
        library = scan_library(library_paths, include_hashes=not args.skip_hashes) if library_paths else {
            "files": [],
            "duplicate_files": [],
        }

        match_tracks_to_library(tracks, library["files"])

        if args.organize_to:
            organize_tracks(tracks, Path(args.organize_to))

        if args.m3u:
            write_m3u(Path(args.m3u), tracks)

        payload = {
            "source": {
                "kind": kind,
                "id": spotify_id,
                "input": args.spotify_link,
                **source_override,
            },
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "notice": "Metadata only. Audio deve vir de arquivos locais autorizados.",
            "library": {
                "scanned_paths": [str(path) for path in library_paths],
                "audio_files_found": len(library["files"]),
                "duplicate_files": library["duplicate_files"],
            },
            "summary": {
                "spotify_items": len(raw_tracks),
                "unique_items": len(tracks),
                "ready": sum(1 for track in tracks if track.get("status") == "ready"),
                "pending_local_audio": sum(1 for track in tracks if track.get("status") == "pending_local_audio"),
                "duplicate_spotify_items": len(duplicate_spotify_items),
            },
            "items": tracks,
            "duplicate_spotify_items": duplicate_spotify_items,
        }

        write_output(Path(args.out), payload)
        if args.m3u:
            print(f"Playlist M3U: {args.m3u}")
        print(
            f"Salvo: {args.out} "
            f"({payload['summary']['ready']} prontas, "
            f"{payload['summary']['pending_local_audio']} pendentes)"
        )
        return 0
    except Exception as error:
        print(f"Erro: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

