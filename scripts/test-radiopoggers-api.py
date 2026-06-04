#!/usr/bin/env python3
"""
Testes HTTP da API local RadioPoggers e dependencias opcionais (AzuraCast, frontend).
Uso: python scripts/test-radiopoggers-api.py
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass, field

API_BASE = os.environ.get("RADIOPOGGERS_TEST_API", "http://127.0.0.1:8765").rstrip("/")
AZURACAST_BASE = os.environ.get("RADIOPOGGERS_TEST_AZURACAST", "http://localhost").rstrip("/")
FRONTEND_BASE = os.environ.get("RADIOPOGGERS_TEST_FRONTEND", "http://localhost:5500").rstrip("/")


@dataclass
class Result:
    name: str
    ok: bool
    detail: str = ""
    skipped: bool = False


@dataclass
class Suite:
    results: list[Result] = field(default_factory=list)

    def add(self, name: str, ok: bool, detail: str = "", *, skipped: bool = False) -> None:
        self.results.append(Result(name=name, ok=ok, detail=detail, skipped=skipped))

    @property
    def failed(self) -> int:
        return sum(1 for r in self.results if not r.ok and not r.skipped)

    @property
    def passed(self) -> int:
        return sum(1 for r in self.results if r.ok)

    @property
    def skipped(self) -> int:
        return sum(1 for r in self.results if r.skipped)


def fetch(
    url: str,
    *,
    method: str = "GET",
    body: dict | None = None,
    timeout: float = 12.0,
) -> tuple[int | None, dict | str | None, str | None]:
    headers = {"Accept": "application/json"}
    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            status = resp.status
            if not raw:
                return status, None, None
            try:
                return status, json.loads(raw.decode("utf-8")), None
            except json.JSONDecodeError:
                return status, raw.decode("utf-8", errors="replace")[:200], None
    except urllib.error.HTTPError as exc:
        err_body = exc.read().decode("utf-8", errors="replace")[:300]
        return exc.code, err_body, str(exc)
    except Exception as exc:
        return None, None, str(exc)


def test_api_health(suite: Suite) -> None:
    status, data, err = fetch(f"{API_BASE}/api/health")
    if err:
        suite.add("API /api/health", False, err)
        return
    ok = status == 200 and isinstance(data, dict) and data.get("ok", True) is not False
    suite.add("API /api/health", ok, f"HTTP {status}")


def test_api_nowplaying(suite: Suite) -> None:
    status, data, err = fetch(f"{API_BASE}/api/nowplaying")
    if err:
        suite.add("API /api/nowplaying", False, err)
        return
    title = ""
    if isinstance(data, dict):
        np = data.get("now_playing") or data.get("nowPlaying") or {}
        song = np.get("song") or {}
        title = str(song.get("title") or song.get("text") or "")[:60]
    ok = status == 200 and isinstance(data, dict)
    suite.add("API /api/nowplaying", ok, title or f"HTTP {status}")


def test_api_manifest(suite: Suite) -> None:
    status, data, err = fetch(f"{API_BASE}/api/manifest", timeout=60)
    if err:
        suite.add("API /api/manifest", False, err)
        return
    count = 0
    if isinstance(data, dict):
        tracks = data.get("tracks") or data.get("items") or []
        if isinstance(tracks, list):
            count = len(tracks)
    ok = status == 200 and isinstance(data, dict)
    suite.add("API /api/manifest", ok, f"{count} faixas" if count else f"HTTP {status}")


def test_api_library(suite: Suite) -> None:
    status, data, err = fetch(f"{API_BASE}/api/library?limit=5", timeout=45)
    if err:
        suite.add("API /api/library", False, err)
        return
    total = 0
    if isinstance(data, dict):
        total = int(data.get("total") or len(data.get("tracks") or []) or 0)
    ok = status == 200 and isinstance(data, dict)
    suite.add("API /api/library", ok, f"total={total}" if total else f"HTTP {status}")


def test_api_library_filters(suite: Suite) -> None:
    status, data, err = fetch(f"{API_BASE}/api/library/filters", timeout=30)
    if err:
        suite.add("API /api/library/filters", False, err)
        return
    artists = 0
    if isinstance(data, dict):
        artists = len(data.get("artists") or [])
    ok = status == 200 and isinstance(data, dict)
    suite.add("API /api/library/filters", ok, f"{artists} artistas" if artists else f"HTTP {status}")


def test_api_library_preview(suite: Suite) -> None:
    status, lib, err = fetch(f"{API_BASE}/api/library?limit=1", timeout=45)
    if err or not isinstance(lib, dict):
        suite.add("API /api/library/preview", False, err or "sem biblioteca")
        return
    tracks = lib.get("tracks") or []
    if not tracks:
        suite.add("API /api/library/preview", True, "sem faixas (skip preview)", skipped=True)
        return
    track_id = tracks[0].get("id") or tracks[0].get("track_id")
    if not track_id:
        suite.add("API /api/library/preview", False, "faixa sem id")
        return
    url = f"{API_BASE}/api/library/preview/{track_id}"
    req = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            ctype = resp.headers.get("Content-Type", "")
            ok = resp.status == 200 and ("audio" in ctype or "octet" in ctype)
            suite.add("API /api/library/preview", ok, f"HTTP {resp.status} {ctype[:40]}")
    except Exception as exc:
        suite.add("API /api/library/preview", False, str(exc))


def test_api_miku_status(suite: Suite) -> None:
    status, data, err = fetch(f"{API_BASE}/api/miku/status")
    if err:
        suite.add("API /api/miku/status", False, err)
        return
    engine = ""
    if isinstance(data, dict):
        engine = str(data.get("tts") or data.get("engine") or "")
    ok = status == 200
    suite.add("API /api/miku/status", ok, engine or f"HTTP {status}")


def test_api_voice_drop_active(suite: Suite) -> None:
    status, data, err = fetch(f"{API_BASE}/api/voice-drop/active")
    if err:
        suite.add("API /api/voice-drop/active", False, err)
        return
    ok = status == 200
    suite.add("API /api/voice-drop/active", ok, f"HTTP {status}")


def test_api_audience(suite: Suite) -> None:
    status, data, err = fetch(f"{API_BASE}/api/audience/count")
    if err:
        suite.add("API /api/audience/count", False, err)
        return
    ok = status == 200 and isinstance(data, dict) and "eligible" in data
    detail = ""
    if isinstance(data, dict):
        detail = f"eligible={data.get('eligible')} total={data.get('total_on_site')}"
    suite.add("API /api/audience/count", ok, detail)


def test_api_vote_active(suite: Suite) -> None:
    status, data, err = fetch(f"{API_BASE}/api/vote/active")
    if err:
        suite.add("API /api/vote/active", False, err)
        return
    ok = status == 200
    phase = ""
    if isinstance(data, dict) and data.get("vote"):
        phase = str(data["vote"].get("phase") or "")
    suite.add("API /api/vote/active", ok, phase or "sem votacao")


def test_api_import_inspect(suite: Suite) -> None:
    status, data, err = fetch(
        f"{API_BASE}/api/import-spotify/inspect?url=https://open.spotify.com/playlist/37i9dQZF1DZ06evO4zuVE2",
        timeout=30,
    )
    if err:
        suite.add("API /api/import-spotify/inspect", False, err)
        return
    ok = status == 200 and isinstance(data, dict)
    ready = data.get("ready") if isinstance(data, dict) else None
    suite.add("API /api/import-spotify/inspect", ok, f"ready={ready}" if ready is not None else f"HTTP {status}")


def test_api_vote_flow(suite: Suite) -> None:
    hb_status, _, hb_err = fetch(
        f"{API_BASE}/api/audience/heartbeat",
        method="POST",
        body={"listener_id": "test-suite-proposer", "playing": True},
    )
    if hb_err:
        suite.add("API votacao heartbeat", False, hb_err)
        return
    suite.add("API votacao heartbeat", hb_status == 200, f"HTTP {hb_status}")

    start_status, start_data, start_err = fetch(
        f"{API_BASE}/api/vote/start",
        method="POST",
        body={
            "type": "skip_track",
            "proposer_id": "test-suite-proposer",
            "payload": {},
        },
    )
    if start_err:
        suite.add("API /api/vote/start", False, start_err)
        return

    conflict = start_status == 409
    if isinstance(start_data, str) and "andamento" in start_data.lower():
        conflict = True
    if conflict:
        active_status, active_data, _ = fetch(f"{API_BASE}/api/vote/active")
        vote_id = None
        if active_status == 200 and isinstance(active_data, dict) and active_data.get("vote"):
            vote_id = active_data["vote"].get("id")
        suite.add("API /api/vote/start", True, "votacao ja aberta (ok)")
        if vote_id:
            cast_status, _, cast_err = fetch(
                f"{API_BASE}/api/vote/cast",
                method="POST",
                body={
                    "vote_id": vote_id,
                    "listener_id": "test-suite-proposer",
                    "choice": "no",
                },
            )
            suite.add(
                "API /api/vote/cast",
                cast_err is None and cast_status == 200,
                cast_err or f"HTTP {cast_status}",
            )
        return

    vote_id = None
    if isinstance(start_data, dict):
        vote = start_data.get("vote") or start_data
        vote_id = vote.get("id") if isinstance(vote, dict) else None

    ok_start = start_status == 200 and vote_id
    suite.add("API /api/vote/start", ok_start, vote_id or f"HTTP {start_status}")

    if not vote_id:
        return

    cast_status, _, cast_err = fetch(
        f"{API_BASE}/api/vote/cast",
        method="POST",
        body={
            "vote_id": vote_id,
            "listener_id": "test-suite-proposer",
            "choice": "no",
        },
    )
    suite.add("API /api/vote/cast", cast_err is None and cast_status == 200, cast_err or f"HTTP {cast_status}")


def test_azuracast_optional(suite: Suite) -> None:
    status, data, err = fetch(f"{AZURACAST_BASE}/api/nowplaying/1", timeout=8)
    if err:
        suite.add("AzuraCast nowplaying/1", False, err, skipped=True)
        return
    title = ""
    if isinstance(data, dict):
        np = data.get("now_playing") or {}
        song = np.get("song") or {}
        title = str(song.get("title") or "")[:50]
    suite.add("AzuraCast nowplaying/1", status == 200, title or f"HTTP {status}")


def test_hls_optional(suite: Suite) -> None:
    url = f"{AZURACAST_BASE}/hls/radio-no-grale/live.m3u8"
    req = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            ok = resp.status == 200
            suite.add("AzuraCast HLS m3u8", ok, f"HTTP {resp.status}")
    except Exception as exc:
        suite.add("AzuraCast HLS m3u8", False, str(exc), skipped=True)


def test_frontend_optional(suite: Suite) -> None:
    url = f"{FRONTEND_BASE}/frontend/index.html"
    req = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=6) as resp:
            body = resp.read(12000).decode("utf-8", errors="replace")
            ok = resp.status == 200 and "RADIO NO GRALE" in body.upper()
            suite.add("Frontend index.html", ok, f"HTTP {resp.status}")
    except Exception as exc:
        suite.add("Frontend index.html", False, str(exc), skipped=True)


def test_ascii_assets(suite: Suite) -> None:
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    assets = [
        "frontend/assets/ascii-frames.json",
        "frontend/assets/ascii-frames sentado.json",
        "frontend/assets/ascii-frames off.json",
        "frontend/assets/ascii-animation off.gif",
        "frontend/ascii-guitarist.js",
    ]
    missing = [a for a in assets if not os.path.isfile(os.path.join(root, a.replace("/", os.sep)))]
    suite.add("Assets ASCII (disco)", len(missing) == 0, "faltando: " + ", ".join(missing) if missing else "ok")


def main() -> int:
    suite = Suite()
    print(f"RadioPoggers API tests — {API_BASE}\n")

    test_api_health(suite)
    api_up = suite.results and suite.results[0].ok

    if not api_up:
        print("API local offline. Suba: .\\scripts\\start-local-api.ps1\n")
        for r in suite.results:
            mark = "SKIP" if r.skipped else ("OK" if r.ok else "FAIL")
            print(f"  [{mark}] {r.name}: {r.detail}")
        return 2

    test_api_nowplaying(suite)
    test_api_manifest(suite)
    test_api_library(suite)
    test_api_library_filters(suite)
    test_api_library_preview(suite)
    test_api_miku_status(suite)
    test_api_voice_drop_active(suite)
    test_api_audience(suite)
    test_api_vote_active(suite)
    test_api_import_inspect(suite)
    test_api_vote_flow(suite)
    test_azuracast_optional(suite)
    test_hls_optional(suite)
    test_frontend_optional(suite)
    test_ascii_assets(suite)

    print("")
    for r in suite.results:
        if r.skipped:
            mark = "SKIP"
        elif r.ok:
            mark = "OK"
        else:
            mark = "FAIL"
        line = f"  [{mark}] {r.name}"
        if r.detail:
            line += f" — {r.detail}"
        print(line)

    print(f"\nResumo: {suite.passed} ok, {suite.failed} falha, {suite.skipped} skip/condicional")
    return 1 if suite.failed else 0


if __name__ == "__main__":
    sys.exit(main())
