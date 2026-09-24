"""Incremental session snapshots through the real route; isolated, no providers or sockets."""
from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
import copy
import os
from pathlib import Path
import sys
import tempfile
import threading
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def run(check):
    with tempfile.TemporaryDirectory(prefix="session-checkpoint-") as tmp, ExitStack() as stack:
        stack.enter_context(patch.dict(os.environ, {"MOCK_LLM": "1", "CLOUD_SYNC": "0", "STORAGE_BACKEND": "local",
            "DEMO_STUDIO_DATA": str(Path(tmp) / "demos"), "DEMO_STUDIO_GRAPH_DB": str(Path(tmp) / "graph.sqlite")}))
        import httpx
        from server import app as routes, config, storage, store
        stack.enter_context(patch.object(config, "DATA_DIR", Path(tmp) / "demos"))
        stack.enter_context(patch.object(config, "MOCK_LLM", True))
        backend = storage.Local()
        stack.enter_context(patch.object(storage, "backend", return_value=backend))
        for name in ("socket.create_connection", "socket.getaddrinfo", "socket.socket.connect", "socket.socket.connect_ex", "socket.socket.sendto"):
            stack.enter_context(patch(name, side_effect=AssertionError("Sockets blocked")))
        did = store.new_demo("Incremental session fixture")["id"]
        workers = []
        original_thread = threading.Thread

        class Worker(original_thread):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                if self.name.startswith("summary-"):
                    workers.append(self)

        stack.enter_context(patch.object(routes.threading, "Thread", Worker))

        def request(method, path, body=None):
            async def send():
                async with httpx.AsyncClient(transport=httpx.ASGITransport(app=routes.app), base_url="http://test") as client:
                    return await client.request(method, path, **({"json": body} if body is not None else {}))
            return asyncio.run(send())

        def save(body, status=200):
            response = request("POST", f"/api/demos/{did}/run/session", body)
            assert response.status_code == status, response.text
            return response.json()

        def record(sid, seq=None, text="Buyer asked about the cabin", **changes):
            return {"id": sid, "ended": False, "minutes": 1, "input_mode": "voice",
                    "profile": {"name": "Fixture buyer", "why": "Cabin space"},
                    "questions": [text], "turns": [{"question": text, "via": "voice"}],
                    "transcript": [{"role": "user", "text": text}],
                    **({"save_seq": seq} if seq is not None else {}), **changes}

        def stored(sid):
            return backend.get_session(did, sid)

        def drain():
            for worker in workers:
                worker.join(3)
            assert all(not worker.is_alive() for worker in workers), "fake summary worker did not terminate"

        calls = []

        def summarize(_did, body):
            calls.append(copy.deepcopy(body))
            return {"context": body["transcript"][0]["text"], "transcript_lines": len(body["transcript"]),
                    "generated_at": 1, "leads": copy.deepcopy(body.get("leads", []))}

        with patch.object(routes._summary, "summarize", side_effect=summarize):
            first = save(record("s_ongoing", 1))
            check("first ongoing checkpoint is durable before the session ends", stored("s_ongoing")["transcript"] == record("s_ongoing")["transcript"] and not stored("s_ongoing")["ended"])
            check("ongoing autosaves never start summary work", not workers and not calls)
            check("accepted response acknowledges sequence and stable share identity", first["accepted"] is True and first["save_seq"] == 1 and first["share_key"] == routes._share_key(did, "s_ongoing"))
            latest = record("s_ongoing", 3, text="Later question with more detail", minutes=16)
            save(latest)
            before = copy.deepcopy(stored("s_ongoing"))
            stale = save(record("s_ongoing", 2, text="Short stale fragment"))
            check("late lower checkpoint cannot truncate the sixteen-minute visit", stored("s_ongoing") == before and stale["accepted"] is False and stale["save_seq"] == 3)
            equal = save(record("s_ongoing", 3, text="Different retry words", ended=True))
            check("same sequence retry cannot change words, time or ended state", stored("s_ongoing") == before and equal["accepted"] is False)
            legacy = save(record("s_ongoing", text="Late unsequenced beacon"))
            check("legacy beacon cannot overwrite a session owned by sequenced saves", legacy["accepted"] is False and stored("s_ongoing") == before)
            listed = request("GET", f"/api/demos/{did}/sessions").json()["sessions"]
            check("sales session list already includes ongoing visit and elapsed minutes", any(row["id"] == "s_ongoing" and row["minutes"] == 16 and not row["ended"] for row in listed))
            save(record("s_ongoing", 4, text="Later question with more detail", minutes=16, ended=True))
            drain()
            ended = copy.deepcopy(stored("s_ongoing"))
            save(record("s_ongoing", 3, text="Late ongoing beacon", ended=False))
            check("late ongoing beacon cannot reopen an ended session or remove its summary", stored("s_ongoing") == ended and ended["summary"]["context"] == "Later question with more detail")
            count = len(calls)
            save(record("s_ongoing", 5, text="Later question with more detail", minutes=16, ended=True))
            drain()
            check("higher transport sequence with identical ended content reuses summary", len(calls) == count and stored("s_ongoing")["summary"] == ended["summary"] and stored("s_ongoing")["save_seq"] == 5)
            save(record("s_ongoing", 6, text="Intentional resumed conversation", ended=False))
            check("higher sequence intentionally resumes same visit and drops old summary", stored("s_ongoing")["save_seq"] == 6 and not stored("s_ongoing")["ended"] and "summary" not in stored("s_ongoing"))
            save(record("s_old", text="Legacy first save"))
            save(record("s_old", text="Legacy update"))
            check("legacy-to-legacy saves retain their established behavior", stored("s_old")["transcript"][0]["text"] == "Legacy update" and "save_seq" not in stored("s_old"))
            save(record("s_old", 1, text="New client owns the visit"))
            save(record("s_old", text="Old client arrives late"))
            check("first sequenced checkpoint safely migrates a legacy session", stored("s_old")["save_seq"] == 1 and stored("s_old")["transcript"][0]["text"] == "New client owns the visit")
            bad_before = copy.deepcopy(stored("s_old"))
            for invalid in (True, False, 0, -1, 1.5, 2.0, "3", None, 9007199254740992):
                body = record("s_old", 2)
                body["save_seq"] = invalid
                save(body, 400)
            check("booleans, floats, strings, null and unsafe sequence values are rejected", stored("s_old") == bad_before)
            save(record("s_mode", 1, input_mode="text"))
            mode = record("s_mode", 2)
            mode.pop("input_mode")
            save(mode)
            check("incremental save preserves known input-mode selection when omitted", stored("s_mode")["input_mode"] == "text")
            save(record("s_other", 1))
            check("sequence counters belong to their session, not the whole demo", stored("s_other")["save_seq"] == 1 and stored("s_ongoing")["save_seq"] == 6)
            safe = record("s_private", 1, ended=True,
                          leads=[{"phone": "9876543210", "question": "Please contact me", "consent": True}],
                          summary={"context": "Client-forged summary"})
            response = save(safe)
            drain()
            shared = request("GET", f"/api/share/{did}/s_private?k={response['share_key']}")
            public = shared.json()
            check("checkpoint route still strips client-supplied summaries", stored("s_private")["summary"]["context"] != "Client-forged summary")
            check("sharing keeps transcript private and masks lead phones after checkpoints", shared.status_code == 200 and "transcript" not in public and public["leads"][0]["phone"] == "•••••• 3210" and "9876543210" not in shared.text)
            check("private consent survives exactly in the stored snapshot", stored("s_private")["leads"][0]["consent"] is True)
            check("wrong share key remains forbidden", request("GET", f"/api/share/{did}/s_private?k=wrong").status_code == 403)
            contact = copy.deepcopy(stored("s_private"))
            contact["escalations"] = ['callback requested on 9876543210: "Please call me"']
            contact["questions"] = ["Please contact +91 98765-43210", "Does it seat five?"]
            contact["summary"]["opening_line"] = "Call 98765 43210 about the cabin."
            contact["summary"]["objections"] = [{"text": "Contact 9876543210 after five", "resolved": False}]
            backend.put_session(did, contact)
            private_before = copy.deepcopy(contact)
            public_contact = request("GET", f"/api/share/{did}/s_private?k={response['share_key']}").json()
            check("public callback escalations and questions never expose the full number", public_contact["escalations"][0] == 'callback requested on •••••• 3210: "Please call me"' and public_contact["questions"] == ["Please contact •••••• 3210", "Does it seat five?"])
            check("public model prose and nested objections mask contact numbers too", public_contact["summary"]["opening_line"] == "Call •••••• 3210 about the cabin." and public_contact["summary"]["objections"][0]["text"] == "Contact •••••• 3210 after five")
            check("public contact masking never rewrites the private consented record", stored("s_private") == private_before)

        # Hold an old summary while the visit resumes. Completion must not attach
        # its result to the later ongoing record, even with equal text length.
        entered, release = threading.Event(), threading.Event()

        def held_summary(_did, body):
            entered.set()
            release.wait(3)
            return {"context": "Old ended revision", "transcript_lines": 1}

        with patch.object(routes._summary, "summarize", side_effect=held_summary):
            try:
                save(record("s_held", 1, ended=True))
                assert entered.wait(2), "old worker never entered fake provider"
                save(record("s_held", 2, text="Resumed current buyer words", ended=False))
                release.set()
                drain()
                current = stored("s_held")
                check("old in-flight summary cannot attach after a higher-sequence resume", current["save_seq"] == 2 and not current["ended"] and "summary" not in current)
            finally:
                release.set()
                drain()

        # Several real ASGI calls race from separate threads. A delayed older
        # request must not win merely because it arrives after the highest one.
        gate = threading.Event()

        def concurrent_save(seq):
            if seq != 20:
                assert gate.wait(3)
            response = save(record("s_race", seq, text=f"Snapshot {seq}"))
            if seq == 20:
                gate.set()
            return response

        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(concurrent_save, [20, 1, 19, 3, 2, 18, 7, 6]))
        check("concurrent out-of-order requests retain the highest complete snapshot", stored("s_race")["save_seq"] == 20 and stored("s_race")["transcript"][0]["text"] == "Snapshot 20" and sum(r["accepted"] for r in results) == 1)
        check("summary content revision excludes only transport bookkeeping", routes._session_revision({"ended": True, "transcript": [], "save_seq": 1}) == routes._session_revision({"ended": True, "transcript": [], "save_seq": 2}) and routes._session_revision({"ended": True, "transcript": []}) != routes._session_revision({"ended": False, "transcript": []}))
        check("all fake workers finish under blocked sockets", all(not worker.is_alive() for worker in workers))


if __name__ == "__main__":
    results = []
    def check(name, ok):
        results.append(bool(ok))
        print(f"{'PASS' if ok else 'FAIL'} session checkpoint: {name}")
    run(check)
    print(f"Session checkpoint: {sum(results)}/{len(results)} (actual route and threads; isolated mock; blocked sockets)")
    raise SystemExit(0 if all(results) else 1)
