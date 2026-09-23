"""The optional product-site allowlist is off until a valid explicit setting enables it."""
from __future__ import annotations

import os
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch


def run(check):
    from fastapi.testclient import TestClient
    from server import store
    from server.app import app

    demo = store.new_demo("Customer website setting fixture")
    did = demo["id"]
    api = TestClient(app)
    check("new demos leave product-site lookup off", demo["settings"]["runtime_default_sites"] == "off")
    response = api.patch(f"/api/demos/{did}", json={"settings": {"runtime_default_sites": "on"}})
    check("explicit on is stored through the existing settings API", response.status_code == 200 and store.load(did)["settings"]["runtime_default_sites"] == "on")
    response = api.patch(f"/api/demos/{did}", json={"settings": {"audience": "expert"}})
    check("unrelated setting changes preserve the selection", response.status_code == 200 and store.load(did)["settings"]["runtime_default_sites"] == "on")
    before = store.path(did, "demo.json").read_bytes()
    for invalid in (True, "ON", "yes", None):
        response = api.patch(f"/api/demos/{did}", json={"name": "Must not be saved", "settings": {"runtime_default_sites": invalid}})
        check(f"invalid {invalid!r} rejects the entire write", response.status_code == 400 and store.path(did, "demo.json").read_bytes() == before)
    response = api.patch(f"/api/demos/{did}", json={"settings": {"runtime_default_sites": "off"}})
    saved = store.load(did)
    check("off can be restored without changing approvals", response.status_code == 200 and saved["settings"]["runtime_default_sites"] == "off" and saved["approvals"] == demo["approvals"])


if __name__ == "__main__":
    with tempfile.TemporaryDirectory(prefix="runtime-site-settings-") as tmp:
        os.environ.update(MOCK_LLM="1", CLOUD_SYNC="0", DEMO_STUDIO_DATA=tmp, DEMO_STUDIO_GRAPH_DB=str(Path(tmp) / "graph.sqlite"))
        sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
        rows = []
        def check(name, passed):
            rows.append(bool(passed)); print(("PASS " if passed else "FAIL ") + name)
        with patch("socket.socket.connect", side_effect=AssertionError("Outbound blocked")), patch("socket.create_connection", side_effect=AssertionError("Outbound blocked")):
            run(check)
        print(f"Runtime site settings: {sum(rows)}/{len(rows)}")
        raise SystemExit(0 if all(rows) else 1)
