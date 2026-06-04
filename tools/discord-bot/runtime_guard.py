"""Garante dependencias de voz e uma unica instancia do bot."""

from __future__ import annotations

import atexit
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PID_FILE = PROJECT_ROOT / "data" / "discord-bot.pid"
SHUTDOWN_FILE = PROJECT_ROOT / "data" / "discord-bot.shutdown"


def clear_shutdown_request() -> None:
    try:
        SHUTDOWN_FILE.unlink(missing_ok=True)
    except OSError:
        pass


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if os.name == "nt":
        import ctypes

        kernel32 = ctypes.windll.kernel32
        handle = kernel32.OpenProcess(0x1000, False, pid)
        if not handle:
            return False
        kernel32.CloseHandle(handle)
        return True
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def require_voice_dependencies() -> None:
    missing: list[str] = []
    try:
        import davey  # noqa: F401
    except ImportError:
        missing.append("davey")

    try:
        import nacl  # noqa: F401
    except ImportError:
        missing.append("PyNaCl")

    if missing:
        packages = " ".join(missing)
        exe = sys.executable
        raise SystemExit(
            f"Dependencias de voz ausentes ({packages}).\n"
            f"Rode com ESTE Python:\n"
            f'  "{exe}" -m pip install -r tools/discord-bot/requirements.txt'
        )


def ensure_single_instance() -> None:
    PID_FILE.parent.mkdir(parents=True, exist_ok=True)
    clear_shutdown_request()
    current = os.getpid()

    if PID_FILE.exists():
        raw = PID_FILE.read_text(encoding="utf-8").strip()
        if raw.isdigit():
            old_pid = int(raw)
            if old_pid != current and _pid_alive(old_pid):
                raise SystemExit(
                    f"Bot Discord ja esta rodando (PID {old_pid}).\n"
                    "Pare com: .\\scripts\\stop-discord-bot.ps1\n"
                    "Ou reinicie com: .\\scripts\\restart-discord-bot.ps1"
                )

    PID_FILE.write_text(str(current), encoding="utf-8")

    def _cleanup() -> None:
        try:
            if PID_FILE.exists() and PID_FILE.read_text(encoding="utf-8").strip() == str(current):
                PID_FILE.unlink(missing_ok=True)
        except OSError:
            pass

    atexit.register(_cleanup)
