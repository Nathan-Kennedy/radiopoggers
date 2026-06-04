"""Mixer da radio + voice drops (Miku, ouvintes) para o Discord."""

from __future__ import annotations

import audioop
import logging
import struct
import subprocess
import threading
import time
import urllib.request
from collections import deque
from typing import Any

import discord

log = logging.getLogger("radiopoggers.discord.mixer")

DISCORD_FRAME_BYTES = 3840  # 20 ms @ 48 kHz stereo s16le
SAMPLE_RATE = 48000
FRAME_SEC = 0.02
# Jitter buffer da radio (PCM) + fila Opus com relogio fixo 20 ms no envio ao Discord.
RADIO_BUFFER_LIMIT = DISCORD_FRAME_BYTES * 1000
RADIO_TARGET_BUFFER_BYTES = DISCORD_FRAME_BYTES * 160
RADIO_PREFILL_BYTES = DISCORD_FRAME_BYTES * 120
RADIO_LOW_WATER_BYTES = DISCORD_FRAME_BYTES * 50
RADIO_READ_CHUNK_BYTES = DISCORD_FRAME_BYTES * 64
OPUS_QUEUE_MAX_FRAMES = 700
OPUS_QUEUE_HIGH_WATER_FRAMES = 600
DEFAULT_OPUS_BITRATE_KBPS = 128
RADIO_UNDERRUN_HOLD_MAX = 4

DUCK_FLOOR = 0.08
DUCK_PRE_DIP = 0.14
DUCK_ATTACK_SEC = 0.012
DUCK_RELEASE_SEC = 0.48
VOICE_SIDECHAIN_SENSITIVITY = 4.4

# Mesmo ganho para Miku e voice drops gravados por ouvintes.
VOICE_DROP_GAIN = 1.35
NARRATOR_MIN_RMS = 900
NARRATOR_BOOST_TARGET_RMS = 3200
NARRATOR_PCM_MAX_GAIN = 2.0
NARRATOR_DUCK_FLOOR = 0.10
NARRATOR_DUCK_PRE_DIP = 0.20

MIKU_LISTENER_ID = "miku-narrator"
HOSHINO_LISTENER_ID = "hoshino-narrator"
NARRATOR_IDS = {MIKU_LISTENER_ID}

FFMPEG_BEFORE = (
    "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5 "
    "-protocol_whitelist file,http,https,tcp,tls,crypto "
    "-fflags +nobuffer -flags low_delay"
)

# Stream da radio: opcoes alinhadas a bots de musica (reconnect, genpts, resample async).
FFMPEG_RADIO_BEFORE = (
    "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5 "
    "-protocol_whitelist file,http,https,tcp,tls,crypto "
    "-fflags +genpts -thread_queue_size 8192 -rw_timeout 15000000 "
    "-multiple_requests 1 -user_agent RadioPoggersDiscordBot/1.0"
)

FFMPEG_RADIO_OUTPUT = ("-af", "aresample=48000:async=1:min_hard_comp=0.100:first_pts=0")

# HLS ao vivo (mesma fonte que o site com streamMode hls).
FFMPEG_HLS_RADIO_BEFORE = (
    "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5 "
    "-protocol_whitelist file,http,https,tcp,tls,crypto "
    "-fflags +genpts -thread_queue_size 8192 -rw_timeout 15000000 "
    "-multiple_requests 1 -user_agent RadioPoggersDiscordBot/1.0 "
    "-live_start_index -1"
)


def _ffmpeg_radio_before(stream_kind: str) -> str:
    kind = str(stream_kind or "mp3").strip().lower()
    if kind == "hls":
        return FFMPEG_HLS_RADIO_BEFORE
    return FFMPEG_RADIO_BEFORE

MIKU_AF = (
    "highpass=f=90,"
    "equalizer=f=260:width_type=q:width=0.85:g=2.6,"
    "equalizer=f=380:width_type=q:width=0.7:g=1.2,"
    "equalizer=f=2800:width_type=q:width=0.9:g=2.8,"
    "equalizer=f=4200:width_type=q:width=1.2:g=0.6,"
    "equalizer=f=6800:width_type=q:width=2.4:g=-4,"
    "highshelf=f=9500:g=-1.8,"
    "lowpass=f=12000,"
    "acompressor=threshold=-12dB:ratio=2.4:attack=12:release=240,"
    "asoftclip=type=tanh:threshold=0.92:output=1,"
    "aecho=0.36:0.58:36|58:0.09|0.05,"
    "acompressor=threshold=-4dB:ratio=6:attack=4:release=200"
)


def _sidechain_duck_target(envelope: float, *, floor: float = DUCK_FLOOR) -> float:
    return floor + ((1.0 - envelope) * (1.0 - floor))


def _normalize_narrator_pcm(pcm: bytes) -> bytes:
    if not pcm:
        return pcm
    rms = audioop.rms(pcm, 2)
    if rms >= NARRATOR_MIN_RMS:
        return pcm
    gain = min(NARRATOR_PCM_MAX_GAIN, NARRATOR_BOOST_TARGET_RMS / max(rms, 1))
    if gain <= 1.02:
        return pcm
    return audioop.mul(pcm, 2, gain)


def _resolve_narrator_variant(listener_id: str) -> str:
    listener_id = str(listener_id or "").strip()
    if listener_id == MIKU_LISTENER_ID:
        return "miku"
    return ""


def _fetch_json(url: str, timeout: float = 8.0) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        headers={"Accept": "application/json", "User-Agent": "RadioPoggersDiscordBot/1.0"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = response.read().decode("utf-8")
    import json

    data = json.loads(payload)
    return data if isinstance(data, dict) else {}


def _decode_pcm(
    ffmpeg_path: str,
    source: str,
    *,
    variant: str = "",
    timeout: float = 45.0,
) -> bytes:
    cmd = [
        ffmpeg_path,
        "-hide_banner",
        "-loglevel",
        "error",
        "-nostdin",
    ]
    if source.startswith("http://") or source.startswith("https://"):
        cmd.extend(FFMPEG_BEFORE.split())
    cmd.extend(["-i", source, "-f", "s16le", "-acodec", "pcm_s16le", "-ar", str(SAMPLE_RATE), "-ac", "2"])
    if variant == "miku":
        cmd.extend(["-af", MIKU_AF])
    cmd.append("-")

    proc = subprocess.run(cmd, capture_output=True, timeout=timeout, check=False)
    if proc.returncode != 0:
        detail = proc.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(detail or f"ffmpeg exit {proc.returncode}")
    if not proc.stdout:
        raise RuntimeError("ffmpeg nao retornou audio.")
    if len(proc.stdout) % 2:
        proc.stdout += b"\x00"
    return proc.stdout


def _mix_frames(
    radio: bytes,
    voice: bytes,
    duck_gain: float,
    voice_gain: float = 1.0,
    *,
    voice_active: bool = False,
    is_narrator: bool = False,
) -> bytes:
    if len(voice) < DISCORD_FRAME_BYTES:
        voice = voice + (b"\x00" * (DISCORD_FRAME_BYTES - len(voice)))
    if len(radio) < DISCORD_FRAME_BYTES:
        radio = radio + (b"\x00" * (DISCORD_FRAME_BYTES - len(radio)))

    if duck_gain >= 0.999 and not voice_active:
        return radio[:DISCORD_FRAME_BYTES]

    # Miku/narrador: sem ducking da radio (musica no volume cheio + voz por cima).
    effective_duck = 1.0 if (voice_active and is_narrator) else duck_gain

    if voice_active and voice_gain > 1.001 and any(voice):
        voice = audioop.mul(voice[:DISCORD_FRAME_BYTES], 2, min(voice_gain, 2.0))

    ducked = audioop.mul(radio[:DISCORD_FRAME_BYTES], 2, effective_duck)

    mixed = bytearray(DISCORD_FRAME_BYTES)
    for offset in range(0, DISCORD_FRAME_BYTES, 2):
        sample = struct.unpack_from("<h", ducked, offset)[0] + struct.unpack_from("<h", voice, offset)[0]
        if sample > 32767:
            sample = 32767
        elif sample < -32768:
            sample = -32768
        struct.pack_into("<h", mixed, offset, sample)
    return bytes(mixed)


def _drain_ffmpeg_stderr(proc: subprocess.Popen[bytes], stop: threading.Event) -> None:
    """Evita ffmpeg travar quando o pipe de stderr enche."""
    stderr = proc.stderr
    if not stderr:
        return
    try:
        while not stop.is_set():
            if proc.poll() is not None and not stderr.readable():
                break
            line = stderr.readline()
            if not line:
                break
    except Exception:
        pass


class _RadioStreamThread(threading.Thread):
    def __init__(
        self,
        stream_url: str,
        ffmpeg_path: str,
        mixer: "MixedRadioAudioSource",
        *,
        stream_kind: str = "mp3",
    ) -> None:
        super().__init__(daemon=True, name="discord-radio-stream")
        self.stream_url = stream_url
        self.ffmpeg_path = ffmpeg_path
        self.stream_kind = stream_kind
        self.mixer = mixer
        self._stop = threading.Event()
        self._proc: subprocess.Popen[bytes] | None = None

    def stop(self) -> None:
        self._stop.set()
        proc = self._proc
        if proc and proc.poll() is None:
            proc.kill()

    def run(self) -> None:
        while not self._stop.is_set():
            try:
                self._run_once()
            except Exception as error:
                log.warning("Stream da radio caiu, reconectando: %s", error)
                time.sleep(1.5)

    def _run_once(self) -> None:
        self.mixer._reset_radio_stream_buffer()
        cmd = [
            self.ffmpeg_path,
            "-hide_banner",
            "-loglevel",
            "error",
            "-nostdin",
            *_ffmpeg_radio_before(self.stream_kind).split(),
            "-i",
            self.stream_url,
            *FFMPEG_RADIO_OUTPUT,
            "-f",
            "s16le",
            "-acodec",
            "pcm_s16le",
            "-ar",
            str(SAMPLE_RATE),
            "-ac",
            "2",
            "-",
        ]
        self._proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=1024 * 1024,
        )
        assert self._proc.stdout is not None
        stderr_stop = threading.Event()
        stderr_thread = threading.Thread(
            target=_drain_ffmpeg_stderr,
            args=(self._proc, stderr_stop),
            daemon=True,
            name="discord-radio-ffmpeg-stderr",
        )
        stderr_thread.start()

        while not self._stop.is_set():
            chunk = self._proc.stdout.read(RADIO_READ_CHUNK_BYTES)
            if not chunk:
                break
            self.mixer._append_radio_chunk(chunk)

        stderr_stop.set()
        stderr_thread.join(timeout=2.0)
        proc = self._proc
        if proc and proc.poll() is None:
            proc.kill()
        self._proc = None
        if not self._stop.is_set():
            raise RuntimeError("ffmpeg stream encerrou")


class _OpusPumpThread(threading.Thread):
    """Gera pacotes Opus a cada 20 ms (relogio fixo), independente do timing do read() do Discord."""

    def __init__(self, mixer: "MixedRadioAudioSource") -> None:
        super().__init__(daemon=True, name="discord-opus-pump")
        self.mixer = mixer
        self._stop = threading.Event()

    def stop(self) -> None:
        self._stop.set()

    def run(self) -> None:
        from discord.opus import Encoder as OpusEncoder

        next_tick = time.monotonic()
        while not self._stop.is_set():
            pcm = self.mixer.render_pcm_frame()
            try:
                packet = self.mixer._opus_encoder.encode(pcm, OpusEncoder.SAMPLES_PER_FRAME)
                self.mixer._enqueue_opus(packet)
            except Exception as error:
                log.warning("Encode Opus falhou: %s", error)

            next_tick += FRAME_SEC
            delay = next_tick - time.monotonic()
            if delay > 0:
                self._stop.wait(delay)
            else:
                next_tick = time.monotonic()


class _VoiceDropThread(threading.Thread):
    def __init__(
        self,
        api_base: str,
        ffmpeg_path: str,
        mixer: "MixedRadioAudioSource",
        poll_seconds: float,
    ) -> None:
        super().__init__(daemon=True, name="discord-voice-drops")
        self.api_base = api_base.rstrip("/")
        self.ffmpeg_path = ffmpeg_path
        self.mixer = mixer
        self.poll_seconds = max(poll_seconds, 0.25)
        self._stop = threading.Event()
        self._inflight_ids: set[str] = set()
        self._inflight_lock = threading.Lock()

    def stop(self) -> None:
        self._stop.set()

    def run(self) -> None:
        try:
            self._poll_once()
        except Exception as error:
            log.warning("Poll inicial de voice-drop falhou: %s", error)

        while not self._stop.is_set():
            try:
                self._poll_once()
            except Exception as error:
                log.warning("Poll voice-drop falhou: %s", error)
            self._stop.wait(self.poll_seconds)

    def _fetch_active_drop(self) -> dict[str, Any] | None:
        for path in ("/api/voice-drop/active", "/api/nowplaying"):
            try:
                data = _fetch_json(f"{self.api_base}{path}")
            except Exception as error:
                log.debug("Fetch %s falhou: %s", path, error)
                continue
            drop = data.get("voice_drop")
            if isinstance(drop, dict) and drop.get("id"):
                return drop
        return None

    def _should_queue_drop(self, drop: dict[str, Any]) -> bool:
        listener_id = str(drop.get("listener_id") or "")
        if listener_id == HOSHINO_LISTENER_ID:
            return False
        if listener_id in NARRATOR_IDS:
            return True
        return self.mixer.narrator_busy()

    def _poll_once(self) -> None:
        if not self.mixer.voice_busy():
            pending = self.mixer.take_pending_drop()
            if pending:
                self._schedule_load_drop(pending)
                return

        drop = self._fetch_active_drop()
        if not drop:
            return

        drop_id = str(drop["id"])
        if self.mixer.has_played(drop_id):
            return

        listener_id = str(drop.get("listener_id") or "")
        if listener_id == HOSHINO_LISTENER_ID:
            self.mixer.mark_drop_seen(drop_id)
            return

        if self.mixer.voice_busy():
            if self._should_queue_drop(drop):
                self.mixer.queue_pending_drop(drop)
            return

        if listener_id not in NARRATOR_IDS and self.mixer.narrator_busy():
            self.mixer.queue_pending_drop(drop)
            return

        self._schedule_load_drop(drop)

    def _schedule_load_drop(self, drop: dict[str, Any]) -> None:
        drop_id = str(drop.get("id") or "")
        if not drop_id:
            return

        with self._inflight_lock:
            if drop_id in self._inflight_ids or self.mixer.has_played(drop_id):
                return
            self._inflight_ids.add(drop_id)

        worker = threading.Thread(
            target=self._load_drop_worker,
            args=(dict(drop),),
            daemon=True,
            name=f"discord-drop-{drop_id[:8]}",
        )
        worker.start()

    def _load_drop_worker(self, drop: dict[str, Any]) -> None:
        drop_id = str(drop.get("id") or "")
        try:
            rel_url = str(drop.get("url") or "")
            if not drop_id or not rel_url:
                return

            listener_id = str(drop.get("listener_id") or "")
            if listener_id == HOSHINO_LISTENER_ID:
                self.mixer.mark_drop_seen(drop_id)
                return

            if self.mixer.has_played(drop_id):
                return

            file_url = rel_url if rel_url.startswith("http") else f"{self.api_base}{rel_url}"
            is_narrator = listener_id == MIKU_LISTENER_ID
            label = "miku" if is_narrator else "ouvinte"
            log.info("Voice drop no Discord: %s (%s)", drop_id, label)

            try:
                # Mesmo decode PCM que ouvintes (sem filtro MIKU_AF) para volume igual.
                pcm = _decode_pcm(self.ffmpeg_path, file_url, variant="")
            except Exception as error:
                log.warning("Falha ao decodificar drop %s (%s): %s", drop_id, label, error)
                return

            if is_narrator:
                rms = audioop.rms(pcm, 2) if pcm else 0
                log.info("Miku pronta no Discord: %s (%d bytes, rms %d)", drop_id, len(pcm), rms)

            self.mixer.start_voice_pcm(drop_id, pcm, is_narrator=is_narrator)
        finally:
            with self._inflight_lock:
                self._inflight_ids.discard(drop_id)


class MixedRadioAudioSource(discord.AudioSource):
    """Radio + voice drops; envio Opus com pump de relogio fixo (menos travas no Discord)."""

    def __init__(
        self,
        stream_url: str,
        api_base: str,
        ffmpeg_path: str = "ffmpeg",
        poll_seconds: float = 0.4,
        stream_kind: str = "mp3",
        *,
        radio_target_buffer_ms: int = 12000,
        radio_prefill_ms: int = 10000,
        opus_bitrate_kbps: int = DEFAULT_OPUS_BITRATE_KBPS,
        opus_queue_target_ms: int = 2500,
        opus_fec: bool = True,
        opus_packet_loss: float = 0.15,
    ) -> None:
        self.stream_url = stream_url
        self.stream_kind = str(stream_kind or "mp3").strip().lower()
        self.api_base = api_base.rstrip("/")
        self.ffmpeg_path = ffmpeg_path
        frame_ms = int(FRAME_SEC * 1000)
        self._radio_target_bytes = max(
            DISCORD_FRAME_BYTES * 20,
            int(radio_target_buffer_ms / frame_ms) * DISCORD_FRAME_BYTES,
        )
        self._radio_prefill_bytes = max(
            DISCORD_FRAME_BYTES * 20,
            int(radio_prefill_ms / frame_ms) * DISCORD_FRAME_BYTES,
        )
        self._radio_low_water_bytes = max(
            DISCORD_FRAME_BYTES * 15,
            self._radio_target_bytes // 4,
        )
        self._opus_queue_target_frames = max(
            30,
            int(opus_queue_target_ms / frame_ms),
        )
        self._radio_lock = threading.Lock()
        self._voice_lock = threading.Lock()
        self._radio_chunks: deque[bytes] = deque()
        self._radio_pending = b""
        self._radio_buffer_bytes = 0
        self._voice_pcm = b""
        self._voice_pos = 0
        self._voice_active = False
        self._voice_is_narrator = False
        self._played_ids: set[str] = set()
        self._pending_drop: dict[str, Any] | None = None
        self._duck_envelope = 0.0
        self._duck_gain = 1.0
        self._voice_gain = 1.0
        self._last_radio_frame = b"\x00" * DISCORD_FRAME_BYTES
        self._radio_started = False
        self._radio_underruns = 0
        self._closed = False
        self._opus_lock = threading.Lock()
        self._opus_queue: deque[bytes] = deque()
        self._last_opus_packet: bytes | None = None
        self._next_read_at = time.monotonic()
        self._radio_hold_frames = 0
        from discord.opus import Encoder as OpusEncoder

        packet_loss = max(0.01, min(float(opus_packet_loss or 0.15), 0.5))
        self._opus_encoder = OpusEncoder(
            application="audio",
            bitrate=max(64, min(int(opus_bitrate_kbps or DEFAULT_OPUS_BITRATE_KBPS), 256)),
            fec=bool(opus_fec),
            expected_packet_loss=packet_loss,
            signal_type="music",
        )

        self._stream_thread = _RadioStreamThread(
            stream_url,
            ffmpeg_path,
            self,
            stream_kind=self.stream_kind,
        )
        self._voice_thread = _VoiceDropThread(api_base, ffmpeg_path, self, poll_seconds)
        self._opus_pump = _OpusPumpThread(self)
        self._stream_thread.start()
        self._voice_thread.start()
        self._opus_pump.start()

    def is_opus(self) -> bool:
        return True

    def wait_playback_ready(self, timeout_seconds: float = 25.0) -> bool:
        """Preenche buffers antes do Discord comecar a puxar (pratica comum em bots de musica)."""
        deadline = time.monotonic() + max(timeout_seconds, 5.0)
        while time.monotonic() < deadline:
            with self._radio_lock:
                radio_ok = self._radio_bytes_available_unlocked() >= self._radio_prefill_bytes
            with self._opus_lock:
                opus_ok = len(self._opus_queue) >= self._opus_queue_target_frames
            if radio_ok and opus_ok:
                log.info(
                    "Playback pronto: radio %d ms, fila Opus %d frames",
                    int(self._radio_bytes_available_unlocked() / DISCORD_FRAME_BYTES * FRAME_SEC * 1000),
                    len(self._opus_queue),
                )
                return True
            time.sleep(0.12)
        log.warning("Warmup de playback incompleto apos %.0fs", timeout_seconds)
        return False

    def _enqueue_opus(self, packet: bytes) -> None:
        if not packet:
            return
        with self._opus_lock:
            self._opus_queue.append(packet)
            while len(self._opus_queue) > OPUS_QUEUE_HIGH_WATER_FRAMES:
                self._opus_queue.popleft()
            while len(self._opus_queue) > OPUS_QUEUE_MAX_FRAMES:
                self._opus_queue.popleft()

    def _radio_bytes_available_unlocked(self) -> int:
        return self._radio_buffer_bytes + len(self._radio_pending)

    def _reset_radio_stream_buffer(self) -> None:
        with self._radio_lock:
            self._radio_chunks.clear()
            self._radio_pending = b""
            self._radio_buffer_bytes = 0
            self._radio_started = False
            self._radio_underruns = 0
            self._radio_hold_frames = 0
        with self._opus_lock:
            self._opus_queue.clear()
            self._last_opus_packet = None
        self._next_read_at = time.monotonic()

    def _trim_radio_buffer_unlocked(self) -> None:
        while self._radio_bytes_available_unlocked() > RADIO_BUFFER_LIMIT:
            if len(self._radio_pending) >= DISCORD_FRAME_BYTES:
                self._radio_pending = self._radio_pending[DISCORD_FRAME_BYTES:]
                continue
            if self._radio_chunks:
                removed = self._radio_chunks.popleft()
                excess = self._radio_bytes_available_unlocked() - RADIO_BUFFER_LIMIT
                drop = min(len(removed), max(excess, DISCORD_FRAME_BYTES))
                if drop >= len(removed):
                    self._radio_buffer_bytes = max(0, self._radio_buffer_bytes - len(removed))
                else:
                    self._radio_chunks.appendleft(removed[drop:])
                    self._radio_buffer_bytes = max(0, self._radio_buffer_bytes - drop)
                continue
            break

    def _append_radio_chunk(self, chunk: bytes) -> None:
        if not chunk:
            return
        with self._radio_lock:
            self._radio_chunks.append(chunk)
            self._radio_buffer_bytes += len(chunk)
            self._trim_radio_buffer_unlocked()
            self._stabilize_radio_buffer_unlocked()

    def _drop_one_radio_frame_unlocked(self) -> bool:
        if len(self._radio_pending) >= DISCORD_FRAME_BYTES:
            self._radio_pending = self._radio_pending[DISCORD_FRAME_BYTES:]
            return True
        if self._radio_chunks:
            removed = self._radio_chunks.popleft()
            if len(removed) <= DISCORD_FRAME_BYTES:
                self._radio_buffer_bytes = max(0, self._radio_buffer_bytes - len(removed))
                return True
            self._radio_chunks.appendleft(removed[DISCORD_FRAME_BYTES:])
            self._radio_buffer_bytes = max(0, self._radio_buffer_bytes - DISCORD_FRAME_BYTES)
            return True
        return False

    def _stabilize_radio_buffer_unlocked(self) -> None:
        """Mantem atraso proximo do alvo (jitter buffer), em vez de colar na borda do buffer."""
        target = getattr(self, "_radio_target_bytes", RADIO_TARGET_BUFFER_BYTES)
        while self._radio_bytes_available_unlocked() > target:
            if not self._drop_one_radio_frame_unlocked():
                break

    def has_played(self, drop_id: str) -> bool:
        with self._voice_lock:
            return drop_id in self._played_ids

    def mark_drop_seen(self, drop_id: str) -> None:
        with self._voice_lock:
            self._played_ids.add(drop_id)
            if len(self._played_ids) > 128:
                self._played_ids = set(list(self._played_ids)[-64:])

    def voice_busy(self) -> bool:
        with self._voice_lock:
            return self._voice_active

    def narrator_busy(self) -> bool:
        with self._voice_lock:
            return self._voice_active and self._voice_is_narrator

    def queue_pending_drop(self, drop: dict[str, Any]) -> None:
        with self._voice_lock:
            if not self._pending_drop:
                self._pending_drop = dict(drop)

    def take_pending_drop(self) -> dict[str, Any] | None:
        with self._voice_lock:
            pending = self._pending_drop
            self._pending_drop = None
            return pending

    def start_voice_pcm(self, drop_id: str, pcm: bytes, *, is_narrator: bool) -> None:
        with self._voice_lock:
            self._played_ids.add(drop_id)
            if len(self._played_ids) > 128:
                self._played_ids = set(list(self._played_ids)[-64:])
            self._voice_pcm = pcm
            self._voice_pos = 0
            self._voice_active = True
            self._voice_is_narrator = is_narrator
            self._voice_gain = VOICE_DROP_GAIN
            self._duck_envelope = 0.0
            self._duck_gain = 1.0

    def _read_radio_frame(self) -> bytes:
        prefill = getattr(self, "_radio_prefill_bytes", RADIO_PREFILL_BYTES)
        low_water = getattr(self, "_radio_low_water_bytes", RADIO_LOW_WATER_BYTES)

        with self._radio_lock:
            available = self._radio_bytes_available_unlocked()
            if not self._radio_started and available < prefill:
                return b"\x00" * DISCORD_FRAME_BYTES

            if self._radio_started and available < low_water:
                self._radio_underruns += 1
                if any(self._last_radio_frame) and self._radio_hold_frames < RADIO_UNDERRUN_HOLD_MAX:
                    self._radio_hold_frames += 1
                    return self._last_radio_frame
                return b"\x00" * DISCORD_FRAME_BYTES

            while len(self._radio_pending) < DISCORD_FRAME_BYTES:
                if not self._radio_chunks:
                    break
                next_chunk = self._radio_chunks.popleft()
                self._radio_buffer_bytes = max(0, self._radio_buffer_bytes - len(next_chunk))
                self._radio_pending += next_chunk

            if len(self._radio_pending) >= DISCORD_FRAME_BYTES:
                frame = self._radio_pending[:DISCORD_FRAME_BYTES]
                self._radio_pending = self._radio_pending[DISCORD_FRAME_BYTES:]
                self._last_radio_frame = frame
                self._radio_started = True
                self._radio_underruns = 0
                self._radio_hold_frames = 0
                return frame

        return b"\x00" * DISCORD_FRAME_BYTES

    def _update_ducking(self, voice_frame: bytes, voice_playing: bool, *, is_narrator: bool) -> float:
        if is_narrator:
            self._duck_envelope = 0.0
            self._duck_gain = 1.0
            return 1.0

        duck_floor = DUCK_FLOOR

        if not voice_playing:
            follow = 0.16
            self._duck_envelope = max(0.0, self._duck_envelope * (1.0 - follow))
            target = (
                1.0
                if self._duck_envelope < 0.02
                else _sidechain_duck_target(self._duck_envelope, floor=duck_floor)
            )
            time_constant = DUCK_RELEASE_SEC
        else:
            rms = audioop.rms(voice_frame, 2) / 32768.0
            voice_level = min(1.0, rms * VOICE_SIDECHAIN_SENSITIVITY)
            follow = 0.5 if voice_level > self._duck_envelope else 0.16
            self._duck_envelope += (voice_level - self._duck_envelope) * follow
            target = _sidechain_duck_target(self._duck_envelope, floor=duck_floor)
            time_constant = DUCK_ATTACK_SEC if voice_level > 0.06 else DUCK_RELEASE_SEC

        alpha = min(1.0, FRAME_SEC / max(time_constant, 0.001))
        self._duck_gain += (target - self._duck_gain) * alpha
        return self._duck_gain

    def render_pcm_frame(self) -> bytes:
        radio = self._read_radio_frame()
        with self._voice_lock:
            if not self._voice_active:
                return radio
            voice, voice_playing, is_narrator = self._read_voice_frame_unlocked()
            duck = self._update_ducking(voice, voice_playing, is_narrator=is_narrator)
            gain = self._voice_gain if voice_playing else 1.0
        return _mix_frames(
            radio,
            voice,
            duck,
            gain,
            voice_active=voice_playing,
            is_narrator=is_narrator,
        )

    def read(self) -> bytes:
        if self._closed:
            return b""

        from discord.opus import OPUS_SILENCE

        now = time.monotonic()
        wait = self._next_read_at - now
        if wait > 0:
            time.sleep(wait)
        self._next_read_at = time.monotonic() + FRAME_SEC

        # Discord as vezes chama read() em rajada e esvazia a fila -> micro-travas.
        for attempt in range(12):
            with self._opus_lock:
                depth = len(self._opus_queue)
                if depth >= self._opus_queue_target_frames or (depth > 0 and attempt >= 8):
                    packet = self._opus_queue.popleft()
                    self._last_opus_packet = packet
                    return packet
            time.sleep(0.002)

        if self._last_opus_packet:
            return self._last_opus_packet
        return OPUS_SILENCE

    def _read_voice_frame_unlocked(self) -> tuple[bytes, bool, bool]:
        if not self._voice_active:
            return b"\x00" * DISCORD_FRAME_BYTES, False, False

        is_narrator = self._voice_is_narrator
        end = self._voice_pos + DISCORD_FRAME_BYTES
        frame = self._voice_pcm[self._voice_pos:end]
        self._voice_pos = end
        if self._voice_pos >= len(self._voice_pcm):
            self._voice_active = False
            self._voice_is_narrator = False
        if len(frame) < DISCORD_FRAME_BYTES:
            frame += b"\x00" * (DISCORD_FRAME_BYTES - len(frame))
        return frame, True, is_narrator

    def cleanup(self) -> None:
        self._closed = True
        self._opus_pump.stop()
        self._stream_thread.stop()
        self._voice_thread.stop()
        self._opus_pump.join(timeout=3.0)
        with self._opus_lock:
            self._opus_queue.clear()
