#!/usr/bin/env python3
"""Gera e cacheia risadas/bocejos/suspiros em assets/narrator-sfx/ via ChatTTS."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SERVER_DIR = PROJECT_ROOT / "tools" / "radiopoggers-server"
sys.path.insert(0, str(SERVER_DIR))

from expressive_francisca import ExpressiveFranciscaEngine, SFX_DIR  # noqa: E402
from nonverbal_engine import CHATTTS_EXPRESSIVE  # noqa: E402


def main() -> int:
    print("Gerando efeitos nao-verbais (ChatTTS + recorte de risada real)...")
    print("Primeira execucao baixa o modelo (~1-2 GB).\n")

    try:
        from huggingface_hub import snapshot_download
        from expressive_francisca import CHATTTS_CACHE

        CHATTTS_CACHE.mkdir(parents=True, exist_ok=True)
        print("Baixando/retomando modelo 2Noise/ChatTTS...")
        snapshot_download(
            repo_id="2Noise/ChatTTS",
            allow_patterns=["*.yaml", "*.json", "*.safetensors"],
            cache_dir=str(CHATTTS_CACHE),
        )
        print("Modelo no cache.\n")
    except Exception as error:
        print(f"Aviso no prefetch: {error}\n")

    if SFX_DIR.exists():
        for old in SFX_DIR.glob("*.wav"):
            if old.stat().st_size < 8000:
                old.unlink()
                print(f"  removido cache antigo curto: {old.name}")

    engine = ExpressiveFranciscaEngine(force_regenerate_sfx=True)
    SFX_DIR.mkdir(parents=True, exist_ok=True)

    for tag in CHATTTS_EXPRESSIVE:
        out = SFX_DIR / f"{tag.replace(':', '-')}.wav"
        if out.exists() and out.stat().st_size > 8000:
            print(f"  [skip] {tag} (ja existe)")
            continue
        print(f"  -> {tag} ...")
        pcm, duration_ms = engine.synthesize_nonverbal(tag)
        out = SFX_DIR / f"{tag.replace(':', '-')}.wav"
        print(f"     OK {duration_ms}ms -> {out.name}")

    print(f"\nEfeitos salvos em: {SFX_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
