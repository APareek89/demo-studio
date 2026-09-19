"""Versioned conversation state and delivery contracts, separate from media timing.

The local single-worker server persists meaningful turn boundaries. Audio frames
never enter checkpoints; a cancelled turn cannot publish over its successor.
"""
from __future__ import annotations

import hashlib
import json
import re
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Literal, TypedDict

from pydantic import BaseModel, Field

from . import store


class SpokenClaim(BaseModel):
    text: str = Field(max_length=900, description="One short natural spoken sentence. No markdown or speech tags.")
    fact_ids: list[str] = Field(default_factory=list, description="Every evidence or calculated-result ID supporting this sentence")
    kind: Literal["fact", "context", "limitation"] = "fact"


class Operand(BaseModel):
    name: str = Field(description="Input name required by the operation")
    value: float
    unit: str = Field(description="Explicit unit: INR, percent, months, years, km, km/month, km/litre, INR/litre, etc.")
    source_id: str = Field(description="An evidence ID or 'customer'. Never use a general-knowledge input.")
    quote: str = Field(description="Exact source/customer substring that supplies this value AND its meaning/unit")


class ToolRequest(BaseModel):
    tool: Literal["calculator", "source_lookup"]
    operation: Literal["emi", "fuel_cost", "difference", "sum", "product", "divide", "percentage"] = "difference"
    inputs: list[Operand] = Field(default_factory=list)
    url: str = Field(default="", description="A URL explicitly supplied by the customer; relevant links within that source may be read")
    query: str = Field(default="", max_length=400)


class TurnDecision(BaseModel):
    action: Literal["answer", "clarify", "tools"]
    sentences: list[SpokenClaim] = Field(default_factory=list, description="Answer first, 1–3 short sentences, total at most75 words")
    clarification: str = Field(default="", description="Only ONE necessary question, no product claims; empty for ordinary answers")
    tool_calls: list[ToolRequest] = Field(default_factory=list, max_length=4)
    answered: bool = True
    topic: str = "other"
    cta: str = Field(default="", description="Suggestion only; must be configured and explicitly requested by the customer")


class DeliveryPlan(BaseModel):
    version: int = 1
    session_id: str
    turn_id: str
    utterance_id: str
    plan_revision: int = 0
    snapshot_id: str = ""
    speech: str
    result: dict[str, Any]
    next_interaction: Literal["listen", "clarify"] = "listen"


@dataclass
class TurnControl:
    deadline: float
    cancelled: threading.Event = field(default_factory=threading.Event)

    def remaining(self) -> float:
        if self.cancelled.is_set():
            raise InterruptedError("Turn superseded")
        left = self.deadline - time.monotonic()
        if left <= 0:
            raise TimeoutError("Conversation deadline reached")
        return left


class RuntimeState(TypedDict, total=False):
    demo_id: str
    session_id: str
    turn_id: str
    kind: str
    question: str
    history: list[dict]
    profile: dict
    slide_id: str | None
    snapshot_id: str
    seen_segments: list[str]
    plan_revision: int
    control: TurnControl
    evidence: list[dict]
    coverage: dict
    conflicts: list[dict]
    requested_scope: dict
    tool_results: list[dict]
    tool_rounds: int
    tool_count: int
    decision: dict
    timings: dict
    errors: list[str]
    result: dict
    delivery: dict


def safe_id(value: str, prefix: str = "s") -> str:
    value = str(value or "")
    if re.fullmatch(r"[A-Za-z0-9_-]{1,100}", value):
        return value
    return prefix + "_" + hashlib.sha256(value.encode()).hexdigest()[:20]


_guard = threading.Lock()
_owners: dict[tuple[str, str], tuple[str, TurnControl]] = {}


def claim_turn(demo_id: str, session_id: str, turn_id: str, budget: float = 12.0) -> TurnControl:
    with _guard:
        key = (demo_id, session_id)
        previous = _owners.get(key)
        if previous:
            previous[1].cancelled.set()
        control = TurnControl(time.monotonic() + budget)
        _owners[key] = (turn_id, control)
        return control


def cancel_turn(demo_id: str, session_id: str) -> None:
    with _guard:
        previous = _owners.pop((demo_id, session_id), None)
        if previous:
            previous[1].cancelled.set()


def checkpoint(state: RuntimeState, phase: str) -> None:
    """Persist only if this turn still owns the session; never persist credentials/audio."""
    with _guard:
        owner = _owners.get((state["demo_id"], state["session_id"]))
        if not owner or owner[0] != state["turn_id"] or owner[1].cancelled.is_set():
            return
        value = {k: state.get(k) for k in ("session_id", "turn_id", "kind", "question", "history", "profile", "snapshot_id", "plan_revision", "slide_id", "seen_segments", "delivery", "timings", "errors")}
        value.update(phase=phase, updated_at=time.time(), version=1)
        rel = "runtime/" + safe_id(state["session_id"]) + ".json"
        store.write_json(state["demo_id"], rel, value)


def previous_state(demo_id: str, session_id: str) -> dict:
    return store.read_json(demo_id, "runtime/" + safe_id(session_id) + ".json") or {}
