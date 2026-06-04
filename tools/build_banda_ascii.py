#!/usr/bin/env python3
"""Extract banda ASCII art and write banda.md + frontend/assets/banda-ascii.json."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BANDA_MD = ROOT / "banda.md"
JSON_OUT = ROOT / "frontend" / "assets" / "banda-ascii.json"
TRANSCRIPT = (
    Path.home()
    / ".cursor"
    / "projects"
    / "c-Projetos-Dev-RadioPoggers"
    / "agent-transcripts"
    / "891a02c9-2c54-424c-a3a0-2148ec655a98"
    / "891a02c9-2c54-424c-a3a0-2148ec655a98.jsonl"
)

READ_LINE = re.compile(r"^\s*\d+\|(.*)$")
SKIP_LINE = re.compile(r"^\.\.\. \d+ lines not shown \.\.\.$")


def parse_read_format(text: str) -> list[str]:
    lines: list[str] = []
    for line in text.splitlines():
        if SKIP_LINE.match(line.strip()):
            continue
        m = READ_LINE.match(line)
        if m:
            lines.append(m.group(1))
    return lines


def load_from_chunks() -> list[str] | None:
    chunk_dir = ROOT / "tools" / "banda-chunks"
    chunk_paths = sorted(chunk_dir.glob("chunk-*.raw"))
    if not chunk_paths:
        return None
    lines: list[str] = []
    for path in chunk_paths:
        lines.extend(parse_read_format(path.read_text(encoding="utf-8")))
    return lines if lines else None


def load_from_transcript() -> list[str]:
    if not TRANSCRIPT.is_file():
        raise FileNotFoundError(f"Transcript not found: {TRANSCRIPT}")
    record = json.loads(TRANSCRIPT.read_text(encoding="utf-8").splitlines()[198])
    text = record["message"]["content"][0]["text"]
    match = re.search(r"<user_query>\s*(?:.*?\n)?(.*)</user_query>", text, re.DOTALL)
    if not match:
        raise ValueError("Could not parse transcript user_query block")
    lines = match.group(1).splitlines()
    if lines and "daria pra fazer" in lines[0]:
        lines = lines[1:]
    return lines


def compute_crop_box(lines: list[str]) -> dict[str, int]:
    if not lines:
        return {"left": 0, "top": 0, "right": 0, "bottom": 0}

    height = len(lines)
    width = max(len(line) for line in lines)
    top = height
    bottom = -1
    left = width
    right = -1

    for y, line in enumerate(lines):
        for x, ch in enumerate(line):
            if ch != " ":
                top = min(top, y)
                bottom = max(bottom, y)
                left = min(left, x)
                right = max(right, x)

    if bottom < top:
        return {"left": 0, "top": 0, "right": width - 1, "bottom": height - 1}

    return {"left": left, "top": top, "right": right, "bottom": bottom}


def crop_lines(lines: list[str], box: dict[str, int]) -> list[str]:
    l, t, r, b = box["left"], box["top"], box["right"], box["bottom"]
    return [line[l : r + 1] for line in lines[t : b + 1]]


def main() -> int:
    lines = load_from_chunks()
    if not lines:
        lines = load_from_transcript()

    if not lines:
        print("No ASCII art lines found", file=sys.stderr)
        return 1

    BANDA_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")

    width = max(len(line) for line in lines)
    crop_box = compute_crop_box(lines)
    cropped = crop_lines(lines, crop_box)

    payload = {
        "width": width,
        "height": len(lines),
        "lines": lines,
        "cropBox": crop_box,
        "croppedWidth": crop_box["right"] - crop_box["left"] + 1,
        "croppedHeight": crop_box["bottom"] - crop_box["top"] + 1,
        "croppedLines": cropped,
    }

    JSON_OUT.parent.mkdir(parents=True, exist_ok=True)
    JSON_OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    md_size = BANDA_MD.stat().st_size
    json_size = JSON_OUT.stat().st_size

    print(f"lines={len(lines)}")
    print(f"width={width}")
    print(f"cropBox={crop_box}")
    print(f"croppedSize={payload['croppedWidth']}x{payload['croppedHeight']}")
    print(f"banda.md bytes={md_size}")
    print(f"json bytes={json_size}")
    print(f"json path={JSON_OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
