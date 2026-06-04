#!/usr/bin/env python3
"""Baixa stingers CC (Mixkit) para assets/radio_imaging/ e copia pro app Flutter."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
MANIFEST = PROJECT_ROOT / "assets" / "radio_imaging" / "manifest.json"
OUT_DIR = MANIFEST.parent
APP_DIR = PROJECT_ROOT / "apps" / "radiopoggers_app" / "assets" / "radio_imaging"


def mixkit_url(mixkit_id: int) -> str:
    return f"https://assets.mixkit.co/active_storage/sfx/{mixkit_id}/{mixkit_id}.wav"


def download(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    print(f"  -> {dest.name} ...", flush=True)
    urllib.request.urlretrieve(url, dest)


def ffmpeg_available() -> bool:
    try:
        subprocess.run(["ffmpeg", "-version"], capture_output=True, check=True)
        return True
    except (FileNotFoundError, subprocess.CalledProcessError):
        return False


def trim_wav(src: Path, dest: Path, max_seconds: float) -> None:
    if not ffmpeg_available():
        if src != dest:
            shutil.copy2(src, dest)
        return
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(src),
            "-t",
            str(max_seconds),
            "-af",
            f"afade=t=out:st={max(0.1, max_seconds - 0.25)}:d=0.25",
            str(dest),
        ],
        capture_output=True,
        check=True,
    )


def main() -> int:
    if not MANIFEST.exists():
        print(f"Manifesto ausente: {MANIFEST}", file=sys.stderr)
        return 1

    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    items = data.get("items") or []
    if not items:
        print("Nenhum item no manifesto.", file=sys.stderr)
        return 1

    tmp = OUT_DIR / "_dl"
    tmp.mkdir(parents=True, exist_ok=True)

    for item in items:
        mid = int(item["mixkit_id"])
        out_name = item["file"]
        raw = tmp / f"{mid}.wav"
        final = OUT_DIR / out_name
        download(mixkit_url(mid), raw)
        max_sec = item.get("max_seconds")
        if max_sec:
            trim_wav(raw, final, float(max_sec))
        else:
            shutil.copy2(raw, final)
        print(f"     OK {final.stat().st_size // 1024} KB", flush=True)

    shutil.rmtree(tmp, ignore_errors=True)

    APP_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copy2(MANIFEST, APP_DIR / "manifest.json")
    for item in items:
        src = OUT_DIR / item["file"]
        shutil.copy2(src, APP_DIR / item["file"])

    print(f"\n[ok] {len(items)} stingers em {OUT_DIR}")
    print(f"[ok] Copiado para {APP_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
