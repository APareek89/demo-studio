"""Stage 1 — Understand.  Gemini watches; Claude reads.

Outputs understanding.json: product, shots, images, fact registry (with citations),
unknowns, brand profile. Nothing downstream may state a fact that is not in here.
"""
from __future__ import annotations

import csv
import json

from .. import config, media, schemas, sources, store
from ..llm import claude, gemini

VIDEO_PROMPT = """You are indexing product footage so a demo can seek to the exact moment that shows a feature.
Split this video into shots (a shot = one continuous camera view or one distinct subject). For EACH shot give
start and end in seconds (floats, covering the whole video in order), what is visible, the product part shown,
the feature it could demonstrate, a quality score 1-5 for use as demo footage, and any on-screen text.
Be concrete and literal about what is visible — never infer specifications from footage.
Product hint: {hint}
Cap at 60 shots; merge very short cuts of the same subject."""

IMAGES_PROMPT = """These are product images in the order given (index 0 first). For each image describe what is visible,
the camera angle, and a quality score 1-5 for use as a demo visual. List EVERY distinct product part you can actually see
(headlamp, grille, alloy wheel, touchscreen, seat, boot, charging port, badge, mirror…), each with a TIGHT bounding box
[ymin, xmin, ymax, xmax] on a 0-1000 grid of that image and your confidence 0-1 that the part is visible and the box is tight.
Set full_product true only when the whole product is in frame. Be literal — never infer specifications. Product hint: {hint}"""

FACTS_SYSTEM = """You build the FACT REGISTRY for a spoken product demo. The registry is the ONLY thing the demo
agent will be allowed to say. Rules:
- Extract every customer-relevant fact from the sources: specs, prices, offers, warranty/policies, features,
  availability, claims. One fact per row, value quoted exactly as the source states it, with units and conditions.
- Every fact cites its source id, a locator (page / heading / URL fragment) and a short exact quote.
- Never invent, round, or "fill in" a value. If two sources disagree, keep both facts and note it in conditions.
- Marketing adjectives are not facts. "Best-in-class" without a number is a claim with confidence ≤ 0.4.
- UNKNOWNS: list 8-15 questions a real buyer of this kind of product would ask that these sources do NOT answer
  (e.g. weight, delivery time, service cost). These become the gap list the brand sees. Give each a category
  (pricing, finance, insurance, warranty_service, features, availability, comparison, usage, other) and name the
  document that would answer it (e.g. "EMI schedule / bank tie-up sheet", "insurance partner terms", "spec sheet PDF",
  "FAQ page", "dealer price list for the state").
- BRAND: from the brand guideline if given; otherwise infer a sensible, restrained profile from the product and
  its category and say so in persona_hint.
- PRODUCT: name, category, a factual 2-sentence summary, and who buys it.
Return only what the schema asks for."""


COMP_SYSTEM = """You extract ONLY stated facts from the supplied competitor source, for a strictly-cited comparison.
Rules: one fact per row, value exactly as stated with units, a locator and a short exact quote; kinds spec/price/offer/policy/
feature/availability; never infer or round; ignore marketing adjectives. Name the product as the source names it.
Use only this source, never general knowledge or the main demo product. Each fact must cite the supplied SOURCE id.
Preserve the exact model generation, variant, engine/fuel, transmission, test cycle, market, price basis and effective date
when stated. Put applicability in the claim and conditions; a feature of a named variant is never a whole-range feature.
Respect table headers, availability marks and footnotes. If extracted table text does not preserve which variant a value
belongs to, omit that fact rather than reconstructing the columns. A URL or marketing teaser is not evidence of the
linked brochure's contents. An unavailable/empty source yields no facts."""


def _part(p) -> dict:
    """Gemini's [ymin, xmin, ymax, xmax] on a 0-1000 grid → {x, y, w, h} in 0-1, clamped and ordered."""
    b = [v for v in (p.box_2d or [])][:4] + [0, 0, 0, 0]
    y0, x0, y1, x1 = [min(1000, max(0, int(v))) / 1000.0 for v in b[:4]]
    if x1 < x0:
        x0, x1 = x1, x0
    if y1 < y0:
        y0, y1 = y1, y0
    return {"name": (p.name or "").strip().lower(), "box": {"x": round(x0, 4), "y": round(y0, 4), "w": round(x1 - x0, 4), "h": round(y1 - y0, 4)},
            "confidence": round(min(1.0, max(0.0, float(p.confidence or 0.0))), 3)}


def _stills_from_shots(demo_id: str, demo: dict, shots: list[dict], emit, max_stills: int = 12) -> int:
    """A demo with video but no images gets one still per good shot, added as ordinary image sources
    (role product, derived_from = the shot) so tagging, the deck and the player treat them like uploads."""
    src_by_id = {s["id"]: s for s in demo["sources"]}
    good = sorted((s for s in shots if s.get("quality", 0) >= 3 and (s["end"] - s["start"]) >= 0.8), key=lambda s: (-s["quality"], s["start"]))[:max_stills]
    n = 0
    for sh in good:
        src = src_by_id.get(sh["source_id"])
        if not src:
            continue
        video = store.path(demo_id, src.get("play") or src["path"])
        tmp = store.path(demo_id, "derived", f"still_{sh['id']}.jpg")
        try:
            if not media.extract_still(video, (sh["start"] + sh["end"]) / 2, tmp):
                continue
            added = store.add_file_source(demo_id, f"{sh['id']}-{sources.slug(sh.get('part') or 'still')}.jpg", tmp.read_bytes(), role="product")
            store.patch_source(demo_id, added["id"], {"derived_from": sh["id"]})
            tmp.unlink(missing_ok=True)
            n += 1
        except Exception as e:  # noqa: BLE001 — a still is best effort; the shot itself stays usable
            emit(f"Still for {sh['id']} skipped ({str(e)[:60]}).")
    if n:
        emit(f"No images were uploaded — took {n} still(s) from the video's best shots to use as pictures.")
    return n


def _hint(demo: dict) -> str:
    p = demo.get("product", {})
    return f"{demo.get('name','')} — {p.get('category','')} {p.get('url','')}".strip(" —")


def _verified_manifest(demo_id: str, demo: dict) -> schemas.FactsOut | None:
    """Load an explicit human-reviewed fact manifest when reasoning providers are unavailable."""
    manifests = [s for s in demo.get("sources", []) if s.get("kind") == "text" and s.get("name", "").lower() == "verified-facts.csv"]
    if not manifests:
        return None
    source = manifests[-1]
    rows = list(csv.DictReader(store.path(demo_id, source["path"]).read_text(encoding="utf-8").splitlines()))
    by_name = {s.get("name"): s for s in demo.get("sources", [])}
    by_name.update({s.get("url"): s for s in demo.get("sources", []) if s.get("url")})
    product, brand = {}, {}
    facts, unknowns = [], []
    for row in rows:
        record_type = (row.get("record_type") or "").strip().lower()
        if record_type == "product":
            product = {k: (row.get(k) or "").strip() for k in ("name", "category", "summary", "audience")}
        elif record_type == "brand":
            brand = {
                "tone": (row.get("tone") or "").strip(), "voice_style": (row.get("voice_style") or "").strip(),
                "dos": [x.strip() for x in (row.get("dos") or "").split("|") if x.strip()],
                "donts": [x.strip() for x in (row.get("donts") or "").split("|") if x.strip()],
                "persona_hint": (row.get("persona_hint") or "").strip(),
            }
        elif record_type == "unknown":
            unknowns.append(schemas.UnknownOut(
                question=(row.get("claim") or "").strip(), why_customers_ask=(row.get("why") or "").strip(),
                category=(row.get("category") or "other").strip(), suggested_document=(row.get("suggested_document") or "").strip(),
            ))
        elif record_type == "fact":
            cited = by_name.get((row.get("source_name") or "").strip())
            if not cited or cited["id"] == source["id"]:
                raise RuntimeError(f"Verified manifest cites an unknown source: {row.get('source_name', '')}")
            facts.append(schemas.FactOut(
                kind=(row.get("kind") or "other").strip(), claim=(row.get("claim") or "").strip(),
                value=(row.get("value") or "").strip(),
                source=schemas.FactSource(ref=cited["id"], locator=(row.get("locator") or "").strip(), quote=(row.get("quote") or "").strip()),
                confidence=float(row.get("confidence") or 1.0), conditions=(row.get("conditions") or "").strip(),
                truth=(row.get("truth") or "stated").strip(),
            ))
    if not facts or not product or not brand:
        raise RuntimeError("Verified manifest needs product, brand and at least one fact row")
    return schemas.FactsOut(product=schemas.Product(**product), facts=facts, unknowns=unknowns, brand=schemas.Brand(**brand))


def run(demo_id: str, emit, instruction: str = "") -> dict:
    demo = store.load(demo_id)
    prev = store.read_json(demo_id, "understanding.json")
    hint = _hint(demo)
    shots: list[dict] = []
    images: list[dict] = []
    video_summaries: dict[str, str] = {}
    n_shot = 0

    # ---- visuals (Gemini) ----
    videos = [s for s in demo["sources"] if s["kind"] == "video" and s.get("role") != "intro_video"]
    imgs = [s for s in demo["sources"] if s["kind"] == "image"]
    for src in videos:
        emit(f"Watching {src['name']}…")
        prep = media.prepare_video(demo_id, src, emit)
        if prep.get("play") and prep["play"] != src["path"]:
            store.patch_source(demo_id, src["id"], {"play": prep["play"], "proxy": bool(prep.get("proxy"))})
        p = prep["model"]
        try:
            up = gemini.upload_file(p, src.get("mime") if not prep.get("proxy") else "video/mp4")
            out = gemini.structured(VIDEO_PROMPT.format(hint=hint), [gemini.file_part(up)], schemas.ShotsOut)
        except Exception as e:
            raise RuntimeError(f"Video understanding failed for {src['name']}: {gemini.describe_error(e)}") from e
        video_summaries[src["id"]] = out.summary
        for sh in out.shots:
            n_shot += 1
            d = sh.model_dump()
            d.update({"id": f"sh{n_shot:02d}", "source_id": src["id"]})
            shots.append(d)
        store.log(demo_id, "understand-video", {"source": src["id"], "shots": len(out.shots)})
    if not imgs and shots and _stills_from_shots(demo_id, demo, shots, emit):
        demo = store.load(demo_id)
        imgs = [s for s in demo["sources"] if s["kind"] == "image"]
    if imgs:
        emit(f"Looking at {len(imgs)} image{'s' if len(imgs) != 1 else ''}…")
        for i in range(0, len(imgs), 12):
            batch = imgs[i:i + 12]
            parts = []
            for s in batch:
                try:
                    parts.append(gemini.bytes_part(media.model_image_path(demo_id, s)))
                except Exception as e:
                    emit(f"Could not decode {s['name']} ({str(e)[:60]}) — skipping it for tagging.")
                    parts.append(None)
            try:
                out = gemini.structured(IMAGES_PROMPT.format(hint=hint), parts, schemas.ImagesOut)
                by_index = {im.index: im for im in out.images}
            except Exception as e:
                # Don't fail the whole read for a transient vision outage: keep the images untagged and say so.
                emit(f"Image tagging unavailable ({gemini.describe_error(e)[:90]}) — keeping the images untagged; re-read later to tag them.")
                by_index = {}
            for j, s in enumerate(batch):
                im = by_index.get(j)
                images.append({
                    "id": f"im{len(images)+1:02d}", "source_id": s["id"],
                    "description": im.description if im else f"{s['name']} (untagged — image tagging was unavailable)", "angle": im.angle if im else "",
                    "parts": [_part(pp) for pp in (im.parts if im else [])], "quality": im.quality if im else 3,
                    "full_product": bool(im.full_product) if im else False,
                })

    # ---- facts + brand (Claude) ----
    # Rival pages have their own constrained extractor below. Feeding them into
    # the product registry wastes context and risks attributing rival specs to
    # the product under review.
    control_sources = {"verified-plan.json.md", "verified-script.json.md"}
    docs = [s for s in demo["sources"] if s["kind"] in ("pdf", "doc", "url", "text")
            and s.get("role") != "competitor" and s.get("name", "").lower() not in control_sources]
    emit("Reading the catalogue, documents and product page…" if docs else "No documents given — the registry will be thin; the gap list will say what's missing.")
    blocks: list[dict] = []
    for s in docs:
        role = s.get("role", "product")
        if s["kind"] == "pdf":
            blocks.append(claude.text_block(f"=== SOURCE {s['id']} · pdf · role={role} · {s['name']} ==="))
            try:
                blocks.append(claude.pdf_block(store.path(demo_id, s["path"]), title=s["name"]))
            except Exception as e:
                blocks.append(claude.text_block(f"[pdf could not be attached: {e}] Extracted text follows:\n" + sources.source_text(demo_id, s)["text"][:60000]))
        else:
            st = sources.source_text(demo_id, s)
            blocks.append(claude.text_block(f"=== SOURCE {s['id']} · {s['kind']} · role={role} · {st['name']} ===\n{st['text'][:60000]}"))
    if not docs:
        blocks.append(claude.text_block("No documents or URL were provided. Build the registry only from what is certain (product name), leave facts empty, and make the unknowns list thorough."))
    blocks.append(claude.text_block(
        f"PRODUCT HINT: {hint}\nVISUALS AVAILABLE (for context only, never a fact source): "
        f"{len(shots)} video shots, {len(images)} images.\n"
        + (f"\nPREVIOUS REGISTRY (revise it, keep ids stable where the fact is unchanged):\n{json.dumps(prev.get('facts', [])[:200])}" if prev and instruction else "")
        + (f"\n\nREVISION INSTRUCTION FROM THE USER — follow it precisely:\n{instruction}" if instruction else "")
    ))
    try:
        out = claude.structured(FACTS_SYSTEM, blocks, schemas.FactsOut, max_tokens=32000)
    except Exception as e:
        # A visually rich brochure can exceed the provider's request envelope even
        # though its human-reviewed fact manifest is small and complete. Treat that
        # explicit manifest as the safe fallback; do not discard the whole read.
        manifest = _verified_manifest(demo_id, demo)
        request_too_large = any(marker in str(e).lower() for marker in ("request_too_large", "request too large", "maximum size"))
        if not config.ANTHROPIC_API_KEY or claude._provider_unavailable(e) or isinstance(e, claude.TextFallbackError) or (request_too_large and manifest):
            # Gemini cannot consume Anthropic's in-message PDF block, but the
            # source layer already has a guarded text extractor for every doc.
            # Preserve source boundaries and citations in a text-only retry.
            if manifest:
                reason = "request was too large" if request_too_large else "primary document reader was unavailable"
                emit(f"The {reason} — using the explicit verified-fact manifest…")
                out = manifest
            elif isinstance(e, claude.TextFallbackError):
                # Text sources already traversed the full chain inside claude.structured.
                raise RuntimeError(f"Fact extraction failed: {e}") from e
            else:
                emit("Primary document reader unavailable — retrying from extracted source text…")
                plain = []
                for s in docs:
                    st = sources.source_text(demo_id, s)
                    plain.append(f"=== SOURCE {s['id']} · {s['kind']} · role={s.get('role', 'product')} · {st['name']} ===\n{st['text'][:60000]}")
                plain.append(
                    f"PRODUCT HINT: {hint}\nVISUALS AVAILABLE (context only, never a fact source): {len(shots)} video shots, {len(images)} images."
                    + (f"\n\nREVISION INSTRUCTION FROM THE USER — follow it precisely:\n{instruction}" if instruction else "")
                )
                try:
                    out = claude.text_fallback(FACTS_SYSTEM, [{"role": "user", "content": "\n\n".join(plain)}],
                                              schemas.FactsOut, max_tokens=32000, fallback_reason=claude.describe_error(e))
                except Exception as fallback_error:
                    raise RuntimeError(f"Fact extraction failed: {gemini.describe_error(fallback_error)}") from fallback_error
        else:
            raise RuntimeError(f"Fact extraction failed: {claude.describe_error(e)}") from e

    facts = []
    for i, f in enumerate(out.facts, 1):
        d = f.model_dump()
        d.update({"id": f"F{i:03d}", "approved": True, "edited": False})
        facts.append(d)
    unknowns = []
    for i, u in enumerate(out.unknowns, 1):
        d = u.model_dump()
        d.update({"id": f"U{i:02d}", "status": "open", "origin": "extraction"})
        unknowns.append(d)
    # keep human edits from a previous registry when revising
    if prev and instruction:
        edited = {f["claim"].lower(): f for f in prev.get("facts", []) if f.get("edited")}
        for f in facts:
            e = edited.get(f["claim"].lower())
            if e:
                f["value"], f["edited"] = e["value"], True

    # Rival documents use the same page-located text extractor, but never enter
    # the product registry. Uploaded sources can retain their official URL as
    # metadata; source_text still reads their local document, not that URL.
    competitors = []
    comp_sources = [s for s in demo["sources"] if s.get("role") == "competitor" and s["kind"] in ("url", "pdf", "doc", "text")]
    for s in comp_sources:
        emit(f"Reading competitor source {s.get('name') or s.get('url', '')}…")
        st = sources.source_text(demo_id, s)
        try:
            cout = claude.structured(COMP_SYSTEM,
                                    f"=== SOURCE {s['id']} · competitor · {s['kind']} · {st['name']} ===\n"
                                    f"SOURCE URL: {s.get('url') or '(not supplied; cite the uploaded document)'}\n{st['text'][:50000]}",
                                    schemas.CompetitorsOut, max_tokens=12000)
        except Exception as e:
            emit(f"Competitor source skipped: {claude.describe_error(e)[:100]}")
            continue
        for comp in cout.competitors:
            cfacts = []
            for fi, f in enumerate(comp.facts, 1):
                d = f.model_dump()
                d["source"]["ref"] = s["id"]
                d.update({"id": f"C{len(competitors)+1}-{fi:03d}", "approved": True, "edited": False})
                cfacts.append(d)
            competitors.append({"name": comp.name, "url": s.get("url", ""), "source_id": s["id"], "facts": cfacts, "fetched_at": store.now()})
    und = {
        "product": out.product.model_dump(), "shots": shots, "images": images,
        "facts": facts, "unknowns": unknowns, "brand": out.brand.model_dump(),
        "video_summaries": video_summaries, "competitors": competitors,
    }
    schemas.Understanding.model_validate(und)  # contract check
    try:
        from . import visuals as _vis
        und["image_map"] = _vis.build_map(und, demo)
        emit(f"Mapped {len(und['image_map'])} facts to the pictures that show them.")
    except Exception as e:
        emit(f"Picture map skipped ({str(e)[:60]}).")
    store.write_json(demo_id, "understanding.json", und)
    store.log(demo_id, "understand", {"facts": len(facts), "unknowns": len(unknowns), "shots": len(shots), "images": len(images)})

    def upd(d):
        d["product"]["name"] = out.product.name or d["product"]["name"]
        d["product"]["category"] = out.product.category
        if not d.get("name") or d["name"] == "Untitled demo":
            d["name"] = out.product.name
    store.update(demo_id, upd)
    emit(f"Registry: {len(facts)} facts, {len(unknowns)} open questions, {len(shots)} shots, {len(images)} images.")
    try:
        media.enhance_images(demo_id, emit)
    except Exception as e:
        emit(f"Image clean-up skipped ({str(e)[:80]}).")
    return und
