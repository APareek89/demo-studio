"""Latency cohorts with missing/cancelled turns visible, never filled with zeroes."""
from __future__ import annotations

import math
from collections import defaultdict

from . import storage, store


def percentile(values: list[float], fraction: float):
    if not values: return None
    ordered=sorted(values)
    return round(ordered[max(0,min(len(ordered)-1,math.ceil(len(ordered)*fraction)-1))])


def _duration(row,a,b):
    x,y=row.get(a),row.get(b)
    if not isinstance(x,(float,int)) or isinstance(x,bool) or not isinstance(y,(float,int)) or isinstance(y,bool):return None
    if not math.isfinite(x) or not math.isfinite(y) or y<x:return None
    return y-x


def response_kind(row):
    if row.get("response_kind") == "clarification" or row.get("clarifying_question"):
        return "clarification"
    if row.get("response_kind") == "answer" and row.get("answered") is True:
        return "answer"
    if row.get("response_kind") == "decline" and row.get("answered") is False:
        return "decline"
    # Older players persisted answered but not whether they asked a clarification.
    # That boolean alone cannot retrospectively identify substantive speech.
    return "legacy_all_responses"


def aggregate(demo_id: str | None = None) -> dict:
    groups=defaultdict(list);interruptions=[];sessions=0
    ids=[demo_id] if demo_id else [d["id"] for d in store.list_demos()]
    for did in ids:
        for session in storage.backend().iter_sessions(did):
            sessions+=1
            for event in session.get("interruptions",[]):
                duration=_duration(event,"detected_at","stopped_at")
                if duration is not None:interruptions.append(duration)
            for turn in session.get("turns",[]):
                route=turn.get("answer_route") or ("tool" if turn.get("tool_count") else "cache" if turn.get("from_bank") else "model")
                source = str(turn.get("input_source",turn.get("via","unknown")))
                basis = str(turn.get("speech_end_basis") or ("typed_submission" if source=="typed" else "unspecified"))
                key=(did,str(session.get("bundle_version",session.get("version","unknown"))),str(session.get("voice_provider",session.get("provider","unknown"))),source,route,basis,response_kind(turn))
                groups[key].append(turn)
    cohorts=[]
    for key,turns in groups.items():
        measured=[row for row in turns if _duration(row,"voice_ended","answer_audio") is not None]
        eligible=[row for row in measured if not row.get("cancelled") and not row.get("failed") and key[6] != "decline"]
        values=[_duration(row,"voice_ended","answer_audio") for row in eligible]
        endpoint=[v for row in eligible if (v:=_duration(row,"voice_ended","endpoint_received_at")) is not None]
        # Clarification delivery_done currently includes waiting for the customer's
        # clarification reply, so it cannot represent audio completion latency.
        completion=[v for row in eligible if key[6] != "clarification" and (v:=_duration(row,"voice_ended","delivery_done")) is not None]
        cohorts.append({"demo_id":key[0],"version":key[1],"voice_provider":key[2],"input":key[3],"route":key[4],"speech_end_basis":key[5],"response_kind":key[6],"turns":len(turns),"complete_timings":len(values),"useful_answer_timings":len(values) if key[6]=="answer" else 0,"measured_responses":len(measured),"declined":sum(response_kind(t)=="decline" for t in turns),"unclassified":sum(response_kind(t)=="legacy_all_responses" for t in turns),"missing_timings":len(turns)-len(measured),"cancelled":sum(bool(t.get("cancelled")) for t in turns),"failed":sum(bool(t.get("failed")) for t in turns),"p50_ms":percentile(values,.5),"p95_ms":percentile(values,.95),"completion_p50_ms":percentile(completion,.5),"endpoint_delay_p50_ms":percentile(endpoint,.5),"small_sample":len(values)<20})
    return {"sessions":sessions,"cohorts":cohorts,"interruption":{"n":len(interruptions),"p50_ms":percentile(interruptions,.5),"p95_ms":percentile(interruptions,.95),"basis":"detected speech onset to local stop request; acoustic detection delay is separate"},"clock":"typed submission or labelled speech-end estimate/endpoint receipt to response playback callback; filler excluded","note":"Answer playback timing requires an explicit answer classification and answered=true; answer quality is evaluated separately. Clarifications have a separate response cohort; declines retain counts without answer percentiles. Unclassified legacy rows are labelled all responses, not inferred as answers or declines. Cancelled/failed turns are excluded from latency. Speech timing bases remain separate; none proves acoustic onset. Small samples do not establish a reliable p95."}
