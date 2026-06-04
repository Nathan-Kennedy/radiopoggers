from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
TOKEN_FILE = DATA_DIR / "discord-bot-token.txt"
CONFIG_FILE = DATA_DIR / "discord-bot-config.json"
CONFIG_EXAMPLE = DATA_DIR / "discord-bot-config.example.json"


def _read_secret_file(path: Path) -> str:
    if not path.exists():
        return ""
    for line in path.read_text(encoding="utf-8").splitlines():
        cleaned = line.strip()
        if cleaned and not cleaned.startswith("#"):
            return cleaned
    return ""


def load_config() -> dict[str, Any]:
    source = CONFIG_FILE if CONFIG_FILE.exists() else CONFIG_EXAMPLE
    if not source.exists():
        raise RuntimeError(
            "Config ausente. Copie data/discord-bot-config.example.json "
            "para data/discord-bot-config.json e ajuste as URLs."
        )
    config = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(config, dict):
        raise RuntimeError("discord-bot-config.json invalido.")

    config["application_id"] = (
        os.environ.get("DISCORD_APPLICATION_ID")
        or str(config.get("application_id") or "").strip()
    )
    config["api_base_url"] = (
        os.environ.get("RADIOPOGGERS_API_URL")
        or str(config.get("api_base_url") or "http://127.0.0.1:8765").strip()
    ).rstrip("/")
    config["azuracast_public_url"] = (
        os.environ.get("RADIOPOGGERS_AZURACAST_PUBLIC_URL")
        or str(config.get("azuracast_public_url") or "http://127.0.0.1").strip()
    ).rstrip("/")
    config["player_url"] = str(config.get("player_url") or "").strip()
    config["stream_url"] = str(config.get("stream_url") or "").strip()
    local_stream = str(config.get("stream_url_local") or "").strip()
    if not local_stream:
        local_stream = "http://127.0.0.1/listen/radio-no-grale/radio.mp3"
    config["stream_url_local"] = local_stream
    config["stream_hls_url"] = str(config.get("stream_hls_url") or "").strip()
    local_hls = str(config.get("stream_hls_url_local") or "").strip()
    if not local_hls:
        local_hls = "http://127.0.0.1/hls/radio-no-grale/live.m3u8"
    config["stream_hls_url_local"] = local_hls
    config["discord_stream_mode"] = str(
        config.get("discord_stream_mode") or "hls"
    ).strip().lower()
    config["station_name"] = str(config.get("station_name") or "RADIO NO GRALE").strip()
    config["status_update_seconds"] = max(int(config.get("status_update_seconds") or 30), 15)
    guild_ids = config.get("guild_ids") if isinstance(config.get("guild_ids"), list) else []
    config["guild_ids"] = [int(value) for value in guild_ids if str(value).strip().isdigit()]
    config["admin_role_id"] = int(os.environ.get("DISCORD_ADMIN_ROLE_ID") or config.get("admin_role_id") or 0)
    config["alone_leave_seconds"] = max(int(config.get("alone_leave_seconds") or 30), 10)
    return config


def resolve_discord_stream(config: dict[str, Any]) -> tuple[str, str]:
    """Escolhe URL e formato (hls/mp3) — alinhado ao player web quando possivel."""
    mode = str(config.get("discord_stream_mode") or "hls").strip().lower()
    mp3 = config.get("stream_url_local") or config.get("stream_url") or ""
    hls_local = str(config.get("stream_hls_url_local") or "").strip()
    hls_remote = str(config.get("stream_hls_url") or "").strip()
    if not hls_remote and config.get("azuracast_public_url"):
        base = str(config["azuracast_public_url"]).rstrip("/")
        hls_remote = f"{base}/hls/radio-no-grale/live.m3u8"

    if mode in ("hls", "auto"):
        for url in (hls_local, hls_remote):
            if url:
                return url, "hls"
        mode = "mp3"

    return str(mp3).strip(), "mp3"


def load_token() -> str:
    token = os.environ.get("DISCORD_BOT_TOKEN", "").strip() or _read_secret_file(TOKEN_FILE)
    if not token:
        raise RuntimeError(
            "Token do bot ausente. Crie data/discord-bot-token.txt "
            "(veja discord-bot-token.example.txt) ou defina DISCORD_BOT_TOKEN."
        )
    return token
