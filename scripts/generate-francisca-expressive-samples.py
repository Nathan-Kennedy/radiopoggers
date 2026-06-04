#!/usr/bin/env python3
"""Gera amostras Francisca expressiva (pt-BR + risadas/bocejos naturais via ChatTTS)."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SERVER_DIR = PROJECT_ROOT / "tools" / "radiopoggers-server"
OUTPUT_DIR = PROJECT_ROOT / "data" / "narrator-voice-tests" / "expressive"

# Roteiro com marcadores expressivos (nao escreva "ha ha" — use {laugh})
DEMO_SCRIPTS = [
    {
        "id": "francisca-expressive-v1-radio-completa",
        "label": "Francisca expressiva — vinheta completa da radio",
        "description": (
            "Locutora pt-BR (Francisca) + risada natural no meio e no final, "
            "pausas sedutoras e respiracao leve."
        ),
        "script": (
            "Olá, ouvinte lindo! {breath} Você sintonizou na Rádio no Grale, "
            "a Alta Cúpula que não te deixa ficar parado! {pause:450ms} "
            "A noite está pegando fogo, o som está absurdamente bom, "
            "e eu estou aqui só pra te manter colado nessa frequência. {laugh:soft} "
            "Vira o volume, sente o grave, deixa o corpo balançar… "
            "e vem comigo até o amanhecer! {pause:300ms} {laugh:full}"
        ),
    },
    {
        "id": "francisca-expressive-v2-madrugada",
        "label": "Francisca expressiva — locutora da madrugada",
        "description": "Tom mais intimo: suspiro, bocejo leve e risada curta no fechamento.",
        "script": (
            "Você ligou na Rádio no Grale… {sigh} Alta Cúpula no ar, música quente, "
            "energia lá em cima. {pause:500ms} Fica comigo, não desliga esse radinho. "
            "{yawn} Desculpa, essa faixa me pegou… {laugh:light} "
            "Gira o volume e sente o grave te pegar de jeito!"
        ),
    },
    {
        "id": "francisca-expressive-v3-energia-pura",
        "label": "Francisca expressiva — alta energia",
        "description": "Mais animada: risada no meio da frase e fechamento com risada cheia.",
        "script": (
            "Rádio no Grale no ar! {breath} Alta Cúpula, som quente, eu aqui só por você! "
            "{laugh} Não dá pra ficar parado ouvindo isso! {pause:250ms} "
            "Cola na frequência, vira o volume no máximo… vem! {laugh:full}"
        ),
    },
]


async def main() -> int:
    sys.path.insert(0, str(SERVER_DIR))
    try:
        from expressive_francisca import render_expressive_francisca
    except ImportError as error:
        print(f"Erro de import: {error}", file=sys.stderr)
        print("Rode: .\\scripts\\install-expressive-narrator.ps1", file=sys.stderr)
        return 1

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    manifest = {
        "engine": "Francisca (edge-tts pt-BR, prosodia suave) + risadas reais (ChatTTS com recorte)",
        "voice_speech": "pt-BR-FranciscaNeural",
        "markers": ["{pause}", "{laugh}", "{laugh:soft}", "{yawn}", "{sigh}", "{breath}"],
        "samples": [],
    }

    print("Gerando Francisca expressiva (primeira vez baixa modelo ChatTTS, pode demorar)...\n")

    for item in DEMO_SCRIPTS:
        out_path = OUTPUT_DIR / f"{item['id']}.mp3"
        print(f"  -> {item['label']}")
        audio, mime, duration_ms = await render_expressive_francisca(
            item["script"],
            force_regenerate_sfx=True,
        )
        out_path.write_bytes(audio)
        manifest["samples"].append(
            {
                **item,
                "file": out_path.name,
                "duration_ms": duration_ms,
                "mime_type": mime,
            }
        )
        print(f"     OK {duration_ms // 1000}s -> {out_path.name}")

    (OUTPUT_DIR / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    html = _build_html(manifest)
    (OUTPUT_DIR / "index.html").write_text(html, encoding="utf-8")

    print(f"\nOuvir (abra o arquivo no Explorer se o site nao estiver no ar):")
    print(f"  {OUTPUT_DIR / 'index.html'}")
    print(f"  http://127.0.0.1:5500/data/narrator-voice-tests/expressive/index.html")
    print(f"Pasta:  {OUTPUT_DIR}")
    return 0


def _build_html(manifest: dict) -> str:
    cards = []
    for sample in manifest["samples"]:
        cards.append(
            f"""
        <article class="card">
          <h2>{sample["label"]}</h2>
          <p class="desc">{sample["description"]}</p>
          <p class="script"><strong>Roteiro:</strong> {sample["script"]}</p>
          <audio controls preload="metadata" src="{sample["file"]}"></audio>
        </article>"""
        )
    markers = ", ".join(manifest.get("markers", []))
    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Francisca expressiva | Radio no Grale</title>
  <style>
    body {{ font-family: system-ui, sans-serif; background:#0f0a12; color:#f5e6f0; margin:0; padding:1.5rem; max-width:760px; margin-inline:auto; }}
    h1 {{ color:#ff9ec8; font-size:1.3rem; }}
    .intro {{ opacity:.88; line-height:1.5; }}
    .card {{ background:#1a1220; border:1px solid #3d2548; border-radius:12px; padding:1rem 1.2rem; margin:1rem 0; }}
    .desc {{ font-size:.9rem; line-height:1.45; }}
    .script {{ font-size:.78rem; opacity:.75; font-style:italic; }}
    audio {{ width:100%; margin-top:.6rem; }}
  </style>
</head>
<body>
  <h1>Francisca expressiva (pt-BR + risadas naturais)</h1>
  <p class="intro">
    Fala: <strong>Francisca</strong> (edge-tts). Risadas e efeitos: <strong>ChatTTS</strong> (som real, nao a palavra laugh).
    Se o link HTTP nao abrir, use o botao direito no index.html &rarr; Abrir com o navegador.
  </p>
  {"".join(cards)}
</body>
</html>"""


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
