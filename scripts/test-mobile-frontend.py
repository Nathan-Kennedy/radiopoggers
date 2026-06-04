#!/usr/bin/env python3
"""Auditoria dos recursos do frontend via IP LAN (simula celular na mesma Wi-Fi)."""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

LAN = os.environ.get("RADIOPOGGERS_TEST_LAN", "192.168.2.7")
FE = f"http://{LAN}:5500"
API = f"http://{LAN}:8765"
AZ = f"http://{LAN}"
UA = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
)


def get(url: str, *, timeout: float = 12.0, accept: str = "*/*") -> tuple[int | None, str, bytes, str]:
    req = urllib.request.Request(url, headers={"Accept": accept, "User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return response.status, response.headers.get("Content-Type", ""), response.read(), ""
    except Exception as error:
        return None, "", b"", str(error)


def main() -> int:
    results: list[tuple[str, bool, str]] = []

    def record(name: str, ok: bool, detail: str = "") -> None:
        results.append((name, ok, detail))

    status, _, body, err = get(f"{FE}/frontend/config.js")
    text = body.decode("utf-8", errors="replace") if body else ""
    record("config.js carrega", status == 200, err or f"HTTP {status}")
    record("config aponta pro LAN", f"http://{LAN}:8765" in text and f"http://{LAN}/hls/" in text)
    record("config sem localhost", "localhost" not in text and "127.0.0.1" not in text)

    assets = [
        "frontend/index.html",
        "frontend/app.js",
        "frontend/styles.css",
        "frontend/sw.js",
        "frontend/manifest.webmanifest",
        "frontend/vendor/hls.min.js",
        "frontend/ascii-guitarist.js",
        "frontend/assets/ascii-frames.json",
        "frontend/assets/ascii-frames%20falando.json",
        "frontend/assets/img/cover-fallback.svg",
        "frontend/assets/icons/icon.svg",
    ]
    for asset in assets:
        status, content_type, _, err = get(f"{FE}/{asset}")
        label = asset.rsplit("/", 1)[-1]
        record(f"asset {label}", status == 200, err or content_type[:40])

    api_paths = [
        "/api/health",
        "/api/nowplaying",
        "/api/library?limit=3",
        "/api/library/filters",
        "/api/manifest",
        "/api/miku/status",
        "/api/voice-drop/active",
        "/api/audience/count",
        "/api/vote/active",
    ]
    for path in api_paths:
        status, _, _, err = get(f"{API}{path}", accept="application/json")
        record(f"API {path.split('?')[0]}", status == 200, err or f"HTTP {status}")

    status, _, lib_body, err = get(f"{API}/api/library?limit=1", accept="application/json")
    if status == 200 and lib_body:
        tracks = json.loads(lib_body.decode()).get("tracks") or []
        if tracks:
            track_id = tracks[0].get("id") or tracks[0].get("spotify_id")
            preview_status, preview_type, _, preview_err = get(
                f"{API}/api/library/preview/{track_id}",
                accept="audio/*",
            )
            record(
                "API preview de audio",
                preview_status == 200 and "audio" in preview_type,
                preview_err or preview_type,
            )

    status, content_type, body, err = get(f"{AZ}/hls/radio-no-grale/live.m3u8")
    record("Stream HLS manifest", status == 200 and body.startswith(b"#EXTM3U"), err or content_type)

    status, _, html, err = get(f"{FE}/frontend/index.html")
    html_text = html.decode("utf-8", errors="replace") if html else ""
    record("HTML viewport mobile", "width=device-width" in html_text, err)
    for element_id in [
        "playButton",
        "skipTrackButton",
        "libraryList",
        "voteOverlay",
        "voteDirectModal",
        "voiceDropButton",
        "spotifyImportForm",
        "librarySearchInput",
        "libraryRequestButton",
        "libraryClearCustomButton",
        "shelfPreviewStop",
    ]:
        record(f"UI #{element_id}", f'id="{element_id}"' in html_text)

    status, _, manifest_body, err = get(f"{FE}/frontend/manifest.webmanifest")
    if status == 200 and manifest_body:
        manifest = json.loads(manifest_body.decode())
        record("PWA manifest", bool(manifest.get("name")) and bool(manifest.get("icons")), manifest.get("display", ""))
    else:
        record("PWA manifest", False, err)

    passed = sum(1 for _, ok, _ in results if ok)
    failed = [(name, detail) for name, ok, detail in results if not ok]

    print(f"Auditoria mobile (LAN {LAN}): {passed}/{len(results)} OK\n")
    for name, ok, detail in results:
        mark = "OK" if ok else "FAIL"
        suffix = f" — {detail}" if detail else ""
        print(f"  [{mark}] {name}{suffix}")

    if failed:
        print(f"\n{len(failed)} falha(s).")
        return 1

    print("\nTodos os recursos testados responderam pelo IP da rede.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
