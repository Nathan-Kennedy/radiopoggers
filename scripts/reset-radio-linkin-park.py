#!/usr/bin/env python3
"""Zera a playlist da radio e deixa so faixas Linkin Park prontas no AzuraCast."""

from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SERVER_DIR = PROJECT_ROOT / "tools" / "radiopoggers-server"
sys.path.insert(0, str(SERVER_DIR))

import server  # noqa: E402


def is_linkin_park_track(track: dict) -> bool:
    artists = track.get("artists") if isinstance(track.get("artists"), list) else []
    return any("linkin park" in str(artist).lower() for artist in artists)


def catalog_track_to_manifest_item(track: dict, position: int) -> dict:
    return {
        "spotify_id": str(track.get("spotify_id") or track.get("id") or ""),
        "isrc": str(track.get("isrc") or ""),
        "spotify_url": str(track.get("spotify_url") or ""),
        "title": str(track.get("title") or ""),
        "artists": track.get("artists") if isinstance(track.get("artists"), list) else ["Linkin Park"],
        "album": str(track.get("album") or "This Is Linkin Park"),
        "duration_ms": int(track.get("duration_ms") or 0),
        "track_number": position,
        "disc_number": 1,
        "cover_url": str(track.get("cover_url") or ""),
        "local_file": str(track.get("local_file") or ""),
        "status": "ready",
        "match": {"score": 100, "reason": "linkin_park_reset"},
        "playlist_position": position,
    }


def build_linkin_park_manifest() -> dict:
    catalog = json.loads(server.LIBRARY_CATALOG.read_text(encoding="utf-8"))
    tracks = [
        track for track in catalog.get("tracks", [])
        if isinstance(track, dict)
        and track.get("status") == "ready"
        and track.get("local_file")
        and Path(str(track["local_file"])).exists()
        and is_linkin_park_track(track)
    ]
    tracks.sort(key=lambda item: (str(item.get("album") or ""), str(item.get("title") or "")))

    if not tracks:
        raise RuntimeError("Nenhuma faixa Linkin Park pronta encontrada em data/library-catalog.json.")

    items = [catalog_track_to_manifest_item(track, index + 1) for index, track in enumerate(tracks)]
    return {
        "source": {
            "kind": "playlist",
            "id": "37i9dQZF1DZ06evO47cwRq",
            "input": "https://open.spotify.com/playlist/37i9dQZF1DZ06evO47cwRq",
            "title": "This Is Linkin Park",
            "url": "https://open.spotify.com/playlist/37i9dQZF1DZ06evO47cwRq",
        },
        "generated_at": server.time.strftime("%Y-%m-%dT%H:%M:%SZ", server.time.gmtime()),
        "notice": "Playlist da radio limitada ao Linkin Park.",
        "library": {
            "scanned_paths": [str(server.LIBRARY_MANAGED), str(server.LIBRARY_INBOX)],
            "audio_files_found": len(items),
            "duplicate_files": [],
        },
        "summary": {
            "spotify_items": len(items),
            "unique_items": len(items),
            "ready": len(items),
            "pending_local_audio": 0,
            "duplicate_spotify_items": 0,
        },
        "items": items,
        "duplicate_spotify_items": [],
    }


def clear_azuracast_playlist_and_imported() -> None:
    station = server.STATION_SHORTCODE
    container = server.AZURACAST_CONTAINER
    imported_dir = f"/var/azuracast/stations/{station}/media/imported"

    sql = "DELETE FROM station_playlist_media WHERE playlist_id=1;"
    db_result = server.run_command([
        "python",
        str(PROJECT_ROOT / "tools" / "query_azuracast_db.py"),
        sql,
    ])
    if db_result.returncode != 0:
        raise RuntimeError(db_result.stderr.strip() or "Falha ao limpar playlist do AzuraCast.")

    wipe_result = server.run_command([
        "docker",
        "exec",
        container,
        "bash",
        "-lc",
        f"rm -rf '{imported_dir}'/* && mkdir -p '{imported_dir}'",
    ])
    if wipe_result.returncode != 0:
        raise RuntimeError(wipe_result.stderr.strip() or "Falha ao limpar pasta imported/ no AzuraCast.")


def sync_linkin_park_only(manifest: dict) -> dict:
    clear_azuracast_playlist_and_imported()
    sync = server.sync_ready_tracks_to_azuracast(manifest)
    link_sql = (
        "INSERT INTO station_playlist_media (playlist_id, media_id, weight, last_played, is_queued, folder_id) "
        "SELECT 1, sm.id, 1, 0, 0, NULL FROM station_media sm "
        "WHERE sm.path LIKE 'imported/%' "
        "AND NOT EXISTS (SELECT 1 FROM station_playlist_media spm WHERE spm.playlist_id=1 AND spm.media_id=sm.id);"
    )
    link_result = server.run_command([
        "python",
        str(PROJECT_ROOT / "tools" / "query_azuracast_db.py"),
        link_sql,
    ])
    if link_result.returncode != 0:
        raise RuntimeError(link_result.stderr.strip() or "Falha ao vincular faixas Linkin Park na playlist.")
    restart = server.run_command([
        "docker",
        "exec",
        server.AZURACAST_CONTAINER,
        "bash",
        "-lc",
        (
            "cd /var/azuracast/www && "
            "php backend/bin/console azuracast:sync:run && "
            f"php backend/bin/console azuracast:radio:restart {server.STATION_SHORTCODE}"
        ),
    ], timeout=120)
    if restart.returncode != 0:
        sync.setdefault("errors", []).append(restart.stderr.strip() or "Falha ao reiniciar radio.")
    return sync


def main() -> int:
    manifest = build_linkin_park_manifest()
    server.DEFAULT_MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    server.write_m3u_from_items(server.DEFAULT_M3U, manifest["items"])

    print(f"Manifesto atualizado: {len(manifest['items'])} faixa(s) Linkin Park.")
    sync = sync_linkin_park_only(manifest)
    print(sync.get("message") or sync)
    if sync.get("errors"):
        for error in sync["errors"]:
            print(f"  aviso: {error}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"Erro: {error}", file=sys.stderr)
        raise SystemExit(1)
