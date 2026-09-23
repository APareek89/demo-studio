"""Selected input mode survives server saves and runtime checkpoints without relabelling old visits."""
from __future__ import annotations

import asyncio
import os
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch


def run(check):
    from fastapi.testclient import TestClient
    from server import runtime_graph, runtime_state, storage, store
    from server.app import app
    did = store.new_demo("Input mode fixture")["id"]
    api = TestClient(app)

    def save(mode=None, sid="s_mode"):
        body = {"id": sid, "ended": False, "turns": []}
        if mode is not None:
            body["input_mode"] = mode
        response = api.post(f"/api/demos/{did}/run/session", json=body)
        assert response.status_code == 200, response.text
        return storage.backend().get_session(did, sid)

    check("server saves selected voice mode", save("voice")["input_mode"] == "voice")
    check("server saves selected text mode", save("text")["input_mode"] == "text")
    check("old save without mode preserves known choice", save()["input_mode"] == "text")
    check("invalid mode cannot erase the known choice", save("invalid")["input_mode"] == "text")
    check("old session cannot invent a selected mode", "input_mode" not in save(sid="s_old"))

    async def finish(state, config):
        runtime_state.checkpoint(state, "delivered")
        return {**state, "result": {"answer": "", "answered": False}}

    with patch.object(runtime_graph.graph, "ainvoke", side_effect=finish):
        asyncio.run(runtime_graph.run_turn(did, {"session_id": "s_graph", "question": "Hello", "input_mode": "voice"}))
        check("runtime persists voice mode in its owned checkpoint", runtime_state.previous_state(did, "s_graph")["input_mode"] == "voice")
        asyncio.run(runtime_graph.run_turn(did, {"session_id": "s_graph", "question": "Hello again"}))
        check("later runtime turn can omit unchanged input mode", runtime_state.previous_state(did, "s_graph")["input_mode"] == "voice")
        asyncio.run(runtime_graph.run_turn(did, {"session_id": "s_graph", "question": "Typing now", "input_mode": "text"}))
        check("runtime mode toggle updates its next checkpoint", runtime_state.previous_state(did, "s_graph")["input_mode"] == "text")


if __name__ == "__main__":
    with tempfile.TemporaryDirectory(prefix="input-mode-") as tmp:
        os.environ.update(MOCK_LLM="1", CLOUD_SYNC="0", DEMO_STUDIO_DATA=tmp, DEMO_STUDIO_GRAPH_DB=str(Path(tmp) / "graph.sqlite"))
        sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
        rows = []
        def check(name, passed):
            rows.append(bool(passed)); print(("PASS " if passed else "FAIL ") + name)
        with patch("socket.socket.connect", side_effect=AssertionError("Outbound blocked")), patch("socket.create_connection", side_effect=AssertionError("Outbound blocked")):
            run(check)
        print(f"Session input mode: {sum(rows)}/{len(rows)}")
        raise SystemExit(0 if all(rows) else 1)
