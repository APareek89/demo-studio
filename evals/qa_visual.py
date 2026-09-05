"""Free failure-path eval for the optional Demo Visual workflow."""
from __future__ import annotations

import os
import struct
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
os.environ["MOCK_LLM"] = "1"
os.environ.setdefault("CLOUD_SYNC", "0")
os.environ.setdefault("DEMO_STUDIO_DATA", str(ROOT / "data" / "test-demos"))
sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient
from server import config, store
from server.app import app

c = TestClient(app)
results: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, ok, detail))


demo = c.post("/api/demos", json={"name": "Visual failure QA iQube"}).json()
demo_id = demo["id"]
state = c.get(f"/api/demos/{demo_id}/visual").json()
required = [x for x in state["schema"] if x["required"]]
check("exactly five required views", len(required) == 5, ", ".join(x["key"] for x in required))
check("multi-view Rodin is the recommended model", state["model"] == "hyper3d:rodin@gen-2", state["model"])
check("all supported 3D models are exposed", {m["id"] for m in state["models"]} == set(config.RUNWARE_MODELS), str(state["models"]))

# A supplied 3D asset bypasses Runware but not the human approval gate.
direct = c.post("/api/demos", json={"name": "Direct GLB QA"}).json()["id"]
r = c.post(f"/api/demos/{direct}/visual/upload", files={"file": ("model.obj", b"not glb", "application/octet-stream")})
check("direct upload accepts GLB only", r.status_code == 400, r.text[:100])
r = c.post(f"/api/demos/{direct}/visual/upload", files={"file": ("broken.glb", b"glTF" + b"\0" * 20, "model/gltf-binary")})
check("broken GLB is rejected", r.status_code == 400, r.text[:100])
bad_scene = b"{not-json}" + b" " * 2
bad_scene_glb = struct.pack("<4sII", b"glTF", 2, 20 + len(bad_scene)) + struct.pack("<I4s", len(bad_scene), b"JSON") + bad_scene
r = c.post(f"/api/demos/{direct}/visual/upload", files={"file": ("broken-scene.glb", bad_scene_glb, "model/gltf-binary")})
check("unreadable GLB scene is rejected", r.status_code == 400, r.text[:100])
external_scene = b'{"asset":{"version":"2.0"},"buffers":[{"uri":"mesh.bin"}]}'
external_scene += b" " * ((4 - len(external_scene) % 4) % 4)
external_glb = struct.pack("<4sII", b"glTF", 2, 20 + len(external_scene)) + struct.pack("<I4s", len(external_scene), b"JSON") + external_scene
r = c.post(f"/api/demos/{direct}/visual/upload", files={"file": ("external.glb", external_glb, "model/gltf-binary")})
check("GLB with external dependencies is rejected", r.status_code == 400, r.text[:100])
scene = b'{"asset":{"version":"2.0"},"scene":0,"scenes":[{}]}'
scene += b" " * ((4 - len(scene) % 4) % 4)
glb = struct.pack("<4sII", b"glTF", 2, 20 + len(scene)) + struct.pack("<I4s", len(scene), b"JSON") + scene
r = c.post(f"/api/demos/{direct}/visual/upload", files={"file": ("ready.glb", glb, "model/gltf-binary")})
direct_state = r.json() if r.status_code == 200 else {}
direct_attempt = (direct_state.get("attempts") or [{}])[-1]
check("valid GLB enters review without Runware", r.status_code == 200 and direct_state.get("status") == "review" and direct_attempt.get("uploaded") and direct_attempt.get("cost_usd") == 0, r.text[:120])
r = c.post(f"/api/demos/{direct}/visual/approve", json={})
check("uploaded GLB attaches only after approval", r.status_code == 200 and r.json().get("asset", {}).get("source_mode") == "upload" and r.json().get("asset", {}).get("model") == "uploaded", r.text[:120])

r = c.post(f"/api/demos/{demo_id}/visual/generate", json={})
check("build blocked when required views missing", r.status_code == 400, r.text[:100])
r = c.post(f"/api/demos/{demo_id}/visual/images", data={"angle": "made_up"}, files={"file": ("x.jpg", b"x", "image/jpeg")})
check("unknown angle rejected", r.status_code == 400, r.text[:100])
r = c.post(f"/api/demos/{demo_id}/visual/images", data={"angle": "front"}, files={"file": ("bad.jpg", b"not an image", "image/jpeg")})
check("corrupted image rejected", r.status_code == 400, r.text[:100])

r = c.post(f"/api/demos/{demo_id}/visual/mode", json={"mode": "video"})
check("video mode saved", r.status_code == 200 and r.json()["mode"] == "video")
r = c.post(f"/api/demos/{demo_id}/visual/generate", json={})
check("video build blocked without video", r.status_code == 400, r.text[:100])
c.post(f"/api/demos/{demo_id}/visual/mode", json={"mode": "images"})

mapping = {"front": "front.webp", "front_three_quarter": "angle.webp", "side": "left.webp", "rear_three_quarter": "right.webp", "rear": "back.webp"}
for angle, filename in mapping.items():
    raw = (ROOT / "samples" / "iqube" / filename).read_bytes()
    r = c.post(f"/api/demos/{demo_id}/visual/images", data={"angle": angle}, files={"file": (filename, raw, "image/webp")})
    check(f"upload {angle}", r.status_code == 200, r.text[:80])

r = c.post(f"/api/demos/{demo_id}/visual/generate", json={})
check("3D spend blocked before view approval", r.status_code == 400, r.text[:100])
r = c.post(f"/api/demos/{demo_id}/visual/views/prepare", json={})
check("view preparation accepted", r.status_code == 200, r.text[:100])
for _ in range(100):
    state = c.get(f"/api/demos/{demo_id}/visual").json()
    if state["status"] == "views_review":
        break
    time.sleep(.05)
check("view review stops before Runware", state["status"] == "views_review" and not state["attempts"], str(state.get("status")))
r = c.post(f"/api/demos/{demo_id}/visual/views/approve", json={})
check("view approval recorded", r.status_code == 200 and r.json().get("views_approved"), r.text[:100])
r1 = c.post(f"/api/demos/{demo_id}/visual/generate", json={})
r2 = c.post(f"/api/demos/{demo_id}/visual/generate", json={})
check("first async build accepted", r1.status_code == 200)
check("duplicate concurrent build rejected", r2.status_code == 409, r2.text[:100])
raw = (ROOT / "samples" / "iqube" / "front.webp").read_bytes()
r = c.post(f"/api/demos/{demo_id}/visual/images", data={"angle": "front"}, files={"file": ("front.webp", raw, "image/webp")})
check("inputs cannot change during a build", r.status_code == 400, r.text[:100])
r = c.post(f"/api/demos/{demo_id}/visual/skip", json={})
check("skip remains available while building", r.status_code == 200 and r.json()["status"] == "skipped")
for _ in range(50):
    state = c.get(f"/api/demos/{demo_id}/visual").json()
    if state["status"] == "skipped":
        break
    time.sleep(.05)

for _ in range(50):
    r = c.post(f"/api/demos/{demo_id}/visual/generate", json={})
    if r.status_code == 200:
        break
    time.sleep(.05)
check("regenerate allowed after skip", r.status_code == 200, r.text[:100])
for _ in range(100):
    state = c.get(f"/api/demos/{demo_id}/visual").json()
    if state["status"] in ("review", "error"):
        break
    time.sleep(.05)
attempt = state["attempts"][-1]
glb = c.get(attempt.get("glb_url", "")) if attempt.get("glb_url") else None
check("review-ready GLB is valid", state["status"] == "review" and glb is not None and glb.status_code == 200 and glb.content[:4] == b"glTF", state.get("error", ""))
r = c.post(f"/api/demos/{demo_id}/visual/approve", json={})
check("explicit approval attaches asset", r.status_code == 200 and r.json().get("asset", {}).get("glb"), r.text[:100])
r = c.post(f"/api/demos/{demo_id}/visual/approve", json={})
check("same attempt cannot be approved twice", r.status_code == 400, r.text[:100])

# Approved Gemini gap-fill views are useful only if they actually reach a multi-view
# 3D model; the first/identity view must still be real.
raw_state = store.read_json(demo_id, "visual/state.json")
for angle in ("rear_three_quarter", "rear"):
    raw_state["angles"][angle]["origin"] = "generated"
    raw_state["angles"][angle]["generated"] = True
raw_state.update({"status": "views_review", "views_approved": False})
store.write_json(demo_id, "visual/state.json", raw_state)
r = c.post(f"/api/demos/{demo_id}/visual/views/approve", json={})
r = c.post(f"/api/demos/{demo_id}/visual/generate", json={})
for _ in range(100):
    state = c.get(f"/api/demos/{demo_id}/visual").json()
    if state["status"] == "review":
        break
    time.sleep(.05)
attempt = state["attempts"][-1]
check("approved AI gap-fill reaches multi-view 3D after a real identity view",
      attempt.get("real_count") == 3 and attempt.get("generated_count") == 2 and attempt.get("submitted_angles", [])[0] in {"front", "front_three_quarter"}, str(attempt))

failed = [x for x in results if not x[1]]
for name, ok, detail in results:
    print(("✅" if ok else "❌"), name, ("— " + detail) if detail else "")
print(f"\n{len(results) - len(failed)}/{len(results)} Demo Visual cases passed")
if failed:
    raise SystemExit(1)
