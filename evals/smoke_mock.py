"""Free eval: full pipeline with MOCK_LLM=1 through the FastAPI TestClient (no server, no keys)."""
import os, sys, time, json
os.environ["MOCK_LLM"] = "1"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fastapi.testclient import TestClient
from server.app import app
from server import store

c = TestClient(app)
def status(i): return c.get(f"/api/demos/{i}").json()["demo"]["status"]
def wait(i, want, secs=90):
    t0 = time.time()
    while time.time() - t0 < secs:
        s = status(i)
        if s == want: return True
        if s == "error": raise SystemExit(f"status error: {json.dumps(c.get(f'/api/demos/{i}').json()['demo']['stages'], indent=1)}")
        time.sleep(0.5)
    raise SystemExit(f"timeout waiting for {want}, status={status(i)}")

d = c.post("/api/demos", json={"name": "Smoke iQube", "url": "https://www.tvsmotor.com/electric-scooters/tvs-iqube"}).json()
i = d["id"]; print("created", i)
imgs = sorted(os.listdir("samples/iqube"))
files = [("files", (n, open(f"samples/iqube/{n}", "rb"), "image/webp")) for n in imgs]
r = c.post(f"/api/demos/{i}/sources", files=files, data={"role": "product"}); assert r.status_code == 200, r.text
r = c.post(f"/api/demos/{i}/sources", data={"role": "brand", "text": "Warm and direct. Never say cheapest."}); assert r.status_code == 200, r.text
n_src = len(c.get(f"/api/demos/{i}").json()["demo"]["sources"]); print("sources", n_src); assert n_src == len(imgs) + 2
r = c.post(f"/api/demos/{i}/read"); assert r.status_code == 200, r.text
wait(i, "align"); print("read → align ok")
st = c.get(f"/api/demos/{i}").json()
assert st["cards"] and st["cards"]["facts"]["facts"], "no facts"
assert any(m["role"] == "agent" for m in st["conversation"]), "no opening message"
print("cards: images", len(st["cards"]["visuals"]["images"]), "facts", len(st["cards"]["facts"]["facts"]), "ctas", len(st["cards"]["ctas"]))
r = c.post(f"/api/demos/{i}/align", data={"message": "looks fine", "context": "align"}); assert r.status_code == 200, r.text; print("align reply:", r.json()["reply"][:60])
for card in ("visuals", "facts", "persona", "ctas"):
    r = c.post(f"/api/demos/{i}/approve/{card}"); assert r.status_code == 200, r.text
assert all(c.get(f"/api/demos/{i}").json()["demo"]["approvals"].values()); print("approved all")
r = c.post(f"/api/demos/{i}/ctas", json={"ctas": [{"id": "book", "label": "Book a test ride", "kind": "book", "url": "", "primary": True, "when": "always"}]}); assert r.status_code == 200, r.text
r = c.post(f"/api/demos/{i}/build"); assert r.status_code == 200, r.text
wait(i, "ready", 180); print("build → ready ok")
b = c.get(f"/api/demos/{i}/bundle").json()
assert b["segments"], "no segments"; print("bundle v", b["version"], "segments", len(b["segments"]), "closing", len(b["closing"]), "ctas", [x["label"] for x in b["ctas"]])
audio = [l["audio"] for s in b["segments"] for l in s["lines"]]; print("lines with audio", sum(1 for a in audio if a), "/", len(audio))
if audio and audio[0]:
    r = c.get(audio[0]); assert r.status_code == 200 and r.headers["content-type"].startswith("audio"), "audio not served"
r = c.post(f"/api/demos/{i}/run/qa", json={"question": "what is the kerb weight?", "history": [], "profile": {"name": "Anand"}}); assert r.status_code == 200, r.text
qa = r.json(); assert qa["answered"] is False and qa["fact_ids"] == [], qa; print("qa don't-guess ok:", qa["answer"][:50])
und = store.read_json(i, "understanding.json"); assert any(u["origin"] == "runtime" for u in und["unknowns"]), "runtime unknown not recorded"
r = c.post(f"/api/demos/{i}/run/session", json={"profile": {"name": "Anand"}, "questions": ["kerb weight"], "cta": "Book a test ride", "intent": 61}); assert r.status_code == 200
r = c.post(f"/api/demos/{i}/feedback", json={"message": "say the warranty before the price", "context": {"segment": "x"}}); assert r.status_code == 200, r.text; print("feedback reply:", r.json()["reply"][:60])
reh = c.get(f"/api/demos/{i}").json()["rehearsal"]; print("rehearsal coverage", reh and reh.get("coverage"), "gaps", reh and len(reh.get("gaps", [])))
print("SMOKE OK", i)
