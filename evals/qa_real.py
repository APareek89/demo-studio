"""Paid QA: build real demos against the running server (default http://127.0.0.1:8877) and report
stage-wise latency and cost from the trace. Usage:
  .venv/bin/python evals/qa_real.py images            # images-only demo
  .venv/bin/python evals/qa_real.py video             # dummy video + images
  .venv/bin/python evals/qa_real.py images --lang hi-IN   # add a second language
Writes docs/qa/<demo_id>.md and prints it."""
import json
import os
import sys
import time
import urllib.request

BASE = os.getenv("DEMO_STUDIO_URL", "http://127.0.0.1:8877")
mode = sys.argv[1] if len(sys.argv) > 1 else "images"
extra_lang = sys.argv[sys.argv.index("--lang") + 1] if "--lang" in sys.argv else None


def api(method, path, body=None, files=None, data=None):
    if files or data:
        import mimetypes
        import uuid
        boundary = uuid.uuid4().hex
        parts = []
        for k, v in (data or {}).items():
            parts.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n{v}\r\n".encode())
        for k, (fn, blob, mime) in files or []:
            parts.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"{k}\"; filename=\"{fn}\"\r\nContent-Type: {mime or mimetypes.guess_type(fn)[0] or 'application/octet-stream'}\r\n\r\n".encode() + blob + b"\r\n")
        parts.append(f"--{boundary}--\r\n".encode())
        req = urllib.request.Request(BASE + path, data=b"".join(parts), method=method, headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
    else:
        req = urllib.request.Request(BASE + path, data=json.dumps(body).encode() if body is not None else None, method=method, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=600) as r:
        return json.loads(r.read().decode())


def wait(i, want, secs):
    t0 = time.time()
    last = ""
    while time.time() - t0 < secs:
        d = api("GET", f"/api/demos/{i}")["demo"]
        if d["status"] != last:
            print(f"  status → {d['status']} ({time.time() - t0:.0f}s)", flush=True)
            last = d["status"]
        if d["status"] == want:
            return d
        if d["status"] == "error":
            raise SystemExit("stage error: " + json.dumps({k: v.get("error") for k, v in d["stages"].items() if v.get("error")}))
        time.sleep(3)
    raise SystemExit(f"timeout waiting for {want}")


t_all = time.time()
name = f"QA {mode}" + (f" +{extra_lang}" if extra_lang else "") + " " + time.strftime("%H:%M")
d = api("POST", "/api/demos", {"name": name, "url": "https://www.tvsmotor.com/electric-scooters/tvs-iqube"})
i = d["id"]
print("demo", i, name)
settings = {"audience": "everyday", "pitch_minutes": 3}
if extra_lang:
    settings["languages"] = ["en-IN", extra_lang]
api("PATCH", f"/api/demos/{i}", {"settings": settings})
imgs = sorted(os.listdir("samples/iqube"))
api("POST", f"/api/demos/{i}/sources", files=[("files", (n, open(f"samples/iqube/{n}", "rb").read(), "image/webp")) for n in imgs], data={"role": "product"})
if mode == "video":
    api("POST", f"/api/demos/{i}/sources", files=[("files", ("iqube_dummy.mp4", open("samples/iqube_dummy.mp4", "rb").read(), "video/mp4"))], data={"role": "product"})
spec = open("samples/iqube_spec.txt").read() if os.path.exists("samples/iqube_spec.txt") else (
    "TVS iQube (2025) — official spec sheet extract.\nVariants: iQube 2.2 kWh, iQube 3.5 kWh, iQube ST 3.5 kWh, iQube ST 5.3 kWh.\n"
    "IDC range: 2.2 kWh 94 km; 3.5 kWh 145 km; ST 5.3 kWh 212 km (IDC certified, ideal conditions).\n"
    "Real-world range (company stated, mixed city riding): 3.5 kWh about 100 km.\nTop speed: 78 km/h (3.5 kWh), 82 km/h (ST 5.3 kWh).\n"
    "Charging: 0-80% in 4 h 30 min with the standard 950 W charger from a normal 15A home socket (3.5 kWh).\n"
    "Battery warranty: 3 years or 50,000 km, whichever is earlier. Vehicle warranty: 3 years.\n"
    "Boot space: 32 litres under the seat. Motor: 4.4 kW peak hub motor. Kerb weight: 121 kg (3.5 kWh).\n"
    "Ex-showroom price Delhi: iQube 2.2 kWh Rs 99,990; iQube 3.5 kWh Rs 1,24,990; ST 5.3 kWh Rs 1,59,990 (as of the spec sheet date).\n"
    "Water resistance: IP67 battery. Display: 7-inch TFT with navigation, call and music control. Colours: Titanium Grey, Pearl White, Lucid Yellow, Copper Bronze, Walnut Brown, Starlight Blue, Coral Sand.\n"
    "Service: 11 free service visits in first 3 years. Roadside assistance included for 3 years.")
api("POST", f"/api/demos/{i}/sources", data={"role": "catalogue", "text": spec})
api("POST", f"/api/demos/{i}/sources", data={"role": "brand", "text": "Warm, direct, honest. Never say 'cheapest'. Say 'TVS iQube', never 'the iQube'."})
t0 = time.time()
api("POST", f"/api/demos/{i}/read")
wait(i, "align", 900)
t_read = time.time() - t0
for card in ("visuals", "facts", "pitch", "persona", "ctas"):
    api("POST", f"/api/demos/{i}/approve/{card}")
t0 = time.time()
api("POST", f"/api/demos/{i}/build")
wait(i, "ready", 1800)
t_build = time.time() - t0
b = api("GET", f"/api/demos/{i}/bundle")

# runtime probes
runtime = []
for q in ["How long will one charge last for my 15 km office commute?", "What is the kerb weight?", "Can you give me a discount on the price?", "How does it compare with the Ather 450X?"]:
    t0 = time.time()
    r = api("POST", f"/api/demos/{i}/run/qa", {"question": q, "history": [], "profile": {"name": "Anand", "why": "15 km daily commute, tired of petrol", "language": "en-IN"}})
    runtime.append((q, round(time.time() - t0, 1), r.get("answered"), (r.get("answer") or "")[:160], r.get("fact_ids")))
t0 = time.time()
p = api("POST", f"/api/demos/{i}/run/pitch", {"profile": {"name": "Anand", "why": "15 km daily commute, tired of petrol, worried about charging at home", "focus": []}, "refine": False})
t_pitch = round(time.time() - t0, 1)
tr = api("GET", f"/api/demos/{i}/trace?limit=1000")
u = tr["usage"]
by_stage = {}
for r in tr["rows"]:
    s = by_stage.setdefault(r["stage"], {"calls": 0, "ms": 0, "usd": 0.0, "in": 0, "out": 0})
    s["calls"] += 1; s["ms"] += r["latency_ms"]; s["usd"] += r.get("usd", 0); s["in"] += r["in"]; s["out"] += r["out"]
words = sum(len(l["text"].split()) for s in b["segments"] for l in s["lines"]) + sum(len(l["text"].split()) for l in b["closing"])
route_words = sum(len(l["text"].split()) for s in b["segments"] if s["role"] in ("intro", "outcome") for l in s["lines"])
lines = [f"# QA run — {name}", "", f"- demo: `{i}` · mode: **{mode}** · languages: {b.get('languages')} · audience: everyday", f"- sources: {len(imgs)} images" + (" + 1 dummy video (20 s, 720p)" if mode == "video" else "") + " + spec text + brand note",
         f"- wall clock: read {t_read:.0f}s · build {t_build:.0f}s · total {time.time() - t_all:.0f}s", f"- script: {len(b['segments'])} segments, {words} spoken words total (opening {route_words} words); roles {[s['role'] for s in b['segments']]}",
         f"- voice: {b['voice']['provider']} / {b['voice']['name']}; audio lines {sum(1 for s in b['segments'] for l in s['lines'] if l['audio'])}/{sum(len(s['lines']) for s in b['segments'])}",
         f"- cost: **${u['total_usd']:.3f}** (≈ ₹{u['total_inr']:.0f}) over {u['rows']} calls", "", "## Stage timings (orchestrator wall clock)", "", "| stage | seconds | status |", "|---|---|---|"]
for k, v in tr["stages"].items():
    lines.append(f"| {k} | {v.get('seconds', '—')} | {v.get('status')} |")
lines += ["", "## Calls by stage (from trace)", "", "| stage | calls | latency total | tokens in / out | cost |", "|---|---|---|---|---|"]
for k, v in by_stage.items():
    lines.append(f"| {k} | {v['calls']} | {v['ms'] / 1000:.1f}s | {v['in']:,} / {v['out']:,} | ${v['usd']:.4f} |")
lines += ["", "## Calls by model", "", "| model | calls | in / out | cost |", "|---|---|---|---|"]
for k, v in u["by_model"].items():
    lines.append(f"| {k} | {v['calls']} | {v['in']:,} / {v['out']:,}" + (f" · {v['chars']:,} chars" if v.get("chars") else "") + f" | ${v['usd']:.4f} |")
lines += ["", "## Runtime probes", "", "| question | s | answered | answer | facts |", "|---|---|---|---|---|"]
for q, s, a, ans, f in runtime:
    lines.append(f"| {q} | {s} | {a} | {ans.replace('|', '/')} | {f} |")
lines += ["", f"Pitch planner: {t_pitch}s → state `{p.get('customer_state')}`, route {[s['segment_id'] for s in p.get('route', [])]}", "", "## Opening script (what every customer hears first)", ""]
for s in b["segments"]:
    if s["role"] in ("intro", "outcome"):
        for l in s["lines"]:
            lines.append(f"- **{s['role']}** · {l['text']}")
lines += ["", "## More-features block", ""]
for s in b["segments"]:
    if s["role"] == "features":
        for l in s["lines"]:
            lines.append(f"- {l['text']}")
os.makedirs("docs/qa", exist_ok=True)
open(f"docs/qa/{i}.md", "w").write("\n".join(lines) + "\n")
print("\n".join(lines))
print("REPORT docs/qa/" + i + ".md")
