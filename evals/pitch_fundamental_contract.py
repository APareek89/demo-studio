"""Initial-only fundamental reservation through real Pitch; isolated, offline, free."""
from __future__ import annotations

import copy
import os
import sys
import tempfile
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch


def run(check):
    from server import store, schemas
    from server.agents import pitch, voice

    demo_id = store.new_demo("Fundamental route fixture")["id"]
    ids = ["roof", "screens", "audio", "engine", "space", "features", "ownership"]
    segments = [{"id": sid, "role": "features" if sid == "features" else "establish" if sid == "ownership" else "proof",
                 "title": sid.title(), "topic": sid, "fundamental": sid in {"engine", "space"},
                 "lines": [{"id": sid + "-L1", "text": "Review this part of the product.", "fact_ids": ["F1"]}],
                 "checkin": {"text": ""}, "deeper": []} for sid in ids]
    bundle = {"segments": segments, "version": 1, "knowledge_snapshot_id": "fundamental-fixture",
              "facts": [{"id": "F1", "kind": "feature", "claim": "Product section", "value": "Reviewed section", "approved": True}],
              "slides": [{"id": "sl-" + sid, "segment_id": sid} for sid in ids], "media": {"images": []}}
    store.write_json(demo_id, "bundle.json", bundle)
    with ExitStack() as stack:
        sockets = [stack.enter_context(patch(name, side_effect=AssertionError("No outbound calls")))
                   for name in ("socket.create_connection", "socket.socket.connect", "socket.socket.connect_ex")]
        stack.enter_context(patch.object(voice, "render_line", side_effect=AssertionError("No TTS")))

        def call(selected, *, refine=False, seen=()):
            output = schemas.PitchPlan(customer_state="unknown", decision_frame="", follow_up_question="",
                                       primary_outcome="", focus_topics=[], advance="",
                                       route=[{"segment_id": sid} for sid in selected])
            with patch.object(pitch.runtime, "structured", return_value=output) as model:
                result = pitch.plan_pitch(demo_id, {}, refine, voice_it=False, seen_segment_ids=list(seen))
                return [step["segment_id"] for step in result["route"]], model.call_args.args[0]

        route, prompt = call(["screens", "audio", "roof"])
        check("initial route inserts one omitted fundamental before the three-proof cap", route == ["engine", "screens", "audio", "features", "ownership"])
        route, _ = call(["screens", "audio", "roof", "engine"])
        check("fundamental beyond the cap is hoisted before slicing", route[:3] == ["engine", "screens", "audio"])
        route, _ = call(["engine", "screens", "space"])
        check("already-first fundamental is not duplicated or otherwise reordered", route == ["engine", "screens", "space", "features", "ownership"])
        route, _ = call(["screens", "audio", "roof"], seen=["engine"])
        check("seen filter wins and next unseen fundamental can lead", route[:3] == ["space", "screens", "audio"] and "engine" not in route)
        route, _ = call(["screens", "audio", "engine"], seen=["engine", "space"])
        check("all fundamentals seen means no fundamental is forced", route[:2] == ["screens", "audio"] and not {"engine", "space"}.intersection(route))
        route, _ = call(["screens", "audio", "roof"], refine=True)
        check("refinement preserves buyer order without forcing either fundamental", route[:3] == ["screens", "audio", "roof"])
        route, _ = call(["screens", "engine"], refine=True, seen=ids)
        check("explicit refinement keeps selected seen proof eligible", route == ["screens", "engine"])
        route, _ = call([])
        check("empty-model fallback hoists one fundamental before slicing", route == ["engine", "roof", "screens", "features", "ownership"])
        route, _ = call([], refine=True)
        check("refinement fallback retains original reviewed order", route[:3] == ["roof", "screens", "audio"])
        legacy = copy.deepcopy(bundle)
        for segment in legacy["segments"]:
            segment.pop("fundamental")
        store.write_json(demo_id, "bundle.json", legacy)
        route, _ = call(["screens", "audio", "roof"])
        check("legacy bundle without flags retains selected order", route[:3] == ["screens", "audio", "roof"])
        check("Pitch library exposes the fundamental flag", "engine [proof] Engine — fundamental: True" in prompt and "roof [proof] Roof — fundamental: False" in prompt)
        check("no outbound sockets", not any(mock.called for mock in sockets))


if __name__ == "__main__":
    with tempfile.TemporaryDirectory(prefix="pitch-fundamental-") as tmp:
        os.environ.update(MOCK_LLM="1", CLOUD_SYNC="0", DEMO_STUDIO_DATA=tmp, DEMO_STUDIO_GRAPH_DB=str(Path(tmp) / "graph.sqlite"))
        sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
        results = []
        def check(name, ok):
            results.append(bool(ok))
            print(("PASS " if ok else "FAIL ") + name)
        run(check)
        print(f"Pitch fundamental contracts: {sum(results)}/{len(results)}")
        raise SystemExit(0 if all(results) else 1)
