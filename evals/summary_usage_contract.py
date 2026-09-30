"""Summary worker accounting: real threads and temporary stores, no providers."""
from __future__ import annotations

import json
import os
import sys
import tempfile
import threading
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def run(check):
    with tempfile.TemporaryDirectory(prefix="summary-usage-") as tmp, ExitStack() as stack:
        stack.enter_context(patch.dict(os.environ, {"MOCK_LLM": "1", "CLOUD_SYNC": "0",
            "STORAGE_BACKEND": "local", "DEMO_STUDIO_DATA": str(Path(tmp) / "demos"),
            "DEMO_STUDIO_GRAPH_DB": str(Path(tmp) / "graph.sqlite")}))
        from server import app as routes, config, storage, store, usage
        stack.enter_context(patch.object(config, "DATA_DIR", Path(tmp) / "demos"))
        backend = storage.Local()
        stack.enter_context(patch.object(storage, "backend", return_value=backend))
        for name in ("socket.create_connection", "socket.socket.connect", "socket.socket.connect_ex"):
            stack.enter_context(patch(name, side_effect=AssertionError("Network forbidden")))
        ids = [store.new_demo("Summary usage fixture")["id"] for _ in range(2)]
        for did in ids:
            backend.put_session(did, {"id": "s_fixture", "ended": True, "transcript": []})

        observed = []
        def provider(did, session):
            observed.append((usage.current_demo.get(), usage.current_stage.get()))
            usage.record("runtime", "gemini-3.8-flash", input_tokens=100, output_tokens=20)
            usage.trace("runtime", "gemini-3.8-flash", latency_ms=1, input_tokens=100, output_tokens=20)
            return {"context": "Fixture", "transcript_lines": 0}

        def rows(did, name):
            path = store.path(did, name)
            return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []

        parent_demo = usage.current_demo.set("parent-demo")
        parent_stage = usage.current_stage.set("parent-stage")
        try:
            with patch.object(routes._summary, "summarize", side_effect=provider):
                workers = [threading.Thread(target=routes._summarize_session, args=(did, "s_fixture")) for did in ids]
                for worker in workers:
                    worker.start()
                for worker in workers:
                    worker.join(timeout=5)
                check("summary usage: independent workers complete", all(not w.is_alive() for w in workers))
                check("summary usage: each worker establishes its own demo and runtime stage",
                      set(observed) == {(did, "runtime") for did in ids})
                check("summary usage: both actual usage and trace files receive exactly one row per demo",
                      all(len(rows(did, name)) == 1 for did in ids for name in ("usage.jsonl", "trace.jsonl")))
                check("summary usage: recorded cost contributes to the demo total",
                      all(usage.summary(did)["total_usd"] > 0 for did in ids))
                check("summary usage: parent context is unchanged by concurrent workers",
                      (usage.current_demo.get(), usage.current_stage.get()) == ("parent-demo", "parent-stage"))
                direct = backend.get_session(ids[0], "s_fixture")
                direct.pop("summary", None)
                direct["profile"] = {"why": "New customer context for a distinct summary revision"}
                backend.put_session(ids[0], direct)
                routes._summarize_session(ids[0], "s_fixture")
                check("summary usage: direct worker call restores both caller context values",
                      (usage.current_demo.get(), usage.current_stage.get()) == ("parent-demo", "parent-stage"))

            def failed(did, session):
                usage.trace("runtime", "gemini-3.8-flash", latency_ms=1, error="Fixture provider failed")
                raise RuntimeError("Fixture provider failed: credential-like-content-must-not-echo")
            with patch.object(routes._summary, "summarize", side_effect=failed):
                revised = backend.get_session(ids[1], "s_fixture")
                revised.pop("summary", None)
                revised["profile"] = {"why": "Different input whose new summary attempt fails"}
                backend.put_session(ids[1], revised)
                routes._summarize_session(ids[1], "s_fixture")
                check("summary usage: failure trace remains attributed while session receives a safe error",
                      any(r.get("error") == "Fixture provider failed" for r in rows(ids[1], "trace.jsonl"))
                      and backend.get_session(ids[1], "s_fixture")["summary"]["error"] == "The visit summary could not finish."
                      and "credential-like-content" not in json.dumps(backend.get_session(ids[1], "s_fixture")))
                check("summary usage: failure also restores caller context",
                      (usage.current_demo.get(), usage.current_stage.get()) == ("parent-demo", "parent-stage"))
        finally:
            usage.current_stage.reset(parent_stage)
            usage.current_demo.reset(parent_demo)


if __name__ == "__main__":
    results = []
    def check(name, ok):
        results.append(bool(ok))
        print(f"{'PASS' if ok else 'FAIL'} {name}")
    run(check)
    print(f"Summary usage: {sum(results)}/{len(results)} (no paid calls)")
    raise SystemExit(0 if all(results) else 1)
