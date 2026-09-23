"""Stage — Deck.  One script segment = one slide.

Deterministic wherever a rule can decide: which picture a slide shows (tagged parts vs. the words), where a label sits
(outside the part box, inside the frame, never overlapping another label), and the fallback callouts (the slide's own
cited facts). The model writes only what needs judgement — a ≤ 6-word title and ≤ 3 callouts of ≤ 8 words per slide,
each citing fact ids — and the same validator that guards script lines drops any callout that states a figure or claim
without a citation. Positions are never guessed: no confident part, no anchor → the callout goes to a side panel.

Output: deck.json. Audio joins at bundle time by line id, so the deck stays a pure function of script + understanding."""
from __future__ import annotations

import copy
import json
import re

from pydantic import BaseModel, Field

from .. import config, schemas, store
from ..llm import claude
from . import visuals
from .author import ungrounded, words
from .principles import EVIDENCE_RULES, audience_instruction, fact_context, language_instruction

# Map script roles to slide kinds and set label length, confidence and layout limits.
# build and place_callouts use these values; bundle.py:build sends the resulting design to the player.
KIND_BY_ROLE = {"intro": "intro", "outcome": "outcome", "proof": "proof", "features": "features", "establish": "establish"}
MAX_CALLOUTS = 3
MAX_CALLOUT_WORDS = 8
MAX_TITLE_WORDS = 6
PART_CONFIDENCE = 0.6          # below this the part is not trusted for a position: the callout goes to the panel
LABEL_W, LABEL_H = 0.30, 0.09  # a one-line chip's footprint as a fraction of the frame
MARGIN, GAP = 0.02, 0.02


# Describe one model-proposed label, its cited facts, named part and reveal line.
# The parsed fields go to clean_callouts; bundle.py:build later carries accepted labels to the player.
class CalloutOut(BaseModel):
    slide_id: str
    text: str = Field(description="≤ 8 words: a complete source-supported label, neutral specification or fit-check; retain material scope and units, and omit the callout if they do not fit; never invent a benefit")
    fact_ids: list[str] = Field(description="every fact this callout relies on; a figure or claim with none is deleted")
    part: str = Field(default="", description="the product part it points at, spelled EXACTLY as in the slide's PARTS list, or empty")
    reveal_on_line: int = Field(default=0, description="0-based index of the slide line this callout supports")


# Describe a proposed short title tied to an existing slide ID.
# The title enters build after length checks; bundle.py:build adds it to the published slide.
class SlideTitleOut(BaseModel):
    slide_id: str
    title: str = Field(description="≤ 6 words, plain: the supported topic or choice to explore, without a promised result beyond the facts")


# Collect model-proposed titles and callouts without changing the spoken script.
# This response shape is passed to llm/claude.py:structured by _ask_model.
class DeckOut(BaseModel):
    titles: list[SlideTitleOut]
    callouts: list[CalloutOut]


# Ask only for the on-screen layer, using approved fact text and the selected picture parts.
# _ask_model sends this prompt to llm/claude.py:structured; spoken wording still comes from author.py:run.
DECK_SYSTEM = """You write the on-screen layer of a spoken product demo: a short title and up to three callouts per slide.
Help the buyer notice the supported detail or choice. Narration and existing slide titles are context, not evidence
for extra claims; use the current fact registry and its conditions even when narration sounds more persuasive.
- A callout is ≤ 8 words: a complete supported label, neutral specification or fit-check. A plain feature name with
  its scope is useful; no benefit or performance promise is required. Retain units and material trim/fuel/offer
  qualifications. If they cannot fit, omit the callout rather than dropping a condition or inventing a shorter benefit.
- Every figure or claim cites fact ids from the REGISTRY. A validator deletes an uncited claim, but an existing id
  does not establish that an added benefit is true. Do not infer room, road capability, savings or safety from a spec.
- Point each callout at a part from that slide's PARTS list, spelled exactly; leave part empty when nothing fits — it is
  then shown in a side panel, which is fine. Never point at a part that is not listed.
- reveal_on_line is the 0-based line the callout supports, so it appears as those words are spoken.
- At most three per slide; none for the greeting and closing slides. Titles ≤ 6 words, plain, no marketing.
{evidence}
{audience}
{language}
PRODUCT: {product}
PERSONA: {persona}

SLIDES:
{slides}

FACT REGISTRY (only these may be cited):
{facts}"""


# Take a label and word limit; return the complete label or an empty string.
# Uses author.py:words so shortening never cuts a fact condition in half.
def _compact(text: str, limit: int) -> str:
    """Keep complete copy or omit it; a word slice can remove a condition or half a sentence."""
    complete = " ".join(re.findall(r"\S+", text or ""))
    return complete if words(complete) <= limit else ""


# Turn a segment title, topic and main lines into matching words.
# Uses visuals.py:_tokens and visuals.py:_expand before choose_image scores tagged pictures.
def _slide_tokens(seg: dict) -> set[str]:
    txt = " ".join([seg.get("title", ""), seg.get("topic", "")] + [l.get("text", "") for l in seg.get("lines", [])])
    return visuals._expand(visuals._tokens(txt))


# Choose one slide image from tagged pictures, with extra weight for Author references.
# Returns an image ID and reason; visuals.py:_score does matching, while the reviewed installer pins its own choice.
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

# Compare two fractional rectangles and return whether their areas overlap.
# place_callouts uses this check before bundle.py:build sends positions to the player.
def _overlaps(a: dict, b: dict) -> bool:
    return not (a["x"] + a["w"] <= b["x"] or b["x"] + b["w"] <= a["x"] or a["y"] + a["h"] <= b["y"] or b["y"] + b["h"] <= a["y"])


# Check whether a proposed label rectangle fits inside the allowed picture margin.
# Returns a boolean used by place_callouts; bundle.py:build preserves the accepted coordinates.
def _inside(r: dict) -> bool:
    return r["x"] >= MARGIN and r["y"] >= MARGIN and r["x"] + r["w"] <= 1 - MARGIN and r["y"] + r["h"] <= 1 - MARGIN


# Turn one tagged part box into eight possible nearby label rectangles.
# place_callouts tests these positions; visuals.py:part_boxes supplies the original part geometry.
def _candidates(box: dict) -> list[dict]:
    """Eight spots around the part box — above, below, right, left — each tried left- then right-aligned."""
    x0, y0, x1, y1 = box["x"], box["y"], box["x"] + box["w"], box["y"] + box["h"]
    spots = [(x0, y0 - GAP - LABEL_H), (x1 - LABEL_W, y0 - GAP - LABEL_H), (x0, y1 + GAP), (x1 - LABEL_W, y1 + GAP),
             (x1 + GAP, y0), (x1 + GAP, y1 - LABEL_H), (x0 - GAP - LABEL_W, y0), (x0 - GAP - LABEL_W, y1 - LABEL_H)]
    return [{"x": round(x, 4), "y": round(y, 4), "w": LABEL_W, "h": LABEL_H} for x, y in spots]


# Use tagged part boxes to add overlay positions, or send uncertain labels to the side panel.
# Mutates the slide callouts; visuals.py:part_boxes supplies boxes and bundle.py:build publishes them.
def place_callouts(slide: dict, image: dict | None) -> None:
    """Overlay only when the part is found with confidence; the label sits outside the part box, inside the frame and
    clear of every other label. Anything else goes to the panel — a position is never guessed."""
    # Load trusted part names and boxes from the chosen image before placing labels.
    # visuals.py:part_boxes supplies this geometry; missing or weak matches become panel labels.
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
        # Try nearby positions that stay inside the image and avoid the part and other labels.
        # The first safe position becomes an overlay; bundle.py:build preserves those fractional coordinates.
        spot = next((r for r in _candidates(box) if _inside(r) and not _overlaps(r, box) and not any(_overlaps(r, t) for t in taken)), None)
        if not spot:
            c.update({"placement": "panel", "anchor": None, "label_pos": None})
            continue
        taken.append(spot)
        c.update({"placement": "overlay", "anchor": {"x": round(box["x"] + box["w"] / 2, 4), "y": round(box["y"] + box["h"] / 2, 4)},
                  "label_pos": {"x": spot["x"], "y": spot["y"]}})


# ---------- callouts ----------

# Build fallback labels from the slide lines and their approved facts, keeping full conditions.
# Returns only labels that fit; author.py:words sets the length test and visuals.py:part_boxes helps match parts.
def derive_callouts(slide: dict, facts_by_id: dict, image: dict | None) -> list[dict]:
    """No model: use a complete cited fact, including its scope, only when it fits.

    Do not manufacture a shorter benefit or clip the qualifier. Narration and the
    fact card retain omitted facts; an empty callout is preferable to a changed claim.
    """
    # Walk the slide citations once, retaining full fact wording, conditions and any truth label.
    # Overlong labels are omitted, not shortened; author.py:words provides the word count.
    names = [p["name"] for p in visuals.part_boxes(image or {})]
    seen, out = set(), []
    for li, ln in enumerate(slide["lines"]):
        for fid in ln.get("fact_ids", []):
            f = facts_by_id.get(fid)
            if not f or fid in seen:
                continue
            seen.add(fid)
            label = f"{f['claim']}: {f['value']}"
            if f.get("conditions"):
                label += f"; {f['conditions']}"
            truth_label = {"certified": "Certified", "modeled": "Estimate", "observed": "Observed", "contractual": "Written terms"}.get(f.get("truth"))
            if truth_label:
                label = f"{truth_label} — {label}"
            label = _compact(label, MAX_CALLOUT_WORDS)
            if not label:
                continue
            ft = visuals._expand(visuals._tokens(f"{f['claim']} {f['value']}"))
            part = next((n for n in names if visuals._tokens(n) & ft), "")
            out.append({"text": label, "fact_ids": [fid], "part": part, "reveal_on_line": li})
            if len(out) >= MAX_CALLOUTS:
                return out
    return out


# Filter proposed labels by citation IDs, word count and the selected image parts.
# Returns cleaned labels with bounded reveal indexes; author.py:ungrounded checks the citation rule.
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


# Give the model existing slide lines, part names and approved facts to propose titles and labels.
# Returns DeckOut through llm/claude.py:structured; it does not write narration or choose new media.
def _ask_model(demo: dict, und: dict, plan: dict, slides: list[dict], images_by_id: dict, facts_by_id: dict, instruction: str = "") -> DeckOut:
    voice = plan.get("voice", {})
    rows = []
    for s in slides:
        if not s["lines"]:
            continue
        parts = ", ".join(p["name"] for p in visuals.part_boxes(images_by_id.get(s["image_id"]) or {})) or "(none)"
        rows.append(f"{s['id']} [{s['kind']}] title: {s['title']}\n  PARTS on its picture: {parts}\n" + "\n".join(f"  line {i}: {l['text']}  facts {l['fact_ids']}" for i, l in enumerate(s["lines"])))
    facts_txt = "\n".join(fact_context(f) for f in facts_by_id.values()) or "(empty)"
    st = demo.get("settings", {})
    sys = DECK_SYSTEM.format(evidence=EVIDENCE_RULES, audience=audience_instruction(st.get("audience", "everyday")), language=language_instruction(st.get("language", "en-IN")),
                             product=json.dumps(und.get("product", {})), persona=json.dumps({k: voice.get(k) for k in ("persona_name", "tone")}),
                             slides="\n".join(rows), facts=facts_txt)
    ask = "Write the titles and callouts now." + (f"\n\nREVISION INSTRUCTION FROM THE USER — follow it precisely:\n{instruction}" if instruction else "")
    return claude.structured(sys, ask, DeckOut, max_tokens=6000)


# ---------- what the user fixed in Align wins over anything computed ----------

# Apply saved Align image, title and label edits to the newly built slides.
# Mutates only matching slide entries; author.py:ungrounded checks edited text before bundle.py:build uses it.
def apply_overrides(slides: list[dict], overrides: dict, images_by_id: dict, allowed: set[str]) -> None:
    """deck-overrides.json (written by Align): per slide an image, a title, and per callout text / fact ids / part /
    a dragged position. Text edits pass the same validator; a dragged label is trusted as given (inside the frame)."""
    # Match saved edits by slide ID, and accept replacement images only from the allowed catalogue.
    # The catalogue comes from visuals.py:catalogue; edits do not grant access to excluded media.
    by_slide = {o.get("slide_id"): o for o in overrides.get("slides", []) if o.get("slide_id")}
    for s in slides:
        o = by_slide.get(s["id"])
        if not o:
            continue
        image_changed = o.get("image_id") in images_by_id and o["image_id"] != s["image_id"]
        if image_changed:
            s["image_id"], s["image_reason"] = o["image_id"], "chosen in Align"
        title = _compact(o.get("title", ""), MAX_TITLE_WORDS)
        if title:
            s["title"] = title
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
        # A changed image or part invalidates the old anchor, so recompute placement before applying drags.
        # visuals.py:part_boxes supplies the new geometry; the later position edit cannot invent a missing anchor.
        if image_changed or any("part" in oc for oc in o.get("callouts", [])):
            place_callouts(s, img)  # a new picture or part → recompute anchors and clear spots; unlisted parts go to the panel
        for oc in o.get("callouts", []):
            c = next((x for x in s["callouts"] if x["id"] == oc.get("id")), None)
            lp = oc.get("label_pos")
            if c and isinstance(lp, dict) and 0 <= float(lp.get("x", -1)) <= 1 and 0 <= float(lp.get("y", -1)) <= 1:
                c["label_pos"] = {"x": round(float(lp["x"]), 4), "y": round(float(lp["y"]), 4)}
                c["placement"] = "overlay" if c.get("anchor") else "panel"
            if c and oc.get("placement") in ("overlay", "panel"):
                c["placement"] = oc["placement"] if (oc["placement"] == "panel" or c.get("anchor")) else "panel"


# Join current verified script lines onto saved slide designs using segment IDs.
# Returns copied slides with refreshed narration and citations; bundle.py:build calls this before attaching audio.
def slides_with_script(slides: list[dict], script: dict) -> list[dict]:
    """Join current approved narration onto saved slide design, without rebuilding it."""
    out = copy.deepcopy(slides)
    if "segments" not in script:
        return out
    segments = {segment["id"]: segment for segment in script.get("segments", [])}
    # Copy verified narration fields while keeping saved visual design separate from speech.
    # bundle.py:build later uses these line IDs to attach the current audio and delivery instructions.
    def lines(rows):
        return [{key: copy.deepcopy(line[key]) for key in ("id", "text", "fact_ids", "step", "start", "duration") if key in line}
                for line in rows if not line.get("unverified")]
    # Join each saved slide to its current segment, with a separate join for the closing lines.
    # Refresh line citations without regenerating images; bundle.py:build consumes this copied result.
    for slide in out:
        segment_id = slide.get("segment_id")
        if segment_id:
            segment = segments.get(segment_id, {})
            slide["lines"] = lines(segment.get("lines", []))
            slide["deeper"] = lines(segment.get("deeper", []))
            slide["checkin"] = segment.get("checkin", "")
            for field in ("role", "usp_ids", "outcome"):
                if field in segment:
                    slide[field] = copy.deepcopy(segment[field])
            if "topic" in segment:
                slide["topics"] = [segment["topic"]] if segment["topic"] else []
        elif slide.get("kind") == "closing":
            slide["lines"] = lines(script.get("closing", []))
            slide["deeper"], slide["checkin"] = [], ""
        else:
            continue
        slide["fact_ids"] = sorted({fid for line in slide["lines"] for fid in line.get("fact_ids", [])})
    return out


# ---------- the stage ----------

# Read understanding, script, Plan and Align overrides, then write the slide design to deck.json.
# Called by orchestrator.py:_run_stage; bundle.py:build later joins recorded audio by line ID.
def build(demo_id: str, emit, instruction: str = "") -> dict:
    und = store.read_json(demo_id, "understanding.json")
    script = store.read_json(demo_id, "script.json")
    plan = store.read_json(demo_id, "plan.json") or {}
    if not (und and script):
        raise RuntimeError("Author first, then the deck")
    demo = store.load(demo_id)
    prev = store.read_json(demo_id, "deck.json") or {}
    overrides = store.read_json(demo_id, "deck-overrides.json") or {}
    # Build the allowed fact and image lookups from the saved understanding and source permissions.
    # visuals.py:catalogue supplies matching tags; unapproved facts and excluded images are left out.
    facts_by_id = {f["id"]: f for f in und.get("facts", []) if f.get("approved", True)}
    images = [i for i in und.get("images", []) if store.visual_allowed(demo, i["source_id"])]
    images_by_id = {i["id"]: i for i in images}
    cat = {c["ref"]: c for c in visuals.catalogue(demo_id, und, demo) if c["kind"] == "image"}
    hero = visuals.pick_hero(demo, images)
    hero_id = hero["id"] if hero else None
    product = (und.get("product") or {}).get("name") or demo["name"]
    plan_by_id = {s["id"]: s for s in plan.get("segments", [])}

    # Create the common slide record from its identity, chosen image and verified lines.
    # The output keeps segment and line IDs for bundle.py:build to join audio later.
    def slide(sid, seg_id, kind, title, image_id, lines, **kw):
        safe_title = _compact(title, MAX_TITLE_WORDS) or {"intro": "Overview", "outcome": "What matters", "proof": "Explore the details",
                                                       "features": "A few more things", "establish": "Ownership and terms", "closing": "Your next step"}.get(kind, "")
        return {"id": sid, "segment_id": seg_id, "kind": kind, "title": safe_title, "topics": kw.get("topics", []),
                "fact_ids": sorted({f for l in lines for f in l.get("fact_ids", [])}), "image_id": image_id, "image_reason": kw.get("reason", ""),
                "motion": kw.get("motion", "zoom_in"), "callouts": [], "lines": lines, "checkin": kw.get("checkin", ""), "deeper": kw.get("deeper", []),
                "usp_ids": kw.get("usp_ids", []), "priority": kw.get("priority", False), "role": kw.get("role", kind)}

    # Keep only narration identity, text, citations and step in the deck record.
    # Audio and per-line visual references stay in the script until bundle.py:build joins what the slide needs.
    def strip(l):
        return {"id": l["id"], "text": l["text"], "fact_ids": l.get("fact_ids", []), "step": l.get("step", "other")}

    # Build hero slides around one content slide per segment that has verified main lines.
    # Normal selection scores image tags with Author references; install_reviewed_session.py:install instead pins reviewed references.
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
    # Try model-written titles and labels, falling back to complete cited facts in mock mode or on error.
    # llm/claude.py:structured is called only through _ask_model; it does not choose the spoken script.
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
    # Validate each slide's proposed labels, then derive labels when none survive.
    # author.py:ungrounded checks citation presence and IDs; this is not a second full semantic review.
    for s in slides:
        img = images_by_id.get(s["image_id"])
        raw = [c.model_dump() for c in (out.callouts if out else []) if c.slide_id == s["id"]]
        cleaned = clean_callouts(raw, s, allowed, img) if raw else []
        if cleaned:
            n_model += len(cleaned)
        elif s["lines"] and s["kind"] not in ("hero_open", "hero_close"):
            cleaned = derive_callouts(s, facts_by_id, img)
            n_derived += len(cleaned)
        # Omitting a long fact must not move its old positional id onto a
        # different fact and silently reapply that fact's reviewed Align edit.
        # Reuse an id only for unambiguous matching evidence; keep orphaned
        # override ids reserved even after a further rebuild.
        # Reserve old label IDs and retain reviewed labels only when their cited facts still belong here.
        # This keeps an Align edit from moving to another fact when rebuilds omit a label; author.py:ungrounded still checks it.
        old_callouts = next((old.get("callouts", []) for old in prev.get("slides", []) if old.get("id") == s["id"]), [])
        old_overrides = next((old.get("callouts", []) for old in overrides.get("slides", []) if old.get("slide_id") == s["id"]), [])
        reserved = {c.get("id") for c in old_callouts + old_overrides if c.get("id")}
        identity = lambda c: tuple(sorted(set(c.get("fact_ids", []))))
        reviewed = []
        for edit in old_overrides:
            old = next((c for c in old_callouts if c.get("id") == edit.get("id")), None)
            if not old or "text" not in edit:
                continue
            candidate = {**old, **edit}
            citations = set(candidate.get("fact_ids", []))
            # An explicit, concise human edit may still be useful when the
            # unedited fact is too long to derive. Keep it only while all its
            # evidence is approved AND belongs to this slide.
            if not citations or not citations <= allowed.intersection(s["fact_ids"]):
                continue
            safe = clean_callouts([candidate], s, allowed, img)
            if safe:
                reviewed.append({**safe[0], "id": old["id"]})
        if reviewed:
            reviewed_keys = {identity(c) for c in reviewed}
            cleaned = (reviewed + [c for c in cleaned if identity(c) not in reviewed_keys])[:MAX_CALLOUTS]
        # Reuse a label ID only for one unambiguous citation match; otherwise allocate a fresh ID.
        # The stable IDs keep later overrides and bundle.py:build callout references attached to the right label.
        next_id = 1
        for c in cleaned:
            if c.get("id"):
                continue
            key = identity(c)
            matches = [old for old in old_callouts if identity(old) == key]
            if key and len(matches) == 1 and sum(identity(new) == key for new in cleaned) == 1 and matches[0].get("id"):
                c["id"] = matches[0]["id"]
            else:
                while f"{s['id']}-c{next_id}" in reserved:
                    next_id += 1
                c["id"] = f"{s['id']}-c{next_id}"
                reserved.add(c["id"])
                next_id += 1
        s["callouts"] = cleaned
        if out:
            title = next((t.title for t in out.titles if t.slide_id == s["id"]), "")
            title = _compact(title, MAX_TITLE_WORDS)
            if title:
                s["title"] = title
        place_callouts(s, img)
    # Apply reviewed edits last, then validate and save the complete deck and its layout summary.
    # store.py:write_json writes deck.json; bundle.py:build resolves its media and narration into player data.
    apply_overrides(slides, overrides, images_by_id, allowed)
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


# ---------- runtime routing: which slide answers a question (plain code on fact ids and topics — no model call) ----------
# Ignore common words when routing a question by topic after citation matching fails.
# These words affect only slide_for matching used by faq.py:run and runtime_graph.py:validate.
ROUTE_STOP = set("a an and the of to in on for with is it its this that how what does do can i my your be are was has have any about".split())


# Reduce a routing question or slide title to useful lowercase words.
# Returns a word set for slide_for, which faq.py:run uses when assigning answers to slides.
def _terms(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]+", (text or "").lower()) if len(w) > 2 and w not in ROUTE_STOP}


# Keep slides that contain narration, excluding the opening and closing hero pictures.
# Returns routing candidates for slide_for; faq.py:run stores the resulting slide IDs.
def content_slides(slides: list[dict]) -> list[dict]:
    return [s for s in slides if s.get("kind") not in ("hero_open", "hero_close") and s.get("lines")]


# Collect the fact IDs from a slide, its callouts and its deeper lines.
# Returns a set for routing; runtime_graph.py:validate uses route_for to keep answers near their evidence.
def slide_facts(s: dict) -> set[str]:
    """Every fact a slide carries: its lines, its callouts and its deeper lines."""
    return set(s.get("fact_ids") or []) | {f for c in s.get("callouts", []) for f in c.get("fact_ids", [])} | {f for l in s.get("deeper", []) for f in l.get("fact_ids", [])}


# Pick the slide with the most matching facts, falling back to topic and title words.
# Returns a slide ID and match reason; faq.py:run uses it without making a model call.
def slide_for(slides: list[dict], fact_ids: list[str] | None, text: str = "") -> tuple[str | None, str]:
    """The slide sharing the most facts with an answer; else the slide whose topic / title words the question uses; else None.
    Returns (slide_id, how) with how = 'facts' | 'topic' | ''."""
    facts = set(fact_ids or [])
    best, score = None, 0
    for s in content_slides(slides):
        n = len(slide_facts(s) & facts)
        if n > score:
            best, score = s, n
    if best:
        return best["id"], "facts"
    # If no slide shares an answer fact, try question words against slide titles and topics.
    # Return no match rather than inventing a destination; runtime_graph.py:validate can keep the current slide.
    qt = _terms(text)
    if qt:
        for s in content_slides(slides):
            n = len(qt & _terms(" ".join(s.get("topics", [])) + " " + s.get("title", "")))
            if n > score:
                best, score = s, n
        if best:
            return best["id"], "topic"
    return None, ""


# Find the first callout sharing a fact with the answer, or return no callout.
# route_for adds this ID to the route that runtime_graph.py:validate returns to the player.
def _callout_for(s: dict | None, facts: set[str]) -> str | None:
    for c in (s or {}).get("callouts", []):
        if set(c.get("fact_ids", [])) & facts:
            return c["id"]
    return None


# Compare the answer facts with the current and available slides to choose stay, jump or none.
# Returns a route dictionary consumed by runtime_graph.py:validate; it does not generate an answer.
def route_for(slides: list[dict], current_id: str | None, fact_ids: list[str] | None, text: str = "") -> dict:
    """stay: the current slide carries one of the answer's facts (the customer asked about what they are looking at) ·
    jump: another slide carries them, or the question names another slide's topic · none: nothing matches."""
    cur = next((s for s in slides if s["id"] == current_id), None)
    facts = set(fact_ids or [])
    if cur and facts and (slide_facts(cur) & facts):
        return {"slide_id": cur["id"], "route": "stay", "callout_id": _callout_for(cur, facts), "by": "facts"}
    sid, by = slide_for(slides, fact_ids, text)
    if not sid:
        return {"slide_id": current_id, "route": "none", "callout_id": None, "by": ""}
    if sid == current_id:
        return {"slide_id": sid, "route": "stay", "callout_id": _callout_for(cur, facts), "by": by}
    return {"slide_id": sid, "route": "jump", "callout_id": _callout_for(next(s for s in slides if s["id"] == sid), facts), "by": by}
