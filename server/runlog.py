"""Human-readable run log per demo: data/demos/<id>/RUN.md.

One Markdown file that reads top to bottom like the build happened — what the user put in (sources,
settings, chat, approvals), what each stage received and produced, every model call with its prompt and
response (folded), timings and cost. Written by hooks in app.py and orchestrator.py; never raises (logging
must not break a build). Open it in VS Code; the preview renders the tables and the folded prompts."""
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


def append(demo_id: str, md: str) -> None:
    try:
        p = store.path(demo_id, FILE)
        p.parent.mkdir(parents=True, exist_ok=True)
        if not p.exists():
            demo = store.load(demo_id)
            p.write_text(f"# Run log — {demo.get('name', demo_id)} (`{demo_id}`)\n\n"
                         "Every input and every stage output, in order. Model prompts and responses are folded under each call; "
                         "the same rows live in `trace.jsonl` (Observability tab). Times are local.\n")
        with p.open("a", encoding="utf-8") as f:
            f.write("\n" + md.rstrip() + "\n")
    except Exception:
        pass


def event(demo_id: str, title: str, body: str = "") -> None:
    append(demo_id, f"## {_ts()} · {title}\n\n{body}".rstrip())


# ---------- user inputs ----------

def sources_added(demo_id: str, sources: list[dict]) -> None:
    rows = [[s.get("kind"), s.get("name") or s.get("url"), f"{(s.get('size') or 0) / 1e6:.1f} MB" if s.get("size") else "", s.get("role"), "yes" if s.get("use_in_demo", True) else "no"] for s in sources]
    body = _table(["kind", "name / url", "size", "role", "use in demo"], rows)
    for s in sources:
        if s.get("kind") == "text" and s.get("path"):
            try:
                txt = store.path(demo_id, s["path"]).read_text(errors="replace")
                body += "\n\n" + _details(f"pasted text · {s.get('name')} · {len(txt)} chars", _fence(txt[:20000]))
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
        body += "\n\nActions executed:\n" + "\n".join(f"- `{a.get('type')}` {json.dumps({k: v for k, v in a.items() if k != 'type'}, ensure_ascii=False)[:300]}" for a in actions)
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
            body += "**System prompt**\n\n" + _fence(sysm) + "\n\n"
        elif sysm:
            body += "_System prompt: same as above._\n\n"
        body += "**Input**\n\n" + _fence(r.get("user") or "") + "\n\n**Response**\n\n" + _fence(r.get("response") or "")
        if r.get("error"):
            body += "\n\n**Error**\n\n" + _fence(r["error"])
        parts.append(_details(f"call {i + 1} · {r.get('kind')} · {r.get('model')} · {(r.get('latency_ms') or 0) / 1000:.1f} s", body))
    return "\n\n".join(parts)


def _understand(demo_id: str) -> str:
    u = store.read_json(demo_id, "understanding.json") or {}
    facts = u.get("facts", [])
    out = [f"**Product:** {u.get('product', {}).get('name', '')} · {u.get('product', {}).get('category', '')}",
           f"**Registry:** {len(facts)} facts · {len(u.get('unknowns', []))} open questions · {len(u.get('shots', []))} video shots · {len(u.get('images', []))} images · {len(u.get('competitors', []))} competitor pages"]
    out.append(_details(f"all {len(facts)} facts", _table(["id", "kind", "truth", "claim", "value", "conditions", "source"], [[f.get("id"), f.get("kind"), f.get("truth"), f.get("claim"), f.get("value"), f.get("conditions"), f.get("source_id")] for f in facts])))
    unk = u.get("unknowns", [])
    if unk:
        out.append(_details(f"{len(unk)} open questions (the guide will decline these)", _table(["id", "category", "question", "document that would answer it", "status"], [[x.get("id"), x.get("category"), x.get("question"), x.get("suggested_document"), x.get("status")] for x in unk])))
    if u.get("shots"):
        out.append(_details(f"{len(u['shots'])} video shots", _table(["id", "start–end", "part", "quality", "description"], [[s.get("id"), f"{s.get('start', 0):.0f}–{s.get('end', 0):.0f}s", s.get("part"), s.get("quality"), s.get("description")] for s in u["shots"]])))
    if u.get("images"):
        out.append(_details(f"{len(u['images'])} images", _table(["id", "angle", "quality", "description"], [[i.get("id"), i.get("angle"), i.get("quality"), i.get("description")] for i in u["images"]])))
    if u.get("brand"):
        out.append(_details("brand profile", _fence(json.dumps(u["brand"], ensure_ascii=False, indent=1), "json")))
    return "\n\n".join(out)


def _plan(demo_id: str) -> str:
    p = store.read_json(demo_id, "plan.json") or {}
    out = [f"**Decision frame:** {p.get('decision_frame', '')}", f"**Takeaway:** {p.get('takeaway', '')}", f"**Primary outcome:** {p.get('primary_outcome', '')}",
           "**Supporting outcomes:** " + "; ".join(p.get("supporting_outcomes", []) or []),
           "**USPs:** " + "; ".join((x.get("text") or x.get("title") or json.dumps(x, ensure_ascii=False)) if isinstance(x, dict) else str(x) for x in p.get("usps", []) or []),
           f"**Persona / voice:** {json.dumps(p.get('voice', {}), ensure_ascii=False)[:600]}",
           f"**Customer persona:** {p.get('customer_persona', '')}", f"**Advance:** {p.get('advance', '')}", f"**Do not recommend if:** {p.get('do_not_recommend_if', '')}"]
    segs = p.get("segments", [])
    out.append(_table(["#", "segment", "role", "topic", "outcome", "USPs", "priority"], [[i + 1, s.get("title"), s.get("role"), s.get("topic"), s.get("outcome"), ",".join(s.get("usp_ids", []) or []), "yes" if s.get("priority_topic") else ""] for i, s in enumerate(segs)]))
    if p.get("ctas"):
        out.append("**CTAs:** " + "; ".join(f"{c.get('label')} ({c.get('kind')}{', primary' if c.get('primary') else ''})" for c in p["ctas"]))
    if p.get("intake"):
        out.append("**Intake chips:** " + ", ".join(c.get("label", "") for c in p["intake"].get("chips", []) if isinstance(c, dict)))
    return "\n\n".join(out)


def _script_md(sc: dict, title: str) -> str:
    lines = [f"**Intake:** {sc.get('intake_q1', '')} / {sc.get('intake_q2', '')}"]
    for s in sc.get("segments", []):
        lines.append(f"\n**{s.get('id')} · {s.get('title')}** — role `{s.get('role')}` · topic {s.get('topic')}")
        for l in s.get("lines", []):
            v = l.get("visual") or {}
            flag = " ⚠ unverified" if l.get("unverified") else ""
            lines.append(f"- {l.get('text')}  ·  facts {','.join(l.get('fact_ids', []) or []) or '—'} · visual {v.get('ref') or '—'} · card {l.get('card', 'none')} · audio {'yes' if l.get('audio') else 'no'}{flag}")
        if s.get("checkin"):
            lines.append(f"- _check-in:_ {s['checkin']}")
        for l in s.get("deeper", []):
            lines.append(f"- _deeper:_ {l.get('text')} · facts {','.join(l.get('fact_ids', []) or []) or '—'}")
    lines.append("\n**Closing**")
    for l in sc.get("closing", []):
        lines.append(f"- {l.get('text')}")
    n = sum(len(s.get("lines", [])) for s in sc.get("segments", []))
    words = sum(len((l.get("text") or "").split()) for s in sc.get("segments", []) for l in s.get("lines", []))
    return _details(f"{title} · {len(sc.get('segments', []))} segments · {n} lines · {words} words", "\n".join(lines))


def _author(demo_id: str) -> str:
    sc = store.read_json(demo_id, "script.json") or {}
    logs = _last_log(demo_id, "author")
    out = []
    if logs:
        out.append(f"**Validator:** {json.dumps(logs, ensure_ascii=False)[:800]}")
    out.append(_script_md(sc, "full script"))
    return "\n\n".join(out)


def _voice(demo_id: str) -> str:
    demo = store.load(demo_id)
    sc = store.read_json(demo_id, "script.json") or {}
    n = sum(1 for s in sc.get("segments", []) for l in s.get("lines", []) if l.get("audio"))
    total = sum(len(s.get("lines", [])) for s in sc.get("segments", []))
    out = [f"**Provider:** {sc.get('voice_provider')} · voice {sc.get('voice_name')} · {n}/{total} narration lines have audio · failures {sc.get('voice_failures', 0)}"]
    for lang in demo.get("settings", {}).get("languages", []) or []:
        if lang == demo.get("settings", {}).get("language"):
            continue
        alt = store.read_json(demo_id, f"script.{lang}.json")
        if alt:
            na = sum(1 for s in alt.get("segments", []) for l in s.get("lines", []) if l.get("audio"))
            kept = sum(1 for s in alt.get("segments", []) for l in s.get("lines", []) if l.get("kept_source"))
            out.append(f"**{lang}:** {na} lines with audio · {kept} kept in the main language (number changed in translation)")
            out.append(_script_md(alt, f"{lang} script"))
    return "\n\n".join(out)


def _rehearsal(demo_id: str) -> str:
    r = store.read_json(demo_id, "rehearsal.json") or {}
    if r.get("skipped"):
        return "_skipped_"
    out = [f"**Coverage:** {r.get('coverage')} · gaps: {len(r.get('gaps', []))}"]
    out.append(_table(["#", "question", "answered", "facts", "answer"], [[i + 1, q.get("question"), "yes" if q.get("answered") else "no", ",".join(q.get("fact_ids", []) or []), (q.get("answer") or "")[:300]] for i, q in enumerate(r.get("questions", []))]))
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
    return "\n\n".join([
        f"**bundle.json v{b.get('version')}** · {len(b.get('segments', []))} segments · {n} lines · languages {b.get('languages')} · {len(b.get('facts', []))} facts · {len(b.get('ctas', []))} CTAs · voice {b.get('voice', {}).get('provider')}",
        f"**Media:** {len(b.get('media', {}).get('images', []))} images · {len(b.get('media', {}).get('videos', []))} videos · hero {b.get('media', {}).get('hero')}",
        f"**Pitch:** {json.dumps(b.get('pitch', {}), ensure_ascii=False)[:900]}",
        f"Play it: Studio › Rehearse, or `GET /api/demos/{demo_id}/bundle`.",
    ])


def _last_log(demo_id: str, stage: str) -> dict | None:
    try:
        p = store.path(demo_id, "logs", f"{stage}.jsonl")
        if not p.exists():
            return None
        lines = p.read_text().splitlines()
        return json.loads(lines[-1]) if lines else None
    except Exception:
        return None


_REPORTS = {"understand": _understand, "plan": _plan, "author": _author, "voice": _voice, "rehearsal": _rehearsal, "bundle": _bundle}


def stage_report(demo_id: str, stage: str, *, seconds: float | None = None, started_at: float | None = None, instruction: str = "") -> None:
    """Append the section for one finished stage: inputs it saw, what it produced, every model call."""
    try:
        demo = store.load(demo_id)
        rows = [r for r in usage.traces(demo_id, limit=5000) if r.get("stage") == stage and (started_at is None or r.get("t", 0) >= started_at - 1)]
        cost = sum(r.get("usd", 0) for r in rows)
        head = f"### {stage.upper()} · {f'{seconds:.0f} s' if seconds is not None else '—'} · {len(rows)} calls · ${cost:.3f}"
        inputs = []
        if stage == "understand":
            inputs.append("Sources: " + ", ".join(f"{s.get('kind')}:{s.get('name') or s.get('url')}" for s in demo.get("sources", [])))
        if stage in ("plan", "author"):
            st = demo.get("settings", {})
            inputs.append(f"Settings: audience {st.get('audience')} · language {st.get('language')} · languages {st.get('languages')} · pitch minutes {st.get('pitch_minutes')}")
        if instruction:
            inputs.append(f"Instruction: {instruction}")
        body = ("\n".join(f"- {x}" for x in inputs) + "\n\n" if inputs else "") + "**Output**\n\n" + _REPORTS[stage](demo_id) + "\n\n**Model calls**\n\n" + _calls(demo_id, stage, started_at)
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
    append(demo_id, f"- {_ts()} · **Q&A** ({(profile or {}).get('name', 'anonymous')}): {question} → {'answered' if result.get('answered') else 'declined'} · facts {result.get('fact_ids')} · {(result.get('answer') or '')[:200]}")


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
        event(demo_id, f"Alignment conversation ({len(conv)} messages)", "\n\n".join(f"**{m.get('role')}:** {m.get('text', '')}" for m in conv))
    event(demo_id, "Approvals", _table(["card", "approved"], [[k, "yes" if v else "no"] for k, v in demo.get("approvals", {}).items()]))
    for stage in store.STAGES:
        st = demo.get("stages", {}).get(stage, {})
        if st.get("status") == "done":
            stage_report(demo_id, stage, seconds=st.get("seconds"), started_at=st.get("started_at"))
        elif st.get("status") == "error":
            stage_failed(demo_id, stage, st.get("error") or "")
    phase_done(demo_id, "backfill")
    return str(p)
