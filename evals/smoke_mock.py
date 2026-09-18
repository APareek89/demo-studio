"""Free eval: full pipeline with MOCK_LLM=1 through the FastAPI TestClient (no server, no keys)."""
import os, sys, time, json
os.environ["MOCK_LLM"] = "1"
os.environ.setdefault("DEMO_STUDIO_DATA", os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "test-demos"))  # keep test demos out of the real list
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
mp4 = open("samples/iqube_dummy.mp4", "rb").read()[:400000] if os.path.exists("samples/iqube_dummy.mp4") else b"\x00" * 2000
r = c.post(f"/api/demos/{i}/sources", files=[("files", ("opening.mp4", mp4, "video/mp4"))], data={"role": "intro_video"}); assert r.status_code == 200, r.text
n_src = len(c.get(f"/api/demos/{i}").json()["demo"]["sources"]); print("sources", n_src); assert n_src == len(imgs) + 3  # images + url + brand text + opening film
r = c.post(f"/api/demos/{i}/read"); assert r.status_code == 200, r.text
wait(i, "align"); print("read → align ok")
st = c.get(f"/api/demos/{i}").json()
assert st["cards"] and st["cards"]["facts"]["facts"], "no facts"
assert st["cards"]["script"]["segments"] and st["cards"]["script"]["timeline"]["total_seconds"] > 0, "script missing at Align"
assert "faq" in st["cards"], "faq card missing"
assert any(m["role"] == "agent" for m in st["conversation"]), "no opening message"
print("cards: images", len(st["cards"]["visuals"]["images"]), "facts", len(st["cards"]["facts"]["facts"]), "ctas", len(st["cards"]["ctas"]), "script batches", len(st["cards"]["script"]["segments"]), "seconds", st["cards"]["script"]["timeline"]["total_seconds"], "faq", st["cards"]["faq"]["total"])
r = c.post(f"/api/demos/{i}/align", data={"message": "looks fine", "context": "align"}); assert r.status_code == 200, r.text; print("align reply:", r.json()["reply"][:60])
for card in c.get(f"/api/demos/{i}").json()["demo"]["approvals"].keys():
    r = c.post(f"/api/demos/{i}/approve/{card}"); assert r.status_code == 200, r.text
assert all(c.get(f"/api/demos/{i}").json()["demo"]["approvals"].values()); print("approved all")
r = c.post(f"/api/demos/{i}/ctas", json={"ctas": [{"id": "book", "label": "Book a test ride", "kind": "book", "url": "", "primary": True, "when": "always"}]}); assert r.status_code == 200, r.text
r = c.post(f"/api/demos/{i}/build"); assert r.status_code == 200, r.text
wait(i, "ready", 180); print("build → ready ok")
b = c.get(f"/api/demos/{i}/bundle").json()
assert b["segments"], "no segments"; assert "visual_asset" not in b, "3D field should be gone"; assert b.get("slides") and b["slides"][0]["kind"] == "hero_open" and b["slides"][-1]["kind"] == "hero_close", "deck slides missing from bundle"; print("bundle v", b["version"], "segments", len(b["segments"]), "closing", len(b["closing"]), "ctas", [x["label"] for x in b["ctas"]])
audio = [l["audio"] for s in b["segments"] for l in s["lines"]]; print("lines with audio", sum(1 for a in audio if a), "/", len(audio))
if audio and audio[0]:
    r = c.get(audio[0]); assert r.status_code == 200 and r.headers["content-type"].startswith("audio"), "audio not served"
r = c.post(f"/api/demos/{i}/run/qa", json={"question": "what is the kerb weight?", "history": [], "profile": {"name": "Anand"}}); assert r.status_code == 200, r.text
qa = r.json(); assert qa["answered"] is False and qa["fact_ids"] == [], qa; print("qa don't-guess ok:", qa["answer"][:50])
und = store.read_json(i, "understanding.json"); assert any(u["origin"] == "runtime" for u in und["unknowns"]), "runtime unknown not recorded"
r = c.post(f"/api/demos/{i}/run/pitch", json={"profile": {"name": "Anand", "why": "replace my Activa for a 25 km commute", "focus": []}, "refine": False}); assert r.status_code == 200, r.text
pp = r.json(); assert pp["route"] and all(s["segment_id"] for s in pp["route"]), pp; print("pitch route", [s["segment_id"] for s in pp["route"]], "state", pp["customer_state"])
r = c.post(f"/api/demos/{i}/run/lead", json={"phone": "my number is 98765 43210", "question": "kerb weight", "profile": {"name": "Anand"}, "consent": True, "consent_text": "By sharing your number you agree the dealership may call you about this product."}); assert r.status_code == 200 and r.json()["lead"]["phone"] == "9876543210", r.text; print("lead saved")
r = c.post(f"/api/demos/{i}/run/lead", json={"phone": "call me on 12345", "question": "x", "consent": True, "consent_text": "By sharing your number you agree the dealership may call you about this product."}); assert r.status_code == 400, "bad phone accepted"
assert c.get(f"/api/demos/{i}").json()["leads"], "lead not listed"
import struct
wav = b"RIFF" + struct.pack("<I", 36 + 4000) + b"WAVEfmt " + struct.pack("<IHHIIHH", 16, 1, 1, 16000, 32000, 2, 16) + b"data" + struct.pack("<I", 4000) + b"\x00" * 4000
r = c.post(f"/api/demos/{i}/run/stt", files={"file": ("a.wav", wav, "audio/wav")}, data={"language": "hi-IN"}); assert r.status_code == 200 and r.json()["transcript"], r.text; print("stt ok:", r.json()["transcript"])
v = c.get("/api/voices", params={"demo_id": i}).json(); assert v["provider"] in ("sarvam", "gemini") and v["voices"], v; print("voices:", v["provider"], len(v["voices"]))
sid0 = c.get(f"/api/demos/{i}").json()["demo"]["sources"][0]["id"]
r = c.patch(f"/api/demos/{i}/sources/{sid0}", json={"use_in_demo": False}); assert r.status_code == 200 and r.json()["sources"][0]["use_in_demo"] is False, r.text; print("source toggle ok")
r = c.get(f"/api/demos/{i}/faq-template"); assert r.status_code == 200 and "# FAQ" in r.text, r.text[:100]; print("faq template ok:", len(r.text), "chars")
u = c.get(f"/api/demos/{i}/usage").json(); print("usage rows", u["rows"], "usd", u["total_usd"])
r = c.post(f"/api/demos/{i}/evals", json={"questions": ["what is the kerb weight?", "how much is the EMI?"]}); assert r.status_code == 200 and len(r.json()["results"]) == 2, r.text; print("evals ok coverage", r.json()["coverage"])
assert c.get(f"/api/demos/{i}/evals").json(), "evals not listed"
r = c.post(f"/api/demos/{i}/run/session", json={"profile": {"name": "Anand"}, "questions": ["kerb weight"], "cta": "Book a test ride", "intent": 61}); assert r.status_code == 200
r = c.post(f"/api/demos/{i}/feedback", json={"message": "say the warranty before the price", "context": {"segment": "x"}}); assert r.status_code == 200, r.text; print("feedback reply:", r.json()["reply"][:60])
reh = c.get(f"/api/demos/{i}").json()["rehearsal"]; print("rehearsal coverage", reh and reh.get("coverage"), "gaps", reh and len(reh.get("gaps", [])), "scorecard", reh and reh.get("scorecard") and reh["scorecard"].get("total"))
b2 = c.get(f"/api/demos/{i}/bundle").json(); assert b2.get("pitch") and "language" in b2, "bundle lacks pitch/language"; assert "fillers" in b2 and "faq" in b2 and b2.get("timeline"), "bundle lacks fillers/faq/timeline"; assert b2.get("intro_video") and b2["intro_video"]["enabled"], "intro film missing from bundle"; assert b2["fillers"].get("before_video", {}).get("audio") and b2["fillers"].get("after_video", {}).get("audio"), "film handoff audio missing"; assert not any(v["name"] == "opening.mp4" for v in b2["media"]["videos"]), "intro film leaked into the media pool"; r = c.patch(f"/api/demos/{i}", json={"settings": {"intro_video": "off"}}); assert r.status_code == 200; print("fillers", len(b2["fillers"]), "faq", len(b2["faq"]), "timeline", b2["timeline"]["total_seconds"]); roles = [s["role"] for s in b2["segments"]]; print("roles", roles)
print("SMOKE OK", i)
# --- settings, multi-language, observability (added 2026-09-03) ---
r = c.patch(f"/api/demos/{i}", json={"settings": {"audience": "everyday", "languages": ["en-IN", "hi-IN"], "pitch_minutes": 3}}); assert r.status_code == 200, r.text
st = c.get(f"/api/demos/{i}").json()["demo"]["settings"]; assert st["languages"] == ["en-IN", "hi-IN"] and st["language"] == "en-IN" and st["audience"] == "everyday", st; print("settings ok", st["languages"], st["audience"])
r = c.post(f"/api/demos/{i}/build"); assert r.status_code == 200, r.text
wait(i, "ready", 180)
b3 = c.get(f"/api/demos/{i}/bundle").json(); assert b3.get("languages") == ["en-IN", "hi-IN"] and "hi-IN" in b3.get("alt_languages", {}), b3.get("languages"); alt = b3["alt_languages"]["hi-IN"]
assert len(alt["segments"]) == len(b3["segments"]) and alt["segments"][0]["lines"][0]["text"].startswith("[hi-IN]"), alt["segments"][0]["lines"][0]; assert alt["segments"][0]["lines"][0]["audio"], "no hi-IN audio"; assert alt.get("slides") and alt["slides"][1]["title"].startswith("[hi-IN]") and alt["slides"][1]["lines"][0]["text"].startswith("[hi-IN]") and alt["slides"][1]["lines"][0]["audio"], "hi-IN slides missing title/text/audio"; print("multi-language bundle ok: hi-IN", len(alt["segments"]), "segments, audio", bool(alt["segments"][0]["lines"][0]["audio"]))
r = c.post(f"/api/demos/{i}/run/tts", json={"text": "नमस्ते", "language": "hi-IN"}); assert r.status_code == 200 and r.json()["url"], r.text; print("tts with language ok")
tr = c.get(f"/api/demos/{i}/trace").json(); assert "stages" in tr and "rows" in tr and "usage" in tr, tr.keys(); assert any(v.get("seconds") is not None for v in tr["stages"].values()), tr["stages"]; print("trace ok: stages", {k: v.get("seconds") for k, v in tr["stages"].items()}, "rows", len(tr["rows"]))
from server.agents import author
und = store.read_json(i, "understanding.json"); bad = {"segments": [{"id": "s1", "role": "intro", "title": "t", "topic": "t", "lines": [{"id": "l1", "text": "It has a 3.4 kWh battery and 15A charging with IDC range.", "fact_ids": [], "visual": None, "card": "none"}], "checkin": "", "deeper": []}], "closing": [], "intake_q1": "", "intake_q2": ""}
iss = author.validate(bad, und, "everyday"); assert any("jargon" in x.lower() or "kwh" in x.lower() for x in iss), iss; print("jargon check ok:", iss[:2])
print("SMOKE OK (phase 2)", i)
