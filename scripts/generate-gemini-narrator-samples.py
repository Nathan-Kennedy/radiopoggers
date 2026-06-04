#!/usr/bin/env python3
"""Gera amostras de narradora feminina via Gemini TTS (risadas nativas, pt-BR)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SERVER_DIR = PROJECT_ROOT / "tools" / "radiopoggers-server"
OUTPUT_DIR = PROJECT_ROOT / "data" / "narrator-voice-tests" / "gemini"
sys.path.insert(0, str(SERVER_DIR))

from gemini_narrator import (  # noqa: E402
    FEMALE_VOICES,
    STYLE_LOCUTORA,
    synthesize_gemini_mp3,
)

VINHETA_RADIO = (
    "Olá, ouvinte lindo! Você sintonizou na Rádio no Grale, a Alta Cúpula que não te deixa ficar parado! "
    "[short pause] A noite está pegando fogo, o som está absurdamente bom, "
    "e eu estou aqui só pra te manter colado nessa frequência. "
    "Reaja com uma risada calorosa e divertida. [laughing] "
    "Vira o volume, sente o grave… e vem comigo até o amanhecer! [laughing]"
)

EXPRESSIVE_DEMOS = [
    {
        "id": "expressivo-risada",
        "label": "Teste de risada (Kore)",
        "voice": "Kore",
        "text": (
            "Reaja com uma risada feminina calorosa e sedutora, como locutora de radio. "
            "[laughing] [laughing]"
        ),
    },
    {
        "id": "expressivo-madrugada",
        "label": "Suspiro + pausa (Kore)",
        "voice": "Kore",
        "text": (
            "Você ligou na Rádio no Grale… fala baixinho, íntima, cansada mas sedutora. "
            "[sigh] [medium pause] Fica comigo nessa frequência… [short pause] não desliga."
        ),
    },
    {
        "id": "expressivo-pacote",
        "label": "Pacote completo (Kore)",
        "voice": "Kore",
        "text": VINHETA_RADIO,
    },
]


def main() -> int:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    manifest: dict = {
        "engine": "Google Gemini TTS (gemini-2.5-flash-preview-tts)",
        "language": "pt-BR",
        "style": STYLE_LOCUTORA,
        "tags_doc": "[laughing], [sigh], [short pause], [medium pause], [long pause], [whispering]",
        "samples": [],
    }

    print("Gemini TTS — gerando amostras femininas (pt-BR + risadas nativas)\n")

    for voice in FEMALE_VOICES:
        out_name = f"{voice['id']}-vinheta-radio.mp3"
        print(f"  -> {voice['label']} ...")
        mp3, _, model = synthesize_gemini_mp3(
            text=VINHETA_RADIO,
            voice_name=voice["name"],
        )
        out_path = OUTPUT_DIR / out_name
        out_path.write_bytes(mp3)
        manifest["samples"].append(
            {
                "id": voice["id"],
                "label": voice["label"],
                "voice": voice["name"],
                "file": out_name,
                "script": VINHETA_RADIO,
                "model": model,
            }
        )
        print(f"     OK -> {out_name}")

    print("\n  Testes expressivos (Kore):\n")
    for demo in EXPRESSIVE_DEMOS:
        out_name = f"kore-{demo['id']}.mp3"
        print(f"  -> {demo['label']} ...")
        mp3, _, model = synthesize_gemini_mp3(
            text=demo["text"],
            voice_name=demo["voice"],
        )
        out_path = OUTPUT_DIR / out_name
        out_path.write_bytes(mp3)
        manifest["samples"].append({**demo, "file": out_name, "model": model})
        print(f"     OK -> {out_name}")

    (OUTPUT_DIR / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (OUTPUT_DIR / "index.html").write_text(_build_html(manifest), encoding="utf-8")

    print(f"\nPasta: {OUTPUT_DIR}")
    print("Ouvir: abra index.html no Explorer ou rode .\\scripts\\open-gemini-player.ps1")
    return 0


def _build_html(manifest: dict) -> str:
    cards = []
    for sample in manifest["samples"]:
        cards.append(
            f"""
        <article class="card">
          <h2>{sample.get("label", sample.get("id", ""))}</h2>
          <p class="meta">Voz: {sample.get("voice", "?")} · {sample.get("model", "")}</p>
          <p class="script">{sample.get("script", sample.get("text", ""))}</p>
          <audio controls preload="metadata" src="{sample["file"]}"></audio>
        </article>"""
        )
    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Gemini TTS — narradora | Radio no Grale</title>
  <style>
    body {{ font-family: system-ui, sans-serif; background:#0a0f14; color:#e8eef5; margin:0; padding:1.5rem; max-width:760px; margin-inline:auto; }}
    h1 {{ color:#8ab4f8; font-size:1.3rem; }}
    .intro {{ opacity:.88; line-height:1.5; font-size:.92rem; }}
    .card {{ background:#141b24; border:1px solid #2a3a4d; border-radius:12px; padding:1rem 1.2rem; margin:1rem 0; }}
    .meta {{ font-size:.75rem; opacity:.7; margin:0; }}
    .script {{ font-size:.78rem; opacity:.75; font-style:italic; line-height:1.4; }}
    audio {{ width:100%; margin-top:.6rem; }}
  </style>
</head>
<body>
  <h1>Gemini TTS — 5 vozes femininas + risadas nativas</h1>
  <p class="intro">
    Google Gemini (plano Pro / API). Tags reais: <strong>[laughing]</strong>, <strong>[sigh]</strong>, pausas.
    Abra este arquivo direto no navegador (nao precisa do servidor :5500).
  </p>
  {"".join(cards)}
</body>
</html>"""


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RuntimeError as error:
        print(f"Erro: {error}", file=sys.stderr)
        raise SystemExit(1)
