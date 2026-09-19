"""Per-demo event log for server-sent events.

Stage runs happen in worker threads (the LLM SDKs are synchronous); the SSE endpoint
polls this in-memory log, which avoids cross-thread asyncio plumbing. Local-only.
"""
from __future__ import annotations

import threading
import time

from . import store

_events: dict[str, list[dict]] = {}
_seq: dict[str, int] = {}
_guard = threading.Lock()
MAX_EVENTS = 800


def _restore(demo_id: str) -> None:
    """Called under the event lock; durable cursors survive an app restart."""
    if demo_id in _events:
        return
    try:
        rows = store.read_json(demo_id, "events.json", []) or []
        rows = [row for row in rows if isinstance(row, dict) and isinstance(row.get("seq"), int)][-MAX_EVENTS:]
    except (KeyError, ValueError, OSError):
        rows = []
    _events[demo_id] = rows
    _seq[demo_id] = max((row["seq"] for row in rows), default=0)


def publish(demo_id: str, type_: str, **data) -> dict:
    with _guard:
        _restore(demo_id)
        seq = _seq.get(demo_id, 0) + 1
        _seq[demo_id] = seq
        ev = {"seq": seq, "t": time.time(), "type": type_, **data}
        lst = _events.setdefault(demo_id, [])
        lst.append(ev)
        if len(lst) > MAX_EVENTS:
            del lst[: len(lst) - MAX_EVENTS]
        # A bounded snapshot is enough for reconnect, progress and warnings.
        # Synthetic IDs in isolated tests stay in-memory; real demos persist.
        if store.exists(demo_id):
            store.write_json(demo_id, "events.json", lst)
        return ev


def since(demo_id: str, seq: int) -> list[dict]:
    with _guard:
        _restore(demo_id)
        return [e for e in _events.get(demo_id, []) if e["seq"] > seq]


def latest_seq(demo_id: str) -> int:
    with _guard:
        _restore(demo_id)
        return _seq.get(demo_id, 0)


def snapshot(demo_id: str, cursor: int | None = None) -> dict:
    """Atomic stream baseline plus current UI state; fresh mounts skip history.

    A reconnect can replay only events after its cursor; a missing/expired/future
    cursor starts at the latest snapshot rather than replaying old phase_done.
    """
    with _guard:
        _restore(demo_id)
        latest = _seq.get(demo_id, 0)
        rows = _events.get(demo_id, [])
        oldest = rows[0]["seq"] if rows else latest + 1
        valid = cursor is not None and oldest - 1 <= cursor <= latest
        seq = cursor if valid else latest
        demo = store.load(demo_id)
        return {"seq": seq, "latest_seq": latest, "reset": not valid, "snapshot": {
            "status": demo.get("status"), "running": demo.get("running"),
            "approvals": demo.get("approvals", {}), "stages": demo.get("stages", {})}}
