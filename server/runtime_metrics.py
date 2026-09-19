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
                key=(did,str(session.get("bundle_version",session.get("version","unknown"))),str(session.get("voice_provider","unknown")),source,route,basis)
                groups[key].append(turn)
    cohorts=[]
    for key,turns in groups.items():
        measured=[row for row in turns if _duration(row,"voice_ended","answer_audio") is not None]
        eligible=[row for row in measured if not row.get("cancelled") and not row.get("failed")]
        values=[_duration(row,"voice_ended","answer_audio") for row in eligible]
        endpoint=[v for row in eligible if (v:=_duration(row,"voice_ended","endpoint_received_at")) is not None]
        completion=[v for row in eligible if (v:=_duration(row,"voice_ended","delivery_done")) is not None]
        cohorts.append({"demo_id":key[0],"version":key[1],"voice_provider":key[2],"input":key[3],"route":key[4],"speech_end_basis":key[5],"turns":len(turns),"complete_timings":len(values),"missing_timings":len(turns)-len(measured),"cancelled":sum(bool(t.get("cancelled")) for t in turns),"failed":sum(bool(t.get("failed")) for t in turns),"p50_ms":percentile(values,.5),"p95_ms":percentile(values,.95),"completion_p50_ms":percentile(completion,.5),"endpoint_delay_p50_ms":percentile(endpoint,.5),"small_sample":len(values)<20})
    return {"sessions":sessions,"cohorts":cohorts,"interruption":{"n":len(interruptions),"p50_ms":percentile(interruptions,.5),"p95_ms":percentile(interruptions,.95),"basis":"detected speech onset to local stop request; acoustic detection delay is separate"},"clock":"typed submission or labelled speech-end estimate/endpoint receipt to first useful playback callback; filler excluded","note":"Cancelled/failed turns are counted and excluded from success latency. Speech timing bases remain separate; none proves acoustic onset. Small samples do not establish a reliable p95. Provider/model request timings are available in traces."}
