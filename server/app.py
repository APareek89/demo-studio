"""Demo Studio — FastAPI app. Run:  .venv/bin/uvicorn server.app:app --port 8877 --reload"""
from __future__ import annotations

import asyncio
import json
import re
import time
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles

from . import cloud, config, events, graph, orchestrator, schemas, store, usage, runlog
from .agents import align, author, deck, faq, pitch, qa, rehearsal, visuals, voice
from .llm import sarvam

app = FastAPI(title="Demo Studio", version="0.1.0")


def _demo_or_404(demo_id: str) -> dict:
    if not store.exists(demo_id) and cloud.enabled() and cloud.restore_demo(demo_id):
        pass  # restored the JSON artefacts from S3; media loads on demand
    try:
        return store.load(demo_id)
    except KeyError:
        raise HTTPException(404, "demo not found")


# ---------- pages & media ----------

@app.get("/")
def index():
    return FileResponse(config.WEB_DIR / "index.html")


@app.get("/media/{demo_id}/{rel:path}")
def media(demo_id: str, rel: str):
    try:
        p = store.media_path(demo_id, rel)
    except KeyError:
        raise HTTPException(404)
    if (not p.exists() or not p.is_file()) and cloud.enabled():
        cloud.fetch_file(demo_id, rel)
    if not p.exists() or not p.is_file():
        raise HTTPException(404)
    return FileResponse(p)


# ---------- demos ----------

@app.get("/api/health")
def health():
    return {**config.health(), "cloud": cloud.status() if cloud.enabled() or True else {}}


@app.get("/api/cloud")
def cloud_status():
    """Where the demos are mirrored: account, region, bucket, tables — never a key."""
    cloud.enabled()
    return cloud.status()


@app.post("/api/cloud/setup")
def cloud_setup():
    """Create the private bucket and the two on-demand tables if missing (idempotent)."""
    if not cloud.enabled():
        raise HTTPException(400, cloud.status().get("why", "cloud not connected"))
    notes = []
    cloud.ensure_resources(notes.append)
    return {"status": cloud.status(), "notes": notes}


@app.post("/api/demos/{demo_id}/sync")
def sync_demo(demo_id: str):
    _demo_or_404(demo_id)
    if not cloud.enabled():
        raise HTTPException(400, cloud.status().get("why", "cloud not connected"))
    notes = []
    cloud.sync_demo(demo_id, notes.append)
    return {"notes": notes, "events": cloud.list_events(demo_id, limit=10)}


@app.get("/api/demos")
def list_demos():
    local = store.list_demos()
    seen = {d["id"] for d in local}
    out = [{**d, "location": "local+cloud" if cloud.enabled() else "local"} for d in local]
    for c in cloud.list_cloud_demos():
        if c.get("demo_id") in seen:
            continue
        out.append({"id": c["demo_id"], "name": c.get("name"), "status": c.get("status"), "version": c.get("version", 0), "created_at": c.get("created_at"), "updated_at": c.get("updated_at"),
                    "sources": len(c.get("sources", [])), "location": "cloud", "approvals": c.get("approvals", {})})
    return out


@app.post("/api/demos")
async def create_demo(req: Request):
    body = await req.json()
    name = (body.get("name") or "").strip()
    demo = store.new_demo(name or "Untitled demo")
    url = (body.get("url") or "").strip()
    if url:
        store.update(demo["id"], lambda d: d["product"].__setitem__("url", url))
        store.add_url_source(demo["id"], url, role="product")
    cloud.sync_demo_async(demo["id"])
    return store.load(demo["id"])


@app.get("/api/demos/{demo_id}")
def get_demo(demo_id: str):
    demo = _demo_or_404(demo_id)
    return {"demo": demo, "cards": align.cards(demo_id) if demo["status"] not in ("sources",) else None,
            "conversation": store.read_json(demo_id, "conversation.json", []), "rehearsal": store.read_json(demo_id, "rehearsal.json"),
            "bundle_ready": store.path(demo_id, "bundle.json").exists(), "running": graph.is_running(demo_id),
            "sessions": _sessions(demo_id), "leads": _leads(demo_id)}


@app.get("/api/demos/{demo_id}/export.mp4")
def export_demo_mp4(demo_id: str):
    _demo_or_404(demo_id)
    raise HTTPException(409, "MP4 export is parked while the player moves to slides with HTML callouts; the exporter will be rebuilt for the deck")


@app.delete("/api/demos/{demo_id}")
def delete_demo(demo_id: str):
    _demo_or_404(demo_id)
    store.delete_demo(demo_id)
    return {"ok": True}


@app.post("/api/demos/{demo_id}/duplicate")
def duplicate(demo_id: str):
    _demo_or_404(demo_id)
    return store.duplicate_demo(demo_id)


@app.patch("/api/demos/{demo_id}")
async def patch_demo(demo_id: str, req: Request):
    _demo_or_404(demo_id)
    body = await req.json()

    def fn(d):
        if "name" in body:
            d["name"] = body["name"].strip() or d["name"]
        if "product" in body:
            d["product"].update({k: v for k, v in body["product"].items() if k in ("name", "category", "url")})
        if "settings" in body:
            allowed = {k: v for k, v in body["settings"].items() if k in ("tts_provider", "voice_name", "sarvam_speaker", "language", "languages", "rehearsal_questions", "competition", "audience", "pitch_minutes", "enhance_images", "faq_questions", "intro_video")}
            if "languages" in allowed:
                allowed["languages"] = [x for x in allowed["languages"] if isinstance(x, str)][:6] or ["en-IN"]
                allowed["language"] = allowed["languages"][0]
            d["settings"].update(allowed)
            if "voice_name" in allowed or "sarvam_speaker" in allowed:
                d["settings"]["voice_locked"] = True
            runlog.settings_changed(demo_id, allowed)
    out = store.update(demo_id, fn)
    cloud.sync_demo_async(demo_id)
    return out


# ---------- sources ----------

@app.post("/api/demos/{demo_id}/sources")
async def add_sources(demo_id: str, files: list[UploadFile] = File(default=[]), role: str = Form(default="product"),
                      url: str = Form(default=""), text: str = Form(default=""), text_name: str = Form(default="brand-guidelines")):
    _demo_or_404(demo_id)
    added = []
    for f in files:
        data = await f.read()
        if not data:
            raise HTTPException(400, f"{f.filename} is empty (0 bytes) — export it again and re-upload")
        if len(data) > config.MAX_UPLOAD_MB * 1024 * 1024:
            raise HTTPException(413, f"{f.filename} is larger than {config.MAX_UPLOAD_MB} MB")
        try:
            added.append(store.add_file_source(demo_id, f.filename or "file", data, role))
        except ValueError as e:
            raise HTTPException(400, str(e))
    if role == "hero" and added:  # one hero at a time: the previous hero stays a normal product image
        keep = added[-1]["id"]
        store.update(demo_id, lambda d: [s.__setitem__("role", "product") for s in d["sources"] if s.get("role") == "hero" and s["id"] != keep])
    runlog.sources_added(demo_id, added)
    cloud.sync_demo_async(demo_id)
    if url.strip():
        u = url.strip()
        if not u.startswith("http"):
            u = "https://" + u
        added.append(store.add_url_source(demo_id, u, role))
        if role == "product":
            store.update(demo_id, lambda d: d["product"].__setitem__("url", u))
    if text.strip():
        added.append(store.add_text_source(demo_id, text_name, text, role))
    return {"added": added, "sources": store.load(demo_id)["sources"]}


@app.patch("/api/demos/{demo_id}/sources/{source_id}")
async def patch_source(demo_id: str, source_id: str, req: Request):
    _demo_or_404(demo_id)
    body = await req.json()
    return {"sources": store.patch_source(demo_id, source_id, body)["sources"]}


@app.get("/api/demos/{demo_id}/faq-template")
def faq_template(demo_id: str):
    demo = _demo_or_404(demo_id)
    und = store.read_json(demo_id, "understanding.json") or {}
    reh = store.read_json(demo_id, "rehearsal.json") or {}
    groups: dict[str, list] = {}
    for u in und.get("unknowns", []):
        if u.get("status", "open") == "open":
            if not u.get("category") or (u.get("category") == "other" and not u.get("suggested_document")):
                u = {**u, "category": qa.classify(u["question"])[0], "suggested_document": qa.classify(u["question"])[1]}
            groups.setdefault(u.get("category", "other"), []).append(u)
    order = ["pricing", "finance", "insurance", "warranty_service", "features", "availability", "comparison", "usage", "other"]
    titles = {"pricing": "Pricing & offers", "finance": "Finance / EMI", "insurance": "Insurance", "warranty_service": "Warranty & service", "features": "Features & specs", "availability": "Availability & delivery", "comparison": "Comparisons", "usage": "Usage & ownership", "other": "Other"}
    lines = [f"# FAQ — {demo['name']}", "", "Fill in the answers below (only what is true and current), save as FAQ.md, and upload it on the Facts card.", "The guide will then answer these questions with a citation to this document.", ""]
    for cat in order:
        if cat not in groups:
            continue
        lines.append(f"## {titles[cat]}")
        docs = sorted({u.get("suggested_document", "") for u in groups[cat] if u.get("suggested_document")})
        if docs:
            lines.append("_Documents that would answer these: " + "; ".join(docs) + "_")
        lines.append("")
        for u in groups[cat]:
            tag = "  \n_(asked " + str(u.get("origin")) + ")_" if u.get("origin") in ("runtime", "rehearsal") else ""
            lines.append("**Q: " + u["question"] + "**" + tag)
            lines.append("A: ")
            lines.append("")
    gaps = [g for g in reh.get("gaps", []) if not any(g.strip().lower() == u["question"].strip().lower() for u in und.get("unknowns", []))]
    if gaps:
        lines.append("## Asked in rehearsal, unanswered")
        for g in gaps:
            lines += ["**Q: " + g + "**", "A: ", ""]
    from fastapi.responses import Response
    return Response("\n".join(lines), media_type="text/markdown", headers={"Content-Disposition": "attachment; filename=FAQ-" + demo_id + ".md"})


@app.get("/api/demos/{demo_id}/usage")
def get_usage(demo_id: str):
    _demo_or_404(demo_id)
    return usage.summary(demo_id)


@app.get("/api/demos/{demo_id}/runlog")
def get_runlog(demo_id: str):
    """The human-readable end-to-end log (data/demos/<id>/RUN.md). Backfilled from disk if it does not exist yet."""
    _demo_or_404(demo_id)
    p = store.path(demo_id, runlog.FILE)
    if not p.exists():
        runlog.backfill(demo_id)
    return Response(p.read_text(encoding="utf-8"), media_type="text/markdown; charset=utf-8")


@app.get("/api/workflow")
def workflow():
    """The LangGraph workflow as Mermaid, plus which demos are parked at the Align checkpoint."""
    return {"mermaid": graph.mermaid(), "waiting": [d["id"] for d in store.list_demos() if graph.is_waiting(d["id"])], "running": [d["id"] for d in store.list_demos() if graph.is_running(d["id"])]}


@app.get("/api/demos/{demo_id}/trace")
def get_trace(demo_id: str, limit: int = 300):
    demo = _demo_or_404(demo_id)
    return {"stages": demo.get("stages", {}), "rows": usage.traces(demo_id, limit), "usage": usage.summary(demo_id)}


@app.get("/api/demos/{demo_id}/evals")
def list_evals(demo_id: str):
    _demo_or_404(demo_id)
    out = []
    d = store.path(demo_id, "evals")
    if d.exists():
        for p in sorted(d.glob("*.json"), reverse=True)[:20]:
            try:
                e = json.loads(p.read_text())
                out.append({"id": e.get("id"), "at": e.get("at"), "n": len(e.get("results", [])), "coverage": e.get("coverage"), "label": e.get("label", "")})
            except Exception:
                pass
    return out


@app.post("/api/demos/{demo_id}/evals")
async def run_evals(demo_id: str, req: Request):
    _demo_or_404(demo_id)
    usage.current_demo.set(demo_id)
    usage.current_stage.set("evals")
    body = await req.json()
    questions = [q.strip() for q in (body.get("questions") or []) if q and q.strip()][:40]
    if not questions and body.get("generate"):
        try:
            questions = rehearsal.generate_questions(demo_id, int(body.get("n") or 12))
        except RuntimeError as e:
            raise HTTPException(502, str(e))
    if not questions:
        raise HTTPException(400, "give questions, or set generate=true")
    results = []
    for q in questions:
        try:
            r = qa.answer(demo_id, q, [], body.get("profile") or None, live=True)
            results.append({"question": q, "answered": r["answered"], "fact_ids": r["fact_ids"], "answer": r["answer"], "escalate": r["escalate"], "clarifying_question": r.get("clarifying_question", "")})
        except Exception as e:
            results.append({"question": q, "answered": False, "fact_ids": [], "answer": "", "escalate": "error: " + str(e)[:120]})
    cov = round(sum(1 for r in results if r["answered"]) / max(1, len(results)), 2)
    ev = {"id": "ev_" + str(int(time.time())), "at": time.time(), "label": body.get("label", ""), "results": results, "coverage": cov}
    store.write_json(demo_id, "evals/" + ev["id"] + ".json", ev)
    return ev


@app.delete("/api/demos/{demo_id}/sources/{source_id}")
def remove_source(demo_id: str, source_id: str):
    _demo_or_404(demo_id)
    store.remove_source(demo_id, source_id)
    return {"sources": store.load(demo_id)["sources"]}


@app.post("/api/demos/{demo_id}/read")
def read_sources(demo_id: str):
    demo = _demo_or_404(demo_id)
    if not demo["sources"]:
        raise HTTPException(400, "Add at least one source first")
    if not config.ANTHROPIC_API_KEY and not config.MOCK_LLM:
        raise HTTPException(400, "ANTHROPIC_API_KEY missing in .env")
    if any(s["kind"] in ("video", "image") for s in demo["sources"]) and not config.GEMINI_API_KEY and not config.MOCK_LLM:
        raise HTTPException(400, "GEMINI_API_KEY missing in .env (needed for video/images)")
    try:
        graph.start_read(demo_id)
    except RuntimeError as e:
        raise HTTPException(409, str(e))
    return {"ok": True}


# ---------- events (SSE) ----------

@app.get("/api/demos/{demo_id}/events")
async def sse(demo_id: str, since: int = 0):
    _demo_or_404(demo_id)

    async def gen():
        seq = since
        last_beat = time.time()
        yield f"event: hello\ndata: {json.dumps({'seq': events.latest_seq(demo_id)})}\n\n"
        while True:
            evs = events.since(demo_id, seq)
            for ev in evs:
                seq = ev["seq"]
                yield f"id: {seq}\nevent: {ev['type']}\ndata: {json.dumps(ev)}\n\n"
            if time.time() - last_beat > 15:
                last_beat = time.time()
                yield ": keepalive\n\n"
            await asyncio.sleep(0.35)

    return StreamingResponse(gen(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


# ---------- align ----------

@app.post("/api/demos/{demo_id}/align")
async def align_message(demo_id: str, message: str = Form(default=""), files: list[UploadFile] = File(default=[]),
                        context: str = Form(default="align")):
    _demo_or_404(demo_id)
    attachments = []
    for f in files:
        data = await f.read()
        try:
            attachments.append(store.add_file_source(demo_id, f.filename or "file", data, "product"))
        except ValueError as e:
            raise HTTPException(400, str(e))
    if not message.strip() and not attachments:
        raise HTTPException(400, "Say something or attach a file")
    try:
        out = graph.handle_message(demo_id, message, attachments, context)
    except RuntimeError as e:
        raise HTTPException(409, str(e))
    return out


@app.post("/api/demos/{demo_id}/approve/{card}")
def approve(demo_id: str, card: str):
    demo = _demo_or_404(demo_id)
    if card not in store.CARDS:
        raise HTTPException(400, "unknown card")
    notes = orchestrator.apply_actions(demo_id, [{"type": "approve", "card": card}], [], "align")
    cloud.sync_demo_async(demo_id)
    return {"approvals": store.load(demo_id)["approvals"], "notes": notes}


@app.post("/api/demos/{demo_id}/unapprove/{card}")
def unapprove(demo_id: str, card: str):
    _demo_or_404(demo_id)
    if card not in store.CARDS:
        raise HTTPException(400, "unknown card")
    out = store.update(demo_id, lambda d: d["approvals"].__setitem__(card, False))["approvals"]
    cloud.sync_demo_async(demo_id)
    return out


@app.patch("/api/demos/{demo_id}/align/facts/{fact_id}")
async def edit_aligned_fact(demo_id: str, fact_id: str, req: Request):
    """Direct, human-authored correction. Downstream script/FAQ must be reviewed again."""
    _demo_or_404(demo_id)
    body = await req.json()
    value = (body.get("value") or "").strip()
    claim = (body.get("claim") or "").strip()
    if not value:
        raise HTTPException(400, "A fact value is required")
    und = store.read_json(demo_id, "understanding.json") or {}
    fact = next((f for f in und.get("facts", []) if f.get("id") == fact_id), None)
    if not fact:
        raise HTTPException(404, "fact not found")
    fact["value"] = value[:1000]
    if claim:
        fact["claim"] = claim[:500]
    if "conditions" in body:
        fact["conditions"] = (body.get("conditions") or "").strip()[:1000]
    fact["edited"] = True
    fact["source"] = {**fact.get("source", {}), "locator": (fact.get("source", {}).get("locator", "") + " · edited by user").strip(" ·")}
    store.write_json(demo_id, "understanding.json", und)
    orchestrator.invalidate(demo_id, "understand")
    orchestrator.set_stage(demo_id, "understand", "done", message="direct fact edit saved and validated")
    store.update(demo_id, lambda d: d["approvals"].update({key: False for key in store.CARDS}))
    runlog.event(demo_id, f"Fact {fact_id} edited directly", "Script, visuals and FAQ require re-approval before build.")
    return {"ok": True, "cards": align.cards(demo_id), "approvals": store.load(demo_id)["approvals"]}


@app.post("/api/demos/{demo_id}/align/facts/{fact_id}/approval")
async def set_aligned_fact_approval(demo_id: str, fact_id: str, req: Request):
    """Explicitly reject or restore a questionable extracted fact from the Align UI."""
    _demo_or_404(demo_id)
    approved = bool((await req.json()).get("approved"))
    und = store.read_json(demo_id, "understanding.json") or {}
    fact = next((f for f in und.get("facts", []) if f.get("id") == fact_id), None)
    if not fact:
        raise HTTPException(404, "fact not found")
    fact["approved"] = approved
    store.write_json(demo_id, "understanding.json", und)
    orchestrator.invalidate(demo_id, "understand")
    orchestrator.set_stage(demo_id, "understand", "done", message="fact approval reviewed directly")
    orchestrator.set_stage(demo_id, "faq", "stale", message="fact approval changed — bank re-answers on the next build")
    store.update(demo_id, lambda d: d["approvals"].update({key: False for key in store.CARDS}))
    runlog.event(demo_id, f"Fact {fact_id} {'restored' if approved else 'rejected'} directly", "Script, visuals and FAQ require review again.")
    return {"ok": True, "cards": align.cards(demo_id), "approvals": store.load(demo_id)["approvals"]}


@app.patch("/api/demos/{demo_id}/align/product")
async def edit_aligned_product(demo_id: str, req: Request):
    """Direct correction for the extracted product framing shown across the demo."""
    _demo_or_404(demo_id)
    body = await req.json()
    allowed = {"name", "category", "summary", "audience"}
    if not isinstance(body, dict) or not body or set(body) - allowed:
        raise HTTPException(400, "Only name, category, summary and audience may be changed")
    und = store.read_json(demo_id, "understanding.json") or {}
    product = dict(und.get("product") or {})
    for key, value in body.items():
        text = str(value or "").strip()
        if not text or len(text) > 2000:
            raise HTTPException(400, f"{key} needs 1–2000 characters")
        product[key] = text
    und["product"] = product
    store.write_json(demo_id, "understanding.json", und)
    orchestrator.invalidate(demo_id, "understand")
    orchestrator.set_stage(demo_id, "understand", "done", message="product framing edited directly")
    store.update(demo_id, lambda d: d["approvals"].update({key: False for key in store.CARDS}))
    runlog.event(demo_id, "Product framing edited directly", "Every downstream card requires review.")
    return {"ok": True, "cards": align.cards(demo_id), "approvals": store.load(demo_id)["approvals"]}


@app.patch("/api/demos/{demo_id}/align/script")
async def edit_aligned_script(demo_id: str, req: Request):
    """Save explicit line edits, validate grounding, then re-run visual alignment."""
    demo = _demo_or_404(demo_id)
    body = await req.json()
    edits = body.get("lines") or []
    if not isinstance(edits, list) or not edits or len(edits) > 200:
        raise HTTPException(400, "Send between 1 and 200 script line edits")
    requested = {str(x.get("id")): x for x in edits if isinstance(x, dict) and x.get("id")}
    if len(requested) != len(edits):
        raise HTTPException(400, "Every script edit needs a line id")
    for edit in requested.values():
        if not any(key in edit for key in ("text", "fact_ids", "visual_ref")):
            raise HTTPException(400, "Each script edit must change text, fact ids or the visual ref")
        if "text" in edit and (not (edit.get("text") or "").strip() or len((edit.get("text") or "").strip()) > 1200):
            raise HTTPException(400, "Every edited line needs 1–1200 characters")
        if "fact_ids" in edit and (not isinstance(edit.get("fact_ids"), list) or len(edit["fact_ids"]) > 30):
            raise HTTPException(400, "fact_ids must be a list of at most 30 fact ids")
    script = store.read_json(demo_id, "script.json") or {}
    und = store.read_json(demo_id, "understanding.json") or {}
    approved_fact_ids = {f.get("id") for f in und.get("facts", []) if f.get("approved", True)}
    cited = {str(fid) for edit in requested.values() for fid in edit.get("fact_ids", [])}
    if cited - approved_fact_ids:
        raise HTTPException(400, "Rejected or unknown fact ids cannot be attached: " + ", ".join(sorted(cited - approved_fact_ids)))
    allowed_visual_refs = {x.get("id") for x in [*und.get("shots", []), *und.get("images", [])] if x.get("_allowed", True)}
    visual_refs = {str(edit.get("visual_ref") or "") for edit in requested.values() if "visual_ref" in edit}
    if (visual_refs - {""}) - allowed_visual_refs:
        raise HTTPException(400, "Unknown or excluded visual refs cannot be attached: " + ", ".join(sorted((visual_refs - {""}) - allowed_visual_refs)))
    found = set()
    for seg in script.get("segments", []):
        for line in [*(seg.get("lines") or []), *(seg.get("deeper") or [])]:
            if line.get("id") in requested:
                edit = requested[line["id"]]
                if "text" in edit:
                    line["text"] = (edit.get("text") or "").strip()
                    line.pop("audio", None)
                if "fact_ids" in edit:
                    line["fact_ids"] = [str(x) for x in edit["fact_ids"]]
                if "visual_ref" in edit:
                    line["visual"] = ({"kind": "image" if str(edit["visual_ref"]).startswith("im") else "shot", "ref": str(edit["visual_ref"]), "focus": (line.get("visual") or {}).get("focus", "")} if edit.get("visual_ref") else {"kind": "none", "ref": "", "focus": ""})
                found.add(line["id"])
    for line in script.get("closing", []):
        if line.get("id") in requested:
            edit = requested[line["id"]]
            if "text" in edit:
                line["text"] = (edit.get("text") or "").strip()
                line.pop("audio", None)
            if "fact_ids" in edit:
                line["fact_ids"] = [str(x) for x in edit["fact_ids"]]
            if "visual_ref" in edit:
                line["visual"] = ({"kind": "image" if str(edit["visual_ref"]).startswith("im") else "shot", "ref": str(edit["visual_ref"]), "focus": (line.get("visual") or {}).get("focus", "")} if edit.get("visual_ref") else {"kind": "none", "ref": "", "focus": ""})
            found.add(line["id"])
    missing = set(requested) - found
    if missing:
        raise HTTPException(404, "script line not found: " + ", ".join(sorted(missing)))
    issues = author.validate(script, und, demo.get("settings", {}).get("audience", "everyday"))
    invalid = [line.get("id") for seg in script.get("segments", []) for line in [*(seg.get("lines") or []), *(seg.get("deeper") or [])] if line.get("id") in requested and line.get("unverified")]
    invalid += [line.get("id") for line in script.get("closing", []) if line.get("id") in requested and line.get("unverified")]
    if invalid:
        raise HTTPException(400, "That edit introduces an uncited claim or figure. Add the information as a source/fact first: " + ", ".join(invalid))
    script["issues"] = issues
    und["image_map"] = visuals.build_map(und, demo)
    store.write_json(demo_id, "understanding.json", und)
    realigned = bool(body.get("realign_visuals", True))
    if realigned:
        script = visuals.align(demo_id, script, und)
    author.timeline(script, demo_id)
    store.write_json(demo_id, "script.json", script)
    orchestrator.invalidate(demo_id, "author")
    orchestrator.set_stage(demo_id, "author", "done", message="direct script edits saved and validated")
    store.update(demo_id, lambda d: d["approvals"].update({"visuals": False, "script": False}))
    runlog.event(demo_id, "Script edited directly", f"{len(found)} line(s) saved; visual alignment {'refreshed' if realigned else 'kept'}; script and visuals require re-approval.")
    return {"ok": True, "cards": align.cards(demo_id), "approvals": store.load(demo_id)["approvals"], "issues": issues}


@app.patch("/api/demos/{demo_id}/align/deck")
async def edit_aligned_deck(demo_id: str, req: Request):
    """Slide review in Align: picture, title, callout text / facts / part, dragged positions. Saved to deck-overrides.json
    (kept over any rebuild) and applied to deck.json now, through the same validator as script lines. No model call."""
    demo = _demo_or_404(demo_id)
    body = await req.json()
    edits = body.get("slides") or []
    if not isinstance(edits, list) or not edits or len(edits) > 60:
        raise HTTPException(400, "Send between 1 and 60 slide edits")
    dk = store.read_json(demo_id, "deck.json") or {}
    if not dk.get("slides"):
        raise HTTPException(409, "No deck yet — configure the demo first")
    und = store.read_json(demo_id, "understanding.json") or {}
    allowed_facts = {f["id"] for f in und.get("facts", []) if f.get("approved", True)}
    images = {i["id"]: i for i in und.get("images", []) if store.visual_allowed(demo, i["source_id"])}
    slides = {s["id"]: s for s in dk["slides"]}
    ov = store.read_json(demo_id, "deck-overrides.json") or {"slides": []}
    ov_by = {o["slide_id"]: o for o in ov.get("slides", []) if o.get("slide_id")}
    for e in edits:
        sid = str(e.get("slide_id") or "")
        s = slides.get(sid)
        if not s:
            raise HTTPException(404, f"slide not found: {sid}")
        o = ov_by.setdefault(sid, {"slide_id": sid, "callouts": []})
        if "image_id" in e:
            if e["image_id"] not in images:
                raise HTTPException(400, f"unknown or excluded picture: {e['image_id']}")
            o["image_id"] = e["image_id"]
        if "title" in e:
            title = (e.get("title") or "").strip()
            if not title or len(title) > 80:
                raise HTTPException(400, "A title needs 1–80 characters")
            o["title"] = title
        oc_by = {c["id"]: c for c in o.get("callouts", []) if c.get("id")}
        for ce in e.get("callouts") or []:
            cid = str(ce.get("id") or "")
            cur = next((c for c in s["callouts"] if c["id"] == cid), None)
            if not cur:
                raise HTTPException(404, f"callout not found: {cid}")
            oc = oc_by.setdefault(cid, {"id": cid})
            if "text" in ce or "fact_ids" in ce:
                text = (ce.get("text") if "text" in ce else oc.get("text", cur["text"])).strip()
                fids = ce.get("fact_ids") if "fact_ids" in ce else oc.get("fact_ids", cur["fact_ids"])
                if not isinstance(fids, list):
                    raise HTTPException(400, "fact_ids must be a list")
                unknown = {str(x) for x in fids} - allowed_facts
                if unknown:
                    raise HTTPException(400, "Rejected or unknown fact ids cannot be attached: " + ", ".join(sorted(unknown)))
                valid, bad = author.ungrounded(text, [str(x) for x in fids], allowed_facts)
                if not text or bad:
                    raise HTTPException(400, "That callout states a figure or claim without a fact id. Add the information as a source/fact first.")
                if author.words(text) > deck.MAX_CALLOUT_WORDS:
                    raise HTTPException(400, f"A callout is at most {deck.MAX_CALLOUT_WORDS} words")
                oc["text"], oc["fact_ids"] = text, valid
            if "part" in ce:
                oc["part"] = (ce.get("part") or "").strip().lower()
            if "label_pos" in ce:
                lp = ce.get("label_pos") or {}
                try:
                    x, y = float(lp.get("x")), float(lp.get("y"))
                except (TypeError, ValueError):
                    raise HTTPException(400, "label_pos needs x and y")
                if not (0 <= x <= 1 and 0 <= y <= 1):
                    raise HTTPException(400, "label_pos is a fraction of the picture, 0–1")
                oc["label_pos"] = {"x": round(x, 4), "y": round(y, 4)}
            if ce.get("placement") in ("overlay", "panel"):
                oc["placement"] = ce["placement"]
        o["callouts"] = list(oc_by.values())
    ov["slides"] = list(ov_by.values())
    store.write_json(demo_id, "deck-overrides.json", ov)
    deck.apply_overrides(dk["slides"], ov, images, allowed_facts)
    schemas.Deck.model_validate(dk)
    store.write_json(demo_id, "deck.json", dk)
    orchestrator.invalidate(demo_id, "deck")
    orchestrator.set_stage(demo_id, "deck", "done", message="slides edited in Align")
    store.update(demo_id, lambda d: d["approvals"].__setitem__("script", False))
    runlog.event(demo_id, "Slides edited in Align", f"{len(edits)} slide(s); the overrides are kept over any rebuild; the Script card requires re-approval.")
    return {"ok": True, "cards": align.cards(demo_id), "approvals": store.load(demo_id)["approvals"]}


@app.patch("/api/demos/{demo_id}/align/plan")
async def edit_aligned_plan(demo_id: str, req: Request):
    """Direct, human-authored pitch correction without another model call."""
    _demo_or_404(demo_id)
    body = await req.json()
    plan = store.read_json(demo_id, "plan.json") or {}
    fields = body.get("fields") or {}
    allowed = {"customer_persona", "decision_frame", "takeaway", "primary_outcome", "supporting_outcomes", "do_not_recommend_if", "advance", "notes"}
    if not isinstance(fields, dict) or set(fields) - allowed:
        raise HTTPException(400, "Only the editable pitch-brief fields may be changed")
    proposed = dict(plan)
    for key, value in fields.items():
        proposed[key] = value.strip() if isinstance(value, str) else value

    replacements = body.get("replacements") or []
    if not isinstance(replacements, list) or len(replacements) > 30:
        raise HTTPException(400, "replacements must be a list of at most 30 items")
    pairs = []
    for item in replacements:
        if not isinstance(item, dict) or not item.get("from") or "to" not in item:
            raise HTTPException(400, "Each replacement needs non-empty 'from' and a 'to' value")
        pairs.append((str(item["from"]), str(item["to"])))

    remove_ids = {str(x) for x in (body.get("remove_fact_ids") or [])}
    def cleanse(value):
        if isinstance(value, str):
            for old, new in pairs:
                value = value.replace(old, new)
            return value
        if isinstance(value, list):
            return [cleanse(x) for x in value]
        if isinstance(value, dict):
            return {k: ([x for x in v if str(x) not in remove_ids] if k == "fact_ids" and isinstance(v, list) else cleanse(v)) for k, v in value.items()}
        return value
    proposed = cleanse(proposed)
    try:
        validated = schemas.Plan.model_validate(proposed).model_dump()
    except Exception as e:
        raise HTTPException(400, "The edited pitch brief is invalid: " + str(e)[:400])
    if plan.get("voice_sample_audio"):
        validated["voice_sample_audio"] = plan["voice_sample_audio"]
    store.write_json(demo_id, "plan.json", validated)
    orchestrator.invalidate(demo_id, "plan")
    orchestrator.set_stage(demo_id, "plan", "done", message="direct pitch edits saved and validated")
    store.update(demo_id, lambda d: d["approvals"].update({key: False for key in store.CARDS}))
    runlog.event(demo_id, "Pitch brief edited directly", f"{len(fields)} field(s), {len(pairs)} replacement(s), {len(remove_ids)} fact id(s) removed; every card requires review.")
    return {"ok": True, "cards": align.cards(demo_id), "approvals": store.load(demo_id)["approvals"]}


@app.post("/api/demos/{demo_id}/ctas")
async def set_ctas(demo_id: str, req: Request):
    _demo_or_404(demo_id)
    body = await req.json()
    ctas = body.get("ctas") or []
    notes = orchestrator.apply_actions(demo_id, [{"type": "set_ctas", "ctas": ctas}], [], "align")
    runlog.event(demo_id, "CTAs saved", "; ".join(f"{c.get('label')} ({c.get('kind')})" for c in ctas))
    return {"ctas": (store.read_json(demo_id, "plan.json") or {}).get("ctas", []), "notes": notes}


@app.post("/api/demos/{demo_id}/build")
def build(demo_id: str):
    _demo_or_404(demo_id)
    try:
        graph.start_build(demo_id)
    except RuntimeError as e:
        raise HTTPException(409, str(e))
    return {"ok": True}


@app.post("/api/demos/{demo_id}/revise")
async def revise(demo_id: str, req: Request):
    _demo_or_404(demo_id)
    body = await req.json()
    stage = body.get("stage")
    if stage not in ("understand", "plan", "author", "deck", "faq"):
        raise HTTPException(400, "stage must be understand | plan | author | deck | faq")
    try:
        graph.start_revise(demo_id, stage, body.get("instruction", ""), bool(body.get("rebuild")))
    except RuntimeError as e:
        raise HTTPException(409, str(e))
    return {"ok": True}


@app.post("/api/demos/{demo_id}/voice/sample")
async def voice_sample(demo_id: str, req: Request):
    _demo_or_404(demo_id)
    body = await req.json()
    text = (body.get("text") or "Hello, I'm your guide for today. Shall we begin?").strip()
    try:
        rel = voice.sample(demo_id, text)
    except Exception as e:
        raise HTTPException(502, str(e)[:300])
    if rel:
        plan = store.read_json(demo_id, "plan.json") or {}
        plan["voice_sample_audio"] = rel
        store.write_json(demo_id, "plan.json", plan)
        store.update(demo_id, lambda d: d["approvals"].__setitem__("persona", False))
    return {"url": f"/media/{demo_id}/{rel}" if rel else None, "provider": voice.provider_for(store.load(demo_id))}


# ---------- runtime ----------

@app.get("/api/demos/{demo_id}/bundle")
def get_bundle(demo_id: str):
    _demo_or_404(demo_id)
    b = store.read_json(demo_id, "bundle.json")
    if not b:
        raise HTTPException(404, "not built yet")
    return b


@app.post("/api/demos/{demo_id}/run/qa")
async def run_qa(demo_id: str, req: Request):
    _demo_or_404(demo_id)
    usage.current_demo.set(demo_id)
    usage.current_stage.set("runtime")
    body = await req.json()
    q = (body.get("question") or "").strip()
    if not q:
        raise HTTPException(400, "question required")
    cur_slide = (body.get("slide_id") or "").strip() or None
    slides = (store.read_json(demo_id, "deck.json") or {}).get("slides", [])

    def routed(r: dict) -> dict:  # where the answer lives — plain code on fact ids and topics, no model call; a decline never moves the slide
        r.update(deck.route_for(slides, cur_slide, r.get("fact_ids"), q) if r.get("answered") else {"slide_id": cur_slide, "route": "none", "callout_id": None, "by": ""})
        return r

    hit = faq.match(demo_id, q)
    if hit and not body.get("skip_bank"):
        r = {"from_bank": True, "bank_id": hit["id"], "audio": f"/media/{demo_id}/{hit['audio']}" if hit.get("audio") else None, "answer": hit["answer"], "fact_ids": hit["fact_ids"], "facts": [], "visual": hit.get("visual"),
             "escalate": "", "topic": "", "cta": "", "answered": hit["answered"], "clarifying_question": hit.get("clarifying_question", ""), "offer_callback": hit.get("offer_callback", not hit["answered"])}
        routed(r)
        runlog.runtime_qa(demo_id, q, {**r, "answer": "[bank " + hit["id"] + "] " + r["answer"]}, body.get("profile") or None)
        return r
    try:
        r = qa.answer(demo_id, q, body.get("history") or [], body.get("profile") or None, live=True)
    except RuntimeError as e:
        raise HTTPException(502, str(e))
    r["from_bank"] = False
    routed(r)
    runlog.runtime_qa(demo_id, q, r, body.get("profile") or None)
    return r


@app.post("/api/demos/{demo_id}/run/pitch")
async def run_pitch(demo_id: str, req: Request):
    _demo_or_404(demo_id)
    usage.current_demo.set(demo_id)
    usage.current_stage.set("runtime")
    body = await req.json()
    try:
        return pitch.plan_pitch(demo_id, body.get("profile") or {}, bool(body.get("refine")))
    except RuntimeError as e:
        raise HTTPException(502, str(e))


@app.post("/api/demos/{demo_id}/run/lead")
async def run_lead(demo_id: str, req: Request):
    _demo_or_404(demo_id)
    body = await req.json()
    phone = qa.parse_phone(body.get("phone") or body.get("text") or "")
    if not phone:
        raise HTTPException(400, "no valid Indian mobile number found")
    lead = qa.save_lead(demo_id, phone, (body.get("question") or "").strip(), body.get("profile") or None, body.get("session_id"))
    cloud.put_event(demo_id, "lead", {"phone": lead.get("phone"), "question": lead.get("question"), "profile": lead.get("profile")})
    cloud.sync_demo_async(demo_id)
    return {"ok": True, "lead": lead}


def _leads(demo_id: str) -> list[dict]:
    out = []
    d = store.path(demo_id, "leads")
    if d.exists():
        for p in sorted(d.glob("*.json"), reverse=True)[:50]:
            try:
                out.append(json.loads(p.read_text()))
            except Exception:
                pass
    return out


@app.get("/api/voices")
def voices(demo_id: str = ""):
    demo = store.load(demo_id) if demo_id and store.exists(demo_id) else {"settings": {}}
    chain = voice.provider_chain(demo)
    prov = chain[0]
    if prov == "sarvam":
        opts = [{"id": k, "label": v} for k, v in sarvam.SPEAKERS.items()]
        key = "sarvam_speaker"
    elif prov == "gemini":
        opts = [{"id": v, "label": v} for v in voice.GEMINI_VOICES]
        key = "voice_name"
    elif prov == "gcloud":
        lang = voice.GCLOUD_LANG.get(demo["settings"].get("language", "en-IN"), demo["settings"].get("language", "en-IN"))
        opts = [{"id": f"{lang}-Chirp3-HD-{n}", "label": f"{n} ({lang})"} for n in ("Aoede", "Kore", "Leda", "Zephyr", "Achernar", "Sulafat")]
        key = "voice_name"
    else:
        opts, key = [], "voice_name"
    return {"provider": prov, "chain": chain, "setting_key": key, "voices": opts, "current": voice.voice_name_for(demo, prov) if prov != "browser" else "", "stt": config.STT_PROVIDER, "unavailable": voice.tripped_providers()}


@app.post("/api/demos/{demo_id}/run/stt")
async def run_stt(demo_id: str, file: UploadFile = File(...), language: str = Form(default="en-IN")):
    _demo_or_404(demo_id)
    usage.current_demo.set(demo_id)
    usage.current_stage.set("runtime")
    if config.STT_PROVIDER != "sarvam" and not config.MOCK_LLM:
        raise HTTPException(400, "server STT not configured (set SARVAM_API_KEY)")
    data = await file.read()
    if len(data) < 1000:
        return {"transcript": ""}
    try:
        text = sarvam.stt(data, file.filename or "audio.wav", language, file.content_type or "audio/wav")
    except Exception as e:
        raise HTTPException(502, sarvam.describe_error(e))
    return {"transcript": text}


@app.post("/api/demos/{demo_id}/run/tts")
async def run_tts(demo_id: str, req: Request):
    _demo_or_404(demo_id)
    usage.current_demo.set(demo_id)
    usage.current_stage.set("runtime")
    body = await req.json()
    text = (body.get("text") or "").strip()
    if not text:
        raise HTTPException(400, "text required")
    try:
        rel = voice.render_line(demo_id, text, lang=(body.get("language") or None), strict=True)
    except Exception as e:
        raise HTTPException(502, str(e)[:300])
    return {"url": f"/media/{demo_id}/{rel}" if rel else None}


@app.post("/api/demos/{demo_id}/run/session")
async def save_session(demo_id: str, req: Request):
    _demo_or_404(demo_id)
    body = await req.json()
    sid = body.get("id") or f"s_{int(time.time())}"
    body["id"] = sid
    body["saved_at"] = time.time()
    store.write_json(demo_id, f"sessions/{sid}.json", body)
    cloud.put_event(demo_id, "session", {"session_id": sid, "profile": body.get("profile"), "cta": body.get("cta"), "intent": body.get("intent"), "questions": body.get("questions", []), "personalized": body.get("personalized"), "escalations": body.get("escalations", [])})
    cloud.sync_demo_async(demo_id)
    return {"ok": True, "id": sid}


def _sessions(demo_id: str) -> list[dict]:
    out = []
    d = store.path(demo_id, "sessions")
    if d.exists():
        for p in sorted(d.glob("*.json"), reverse=True)[:20]:
            try:
                s = json.loads(p.read_text())
                out.append({"id": s.get("id"), "saved_at": s.get("saved_at"), "profile": s.get("profile"), "cta": s.get("cta"),
                            "questions": len(s.get("questions", [])), "intent": s.get("intent"), "drop_point": s.get("drop_point"), "escalations": s.get("escalations", [])})
            except Exception:
                pass
    return out


@app.get("/api/demos/{demo_id}/sessions/{sid}")
def get_session(demo_id: str, sid: str):
    _demo_or_404(demo_id)
    s = store.read_json(demo_id, f"sessions/{sid}.json")
    if not s:
        raise HTTPException(404)
    return s


@app.post("/api/demos/{demo_id}/feedback")
async def feedback(demo_id: str, req: Request):
    _demo_or_404(demo_id)
    body = await req.json()
    msg = (body.get("message") or "").strip()
    if not msg:
        raise HTTPException(400, "message required")
    ctx = body.get("context") or {}
    if ctx:
        msg += f"\n\n(Player context: {json.dumps(ctx)[:1500]})"
    try:
        return graph.handle_message(demo_id, msg, [], "rehearse")
    except RuntimeError as e:
        raise HTTPException(409, str(e))


app.mount("/web", StaticFiles(directory=str(config.WEB_DIR)), name="web")


@app.exception_handler(Exception)
async def on_error(request: Request, exc: Exception):
    return JSONResponse(status_code=500, content={"detail": str(exc)[:500]})
