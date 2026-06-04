from __future__ import annotations

import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen


def fetch_json(url: str, timeout: float = 12.0) -> dict[str, Any]:
    request = Request(url, headers={"Accept": "application/json", "User-Agent": "RadioPoggersDiscordBot/1.0"})
    with urlopen(request, timeout=timeout) as response:
        payload = response.read().decode("utf-8")
    data = json.loads(payload)
    return data if isinstance(data, dict) else {}


def post_json(url: str, body: dict[str, Any], timeout: float = 120.0) -> dict[str, Any]:
    encoded = json.dumps(body, ensure_ascii=False).encode("utf-8")
    request = Request(
        url,
        data=encoded,
        method="POST",
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "RadioPoggersDiscordBot/1.0",
        },
    )
    with urlopen(request, timeout=timeout) as response:
        payload = response.read().decode("utf-8")
    data = json.loads(payload)
    return data if isinstance(data, dict) else {}


def inspect_spotify(api_base: str, spotify_url: str) -> dict[str, Any]:
    return fetch_json(f"{api_base}/api/import-spotify/inspect?spotifyUrl={quote(spotify_url, safe='')}")


def play_spotify_if_ready(api_base: str, spotify_url: str) -> dict[str, Any]:
    return post_json(f"{api_base}/api/discord/play-spotify", {"spotifyUrl": spotify_url})


def start_spotify_import(api_base: str, spotify_url: str) -> dict[str, Any]:
    return post_json(f"{api_base}/api/import-spotify", {"spotifyUrl": spotify_url}, timeout=30.0)


def spotify_import_status(api_base: str, job_id: str) -> dict[str, Any]:
    return fetch_json(f"{api_base}/api/import-spotify/status?job_id={quote(job_id, safe='')}")


def play_track_immediate(api_base: str, track_id: str) -> dict[str, Any]:
    return post_json(f"{api_base}/api/discord/play-track", {"track_id": track_id})


def resolve_play_query(api_base: str, query: str) -> dict[str, Any]:
    return fetch_json(f"{api_base}/api/discord/resolve-query?q={quote(query, safe='')}")


def skip_track(api_base: str) -> dict[str, Any]:
    return post_json(f"{api_base}/api/discord/skip", {})


def send_heartbeat(api_base: str, listener_id: str, playing: bool) -> None:
    try:
        post_json(
            f"{api_base}/api/audience/heartbeat",
            {"listener_id": listener_id, "playing": playing},
            timeout=8.0,
        )
    except (HTTPError, URLError, TimeoutError, ValueError):
        pass
