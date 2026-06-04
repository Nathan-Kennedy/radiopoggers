#!/usr/bin/env python3
"""Narradora via Gemini TTS (Google AI Studio / plano Pro)."""

from __future__ import annotations

import io
import os
import wave
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
API_KEY_FILE = PROJECT_ROOT / "data" / "gemini-api-key.txt"

# Modelos TTS (AI Studio). Tentamos o mais novo primeiro.
TTS_MODELS = (
    "gemini-2.5-flash-preview-tts",
    "gemini-2.5-pro-preview-tts",
)

DEFAULT_LANGUAGE = "pt-BR"
SAMPLE_RATE = 24000
SAMPLE_WIDTH = 2
CHANNELS = 1

# Vozes femininas Gemini — boas para locutora sedutora / FM
FEMALE_VOICES = (
    {"id": "kore", "name": "Kore", "label": "Kore — quente e equilibrada"},
    {"id": "aoede", "name": "Aoede", "label": "Aoede — suave e musical"},
    {"id": "despina", "name": "Despina", "label": "Despina — clara e firme"},
    {"id": "sulafat", "name": "Sulafat", "label": "Sulafat — grave sedutora"},
    {"id": "leda", "name": "Leda", "label": "Leda — jovem e brilhante"},
)

STYLE_LOCUTORA = (
    "Você é locutora de rádio FM brasileira, feminina, sedutora, calorosa e animada. "
    "Fale em português do Brasil com naturalidade, como se estivesse no ar ao vivo."
)


def resolve_gemini_api_key() -> str:
    for env_name in ("GEMINI_API_KEY", "GOOGLE_API_KEY", "RADIOPOGGERS_GEMINI_API_KEY"):
        value = os.environ.get(env_name, "").strip()
        if value:
            return value
    if API_KEY_FILE.exists():
        for line in API_KEY_FILE.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                return line
    raise RuntimeError(
        "API key Gemini ausente. Crie data/gemini-api-key.txt "
        "(veja data/gemini-api-key.example.txt) ou defina GEMINI_API_KEY."
    )


def _pcm_to_wav(pcm: bytes) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(SAMPLE_WIDTH)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(pcm)
    return buf.getvalue()


def _extract_pcm_from_response(response: Any) -> bytes:
    candidates = getattr(response, "candidates", None) or []
    if not candidates:
        raise RuntimeError("Gemini TTS nao retornou candidatos.")
    content = candidates[0].content
    parts = getattr(content, "parts", None) or []
    for part in parts:
        inline = getattr(part, "inline_data", None)
        if inline and inline.data:
            data = inline.data
            if isinstance(data, str):
                import base64

                data = base64.b64decode(data)
            mime = str(getattr(inline, "mime_type", "") or "")
            if "wav" in mime.lower():
                pcm, _ = _wav_bytes_to_pcm(data)
                return pcm
            return bytes(data)
    raise RuntimeError("Gemini TTS nao retornou audio inline_data.")


def _wav_bytes_to_pcm(wav_bytes: bytes) -> tuple[bytes, int]:
    from pydub import AudioSegment

    audio = AudioSegment.from_file(io.BytesIO(wav_bytes), format="wav")
    audio = audio.set_frame_rate(SAMPLE_RATE).set_channels(1)
    return audio.raw_data, len(audio)


def pcm_to_mp3(pcm: bytes) -> bytes:
    from pydub import AudioSegment

    audio = AudioSegment(
        data=pcm,
        sample_width=SAMPLE_WIDTH,
        frame_rate=SAMPLE_RATE,
        channels=CHANNELS,
    )
    out = io.BytesIO()
    audio.export(out, format="mp3", bitrate="192k")
    return out.getvalue()


def synthesize_gemini_tts(
    *,
    text: str,
    voice_name: str,
    style_prompt: str = STYLE_LOCUTORA,
    language_code: str = DEFAULT_LANGUAGE,
    model: str | None = None,
) -> tuple[bytes, str, str]:
    """
    Retorna (pcm_bytes, mime, model_used).
    `text` pode incluir tags Gemini: [laughing], [sigh], [short pause], etc.
    """
    from google import genai
    from google.genai import types

    api_key = resolve_gemini_api_key()
    client = genai.Client(api_key=api_key)

    contents = f"{style_prompt}\n\n{text.strip()}"
    models = (model,) if model else TTS_MODELS
    last_error: Exception | None = None

    for model_name in models:
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=contents,
                config=types.GenerateContentConfig(
                    response_modalities=["AUDIO"],
                    speech_config=types.SpeechConfig(
                        language_code=language_code,
                        voice_config=types.VoiceConfig(
                            prebuilt_voice_config=types.PrebuiltVoiceConfig(
                                voice_name=voice_name,
                            )
                        ),
                    ),
                ),
            )
            pcm = _extract_pcm_from_response(response)
            return pcm, "audio/pcm", model_name
        except Exception as error:
            last_error = error
            continue

    raise RuntimeError(f"Gemini TTS falhou em todos os modelos: {last_error}")


def synthesize_gemini_mp3(**kwargs: Any) -> tuple[bytes, str, str]:
    pcm, _, model = synthesize_gemini_tts(**kwargs)
    return pcm_to_mp3(pcm), "audio/mpeg", model
