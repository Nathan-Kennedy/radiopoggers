#!/usr/bin/env python3
"""Gera/copia amostras fixas para o botao Ouvir amostra no picker de narradoras."""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SERVER_DIR = PROJECT_ROOT / "tools" / "radiopoggers-server"
OUTPUT_DIR = PROJECT_ROOT / "frontend" / "assets" / "narrator-samples"
GEMINI_DIR = PROJECT_ROOT / "data" / "narrator-voice-tests" / "gemini"

sys.path.insert(0, str(SERVER_DIR))

MIKU_SAMPLES = (
    {"id": "01-track-change", "moment": "track_change", "title": "Rebirth", "artist": "ANGRA"},
    {"id": "02-mid-track", "moment": "mid_track", "title": "Rebirth", "artist": "ANGRA"},
    {"id": "03-vote-pedido", "moment": "vote_library_now", "title": "In The End", "artist": "Linkin Park"},
    {"id": "04-track-night", "moment": "track_change", "title": "Californication", "artist": "Red Hot Chili Peppers"},
    {"id": "05-mid-info", "moment": "mid_info", "title": "Rebirth", "artist": "ANGRA"},
)

HOSHINO_COPIES = (
    {
        "id": "01-vinheta",
        "source": "kore-vinheta-radio.mp3",
        "caption": "Ola, eu sou a Hoshino — voce sintonizou a RADIO NO GRALE!",
    },
    {
        "id": "02-madrugada",
        "source": "kore-expressivo-madrugada.mp3",
        "caption": "Voce ligou na RADIO NO GRALE… fica comigo nessa frequencia.",
    },
    {
        "id": "03-pacote",
        "source": "kore-expressivo-pacote.mp3",
        "caption": "A noite esta pegando fogo e o som esta absurdamente bom!",
    },
    {
        "id": "04-risada",
        "source": "kore-expressivo-risada.mp3",
        "caption": "Risada calorosa de locutora no ar.",
    },
)


def clean_caption(text: str) -> str:
    import re

    cleaned = re.sub(r"\[[^\]]+\]", "", text or "")
    return re.sub(r"\s+", " ", cleaned).strip()


def write_mp3(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)


def generate_miku_samples() -> list[dict[str, str]]:
    from miku_narrator import generate_miku_narration

    miku_dir = OUTPUT_DIR / "miku"
    miku_dir.mkdir(parents=True, exist_ok=True)
    entries: list[dict[str, str]] = []

    for sample in MIKU_SAMPLES:
        result = generate_miku_narration(
            title=sample["title"],
            artist=sample["artist"],
            moment=sample["moment"],
        )
        filename = f"{sample['id']}.mp3"
        target = miku_dir / filename
        write_mp3(target, result["audio"])
        entries.append(
            {
                "file": f"miku/{filename}",
                "caption": clean_caption(str(result.get("text") or "")),
            }
        )
        print(f"[miku] {filename} — {entries[-1]['caption'][:72]}...")

    return entries


def generate_hoshino_extra(target: Path) -> str:
    from hoshino_narrator import generate_hoshino_narration

    result = generate_hoshino_narration(
        title="Rebirth",
        artist="ANGRA",
        moment="track_change",
    )
    write_mp3(target, result["audio"])
    return clean_caption(str(result.get("text") or ""))


def copy_hoshino_samples() -> list[dict[str, str]]:
    hoshino_dir = OUTPUT_DIR / "hoshino"
    hoshino_dir.mkdir(parents=True, exist_ok=True)
    entries: list[dict[str, str]] = []

    for sample in HOSHINO_COPIES:
        filename = f"{sample['id']}.mp3"
        target = hoshino_dir / filename

        if sample.get("generate"):
            try:
                caption = generate_hoshino_extra(target)
                print(f"[hoshino] {filename} — gerado via Gemini")
            except Exception as error:
                source = GEMINI_DIR / str(sample["source"])
                shutil.copy2(source, target)
                caption = str(sample["caption"])
                print(f"[hoshino] {filename} — fallback copia ({error})")
        else:
            source = GEMINI_DIR / str(sample["source"])
            if not source.is_file():
                raise FileNotFoundError(f"Arquivo Hoshino ausente: {source}")
            shutil.copy2(source, target)
            caption = str(sample["caption"])
            print(f"[hoshino] {filename} — copiado")

        entries.append({"file": f"hoshino/{filename}", "caption": caption})

    extra_target = hoshino_dir / "05-track-change.mp3"
    try:
        extra_caption = generate_hoshino_extra(extra_target)
        print("[hoshino] 05-track-change.mp3 — gerado via Gemini")
    except Exception as error:
        fallback = GEMINI_DIR / "kore-vinheta-radio.mp3"
        shutil.copy2(fallback, extra_target)
        extra_caption = "Ola, eu sou a Hoshino — voce esta ouvindo a RADIO NO GRALE."
        print(f"[hoshino] 05-track-change.mp3 — fallback copia ({error})")
    entries.append({"file": "hoshino/05-track-change.mp3", "caption": extra_caption})

    return entries


def main() -> int:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    manifest = {
        "purpose": "Amostras fixas do picker de narradoras (sem gerar audio no clique).",
        "miku": generate_miku_samples(),
        "hoshino": copy_hoshino_samples(),
    }

    manifest_path = OUTPUT_DIR / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nManifesto: {manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
