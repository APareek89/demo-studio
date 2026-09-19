"""Free actual API proof: a reviewed edit never changes an existing citation."""
from __future__ import annotations

import copy
import tempfile
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch


def run(check):
    from fastapi.testclient import TestClient
    from server import cloud, config, graph, knowledge, orchestrator, schemas, store
    from server.app import app
    with tempfile.TemporaryDirectory(prefix="fact-identity-") as tmp, ExitStack() as stack:
        stack.enter_context(patch.multiple(config, DATA_DIR=Path(tmp), GRAPH_DB=Path(tmp)/"graph.sqlite", MOCK_LLM=True))
        stack.enter_context(patch.object(cloud, "enabled", return_value=False))
        stack.enter_context(patch.object(cloud, "sync_demo_async"))
        stack.enter_context(patch.object(cloud, "put_event"))
        running = stack.enter_context(patch.object(graph, "is_running", return_value=False))
        blocked = [stack.enter_context(patch(name, side_effect=AssertionError("No network or model calls")))
                   for name in ("socket.create_connection", "socket.socket.connect", "socket.socket.connect_ex", "server.llm.gemini.client")]
        did = store.new_demo("Fact identity fixture")["id"]
        source = store.add_text_source(did, "brochure", "Length: 3995 mm. India, SX.", "catalogue")
        fact = schemas.Fact(id="F001", kind="spec", claim="Length", value="3995 mm", confidence=1,
                            source=schemas.FactSource(ref=source["id"], locator="page 1", quote="Length: 3995 mm.")).model_dump()
        store.write_json(did, "understanding.json", {"product": {"name": "Fixture"}, "facts": [fact], "images": [], "shots": [], "unknowns": [], "brand": {},
            "knowledge": {"conflicts": [{"id": "conf_old", "fact_ids": ["F001", "F099"], "preferred_fact_id": "F001", "status": "resolved"}]}})
        store.write_json(did, "plan.json", {"segments": [], "voice": {}})
        store.write_json(did, "script.json", {"segments": [], "closing": []})
        store.write_json(did, "deck.json", {"slides": []})
        store.write_json(did, "bundle.json", {"facts": [copy.deepcopy(fact)]})
        def approve(d):
            d["approvals"].update({c: True for c in store.CARDS})
            for stage in d["stages"].values(): stage["status"] = "done"
        store.update(did, approve)
        published = knowledge.snapshot(did, publish=True)
        before_snapshot = store.path(did, f"knowledge/snapshots/{published['id']}.json").read_bytes()
        before_bundle = store.path(did, "bundle.json").read_bytes()
        before_pointer = store.path(did, "knowledge/published.json").read_bytes()
        api = TestClient(app)
        def edit(fid, payload): return api.patch(f"/api/demos/{did}/align/facts/{fid}", json=payload)
        def disk(): return {str(p.relative_to(store.demo_dir(did))): p.read_bytes() for p in store.demo_dir(did).rglob("*") if p.is_file()}
        response = edit("F001", {"scope": {"market": "India", "variant": "SX", "model_year": "2026"}})
        result = response.json(); replacement = result["fact"]["id"]
        check("identity: scope-only edit gets a fresh literal ID and explicit previous_id", response.status_code == 200 and result["changed"] and replacement != "F001" and result["previous_id"] == "F001")
        saved = store.read_json(did, "understanding.json")
        check("identity: current registry contains only replacement; no alias rebinding", saved["facts"][0]["id"] == replacement and saved["facts"][0]["scope"]["variant"] == "SX" and all(f["id"] != "F001" for f, _ in store.fact_entries(saved)))
        check("identity: old published snapshot, pointer and bundle bytes are immutable", store.path(did, f"knowledge/snapshots/{published['id']}.json").read_bytes() == before_snapshot and store.path(did, "bundle.json").read_bytes() == before_bundle and store.path(did, "knowledge/published.json").read_bytes() == before_pointer)
        ledger = store.read_json(did, "knowledge/identities.json")
        check("identity: old ledger meaning remains exact", ledger["ids"]["F001"]["identity"] == knowledge._identity(fact) and ledger["ids"][replacement]["identity"] != ledger["ids"]["F001"]["identity"])
        check("identity: prior conflict is superseded, never retargeted", saved["knowledge"]["conflicts"][0]["status"] == "superseded" and saved["knowledge"]["conflicts"][0]["fact_ids"] == ["F001", "F099"] and saved["knowledge"]["conflicts"][0]["superseded_by"] == replacement)
        demo = store.load(did)
        check("identity: downstream drafts stale and all cards need approval", not any(demo["approvals"].values()) and all(demo["stages"][s]["status"] == "stale" for s in orchestrator.DOWNSTREAM["understand"]))
        before = disk(); same = edit(replacement, {"value": "3995 mm", "scope": {"market": "India", "variant": "SX", "model_year": "2026"}})
        check("identity: no-op edit preserves ID, approvals, ledger and files", same.status_code == 200 and same.json()["changed"] is False and "previous_id" not in same.json() and disk() == before)
        check("identity: retired ID cannot be edited or approved as an alias", edit("F001", {"value": "4000 mm"}).status_code == 404 and api.post(f"/api/demos/{did}/align/facts/F001/approval", json={"approved": True}).status_code == 404 and disk() == before)
        for label, scope in (("unknown key", {"magic": "all"}), ("non-text value", {"model_year": 2026}), ("bad date", {"effective_from": "2026-02-30"}), ("reversed dates", {"effective_from": "2026-10-01", "effective_to": "2026-09-01"}), ("oversized value", {"variant": "a"*501}), ("non-object", ["SX"])):
            before = disk(); result = edit(replacement, {"scope": scope})
            check("identity: " + label + " scope rejects without allocating an ID", result.status_code == 400 and disk() == before)
        before = disk(); running.return_value = True
        check("identity: running graph blocks concurrent fact edits", edit(replacement, {"value": "4000 mm"}).status_code == 409 and disk() == before)
        running.return_value = False
        notes = orchestrator.apply_actions(did, [{"type": "edit_fact", "fact_id": replacement, "fact_conditions": "India only"}], [], "align", {})
        latest = store.read_json(did, "understanding.json")["facts"][0]
        check("identity: chat correction versions again and reports both IDs", latest["id"] != replacement and notes == [f"edited {replacement} → {latest['id']}"])
        check("identity: no network or provider construction", not any(p.called for p in blocked))


if __name__ == "__main__":
    rows = []
    def check(name, ok, detail=""):
        rows.append(bool(ok)); print(("PASS " if ok else "FAIL ") + name)
    run(check); print(f"Fact identity contracts: {sum(rows)}/{len(rows)}")
    raise SystemExit(0 if all(rows) else 1)
