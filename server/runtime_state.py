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


class InteractionAct(BaseModel):
    """A closed assistant action, never a source of product facts or free speech."""
    model_config = {"extra": "forbid"}
    mode: Literal["verification_limit", "input_request", "fit_check"]
    subject_ids: list[Literal["rear_armrest", "personal_comfort", "guaranteed_resale", "comparison_evidence", "source_instructions"]] = Field(default_factory=list, max_length=3)
    input_ids: list[Literal["source_url", "city", "variant", "loan_amount", "interest_rate", "loan_tenure", "fuel_efficiency", "fuel_price", "travel_distance"]] = Field(default_factory=list, max_length=3)


class SpokenClaim(BaseModel):
    text: str = Field(default="", max_length=900, description="One short natural spoken sentence. Empty when interaction supplies a closed assistant act. No markdown or speech tags.")
    fact_ids: list[str] = Field(default_factory=list, description="Every evidence or calculated-result ID supporting this sentence")
    kind: Literal["fact", "context", "limitation"] = "fact"
    interaction: InteractionAct | None = Field(default=None, description="Use only allowed_interactions IDs, never on a fact row or with citations. Backend supplies the wording.")


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
    sentences: list[SpokenClaim] = Field(default_factory=list, description="Answer first, normally 1–3 short sentences and at most75 words; explicit lists/comparisons may use4 sentences and100 words to preserve all requested parts and conditions")
    clarification: str = Field(default="", description="Only ONE necessary question, no product claims; empty for ordinary answers")
    clarification_act: InteractionAct | None = Field(default=None, description="For action=clarify, prefer an input_request using allowed_interactions. Backend asks only still-missing inputs. Leave clarification empty.")
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
    kind: str = "qa"

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
    demo_version: int | None
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
_planning: dict[tuple[str, str], tuple[str, TurnControl]] = {}
_latest: dict[tuple[str, str], tuple[str, TurnControl]] = {}


def claim_turn(demo_id: str, session_id: str, turn_id: str, budget: float = 12.0, *, kind: str = "qa") -> TurnControl:
    with _guard:
        key = (demo_id, session_id)
        owners = _planning if kind == "explore" else _owners
        previous = owners.get(key)
        if previous:
            previous[1].cancelled.set()
        if kind == "explore":
            # New customer context supersedes both the old route and any answer.
            previous_qa = _owners.pop(key, None)
            if previous_qa:
                previous_qa[1].cancelled.set()
        control = TurnControl(time.monotonic() + budget, kind=kind)
        owners[key] = (turn_id, control)
        _latest[key] = (turn_id, control)
        return control


def cancel_turn(demo_id: str, session_id: str, *, preserve_planning: bool = False) -> None:
    with _guard:
        key = (demo_id, session_id)
        previous = _owners.pop(key, None)
        if previous:
            previous[1].cancelled.set()
        # An ordinary question changes audible ownership, not route context.
        # A new Explore/refine replaces the route; explicit Stop/end cancel both.
        if not preserve_planning:
            previous_plan = _planning.pop(key, None)
            if previous_plan:
                previous_plan[1].cancelled.set()


def checkpoint(state: RuntimeState, phase: str) -> None:
    """Persist only if this turn still owns the session; never persist credentials/audio."""
    with _guard:
        key = (state["demo_id"], state["session_id"])
        owner = (_planning if state.get("kind") == "explore" else _owners).get(key)
        latest = _latest.get(key)
        if (not owner or owner[0] != state["turn_id"] or owner[1].cancelled.is_set()
                or not latest or latest[1] is not owner[1]):
            return
        value = {k: state.get(k) for k in ("session_id", "turn_id", "kind", "question", "history", "profile", "snapshot_id", "demo_version", "plan_revision", "slide_id", "seen_segments", "delivery", "timings", "errors")}
        value.update(phase=phase, updated_at=time.time(), version=1)
        rel = "runtime/" + safe_id(state["session_id"]) + ".json"
        store.write_json(state["demo_id"], rel, value)


def previous_state(demo_id: str, session_id: str) -> dict:
    return store.read_json(demo_id, "runtime/" + safe_id(session_id) + ".json") or {}
