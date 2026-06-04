#!/usr/bin/env python3
"""
Narradora Francisca expressiva: fala pt-BR (edge-tts) + risadas reais (ChatTTS com recorte).
"""

from __future__ import annotations

import asyncio
import io
import re
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from nonverbal_engine import CHATTTS_EXPRESSIVE, SAMPLE_RATE, synthesize_chattts_clip

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SFX_DIR = PROJECT_ROOT / "assets" / "narrator-sfx"
CHATTTS_CACHE = Path.home() / ".cache" / "radiopoggers" / "chattts"

FRANCISCA_VOICE = "pt-BR-FranciscaNeural"
FRANCISCA_RATE = "+3%"
FRANCISCA_PITCH = "-1Hz"
FRANCISCA_VOLUME = "+4%"

TAG_PATTERN = re.compile(
    r"\{(pause(?::\d+(?:ms|s)?)?|laugh(?::soft|light|full)?|yawn|sigh|breath)\}",
    re.IGNORECASE,
)


@dataclass
class Segment:
    kind: str
    text: str = ""
    pause_ms: int = 0
    tag: str = ""


def parse_expressive_script(script: str) -> list[Segment]:
    segments: list[Segment] = []
    last = 0
    for match in TAG_PATTERN.finditer(script):
        if match.start() > last:
            chunk = script[last : match.start()].strip()
            if chunk:
                segments.append(Segment(kind="speech", text=chunk))
        tag = match.group(1).lower()
        if tag.startswith("pause"):
            pause_ms = 350
            if ":" in tag:
                raw = tag.split(":", 1)[1]
                if raw.endswith("ms"):
                    pause_ms = int(raw[:-2])
                elif raw.endswith("s"):
                    pause_ms = int(float(raw[:-1]) * 1000)
                else:
                    pause_ms = int(raw)
            segments.append(Segment(kind="pause", pause_ms=pause_ms))
        else:
            segments.append(Segment(kind="nonverbal", tag=tag))
        last = match.end()
    tail = script[last:].strip()
    if tail:
        segments.append(Segment(kind="speech", text=tail))
    return segments


def humanize_speech_text(text: str) -> str:
    """Pequenos ajustes de prosodia sem alterar o sentido."""
    cleaned = re.sub(r"\s+", " ", text.strip())
    cleaned = cleaned.replace("!", "!…")
    cleaned = cleaned.replace("?", "?…")
    cleaned = re.sub(r"!…+", "!…", cleaned)
    return cleaned


def _mp3_to_pcm(mp3_bytes: bytes) -> tuple[bytes, int]:
    from pydub import AudioSegment

    audio = AudioSegment.from_file(io.BytesIO(mp3_bytes), format="mp3")
    audio = audio.set_frame_rate(SAMPLE_RATE).set_channels(1)
    return audio.raw_data, len(audio)


def _wav_to_pcm(wav_bytes: bytes) -> tuple[bytes, int]:
    from pydub import AudioSegment

    audio = AudioSegment.from_file(io.BytesIO(wav_bytes), format="wav")
    audio = audio.set_frame_rate(SAMPLE_RATE).set_channels(1)
    return audio.raw_data, len(audio)


def _pcm_to_wav(pcm: bytes) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(pcm)
    return buf.getvalue()


def _pcm_to_mp3(pcm: bytes) -> bytes:
    from pydub import AudioSegment

    audio = AudioSegment(
        data=pcm,
        sample_width=2,
        frame_rate=SAMPLE_RATE,
        channels=1,
    )
    out = io.BytesIO()
    audio.export(out, format="mp3", bitrate="192k")
    return out.getvalue()


def _silence_pcm(duration_ms: int) -> bytes:
    from pydub import AudioSegment

    return AudioSegment.silent(duration=duration_ms, frame_rate=SAMPLE_RATE).raw_data


def _concat_pcm(chunks: list[bytes]) -> bytes:
    from pydub import AudioSegment

    if not chunks:
        return b""
    merged = pcm16_to_audiosegment(chunks[0])
    for chunk in chunks[1:]:
        merged += pcm16_to_audiosegment(chunk)
    return merged.raw_data


def pcm16_to_audiosegment(pcm: bytes):
    from pydub import AudioSegment

    return AudioSegment(
        data=pcm,
        sample_width=2,
        frame_rate=SAMPLE_RATE,
        channels=1,
    )


class ExpressiveFranciscaEngine:
    def __init__(self, *, force_regenerate_sfx: bool = False) -> None:
        self._chat: Any = None
        self._speaker_emb: Any = None
        self._chattts_ready = False
        self._sfx_cache: dict[str, bytes] = {}
        self._force_regenerate_sfx = force_regenerate_sfx

    def _sfx_path(self, tag: str) -> Path:
        return SFX_DIR / f"{tag.replace(':', '-')}.wav"

    def _load_sfx_pcm(self, tag: str) -> bytes | None:
        if tag in self._sfx_cache:
            return self._sfx_cache[tag]
        if self._force_regenerate_sfx:
            return None
        path = self._sfx_path(tag)
        if not path.exists():
            return None
        pcm, _ = _wav_to_pcm(path.read_bytes())
        if len(pcm) < SAMPLE_RATE * 2 * 0.18:
            return None
        self._sfx_cache[tag] = pcm
        return pcm

    def _ensure_chattts(self) -> None:
        if self._chattts_ready:
            return
        import ChatTTS
        import torch

        CHATTTS_CACHE.mkdir(parents=True, exist_ok=True)
        chat = ChatTTS.Chat()
        loaded = chat.load(
            source="huggingface",
            custom_path=str(CHATTTS_CACHE),
            compile=False,
        )
        if not loaded:
            raise RuntimeError(
                "ChatTTS nao carregou. Rode .\\scripts\\generate-narrator-sfx.ps1"
            )
        torch.manual_seed(4242)
        self._chat = chat
        self._speaker_emb = chat.sample_random_speaker()
        self._chattts_ready = True

    async def synthesize_francisca(self, text: str) -> bytes:
        import edge_tts

        spoken = humanize_speech_text(text)
        communicate = edge_tts.Communicate(
            spoken,
            FRANCISCA_VOICE,
            rate=FRANCISCA_RATE,
            pitch=FRANCISCA_PITCH,
            volume=FRANCISCA_VOLUME,
        )
        chunks: list[bytes] = []
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                chunks.append(chunk["data"])
        if not chunks:
            raise RuntimeError("edge-tts nao gerou audio para Francisca.")
        return b"".join(chunks)

    def synthesize_nonverbal(self, tag: str) -> tuple[bytes, int]:
        cached = self._load_sfx_pcm(tag)
        if cached is not None:
            duration_ms = int(len(cached) / (SAMPLE_RATE * 2) * 1000)
            return cached, duration_ms

        spec = CHATTTS_EXPRESSIVE.get(tag) or CHATTTS_EXPRESSIVE["laugh"]
        self._ensure_chattts()
        pcm, duration_ms = synthesize_chattts_clip(
            self._chat,
            self._speaker_emb,
            text=str(spec["text"]),
            prompt=str(spec["prompt"]),
            tail_ms=int(spec["tail_ms"]),
        )

        SFX_DIR.mkdir(parents=True, exist_ok=True)
        self._sfx_path(tag).write_bytes(_pcm_to_wav(pcm))
        self._sfx_cache[tag] = pcm
        return pcm, duration_ms

    async def render_script(
        self,
        script: str,
        *,
        output_format: str = "mp3",
    ) -> tuple[bytes, str, int]:
        segments = parse_expressive_script(script)
        pcm_parts: list[bytes] = []

        for segment in segments:
            if segment.kind == "pause":
                pcm_parts.append(_silence_pcm(segment.pause_ms))
                continue
            if segment.kind == "nonverbal":
                pcm, _ = self.synthesize_nonverbal(segment.tag)
                pcm_parts.append(pcm)
                continue
            mp3 = await self.synthesize_francisca(segment.text)
            pcm, _ = _mp3_to_pcm(mp3)
            pcm_parts.append(pcm)

        merged = _concat_pcm(pcm_parts)
        duration_ms = int(len(merged) / (SAMPLE_RATE * 2) * 1000)
        if output_format == "wav":
            return _pcm_to_wav(merged), "audio/wav", duration_ms
        return _pcm_to_mp3(merged), "audio/mpeg", duration_ms


async def render_expressive_francisca(
    script: str,
    *,
    output_format: str = "mp3",
    force_regenerate_sfx: bool = False,
) -> tuple[bytes, str, int]:
    engine = ExpressiveFranciscaEngine(force_regenerate_sfx=force_regenerate_sfx)
    return await engine.render_script(script, output_format=output_format)
