"""WP6 FAQ cache, legacy QA and narration warnings; isolated and socket-blocked."""
from __future__ import annotations

import copy
import os
import sys
import tempfile
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch


def run(check):
    from server import schemas, store
    from server.agents import author, faq, plain_terms, qa, rehearsal, voice

    did = store.new_demo("Everyday answer fixture")["id"]
    store.update(did, lambda demo: demo["settings"].update(audience="everyday", faq_questions=3))
    raw = "Selected variants use McPherson strut with coupled torsion beam axle."
    clean = "Selected variants use strut-type front suspension with a simple rear suspension setup."
    facts = [{"id": "F1", "kind": "spec", "claim": "Suspension", "value": "McPherson strut and coupled torsion beam axle",
              "approved": True, "conditions": "Selected variants only", "source": {"ref": "fixture", "quote": raw}}]
    und = {"product": {"name": "Fixture", "category": "Car"}, "facts": facts, "images": [], "shots": [], "unknowns": []}
    store.write_json(did, "understanding.json", und)
    store.write_json(did, "plan.json", {"voice": {}, "segments": [], "ctas": []})
    questions = ["Tell me about the suspension?", "What exact type of suspension is fitted?", "Which everyday controls are offered?"]
    allowed = "The turbo petrol has an automatic gearbox, airbags and cruise control."
    responses = {questions[0]: raw, questions[1]: raw, questions[2]: allowed}
    with ExitStack() as stack:
        sockets = [stack.enter_context(patch(name, side_effect=AssertionError("No outbound calls")))
                   for name in ("socket.create_connection", "socket.socket.connect", "socket.socket.connect_ex")]
        stack.enter_context(patch.object(faq, "doc_questions", return_value=questions))
        generated = stack.enter_context(patch.object(rehearsal, "generate_questions", side_effect=AssertionError("No generated questions needed")))
        def draft(_did, question, *args, **kwargs):
            return {"answer": responses[question], "fact_ids": ["F1"], "answered": True, "visual": None}
        with patch.object(qa, "answer", side_effect=draft) as model:
            bank = faq.run(did, lambda _: None)
        first = bank["entries"][0]
        check("new everyday FAQ text receives reviewed substitutions", first["answer"] == clean)
        check("FAQ substitutions preserve qualifiers and exact citations", first["answer"].startswith("Selected variants") and first["fact_ids"] == ["F1"] and first["answered"])
        check("FAQ records both longest-phrase substitutions", [pair[0] for pair in first["plain_language_substitutions"]] == ["mcpherson strut", "coupled torsion beam axle"])
        natural = faq.normalize_entry({"question": questions[0], "answer": "It has McPherson strut suspension and a coupled torsion beam axle.", "fact_ids": ["F1"], "audio": "audio/old.wav"}, "everyday")
        check("FAQ substitution avoids repeated suspension and article at phrase boundaries", natural["answer"] == "It has strut-type front suspension and a simple rear suspension setup." and natural["fact_ids"] == ["F1"] and natural["audio"] is None)
        check("technical FAQ question preserves exact cited terms", bank["entries"][1]["answer"] == raw and not bank["entries"][1]["plain_language_substitutions"])
        check("allowed everyday vocabulary stays untouched", bank["entries"][2]["answer"] == allowed and not bank["entries"][2]["plain_language_substitutions"])

        # Simulate an older successful bank whose recorded audio still says the jargon.
        bank["entries"][0].update(answer=raw, audio="audio/old.wav", plain_language_substitutions=[])
        bank["entries"][1]["audio"] = "audio/technical.wav"
        store.write_json(did, "faq.json", bank)
        with patch.object(qa, "answer", side_effect=AssertionError("Cache hit must not call a model")) as reused:
            normalized = faq.run(did, lambda _: None)
        check("unchanged-registry cache is normalized without new answers", not reused.called and not generated.called and normalized["entries"][0]["answer"] == clean)
        check("changed cached text invalidates old audio but unchanged technical text retains it", normalized["entries"][0]["audio"] is None and normalized["entries"][1]["audio"] == "audio/technical.wav")
        normalized["entries"][0]["audio"] = "audio/plain.wav"
        store.write_json(did, "faq.json", normalized)
        saved_normalized = store.read_json(did, "faq.json")
        with patch.object(qa, "answer", side_effect=AssertionError("Cache hit must not call a model")):
            repeated = faq.run(did, lambda _: None)
        check("already-normalized cache preserves audio and substitution history", repeated["entries"][0] == saved_normalized["entries"][0])

        technical_entry = {"question": questions[1], "answer": raw, "fact_ids": ["F1"], "audio": "audio/technical.wav"}
        actual = faq.normalize_entry(technical_entry, "everyday", question=questions[0])
        check("incoming everyday question overrides technical bank exception without mutating bank", actual["answer"] == clean and actual["audio"] is None and technical_entry["answer"] == raw and technical_entry["audio"] == "audio/technical.wav")
        check("incoming explicit technical question preserves bank text and audio", faq.normalize_entry(technical_entry, "everyday", question=questions[1]) == technical_entry)
        store.update(did, lambda demo: demo["settings"].update(audience="expert"))
        with patch.object(qa, "answer", side_effect=draft):
            expert = faq.run(did, lambda _: None, force=True)
        check("expert FAQ build bypasses substitution", expert["entries"][0]["answer"] == raw and not expert["entries"][0]["plain_language_substitutions"])
        expert["entries"][0]["audio"] = "audio/expert.wav"
        store.write_json(did, "faq.json", expert)
        with patch.object(qa, "answer", side_effect=AssertionError("Cache hit must not call a model")):
            expert_cached = faq.run(did, lambda _: None)
        check("expert cached answer and audio remain unchanged", expert_cached["entries"][0] == expert["entries"][0])

        # Exercise the real legacy answer boundary, including text handed to voice.
        store.update(did, lambda demo: demo["settings"].update(audience="everyday"))
        proposal = schemas.QAOut(answer=raw, fact_ids=["F1"], answered=True)
        with patch.object(qa.claude, "structured", return_value=proposal), patch.object(voice, "render_line", return_value="audio/new.wav") as rendered:
            result = qa.answer(did, questions[0])
        check("legacy QA substitutes only grounded text before voice", result["answer"] == clean and result["fact_ids"] == ["F1"] and rendered.call_args.args[1] == clean and len(result["plain_language_substitutions"]) == 2)
        with patch.object(qa.claude, "structured", return_value=proposal):
            technical = qa.answer(did, questions[1], voice_it=False)
        check("legacy explicit technical QA keeps exact sourced terms", technical["answer"] == raw and technical["fact_ids"] == ["F1"] and not technical["plain_language_substitutions"])
        store.update(did, lambda demo: demo["settings"].update(audience="expert"))
        with patch.object(qa.claude, "structured", return_value=proposal):
            expert_qa = qa.answer(did, questions[0], voice_it=False)
        check("legacy expert QA bypasses substitution", expert_qa["answer"] == raw and not expert_qa["plain_language_substitutions"])
        store.update(did, lambda demo: demo["settings"].update(audience="everyday"))
        with patch.object(qa.claude, "structured", return_value=schemas.QAOut(answer=raw, fact_ids=["invented"], answered=True)):
            rejected = qa.answer(did, questions[0], voice_it=False)
        check("language cleanup cannot rescue unsupported citations", rejected["answer"] == qa.DONT_GUESS and rejected["fact_ids"] == [] and not rejected["plain_language_substitutions"])

        script = {"segments": [{"id": "s1", "role": "proof", "title": "Suspension", "topic": "suspension",
                                "lines": [{"text": "Selected variants use mcpherson strut suspension.", "fact_ids": ["F1"], "visual": {"kind": "none"}}],
                                "deeper": [], "checkin": ""}], "closing": []}
        issues = author.validate(script, und)
        check("new Author blocklist warns case-insensitively without suppressing cited narration", any("jargon 'mcpherson strut'" in issue for issue in issues) and not script["segments"][0]["lines"][0]["unverified"])
        check("every blocklist key and previous engineering patterns remain Author warnings", all(author.JARGON.search(term.swapcase()) for term in plain_terms.JARGON) and all(author.JARGON.search(term) for term in ["kWh", "Nm", "ABS", "torque", "4330 mm", "four-cylinder"]))
        technical_script = copy.deepcopy(script)
        check("expert narration preserves existing warning bypass", not any("register warning" in issue for issue in author.validate(technical_script, und, "expert")))
        check("no outbound sockets", not any(mock.called for mock in sockets))


if __name__ == "__main__":
    with tempfile.TemporaryDirectory(prefix="faq-plain-") as tmp:
        os.environ.update(MOCK_LLM="1", CLOUD_SYNC="0", DEMO_STUDIO_DATA=tmp, DEMO_STUDIO_GRAPH_DB=str(Path(tmp) / "graph.sqlite"))
        sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
        results = []
        def check(name, ok):
            results.append(bool(ok))
            print(("PASS " if ok else "FAIL ") + name)
        run(check)
        print(f"FAQ plain language contracts: {sum(results)}/{len(results)}")
        raise SystemExit(0 if all(results) else 1)
