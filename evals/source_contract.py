"""Free source-isolation and competitor-evidence contracts. No outbound calls."""
from __future__ import annotations

import copy
import sys
import tempfile
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch


def _pdf(text: str) -> bytes:
    """Tiny real text PDF, so the contract exercises the existing PDF extractor."""
    stream = f"BT /F1 12 Tf 24 700 Td ({text}) Tj ET".encode()
    objects = [b"<< /Type /Catalog /Pages 2 0 R >>", b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
               b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>",
               b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
               b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"]
    out = bytearray(b"%PDF-1.4\n"); offsets = [0]
    for i, obj in enumerate(objects, 1):
        offsets.append(len(out)); out.extend(f"{i} 0 obj\n".encode() + obj + b"\nendobj\n")
    xref = len(out)
    out.extend(f"xref\n0 {len(objects)+1}\n0000000000 65535 f \n".encode())
    out.extend(b"".join(f"{offset:010d} 00000 n \n".encode() for offset in offsets[1:]))
    out.extend(f"trailer\n<< /Root 1 0 R /Size {len(objects)+1} >>\nstartxref\n{xref}\n%%EOF\n".encode())
    return bytes(out)


def run(check, _demo_id: str | None = None) -> None:
    from fastapi.testclient import TestClient
    from server import config, media, schemas, sources, store
    from server.agents import faq, qa, understand, visuals, voice
    from server.app import app

    with tempfile.TemporaryDirectory(prefix="source-contract-") as tmp, ExitStack() as stack:
        stack.enter_context(patch.multiple(config, MOCK_LLM=True, DATA_DIR=Path(tmp)))
        network = [stack.enter_context(patch(name, side_effect=AssertionError("Unexpected outbound call")))
                   for name in ("socket.create_connection", "socket.socket.connect", "socket.socket.connect_ex")]
        stack.enter_context(patch.object(media, "enhance_images"))
        stack.enter_context(patch.object(visuals, "build_map", return_value={}))
        stack.enter_context(patch.object(visuals, "for_facts", return_value=None))
        model_clients = [stack.enter_context(patch(name, side_effect=AssertionError("Unexpected provider call")))
                         for name in ("server.llm.gemini.client", "server.llm.runware._post", "server.llm.claude._client_opts")]
        demo = store.new_demo("Product fixture"); did = demo["id"]
        product = store.add_text_source(did, "product", "PRODUCT-ONLY: LED lamp.", "product")
        pdf = store.add_file_source(did, "rival.pdf", _pdf("RIVAL-PDF: six speeds on 2026 VX petrol automatic only."), "competitor")
        text = store.add_text_source(did, "rival-feature-table", "RIVAL-TEXT: six airbags on HX8 only; other trims unknown.", "competitor")
        url = store.add_url_source(did, "https://example.com/rival", "competitor")
        store.update(did, lambda d: d["settings"].update(competition="on"))
        api = TestClient(app)
        origins = {pdf["id"]: "https://example.com/official/rival.pdf", text["id"]: "https://example.com/official/features"}
        for src in (pdf, text):
            response = api.patch(f"/api/demos/{did}/sources/{src['id']}", json={"url": origins[src["id"]]})
            saved = next(x for x in store.load(did)["sources"] if x["id"] == src["id"])
            check(f"sources: {src['kind']} upload keeps official URL without becoming a URL source",
                  response.status_code == 200 and saved["url"] == origins[src["id"]]
                  and saved["kind"] == src["kind"] and saved["path"] == src["path"] and saved["role"] == "competitor")
        before = store.path(did, "demo.json").read_bytes()
        for bad in ("javascript:alert(1)", "file:///tmp/source", "/relative", "https://", "https://user:secret@example.com/file", "https://example.com:99999/file", "https://example.com/bad path", None):
            response = api.patch(f"/api/demos/{did}/sources/{pdf['id']}", json={"url": bad, "name": "must-not-be-saved"})
            check(f"sources: invalid URL {str(bad).split(':')[0]} returns 400 without partial mutation",
                  response.status_code == 400 and store.path(did, "demo.json").read_bytes() == before)

        calls = []
        def fact(ref, claim, value, conditions="", locator="", quote=""):
            return schemas.FactOut(kind="spec", claim=claim, value=value, conditions=conditions, confidence=1,
                                   source=schemas.FactSource(ref=ref, locator=locator, quote=quote), truth="stated")
        def model(system, content, schema, **_kwargs):
            calls.append((schema, copy.deepcopy(content)))
            if schema is schemas.FactsOut:
                return schemas.FactsOut(product=schemas.Product(name="Product fixture", category="Car", summary="Source fixture.", audience="Buyers"),
                                        facts=[fact(product["id"], "Lamp", "LED", quote="LED lamp")], unknowns=[],
                                        brand=schemas.Brand(tone="Direct", voice_style="Calm", dos=[], donts=[], persona_hint="Fixture"))
            assert schema is schemas.CompetitorsOut
            if "RIVAL-PDF" in content:
                name, claim, value, condition, locator, quote = "Rival PDF", "VX transmission", "6 speeds", "2026 VX petrol automatic only", "page 1", "six speeds on 2026 VX petrol automatic only"
            elif "RIVAL-TEXT" in content:
                name, claim, value, condition, locator, quote = "Rival Text", "Airbags", "6", "HX8 only; other trims unknown", "feature matrix row 1", "six airbags on HX8 only"
            else:
                assert "RIVAL-URL" in content
                name, claim, value, condition, locator, quote = "Rival URL", "Seats", "5", "India specification", "seating", "five seats"
            return schemas.CompetitorsOut(competitors=[schemas.CompetitorOut(name=name, facts=[fact("wrong-source-id", claim, value, condition, locator, quote)])])

        with patch.object(understand.claude, "structured", side_effect=model), \
                patch.object(sources, "fetch_url", return_value={"title": "Rival", "text": "RIVAL-URL: five seats.", "error":None, "images":[]}) as fetched:
            und = understand.run(did, lambda _message: None)
        product_content = repr(next(content for schema, content in calls if schema is schemas.FactsOut))
        check("sources: competitor PDF/text/URL content never enters product extraction",
              "PRODUCT-ONLY" in product_content and "RIVAL-" not in product_content and "rival.pdf" not in product_content
              and [x["source"]["ref"] for x in und["facts"]] == [product["id"]])
        check("sources: PDF, text and URL each reach the separate competitor extractor",
              len(und["competitors"]) == 3 and len([1 for schema, _ in calls if schema is schemas.CompetitorsOut]) == 3)
        check("sources: uploaded origin metadata is not fetched instead of the uploaded document",
              fetched.call_count == 1 and fetched.call_args.args[0] == url["url"])
        pdf_prompt = next(content for schema, content in calls if schema is schemas.CompetitorsOut and "RIVAL-PDF" in content)
        check("sources: real PDF text keeps page markers, source id and official origin URL",
              "[page 1]" in pdf_prompt and pdf["id"] in pdf_prompt and origins[pdf["id"]] in pdf_prompt)
        by_source = {c["source_id"]:c for c in und["competitors"]}
        check("sources: extracted competitor citations are bound to the actual supplied source",
              all(f["source"]["ref"] == c["source_id"] for c in und["competitors"] for f in c["facts"]))
        check("sources: competitor source URL, quote, locator and variant conditions survive storage",
              by_source[pdf["id"]]["url"] == origins[pdf["id"]]
              and by_source[pdf["id"]]["facts"][0]["conditions"] == "2026 VX petrol automatic only"
              and by_source[pdf["id"]]["facts"][0]["source"]["locator"] == "page 1"
              and by_source[pdf["id"]]["facts"][0]["source"]["quote"] == "six speeds on 2026 VX petrol automatic only")

        approved = by_source[pdf["id"]]["facts"][0]
        rejected = by_source[text["id"]]["facts"][0]
        rejected["approved"] = False
        store.write_json(did, "understanding.json", und)
        store.write_json(did, "plan.json", {"voice":{},"segments":[],"ctas":[]})
        system, _, _ = qa._system(did, None)
        check("sources: runtime receives competitor variant condition, origin, exact quote and locator",
              all(value in system for value in ("2026 VX petrol automatic only", origins[pdf["id"]], "page 1", "six speeds on 2026 VX petrol automatic only", "checked:", "stated")))
        check("sources: rejected competitor facts are absent from the model prompt", rejected["id"] not in system and "HX8 only" not in system)
        answer = schemas.QAOut(answer="The VX petrol automatic has 6 speeds.", fact_ids=[approved["id"]], answered=True)
        with patch.object(qa.runtime, "structured", return_value=answer):
            result = qa.answer(did, "What transmission does this rival variant use?", live=True, voice_it=False)
        check("sources: an approved competitor fact can ground a runtime answer",
              result["answered"] and result["fact_ids"] == [approved["id"]] and result["facts"][0]["source"]["ref"] == pdf["id"])
        for ids in ([rejected["id"]], [approved["id"], rejected["id"]]):
            answer = schemas.QAOut(answer="The rival has 6 airbags.", fact_ids=ids, answered=True)
            with patch.object(qa.runtime, "structured", return_value=answer):
                result = qa.answer(did, "Does that trim have airbags?", live=True, voice_it=False)
            check("sources: rejected competitor citation declines even alongside a valid citation",
                  not result["answered"] and not result["fact_ids"] and not result["facts"] and result["offer_callback"])
        for label, ids in (("rejected", [rejected["id"]]), ("uncited", [])):
            claim = "The rival has 6 airbags." if ids else "The on-road price is Rs 500000."
            unsafe_action = schemas.QAOut(answer=claim + " Let's book it.", fact_ids=ids,
                                         answered=True, cta="book")
            with patch.object(qa.runtime, "structured", return_value=unsafe_action), \
                    patch.object(voice, "render_line", return_value=None) as speech:
                result = qa.answer(did, "Can I book the rival with those airbags?", live=True, voice_it=True)
            check(f"sources: a CTA cannot preserve or speak a {label} competitor claim",
                  not result["answered"] and not result["cta"] and not result["fact_ids"] and not result["facts"]
                  and result["offer_callback"] and result["answer"] == qa.DONT_GUESS
                  and speech.call_count == 1 and speech.call_args.args[1] == qa.DONT_GUESS)

        equipment_source = store.add_text_source(did, "equipment-fixture", "6 airbags. 5-star test rating. 7 seats.", "product")
        for index, claim in enumerate(("It has 6airbags.", "It has a 5-star test rating.", "It has 7 seats."), 1):
            fid = f"F90{index}"
            und["facts"].append({**fact(equipment_source["id"], "Fixture equipment", claim, quote=claim).model_dump(), "id":fid, "approved":True})
            store.write_json(did, "understanding.json", und)
            for cited in (False, True):
                proposed = schemas.QAOut(answer=claim, answered=True, fact_ids=[fid] if cited else [])
                with patch.object(qa.runtime, "structured", return_value=proposed):
                    result = qa.answer(did, "What equipment does the fixture have?", live=True, voice_it=False)
                check(f"sources: single-digit equipment count {index} {'survives with evidence' if cited else 'declines without evidence'}",
                      result["answered"] == cited and (result["answer"] == claim if cited else result["answer"] == qa.DONT_GUESS))
        proposed = schemas.QAOut(answer="It has 6 airbags. Let's book it.", answered=True, fact_ids=[], cta="book")
        with patch.object(qa.runtime, "structured", return_value=proposed), \
                patch.object(voice, "render_line", return_value=None) as speech:
            result = qa.answer(did, "Can I book the car with those airbags?", live=True, voice_it=True)
        check("sources: uncited single-digit equipment plus CTA declines before speech",
              not result["answered"] and not result["cta"] and result["answer"] == qa.DONT_GUESS
              and result["offer_callback"] and speech.call_args.args[1] == qa.DONT_GUESS)
        proposed = schemas.QAOut(answer="You can choose option 6.", answered=True, fact_ids=[])
        with patch.object(qa.runtime, "structured", return_value=proposed):
            result = qa.answer(did, "Which option can I select?", live=True, voice_it=False)
        check("sources: equipment-count guard does not classify every single digit as a product claim",
              result["answered"] and result["answer"] == proposed.answer)

        rejected_hash = faq._registry_hash(did)
        rejected["approved"] = True; store.write_json(did, "understanding.json", und)
        approved_hash = faq._registry_hash(did)
        rejected["approved"] = False; store.write_json(did, "understanding.json", und)
        check("sources: competitor approval changes invalidate the FAQ build cache", approved_hash != rejected_hash)
        bank_question = "Does the rival automatic have six speeds?"
        bank = {"id":"Q1", "question":bank_question, "answer":"The rival automatic has 6 speeds.", "fact_ids":[approved["id"]],
                "answered":True, "audio":"old-bank.wav"}
        store.write_json(did, "faq.json", {"entries":[bank]})
        with patch.object(qa, "answer") as live:
            result = api.post(f"/api/demos/{did}/run/qa", json={"question":bank_question}).json()
        check("sources: an approved competitor FAQ remains an immediate bank response",
              result.get("from_bank") and result["fact_ids"] == [approved["id"]] and not live.called)
        decline = {"answer":qa.DONT_GUESS, "answered":False, "fact_ids":[], "facts":[], "offer_callback":True,
                   "audio":None, "visual":None, "escalate":bank_question, "topic":"comparison", "cta":"", "clarifying_question":""}
        for ids in ([rejected["id"]], [approved["id"], rejected["id"]]):
            store.write_json(did, "faq.json", {"entries":[{**bank, "fact_ids":ids}]})
            with patch.object(qa, "answer", return_value=copy.deepcopy(decline)) as live:
                response = api.post(f"/api/demos/{did}/run/qa", json={"question":bank_question})
            result = response.json()
            check("sources: stale FAQ audio citing a rejected competitor cannot bypass runtime approval",
                  response.status_code == 200 and not result["from_bank"] and not result["answered"]
                  and not result["audio"] and not result["fact_ids"] and live.call_count == 1)
        store.write_json(did, "faq.json", {"entries":[bank]})
        store.update(did, lambda d: d["settings"].update(competition="off"))
        check("sources: disabling comparison invalidates the FAQ build cache", faq._registry_hash(did) != rejected_hash)
        with patch.object(qa, "answer", return_value=copy.deepcopy(decline)) as live:
            result = api.post(f"/api/demos/{did}/run/qa", json={"question":bank_question}).json()
        check("sources: comparison-off blocks an otherwise approved competitor bank answer",
              not result["from_bank"] and not result["answered"] and live.call_count == 1)
        system, _, _ = qa._system(did, None)
        answer = schemas.QAOut(answer="The VX petrol automatic has 6 speeds.", fact_ids=[approved["id"]], answered=True)
        with patch.object(qa.runtime, "structured", return_value=answer):
            result = qa.answer(did, "Compare the rival automatic.", live=True, voice_it=False)
        check("sources: disabling comparison removes rival context and invalidates its citations",
              approved["id"] not in system and not result["answered"] and not result["fact_ids"])
        check("sources: all source contracts avoid provider and outbound network calls",
              not any(mock.called for mock in network + model_clients))


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    rows = []
    def check(name, ok, detail=""):
        rows.append(bool(ok)); print(("PASS " if ok else "FAIL ") + name + (" — " + detail if detail else ""))
    run(check)
    print(f"Source contracts: {sum(rows)}/{len(rows)}")
    raise SystemExit(0 if all(rows) else 1)
