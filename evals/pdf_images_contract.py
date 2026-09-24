"""PDF-only pictures enter the existing visual pipeline; no providers or network."""
from __future__ import annotations
import copy
import io
import os
from pathlib import Path
import socket
import sys
import tempfile
from unittest.mock import patch

ROOT = Path(tempfile.mkdtemp(prefix="demo-pdf-images-"))
os.environ.update(MOCK_LLM="1", CLOUD_SYNC="0", STORAGE_BACKEND="local",
                  DEMO_STUDIO_DATA=str(ROOT / "demos"), DEMO_STUDIO_GRAPH_DB=str(ROOT / "graph.sqlite"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pypdf import PdfWriter
from pypdf.generic import DictionaryObject, NameObject, NumberObject, DecodedStreamObject
from server import sources, store, schemas
from server.agents import bundle, understand, visuals
from server.llm import gemini, mock

passed = []
def check(name, truth):
    assert truth, name
    passed.append(name)
    print("PASS", name)

def blocked(*args, **kwargs):
    raise AssertionError("Outbound socket forbidden")

def pdf(pictures=(), page_refs=None):
    writer = PdfWriter()
    refs = []
    for width, height, rgb, corrupt in pictures:
        raw = DecodedStreamObject()
        raw.set_data(bytes(rgb) * (width * height) if not corrupt else b"invalid JPEG fixture")
        image = raw.flate_encode() if not corrupt else raw
        image.update({NameObject("/Type"): NameObject("/XObject"), NameObject("/Subtype"): NameObject("/Image"),
            NameObject("/Width"): NumberObject(width), NameObject("/Height"): NumberObject(height),
            NameObject("/ColorSpace"): NameObject("/DeviceRGB"), NameObject("/BitsPerComponent"): NumberObject(8)})
        if corrupt:
            image[NameObject("/Filter")] = NameObject("/DCTDecode")
        refs.append(writer._add_object(image))
    for indexes in (page_refs if page_refs is not None else [list(range(len(refs)))]):
        page = writer.add_blank_page(width=600, height=800)
        page[NameObject("/Resources")] = DictionaryObject({NameObject("/XObject"): DictionaryObject({NameObject(f"/I{i}"): refs[i] for i in indexes})})
        stream = DecodedStreamObject(); stream.set_data("\n".join(f"q 100 0 0 100 0 0 cm /I{i} Do Q" for i in indexes).encode())
        page[NameObject("/Contents")] = writer._add_object(stream)
    output = io.BytesIO(); writer.write(output); return output.getvalue()

def extract(payload, label, **kwargs):
    path = ROOT / f"{label}.pdf"; path.write_bytes(payload)
    return sources.extract_pdf_images(path, ROOT / label, **kwargs)

with patch.object(socket.socket, "connect", blocked), patch.object(socket, "create_connection", blocked), patch.object(socket, "getaddrinfo", blocked):
    picture = (128, 96, (35, 70, 110), False)
    payload = pdf([picture, picture, (96, 128, (80, 10, 150), False)], [[0, 1], [0, 2]])
    first = extract(payload, "normal")
    check("extracts actual embedded pixels with page provenance", len(first["images"]) == 2 and first["images"][0]["pages"] == [1, 2])
    check("deduplicates identical pixel data across objects and pages", first["candidates"] == 4 and len({i["sha256"] for i in first["images"]}) == 2)
    second = sources.extract_pdf_images(ROOT / "normal.pdf", ROOT / "normal")
    check("repeat extraction keeps identical assets and identities", first == second and len(list((ROOT / "normal").glob("*.png"))) == 2)
    check("picture count budget is visible", len(extract(payload, "limited", max_images=1)["images"]) == 1 and bool(extract(payload, "limited-two", max_images=1)["warnings"]))
    check("page budget defers later pages", len(extract(payload, "pages", max_pages=1)["images"]) == 1)
    gallery = pdf([(96, 96, (n * 30, 50, 90), False) for n in range(6)], [[0, 1, 2, 3, 4], [5]])
    fair = extract(gallery, "fair", max_images=3)
    check("later subject pages precede dense early galleries", len(fair["images"]) == 3 and fair["images"][2]["pages"] == [2])
    check("embedded resource index is retained for independent pixel review", fair["images"][2]["occurrences"] == [{"page": 2, "image_index": 1, "resource": "/I5"}])
    check("candidate budget limits repeated resources too", extract(payload, "candidates", max_candidates=1)["candidates"] == 1)
    check("zero time budget decodes no picture", extract(payload, "time", timeout=0)["images"] == [])
    check("total byte budget retains no oversize output", extract(payload, "bytes", max_total_bytes=1)["images"] == [])
    check("pixel budget is checked before image decoding", extract(payload, "pixels", max_pixels=100)["images"] == [])
    check("file size budget is explicit", bool(extract(payload, "file", max_file_bytes=1)["error"]))
    check("small icons are omitted", extract(pdf([(20, 20, (0, 0, 0), False)]), "icon")["images"] == [])
    check("text-only or empty-image PDF is valid", extract(pdf(), "empty")["images"] == [] and extract(pdf(), "empty-two")["error"] is None)
    check("corrupt PDF is a reported nonfatal gap", bool(extract(b"not a pdf", "corrupt")["error"]))
    broken = extract(pdf([(128, 96, (0, 0, 0), True)]), "broken-image")
    check("corrupt embedded image is skipped visibly", broken["images"] == [] and bool(broken["warnings"]))

    demo = store.new_demo("PDF-only visual fixture"); did = demo["id"]
    parent = store.add_file_source(did, "source.pdf", payload)
    events = []
    demo = understand._pdf_images_from_sources(did, store.load(did), events.append)
    children = [s for s in demo["sources"] if s.get("pdf_parent_source_id")]
    check("PDF remains sole uploaded source and fact authority", len(children) == 2 and all(s["kind"] == "image" and s["pdf_parent_source_id"] == parent["id"] and s["origin"] == "derived_pdf_image" for s in children))
    check("children have stable provenance and are visually allowed", all(store.visual_allowed(demo, s["id"]) and s["pdf_pages"] and s["pdf_parent_revision"] for s in children))
    with patch.object(sources, "extract_pdf_images", side_effect=AssertionError("unchanged cache should be reused")):
        again = understand._pdf_images_from_sources(did, store.load(did), events.append)
    check("retry reuses immutable extraction without duplicate source rows", [s for s in again["sources"] if s.get("pdf_parent_source_id")] == children)
    asset = store.path(did, children[0]["path"]); original = asset.read_bytes(); asset.write_bytes(b"damaged")
    recovered = understand._pdf_images_from_sources(did, store.load(did), events.append)
    check("damaged cached asset is re-extracted with same identity", asset.read_bytes() == original and {s["id"] for s in recovered["sources"] if s.get("pdf_parent_source_id")} == {s["id"] for s in children})
    store.patch_source(did, parent["id"], {"use_in_demo": False})
    check("parent exclusion applies immediately before another Read", all(not store.visual_allowed(store.load(did), s["id"]) for s in children))
    excluded = understand._pdf_images_from_sources(did, store.load(did), events.append)
    check("excluded PDF derivatives remain inactive on Read", all(not s.get("pdf_image_active") for s in excluded["sources"] if s.get("pdf_parent_source_id")))
    store.patch_source(did, parent["id"], {"use_in_demo": True})
    store.patch_source(did, children[0]["id"], {"use_in_demo": False})
    restored = understand._pdf_images_from_sources(did, store.load(did), events.append)
    check("parent restoration preserves individual picture rejection", not store.visual_allowed(restored, children[0]["id"]) and store.visual_allowed(restored, children[1]["id"]))
    for key, value in [("role", "competitor"), ("scope_excluded", True), ("crawl_active", False), ("revision", "new revision")]:
        altered = copy.deepcopy(restored)
        next(s for s in altered["sources"] if s["id"] == parent["id"])[key] = value
        check(f"parent {key} invalidates derived pictures", not store.visual_allowed(altered, children[1]["id"]))
    deleted = copy.deepcopy(restored); deleted["sources"] = [s for s in deleted["sources"] if s["id"] != parent["id"]]
    check("deleted parent and missing derived reference cannot publish", not store.visual_allowed(deleted, children[1]["id"]) and not store.visual_allowed(deleted, "src_pdf_missing"))
    cyclic = copy.deepcopy(restored); next(s for s in cyclic["sources"] if s["id"] == parent["id"])["pdf_parent_source_id"] = children[1]["id"]
    check("parent cycles fail closed without recursion", not store.visual_allowed(cyclic, children[1]["id"]))

    # Exercise the actual Understand image batching with a mocked model; no boxes
    # are synthesized by PDF extraction. Literal picture QA remains a separate step.
    store.patch_source(did, children[0]["id"], {"use_in_demo": True})
    def settings(d): d["settings"]["enhance_images"] = "off"
    store.update(did, settings)
    observed = []
    original_structured = gemini.structured
    def tagging(system, content, schema, **kwargs):
        if schema is schemas.ImagesOut:
            observed.append(content)
            return schemas.ImagesOut(images=[schemas.ImageG(index=i, description="Synthetic rectangle fixture, no product claim", angle="front", quality=3, parts=[], full_product=False) for i in range(len(content))])
        return original_structured(system, content, schema, **kwargs)
    with patch.object(gemini, "structured", side_effect=tagging):
        und = understand.run(did, events.append)
    check("PDF-only Read uses existing image model entry point", len(observed) == 1 and len(observed[0]) == 2 and len(und["images"]) == 2)
    check("no extraction-invented tags or boxes", all(i["parts"] == [] and i["description"].startswith("Synthetic rectangle") for i in und["images"]))
    check("stable image catalogue IDs derive from the media source", all(i["id"].startswith("im_pdf_") for i in und["images"]))
    with patch.object(gemini, "structured", side_effect=RuntimeError("tagging fixture unavailable")):
        gap = understand.run(did, events.append)
    check("tagging failure remains visibly untagged", all(not i["parts"] and "untagged" in i["description"] for i in gap["images"]))
    upload = store.add_file_source(did, "ordinary.png", original)
    with patch.object(gemini, "structured", side_effect=tagging):
        ordinary = understand.run(did, events.append)
    check("existing uploaded pictures retain ordinary source identity", any(i["source_id"] == upload["id"] and i["id"] == "im01" for i in ordinary["images"]))
    store.patch_source(did, parent["id"], {"use_in_demo": False})
    check("shared visual catalogue excludes parent-held derivatives", all(row["ref"] == next(i["id"] for i in ordinary["images"] if i["source_id"] == upload["id"]) for row in visuals.catalogue(did, ordinary, store.load(did))))
    # Frontend parent-source ownership and Bundle publication both use these paths.
    repo = Path(__file__).resolve().parents[1]
    check("Sources lists the parent upload without derived-file clutter", "demo.sources.filter((s) => !s.pdf_parent_source_id)" in (repo/"web/studio/sources.js").read_text())
    check("Bundle shares the parent-aware visual allowance", 'store.visual_allowed(demo, i["source_id"])' in (repo/"server/agents/bundle.py").read_text())
    store.patch_source(did, parent["id"], {"use_in_demo": True})
    store.path(did, parent["path"]).write_bytes(pdf([(128, 96, (250, 100, 20), False)]))
    changed = understand._pdf_images_from_sources(did, store.load(did), events.append)
    fresh = [s for s in changed["sources"] if s.get("pdf_parent_source_id") and store.visual_allowed(changed, s["id"])]
    check("changed parent bytes mint new identities and retire old pictures", len(fresh) == 1 and fresh[0]["id"] not in {s["id"] for s in children} and all(not store.visual_allowed(changed, s["id"]) for s in children))
    check("prior published media bytes are retained", all(store.path(did, s["path"]).is_file() for s in children))
    manifest = store.path(did, str(Path(fresh[0]["path"]).parent), f"manifest-v{sources.PDF_IMAGE_VERSION}.json")
    manifest.write_text("{broken")
    repaired = understand._pdf_images_from_sources(did, store.load(did), events.append)
    check("corrupt extraction manifest is rebuilt from source", store.visual_allowed(repaired, fresh[0]["id"]) and manifest.read_text().startswith("{"))
    doc2 = store.add_file_source(did, "second.pdf", payload)
    with patch.dict(sources.PDF_IMAGE_LIMITS, max_images=2):
        limited = understand._pdf_images_from_sources(did, store.load(did), events.append)
    check("picture budget is shared across documents", len([s for s in limited["sources"] if s.get("pdf_parent_source_id") and store.visual_allowed(limited, s["id"])]) <= 2)

    check("only time interruption marks an extraction retryable",
        extract(payload, "timeout-flag", timeout=0).get("interrupted") is True
        and not extract(payload, "count-policy-flag", max_images=1).get("interrupted")
        and not extract(payload, "page-policy-flag", max_pages=1).get("interrupted"))
    timeout_demo = store.new_demo("Interrupted PDF retry fixture")["id"]
    timeout_parent = store.add_file_source(timeout_demo, "interrupted.pdf", payload)
    real_extract = sources.extract_pdf_images
    def partially_timed_out(*args, **kwargs):
        # Preserve real successful assets and provenance, then model a time
        # interruption before the remaining distinct picture was registered.
        result = real_extract(*args, **kwargs)
        result["images"] = result["images"][:1]
        result["bytes"] = sum(item["size"] for item in result["images"])
        result["warnings"].append("PDF picture time budget reached; remaining pages deferred.")
        result["interrupted"] = True
        return result
    with patch.object(sources, "extract_pdf_images", side_effect=partially_timed_out):
        interrupted = understand._pdf_images_from_sources(timeout_demo, store.load(timeout_demo), events.append)
    initial_children = [s for s in interrupted["sources"] if s.get("pdf_parent_source_id")]
    initial_asset = store.path(timeout_demo, initial_children[0]["path"])
    initial_bytes = initial_asset.read_bytes()
    check("interrupted extraction retains its successfully registered picture", len(initial_children) == 1
        and store.visual_allowed(interrupted, initial_children[0]["id"]) and bool(initial_bytes))
    with patch.object(sources, "extract_pdf_images", wraps=real_extract) as resumed:
        complete = understand._pdf_images_from_sources(timeout_demo, store.load(timeout_demo), events.append)
    complete_children = [s for s in complete["sources"] if s.get("pdf_parent_source_id") and store.visual_allowed(complete, s["id"])]
    check("healthy Read retries interrupted extraction and preserves successful identities", resumed.call_count == 1
        and len(complete_children) == 2 and initial_children[0]["id"] in {s["id"] for s in complete_children}
        and initial_asset.read_bytes() == initial_bytes)
    with patch.object(sources, "extract_pdf_images", side_effect=AssertionError("completed retry should be reusable")):
        reused = understand._pdf_images_from_sources(timeout_demo, store.load(timeout_demo), events.append)
    check("complete extraction after interruption is reusable without duplicates", len([
        s for s in reused["sources"] if s.get("pdf_parent_source_id")]) == 2)


    # Revalidate final serialized media even when a source changes after the
    # reviewed deck was saved. Old publications remain byte-for-byte unchanged.
    published_demo = store.new_demo("PDF publication exclusion fixture")["id"]
    published_parent = store.add_file_source(published_demo, "publication.pdf", payload)
    publication_sources = understand._pdf_images_from_sources(published_demo, store.load(published_demo), events.append)
    published_child = next(s for s in publication_sources["sources"] if s.get("pdf_parent_source_id"))
    ordinary_source = store.add_file_source(published_demo, "approved-original.png", original)
    held_ref, kept_ref = "im_pdf_publication", "im_original"
    image_rows = [{"id": ref, "source_id": src["id"], "description": "reviewed synthetic image",
                   "angle": "front", "quality": 3, "parts": []}
                  for ref, src in [(held_ref, published_child), (kept_ref, ordinary_source)]]
    fact = {"id": "F1", "kind": "feature", "claim": "Fixture finish", "value": "Blue",
            "approved": True, "truth": "stated", "source": {"ref": published_parent["id"], "locator": "fixture", "quote": "Blue"}}
    speech = {"id": "line-pdf", "text": "The fixture shows a blue finish.", "fact_ids": ["F1"],
              "visual": {"kind": "image", "ref": held_ref}}
    segment = {"id": "proof", "title": "Reviewed pictures", "topic": "finish", "role": "proof",
               "lines": [speech], "deeper": [{**speech, "id": "deeper-pdf"}], "checkin": ""}
    publication_script = {"segments": [segment], "closing": [{**speech, "id": "closing-pdf"}]}
    publication_deck = {"slides": [
        {"id": "paired", "segment_id": "proof", "kind": "proof", "image_id": held_ref,
         "media": [{"image_id": held_ref, "from_line": 0}, {"image_id": kept_ref, "from_line": 0}],
         "callouts": [{"id": "held-explicit", "text": "Blue", "image_id": held_ref, "fact_ids": ["F1"]},
                      {"id": "held-legacy", "text": "Blue", "fact_ids": ["F1"]},
                      {"id": "kept", "text": "Blue", "image_id": kept_ref, "fact_ids": ["F1"]}]},
        {"id": "legacy", "segment_id": "proof", "kind": "proof", "image_id": held_ref,
         "callouts": [{"id": "legacy-label", "text": "Blue", "fact_ids": ["F1"]}]},
    ]}
    store.write_json(published_demo, "understanding.json", {"product": {"name": "Fixture"}, "images": image_rows,
        "facts": [fact], "shots": [], "unknowns": [], "image_map": {"F1": [held_ref, kept_ref]}})
    store.write_json(published_demo, "plan.json", {"segments": [], "ctas": []})
    store.write_json(published_demo, "script.json", publication_script)
    store.write_json(published_demo, "script.hi-IN.json", publication_script)
    store.write_json(published_demo, "deck.json", publication_deck)
    def publication_settings(d):
        d["settings"].update(language="en-IN", languages=["en-IN", "hi-IN"])
        d["approvals"].update({card: True for card in store.CARDS})
    store.update(published_demo, publication_settings)
    saved_deck = store.path(published_demo, "deck.json").read_bytes()
    # Timing is separately contracted with real fixture recordings; these cases
    # isolate the publication's media boundary, without recording or providers.
    with patch.object(bundle.narration, "require_minimum", return_value={"sufficient": True, "measured": False}):
        original_bundle = bundle.build(published_demo, lambda _: None)
        for label, mutate in [
            ("excluded", lambda: store.patch_source(published_demo, published_parent["id"], {"use_in_demo": False})),
            ("revised", lambda: store.update(published_demo, lambda d: next(s for s in d["sources"] if s["id"] == published_parent["id"]).update(use_in_demo=True, revision="changed-parent"))),
            ("removed", lambda: store.remove_source(published_demo, published_parent["id"]))]:
            mutate()
            serialized = bundle.build(published_demo, lambda _: None)
            languages = [serialized, serialized["alt_languages"]["hi-IN"]]
            check(f"{label} PDF is removed from line, deeper and closing visuals in all languages", all(
                line["visual"] == {"kind": "none"} for language in languages
                for line in [*language["segments"][0]["lines"], *language["segments"][0]["deeper"], *language["closing"]]))
            check(f"{label} PDF is removed from paired slide URLs and attached labels", all(
                language["slides"][0]["image_id"] == kept_ref
                and language["slides"][0]["image_url"] == language["slides"][0]["media"][0]["image_url"]
                and [m["image_id"] for m in language["slides"][0]["media"]] == [kept_ref]
                and [c["id"] for c in language["slides"][0]["callouts"]] == ["kept"] for language in languages))
            check(f"{label} PDF leaves no legacy slide picture or orphan label", all(
                language["slides"][1]["image_id"] is None and language["slides"][1]["image_url"] is None
                and language["slides"][1]["image_parts"] == [] and language["slides"][1]["media"] == []
                and language["slides"][1]["callouts"] == [] for language in languages))
            check(f"{label} PDF is removed from published catalogue and fact image map", [i["id"] for i in serialized["media"]["images"]] == [kept_ref]
                and serialized["image_map"] == {"F1": [kept_ref]})
        check("publication filtering leaves saved design, original uploads and prior result intact",
            store.path(published_demo, "deck.json").read_bytes() == saved_deck
            and store.path(published_demo, ordinary_source["path"]).read_bytes() == original
            and original_bundle["slides"][0]["image_id"] == held_ref
            and original_bundle["segments"][0]["lines"][0]["visual"]["ref"] == held_ref)

print(f"PDF IMAGES CONTRACT: {len(passed)}/{len(passed)} passed")
