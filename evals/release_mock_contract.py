"""One isolated release journey through real APIs/graphs; no provider or network calls.

Provider fixtures are explicit: extracted handbook facts, Coach/Planner/Author
responses, and silent WAVs at the existing 1.9 words/second estimate. Actual
Voice writes/content hashes, WAV measurement, citation checks, six approvals,
publication minimum, runtime cache, review and session persistence stay active.
This is plumbing evidence, not a claim about model or real speech quality.
"""
from __future__ import annotations

import copy
import json
import os
from pathlib import Path
import socket
import sys
import tempfile
import time
from urllib.parse import urlsplit
from unittest.mock import patch


def browser_visit(client, did, question, check):
    """Real app/modules with every HTTP request fulfilled by the in-process API.

    No listening server or device is used. A deliberately failed fake
    WebSocket exercises the product's typed HTTP fallback. Muted review uses the
    real recorded fixture clips; it makes no acoustic-quality assertion.
    """
    from playwright.sync_api import sync_playwright
    from server.crawl import _render_executable
    requests, rejected, errors = [], [], []
    with sync_playwright() as pw:
        browser = pw.chromium.launch(executable_path=_render_executable(pw.chromium), chromium_sandbox=True,
                                     headless=True, args=["--mute-audio", "--disable-background-networking"])
        context = browser.new_context(viewport={"width": 1440, "height": 1000}, reduced_motion="reduce")
        context.add_init_script("""window.micAttempts=0;Object.defineProperty(navigator,'mediaDevices',{value:{getUserMedia(){window.micAttempts++;return Promise.reject(Error('Devices forbidden'));}}});window.WebSocket=class {constructor(){this.readyState=0;setTimeout(()=>this.onerror?.({}),0)}close(){this.readyState=3;this.onclose?.({})}send(){}};""")
        def route(request_route):
            request = request_route.request
            target = urlsplit(request.url)
            if target.hostname in {"fonts.googleapis.com", "fonts.gstatic.com"}:
                request_route.fulfill(status=200, content_type="text/css", body="")
                return
            if target.hostname != "release.invalid":
                rejected.append(request.url); request_route.abort(); return
            path = target.path + ("?" + target.query if target.query else "")
            requests.append((request.method, path, request.post_data))
            response = client.request(request.method, path, content=request.post_data_buffer,
                                      headers={"content-type": request.headers.get("content-type", "application/json")})
            request_route.fulfill(status=response.status_code, content_type=response.headers.get("content-type", "text/plain"), body=response.content)
        context.route("**/*", route)
        page = context.new_page()
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto(f"http://release.invalid/?mute=1#/play/{did}")
        page.wait_for_selector(".sample-player .sample-layout")
        check("newly published bundle mounts the actual Marine app and centered sample renderer", page.locator('.pl[data-visual-theme="marine"] .sample-layout').count() == 1 and page.get_by_role("switch", name="Voice mode").is_checked() is False)
        page.get_by_role("button", name="Browse at my pace", exact=True).click()
        page.locator(".pl-reply input").fill(question)
        page.locator(".pl-reply").evaluate("form=>form.requestSubmit()")
        page.wait_for_function("document.querySelector('.pl-cap .txt')?.textContent.includes('driver seat')", timeout=20000)
        check("typed player question traverses real HTTP runtime fallback and renders cited answer", any(method == "POST" and path.endswith("/run/qa") and question in (body or "") for method, path, body in requests) and bool(page.locator(".pl-cap .cite").inner_text().strip()))
        page.get_by_role("button", name="Stop and see the summary", exact=True).click()
        page.wait_for_selector(".pl-handoff.open")
        page.wait_for_function("document.querySelector('.pl-handoff.open')!==null")
        # Drain pending fetch through Playwright's route dispatcher before checking.
        page.wait_for_timeout(150)
        saves = [json.loads(body) for method, path, body in requests if method == "POST" and path.endswith("/run/session")]
        check("actual player Stop saves its ended text-mode visit and heard transcript", bool(saves) and saves[-1]["ended"] and saves[-1]["input_mode"] == "text" and any(row.get("text") == question for row in saves[-1]["transcript"]))
        check("browser journey uses no microphone, external HTTP or unhandled exception", page.evaluate("window.micAttempts") == 0 and not rejected and not errors)
        context.close(); browser.close()


def run():
    from fastapi.testclient import TestClient
    from server import config, graph, schemas, store
    from server.agents import coach, faq, narration
    from server.app import app
    from server.llm import mock, sarvam
    from minimum_narration_contract import rich_fixture

    rows = []
    def check(label, value):
        rows.append(bool(value))
        print(("PASS " if value else "FAIL ") + label, flush=True)
        assert value, label

    # Reuse distinct cited paragraphs; this scratch demo is never the journey's
    # demo and no generated artifact is copied into the actual journey's store.
    template_id = store.new_demo("Release provider fixture template")["id"]
    rich = rich_fixture(template_id)
    texts = [fact["value"] for fact in rich["understanding"]["facts"]]
    original_fake = mock.fake
    fixture_calls = []
    source_id = ""

    def fixture(schema, content=None):
        if schema is schemas.FactsOut:
            fixture_calls.append("facts")
            out = mock.fake_dict(schema)
            out.update(product={"name": "Release handbook car", "category": "car", "summary": "Reviewed handbook controls", "audience": "Everyday drivers"}, unknowns=[],
                       facts=[{"kind": "feature", "claim": f"Handbook {index}: " + text.split(".")[0], "value": text,
                               "source": {"ref": source_id, "quote": text, "locator": f"Section {index}"},
                               "confidence": 1, "truth": "stated", "conditions": ""} for index, text in enumerate(texts)])
            return schema.model_validate(out)
        if schema is schemas.Plan:
            fixture_calls.append("plan")
            out = mock.fake_dict(schema)
            template = out["segments"][2]
            out["segments"] = []
            for index, role in [*[(x, "proof") for x in range(1, 9)], (9, "features"), (10, "establish")]:
                out["segments"].append({**copy.deepcopy(template), "id": f"section-{index}", "role": role,
                    "title": f"Handbook area {index}", "topic": f"area-{index}", "stop_id": f"area-{index}" if role == "proof" else None,
                    "fact_ids": [f"F{index + 1:03d}"], "visual_refs": ["im01"], "usp_ids": []})
            out["ctas"] = [{"id": "contact", "label": "Contact dealer", "kind": "contact", "primary": True}]
            return schema.model_validate(out)
        if schema is schemas.ScriptOut:
            fixture_calls.append("author")
            plan, _ = json.JSONDecoder().raw_decode(content.split("\nPLAN: ", 1)[1])
            def line(index):
                return {"text": texts[index], "fact_ids": [f"F{index + 1:03d}"], "step": "say",
                        "visual": {"kind": "image", "ref": "im01", "focus": ""}, "card": "none"}
            out = {"overview": line(0), "segments": [], "closing": [line(11)],
                   "intake_q1": "Welcome. What would you like to know about these controls?", "intake_q2": ""}
            for segment in plan["segments"]:
                index = int(segment["fact_ids"][0][1:]) - 1
                out["segments"].append({"id": segment["id"], "title": segment["title"], "role": segment["role"],
                    "topic": segment["topic"], "lines": [line(index)], "deeper": [], "checkin": ""})
            return schema.model_validate(out)
        return original_fake(schema, content)

    def coached(und, entry):
        fixture_calls.append("coach")
        stops = [{"id": f"area-{i}", "label": f"Handbook area {i}", "kind": "fundamental" if i <= 3 else "differentiator",
                  "why_here": "Follow the documented controls.", "fact_ids": [f"F{i + 1:03d}"], "picture_ids": [],
                  "must_cover": True, "gaps": []} for i in range(1, 9)]
        return {"category": "car", "category_source": "library", "stops": stops,
                "usps": [{"id": f"usp-{i}", "name": name, "fact_ids": stops[i - 1]["fact_ids"], "stop_id": stops[i - 1]["id"]}
                         for i, name in enumerate(["Explore the seating controls", "Understand the folding backrest", "Locate the storage tray"], 1)],
                "objections": [], "evidence_gaps": [], "notes": "Canned provider response for release plumbing only."}

    def wav_fixture(text, *args, **kwargs):
        return mock.silent_wav(max(.6, len(text.split()) / 1.9)), "wav"

    client = TestClient(app)
    def state():
        response = client.get(f"/api/demos/{did}")
        assert response.status_code == 200, response.text
        return response.json()
    def wait_status(wanted, timeout=90):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            current = state()
            if current["demo"]["status"] == wanted and not graph.is_running(did):
                return current
            assert current["demo"]["status"] != "error", json.dumps(current["demo"]["stages"])
            time.sleep(.05)
        raise AssertionError(f"Timed out waiting for {wanted}")
    def post(path, body=None):
        response = client.post(f"/api/demos/{did}/{path}", json=body)
        assert response.status_code == 200, response.text
        return response.json()

    with patch.object(mock, "fake", side_effect=fixture), patch.object(coach, "mock_playbook", side_effect=coached), patch.object(sarvam, "tts", side_effect=wav_fixture):
        response = client.post("/api/demos", json={"name": "Release dry run"})
        did = response.json()["id"]
        check("new demo has exactly six review cards and no publication", response.status_code == 200 and len(state()["demo"]["approvals"]) == 6 and not store.read_json(did, "bundle.json"))
        response = client.post(f"/api/demos/{did}/sources", data={"role": "product", "text_name": "handbook.txt", "text": "\n\n".join(texts)})
        source_id = response.json()["added"][0]["id"]
        image = next((Path(__file__).resolve().parents[1] / "samples/iqube").glob("*.webp"))
        response = client.post(f"/api/demos/{did}/sources", files=[("files", (image.name, image.read_bytes(), "image/webp"))], data={"role": "product"})
        check("text and real local image upload through source API", response.status_code == 200 and len(state()["demo"]["sources"]) == 2)
        post("read")
        aligned = wait_status("align")
        check("Read traverses extraction, Coach, Plan, Author and Deck into Align", all(key in fixture_calls for key in ("facts", "coach", "plan", "author")) and all(aligned["demo"]["stages"][key]["status"] == "done" for key in ("understand", "coach", "plan", "author", "deck", "faq")))
        check("source citations survive actual extraction and reconciliation", len(aligned["cards"]["facts"]["facts"]) == len(texts) and all(f["source"]["ref"] == source_id for f in store.read_json(did, "understanding.json")["facts"]))
        check("empty Asked and answered is auto-approved without invented FAQs or rehearsal", aligned["cards"]["faq"]["total"] == 0 and aligned["demo"]["approvals"]["faq"] and aligned["rehearsal"] is None)
        for card in aligned["demo"]["approvals"]:
            post("approve/" + card)
        check("all six Align approvals are explicit before Build", all(state()["demo"]["approvals"].values()))
        post("build")
        built = wait_status("ready")
        published = client.get(f"/api/demos/{did}/bundle").json()
        minimum = published["runtime"]["narration_minimum"]
        check("real Build/Voice/Bundle passes unchanged measured publication minimum", minimum["sufficient"] and minimum["measured"] and minimum["seconds"] >= 180 and minimum["basis"] == "measured")
        check("publication creates immutable evidence snapshot and default Marine player payload", published["knowledge_snapshot_id"].startswith("kb_") and published["visual_theme"] == "marine" and published["slides"] and published["runtime"]["version"] == 1)
        audio = next(line["audio"] for slide in published["slides"] for line in slide.get("lines", []) if line.get("audio"))
        response = client.get(audio)
        check("recorded content-hash WAV is served through actual media route", response.status_code == 200 and response.content.startswith(b"RIFF") and "audio/" in audio)
        check("Build never runs rehearsal", built["rehearsal"] is None)
        pitch = post("run/pitch", {"runtime_version": 1, "session_id": "release-visit", "turn_id": "explore",
                                    "snapshot_id": published["knowledge_snapshot_id"], "profile": {}, "voice_it": False})
        check("default player route keeps measured minimum and extends beyond three proofs", pitch["narration_minimum"]["sufficient"] and len(pitch["route"]) > 5)

        sid = "release-visit"
        base = {"runtime_version": 1, "session_id": sid, "input_mode": "text", "voice_it": True,
                "snapshot_id": published["knowledge_snapshot_id"], "profile": {}, "history": []}
        question = "What does the driver seat handbook describe?"
        first = post("run/qa", {**base, "turn_id": "first", "question": question})
        check("runtime answers from pinned approved evidence and learns customer answer", first["answered"] and first["fact_ids"] and not first["from_bank"] and first.get("faq_entry_id"))
        bank_id = first["faq_entry_id"]
        from server import runtime_graph
        with patch.object(runtime_graph.graph, "ainvoke", side_effect=AssertionError("Cache hit must bypass reasoning")):
            repeated = post("run/qa", {**base, "turn_id": "repeat", "question": question})
        bank = store.read_json(did, "faq.json")
        entry = next(row for row in bank["entries"] if row["id"] == bank_id)
        check("repeated question uses validated cache before graph reasoning and increments count", repeated["from_bank"] and repeated["answer"] == first["answer"] and entry["asked_count"] == 2)
        check("cached exact wording keeps the same recorded audio", repeated["audio"] == first["audio"] and bool(repeated["audio"]))
        unknown_question = "What is the battery warranty? Do not search online."
        from server.runtime_state import TurnDecision
        decline = TurnDecision(action="answer", answered=False, sentences=[{
            "text": "I couldn't verify the battery warranty.", "kind": "limitation"}])
        with patch.object(runtime_graph, "_mock_decision", return_value=decline):
            unknown = post("run/qa", {**base, "turn_id": "unknown", "question": unknown_question})
        gaps = store.read_json(did, "understanding.json")["unknowns"]
        check("unsupported question declines and learns a customer evidence gap", not unknown["answered"] and not unknown["fact_ids"] and unknown["offer_callback"] and any(row.get("source") == "customer" and row["question"] == unknown_question for row in gaps))
        check("new answer and unknown require human FAQ review without changing publication", not state()["demo"]["approvals"]["faq"] and client.get(f"/api/demos/{did}/bundle").json() == published)
        approved = client.patch(f"/api/demos/{did}/align/faq/{bank_id}", json={"action": "approve"})
        check("reviewer can approve learned answer", approved.status_code == 200 and next(row for row in store.read_json(did, "faq.json")["entries"] if row["id"] == bank_id)["reviewed"])
        revised = "The driver seat has a sliding base and an adjustable backrest."
        edited = client.patch(f"/api/demos/{did}/align/faq/{bank_id}", json={"answer": revised, "fact_ids": first["fact_ids"]})
        saved = next(row for row in store.read_json(did, "faq.json")["entries"] if row["id"] == bank_id)
        check("reviewed FAQ edit preserves exact words and invalidates previous audio", edited.status_code == 200 and saved["answer"] == revised and saved["audio"] is None and not state()["demo"]["approvals"]["faq"])
        rejected = client.patch(f"/api/demos/{did}/align/faq/{bank_id}", json={"action": "reject"})
        check("rejected FAQ persists as tombstone and cannot match", rejected.status_code == 200 and next(row for row in store.read_json(did, "faq.json")["entries"] if row["id"] == bank_id)["rejected"] and faq.match(did, question) is None)

        before = state()["demo"]
        post("rehearsal")
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            after = state()
            if after["demo"]["stages"]["rehearsal"]["status"] == "done" and not graph.is_running(did):
                break
            assert after["demo"]["stages"]["rehearsal"]["status"] != "error", after
            time.sleep(.05)
        check("on-demand rehearsal creates scorecard while keeping publication and approvals", bool(after["rehearsal"]["scorecard"]) and after["demo"]["approvals"] == before["approvals"] and client.get(f"/api/demos/{did}/bundle").json() == published)
        transcript = [{"role": "user", "text": question}, {"role": "agent", "text": first["answer"]}, {"role": "user", "text": unknown_question}, {"role": "agent", "text": unknown["answer"]}]
        session = {"id": sid, "ended": True, "input_mode": "text", "profile": {}, "transcript": transcript,
                   "questions": [question, unknown_question], "turns": [], "snapshot_id": published["knowledge_snapshot_id"]}
        receipt = post("run/session", session)
        post("run/session", session)
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            saved = client.get(f"/api/demos/{did}/sessions/{sid}").json()
            if saved.get("summary"):
                break
            time.sleep(.05)
        sessions = client.get(f"/api/demos/{did}/sessions").json()["sessions"]
        check("session final save is idempotent and summary follows actual transcript", len([s for s in sessions if s["id"] == sid]) == 1 and saved["transcript"] == transcript and saved["input_mode"] == "text" and saved.get("summary"))
        shared = client.get(f"/api/share/{did}/{sid}", params={"k": receipt["share_key"]})
        check("share link exposes summary with no full transcript and rejects wrong key", shared.status_code == 200 and "transcript" not in shared.json() and client.get(f"/api/share/{did}/{sid}", params={"k": "wrong"}).status_code == 403)
        trace = client.get(f"/api/demos/{did}/trace").json()
        check("stage and runtime traces are retained for diagnosis", "rows" in trace and all(trace["stages"][name]["status"] == "done" for name in ("understand", "coach", "plan", "author", "deck")))
        browser_visit(client, did, question, check)
        print("FIXTURES: canned provider responses; silent WAV files measured by real publication gate; no duration bypass", flush=True)
        print(f"RELEASE JOURNEY: {sum(rows)}/{len(rows)} passed; narration={minimum['seconds']}s measured; provider calls=0", flush=True)


if __name__ == "__main__":
    with tempfile.TemporaryDirectory(prefix="release-mock-") as temp:
        os.environ.update(MOCK_LLM="1", CLOUD_SYNC="0", STORAGE_BACKEND="local",
                          DEMO_STUDIO_DATA=str(Path(temp) / "demos"), DEMO_STUDIO_GRAPH_DB=str(Path(temp) / "graph.sqlite"))
        sys.path[:0] = [str(Path(__file__).resolve().parents[1]), str(Path(__file__).resolve().parent)]
        attempts = []
        def blocked(*args, **kwargs):
            attempts.append(True)
            raise AssertionError("Release contract must not open outbound sockets")
        with patch.object(socket.socket, "connect", side_effect=blocked), patch.object(socket.socket, "connect_ex", side_effect=blocked), patch.object(socket, "create_connection", side_effect=blocked):
            try:
                run()
            finally:
                print("OUTBOUND_ATTEMPTS", len(attempts), flush=True)
                assert not attempts
