#!/usr/bin/env python3
"""Aguarda efeitos ChatTTS prontos e gera vinhetas Francisca expressivas."""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SFX_DIR = PROJECT_ROOT / "assets" / "narrator-sfx"
REQUIRED_SFX = ("breath.wav", "laugh.wav", "laugh-soft.wav", "sigh.wav", "yawn.wav")
POLL_SEC = 15
MAX_WAIT_SEC = 3600


def sfx_ready() -> bool:
    return all((SFX_DIR / name).exists() for name in REQUIRED_SFX)


def main() -> int:
    print("Aguardando assets/narrator-sfx/ (processo ChatTTS em andamento)...", flush=True)
    print(f"Arquivos necessarios: {', '.join(REQUIRED_SFX)}", flush=True)
    print("(Ctrl+C nao interrompe o download; so este script de espera.)\n", flush=True)

    deadline = time.time() + MAX_WAIT_SEC
    last_list = ""

    while time.time() < deadline:
        if sfx_ready():
            print("\n[ok] Efeitos prontos. Gerando vinhetas Francisca expressivas...\n")
            script = PROJECT_ROOT / "scripts" / "generate-francisca-expressive-samples.py"
            return subprocess.call([sys.executable, str(script)])

        existing = sorted(p.name for p in SFX_DIR.glob("*.wav")) if SFX_DIR.exists() else []
        listing = ", ".join(existing) if existing else "(nenhum ainda)"
        if listing != last_list:
            print(f"  ... {listing}", flush=True)
            last_list = listing

        time.sleep(POLL_SEC)

    print("\n[timeout] Efeitos ainda nao prontos apos 1h.", file=sys.stderr)
    print("Deixe generate-narrator-sfx.py terminar e rode de novo:", file=sys.stderr)
    print("  python scripts\\continue-expressive-narrator.py", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
