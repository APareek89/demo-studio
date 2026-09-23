"""Legacy FAQ replies cannot replay old engineering wording or mismatched audio."""
from __future__ import annotations

import copy
from contextlib import ExitStack
from unittest.mock import patch


def run(check):
    from fastapi.testclient import TestClient
    from server import store
    from server.app import app
    from server.agents import faq, qa, voice

    demo_id = store.new_demo("Cached speech fixture")["id"]
    store.update(demo_id, lambda demo: demo["settings"].update(tts_provider="sarvam", sarvam_speaker="priya", voice_locked=True, language="en-IN"))
    fact = {"id": "F1", "kind": "feature", "claim": "Front suspension", "value": "McPherson strut", "approved": True}
    store.write_json(demo_id, "understanding.json", {"facts": [fact], "competitors": []})
    entry = {"id": "Q01", "question": "Tell me about the suspension?", "answer": "It has McPherson strut front suspension.",
             "fact_ids": ["F1"], "answered": True}
    entry["audio"] = voice.save_streamed_clip(demo_id, entry["answer"], b"\0\0" * 2400, speaker="priya", language="en-IN")
    bank = {"entries": [entry]}
    store.write_json(demo_id, "faq.json", bank)
    with ExitStack() as stack:
        blocked = [stack.enter_context(patch(name, side_effect=AssertionError("No outbound calls")))
                   for name in ("socket.create_connection", "socket.socket.connect", "socket.socket.connect_ex")]
        stack.enter_context(patch.object(qa, "answer", side_effect=AssertionError("No model needed")))
        stack.enter_context(patch.object(voice, "render_line", side_effect=AssertionError("No TTS needed")))
        stack.enter_context(patch.object(faq, "match", side_effect=lambda *_: copy.deepcopy(entry)))
        api = TestClient(app)

        def ask(question="Tell me about the suspension?"):
            response = api.post(f"/api/demos/{demo_id}/run/qa", json={"question": question, "voice_it": False})
            assert response.status_code == 200, response.text
            return response.json()

        result = ask()
        check("cached everyday speech uses reviewed rendering", result["answer"] == "It has strut-type front suspension.")
        check("cached reply keeps approved citations", result["fact_ids"] == ["F1"] and result["answered"])
        check("changed cached text cannot replay stale audio", result["audio"] is None)
        check("cached reply records substitutions", result["plain_language_substitutions"] == [["mcpherson strut", "strut-type front suspension"]])
        check("serving old speech leaves persisted bank intact", store.read_json(demo_id, "faq.json") == bank)
        result = ask("What is the exact type of suspension?")
        check("explicit technical question retains exact cached speech", result["answer"] == entry["answer"] and result["audio"].endswith(entry["audio"]))
        store.update(demo_id, lambda demo: demo["settings"].update(audience="expert"))
        result = ask()
        check("expert audience bypasses cached substitution", result["answer"] == entry["answer"] and not result["plain_language_substitutions"])
        store.update(demo_id, lambda demo: demo["settings"].update(audience="everyday"))
        reviewed_audio = voice.save_streamed_clip(demo_id, "It has strut-type front suspension.", b"\1\0" * 2400, speaker="priya", language="en-IN")
        entry.update(answer="It has strut-type front suspension.", audio=reviewed_audio,
                     plain_language_substitutions=[["mcpherson strut", "strut-type front suspension"]])
        result = ask()
        check("already normalized speech keeps matching audio and provenance", result["audio"].endswith(reviewed_audio)
              and result["plain_language_substitutions"] == entry["plain_language_substitutions"])
        check("cached speech uses no network", not any(mock.called for mock in blocked))


if __name__ == "__main__":
    import os
    import sys
    import tempfile
    from pathlib import Path
    with tempfile.TemporaryDirectory(prefix="cached-plain-") as tmp:
        os.environ.update(MOCK_LLM="1", CLOUD_SYNC="0", DEMO_STUDIO_DATA=tmp, DEMO_STUDIO_GRAPH_DB=str(Path(tmp) / "graph.sqlite"))
        sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
        rows = []
        def check(name, passed):
            rows.append(bool(passed)); print(("PASS " if passed else "FAIL ") + name)
        run(check)
        print(f"Cached plain language: {sum(rows)}/{len(rows)}")
        raise SystemExit(0 if all(rows) else 1)
