"""Stage 6 — Bundle.  Deterministic: assemble everything the player needs into bundle.json."""
from __future__ import annotations

import time

from .. import config, store
from . import visuals


def media_url(demo_id: str, rel: str | None) -> str | None:
    return f"/media/{demo_id}/{rel}" if rel else None


def build(demo_id: str, emit) -> dict:
    emit("Assembling the demo bundle…")
    demo = store.load(demo_id)
    und = store.read_json(demo_id, "understanding.json") or {}
    plan = store.read_json(demo_id, "plan.json") or {}
    script = store.read_json(demo_id, "script.json") or {}
    src_by_id = {s["id"]: s for s in demo["sources"]}
    shots = {s["id"]: s for s in und.get("shots", [])}
    images = {i["id"]: i for i in und.get("images", [])}
    facts = {f["id"]: f for f in und.get("facts", []) if f.get("approved", True)}

    def img_url(i: dict) -> str | None:
        src = src_by_id.get(i["source_id"], {})
        return media_url(demo_id, src.get("play") or src.get("path"))

    def visual(v: dict | None) -> dict:
        if not v or not v.get("ref"):
            return {"kind": "none"}
        if v["ref"] in shots:
            s = shots[v["ref"]]
            src = src_by_id.get(s["source_id"], {})
            if src.get("use_in_demo", True) is False:
                return {"kind": "none"}
            return {"kind": "shot", "ref": s["id"], "url": media_url(demo_id, src.get("play") or src.get("path")), "start": s["start"], "end": s["end"], "focus": v.get("focus", ""), "description": s["description"]}
        if v["ref"] in images:
            i = images[v["ref"]]
            src = src_by_id.get(i["source_id"], {})
            if src.get("use_in_demo", True) is False:
                return {"kind": "none"}
            return {"kind": "image", "ref": i["id"], "url": media_url(demo_id, src.get("play") or src.get("path")), "focus": v.get("focus", ""), "description": i["description"]}
        return {"kind": "none"}

    def line(ln: dict) -> dict:
        v = visual(ln.get("visual"))
        return {"id": ln["id"], "text": ln["text"], "audio": media_url(demo_id, ln.get("audio")), "visual": v, "start": ln.get("start"), "duration": ln.get("duration"),
                "fact_ids": ln.get("fact_ids", []), "step": ln.get("step", "other"), "card": ln.get("card", "none"), "unverified": bool(ln.get("unverified"))}

    def assemble(sc: dict) -> dict:
        segs = []
        for seg in sc.get("segments", []):
            splan = next((s for s in plan.get("segments", []) if s["id"] == seg["id"]), {})
            segs.append({
                "id": seg["id"], "title": seg["title"], "topic": seg["topic"], "priority": bool(splan.get("priority_topic")),
                "role": seg.get("role", "proof"), "outcome": seg.get("outcome") or splan.get("outcome", ""), "usp_ids": seg.get("usp_ids") or splan.get("usp_ids", []),
                "lines": [line(l) for l in seg["lines"] if not l.get("unverified")],
                "checkin": {"text": seg.get("checkin", ""), "audio": media_url(demo_id, seg.get("checkin_audio"))},
                "deeper": [line(l) for l in seg.get("deeper", []) if not l.get("unverified")],
            })
        return {"segments": segs, "closing": [line(l) for l in sc.get("closing", [])],
                "intake": {"q1": sc.get("intake_q1", ""), "q2": sc.get("intake_q2", ""), "audio": {k: media_url(demo_id, v) for k, v in (sc.get("intake_audio") or {}).items()}, "chips": plan.get("intake", {}).get("chips", [])},
                "voice_provider": sc.get("voice_provider", "browser")}

    deck = store.read_json(demo_id, "deck.json") or {}

    def assemble_slides(sc: dict, overlay: dict | None) -> list[dict]:
        """deck.json is the structure; the script (main or translated) supplies each line's text, audio and timing by id;
        deck.<lang>.json supplies titles and callout text in that language."""
        by_id = {l["id"]: l for seg in sc.get("segments", []) for l in seg["lines"] + seg.get("deeper", [])} | {l["id"]: l for l in sc.get("closing", [])}
        seg_by_id = {s["id"]: s for s in sc.get("segments", [])}
        ov = {s["id"]: s for s in (overlay or {}).get("slides", [])}

        def sl_line(l: dict) -> dict:
            src = by_id.get(l["id"], {})
            return {"id": l["id"], "text": src.get("text") or l["text"], "fact_ids": l.get("fact_ids", []), "audio": media_url(demo_id, src.get("audio")),
                    "start": src.get("start"), "duration": src.get("duration"), "step": src.get("step") or l.get("step", "other")}
        out = []
        for s in deck.get("slides", []):
            seg = seg_by_id.get(s.get("segment_id") or "", {})
            im = images.get(s.get("image_id") or "")
            o = ov.get(s["id"], {})
            ctext = {c["id"]: c["text"] for c in o.get("callouts", [])}
            out.append({**{k: s.get(k) for k in ("id", "segment_id", "kind", "topics", "fact_ids", "image_id", "image_reason", "motion", "usp_ids", "priority", "role")},
                        "title": o.get("title") or s.get("title", ""), "image_url": img_url(im) if im else None, "image_parts": visuals.part_boxes(im) if im else [],
                        "callouts": [{**c, "text": ctext.get(c["id"], c["text"])} for c in s.get("callouts", [])],
                        "lines": [sl_line(l) for l in s.get("lines", [])], "deeper": [sl_line(l) for l in s.get("deeper", [])],
                        "checkin": {"text": seg.get("checkin") or s.get("checkin", ""), "audio": media_url(demo_id, seg.get("checkin_audio"))}})
        return out

    main_lang = demo.get("settings", {}).get("language", "en-IN")
    alt = {}
    for lang in (demo.get("settings", {}).get("languages") or []):
        if lang == main_lang:
            continue
        sc = store.read_json(demo_id, f"script.{lang}.json")
        if sc:
            alt[lang] = assemble(sc)
            alt[lang]["slides"] = assemble_slides(sc, store.read_json(demo_id, f"deck.{lang}.json"))
    segments = []
    for seg in script.get("segments", []):
        splan = next((s for s in plan.get("segments", []) if s["id"] == seg["id"]), {})
        segments.append({
            "id": seg["id"], "title": seg["title"], "topic": seg["topic"], "priority": bool(splan.get("priority_topic")),
            "role": seg.get("role", "proof"), "outcome": seg.get("outcome") or splan.get("outcome", ""), "usp_ids": seg.get("usp_ids") or splan.get("usp_ids", []),
            "lines": [line(l) for l in seg["lines"] if not l.get("unverified")],
            "checkin": {"text": seg.get("checkin", ""), "audio": media_url(demo_id, seg.get("checkin_audio"))},
            "deeper": [line(l) for l in seg.get("deeper", []) if not l.get("unverified")],
        })
    price_facts = [f for f in facts.values() if f["kind"] in ("price", "offer")]
    spec_facts = [f for f in facts.values() if f["kind"] in ("spec", "feature", "policy")]
    usable_images = [i for i in und.get("images", []) if src_by_id.get(i["source_id"], {}).get("use_in_demo", True) is not False]
    all_images = [{"id": i["id"], "url": img_url(i), "angle": i["angle"], "description": i["description"], "parts": visuals.part_boxes(i),
                   "full_product": bool(i.get("full_product")), "role": src_by_id.get(i["source_id"], {}).get("role", "product"),
                   "derived_from": src_by_id.get(i["source_id"], {}).get("derived_from")} for i in usable_images]
    hero = visuals.pick_hero(demo, usable_images)
    videos = [{"id": s["id"], "url": media_url(demo_id, s.get("play") or s["path"]), "name": s["name"]} for s in demo["sources"] if s["kind"] == "video" and s.get("use_in_demo", True) is not False and s.get("role") != "intro_video"]
    intro_src = next((s for s in reversed(demo["sources"]) if s["kind"] == "video" and s.get("role") == "intro_video"), None)
    intro_video = {"url": media_url(demo_id, intro_src.get("play") or intro_src["path"]), "name": intro_src["name"], "enabled": demo.get("settings", {}).get("intro_video", "on") != "off"} if intro_src else None
    b = {
        "id": demo_id, "name": demo["name"], "version": demo.get("version", 0) + 1, "built_at": time.time(),
        "product": und.get("product", {}), "customer_persona": plan.get("customer_persona", ""),
        "voice": {"provider": script.get("voice_provider", "browser"), "name": script.get("voice_name", ""), "persona": plan.get("voice", {})},
        "intake": {"q1": script.get("intake_q1", ""), "q2": script.get("intake_q2", ""), "audio": {k: media_url(demo_id, v) for k, v in (script.get("intake_audio") or {}).items()}, "chips": plan.get("intake", {}).get("chips", [])},
        "segments": segments,
        "closing": [line(l) for l in script.get("closing", [])],
        "ctas": plan.get("ctas", []),
        "pitch": {"decision_frame": plan.get("decision_frame", ""), "takeaway": plan.get("takeaway", ""), "primary_outcome": plan.get("primary_outcome", ""), "supporting_outcomes": plan.get("supporting_outcomes", []), "usps": plan.get("usps", []), "advance": plan.get("advance", ""), "do_not_recommend_if": plan.get("do_not_recommend_if", ""), "state_questions": plan.get("state_questions", [])},
        "language": main_lang, "languages": [main_lang] + list(alt.keys()), "alt_languages": alt,
        "mascot": media_url(demo_id, demo.get("mascot")) if demo.get("mascot") else None,
        "intro_video": intro_video,
        "timeline": script.get("timeline"),
        "faq": [{**e, "audio": media_url(demo_id, e.get("audio")), "visual": visual({"ref": (e.get("visual") or {}).get("ref")}) if e.get("visual") else {"kind": "none"}} for e in (store.read_json(demo_id, "faq.json") or {}).get("entries", [])],
        "fillers": {k: {"text": v.get("text"), "audio": media_url(demo_id, v.get("audio"))} for k, v in (store.read_json(demo_id, "fillers.json") or {}).items()},
        "image_map": und.get("image_map", {}),
        "stt": {"provider": config.STT_PROVIDER},
        "facts": list(facts.values()),
        "cards": {"price": [{"claim": f["claim"], "value": f["value"], "conditions": f.get("conditions", "")} for f in price_facts][:12],
                  "facts": [{"claim": f["claim"], "value": f["value"], "conditions": f.get("conditions", "")} for f in spec_facts][:12]},
        "unknowns": [u for u in und.get("unknowns", []) if u.get("status") == "open"],
        "hero_image": hero["id"] if hero else None,
        "slides": assemble_slides(script, None), "deck_version": deck.get("version"), "deck_method": deck.get("method"),
        "media": {"images": all_images, "videos": videos, "hero": (img_url(hero) if hero else (videos[0]["url"] if videos else None))},
        "brand": und.get("brand", {}),
        "guardrails": {"no_citation_no_claim": True, "escalate_on_unknown": True, "no_price_negotiation": True},
    }
    store.write_json(demo_id, "bundle.json", b)

    def upd(d):
        d["version"] = b["version"]
    store.update(demo_id, upd)
    emit(f"Bundle v{b['version']}: {len(b['slides'])} slides ({len(segments)} segments), {len(facts)} facts, {len(b['ctas'])} calls to action" + (f", {len(alt)} extra language(s)" if alt else "") + ".")
    return b
