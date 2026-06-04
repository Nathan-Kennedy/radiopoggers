#!/usr/bin/env python3
"""Extrai risadas/suspiros reais de clips ChatTTS (nao so o token [laugh] isolado)."""

from __future__ import annotations

import io
from typing import Any

SAMPLE_RATE = 24000

# Frase em ingles + tokens ChatTTS no final -> recortamos so a cauda expressiva.
CHATTTS_EXPRESSIVE: dict[str, dict[str, Any]] = {
    "laugh": {
        "text": "That is so funny [laugh]",
        "prompt": "[oral_2][laugh_1][break_4]",
        "tail_ms": 850,
    },
    "laugh:soft": {
        "text": "Hehe that is sweet [laugh]",
        "prompt": "[oral_1][laugh_0][break_3]",
        "tail_ms": 650,
    },
    "laugh:light": {
        "text": "That made me smile [laugh]",
        "prompt": "[oral_1][laugh_0][break_3]",
        "tail_ms": 750,
    },
    "laugh:full": {
        "text": "Oh wow that is hilarious [laugh][laugh][laugh]",
        "prompt": "[oral_3][laugh_2][break_5]",
        "tail_ms": 1600,
    },
    "yawn": {
        "text": "I am so sleepy now [uv_break]",
        "prompt": "[oral_4][break_7]",
        "tail_ms": 1100,
    },
    "sigh": {
        "text": "Ahhh [uv_break]",
        "prompt": "[oral_2][break_6]",
        "tail_ms": 800,
    },
    "breath": {
        "text": "Okay [uv_break]",
        "prompt": "[oral_1][break_2]",
        "tail_ms": 450,
    },
}


def pcm16_to_audiosegment(pcm: bytes, sample_rate: int = SAMPLE_RATE):
    from pydub import AudioSegment

    return AudioSegment(
        data=pcm,
        sample_width=2,
        frame_rate=sample_rate,
        channels=1,
    )


def audiosegment_to_pcm16(audio) -> bytes:
    mono = audio.set_channels(1).set_frame_rate(SAMPLE_RATE)
    return mono.raw_data


def trim_expressive_tail(pcm: bytes, tail_ms: int, sample_rate: int = SAMPLE_RATE) -> bytes:
    from pydub import AudioSegment
    from pydub.silence import detect_nonsilent

    audio = pcm16_to_audiosegment(pcm, sample_rate)
    if len(audio) <= tail_ms + 80:
        return pcm

    nonsilent = detect_nonsilent(
        audio,
        min_silence_len=120,
        silence_thresh=audio.dBFS - 16,
        seek_step=10,
    )
    if nonsilent:
        start_ms = nonsilent[-1][0]
        tail = audio[max(0, start_ms - 80) :]
    else:
        tail = audio[-tail_ms:]

    if len(tail) > tail_ms + 200:
        tail = tail[-tail_ms:]
    elif len(tail) < 180:
        tail = audio[-tail_ms:]

    # Fade suave para encaixar na locucao
    tail = tail.fade_in(20).fade_out(120)
    return audiosegment_to_pcm16(tail)


def synthesize_chattts_clip(
    chat: Any,
    speaker_emb: str,
    *,
    text: str,
    prompt: str,
    tail_ms: int,
) -> tuple[bytes, int]:
    import ChatTTS
    import numpy as np

    params_refine = ChatTTS.Chat.RefineTextParams(
        prompt=prompt,
        ensure_non_empty=False,
        show_tqdm=False,
    )
    params_infer = ChatTTS.Chat.InferCodeParams(
        spk_emb=speaker_emb,
        temperature=0.45,
        top_P=0.78,
        top_K=28,
        ensure_non_empty=False,
        show_tqdm=False,
        max_new_token=512,
    )
    wavs = chat.infer(
        text,
        skip_refine_text=True,
        params_refine_text=params_refine,
        params_infer_code=params_infer,
    )
    if not wavs or wavs[0] is None or len(np.asarray(wavs[0]).ravel()) < SAMPLE_RATE * 0.12:
        # fallback minimal
        wavs = chat.infer(
            "[uv_break]",
            skip_refine_text=True,
            params_refine_text=params_refine,
            params_infer_code=params_infer,
        )
    if not wavs or wavs[0] is None:
        raise RuntimeError(f"ChatTTS falhou para: {text!r}")

    samples = np.asarray(wavs[0], dtype=np.float32)
    if samples.size < SAMPLE_RATE * 0.15:
        raise RuntimeError(f"ChatTTS gerou clip curto demais para: {text!r}")
    samples = np.clip(samples, -1.0, 1.0)
    pcm16 = (samples * 32767.0).astype("<i2").tobytes()
    trimmed = trim_expressive_tail(pcm16, tail_ms=tail_ms)
    duration_ms = int(len(trimmed) / (SAMPLE_RATE * 2) * 1000)
    if duration_ms < 180:
        raise RuntimeError(f"Clip expressivo curto demais ({duration_ms}ms) para: {text!r}")
    return trimmed, duration_ms
