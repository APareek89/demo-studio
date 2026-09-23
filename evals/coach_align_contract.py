"""Free API checks for reviewed story order; isolated storage and blocked sockets."""
from __future__ import annotations

import copy
import os
import sys
import tempfile
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch


def run(check):
    from fastapi.testclient import TestClient
    from server import config, graph, store
    from server.agents import align
    from server.app import app

    with tempfile.TemporaryDirectory(prefix="coach-align-") as tmp, ExitStack() as stack:
        stack.enter_context(patch.multiple(config, MOCK_LLM=True, DATA_DIR=Path(tmp)))
        blocked = [stack.enter_context(patch(name, side_effect=AssertionError("Outbound call blocked")))
                   for name in ("socket.create_connection", "socket.socket.connect", "socket.socket.connect_ex")]
        revise = stack.enter_context(patch.object(graph, "start_revise"))
        stack.enter_context(patch.object(graph, "is_running", return_value=False))
        did = store.new_demo("Story review fixture")["id"]
        store.update(did, lambda demo: demo["approvals"].update({key: True for key in store.CARDS}))
        und = {"product": {"name": "Fixture", "category": "compact suv"}, "images": [], "shots": [], "unknowns": [],
               "facts": [{"id": f"F{n}", "claim": claim, "value": "Available", "approved": True}
                         for n, claim in enumerate(["Engine choice", "Rear seating", "Airbags", "Sunroof"], 1)]}
        store.write_json(did, "understanding.json", und)
        stops = [{"id": sid, "label": label, "kind": kind, "why_here": "A reviewed part of the story.",
                  "fact_ids": [f"F{n}"], "picture_ids": [], "must_cover": True, "gaps": [f"A picture of {label.lower()}"]}
                 for n, (sid, label, kind) in enumerate([
                     ("powertrain", "Engine choice", "fundamental"), ("space", "Room for passengers", "fundamental"),
                     ("safety", "Safety features", "fundamental"), ("delighters", "Cabin extras", "delighter")], 1)]
        pb = {"category": "compact suv", "category_source": "library", "stops": stops,
              "usps": [{"id": f"usp{n}", "name": name, "fact_ids": [f"F{n}"], "stop_id": stops[n - 1]["id"]}
                       for n, name in enumerate(["Pick your engine choice", "Room for your passengers", "Safety for every journey"], 1)],
              "objections": [], "evidence_gaps": [{"what": "Warranty terms", "why_it_matters": "Ownership planning", "suggested_source": "Warranty document"}],
              "notes": "", "issues": []}
        store.write_json(did, "playbook.json", pb)
        api = TestClient(app)
        payload = {"stop_order": ["space", "powertrain", "safety", "delighters"], "kinds": {"safety": "fundamental"}}
        response = api.patch(f"/api/demos/{did}/align/playbook", json=payload)
        check("story review: validated order is saved", response.status_code == 200 and store.read_json(did, "playbook-overrides.json")["stop_order"] == payload["stop_order"])
        check("story review: revision starts at Plan", revise.call_count == 1 and revise.call_args.args[:2] == (did, "plan"))
        approvals = store.load(did)["approvals"]
        check("story review: only script and visuals approvals are cleared", not approvals["script"] and not approvals["visuals"] and all(approvals[key] for key in store.CARDS if key not in ("script", "visuals")))
        card = align.cards(did)["script"]["playbook"]
        check("story review: the script card carries ordered stops, winning points, gaps and issues", [stop["id"] for stop in card["stops"]] == payload["stop_order"] and len(card["usps"]) == 3 and card["gaps"] == pb["evidence_gaps"] and "issues" in card)
        def snapshot():
            return {name: store.path(did, name).read_bytes() for name in ("demo.json", "playbook.json", "playbook-overrides.json")}
        for label, invalid in [
            ("non-object", []), ("unknown property", {**payload, "approved": True}),
            ("missing stop", {**payload, "stop_order": payload["stop_order"][:-1]}),
            ("repeated stop", {**payload, "stop_order": ["space", "space", "safety", "delighters"]}),
            ("unknown stop", {**payload, "stop_order": ["space", "powertrain", "safety", "unknown"]}),
            ("invalid kind", {**payload, "kinds": {"space": "lead"}}),
            ("unknown kind target", {**payload, "kinds": {"unknown": "fundamental"}}),
            ("removing every fundamental", {**payload, "kinds": {stop["id"]: "delighter" for stop in stops}}),
        ]:
            before = snapshot()
            rejected = api.patch(f"/api/demos/{did}/align/playbook", json=invalid)
            check(f"story review: {label} rejected without mutations", rejected.status_code == 400 and before == snapshot())
        with patch.object(graph, "is_running", return_value=True):
            before = snapshot()
            rejected = api.patch(f"/api/demos/{did}/align/playbook", json=payload)
            check("story review: running stage blocks edits without mutations", rejected.status_code == 409 and before == snapshot())
        action = {"type": "request_upload", "upload_kind": "document", "reason": "Warranty terms — Warranty document"}
        response = api.post(f"/api/demos/{did}/align/request-upload", json=action)
        check("story review: gap button executes the existing upload action", response.status_code == 200 and response.json()["actions"] == [action] and "Warranty terms" in store.read_json(did, "conversation.json")[-1]["text"] and revise.call_count == 1)
        before = copy.deepcopy(store.load(did)["approvals"])
        rejected = api.post(f"/api/demos/{did}/align/request-upload", json={"type": "approve", "upload_kind": "document", "reason": "approve"})
        check("story review: upload route cannot approve cards", rejected.status_code == 400 and store.load(did)["approvals"] == before)
        response = api.post(f"/api/demos/{did}/revise", json={"stage": "coach", "instruction": "Review the story"})
        check("story review: Coach is accepted by the revision API", response.status_code == 200 and revise.call_args.args[1] == "coach")
        store.update(did, lambda demo: [stage.update(status="done") for stage in demo["stages"].values()])
        revise.side_effect = RuntimeError("Dispatch unavailable")
        response = api.patch(f"/api/demos/{did}/align/playbook", json=payload)
        check("story review: dispatch failure leaves all dependent artifacts stale", response.status_code == 409 and all(store.load(did)["stages"][stage]["status"] == "stale" for stage in ("plan", "author", "deck", "voice", "bundle")))
        check("story review: no outbound socket calls", not any(mock.called for mock in blocked))


if __name__ == "__main__":
    with tempfile.TemporaryDirectory(prefix="coach-align-process-") as tmp:
        os.environ.update(MOCK_LLM="1", CLOUD_SYNC="0", DEMO_STUDIO_DATA=tmp, DEMO_STUDIO_GRAPH_DB=str(Path(tmp) / "graph.sqlite"))
        sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
        rows = []
        def check(name, ok):
            rows.append((name, bool(ok)))
            print(("PASS " if ok else "FAIL ") + name)
        run(check)
        print(f"{sum(ok for _, ok in rows)}/{len(rows)} coach Align contracts passed")
        raise SystemExit(0 if all(ok for _, ok in rows) else 1)
