"""Free eval: the slides-v1 player contract, exercised end to end through the mock server (no source grepping).

Phase 1: stage modes are video | slide, the 3D path is gone, runtime Q&A declines with a callback when every
provider fails, the FAQ bank still answers instantly, MP4 export is parked. Later phases add the deck checks here."""
import os, sys, time, json
os.environ["MOCK_LLM"] = "1"
os.environ.setdefault("DEMO_STUDIO_DATA", os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "test-demos"))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fastapi.testclient import TestClient
from server.app import app
from server import store, config
from server.agents import qa
from server.llm import runtime

c = TestClient(app)
rows: list[tuple[str, bool, str]] = []
def check(name: str, ok: bool, detail: str = ""):
    rows.append((name, bool(ok), detail))

def wait(i, want, secs=180):
    t0 = time.time()
    while time.time() - t0 < secs:
        s = c.get(f"/api/demos/{i}").json()["demo"]["status"]
        if s == want: return
        if s == "error": raise SystemExit("status error: " + json.dumps(c.get(f"/api/demos/{i}").json()["demo"]["stages"], indent=1))
        time.sleep(0.4)
    raise SystemExit(f"timeout waiting for {want}")

# ---- build one mock demo from the sample images ----
i = c.post("/api/demos", json={"name": "Deck QA iQube"}).json()["id"]
imgs = sorted(os.listdir("samples/iqube"))
r = c.post(f"/api/demos/{i}/sources", files=[("files", ("hero-front.webp", open("samples/iqube/front.webp", "rb").read(), "image/webp"))], data={"role": "hero"}); assert r.status_code == 200, r.text
hero_src = r.json()["added"][0]["id"]
r = c.post(f"/api/demos/{i}/sources", files=[("files", (n, open(f"samples/iqube/{n}", "rb"), "image/webp")) for n in imgs], data={"role": "product"}); assert r.status_code == 200, r.text
r = c.post(f"/api/demos/{i}/sources", data={"role": "catalogue", "text": "Battery warranty: 3 years / 50,000 km. Ex-showroom price Rs 1,24,990.", "text_name": "spec"}); assert r.status_code == 200, r.text
c.post(f"/api/demos/{i}/read"); wait(i, "align")
for card in c.get(f"/api/demos/{i}").json()["demo"]["approvals"]:
    c.post(f"/api/demos/{i}/approve/{card}")
c.post(f"/api/demos/{i}/build"); wait(i, "ready")
b = c.get(f"/api/demos/{i}/bundle").json()

# ---- 3D is gone, everywhere the customer or the studio could see it ----
check("bundle carries no 3D asset", "visual_asset" not in b)
check("no line carries a stage-mode classifier", not any("display_mode" in (l.get("visual") or {}) for s in b["segments"] for l in s["lines"] + s["deeper"]))
check("every line visual is none | image | shot", all((l.get("visual") or {}).get("kind") in ("none", "image", "shot") for s in b["segments"] for l in s["lines"]))
check("demo record has no visual_asset field", "visual_asset" not in c.get(f"/api/demos/{i}").json()["demo"])
check("no visual/ folder is created for a new demo", not (store.demo_dir(i) / "visual").exists())
check("/visual routes are gone", c.get(f"/api/demos/{i}/visual").status_code == 404)
check("/assets routes are gone", c.get("/api/assets").status_code == 404)
check("MP4 export is parked with 409", c.get(f"/api/demos/{i}/export.mp4").status_code == 409)
h = c.get("/api/health").json()
check("health lists runtime providers, not runware", "runtime_providers" in h and "runware" not in h and "runware_model" not in h)
check("index.html loads no model-viewer", "model-viewer" not in c.get("/").text)
check("player has no 3D branch", "model-viewer" not in c.get("/web/player/player.js").text)

# ---- runtime Q&A: every provider down → decline + callback, never a guess, never a cooldown ----
orig = runtime.structured
runtime.structured = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("all runtime providers failed — gemini: 503 | claude: credit balance"))
try:
    r = c.post(f"/api/demos/{i}/run/qa", json={"question": "What is the exact on-road price in Pune?", "history": [], "profile": {"name": "QA"}, "skip_bank": True}).json()
    check("providers down → declines", r["answered"] is False and r["fact_ids"] == [])
    check("providers down → offers a callback", r.get("offer_callback") is True)
    check("providers down → says it will not guess", "won't guess" in r["answer"])
    r2 = c.post(f"/api/demos/{i}/run/qa", json={"question": "What colours are there?", "history": [], "skip_bank": True}).json()
    check("no ten-minute cooldown: the next call still tries the providers (and declines again)", r2["answered"] is False)
    check("no hardcoded product fallback survives", not hasattr(qa, "_local_grounded_answer") and not hasattr(qa, "_named_competitor"))
finally:
    runtime.structured = orig
tr = c.get(f"/api/demos/{i}/trace").json()["rows"]
check("provider failure is traced", any(x.get("kind") == "qa-providers-failed" for x in tr))

# ---- the FAQ bank still answers with no model call ----
faq = b.get("faq") or []
if faq:
    r = c.post(f"/api/demos/{i}/run/qa", json={"question": faq[0]["question"], "history": []}).json()
    check("bank question answers from the bank", r.get("from_bank") is True and r.get("bank_id") == faq[0]["id"])
else:
    check("bank question answers from the bank", False, "no FAQ entries in the mock bundle")

# ---- Phase 2: parts carry boxes; hero selection; stills from a video-only upload ----
und = store.read_json(i, "understanding.json"); imgs_u = und.get("images", [])
parts = [p for im in imgs_u for p in im.get("parts", [])]
check("every tagged image lists parts as {name, box, confidence}", bool(parts) and all(isinstance(p, dict) and {"name", "box", "confidence"} <= set(p) for p in parts))
check("every part box is normalised 0-1 with positive size", all(0 <= p["box"]["x"] <= 1 and 0 <= p["box"]["y"] <= 1 and 0 < p["box"]["w"] <= 1 and 0 < p["box"]["h"] <= 1 for p in parts))
check("every part confidence is 0-1", all(0 <= p["confidence"] <= 1 for p in parts))
check("images carry full_product", all("full_product" in im for im in imgs_u))
check("bundle media images carry parts, full_product and role", all({"parts", "full_product", "role"} <= set(im) for im in b["media"]["images"]))
hero_im = next((im for im in imgs_u if im["source_id"] == hero_src), None)
check("the hero upload is bundle.hero_image", hero_im is not None and b.get("hero_image") == hero_im["id"])
check("media.hero is the hero image's url", b["media"]["hero"] == next((x["url"] for x in b["media"]["images"] if x["id"] == b.get("hero_image")), None))
r = c.post(f"/api/demos/{i}/sources", files=[("files", ("hero-2.webp", open("samples/iqube/angle.webp", "rb").read(), "image/webp"))], data={"role": "hero"}).json()
h2 = r["added"][0]["id"]; srcs = c.get(f"/api/demos/{i}").json()["demo"]["sources"]
check("a second hero upload replaces the first (old one becomes a product image)", next(s["role"] for s in srcs if s["id"] == hero_src) == "product" and next(s["role"] for s in srcs if s["id"] == h2) == "hero")

# video only, no hero: stills become images; the best full-product still becomes the hero
v = c.post("/api/demos", json={"name": "Deck QA video-only"}).json()["id"]
r = c.post(f"/api/demos/{v}/sources", files=[("files", ("walkaround.mp4", open("samples/iqube_dummy.mp4", "rb").read(), "video/mp4"))], data={"role": "product"}); assert r.status_code == 200, r.text
c.post(f"/api/demos/{v}/read"); wait(v, "align")
vd = c.get(f"/api/demos/{v}").json()["demo"]; vund = store.read_json(v, "understanding.json")
stills = [s for s in vd["sources"] if s["kind"] == "image" and s.get("derived_from")]
from server import media as _media
if _media.ffmpeg():
    check("video-only demo gets one still per good shot, tagged with its shot id", bool(stills) and all(s["derived_from"].startswith("sh") for s in stills))
    check("stills are tagged like uploaded images", bool(vund.get("images")) and all(im["source_id"] in {s["id"] for s in stills} for im in vund["images"]))
    from server.agents import bundle as _bundle
    vb = _bundle.build(v, lambda m: None)
    full = [im for im in vund["images"] if im.get("full_product")]
    check("without a hero upload, hero_image is the best full-product still", bool(vb.get("hero_image")) and (not full or vb["hero_image"] == max(full, key=lambda x: x["quality"])["id"]))
else:
    check("video-only demo gets stills", False, "ffmpeg unavailable on this machine")

# ---- runtime config ----
check("runtime provider order is configurable and defaults gemini first", config.RUNTIME_PROVIDERS[0] == "gemini" and "claude" in config.RUNTIME_PROVIDERS)
check("runtime timeout is short", 0 < config.RUNTIME_TIMEOUT <= 30)

print("| Case | OK |"); print("|---|---|")
for name, ok, detail in rows:
    print(f"| {name}{(' — ' + detail) if detail and not ok else ''} | {'✅' if ok else '❌'} |")
n_ok = sum(1 for _, ok, _ in rows if ok)
print(f"\n{n_ok}/{len(rows)} deck cases pass")
sys.exit(0 if n_ok == len(rows) else 1)
