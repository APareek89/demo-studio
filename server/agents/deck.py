"""Stage — Deck.  One script segment = one slide.

Deterministic wherever a rule can decide: which picture a slide shows (tagged parts vs. the words), where a label sits
(outside the part box, inside the frame, never overlapping another label), and the fallback callouts (the slide's own
cited facts). The model writes only what needs judgement — a ≤ 6-word title and ≤ 3 callouts of ≤ 8 words per slide,
each citing fact ids — and the same validator that guards script lines drops any callout that states a figure or claim
without a citation. Positions are never guessed: no confident part, no anchor → the callout goes to a side panel.

Output: deck.json. Audio joins at bundle time by line id, so the deck stays a pure function of script + understanding."""
from __future__ import annotations

import json
import re

from pydantic import BaseModel, Field

from .. import config, schemas, store
from ..llm import claude
from . import visuals
from .author import ungrounded, words
from .principles import audience_instruction, language_instruction

KIND_BY_ROLE = {"intro": "intro", "outcome": "outcome", "proof": "proof", "features": "features", "establish": "establish"}
MAX_CALLOUTS = 3
MAX_CALLOUT_WORDS = 8
MAX_TITLE_WORDS = 6
PART_CONFIDENCE = 0.6          # below this the part is not trusted for a position: the callout goes to the panel
LABEL_W, LABEL_H = 0.30, 0.09  # a one-line chip's footprint as a fraction of the frame
MARGIN, GAP = 0.02, 0.02


class CalloutOut(BaseModel):
    slide_id: str
    text: str = Field(description="≤ 8 words: the one thing on this slide that moves a buyer — a benefit in their terms backed by the cited fact, never a bare spec label")
    fact_ids: list[str] = Field(description="every fact this callout relies on; a figure or claim with none is deleted")
    part: str = Field(default="", description="the product part it points at, spelled EXACTLY as in the slide's PARTS list, or empty")
    reveal_on_line: int = Field(default=0, description="0-based index of the slide line this callout supports")


class SlideTitleOut(BaseModel):
    slide_id: str
    title: str = Field(description="≤ 6 words, plain: the slide's promise in the buyer's terms")


class DeckOut(BaseModel):
    titles: list[SlideTitleOut]
    callouts: list[CalloutOut]


DECK_SYSTEM = """You write the on-screen layer of a spoken product demo: a short title and up to three callouts per slide.
The narration already says everything; the screen must make the buyer WANT it and trust it.
- A callout is ≤ 8 words: a benefit in the buyer's terms with the fact that proves it ("Two-year warranty, in writing",
  "Charges from any home socket"). Never a bare spec label, never an adjective without a fact.
- Every figure or claim cites fact ids from the REGISTRY; a validator deletes any callout without a citation.
- Point each callout at a part from that slide's PARTS list, spelled exactly; leave part empty when nothing fits — it is
  then shown in a side panel, which is fine. Never point at a part that is not listed.
- reveal_on_line is the 0-based line the callout supports, so it appears as those words are spoken.
- At most three per slide; none for the greeting and closing slides. Titles ≤ 6 words, plain, no marketing.
{audience}
{language}
PRODUCT: {product}
PERSONA: {persona}

SLIDES:
{slides}

FACT REGISTRY (only these may be cited):
{facts}"""


def _compact(text: str, limit: int) -> str:
    return " ".join(re.findall(r"\S+", text or "")[:limit])


def _slide_tokens(seg: dict) -> set[str]:
    txt = " ".join([seg.get("title", ""), seg.get("topic", "")] + [l.get("text", "") for l in seg.get("lines", [])])
    return visuals._expand(visuals._tokens(txt))


def choose_image(seg: dict, cat: dict[str, dict], script_refs: list[str], hero_id: str | None) -> tuple[str | None, str]:
    """The picture whose tagged parts match the words; the script's own pick counts extra; else the hero."""
    lt = _slide_tokens(seg)
    best, best_score = None, 0.0
    for ref, item in cat.items():
        sc, _ = visuals._score(lt, item)
        if ref in script_refs:
            sc += 2.0
        if sc > best_score:
            best, best_score = ref, sc
    if best and best_score >= 3.0:
        return best, "its tagged parts match the words" if best not in script_refs else "the script's own picture, and its parts match"
    if script_refs:
        return script_refs[0], "the script's own picture"
    return hero_id, "hero — no picture matches this topic"


# ---------- label layout ----------

def _overlaps(a: dict, b: dict) -> bool:
    return not (a["x"] + a["w"] <= b["x"] or b["x"] + b["w"] <= a["x"] or a["y"] + a["h"] <= b["y"] or b["y"] + b["h"] <= a["y"])


def _inside(r: dict) -> bool:
    return r["x"] >= MARGIN and r["y"] >= MARGIN and r["x"] + r["w"] <= 1 - MARGIN and r["y"] + r["h"] <= 1 - MARGIN


def _candidates(box: dict) -> list[dict]:
    """Eight spots around the part box — above, below, right, left — each tried left- then right-aligned."""
    x0, y0, x1, y1 = box["x"], box["y"], box["x"] + box["w"], box["y"] + box["h"]
    spots = [(x0, y0 - GAP - LABEL_H), (x1 - LABEL_W, y0 - GAP - LABEL_H), (x0, y1 + GAP), (x1 - LABEL_W, y1 + GAP),
             (x1 + GAP, y0), (x1 + GAP, y1 - LABEL_H), (x0 - GAP - LABEL_W, y0), (x0 - GAP - LABEL_W, y1 - LABEL_H)]
    return [{"x": round(x, 4), "y": round(y, 4), "w": LABEL_W, "h": LABEL_H} for x, y in spots]


def place_callouts(slide: dict, image: dict | None) -> None:
    """Overlay only when the part is found with confidence; the label sits outside the part box, inside the frame and
    clear of every other label. Anything else goes to the panel — a position is never guessed."""
    parts = {p["name"]: p for p in visuals.part_boxes(image or {})}
    taken: list[dict] = []
    for c in slide["callouts"]:
        p = parts.get((c.get("part") or "").lower())
        c["confidence"] = round(float(p["confidence"]), 3) if p else 0.0
        c["part_box"] = p["box"] if p else None
        if not p or p["confidence"] < PART_CONFIDENCE:
            c.update({"placement": "panel", "anchor": None, "label_pos": None})
            continue
        box = p["box"]
        spot = next((r for r in _candidates(box) if _inside(r) and not _overlaps(r, box) and not any(_overlaps(r, t) for t in taken)), None)
        if not spot:
            c.update({"placement": "panel", "anchor": None, "label_pos": None})
            continue
        taken.append(spot)
        c.update({"placement": "overlay", "anchor": {"x": round(box["x"] + box["w"] / 2, 4), "y": round(box["y"] + box["h"] / 2, 4)},
                  "label_pos": {"x": spot["x"], "y": spot["y"]}})


# ---------- callouts ----------

def derive_callouts(slide: dict, facts_by_id: dict, image: dict | None) -> list[dict]:
    """No model (mock, old demos, model failure): the slide's own cited facts, claim + value in ≤ 8 words, pointed at the
    part whose name shares a word with the fact. Grounded by construction."""
    names = [p["name"] for p in visuals.part_boxes(image or {})]
    seen, out = set(), []
    for li, ln in enumerate(slide["lines"]):
        for fid in ln.get("fact_ids", []):
            f = facts_by_id.get(fid)
            if not f or fid in seen:
                continue
            seen.add(fid)
            ft = visuals._expand(visuals._tokens(f"{f['claim']} {f['value']}"))
            part = next((n for n in names if visuals._tokens(n) & ft), "")
            out.append({"text": _compact(f"{f['claim']}: {f['value']}", MAX_CALLOUT_WORDS), "fact_ids": [fid], "part": part, "reveal_on_line": li})
            if len(out) >= MAX_CALLOUTS:
                return out
    return out


def clean_callouts(raw: list[dict], slide: dict, allowed: set[str], image: dict | None) -> list[dict]:
    """The script-line rule applied to callouts: an uncited figure or claim is dropped; so is anything over 8 words or
    pointing at a part the picture does not list."""
    names = {p["name"] for p in visuals.part_boxes(image or {})}
    out = []
    for c in raw:
        text = (c.get("text") or "").strip()
        valid, bad = ungrounded(text, c.get("fact_ids"), allowed)
        if not text or bad or words(text) > MAX_CALLOUT_WORDS:
            continue
        part = (c.get("part") or "").strip().lower()
        line_max = max(0, len(slide["lines"]) - 1)
        out.append({"text": text, "fact_ids": valid, "part": part if part in names else "", "reveal_on_line": max(0, min(int(c.get("reveal_on_line") or 0), line_max))})
        if len(out) >= MAX_CALLOUTS:
            break
    return out


def _ask_model(demo: dict, und: dict, plan: dict, slides: list[dict], images_by_id: dict, facts_by_id: dict, instruction: str = "") -> DeckOut:
    voice = plan.get("voice", {})
    rows = []
    for s in slides:
        if not s["lines"]:
            continue
        parts = ", ".join(p["name"] for p in visuals.part_boxes(images_by_id.get(s["image_id"]) or {})) or "(none)"
        rows.append(f"{s['id']} [{s['kind']}] title: {s['title']}\n  PARTS on its picture: {parts}\n" + "\n".join(f"  line {i}: {l['text']}  facts {l['fact_ids']}" for i, l in enumerate(s["lines"])))
    facts_txt = "\n".join(f"{f['id']} [{f['kind']}] {f['claim']}: {f['value']}" + (f" ({f['conditions']})" if f.get("conditions") else "") for f in facts_by_id.values()) or "(empty)"
    st = demo.get("settings", {})
    sys = DECK_SYSTEM.format(audience=audience_instruction(st.get("audience", "everyday")), language=language_instruction(st.get("language", "en-IN")),
                             product=json.dumps(und.get("product", {})), persona=json.dumps({k: voice.get(k) for k in ("persona_name", "tone")}),
                             slides="\n".join(rows), facts=facts_txt)
    ask = "Write the titles and callouts now." + (f"\n\nREVISION INSTRUCTION FROM THE USER — follow it precisely:\n{instruction}" if instruction else "")
    return claude.structured(sys, ask, DeckOut, max_tokens=6000)


# ---------- what the user fixed in Align wins over anything computed ----------

def apply_overrides(slides: list[dict], overrides: dict, images_by_id: dict, allowed: set[str]) -> None:
    """deck-overrides.json (written by Align): per slide an image, a title, and per callout text / fact ids / part /
    a dragged position. Text edits pass the same validator; a dragged label is trusted as given (inside the frame)."""
    by_slide = {o.get("slide_id"): o for o in overrides.get("slides", []) if o.get("slide_id")}
    for s in slides:
        o = by_slide.get(s["id"])
        if not o:
            continue
        if o.get("image_id") in images_by_id:
            s["image_id"], s["image_reason"] = o["image_id"], "chosen in Align"
        if (o.get("title") or "").strip():
            s["title"] = _compact(o["title"], MAX_TITLE_WORDS)
        img = images_by_id.get(s["image_id"])
        for oc in o.get("callouts", []):
            c = next((x for x in s["callouts"] if x["id"] == oc.get("id")), None)
            if not c:
                continue
            if "text" in oc or "fact_ids" in oc:
                text = (oc.get("text") if "text" in oc else c["text"]).strip()
                valid, bad = ungrounded(text, oc.get("fact_ids", c["fact_ids"]), allowed)
                if text and not bad and words(text) <= MAX_CALLOUT_WORDS:
                    c["text"], c["fact_ids"] = text, valid
            if "part" in oc:
                c["part"] = (oc.get("part") or "").strip().lower()
        if any("part" in oc for oc in o.get("callouts", [])):
            place_callouts(s, img)  # a new part → recompute its anchor and a clear spot
        for oc in o.get("callouts", []):
            c = next((x for x in s["callouts"] if x["id"] == oc.get("id")), None)
            lp = oc.get("label_pos")
            if c and isinstance(lp, dict) and 0 <= float(lp.get("x", -1)) <= 1 and 0 <= float(lp.get("y", -1)) <= 1:
                c["label_pos"] = {"x": round(float(lp["x"]), 4), "y": round(float(lp["y"]), 4)}
                c["placement"] = "overlay" if c.get("anchor") else "panel"
            if c and oc.get("placement") in ("overlay", "panel"):
                c["placement"] = oc["placement"] if (oc["placement"] == "panel" or c.get("anchor")) else "panel"


# ---------- the stage ----------

def build(demo_id: str, emit, instruction: str = "") -> dict:
    und = store.read_json(demo_id, "understanding.json")
    script = store.read_json(demo_id, "script.json")
    plan = store.read_json(demo_id, "plan.json") or {}
    if not (und and script):
        raise RuntimeError("Author first, then the deck")
    demo = store.load(demo_id)
    prev = store.read_json(demo_id, "deck.json") or {}
    facts_by_id = {f["id"]: f for f in und.get("facts", []) if f.get("approved", True)}
    images = [i for i in und.get("images", []) if store.visual_allowed(demo, i["source_id"])]
    images_by_id = {i["id"]: i for i in images}
    cat = {c["ref"]: c for c in visuals.catalogue(demo_id, und, demo) if c["kind"] == "image"}
    hero = visuals.pick_hero(demo, images)
    hero_id = hero["id"] if hero else None
    product = (und.get("product") or {}).get("name") or demo["name"]
    plan_by_id = {s["id"]: s for s in plan.get("segments", [])}

    def slide(sid, seg_id, kind, title, image_id, lines, **kw):
        return {"id": sid, "segment_id": seg_id, "kind": kind, "title": _compact(title, MAX_TITLE_WORDS), "topics": kw.get("topics", []),
                "fact_ids": sorted({f for l in lines for f in l.get("fact_ids", [])}), "image_id": image_id, "image_reason": kw.get("reason", ""),
                "motion": kw.get("motion", "zoom_in"), "callouts": [], "lines": lines, "checkin": kw.get("checkin", ""), "deeper": kw.get("deeper", []),
                "usp_ids": kw.get("usp_ids", []), "priority": kw.get("priority", False), "role": kw.get("role", kind)}

    def strip(l):
        return {"id": l["id"], "text": l["text"], "fact_ids": l.get("fact_ids", [])}

    emit("Laying out one slide per script segment…")
    slides = [slide("sl00", None, "hero_open", product, hero_id, [], reason="hero", motion="zoom_in")]
    n = 0
    for seg in script.get("segments", []):
        lines = [strip(l) for l in seg["lines"] if not l.get("unverified")]
        if not lines:
            continue
        n += 1
        refs = [r for r in ((l.get("visual") or {}).get("ref") for l in seg["lines"]) if r in images_by_id]
        image_id, reason = choose_image(seg, cat, list(dict.fromkeys(refs)), hero_id)
        splan = plan_by_id.get(seg["id"], {})
        slides.append(slide(f"sl{n:02d}", seg["id"], KIND_BY_ROLE.get(seg.get("role", "proof"), "proof"), seg["title"], image_id, lines,
                            topics=[t for t in [seg.get("topic", "")] if t], reason=reason, motion="pan_left" if n % 2 else "zoom_in",
                            checkin=seg.get("checkin", ""), deeper=[strip(l) for l in seg.get("deeper", []) if not l.get("unverified")],
                            usp_ids=seg.get("usp_ids") or splan.get("usp_ids", []), priority=bool(splan.get("priority_topic")), role=seg.get("role", "proof")))
    closing = [strip(l) for l in script.get("closing", []) if not l.get("unverified")]
    if closing:
        n += 1
        slides.append(slide(f"sl{n:02d}", None, "closing", "Where that leaves you", hero_id, closing, reason="hero", motion="none", role="closing"))
    slides.append(slide(f"sl{n + 1:02d}", None, "hero_close", product, hero_id, [], reason="hero", motion="zoom_in", role="hero_close"))

    # ---- titles + callouts: the model where it can, the slides' own facts otherwise ----
    out: DeckOut | None = None
    if config.MOCK_LLM:
        emit("Mock run — callouts come from each slide's cited facts.")
    else:
        emit("Writing slide titles and callouts…")
        try:
            out = _ask_model(demo, und, plan, slides, images_by_id, facts_by_id, instruction)
        except Exception as e:  # noqa: BLE001
            emit(f"Callout writer unavailable ({str(e)[:80]}) — using each slide's cited facts instead.")
    allowed = set(facts_by_id)
    n_model = n_derived = 0
    for s in slides:
        img = images_by_id.get(s["image_id"])
        raw = [c.model_dump() for c in (out.callouts if out else []) if c.slide_id == s["id"]]
        cleaned = clean_callouts(raw, s, allowed, img) if raw else []
        if cleaned:
            n_model += len(cleaned)
        elif s["lines"] and s["kind"] not in ("hero_open", "hero_close"):
            cleaned = derive_callouts(s, facts_by_id, img)
            n_derived += len(cleaned)
        for k, c in enumerate(cleaned, 1):
            c["id"] = f"{s['id']}-c{k}"
        s["callouts"] = cleaned
        if out:
            title = next((t.title for t in out.titles if t.slide_id == s["id"]), "")
            if title.strip():
                s["title"] = _compact(title, MAX_TITLE_WORDS)
        place_callouts(s, img)
    apply_overrides(slides, store.read_json(demo_id, "deck-overrides.json") or {}, images_by_id, allowed)
    overlay = sum(1 for s in slides for c in s["callouts"] if c["placement"] == "overlay")
    panel = sum(1 for s in slides for c in s["callouts"] if c["placement"] == "panel")
    intro_src = next((src["id"] for src in reversed(demo["sources"]) if src["kind"] == "video" and src.get("role") == "intro_video"), None)
    deck = {"hero_image": hero_id, "intro_video": intro_src, "slides": slides, "version": int(prev.get("version", 0)) + 1,
            "script_version": script.get("version"), "method": "model" if out else ("derived (mock)" if config.MOCK_LLM else "derived"), "issues": []}
    schemas.Deck.model_validate(deck)
    store.write_json(demo_id, "deck.json", deck)
    store.log(demo_id, "deck", {"slides": [(s["id"], s["kind"], s["image_id"], s["image_reason"], len(s["callouts"])) for s in slides],
                                "callouts": {"model": n_model, "derived": n_derived, "overlay": overlay, "panel": panel}, "method": deck["method"]})
    emit(f"Deck: {len(slides)} slides · {overlay + panel} callouts ({overlay} on the picture, {panel} in the side panel)" + (f" · {n_derived} from cited facts" if n_derived and out else "") + ".")
    return deck
