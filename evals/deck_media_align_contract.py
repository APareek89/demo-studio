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
        before_media_edit = {name: store.read_json(did, name) for name in ("deck.json", "deck-overrides.json")}
        media_only = api.patch(f"/api/demos/{did}/align/deck", json={"slides": [{"slide_id":"s1", "media":["im1"], "callouts":[]}]})
        media_label = (store.read_json(did, "deck.json")["slides"][0].get("callouts") or [{}])[0]
        check("media-only API edit retains existing feature text and evidence", media_only.status_code == 200
              and all(media_label.get(key) == callout.get(key) for key in ("id", "text", "fact_ids", "reveal_on_line")))
        check("media-only API edit retires stale saved part and drag instead of anchoring new illustration", media_only.status_code == 200
              and media_label.get("image_id") == "im1" and media_label.get("placement") == "panel"
              and not media_label.get("part") and media_label.get("anchor") is None and media_label.get("label_pos") is None)
        if media_only.status_code == 200:
            saved = store.read_json(did, "deck-overrides.json")["slides"][0]
            check("media-only API edit does not save obsolete attachment geometry", all(not any(key in c for key in ("image_id", "part", "label_pos", "placement")) for c in saved.get("callouts", [])))
        else:
            check("media-only API edit does not save obsolete attachment geometry", False)
        for name, value in before_media_edit.items(): store.write_json(did, name, value)
        legacy = copy.deepcopy(before_media_edit["deck.json"])
        legacy["slides"][0].update(image_id="im2", media=[legacy["slides"][0]["media"][1]])
        store.write_json(did, "deck.json", legacy)
        store.write_json(did, "deck-overrides.json", {"slides":[{"slide_id":"s1", "image_id":"im2", "callouts":[{"id":"c1", "image_id":"im2", "part":"bonnet", "label_pos":{"x":.15, "y":.15}}]}]})
        legacy_edit = api.patch(f"/api/demos/{did}/align/deck", json={"slides":[{"slide_id":"s1", "image_id":"im1"}]})
        legacy_label = store.read_json(did, "deck.json")["slides"][0]["callouts"][0]
        check("legacy primary-picture edits retire old saved attachment geometry", legacy_edit.status_code == 200
              and legacy_label["image_id"] == "im1" and legacy_label["placement"] == "panel" and legacy_label["anchor"] is None and not legacy_label["part"])
        for name, value in before_media_edit.items(): store.write_json(did, name, value)
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
              and len(store.read_json(did, "deck.json")["slides"][0]["callouts"]) == 1
              and all(c.get("placement") == "panel" and not c.get("anchor") for c in store.read_json(did, "deck.json")["slides"][0]["callouts"]))
        check("two-picture review makes no outbound requests", not any(mock.called for mock in blocked))

        # Missing labels can be restored explicitly through the same review API;
        # ordinary edits still cannot silently create unknown IDs.
        creation_slide = {**copy.deepcopy(slide), "callouts":[], "fact_ids":["F1"],
                          "lines":[{"id":"l1", "text":"Petrol engine", "fact_ids":["F1"]}]}
        store.write_json(did, "deck.json", {"slides":[creation_slide]})
        store.write_json(did, "deck-overrides.json", {"slides":[]})
        und["facts"].extend([{"id":"F2", "claim":"Held", "value":"Held", "approved":False},
                             {"id":"F3", "claim":"Other feature", "value":"Other", "approved":True}])
        store.write_json(did, "understanding.json", und)
        new_label = {"id":"s1-reviewed-feature", "create":True, "text":"Petrol engine", "fact_ids":["F1"],
                     "reveal_on_line":0, "image_id":"im1"}
        for name, update in (
            ("ordinary unknown edit", {"create":False}),
            ("missing citations", {"fact_ids":[]}), ("unknown citation", {"fact_ids":["missing"]}),
            ("rejected citation", {"fact_ids":["F2"]}), ("foreign slide citation", {"fact_ids":["F3"]}),
            ("unknown picture", {"image_id":"im3"}), ("invalid reveal", {"reveal_on_line":1}),
            ("noninteger reveal", {"reveal_on_line":True}),
            ("nontext label", {"text":None}), ("nontext part", {"part":{}}),
            ("overlong label", {"text":"This source faithful feature label is longer than eight words"}),
        ):
            before = snapshot()
            response = api.patch(f"/api/demos/{did}/align/deck", json={"slides":[{"slide_id":"s1", "callouts":[{**new_label, **update}]}]})
            check(f"create: {name} rejected without artifact changes", response.status_code == (404 if name == "ordinary unknown edit" else 400) and snapshot() == before)
        response = api.patch(f"/api/demos/{did}/align/deck", json={"slides":[{"slide_id":"s1", "callouts":[new_label]}]})
        labels = store.read_json(did, "deck.json")["slides"][0]["callouts"]
        check("create: explicit reviewed label saved with exact citations and reveal", response.status_code == 200 and len(labels) == 1
              and all(labels[0].get(key) == new_label[key] for key in ("id", "text", "fact_ids", "reveal_on_line", "image_id")))
        check("create: label defaults to a caption without guessing a part", bool(labels) and labels[0]["placement"] == "panel" and labels[0]["anchor"] is None)
        before = snapshot()
        repeated = api.patch(f"/api/demos/{did}/align/deck", json={"slides":[{"slide_id":"s1", "callouts":[new_label]}]})
        check("create: duplicate ID is rejected without replacing reviewed wording", repeated.status_code == 400 and snapshot() == before)
        restored = [copy.deepcopy(creation_slide)]
        deck.apply_overrides(restored, store.read_json(did, "deck-overrides.json"), {"im1":images[0]}, {"F1", "F3"}, strict=False)
        check("create: saved explicit label is restored after regeneration and stays idempotent", restored[0]["callouts"] == labels and bool(labels))
        deck.apply_overrides(restored, store.read_json(did, "deck-overrides.json"), {"im1":images[0]}, {"F1", "F3"}, strict=False)
        check("create: replay never duplicates the restored label", restored[0]["callouts"] == labels and len(labels) == 1)
        retired = [copy.deepcopy(creation_slide)]
        deck.apply_overrides(retired, store.read_json(did, "deck-overrides.json"), {"im1":images[0]}, {"F3"}, strict=False)
        check("create: a later held fact cannot resurrect a saved label", retired[0]["callouts"] == [])
        replacement = {**copy.deepcopy(creation_slide), "image_id":None, "media":[], "callouts":[]}
        deck.apply_overrides([replacement], store.read_json(did, "deck-overrides.json"), {}, {"F1"}, strict=False)
        check("create: excluded saved picture retains approved wording as an unanchored caption", len(replacement["callouts"]) == 1
              and replacement["callouts"][0]["text"] == new_label["text"] and replacement["callouts"][0]["image_id"] is None
              and replacement["callouts"][0]["placement"] == "panel" and replacement["callouts"][0]["anchor"] is None)
        extras = [{**new_label, "id":f"s1-extra-{index}"} for index in (2, 3)]
        response = api.patch(f"/api/demos/{did}/align/deck", json={"slides":[{"slide_id":"s1", "callouts":extras}]})
        check("create: three explicit reviewed captions fit the existing per-picture cap", response.status_code == 200
              and len(store.read_json(did, "deck.json")["slides"][0]["callouts"]) == 3)
        before = snapshot()
        response = api.patch(f"/api/demos/{did}/align/deck", json={"slides":[{"slide_id":"s1", "callouts":[{**new_label, "id":"s1-fourth"}]}]})
        check("create: fourth label is rejected without changing approved wording", response.status_code == 400 and snapshot() == before)


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
