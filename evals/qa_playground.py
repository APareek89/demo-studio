"""Paid QA of the Playground against EXISTING demos (never creates demos, never triggers a rebuild).
Exercises the same routes the Playground tab calls: ask (/run/qa), evals (typed questions → /evals), cost (/usage),
plus the eval listing. Writes docs/qa/playground-<date>.md. Usage: .venv/bin/python evals/qa_playground.py dm_a dm_b …"""
import json
import os
import sys
import time
import urllib.request

BASE = os.getenv("DEMO_STUDIO_URL", "http://127.0.0.1:8877")
ids = [a for a in sys.argv[1:] if a.startswith("dm_")]
if not ids:
    raise SystemExit("give demo ids")


def api(method, path, body=None):
    req = urllib.request.Request(BASE + path, data=json.dumps(body).encode() if body is not None else None, method=method, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=600) as r:
        return json.loads(r.read().decode())


lines = [f"# Playground QA — {time.strftime('%Y-%m-%d %H:%M')}", "", "Existing demos only; no demo was created or rebuilt. Same routes the Playground tab calls.", ""]
total_usd_before = {}
for i in ids:
    d = api("GET", f"/api/demos/{i}")["demo"]
    u0 = api("GET", f"/api/demos/{i}/usage")
    total_usd_before[i] = u0["total_usd"]
    lines += [f"## {d['name']} (`{i}`) — status {d['status']}, v{d.get('version')}", "", f"- cost panel before: ${u0['total_usd']:.3f} over {u0['rows']} rows; stages {sorted(u0['by_stage'].keys())}; per-session {u0.get('per_session_usd')}"]
    if d["status"] != "ready":
        lines.append("- skipped ask/evals (demo not ready)")
        continue
    # Ask
    for q in ["What is the battery warranty?", "How much does a home charger cost?"]:
        t0 = time.time()
        r = api("POST", f"/api/demos/{i}/run/qa", {"question": q, "history": [], "profile": {"name": "Playground"}})
        lines.append(f"- ask `{q}` → {time.time() - t0:.1f}s · answered={r.get('answered')} · facts={r.get('fact_ids')} · callback={r.get('offer_callback')} · clarifier={bool(r.get('clarifying_question'))}\n  > {(r.get('answer') or '')[:220].replace(chr(10), ' ')}")
    # Evals (typed — 3 questions, 3 paid calls)
    qs = ["What is the on-road price in Pune?", "Is the battery waterproof?", "Can I get a test ride this weekend?"]
    t0 = time.time()
    ev = api("POST", f"/api/demos/{i}/evals", {"questions": qs})
    lines.append(f"- evals ({len(qs)} typed) → {time.time() - t0:.1f}s · coverage {ev.get('coverage')} · id {ev.get('id')}")
    for r in ev.get("results", []):
        lines.append(f"  - {'✅' if r.get('answered') else '❌'} {r.get('question')} → facts {r.get('fact_ids')} · {(r.get('answer') or '')[:120].replace(chr(10), ' ')}")
    listed = api("GET", f"/api/demos/{i}/evals")
    lines.append(f"- eval runs listed: {len(listed)} (latest {listed[0].get('id') if listed else None})")
    u1 = api("GET", f"/api/demos/{i}/usage")
    lines.append(f"- cost panel after: ${u1['total_usd']:.3f} (+${u1['total_usd'] - u0['total_usd']:.3f} for this QA) · runtime rows {u1['by_stage'].get('runtime', {}).get('calls')}")
    lines.append("")
lines += ["## Not exercised", "", "- Refine (POST /feedback) — it hands the message to the align agent, which may rewrite the script and rebuild the demo; not run on your demos without asking.", ""]
os.makedirs("docs/qa", exist_ok=True)
out = f"docs/qa/playground-{time.strftime('%Y-%m-%d')}.md"
open(out, "w").write("\n".join(lines) + "\n")
print("\n".join(lines))
print("REPORT", out)
