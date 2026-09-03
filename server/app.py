"""Demo Studio — FastAPI app. Run:  .venv/bin/uvicorn server.app:app --port 8877 --reload"""
from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from . import config, events, orchestrator, store, usage
from .agents import align, pitch, qa, rehearsal, voice
from .llm import sarvam

app = FastAPI(title="Demo Studio", version="0.1.0")


def _demo_or_404(demo_id: str) -> dict:
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
    if not p.exists() or not p.is_file():
        raise HTTPException(404)
    return FileResponse(p)


# ---------- demos ----------

@app.get("/api/health")
def health():
    return config.health()


@app.get("/api/demos")
def list_demos():
    return store.list_demos()


@app.post("/api/demos")
async def create_demo(req: Request):
    body = await req.json()
    name = (body.get("name") or "").strip()
    demo = store.new_demo(name or "Untitled demo")
    url = (body.get("url") or "").strip()
    if url:
        store.update(demo["id"], lambda d: d["product"].__setitem__("url", url))
        store.add_url_source(demo["id"], url, role="product")
    return store.load(demo["id"])


@app.get("/api/demos/{demo_id}")
def get_demo(demo_id: str):
    demo = _demo_or_404(demo_id)
    return {"demo": demo, "cards": align.cards(demo_id) if demo["status"] not in ("sources",) else None,
            "conversation": store.read_json(demo_id, "conversation.json", []), "rehearsal": store.read_json(demo_id, "rehearsal.json"),
            "bundle_ready": store.path(demo_id, "bundle.json").exists(), "running": orchestrator.is_running(demo_id),
            "sessions": _sessions(demo_id), "leads": _leads(demo_id)}


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
            allowed = {k: v for k, v in body["settings"].items() if k in ("tts_provider", "voice_name", "sarvam_speaker", "language", "languages", "rehearsal_questions", "competition", "audience", "pitch_minutes")}
            if "languages" in allowed:
                allowed["languages"] = [x for x in allowed["languages"] if isinstance(x, str)][:6] or ["en-IN"]
                allowed["language"] = allowed["languages"][0]
            d["settings"].update(allowed)
            if "voice_name" in allowed:
                d["settings"]["voice_locked"] = True
    return store.update(demo_id, fn)


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
            r = qa.answer(demo_id, q, [], body.get("profile") or None)
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
        orchestrator.start_read(demo_id)
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
        out = orchestrator.handle_message(demo_id, message, attachments, context)
    except RuntimeError as e:
        raise HTTPException(409, str(e))
    return out


@app.post("/api/demos/{demo_id}/approve/{card}")
def approve(demo_id: str, card: str):
    demo = _demo_or_404(demo_id)
    if card not in store.CARDS:
        raise HTTPException(400, "unknown card")
    notes = orchestrator.apply_actions(demo_id, [{"type": "approve", "card": card}], [], "align")
    return {"approvals": store.load(demo_id)["approvals"], "notes": notes}


@app.post("/api/demos/{demo_id}/unapprove/{card}")
def unapprove(demo_id: str, card: str):
    _demo_or_404(demo_id)
    if card not in store.CARDS:
        raise HTTPException(400, "unknown card")
    return store.update(demo_id, lambda d: d["approvals"].__setitem__(card, False))["approvals"]


@app.post("/api/demos/{demo_id}/ctas")
async def set_ctas(demo_id: str, req: Request):
    _demo_or_404(demo_id)
    body = await req.json()
    ctas = body.get("ctas") or []
    notes = orchestrator.apply_actions(demo_id, [{"type": "set_ctas", "ctas": ctas}], [], "align")
    return {"ctas": (store.read_json(demo_id, "plan.json") or {}).get("ctas", []), "notes": notes}


@app.post("/api/demos/{demo_id}/build")
def build(demo_id: str):
    _demo_or_404(demo_id)
    try:
        orchestrator.start_build(demo_id)
    except RuntimeError as e:
        raise HTTPException(409, str(e))
    return {"ok": True}


@app.post("/api/demos/{demo_id}/revise")
async def revise(demo_id: str, req: Request):
    _demo_or_404(demo_id)
    body = await req.json()
    stage = body.get("stage")
    if stage not in ("understand", "plan", "author"):
        raise HTTPException(400, "stage must be understand | plan | author")
    try:
        orchestrator.start_revise(demo_id, stage, body.get("instruction", ""), bool(body.get("rebuild")))
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
    try:
        return qa.answer(demo_id, q, body.get("history") or [], body.get("profile") or None)
    except RuntimeError as e:
        raise HTTPException(502, str(e))


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
    return {"provider": prov, "chain": chain, "setting_key": key, "voices": opts, "current": voice.voice_name_for(demo, prov) if prov != "browser" else "", "stt": config.STT_PROVIDER}


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
        rel = voice.render_line(demo_id, text, lang=(body.get("language") or None))
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
        return orchestrator.handle_message(demo_id, msg, [], "rehearse")
    except RuntimeError as e:
        raise HTTPException(409, str(e))


app.mount("/web", StaticFiles(directory=str(config.WEB_DIR)), name="web")


@app.exception_handler(Exception)
async def on_error(request: Request, exc: Exception):
    return JSONResponse(status_code=500, content={"detail": str(exc)[:500]})
