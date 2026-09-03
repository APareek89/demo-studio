"""Per-demo event log for server-sent events.

Stage runs happen in worker threads (the LLM SDKs are synchronous); the SSE endpoint
polls this in-memory log, which avoids cross-thread asyncio plumbing. Local-only.
"""
from __future__ import annotations

import threading
import time

_events: dict[str, list[dict]] = {}
_seq: dict[str, int] = {}
_guard = threading.Lock()
MAX_EVENTS = 800


def publish(demo_id: str, type_: str, **data) -> dict:
    with _guard:
        seq = _seq.get(demo_id, 0) + 1
        _seq[demo_id] = seq
        ev = {"seq": seq, "t": time.time(), "type": type_, **data}
        lst = _events.setdefault(demo_id, [])
        lst.append(ev)
        if len(lst) > MAX_EVENTS:
            del lst[: len(lst) - MAX_EVENTS]
        return ev


def since(demo_id: str, seq: int) -> list[dict]:
    with _guard:
        return [e for e in _events.get(demo_id, []) if e["seq"] > seq]


def latest_seq(demo_id: str) -> int:
    with _guard:
        return _seq.get(demo_id, 0)
