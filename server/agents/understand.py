"""Stage 1 — Understand.  Gemini watches; Claude reads.

Outputs understanding.json: product, shots, images, fact registry (with citations),
unknowns, brand profile. Nothing downstream may state a fact that is not in here.
"""
from __future__ import annotations

import json

from .. import schemas, sources, store
from ..llm import claude, gemini

VIDEO_PROMPT = """You are indexing product footage so a demo can seek to the exact moment that shows a feature.
Split this video into shots (a shot = one continuous camera view or one distinct subject). For EACH shot give
start and end in seconds (floats, covering the whole video in order), what is visible, the product part shown,
the feature it could demonstrate, a quality score 1-5 for use as demo footage, and any on-screen text.
Be concrete and literal about what is visible — never infer specifications from footage.
Product hint: {hint}
Cap at 60 shots; merge very short cuts of the same subject."""

IMAGES_PROMPT = """These are product images in the order given (index 0 first). For each image describe what is visible,
the camera angle, the product parts visible, and a quality score 1-5 for use as a demo visual.
Be literal — never infer specifications. Product hint: {hint}"""

FACTS_SYSTEM = """You build the FACT REGISTRY for a spoken product demo. The registry is the ONLY thing the demo
agent will be allowed to say. Rules:
- Extract every customer-relevant fact from the sources: specs, prices, offers, warranty/policies, features,
  availability, claims. One fact per row, value quoted exactly as the source states it, with units and conditions.
- Every fact cites its source id, a locator (page / heading / URL fragment) and a short exact quote.
- Never invent, round, or "fill in" a value. If two sources disagree, keep both facts and note it in conditions.
- Marketing adjectives are not facts. "Best-in-class" without a number is a claim with confidence ≤ 0.4.
- UNKNOWNS: list 8-15 questions a real buyer of this kind of product would ask that these sources do NOT answer
  (e.g. weight, delivery time, service cost). These become the gap list the brand sees.
- BRAND: from the brand guideline if given; otherwise infer a sensible, restrained profile from the product and
  its category and say so in persona_hint.
- PRODUCT: name, category, a factual 2-sentence summary, and who buys it.
Return only what the schema asks for."""


def _hint(demo: dict) -> str:
    p = demo.get("product", {})
    return f"{demo.get('name','')} — {p.get('category','')} {p.get('url','')}".strip(" —")


def run(demo_id: str, emit, instruction: str = "") -> dict:
    demo = store.load(demo_id)
    prev = store.read_json(demo_id, "understanding.json")
    hint = _hint(demo)
    shots: list[dict] = []
    images: list[dict] = []
    video_summaries: dict[str, str] = {}
    n_shot = 0

    # ---- visuals (Gemini) ----
    videos = [s for s in demo["sources"] if s["kind"] == "video"]
    imgs = [s for s in demo["sources"] if s["kind"] == "image"]
    for src in videos:
        emit(f"Watching {src['name']}…")
        p = store.path(demo_id, src["path"])
        try:
            up = gemini.upload_file(p, src.get("mime"))
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
    if imgs:
        emit(f"Looking at {len(imgs)} image{'s' if len(imgs) != 1 else ''}…")
        for i in range(0, len(imgs), 12):
            batch = imgs[i:i + 12]
            parts = [gemini.bytes_part(store.path(demo_id, s["path"])) for s in batch]
            try:
                out = gemini.structured(IMAGES_PROMPT.format(hint=hint), parts, schemas.ImagesOut)
            except Exception as e:
                raise RuntimeError(f"Image understanding failed: {gemini.describe_error(e)}") from e
            by_index = {im.index: im for im in out.images}
            for j, s in enumerate(batch):
                im = by_index.get(j)
                images.append({
                    "id": f"im{len(images)+1:02d}", "source_id": s["id"],
                    "description": im.description if im else s["name"], "angle": im.angle if im else "",
                    "parts": im.parts if im else [], "quality": im.quality if im else 3,
                })

    # ---- facts + brand (Claude) ----
    docs = [s for s in demo["sources"] if s["kind"] in ("pdf", "doc", "url", "text")]
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

    und = {
        "product": out.product.model_dump(), "shots": shots, "images": images,
        "facts": facts, "unknowns": unknowns, "brand": out.brand.model_dump(),
        "video_summaries": video_summaries,
    }
    schemas.Understanding.model_validate(und)  # contract check
    store.write_json(demo_id, "understanding.json", und)
    store.log(demo_id, "understand", {"facts": len(facts), "unknowns": len(unknowns), "shots": len(shots), "images": len(images)})

    def upd(d):
        d["product"]["name"] = out.product.name or d["product"]["name"]
        d["product"]["category"] = out.product.category
        if not d.get("name") or d["name"] == "Untitled demo":
            d["name"] = out.product.name
    store.update(demo_id, upd)
    emit(f"Registry: {len(facts)} facts, {len(unknowns)} open questions, {len(shots)} shots, {len(images)} images.")
    return und
