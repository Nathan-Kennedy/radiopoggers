"""
Votacao em tempo real — presenca de ouvintes ouvindo + sessoes de voto + SSE.
"""

from __future__ import annotations

import json
import os
import random
import secrets
import threading
import time
from typing import Any, Callable

VOTE_ENABLED = os.environ.get("RADIOPOGGERS_VOTE_ENABLED", "1").strip().lower() not in {"0", "false", "no", "off"}
VOTE_DURATION_SEC = float(os.environ.get("RADIOPOGGERS_VOTE_DURATION_SEC", "20"))
VOTE_SOLO_DURATION_SEC = float(os.environ.get("RADIOPOGGERS_VOTE_SOLO_DURATION_SEC", "6"))
AUDIENCE_TTL_SEC = float(os.environ.get("RADIOPOGGERS_AUDIENCE_TTL_SEC", "35"))
LOTTERY_DISPLAY_SEC = float(os.environ.get("RADIOPOGGERS_VOTE_LOTTERY_SEC", "3.5"))
VOTE_ACTION_COOLDOWN_SEC = float(os.environ.get("RADIOPOGGERS_VOTE_ACTION_COOLDOWN_SEC", "45"))

VOTE_TYPES = frozenset({"skip_track", "library_request", "library_clear", "spotify_import"})
VOTE_ACTION_COOLDOWN_TYPES = frozenset({"skip_track", "library_request", "library_clear"})

_VOTE_LABELS: dict[str, dict[str, str]] = {
    "skip_track": {
        "title": "Pular a faixa atual?",
        "yes": "Pular",
        "no": "Deixa rolar",
    },
    "library_request": {
        "title": "Pedido na estante: tocar ja ou na fila?",
        "yes": "Tocar ja",
        "no": "Na fila",
    },
    "library_clear": {
        "title": "Zerar Minha playlist?",
        "yes": "Zerar",
        "no": "Manter",
    },
    "spotify_import": {
        "title": "Playlist pronta! O que fazemos?",
        "yes": "Tocar ja",
        "no": "So na fila",
    },
}

_LOCK = threading.Lock()
_PRESENCE: dict[str, dict[str, Any]] = {}
_ACTIVE_VOTE: dict[str, Any] | None = None
_VOTE_FINISH_TIMERS: dict[str, threading.Timer] = {}
_VOTE_FINISH_LOCK = threading.Lock()
_SSE_QUEUES: list[list[str]] = []
_EXECUTOR: Callable[[str, dict[str, Any], str, str], dict[str, Any]] | None = None
_MIKU_HOOK: Callable[[str, dict[str, Any], str], None] | None = None
_LAST_VOTE_ACTION_AT = 0.0


def register_vote_executor(
    executor: Callable[[str, dict[str, Any], str, str], dict[str, Any]],
) -> None:
    global _EXECUTOR
    _EXECUTOR = executor


def register_miku_hook(hook: Callable[[str, dict[str, Any], str], None]) -> None:
    global _MIKU_HOOK
    _MIKU_HOOK = hook


def vote_action_cooldown_remaining() -> float:
    with _LOCK:
        elapsed = _now() - _LAST_VOTE_ACTION_AT
        return max(VOTE_ACTION_COOLDOWN_SEC - elapsed, 0.0)


def require_vote_action_cooldown(vote_type: str) -> None:
    if vote_type not in VOTE_ACTION_COOLDOWN_TYPES:
        return

    remaining = vote_action_cooldown_remaining()
    if remaining > 0:
        wait_sec = int(remaining + 0.999)
        raise RuntimeError(
            f"Aguarde {wait_sec}s antes de pular, pedir musica ou zerar a playlist "
            "(intervalo protege a radio e a locucao da Miku)."
        )


def touch_vote_action_cooldown(vote_type: str) -> None:
    global _LAST_VOTE_ACTION_AT

    if vote_type not in VOTE_ACTION_COOLDOWN_TYPES:
        return

    with _LOCK:
        _LAST_VOTE_ACTION_AT = _now()


def vote_status() -> dict[str, Any]:
    remaining = vote_action_cooldown_remaining()
    return {
        "enabled": VOTE_ENABLED,
        "duration_sec": VOTE_DURATION_SEC,
        "solo_duration_sec": VOTE_SOLO_DURATION_SEC,
        "audience_ttl_sec": AUDIENCE_TTL_SEC,
        "action_cooldown_sec": VOTE_ACTION_COOLDOWN_SEC,
        "action_cooldown_remaining_sec": round(remaining, 1),
        "action_cooldown_types": sorted(VOTE_ACTION_COOLDOWN_TYPES),
    }


def _now() -> float:
    return time.time()


def _prune_presence(now: float | None = None) -> None:
    cutoff = (now or _now()) - AUDIENCE_TTL_SEC
    stale = [key for key, item in _PRESENCE.items() if float(item.get("last_seen") or 0) < cutoff]
    for key in stale:
        _PRESENCE.pop(key, None)


def record_heartbeat(listener_id: str, playing: bool) -> dict[str, Any]:
    safe_id = str(listener_id or "").strip()
    if not safe_id:
        raise ValueError("listener_id obrigatorio.")

    now = _now()
    with _LOCK:
        _prune_presence(now)
        _PRESENCE[safe_id] = {
            "listener_id": safe_id,
            "playing": bool(playing),
            "last_seen": now,
        }
        return audience_counts_locked()


def audience_counts() -> dict[str, int]:
    with _LOCK:
        _prune_presence()
        return audience_counts_locked()


def audience_counts_locked() -> dict[str, int]:
    total_on_site = len(_PRESENCE)
    eligible = sum(1 for item in _PRESENCE.values() if item.get("playing"))
    return {"eligible": eligible, "total_on_site": total_on_site}


def _vote_public(vote: dict[str, Any]) -> dict[str, Any]:
    now = _now()
    deadline = float(vote.get("deadline_at") or 0)
    remaining = max(int(deadline - now), 0) if vote.get("phase") == "open" else 0
    labels = _VOTE_LABELS.get(str(vote.get("type") or ""), {})
    title = labels.get("title", "Votacao aberta")
    payload = vote.get("payload") if isinstance(vote.get("payload"), dict) else {}

    if vote.get("type") == "library_request":
        track_title = str(payload.get("title") or "faixa")
        title = f"Pedir {track_title}: tocar ja ou na fila?"
    elif vote.get("type") == "library_clear":
        track_count = int(payload.get("track_count") or payload.get("count") or 0)
        suffix = f" ({track_count} faixa(s))" if track_count > 0 else ""
        title = f"Zerar Minha playlist{suffix}?"
    elif vote.get("type") == "spotify_import":
        track_title = str(payload.get("title") or "nova playlist")
        title = f"{track_title} pronta! Tocar ja ou so na fila?"

    return {
        "id": vote.get("id"),
        "type": vote.get("type"),
        "phase": vote.get("phase"),
        "title": title,
        "yes_label": labels.get("yes", "Sim"),
        "no_label": labels.get("no", "Nao"),
        "proposer_id": vote.get("proposer_id"),
        "payload": payload,
        "eligible_snapshot": int(vote.get("eligible_snapshot") or 0),
        "solo": bool(vote.get("solo")),
        "duration_sec": float(vote.get("duration_sec") or VOTE_DURATION_SEC),
        "yes_votes": int(vote.get("yes_votes") or 0),
        "no_votes": int(vote.get("no_votes") or 0),
        "abstain": int(vote.get("abstain") or 0),
        "remaining_sec": remaining,
        "deadline_at": deadline,
        "outcome": vote.get("outcome"),
        "lottery_winner": vote.get("lottery_winner"),
        "execution": vote.get("execution"),
        "message": vote.get("message"),
        "narrator_moment": vote.get("narrator_moment"),
    }


def get_active_vote_public() -> dict[str, Any] | None:
    with _LOCK:
        if not _ACTIVE_VOTE:
            return None
        return _vote_public(_ACTIVE_VOTE)


def _broadcast(event: dict[str, Any]) -> None:
    payload = json.dumps(event, ensure_ascii=False)
    with _LOCK:
        dead: list[list[str]] = []
        for queue in _SSE_QUEUES:
            queue.append(payload)
            if len(queue) > 64:
                queue.pop(0)
        for queue in dead:
            if queue in _SSE_QUEUES:
                _SSE_QUEUES.remove(queue)


def sse_subscribe() -> tuple[list[str], Callable[[], None]]:
    queue: list[str] = []
    with _LOCK:
        _SSE_QUEUES.append(queue)

    def unsubscribe() -> None:
        with _LOCK:
            if queue in _SSE_QUEUES:
                _SSE_QUEUES.remove(queue)

    active = get_active_vote_public()
    if active:
        queue.append(json.dumps({"event": "vote_update", "vote": active}, ensure_ascii=False))

    return queue, unsubscribe


def _eligible_listener_ids_locked() -> set[str]:
    return {
        str(item.get("listener_id") or "")
        for item in _PRESENCE.values()
        if item.get("playing") and str(item.get("listener_id") or "")
    }


def _tally(vote: dict[str, Any]) -> str:
    eligible = int(vote.get("eligible_snapshot") or 0)
    yes_votes = len(vote.get("votes_yes") or [])
    no_votes = len(vote.get("votes_no") or [])
    voted = yes_votes + no_votes
    abstain = max(eligible - voted, 0)
    against = no_votes + abstain

    vote["yes_votes"] = yes_votes
    vote["no_votes"] = no_votes
    vote["abstain"] = abstain

    if yes_votes > against:
        return "yes"
    if yes_votes < against:
        return "no"
    return "lottery"


_SKIP_COUNT_BY_PROPOSER: dict[str, int] = {}
_SKIP_COUNT_LOCK = threading.Lock()


def resolve_skip_narrator_moment(base_moment: str, proposer_id: str) -> str:
    if base_moment not in {"vote_skip_yes", "vote_skip_lottery_yes"}:
        return base_moment

    proposer = str(proposer_id or "").strip() or "_anonymous_"
    with _SKIP_COUNT_LOCK:
        count = _SKIP_COUNT_BY_PROPOSER.get(proposer, 0) + 1
        _SKIP_COUNT_BY_PROPOSER[proposer] = count

    lottery = base_moment == "vote_skip_lottery_yes"
    if count >= 3:
        return "vote_skip_lottery_yes_angry" if lottery else "vote_skip_yes_angry"
    if count >= 2:
        return "vote_skip_lottery_yes_repeat" if lottery else "vote_skip_yes_repeat"
    return base_moment


def resolve_narrator_moment(
    vote_type: str,
    outcome: str,
    lottery_winner: str | None,
    proposer_id: str = "",
) -> str | None:
    moment = _resolve_miku_moment(vote_type, outcome, lottery_winner)
    if moment in {"vote_skip_yes", "vote_skip_lottery_yes"}:
        moment = resolve_skip_narrator_moment(moment, proposer_id)
    return moment


def _resolve_miku_moment(vote_type: str, outcome: str, lottery_winner: str | None) -> str | None:
    if vote_type == "skip_track":
        if outcome == "lottery":
            return "vote_skip_lottery_yes" if lottery_winner == "yes" else "vote_skip_lottery_no"
        return "vote_skip_yes" if outcome == "yes" else "vote_skip_no"

    if vote_type == "library_request":
        if outcome == "lottery":
            winner = lottery_winner or "no"
            return "vote_library_now" if winner == "yes" else "vote_library_queue"
        return "vote_library_now" if outcome == "yes" else "vote_library_queue"

    if vote_type == "library_clear":
        if outcome == "lottery":
            winner = lottery_winner or "no"
            return "vote_skip_yes" if winner == "yes" else "vote_skip_no"
        return "vote_skip_yes" if outcome == "yes" else "vote_skip_no"

    if vote_type == "spotify_import":
        if outcome == "lottery":
            winner = lottery_winner or "no"
            return "vote_spotify_now" if winner == "yes" else "vote_spotify_queue"
        return "vote_spotify_now" if outcome == "yes" else "vote_spotify_queue"

    return None


def _execute_outcome(vote: dict[str, Any], final_choice: str) -> dict[str, Any]:
    if not _EXECUTOR:
        return {"ok": False, "error": "Executor de votacao nao registrado."}

    try:
        result = _EXECUTOR(str(vote.get("type") or ""), vote.get("payload") or {}, final_choice, str(vote.get("id") or ""))
        if not isinstance(result, dict):
            result = {"ok": True}
        return result
    except Exception as error:
        return {"ok": False, "error": str(error)}


def _miku_hook_payload(vote: dict[str, Any]) -> dict[str, Any]:
    payload = dict(vote.get("payload") or {}) if isinstance(vote.get("payload"), dict) else {}
    proposer = str(vote.get("proposer_id") or "").strip()
    if proposer:
        payload["proposer_id"] = proposer
    return payload


def _finish_vote(vote_id: str) -> None:
    global _ACTIVE_VOTE

    with _LOCK:
        vote = _ACTIVE_VOTE
        if not vote or vote.get("id") != vote_id:
            return
        if vote.get("phase") != "open":
            return
        vote["phase"] = "tallying"

    _cancel_vote_finish(vote_id)

    outcome = _tally(vote)
    lottery_winner: str | None = None
    final_choice = outcome

    if outcome == "lottery":
        lottery_winner = "yes" if random.random() < 0.5 else "no"
        final_choice = lottery_winner
        vote["phase"] = "lottery"
        vote["outcome"] = outcome
        vote["lottery_winner"] = lottery_winner
        _broadcast({"event": "vote_update", "vote": _vote_public(vote)})
        _broadcast({"event": "vote_lottery", "vote": _vote_public(vote), "winner": lottery_winner})
        time.sleep(LOTTERY_DISPLAY_SEC)

    vote["phase"] = "executing"
    vote["outcome"] = outcome
    execution = _execute_outcome(vote, final_choice)
    vote["execution"] = execution
    vote["message"] = str(execution.get("message") or execution.get("error") or "")

    moment = resolve_narrator_moment(
        str(vote.get("type") or ""),
        outcome,
        lottery_winner or final_choice,
        str(vote.get("proposer_id") or ""),
    )
    vote["narrator_moment"] = moment
    if moment and _MIKU_HOOK:
        try:
            _MIKU_HOOK(moment, _miku_hook_payload(vote), final_choice)
        except Exception as error:
            print(f"[Vote] Miku hook falhou: {error}")

    vote["phase"] = "closed"
    _broadcast({"event": "vote_closed", "vote": _vote_public(vote)})

    with _LOCK:
        if _ACTIVE_VOTE and _ACTIVE_VOTE.get("id") == vote_id:
            _ACTIVE_VOTE = None


def _cancel_vote_finish(vote_id: str) -> None:
    with _VOTE_FINISH_LOCK:
        timer = _VOTE_FINISH_TIMERS.pop(vote_id, None)
    if timer:
        timer.cancel()


def _schedule_finish(vote_id: str, delay_sec: float) -> None:
    _cancel_vote_finish(vote_id)
    timer = threading.Timer(max(delay_sec, 0), _finish_vote, args=[vote_id])
    timer.daemon = True
    timer.name = f"vote-finish-{vote_id[:8]}"
    with _VOTE_FINISH_LOCK:
        _VOTE_FINISH_TIMERS[vote_id] = timer
    timer.start()


def _maybe_finish_vote_early(vote_id: str) -> None:
    with _LOCK:
        vote = _ACTIVE_VOTE
        if not vote or vote.get("id") != vote_id or vote.get("phase") != "open":
            return
        if not vote.get("solo"):
            return
        eligible = int(vote.get("eligible_snapshot") or 0)
        voted = len(vote.get("votes_yes") or []) + len(vote.get("votes_no") or [])
        if voted < eligible:
            return

    _cancel_vote_finish(vote_id)
    threading.Thread(
        target=_finish_vote,
        args=[vote_id],
        daemon=True,
        name=f"vote-early-{vote_id[:8]}",
    ).start()


def start_vote(vote_type: str, proposer_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    global _ACTIVE_VOTE

    if not VOTE_ENABLED:
        raise RuntimeError("Sistema de votacao desligado.")

    safe_type = str(vote_type or "").strip()
    if safe_type not in VOTE_TYPES:
        raise ValueError(f"Tipo de votacao invalido: {safe_type}")

    require_vote_action_cooldown(safe_type)

    safe_proposer = str(proposer_id or "").strip()
    if not safe_proposer:
        raise ValueError("proposer_id obrigatorio.")

    touch_vote_action_cooldown(safe_type)

    now = _now()
    with _LOCK:
        _prune_presence(now)
        if _ACTIVE_VOTE and _ACTIVE_VOTE.get("phase") in {"open", "lottery", "executing", "tallying"}:
            raise RuntimeError("Ja existe uma votacao em andamento.")

        counts = audience_counts_locked()
        total_on_site = int(counts.get("total_on_site") or 0)
        eligible_ids = _eligible_listener_ids_locked()
        if safe_proposer:
            eligible_ids = set(eligible_ids)
            eligible_ids.add(safe_proposer)
        eligible = len(eligible_ids)
        if eligible <= 0:
            raise RuntimeError("Nenhum ouvinte elegivel ouvindo agora.")

        # Solo rapido so quando esta realmente sozinho na pagina.
        solo = total_on_site <= 1 and eligible <= 1
        duration_sec = VOTE_SOLO_DURATION_SEC if solo else VOTE_DURATION_SEC

        vote_id = secrets.token_hex(8)
        deadline = now + duration_sec
        vote = {
            "id": vote_id,
            "type": safe_type,
            "phase": "open",
            "proposer_id": safe_proposer,
            "payload": dict(payload or {}),
            "eligible_snapshot": eligible,
            "total_on_site_snapshot": total_on_site,
            "solo": solo,
            "duration_sec": duration_sec,
            "eligible_ids": sorted(eligible_ids),
            "votes_yes": [],
            "votes_no": [],
            "yes_votes": 0,
            "no_votes": 0,
            "abstain": 0,
            "started_at": now,
            "deadline_at": deadline,
            "outcome": None,
            "lottery_winner": None,
            "execution": None,
            "message": "",
        }
        _ACTIVE_VOTE = vote
        public = _vote_public(vote)

    _broadcast({"event": "vote_started", "vote": public})
    _schedule_finish(vote_id, duration_sec)
    return public


def execute_direct(
    vote_type: str,
    proposer_id: str,
    choice: str,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if not VOTE_ENABLED:
        raise RuntimeError("Sistema de votacao desligado.")

    safe_type = str(vote_type or "").strip()
    if safe_type not in VOTE_TYPES:
        raise ValueError(f"Tipo de votacao invalido: {safe_type}")

    safe_choice = str(choice or "").strip().lower()
    if safe_choice not in {"yes", "no"}:
        raise ValueError("choice deve ser yes ou no.")

    require_vote_action_cooldown(safe_type)
    touch_vote_action_cooldown(safe_type)

    now = _now()
    with _LOCK:
        _prune_presence(now)
        total_on_site = len(_PRESENCE)
        eligible_ids = set(_eligible_listener_ids_locked())
        proposer = str(proposer_id or "").strip()
        if proposer:
            eligible_ids.add(proposer)

    if total_on_site > 1 or len(eligible_ids) > 1:
        raise RuntimeError("Mais de um ouvinte no site — use votacao coletiva.")

    vote_id = secrets.token_hex(8)
    vote = {
        "id": vote_id,
        "type": safe_type,
        "phase": "executing",
        "proposer_id": str(proposer_id or "").strip(),
        "payload": dict(payload or {}),
        "eligible_snapshot": len(eligible_ids),
        "outcome": "direct",
        "lottery_winner": None,
    }

    execution = _execute_outcome(vote, safe_choice)
    if not execution.get("ok", True):
        error_msg = str(
            execution.get("error")
            or execution.get("message")
            or "Falha ao executar comando."
        )
        raise RuntimeError(error_msg)

    moment = resolve_narrator_moment(
        safe_type,
        "yes" if safe_choice == "yes" else "no",
        None,
        str(proposer_id or "").strip(),
    )
    if moment and _MIKU_HOOK:
        try:
            _MIKU_HOOK(moment, _miku_hook_payload(vote), safe_choice)
        except Exception as error:
            print(f"[Vote] Miku hook falhou: {error}")

    return {
        "ok": True,
        "direct": True,
        "choice": safe_choice,
        "execution": execution,
        "message": str(execution.get("message") or "Comando executado."),
        "narrator_moment": moment,
    }


def cast_vote(vote_id: str, listener_id: str, choice: str) -> dict[str, Any]:
    safe_id = str(vote_id or "").strip()
    safe_listener = str(listener_id or "").strip()
    safe_choice = str(choice or "").strip().lower()

    if not safe_id or not safe_listener:
        raise ValueError("vote_id e listener_id obrigatorios.")
    if safe_choice not in {"yes", "no"}:
        raise ValueError("choice deve ser yes ou no.")

    now = _now()
    with _LOCK:
        _prune_presence(now)
        vote = _ACTIVE_VOTE
        if not vote or vote.get("id") != safe_id:
            raise RuntimeError("Votacao nao encontrada ou encerrada.")
        if vote.get("phase") != "open":
            raise RuntimeError("Votacao nao esta aberta.")

        proposer_id = str(vote.get("proposer_id") or "").strip()
        if safe_listener != proposer_id and safe_listener not in _eligible_listener_ids_locked():
            raise RuntimeError("Voce precisa estar ouvindo a radio para votar.")

        yes_list = list(vote.get("votes_yes") or [])
        no_list = list(vote.get("votes_no") or [])
        if safe_listener in yes_list:
            yes_list.remove(safe_listener)
        if safe_listener in no_list:
            no_list.remove(safe_listener)

        if safe_choice == "yes":
            yes_list.append(safe_listener)
        else:
            no_list.append(safe_listener)

        vote["votes_yes"] = yes_list
        vote["votes_no"] = no_list
        _tally(vote)
        public = _vote_public(vote)

    _broadcast({"event": "vote_update", "vote": public})
    _maybe_finish_vote_early(safe_id)
    return public
