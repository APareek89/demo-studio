"""Human-readable run log per demo: data/demos/<id>/RUN.md.

Reads top to bottom like the build happened: every user input (sources with the text that was extracted,
settings, chat, approvals), and for every stage an INPUT block (exactly which files and settings it read),
an OUTPUT block (everything it produced, in full, folded where long) and every MODEL CALL with the full
system prompt, the full input and the full response. Written by hooks in app.py and orchestrator.py; never
raises (logging must not break a build). Open it in VS Code; the Markdown preview renders tables and folds."""
from __future__ import annotations

import json
import time

from . import store, usage

FILE = "RUN.md"


# ---------- primitives ----------

def _ts(t: float | None = None) -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(t or time.time()))


def _fence(text: str, lang: str = "") -> str:
    text = (text or "").replace("```", "'''")
    return f"```{lang}\n{text}\n```"


def _json(obj) -> str:
    try:
        return _fence(json.dumps(obj, ensure_ascii=False, indent=1), "json")
    except Exception:
        return _fence(str(obj))


def _details(summary: str, body: str) -> str:
    return f"<details><summary>{summary}</summary>\n\n{body}\n\n</details>"


def _cell(v) -> str:
    return str(v if v is not None else "").replace("|", "/").replace("\n", " ").strip()


def _table(headers: list[str], rows: list[list]) -> str:
    if not rows:
        return "_none_"
    out = ["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers)]
    for r in rows:
        out.append("| " + " | ".join(_cell(c) for c in r) + " |")
    return "\n".join(out)


def _size(demo_id: str, rel: str | None) -> str:
    try:
        n = store.path(demo_id, rel).stat().st_size
        return f"{n / 1e6:.1f} MB" if n > 1e6 else f"{n / 1e3:.0f} KB"
    except Exception:
        return "—"


def append(demo_id: str, md: str) -> None:
    try:
        p = store.path(demo_id, FILE)
        p.parent.mkdir(parents=True, exist_ok=True)
        if not p.exists():
            demo = store.load(demo_id)
            p.write_text(f"# Run log — {demo.get('name', demo_id)} (`{demo_id}`)\n\n"
                         "Every input and every stage output, in order, in full. For each stage: **INPUT** (what it read), **OUTPUT** (what it wrote) "
                         "and **MODEL CALLS** (full system prompt, input and response, folded). The same call rows live in `trace.jsonl` "
                         "(Observability tab). Times are local.\n", encoding="utf-8")
        with p.open("a", encoding="utf-8") as f:
            f.write("\n" + md.rstrip() + "\n")
    except Exception:
        pass


def event(demo_id: str, title: str, body: str = "") -> None:
    append(demo_id, f"## {_ts()} · {title}\n\n{body}".rstrip())


# ---------- user inputs ----------

def sources_added(demo_id: str, sources: list[dict]) -> None:
    rows = [[s.get("kind"), s.get("name") or s.get("url"), _size(demo_id, s.get("path")) if s.get("path") else "", s.get("role"), "yes" if s.get("use_in_demo", True) else "no", s.get("id")] for s in sources]
    body = _table(["kind", "name / url", "size", "role", "use in demo", "id"], rows)
    for s in sources:
        if s.get("kind") == "text" and s.get("path"):
            try:
                txt = store.path(demo_id, s["path"]).read_text(errors="replace")
                body += "\n\n" + _details(f"pasted text · {s.get('name')} · {len(txt)} chars (full)", _fence(txt))
            except Exception:
                pass
    event(demo_id, f"Sources added ({len(sources)})", body)


def settings_changed(demo_id: str, changed: dict) -> None:
    event(demo_id, "Settings changed", _table(["setting", "value"], [[k, json.dumps(v, ensure_ascii=False)] for k, v in changed.items()]))


def chat(demo_id: str, context: str, message: str, reply: str, actions: list[dict] | None, attachments: list[dict] | None = None) -> None:
    body = f"**User ({context}):** {message or '(attachment only)'}\n\n**Agent:** {reply}"
    if attachments:
        body += "\n\nAttachments: " + ", ".join(a.get("name", "?") for a in attachments)
    if actions:
        body += "\n\nActions the agent chose (executed by the orchestrator):\n\n" + _json(actions)
    event(demo_id, "Alignment message", body)


# ---------- stage reports ----------

def _calls(demo_id: str, stage: str, since: float | None) -> str:
    rows = [r for r in usage.traces(demo_id, limit=5000) if r.get("stage") == stage and (since is None or r.get("t", 0) >= since - 1)]
    if not rows:
        return "_no model calls recorded for this stage_"
    head = _table(["#", "call", "model", "latency", "tokens in / out", "chars", "cost", "status"],
                  [[i + 1, r.get("kind"), r.get("model"), f"{(r.get('latency_ms') or 0) / 1000:.1f} s", f"{r.get('in', 0):,} / {r.get('out', 0):,}", r.get("chars") or "", f"${r.get('usd', 0):.4f}", "error" if r.get("error") else "ok"] for i, r in enumerate(rows)])
    parts = [head]
    seen_system = set()
    for i, r in enumerate(rows):
        body = ""
        sysm = r.get("system") or ""
        if sysm and sysm not in seen_system:
            seen_system.add(sysm)
            body += f"**System prompt** ({len(sysm):,} chars)\n\n" + _fence(sysm) + "\n\n"
        elif sysm:
            body += "_System prompt: same as an earlier call in this stage._\n\n"
        body += f"**Input sent to the model** ({len(r.get('user') or ''):,} chars)\n\n" + _fence(r.get("user") or "") + f"\n\n**Response** ({len(r.get('response') or ''):,} chars)\n\n" + _fence(r.get("response") or "")
        if r.get("error"):
            body += "\n\n**Error**\n\n" + _fence(r["error"])
        parts.append(_details(f"call {i + 1} · {r.get('kind')} · {r.get('model')} · {(r.get('latency_ms') or 0) / 1000:.1f} s · {r.get('in', 0):,} in / {r.get('out', 0):,} out", body))
    return "\n\n".join(parts)


def _inputs(demo_id: str, stage: str, demo: dict) -> str:
    st = demo.get("settings", {})
    rows = []
    if stage == "understand":
        rows += [[f"{s.get('kind')} · {s.get('name') or s.get('url')}", _size(demo_id, s.get("path")) if s.get("path") else "url", f"role {s.get('role')} · {'used in demo' if s.get('use_in_demo', True) else 'learn only'}"] for s in demo.get("sources", [])]
        rows.append(["product hint", "", f"{demo.get('product', {}).get('name', '')} · {demo.get('product', {}).get('url', '')}"])
    if stage == "plan":
        rows += [["understanding.json", _size(demo_id, "understanding.json"), "facts, unknowns, shots, images, brand"]]
    if stage == "author":
        rows += [["plan.json", _size(demo_id, "plan.json"), "decision frame, segments, USPs, CTAs, voice"], ["understanding.json", _size(demo_id, "understanding.json"), "fact registry (only these ids may be cited)"]]
        if store.path(demo_id, "script.json").exists():
            rows.append(["script.json (previous)", _size(demo_id, "script.json"), "revised in place, ids kept"])
    if stage == "voice":
        rows += [["script.json", _size(demo_id, "script.json"), "every narration, deeper, check-in and closing line"], ["faq.json + filler lines", _size(demo_id, "faq.json"), "FAQ answers and the persona's acknowledgement / bridge / hold lines, all pre-recorded"]]
    if stage == "faq":
        rows += [["understanding.json + plan.json", "", "questions generated from product, persona, concerns and facts; FAQ documents (role faq) add their own"], ["qa.answer", "", "every answer goes through the grounded runtime path"]]
    if stage == "rehearsal":
        rows += [["understanding.json + plan.json", "", "questions are generated from the product, persona, concerns and facts"], ["script.json", _size(demo_id, "script.json"), "scored against the playbook"]]
    if stage == "bundle":
        rows += [["understanding.json · plan.json · script.json" + (" · script.<lang>.json" if len(st.get("languages") or []) > 1 else ""), "", "assembled into bundle.json"]]
    if stage in ("plan", "author", "voice", "rehearsal"):
        rows.append(["settings", "", f"audience {st.get('audience')} · language {st.get('language')} · languages {st.get('languages')} · pitch minutes {st.get('pitch_minutes')} · voice {st.get('sarvam_speaker') or st.get('voice_name') or 'default'} · competition {st.get('competition')} · rehearsal questions {st.get('rehearsal_questions', 12)}"])
    return _table(["read", "size", "what for"], rows)


def _understand(demo_id: str) -> str:
    u = store.read_json(demo_id, "understanding.json") or {}
    demo = store.load(demo_id)
    facts = u.get("facts", [])
    out = [f"**Product:** {u.get('product', {}).get('name', '')} · {u.get('product', {}).get('category', '')}",
           f"**Registry:** {len(facts)} facts · {len(u.get('unknowns', []))} open questions · {len(u.get('shots', []))} video shots · {len(u.get('images', []))} images · {len(u.get('competitors', []))} competitor pages"]
    out.append(_details(f"all {len(facts)} facts (id, kind, truth, claim, value, conditions, source)", _table(["id", "kind", "truth", "claim", "value", "conditions", "source"], [[f.get("id"), f.get("kind"), f.get("truth"), f.get("claim"), f.get("value"), f.get("conditions"), (f.get("source") or {}).get("ref") if isinstance(f.get("source"), dict) else f.get("source_id")] for f in facts])))
    unk = u.get("unknowns", [])
    if unk:
        out.append(_details(f"{len(unk)} open questions (the guide will decline these)", _table(["id", "category", "question", "document that would answer it", "status"], [[x.get("id"), x.get("category"), x.get("question"), x.get("suggested_document"), x.get("status")] for x in unk])))
    if u.get("shots"):
        out.append(_details(f"{len(u['shots'])} video shots", _table(["id", "source", "start–end", "part", "quality", "description"], [[s.get("id"), s.get("source_id"), f"{s.get('start', 0):.0f}–{s.get('end', 0):.0f}s", s.get("part"), s.get("quality"), s.get("description")] for s in u["shots"]])))
    if u.get("images"):
        src_by = {s["id"]: s for s in demo.get("sources", [])}
        out.append(_details(f"{len(u['images'])} images as the model saw them", _table(["id", "file", "angle", "parts visible", "quality", "description", "clean-up"], [[i.get("id"), src_by.get(i.get("source_id"), {}).get("name"), i.get("angle"), ", ".join(i.get("parts", []) or []), i.get("quality"), i.get("description"), (src_by.get(i.get("source_id"), {}).get("enhanced") or {}).get("why", "")] for i in u["images"]])))
    if u.get("video_summaries"):
        out.append(_details("video summaries", _json(u["video_summaries"])))
    if u.get("brand"):
        out.append(_details("brand profile", _json(u["brand"])))
    if u.get("competitors"):
        out.append(_details(f"{len(u['competitors'])} competitor pages", _json(u["competitors"])))
    return "\n\n".join(out)


def _plan(demo_id: str) -> str:
    p = store.read_json(demo_id, "plan.json") or {}
    out = [f"**Decision frame:** {p.get('decision_frame', '')}", f"**Takeaway:** {p.get('takeaway', '')}", f"**Primary outcome:** {p.get('primary_outcome', '')}",
           "**Supporting outcomes:** " + "; ".join(p.get("supporting_outcomes", []) or []),
           f"**Customer persona:** {p.get('customer_persona', '')}", f"**Advance:** {p.get('advance', '')}", f"**Do not recommend if:** {p.get('do_not_recommend_if', '')}"]
    segs = p.get("segments", [])
    out.append(_table(["#", "segment", "role", "topic", "outcome", "USPs", "priority", "visuals"], [[i + 1, s.get("title"), s.get("role"), s.get("topic"), s.get("outcome"), ",".join(s.get("usp_ids", []) or []), "yes" if s.get("priority_topic") else "", ",".join((v.get("ref") if isinstance(v, dict) else str(v)) for v in (s.get("visuals") or []))] for i, s in enumerate(segs)]))
    if p.get("usps"):
        out.append(_details("USPs", _json(p["usps"])))
    if p.get("ctas"):
        out.append("**CTAs:** " + "; ".join(f"{c.get('label')} ({c.get('kind')}{', primary' if c.get('primary') else ''})" for c in p["ctas"]))
    out.append(_details("plan.json in full", _json(p)))
    return "\n\n".join(out)


def _script_md(sc: dict, title: str) -> str:
    lines = [f"**Intake:** {sc.get('intake_q1', '')} / {sc.get('intake_q2', '')}"]
    for s in sc.get("segments", []):
        lines.append(f"\n**{s.get('id')} · {s.get('title')}** — role `{s.get('role')}` · topic {s.get('topic')} · outcome: {s.get('outcome', '')}")
        for l in s.get("lines", []):
            v = l.get("visual") or {}
            flag = " ⚠ unverified (held back)" if l.get("unverified") else ""
            lines.append(f"- {l.get('text')}  ·  facts {','.join(l.get('fact_ids', []) or []) or '—'} · visual {v.get('ref') or '—'}{(' (' + v.get('focus') + ')') if v.get('focus') else ''} · card {l.get('card', 'none')} · audio {'yes' if l.get('audio') else 'no'}{flag}")
        if s.get("checkin"):
            lines.append(f"- _check-in:_ {s['checkin']}")
        for l in s.get("deeper", []):
            lines.append(f"- _deeper (only if asked):_ {l.get('text')} · facts {','.join(l.get('fact_ids', []) or []) or '—'}")
    lines.append("\n**Closing**")
    for l in sc.get("closing", []):
        lines.append(f"- {l.get('text')} · facts {','.join(l.get('fact_ids', []) or []) or '—'}")
    n = sum(len(s.get("lines", [])) for s in sc.get("segments", []))
    words = sum(len((l.get("text") or "").split()) for s in sc.get("segments", []) for l in s.get("lines", []))
    return _details(f"{title} · {len(sc.get('segments', []))} segments · {n} lines · {words} spoken words", "\n".join(lines))


def _visuals_log(demo_id: str) -> str:
    v = _last_log(demo_id, "visuals")
    if not v:
        return ""
    body = f"Catalogue the matcher could choose from: {len(v.get('catalogue', []))} pictures/shots.\n\n"
    body += _table(["line", "was", "now", "pass", "why"], [[c.get("line_id"), c.get("from") or "—", c.get("to"), c.get("pass"), c.get("why")] for c in v.get("changes", [])]) if v.get("changes") else "No line needed a different picture."
    if v.get("unused_after"):
        body += f"\n\nStill unused after alignment: {', '.join(v['unused_after'])} (nothing spoken matches them)."
    if v.get("model"):
        body += "\n\n" + _details("model decisions on the unsure lines", _table(["line", "visual", "reason"], [[m.get("line_id"), m.get("visual"), m.get("reason")] for m in v["model"]]))
    return _details(f"visual alignment — {len(v.get('changes', []))} line(s) re-pictured so the screen shows what is being said", body)


def _author(demo_id: str) -> str:
    sc = store.read_json(demo_id, "script.json") or {}
    logs = _last_log(demo_id, "author")
    out = []
    if logs:
        out.append("**Validator (no citation, no claim; word budgets; jargon):** " + _json(logs))
    tl = sc.get("timeline") or {}
    if tl:
        out.append(f"**Timeline:** {tl.get('total_seconds', 0):.0f} s total ({'exact from audio' if tl.get('exact') else 'estimated at 2.5 words/s'}) · " + _table(["batch", "role", "starts at", "seconds", "> 20 s?"], [[b.get("title"), b.get("role"), f"{int(b.get('start', 0)) // 60}:{int(b.get('start', 0)) % 60:02d}", b.get("duration"), "⚠ yes" if b.get("over_20s") else ""] for b in tl.get("batches", [])]))
    out.append(_script_md(sc, "full script as written"))
    vis = _visuals_log(demo_id)
    if vis:
        out.append(vis)
    out.append(_details("script.json in full", _json(sc)))
    return "\n\n".join(out)


def _voice(demo_id: str) -> str:
    demo = store.load(demo_id)
    sc = store.read_json(demo_id, "script.json") or {}
    n = sum(1 for s in sc.get("segments", []) for l in s.get("lines", []) if l.get("audio"))
    total = sum(len(s.get("lines", [])) for s in sc.get("segments", []))
    out = [f"**Provider:** {sc.get('voice_provider')} · voice {sc.get('voice_name')} · {n}/{total} narration lines have audio · failures {sc.get('voice_failures', 0)}"]
    rows = []
    for s in sc.get("segments", []):
        for l in s.get("lines", []) + s.get("deeper", []):
            rows.append([l.get("id"), (l.get("text") or "")[:90], l.get("audio") or "— (browser voice)", _size(demo_id, l.get("audio")) if l.get("audio") else ""])
        if s.get("checkin"):
            rows.append([f"{s.get('id')} check-in", s["checkin"][:90], s.get("checkin_audio") or "—", _size(demo_id, s.get("checkin_audio")) if s.get("checkin_audio") else ""])
    for l in sc.get("closing", []):
        rows.append([l.get("id"), (l.get("text") or "")[:90], l.get("audio") or "—", _size(demo_id, l.get("audio")) if l.get("audio") else ""])
    out.append(_details(f"every line → audio file ({len(rows)} lines)", _table(["line", "text", "audio file", "size"], rows)))
    for lang in demo.get("settings", {}).get("languages", []) or []:
        if lang == demo.get("settings", {}).get("language"):
            continue
        alt = store.read_json(demo_id, f"script.{lang}.json")
        if alt:
            na = sum(1 for s in alt.get("segments", []) for l in s.get("lines", []) if l.get("audio"))
            kept = [l.get("id") for s in alt.get("segments", []) for l in s.get("lines", []) + s.get("deeper", []) if l.get("kept_source")]
            out.append(f"**{lang}:** {na} lines with audio · {len(kept)} kept in the main language because the translation changed a figure" + (f" ({', '.join(kept)})" if kept else ""))
            out.append(_script_md(alt, f"{lang} script"))
    return "\n\n".join(out)


def _rehearsal(demo_id: str) -> str:
    r = store.read_json(demo_id, "rehearsal.json") or {}
    if r.get("skipped"):
        return "_skipped_"
    out = [f"**Coverage:** {r.get('coverage')} · gaps: {len(r.get('gaps', []))}"]
    out.append(_table(["#", "question", "answered", "facts cited", "answer (full)"], [[i + 1, q.get("question"), "yes" if q.get("answered") else "no", ",".join(q.get("fact_ids", []) or []), q.get("answer") or ""] for i, q in enumerate(r.get("questions", []))]))
    if r.get("gaps"):
        out.append("**Gaps:** " + "; ".join(str(g) for g in r["gaps"]))
    sc = r.get("scorecard") or {}
    if sc:
        out.append(f"**Scorecard:** {sc.get('total')} / 20")
        out.append(_table(["criterion", "score", "note"], [[c.get("name"), c.get("score"), c.get("note")] for c in sc.get("criteria", [])]))
        if sc.get("fixes"):
            out.append("**Fix first:** " + " · ".join(str(x) for x in sc["fixes"]))
    return "\n\n".join(out)


def _bundle(demo_id: str) -> str:
    b = store.read_json(demo_id, "bundle.json") or {}
    n = sum(len(s.get("lines", [])) for s in b.get("segments", []))
    rows = [[s.get("id"), s.get("role"), s.get("title"), len(s.get("lines", [])), ",".join(sorted({(l.get("visual") or {}).get("ref") or "—" for l in s.get("lines", [])})), sum(1 for l in s.get("lines", []) if l.get("audio"))] for s in b.get("segments", [])]
    return "\n\n".join([
        f"**bundle.json v{b.get('version')}** · {len(b.get('segments', []))} segments · {n} lines · languages {b.get('languages')} · {len(b.get('facts', []))} facts · {len(b.get('ctas', []))} CTAs · voice {b.get('voice', {}).get('provider')}" + (f" · mascot {b.get('mascot')}" if b.get("mascot") else ""),
        _table(["segment", "role", "title", "lines", "visuals used", "lines with audio"], rows),
        f"**Media:** {len(b.get('media', {}).get('images', []))} images · {len(b.get('media', {}).get('videos', []))} videos · hero {b.get('media', {}).get('hero')}",
        _details("pitch block (decision frame, takeaway, outcomes, USPs, advance)", _json(b.get("pitch", {}))),
        f"Play it: Studio › Rehearse, or `GET /api/demos/{demo_id}/bundle`.",
    ])


def _last_log(demo_id: str, stage: str) -> dict | None:
    """store.log writes logs/<epoch>-<stage>.json; return the newest one for the stage."""
    try:
        files = sorted(store.path(demo_id, "logs").glob(f"*-{stage}.json"))
        return json.loads(files[-1].read_text()) if files else None
    except Exception:
        return None


def _faq(demo_id: str) -> str:
    b = store.read_json(demo_id, "faq.json") or {}
    return f"**{b.get('answered', 0)} of {b.get('total', 0)} answered from the sources** (the rest decline and offer a callback — instant at runtime)\n\n" + _table(["id", "origin", "question", "answered", "facts", "answer (full)", "audio"], [[e.get("id"), e.get("origin"), e.get("question"), "yes" if e.get("answered") else "no", ",".join(e.get("fact_ids", []) or []), e.get("answer"), "yes" if e.get("audio") else "not yet"] for e in b.get("entries", [])])


_REPORTS = {"understand": _understand, "plan": _plan, "author": _author, "faq": _faq, "voice": _voice, "rehearsal": _rehearsal, "bundle": _bundle}


def stage_report(demo_id: str, stage: str, *, seconds: float | None = None, started_at: float | None = None, instruction: str = "") -> None:
    """Append the section for one finished stage: INPUT it read, OUTPUT it wrote, every MODEL CALL in full."""
    try:
        demo = store.load(demo_id)
        rows = [r for r in usage.traces(demo_id, limit=5000) if r.get("stage") == stage and (started_at is None or r.get("t", 0) >= started_at - 1)]
        cost = sum(r.get("usd", 0) for r in rows)
        head = f"### {stage.upper()} · {f'{seconds:.0f} s' if seconds is not None else '—'} · {len(rows)} model calls · ${cost:.3f}"
        body = "**INPUT**\n\n" + _inputs(demo_id, stage, demo)
        if instruction:
            body += f"\n\nInstruction from the user / align agent: {instruction}"
        body += "\n\n**OUTPUT**\n\n" + _REPORTS[stage](demo_id) + "\n\n**MODEL CALLS**\n\n" + _calls(demo_id, stage, started_at)
        append(demo_id, head + "\n\n" + body)
    except Exception as e:
        append(demo_id, f"### {stage.upper()} · report failed: {str(e)[:200]}")


def stage_failed(demo_id: str, stage: str, error: str) -> None:
    append(demo_id, f"### {stage.upper()} · FAILED\n\n{_fence(error)}")


def phase_done(demo_id: str, phase: str) -> None:
    try:
        u = usage.summary(demo_id)
        demo = store.load(demo_id)
        stages = demo.get("stages", {})
        rows = [[k, v.get("status"), v.get("seconds")] for k, v in stages.items()]
        event(demo_id, f"{phase.upper()} finished → status `{demo.get('status')}`",
              _table(["stage", "status", "seconds"], rows) + f"\n\n**Cost so far:** ${u.get('total_usd', 0):.3f} ≈ ₹{u.get('total_inr', 0):.0f} over {u.get('rows', 0)} calls")
    except Exception:
        pass


def runtime_qa(demo_id: str, question: str, result: dict, profile: dict | None) -> None:
    append(demo_id, f"- {_ts()} · **Q&A** ({(profile or {}).get('name', 'anonymous')}): {question} → {'answered' if result.get('answered') else 'declined'} · facts {result.get('fact_ids')} · {(result.get('answer') or '')}")


def backfill(demo_id: str) -> str:
    """Write RUN.md for a demo built before run logs existed, from what is on disk."""
    p = store.path(demo_id, FILE)
    if p.exists():
        p.unlink()
    demo = store.load(demo_id)
    event(demo_id, "Backfilled from disk", f"This demo was built before run logs existed; sections below are reconstructed from demo.json, stage outputs and trace.jsonl. Created {_ts(demo.get('created_at'))}.")
    sources_added(demo_id, demo.get("sources", []))
    settings_changed(demo_id, demo.get("settings", {}))
    conv = store.read_json(demo_id, "conversation.json") or []
    if conv:
        event(demo_id, f"Alignment conversation ({len(conv)} messages)", "\n\n".join(f"**{m.get('role')}:** {m.get('text', '')}" + (("\n\n" + _json(m.get("actions"))) if m.get("actions") else "") for m in conv))
    event(demo_id, "Approvals", _table(["card", "approved"], [[k, "yes" if v else "no"] for k, v in demo.get("approvals", {}).items()]))
    for stage in store.STAGES:
        st = demo.get("stages", {}).get(stage, {})
        if st.get("status") == "done":
            stage_report(demo_id, stage, seconds=st.get("seconds"), started_at=st.get("started_at"))
        elif st.get("status") == "error":
            stage_failed(demo_id, stage, st.get("error") or "")
    phase_done(demo_id, "backfill")
    return str(p)
