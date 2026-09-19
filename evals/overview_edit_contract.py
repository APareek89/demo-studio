"""Free API-level overview edit regression; isolated storage, all network blocked."""
import copy
import sys
import tempfile
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fastapi.testclient import TestClient
from server import config, store
from server.agents import visuals
from server.app import app

passed = []
def check(name, condition):
    assert condition, name
    passed.append(name)
    print("PASS", name)

with tempfile.TemporaryDirectory(prefix="overview-edit-") as temp, ExitStack() as stack:
    stack.enter_context(patch.multiple(config, MOCK_LLM=True, DATA_DIR=Path(temp)))
    network = [stack.enter_context(patch(name, side_effect=AssertionError("No outbound calls"))) for name in ("socket.create_connection", "socket.socket.connect", "socket.socket.connect_ex", "server.llm.gemini.client")]
    stack.enter_context(patch.object(visuals, "build_map", return_value={}))
    did = store.new_demo("Overview contract")["id"]
    fact = {"id": "F001", "kind": "feature", "claim": "Airbags", "value": "Six airbags.", "source": {"ref": "src_doc", "locator": "p1", "quote": "Six airbags."}, "confidence": 1, "approved": True, "truth": "stated"}
    store.write_json(did, "understanding.json", {"product": {"name": "Contract car"}, "facts": [fact], "images": [], "shots": [], "competitors": [], "brand": {}})
    store.write_json(did, "plan.json", {"voice": {}, "ctas": [], "segments": []})
    script = {"segments": [], "closing": [], "runtime_overview": {"id": "runtime-overview", "text": "Six airbags support your journey. We can explore the features together, take a closer look at what matters, and leave space for your questions.", "fact_ids": ["F001"], "audio": "audio/old.wav", "delivery": {"tone": "warm", "pace": 1.0}, "duration_seconds": 12, "duration_exact": True}}
    store.write_json(did, "script.json", script)
    store.update(did, lambda demo: demo["approvals"].update({name: True for name in store.CARDS}))
    client = TestClient(app)
    text = "Six airbags support your journey. Together, we can explore the details that matter to you, see how they fit, and answer your questions along the way."
    response = client.patch(f"/api/demos/{did}/align/script", json={"lines": [{"id": "runtime-overview", "text": text, "delivery": {"tone": "reassuring", "pace": .95}}], "realign_visuals": False})
    saved = store.read_json(did, "script.json")["runtime_overview"]
    check("overview is editable through the actual script API", response.status_code == 200 and saved["text"] == text and saved["delivery"]["tone"] == "reassuring")
    check("text and delivery edits invalidate the old recording", not saved.get("audio") and saved["fact_ids"] == ["F001"])
    check("edited overview cannot retain the old exact audio duration", not saved.get("duration_exact") and saved.get("duration_seconds") is None)
    check("overview edits reopen script and visual human review", not store.load(did)["approvals"]["script"] and not store.load(did)["approvals"]["visuals"])
    before = {name: store.path(did, name).read_bytes() for name in ("script.json", "demo.json", "understanding.json")}
    for label, update, status in [("unknown fact", {"fact_ids": ["F999"]}, 400), ("uncited numeric claim", {"text": "The car travels 999 km on one charge.", "fact_ids": []}, 400), ("unsupported delivery", {"delivery": {"tone": "salesy", "pace": 2}}, 400), ("missing line", {"id": "missing-overview", "text": text}, 404)]:
        edit = {"id": "runtime-overview", **update}
        response = client.patch(f"/api/demos/{did}/align/script", json={"lines": [edit], "realign_visuals": False})
        check(f"overview rejects {label} atomically", response.status_code == status and all(store.path(did, name).read_bytes() == data for name, data in before.items()))
    check("overview validation performs no outbound call", not any(mock.called for mock in network))
print(f"Overview editing: {len(passed)}/{len(passed)} passed")
