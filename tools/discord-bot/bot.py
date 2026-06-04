#!/usr/bin/env python3
"""Bot Discord da RADIO NO GRALE — ponte de audio + comandos da radio."""

from __future__ import annotations

import asyncio
import logging
import re
import signal
import sys
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse

from runtime_guard import (
    SHUTDOWN_FILE,
    clear_shutdown_request,
    ensure_single_instance,
    require_voice_dependencies,
)

require_voice_dependencies()

import discord
from discord import app_commands

from config import load_config, load_token, resolve_discord_stream
from radio_api import (
    fetch_json,
    inspect_spotify,
    play_spotify_if_ready,
    play_track_immediate,
    resolve_play_query,
    send_heartbeat,
    skip_track,
    spotify_import_status,
    start_spotify_import,
)
from voice_player import RadioVoicePlayer, bot_voice_channel, resolve_ffmpeg_path

logging.basicConfig(level=logging.INFO, format="[discord-bot] %(levelname)s %(message)s")
log = logging.getLogger("radiopoggers.discord")

CONFIG = load_config()
TOKEN = load_token()
APPLICATION_ID = int(CONFIG["application_id"] or "0")
STATION_NAME = CONFIG["station_name"]
API_BASE = CONFIG["api_base_url"]
PLAYER_URL = CONFIG["player_url"]
STREAM_URL, STREAM_KIND = resolve_discord_stream(CONFIG)
AZURACAST_PUBLIC = CONFIG["azuracast_public_url"]
STATUS_SECONDS = CONFIG["status_update_seconds"]
PRESENCE_PREFIX = "/play · "
PRESENCE_MAX_LEN = 128
GUILD_IDS: list[int] = CONFIG["guild_ids"]
GUILD_OBJECTS: list[discord.Object] = [discord.Object(id=guild_id) for guild_id in GUILD_IDS]
IMPORT_POLL_SECONDS = max(int(CONFIG.get("import_poll_seconds") or 3), 2)
IMPORT_TIMEOUT_SECONDS = max(int(CONFIG.get("import_timeout_seconds") or 1800), 120)
ALONE_LEAVE_SECONDS = max(int(CONFIG.get("alone_leave_seconds") or 30), 10)

FFMPEG_PATH = resolve_ffmpeg_path(str(CONFIG.get("ffmpeg_path") or ""))
VOICE = RadioVoicePlayer(
    STREAM_URL,
    FFMPEG_PATH,
    stream_kind=STREAM_KIND,
    api_base=API_BASE,
    voice_drop_poll_seconds=float(CONFIG.get("voice_drop_poll_seconds") or 0.4),
    radio_target_buffer_ms=int(CONFIG.get("radio_target_buffer_ms") or 12000),
    radio_prefill_ms=int(CONFIG.get("radio_prefill_ms") or 10000),
    opus_queue_target_ms=int(CONFIG.get("radio_opus_queue_ms") or 3000),
    opus_bitrate_kbps=int(CONFIG.get("discord_opus_bitrate_kbps") or 128),
    radio_warmup_timeout_sec=int(CONFIG.get("radio_warmup_timeout_sec") or 25),
    opus_fec=bool(CONFIG.get("radio_opus_fec", True)),
    opus_packet_loss=float(CONFIG.get("radio_opus_packet_loss") or 0.15),
)

SPOTIFY_URL_RE = re.compile(r"^https://open\.spotify\.com/(playlist|track)/[A-Za-z0-9]+", re.I)

_alone_since: dict[int, float] = {}
_stream_stalled: dict[int, int] = {}
_shutting_down = False

intents = discord.Intents.default()
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)


def slash_command(**kwargs: Any):
    """Registra slash commands globais (aparecem em todo servidor com o bot)."""
    return tree.command(**kwargs)


def listener_id(user: discord.abc.User) -> str:
    return f"discord:{user.id}"


def bot_voice_channel_for_guild(guild: discord.Guild) -> discord.VoiceChannel | None:
    return bot_voice_channel(guild, client)


def count_humans_in_channel(channel: discord.VoiceChannel) -> int:
    return sum(1 for member in channel.members if not member.bot)


def refresh_alone_timer(guild: discord.Guild) -> None:
    channel = bot_voice_channel_for_guild(guild)
    if not channel:
        _alone_since.pop(guild.id, None)
        return

    if count_humans_in_channel(channel) > 0:
        _alone_since.pop(guild.id, None)
        return

    if guild.id not in _alone_since:
        _alone_since[guild.id] = time.monotonic()
        log.info(
            "Bot sozinho em %s — sai em %ss se ninguem entrar",
            channel.name,
            ALONE_LEAVE_SECONDS,
        )


def is_valid_spotify_url(value: str) -> bool:
    return bool(SPOTIFY_URL_RE.match(str(value or "").strip()))


def resolve_art_url(raw_url: str) -> str:
    raw = str(raw_url or "").strip()
    if not raw:
        return ""
    try:
        parsed = urlparse(raw)
        if parsed.hostname in {"localhost", "127.0.0.1"} and parsed.path:
            return f"{AZURACAST_PUBLIC}{parsed.path}"
    except ValueError:
        return raw
    return raw


def format_presence_label(song: dict[str, str] | None = None) -> str:
    """Status na lista de membros: comando /play + faixa (como outros bots mostram .help)."""
    if song:
        core = f"{song['artist']} — {song['title']}"
    else:
        core = f"{STATION_NAME} — entre na call"
    return f"{PRESENCE_PREFIX}{core}"[:PRESENCE_MAX_LEN]


def song_from_now_playing(payload: dict[str, Any]) -> dict[str, str]:
    now = payload.get("now_playing") if isinstance(payload.get("now_playing"), dict) else {}
    song = now.get("song") if isinstance(now.get("song"), dict) else {}
    title = str(song.get("title") or "Ao vivo").strip() or "Ao vivo"
    artist = str(song.get("artist") or STATION_NAME).strip() or STATION_NAME
    album = str(song.get("album") or "").strip()
    art = resolve_art_url(str(song.get("art") or ""))
    elapsed = int(now.get("elapsed") or 0)
    duration = int(now.get("duration") or song.get("length") or 0)
    return {
        "title": title,
        "artist": artist,
        "album": album,
        "art": art,
        "elapsed": str(elapsed),
        "duration": str(duration),
    }


def build_now_playing_embed(song: dict[str, str]) -> discord.Embed:
    embed = discord.Embed(title=song["title"], description=song["artist"], colour=0xE11D2E)
    embed.set_author(name=STATION_NAME)
    if song.get("album"):
        embed.add_field(name="Album", value=song["album"], inline=True)
    if song.get("duration") not in {"", "0"} and song.get("elapsed"):
        elapsed = int(song["elapsed"])
        duration = int(song["duration"])
        embed.add_field(
            name="Progresso",
            value=f"{elapsed // 60}:{elapsed % 60:02d} / {duration // 60}:{duration % 60:02d}",
            inline=True,
        )
    if PLAYER_URL:
        embed.add_field(name="Player", value=f"[Abrir no navegador]({PLAYER_URL})", inline=False)
    if STREAM_URL:
        embed.add_field(name="Stream", value=f"[Ouvir direto]({STREAM_URL})", inline=False)
    if song.get("art"):
        embed.set_thumbnail(url=song["art"])
    embed.set_footer(text="RADIO NO GRALE — ponte Discord → radio com Miku no ar")
    return embed


def member_voice_channel(interaction: discord.Interaction) -> discord.VoiceChannel | None:
    if not isinstance(interaction.user, discord.Member):
        return None
    voice = interaction.user.voice
    if not voice or not voice.channel or not isinstance(voice.channel, discord.VoiceChannel):
        return None
    return voice.channel


async def ensure_member_in_voice(interaction: discord.Interaction) -> discord.VoiceChannel | None:
    channel = member_voice_channel(interaction)
    if channel:
        return channel
    await interaction.response.send_message(
        "Entre em um **canal de voz** antes de usar este comando. O bot entra no seu canal e toca a radio.",
        ephemeral=True,
    )
    return None


async def connect_radio_voice(
    interaction: discord.Interaction,
    channel: discord.VoiceChannel,
    *,
    restart_stream: bool = True,
) -> discord.VoiceClient:
    guild = interaction.guild
    if not guild:
        raise RuntimeError("Comando so funciona dentro de um servidor.")

    voice = await asyncio.wait_for(
        VOICE.ensure_playing(guild, channel, restart_stream=restart_stream),
        timeout=40.0,
    )
    asyncio.create_task(asyncio.to_thread(send_heartbeat, API_BASE, listener_id(interaction.user), True))
    refresh_alone_timer(guild)
    return voice


def is_bot_playing_in_channel(guild: discord.Guild | None, channel: discord.VoiceChannel) -> bool:
    if not guild:
        return False
    active_channel = bot_voice_channel(guild, client)
    if not active_channel or active_channel.id != channel.id:
        return False
    voice = guild.voice_client
    return bool(voice and voice.is_playing())


async def safe_followup(interaction: discord.Interaction, content: str, **kwargs) -> None:
    try:
        await interaction.followup.send(content, **kwargs)
    except discord.HTTPException as error:
        log.warning("Falha ao responder comando Discord: %s", error)


def extract_track_id_from_job(status: dict[str, Any]) -> str:
    result = status.get("result") if isinstance(status.get("result"), dict) else {}
    vote_payload = result.get("vote_payload") if isinstance(result.get("vote_payload"), dict) else {}
    track_id = str(
        vote_payload.get("track_id")
        or vote_payload.get("first_track_id")
        or ""
    ).strip()
    if track_id:
        return track_id

    manifest = result.get("manifest") if isinstance(result.get("manifest"), dict) else {}
    items = manifest.get("items") if isinstance(manifest.get("items"), list) else []
    for item in items:
        if not isinstance(item, dict):
            continue
        if str(item.get("status") or "").lower() != "ready":
            continue
        candidate = str(item.get("spotify_id") or item.get("id") or "").strip()
        if candidate:
            return candidate
    return ""


async def import_and_play_spotify(spotify_url: str) -> dict[str, Any]:
    ready = await asyncio.to_thread(play_spotify_if_ready, API_BASE, spotify_url)
    if ready.get("need_import") is not True and ready.get("ready") is not False:
        return ready

    started = await asyncio.to_thread(start_spotify_import, API_BASE, spotify_url)
    if not started.get("ok"):
        raise RuntimeError(str(started.get("error") or "Falha ao iniciar importacao Spotify."))

    job_id = str(started.get("job_id") or "").strip()
    if not job_id:
        raise RuntimeError("Importacao sem job_id.")

    deadline = time.monotonic() + IMPORT_TIMEOUT_SECONDS
    last_message = "Baixando e sincronizando playlist..."

    while time.monotonic() < deadline:
        status = await asyncio.to_thread(spotify_import_status, API_BASE, job_id)
        phase = str(status.get("phase") or status.get("status") or "").strip()
        message = str(status.get("message") or last_message).strip()
        last_message = message or last_message

        if str(status.get("status") or "").lower() == "error":
            raise RuntimeError(str(status.get("error") or message or "Importacao falhou."))

        if str(status.get("status") or "").lower() == "done":
            track_id = extract_track_id_from_job(status)
            if not track_id:
                replay = await asyncio.to_thread(play_spotify_if_ready, API_BASE, spotify_url)
                if replay.get("ok"):
                    return replay
                raise RuntimeError("Importacao concluida, mas nenhuma faixa pronta foi encontrada.")
            played = await asyncio.to_thread(play_track_immediate, API_BASE, track_id)
            played["import_message"] = message
            played["phase"] = phase
            return played

        await asyncio.sleep(IMPORT_POLL_SECONDS)

    raise RuntimeError("Importacao Spotify demorou demais. Tente de novo em alguns minutos.")


@slash_command(name="play", description="Entra no seu canal de voz e toca a radio.")
@app_commands.describe(
    musica="Opcional: nome da musica/artista, ou link Spotify (open.spotify.com)",
)
async def cmd_play(interaction: discord.Interaction, musica: str | None = None) -> None:
    channel = member_voice_channel(interaction)
    if not channel:
        await interaction.response.send_message(
            "Entre em um **canal de voz** antes de usar este comando. O bot entra no seu canal e toca a radio.",
            ephemeral=True,
        )
        return

    raw = str(musica or "").strip()
    if raw and is_valid_spotify_url(raw) is False and raw.lower().startswith("http"):
        await interaction.response.send_message(
            "Use um link Spotify valido ou digite so o nome da musica/artista.",
            ephemeral=True,
        )
        return

    await interaction.response.defer(thinking=False)

    guild = interaction.guild
    already_playing = is_bot_playing_in_channel(guild, channel)

    try:
        if not already_playing:
            await safe_followup(interaction, f"Conectando em **{channel.name}**...")
            await connect_radio_voice(interaction, channel, restart_stream=True)
        else:
            asyncio.create_task(asyncio.to_thread(send_heartbeat, API_BASE, listener_id(interaction.user), True))

        if not raw:
            try:
                payload = await asyncio.wait_for(
                    asyncio.to_thread(fetch_json, f"{API_BASE}/api/nowplaying"),
                    timeout=10.0,
                )
                song = song_from_now_playing(payload)
                embed = build_now_playing_embed(song)
                await safe_followup(
                    interaction,
                    f"Tocando **{STATION_NAME}** ao vivo em **{channel.name}** (Miku no stream).",
                    embed=embed,
                )
            except Exception as error:
                log.warning("Now playing indisponivel apos conectar voz: %s", error)
                await safe_followup(
                    interaction,
                    f"Conectado em **{channel.name}** — radio no ar.",
                )
            return

        if is_valid_spotify_url(raw):
            await safe_followup(interaction, f"Processando Spotify... aguarde.")
            result = await import_and_play_spotify(raw)
        else:
            await safe_followup(interaction, f"Buscando **{raw}** na biblioteca e no Spotify...")
            resolved = await asyncio.to_thread(resolve_play_query, API_BASE, raw)
            title = str(resolved.get("title") or raw)
            artist = str(resolved.get("artist") or "Artista")
            source = str(resolved.get("source") or "")
            spotify_url = str(resolved.get("spotify_url") or "").strip()

            if source == "library":
                track_id = str(resolved.get("track_id") or "").strip()
                result = await asyncio.to_thread(play_track_immediate, API_BASE, track_id)
                result["playlist_title"] = ""
            elif spotify_url:
                result = await import_and_play_spotify(spotify_url)
            else:
                raise RuntimeError("Busca nao retornou faixa.")

            result.setdefault("title", title)
            result.setdefault("artist", artist)

        title = str(result.get("title") or "Nova faixa")
        artist = str(result.get("artist") or "Artista")
        playlist_title = str(result.get("playlist_title") or "").strip()
        extra = f"Playlist **{playlist_title}** na radio." if playlist_title else "Faixa colocada na frente da fila da radio."
        await safe_followup(
            interaction,
            f"**{channel.name}** — **{artist} — {title}**\n{extra}\n_Miku narra pelo stream da radio._",
        )
    except asyncio.TimeoutError:
        await safe_followup(interaction, "Timeout ao conectar o audio. Tente `/play` de novo.")
    except HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace") if hasattr(error, "read") else str(error)
        await safe_followup(interaction, f"Falha na API da radio: {detail}")
    except Exception as error:
        log.exception("Erro no /play")
        await safe_followup(interaction, f"Nao deu para tocar agora: {error}")


async def run_skip(interaction: discord.Interaction) -> None:
    await interaction.response.defer(thinking=False, ephemeral=True)
    try:
        result = await asyncio.to_thread(skip_track, API_BASE)
        message = str(result.get("message") or "Faixa pulada.")
        await interaction.followup.send(message, ephemeral=True)
    except HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace") if hasattr(error, "read") else str(error)
        await interaction.followup.send(f"Falha ao pular: {detail}", ephemeral=True)
    except (URLError, TimeoutError) as error:
        await interaction.followup.send(f"API offline em `{API_BASE}`: {error}", ephemeral=True)
    except Exception as error:
        log.exception("Erro no skip")
        await interaction.followup.send(f"Nao deu para pular: {error}", ephemeral=True)


async def run_stop(interaction: discord.Interaction) -> None:
    guild = interaction.guild
    if not guild:
        await interaction.response.send_message("Use este comando dentro de um servidor.", ephemeral=True)
        return

    await interaction.response.defer(thinking=False, ephemeral=True)

    channel = bot_voice_channel(guild, client)
    if not channel:
        await interaction.followup.send(
            "O bot **nao esta** em nenhum canal de voz neste servidor.",
            ephemeral=True,
        )
        return

    channel_name = channel.name

    try:
        stopped = await VOICE.stop(guild, client=client)
        await asyncio.to_thread(send_heartbeat, API_BASE, listener_id(interaction.user), False)
        _alone_since.pop(guild.id, None)

        still_in_call = bot_voice_channel(guild, client)
        if stopped and not still_in_call:
            await interaction.followup.send(
                f"Parei o audio e sai de **{channel_name}**.",
                ephemeral=True,
            )
        elif still_in_call:
            await interaction.followup.send(
                f"Tentei sair de **{channel_name}**, mas o Discord ainda mostra o bot na call. "
                "Use `/stop` de novo ou reinicie o bot com `start-discord-bot.ps1`.",
                ephemeral=True,
            )
        else:
            await interaction.followup.send(
                f"Nao consegui sair de **{channel_name}**. Tente `/stop` de novo.",
                ephemeral=True,
            )
    except Exception as error:
        log.exception("Erro no stop/parar")
        await interaction.followup.send(f"Nao deu para sair da call: {error}", ephemeral=True)


@slash_command(name="skip", description="Pula a musica atual na radio (instantaneo, sem votacao).")
async def cmd_skip(interaction: discord.Interaction) -> None:
    await run_skip(interaction)


@slash_command(name="pular", description="Alias de /skip — pula a musica atual na radio.")
async def cmd_pular(interaction: discord.Interaction) -> None:
    await run_skip(interaction)


@slash_command(name="stop", description="Para o audio no Discord e sai do canal de voz.")
async def cmd_stop(interaction: discord.Interaction) -> None:
    await run_stop(interaction)


@slash_command(name="parar", description="Alias de /stop — sai do canal de voz.")
async def cmd_parar(interaction: discord.Interaction) -> None:
    await run_stop(interaction)


@slash_command(name="tocando", description="Mostra a musica que esta tocando agora na radio.")
async def cmd_tocando(interaction: discord.Interaction) -> None:
    await interaction.response.defer(thinking=True)
    try:
        payload = await asyncio.to_thread(fetch_json, f"{API_BASE}/api/nowplaying")
        song = song_from_now_playing(payload)
        await interaction.followup.send(embed=build_now_playing_embed(song))
    except (HTTPError, URLError, TimeoutError, ValueError) as error:
        await interaction.followup.send(
            f"Nao consegui ler a radio agora. A API local esta rodando em `{API_BASE}`?\n`{error}`"
        )


@slash_command(name="ouvir", description="Links do player e do stream da radio.")
async def cmd_ouvir(interaction: discord.Interaction) -> None:
    lines = [f"**{STATION_NAME}**"]
    if PLAYER_URL:
        lines.append(f"Player: {PLAYER_URL}")
    if STREAM_URL:
        lines.append(f"Stream MP3: {STREAM_URL}")
    await interaction.response.send_message("\n".join(lines))


@slash_command(name="site", description="Link do site Alta Cupula / Radio no Grale.")
async def cmd_site(interaction: discord.Interaction) -> None:
    if not PLAYER_URL:
        await interaction.response.send_message("Player URL nao configurado.", ephemeral=True)
        return
    await interaction.response.send_message(f"Site da radio: {PLAYER_URL}")


async def status_loop() -> None:
    await client.wait_until_ready()
    last_label = ""
    while not client.is_closed():
        try:
            payload = await asyncio.to_thread(fetch_json, f"{API_BASE}/api/nowplaying")
            song = song_from_now_playing(payload)
            label = format_presence_label(song)
            if label != last_label:
                await client.change_presence(
                    activity=discord.Activity(type=discord.ActivityType.listening, name=label)
                )
                last_label = label
        except Exception as error:
            log.warning("Status update falhou: %s", error)
            fallback = format_presence_label(None)
            if last_label != fallback:
                await client.change_presence(
                    activity=discord.Activity(type=discord.ActivityType.listening, name=fallback)
                )
                last_label = fallback
        await asyncio.sleep(STATUS_SECONDS)


async def graceful_shutdown(reason: str = "shutdown") -> None:
    global _shutting_down
    if _shutting_down:
        return
    _shutting_down = True
    clear_shutdown_request()
    log.info("Desligamento (%s): saindo dos canais de voz...", reason)
    try:
        await asyncio.wait_for(VOICE.stop_all(client), timeout=25.0)
    except asyncio.TimeoutError:
        log.warning("Timeout ao sair das calls; encerrando mesmo assim")
    except Exception as error:
        log.warning("Erro ao sair das calls: %s", error)
    await asyncio.sleep(0.4)
    if not client.is_closed():
        await client.close()


async def shutdown_watch_loop() -> None:
    await client.wait_until_ready()
    while not client.is_closed() and not _shutting_down:
        if SHUTDOWN_FILE.exists():
            await graceful_shutdown("stop-discord-bot.ps1")
            return
        await asyncio.sleep(0.25)


def _signal_request_shutdown(signum: int, _frame: object) -> None:
    try:
        SHUTDOWN_FILE.parent.mkdir(parents=True, exist_ok=True)
        SHUTDOWN_FILE.write_text(str(signum), encoding="utf-8")
    except OSError:
        pass


async def stream_watchdog_loop() -> None:
    await client.wait_until_ready()
    while not client.is_closed() and not _shutting_down:
        await asyncio.sleep(5.0)
        for guild in list(client.guilds):
            channel = bot_voice_channel_for_guild(guild)
            if not channel:
                _stream_stalled.pop(guild.id, None)
                continue
            voice = guild.voice_client
            if not voice or not voice.is_connected():
                _stream_stalled.pop(guild.id, None)
                continue
            if voice.is_playing():
                _stream_stalled.pop(guild.id, None)
                continue

            stalled = _stream_stalled.get(guild.id, 0) + 1
            _stream_stalled[guild.id] = stalled
            if stalled < 10:
                continue

            log.warning("Stream Discord parado em %s; religando...", channel.name)
            try:
                await VOICE.ensure_playing(guild, channel, restart_stream=True)
            except Exception as error:
                log.warning("Falha ao religar stream em %s: %s", channel.name, error)
            finally:
                _stream_stalled.pop(guild.id, None)


async def alone_watchdog_loop() -> None:
    await client.wait_until_ready()
    while not client.is_closed() and not _shutting_down:
        await asyncio.sleep(2.0)
        now = time.monotonic()
        for guild in list(client.guilds):
            channel = bot_voice_channel_for_guild(guild)
            if not channel:
                _alone_since.pop(guild.id, None)
                continue

            if count_humans_in_channel(channel) > 0:
                _alone_since.pop(guild.id, None)
                continue

            since = _alone_since.get(guild.id)
            if since is None:
                refresh_alone_timer(guild)
                continue

            elapsed = now - since
            if elapsed < ALONE_LEAVE_SECONDS:
                continue

            log.info("Saindo de %s — sozinho ha %.0fs", channel.name, elapsed)
            try:
                stopped = await VOICE.stop(guild, client=client)
                if stopped:
                    await asyncio.to_thread(send_heartbeat, API_BASE, "discord:bot", False)
            except Exception as error:
                log.warning("Falha ao sair sozinho da call: %s", error)
            finally:
                _alone_since.pop(guild.id, None)


async def sync_slash_commands() -> None:
    """Limpa comandos guild antigos (duplicatas) e publica comandos globais."""
    for guild_obj in GUILD_OBJECTS:
        tree.clear_commands(guild=guild_obj)
        try:
            await tree.sync(guild=guild_obj)
            log.info("Comandos guild antigos removidos no servidor %s", guild_obj.id)
        except discord.Forbidden:
            log.warning(
                "Sem acesso ao servidor %s — adicione o bot la se quiser usar la tambem.",
                guild_obj.id,
            )
        except discord.HTTPException as error:
            log.warning("Falha ao limpar guild %s: %s", guild_obj.id, error)

    synced = await tree.sync()
    names = ", ".join(cmd.name for cmd in synced)
    log.info("Comandos globais sincronizados (%s): %s", len(synced), names)


@tree.error
async def on_app_command_error(
    interaction: discord.Interaction,
    error: app_commands.AppCommandError,
) -> None:
    log.exception("Erro em comando slash: %s", getattr(interaction.command, "name", "?"))
    message = f"Comando falhou: {error}"
    try:
        if interaction.response.is_done():
            await interaction.followup.send(message, ephemeral=True)
        else:
            await interaction.response.send_message(message, ephemeral=True)
    except discord.HTTPException:
        pass


@client.event
async def on_voice_state_update(
    member: discord.Member,
    before: discord.VoiceState,
    after: discord.VoiceState,
) -> None:
    if member.guild is None:
        return

    guild = member.guild
    if not bot_voice_channel_for_guild(guild):
        _alone_since.pop(guild.id, None)
        return

    refresh_alone_timer(guild)


@client.event
async def on_ready() -> None:
    log.info("Logado como %s (%s)", client.user, client.user.id if client.user else "?")
    log.info("Stream Discord (%s): %s", STREAM_KIND, STREAM_URL)
    log.info("Auto-saida da call sozinho: %ss", ALONE_LEAVE_SECONDS)
    client.loop.create_task(sync_slash_commands())
    client.loop.create_task(status_loop())
    client.loop.create_task(stream_watchdog_loop())
    client.loop.create_task(alone_watchdog_loop())
    client.loop.create_task(shutdown_watch_loop())


def main() -> int:
    if not APPLICATION_ID:
        raise RuntimeError("application_id ausente em data/discord-bot-config.json")
    if not STREAM_URL:
        raise RuntimeError("stream_url ausente em discord-bot-config.json")
    ensure_single_instance()
    require_voice_dependencies()
    from discord.voice_client import VoiceClient

    if VoiceClient.warn_dave or VoiceClient.warn_nacl:
        raise RuntimeError(
            "discord.py nao detectou davey/PyNaCl neste processo. "
            f"Reinstale com: \"{__import__('sys').executable}\" -m pip install -r tools/discord-bot/requirements.txt"
        )
    log.info("Voz OK (davey + PyNaCl) — Python: %s", sys.executable)
    signal.signal(signal.SIGINT, _signal_request_shutdown)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, _signal_request_shutdown)
    client.run(TOKEN, log_handler=None)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
