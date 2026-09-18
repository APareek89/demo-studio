"""Real summary threads and session route writes, with held fake providers only."""
from __future__ import annotations

import asyncio
import copy
import os
import sys
import tempfile
import threading
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def run(check):
    with tempfile.TemporaryDirectory(prefix="summary-race-") as tmp, ExitStack() as stack:
        stack.enter_context(patch.dict(os.environ, {"MOCK_LLM": "1", "CLOUD_SYNC": "0", "STORAGE_BACKEND": "local",
            "DEMO_STUDIO_DATA": str(Path(tmp) / "demos"), "DEMO_STUDIO_GRAPH_DB": str(Path(tmp) / "graph.sqlite")}))
        import httpx
        from server import app as routes, config, storage, store
        stack.enter_context(patch.object(config, "DATA_DIR", Path(tmp) / "demos"))
        backend = storage.Local()
        stack.enter_context(patch.object(storage, "backend", return_value=backend))
        for name in ("socket.create_connection", "socket.socket.connect", "socket.socket.connect_ex"):
            stack.enter_context(patch(name, side_effect=AssertionError("Network forbidden")))
        did = store.new_demo("Summary race fixture")["id"]
        workers = []
        original_thread = threading.Thread

        class Worker(original_thread):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                workers.append(self)

        stack.enter_context(patch.object(routes.threading, "Thread", Worker))

        def save(record):
            async def request():
                async with httpx.AsyncClient(transport=httpx.ASGITransport(app=routes.app), base_url="http://test") as client:
                    response = await client.post(f"/api/demos/{did}/run/session", json=record)
                    if response.status_code != 200:
                        raise AssertionError(response.text)
            asyncio.run(request())

        def session(sid, text="Original buyer words", **extra):
            return {"id": sid, "ended": True, "profile": {"why": text}, "questions": [text],
                    "transcript": [{"role": "user", "text": text}], "minutes": 1, **extra}

        def result(text):
            return {"context": text, "transcript_lines": 1, "generated_at": 1}

        # The first success is followed by a duplicate worker's delayed failure
        # in the original implementation. All calls use genuine Thread workers.
        entered = threading.Event(); duplicate_entered = threading.Event()
        success_release = threading.Event(); failure_release = threading.Event()
        calls = []; calls_lock = threading.Lock()

        def competing(_did, record):
            with calls_lock:
                calls.append(copy.deepcopy(record)); number = len(calls)
            if number == 1:
                entered.set(); success_release.wait(3)
                return result("Successful current summary")
            duplicate_entered.set(); failure_release.wait(3)
            raise RuntimeError("Duplicate provider failure")

        with patch.object(routes._summary, "summarize", side_effect=competing):
            try:
                with patch.object(routes.time, "time", return_value=100):
                    save(session("s_duplicates"))
                check("summary race: first actual worker enters the fake provider", entered.wait(2))
                first = workers[-1]
                with patch.object(routes.time, "time", return_value=200):
                    save(session("s_duplicates"))
                duplicate = workers[-1]
                duplicate.join(.1)
                check("summary race: identical in-flight saves launch only one provider call", len(calls) == 1 and not duplicate_entered.is_set())
                success_release.set(); first.join(2)
                current = backend.get_session(did, "s_duplicates")
                check("summary race: attaching success preserves the latest saved record metadata", current.get("saved_at") == 200)
                failure_release.set(); duplicate.join(2)
                current = backend.get_session(did, "s_duplicates")
                check("summary race: a late duplicate failure cannot replace current success", current.get("summary", {}).get("context") == "Successful current summary" and "error" not in current.get("summary", {}))
                count = len(calls); save(session("s_duplicates"))
                for worker in workers:
                    worker.join(2)
                check("summary race: an identical completed save reuses its summary without provider work", len(calls) == count)
            finally:
                success_release.set(); failure_release.set()
                for worker in workers:
                    worker.join(3)

        # Same line count is not the same input. Resume must invalidate the old
        # summary and an old in-flight result must not roll the record back.
        old_entered = threading.Event(); old_release = threading.Event(); seen = []

        def revisions(_did, record):
            seen.append(record["transcript"][0]["text"])
            if record["id"] == "s_resume" and record["transcript"][0]["text"] == "Old words":
                old_entered.set(); old_release.wait(3)
            return result(record["transcript"][0]["text"])

        with patch.object(routes._summary, "summarize", side_effect=revisions):
            try:
                save(session("s_resume", "Old words")); old_worker = workers[-1]
                check("summary race: held old revision reaches the provider", old_entered.wait(2))
                save(session("s_independent", "Independent session")); independent = workers[-1]; independent.join(2)
                check("summary race: one held provider does not block another session summary", not independent.is_alive() and backend.get_session(did, "s_independent").get("summary", {}).get("context") == "Independent session")
                save(session("s_resume", "Corrected buyer words", ended=False, minutes=2))
                old_release.set(); old_worker.join(2)
                current = backend.get_session(did, "s_resume")
                check("summary race: a resumed same-length transcript survives an old result unchanged", current["transcript"][0]["text"] == "Corrected buyer words" and not current["ended"] and current["minutes"] == 2 and not current.get("summary"))
                save(session("s_resume", "Corrected buyer words", minutes=2)); workers[-1].join(2)
                current = backend.get_session(did, "s_resume")
                check("summary race: the newly ended revision receives its own summary", current.get("summary", {}).get("context") == "Corrected buyer words" and seen.count("Corrected buyer words") == 1)
                save(session("s_resume", "Different same-length transcript", minutes=2)); workers[-1].join(2)
                current = backend.get_session(did, "s_resume")
                check("summary race: equal transcript length cannot reuse a different-content summary", current.get("summary", {}).get("context") == "Different same-length transcript")
                save(session("s_resume", "Different same-length transcript", minutes=2, cta="Customer selected follow-up")); workers[-1].join(2)
                check("summary race: changed non-transcript summary input triggers current work", seen.count("Different same-length transcript") == 2)
            finally:
                old_release.set()
                for worker in workers:
                    worker.join(3)

        stale_entered = threading.Event(); stale_release = threading.Event()

        def late_error(_did, record):
            if record["transcript"][0]["text"] == "Stale revision":
                stale_entered.set(); stale_release.wait(3)
                raise RuntimeError("Old revision failed")
            return result("New revision succeeded")

        with patch.object(routes._summary, "summarize", side_effect=late_error):
            try:
                save(session("s_replaced", "Stale revision")); stale = workers[-1]
                check("summary race: superseded failed worker is held before completion", stale_entered.wait(2))
                save(session("s_replaced", "Fresh revision")); fresh = workers[-1]; fresh.join(2)
                stale_release.set(); stale.join(2)
                current = backend.get_session(did, "s_replaced")
                check("summary race: a superseded error cannot overwrite the new session or summary", current["transcript"][0]["text"] == "Fresh revision" and current.get("summary", {}).get("context") == "New revision succeeded")
            finally:
                stale_release.set()
                for worker in workers:
                    worker.join(3)
        check("summary race: all fake workers terminate without outbound calls", all(not w.is_alive() for w in workers))


if __name__ == "__main__":
    results = []
    def check(name, ok):
        results.append(bool(ok))
        print(f"{'PASS' if ok else 'FAIL'} {name}")
    run(check)
    print(f"Summary race: {sum(results)}/{len(results)} (actual threads and ASGI route, no paid calls)")
    raise SystemExit(0 if all(results) else 1)
