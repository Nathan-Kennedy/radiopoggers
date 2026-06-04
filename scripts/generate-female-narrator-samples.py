#!/usr/bin/env python3
"""
Gera 5 amostras de narradora feminina (separado da Miku) para escolha da voz.
Usa edge-tts (Microsoft Neural). Saida: data/narrator-voice-tests/
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = PROJECT_ROOT / "data" / "narrator-voice-tests"

SAMPLE_TEXT = (
    "Olá, ouvinte lindo! Você sintonizou na Rádio no Grale, a Alta Cúpula que não te deixa ficar parado! "
    "A noite está pegando fogo, o som está absurdamente bom, e eu estou aqui só pra te manter colado nessa frequência. "
    "Vira o volume, sente o grave, deixa o corpo balançar… e vem comigo até o amanhecer! Hã-hã!"
)

# Cinco perfis distintos: timbre + prosódia de locutora sedutora/animada
VOICE_CANDIDATES = [
    {
        "id": "01-francisca-locutora-quente",
        "label": "Francisca — locutora FM quente (BR)",
        "voice": "pt-BR-FranciscaNeural",
        "rate": "+6%",
        "pitch": "-2Hz",
        "description": "Voz brasileira clássica de rádio; grave suave, tom acolhedor e sedutor.",
    },
    {
        "id": "02-thalita-animada-brilhante",
        "label": "Thalita — animada e brilhante (BR)",
        "voice": "pt-BR-ThalitaMultilingualNeural",
        "rate": "+14%",
        "pitch": "+4Hz",
        "description": "Mais jovem e elétrica; boa para vinhetas com energia e sorriso na voz.",
    },
    {
        "id": "03-raquel-elegante-sedutora",
        "label": "Raquel — elegante sedutora (PT)",
        "voice": "pt-PT-RaquelNeural",
        "rate": "-4%",
        "pitch": "-3Hz",
        "description": "Tom europeu sofisticado; pausada, charmosa, estilo locutora noturna.",
    },
    {
        "id": "04-ava-multilingual-ousada",
        "label": "Ava — multilingual ousada (EN/PT)",
        "voice": "en-US-AvaMultilingualNeural",
        "rate": "+8%",
        "pitch": "+1Hz",
        "description": "Timbre internacional; firme e confiante, leitura natural do português.",
    },
    {
        "id": "05-emma-multilingual-suave",
        "label": "Emma — multilingual suave (EN/PT)",
        "voice": "en-US-EmmaMultilingualNeural",
        "rate": "+2%",
        "pitch": "-4Hz",
        "description": "Mais doce e íntima; sussurro de locutora, ideal para chamadas sedutoras.",
    },
]


async def synthesize_sample(
    *,
    voice: str,
    text: str,
    rate: str,
    pitch: str,
    output_path: Path,
) -> None:
    import edge_tts

    communicate = edge_tts.Communicate(text, voice, rate=rate, pitch=pitch)
    await communicate.save(str(output_path))


async def main() -> int:
    try:
        import edge_tts  # noqa: F401
    except ImportError:
        print("Instale edge-tts: python -m pip install edge-tts", file=sys.stderr)
        return 1

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    manifest: dict = {
        "purpose": "Testes de narradora feminina — Radio no Grale (separado da Miku)",
        "sample_text": SAMPLE_TEXT,
        "backend": "edge-tts",
        "samples": [],
    }

    print(f"Texto de exemplo:\n{SAMPLE_TEXT}\n")
    print(f"Gerando em {OUTPUT_DIR}\n")

    for item in VOICE_CANDIDATES:
        filename = f"{item['id']}.mp3"
        out_path = OUTPUT_DIR / filename
        print(f"  -> {item['label']} ...")
        await synthesize_sample(
            voice=item["voice"],
            text=SAMPLE_TEXT,
            rate=item["rate"],
            pitch=item["pitch"],
            output_path=out_path,
        )
        size_kb = out_path.stat().st_size // 1024
        manifest["samples"].append(
            {
                **item,
                "file": filename,
                "size_kb": size_kb,
            }
        )
        print(f"     OK ({size_kb} KB) -> {out_path.name}")

    manifest_path = OUTPUT_DIR / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nManifesto: {manifest_path}")

    html_path = OUTPUT_DIR / "index.html"
    html_path.write_text(_build_index_html(manifest), encoding="utf-8")
    print(f"Player:    {html_path}")
    print("\nAbra no navegador:")
    print(f"  file:///{html_path.as_posix()}")
    print("  ou http://127.0.0.1:5500/data/narrator-voice-tests/index.html")
    return 0


def _build_index_html(manifest: dict) -> str:
    cards = []
    for sample in manifest["samples"]:
        cards.append(
            f"""
        <article class="card">
          <h2>{sample["label"]}</h2>
          <p class="meta">{sample["voice"]} · rate {sample["rate"]} · pitch {sample["pitch"]}</p>
          <p class="desc">{sample["description"]}</p>
          <audio controls preload="metadata" src="{sample["file"]}"></audio>
        </article>"""
        )

    text = manifest.get("sample_text", "")
    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Narradora feminina — testes de voz | Radio no Grale</title>
  <style>
    :root {{
      font-family: "Segoe UI", system-ui, sans-serif;
      background: #0f0a12;
      color: #f5e6f0;
    }}
    body {{ margin: 0; padding: 1.5rem; max-width: 720px; margin-inline: auto; }}
    h1 {{ font-size: 1.35rem; color: #ff9ec8; }}
    .intro {{ opacity: 0.85; line-height: 1.5; font-size: 0.95rem; }}
    .sample-text {{
      background: #1a1220;
      border-left: 3px solid #c94b8a;
      padding: 0.75rem 1rem;
      margin: 1rem 0 1.5rem;
      font-style: italic;
      font-size: 0.9rem;
    }}
    .card {{
      background: #1a1220;
      border-radius: 12px;
      padding: 1rem 1.25rem;
      margin-bottom: 1rem;
      border: 1px solid #3d2548;
    }}
    .card h2 {{ margin: 0 0 0.35rem; font-size: 1.05rem; }}
    .meta {{ margin: 0; font-size: 0.75rem; opacity: 0.65; }}
    .desc {{ margin: 0.5rem 0 0.75rem; font-size: 0.88rem; line-height: 1.4; }}
    audio {{ width: 100%; margin-top: 0.25rem; }}
  </style>
</head>
<body>
  <h1>5 vozes femininas — teste de narradora</h1>
  <p class="intro">
    Separado da Miku. Ouça todas e escolha a favorita; depois integramos no site.
    Pasta dos áudios: <code>data/narrator-voice-tests/</code>
  </p>
  <p class="sample-text">{text}</p>
  {"".join(cards)}
</body>
</html>
"""


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
