"""Offline API contracts for reviewed two-picture slides and per-picture labels."""
from __future__ import annotations

import copy
import os
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch
from contextlib import ExitStack


def run(check):
    from fastapi.testclient import TestClient
    from server import config, schemas, store
    from server.app import app
    from server.agents import deck

    with tempfile.TemporaryDirectory(prefix="deck-media-align-") as tmp, ExitStack() as stack:
        stack.enter_context(patch.object(config, "DATA_DIR", Path(tmp)))
        stack.enter_context(patch.object(config, "MOCK_LLM", True))
        blocked = [stack.enter_context(patch(name, side_effect=AssertionError("Outbound blocked"))) for name in
                   ("socket.create_connection", "socket.socket.connect", "socket.socket.connect_ex")]
        did = store.new_demo("Two pictures")["id"]
        sources = [{"id": f"src{n}", "kind": "image", "path": f"sources/{n}.png", "use_in_demo": n != 3} for n in (1, 2, 3)]
        store.update(did, lambda d: d.update(sources=sources, approvals={key: True for key in store.CARDS}))
        images = [{"id": f"im{n}", "source_id": f"src{n}", "angle": "front", "description": "Front view", "quality": 5,
                   "parts": [{"name": "bonnet", "confidence": .9, "box": {"x": .15 * n, "y": .4, "w": .12, "h": .1}}]} for n in (1, 2, 3)]
        und = {"product": {"name": "Fixture"}, "facts": [{"id": "F1", "claim": "Engine choice", "value": "Petrol engine", "approved": True}],
               "images": images, "shots": [], "unknowns": [], "brand": {}}
        label = {"id": "c1", "text": "Petrol engine", "fact_ids": ["F1"], "part": "bonnet", "reveal_on_line": 0}
        slide = {"id": "s1", "segment_id": "proof", "kind": "proof", "title": "Engine choice", "image_id": "im1",
                 "media": [{"image_id": "im1", "from_line": 0, "proxy": True, "proxy_reason": "closest by part: bonnet"}], "callouts": [label], "lines": []}
        store.write_json(did, "understanding.json", und)
        store.write_json(did, "deck.json", {"slides": [slide]})
        store.write_json(did, "deck-overrides.json", {"slides": []})
        api = TestClient(app)
        def snapshot():
            return {name: store.path(did, name).read_bytes() for name in ("demo.json", "deck.json", "deck-overrides.json")}
        response = api.patch(f"/api/demos/{did}/align/deck", json={"slides": [{"slide_id": "s1", "media": ["im1", "im2"],
            "callouts": [{"id": "c1", "image_id": "im2", "part": "bonnet", "label_pos": {"x": .15, "y": .15}}]}]})
        assert response.status_code == 200, response.text
        reviewed = response.json()["cards"]["deck"]["slides"][0]
        check("two-picture review persists IDs and resolves both picture URLs", [m["image_id"] for m in reviewed["media"]] == ["im1", "im2"]
              and all(m["image_url"] and m["image_parts"] for m in reviewed["media"]) and reviewed["image_id"] == "im1")
        callout = reviewed["callouts"][0]
        check("callout anchors and drag fractions belong to its second picture", callout["image_id"] == "im2"
              and abs(callout["anchor"]["x"] - .36) < .001 and callout["label_pos"] == {"x": .15, "y": .15})
        check("reviewed illustrations retain the proxy badge", reviewed["media"][0]["proxy"] is True)
        approvals = store.load(did)["approvals"]
        check("media review resets script approval without granting any approval", not approvals["script"]
              and all(approvals[key] for key in store.CARDS if key != "script"))
        rebuilt = [copy.deepcopy(slide)]
        deck.apply_overrides(rebuilt, store.read_json(did, "deck-overrides.json"), {i["id"]: i for i in images[:2]}, {"F1"})
        check("saved picture assignments and per-picture drags survive rebuild", rebuilt[0]["callouts"][0]["image_id"] == "im2"
              and rebuilt[0]["callouts"][0]["label_pos"] == {"x": .15, "y": .15})
        for name, edit in [
            ("three pictures", {"media": ["im1", "im2", "im3"]}),
            ("excluded picture", {"media": ["im1", "im3"]}),
            ("duplicate picture", {"media": ["im1", "im1"]}),
            ("non-list pictures", {"media": "im1"}),
            ("unknown callout picture", {"callouts": [{"id": "c1", "image_id": "im3"}]}),
            ("conflicting legacy primary", {"media": ["im1", "im2"], "image_id": "im2"}),
        ]:
            before = snapshot()
            result = api.patch(f"/api/demos/{did}/align/deck", json={"slides": [{"slide_id": "s1", **edit}]})
            check(f"{name} fails without changing any saved artifact", result.status_code == 400 and snapshot() == before)
        before = snapshot()
        with patch.object(schemas.Deck, "model_validate", side_effect=ValueError("Fixture validation failure")):
            result = api.patch(f"/api/demos/{did}/align/deck", json={"slides": [{"slide_id": "s1", "title": "New heading"}]})
        check("failed final validation preserves previous deck and overrides", result.status_code == 400 and snapshot() == before)
        # Excluding an old saved choice must not poison unrelated later edits.
        store.update(did, lambda demo: next(source for source in demo["sources"] if source["id"] == "src2").update(use_in_demo=False))
        safe_deck = store.read_json(did, "deck.json")
        deck.apply_overrides(safe_deck["slides"], store.read_json(did, "deck-overrides.json"), {"im1": images[0]}, {"F1"}, strict=False)
        store.write_json(did, "deck.json", safe_deck)
        result = api.patch(f"/api/demos/{did}/align/deck", json={"slides": [{"slide_id": "s1", "title": "Reviewed engine choice"}]})
        check("an excluded saved picture does not block later title edits", result.status_code == 200
              and all(ref != "im2" for row in store.read_json(did, "deck-overrides.json")["slides"] for ref in row.get("media", [])))
        result = api.patch(f"/api/demos/{did}/align/deck", json={"slides": [{"slide_id": "s1", "media": [],
            "callouts": [{"id": "c1", "image_id": None}]}]})
        check("removing pictures accepts the editor's null callout attachment", result.status_code == 200
              and store.read_json(did, "deck.json")["slides"][0]["media"] == []
              and all(c.get("placement") == "panel" and not c.get("anchor") for c in store.read_json(did, "deck.json")["slides"][0]["callouts"]))
        check("two-picture review makes no outbound requests", not any(mock.called for mock in blocked))


if __name__ == "__main__":
    with tempfile.TemporaryDirectory(prefix="deck-media-process-") as tmp:
        os.environ.update(MOCK_LLM="1", CLOUD_SYNC="0", DEMO_STUDIO_DATA=tmp, DEMO_STUDIO_GRAPH_DB=str(Path(tmp) / "graph.sqlite"))
        sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
        rows = []
        def check(name, passed):
            rows.append(bool(passed)); print(("PASS " if passed else "FAIL ") + name)
        run(check)
        print(f"{sum(rows)}/{len(rows)} deck media Align contracts passed")
        raise SystemExit(0 if all(rows) else 1)
