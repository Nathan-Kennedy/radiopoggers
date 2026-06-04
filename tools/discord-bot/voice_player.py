from __future__ import annotations

import asyncio
import logging
import shutil
import time

import discord

from voice_mixer import MixedRadioAudioSource

log = logging.getLogger("radiopoggers.discord.voice")

FFMPEG_BEFORE = (
    "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5 "
    "-protocol_whitelist file,http,https,tcp,tls,crypto "
    "-fflags +genpts -thread_queue_size 8192 -rw_timeout 15000000 "
    "-multiple_requests 1 -user_agent RadioPoggersDiscordBot/1.0"
)
FFMPEG_OPTIONS = "-vn -loglevel error -fec true -packet_loss 15"


def bot_voice_channel(guild: discord.Guild, client: discord.Client | None = None) -> discord.VoiceChannel | None:
    me = guild.me
    if me and me.voice and me.voice.channel:
        return me.voice.channel if isinstance(me.voice.channel, discord.VoiceChannel) else None

    if client:
        for voice in client.voice_clients:
            if voice.guild and voice.guild.id == guild.id and voice.channel:
                return voice.channel if isinstance(voice.channel, discord.VoiceChannel) else None
    voice = guild.voice_client
    if voice and voice.channel and isinstance(voice.channel, discord.VoiceChannel):
        return voice.channel
    return None


def guild_voice_clients(guild: discord.Guild, client: discord.Client | None = None) -> list[discord.VoiceClient]:
    voices: list[discord.VoiceClient] = []
    seen: set[int] = set()

    if client:
        for voice in client.voice_clients:
            if voice.guild and voice.guild.id == guild.id and id(voice) not in seen:
                voices.append(voice)
                seen.add(id(voice))

    voice = guild.voice_client
    if voice and id(voice) not in seen:
        voices.append(voice)
    return voices


class RadioVoicePlayer:
    def __init__(
        self,
        stream_url: str,
        ffmpeg_path: str = "ffmpeg",
        *,
        stream_kind: str = "mp3",
        api_base: str = "",
        voice_drop_poll_seconds: float = 0.4,
        radio_target_buffer_ms: int = 12000,
        radio_prefill_ms: int = 10000,
        opus_bitrate_kbps: int = 128,
        opus_queue_target_ms: int = 2500,
        radio_warmup_timeout_sec: int = 25,
        opus_fec: bool = True,
        opus_packet_loss: float = 0.15,
    ) -> None:
        self.stream_url = stream_url
        self.stream_kind = str(stream_kind or "mp3").strip().lower()
        self.ffmpeg_path = ffmpeg_path or "ffmpeg"
        self.api_base = str(api_base or "").strip()
        self.voice_drop_poll_seconds = max(float(voice_drop_poll_seconds or 0.4), 0.25)
        self.radio_target_buffer_ms = max(int(radio_target_buffer_ms or 2000), 400)
        self.radio_prefill_ms = max(int(radio_prefill_ms or 7200), 400)
        self.opus_bitrate_kbps = max(64, min(int(opus_bitrate_kbps or 128), 256))
        self.opus_queue_target_ms = max(500, int(opus_queue_target_ms or 2500))
        self.radio_warmup_timeout_sec = max(8, int(radio_warmup_timeout_sec or 25))
        self.opus_fec = bool(opus_fec)
        self.opus_packet_loss = max(0.01, min(float(opus_packet_loss or 0.15), 0.5))

    def _build_source(self) -> discord.AudioSource:
        if self.api_base:
            log.info(
                "Discord com mixer (%s) + voice drops via %s",
                self.stream_kind.upper(),
                self.api_base,
            )
            return MixedRadioAudioSource(
                self.stream_url,
                self.api_base,
                self.ffmpeg_path,
                poll_seconds=self.voice_drop_poll_seconds,
                stream_kind=self.stream_kind,
                radio_target_buffer_ms=self.radio_target_buffer_ms,
                radio_prefill_ms=self.radio_prefill_ms,
                opus_bitrate_kbps=self.opus_bitrate_kbps,
                opus_queue_target_ms=self.opus_queue_target_ms,
                opus_fec=self.opus_fec,
                opus_packet_loss=self.opus_packet_loss,
            )

        return discord.FFmpegOpusAudio(
            self.stream_url,
            executable=self.ffmpeg_path,
            before_options=FFMPEG_BEFORE,
            options=FFMPEG_OPTIONS,
        )

    def _after_play(self, guild_id: int, error: Exception | None) -> None:
        if error:
            log.warning("Stream parou na guild %s: %s", guild_id, error)

    async def ensure_playing(
        self,
        guild: discord.Guild,
        channel: discord.VoiceChannel,
        *,
        restart_stream: bool = True,
    ) -> discord.VoiceClient:
        voice = guild.voice_client

        if voice and voice.is_connected():
            if voice.channel and voice.channel.id != channel.id:
                await voice.move_to(channel)
        else:
            voice = await channel.connect(reconnect=True, timeout=30.0)

        if (
            not restart_stream
            and voice.is_connected()
            and voice.channel
            and voice.channel.id == channel.id
            and voice.is_playing()
        ):
            return voice

        if voice.is_playing() or voice.is_paused():
            source = voice.source
            voice.stop()
            if source and hasattr(source, "cleanup"):
                try:
                    source.cleanup()
                except Exception as error:
                    log.warning("Falha ao limpar audio source: %s", error)
            await asyncio.sleep(0.3)

        source = self._build_source()
        if isinstance(source, MixedRadioAudioSource):
            warmup_timeout = float(self.radio_warmup_timeout_sec)
            ready = await asyncio.to_thread(source.wait_playback_ready, warmup_timeout)
            if not ready:
                log.warning(
                    "Warmup incompleto (%ss); tocando mesmo assim — aguarde alguns segundos",
                    int(warmup_timeout),
                )

        voice.play(
            source,
            after=lambda error, gid=guild.id: self._after_play(gid, error),
        )
        return voice

    async def _teardown_voice_client(self, voice: discord.VoiceClient) -> bool:
        try:
            source = voice.source
            if voice.is_playing() or voice.is_paused():
                voice.stop()

            if source and hasattr(source, "cleanup"):
                try:
                    source.cleanup()
                except Exception as error:
                    log.warning("Falha ao limpar audio source: %s", error)

            await asyncio.sleep(0.25)

            if voice.is_connected():
                await asyncio.wait_for(voice.disconnect(force=True), timeout=15.0)

            for _ in range(30):
                if not voice.is_connected():
                    return True
                await asyncio.sleep(0.1)

            if voice.is_connected():
                log.warning("Voice client ainda conectado apos disconnect, tentando de novo")
                await voice.disconnect(force=True)
                await asyncio.sleep(0.3)
            return not voice.is_connected()
        except asyncio.TimeoutError:
            log.warning("Timeout ao desconectar voice client")
            try:
                if voice.is_connected():
                    await voice.disconnect(force=True)
            except Exception:
                pass
            return not voice.is_connected()
        except Exception:
            log.exception("Erro ao desmontar voice client")
            try:
                if voice.is_connected():
                    await voice.disconnect(force=True)
            except Exception:
                pass
            return False

    async def stop_all(self, client: discord.Client) -> bool:
        ok = True
        seen: set[int] = set()
        for voice in list(client.voice_clients):
            guild = voice.guild
            if not guild or guild.id in seen:
                continue
            seen.add(guild.id)
            if not await self.stop(guild, client=client):
                ok = False
        for guild in list(client.guilds):
            if guild.id in seen:
                continue
            if bot_voice_channel(guild, client):
                seen.add(guild.id)
                if not await self.stop(guild, client=client):
                    ok = False
        return ok

    async def stop(self, guild: discord.Guild, *, client: discord.Client | None = None) -> bool:
        voices = guild_voice_clients(guild, client)
        if voices:
            ok = True
            for voice in list(voices):
                if not await self._teardown_voice_client(voice):
                    ok = False
            if not bot_voice_channel(guild, client):
                return ok
            log.warning("Ainda aparece em call apos teardown; tentando saida forcada guild %s", guild.id)

        channel = bot_voice_channel(guild, client)
        if not channel or not client:
            return not bot_voice_channel(guild, client)

        log.warning("Conexao de voz perdida no client; reconectando para sair de %s", channel.name)
        temp: discord.VoiceClient | None = None
        try:
            temp = await channel.connect(reconnect=False, timeout=20.0)
            return await self._teardown_voice_client(temp)
        except Exception as error:
            log.exception("Falha na saida forcada de voz: %s", error)
            if temp and temp.is_connected():
                try:
                    return await self._teardown_voice_client(temp)
                except Exception:
                    pass
            return False


def resolve_ffmpeg_path(configured: str = "") -> str:
    if configured and shutil.which(configured):
        return configured
    if configured:
        return configured
    found = shutil.which("ffmpeg")
    if not found:
        raise RuntimeError("FFmpeg nao encontrado no PATH. Instale ffmpeg para o bot tocar no Discord.")
    return found


async def wait_for_voice_ready(voice: discord.VoiceClient, timeout: float = 8.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if voice.is_playing():
            return True
        await asyncio.sleep(0.25)
    return voice.is_connected()
