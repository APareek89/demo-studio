"""Demo Studio — FastAPI app. Run:  .venv/bin/uvicorn server.app:app --port 8877 --reload"""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import secrets
import threading
import re
import time
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool

from . import cloud, config, events, graph, orchestrator, runlog, schemas, storage, store, usage
from . import portfolio_auth as auth
from . import portfolio_example as examples
from .agents import align, author, coach, deck, faq, narration, pitch, qa, rehearsal, summary as _summary, visuals, voice
from .llm import sarvam

app = FastAPI(title="Demo Studio", version="0.1.0")
auth.install(app)
from .runtime_live import router as runtime_live_router
app.include_router(runtime_live_router)
from .livekit_trial import router as livekit_trial_router
app.include_router(livekit_trial_router)


_PUBLIC_GETS = {"/", "/api/health", "/api/runtime/transport"}
_PUBLIC_RUNTIME = {"run/visit", "run/qa", "run/pitch", "run/lead", "run/stt", "run/tts", "run/session", "run/livekit/token"}
_COSTLY_ACTIONS = {"read", "build", "revise", "align", "rehearsal", "voice/sample", "readiness/probe", "evals", "feedback"}


@app.middleware("http")
async def portfolio_boundary(request: Request, call_next):
    """Private by default; public playback has its own persisted visit capability.

    All demo routes are covered here, including future private routes. Runtime
    handlers additionally bind request IDs to the visit before any model work.
    """
    if not auth.enabled():
        return await call_next(request)
    path, method = request.url.path, request.method
    try:
        if method not in {"GET", "HEAD", "OPTIONS"}:
            auth.check_origin(request)
        if path.startswith("/api/auth/"):
            pass  # The auth router owns its credential/session rate budgets.
        elif method in {"GET", "HEAD"} and (path in _PUBLIC_GETS or path.startswith("/web/")):
            pass
        elif path.startswith("/media/"):
            media_parts = path.split("/", 3)
            if len(media_parts) != 4:
                raise HTTPException(404, "Media not found")
            await run_in_threadpool(auth.require_media, request, media_parts[2], media_parts[3])
        elif path.startswith("/api/share/") and method == "GET":
            pass  # Exact HMAC capability is verified by share_session below.
        elif match := re.fullmatch(r"/api/demos/(dm_[a-z0-9]{8})(?:/(.*))?", path):
            demo_id, action = match.group(1), match.group(2) or ""
            if (action == "bundle" and method == "GET") or (action in _PUBLIC_RUNTIME and method == "POST"):
                if not await run_in_threadpool(auth.is_public_demo, demo_id):
                    if action != "bundle":
                        raise HTTPException(404, "Published demo not found")
                    await run_in_threadpool(auth.require_owner, request, demo_id)
                if action in {"run/qa", "run/pitch", "run/stt", "run/tts"}:
                    await run_in_threadpool(auth.limit_action, request, "runtime", 60, 60)
            else:
                await run_in_threadpool(auth.require_owner, request, demo_id)
                if method == "POST" and action in _COSTLY_ACTIONS:
                    if await run_in_threadpool(examples.is_cached_only, demo_id):
                        raise HTTPException(409, "This prepared example is free to explore. Create a demo with your own sources to generate or revise content.")
                    await run_in_threadpool(auth.limit_action, request, "build", 40, 3600)
        elif path.startswith("/api/"):
            await run_in_threadpool(auth.require_user, request)
            if path == "/api/cloud/setup":
                raise HTTPException(403, "Cloud infrastructure is managed by deployment configuration")
            if path == "/api/voices" and request.query_params.get("demo_id"):
                await run_in_threadpool(auth.require_owner, request, request.query_params["demo_id"])
        response = await call_next(request)
        if path.startswith(("/api/", "/media/")):
            response.headers["Cache-Control"] = "private, no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer" if path.startswith("/api/share/") else "same-origin"
        return response
    except HTTPException as error:
        return JSONResponse({"detail": error.detail}, status_code=error.status_code,
                            headers={**(error.headers or {}), "Cache-Control": "no-store"})


def _runtime_visit(request: Request, demo_id: str, body: dict, *, session_field="session_id"):
    if not auth.enabled():
        return
    visit = auth.require_visit(request, demo_id, body.get(session_field))
    body[session_field] = visit["session_id"]
    body["snapshot_id"] = visit["snapshot_id"]
    body["demo_version"] = visit["published_version"]
    body["bundle_version"] = visit["published_version"]
    body["runtime_version"] = 1


async def _runtime_body(request: Request, *, limit=65536) -> dict:
    raw = bytearray()
    async for part in request.stream():
        raw.extend(part)
        if len(raw) > limit:
            raise HTTPException(413, "The request is too large")
    try:
        body = json.loads(raw)
    except (ValueError, RecursionError):
        raise HTTPException(400, "Invalid request") from None
    if not isinstance(body, dict):
        raise HTTPException(400, "Invalid request")
    return body


def _grant_audio(request: Request, demo_id: str, body: dict, result: dict):
    auth.grant_response_audio(request, demo_id, body.get("session_id"), result)
    return result


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
def media(demo_id: str, rel: str, request: Request):
    if auth.enabled():
        return FileResponse(auth.media_file(request, demo_id, rel))
    try:
        p = store.media_path(demo_id, rel)
    except KeyError:
        raise HTTPException(404)
    if (not p.exists() or not p.is_file()) and cloud.enabled():
        cloud.fetch_file(demo_id, rel)
    if not p.exists() or not p.is_file():
        raise HTTPException(404)
    signed = storage.backend().media_url(demo_id, rel)
    if signed:
        return RedirectResponse(signed, status_code=302)
    return FileResponse(p)


# ---------- demos ----------

@app.get("/api/runtime/transport")
def runtime_transport():
    """Public, non-secret transport selection; never cache a deployment switch."""
    from .livekit_trial import transport_capability
    return JSONResponse(transport_capability(), headers={"Cache-Control": "no-store"})


@app.get("/api/health")
def health():
    if auth.enabled():
        try:
            with auth.connection() as conn:
                conn.execute("SET LOCAL statement_timeout='2000ms'")
                conn.execute("SELECT 1").fetchone()
        except RuntimeError:
            return JSONResponse({"ok": False, "detail": "Account storage is unavailable"}, status_code=503)
        return {"ok": True, "auth": True, "mock": bool(config.MOCK_LLM)}
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
def list_demos(request: Request):
    user = auth.require_user(request)
    local = store.list_demos(owner_user_id=user["id"] if auth.enabled() else None)
    seen = {d["id"] for d in local}
    out = [{**d, "location": "local+cloud" if cloud.enabled() else "local"} for d in local]
    for c in ([] if auth.enabled() else cloud.list_cloud_demos()):
        if c.get("demo_id") in seen:
            continue
        out.append({"id": c["demo_id"], "name": c.get("name"), "status": c.get("status"), "version": c.get("version", 0), "created_at": c.get("created_at"), "updated_at": c.get("updated_at"),
                    "sources": len(c.get("sources", [])), "location": "cloud", "approvals": c.get("approvals", {})})
    return out


@app.post("/api/demos")
async def create_demo(req: Request):
    user = auth.require_user(req)
    body = await req.json()
    name = (body.get("name") or "").strip()
    demo = store.new_demo(name or "Untitled demo", owner_user_id=user["id"] if auth.enabled() else None)
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
def duplicate(demo_id: str, request: Request):
    user = auth.require_owner(request, demo_id)
    _demo_or_404(demo_id)
    return store.duplicate_demo(demo_id, owner_user_id=user["id"] if auth.enabled() else None)


@app.post("/api/examples")
def create_example(request: Request):
    from .portfolio_example import create_example as copy_example
    user = auth.require_user(request)
    auth.limit_action(request, "examples", limit=10, seconds=3600)
    if auth.enabled():
        auth.limit_owner_action(user["id"], "examples", limit=10, seconds=3600)
    return copy_example(user["id"] if auth.enabled() else None)


@app.patch("/api/demos/{demo_id}")
async def patch_demo(demo_id: str, req: Request):
    _demo_or_404(demo_id)
    body = await req.json()
    settings = body.get("settings")
    if isinstance(settings, dict) and "pitch_minutes" in settings:
        from .agents import narration
        try:
            narration.validate_minutes(settings["pitch_minutes"])
        except ValueError as error:
            raise HTTPException(400, str(error)) from None
        if graph.is_running(demo_id) or store.load(demo_id).get("running"):
            raise HTTPException(409, "Wait for the current work to finish before changing the demo duration")
    if isinstance(settings, dict) and "runtime_default_sites" in settings and settings["runtime_default_sites"] not in ("off", "on"):
        raise HTTPException(400, "runtime_default_sites must be off or on")
    if isinstance(settings, dict) and "visual_theme" in settings:
        if settings["visual_theme"] not in ("marine", "sage", "graphite"):
            raise HTTPException(400, "visual_theme must be marine, sage or graphite")
        if graph.is_running(demo_id) or store.load(demo_id).get("running"):
            raise HTTPException(409, "Wait for the current work to finish before changing the demo color")

    def fn(d):
        if "name" in body:
            d["name"] = body["name"].strip() or d["name"]
        if "product" in body:
            d["product"].update({k: v for k, v in body["product"].items() if k in ("name", "category", "url")})
        if "settings" in body:
            allowed = {k: v for k, v in body["settings"].items() if k in ("tts_provider", "voice_name", "sarvam_speaker", "language", "languages", "rehearsal_questions", "competition", "audience", "pitch_minutes", "enhance_images", "intro_video", "runtime_default_sites", "visual_theme")}
            if "languages" in allowed:
                allowed["languages"] = [x for x in allowed["languages"] if isinstance(x, str)][:6] or ["en-IN"]
                allowed["language"] = allowed["languages"][0]
            theme_changed = "visual_theme" in allowed and allowed["visual_theme"] != d["settings"].get("visual_theme", "marine")
            duration_changed = "pitch_minutes" in allowed and allowed["pitch_minutes"] != d["settings"].get("pitch_minutes", 3)
            if duration_changed:
                # The reviewed speech and pictures must be reviewed for the new
                # duration. Existing publication and source/FAQ approvals survive.
                if d.get("running"):
                    raise HTTPException(409, "Wait for the current work to finish before changing the demo duration")
                for card in ("script", "visuals"):
                    d["approvals"][card] = False
                for stage in ("plan", "author", "deck", "voice", "rehearsal", "bundle"):
                    if d["stages"][stage]["status"] != "idle":
                        d["stages"][stage]["status"] = "stale"
                if d.get("status") in ("ready", "error"):
                    d["status"] = "align"
            d["settings"].update(allowed)
            if theme_changed:
                d["approvals"]["visuals"] = False
                if d["stages"]["bundle"]["status"] == "done":
                    d["stages"]["bundle"]["status"] = "stale"
                if d.get("status") == "ready":
                    d["status"] = "align"
            if "voice_name" in allowed or "sarvam_speaker" in allowed:
                d["settings"]["voice_locked"] = True
            runlog.settings_changed(demo_id, allowed)
    out = store.update(demo_id, fn)
    cloud.sync_demo_async(demo_id)
    return out


# ---------- sources ----------

async def _uploaded_source(demo_id: str, file: UploadFile, role: str, *, reuse_identical: bool = False) -> dict:
    """Apply the same bounded source-copy policy in Sources and Align."""
    limit = config.MAX_UPLOAD_MB * 1024 * 1024
    if file.size is not None and file.size > limit:
        raise HTTPException(413, f"{file.filename} is larger than {config.MAX_UPLOAD_MB} MB")
    try:
        return await run_in_threadpool(store.add_stream_source, demo_id,
                                       file.filename or "file", file.file, role, max_bytes=limit,
                                       reuse_identical=reuse_identical)
    except store.UploadTooLarge as e:
        raise HTTPException(413, str(e))
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.post("/api/demos/{demo_id}/sources")
async def add_sources(demo_id: str, files: list[UploadFile] = File(default=[]), role: str = Form(default="product"),
                      url: str = Form(default=""), text: str = Form(default=""), text_name: str = Form(default="brand-guidelines")):
    _demo_or_404(demo_id)
    added = []
    for f in files:
        added.append(await _uploaded_source(demo_id, f, role))
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
    try:
        return {"sources": store.patch_source(demo_id, source_id, body)["sources"]}
    except ValueError as e:
        raise HTTPException(400, str(e)) from None


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
    from .runtime_metrics import aggregate
    return {"stages": demo.get("stages", {}), "rows": usage.traces(demo_id, limit), "usage": usage.summary(demo_id), "latency": _latency(demo_id), "runtime_metrics": aggregate(demo_id)}


@app.get("/api/runtime/metrics")
def runtime_metrics(request: Request):
    from .runtime_metrics import aggregate
    user = auth.require_user(request)
    return aggregate(demo_ids=auth.owned_demo_ids(user["id"]) if auth.enabled() else None)


@app.get("/api/runtime/workflow")
def runtime_workflow():
    from .runtime_graph import graph as live_graph
    return {"mermaid": live_graph.get_graph().draw_mermaid(), "version": 1, "delivery": "Validated DeliveryPlan; audio delivered separately on browser request"}


@app.get("/api/demos/{demo_id}/readiness")
def provider_readiness(demo_id: str):
    _demo_or_404(demo_id)
    from .readiness import status
    return status(demo_id)


@app.post("/api/demos/{demo_id}/readiness/probe")
async def probe_provider_readiness(demo_id: str):
    _demo_or_404(demo_id)
    from .readiness import probe
    return await probe(demo_id)


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
            raise HTTPException(502, "The answer provider could not finish. Please try again.") from None
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


def _require_provider_readiness(demo: dict, *, for_build: bool = False, override: bool = False) -> None:
    """A key's presence is not proof of service. Never spend on an implicit probe."""
    if config.MOCK_LLM:
        return
    if override:
        runlog.event(demo["id"], "Provider readiness override", "Operator explicitly continued without a successful current provider check.")
        return
    from .readiness import status
    observed = status(demo["id"])
    checks = observed.get("checks") or {}
    issues = []
    if observed.get("stale") or observed.get("mock"):
        issues.append("a fresh real provider check is needed")
    if not checks.get("reasoning", {}).get("ready"):
        issues.append("reasoning has not passed its latest check")
    selected = demo.get("settings", {}).get("tts_provider") or config.TTS_PROVIDER
    if for_build and selected == "sarvam":
        speech = checks.get("streaming_speech") or {}
        if not speech.get("ready"):
            issues.append("streaming speech has not passed its latest check")
        elif speech.get("voice") != voice.voice_name_for(demo, "sarvam"):
            issues.append("the selected voice needs a new speech check")
    if issues:
        raise HTTPException(409, "Provider readiness: " + "; ".join(issues) + ". Check providers in Sources or Rehearse, or explicitly enable the readiness override there.")


@app.post("/api/demos/{demo_id}/read")
def read_sources(demo_id: str, override_readiness: bool = False):
    demo = _demo_or_404(demo_id)
    if not demo["sources"]:
        raise HTTPException(400, "Add at least one source first")
    if not (config.ANTHROPIC_API_KEY or config.GEMINI_API_KEY or config.RUNWARE_API_KEY or config.MOCK_LLM):
        raise HTTPException(400, "Add a text-provider key in .env (Anthropic, Gemini or Runware)")
    if any(s["kind"] in ("video", "image") for s in demo["sources"]) and not config.GEMINI_API_KEY and not config.MOCK_LLM:
        raise HTTPException(400, "GEMINI_API_KEY missing in .env (needed for video/images)")
    _require_provider_readiness(demo, override=override_readiness)
    try:
        graph.start_read(demo_id)
    except RuntimeError as e:
        raise HTTPException(409, str(e))
    return {"ok": True}


# ---------- events (SSE) ----------

@app.get("/api/demos/{demo_id}/events")
async def sse(demo_id: str, request: Request, since: int | None = None):
    _demo_or_404(demo_id)

    async def gen():
        try:
            resume = int(request.headers.get("last-event-id", ""))
        except (ValueError, TypeError):
            resume = since
        # Fresh view = current state plus future events. Historical build completion
        # must not navigate a newly opened Align screen away from human review.
        baseline = events.snapshot(demo_id, resume)
        seq = baseline["seq"]
        last_beat = time.time()
        yield f"id: {seq}\nevent: hello\ndata: {json.dumps(baseline)}\n\n"
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
    demo = _demo_or_404(demo_id)
    if graph.is_running(demo_id) or demo.get("running"):
        raise HTTPException(409, "Still working on the last change — give me a moment")
    attachments = []
    for f in files:
        attachments.append(await _uploaded_source(demo_id, f, "product", reuse_identical=True))
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
    if graph.is_running(demo_id):
        raise HTTPException(409, "Wait for the current draft to finish before approving a card")
    if card == "script":
        preparation = narration.preparation_status(demo_id)
        if preparation["status"] in {"incomplete", "needs_sources"}:
            raise HTTPException(409, preparation["reason"])
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


@app.patch("/api/demos/{demo_id}/knowledge/conflicts/{conflict_id}")
async def resolve_knowledge_conflict(demo_id: str, conflict_id: str, req: Request):
    _demo_or_404(demo_id)
    from .knowledge import resolve_conflict
    body = await req.json()
    try:
        result = resolve_conflict(demo_id,conflict_id,str(body.get("preferred_fact_id") or ""),note=str(body.get("note") or "")[:1000])
    except KeyError:
        raise HTTPException(404,"Source conflict not found")
    except ValueError as exc:
        raise HTTPException(400,str(exc))
    orchestrator.invalidate(demo_id,"understand")
    orchestrator.set_stage(demo_id,"understand","done",message="Source conflict reviewed; downstream content needs review")
    store.update(demo_id,lambda d:d["approvals"].update({c:False for c in store.CARDS}))
    runlog.event(demo_id,"Source conflict resolved",conflict_id+" → "+str(body.get("preferred_fact_id")))
    return {"ok":True,"conflict":result["conflict"],"approvals":store.load(demo_id)["approvals"],"cards":align.cards(demo_id)}


@app.patch("/api/demos/{demo_id}/align/facts/{fact_id}")
async def edit_aligned_fact(demo_id: str, fact_id: str, req: Request):
    """A corrected assertion gets a new ID; historical citations never change meaning."""
    demo = _demo_or_404(demo_id)
    if graph.is_running(demo_id) or demo.get("running") or any(stage.get("status") == "running" for stage in demo.get("stages", {}).values()):
        raise HTTPException(409, "Wait for the current stage to finish before editing a fact")
    body = await req.json()
    try:
        fact = store.edit_fact(demo_id, fact_id, body)
    except KeyError:
        raise HTTPException(404, "fact not found")
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    changed = fact["id"] != fact_id
    if changed:
        orchestrator.invalidate(demo_id, "understand")
        orchestrator.set_stage(demo_id, "understand", "done", message="direct fact edit saved with a new assertion ID")
        store.update(demo_id, lambda d: d["approvals"].update({key: False for key in store.CARDS}))
        runlog.event(demo_id, f"Fact {fact_id} replaced by {fact['id']}", "Historical citations stay unchanged. Script, visuals and FAQ require re-approval before build.")
    result = {"ok": True, "fact": fact, "changed": changed, "cards": align.cards(demo_id), "approvals": store.load(demo_id)["approvals"]}
    if changed:
        result["previous_id"] = fact_id
    return result


@app.post("/api/demos/{demo_id}/align/facts/{fact_id}/approval")
async def set_aligned_fact_approval(demo_id: str, fact_id: str, req: Request):
    """Explicitly reject or restore a questionable extracted fact from the Align UI."""
    _demo_or_404(demo_id)
    body = await req.json()
    approved = body.get("approved") if isinstance(body, dict) else None
    try:
        store.set_fact_approval(demo_id, fact_id, approved)
    except KeyError:
        raise HTTPException(404, "fact not found")
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    orchestrator.invalidate(demo_id, "understand")
    orchestrator.set_stage(demo_id, "understand", "done", message="fact approval reviewed directly")
    orchestrator.set_stage(demo_id, "faq", "stale", message="fact approval changed — bank re-answers on the next build")
    store.update(demo_id, lambda d: d["approvals"].update({key: False for key in store.CARDS}))
    runlog.event(demo_id, f"Fact {fact_id} {'restored' if approved else 'rejected'} directly", "Script, visuals and FAQ require review again.")
    return {"ok": True, "cards": align.cards(demo_id), "approvals": store.load(demo_id)["approvals"]}


@app.post("/api/demos/{demo_id}/align/facts/review-held")
async def review_held_facts(demo_id: str, req: Request):
    """Retry saved evidence or explicitly restore citation-held facts as a group."""
    from . import knowledge
    demo = _demo_or_404(demo_id)
    body = await req.json()
    if not isinstance(body, dict) or set(body) != {"action"} or body.get("action") not in {"retry", "restore"}:
        raise HTTPException(400, "Send action: retry or restore")
    if graph.is_running(demo_id) or demo.get("running") or any(stage.get("status") == "running" for stage in demo.get("stages", {}).values()):
        raise HTTPException(409, "Wait for the current stage to finish before reviewing facts")
    result = knowledge.review_held_citations(demo_id, body["action"])
    if result["changed_fact_ids"]:
        orchestrator.invalidate(demo_id, "understand")
        orchestrator.set_stage(demo_id, "understand", "done", message="citation-held facts reviewed together")
        store.update(demo_id, lambda d: d["approvals"].update({key: False for key in store.CARDS}))
    runlog.event(demo_id, "Citation-held facts reviewed", f"{body['action']}: {len(result['changed_fact_ids'])} restored; {len(result['still_held'])} still need matching evidence; {len(result['skipped_conflicts'])} conflicts preserved.")
    return {"ok": True, **result, "cards": align.cards(demo_id), "approvals": store.load(demo_id)["approvals"]}


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
    """Save explicit line/question edits, validate grounding, then re-run visual alignment."""
    demo = _demo_or_404(demo_id)
    body = await req.json()
    if not isinstance(body, dict):
        raise HTTPException(400, "Send a script edit object")
    edits = body.get("lines") or []
    checkins = body.get("checkins") or []
    segments = body.get("segments") or []
    if not isinstance(edits, list) or len(edits) > 200:
        raise HTTPException(400, "Send at most 200 script line edits")
    if not isinstance(checkins, list) or len(checkins) > 200:
        raise HTTPException(400, "Send at most 200 check-in edits")
    if not isinstance(segments, list) or len(segments) > 200:
        raise HTTPException(400, "Send at most 200 segment metadata edits")
    if not edits and not checkins and not segments and "intake_q1" not in body:
        raise HTTPException(400, "Send a line, intake_q1, checkins or segments edit")
    if body.get("intake_q2"):
        raise HTTPException(400, "A second intake question is not supported")
    question_edits = {str(x.get("segment_id")): x for x in checkins if isinstance(x, dict) and x.get("segment_id")}
    if len(question_edits) != len(checkins):
        raise HTTPException(400, "Every check-in edit needs a unique segment_id")
    segment_edits = {str(x.get("id")): x for x in segments if isinstance(x, dict) and x.get("id")}
    if len(segment_edits) != len(segments):
        raise HTTPException(400, "Every segment metadata edit needs a unique id")
    for edit in segment_edits.values():
        if set(edit) - {"id", "title", "outcome"} or not {"title", "outcome"}.intersection(edit):
            raise HTTPException(400, "Segment metadata edits may change title or outcome only")
        for field, limit in (("title", 200), ("outcome", 500)):
            if field in edit and (not isinstance(edit[field], str) or len(edit[field].strip()) > limit or (field == "title" and not edit[field].strip())):
                raise HTTPException(400, "Segment title needs 1–200 characters; outcome needs 0–500 characters")
    questions = [("intake_q1", body["intake_q1"])] if "intake_q1" in body else []
    questions += [(segment_id, edit.get("text")) for segment_id, edit in question_edits.items()]
    for field, text in questions:
        if not isinstance(text, str) or len(text.strip()) > 1200 or (field == "intake_q1" and not text.strip()):
            raise HTTPException(400, "Questions must be text of at most 1200 characters; intake_q1 cannot be empty")
        if author.ungrounded(text, [], set())[1]:
            raise HTTPException(400, "Questions cannot introduce an uncited claim or figure; keep cited facts in narration")
    requested = {str(x.get("id")): x for x in edits if isinstance(x, dict) and x.get("id")}
    if len(requested) != len(edits):
        raise HTTPException(400, "Every script edit needs a line id")
    for edit in requested.values():
        if not any(key in edit for key in ("text", "fact_ids", "visual_ref", "delivery")):
            raise HTTPException(400, "Each script edit must change text, fact ids, delivery or the visual ref")
        if "text" in edit and (not (edit.get("text") or "").strip() or len((edit.get("text") or "").strip()) > 1200):
            raise HTTPException(400, "Every edited line needs 1–1200 characters")
        if "fact_ids" in edit and (not isinstance(edit.get("fact_ids"), list) or len(edit["fact_ids"]) > 30):
            raise HTTPException(400, "fact_ids must be a list of at most 30 fact ids")
        if "delivery" in edit:
            delivery = edit["delivery"]
            if not isinstance(delivery,dict) or set(delivery)-{"tone","pace"} or delivery.get("tone","warm") not in {"warm","upbeat","calm","reassuring"}:
                raise HTTPException(400, "Delivery needs a supported tone and optional pace")
            pace = delivery.get("pace",1.0)
            if isinstance(pace,bool) or not isinstance(pace,(int,float)) or not .9<=pace<=1.08:
                raise HTTPException(400, "Delivery pace must be between 0.9 and 1.08")
    script = store.read_json(demo_id, "script.json") or {}
    und = store.read_json(demo_id, "understanding.json") or {}
    missing_segments = (set(question_edits) | set(segment_edits)) - {seg.get("id") for seg in script.get("segments", [])}
    if missing_segments:
        raise HTTPException(404, "check-in segment not found: " + ", ".join(sorted(missing_segments)))
    if "intake_q1" in body:
        script["intake_q1"] = body["intake_q1"].strip()
        script["intake_q2"] = ""
        script["intake_audio"] = {}
    for seg in script.get("segments", []):
        if seg.get("id") in question_edits:
            seg["checkin"] = question_edits[seg["id"]]["text"].strip()
            seg["checkin_audio"] = None
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
                if "delivery" in edit:
                    line["delivery"] = edit["delivery"]
                    line.pop("audio", None)
                if "fact_ids" in edit:
                    line["fact_ids"] = [str(x) for x in edit["fact_ids"]]
                if "visual_ref" in edit:
                    line["visual"] = ({"kind": "image" if str(edit["visual_ref"]).startswith("im") else "shot", "ref": str(edit["visual_ref"]), "focus": (line.get("visual") or {}).get("focus", "")} if edit.get("visual_ref") else {"kind": "none", "ref": "", "focus": ""})
                found.add(line["id"])
    extra_lines = [*script.get("closing", []), *([script["runtime_overview"]] if script.get("runtime_overview") else [])]
    for line in extra_lines:
        if line.get("id") in requested:
            edit = requested[line["id"]]
            if "text" in edit:
                line["text"] = (edit.get("text") or "").strip()
                line.pop("audio", None)
            if "delivery" in edit:
                line["delivery"] = edit["delivery"]
                line.pop("audio", None)
            if "text" in edit or "delivery" in edit:
                for field in ("duration_seconds", "duration_exact", "duration_in_range", "duration", "exact"):
                    line.pop(field, None)
            if "fact_ids" in edit:
                line["fact_ids"] = [str(x) for x in edit["fact_ids"]]
            if "visual_ref" in edit:
                line["visual"] = ({"kind": "image" if str(edit["visual_ref"]).startswith("im") else "shot", "ref": str(edit["visual_ref"]), "focus": (line.get("visual") or {}).get("focus", "")} if edit.get("visual_ref") else {"kind": "none", "ref": "", "focus": ""})
            found.add(line["id"])
    missing = set(requested) - found
    if missing:
        raise HTTPException(404, "script line not found: " + ", ".join(sorted(missing)))
    for seg in script.get("segments", []):
        if seg.get("id") not in segment_edits:
            continue
        ids = [fid for line in [*(seg.get("lines") or []), *(seg.get("deeper") or [])] for fid in line.get("fact_ids", [])]
        for field in ("title", "outcome"):
            if field in segment_edits[seg["id"]]:
                text = segment_edits[seg["id"]][field].strip()
                if author.ungrounded(text, ids, approved_fact_ids)[1]:
                    raise HTTPException(400, "Segment metadata cannot introduce an uncited claim or figure")
                seg[field] = text
    plan = store.read_json(demo_id, "plan.json") or {}
    issues = author.validate(script, und, plan, demo)
    invalid = [line.get("id") for seg in script.get("segments", []) for line in [*(seg.get("lines") or []), *(seg.get("deeper") or [])] if line.get("id") in requested and line.get("unverified")]
    invalid += [line.get("id") for line in extra_lines if line.get("id") in requested and line.get("unverified")]
    if invalid:
        raise HTTPException(400, "That edit introduces an uncited claim or figure. Add the information as a source/fact first: " + ", ".join(invalid))
    script["issues"] = issues
    if questions or any({"text", "delivery", "fact_ids"}.intersection(edit) for edit in requested.values()):
        script.pop("voice_input_hash", None)
    # A manual edit is a current draft, never an unprepared legacy artifact
    # that Build may silently replace. Keep the user's words and review state.
    script["narration_preparation"] = {**(script.get("narration_preparation") or {}), "status": "incomplete"}
    preparation = narration.preparation_status(demo_id, script=script, plan=plan)
    script["narration_preparation"] = preparation
    incomplete = preparation["status"] in {"incomplete", "needs_sources"}
    und["image_map"] = visuals.build_map(und, demo)
    store.write_json(demo_id, "understanding.json", und)
    realigned = bool(body.get("realign_visuals", True)) and not incomplete
    if realigned:
        script = visuals.align(demo_id, script, und)
    elif incomplete:
        script["visual_audit"] = {"method": "pending_narration", "lines": [], "images": []}
    author.timeline(script, demo_id)
    store.write_json(demo_id, "script.json", script)
    orchestrator.invalidate(demo_id, "author")
    orchestrator.set_stage(demo_id, "author", "pending" if incomplete else "done",
                           message=preparation["reason"] if incomplete else "direct script edits saved and validated")
    store.update(demo_id, lambda d: d["approvals"].update({"visuals": False, "script": False}))
    runlog.event(demo_id, "Script edited directly", f"{len(found)} line(s), {len(questions)} question(s), {len(segment_edits)} segment label(s) saved; visual alignment {'refreshed' if realigned else 'kept'}; script and visuals require re-approval.")
    return {"ok": True, "cards": align.cards(demo_id), "approvals": store.load(demo_id)["approvals"], "issues": issues}


@app.patch("/api/demos/{demo_id}/align/faq/{question_id}")
async def edit_aligned_faq(demo_id: str, question_id: str, req: Request):
    """Save a human-reviewed supported answer without regenerating the FAQ bank."""
    demo = _demo_or_404(demo_id)
    body = await req.json()
    if not isinstance(body, dict):
        raise HTTPException(400, "Send an FAQ review object")
    action = body.get("action", "edit")
    expected = ({"answer", "fact_ids"} | ({"action"} if "action" in body else set())) if action == "edit" else {"action"}
    if action not in {"approve", "edit", "reject"} or set(body) != expected:
        raise HTTPException(400, "Choose approve, edit or reject; edits need answer and fact_ids")
    if action != "edit":
        if graph.is_running(demo_id) or demo.get("running") or any(stage.get("status") == "running" for stage in demo.get("stages", {}).values()):
            raise HTTPException(409, "Wait for the current stage to finish before reviewing an FAQ answer")
        try:
            faq.review_entry(demo_id, question_id, action=action)
        except KeyError:
            raise HTTPException(404, "FAQ question not found")
        except ValueError as exc:
            raise HTTPException(400, str(exc))
        runlog.event(demo_id, f"FAQ {question_id} {action} reviewed", "Customer answers retain their reviewed wording; rejected answers are never served.")
        return {"ok": True, "cards": align.cards(demo_id), "approvals": store.load(demo_id)["approvals"]}
    text, ids = body["answer"], body["fact_ids"]
    if not isinstance(text, str) or not 1 <= len(text.strip()) <= 2000:
        raise HTTPException(400, "answer must contain 1–2000 characters")
    if not isinstance(ids, list) or any(not isinstance(fid, str) or not fid.strip() for fid in ids):
        raise HTTPException(400, "fact_ids must be a list of fact ids")
    if len(ids) != len(set(ids)):
        raise HTTPException(400, "fact_ids must not contain duplicates")
    text = text.strip()
    und = store.read_json(demo_id, "understanding.json") or {}
    allowed = qa.approved_fact_ids(und, demo.get("settings", {}).get("competition") == "on")
    if set(ids) - allowed:
        raise HTTPException(400, "Every citation must be approved and allowed by the comparison setting")
    valid, ungrounded = author.ungrounded(text, ids, allowed)
    if ungrounded:
        raise HTTPException(400, "That answer states an uncited figure or claim; cite approved facts first")
    if not valid:
        raise HTTPException(400, "A supported answer needs at least one approved fact id")
    bank = store.read_json(demo_id, "faq.json") or {}
    matches = [entry for entry in bank.get("entries", []) if entry.get("id") == question_id]
    if not matches:
        raise HTTPException(404, "FAQ question not found")
    if len(matches) != 1:
        raise HTTPException(400, "FAQ question id is ambiguous")
    if graph.is_running(demo_id) or demo.get("running") or any(stage.get("status") == "running" for stage in demo.get("stages", {}).values()):
        raise HTTPException(409, "Wait for the current stage to finish before reviewing an FAQ answer")
    if demo.get("stages", {}).get("faq", {}).get("status") != "done" or bank.get("partial") or bank.get("registry_hash") != faq._registry_hash(demo_id):
        raise HTTPException(409, "Refresh the FAQ bank from the current facts before editing its answers")
    entry = matches[0]
    # An old answer's audio, image or clarification must not survive a correction.
    visual = None
    ref = visuals.for_facts(und, valid)
    for item in und.get("images", []) + und.get("shots", []):
        if item.get("id") == ref and store.visual_allowed(demo, item.get("source_id")):
            visual = {"kind": "image" if item in und.get("images", []) else "shot", "ref": ref, "source_id": item.get("source_id")}
            if visual["kind"] == "shot":
                visual.update({"start": item.get("start"), "end": item.get("end")})
            break
    slides = deck.slides_with_script((store.read_json(demo_id, "deck.json") or {}).get("slides", []),
                                    store.read_json(demo_id, "script.json") or {})
    try:
        from . import knowledge
        faq.review_entry(demo_id, question_id, action="edit", answer=text, fact_ids=valid,
                         visual=visual, slide_id=deck.slide_for(slides, valid, entry["question"])[0],
                         snapshot_id=knowledge.snapshot(demo_id)["id"])
    except KeyError:
        raise HTTPException(404, "FAQ question not found")
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    orchestrator.invalidate(demo_id, "faq")
    orchestrator.set_stage(demo_id, "faq", "done", message="reviewed FAQ answer saved; recording requires rebuild")
    store.update(demo_id, lambda d: d["approvals"].update({"faq": False}))
    runlog.event(demo_id, f"FAQ {question_id} edited directly", "Reviewed answer saved with approved citations; FAQ requires re-approval and its recording will be rebuilt.")
    return {"ok": True, "cards": align.cards(demo_id), "approvals": store.load(demo_id)["approvals"]}


@app.patch("/api/demos/{demo_id}/align/deck")
async def edit_aligned_deck(demo_id: str, req: Request):
    """Slide review in Align: picture, title, callout text / facts / part, dragged positions. Saved to deck-overrides.json
    (kept over any rebuild) and applied to deck.json now, through the same validator as script lines. No model call."""
    demo = _demo_or_404(demo_id)
    body = await req.json()
    if not isinstance(body, dict):
        raise HTTPException(400, "Send slide edits as an object")
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
    reserved_callout_ids = {c.get("id") for row in [*dk["slides"], *ov_by.values()] for c in row.get("callouts", []) if c.get("id")}
    # Source exclusions can retire old saved choices. Sanitize those old choices
    # before applying new, strictly validated edits; never restore excluded media.
    for sid, saved in ov_by.items():
        current = slides.get(sid, {})
        old_media = saved.get("media")
        if isinstance(old_media, list) and old_media and any(ref not in images for ref in old_media):
            saved["media"] = [ref for ref in old_media if ref in images] or [m["image_id"] for m in current.get("media", []) if m["image_id"] in images]
        if saved.get("image_id") and saved["image_id"] not in images:
            saved.pop("image_id")
        for callout in saved.get("callouts", []):
            if callout.get("image_id") and callout["image_id"] not in images:
                callout.pop("image_id")
                callout.pop("label_pos", None)
    for e in edits:
        if not isinstance(e, dict):
            raise HTTPException(400, "Each slide edit must be an object")
        sid = str(e.get("slide_id") or "")
        s = slides.get(sid)
        if not s:
            raise HTTPException(404, f"slide not found: {sid}")
        o = ov_by.setdefault(sid, {"slide_id": sid, "callouts": []})
        if "media" in e:
            media_ids = e["media"]
            if not isinstance(media_ids, list) or len(media_ids) > 2 or any(not isinstance(ref, str) for ref in media_ids):
                raise HTTPException(400, "media must contain at most two picture ids")
            if len(set(media_ids)) != len(media_ids) or any(ref not in images for ref in media_ids):
                raise HTTPException(400, "Pictures must be distinct and allowed in this demo")
            if "image_id" in e and (not media_ids or e["image_id"] != media_ids[0]):
                raise HTTPException(400, "image_id must match the first media picture")
            o["media"] = list(media_ids)
            o.pop("image_id", None)
        if "image_id" in e:
            if e["image_id"] not in images:
                raise HTTPException(400, f"unknown or excluded picture: {e['image_id']}")
            o["image_id"] = e["image_id"]
            if "media" in o and "media" not in e:
                o["media"] = [e["image_id"], *o["media"][1:]]
        selected_media = o.get("media")
        if selected_media is None:
            selected_media = [m["image_id"] for m in deck.slide_media(s)]
            if "image_id" in o:
                selected_media = [o["image_id"], *[ref for ref in selected_media[1:] if ref != o["image_id"]]]
        if len(set(selected_media)) != len(selected_media):
            raise HTTPException(400, "Pictures must be distinct")
        if "title" in e:
            title = (e.get("title") or "").strip()
            if not title or len(title) > 80:
                raise HTTPException(400, "A title needs 1–80 characters")
            o["title"] = title
        oc_by = {c["id"]: c for c in o.get("callouts", []) if c.get("id")}
        if "media" in e or "image_id" in e:
            # Geometry reviewed against a removed picture must not be replayed
            # as an anchor on its replacement. Preserve semantic edits, then
            # merge any explicit new callout binding in this request below.
            for cid, oc in oc_by.items():
                current = next((c for c in s["callouts"] if c["id"] == cid), {})
                old_ref = oc.get("image_id") or current.get("image_id") or s.get("image_id")
                if old_ref not in selected_media:
                    for field in ("image_id", "part", "label_pos", "placement"):
                        oc.pop(field, None)
        for ce in e.get("callouts") or []:
            if not isinstance(ce, dict):
                raise HTTPException(400, "Each callout edit must be an object")
            cid = str(ce.get("id") or "")
            cur = next((c for c in s["callouts"] if c["id"] == cid), None)
            creating = ce.get("create") is True
            if creating:
                if not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", cid) or cid in reserved_callout_ids:
                    raise HTTPException(400, "A new callout needs a unique id using letters, numbers, underscores or hyphens")
                if not {"text", "fact_ids", "reveal_on_line"} <= ce.keys():
                    raise HTTPException(400, "A new callout needs text, fact_ids and reveal_on_line")
                if not isinstance(ce["text"], str) or ("part" in ce and ce["part"] is not None and not isinstance(ce["part"], str)):
                    raise HTTPException(400, "A new callout's text and part must be strings")
                reserved_callout_ids.add(cid)
                cur = {"id":cid, "text":"", "fact_ids":[]}
            if not cur:
                raise HTTPException(404, f"callout not found: {cid}")
            oc = oc_by.setdefault(cid, {"id": cid})
            if creating:
                oc["create"] = True
            if "text" in ce or "fact_ids" in ce:
                text = (ce.get("text") if "text" in ce else oc.get("text", cur["text"])).strip()
                fids = ce.get("fact_ids") if "fact_ids" in ce else oc.get("fact_ids", cur["fact_ids"])
                if not isinstance(fids, list):
                    raise HTTPException(400, "fact_ids must be a list")
                unknown = {str(x) for x in fids} - allowed_facts
                if unknown:
                    raise HTTPException(400, "Rejected or unknown fact ids cannot be attached: " + ", ".join(sorted(unknown)))
                if creating and (not fids or not {str(x) for x in fids} <= deck.slide_facts(s)):
                    raise HTTPException(400, "A new callout must cite approved facts already on this slide")
                valid, bad = author.ungrounded(text, [str(x) for x in fids], allowed_facts)
                if not text or bad:
                    raise HTTPException(400, "That callout states a figure or claim without a fact id. Add the information as a source/fact first.")
                if author.words(text) > deck.MAX_CALLOUT_WORDS:
                    raise HTTPException(400, f"A callout is at most {deck.MAX_CALLOUT_WORDS} words")
                oc["text"], oc["fact_ids"] = text, valid
            if "reveal_on_line" in ce:
                reveal = ce["reveal_on_line"]
                if type(reveal) is not int or not 0 <= reveal <= max(0, len(s.get("lines", [])) - 1):
                    raise HTTPException(400, "reveal_on_line must be an existing slide line index")
                oc["reveal_on_line"] = reveal
            if "image_id" in ce:
                if ce["image_id"] is not None and ce["image_id"] not in selected_media:
                    raise HTTPException(400, "A callout must refer to one of this slide's pictures")
                oc["image_id"] = ce["image_id"]
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
    try:
        deck.apply_overrides(dk["slides"], ov, images, allowed_facts)
        schemas.Deck.model_validate(dk)
    except (ValueError, TypeError) as error:
        raise HTTPException(400, str(error)) from error
    store.write_json(demo_id, "deck-overrides.json", ov)
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
    # These values are computed after the model-output schema is validated.
    # Human pitch edits cannot erase or rewrite the preparation boundary.
    for key in ("narration_preparation", "guided_minimum_seconds", "guided_opening_words", "issues"):
        if key in plan:
            validated[key] = plan[key]
    store.write_json(demo_id, "plan.json", validated)
    orchestrator.invalidate(demo_id, "plan")
    orchestrator.set_stage(demo_id, "plan", "done", message="direct pitch edits saved and validated")
    store.update(demo_id, lambda d: d["approvals"].update({key: False for key in store.CARDS}))
    runlog.event(demo_id, "Pitch brief edited directly", f"{len(fields)} field(s), {len(pairs)} replacement(s), {len(remove_ids)} fact id(s) removed; every card requires review.")
    return {"ok": True, "cards": align.cards(demo_id), "approvals": store.load(demo_id)["approvals"]}


@app.patch("/api/demos/{demo_id}/align/playbook")
async def edit_aligned_playbook(demo_id: str, req: Request):
    """Save a reviewed story order, revalidate it, then rebuild the draft from Plan."""
    demo = _demo_or_404(demo_id)
    body = await req.json()
    if not isinstance(body, dict) or set(body) != {"stop_order", "kinds"}:
        raise HTTPException(400, "Send stop_order and kinds only")
    pb = store.read_json(demo_id, "playbook.json") or {}
    stops = pb.get("stops", [])
    if not stops:
        raise HTTPException(409, "No sales playbook yet — read the sources first")
    order, kinds = body["stop_order"], body["kinds"]
    ids = [stop["id"] for stop in stops]
    if (not isinstance(order, list) or any(not isinstance(sid, str) for sid in order)
            or len(order) != len(ids) or len(set(order)) != len(order) or set(order) != set(ids)):
        raise HTTPException(400, "stop_order must include every current stop exactly once")
    allowed_kinds = {"fundamental", "differentiator", "delighter", "hygiene", "ownership"}
    if (not isinstance(kinds, dict) or set(kinds) - set(ids)
            or any(not isinstance(kind, str) or kind not in allowed_kinds for kind in kinds.values())):
        raise HTTPException(400, "kinds must map current stop ids to a supported kind")
    if graph.is_running(demo_id) or demo.get("running") or any(stage.get("status") == "running" for stage in demo.get("stages", {}).values()):
        raise HTTPException(409, "Wait for the current stage to finish before editing story order")
    by_id = {stop["id"]: stop for stop in stops}
    pb["stops"] = [{**by_id[sid], "kind": kinds.get(sid, by_id[sid]["kind"])} for sid in order]
    if not any(stop["kind"] == "fundamental" for stop in pb["stops"]):
        raise HTTPException(400, "The story needs a fundamental stop to open with")
    und = store.read_json(demo_id, "understanding.json") or {}
    for field in ("images", "shots"):
        und[field] = [item for item in und.get(field, []) if store.visual_allowed(demo, item.get("source_id"))]
    try:
        issues = coach.validate(pb, und)
        schemas.Playbook.model_validate(pb)
    except ValueError as exc:
        raise HTTPException(400, "Invalid story order: " + str(exc)[:400])
    pb["issues"] = list(dict.fromkeys([*pb.get("issues", []), *issues]))
    overrides = {"stop_order": [stop["id"] for stop in pb["stops"]],
                 "kinds": {stop["id"]: stop["kind"] for stop in pb["stops"]}}
    store.write_json(demo_id, "playbook-overrides.json", overrides)
    store.write_json(demo_id, "playbook.json", pb)
    orchestrator.invalidate(demo_id, "coach")
    store.update(demo_id, lambda d: d["approvals"].update(script=False, visuals=False))
    runlog.event(demo_id, "Story order reviewed", "Saved validated playbook overrides; script and visuals require review after Plan runs again.")
    try:
        graph.start_revise(demo_id, "plan", "Follow the reviewed story order and kinds in playbook-overrides.json.")
    except RuntimeError as exc:
        raise HTTPException(409, str(exc))
    return {"ok": True, "playbook": pb, "approvals": store.load(demo_id)["approvals"], "issues": issues}


@app.post("/api/demos/{demo_id}/align/request-upload")
async def request_aligned_upload(demo_id: str, req: Request):
    """Execute the existing upload-request action directly from a reviewed evidence gap."""
    _demo_or_404(demo_id)
    body = await req.json()
    if not isinstance(body, dict) or set(body) != {"type", "upload_kind", "reason"} or body.get("type") != "request_upload":
        raise HTTPException(400, "Send one request_upload action")
    if body.get("upload_kind") not in ("image", "video", "document"):
        raise HTTPException(400, "upload_kind must be image, video or document")
    reason = body.get("reason")
    if not isinstance(reason, str) or not 1 <= len(reason.strip()) <= 2000:
        raise HTTPException(400, "A source request needs a reason of 1–2000 characters")
    action = {**body, "reason": reason.strip()}
    notes = orchestrator.apply_actions(demo_id, [action], [], "align")
    reply = f"Please attach a {action['upload_kind']} for: {action['reason']}"
    message = orchestrator._append_conversation(demo_id, "agent", reply, actions=[action], notes=notes)
    return {"ok": True, "reply": reply, "message": message, "actions": [action], "notes": notes}


@app.post("/api/demos/{demo_id}/ctas")
async def set_ctas(demo_id: str, req: Request):
    _demo_or_404(demo_id)
    body = await req.json()
    ctas = body.get("ctas") or []
    notes = orchestrator.apply_actions(demo_id, [{"type": "set_ctas", "ctas": ctas}], [], "align")
    runlog.event(demo_id, "CTAs saved", "; ".join(f"{c.get('label')} ({c.get('kind')})" for c in ctas))
    return {"ctas": (store.read_json(demo_id, "plan.json") or {}).get("ctas", []), "notes": notes}


@app.post("/api/demos/{demo_id}/build")
def build(demo_id: str, override_readiness: bool = False):
    demo = _demo_or_404(demo_id)
    _require_provider_readiness(demo, for_build=True, override=override_readiness)
    try:
        graph.start_build(demo_id)
    except RuntimeError as e:
        raise HTTPException(409, str(e))
    return {"ok": True}


@app.post("/api/demos/{demo_id}/rehearsal")
def run_rehearsal(demo_id: str):
    _demo_or_404(demo_id)
    try:
        graph.start_rehearsal(demo_id)
    except RuntimeError as error:
        raise HTTPException(409, str(error))
    return {"started": True}


@app.post("/api/demos/{demo_id}/revise")
async def revise(demo_id: str, req: Request, override_readiness: bool = False):
    demo = _demo_or_404(demo_id)
    body = await req.json()
    stage = body.get("stage")
    if stage not in ("understand", "coach", "plan", "author", "deck", "faq"):
        raise HTTPException(400, "stage must be understand | coach | plan | author | deck | faq")
    if stage in {"plan", "author"} and body.get("instruction") == narration.PREPARATION_INSTRUCTION:
        _require_provider_readiness(demo, override=override_readiness)
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
        raise HTTPException(502, "The voice provider could not finish. Please try again.") from None
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
    return examples.public_bundle(demo_id, b) if examples.is_cached_only(demo_id) else b


@app.post("/api/demos/{demo_id}/run/qa")
async def run_qa(demo_id: str, req: Request):
    demo = _demo_or_404(demo_id)
    usage.current_demo.set(demo_id)
    usage.current_stage.set("runtime")
    body = await _runtime_body(req)
    await run_in_threadpool(_runtime_visit, req, demo_id, body)
    q = (body.get("question") or "").strip()
    if len(q) > 2000:
        raise HTTPException(400, "Keep questions under 2,000 characters")
    if not q:
        raise HTTPException(400, "question required")
    if examples.is_cached_only(demo_id):
        result = await asyncio.to_thread(examples.cached_answer, demo_id, q, body.get("slide_id"))
        return await run_in_threadpool(_grant_audio, req, demo_id, body, result)
    # Legacy integrations without a session keep the original REST contract.
    # New players always identify their session; explicit v1 also enables graph
    # calls from tools/benchmarks without a browser.
    if body.get("runtime_version") == 1 or (body.get("session_id") and (store.read_json(demo_id, "bundle.json") or {}).get("runtime", {}).get("version") == 1):
        from .runtime_graph import run_turn
        turn = await run_turn(demo_id, body)
        result = turn["result"]
        # HTTP is the typed/disconnected fallback. Live WS renders the validated
        # delivery plan only when the browser requests it after slide routing.
        if body.get("voice_it", True) and result.get("answer") and not result.get("audio"):
            try:
                rel = await asyncio.to_thread(voice.render_line, demo_id, result["answer"],
                                              demo=voice.runtime_demo(demo_id, turn.get("delivery", {}).get("language")), strict=True)
                result["audio"] = f"/media/{demo_id}/{rel}" if rel else None
                if rel and result.get("faq_entry_id"):
                    faq.update_audio(demo_id, result["faq_entry_id"], result["answer"], rel)
            except Exception:
                result["audio"] = None
        runlog.runtime_qa(demo_id, q, result, body.get("profile") or None)
        return await run_in_threadpool(_grant_audio, req, demo_id, body, result)
    cur_slide = (body.get("slide_id") or "").strip() or None
    # Reviewed script is authoritative for narration/deeper citations, including
    # when saved slide design still contains an older copy of those lines.
    slides = deck.slides_with_script((store.read_json(demo_id, "deck.json") or {}).get("slides", []),
                                    store.read_json(demo_id, "script.json") or {})

    def routed(r: dict) -> dict:  # where the answer lives — plain code on fact ids and topics, no model call; a decline never moves the slide
        r.update(deck.route_for(slides, cur_slide, r.get("fact_ids"), q) if r.get("answered") else {"slide_id": cur_slide, "route": "none", "callout_id": None, "by": ""})
        return r

    hit = faq.match(demo_id, q)
    if hit and not body.get("skip_bank"):
        und = store.read_json(demo_id, "understanding.json") or {}
        allowed = qa.approved_fact_ids(und, demo.get("settings", {}).get("competition") == "on")
        if set(hit.get("fact_ids") or []) - allowed:
            hit = None  # stale/rejected rival evidence must not bypass live QA
    if hit and not body.get("skip_bank"):
        # Old banks may predate the reviewed everyday renderings. Normalize a
        # response copy and retire mismatched audio without rewriting the bank.
        hit = faq.normalize_entry(hit, demo.get("settings", {}).get("audience", "everyday"), q)
        audio = voice._cached(demo_id, hit["answer"], voice.runtime_demo(demo_id, (body.get("profile") or {}).get("language")))
        r = {"from_bank": True, "bank_id": hit["id"], "audio": f"/media/{demo_id}/{audio}" if audio else None, "answer": hit["answer"], "fact_ids": hit["fact_ids"], "facts": [], "visual": hit.get("visual"),
             "escalate": "", "topic": "", "cta": "", "answered": hit["answered"], "clarifying_question": hit.get("clarifying_question", ""), "offer_callback": hit.get("offer_callback", not hit["answered"]),
             "plain_language_substitutions": hit.get("plain_language_substitutions", [])}
        routed(r)
        runlog.runtime_qa(demo_id, q, {**r, "answer": "[bank " + hit["id"] + "] " + r["answer"]}, body.get("profile") or None)
        return r
    try:
        r = await asyncio.to_thread(qa.answer, demo_id, q, body.get("history") or [], body.get("profile") or None, live=True)
    except RuntimeError as e:
        raise HTTPException(502, "The answer provider could not finish. Please try again.") from None
    r["from_bank"] = False
    routed(r)
    runlog.runtime_qa(demo_id, q, r, body.get("profile") or None)
    return r


@app.post("/api/demos/{demo_id}/run/pitch")
async def run_pitch(demo_id: str, req: Request):
    _demo_or_404(demo_id)
    usage.current_demo.set(demo_id)
    usage.current_stage.set("runtime")
    body = await _runtime_body(req)
    await run_in_threadpool(_runtime_visit, req, demo_id, body)
    if examples.is_cached_only(demo_id):
        return examples.cached_pitch(demo_id)
    if body.get("runtime_version") == 1 or (body.get("session_id") and (store.read_json(demo_id, "bundle.json") or {}).get("runtime", {}).get("version") == 1):
        from .runtime_graph import run_turn
        result = (await run_turn(demo_id, body, kind="explore"))["result"]
        return await run_in_threadpool(_grant_audio, req, demo_id, body, result)
    try:
        return await asyncio.to_thread(pitch.plan_pitch, demo_id, body.get("profile") or {}, bool(body.get("refine")))
    except RuntimeError as e:
        raise HTTPException(502, "The answer provider could not finish. Please try again.") from None


@app.post("/api/demos/{demo_id}/run/lead")
async def run_lead(demo_id: str, req: Request):
    _demo_or_404(demo_id)
    body = await _runtime_body(req)
    await run_in_threadpool(_runtime_visit, req, demo_id, body)
    if examples.is_cached_only(demo_id):
        raise HTTPException(409, "This portfolio example does not collect contact details or arrange dealership follow-ups.")
    phone = qa.parse_phone(body.get("phone") or body.get("text") or "")
    if not phone:
        raise HTTPException(400, "no valid Indian mobile number found")
    if not body.get("consent"):
        raise HTTPException(400, "consent required: the form shows one line of consent before a number is saved")
    lead = qa.save_lead(demo_id, phone, (body.get("question") or "").strip(), body.get("profile") or None, body.get("session_id"))
    lead["consent"], lead["consent_text"] = True, str(body.get("consent_text") or "")[:300]
    storage.backend().put_lead(demo_id, lead)
    storage.backend().after_write(demo_id)
    return {"ok": True, "lead": lead}


def _leads(demo_id: str) -> list[dict]:
    return storage.backend().list_leads(demo_id)


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
async def run_stt(demo_id: str, req: Request, file: UploadFile = File(...), language: str = Form(default="en-IN"), session_id: str = Form(default="")):
    await run_in_threadpool(auth.require_visit, req, demo_id, session_id)
    _demo_or_404(demo_id)
    if examples.is_cached_only(demo_id):
        raise HTTPException(409, "This free example uses recorded narration and typed questions. Live microphone input is available in your own demos.")
    usage.current_demo.set(demo_id)
    usage.current_stage.set("runtime")
    if config.STT_PROVIDER != "sarvam" and not config.MOCK_LLM:
        raise HTTPException(400, "server STT not configured (set SARVAM_API_KEY)")
    data = await file.read(8 * 1024 * 1024 + 1)
    if len(data) > 8 * 1024 * 1024:
        raise HTTPException(413, "Keep voice recordings under 8 MB")
    if len(data) < 1000:
        return {"transcript": ""}
    try:
        text = await asyncio.to_thread(sarvam.stt, data, file.filename or "audio.wav", language, file.content_type or "audio/wav")
    except Exception as e:
        raise HTTPException(502, "The speech provider could not finish. Please try again.") from None
    return {"transcript": text}


@app.post("/api/demos/{demo_id}/run/tts")
async def run_tts(demo_id: str, req: Request):
    _demo_or_404(demo_id)
    usage.current_demo.set(demo_id)
    usage.current_stage.set("runtime")
    body = await _runtime_body(req)
    await run_in_threadpool(_runtime_visit, req, demo_id, body)
    text = (body.get("text") or "").strip()
    if len(text) > 1500:
        raise HTTPException(400, "Keep spoken text under 1,500 characters")
    if not text:
        raise HTTPException(400, "text required")
    if examples.is_cached_only(demo_id):
        return {"url": examples.cached_audio(demo_id, text), "cached_only": True}
    try:
        identity = voice.runtime_demo(demo_id, body.get("language") or None)
        rel = await asyncio.to_thread(voice.render_line, demo_id, text, lang=identity.get("settings", {}).get("language"), demo=identity, strict=True)
    except Exception as e:
        raise HTTPException(502, "The voice provider could not finish. Please try again.") from None
    if rel:
        await run_in_threadpool(auth.grant_visit_media, req, demo_id, body.get("session_id"), rel)
    return {"url": f"/media/{demo_id}/{rel}" if rel else None}


_session_work_guard = threading.Lock()
_session_work_items = {}


def _session_work(demo_id: str, sid: str):
    """One small record lock and in-flight revision set per local session."""
    with _session_work_guard:
        key = (demo_id, sid)
        if key not in _session_work_items:
            _session_work_items[key] = (threading.Lock(), set())
        return _session_work_items[key]


def _session_revision(record: dict) -> str:
    # Count equality cannot identify changed words, profile, consent or timing.
    # Server bookkeeping is excluded so repeated Stop/Done/beacons share work.
    content = {k: v for k, v in record.items() if k not in {"summary", "saved_at", "save_seq"}}
    return hashlib.sha256(json.dumps(content, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()


@app.post("/api/demos/{demo_id}/run/session")
async def save_session(demo_id: str, req: Request):
    """Save incremental, final and tab-close snapshots as one visit.

    Sequenced clients own a monotonic snapshot counter. Retries and late beacons
    acknowledge the current record without replacing it. Historical clients keep
    their existing behavior until a sequenced snapshot takes ownership. Summary
    work runs only for an ended content revision, never for an autosave tick.
    """
    _demo_or_404(demo_id)
    body = await _runtime_body(req, limit=1048576)
    await run_in_threadpool(lambda: _runtime_visit(req, demo_id, body, session_field="id"))
    incoming_seq = body.get("save_seq")
    if "save_seq" in body and (type(incoming_seq) is not int or not 0 < incoming_seq <= 9007199254740991):
        raise HTTPException(400, "save_seq must be a positive safe integer")
    sid = re.sub(r"[^A-Za-z0-9_-]", "", str(body.get("id") or "")) or f"s_{int(time.time())}"
    body["id"] = sid
    body["saved_at"] = time.time()
    body.pop("summary", None)  # A client save cannot restore an old server-generated result.
    be = storage.backend()
    lock, _ = _session_work(demo_id, sid)
    with lock:
        prev = be.get_session(demo_id, sid) or {}
        previous_seq = prev.get("save_seq")
        if type(previous_seq) is int and previous_seq > 0 and (incoming_seq is None or incoming_seq <= previous_seq):
            # Keep the entire newest snapshot, including ended state, consent,
            # transcript and a revision-bound summary. A stale request cannot
            # reopen a visit or erase words already saved by a newer beacon.
            return {"ok": True, "id": sid, "share_key": _share_key(demo_id, sid),
                    "accepted": False, "save_seq": previous_seq}
        if body.get("input_mode") not in ("voice", "text"):
            # Old clients may omit this field; retain a known selection without
            # inventing a mode for historical sessions.
            if prev.get("input_mode") in ("voice", "text"):
                body["input_mode"] = prev["input_mode"]
            else:
                body.pop("input_mode", None)
        if prev.get("summary") and _session_revision(prev) == _session_revision(body):
            body["summary"] = prev["summary"]
        be.put_session(demo_id, body)
    be.after_write(demo_id)
    if body.get("ended") and not body.get("summary"):
        scope = await run_in_threadpool(auth.capture_job_scope, demo_id)
        threading.Thread(target=auth.run_scoped_job, args=(scope, _summarize_session, demo_id, sid), daemon=True, name=f"summary-{sid}").start()
    return {"ok": True, "id": sid, "share_key": _share_key(demo_id, sid),
            "accepted": True, **({"save_seq": incoming_seq} if incoming_seq is not None else {})}


def _summarize_session(demo_id: str, sid: str) -> None:
    """Coalesce identical work and attach only to its still-current ended session."""
    be = storage.backend()
    lock, pending = _session_work(demo_id, sid)
    with lock:
        s = be.get_session(demo_id, sid)
        if not s or not s.get("ended") or s.get("summary"):
            return
        revision = _session_revision(s)
        if revision in pending:
            return
        pending.add(revision)
    wrote = False
    try:
        # A plain Thread does not inherit request ContextVars. Provider work is
        # outside every record lock; unrelated sessions remain independent.
        demo_token = usage.current_demo.set(demo_id)
        stage_token = usage.current_stage.set("runtime")
        try:
            result = examples.cached_summary(demo_id, s) if examples.is_cached_only(demo_id) else _summary.summarize(demo_id, s)
        except Exception as e:  # noqa: BLE001
            result = {"error": "The visit summary could not finish.", "generated_at": time.time(), "transcript_lines": len(s.get("transcript", []))}
            store.log(demo_id, "summary-error", {"session": sid, "error_type": type(e).__name__})
        finally:
            usage.current_stage.reset(stage_token)
            usage.current_demo.reset(demo_token)
        with lock:
            latest = be.get_session(demo_id, sid)
            if latest and latest.get("ended") and _session_revision(latest) == revision and not latest.get("summary"):
                latest["summary"] = result
                be.put_session(demo_id, latest)
                wrote = True
    finally:
        with lock:
            pending.discard(revision)
    if wrote:
        be.after_write(demo_id)


def _share_secret() -> bytes:
    if config.SHARE_SECRET:
        return config.SHARE_SECRET.encode()
    p = config.DATA_DIR.parent / ".share-secret"
    if not p.exists():
        p.write_text(secrets.token_hex(32))
    return p.read_text().strip().encode()


def _share_key(demo_id: str, sid: str) -> str:
    return hmac.new(_share_secret(), f"{demo_id}/{sid}".encode(), hashlib.sha256).hexdigest()[:20]


def _public_view(s: dict) -> dict:
    """What a share link shows: the summary and the questions — phone numbers masked to their last four digits."""
    mask = lambda ph: ("•••••• " + str(ph)[-4:]) if ph else ""  # noqa: E731
    sm = dict(s.get("summary") or {})
    sm["leads"] = [{**l, "phone": mask(l.get("phone"))} for l in sm.get("leads", [])]
    public = {"id": s.get("id"), "saved_at": s.get("saved_at"), "minutes": s.get("minutes"), "profile": {"name": (s.get("profile") or {}).get("name", "")}, "cta": s.get("cta"), "intent": s.get("intent"),
              "questions": s.get("questions", []), "escalations": s.get("escalations", []), "summary": sm, "leads": [{"phone": mask(l.get("phone")), "question": l.get("question")} for l in s.get("leads", [])]}
    # Contact numbers can also occur in callback escalation strings, customer
    # questions or the model's sales opener. Mask the public copy recursively;
    # sales retains the original consented record and full private transcript.
    phone = re.compile(r"(?<!\d)(?:\+?91[\s-]*)?([6-9](?:[\s-]*\d){9})(?!\d)")
    def redact(value):
        if isinstance(value, str):
            return phone.sub(lambda match: mask(re.sub(r"\D", "", match.group(1))), value)
        if isinstance(value, list):
            return [redact(item) for item in value]
        if isinstance(value, dict):
            return {key: item if key in {"id", "slide_id"} else redact(item) for key, item in value.items()}
        return value
    return redact(public)


STAGES_MS = (("stt", "voice_ended", "stt_done"), ("qa", "stt_done", "qa_done"), ("tts", "qa_done", "answer_audio"), ("total", "voice_ended", "answer_audio"))


def _pct(values: list[float], q: float) -> float | None:
    """Nearest-rank percentile on a sorted copy; None when there is nothing to rank."""
    if not values:
        return None
    v = sorted(values)
    k = max(0, min(len(v) - 1, int(round(q * (len(v) - 1)))))
    return round(v[k])


def _latency(demo_id: str) -> dict:
    """Useful-answer latency, with an explicitly labelled legacy-only fallback."""
    from .runtime_metrics import response_kind, _duration
    turns = [tn for s in storage.backend().iter_sessions(demo_id) for tn in (s.get("turns") or [])]
    classified = any(response_kind(tn) != "legacy_all_responses" for tn in turns)
    eligible = [tn for tn in turns if not tn.get("failed") and not tn.get("cancelled") and (response_kind(tn) == "answer" if classified else True)]
    out = {"turns": len(turns), "eligible_turns":len(eligible), "scope":"useful_answers" if classified else "legacy_all_responses", "response_counts":{kind:sum(response_kind(tn)==kind for tn in turns) for kind in ("answer","clarification","decline","legacy_all_responses")}, "sessions_with_turns": sum(1 for s in storage.backend().iter_sessions(demo_id) if s.get("turns")), "stages": {}}
    for name, a, b in STAGES_MS:
        vals = [value for tn in eligible if (value := _duration(tn,a,b)) is not None]
        out["stages"][name] = {"n": len(vals), "p50": _pct(vals, 0.5), "p95": _pct(vals, 0.95)}
    out["by_source"] = {k: sum(1 for tn in eligible if (tn.get("from_bank") and k == "bank") or (not tn.get("from_bank") and k == "model")) for k in ("bank", "model")}
    return out


def _sessions(demo_id: str) -> list[dict]:
    return storage.backend().list_sessions(demo_id, 20)


@app.get("/api/demos/{demo_id}/sessions")
def list_sessions(demo_id: str):
    _demo_or_404(demo_id)
    return {"sessions": storage.backend().list_sessions(demo_id), "storage": storage.backend().status()}


@app.get("/api/demos/{demo_id}/sessions/{sid}")
def get_session(demo_id: str, sid: str):
    _demo_or_404(demo_id)
    s = storage.backend().get_session(demo_id, sid)
    if not s:
        raise HTTPException(404)
    return {**s, "share_key": _share_key(demo_id, sid)}


@app.get("/api/share/{demo_id}/{sid}")
def share_session(demo_id: str, sid: str, request: Request, k: str = ""):
    """The owning visitor or creator can view a signed, minimized recap."""
    if auth.enabled():
        user = auth.current_user(request)
        if not user or auth.owner_for(demo_id) != user["id"]:
            auth.require_visit(request, demo_id, sid)
    if not store.exists(demo_id) or not k or not hmac.compare_digest(k, _share_key(demo_id, sid)):
        raise HTTPException(403, "this link is not valid")
    s = storage.backend().get_session(demo_id, sid)
    if not s:
        raise HTTPException(404)
    return _public_view(s)


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


@app.middleware("http")
async def _revalidate_static(request: Request, call_next):
    """The no-build front end is plain ES modules: without a cache policy a browser reuses a recently fetched module by
    heuristic freshness (a reload only revalidates the document), so a deploy could mix old and new modules. `no-cache`
    means revalidate every time — with the ETag that is a cheap 304 when nothing changed."""
    resp = await call_next(request)
    path = request.url.path
    if path == "/" or path.startswith("/web/") or path.endswith((".html", ".js", ".css")):
        resp.headers["Cache-Control"] = "no-cache"
    return resp


app.mount("/web", StaticFiles(directory=str(config.WEB_DIR)), name="web")


@app.exception_handler(Exception)
async def on_error(request: Request, exc: Exception):
    # Avoid returning provider payloads, filesystem paths or database credentials.
    import logging
    logging.getLogger("demo-studio").error("request_failed type=%s", type(exc).__name__)
    return JSONResponse(status_code=500, content={"detail": "This request could not finish. Please try again."})
