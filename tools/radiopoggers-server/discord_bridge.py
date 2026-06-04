"""Pontes Discord → radio (sem alterar fluxo do site)."""

from __future__ import annotations

from typing import Any


def discord_skip_track() -> dict[str, Any]:
    from server import skip_current_track

    return skip_current_track()


def discord_play_track_immediate(track_id: str) -> dict[str, Any]:
    from server import find_track_in_catalog_by_id, load_library_catalog, play_track_immediately_on_radio

    safe_id = str(track_id or "").strip()
    if not safe_id:
        raise RuntimeError("track_id ausente.")

    catalog = load_library_catalog(refresh=True)
    track = find_track_in_catalog_by_id(catalog, safe_id)
    if not track:
        raise RuntimeError("Faixa nao encontrada no catalogo local.")

    result = play_track_immediately_on_radio(track)
    result["track_id"] = safe_id
    result["title"] = track.get("title")
    result["artist"] = ", ".join(track.get("artists") or []) or track.get("artist", "")
    return result


def discord_play_spotify_if_ready(spotify_url: str) -> dict[str, Any]:
    from server import (
        first_ready_track_payload,
        inspect_spotify_import,
        load_cached_manifest_for_spotify_url,
        spotify_import_is_cached_ready,
        validate_spotify_url,
    )

    safe_url = validate_spotify_url(spotify_url)
    inspect = inspect_spotify_import(safe_url)

    if not spotify_import_is_cached_ready(safe_url):
        return {
            "ok": True,
            "ready": False,
            "need_import": True,
            "inspect": inspect,
        }

    manifest = load_cached_manifest_for_spotify_url(safe_url) or inspect.get("manifest") or {}
    payload = first_ready_track_payload(manifest if isinstance(manifest, dict) else {})
    if not payload:
        raise RuntimeError("Playlist importada, mas nenhuma faixa pronta foi encontrada.")

    played = discord_play_track_immediate(str(payload.get("track_id") or payload.get("first_track_id") or ""))
    played["ready"] = True
    played["need_import"] = False
    played["playlist_title"] = payload.get("playlist_title") or inspect.get("playlist_title") or ""
    return played


def discord_resolve_query(query: str) -> dict[str, Any]:
    from spotify_search import resolve_play_query

    target = resolve_play_query(query)
    target["ok"] = True
    target["query"] = str(query or "").strip()
    return target


def discord_play_query(query: str) -> dict[str, Any]:
    target = discord_resolve_query(query)
    source = str(target.get("source") or "")

    if source == "library":
        played = discord_play_track_immediate(str(target.get("track_id") or ""))
        played["resolved"] = target
        played["need_import"] = False
        played["ready"] = True
        return played

    spotify_url = str(target.get("spotify_url") or "").strip()
    if not spotify_url:
        raise RuntimeError("Busca nao retornou URL Spotify.")

    played = discord_play_spotify_if_ready(spotify_url)
    played["resolved"] = target
    if played.get("need_import"):
        return played

    played["title"] = played.get("title") or target.get("title")
    played["artist"] = played.get("artist") or target.get("artist")
    return played
