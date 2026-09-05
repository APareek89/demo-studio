"""Free failure-path eval for the optional Demo Visual workflow."""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
os.environ["MOCK_LLM"] = "1"
os.environ.setdefault("CLOUD_SYNC", "0")
os.environ.setdefault("DEMO_STUDIO_DATA", str(ROOT / "data" / "test-demos"))
sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient
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
check("TRELLIS.2 model is fixed", state["model"] == "microsoft:trellis-2@4b", state["model"])

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

failed = [x for x in results if not x[1]]
for name, ok, detail in results:
    print(("✅" if ok else "❌"), name, ("— " + detail) if detail else "")
print(f"\n{len(results) - len(failed)}/{len(results)} Demo Visual cases passed")
if failed:
    raise SystemExit(1)
