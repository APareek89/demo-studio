"""Free eval: the slides-v1 player contract, exercised end to end through the mock server (no source grepping).

Phase 1: stage modes are video | slide, the 3D path is gone, runtime Q&A declines with a callback when every
provider fails, the FAQ bank still answers instantly, MP4 export is parked. Later phases add the deck checks here."""
import os, sys, time, json
os.environ["MOCK_LLM"] = "1"
os.environ.setdefault("DEMO_STUDIO_DATA", os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "test-demos"))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fastapi.testclient import TestClient
from server.app import app
from server import store, config
from server.agents import qa
from server.llm import runtime

c = TestClient(app)
rows: list[tuple[str, bool, str]] = []
def check(name: str, ok: bool, detail: str = ""):
    rows.append((name, bool(ok), detail))

def wait(i, want, secs=180):
    t0 = time.time()
    while time.time() - t0 < secs:
        s = c.get(f"/api/demos/{i}").json()["demo"]["status"]
        if s == want: return
        if s == "error": raise SystemExit("status error: " + json.dumps(c.get(f"/api/demos/{i}").json()["demo"]["stages"], indent=1))
        time.sleep(0.4)
    raise SystemExit(f"timeout waiting for {want}")

# ---- build one mock demo from the sample images ----
i = c.post("/api/demos", json={"name": "Deck QA iQube"}).json()["id"]
imgs = sorted(os.listdir("samples/iqube"))
r = c.post(f"/api/demos/{i}/sources", files=[("files", ("hero-front.webp", open("samples/iqube/front.webp", "rb").read(), "image/webp"))], data={"role": "hero"}); assert r.status_code == 200, r.text
hero_src = r.json()["added"][0]["id"]
r = c.post(f"/api/demos/{i}/sources", files=[("files", (n, open(f"samples/iqube/{n}", "rb"), "image/webp")) for n in imgs], data={"role": "product"}); assert r.status_code == 200, r.text
r = c.post(f"/api/demos/{i}/sources", data={"role": "catalogue", "text": "Battery warranty: 3 years / 50,000 km. Ex-showroom price Rs 1,24,990.", "text_name": "spec"}); assert r.status_code == 200, r.text
c.post(f"/api/demos/{i}/read"); wait(i, "align")
for card in c.get(f"/api/demos/{i}").json()["demo"]["approvals"]:
    c.post(f"/api/demos/{i}/approve/{card}")
c.post(f"/api/demos/{i}/build"); wait(i, "ready")
b = c.get(f"/api/demos/{i}/bundle").json()

# ---- 3D is gone, everywhere the customer or the studio could see it ----
check("bundle carries no 3D asset", "visual_asset" not in b)
check("no line carries a stage-mode classifier", not any("display_mode" in (l.get("visual") or {}) for s in b["segments"] for l in s["lines"] + s["deeper"]))
check("every line visual is none | image | shot", all((l.get("visual") or {}).get("kind") in ("none", "image", "shot") for s in b["segments"] for l in s["lines"]))
check("demo record has no visual_asset field", "visual_asset" not in c.get(f"/api/demos/{i}").json()["demo"])
check("no visual/ folder is created for a new demo", not (store.demo_dir(i) / "visual").exists())
check("/visual routes are gone", c.get(f"/api/demos/{i}/visual").status_code == 404)
check("/assets routes are gone", c.get("/api/assets").status_code == 404)
check("MP4 export is parked with 409", c.get(f"/api/demos/{i}/export.mp4").status_code == 409)
h = c.get("/api/health").json()
check("health lists runtime providers, not runware", "runtime_providers" in h and "runware" not in h and "runware_model" not in h)
check("index.html loads no model-viewer", "model-viewer" not in c.get("/").text)
check("player has no 3D branch", "model-viewer" not in c.get("/web/player/player.js").text)

# ---- runtime Q&A: every provider down → decline + callback, never a guess, never a cooldown ----
orig = runtime.structured
runtime.structured = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("all runtime providers failed — gemini: 503 | claude: credit balance"))
try:
    r = c.post(f"/api/demos/{i}/run/qa", json={"question": "What is the exact on-road price in Pune?", "history": [], "profile": {"name": "QA"}, "skip_bank": True}).json()
    check("providers down → declines", r["answered"] is False and r["fact_ids"] == [])
    check("providers down → offers a callback", r.get("offer_callback") is True)
    check("providers down → says it will not guess", "won't guess" in r["answer"])
    r2 = c.post(f"/api/demos/{i}/run/qa", json={"question": "What colours are there?", "history": [], "skip_bank": True}).json()
    check("no ten-minute cooldown: the next call still tries the providers (and declines again)", r2["answered"] is False)
    check("no hardcoded product fallback survives", not hasattr(qa, "_local_grounded_answer") and not hasattr(qa, "_named_competitor"))
finally:
    runtime.structured = orig
tr = c.get(f"/api/demos/{i}/trace").json()["rows"]
check("provider failure is traced", any(x.get("kind") == "qa-providers-failed" for x in tr))

# ---- the FAQ bank still answers with no model call ----
faq = b.get("faq") or []
if faq:
    r = c.post(f"/api/demos/{i}/run/qa", json={"question": faq[0]["question"], "history": []}).json()
    check("bank question answers from the bank", r.get("from_bank") is True and r.get("bank_id") == faq[0]["id"])
else:
    check("bank question answers from the bank", False, "no FAQ entries in the mock bundle")

# ---- Phase 2: parts carry boxes; hero selection; stills from a video-only upload ----
und = store.read_json(i, "understanding.json"); imgs_u = und.get("images", [])
parts = [p for im in imgs_u for p in im.get("parts", [])]
check("every tagged image lists parts as {name, box, confidence}", bool(parts) and all(isinstance(p, dict) and {"name", "box", "confidence"} <= set(p) for p in parts))
check("every part box is normalised 0-1 with positive size", all(0 <= p["box"]["x"] <= 1 and 0 <= p["box"]["y"] <= 1 and 0 < p["box"]["w"] <= 1 and 0 < p["box"]["h"] <= 1 for p in parts))
check("every part confidence is 0-1", all(0 <= p["confidence"] <= 1 for p in parts))
check("images carry full_product", all("full_product" in im for im in imgs_u))
check("bundle media images carry parts, full_product and role", all({"parts", "full_product", "role"} <= set(im) for im in b["media"]["images"]))
hero_im = next((im for im in imgs_u if im["source_id"] == hero_src), None)
check("the hero upload is bundle.hero_image", hero_im is not None and b.get("hero_image") == hero_im["id"])
check("media.hero is the hero image's url", b["media"]["hero"] == next((x["url"] for x in b["media"]["images"] if x["id"] == b.get("hero_image")), None))
r = c.post(f"/api/demos/{i}/sources", files=[("files", ("hero-2.webp", open("samples/iqube/angle.webp", "rb").read(), "image/webp"))], data={"role": "hero"}).json()
h2 = r["added"][0]["id"]; srcs = c.get(f"/api/demos/{i}").json()["demo"]["sources"]
check("a second hero upload replaces the first (old one becomes a product image)", next(s["role"] for s in srcs if s["id"] == hero_src) == "product" and next(s["role"] for s in srcs if s["id"] == h2) == "hero")

# video only, no hero: stills become images; the best full-product still becomes the hero
v = c.post("/api/demos", json={"name": "Deck QA video-only"}).json()["id"]
r = c.post(f"/api/demos/{v}/sources", files=[("files", ("walkaround.mp4", open("samples/iqube_dummy.mp4", "rb").read(), "video/mp4"))], data={"role": "product"}); assert r.status_code == 200, r.text
c.post(f"/api/demos/{v}/read"); wait(v, "align")
vd = c.get(f"/api/demos/{v}").json()["demo"]; vund = store.read_json(v, "understanding.json")
stills = [s for s in vd["sources"] if s["kind"] == "image" and s.get("derived_from")]
from server import media as _media
if _media.ffmpeg():
    check("video-only demo gets one still per good shot, tagged with its shot id", bool(stills) and all(s["derived_from"].startswith("sh") for s in stills))
    check("stills are tagged like uploaded images", bool(vund.get("images")) and all(im["source_id"] in {s["id"] for s in stills} for im in vund["images"]))
    from server.agents import bundle as _bundle
    vb = _bundle.build(v, lambda m: None)
    full = [im for im in vund["images"] if im.get("full_product")]
    check("without a hero upload, hero_image is the best full-product still", bool(vb.get("hero_image")) and (not full or vb["hero_image"] == max(full, key=lambda x: x["quality"])["id"]))
else:
    check("video-only demo gets stills", False, "ffmpeg unavailable on this machine")

# ---- Phase 3: the deck — one slide per segment, grounded callouts, positions never guessed ----
from server.agents import deck as _deck
dk = store.read_json(i, "deck.json") or {}
sc = store.read_json(i, "script.json") or {}
st_all = c.get(f"/api/demos/{i}").json()["demo"]["stages"]
segs_with_lines = [s for s in sc.get("segments", []) if any(not l.get("unverified") for l in s["lines"])]
check("deck.json written at Configure: one slide per segment + hero open, closing, hero close", bool(dk) and len(dk["slides"]) == len(segs_with_lines) + 3)
check("first and last slides are the hero", dk["slides"][0]["kind"] == "hero_open" and dk["slides"][-1]["kind"] == "hero_close" and dk["slides"][0]["image_id"] == dk["hero_image"] == b.get("hero_image"))
check("every content slide has a picture and lines", all(s["image_id"] and s["lines"] for s in dk["slides"][1:-1]))
check("deck stage done; author stayed done", st_all["deck"]["status"] == "done" and st_all["author"]["status"] == "done")
cos = [x for s in dk["slides"] for x in s["callouts"]]
check("callouts exist (mock: derived from each slide's cited facts)", bool(cos) and dk["method"].startswith("derived"))
check("≤ 3 callouts per slide, ≤ 8 words each, ≤ 6-word titles", all(len(s["callouts"]) <= 3 and len(s["title"].split()) <= 6 for s in dk["slides"]) and all(len(x["text"].split()) <= 8 for x in cos))
reg = {f["id"] for f in und["facts"]}
check("every callout cites only registry facts", all(x["fact_ids"] and set(x["fact_ids"]) <= reg for x in cos))
check("every callout has a placement; panel ones carry no position", all(x["placement"] in ("overlay", "panel") and (x["placement"] == "overlay" or (x["anchor"] is None and x["label_pos"] is None)) for x in cos))
check("bundle.slides present, every line's audio joined by id", bool(b.get("slides")) and all(l["audio"] for s in b["slides"] for l in s["lines"]))
check("bundle slides carry image urls and part boxes", all(s["image_url"] and isinstance(s["image_parts"], list) for s in b["slides"] if s["image_id"]))
check("bundle keeps segments for the pre-slide player (until Phase 5)", bool(b.get("segments")))

# label layout, tested on its own geometry
img = {"parts": [{"name": "headlamp", "box": {"x": 0.1, "y": 0.2, "w": 0.2, "h": 0.15}, "confidence": 0.9},
                 {"name": "wheel", "box": {"x": 0.6, "y": 0.6, "w": 0.25, "h": 0.25}, "confidence": 0.95},
                 {"name": "badge", "box": {"x": 0.45, "y": 0.45, "w": 0.05, "h": 0.05}, "confidence": 0.3}]}
sl = {"id": "t", "lines": [{"id": "l0", "text": "x", "fact_ids": ["F001"]}], "callouts": [
    {"id": "c1", "text": "LED headlamps see further", "fact_ids": ["F001"], "part": "headlamp", "reveal_on_line": 0},
    {"id": "c2", "text": "Alloy wheels, 17 inch", "fact_ids": ["F002"], "part": "wheel", "reveal_on_line": 0},
    {"id": "c3", "text": "Chrome badge", "fact_ids": ["F003"], "part": "badge", "reveal_on_line": 0},
    {"id": "c4", "text": "No part named", "fact_ids": ["F001"], "part": "", "reveal_on_line": 0}]}
_deck.place_callouts(sl, img); cc = {x["id"]: x for x in sl["callouts"]}
rect = lambda lp: {"x": lp["x"], "y": lp["y"], "w": _deck.LABEL_W, "h": _deck.LABEL_H}
check("layout: confident part → overlay, anchor at the box centre", cc["c1"]["placement"] == "overlay" and abs(cc["c1"]["anchor"]["x"] - 0.2) < 1e-6 and abs(cc["c1"]["anchor"]["y"] - 0.275) < 1e-6)
check("layout: label outside its part box", all(not _deck._overlaps(rect(cc[k]["label_pos"]), cc[k]["part_box"]) for k in ("c1", "c2")))
check("layout: label inside the frame", all(_deck._inside(rect(cc[k]["label_pos"])) for k in ("c1", "c2")))
check("layout: two overlay labels on one slide do not overlap", not _deck._overlaps(rect(cc["c1"]["label_pos"]), rect(cc["c2"]["label_pos"])))
check("layout: low-confidence part → panel, no position", cc["c3"]["placement"] == "panel" and cc["c3"]["label_pos"] is None and cc["c3"]["anchor"] is None)
check("layout: no part → panel, no position", cc["c4"]["placement"] == "panel" and cc["c4"]["label_pos"] is None)
raw = [{"text": "Two-year warranty in writing", "fact_ids": ["F001"], "part": "headlamp"},
       {"text": "Best in class mileage", "fact_ids": [], "part": ""},
       {"text": "Warranty for five years", "fact_ids": ["F999"], "part": ""},
       {"text": "one two three four five six seven eight nine", "fact_ids": ["F001"], "part": ""},
       {"text": "Points at nothing listed", "fact_ids": ["F001"], "part": "spoiler"}]
out = _deck.clean_callouts(raw, sl, {"F001"}, img)
check("callout validator: cited kept · uncited claim dropped · unknown-fact claim dropped · 9 words dropped", [x["text"] for x in out] == ["Two-year warranty in writing", "Points at nothing listed"])
check("callout validator clears a part the picture does not list", out[1]["part"] == "")
old_shape_img = {"parts": ["headlamp", "wheel"]}
check("older demos (parts as plain names) still derive callouts, in the panel", all(x["part"] == "" for x in _deck.derive_callouts({"id": "o", "lines": [{"id": "l", "text": "x", "fact_ids": ["F001"]}], "callouts": []}, {"F001": {"claim": "Headlamp", "value": "LED"}}, old_shape_img)))

# revise the deck alone: version bumps, author untouched; what the user fixed in Align wins
first = dk["slides"][1]
store.write_json(i, "deck-overrides.json", {"slides": [{"slide_id": first["id"], "title": "A title the user chose", "callouts": ([{"id": first["callouts"][0]["id"], "label_pos": {"x": 0.5, "y": 0.5}}] if first["callouts"] else [])}]})
r = c.post(f"/api/demos/{i}/revise", json={"stage": "deck", "instruction": "shorter titles"}); assert r.status_code == 200, r.text
wait(i, "ready")
dk2 = store.read_json(i, "deck.json"); st2 = c.get(f"/api/demos/{i}").json()["demo"]["stages"]
check("revise deck bumps the deck version without re-authoring", dk2["version"] == dk["version"] + 1 and st2["author"]["status"] == "done" and st2["deck"]["status"] == "done")
check("Align override: the user's title wins", dk2["slides"][1]["title"] == "A title the user chose")
if first["callouts"]:
    check("Align override: the dragged label position wins", dk2["slides"][1]["callouts"][0]["label_pos"] == {"x": 0.5, "y": 0.5})
store.path(i, "deck-overrides.json").unlink(missing_ok=True)
b = c.get(f"/api/demos/{i}/bundle").json()
check("the rebuilt bundle carries the override", b["slides"][1]["title"] == "A title the user chose")

# ---- Phase 4: slide review in Align — PATCH /align/deck through the same validator; overrides survive rebuilds ----
dk = store.read_json(i, "deck.json"); s1 = dk["slides"][1]; c1 = s1["callouts"][0] if s1["callouts"] else None
imgs_all = [im["id"] for im in und["images"]]; other_img = next((x for x in imgs_all if x != s1["image_id"]), None)
r = c.patch(f"/api/demos/{i}/align/deck", json={"slides": [{"slide_id": s1["id"], "title": "Chosen in review", "image_id": other_img, "callouts": ([{"id": c1["id"], "label_pos": {"x": 0.62, "y": 0.11}, "text": "Warranty in writing", "fact_ids": ["F001"]}] if c1 else [])}]})
check("PATCH /align/deck accepts title, picture and callout edits", r.status_code == 200, r.text[:120])
dk2 = store.read_json(i, "deck.json"); s2 = dk2["slides"][1]
check("the edit lands in deck.json (title, picture chosen in Align)", s2["title"] == "Chosen in review" and s2["image_id"] == other_img and s2["image_reason"] == "chosen in Align")
if c1:
    c2 = next(x for x in s2["callouts"] if x["id"] == c1["id"])
    check("callout text, facts and the dragged position land", c2["text"] == "Warranty in writing" and c2["fact_ids"] == ["F001"] and c2["label_pos"] == {"x": 0.62, "y": 0.11})
ov = store.read_json(i, "deck-overrides.json")
check("overrides are saved for the next rebuild", bool(ov) and ov["slides"][0]["slide_id"] == s1["id"] and ov["slides"][0]["title"] == "Chosen in review")
d3 = c.get(f"/api/demos/{i}").json()["demo"]
check("a slide edit un-approves the Script card and marks only the bundle stale", d3["approvals"]["script"] is False and d3["stages"]["bundle"]["status"] == "stale" and d3["stages"]["voice"]["status"] == "done" and d3["stages"]["deck"]["status"] == "done")
if c1:
    r = c.patch(f"/api/demos/{i}/align/deck", json={"slides": [{"slide_id": s1["id"], "callouts": [{"id": c1["id"], "text": "Best in class mileage", "fact_ids": []}]}]})
    check("an uncited claim in a callout is refused (400, names the fact-id rule)", r.status_code == 400 and "fact id" in r.json()["detail"])
    r = c.patch(f"/api/demos/{i}/align/deck", json={"slides": [{"slide_id": s1["id"], "callouts": [{"id": c1["id"], "text": "one two three four five six seven eight nine", "fact_ids": ["F001"]}]}]})
    check("a 9-word callout is refused", r.status_code == 400)
    r = c.patch(f"/api/demos/{i}/align/deck", json={"slides": [{"slide_id": s1["id"], "callouts": [{"id": c1["id"], "label_pos": {"x": 1.4, "y": 0.2}}]}]})
    check("a position outside the picture is refused", r.status_code == 400)
check("an unknown picture is refused", c.patch(f"/api/demos/{i}/align/deck", json={"slides": [{"slide_id": s1["id"], "image_id": "im99"}]}).status_code == 400)
check("an unknown slide is 404", c.patch(f"/api/demos/{i}/align/deck", json={"slides": [{"slide_id": "sl99", "title": "x"}]}).status_code == 404)
r = c.post(f"/api/demos/{i}/revise", json={"stage": "deck"}); assert r.status_code == 200, r.text
wait(i, "ready")
s3 = store.read_json(i, "deck.json")["slides"][1]
check("after a full deck rebuild the Align edits still win", s3["title"] == "Chosen in review" and s3["image_id"] == other_img)
b = c.get(f"/api/demos/{i}/bundle").json()
check("the rebuilt bundle shows the reviewed slide", b["slides"][1]["title"] == "Chosen in review" and b["slides"][1]["image_id"] == other_img)
cd = c.get(f"/api/demos/{i}").json()["cards"]["deck"]
check("cards.deck gives the editor its slides and pictures with parts", bool(cd["slides"]) and bool(cd["images"]) and all("parts" in im for im in cd["images"]) and all("image_url" in s for s in cd["slides"]))
store.path(i, "deck-overrides.json").unlink(missing_ok=True)

# ---- Phase 5: the player plays the deck — slides in order, event-driven sync, a true transcript ----
import re as _re
pj = c.get("/web/player/player.js").text; css = c.get("/web/styles.css").text; sj = c.get("/web/slide.js").text
kinds = [s["kind"] for s in b["slides"]]
check("bundle.slides is the player's structure: hero open → content → closing → hero close", kinds[0] == "hero_open" and kinds[-1] == "hero_close" and "closing" in kinds and kinds.index("closing") == len(kinds) - 2)
check("every content slide carries a picture, lines and callouts with placement and reveal line", all(s["image_url"] and s["lines"] and all(x["placement"] in ("overlay", "panel") and isinstance(x.get("reveal_on_line"), int) for x in s["callouts"]) for s in b["slides"] if s["kind"] not in ("hero_open", "hero_close")))
check("the player renders slides through web/slide.js; the segment stage and 3D/media card are gone", 'from "/web/slide.js"' in pj and "renderSlide(" in pj and "showVisual(" not in pj and "pl-media" not in pj and "pl-card" not in pj and "pl-media" not in css)
def _fn(src, name):
    i = src.find(f"function {name}("); j = src.find("\n  }\n", i); return src[i:j] if i >= 0 else ""
loop = _fn(pj, "playLines") + _fn(pj, "showSlideView") + _fn(pj, "playOpening")
check("sync is event-driven: no timer in the line loop or the slide switch (audio ended → next)", bool(loop) and "setTimeout" not in loop.replace("setTimeout(() => old.view.destroy()", "") and "setInterval" not in loop and "setRevealed(j)" in loop and "await speak(" in _fn(pj, "playLines"))
check("a line's callouts reveal when its audio starts (setRevealed before speak)", _fn(pj, "playLines").find("setRevealed(j)") < _fn(pj, "playLines").find("await speak("))
agent_logs = [m.start() for m in _re.finditer(r'addMsg\("agent"', pj)]
lh = pj.find("function logHeard("); lh_end = pj.find("\n  }\n", lh)
check("transcript: an agent line is logged only by logHeard — when its audio ends, never when it starts", bool(agent_logs) and all(lh < a < lh_end for a in agent_logs))
check("transcript: a cut-off line logs the heard prefix (elapsed/duration × words) and marks it interrupted", "interrupted: true" in pj and "currentTime / a.duration" in pj and "heard_fraction" in pj)
check("cancelSpeech logs the partial before stopping the audio", _fn(pj, "cancelSpeech").find("logHeard(S.speaking, false)") < _fn(pj, "cancelSpeech").find("S.audio.pause()"))
check("only the true transcript goes to /run/qa as history", "history: S.transcript.slice(-8)" in pj)
check("next slide is preloaded (picture + audio) while the current one plays", "function preloadAfter(" in pj and "preloadAfter(slide)" in _fn(pj, "showSlideView"))
check("motion is CSS-only and respects prefers-reduced-motion", "@keyframes slZoom" in css and "prefers-reduced-motion" in css and "animation:none!important" in css and "motion-" in sj)
check("the renderer fits the picture box to the stage (player) and is shared with Align", "opts.fit" in sj and 'from "/web/slide.js"' in c.get("/web/studio/align.js").text)
check("an older bundle without slides still plays (one slide per segment)", "function slidesOf(" in pj and "b.segments" in _fn(pj, "slidesOf"))
check("the session record carries slides visited and the route by slide id", "slides_visited" in pj and "slides: S.plan.map((st) => st.slide.id)" in pj)

# ---- Phase 6: questions route to slides — plain code on fact ids and topics, no model call ----
RS = [{"id": "r0", "kind": "hero_open", "lines": [], "callouts": []},
      {"id": "r1", "kind": "proof", "title": "Range that covers the week", "topics": ["range"], "fact_ids": ["F001"], "lines": [{"text": "x", "fact_ids": ["F001"]}], "callouts": [{"id": "r1-c1", "fact_ids": ["F001"]}]},
      {"id": "r2", "kind": "proof", "title": "Charging at home", "topics": ["charging"], "fact_ids": ["F002", "F003"], "lines": [{"text": "y", "fact_ids": ["F002"]}], "callouts": [{"id": "r2-c1", "fact_ids": ["F003"]}]},
      {"id": "r3", "kind": "hero_close", "lines": [], "callouts": []}]
rr = _deck.route_for(RS, "r1", ["F001"], "how far does it go")
check("route: the current slide carries an answer fact → stay, its matching callout named", rr["route"] == "stay" and rr["slide_id"] == "r1" and rr["callout_id"] == "r1-c1")
rr = _deck.route_for(RS, "r1", ["F003"], "charging time")
check("route: another slide carries the facts → jump to it with its callout", rr["route"] == "jump" and rr["slide_id"] == "r2" and rr["callout_id"] == "r2-c1")
rr = _deck.route_for(RS, "r1", [], "how long does charging take")
check("route: no facts, the question names another slide's topic → jump by topic", rr["route"] == "jump" and rr["slide_id"] == "r2" and rr["by"] == "topic")
rr = _deck.route_for(RS, "r1", [], "what colours are there")
check("route: nothing matches → none, the slide is unchanged", rr["route"] == "none" and rr["slide_id"] == "r1")
rr = _deck.route_for(RS, None, ["F002"], "")
check("route: no current slide (opening, custom batch) → jump to the slide that carries the facts", rr["route"] == "jump" and rr["slide_id"] == "r2")
check("route: hero slides are never a target", _deck.slide_for(RS, [], "hero")[0] is None)
fq = store.read_json(i, "faq.json") or {"entries": []}; dk = store.read_json(i, "deck.json"); sids = {s["id"] for s in dk["slides"]}
check("every FAQ bank entry carries a slide_id naming a deck slide (or None when nothing matches)", bool(fq["entries"]) and all("slide_id" in e and (e["slide_id"] is None or e["slide_id"] in sids) for e in fq["entries"]))
check("bundle FAQ entries carry the slide id", all("slide_id" in e for e in b["faq"]))
content = [s for s in dk["slides"] if s["kind"] not in ("hero_open", "hero_close") and s["fact_ids"]]
tgt, other = content[0], content[1]
import copy as _copy
dk_orig = _copy.deepcopy(dk)
tgt["fact_ids"] = tgt["fact_ids"] + ["FROUTE"]; tgt["callouts"][0]["fact_ids"] = tgt["callouts"][0]["fact_ids"] + ["FROUTE"]  # mock slides all cite F001: give one slide a fact only it carries
store.write_json(i, "deck.json", dk)
seed = {"id": "Q99", "question": "how many kilometres on one full charge", "origin": "test", "answer": "The registry answer.", "fact_ids": ["FROUTE"], "answered": True, "visual": None, "offer_callback": False, "clarifying_question": "", "audio": None, "slide_id": tgt["id"]}
store.write_json(i, "faq.json", {**fq, "entries": fq["entries"] + [seed]})
try:
    r = c.post(f"/api/demos/{i}/run/qa", json={"question": seed["question"], "slide_id": other["id"]}).json()
    check("/run/qa: an answered bank hit asked from another slide → route jump to the slide that carries its fact", r.get("from_bank") and r["route"] == "jump" and r["slide_id"] == tgt["id"])
    check("/run/qa: the jump names the callout that cites the fact (mock callouts come from cited facts)", r.get("callout_id") in {x["id"] for x in tgt["callouts"]})
    r = c.post(f"/api/demos/{i}/run/qa", json={"question": seed["question"], "slide_id": tgt["id"]}).json()
    check("/run/qa: the same question asked on that slide → route stay", r["route"] == "stay" and r["slide_id"] == tgt["id"])
    r = c.post(f"/api/demos/{i}/run/qa", json={"question": fq["entries"][0]["question"], "slide_id": other["id"]}).json()
    check("/run/qa: a declined bank answer never moves the slide (route none)", r["answered"] is False and r["route"] == "none" and r["slide_id"] == other["id"])
    r = c.post(f"/api/demos/{i}/run/qa", json={"question": "what colours are there", "slide_id": other["id"], "skip_bank": True}).json()
    check("/run/qa: the model path carries slide_id + route too (mock declines → none)", "route" in r and r["route"] == "none" and r["slide_id"] == other["id"])
finally:
    store.write_json(i, "faq.json", fq); store.write_json(i, "deck.json", dk_orig)
r = c.post(f"/api/demos/{i}/run/pitch", json={"profile": {"name": "Test", "why": "daily commute", "focus": []}, "refine": True})
check("/run/pitch: every route step names its slide (personalisation orders slides)", r.status_code == 200 and bool(r.json()["route"]) and all(st.get("slide_id") in sids for st in r.json()["route"]), r.text[:120])
pj = c.get("/web/player/player.js").text
check("player sends the current slide with every question", "slide_id: cur?.slide?.id" in pj)
check("player: jump cross-fades to the target, lights the callout, marks it covered; stay reveals this slide's callouts", 'r.route === "jump"' in pj and "S.covered.add(jumped.id)" in pj and "highlight(r.callout_id)" in pj and "cur?.view.setRevealed(99)" in pj)
check("player: after a jump the demo returns to the exact interrupted line (S.seg / S.line untouched, depth 1)", "wasAtCheckin ? 0 : S.line" in pj and "S.seg = " not in _fn(pj, "handleQuestion"))
check("player: a covered slide plays its title + first line, no check-in", "short ? 1 : sl.lines.length" in pj and "sl.checkin?.text && !short" in pj)
check("player: the pitch route is applied by slide id, segment id as fallback", "r.slide_id && lib.find" in pj)
check("player: a decline stays on the current slide (no transient answer slide)", "transientSlide(`ans-" not in pj)

# ---- runtime config ----
check("runtime provider order is configurable and defaults gemini first", config.RUNTIME_PROVIDERS[0] == "gemini" and "claude" in config.RUNTIME_PROVIDERS)
check("runtime timeout is short", 0 < config.RUNTIME_TIMEOUT <= 30)

print("| Case | OK |"); print("|---|---|")
for name, ok, detail in rows:
    print(f"| {name}{(' — ' + detail) if detail and not ok else ''} | {'✅' if ok else '❌'} |")
n_ok = sum(1 for _, ok, _ in rows if ok)
print(f"\n{n_ok}/{len(rows)} deck cases pass")
sys.exit(0 if n_ok == len(rows) else 1)
