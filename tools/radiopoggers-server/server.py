#!/usr/bin/env python3
"""
Servidor local da RadioPoggers.

Ele permite que o frontend envie um link do Spotify, baixe os audios via
spotdl para a biblioteca local, gere um manifesto e sincronize faixas prontas
com o AzuraCast.
"""

from __future__ import annotations

import base64
import json
import os
import random
import re
import secrets
import shlex
import shutil
import subprocess
import sys
import threading
import time
import unicodedata
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.error import HTTPError
from urllib.parse import parse_qs, quote, unquote, urlunparse, urlparse
from urllib.request import Request, urlopen

try:
    from miku_narrator import (
        MIKU_LISTENER_ID,
        MIKU_MAX_SECONDS,
        MIKU_MID_COOLDOWN_SEC,
        MIKU_MID_INFO_CHANCE,
        MIKU_MID_TRACK_CHANCE,
        MIKU_MIN_TRACK_SECONDS,
        MIKU_TRACK_CHANGE_DELAY_SEC,
        build_track_key,
        generate_miku_narration,
        miku_status,
        pick_mid_break_moment,
    )
except ImportError:
    MIKU_LISTENER_ID = "miku-narrator"
    MIKU_MAX_SECONDS = 28
    MIKU_MID_TRACK_CHANCE = 0.58
    MIKU_MID_COOLDOWN_SEC = 22.0
    MIKU_MID_INFO_CHANCE = 0.4
    MIKU_MIN_TRACK_SECONDS = 48
    MIKU_TRACK_CHANGE_DELAY_SEC = 10.0

    def pick_mid_break_moment() -> str:
        return "mid_track"

    build_track_key = None  # type: ignore[assignment]
    generate_miku_narration = None  # type: ignore[assignment]

    def miku_status() -> dict[str, Any]:
        return {"enabled": False, "error": "Modulo miku_narrator indisponivel."}

try:
    from hoshino_narrator import (
        HOSHINO_LISTENER_ID,
        HOSHINO_MAX_SECONDS,
        generate_hoshino_narration,
        hoshino_status,
    )
except ImportError:
    HOSHINO_LISTENER_ID = "hoshino-narrator"
    HOSHINO_MAX_SECONDS = 28
    generate_hoshino_narration = None  # type: ignore[assignment]

    def hoshino_status() -> dict[str, Any]:
        return {"enabled": False, "error": "Modulo hoshino_narrator indisponivel."}

try:
    from vote_system import (
        audience_counts,
        cast_vote,
        execute_direct,
        get_active_vote_public,
        record_heartbeat,
        register_miku_hook,
        register_vote_executor,
        resolve_skip_narrator_moment,
        sse_subscribe,
        start_vote,
        vote_status,
    )
except ImportError:
    def vote_status() -> dict[str, Any]:
        return {"enabled": False, "error": "Modulo vote_system indisponivel."}

    def audience_counts() -> dict[str, int]:
        return {"eligible": 0, "total_on_site": 0}

    def get_active_vote_public() -> dict[str, Any] | None:
        return None

    def record_heartbeat(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
        raise RuntimeError("Modulo vote_system indisponivel.")

    def start_vote(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
        raise RuntimeError("Modulo vote_system indisponivel.")

    def cast_vote(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
        raise RuntimeError("Modulo vote_system indisponivel.")

    def execute_direct(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
        raise RuntimeError("Modulo vote_system indisponivel.")

    def register_vote_executor(_executor: Any) -> None:
        pass

    def register_miku_hook(_hook: Any) -> None:
        pass

    def resolve_skip_narrator_moment(base_moment: str, _proposer_id: str) -> str:
        return base_moment

    def sse_subscribe() -> tuple[list[str], Any]:
        return [], lambda: None

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
LIBRARY_INBOX = PROJECT_ROOT / "library" / "Inbox"
LIBRARY_MANAGED = PROJECT_ROOT / "library" / "Managed"
SPOTDL_DOWNLOAD_ROOT = LIBRARY_INBOX / "Spotdl"
SPOTIFY_TOOL = PROJECT_ROOT / "tools" / "spotify-metadata" / "spotify_metadata.py"
DEFAULT_MANIFEST = DATA_DIR / "spotify-imported.json"
DEFAULT_M3U = DATA_DIR / "spotify-imported.m3u"
LIBRARY_CATALOG = DATA_DIR / "library-catalog.json"
VOICE_DROPS_DIR = DATA_DIR / "voice-drops"
AUDIO_EXTENSIONS = {".mp3", ".flac", ".wav", ".m4a", ".aac", ".ogg", ".opus", ".webm"}

HOST = os.environ.get("RADIOPOGGERS_API_HOST", "127.0.0.1").strip() or "127.0.0.1"
PORT = int(os.environ.get("RADIOPOGGERS_API_PORT", "8765"))
STATION_SHORTCODE = os.environ.get("RADIOPOGGERS_STATION", "radio-no-grale")
AZURACAST_CONTAINER = os.environ.get("RADIOPOGGERS_AZURACAST_CONTAINER", "azuracast")
AZURACAST_BASE_URL = os.environ.get("RADIOPOGGERS_AZURACAST_BASE_URL", "http://localhost").rstrip("/")
PUBLIC_AZURACAST_BASE_URL = (
    os.environ.get("RADIOPOGGERS_PUBLIC_AZURACAST_URL", "").strip().rstrip("/")
    or AZURACAST_BASE_URL
)
AZURACAST_API_KEY_FILE = DATA_DIR / "azuracast-api-key.txt"
MAINTENANCE_FILE = DATA_DIR / "maintenance.json"
APP_RELEASE_MANIFEST = DATA_DIR / "app-release.json"
APP_RELEASE_APK_DEFAULT = PROJECT_ROOT / "dist" / "app-release" / "RadioPoggers-android.apk"


def load_app_release_manifest() -> dict[str, Any] | None:
    """Metadados da APK publicada pelo operador (data/app-release.json)."""
    try:
        if not APP_RELEASE_MANIFEST.is_file():
            return None
        raw = json.loads(APP_RELEASE_MANIFEST.read_text(encoding="utf-8"))
        return raw if isinstance(raw, dict) else None
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return None


def resolve_app_release_apk_path(manifest: dict[str, Any] | None = None) -> Path | None:
    manifest = manifest if manifest is not None else load_app_release_manifest()
    if manifest:
        custom = str(manifest.get("android_apk_path") or "").strip()
        if custom:
            candidate = Path(custom)
            if not candidate.is_absolute():
                candidate = PROJECT_ROOT / candidate
            if candidate.is_file():
                return candidate
    if APP_RELEASE_APK_DEFAULT.is_file():
        return APP_RELEASE_APK_DEFAULT
    return None


def load_maintenance_status() -> dict[str, Any]:
    """Aviso operacional para ouvintes (arquivo data/maintenance.json)."""
    default: dict[str, Any] = {
        "active": False,
        "message": "",
        "level": "maintenance",
        "updated_at": None,
    }
    try:
        if not MAINTENANCE_FILE.is_file():
            return default
        raw = json.loads(MAINTENANCE_FILE.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            return {**default, "error": "invalid_maintenance_file"}
        level = str(raw.get("level") or "maintenance").strip().lower()
        if level not in ("maintenance", "warning"):
            level = "maintenance"
        return {
            "active": bool(raw.get("active")),
            "message": str(raw.get("message") or "").strip(),
            "level": level,
            "updated_at": raw.get("updated_at"),
        }
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return {**default, "error": "invalid_maintenance_file"}


def normalize_client_art_url(url: str) -> str:
    raw = str(url or "").strip()
    if not raw:
        return ""

    public_base = PUBLIC_AZURACAST_BASE_URL or "http://localhost"
    try:
        parsed = urlparse(raw)
    except ValueError:
        return raw

    if parsed.hostname not in {"localhost", "127.0.0.1"}:
        return raw

    try:
        public = urlparse(public_base if "://" in public_base else f"http://{public_base}")
    except ValueError:
        return raw

    if not public.netloc:
        return raw

    normalized = parsed._replace(scheme=public.scheme or parsed.scheme, netloc=public.netloc)
    return urlunparse(normalized)


def resolve_azuracast_api_key() -> str:
    env_key = os.environ.get("RADIOPOGGERS_AZURACAST_API_KEY", "").strip()
    if env_key:
        return env_key
    if AZURACAST_API_KEY_FILE.exists():
        for line in AZURACAST_API_KEY_FILE.read_text(encoding="utf-8").splitlines():
            cleaned = line.strip()
            if cleaned and not cleaned.startswith("#"):
                return cleaned
    return ""


def azuracast_http_error_message(error: HTTPError) -> str:
    detail = error.read().decode("utf-8", errors="replace")
    try:
        payload = json.loads(detail) if detail.strip() else {}
        message = str(payload.get("formatted_message") or payload.get("message") or detail).strip()
    except json.JSONDecodeError:
        message = detail.strip() or str(error)
    return message or f"AzuraCast HTTP {error.code}"


AZURACAST_API_KEY = resolve_azuracast_api_key()
SPOTDL_TIMEOUT = int(os.environ.get("RADIOPOGGERS_SPOTDL_TIMEOUT", "3600"))
_LIBRARY_CATALOG_CACHE: dict[str, Any] | None = None
_LIBRARY_CATALOG_REVISION = 0
_LIBRARY_REBUILD_LOCK = threading.Lock()
_AZURACAST_REQUESTS_CACHE: tuple[float, list[dict[str, Any]]] | None = None
_VOICE_DROP_LOCK = threading.Lock()
_ACTIVE_VOICE_DROP: dict[str, Any] | None = None
VOICE_DROP_MAX_SECONDS = int(os.environ.get("RADIOPOGGERS_VOICE_DROP_MAX_SECONDS", "15"))
VOICE_DROP_MAX_BYTES = int(os.environ.get("RADIOPOGGERS_VOICE_DROP_MAX_BYTES", str(3 * 1024 * 1024)))
VOICE_DROP_DELIVERY_GRACE_SEC = float(os.environ.get("RADIOPOGGERS_VOICE_DROP_DELIVERY_GRACE_SEC", "90"))
_LAST_AZURACAST_NOW_PLAYING_SYNC = 0.0
_STATION_ID_CACHE: int | None = None
_AZURACAST_PLAYLIST_FIXED = False
NOWPLAYING_AUTO_SYNC_SECONDS = int(os.environ.get("RADIOPOGGERS_NOWPLAYING_SYNC_SECONDS", "20"))
NOWPLAYING_SYNC_COOLDOWN_SECONDS = int(os.environ.get("RADIOPOGGERS_NOWPLAYING_SYNC_COOLDOWN", "10"))
_MIKU_TRACK_KEY = ""
_MIKU_GENERATION_BUSY = False
_MIKU_GENERATION_LOCK = threading.Lock()
_MIKU_MID_SPOKE = False
_MIKU_MID_WILL_SPEAK = False
_MIKU_MID_MOMENT = "mid_track"
_MIKU_MID_TARGET_RATIO = 0.5
_MIKU_LAST_SPOKE_AT = 0.0
_MIKU_TRACK_CHANGE_TIMER: threading.Timer | None = None
_MIKU_TRACK_CHANGE_TIMER_LOCK = threading.Lock()


def json_response(handler: BaseHTTPRequestHandler, status: int, payload: dict[str, Any]) -> None:
    body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
    handler.send_header(
        "Access-Control-Allow-Headers",
        "Content-Type, X-Duration-Ms, X-Listener-Id, X-Client-Radio-Processed",
    )
    handler.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
    handler.end_headers()
    handler.wfile.write(body)


def read_json_body(handler: BaseHTTPRequestHandler) -> dict[str, Any]:
    length = int(handler.headers.get("Content-Length", "0"))
    if length <= 0:
        return {}

    raw = handler.rfile.read(length)
    return json.loads(raw.decode("utf-8"))


def drain_request_body(handler: BaseHTTPRequestHandler) -> None:
    length = int(handler.headers.get("Content-Length", "0"))
    if length > 0:
        handler.rfile.read(length)


def read_binary_body(handler: BaseHTTPRequestHandler) -> bytes:
    length = int(handler.headers.get("Content-Length", "0"))
    if length <= 0:
        return b""

    if length > VOICE_DROP_MAX_BYTES:
        drain_request_body(handler)
        raise ValueError(f"Audio excede {VOICE_DROP_MAX_BYTES // (1024 * 1024)} MB.")

    return handler.rfile.read(length)


def fetch_json_url(url: str, timeout: int = 8) -> dict[str, Any]:
    with urlopen(url, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def validate_spotify_url(value: str) -> str:
    value = value.strip()
    parsed = urlparse(value)

    if parsed.scheme not in {"http", "https"}:
        raise ValueError("Use um link Spotify http/https.")

    if parsed.netloc.lower() != "open.spotify.com":
        raise ValueError("O link precisa ser do open.spotify.com.")

    if not re.search(r"/(playlist|track)/[A-Za-z0-9]+", parsed.path):
        raise ValueError("Informe um link de playlist ou faixa do Spotify.")

    return value


def spotify_ref(value: str) -> tuple[str, str]:
    parsed = urlparse(value)
    match = re.search(r"/(playlist|track)/([A-Za-z0-9]+)", parsed.path)
    if not match:
        raise ValueError("Informe um link de playlist ou faixa do Spotify.")

    return match.group(1), match.group(2)


def spotify_url_key(value: str) -> str:
    kind, spotify_id = spotify_ref(value)
    return f"{kind}:{spotify_id}"


class SpotifyImportBusyError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        active_job_id: str,
        active_spotify_url: str = "",
        active_spotify_key: str = "",
    ) -> None:
        super().__init__(message)
        self.active_job_id = active_job_id
        self.active_spotify_url = active_spotify_url
        self.active_spotify_key = active_spotify_key


def run_command(command: list[str], timeout: int = 600) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            command,
            cwd=PROJECT_ROOT,
            text=True,
            capture_output=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as error:
        command_name = " ".join(command[:3])
        raise RuntimeError(f"Comando excedeu {timeout}s: {command_name}") from error


def audio_files_in(root: Path) -> list[Path]:
    if not root.exists():
        return []

    return sorted(
        path for path in root.rglob("*")
        if path.is_file() and path.suffix.lower() in AUDIO_EXTENSIONS
    )


def command_output_tail(result: subprocess.CompletedProcess[str], max_chars: int = 2000) -> str:
    text = "\n".join(part for part in [result.stdout, result.stderr] if part)
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return "\n".join(lines[-20:])[-max_chars:]


def spotdl_command_prefix() -> list[str]:
    configured = os.environ.get("RADIOPOGGERS_SPOTDL_COMMAND", "").strip()
    if configured:
        return shlex.split(configured)

    executable = shutil.which("spotdl")
    if executable:
        return [executable]

    return [sys.executable, "-m", "spotdl"]


def ensure_spotdl_available(command_prefix: list[str]) -> None:
    result = run_command([*command_prefix, "--version"], timeout=30)
    if result.returncode == 0:
        return

    details = command_output_tail(result, max_chars=1000)
    message = (
        "spotdl nao esta disponivel. Instale com "
        "`python -m pip install --upgrade spotdl` ou configure "
        "RADIOPOGGERS_SPOTDL_COMMAND."
    )
    if details:
        message = f"{message} {details}"

    raise RuntimeError(message)


def download_spotify_audio(spotify_url: str) -> dict[str, Any]:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    SPOTDL_DOWNLOAD_ROOT.mkdir(parents=True, exist_ok=True)

    kind, spotify_id = spotify_ref(spotify_url)
    download_dir = SPOTDL_DOWNLOAD_ROOT / f"{kind}-{spotify_id}"
    download_dir.mkdir(parents=True, exist_ok=True)

    before = {str(path.resolve()) for path in audio_files_in(download_dir)}
    save_file = DATA_DIR / f"spotdl-{kind}-{spotify_id}.spotdl"
    errors_file = DATA_DIR / f"spotdl-{kind}-{spotify_id}-errors.json"
    output_template = str(download_dir / "{artists} - {title}.{output-ext}")
    command_prefix = spotdl_command_prefix()
    ensure_spotdl_available(command_prefix)

    catalog = load_library_catalog(refresh=True)
    expected_tracks = load_spotdl_songs(save_file)
    reused_existing = 0
    needs_download = 0

    for song in expected_tracks:
        title = str(song.get("name") or song.get("title") or "")
        artists = song.get("artists") if isinstance(song.get("artists"), list) else []
        if not artists and song.get("artist"):
            artists = [str(song["artist"])]

        existing = find_catalog_track(
            catalog,
            str(song.get("song_id") or ""),
            title,
            artists,
            str(song.get("isrc") or ""),
        )
        if existing:
            reused_existing += 1
        else:
            needs_download += 1

    if expected_tracks and needs_download == 0 and reused_existing > 0:
        after_files = audio_files_in(download_dir)
        return {
            "attempted": False,
            "skipped": True,
            "ok": True,
            "directory": str(download_dir),
            "save_file": str(save_file),
            "errors_file": str(errors_file),
            "audio_files_before": len(before),
            "audio_files_after": len(after_files),
            "downloaded_estimate": 0,
            "reused_existing": reused_existing,
            "needs_download": 0,
            "message": f"{reused_existing} faixa(s) reutilizadas da biblioteca local; nenhum download necessario.",
        }

    command = [
        *command_prefix,
        "download",
        spotify_url,
        "--format",
        "mp3",
        "--output",
        output_template,
        "--save-file",
        str(save_file),
        "--save-errors",
        str(errors_file),
        "--print-errors",
    ]

    result = run_command(command, timeout=SPOTDL_TIMEOUT)
    after_files = audio_files_in(download_dir)
    after = {str(path.resolve()) for path in after_files}
    added = len(after - before)
    output_tail = command_output_tail(result)
    ok = result.returncode == 0

    if expected_tracks and reused_existing > 0:
        message = f"{reused_existing} faixa(s) reutilizadas, {added} nova(s) baixada(s)."
    else:
        message = f"spotdl encontrou {len(after)} arquivo(s); {added} novo(s) nesta importacao."

    payload: dict[str, Any] = {
        "attempted": True,
        "ok": ok,
        "directory": str(download_dir),
        "save_file": str(save_file),
        "errors_file": str(errors_file),
        "audio_files_before": len(before),
        "audio_files_after": len(after),
        "downloaded_estimate": added,
        "reused_existing": reused_existing,
        "needs_download": needs_download or max(len(expected_tracks) - reused_existing, added),
        "message": message,
    }

    if output_tail:
        payload["log_tail"] = output_tail

    if ok:
        return payload

    payload["message"] = (
        "spotdl terminou com erro, mas alguns arquivos foram encontrados."
        if after_files
        else "spotdl terminou com erro e nenhum arquivo foi baixado."
    )

    if not after_files:
        raise RuntimeError(f"spotdl falhou: {output_tail or 'sem detalhes retornados'}")

    return payload


def parse_downloaded_filename(path: Path) -> tuple[list[str], str]:
    clean = re.sub(r"^\d+[\s._-]+", "", path.stem).strip()

    if " - " not in clean:
        return [], clean or path.stem

    artist_text, title = clean.split(" - ", 1)
    artists = [artist.strip() for artist in re.split(r",|;", artist_text) if artist.strip()]
    return artists, title.strip() or path.stem


def normalize_text(value: str) -> str:
    text = unicodedata.normalize("NFKD", value or "")
    text = "".join(char for char in text if not unicodedata.combining(char))
    text = text.lower()
    text = re.sub(r"[()\[\]]", " ", text)
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def downloaded_file_index(files: list[Path]) -> tuple[dict[str, Path], dict[str, Path]]:
    by_full_key: dict[str, Path] = {}
    by_title_key: dict[str, Path] = {}

    for path in files:
        artists, title = parse_downloaded_filename(path)
        artist_text = " ".join(artists)
        title_key = normalize_text(title)
        full_key = normalize_text(f"{artist_text} {title}")

        if full_key:
            by_full_key[full_key] = path
        if title_key:
            by_title_key[title_key] = path

    return by_full_key, by_title_key


def load_spotdl_songs(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []

    return payload if isinstance(payload, list) else []


def write_m3u_from_items(path: Path, items: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["#EXTM3U"]

    for item in items:
        local_file = item.get("local_file")
        if item.get("status") != "ready" or not local_file:
            continue

        artist = ", ".join(item.get("artists") or [])
        title = item.get("title", "")
        lines.append(f"#EXTINF:-1,{artist} - {title}".rstrip())
        lines.append(local_file)

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def default_library_scan_paths() -> list[Path]:
    return [LIBRARY_MANAGED, LIBRARY_INBOX, SPOTDL_DOWNLOAD_ROOT]


def collect_all_library_files(extra_paths: list[Path] | None = None) -> list[Path]:
    paths = list(default_library_scan_paths())
    seen_roots: set[str] = {str(path.resolve()) if path.exists() else str(path) for path in paths}

    if extra_paths:
        for path in extra_paths:
            key = str(path.resolve()) if path.exists() else str(path)
            if key not in seen_roots:
                seen_roots.add(key)
                paths.append(path)

    files: list[Path] = []
    seen_files: set[str] = set()
    for root in paths:
        for path in audio_files_in(root):
            resolved = str(path.resolve())
            if resolved not in seen_files:
                seen_files.add(resolved)
                files.append(path)

    return files


def path_preference_rank(path: Path) -> tuple[int, str]:
    normalized = str(path).replace("\\", "/").lower()
    if "/managed/" in normalized:
        return (0, normalized)
    if "/spotdl/" in normalized:
        return (1, normalized)
    return (2, normalized)


def pick_preferred_path(*candidates: Path | None) -> Path | None:
    existing = [path for path in candidates if path and path.exists()]
    if not existing:
        return None
    return min(existing, key=path_preference_rank)


def track_dedup_key(spotify_id: str, isrc: str, title: str, artists: list[str]) -> str:
    if spotify_id:
        return f"spotify:{spotify_id}"
    if isrc:
        return f"isrc:{isrc}"
    artist_text = normalize_text(" ".join(str(artist) for artist in artists))
    return f"text:{normalize_text(title)}:{artist_text}"


def resolve_track_id(item: dict[str, Any]) -> str:
    spotify_id = str(item.get("spotify_id") or item.get("song_id") or "").strip()
    if spotify_id:
        return spotify_id

    artists = item.get("artists") if isinstance(item.get("artists"), list) else []
    dedup_key = track_dedup_key(
        "",
        str(item.get("isrc") or ""),
        str(item.get("title") or item.get("name") or ""),
        [str(artist) for artist in artists],
    )
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", dedup_key).strip("_")
    return safe or f"local_{int(time.time())}"


def infer_source_tag(path: Path) -> str:
    parts = [part for part in path.parts]
    for index, part in enumerate(parts):
        if part.lower() == "spotdl" and index + 1 < len(parts):
            return parts[index + 1]
    return ""


def catalog_entry_from_item(item: dict[str, Any], source: str = "") -> dict[str, Any] | None:
    local_file = str(item.get("local_file") or "")
    if item.get("status") != "ready" or not local_file:
        return None

    path = Path(local_file)
    if not path.exists():
        return None

    artists = item.get("artists") if isinstance(item.get("artists"), list) else []
    title = str(item.get("title") or item.get("name") or path.stem)
    if not artists:
        parsed_artists, parsed_title = parse_downloaded_filename(path)
        if parsed_artists:
            artists = parsed_artists
        if parsed_title and not title:
            title = parsed_title

    source_tag = source or infer_source_tag(path)
    track_id = resolve_track_id(item)
    sources = [source_tag] if source_tag else []

    return {
        "id": track_id,
        "spotify_id": str(item.get("spotify_id") or item.get("song_id") or ""),
        "isrc": str(item.get("isrc") or ""),
        "spotify_url": str(item.get("spotify_url") or item.get("url") or ""),
        "title": title,
        "artists": artists,
        "album": str(item.get("album") or item.get("album_name") or ""),
        "duration_ms": int(item.get("duration_ms") or (int(item.get("duration") or 0) * 1000)),
        "cover_url": str(item.get("cover_url") or ""),
        "local_file": str(path.resolve()),
        "status": "ready",
        "sources": sources,
    }


def merge_catalog_entries(existing: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
    merged = dict(existing)
    merged_sources = list(existing.get("sources") or [])
    for source in incoming.get("sources") or []:
        if source and source not in merged_sources:
            merged_sources.append(source)

    existing_path = Path(str(existing.get("local_file") or ""))
    incoming_path = Path(str(incoming.get("local_file") or ""))
    preferred = pick_preferred_path(existing_path, incoming_path) or incoming_path

    merged.update({
        "title": incoming.get("title") or existing.get("title"),
        "artists": incoming.get("artists") or existing.get("artists"),
        "album": incoming.get("album") or existing.get("album"),
        "duration_ms": incoming.get("duration_ms") or existing.get("duration_ms"),
        "cover_url": incoming.get("cover_url") or existing.get("cover_url"),
        "spotify_url": incoming.get("spotify_url") or existing.get("spotify_url"),
        "spotify_id": incoming.get("spotify_id") or existing.get("spotify_id"),
        "isrc": incoming.get("isrc") or existing.get("isrc"),
        "local_file": str(preferred.resolve()) if preferred.exists() else merged.get("local_file"),
        "sources": merged_sources,
        "status": "ready",
    })

    spotify_id = str(merged.get("spotify_id") or "").strip()
    if spotify_id:
        merged["id"] = spotify_id
    elif incoming.get("id") and not str(existing.get("id") or "").strip():
        merged["id"] = incoming.get("id")

    return merged


def catalog_entries_are_same_song(left: dict[str, Any], right: dict[str, Any]) -> bool:
    left_spotify = str(left.get("spotify_id") or "").strip()
    right_spotify = str(right.get("spotify_id") or "").strip()
    if left_spotify and right_spotify:
        return left_spotify == right_spotify

    left_isrc = str(left.get("isrc") or "").strip()
    right_isrc = str(right.get("isrc") or "").strip()
    if left_isrc and right_isrc:
        return left_isrc == right_isrc

    left_title = normalize_text(str(left.get("title") or ""))
    right_title = normalize_text(str(right.get("title") or ""))
    if not left_title or left_title != right_title:
        return False

    if left_spotify or right_spotify:
        return True

    left_artists = left.get("artists") if isinstance(left.get("artists"), list) else []
    right_artists = right.get("artists") if isinstance(right.get("artists"), list) else []
    left_artist_text = normalize_text(" ".join(str(artist) for artist in left_artists))
    right_artist_text = normalize_text(" ".join(str(artist) for artist in right_artists))

    if not left_artist_text or not right_artist_text:
        return True

    return left_artist_text == right_artist_text


def find_catalog_merge_key(
    tracks_by_key: dict[str, dict[str, Any]],
    entry: dict[str, Any],
) -> str | None:
    primary_key = track_dedup_key(
        str(entry.get("spotify_id") or ""),
        str(entry.get("isrc") or ""),
        str(entry.get("title") or ""),
        entry.get("artists") if isinstance(entry.get("artists"), list) else [],
    )
    if primary_key in tracks_by_key:
        return primary_key

    for key, existing in tracks_by_key.items():
        if catalog_entries_are_same_song(existing, entry):
            return key

    return None


def consolidate_catalog_tracks(tracks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    consolidated: list[dict[str, Any]] = []

    for entry in tracks:
        match_index: int | None = None
        for index, existing in enumerate(consolidated):
            if catalog_entries_are_same_song(existing, entry):
                match_index = index
                break

        if match_index is None:
            consolidated.append(entry)
        else:
            consolidated[match_index] = merge_catalog_entries(consolidated[match_index], entry)

    return consolidated


def library_catalog_public_meta(catalog: dict[str, Any] | None = None) -> dict[str, Any]:
    if catalog is None:
        catalog = load_library_catalog(refresh=False)

    summary = catalog.get("summary") if isinstance(catalog.get("summary"), dict) else {}
    revision = int(catalog.get("revision") or _LIBRARY_CATALOG_REVISION or 0)

    return {
        "revision": revision,
        "generated_at": catalog.get("generated_at"),
        "tracks": int(summary.get("tracks") or 0),
        "artists": int(summary.get("artists") or 0),
        "albums": int(summary.get("albums") or 0),
    }


def rebuild_library_catalog(manifest: dict[str, Any] | None = None) -> dict[str, Any]:
    global _LIBRARY_CATALOG_CACHE, _LIBRARY_CATALOG_REVISION

    if manifest is None and DEFAULT_MANIFEST.exists():
        manifest = load_manifest(refresh_local=True)

    tracks_by_key: dict[str, dict[str, Any]] = {}

    def upsert(entry: dict[str, Any]) -> None:
        merge_key = find_catalog_merge_key(tracks_by_key, entry)
        if merge_key:
            tracks_by_key[merge_key] = merge_catalog_entries(tracks_by_key[merge_key], entry)
            return

        key = track_dedup_key(
            str(entry.get("spotify_id") or ""),
            str(entry.get("isrc") or ""),
            str(entry.get("title") or ""),
            entry.get("artists") if isinstance(entry.get("artists"), list) else [],
        )
        tracks_by_key[key] = entry

    if isinstance(manifest, dict):
        source = manifest.get("source") or {}
        source_tag = ""
        if source.get("kind") and source.get("id"):
            source_tag = f"{source.get('kind')}-{source.get('id')}"

        for item in manifest.get("items") or []:
            if isinstance(item, dict):
                entry = catalog_entry_from_item(item, source_tag)
                if entry:
                    upsert(entry)

    for save_file in sorted(DATA_DIR.glob("spotdl-*.spotdl")):
        if save_file.name.endswith("-errors.json"):
            continue

        match = re.match(r"spotdl-(playlist|track)-([A-Za-z0-9]+)\.spotdl$", save_file.name)
        source_tag = f"{match.group(1)}-{match.group(2)}" if match else save_file.stem

        for song in load_spotdl_songs(save_file):
            entry = catalog_entry_from_item({
                "spotify_id": song.get("song_id", ""),
                "isrc": song.get("isrc", ""),
                "spotify_url": song.get("url", ""),
                "title": song.get("name") or song.get("title") or "",
                "artists": song.get("artists") if isinstance(song.get("artists"), list) else [],
                "album": song.get("album_name", ""),
                "duration_ms": int(song.get("duration") or 0) * 1000,
                "cover_url": song.get("cover_url", ""),
                "local_file": "",
                "status": "pending_local_audio",
            }, source_tag)
            if not entry:
                title = str(song.get("name") or song.get("title") or "")
                artists = song.get("artists") if isinstance(song.get("artists"), list) else []
                artist_text = " ".join(str(artist) for artist in artists)
                files = collect_all_library_files()
                by_full_key, by_title_key = downloaded_file_index(files)
                path = by_full_key.get(normalize_text(f"{artist_text} {title}")) or by_title_key.get(normalize_text(title))
                if path:
                    entry = catalog_entry_from_item({
                        "spotify_id": song.get("song_id", ""),
                        "isrc": song.get("isrc", ""),
                        "spotify_url": song.get("url", ""),
                        "title": title,
                        "artists": artists,
                        "album": song.get("album_name", ""),
                        "duration_ms": int(song.get("duration") or 0) * 1000,
                        "cover_url": song.get("cover_url", ""),
                        "local_file": str(path.resolve()),
                        "status": "ready",
                    }, source_tag)
            if entry and Path(entry["local_file"]).exists():
                upsert(entry)

    for path in collect_all_library_files():
        resolved = str(path.resolve())
        if any(str(track.get("local_file") or "") == resolved for track in tracks_by_key.values()):
            continue

        parsed_artists, parsed_title = parse_downloaded_filename(path)
        entry = catalog_entry_from_item({
            "title": parsed_title or path.stem,
            "artists": parsed_artists,
            "local_file": str(path.resolve()),
            "status": "ready",
        })
        if entry:
            upsert(entry)

    tracks = consolidate_catalog_tracks(list(tracks_by_key.values()))
    tracks = sorted(
        tracks,
        key=lambda item: (
            normalize_text(" ".join(item.get("artists") or [])),
            normalize_text(str(item.get("title") or "")),
        ),
    )
    artists = sorted({
        artist
        for track in tracks
        for artist in (track.get("artists") or [])
        if artist
    })
    albums = sorted({
        str(track.get("album") or "")
        for track in tracks
        if track.get("album")
    })

    _LIBRARY_CATALOG_REVISION += 1
    payload = {
        "revision": _LIBRARY_CATALOG_REVISION,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "summary": {
            "tracks": len(tracks),
            "artists": len(artists),
            "albums": len(albums),
        },
        "tracks": tracks,
    }

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    LIBRARY_CATALOG.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    _LIBRARY_CATALOG_CACHE = payload
    return payload


def refresh_library_catalog_after_download(download: dict[str, Any], manifest: dict[str, Any] | None = None) -> dict[str, Any]:
    """Reindexa a estante quando novos arquivos aparecem no disco."""
    added = int(download.get("downloaded_estimate") or 0)
    before = int(download.get("audio_files_before") or 0)
    after = int(download.get("audio_files_after") or 0)

    if added <= 0 and after <= before and manifest is None:
        return library_catalog_public_meta()

    if manifest is not None:
        return library_catalog_public_meta(rebuild_library_catalog(manifest))

    return library_catalog_public_meta(rebuild_library_catalog())


def load_library_catalog(refresh: bool = False) -> dict[str, Any]:
    global _LIBRARY_CATALOG_CACHE, _LIBRARY_CATALOG_REVISION

    if refresh:
        with _LIBRARY_REBUILD_LOCK:
            return rebuild_library_catalog()

    if _LIBRARY_CATALOG_CACHE is not None:
        return _LIBRARY_CATALOG_CACHE

    if LIBRARY_CATALOG.exists():
        try:
            loaded = json.loads(LIBRARY_CATALOG.read_text(encoding="utf-8"))
            file_revision = int(loaded.get("revision") or 0)
            if file_revision <= 0:
                _LIBRARY_CATALOG_REVISION = max(_LIBRARY_CATALOG_REVISION, 1)
                loaded["revision"] = _LIBRARY_CATALOG_REVISION
            else:
                _LIBRARY_CATALOG_REVISION = max(_LIBRARY_CATALOG_REVISION, file_revision)
            _LIBRARY_CATALOG_CACHE = loaded
            return _LIBRARY_CATALOG_CACHE
        except (json.JSONDecodeError, OSError):
            pass

    with _LIBRARY_REBUILD_LOCK:
        if _LIBRARY_CATALOG_CACHE is not None:
            return _LIBRARY_CATALOG_CACHE
        return rebuild_library_catalog()


def library_refresh_requested(query: dict[str, list[str]]) -> bool:
    flag = (query.get("refresh", [""])[0] or "").strip().lower()
    return flag in {"1", "true", "yes", "on"}


def find_catalog_track(
    catalog: dict[str, Any],
    spotify_id: str = "",
    title: str = "",
    artists: list[str] | None = None,
    isrc: str = "",
) -> dict[str, Any] | None:
    artists = artists or []
    target_keys = {
        track_dedup_key(spotify_id, isrc, title, artists),
    }
    if spotify_id:
        target_keys.add(f"spotify:{spotify_id}")
    if isrc:
        target_keys.add(f"isrc:{isrc}")

    for track in catalog.get("tracks") or []:
        if not isinstance(track, dict):
            continue

        track_keys = {
            track_dedup_key(
                str(track.get("spotify_id") or ""),
                str(track.get("isrc") or ""),
                str(track.get("title") or ""),
                track.get("artists") if isinstance(track.get("artists"), list) else [],
            )
        }
        if track_keys & target_keys:
            local_file = str(track.get("local_file") or "")
            if local_file and Path(local_file).exists():
                return track

    full_key = normalize_text(f"{' '.join(str(artist) for artist in artists)} {title}")
    title_key = normalize_text(title)
    for track in catalog.get("tracks") or []:
        track_artists = track.get("artists") if isinstance(track.get("artists"), list) else []
        track_full = normalize_text(f"{' '.join(str(artist) for artist in track_artists)} {track.get('title', '')}")
        if full_key and full_key == track_full:
            local_file = str(track.get("local_file") or "")
            if local_file and Path(local_file).exists():
                return track
        if title_key and title_key == normalize_text(str(track.get("title") or "")):
            local_file = str(track.get("local_file") or "")
            if local_file and Path(local_file).exists():
                return track

    return None


def find_track_in_catalog_by_id(catalog: dict[str, Any], track_id: str) -> dict[str, Any] | None:
    track_id = unquote(track_id).strip()
    for track in catalog.get("tracks") or []:
        if str(track.get("id") or "") == track_id:
            return track
        if track_id and str(track.get("spotify_id") or "") == track_id:
            return track
    return None


def filter_library_tracks(
    tracks: list[dict[str, Any]],
    *,
    query: str = "",
    artist: str = "",
    album: str = "",
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[dict[str, Any]], int]:
    query_key = normalize_text(query)
    artist_key = normalize_text(artist)
    album_key = normalize_text(album)

    filtered: list[dict[str, Any]] = []
    for track in tracks:
        track_artists = track.get("artists") if isinstance(track.get("artists"), list) else []
        artist_text = normalize_text(", ".join(str(item) for item in track_artists))
        title_text = normalize_text(str(track.get("title") or ""))
        album_text = normalize_text(str(track.get("album") or ""))
        haystack = normalize_text(f"{artist_text} {title_text} {album_text}")

        if artist_key and artist_key not in artist_text:
            continue
        if album_key and album_key not in album_text:
            continue
        if query_key and query_key not in haystack:
            continue

        filtered.append(track)

    total = len(filtered)
    start = max(offset, 0)
    end = start + max(min(limit, 200), 1)
    return filtered[start:end], total


def library_filters_from_catalog(catalog: dict[str, Any]) -> dict[str, list[str]]:
    artists: set[str] = set()
    albums: set[str] = set()

    for track in catalog.get("tracks") or []:
        for artist in track.get("artists") or []:
            if artist:
                artists.add(str(artist))
        album = str(track.get("album") or "").strip()
        if album:
            albums.add(album)

    return {
        "artists": sorted(artists, key=lambda value: normalize_text(value)),
        "albums": sorted(albums, key=lambda value: normalize_text(value)),
    }


def resolve_track_local_file(
    *,
    spotify_id: str,
    isrc: str,
    title: str,
    artists: list[str],
    catalog: dict[str, Any],
    by_full_key: dict[str, Path],
    by_title_key: dict[str, Path],
    download_dir_paths: dict[str, Path],
) -> tuple[str, str]:
    catalog_track = find_catalog_track(catalog, spotify_id, title, artists, isrc)
    if catalog_track:
        return str(catalog_track["local_file"]), "library_catalog_reuse"

    artist_text = " ".join(str(artist) for artist in artists)
    full_key = normalize_text(f"{artist_text} {title}")
    title_key = normalize_text(title)

    path = pick_preferred_path(
        by_full_key.get(full_key),
        by_title_key.get(title_key),
        download_dir_paths.get(full_key),
        download_dir_paths.get(title_key),
    )
    if path:
        if str(path).replace("\\", "/").lower().find("/managed/") >= 0:
            return str(path.resolve()), "managed_library_match"
        if catalog_track:
            return str(path.resolve()), "library_catalog_reuse"
        return str(path.resolve()), "local_library_rescan"

    return "", ""


def is_path_in_library(path: Path) -> bool:
    try:
        resolved = path.resolve()
        library_root = (PROJECT_ROOT / "library").resolve()
        resolved.relative_to(library_root)
        return True
    except ValueError:
        return False


def serve_file_with_range(handler: BaseHTTPRequestHandler, path: Path) -> None:
    size = path.stat().st_size
    suffix = path.suffix.lower()
    content_type = {
        ".mp3": "audio/mpeg",
        ".flac": "audio/flac",
        ".wav": "audio/wav",
        ".m4a": "audio/mp4",
        ".aac": "audio/aac",
        ".ogg": "audio/ogg",
        ".opus": "audio/opus",
        ".apk": "application/vnd.android.package-archive",
    }.get(suffix, "application/octet-stream")

    range_header = handler.headers.get("Range", "")
    if range_header.startswith("bytes="):
        range_spec = range_header.removeprefix("bytes=").split(",", 1)[0]
        start_text, _, end_text = range_spec.partition("-")
        try:
            start = int(start_text) if start_text else 0
            end = int(end_text) if end_text else size - 1
        except ValueError:
            start, end = 0, size - 1

        start = max(start, 0)
        end = min(end, size - 1)
        if start > end:
            handler.send_response(416)
            handler.end_headers()
            return

        length = end - start + 1
        handler.send_response(206)
        handler.send_header("Content-Type", content_type)
        handler.send_header("Accept-Ranges", "bytes")
        handler.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        handler.send_header("Content-Length", str(length))
        handler.send_header("Access-Control-Allow-Origin", "*")
        handler.send_header("Access-Control-Expose-Headers", "Content-Length, Content-Range, Accept-Ranges")
        handler.end_headers()

        with path.open("rb") as handle:
            handle.seek(start)
            handler.wfile.write(handle.read(length))
        return

    handler.send_response(200)
    handler.send_header("Content-Type", content_type)
    handler.send_header("Content-Length", str(size))
    handler.send_header("Accept-Ranges", "bytes")
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.send_header("Access-Control-Expose-Headers", "Content-Length, Content-Range, Accept-Ranges")
    handler.end_headers()

    with path.open("rb") as handle:
        shutil.copyfileobj(handle, handler.wfile)


def fetch_azuracast_requests(force_refresh: bool = False) -> list[dict[str, Any]]:
    global _AZURACAST_REQUESTS_CACHE

    if not resolve_azuracast_api_key():
        raise RuntimeError(
            "Configure RADIOPOGGERS_AZURACAST_API_KEY ou data/azuracast-api-key.txt "
            "(AzuraCast → My API Keys) para pedir musicas na radio."
        )

    station_id = get_station_id()
    if station_id is None:
        raise RuntimeError("Nao consegui identificar a estacao AzuraCast.")

    now = time.time()
    if (
        not force_refresh
        and _AZURACAST_REQUESTS_CACHE is not None
        and now - _AZURACAST_REQUESTS_CACHE[0] < 60
    ):
        return _AZURACAST_REQUESTS_CACHE[1]

    api_key = resolve_azuracast_api_key()
    request = Request(
        f"{AZURACAST_BASE_URL}/api/station/{station_id}/requests",
        headers={"Authorization": f"Bearer {api_key}"},
    )
    try:
        with urlopen(request, timeout=20) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        message = azuracast_http_error_message(error)
        if "does not currently accept requests" in message.lower():
            raise RuntimeError(
                "Pedidos desligados no AzuraCast. Ative Enable Song Requests na estacao RADIO NO GRALE."
            ) from error
        raise RuntimeError(message) from error

    requests_list = payload if isinstance(payload, list) else payload.get("data", [])
    if not isinstance(requests_list, list):
        requests_list = []

    _AZURACAST_REQUESTS_CACHE = (now, requests_list)
    return requests_list


def match_request_for_track(track: dict[str, Any], requests_list: list[dict[str, Any]]) -> dict[str, Any] | None:
    track_title = normalize_text(str(track.get("title") or ""))
    track_artists = normalize_text(", ".join(str(artist) for artist in track.get("artists") or []))
    track_full = normalize_text(f"{track_artists} {track_title}")

    best: dict[str, Any] | None = None
    best_score = 0

    for item in requests_list:
        if not isinstance(item, dict):
            continue

        song = item.get("song") if isinstance(item.get("song"), dict) else item
        title = normalize_text(str(song.get("title") or song.get("text") or ""))
        artist = normalize_text(str(song.get("artist") or ""))
        full = normalize_text(f"{artist} {title}")

        score = 0
        if track_full and track_full == full:
            score = 100
        elif track_title and track_title == title:
            if track_artists and artist and track_artists == artist:
                score = 95
            elif not track_artists or not artist:
                score = 70

        if score > best_score:
            best_score = score
            best = item

    return best if best_score >= 90 else None


def sql_escape(value: str) -> str:
    return (value or "").replace("\\", "\\\\").replace("'", "''")


def expected_azuracast_media_path(track: dict[str, Any]) -> str | None:
    local_file = Path(str(track.get("local_file") or ""))
    if not local_file.exists():
        return None
    return f"imported/{azuracast_media_filename(track, local_file)}"


def azuracast_container_has_media(relative_path: str) -> bool:
    if not relative_path or not shutil.which("docker"):
        return False
    safe_path = relative_path.lstrip("/")
    container_file = f"/var/azuracast/stations/{STATION_SHORTCODE}/media/{safe_path}"
    result = run_command(["docker", "exec", AZURACAST_CONTAINER, "test", "-f", container_file])
    return result.returncode == 0


def resolve_azuracast_media_path(track: dict[str, Any]) -> str | None:
    if not shutil.which("docker"):
        return None

    spotify_id = str(track.get("spotify_id") or track.get("id") or "").strip()
    local_file = Path(str(track.get("local_file") or ""))
    if spotify_id:
        result = run_azuracast_sql(
            "SELECT path FROM station_media "
            f"WHERE path LIKE 'imported/{sql_escape(spotify_id)}.%' "
            "ORDER BY id DESC LIMIT 1;"
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip().split("\t", 1)[0].strip()

    if local_file.exists():
        expected_name = azuracast_media_filename(track, local_file)
        result = run_azuracast_sql(
            "SELECT path FROM station_media "
            f"WHERE path = 'imported/{sql_escape(expected_name)}' "
            "LIMIT 1;"
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip().split("\t", 1)[0].strip()

    track_title = sql_escape(str(track.get("title") or "").strip())
    artists = track.get("artists") if isinstance(track.get("artists"), list) else []
    track_artist = sql_escape(", ".join(str(artist) for artist in artists if artist).strip())
    if not track_title:
        return None

    artist_clause = (
        f"AND LOWER(artist) = LOWER('{track_artist}') "
        if track_artist
        else ""
    )
    result = run_azuracast_sql(
        "SELECT path FROM station_media "
        f"WHERE path LIKE 'imported/%' "
        f"AND LOWER(title) = LOWER('{track_title}') {artist_clause}"
        "ORDER BY id DESC LIMIT 1;"
    )
    if result.returncode == 0 and result.stdout.strip():
        return result.stdout.strip().split("\t", 1)[0].strip()

    result = run_azuracast_sql(
        "SELECT path FROM station_media "
        f"WHERE path LIKE 'imported/%' "
        f"AND LOWER(title) = LOWER('{track_title}') "
        "ORDER BY id DESC LIMIT 1;"
    )
    if result.returncode == 0 and result.stdout.strip():
        return result.stdout.strip().split("\t", 1)[0].strip()

    for artist in artists:
        artist_name = sql_escape(str(artist or "").strip())
        if not artist_name:
            continue
        result = run_azuracast_sql(
            "SELECT path FROM station_media "
            f"WHERE path LIKE 'imported/%' "
            f"AND LOWER(title) = LOWER('{track_title}') "
            f"AND LOWER(artist) LIKE LOWER('%{artist_name}%') "
            "ORDER BY id DESC LIMIT 1;"
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip().split("\t", 1)[0].strip()

    expected = expected_azuracast_media_path(track)
    if expected and azuracast_container_has_media(expected):
        return expected

    return None


def play_track_immediately_on_radio(track: dict[str, Any]) -> dict[str, Any]:
    media_path = resolve_azuracast_media_path(track)
    sync_note = ""
    if not media_path:
        local_file = Path(str(track.get("local_file") or ""))
        if local_file.exists() and str(track.get("status") or "").lower() == "ready":
            sync_result = sync_track_to_azuracast(track)
            sync_note = str(sync_result.get("message") or "").strip()
            for _ in range(8):
                media_path = resolve_azuracast_media_path(track)
                if media_path:
                    break
                time.sleep(1.5)
    if not media_path:
        detail = (
            f"Faixa nao encontrada no AzuraCast: {track.get('title') or 'sem titulo'}. "
        )
        if sync_note:
            detail += f"Sincronizacao tentada: {sync_note} "
        detail += "Confira Docker/AzuraCast ou rode fix-azuracast-station."
        raise RuntimeError(detail)

    api_key = resolve_azuracast_api_key()
    if not api_key:
        raise RuntimeError(
            "Configure RADIOPOGGERS_AZURACAST_API_KEY ou data/azuracast-api-key.txt "
            "(AzuraCast → My API Keys) para tocar na radio."
        )

    station_id = get_station_id()
    if station_id is None:
        raise RuntimeError("Nao consegui identificar a estacao AzuraCast.")

    body = json.dumps({"do": "immediate", "files": [media_path]}, ensure_ascii=False).encode("utf-8")
    request = Request(
        f"{AZURACAST_BASE_URL}/api/station/{station_id}/files/batch",
        data=body,
        method="PUT",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )
    try:
        with urlopen(request, timeout=30) as response:
            raw = response.read().decode("utf-8")
            payload = json.loads(raw) if raw.strip() else {}
            if isinstance(payload, dict) and payload.get("success") is False:
                detail = str(payload.get("formatted_message") or payload.get("message") or "AzuraCast recusou tocar agora.")
                raise RuntimeError(detail)
            return {
                "ok": True,
                "media_path": media_path,
                "track_id": track.get("id"),
                "title": track.get("title"),
                "result": payload if isinstance(payload, dict) else {"ok": True},
                "message": f"Tocando ja: {track.get('title')}",
                "via": "files_batch_immediate",
            }
    except HTTPError as error:
        raise RuntimeError(azuracast_http_error_message(error)) from error


def submit_azuracast_request(request_id: str) -> dict[str, Any]:
    api_key = resolve_azuracast_api_key()
    if not api_key:
        raise RuntimeError(
            "Configure RADIOPOGGERS_AZURACAST_API_KEY ou data/azuracast-api-key.txt "
            "(AzuraCast → My API Keys) para pedir musicas na radio."
        )

    station_id = get_station_id()
    if station_id is None:
        raise RuntimeError("Nao consegui identificar a estacao AzuraCast.")

    request = Request(
        f"{AZURACAST_BASE_URL}/api/station/{station_id}/request/{quote(str(request_id), safe='')}",
        method="POST",
        headers={"Authorization": f"Bearer {api_key}"},
    )
    try:
        with urlopen(request, timeout=20) as response:
            raw = response.read().decode("utf-8")
            if not raw.strip():
                return {"ok": True}
            payload = json.loads(raw)
            if isinstance(payload, dict) and payload.get("success") is False:
                detail = str(payload.get("formatted_message") or payload.get("message") or "AzuraCast recusou o pedido.")
                raise RuntimeError(detail)
            return payload if isinstance(payload, dict) else {"ok": True}
    except HTTPError as error:
        message = azuracast_http_error_message(error)
        if "played too recently" in message.lower():
            raise RuntimeError(
                "AzuraCast bloqueou repeticao recente. Tente outra faixa ou reduza Request Threshold no painel."
            ) from error
        raise RuntimeError(message) from error


def request_track_on_radio(track: dict[str, Any]) -> dict[str, Any]:
    requests_list = fetch_azuracast_requests(force_refresh=True)
    matched = match_request_for_track(track, requests_list)
    if not matched:
        raise RuntimeError(
            "Faixa nao encontrada na fila de pedidos do AzuraCast. Sincronize a biblioteca com Tocar primeiro."
        )

    request_id = matched.get("request_id") or matched.get("id")
    if not request_id:
        raise RuntimeError("Pedido AzuraCast sem request_id.")

    result = submit_azuracast_request(str(request_id))
    return {
        "ok": True,
        "request_id": str(request_id),
        "track_id": track.get("id"),
        "title": track.get("title"),
        "result": result,
        "message": f"Pedido enviado: {track.get('title')}",
    }


def skip_current_track() -> dict[str, Any]:
    api_key = resolve_azuracast_api_key()
    if not api_key:
        return skip_current_track_via_docker()

    station_id = get_station_id()
    if station_id is None:
        raise RuntimeError("Nao consegui identificar a estacao AzuraCast.")

    request = Request(
        f"{AZURACAST_BASE_URL}/api/station/{station_id}/backend/skip",
        method="POST",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        },
        data=b"{}",
    )
    try:
        with urlopen(request, timeout=20) as response:
            raw = response.read().decode("utf-8")
            if not raw.strip():
                return {"ok": True, "message": "Faixa pulada."}
            payload = json.loads(raw)
            if isinstance(payload, dict) and payload.get("success") is False:
                detail = str(payload.get("formatted_message") or payload.get("message") or "AzuraCast recusou o skip.")
                raise RuntimeError(detail)
            return {
                "ok": True,
                "message": "Faixa pulada.",
                "result": payload if isinstance(payload, dict) else {"ok": True},
            }
    except HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        try:
            payload = json.loads(detail) if detail.strip() else {}
            message = str(payload.get("formatted_message") or payload.get("message") or detail).strip()
        except json.JSONDecodeError:
            message = detail.strip() or str(error)
        raise RuntimeError(f"AzuraCast recusou pular faixa ({error.code}): {message}") from error


_LIQUIDSOAP_DOCKER_CACHE: tuple[float, str, int] | None = None


def read_liquidsoap_docker_settings(force_refresh: bool = False) -> tuple[str, int]:
    global _LIQUIDSOAP_DOCKER_CACHE

    now = time.time()
    if (
        not force_refresh
        and _LIQUIDSOAP_DOCKER_CACHE is not None
        and now - _LIQUIDSOAP_DOCKER_CACHE[0] < 300
    ):
        return _LIQUIDSOAP_DOCKER_CACHE[1], _LIQUIDSOAP_DOCKER_CACHE[2]

    liq_path = f"/var/azuracast/stations/{STATION_SHORTCODE}/config/liquidsoap.liq"
    result = run_command(["docker", "exec", AZURACAST_CONTAINER, "cat", liq_path], timeout=30)
    if result.returncode != 0:
        return "", 8004

    text = result.stdout or ""
    key_match = re.search(
        r"settings\.azuracast\.api_key\s*:=\s*\{str_[^|]+\|([^|]+)\|",
        text,
    )
    port_match = re.search(r"settings\.azuracast\.liquidsoap_api_port\s*:=\s*(\d+)", text)
    adapter_key = key_match.group(1) if key_match else ""
    port = int(port_match.group(1)) if port_match else 8004
    _LIQUIDSOAP_DOCKER_CACHE = (now, adapter_key, port)
    return adapter_key, port


def skip_current_track_via_docker() -> dict[str, Any]:
    if not shutil.which("docker"):
        raise RuntimeError(
            "Configure RADIOPOGGERS_AZURACAST_API_KEY ou data/azuracast-api-key.txt "
            "(AzuraCast → My API Keys), ou instale Docker com o container azuracast rodando."
        )

    adapter_key, port = read_liquidsoap_docker_settings()
    if not adapter_key:
        raise RuntimeError(
            "Nao consegui ler a chave interna do Liquidsoap no Docker. "
            "Configure data/azuracast-api-key.txt ou reinicie o AzuraCast."
        )

    safe_key = adapter_key.replace("'", "'\\''")
    inner = (
        f"curl -s -f -X POST 'http://127.0.0.1:{port}/telnet' "
        f"-H 'x-liquidsoap-api-key: {safe_key}' -d 'radio.skip'"
    )
    result = run_command(
        ["docker", "exec", AZURACAST_CONTAINER, "bash", "-lc", inner],
        timeout=30,
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        raise RuntimeError(
            detail
            or "Liquidsoap recusou pular faixa (container azuracast parado?)."
        )

    body = (result.stdout or "").strip()
    return {
        "ok": True,
        "message": "Faixa pulada.",
        "via": "docker_liquidsoap",
        "result": body or "Done!",
    }


def first_ready_track_payload(manifest: dict[str, Any]) -> dict[str, Any] | None:
    items = manifest.get("items") if isinstance(manifest.get("items"), list) else []
    source = manifest.get("source") if isinstance(manifest.get("source"), dict) else {}
    playlist_title = str(source.get("title") or "Playlist").strip() or "Playlist"

    for item in items:
        if not isinstance(item, dict):
            continue
        if str(item.get("status") or "").lower() != "ready":
            continue
        track_id = resolve_track_id(item)
        if not track_id:
            continue
        artists = item.get("artists") if isinstance(item.get("artists"), list) else []
        return {
            "first_track_id": track_id,
            "track_id": track_id,
            "title": str(item.get("title") or "Nova faixa"),
            "artist": ", ".join(str(artist) for artist in artists if artist) or "Artista",
            "playlist_title": playlist_title,
        }
    return None


def load_cached_manifest_for_spotify_url(spotify_url: str) -> dict[str, Any] | None:
    try:
        kind, spotify_id = spotify_ref(spotify_url)
    except ValueError:
        return None

    if not DEFAULT_MANIFEST.exists():
        return None

    try:
        manifest = json.loads(DEFAULT_MANIFEST.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None

    if not isinstance(manifest, dict):
        return None

    source = manifest.get("source") if isinstance(manifest.get("source"), dict) else {}
    if str(source.get("kind") or "") != kind or str(source.get("id") or "") != spotify_id:
        return None

    return manifest


def spotify_import_is_cached_ready(spotify_url: str) -> bool:
    manifest = load_cached_manifest_for_spotify_url(spotify_url)
    if not manifest:
        return False

    summary = manifest.get("summary") if isinstance(manifest.get("summary"), dict) else {}
    return int(summary.get("ready") or 0) > 0


def build_skipped_download_payload(spotify_url: str, manifest: dict[str, Any]) -> dict[str, Any]:
    kind, spotify_id = spotify_ref(spotify_url)
    download_dir = SPOTDL_DOWNLOAD_ROOT / f"{kind}-{spotify_id}"
    download_dir.mkdir(parents=True, exist_ok=True)
    save_file = DATA_DIR / f"spotdl-{kind}-{spotify_id}.spotdl"
    errors_file = DATA_DIR / f"spotdl-{kind}-{spotify_id}-errors.json"
    after_files = audio_files_in(download_dir)
    summary = manifest.get("summary") if isinstance(manifest.get("summary"), dict) else {}
    ready = int(summary.get("ready") or 0)
    pending = int(summary.get("pending_local_audio") or 0)

    return {
        "attempted": False,
        "skipped": True,
        "already_imported": True,
        "ok": True,
        "directory": str(download_dir),
        "save_file": str(save_file),
        "errors_file": str(errors_file),
        "audio_files_before": len(after_files),
        "audio_files_after": len(after_files),
        "downloaded_estimate": 0,
        "reused_existing": ready,
        "needs_download": pending,
        "message": (
            f"Playlist ja importada: {ready} faixa(s) pronta(s)"
            + (f", {pending} pendente(s)." if pending else ".")
        ),
    }


def inspect_spotify_import(spotify_url: str) -> dict[str, Any]:
    safe_url = validate_spotify_url(spotify_url)
    manifest = load_cached_manifest_for_spotify_url(safe_url)
    summary = manifest.get("summary") if isinstance(manifest, dict) and isinstance(manifest.get("summary"), dict) else {}
    ready = int(summary.get("ready") or 0)
    pending = int(summary.get("pending_local_audio") or 0)
    source = manifest.get("source") if isinstance(manifest, dict) and isinstance(manifest.get("source"), dict) else {}

    return {
        "ok": True,
        "spotify_url": safe_url,
        "already_imported": ready > 0,
        "ready": ready,
        "pending": pending,
        "playlist_title": str(source.get("title") or "").strip(),
        "manifest": manifest,
        "vote_payload": first_ready_track_payload(manifest) if manifest else None,
    }


def execute_vote_action(
    vote_type: str,
    payload: dict[str, Any],
    choice: str,
    _vote_id: str = "",
) -> dict[str, Any]:
    safe_choice = str(choice or "").strip().lower()
    safe_payload = payload if isinstance(payload, dict) else {}

    if vote_type == "skip_track":
        if safe_choice == "yes":
            return skip_current_track()
        return {"ok": True, "message": "A galera decidiu: deixa rolar!"}

    if vote_type == "library_request":
        track_id = str(safe_payload.get("track_id") or safe_payload.get("trackId") or "").strip()
        if not track_id:
            raise RuntimeError("track_id ausente no pedido.")

        catalog = load_library_catalog(refresh=False)
        track = find_track_in_catalog_by_id(catalog, track_id)
        if not track:
            raise RuntimeError("Faixa nao encontrada no catalogo local.")

        if safe_choice == "yes":
            result = play_track_immediately_on_radio(track)
        else:
            result = request_track_on_radio(track)
            result["message"] = f"Entrou na fila: {track.get('title')}"
        return result

    if vote_type == "library_clear":
        if safe_choice == "yes":
            return {
                "ok": True,
                "clear_custom_playlist": True,
                "message": "Minha playlist zerada.",
            }
        return {"ok": True, "message": "A galera decidiu: playlist mantida."}

    if vote_type == "spotify_import":
        if safe_choice == "no":
            return {
                "ok": True,
                "message": "Playlist sincronizada. A faixa atual continua no ar.",
            }

        track_id = str(safe_payload.get("first_track_id") or safe_payload.get("track_id") or "").strip()
        if not track_id:
            raise RuntimeError("Primeira faixa da importacao nao informada.")

        catalog = load_library_catalog(refresh=False)
        track = find_track_in_catalog_by_id(catalog, track_id)
        if not track:
            raise RuntimeError("Primeira faixa da importacao nao encontrada no catalogo.")

        result = play_track_immediately_on_radio(track)
        result["message"] = f"Playlist no ar com {track.get('title')}!"
        return result

    raise RuntimeError(f"Tipo de votacao desconhecido: {vote_type}")



def resolve_skip_miku_moment(base_moment: str, proposer_id: str) -> str:
    return resolve_skip_narrator_moment(base_moment, proposer_id)


def announce_vote_outcome(moment: str, payload: dict[str, Any], _choice: str) -> None:
    if not miku_narrator_enabled() or not generate_miku_narration:
        return

    title = str(payload.get("title") or "").strip()
    artist = str(payload.get("artist") or "").strip()
    if not title or title.lower().startswith("aguardando"):
        title = ""
    if not artist or artist.lower().startswith("configure"):
        artist = ""

    if not title:
        title = "essa faixa"
    if not artist:
        artist = "artista desconhecido"

    _launch_miku_narration_job(
        title=title,
        artist=artist,
        album="",
        genre="rock",
        moment=moment,
    )


register_vote_executor(execute_vote_action)
register_miku_hook(announce_vote_outcome)


def voice_drop_extension(mime_type: str) -> str:
    normalized = (mime_type or "").lower().split(";", 1)[0].strip()
    mapping = {
        "audio/wav": ".wav",
        "audio/x-wav": ".wav",
        "audio/webm": ".webm",
        "audio/ogg": ".ogg",
        "audio/mpeg": ".mp3",
        "audio/mp4": ".m4a",
    }
    return mapping.get(normalized, ".wav")


def boost_listener_voice_drop_file(
    path: Path,
    listener_id: str,
    *,
    skip_heavy_boost: bool = False,
) -> None:
    """Deixa voice drops de ouvintes mais altos (Miku/Hoshino ja saem processados)."""
    lid = str(listener_id or "").strip()
    if lid in (MIKU_LISTENER_ID, HOSHINO_LISTENER_ID):
        return

    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg or not path.exists() or path.stat().st_size < 64:
        return

    tmp = path.with_name(f"{path.stem}.boost{path.suffix}")
    if skip_heavy_boost:
        audio_filter = "alimiter=limit=0.99"
    else:
        audio_filter = (
            "highpass=f=90,"
            "acompressor=threshold=-28dB:ratio=3:attack=5:release=180:makeup=14,"
            "volume=6.5,"
            "alimiter=limit=0.99"
        )
    cmd = [
        ffmpeg,
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-i",
        str(path),
        "-af",
        audio_filter,
        "-ar",
        "48000",
        "-ac",
        "1",
        str(tmp),
    ]
    try:
        subprocess.run(cmd, check=True, capture_output=True, timeout=45)
        tmp.replace(path)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError) as error:
        print(f"[voice-drop] boost falhou ({path.name}): {error}")
        if tmp.exists():
            tmp.unlink(missing_ok=True)


def register_voice_drop(
    *,
    drop_id: str,
    path: Path,
    duration_ms: int,
    listener_id: str,
    mime_type: str,
    max_duration_ms: int | None = None,
    caption: str = "",
) -> dict[str, Any]:
    global _ACTIVE_VOICE_DROP

    cap_ms = max_duration_ms if max_duration_ms is not None else (VOICE_DROP_MAX_SECONDS * 1000)
    duration_ms = max(min(int(duration_ms), cap_ms), 500)
    expires_at = time.time() + max(
        (duration_ms / 1000.0) + VOICE_DROP_DELIVERY_GRACE_SEC,
        VOICE_DROP_DELIVERY_GRACE_SEC,
    )

    payload = {
        "id": drop_id,
        "listener_id": listener_id,
        "url": f"/api/voice-drop/file/{drop_id}",
        "mime_type": mime_type or "audio/wav",
        "duration_ms": duration_ms,
        "started_at": int(time.time()),
        "expires_at": int(expires_at),
        "caption": str(caption or "").strip(),
    }

    with _VOICE_DROP_LOCK:
        _ACTIVE_VOICE_DROP = payload

    return payload


def get_active_voice_drop() -> dict[str, Any] | None:
    global _ACTIVE_VOICE_DROP

    with _VOICE_DROP_LOCK:
        if not _ACTIVE_VOICE_DROP:
            return None

        if time.time() >= float(_ACTIVE_VOICE_DROP.get("expires_at") or 0):
            _ACTIVE_VOICE_DROP = None
            return None

        return dict(_ACTIVE_VOICE_DROP)


def voice_drop_file_path(drop_id: str) -> Path | None:
    safe_id = re.sub(r"[^A-Za-z0-9_-]+", "", drop_id).strip()
    if not safe_id:
        return None

    for path in VOICE_DROPS_DIR.glob(f"{safe_id}.*"):
        if path.is_file():
            return path.resolve()

    return None


def is_path_in_voice_drops(path: Path) -> bool:
    try:
        path.resolve().relative_to(VOICE_DROPS_DIR.resolve())
        return True
    except ValueError:
        return False


def persist_voice_drop_bytes(
    raw: bytes,
    *,
    duration_ms: int,
    listener_id: str,
    mime_type: str,
    max_seconds: int | None = None,
    caption: str = "",
    register_active: bool = True,
    skip_server_boost: bool = False,
) -> dict[str, Any]:
    if not raw:
        raise ValueError("Audio vazio.")

    if len(raw) > VOICE_DROP_MAX_BYTES:
        raise ValueError(f"Audio excede {VOICE_DROP_MAX_BYTES // (1024 * 1024)} MB.")

    VOICE_DROPS_DIR.mkdir(parents=True, exist_ok=True)

    cap_seconds = max_seconds if max_seconds is not None else VOICE_DROP_MAX_SECONDS
    duration_ms = int(duration_ms or 0)
    if duration_ms <= 0:
        duration_ms = cap_seconds * 1000
    duration_ms = min(duration_ms, cap_seconds * 1000)

    listener_id = listener_id.strip() or secrets.token_hex(8)
    mime_type = (mime_type or "audio/wav").strip()
    drop_id = secrets.token_hex(8)
    path = VOICE_DROPS_DIR / f"{drop_id}{voice_drop_extension(mime_type)}"
    path.write_bytes(raw)
    boost_listener_voice_drop_file(path, listener_id, skip_heavy_boost=skip_server_boost)

    expires_at = time.time() + max(
        (duration_ms / 1000.0) + VOICE_DROP_DELIVERY_GRACE_SEC,
        VOICE_DROP_DELIVERY_GRACE_SEC,
    )
    drop_payload = {
        "id": drop_id,
        "listener_id": listener_id,
        "url": f"/api/voice-drop/file/{drop_id}",
        "mime_type": mime_type or "audio/wav",
        "duration_ms": duration_ms,
        "started_at": int(time.time()),
        "expires_at": int(expires_at),
        "caption": str(caption or "").strip(),
    }

    if register_active:
        active = register_voice_drop(
            drop_id=drop_id,
            path=path,
            duration_ms=duration_ms,
            listener_id=listener_id,
            mime_type=mime_type,
            max_duration_ms=cap_seconds * 1000,
            caption=caption,
        )
        drop_payload = active

    return {
        "ok": True,
        "voice_drop": drop_payload,
        "message": "Chamada enviada para a radio." if register_active else "Locucao pronta.",
    }


def save_voice_drop(payload: dict[str, Any]) -> dict[str, Any]:
    audio_base64 = str(payload.get("audioBase64") or payload.get("audio_base64") or "").strip()
    if not audio_base64:
        raise ValueError("Envie audioBase64 com o audio gravado.")

    if "," in audio_base64 and audio_base64.lower().startswith("data:"):
        audio_base64 = audio_base64.split(",", 1)[1]

    try:
        raw = base64.b64decode(audio_base64, validate=True)
    except ValueError as error:
        raise ValueError("audioBase64 invalido.") from error

    duration_ms = int(payload.get("durationMs") or payload.get("duration_ms") or 0)
    listener_id = str(payload.get("listenerId") or payload.get("listener_id") or "").strip()
    mime_type = str(payload.get("mimeType") or payload.get("mime_type") or "audio/wav").strip()

    return persist_voice_drop_bytes(
        raw,
        duration_ms=duration_ms,
        listener_id=listener_id,
        mime_type=mime_type,
    )


def save_voice_drop_request(handler: BaseHTTPRequestHandler) -> dict[str, Any]:
    content_type = (handler.headers.get("Content-Type") or "").lower().split(";", 1)[0].strip()

    if content_type in {"audio/wav", "audio/x-wav", "audio/webm", "audio/ogg", "application/octet-stream"}:
        raw = read_binary_body(handler)
        duration_ms = int(handler.headers.get("X-Duration-Ms") or handler.headers.get("X-Duration-ms") or 0)
        listener_id = str(handler.headers.get("X-Listener-Id") or handler.headers.get("X-Listener-id") or "").strip()
        client_radio = str(
            handler.headers.get("X-Client-Radio-Processed")
            or handler.headers.get("X-Client-Radio-processed")
            or ""
        ).strip().lower()
        skip_boost = client_radio in {"1", "true", "yes"}
        return persist_voice_drop_bytes(
            raw,
            duration_ms=duration_ms,
            listener_id=listener_id,
            mime_type=content_type or "audio/wav",
            skip_server_boost=skip_boost,
        )

    payload = read_json_body(handler)
    return save_voice_drop(payload)


def miku_narrator_enabled() -> bool:
    return os.environ.get("RADIOPOGGERS_MIKU_NARRATOR", "1").strip().lower() not in {"0", "false", "no", "off"}


def clear_miku_voice_drop() -> None:
    global _ACTIVE_VOICE_DROP

    with _VOICE_DROP_LOCK:
        if _ACTIVE_VOICE_DROP and _ACTIVE_VOICE_DROP.get("listener_id") == MIKU_LISTENER_ID:
            _ACTIVE_VOICE_DROP = None


def _voice_drop_register_active(payload: dict[str, Any], *, default: bool = True) -> bool:
    if payload.get("preview") or payload.get("preview_only") or payload.get("previewOnly"):
        return False
    raw = payload.get("register_active", payload.get("registerActive", default))
    if isinstance(raw, str):
        return raw.strip().lower() not in {"0", "false", "no", "off"}
    if raw is None:
        return default
    return bool(raw)


def save_miku_narration(payload: dict[str, Any]) -> dict[str, Any]:
    if not generate_miku_narration:
        raise RuntimeError("Modulo miku_narrator indisponivel.")

    title = str(payload.get("title") or "").strip()
    artist = str(payload.get("artist") or "").strip()
    album = str(payload.get("album") or "").strip()
    genre = str(payload.get("genre") or "").strip()
    backend = str(payload.get("backend") or payload.get("tts") or "").strip()

    if not title:
        raise ValueError("Informe title da faixa.")

    result = generate_miku_narration(
        title=title,
        artist=artist or "Artista desconhecido",
        album=album,
        genre=genre,
        backend=backend,
        moment=str(payload.get("moment") or "track_change").strip(),
    )

    saved = persist_voice_drop_bytes(
        result["audio"],
        duration_ms=int(result["duration_ms"]),
        listener_id=MIKU_LISTENER_ID,
        mime_type=str(result["mime_type"]),
        max_seconds=MIKU_MAX_SECONDS,
        caption=str(result.get("text") or ""),
        register_active=_voice_drop_register_active(payload, default=True),
    )

    saved["miku"] = {
        "text": result["text"],
        "backend": result["backend"],
        "listener_id": MIKU_LISTENER_ID,
        "moment": result.get("moment", "track_change"),
    }
    return saved


def hoshino_narrator_enabled() -> bool:
    return os.environ.get("RADIOPOGGERS_HOSHINO_NARRATOR", "1").strip().lower() not in {
        "0",
        "false",
        "no",
        "off",
    }


def save_hoshino_narration(payload: dict[str, Any]) -> dict[str, Any]:
    if not generate_hoshino_narration:
        raise RuntimeError("Modulo hoshino_narrator indisponivel.")
    if not hoshino_narrator_enabled():
        raise RuntimeError("Narradora Hoshino desligada no servidor.")

    title = str(payload.get("title") or "").strip()
    artist = str(payload.get("artist") or "").strip()
    album = str(payload.get("album") or "").strip()
    genre = str(payload.get("genre") or "").strip()
    voice = str(payload.get("voice") or "").strip()
    style_prompt = str(payload.get("style_prompt") or payload.get("stylePrompt") or "").strip()

    if not title:
        raise ValueError("Informe title da faixa.")

    result = generate_hoshino_narration(
        title=title,
        artist=artist or "Artista desconhecido",
        album=album,
        genre=genre,
        moment=str(payload.get("moment") or "track_change").strip(),
        voice=voice,
        style_prompt=style_prompt,
    )

    saved = persist_voice_drop_bytes(
        result["audio"],
        duration_ms=int(result["duration_ms"]),
        listener_id=HOSHINO_LISTENER_ID,
        mime_type=str(result["mime_type"]),
        max_seconds=HOSHINO_MAX_SECONDS,
        caption=str(result.get("text") or ""),
        register_active=False,
    )

    saved["hoshino"] = {
        "text": result["text"],
        "backend": result["backend"],
        "listener_id": HOSHINO_LISTENER_ID,
        "moment": result.get("moment", "track_change"),
        "model": result.get("model", ""),
        "voice": result.get("voice", ""),
    }
    return saved


def get_narrator_hints() -> dict[str, Any]:
    with _MIKU_GENERATION_LOCK:
        return {
            "track_key": _MIKU_TRACK_KEY,
            "mid_will_speak": _MIKU_MID_WILL_SPEAK,
            "mid_moment": _MIKU_MID_MOMENT,
            "mid_target_ratio": _MIKU_MID_TARGET_RATIO,
            "track_change_delay_sec": MIKU_TRACK_CHANGE_DELAY_SEC,
            "mid_min_track_seconds": MIKU_MIN_TRACK_SECONDS,
            "mid_cooldown_sec": MIKU_MID_COOLDOWN_SEC,
        }


def _miku_voice_drop_blocks_narration() -> bool:
    active = get_active_voice_drop()
    if not active:
        return False
    return active.get("listener_id") != MIKU_LISTENER_ID


def _launch_miku_narration_job(
    *,
    title: str,
    artist: str,
    album: str,
    genre: str,
    moment: str,
) -> bool:
    global _MIKU_GENERATION_BUSY, _MIKU_LAST_SPOKE_AT

    with _MIKU_GENERATION_LOCK:
        if _MIKU_GENERATION_BUSY:
            return False
        _MIKU_GENERATION_BUSY = True

    if moment == "track_change":
        clear_miku_voice_drop()
    elif _miku_voice_drop_blocks_narration():
        with _MIKU_GENERATION_LOCK:
            _MIKU_GENERATION_BUSY = False
        return False

    def job() -> None:
        global _MIKU_GENERATION_BUSY, _MIKU_LAST_SPOKE_AT
        try:
            result = generate_miku_narration(
                title=title,
                artist=artist or "Artista desconhecido",
                album=album,
                genre=genre,
                moment=moment,
            )
            saved = persist_voice_drop_bytes(
                result["audio"],
                duration_ms=int(result["duration_ms"]),
                listener_id=MIKU_LISTENER_ID,
                mime_type=str(result["mime_type"]),
                max_seconds=MIKU_MAX_SECONDS,
                caption=str(result.get("text") or ""),
            )
            _MIKU_LAST_SPOKE_AT = time.time()
            print(f"[Miku/{moment}] {result['text']} ({result['backend']})")
            if saved.get("voice_drop"):
                print(f"[Miku] drop {saved['voice_drop'].get('id')}")
        except Exception as error:
            print(f"[Miku] erro ao narrar ({moment}): {error}")
        finally:
            with _MIKU_GENERATION_LOCK:
                _MIKU_GENERATION_BUSY = False

    threading.Thread(target=job, daemon=True, name=f"miku-{moment}").start()
    return True


def _cancel_miku_track_change_timer() -> None:
    global _MIKU_TRACK_CHANGE_TIMER

    with _MIKU_TRACK_CHANGE_TIMER_LOCK:
        if _MIKU_TRACK_CHANGE_TIMER is not None:
            _MIKU_TRACK_CHANGE_TIMER.cancel()
            _MIKU_TRACK_CHANGE_TIMER = None


def miku_should_defer_for_active_vote() -> bool:
    vote = get_active_vote_public()
    if not vote:
        return False
    phase = str(vote.get("phase") or "").strip().lower()
    return phase not in {"", "closed"}


def _schedule_miku_track_change_narration(
    *,
    track_key: str,
    title: str,
    artist: str,
    album: str,
    genre: str,
) -> None:
    global _MIKU_TRACK_CHANGE_TIMER

    delay = max(float(MIKU_TRACK_CHANGE_DELAY_SEC), 0.0)
    _cancel_miku_track_change_timer()

    def fire() -> None:
        global _MIKU_TRACK_CHANGE_TIMER

        with _MIKU_TRACK_CHANGE_TIMER_LOCK:
            _MIKU_TRACK_CHANGE_TIMER = None

        with _MIKU_GENERATION_LOCK:
            if track_key != _MIKU_TRACK_KEY:
                return
            if miku_should_defer_for_active_vote():
                return

        _launch_miku_narration_job(
            title=title,
            artist=artist,
            album=album,
            genre=genre,
            moment="track_change",
        )

    if delay <= 0:
        fire()
        return

    timer = threading.Timer(delay, fire)
    timer.daemon = True
    with _MIKU_TRACK_CHANGE_TIMER_LOCK:
        _MIKU_TRACK_CHANGE_TIMER = timer
    timer.start()


def maybe_schedule_miku_narration(data: dict[str, Any]) -> None:
    global _MIKU_TRACK_KEY, _MIKU_MID_SPOKE, _MIKU_MID_WILL_SPEAK, _MIKU_MID_MOMENT, _MIKU_MID_TARGET_RATIO

    if not miku_narrator_enabled() or not build_track_key or not generate_miku_narration:
        return

    live = data.get("live") if isinstance(data.get("live"), dict) else {}
    if live.get("is_live"):
        return

    if miku_should_defer_for_active_vote():
        return

    now_playing = data.get("now_playing") if isinstance(data.get("now_playing"), dict) else {}
    song = now_playing.get("song") if isinstance(now_playing.get("song"), dict) else {}
    title = str(song.get("title") or song.get("text") or "").strip()
    artist = str(song.get("artist") or "").strip()
    if not title:
        return

    track_key = build_track_key(
        title,
        artist,
        str(now_playing.get("sh_id") or ""),
        str(song.get("id") or ""),
        str(now_playing.get("played_at") or ""),
    )
    album = str(song.get("album") or "")
    genre = str(song.get("genre") or "")

    try:
        elapsed = max(int(now_playing.get("elapsed") or 0), 0)
        duration = max(int(now_playing.get("duration") or song.get("length") or 0), 0)
    except (TypeError, ValueError):
        elapsed = 0
        duration = 0

    moment = ""
    with _MIKU_GENERATION_LOCK:
        if track_key != _MIKU_TRACK_KEY:
            previous = _MIKU_TRACK_KEY
            _MIKU_TRACK_KEY = track_key
            _MIKU_MID_SPOKE = False
            _MIKU_MID_WILL_SPEAK = random.random() < MIKU_MID_TRACK_CHANCE
            _MIKU_MID_MOMENT = pick_mid_break_moment() if _MIKU_MID_WILL_SPEAK else "mid_track"
            _MIKU_MID_TARGET_RATIO = random.uniform(0.32, 0.68)
            if previous:
                moment = "track_change"
        elif (
            not _MIKU_GENERATION_BUSY
            and _MIKU_MID_WILL_SPEAK
            and not _MIKU_MID_SPOKE
            and duration >= MIKU_MIN_TRACK_SECONDS
            and (time.time() - _MIKU_LAST_SPOKE_AT) >= MIKU_MID_COOLDOWN_SEC
            and duration > 0
            and (elapsed / duration) >= _MIKU_MID_TARGET_RATIO
        ):
            _MIKU_MID_SPOKE = True
            moment = _MIKU_MID_MOMENT or "mid_track"

    if not moment:
        return

    if moment == "track_change":
        _schedule_miku_track_change_narration(
            track_key=track_key,
            title=title,
            artist=artist,
            album=album,
            genre=genre,
        )
        return

    with _MIKU_GENERATION_LOCK:
        if _MIKU_GENERATION_BUSY:
            return

    _launch_miku_narration_job(
        title=title,
        artist=artist,
        album=album,
        genre=genre,
        moment=moment,
    )


def build_download_manifest(spotify_url: str, download: dict[str, Any]) -> dict[str, Any]:
    download_dir = Path(download["directory"])
    download_files = audio_files_in(download_dir)
    kind, spotify_id = spotify_ref(spotify_url)
    spotdl_songs = load_spotdl_songs(Path(download.get("save_file", "")))
    items: list[dict[str, Any]] = []
    matched_files: set[Path] = set()
    catalog = load_library_catalog(refresh=True)
    all_files = collect_all_library_files([download_dir])
    by_full_key, by_title_key = downloaded_file_index(all_files)
    download_by_full, download_by_title = downloaded_file_index(download_files)
    download_dir_paths = {**download_by_full, **download_by_title}
    scan_paths = default_library_scan_paths()
    if download_dir not in scan_paths:
        scan_paths.append(download_dir)

    for index, song in enumerate(spotdl_songs, start=1):
        title = str(song.get("name") or song.get("title") or f"Faixa {index}")
        artists = song.get("artists") if isinstance(song.get("artists"), list) else []
        if not artists and song.get("artist"):
            artists = [str(song["artist"])]

        local_file, match_reason = resolve_track_local_file(
            spotify_id=str(song.get("song_id") or ""),
            isrc=str(song.get("isrc") or ""),
            title=title,
            artists=[str(artist) for artist in artists],
            catalog=catalog,
            by_full_key=by_full_key,
            by_title_key=by_title_key,
            download_dir_paths=download_dir_paths,
        )

        path = Path(local_file) if local_file else None
        if path:
            matched_files.add(path)

        items.append({
            "spotify_id": song.get("song_id", ""),
            "isrc": song.get("isrc", ""),
            "spotify_url": song.get("url", ""),
            "title": title,
            "artists": artists,
            "album": song.get("album_name", ""),
            "duration_ms": int(song.get("duration") or 0) * 1000,
            "track_number": int(song.get("track_number") or 0),
            "disc_number": int(song.get("disc_number") or 0),
            "cover_url": song.get("cover_url", ""),
            "local_file": local_file,
            "status": "ready" if local_file else "pending_local_audio",
            "match": {
                "score": 100,
                "reason": match_reason or "spotdl_downloaded_file",
                "source_file": local_file,
                "sha256": "",
            } if local_file else None,
            "playlist_position": int(song.get("list_position") or index),
        })

    if not spotdl_songs:
        for index, path in enumerate(download_files, start=1):
            artists, title = parse_downloaded_filename(path)
            local_file, match_reason = resolve_track_local_file(
                spotify_id="",
                isrc="",
                title=title,
                artists=artists,
                catalog=catalog,
                by_full_key=by_full_key,
                by_title_key=by_title_key,
                download_dir_paths=download_dir_paths,
            )
            resolved = local_file or str(path.resolve())
            items.append({
                "spotify_id": "",
                "isrc": "",
                "spotify_url": "",
                "title": title,
                "artists": artists,
                "album": "",
                "duration_ms": 0,
                "track_number": index,
                "disc_number": 0,
                "cover_url": "",
                "local_file": resolved,
                "status": "ready",
                "match": {
                    "score": 100,
                    "reason": match_reason or "spotdl_downloaded_file",
                    "source_file": resolved,
                    "sha256": "",
                },
                "playlist_position": index,
            })
            matched_files.add(Path(resolved))

    for path in download_files:
        if path in matched_files:
            continue

        if any(item.get("local_file") == str(path.resolve()) for item in items):
            continue

        artists, title = parse_downloaded_filename(path)
        items.append({
            "spotify_id": "",
            "isrc": "",
            "spotify_url": "",
            "title": title,
            "artists": artists,
            "album": "",
            "duration_ms": 0,
            "track_number": len(items) + 1,
            "disc_number": 0,
            "cover_url": "",
            "local_file": str(path.resolve()),
            "status": "ready",
            "match": {
                "score": 100,
                "reason": "spotdl_extra_downloaded_file",
                "source_file": str(path.resolve()),
                "sha256": "",
            },
            "playlist_position": len(items) + 1,
        })

    ready_count = sum(1 for item in items if item.get("status") == "ready")
    pending_count = sum(1 for item in items if item.get("status") == "pending_local_audio")

    manifest = {
        "source": {
            "kind": kind,
            "id": spotify_id,
            "input": spotify_url,
            "title": spotdl_songs[0].get("list_name", "") if spotdl_songs else f"Downloads spotdl {kind}-{spotify_id}",
        },
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "notice": "Audio baixado via spotdl para a biblioteca local. Use apenas conteudo que voce tem direito de transmitir.",
        "library": {
            "scanned_paths": [str(path) for path in scan_paths],
            "audio_files_found": len(all_files),
            "duplicate_files": [],
        },
        "summary": {
            "spotify_items": len(spotdl_songs) or len(items),
            "unique_items": len(items),
            "ready": ready_count,
            "pending_local_audio": pending_count,
            "duplicate_spotify_items": 0,
        },
        "items": items,
        "duplicate_spotify_items": [],
    }

    DEFAULT_MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    write_m3u_from_items(DEFAULT_M3U, items)
    return manifest


def import_spotify_metadata(spotify_url: str) -> dict[str, Any]:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    LIBRARY_INBOX.mkdir(parents=True, exist_ok=True)
    LIBRARY_MANAGED.mkdir(parents=True, exist_ok=True)

    command = [
        sys.executable,
        str(SPOTIFY_TOOL),
        spotify_url,
        "--library",
        str(LIBRARY_INBOX),
        "--library",
        str(LIBRARY_MANAGED),
        "--organize-to",
        str(LIBRARY_MANAGED),
        "--out",
        str(DEFAULT_MANIFEST),
        "--m3u",
        str(DEFAULT_M3U),
    ]

    result = run_command(command)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or "Falha ao importar playlist.")

    return json.loads(DEFAULT_MANIFEST.read_text(encoding="utf-8"))


def safe_container_name(path: Path) -> str:
    name = re.sub(r"[^A-Za-z0-9._-]+", "_", path.name).strip("_")
    return name or f"track_{int(time.time())}{path.suffix.lower()}"


def azuracast_media_filename(item: dict[str, Any], source: Path) -> str:
    spotify_id = str(item.get("spotify_id") or "").strip()
    if spotify_id:
        return f"{spotify_id}{source.suffix.lower()}"
    return safe_container_name(source)


def sync_ready_tracks_to_azuracast(manifest: dict[str, Any], *, full_refresh: bool = True) -> dict[str, Any]:
    ready_items = [
        item for item in manifest.get("items", [])
        if item.get("status") == "ready" and item.get("local_file")
    ]

    if not ready_items:
        return {
            "attempted": False,
            "synced": 0,
            "message": "Nenhum arquivo local encontrado para sincronizar com o AzuraCast.",
        }

    if not shutil.which("docker"):
        return {
            "attempted": False,
            "synced": 0,
            "message": "Docker nao encontrado no PATH do Windows.",
        }

    container_dir = f"/var/azuracast/stations/{STATION_SHORTCODE}/media/imported"
    mkdir_result = run_command([
        "docker",
        "exec",
        AZURACAST_CONTAINER,
        "bash",
        "-lc",
        f"mkdir -p '{container_dir}'",
    ])
    if mkdir_result.returncode != 0:
        return {
            "attempted": True,
            "synced": 0,
            "message": mkdir_result.stderr.strip() or "Nao consegui preparar a pasta no AzuraCast.",
        }

    synced = 0
    skipped = 0
    errors: list[str] = []
    seen_keys: set[str] = set()

    for item in ready_items:
        source = Path(item["local_file"])
        if not source.exists():
            errors.append(f"Arquivo nao encontrado: {source}")
            continue

        dedup_key = track_dedup_key(
            str(item.get("spotify_id") or ""),
            str(item.get("isrc") or ""),
            str(item.get("title") or ""),
            item.get("artists") if isinstance(item.get("artists"), list) else [],
        )
        if dedup_key in seen_keys:
            skipped += 1
            continue
        seen_keys.add(dedup_key)

        target_name = azuracast_media_filename(item, source)
        target = f"{AZURACAST_CONTAINER}:{container_dir}/{target_name}"
        copy_result = run_command(["docker", "cp", str(source), target])
        if copy_result.returncode == 0:
            synced += 1
        else:
            errors.append(copy_result.stderr.strip() or f"Falha ao copiar {source.name}")

    refresh_script = (
        "set -e; "
        f"chown -R azuracast:azuracast /var/azuracast/stations/{STATION_SHORTCODE}/media; "
        "cd /var/azuracast/www; "
        "php backend/bin/console azuracast:sync:task check_media --force; "
        f"php backend/bin/console azuracast:media:reprocess {STATION_SHORTCODE}; "
    )
    if full_refresh:
        refresh_script += (
            "php backend/bin/console azuracast:sync:run; "
            "mariadb -h localhost -u $MYSQL_USER -p$MYSQL_PASSWORD $MYSQL_DATABASE "
            "-e \"DELETE FROM station_playlist_media "
            "WHERE playlist_id=1 AND media_id IN (SELECT id FROM station_media WHERE path NOT LIKE 'imported/%'); "
            "INSERT INTO station_playlist_media (playlist_id, media_id, weight, last_played, is_queued, folder_id) "
            "SELECT 1, sm.id, 1, 0, 0, NULL FROM station_media sm "
            "WHERE sm.path LIKE 'imported/%' "
            "AND NOT EXISTS (SELECT 1 FROM station_playlist_media spm WHERE spm.playlist_id=1 AND spm.media_id=sm.id); "
            "UPDATE station_playlists SET avoid_duplicates = 0 WHERE id = 1 AND avoid_duplicates = 1; "
            "\"; "
            "php backend/bin/console azuracast:station-queues:clear; "
            "php backend/bin/console azuracast:sync:run; "
            f"php backend/bin/console azuracast:sync:nowplaying:station {STATION_SHORTCODE}; "
            f"php backend/bin/console azuracast:radio:restart {STATION_SHORTCODE}"
        )
    refresh_result = run_command([
        "docker",
        "exec",
        AZURACAST_CONTAINER,
        "bash",
        "-lc",
        refresh_script,
    ], timeout=120)

    if refresh_result.returncode != 0:
        errors.append(refresh_result.stderr.strip() or refresh_result.stdout.strip() or "Falha ao atualizar AzuraCast.")

    return {
        "attempted": True,
        "synced": synced,
        "skipped_duplicates": skipped,
        "errors": errors,
        "message": (
            f"{synced} arquivo(s) sincronizado(s) com o AzuraCast."
            + (f" {skipped} duplicata(s) ignorada(s)." if skipped else "")
        ),
    }


def sync_track_to_azuracast(track: dict[str, Any]) -> dict[str, Any]:
    item = dict(track)
    local_file = Path(str(item.get("local_file") or ""))
    if not local_file.exists():
        return {
            "attempted": False,
            "synced": 0,
            "message": f"Arquivo local ausente: {local_file.name or local_file}",
        }
    if str(item.get("status") or "").lower() != "ready":
        item["status"] = "ready"
    return sync_ready_tracks_to_azuracast({"items": [item]}, full_refresh=False)


def load_manifest(refresh_local: bool = True) -> dict[str, Any]:
    manifest: dict[str, Any] | None = None

    if DEFAULT_MANIFEST.exists():
        manifest = json.loads(DEFAULT_MANIFEST.read_text(encoding="utf-8"))
    else:
        fallback = DATA_DIR / "spotify-linkin-park.json"
        if fallback.exists():
            manifest = json.loads(fallback.read_text(encoding="utf-8"))

    if manifest is None:
        return {
            "source": {"title": "Nenhuma playlist importada"},
            "summary": {"ready": 0, "pending_local_audio": 0},
            "items": [],
        }

    if refresh_local:
        return refresh_manifest_local_files(manifest)

    return manifest


def manifest_library_scan_paths(manifest: dict[str, Any]) -> list[Path]:
    paths: list[Path] = []
    seen: set[str] = set()

    for raw_path in manifest.get("library", {}).get("scanned_paths", []):
        path = Path(str(raw_path))
        key = str(path.resolve()) if path.exists() else str(path)
        if key not in seen:
            seen.add(key)
            paths.append(path)

    for path in (LIBRARY_MANAGED, LIBRARY_INBOX, SPOTDL_DOWNLOAD_ROOT):
        key = str(path.resolve()) if path.exists() else str(path)
        if key not in seen:
            seen.add(key)
            paths.append(path)

    return paths


def refresh_manifest_local_files(manifest: dict[str, Any]) -> dict[str, Any]:
    items = manifest.get("items")
    if not isinstance(items, list) or not items:
        return manifest

    files: list[Path] = []
    seen_files: set[str] = set()
    for root in manifest_library_scan_paths(manifest):
        for path in audio_files_in(root):
            resolved = str(path.resolve())
            if resolved not in seen_files:
                seen_files.add(resolved)
                files.append(path)

    by_full_key, by_title_key = downloaded_file_index(files)
    updated_items: list[dict[str, Any]] = []
    changed = False

    for item in items:
        if not isinstance(item, dict):
            updated_items.append(item)
            continue

        updated = dict(item)
        local_file = str(updated.get("local_file") or "")
        if updated.get("status") == "ready" and local_file and Path(local_file).exists():
            updated_items.append(updated)
            continue

        artists = updated.get("artists") if isinstance(updated.get("artists"), list) else []
        artist_text = " ".join(str(artist) for artist in artists)
        title = str(updated.get("title") or "")
        full_key = normalize_text(f"{artist_text} {title}")
        title_key = normalize_text(title)
        path = by_full_key.get(full_key) or by_title_key.get(title_key)

        if path:
            updated["local_file"] = str(path.resolve())
            updated["status"] = "ready"
            updated["match"] = {
                "score": 100,
                "reason": "local_library_rescan",
                "source_file": str(path.resolve()),
                "sha256": "",
            }
            changed = True

        updated_items.append(updated)

    if not changed:
        return manifest

    ready_count = sum(1 for item in updated_items if item.get("status") == "ready")
    pending_count = sum(1 for item in updated_items if item.get("status") == "pending_local_audio")
    refreshed = dict(manifest)
    refreshed["items"] = updated_items
    refreshed["generated_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    refreshed["summary"] = {
        **(manifest.get("summary") or {}),
        "unique_items": len(updated_items),
        "ready": ready_count,
        "pending_local_audio": pending_count,
    }
    refreshed["library"] = {
        **(manifest.get("library") or {}),
        "scanned_paths": [str(path) for path in manifest_library_scan_paths(manifest)],
        "audio_files_found": len(files),
    }

    if DEFAULT_MANIFEST.exists() or refreshed.get("source"):
        DEFAULT_MANIFEST.write_text(json.dumps(refreshed, ensure_ascii=False, indent=2), encoding="utf-8")
        write_m3u_from_items(DEFAULT_M3U, updated_items)

    return refreshed


def manifest_track_keys(track: dict[str, Any]) -> set[str]:
    title = str(track.get("title") or "")
    artists = [str(artist) for artist in track.get("artists") or [] if artist]
    keys = {normalize_text(title)}

    for artist in artists:
        keys.add(normalize_text(f"{artist} {title}"))
        keys.add(normalize_text(f"{artist} - {title}"))

    local_file = track.get("local_file")
    if local_file:
        file_artists, file_title = parse_downloaded_filename(Path(str(local_file)))
        keys.add(normalize_text(file_title))
        for artist in file_artists:
            keys.add(normalize_text(f"{artist} {file_title}"))
            keys.add(normalize_text(f"{artist} - {file_title}"))

    return {key for key in keys if key}


def now_playing_song_keys(song: dict[str, Any]) -> set[str]:
    title = str(song.get("title") or "")
    artist = str(song.get("artist") or "")
    text = str(song.get("text") or "")
    keys = {normalize_text(title), normalize_text(text)}

    if artist and title:
        keys.add(normalize_text(f"{artist} {title}"))
        keys.add(normalize_text(f"{artist} - {title}"))

    if " - " in text:
        text_artist, text_title = text.split(" - ", 1)
        keys.add(normalize_text(text_title))
        keys.add(normalize_text(f"{text_artist} {text_title}"))
        keys.add(normalize_text(f"{text_artist} - {text_title}"))

    return {key for key in keys if key}


def find_manifest_track(song: dict[str, Any], manifest: dict[str, Any]) -> dict[str, Any] | None:
    song_keys = now_playing_song_keys(song)
    if not song_keys:
        return None

    title_matches: list[dict[str, Any]] = []
    song_title_key = normalize_text(str(song.get("title") or ""))

    for track in manifest.get("items", []):
        if track.get("status") != "ready":
            continue

        track_keys = manifest_track_keys(track)
        if song_keys & track_keys:
            return track

        if song_title_key and song_title_key == normalize_text(str(track.get("title") or "")):
            title_matches.append(track)

    return title_matches[0] if len(title_matches) == 1 else None


def song_title_from_now_playing(song: dict[str, Any]) -> str:
    title = str(song.get("title") or "").strip()
    if title:
        return title

    text = str(song.get("text") or "").strip()
    if " - " in text:
        return text.split(" - ", 1)[1].strip()
    return text


def song_artists_from_now_playing(song: dict[str, Any]) -> list[str]:
    artists = song.get("artists") if isinstance(song.get("artists"), list) else []
    cleaned = [str(artist).strip() for artist in artists if str(artist).strip()]
    if cleaned:
        return cleaned

    artist = str(song.get("artist") or "").strip()
    if artist:
        return [part.strip() for part in artist.split(",") if part.strip()]

    text = str(song.get("text") or "").strip()
    if " - " in text:
        return [text.split(" - ", 1)[0].strip()]
    return []


def find_catalog_track_by_song(catalog: dict[str, Any], song: dict[str, Any]) -> dict[str, Any] | None:
    song_keys = now_playing_song_keys(song)
    if not song_keys:
        return None

    title_matches: list[dict[str, Any]] = []
    song_title_key = normalize_text(song_title_from_now_playing(song))

    for track in catalog.get("tracks") or []:
        if not isinstance(track, dict):
            continue

        local_file = str(track.get("local_file") or "")
        if not local_file or not Path(local_file).exists():
            continue

        track_keys = manifest_track_keys(track)
        if song_keys & track_keys:
            return track

        if song_title_key and song_title_key == normalize_text(str(track.get("title") or "")):
            title_matches.append(track)

    if len(title_matches) == 1:
        return title_matches[0]

    return find_catalog_track(
        catalog,
        title=song_title_from_now_playing(song),
        artists=song_artists_from_now_playing(song),
    )


def find_track_for_song(song: dict[str, Any], manifest: dict[str, Any]) -> tuple[dict[str, Any] | None, str]:
    if not isinstance(song, dict):
        return None, ""

    track = find_manifest_track(song, manifest)
    if track:
        return track, "spotify-imported.json"

    catalog = load_library_catalog(refresh=False)
    track = find_catalog_track_by_song(catalog, song)
    if track:
        return track, "library-catalog.json"

    return None, ""


def enrich_song(song: dict[str, Any], track: dict[str, Any] | None) -> dict[str, Any]:
    if not track:
        if isinstance(song, dict):
            normalized = dict(song)
            art = normalize_client_art_url(str(normalized.get("art") or ""))
            if art:
                normalized["art"] = art
            return normalized
        return song

    artists = track.get("artists") or []
    title = str(track.get("title") or song.get("title") or "")
    artist = ", ".join(str(artist) for artist in artists if artist) or song.get("artist", "")
    album = str(track.get("album") or song.get("album") or "")
    cover_url = normalize_client_art_url(str(track.get("cover_url") or song.get("art") or ""))
    duration = int((track.get("duration_ms") or 0) / 1000)

    enriched = dict(song)
    art = normalize_client_art_url(str(song.get("art") or ""))
    enriched.update({
        "title": title,
        "artist": artist,
        "album": album,
        "art": cover_url or art or song.get("art", ""),
        "text": f"{artist} - {title}".strip(" -") or song.get("text", ""),
        "spotify_url": track.get("spotify_url", ""),
        "local_file": track.get("local_file", ""),
        "radio_poggers_metadata": True,
    })

    if duration > 0:
        enriched["duration"] = duration

    return enriched


def enrich_history_item(item: dict[str, Any], manifest: dict[str, Any]) -> dict[str, Any]:
    song = item.get("song")
    if not isinstance(song, dict):
        return item

    track = find_track_for_song(song, manifest)[0]
    if not track:
        enriched = dict(item)
        normalized_song = dict(song)
        art = normalize_client_art_url(str(normalized_song.get("art") or ""))
        if art:
            normalized_song["art"] = art
        enriched["song"] = normalized_song
        return enriched

    enriched = dict(item)
    enriched["song"] = enrich_song(song, track)
    duration = int((track.get("duration_ms") or 0) / 1000)
    if duration > 0:
        enriched["duration"] = duration
    return enriched


def parse_utc_datetime(value: str) -> datetime | None:
    if not value:
        return None

    try:
        return datetime.fromisoformat(value.replace(" ", "T")).replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def load_current_imported_queue_item(manifest: dict[str, Any]) -> dict[str, Any] | None:
    if not shutil.which("docker"):
        return None

    sql = (
        "SELECT sq.id, COALESCE(sm.path,''), COALESCE(sq.timestamp_played,''), "
        "COALESCE(sq.duration,0), COALESCE(sq.text,''), COALESCE(sq.artist,''), "
        "COALESCE(sq.title,''), COALESCE(sq.album,'') "
        "FROM station_queue sq "
        "LEFT JOIN station_media sm ON sm.id=sq.media_id "
        "WHERE sm.path LIKE 'imported/%' AND sq.sent_to_autodj=1 "
        "AND sq.timestamp_played <= UTC_TIMESTAMP() "
        "ORDER BY sq.timestamp_played DESC LIMIT 8;"
    )
    script = f"mariadb -N -B -h localhost -u $MYSQL_USER -p$MYSQL_PASSWORD $MYSQL_DATABASE -e {sql!r}"
    result = run_command([
        "docker",
        "exec",
        AZURACAST_CONTAINER,
        "bash",
        "-lc",
        script,
    ], timeout=10)

    if result.returncode != 0 or not result.stdout.strip():
        return None

    candidates: list[dict[str, Any]] = []

    for line in result.stdout.strip().splitlines():
        fields = line.split("\t")
        if len(fields) < 8:
            continue

        queue_id, path, played_at_raw, duration_raw, text, artist, title, album = fields[:8]
        played_at = parse_utc_datetime(played_at_raw)
        if not played_at:
            continue

        try:
            duration = int(float(duration_raw))
        except ValueError:
            duration = 0

        song = {
            "id": f"queue-{queue_id}",
            "text": text,
            "artist": artist,
            "title": title,
            "album": album,
            "art": "",
            "local_path": path,
        }
        track, _track_source = find_track_for_song(song, manifest)
        enriched_song = enrich_song(song, track)
        if track and track.get("duration_ms"):
            duration = int((track.get("duration_ms") or 0) / 1000) or duration

        elapsed_raw = int((datetime.now(timezone.utc) - played_at).total_seconds())
        if elapsed_raw < 0:
            continue

        elapsed = elapsed_raw
        if duration > 0 and elapsed > duration + 20:
            continue

        candidates.append({
            "song": enriched_song,
            "duration": duration,
            "elapsed": elapsed,
            "remaining": max(duration - elapsed, 0) if duration > 0 else 0,
            "played_at": int(played_at.timestamp()),
            "queue_path": path,
            "matched": bool(track),
        })

    if not candidates:
        return None

    for item in candidates:
        duration = int(item.get("duration") or 0)
        elapsed = int(item.get("elapsed") or 0)
        if duration <= 0 or elapsed <= duration + 5:
            return item

    return candidates[0]


def _queue_row_state(
    played_at: datetime,
    *,
    duration: int,
    now_utc: datetime,
    playing_assigned: bool,
) -> tuple[str, bool]:
    elapsed = int((now_utc - played_at).total_seconds())
    if played_at > now_utc:
        return "upcoming", playing_assigned
    if not playing_assigned and duration > 0 and 0 <= elapsed <= duration + 8:
        return "playing", True
    if played_at <= now_utc:
        return "played", playing_assigned
    return "upcoming", playing_assigned


def build_manifest_timeline(
    manifest: dict[str, Any],
    current_song: dict[str, Any] | None,
    *,
    limit: int = 48,
) -> list[dict[str, Any]]:
    raw_items = manifest.get("items") if isinstance(manifest.get("items"), list) else []
    sorted_items = sorted(
        [item for item in raw_items if isinstance(item, dict)],
        key=lambda item: int(item.get("playlist_position") or item.get("track_number") or 9999),
    )
    song_keys = now_playing_song_keys(current_song) if isinstance(current_song, dict) else set()
    found_current = False
    timeline: list[dict[str, Any]] = []

    for index, item in enumerate(sorted_items[:limit]):
        track_keys = manifest_track_keys(item)
        if song_keys and track_keys.intersection(song_keys):
            state = "playing"
            found_current = True
        elif not found_current:
            state = "played" if str(item.get("status") or "") == "ready" else "pending"
        else:
            state = "upcoming" if str(item.get("status") or "") == "ready" else "pending"

        artists = item.get("artists") if isinstance(item.get("artists"), list) else []
        artist = ", ".join(str(a) for a in artists if a)
        timeline.append({
            "rank": int(item.get("playlist_position") or item.get("track_number") or index + 1),
            "state": state,
            "status": str(item.get("status") or ""),
            "title": str(item.get("title") or "Faixa sem nome"),
            "artist": artist,
            "album": str(item.get("album") or ""),
            "art": str(item.get("cover_url") or item.get("art") or ""),
            "spotify_url": str(item.get("spotify_url") or ""),
            "duration_sec": int((item.get("duration_ms") or 0) / 1000) if item.get("duration_ms") else 0,
        })

    if timeline and not any(entry.get("state") == "playing" for entry in timeline):
        for entry in timeline:
            if entry.get("state") == "upcoming" and entry.get("status") == "ready":
                entry["state"] = "playing"
                break

    return timeline


def load_station_queue_timeline(
    manifest: dict[str, Any],
    current_song: dict[str, Any] | None = None,
    *,
    limit: int = 48,
) -> dict[str, Any]:
    source = manifest.get("source") if isinstance(manifest.get("source"), dict) else {}
    playlist_title = str(source.get("title") or "Playlist da radio").strip() or "Playlist da radio"
    safe_limit = max(8, min(int(limit or 48), 96))
    now_utc = datetime.now(timezone.utc)
    timeline: list[dict[str, Any]] = []
    queue_source = "manifest"

    if shutil.which("docker"):
        sql = (
            "SELECT sq.id, COALESCE(sm.path,''), COALESCE(sq.timestamp_played,''), "
            "COALESCE(sq.duration,0), COALESCE(sq.text,''), COALESCE(sq.artist,''), "
            "COALESCE(sq.title,''), COALESCE(sq.album,'') "
            "FROM station_queue sq "
            "LEFT JOIN station_media sm ON sm.id=sq.media_id "
            "WHERE sm.path LIKE 'imported/%' AND sq.sent_to_autodj=1 "
            "ORDER BY sq.timestamp_played ASC "
            f"LIMIT {safe_limit};"
        )
        result = run_azuracast_sql(sql, timeout=12)
        if result.returncode == 0 and result.stdout.strip():
            playing_assigned = False
            rank = 0
            for line in result.stdout.strip().splitlines():
                fields = line.split("\t")
                if len(fields) < 8:
                    continue
                rank += 1
                _queue_id, path, played_at_raw, duration_raw, text, artist, title, album = fields[:8]
                played_at = parse_utc_datetime(played_at_raw)
                if not played_at:
                    continue
                try:
                    duration = int(float(duration_raw))
                except ValueError:
                    duration = 0

                song = {
                    "id": f"queue-{_queue_id}",
                    "text": text,
                    "artist": artist,
                    "title": title,
                    "album": album,
                    "art": "",
                    "local_path": path,
                }
                track, _track_source = find_track_for_song(song, manifest)
                enriched = enrich_song(song, track)
                state, playing_assigned = _queue_row_state(
                    played_at,
                    duration=duration,
                    now_utc=now_utc,
                    playing_assigned=playing_assigned,
                )
                timeline.append({
                    "rank": rank,
                    "state": state,
                    "status": "ready" if track else "pending",
                    "title": str(enriched.get("title") or title or "Faixa sem nome"),
                    "artist": str(enriched.get("artist") or artist or ""),
                    "album": str(enriched.get("album") or album or ""),
                    "art": str(enriched.get("art") or ""),
                    "spotify_url": str(track.get("spotify_url") or "") if track else "",
                    "duration_sec": duration,
                    "played_at": int(played_at.timestamp()),
                })
            if timeline:
                queue_source = "station_queue"

    if not timeline:
        timeline = build_manifest_timeline(manifest, current_song, limit=safe_limit)
        queue_source = "manifest"

    return {
        "ok": True,
        "playlist_title": playlist_title,
        "source": queue_source,
        "items": timeline,
    }


def run_azuracast_sql(sql: str, timeout: int = 15) -> subprocess.CompletedProcess[str]:
    script = f"mariadb -N -B -h localhost -u $MYSQL_USER -p$MYSQL_PASSWORD $MYSQL_DATABASE -e {sql!r}"
    return run_command([
        "docker",
        "exec",
        AZURACAST_CONTAINER,
        "bash",
        "-lc",
        script,
    ], timeout=timeout)


def ensure_azuracast_playlist_settings() -> None:
    global _AZURACAST_PLAYLIST_FIXED

    if _AZURACAST_PLAYLIST_FIXED or not shutil.which("docker"):
        return

    station_id = get_station_id()
    if station_id is None:
        return

    result = run_azuracast_sql(
        f"UPDATE station_playlists SET avoid_duplicates = 0 "
        f"WHERE station_id = {station_id} AND avoid_duplicates = 1;"
    )
    if result.returncode == 0:
        _AZURACAST_PLAYLIST_FIXED = True


def build_playing_item(
    manifest: dict[str, Any],
    *,
    path: str,
    played_at: datetime,
    duration_raw: Any,
    text: str,
    artist: str,
    title: str,
    album: str,
    item_id: str,
) -> dict[str, Any]:
    try:
        duration = int(float(duration_raw))
    except (TypeError, ValueError):
        duration = 0

    song = {
        "id": item_id,
        "text": text,
        "artist": artist,
        "title": title,
        "album": album,
        "art": "",
        "local_path": path,
    }
    track, _track_source = find_track_for_song(song, manifest)
    enriched_song = enrich_song(song, track)
    if track and track.get("duration_ms"):
        duration = int((track.get("duration_ms") or 0) / 1000) or duration

    elapsed_raw = int((datetime.now(timezone.utc) - played_at).total_seconds())
    elapsed = max(elapsed_raw, 0)

    return {
        "song": enriched_song,
        "duration": duration,
        "elapsed": elapsed,
        "remaining": max(duration - elapsed, 0) if duration > 0 else 0,
        "played_at": int(played_at.timestamp()),
        "queue_path": path,
        "matched": bool(track),
    }


def load_current_playing_from_history(manifest: dict[str, Any]) -> dict[str, Any] | None:
    station_id = get_station_id()
    if station_id is None or not shutil.which("docker"):
        return None

    sql = (
        "SELECT sh.id, COALESCE(sm.path,''), COALESCE(sh.timestamp_start,''), "
        "COALESCE(sh.duration,0), COALESCE(sh.text,''), COALESCE(sh.artist,''), "
        "COALESCE(sh.title,''), COALESCE(sh.album,'') "
        "FROM song_history sh "
        "LEFT JOIN station_media sm ON sm.id = sh.media_id "
        f"WHERE sh.station_id = {station_id} AND sh.timestamp_end IS NULL "
        "ORDER BY sh.timestamp_start DESC LIMIT 1;"
    )
    result = run_azuracast_sql(sql)
    if result.returncode != 0 or not result.stdout.strip():
        return None

    fields = result.stdout.strip().split("\t")
    if len(fields) < 8:
        return None

    history_id, path, played_at_raw, duration_raw, text, artist, title, album = fields[:8]
    played_at = parse_utc_datetime(played_at_raw)
    if not played_at:
        return None

    elapsed_raw = int((datetime.now(timezone.utc) - played_at).total_seconds())
    if elapsed_raw < 0:
        return None

    return build_playing_item(
        manifest,
        path=path,
        played_at=played_at,
        duration_raw=duration_raw,
        text=text,
        artist=artist,
        title=title,
        album=album,
        item_id=f"history-{history_id}",
    )


def resolve_live_playing_item(manifest: dict[str, Any]) -> tuple[dict[str, Any] | None, str]:
    history_item = load_current_playing_from_history(manifest)
    if history_item:
        return history_item, "song_history_live"

    queue_item = load_current_imported_queue_item(manifest)
    if queue_item:
        return queue_item, "station_queue_live"

    return None, ""


def apply_live_playing_item(data: dict[str, Any], live_item: dict[str, Any], source: str) -> dict[str, Any]:
    updated = dict(data)
    updated["now_playing"] = {
        "song": live_item["song"],
        "duration": live_item["duration"],
        "elapsed": live_item["elapsed"],
        "remaining": live_item["remaining"],
        "played_at": live_item["played_at"],
        "playlist": "default",
        "streamer": "",
        "is_request": False,
    }
    updated["radio_poggers_metadata"] = {
        "matched": live_item["matched"],
        "source": source,
        "path": live_item.get("queue_path", ""),
    }
    if live_item["matched"]:
        track, _track_source = find_track_for_song(live_item["song"], load_manifest(refresh_local=False))
        if track and track.get("spotify_url"):
            updated["radio_poggers_metadata"]["spotify_url"] = track.get("spotify_url", "")
    return updated


def is_demo_song(song: dict[str, Any]) -> bool:
    text = normalize_text(str(song.get("text") or ""))
    artist = normalize_text(str(song.get("artist") or ""))
    album = normalize_text(str(song.get("album") or ""))
    return "demo" in text or "demo" in album or artist == "radiopoggers"


def songs_match(song_a: dict[str, Any], song_b: dict[str, Any]) -> bool:
    keys_a = now_playing_song_keys(song_a)
    keys_b = now_playing_song_keys(song_b)
    return bool(keys_a & keys_b)


def is_offline_placeholder_song(song: dict[str, Any] | None) -> bool:
    if not isinstance(song, dict):
        return False

    combined = " ".join(
        str(song.get(key) or "")
        for key in ("title", "artist", "album", "text")
    )
    normalized = normalize_text(combined)
    return (
        "estacao offline" in normalized
        or "station offline" in normalized
        or normalized in {"offline", "azuracast"}
    )


def get_station_id() -> int | None:
    global _STATION_ID_CACHE

    configured = os.environ.get("RADIOPOGGERS_STATION_ID", "").strip()
    if configured.isdigit():
        return int(configured)

    if _STATION_ID_CACHE is not None:
        return _STATION_ID_CACHE

    try:
        stations = fetch_json_url(f"{AZURACAST_BASE_URL}/api/stations")
    except Exception:
        return None

    if not isinstance(stations, list):
        return None

    for station in stations:
        if isinstance(station, dict) and station.get("shortcode") == STATION_SHORTCODE:
            try:
                _STATION_ID_CACHE = int(station["id"])
            except (TypeError, ValueError):
                return None
            return _STATION_ID_CACHE

    return None


def now_playing_is_stale(now_playing: dict[str, Any] | None, song: dict[str, Any] | None) -> bool:
    if not isinstance(now_playing, dict):
        return True
    return (
        is_static_track_ended(now_playing)
        or is_offline_placeholder_song(song if isinstance(song, dict) else None)
    )


def sync_azuracast_now_playing(force: bool = False) -> bool:
    global _LAST_AZURACAST_NOW_PLAYING_SYNC

    if not shutil.which("docker"):
        return False

    now = time.time()
    cooldown = NOWPLAYING_SYNC_COOLDOWN_SECONDS if force else 60
    if not force and now - _LAST_AZURACAST_NOW_PLAYING_SYNC < cooldown:
        return False

    _LAST_AZURACAST_NOW_PLAYING_SYNC = now
    result = run_command([
        "docker",
        "exec",
        AZURACAST_CONTAINER,
        "bash",
        "-lc",
        f"cd /var/azuracast/www && php backend/bin/console azuracast:sync:nowplaying:station {STATION_SHORTCODE}",
    ], timeout=45)
    return result.returncode == 0


def fetch_now_playing_payload() -> dict[str, Any]:
    station_slug = quote(STATION_SHORTCODE, safe="")
    static_url = f"{AZURACAST_BASE_URL}/api/nowplaying_static/{station_slug}.json"
    last_error: Exception | None = None
    station_id = get_station_id()
    candidate_urls: list[str] = []

    if station_id is not None:
        candidate_urls.extend([
            f"{AZURACAST_BASE_URL}/api/nowplaying/{station_id}",
            f"{AZURACAST_BASE_URL}/api/station/{station_id}/nowplaying",
        ])

    candidate_urls.append(static_url)

    for url in candidate_urls:
        try:
            payload = fetch_json_url(url)
            now_playing = payload.get("now_playing") if isinstance(payload, dict) else None
            song = now_playing.get("song") if isinstance(now_playing, dict) else None
            if now_playing_is_stale(now_playing if isinstance(now_playing, dict) else None, song if isinstance(song, dict) else None):
                sync_azuracast_now_playing(force=True)
                if station_id is not None:
                    try:
                        payload = fetch_json_url(f"{AZURACAST_BASE_URL}/api/nowplaying/{station_id}")
                    except Exception:
                        pass
            return payload
        except Exception as exc:
            last_error = exc

    try:
        payload = fetch_json_url(f"{AZURACAST_BASE_URL}/api/nowplaying")
        if isinstance(payload, list):
            for entry in payload:
                station = entry.get("station") if isinstance(entry, dict) else None
                if isinstance(station, dict) and station.get("shortcode") == STATION_SHORTCODE:
                    now_playing = entry.get("now_playing") if isinstance(entry, dict) else None
                    song = now_playing.get("song") if isinstance(now_playing, dict) else None
                    if now_playing_is_stale(now_playing if isinstance(now_playing, dict) else None, song if isinstance(song, dict) else None):
                        sync_azuracast_now_playing(force=True)
                    return entry
    except Exception as exc:
        last_error = exc

    raise last_error or RuntimeError("Now Playing indisponivel no AzuraCast.")


def merge_queue_timing(now_playing: dict[str, Any], queue_item: dict[str, Any]) -> dict[str, Any]:
    updated = dict(now_playing)
    now_ts = int(time.time())
    queue_played_at = int(queue_item.get("played_at") or 0)

    if queue_played_at > 0 and queue_played_at <= now_ts + 2:
        updated.update({
            "elapsed": queue_item["elapsed"],
            "remaining": queue_item["remaining"],
            "played_at": queue_item["played_at"],
        })

    duration = int(updated.get("duration") or queue_item.get("duration") or 0)
    if duration > 0:
        updated["duration"] = duration
        elapsed = track_elapsed_seconds(updated)
        updated["elapsed"] = elapsed
        updated["remaining"] = max(duration - elapsed, 0)

    return updated


def track_elapsed_seconds(now_playing: dict[str, Any]) -> int:
    static_elapsed = int(now_playing.get("elapsed") or 0)
    played_at = now_playing.get("played_at")
    if played_at is None:
        return static_elapsed

    try:
        played_ts = int(played_at)
        now_ts = int(time.time())
        if played_ts > now_ts + 5:
            return static_elapsed
        return max(now_ts - played_ts, 0)
    except (TypeError, ValueError):
        return static_elapsed


def is_static_track_active(now_playing: dict[str, Any]) -> bool:
    duration = int(now_playing.get("duration") or 0)
    if duration <= 0:
        return False

    static_elapsed = int(now_playing.get("elapsed") or 0)
    if static_elapsed >= duration:
        return False

    elapsed = track_elapsed_seconds(now_playing)
    return elapsed <= duration + 5


def is_static_track_ended(now_playing: dict[str, Any]) -> bool:
    duration = int(now_playing.get("duration") or 0)
    if duration <= 0:
        return False

    static_elapsed = int(now_playing.get("elapsed") or 0)
    if static_elapsed >= duration:
        return True

    return track_elapsed_seconds(now_playing) > duration + 5


def refresh_timing_from_played_at(now_playing: dict[str, Any]) -> dict[str, Any]:
    updated = dict(now_playing)
    if updated.get("played_at") is None:
        return updated

    elapsed = track_elapsed_seconds(updated)
    duration = int(updated.get("duration") or 0)
    updated["elapsed"] = elapsed
    if duration > 0:
        updated["remaining"] = max(duration - elapsed, 0)
    return updated


def is_queue_item_active(queue_item: dict[str, Any]) -> bool:
    duration = int(queue_item.get("duration") or 0)
    elapsed = int(queue_item.get("elapsed") or 0)
    return duration <= 0 or elapsed <= duration + 5


def queue_overlay_metadata(queue_item: dict[str, Any], source: str) -> dict[str, Any]:
    return {
        "matched": queue_item["matched"],
        "source": source,
        "path": queue_item["queue_path"],
    }


def apply_queue_song(now_playing: dict[str, Any], queue_item: dict[str, Any]) -> dict[str, Any]:
    updated = dict(now_playing)
    updated.update({
        "song": queue_item["song"],
        "duration": queue_item["duration"],
        "elapsed": queue_item["elapsed"],
        "remaining": queue_item["remaining"],
        "played_at": queue_item["played_at"],
    })
    return updated


def apply_queue_overlay(
    now_playing: dict[str, Any],
    queue_item: dict[str, Any] | None,
    song: dict[str, Any] | None,
    azuracast_stale: bool = False,
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    if not queue_item:
        return now_playing, None

    queue_song = queue_item["song"]

    if not isinstance(song, dict):
        return apply_queue_song(now_playing, queue_item), queue_overlay_metadata(
            queue_item,
            "station_queue_imported_fallback",
        )

    if is_demo_song(song):
        return apply_queue_song(now_playing, queue_item), queue_overlay_metadata(
            queue_item,
            "station_queue_imported_fallback",
        )

    if songs_match(song, queue_song):
        updated = merge_queue_timing(now_playing, queue_item)
        return updated, queue_overlay_metadata(queue_item, "station_queue_timing_sync")

    if not azuracast_stale and is_static_track_active(now_playing):
        return now_playing, None

    if is_queue_item_active(queue_item) and azuracast_stale:
        return apply_queue_song(now_playing, queue_item), queue_overlay_metadata(
            queue_item,
            "station_queue_live_fallback",
        )

    if is_static_track_ended(now_playing) or is_offline_placeholder_song(song):
        return apply_queue_song(now_playing, queue_item), queue_overlay_metadata(
            queue_item,
            "station_queue_imported_fallback",
        )

    return now_playing, None


def load_enriched_now_playing() -> dict[str, Any]:
    manifest = load_manifest()
    live_item, live_source = resolve_live_playing_item(manifest)
    data = fetch_now_playing_payload()
    now_playing = data.get("now_playing") or {}
    if not isinstance(now_playing, dict):
        now_playing = {}

    song = now_playing.get("song") if isinstance(now_playing.get("song"), dict) else None
    azuracast_stale = now_playing_is_stale(now_playing if isinstance(now_playing, dict) else None, song)
    live_mismatch = bool(
        live_item
        and isinstance(song, dict)
        and not songs_match(song, live_item["song"])
    )

    if live_item and (azuracast_stale or live_mismatch or not isinstance(song, dict)):
        data = apply_live_playing_item(data, live_item, live_source)
        sync_azuracast_now_playing(force=True)
        history = data.get("song_history")
        if isinstance(history, list):
            data["song_history"] = [
                enrich_history_item(item, manifest) if isinstance(item, dict) else item
                for item in history
            ]
        return data

    queue_item = live_item or load_current_imported_queue_item(manifest)
    track = None
    track_source = ""
    if isinstance(song, dict):
        track, track_source = find_track_for_song(song, manifest)

    if isinstance(song, dict):
        enriched_now_playing = dict(now_playing)

        if track:
            enriched_now_playing["song"] = enrich_song(song, track)
            duration = int((track.get("duration_ms") or 0) / 1000)
            if duration > 0:
                enriched_now_playing["duration"] = duration
                elapsed = int(enriched_now_playing.get("elapsed") or 0)
                enriched_now_playing["remaining"] = max(duration - elapsed, 0)

            data["radio_poggers_metadata"] = {
                "matched": True,
                "source": track_source,
                "spotify_url": track.get("spotify_url", ""),
            }
        else:
            enriched_now_playing["song"] = enrich_song(song, None)
            data["radio_poggers_metadata"] = {"matched": False}

        enriched_now_playing, queue_metadata = apply_queue_overlay(
            enriched_now_playing,
            queue_item,
            enriched_now_playing.get("song") if isinstance(enriched_now_playing.get("song"), dict) else song,
            azuracast_stale=azuracast_stale,
        )
        data["now_playing"] = enriched_now_playing
        if queue_metadata:
            base_meta = data.get("radio_poggers_metadata") if isinstance(data.get("radio_poggers_metadata"), dict) else {}
            merged_meta = {**queue_metadata, **base_meta}
            if queue_metadata.get("path"):
                merged_meta["path"] = queue_metadata["path"]
            data["radio_poggers_metadata"] = merged_meta
    elif queue_item:
        data["now_playing"] = {
            "song": queue_item["song"],
            "duration": queue_item["duration"],
            "elapsed": queue_item["elapsed"],
            "remaining": queue_item["remaining"],
            "played_at": queue_item["played_at"],
        }
        data["radio_poggers_metadata"] = {
            "matched": queue_item["matched"],
            "source": "station_queue_imported_fallback",
            "path": queue_item["queue_path"],
        }

    now_playing_out = data.get("now_playing")
    if isinstance(now_playing_out, dict):
        song_out = now_playing_out.get("song")
        if isinstance(song_out, dict) and not str(song_out.get("art") or "").strip():
            fallback_track, _fallback_source = find_track_for_song(song_out, manifest)
            if fallback_track:
                now_playing_out = dict(now_playing_out)
                now_playing_out["song"] = enrich_song(song_out, fallback_track)
                data["now_playing"] = now_playing_out
        data["now_playing"] = refresh_timing_from_played_at(now_playing_out)

    history = data.get("song_history")
    if isinstance(history, list):
        data["song_history"] = [
            enrich_history_item(item, manifest) if isinstance(item, dict) else item
            for item in history
        ]

    active_drop = get_active_voice_drop()
    if active_drop:
        data["voice_drop"] = active_drop

    maybe_schedule_miku_narration(data)

    if miku_narrator_enabled():
        status = miku_status()
        status["busy"] = _MIKU_GENERATION_BUSY
        data["miku_narrator"] = status

    data["narrator_hints"] = get_narrator_hints()

    if hoshino_narrator_enabled():
        data["hoshino_narrator"] = hoshino_status()

    active_vote = get_active_vote_public()
    if active_vote:
        data["audience_vote"] = active_vote
    else:
        data["audience_vote"] = None
    data["audience"] = audience_counts()
    data["vote_system"] = vote_status()

    return data


_SPOTIFY_IMPORT_JOBS: dict[str, dict[str, Any]] = {}
_SPOTIFY_IMPORT_JOB_LOCK = threading.Lock()


def get_running_spotify_import_job() -> dict[str, Any] | None:
    with _SPOTIFY_IMPORT_JOB_LOCK:
        running = [
            dict(job)
            for job in _SPOTIFY_IMPORT_JOBS.values()
            if str(job.get("status") or "").strip().lower() == "running"
        ]
    if not running:
        return None
    return max(running, key=lambda item: float(item.get("updated_at") or 0))


def _update_spotify_import_job(job_id: str, **fields: Any) -> None:
    with _SPOTIFY_IMPORT_JOB_LOCK:
        job = _SPOTIFY_IMPORT_JOBS.get(job_id)
        if not job:
            return
        job.update(fields)
        job["updated_at"] = time.time()


def get_spotify_import_job(job_id: str) -> dict[str, Any] | None:
    safe_id = str(job_id or "").strip()
    if not safe_id:
        return None

    with _SPOTIFY_IMPORT_JOB_LOCK:
        job = _SPOTIFY_IMPORT_JOBS.get(safe_id)
        return dict(job) if job else None


def public_spotify_import_job(job: dict[str, Any]) -> dict[str, Any]:
    payload = {
        "ok": True,
        "job_id": job.get("id"),
        "status": job.get("status", "running"),
        "phase": job.get("phase", ""),
        "message": job.get("message", ""),
        "error": job.get("error", ""),
        "library_catalog": job.get("library_catalog") or library_catalog_public_meta(),
    }

    if job.get("status") == "done" and isinstance(job.get("result"), dict):
        payload["result"] = job["result"]

    return payload


def execute_spotify_import(spotify_url: str, *, on_phase: Any = None) -> dict[str, Any]:
    def phase(name: str, message: str) -> None:
        if callable(on_phase):
            on_phase(name, message)

    cached_manifest = load_cached_manifest_for_spotify_url(spotify_url)
    if cached_manifest and spotify_import_is_cached_ready(spotify_url):
        phase("download", "Playlist ja na biblioteca — pulando download.")
        download = build_skipped_download_payload(spotify_url, cached_manifest)
        manifest = cached_manifest
        phase("metadata", "Atualizando catalogo da playlist importada...")
    else:
        phase("download", "Baixando audio com spotdl...")
        download = download_spotify_audio(spotify_url)
        manifest = None
        catalog_meta = refresh_library_catalog_after_download(download)
        if int(catalog_meta.get("tracks") or 0) > 0 and (
            int(download.get("downloaded_estimate") or 0) > 0
            or int(download.get("audio_files_after") or 0) > int(download.get("audio_files_before") or 0)
        ):
            phase(
                "catalog",
                f"Estante atualizada — {catalog_meta.get('tracks', 0)} faixa(s) no catalogo.",
            )

    try:
        if manifest is None:
            phase("metadata", "Gerando manifesto e catalogo...")
            manifest = import_spotify_metadata(spotify_url)
        from spotify_search import spotify_credentials_configured

        has_spotify_credentials = spotify_credentials_configured()
        if (
            manifest is not None
            and not has_spotify_credentials
            and download.get("audio_files_after", 0) > len(manifest.get("items", []))
        ):
            manifest = build_download_manifest(spotify_url, download)
            manifest["metadata_source"] = "spotdl_save_file_without_spotify_credentials"
            DEFAULT_MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as import_error:
        if download.get("skipped") and cached_manifest:
            manifest = cached_manifest
            manifest["metadata_import_error"] = str(import_error)
            DEFAULT_MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        elif download.get("skipped"):
            manifest = build_download_manifest(spotify_url, download)
            manifest["metadata_import_error"] = str(import_error)
            DEFAULT_MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        elif download.get("audio_files_after", 0) <= 0:
            raise
        else:
            manifest = build_download_manifest(spotify_url, download)
            manifest["metadata_import_error"] = str(import_error)
            DEFAULT_MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    if manifest is None:
        raise RuntimeError("Manifesto da playlist indisponivel apos importacao.")

    phase("sync", "Sincronizando faixas prontas com o AzuraCast...")
    sync = sync_ready_tracks_to_azuracast(manifest)
    catalog = rebuild_library_catalog(manifest)
    vote_payload = first_ready_track_payload(manifest)

    phase("done", "Importacao concluida.")
    return {
        "manifest": manifest,
        "download": download,
        "sync": sync,
        "vote_payload": vote_payload,
        "library_catalog": {
            "tracks": (catalog.get("summary") or {}).get("tracks", 0),
            "generated_at": catalog.get("generated_at"),
        },
    }


def _run_spotify_import_job(job_id: str, spotify_url: str) -> None:
    def on_phase(phase_name: str, message: str) -> None:
        fields: dict[str, Any] = {"phase": phase_name, "message": message}
        if phase_name in {"catalog", "metadata", "sync", "done"}:
            fields["library_catalog"] = library_catalog_public_meta()
        _update_spotify_import_job(job_id, **fields)

    try:
        result = execute_spotify_import(spotify_url, on_phase=on_phase)
        _update_spotify_import_job(
            job_id,
            status="done",
            phase="done",
            message="Importacao concluida.",
            result=result,
            error="",
        )
    except Exception as error:
        _update_spotify_import_job(
            job_id,
            status="error",
            phase="error",
            message="Falha na importacao.",
            error=str(error),
        )


def start_spotify_import_job(spotify_url: str) -> str:
    safe_url = validate_spotify_url(spotify_url)
    safe_key = spotify_url_key(safe_url)
    job_id = secrets.token_hex(8)
    now = time.time()
    job = {
        "id": job_id,
        "status": "running",
        "phase": "starting",
        "message": "Importacao iniciada...",
        "spotify_url": safe_url,
        "spotify_key": safe_key,
        "started_at": now,
        "updated_at": now,
        "error": "",
        "result": None,
    }

    with _SPOTIFY_IMPORT_JOB_LOCK:
        for active in _SPOTIFY_IMPORT_JOBS.values():
            if str(active.get("status") or "").strip().lower() != "running":
                continue
            raise SpotifyImportBusyError(
                "Ja existe uma importacao Spotify em andamento. Aguarde terminar antes de enviar outro link.",
                active_job_id=str(active.get("id") or ""),
                active_spotify_url=str(active.get("spotify_url") or ""),
                active_spotify_key=str(active.get("spotify_key") or ""),
            )

        _SPOTIFY_IMPORT_JOBS[job_id] = job
        if len(_SPOTIFY_IMPORT_JOBS) > 12:
            oldest = sorted(
                _SPOTIFY_IMPORT_JOBS.items(),
                key=lambda item: float(item[1].get("updated_at") or 0),
            )
            for stale_id, _stale_job in oldest[:-8]:
                _SPOTIFY_IMPORT_JOBS.pop(stale_id, None)

    worker = threading.Thread(
        target=_run_spotify_import_job,
        args=(job_id, safe_url),
        name=f"spotify-import-{job_id}",
        daemon=True,
    )
    worker.start()
    return job_id


def parse_request_path(raw_path: str) -> tuple[str, dict[str, list[str]]]:
    parsed = urlparse(raw_path)
    return parsed.path, parse_qs(parsed.query)


def serve_sse_vote_events(handler: BaseHTTPRequestHandler) -> None:
    handler.send_response(200)
    handler.send_header("Content-Type", "text/event-stream; charset=utf-8")
    handler.send_header("Cache-Control", "no-cache")
    handler.send_header("Connection", "keep-alive")
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.end_headers()

    queue, unsubscribe = sse_subscribe()
    last_index = 0
    try:
        handler.wfile.write(b": connected\n\n")
        handler.wfile.flush()
        idle_ticks = 0
        while True:
            time.sleep(0.45)
            if len(queue) > last_index:
                for message in queue[last_index:]:
                    chunk = f"data: {message}\n\n".encode("utf-8")
                    handler.wfile.write(chunk)
                handler.wfile.flush()
                last_index = len(queue)
                idle_ticks = 0
            else:
                idle_ticks += 1
                if idle_ticks >= 6:
                    handler.wfile.write(b": keepalive\n\n")
                    handler.wfile.flush()
                    idle_ticks = 0
    except (BrokenPipeError, ConnectionResetError, OSError):
        pass
    finally:
        unsubscribe()


def serve_library_preview(handler: BaseHTTPRequestHandler, track_id: str) -> None:
    catalog = load_library_catalog(refresh=False)
    track = find_track_in_catalog_by_id(catalog, track_id)
    if not track:
        json_response(handler, 404, {"ok": False, "error": "Faixa nao encontrada."})
        return

    path = Path(str(track.get("local_file") or ""))
    if not path.exists() or not is_path_in_library(path):
        json_response(handler, 404, {"ok": False, "error": "Arquivo local indisponivel."})
        return

    try:
        serve_file_with_range(handler, path)
    except OSError as error:
        json_response(handler, 500, {"ok": False, "error": str(error)})


class RadioPoggersHandler(BaseHTTPRequestHandler):
    server_version = "RadioPoggersLocalAPI/1.0"

    def do_OPTIONS(self) -> None:
        json_response(self, 200, {"ok": True})

    def do_GET(self) -> None:
        path, query = parse_request_path(self.path)

        if path == "/api/app/release":
            manifest = load_app_release_manifest()
            if not manifest:
                json_response(self, 404, {"ok": False, "error": "app_release_not_configured"})
                return
            apk_path = resolve_app_release_apk_path(manifest)
            tag = str(manifest.get("tag_name") or manifest.get("version") or "").strip()
            version = str(manifest.get("version") or tag).strip()
            if tag and not tag.lower().startswith("v"):
                tag = f"v{tag}"
            json_response(self, 200, {
                "ok": True,
                "tag_name": tag,
                "version": version,
                "release_page_url": str(manifest.get("release_page_url") or "").strip(),
                "android_download_url": "/api/app/release/apk" if apk_path else None,
                "apk_available": bool(apk_path),
            })
            return

        if path == "/api/app/release/apk":
            manifest = load_app_release_manifest()
            apk_path = resolve_app_release_apk_path(manifest)
            if not apk_path:
                json_response(self, 404, {"ok": False, "error": "apk_not_found"})
                return
            serve_file_with_range(self, apk_path)
            return

        if path == "/api/health":
            azuracast_key = resolve_azuracast_api_key()
            docker_skip = bool(shutil.which("docker"))
            release_manifest = load_app_release_manifest()
            json_response(self, 200, {
                "ok": True,
                "station": STATION_SHORTCODE,
                "manifest": str(DEFAULT_MANIFEST),
                "library_catalog": str(LIBRARY_CATALOG),
                "voice_drop": True,
                "miku_narrator": miku_narrator_enabled(),
                "miku": miku_status(),
                "hoshino_narrator": hoshino_narrator_enabled(),
                "hoshino": hoshino_status(),
                "vote_system": vote_status(),
                "library_catalog": library_catalog_public_meta(),
                "azuracast": {
                    "base_url": AZURACAST_BASE_URL,
                    "skip_available": bool(azuracast_key) or docker_skip,
                    "skip_mode": "api_key" if azuracast_key else ("docker_liquidsoap" if docker_skip else "unavailable"),
                    "requests_available": bool(azuracast_key),
                    "api_key_file": str(AZURACAST_API_KEY_FILE),
                },
                "maintenance": load_maintenance_status(),
                "app_release": {
                    "configured": bool(release_manifest),
                    "tag_name": (release_manifest or {}).get("tag_name"),
                    "apk_available": resolve_app_release_apk_path(release_manifest) is not None,
                },
            })
            return

        if path == "/api/audience/count":
            json_response(self, 200, {"ok": True, **audience_counts(), **vote_status()})
            return

        if path == "/api/vote/active":
            json_response(self, 200, {
                "ok": True,
                "vote": get_active_vote_public(),
                **vote_status(),
            })
            return

        if path == "/api/vote/events":
            serve_sse_vote_events(self)
            return

        if path == "/api/miku/status":
            json_response(self, 200, {"ok": True, **miku_status()})
            return

        if path == "/api/hoshino/status":
            json_response(self, 200, {"ok": True, **hoshino_status()})
            return

        if path == "/api/manifest":
            json_response(self, 200, load_manifest())
            return

        if path == "/api/station-queue":
            manifest = load_manifest(refresh_local=False)
            now_data = load_enriched_now_playing()
            now_block = now_data.get("now_playing") if isinstance(now_data.get("now_playing"), dict) else {}
            current_song = now_block.get("song") if isinstance(now_block.get("song"), dict) else {}
            try:
                queue_limit = int(query.get("limit", ["48"])[0] or "48")
            except ValueError:
                queue_limit = 48
            payload = load_station_queue_timeline(
                manifest,
                current_song,
                limit=queue_limit,
            )
            json_response(self, 200, payload)
            return

        if path == "/api/nowplaying":
            json_response(self, 200, load_enriched_now_playing())
            return

        if path == "/api/library/meta":
            refresh = library_refresh_requested(query)
            if refresh:
                catalog = load_library_catalog(refresh=True)
            else:
                catalog = load_library_catalog(refresh=False)
            json_response(self, 200, {
                "ok": True,
                "catalog": library_catalog_public_meta(catalog),
            })
            return

        if path == "/api/library/filters":
            catalog = load_library_catalog(refresh=library_refresh_requested(query))
            json_response(self, 200, {
                "ok": True,
                "summary": catalog.get("summary") or {},
                "catalog_meta": library_catalog_public_meta(catalog),
                "filters": library_filters_from_catalog(catalog),
            })
            return

        if path == "/api/library":
            catalog = load_library_catalog(refresh=library_refresh_requested(query))
            tracks = catalog.get("tracks") if isinstance(catalog.get("tracks"), list) else []
            q = (query.get("q", [""])[0] or "").strip()
            artist = (query.get("artist", [""])[0] or "").strip()
            album = (query.get("album", [""])[0] or "").strip()
            try:
                limit = int(query.get("limit", ["50"])[0] or "50")
            except ValueError:
                limit = 50
            try:
                offset = int(query.get("offset", ["0"])[0] or "0")
            except ValueError:
                offset = 0

            page, total = filter_library_tracks(
                tracks,
                query=q,
                artist=artist,
                album=album,
                limit=limit,
                offset=offset,
            )
            json_response(self, 200, {
                "ok": True,
                "generated_at": catalog.get("generated_at"),
                "summary": catalog.get("summary") or {},
                "catalog_meta": library_catalog_public_meta(catalog),
                "query": {"q": q, "artist": artist, "album": album, "limit": limit, "offset": offset},
                "total": total,
                "tracks": page,
            })
            return

        if path.startswith("/api/library/preview/"):
            track_id = unquote(path.removeprefix("/api/library/preview/").strip("/"))
            if not track_id:
                json_response(self, 404, {"ok": False, "error": "Faixa nao informada."})
                return
            serve_library_preview(self, track_id)
            return

        if path.startswith("/api/voice-drop/file/"):
            drop_id = unquote(path.removeprefix("/api/voice-drop/file/").strip("/"))
            file_path = voice_drop_file_path(drop_id)
            if not file_path or not is_path_in_voice_drops(file_path):
                json_response(self, 404, {"ok": False, "error": "Chamada nao encontrada."})
                return
            try:
                serve_file_with_range(self, file_path)
            except OSError as error:
                json_response(self, 500, {"ok": False, "error": str(error)})
            return

        if path == "/api/voice-drop/active":
            active = get_active_voice_drop()
            json_response(self, 200, {"ok": True, "voice_drop": active})
            return

        if path == "/api/import-spotify/status":
            job_id = (query.get("job_id", [""])[0] or query.get("job", [""])[0] or "").strip()
            job = get_spotify_import_job(job_id)
            if not job:
                json_response(self, 404, {"ok": False, "error": "Importacao nao encontrada."})
                return
            json_response(self, 200, public_spotify_import_job(job))
            return

        if path == "/api/import-spotify/inspect":
            spotify_url = (query.get("spotifyUrl", [""])[0] or query.get("url", [""])[0] or "").strip()
            if not spotify_url:
                json_response(self, 400, {"ok": False, "error": "Informe spotifyUrl."})
                return
            try:
                json_response(self, 200, inspect_spotify_import(spotify_url))
            except Exception as error:
                json_response(self, 400, {"ok": False, "error": str(error)})
            return

        if path == "/api/discord/resolve-query":
            search_q = (query.get("q", [""])[0] or query.get("query", [""])[0] or "").strip()
            if not search_q:
                json_response(self, 400, {"ok": False, "error": "Informe q."})
                return
            try:
                from discord_bridge import discord_resolve_query

                json_response(self, 200, discord_resolve_query(search_q))
            except Exception as error:
                json_response(self, 400, {"ok": False, "error": str(error)})
            return

        json_response(self, 404, {"ok": False, "error": "Endpoint nao encontrado."})

    def do_POST(self) -> None:
        path, _query = parse_request_path(self.path)

        if path == "/api/library/request":
            try:
                payload = read_json_body(self)
                track_id = str(payload.get("track_id") or payload.get("trackId") or "").strip()
                if not track_id:
                    raise ValueError("Informe track_id.")

                catalog = load_library_catalog(refresh=False)
                track = find_track_in_catalog_by_id(catalog, track_id)
                if not track:
                    raise ValueError("Faixa nao encontrada no catalogo local.")

                result = request_track_on_radio(track)
                json_response(self, 200, result)
            except Exception as error:
                json_response(self, 400, {"ok": False, "error": str(error)})
            return

        if path == "/api/audience/heartbeat":
            try:
                payload = read_json_body(self)
                listener_id = str(payload.get("listener_id") or payload.get("listenerId") or "").strip()
                playing = payload.get("playing") is True or str(payload.get("playing") or "").lower() in {"1", "true", "yes"}
                counts = record_heartbeat(listener_id, playing)
                json_response(self, 200, {"ok": True, **counts, **vote_status()})
            except Exception as error:
                json_response(self, 400, {"ok": False, "error": str(error)})
            return

        if path == "/api/vote/start":
            try:
                payload = read_json_body(self)
                vote_type = str(payload.get("type") or "").strip()
                proposer_id = str(payload.get("proposer_id") or payload.get("proposerId") or "").strip()
                vote_payload = payload.get("payload") if isinstance(payload.get("payload"), dict) else {}
                vote = start_vote(vote_type, proposer_id, vote_payload)
                json_response(self, 200, {"ok": True, "vote": vote, **vote_status()})
            except Exception as error:
                status = 409 if "votacao em andamento" in str(error).lower() else 400
                json_response(self, status, {"ok": False, "error": str(error)})
            return

        if path == "/api/vote/cast":
            try:
                payload = read_json_body(self)
                vote_id = str(payload.get("vote_id") or payload.get("voteId") or "").strip()
                listener_id = str(payload.get("listener_id") or payload.get("listenerId") or "").strip()
                choice = str(payload.get("choice") or "").strip().lower()
                vote = cast_vote(vote_id, listener_id, choice)
                json_response(self, 200, {"ok": True, "vote": vote})
            except Exception as error:
                json_response(self, 400, {"ok": False, "error": str(error)})
            return

        if path == "/api/vote/execute-direct":
            try:
                payload = read_json_body(self)
                vote_type = str(payload.get("type") or "").strip()
                proposer_id = str(payload.get("proposer_id") or payload.get("proposerId") or "").strip()
                choice = str(payload.get("choice") or "").strip().lower()
                vote_payload = payload.get("payload") if isinstance(payload.get("payload"), dict) else {}
                result = execute_direct(vote_type, proposer_id, choice, vote_payload)
                json_response(self, 200, {**result, **vote_status()})
            except Exception as error:
                json_response(self, 400, {"ok": False, "error": str(error)})
            return

        if path == "/api/voice-drop":
            try:
                result = save_voice_drop_request(self)
                json_response(self, 200, result)
            except Exception as error:
                json_response(self, 400, {"ok": False, "error": str(error)})
            return

        if path == "/api/miku/narrate":
            try:
                payload = read_json_body(self)
                result = save_miku_narration(payload)
                json_response(self, 200, result)
            except Exception as error:
                json_response(self, 400, {"ok": False, "error": str(error)})
            return

        if path == "/api/hoshino/narrate":
            try:
                payload = read_json_body(self)
                result = save_hoshino_narration(payload)
                json_response(self, 200, result)
            except Exception as error:
                json_response(self, 400, {"ok": False, "error": str(error)})
            return

        if path == "/api/discord/skip":
            try:
                from discord_bridge import discord_skip_track

                result = discord_skip_track()
                json_response(self, 200, {"ok": True, **result})
            except Exception as error:
                json_response(self, 400, {"ok": False, "error": str(error)})
            return

        if path == "/api/discord/play-track":
            try:
                from discord_bridge import discord_play_track_immediate

                payload = read_json_body(self)
                track_id = str(payload.get("track_id") or payload.get("trackId") or "").strip()
                result = discord_play_track_immediate(track_id)
                json_response(self, 200, {"ok": True, **result})
            except Exception as error:
                json_response(self, 400, {"ok": False, "error": str(error)})
            return

        if path == "/api/discord/play-spotify":
            try:
                from discord_bridge import discord_play_spotify_if_ready

                payload = read_json_body(self)
                spotify_url = str(payload.get("spotifyUrl") or payload.get("spotify_url") or "").strip()
                if not spotify_url:
                    raise ValueError("Informe spotifyUrl.")
                result = discord_play_spotify_if_ready(spotify_url)
                json_response(self, 200, {"ok": True, **result})
            except Exception as error:
                json_response(self, 400, {"ok": False, "error": str(error)})
            return

        if path == "/api/discord/play-query":
            try:
                from discord_bridge import discord_play_query

                payload = read_json_body(self)
                search_q = str(payload.get("query") or payload.get("q") or "").strip()
                if not search_q:
                    raise ValueError("Informe query.")
                result = discord_play_query(search_q)
                json_response(self, 200, {"ok": True, **result})
            except Exception as error:
                json_response(self, 400, {"ok": False, "error": str(error)})
            return

        if path != "/api/import-spotify":
            drain_request_body(self)
            json_response(self, 404, {"ok": False, "error": "Endpoint nao encontrado."})
            return

        try:
            payload = read_json_body(self)
            spotify_url = validate_spotify_url(str(payload.get("spotifyUrl", "")))
            job_id = start_spotify_import_job(spotify_url)
            json_response(self, 202, {
                "ok": True,
                "job_id": job_id,
                "status": "running",
                "message": "Importacao iniciada. Acompanhe o progresso no player.",
            })
        except SpotifyImportBusyError as error:
            json_response(self, 409, {
                "ok": False,
                "error": str(error),
                "active_job_id": error.active_job_id,
                "active_spotify_url": error.active_spotify_url,
                "active_spotify_key": error.active_spotify_key,
            })
        except Exception as error:
            json_response(self, 400, {
                "ok": False,
                "error": str(error),
            })

    def log_message(self, format: str, *args: Any) -> None:
        print(f"[RadioPoggers API] {self.address_string()} - {format % args}")


def background_now_playing_maintenance() -> None:
    ensure_azuracast_playlist_settings()
    sync_azuracast_now_playing(force=True)

    while True:
        time.sleep(NOWPLAYING_AUTO_SYNC_SECONDS)
        try:
            ensure_azuracast_playlist_settings()
            station_id = get_station_id()
            if station_id is None:
                continue

            payload = fetch_json_url(f"{AZURACAST_BASE_URL}/api/nowplaying/{station_id}")
            now_playing = payload.get("now_playing") if isinstance(payload, dict) else None
            song = now_playing.get("song") if isinstance(now_playing, dict) else None
            if not now_playing_is_stale(now_playing if isinstance(now_playing, dict) else None, song if isinstance(song, dict) else None):
                continue

            live_item, _ = resolve_live_playing_item(load_manifest(refresh_local=False))
            if live_item and isinstance(song, dict) and songs_match(song, live_item["song"]):
                continue

            sync_azuracast_now_playing(force=True)
        except Exception:
            continue


def start_background_now_playing_maintenance() -> None:
    worker = threading.Thread(
        target=background_now_playing_maintenance,
        name="radiopoggers-nowplaying-sync",
        daemon=True,
    )
    worker.start()


def main() -> int:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    LIBRARY_INBOX.mkdir(parents=True, exist_ok=True)
    LIBRARY_MANAGED.mkdir(parents=True, exist_ok=True)
    SPOTDL_DOWNLOAD_ROOT.mkdir(parents=True, exist_ok=True)
    VOICE_DROPS_DIR.mkdir(parents=True, exist_ok=True)

    start_background_now_playing_maintenance()

    server = ThreadingHTTPServer((HOST, PORT), RadioPoggersHandler)
    print(f"RadioPoggers API rodando em http://{HOST}:{PORT}")
    print(f"Now Playing auto-sync a cada {NOWPLAYING_AUTO_SYNC_SECONDS}s")
    print(f"Inbox: {LIBRARY_INBOX}")
    print(f"Managed: {LIBRARY_MANAGED}")
    print(f"Spotdl: {SPOTDL_DOWNLOAD_ROOT}")
    print(f"Catalog: {LIBRARY_CATALOG}")
    server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

