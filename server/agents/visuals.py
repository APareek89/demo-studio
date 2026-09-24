"""Post-script visual audit: rules propose; Gemini verifies the real pixels; deterministic code enforces the result.

Every uploaded image is inspected after the script exists. For each spoken line the audit records the concrete
features being claimed, which of them the assigned image visibly proves, and what remains missing. Only full visual
coverage can replace a feature line's current evidence. The audit is saved as visual-audit.json and in the run logs."""
from __future__ import annotations

import json
import re
from typing import Literal

from pydantic import BaseModel, Field

from .. import config, media, store
from ..llm import gemini

# Ignore common words, positions and generic product terms when proposing visual matches.
# These tokens support server/agents/deck.py:choose_image; they are not factual evidence or a pixel check.
STOP = set("the a an and or of to in on at for with by from as is are was were be been it its this that these those you your we our they their he she i me my "
           "so if then than but not no yes can will would could should may might do does did done have has had into onto over under about across after before "
           "one two three four five six seven eight nine ten first second third also just only very more most less least much many any all some every each per "
           "here there where when what which who whom whose how why let's lets get got go going come came make made take took see seen show shown look looked "
           "like want need say said tell told ask asked give gave keep kept turn turned start stop up down out off back again still even now day days week weeks "
           "km kms kilometre kilometres kilometer kilometers hour hours minute minutes rs rupee rupees lakh lakhs percent view shot close closeup image picture "
           "vehicle car scooter bike product model variant brochure page front rear side left right top high low angle detail lifestyle blue red black white "
           "colour color new".split())

# Expand a limited set of feature words so related labels can propose the same picture.
# server/agents/understand.py:run supplies the tags; the pixel audit still decides literal coverage when available.
# feature-level synonyms only (generic words like front/back/drive are deliberately absent)
SYNONYMS = {"gearbox": ["gear", "shifter", "transmission", "dct", "manual", "automatic", "paddle", "lever"], "gear": ["gearbox", "shifter", "transmission", "dct", "lever"],
            "transmission": ["gearbox", "gear", "dct", "shifter"], "dct": ["gearbox", "gear", "transmission", "automatic"], "shift": ["gearbox", "gear", "shifter", "lever"], "paddle": ["paddle", "shifter"],
            "battery": ["charger", "charging", "pack", "kwh"], "charger": ["charging", "socket", "plug", "battery"], "charging": ["charger", "socket", "plug", "battery"], "range": ["battery"],
            "seat": ["upholstery", "cabin", "interior", "legroom"], "interior": ["cabin", "seat", "dashboard", "console", "upholstery"], "cabin": ["interior", "seat", "dashboard", "upholstery"],
            "display": ["screen", "cluster", "infotainment", "tft", "touchscreen"], "screen": ["display", "cluster", "infotainment", "touchscreen"], "infotainment": ["display", "screen", "touchscreen"],
            "airbag": ["airbags", "curtain"], "safety": ["airbag", "airbags", "adas", "abs", "sensor", "camera"], "adas": ["safety", "sensor", "camera", "cruise"],
            "boot": ["luggage", "storage", "underseat"], "storage": ["boot", "luggage", "underseat"], "luggage": ["boot", "storage"], "underseat": ["boot", "storage"],
            "wheel": ["alloy", "tyre", "rim"], "alloy": ["wheel", "rim"], "tyre": ["wheel"], "roof": ["sunroof", "panoramic"], "sunroof": ["roof", "panoramic"], "panoramic": ["sunroof", "roof"],
            "engine": ["turbo", "motor"], "motor": ["engine", "hub"], "headlamp": ["headlight", "drl", "led"], "headlight": ["headlamp", "drl", "led"], "grille": ["bumper", "fascia"],
            "steering": ["wheel", "paddle"], "exhaust": ["muffler", "tailpipe"], "muffler": ["exhaust"], "mirror": ["orvm"]}

# Exclude claim categories that a product photograph cannot establish from the fact-to-image suggestion map.
# server/agents/understand.py:run uses build_map; this exclusion does not remove the underlying fact.
NON_VISUAL_FACT = re.compile(
    r"\b(price|cost|warranty|roadside|service|capacity|boot space|litres?|expandable|efficiency|power|torque|"
    r"airbags?|isofix|anchorage|stability control|brakes?|brake assist|suspension|fuel type|transmissions?|"
    r"standard on|all variants?|not offered|availability|colou?rs?|foldable|seat split|rear bench)\b", re.I)


# Apply a small plural normalization so labels such as seats can match seat.
# Used by local matching helpers shared with server/agents/deck.py:choose_image, not a general language parser.
def _stem(w: str) -> str:
    return w[:-1] if w.endswith("s") and len(w) > 4 and not w.endswith("ss") else w


# Extract lowercase feature-like words, discard generic terms and normalize simple plurals.
# Returns a set for matching tags from server/agents/understand.py:run against narration and slide topics.
def _tokens(text: str) -> set[str]:
    out = set()
    for w in re.findall(r"[a-z][a-z0-9\-]+", (text or "").lower()):
        if w in STOP or len(w) < 3:
            continue
        out.add(_stem(w))
    return out


# Add the configured feature synonyms to a set of matching words without changing the original text.
# The expanded set helps build_map and server/agents/deck.py:choose_image propose candidate visuals.
def _expand(tokens: set[str]) -> set[str]:
    out = set(tokens)
    for t in tokens:
        for s in SYNONYMS.get(t, []):
            out.add(_stem(s))
    return out


# Read visible-part names from either older string tags or the newer boxed-part format.
# server/agents/plan.py:run and author.py:run use the resulting labels in their visual catalogues.
def part_names(img: dict) -> list[str]:
    """Part names of an image — tagged as {name, box, confidence} (slides-v1) or as plain strings (older demos)."""
    out = []
    for p in img.get("parts") or []:
        n = p.get("name") if isinstance(p, dict) else p
        if isinstance(n, str) and n.strip():
            out.append(n.strip())
    return out


# Return only part records that contain a box, leaving old name-only tags out of geometry work.
# server/agents/deck.py:place_callouts and bundle.py:build use these records for labels and slide image parts.
def part_boxes(img: dict) -> list[dict]:
    """Only the parts that carry a box: [{name, box:{x,y,w,h} in 0-1, confidence}]."""
    return [p for p in (img.get("parts") or []) if isinstance(p, dict) and isinstance(p.get("box"), dict)]


# Prefer an explicitly selected hero; otherwise choose the highest-quality full-product image or available image.
# Returns the image record used by server/agents/deck.py:build and bundle.py:build for opening/closing presentation.
def pick_hero(demo: dict, images: list[dict]) -> dict | None:
    """The hero-role upload, else the best-quality full-product view, else the first image. First and last slide."""
    for s in reversed(demo.get("sources", [])):
        if s.get("role") == "hero":
            hit = next((i for i in images if i["source_id"] == s["id"]), None)
            if hit:
                return hit
    pool = [i for i in images if i.get("full_product")] or images
    return max(pool, key=lambda i: i.get("quality", 0)) if pool else None


# Convert allowed image and shot tags into a shared matching catalogue with stronger part-name evidence.
# server/store.py:visual_allowed filters inputs; server/agents/deck.py:choose_image consumes the catalogue too.
def catalogue(demo_id: str, und: dict, demo: dict) -> list[dict]:
    items = []
    for i in und.get("images", []):
        if not store.visual_allowed(demo, i.get("source_id", "")):
            continue
        parts = part_names(i)
        items.append({"ref": i["id"], "kind": "image", "strong": _tokens(" ".join(parts)), "weak": _tokens(i.get("description", "")), "quality": i.get("quality", 3),
                      "label": f"{i['id']} · {i.get('angle', '')} · {i.get('description', '')}", "parts": parts})
    for s in und.get("shots", []):
        if not store.visual_allowed(demo, s.get("source_id", "")):
            continue
        items.append({"ref": s["id"], "kind": "shot", "strong": _tokens(s.get("part", "")), "weak": _tokens(s.get("description", "")), "quality": s.get("quality", 3),
                      "label": f"{s['id']} · {s.get('start', 0):.0f}–{s.get('end', 0):.0f}s · {s.get('part', '')} · {s.get('description', '')}", "parts": [s.get("part", "")]})
    # Mark less-common words so a generic cabin/vehicle tag cannot dominate every candidate's score.
    # The returned distinct set changes relative matching strength; it does not certify visible equipment.
    # distinctiveness: a word that shows up in a third or more of the pictures says nothing about which one to pick
    n = max(1, len(items))
    df: dict[str, int] = {}
    for it in items:
        for t in it["strong"] | it["weak"]:
            df[t] = df.get(t, 0) + 1
    for it in items:
        it["distinct"] = {t for t in it["strong"] | it["weak"] if df.get(t, 0) <= max(1, int(0.34 * n))}
    return items


# Score matching words: distinctive part names count more than descriptions or common part names.
# Return score plus matched terms for audit explanations and server/agents/deck.py:choose_image.
def _score(line_tokens: set[str], item: dict) -> tuple[float, list[str]]:
    hits = []
    score = 0.0
    for t in line_tokens:
        if t in item["strong"] and t in item["distinct"]:
            score += 3.0; hits.append(t)
        elif t in item["weak"] and t in item["distinct"]:
            score += 1.0; hits.append(t)
        elif t in item["strong"]:
            score += 0.3
    return score, sorted(set(hits))


# Describe one model judgment linking a script line to an image, or to no suitable visual.
# server/llm/gemini.py:structured fills this schema; align applies only accepted full-coverage choices.
class Assignment(BaseModel):
    line_id: str
    visual: str = Field(description="an image ref supplied in this batch, 'keep' only for the current video shot, or 'none'")
    coverage: Literal["full", "partial", "none", "not_visual"]
    spoken_features: list[str] = Field(default_factory=list, description="concrete visible product features named in the line")
    visible_features: list[str] = Field(default_factory=list, description="spoken features literally visible in the selected image")
    missing_features: list[str] = Field(default_factory=list, description="spoken features not visibly proved by the selected image")
    confidence: float = Field(default=0.5, ge=0, le=1)
    reason: str = Field(description="one short, literal explanation of the coverage decision")


# Describe what one inspected image shows and which supplied script lines it fully covers.
# Saved with visual-audit.json through server/store.py:write_json so image limitations remain reviewable.
class ImageAudit(BaseModel):
    visual: str
    visible_features: list[str] = Field(default_factory=list, description="specific product parts/features literally visible")
    script_line_ids: list[str] = Field(default_factory=list, description="lines this image fully covers")
    limitations: list[str] = Field(default_factory=list, description="features a viewer could wrongly assume this image proves")
    confidence: float = Field(default=0.5, ge=0, le=1)


# Require both line assignments and per-image findings in one structured vision response.
# server/llm/gemini.py:structured returns this shape; _vision_batches checks completeness and consistency.
class VisualsOut(BaseModel):
    assignments: list[Assignment]
    images: list[ImageAudit]


# Ask the auditor to inspect actual pixels against every visible feature named in the supplied lines.
# The output uses VisualsOut; server/agents/author.py:run calls align after writing and validating the draft.
MODEL_SYSTEM = """You are the final visual-proof auditor for a spoken product demo. You receive the REAL uploaded images first,
in the exact order listed in image_part_order, then a JSON manifest containing the complete script and earlier metadata.
Inspect the pixels, not just the metadata.

For EVERY line:
- Extract each concrete, visible product feature the narration names. A colour, trim, wheel, screen, airbag, seat, control,
  lamp, roof, boot, safety component or other physical detail is a separate feature.
- Pick an image only when the pixels literally show ALL those visible features. "full" means every visible feature is
  clearly shown; "partial" means at least one is shown and at least one is missing; "none" means no supplied image proves it.
- Use "not_visual" for greetings, opinions, prices, warranty, performance figures, availability and other claims a photo
  cannot prove. Never call a beauty shot proof of safety, cabin equipment, an engine specification or written terms.
- "keep" is allowed only when current_kind is "shot" and the shot metadata literally covers all visible features.
- Prefer the clearest close-up over a generic exterior. Do not optimize for variety at the cost of truth.

Also return one image audit for EVERY ref in image_part_order: list only features visibly present, the line ids it fully
covers, and important limitations. Return one assignment for EVERY supplied line id. Use only an image ref from
image_part_order, "keep", or "none"."""


# Send each allowed image batch plus the line manifest for a real-pixel coverage audit.
# server/media.py:model_image_path supplies image files; server/llm/gemini.py:structured returns assignments and image notes.
def _vision_batches(demo_id: str, demo: dict, und: dict, cat: list[dict], rows: list[dict]) -> tuple[list[dict], list[dict]]:
    """Gemini-inspect every allowed image in batches, then retain the strongest full-coverage decision per line."""
    if config.MOCK_LLM:
        return [], []
    src_by_id = {s.get("id"): s for s in demo.get("sources", [])}
    info_by_ref = {i.get("id"): i for i in und.get("images", [])}
    image_cat = [c for c in cat if c.get("kind") == "image"]
    all_assignments: list[dict] = []
    image_audit: list[dict] = []
    # Limit each vision request to twelve images and keep their transmitted order explicit.
    # Images that cannot be decoded are omitted from this batch, never represented by invented pixel findings.
    for start in range(0, len(image_cat), 12):
        batch = image_cat[start:start + 12]
        refs: list[str] = []
        parts = []
        for item in batch:
            src = src_by_id.get((info_by_ref.get(item["ref"]) or {}).get("source_id"))
            if not src:
                continue
            try:
                parts.append(gemini.bytes_part(media.model_image_path(demo_id, src)))
                refs.append(item["ref"])
            except Exception:
                continue
        if not refs:
            continue
        allowed = set(refs)
        # Pair the image IDs with their bytes and supply each line's text/current choice/rule proposal.
        # The model must decide coverage from the images, not simply approve the earlier metadata labels.
        payload = {
            "image_part_order": refs,
            "image_metadata": [{"ref": c["ref"], "tagged_as": c["label"], "parts": c["parts"]} for c in batch if c["ref"] in allowed],
            "lines": [{"line_id": r["ln"]["id"], "segment": f"{r['seg'].get('title')} ({r['seg'].get('topic')})",
                       "text": r["ln"].get("text", ""), "current": r["cur"],
                       "current_kind": (next((c["kind"] for c in cat if c["ref"] == r["cur"]), "none")),
                       "rule_proposal": r["proposal"], "rule_matches": r["hits"] if r["proposal"] else []} for r in rows],
        }
        out = gemini.structured(MODEL_SYSTEM + "\n\nINPUT MANIFEST:\n" + json.dumps(payload, ensure_ascii=False), parts, VisualsOut, temperature=0.05)
        # Reject incomplete or inconsistent audits before any assignment can modify the script.
        # Unknown visual/line references cannot become trusted links for server/agents/bundle.py:build.
        expected_lines = {r["ln"]["id"] for r in rows}
        row_by_id = {r["ln"]["id"]: r for r in rows}
        if len(out.assignments) != len(expected_lines) or {a.line_id for a in out.assignments} != expected_lines:
            raise RuntimeError("Gemini returned an incomplete line-by-line coverage audit")
        if len(out.images) != len(allowed) or {item.visual for item in out.images} != allowed:
            raise RuntimeError("Gemini returned an incomplete per-image coverage audit")
        for a in out.assignments:
            if a.visual not in allowed and a.visual not in ("keep", "none"):
                continue
            current_kind = next((c["kind"] for c in cat if c["ref"] == row_by_id[a.line_id]["cur"]), "none")
            invalid = ((a.visual == "keep" and current_kind != "shot") or
                       (a.coverage == "full" and (a.visual == "none" or bool(a.missing_features))) or
                       (a.coverage == "partial" and (not a.visible_features or not a.missing_features)))
            if invalid:
                raise RuntimeError(f"Gemini returned an internally inconsistent audit for {a.line_id}")
            all_assignments.append(a.model_dump())
        for item in out.images:
            if item.visual in allowed:
                if not set(item.script_line_ids).issubset(expected_lines):
                    raise RuntimeError(f"Gemini image audit cited an unknown line for {item.visual}")
                image_audit.append(item.model_dump())
    return all_assignments, image_audit


# Audit a written script against allowed media, update its line visual references and save the reasoning.
# server/agents/author.py:run calls this before saving; server/agents/deck.py:build later selects slide-level imagery.
def align(demo_id: str, script: dict, und: dict, emit=lambda m: None) -> dict:
    demo = store.load(demo_id)
    cat = catalogue(demo_id, und, demo)
    if not cat:
        return script
    by_ref = {c["ref"]: c for c in cat}
    # Compare each main/deeper line with tagged parts and descriptions to propose a stronger candidate.
    # Keep the current choice and score alongside the proposal so the subsequent pixel check can disagree.
    rows: list[dict] = []  # per line working record
    for seg in script.get("segments", []):
        for ln in seg.get("lines", []) + seg.get("deeper", []):
            lt = _expand(_tokens(ln.get("text", "")))
            cur = (ln.get("visual") or {}).get("ref")
            scored = sorted(((*_score(lt, c), c["ref"]) for c in cat), key=lambda x: -x[0])
            best_score, best_hits, best_ref = scored[0]
            cur_score, cur_hits = _score(lt, by_ref[cur]) if cur in by_ref else (0.0, [])
            proposal = best_ref if best_score >= 3.0 and best_ref != cur and best_score >= cur_score + 3.0 else None
            rows.append({"seg": seg, "ln": ln, "cur": cur, "cur_hits": cur_hits, "proposal": proposal, "hits": best_hits, "score": best_score, "deeper": ln in seg.get("deeper", [])})
    # Include closing lines in the same proposal/audit process, with an explicit closing context.
    # This changes line metadata only; web/player/player.js:slidesOf still uses the published slide structure.
    closing_seg = {"title": "Closing", "topic": "closing", "role": "outcome"}
    for ln in script.get("closing", []):
        lt = _expand(_tokens(ln.get("text", "")))
        cur = (ln.get("visual") or {}).get("ref")
        scored = sorted(((*_score(lt, c), c["ref"]) for c in cat), key=lambda x: -x[0])
        best_score, best_hits, best_ref = scored[0]
        cur_score, cur_hits = _score(lt, by_ref[cur]) if cur in by_ref else (0.0, [])
        proposal = best_ref if best_score >= 3.0 and best_ref != cur and best_score >= cur_score + 3.0 else None
        rows.append({"seg": closing_seg, "ln": ln, "cur": cur, "cur_hits": cur_hits, "proposal": proposal,
                     "hits": best_hits, "score": best_score, "deeper": False})
    changes: list[dict] = []
    model_notes: list[dict] = []
    image_audit: list[dict] = []
    decided = False
    # Prefer complete pixel findings over rule scores; only full coverage can retain a bound image.
    # The audit can clear a current image, while eligible shot assignments may keep their existing reference.
    if not config.MOCK_LLM:
        try:
            assignments, image_audit = _vision_batches(demo_id, demo, und, cat, rows)
            byid: dict[str, list[dict]] = {}
            for assignment in assignments:
                byid.setdefault(assignment["line_id"], []).append(assignment)
            coverage_rank = {"full": 4, "partial": 2, "none": 1, "not_visual": 0}
            for r in rows:
                candidates = byid.get(r["ln"]["id"], [])
                if not candidates:
                    continue
                a = max(candidates, key=lambda x: (coverage_rank.get(x.get("coverage"), -1), x.get("confidence", 0)))
                # Pixel audit is authoritative: an old assignment does not survive merely
                # because Gemini found no better picture in this batch. Only literal full
                # coverage may bind media; every other result returns to the neutral model/card.
                choice = None
                if a.get("coverage") == "full":
                    choice = r["cur"] if a.get("visual") == "keep" else a.get("visual")
                if choice and choice not in by_ref:
                    continue
                note = {"line_id": r["ln"]["id"], "visual": choice or "none", "coverage": a.get("coverage", "none"),
                        "spoken_features": a.get("spoken_features", [])[:12], "visible_features": a.get("visible_features", [])[:12],
                        "missing_features": a.get("missing_features", [])[:12], "confidence": a.get("confidence", 0),
                        "reason": str(a.get("reason", ""))[:240]}
                model_notes.append(note)
                if choice != r["cur"]:
                    changes.append({"line_id": r["ln"]["id"], "from": r["cur"], "to": choice, "pass": "gemini_vision", "why": note["reason"]})
                    r["ln"]["visual"] = {"ref": choice, "focus": (r["ln"].get("visual") or {}).get("focus", "")} if choice else None
            decided = bool(model_notes)
        except Exception as e:
            emit(f"Gemini visual-proof audit skipped ({str(e)[:80]}) — existing visual assignments retained; rule proposals recorded only.")
    # Without pixel decisions, preserve the validated Author bindings, including explicit none.
    # Metadata matches and unused-image variety are proposals, not evidence that permits replacing them.
    # author.validate already clears unknown/excluded references before this audit runs.
    used = {(r["ln"].get("visual") or {}).get("ref") for r in rows}
    # Save changed assignments, missing features, unused images and which audit method actually ran.
    # server/store.py:write_json retains the detailed audit; the returned script carries a compact summary.
    audit = {"method": "gemini_pixels" if decided else "rules_fallback", "model": config.GEMINI_MODEL if decided else None,
             "lines": model_notes, "images": image_audit, "changes": changes, "catalogue": [c["label"] for c in cat],
             "unused_after": [c["ref"] for c in cat if c["ref"] not in used],
             "proposals": [{"line_id": r["ln"]["id"], "proposal": r["proposal"], "hits": r["hits"]} for r in rows if r["proposal"]]}
    store.write_json(demo_id, "visual-audit.json", audit)
    store.log(demo_id, "visuals", audit)
    script["visual_audit"] = {"method": audit["method"], "model": audit["model"], "line_count": len(model_notes),
                              "image_count": len(image_audit), "missing_line_count": sum(1 for x in model_notes if x.get("missing_features"))}
    if changes:
        emit(f"Visual-proof audit complete: Gemini inspected {len(image_audit)} image(s); {len(changes)} line assignment(s) changed to match the words.")
    elif decided:
        emit(f"Visual-proof audit complete: Gemini inspected {len(image_audit)} image(s); every assigned picture matches its spoken line.")
    else:
        emit("Existing visual assignments retained; rule proposals recorded only because Gemini pixel audit was unavailable.")
    return script



# Suggest up to three visually relevant media IDs for each fact using labels and distinctive-word scores.
# server/agents/understand.py:run saves this lookup; photos are not accepted as proof of nonvisual quantities or terms.
def build_map(und: dict, demo: dict) -> dict:
    """fact id → best picture refs (distinctive-subject match between the fact's claim/value and what each picture shows).
    Built at configure; used by the author, the runtime batches and the answers so the screen matches the words."""
    cat = catalogue("", und, demo)
    out = {}
    for f in und.get("facts", []):
        cue = f"{f.get('claim', '')} {f.get('value', '')} {f.get('conditions', '')}"
        # A product photo can illustrate a visible object; it cannot prove a
        # price, capacity, count, written term or hidden safety mechanism.
        if NON_VISUAL_FACT.search(cue):
            continue
        lt = _expand(_tokens(f"{cue} {f.get('kind', '')}"))
        scored = sorted(((*_score(lt, c), c["ref"]) for c in cat), key=lambda x: -x[0])
        refs = [r for sc, hits, r in scored if sc >= 3.0][:3]
        if refs:
            out[f["id"]] = refs
    return out


# Return the first suggestion available for the supplied cited fact IDs, or None when no map entry exists.
# server/agents/qa.py:answer and pitch.py:plan_pitch use this fallback when choosing runtime visuals.
def for_facts(und: dict, fact_ids: list[str]) -> str | None:
    m = und.get("image_map") or {}
    for fid in fact_ids or []:
        if m.get(fid):
            return m[fid][0]
    return None


# Rank cited-fact image suggestions against the actual spoken words, retaining an equally good current choice.
# server/agents/pitch.py:plan_pitch uses this to avoid choosing a contradictory sibling image from a shared fact.
def for_text_and_facts(demo_id: str, und: dict, text: str, fact_ids: list[str], current: str = "") -> str | None:
    """Pick the most literal cited visual when a runtime model chose a contradictory sibling.

    Example: a transmission fact can map to both manual and automatic gear images. The spoken
    words decide between them; a generic or equally good current choice is left untouched.
    """
    mapped: list[str] = []
    image_map = und.get("image_map") or {}
    for fid in fact_ids or []:
        for ref in image_map.get(fid, []):
            if ref not in mapped:
                mapped.append(ref)
    if current and current not in mapped:
        mapped.insert(0, current)
    if not mapped:
        return current or None
    by_ref = {item["ref"]: item for item in catalogue(demo_id, und, store.load(demo_id))}
    line_tokens = _expand(_tokens(text))
    ranked = sorted(((_score(line_tokens, by_ref[ref])[0], -idx, ref) for idx, ref in enumerate(mapped) if ref in by_ref), reverse=True)
    if not ranked:
        return current or None
    best_score, _, best_ref = ranked[0]
    current_score = _score(line_tokens, by_ref[current])[0] if current in by_ref else -1
    return best_ref if best_score >= 3.0 and best_score > current_score else (current or best_ref)
