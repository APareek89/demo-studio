"""Provider gates test actual API parsing without any service or graph call."""
from __future__ import annotations

import tempfile
import time
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch


def run(check):
    from fastapi.testclient import TestClient
    from server import cloud, config, graph, store
    from server.app import app
    with tempfile.TemporaryDirectory(prefix="readiness-contract-") as tmp, ExitStack() as stack:
        stack.enter_context(patch.multiple(config, DATA_DIR=Path(tmp), MOCK_LLM=False,
                                          GEMINI_API_KEY="test-only", SARVAM_API_KEY="test-only"))
        stack.enter_context(patch.object(cloud, "enabled", return_value=False))
        stack.enter_context(patch.object(cloud, "sync_demo_async"))
        blocked = [stack.enter_context(patch(name, side_effect=AssertionError("No outbound calls")))
                   for name in ("socket.create_connection", "socket.socket.connect", "socket.socket.connect_ex")]
        read = stack.enter_context(patch.object(graph, "start_read"))
        build = stack.enter_context(patch.object(graph, "start_build"))
        demo = store.new_demo("Provider check fixture"); did = demo["id"]
        store.update(did, lambda d: (d["sources"].append({"id": "s1", "kind": "text"}),
                                    d["settings"].update(tts_provider="sarvam", sarvam_speaker="priya")))
        client = TestClient(app)
        post = lambda path, query="": client.post(f"/api/demos/{did}/{path}{query}")
        def observed(**changes):
            row = {"checked_at": time.time(), "mock": False,
                   "checks": {"reasoning": {"ready": True},
                              "streaming_speech": {"ready": True, "voice": "priya"}}}
            row.update(changes); store.write_json(did, "provider-readiness.json", row)
        check("readiness: unprobed Read and Build are blocked before graph starts",
              post("read").status_code == 409 and post("build").status_code == 409 and not read.called and not build.called)
        observed()
        check("readiness: fresh observed reasoning permits Read and selected voice permits Build",
              post("read").status_code == 200 and post("build").status_code == 200 and read.call_count == 1 and build.call_count == 1)
        observed(checked_at=time.time()-86401)
        check("readiness: expired success blocks both operations", post("read").status_code == 409 and post("build").status_code == 409)
        observed(mock=True)
        check("readiness: a mock success cannot authorize a real build", post("read").status_code == 409 and post("build").status_code == 409)
        observed(checks={"reasoning": {"ready": False}, "streaming_speech": {"ready": True, "voice": "priya"}})
        check("readiness: latest failed reasoning blocks Read and Build", post("read").status_code == 409 and post("build").status_code == 409)
        observed(checks={"reasoning": {"ready": True}, "streaming_speech": {"ready": False}})
        check("readiness: failed speech blocks Build while Read may proceed", post("read").status_code == 200 and post("build").status_code == 409)
        observed(checks={"reasoning": {"ready": True}, "streaming_speech": {"ready": True, "voice": "other"}})
        check("readiness: changing voice requires a matching speech check", post("build").status_code == 409)
        check("readiness: explicit parsed override permits operation; false does not bypass",
              post("build", "?override_readiness=false").status_code == 409 and post("build", "?override_readiness=true").status_code == 200)
        observed(checks={})
        with patch.object(config, "MOCK_LLM", True):
            check("readiness: mock-only free fixtures bypass probes", post("read").status_code == 200 and post("build").status_code == 200)
        check("readiness: checks do not probe implicitly or open sockets", not any(p.called for p in blocked))


if __name__ == "__main__":
    rows = []
    def check(name, ok, detail=""):
        rows.append(bool(ok)); print(("PASS " if ok else "FAIL ") + name)
    run(check)
    print(f"Readiness contracts: {sum(rows)}/{len(rows)}")
    raise SystemExit(0 if all(rows) else 1)
