"""Offline contracts for Author bindings when a pixel audit is unavailable."""
from __future__ import annotations

import copy
from contextlib import ExitStack
import os
from pathlib import Path
import socket
import sys
import tempfile
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def run(check):
    with tempfile.TemporaryDirectory(prefix="visual-alignment-") as tmp, ExitStack() as stack:
        stack.enter_context(patch.dict(os.environ, {
            "MOCK_LLM": "1", "CLOUD_SYNC": "0", "STORAGE_BACKEND": "local",
            "DEMO_STUDIO_DATA": str(Path(tmp) / "demos"),
            "DEMO_STUDIO_GRAPH_DB": str(Path(tmp) / "graph.sqlite"),
        }))
        blocked = [stack.enter_context(patch(name, side_effect=AssertionError("Outbound blocked")))
                   for name in ("socket.socket.connect", "socket.socket.connect_ex",
                                "socket.create_connection", "socket.getaddrinfo")]
        from server import config, store
        from server.agents import author, visuals

        stack.enter_context(patch.object(config, "DATA_DIR", Path(tmp) / "demos"))
        stack.enter_context(patch.object(config, "GRAPH_DB", Path(tmp) / "graph.sqlite"))
        stack.enter_context(patch.object(config, "MOCK_LLM", True))
        provider = stack.enter_context(patch.object(visuals.gemini, "structured",
                                                    side_effect=AssertionError("Real vision provider blocked")))
        did = store.new_demo("Visual binding regression")["id"]
        store.update(did, lambda demo: demo.update(sources=[
            {"id": "source-picture", "kind": "image", "path": "sources/fixture.png"},
            {"id": "source-excluded", "kind": "image", "use_in_demo": False},
        ]))

        def image(ref, parts, description=""):
            return {"id": ref, "source_id": "source-picture", "quality": 4,
                    "parts": parts, "description": description}

        und = {"facts": [{"id": "F1", "claim": "Fixture equipment", "approved": True}],
               "shots": [{"id": "shot-wheel", "source_id": "source-picture", "quality": 4,
                          "part": "wheel", "description": "Wheel detail"}],
               "images": [image("wheel", ["alloy", "wheel", "tyre"]),
                          image("steering", ["steering", "wheel"]),
                          image("climate", ["console"], "Controls"),
                          image("temperature-distractor", ["temperature"], "Engine temperature gauge"),
                          image("roof", ["roof"]), image("lamp", ["headlamp"]),
                          image("engine", ["engine"]), image("boot", ["boot"]),
                          image("seat", ["seat"])]}

        def line(id, text, visual):
            return {"id": id, "text": text, "fact_ids": ["F1"], "visual": visual}

        def script():
            return {"segments": [{"id": "proof", "title": "Equipment", "topic": "equipment",
                                  "role": "proof", "checkin": "",
                                  "lines": [line("wheel-line", "The alloy wheel and tyre.",
                                                 {"kind": "image", "ref": "wheel", "focus": "spokes"}),
                                            line("climate-line", "Choose the temperature setting.",
                                                 {"kind": "image", "ref": "climate", "focus": "buttons"})],
                                  "deeper": [line("deeper-line", "The temperature setting.",
                                                  {"kind": "image", "ref": "climate", "focus": "dial"})]}],
                    "closing": [line("closing-line", "Your temperature setting.",
                                     {"kind": "image", "ref": "climate", "focus": "setting"})]}

        def bindings(draft):
            lines = [ln for seg in draft["segments"] for ln in seg["lines"] + seg["deeper"]]
            return {ln["id"]: copy.deepcopy(ln.get("visual")) for ln in lines + draft["closing"]}

        original = script()
        expected = bindings(original)
        messages = []
        aligned = visuals.align(did, copy.deepcopy(original), und, messages.append)
        actual = bindings(aligned)
        audit = store.read_json(did, "visual-audit.json")
        check("rules: matching picture survives unused steering-wheel distractor", actual["wheel-line"] == expected["wheel-line"])
        check("rules: sparse tags do not replace the Author's picture", actual["climate-line"] == expected["climate-line"])
        check("rules: deeper bindings and focus remain intact", actual["deeper-line"] == expected["deeper-line"])
        check("rules: closing bindings and focus remain intact", actual["closing-line"] == expected["closing-line"])
        check("rules: stronger lexical candidates remain recorded proposals",
              any(p["line_id"] == "climate-line" and p["proposal"] == "temperature-distractor" for p in audit["proposals"]))
        check("rules: no assignment changes or pixel findings are claimed",
              audit["changes"] == [] and audit["lines"] == [] and audit["images"] == []
              and audit["method"] == "rules_fallback" and audit["model"] is None)
        check("rules: unused distractors remain unused", "steering" in audit["unused_after"]
              and "temperature-distractor" in audit["unused_after"])
        check("rules: status says bindings were retained without pixel proof",
              any("retained" in message and "unavailable" in message for message in messages))

        none_script = script()
        none_script["segments"][0]["lines"][0]["visual"] = {"kind": "none", "ref": "", "focus": ""}
        none_script["segments"][0]["lines"][1]["visual"] = None
        none_expected = bindings(none_script)
        none_result = bindings(visuals.align(did, none_script, und))
        check("rules: explicit none is not filled by metadata matches", none_result["wheel-line"] == none_expected["wheel-line"])
        check("rules: null visual is not filled by metadata matches", none_result["climate-line"] is None)
        empty = script()
        check("rules: an empty catalogue leaves the entire draft unchanged",
              visuals.align(did, empty, {"images": [], "shots": []}) == script())

        with patch.object(config, "MOCK_LLM", False):
            messages = []
            with patch.object(visuals, "_vision_batches", side_effect=RuntimeError("fixture provider failure")) as failed:
                result = visuals.align(did, copy.deepcopy(original), und, messages.append)
            check("provider failure: Author refs are preserved", bindings(result) == expected and failed.call_count == 1)
            check("provider failure: proposals do not become replacements",
                  store.read_json(did, "visual-audit.json")["changes"] == [])
            check("provider failure: status does not claim rules were applied",
                  any("retained" in message for message in messages) and not any("applied instead" in message for message in messages))
            with patch.object(visuals, "_vision_batches", return_value=([], [])):
                result = visuals.align(did, copy.deepcopy(original), und)
            check("empty pixel result: Author refs are preserved", bindings(result) == expected)

            pixel = {"segments": [{"id": "proof", "title": "Equipment", "topic": "equipment", "role": "proof",
                                    "deeper": [], "lines": [
                                        line(coverage, "The alloy wheel and tyre.", {"kind": "image", "ref": "wheel"})
                                        for coverage in ("partial", "none", "not_visual", "full")]}], "closing": []}
            assignments = [{"line_id": coverage, "visual": "steering", "coverage": coverage,
                            "spoken_features": ["wheel", "tyre"], "visible_features": ["wheel"],
                            "missing_features": ["tyre"] if coverage == "partial" else [],
                            "confidence": .9, "reason": "Fake pixel judgment"}
                           for coverage in ("partial", "none", "not_visual", "full")]
            with patch.object(visuals, "_vision_batches", return_value=(assignments, [])):
                result = visuals.align(did, pixel, und)
            pixel_bindings = bindings(result)
            for coverage in ("partial", "none", "not_visual"):
                check(f"pixels: {coverage} rejection remains authoritative", pixel_bindings[coverage] is None)
            check("pixels: full coverage can still replace the current image", pixel_bindings["full"]["ref"] == "steering")
            pixel_audit = store.read_json(did, "visual-audit.json")
            check("pixels: heuristics never resurrect rejected refs", pixel_audit["method"] == "gemini_pixels"
                  and all(change["pass"] == "gemini_vision" for change in pixel_audit["changes"]))

            # Exercise the real completeness/consistency boundary with fake image bytes and a fake model response.
            one = {"images": und["images"][:1], "shots": []}
            cat = visuals.catalogue(did, one, store.load(did))
            rows = [{"ln": line("check", "Wheel and tyre", {"ref": "wheel"}),
                     "seg": {"title": "Wheel", "topic": "wheel"}, "cur": "wheel", "proposal": None, "hits": []}]
            bad_audit = visuals.VisualsOut(assignments=[visuals.Assignment(
                line_id="check", visual="wheel", coverage="full", missing_features=["tyre"], reason="Inconsistent fixture")],
                images=[visuals.ImageAudit(visual="wheel")])
            with patch.object(visuals.media, "model_image_path", return_value=Path(tmp) / "fake.png"), \
                 patch.object(visuals.gemini, "bytes_part", return_value="fake image bytes"), \
                 patch.object(visuals.gemini, "structured", return_value=bad_audit):
                rejected = False
                try:
                    visuals._vision_batches(did, store.load(did), one, cat, rows)
                except RuntimeError as error:
                    rejected = "internally inconsistent" in str(error)
                check("pixel validator: full coverage with a missing feature still fails", rejected)

        # Source exclusions remain the Author validator's responsibility, before alignment.
        excluded = {**copy.deepcopy(und), "images": copy.deepcopy(und["images"]) + [
            {**image("excluded", ["wheel"]), "source_id": "source-excluded"}]}
        for item in excluded["images"] + excluded["shots"]:
            item["_allowed"] = store.visual_allowed(store.load(did), item["source_id"])
        draft = script()
        draft["segments"][0]["lines"][0]["visual"] = {"kind": "image", "ref": "excluded", "focus": ""}
        author.validate(draft, excluded)
        check("source boundary: Author still clears an excluded ref", bindings(draft)["wheel-line"]["kind"] == "none"
              and bindings(draft)["wheel-line"]["ref"] == "")
        after = visuals.align(did, draft, excluded)
        check("source boundary: rules cannot refill the cleared ref", bindings(after)["wheel-line"]["ref"] == "")
        check("isolation: data and graph paths are temporary", config.DATA_DIR.is_relative_to(tmp) and config.GRAPH_DB.is_relative_to(tmp))
        check("isolation: no real provider or socket was called", not provider.called and not any(mock.called for mock in blocked))


if __name__ == "__main__":
    rows = []

    def check(name, passed):
        rows.append(bool(passed))
        print(("PASS " if passed else "FAIL ") + name)

    run(check)
    print(f"{sum(rows)}/{len(rows)} visual alignment contracts passed")
    raise SystemExit(0 if all(rows) else 1)
