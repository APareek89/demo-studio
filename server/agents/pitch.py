"""Runtime pitch planner — after the standard intro, personalise the route through the
approved proof blocks for THIS buyer (P02/P03/P05/P07), with grounded one-line bridges."""
from __future__ import annotations

import json
import re

from .. import schemas, store
from ..llm import runtime
from .author import CLAIMISH, NUMBERISH
from .principles import CUSTOMER_STATES, PRINCIPLES, audience_instruction, fact_context, language_instruction

PITCH_SYSTEM = """You are {persona_name}, the voice guide in a live demo of {product_name}. An approved standard opening
will play after the opening film. Plan the personalised route that follows it for THIS buyer.

{principles}

{states}

Your output:
- customer_state: from their one context answer and any later clarification reply. Their name alone is not a buying need.
  Only raw why/followup wording establishes stated needs or priorities. Computed focus is a routing hint, never evidence
  that the buyer stated or ranked a preference. Do not turn a matching topic into their "main" or "stated" priority.
- decision_frame: the ACKNOWLEDGEMENT, 1-2 spoken sentences that restate THIS buyer's need in their OWN words and promise
  the order. It plays right after the overview. Warm, specific, zero product specs, no question. Copy any customer numbers
  exactly from CUSTOMER; never invent a distance, budget, location or household from a persona or an example. If they gave no signal, say honestly
  that you'll give the balanced tour and they can steer at any pause. Keep this framing positive: never promise a section
  about gaps, unknowns, or "what I can't tell you"; written terms and open questions belong in the establish block.
- follow_up_question: always empty. They already had one useful intake; do not ask for their name, repeat discovery,
  or add a budget question. Later clarification belongs to Q&A in response to their question.
- route: from the LIBRARY below — the buyer's strongest signal FIRST (a comfort need starts at the cabin, a performance
  want at the drive), then 1-2 supporting blocks, then the single features block, then establish last. Never more than 3 proof blocks: the whole demo must stay near three minutes; everything else
  is for questions. Each step may carry ONE bridge sentence. If a bridge states a product fact, copy one REVIEWED SPOKEN
  PROOF item's exact text and the complete fact_ids. Do not paraphrase, extend or combine that text. Without citations,
  copy only the exact NEUTRAL ROUTE CUES entry for that segment_id, or leave the bridge empty: no other uncited prose.
  Keep the buyer's own situation in decision_frame and the selected route, not in added bridge wording.
  Do not use a factual bridge whose wording already appears in MAIN ROUTE SPEECH for a selected segment.
  Bridges are statements, not questions.
  Never put intro/outcome segments in the route (they already played).
- skipped: segments left out, with the reason.
- usp_order: which USPs get covered, in order (every route step's usps).
- custom_batches: when the buyer said something specific, select 2-3 relevant items from REVIEWED SPOKEN PROOF, in the
  order that best serves their stated need. Copy each item's exact text and the complete fact_ids; never add a prefix,
  suffix, location, property or benefit, and never splice items. Keep the need-led connection in decision_frame and the
  route selection; do not append arbitrary fragments of the buyer's words to factual proof. Each item is ≤38 words and
  already reviewed for speech. If no suitable item exists, omit the optional batch and retain the tailored route.
  Do not repeat wording already scheduled in MAIN ROUTE SPEECH for the selected route; an unused reviewed deeper item
  can add relevant detail, otherwise omit the optional batch.
  Choose the picture that literally shows that item (visual_ref). Never invent an operating consequence that the registry does
  not state. Preserve all material conditions: trim, powertrain, test/measurement basis and policy limitations. A policy
  headline is not a complete contract: when the relationship between limits is unknown, never supply "or" or "whichever
  comes first". Report the unknown relationship, or omit that batch and let the reviewed ownership segment explain it.
  Do not infer convenience, easier installation, secure attachment, fit, comfort or predictable ownership from equipment
  alone. A citation and "That suggests" are not evidence of a benefit; state only demonstrated outcomes, or propose a
  personal fit-check without promising its result. If conditions cannot fit, omit the optional batch rather than shorten
  away its scope. Never a spec list. Empty when the buyer gave
  nothing specific. A generic customer persona, PLAN DEFAULTS and prior script wording are not evidence of this buyer's life.
- advance: the closing advance for this buyer (P10), naming one CTA label; advance_cta = its id.
{audience}
{language}

CUSTOMER SAID: {profile}
COMPUTED ROUTING HINTS (not customer statements or ranked priorities): {focus}

LIBRARY (proof + establish segments):
{library}

NEUTRAL ROUTE CUES (code-owned wording, keyed by segment_id; copy the matching cue exactly or omit):
{neutral_cues}

MAIN ROUTE SPEECH (already plays for each selected segment; do not repeat it in optional proof):
{main_speech}

USPS: {usps}
CTAS: {ctas}
PLAN DEFAULTS: primary_outcome={primary}; supporting={supporting}; advance="{advance}"; do_not_recommend_if="{dnr}"

FACT REGISTRY:
{facts}

REVIEWED SPOKEN PROOF (the only permitted factual wording for custom_batches and cited bridges):
{proofs}"""


def _numbers(text: str) -> set[str]:
    """Compare digit and common spoken English quantities, including hyphenated ones.

    This is an absence check, not an entailment checker: equal numbers can still
    refer to different things, so prompts and human review remain necessary.
    """
    def canonical(number: str) -> str:
        number = number.replace(",", "")
        return number.rstrip("0").rstrip(".") if "." in number else number

    found = {canonical(number) for number in re.findall(r"\d+(?:[.,]\d+)*", text)}
    small = dict(zip("zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen".split(), range(20)))
    small.update(dict(zip("twenty thirty forty fifty sixty seventy eighty ninety".split(), range(20, 100, 10))))
    scales = {"hundred": 100, "thousand": 1000, "lakh": 100000, "crore": 10000000, "million": 1000000}
    token = "(?:" + "|".join([*small, *scales]) + ")"
    phrase = token + r"(?:(?:[\s-]+(?:and[\s-]+)?)" + token + r")*"

    def integer(part: str) -> int:
        total = current = 0
        for word in re.findall(r"[a-z]+", part):
            if word in small:
                current += small[word]
            elif word == "hundred":
                current = (current or 1) * 100
            elif word in scales:
                total += (current or 1) * scales[word]
                current = 0
        return total + current

    for match in re.finditer(r"\b" + phrase + r"(?:[\s-]+point[\s-]+" + phrase + r")?\b", text.lower()):
        parts = re.split(r"[\s-]+point[\s-]+", match.group(), maxsplit=1)
        number = str(integer(parts[0]))
        if len(parts) == 2:
            fraction = re.findall(r"[a-z]+", parts[1])
            # Spoken decimals normally read each digit: one point two five.
            decimal = "".join(str(small[word]) for word in fraction) if all(word in small and small[word] < 10 for word in fraction) else str(integer(parts[1]))
            number += "." + decimal
        found.add(canonical(number))
    return found


# Conservative, pitch-local omission guards for observed additions. These are
# lexical checks, not general semantic entailment; reviewed proof remains the fallback.
_BENEFIT = re.compile(r"\b(?:straightforward|easier|effortless|predictable|properly|securely|hassle[- ]free)\b", re.I)
_NEGATIVE = re.compile(r"\b(?:no|not|never|unknown|unstated|unspecified|unverified|unproven)\b|\b(?:doesn't|doesn’t|isn't|isn’t)\b", re.I)
_RELATION_TOPIC = re.compile(r"\b(?:relationship|which(?:ever)?[^.;]{0,35}(?:first|earlier)|(?:duration|time)[^.;]{0,35}(?:distance|usage)|limits?[^.;]{0,35}(?:appl|first|earlier))\b", re.I)
_RELATION_UNKNOWN = re.compile(r"\b(?:unknown|unstated|unspecified|undetermined)\b|\bnot\s+(?:provided|supplied|stated|specified|detailed|established|known|clear)\b|\b(?:does|do)\s+not\s+(?:state|specify|detail|explain|provide)\b", re.I)
_ASSERTED_RELATION = re.compile(r"\bwhichever\s+(?:(?:occurs|comes|happens|is|applies)\s+)?(?:first|earlier)\b|\b(?:years?|months?|days?|hours?)\b[^.!?;]{0,35}\bor\b[^.!?;]{0,45}\b(?:km|kilometres?|kilometers?|miles?|cycles?)\b|\b(?:km|kilometres?|kilometers?|miles?|cycles?)\b[^.!?;]{0,35}\bor\b[^.!?;]{0,45}\b(?:years?|months?|days?|hours?)\b", re.I)
_MEASUREMENT_BASIS = re.compile(r"\b(?:ISO|VDA|SAE|DIN)\s*[A-Z]?\s*\d+(?:[-:]\d+)*\b", re.I)


def _unsupported_addition(text: str, facts: list[dict]) -> bool:
    for fact in facts:
        source = fact.get("source") or {}
        conditions = fact.get("conditions") or ""
        if fact.get("kind") == "policy" or fact.get("truth") == "contractual":
            clauses = re.split(r"[.;\n]", conditions + ";" + str(source.get("quote") or ""))
            if any(_RELATION_TOPIC.search(c) and _RELATION_UNKNOWN.search(c) for c in clauses) and _ASSERTED_RELATION.search(text):
                return True
        # A quantity carrying an explicit standard cannot silently lose that basis.
        if _numbers(text) & _numbers(str(fact.get("value") or "")):
            normalized = re.sub(r"\s+", "", text).lower()
            measurement_context = conditions + ";" + str(source.get("quote") or "")
            if any(re.sub(r"\s+", "", basis).lower() not in normalized for basis in _MEASUREMENT_BASIS.findall(measurement_context)):
                return True
    benefits = _BENEFIT.findall(text)
    if benefits:
        evidence = ";".join(str(f.get(key) or "") for f in facts for key in ("claim", "value", "conditions"))
        evidence += ";" + ";".join(str((f.get("source") or {}).get("quote") or "") for f in facts)
        affirmative = " ".join(c for c in re.split(r"[.;\n]", evidence) if not _NEGATIVE.search(c)).lower()
        if any(not re.search(r"\b" + re.escape(word.lower()) + r"\b", affirmative) for word in benefits):
            return True
    return False


def _proof_key(text: str, fact_ids: list[str]) -> tuple[str, frozenset[str]]:
    # Only layout whitespace may vary; qualifiers, punctuation and wording stay.
    return " ".join(text.split()), frozenset(fact_ids)


def _neutral_route_cues(segments: list[dict], *, approved: bool) -> dict[str, str]:
    """Only code-owned transitions may speak without a reviewed factual proof.

    Titles come from the current human-approved script. A route cue names that
    section; it cannot be extended with generated properties or personal claims.
    """
    if not approved:
        return {}
    cues = {}
    for segment in segments:
        title = " ".join((segment.get("title") or "").split()).rstrip(".")
        if title and not re.search(r"[?？]", title):
            cues[segment["id"]] = f"Next: {title}."
    return cues


def _reviewed_proofs(script: dict, facts: list[dict], *, approved: bool) -> list[dict]:
    """Reuse human-approved speech, not fresh paraphrases licensed by a fact id.

    This closes generated elaboration, not erroneous human approval or stale
    fact identity. Unreviewed legacy scripts still supply the existing route,
    but cannot authorize optional new factual speech.
    """
    if not approved:
        return []
    by_id = {fact["id"]: fact for fact in facts}
    proofs, seen = [], set()
    for segment in script.get("segments", []):
        if segment.get("role") not in {"proof", "features", "establish"}:
            continue
        for line in [*segment.get("lines", []), *segment.get("deeper", [])]:
            text = (line.get("text") or "").strip()
            ids = line.get("fact_ids") or []
            if (line.get("unverified") or line.get("step") == "confirm" or not text
                    or len(text.split()) > 38 or re.search(r"[?？]", text)
                    or not ids or any(fid not in by_id for fid in ids)
                    or _unsupported_addition(text, [by_id[fid] for fid in ids])):
                continue
            key = _proof_key(text, ids)
            if key not in seen:
                proofs.append({"text": text, "fact_ids": list(dict.fromkeys(ids))})
                seen.add(key)
    return proofs


def plan_pitch(demo_id: str, profile: dict, refine: bool = False) -> dict:
    und = store.read_json(demo_id, "understanding.json") or {}
    plan = store.read_json(demo_id, "plan.json") or {}
    script = store.read_json(demo_id, "script.json") or {}
    demo = store.load(demo_id)
    voice = plan.get("voice", {})
    segs = [s for s in script.get("segments", []) if s.get("role") in ("proof", "features", "establish") and any(not l.get("unverified") for l in s["lines"])]
    plan_by_id = {s["id"]: s for s in plan.get("segments", [])}
    library = "\n".join(f"{s['id']} [{s['role']}] {s['title']} — outcome: {s.get('outcome') or plan_by_id.get(s['id'], {}).get('outcome','')} — topic {s['topic']} — usps {s.get('usp_ids') or plan_by_id.get(s['id'], {}).get('usp_ids', [])} — facts {sorted({f for l in s['lines'] for f in l.get('fact_ids', [])})}" for s in segs) or "(no proof blocks)"
    facts = [f for f in und.get("facts", []) if f.get("approved", True)]
    facts_txt = "\n".join(fact_context(f) for f in facts) or "(empty)"
    script_approved = (demo.get("approvals") or {}).get("script") is True
    proofs = _reviewed_proofs(script, facts, approved=script_approved)
    proof_keys = {_proof_key(item["text"], item["fact_ids"]) for item in proofs}
    neutral_cues = _neutral_route_cues(segs, approved=script_approved)
    main_speech = {s["id"]: [line["text"] for line in s["lines"] if line.get("text") and not line.get("unverified")]
                   for s in segs}
    sys = PITCH_SYSTEM.format(
        persona_name=voice.get("persona_name", "the guide"), product_name=und.get("product", {}).get("name", "the product"),
        principles=PRINCIPLES, states=CUSTOMER_STATES, audience=audience_instruction(demo.get("settings", {}).get("audience", "everyday")), language=language_instruction((profile or {}).get("language") or demo.get("settings", {}).get("language", "en-IN")),
        profile=json.dumps({key: value for key, value in profile.items() if key != "focus"}),
        focus=json.dumps(profile.get("focus") or []), library=library, usps=json.dumps(plan.get("usps", [])),
        ctas=json.dumps([{"id": c["id"], "label": c["label"], "kind": c["kind"]} for c in plan.get("ctas", [])]),
        primary=plan.get("primary_outcome", ""), supporting=plan.get("supporting_outcomes", []), advance=plan.get("advance", ""), dnr=plan.get("do_not_recommend_if", ""), facts=facts_txt,
        proofs=json.dumps(proofs, ensure_ascii=False), neutral_cues=json.dumps(neutral_cues, ensure_ascii=False),
        main_speech=json.dumps(main_speech, ensure_ascii=False),
    )
    ask = "Plan the route now." + (" This is a REFINE call: the follow-up has been answered — leave follow_up_question empty and finalise the route." if refine else "")
    try:
        # runtime providers in order, short timeout each: the plan must land while the standard opening plays
        out = runtime.structured(sys, ask, schemas.PitchPlan, max_tokens=3000, thinking_level="low")
    except Exception as e:
        raise RuntimeError(str(e)[:300]) from e
    p = out.model_dump()
    # The field remains readable in old bundles, but new route planning never
    # adds a second intake, even when a provider ignores the prompt.
    p["follow_up_question"] = ""
    has_context = any(profile.get(key) for key in ("why", "followup"))
    neutral_frame = "We'll take a balanced look, and you can steer us toward what matters to you."
    # Acknowledgements have no product specs; numeric detail can therefore only
    # repeat the customer's actual words. Reject an invented commute or budget.
    customer_text = json.dumps({key: profile.get(key) for key in ("why", "followup")}, ensure_ascii=False)
    customer_numbers = _numbers(customer_text)
    frame = p.get("decision_frame", "")
    if not has_context or _numbers(frame) - customer_numbers or re.search(r"[?？]", frame):
        p["decision_frame"] = neutral_frame
    if not has_context:
        p["customer_state"], p["custom_batches"], p["focus_topics"] = "unknown", [], []
    if re.search(r"\b(can't|cannot|can’t|don't know|do not know|honestly can't|honestly cannot)\b", p.get("decision_frame", ""), re.I):
        first = re.split(r"(?<=[.!?])\s+", p["decision_frame"].strip(), maxsplit=1)[0]
        p["decision_frame"] = first + " I'll start with what matters most, then cover the everyday fit, what's standard, and what's in writing."
    # ---- validate: segment ids exist; bridges obey no-citation-no-claim; establish last
    seg_ids = {s["id"] for s in segs}
    fact_ids = {f["id"] for f in facts}
    by_fact = {f["id"]: f for f in facts}
    product_numbers = _numbers(und.get("product", {}).get("name", ""))

    def invented_number(text: str, citations: list[str]) -> bool:
        # Existing citation checks still apply. A valid fact id does not license
        # an unrelated customer distance/budget absent from both actual inputs.
        supported = customer_numbers | product_numbers
        for fid in citations:
            f = by_fact[fid]
            supported |= _numbers(" ".join(str(f.get(key) or "") for key in ("claim", "value", "conditions")))
            # The exact measurement code can live only in the quoted footnote.
            supported |= _numbers(" ".join(_MEASUREMENT_BASIS.findall(str((f.get("source") or {}).get("quote") or ""))))
        return bool(_numbers(text) - supported)

    route, seen = [], set()
    for st in p["route"]:
        if st["segment_id"] not in seg_ids or st["segment_id"] in seen:
            continue
        seen.add(st["segment_id"])
        proposed_ids = st.get("bridge_fact_ids", [])
        st["bridge_fact_ids"] = [x for x in proposed_ids if x in fact_ids]
        b = (st.get("bridge") or "").strip()
        if proposed_ids:
            bridge_allowed = (_proof_key(b, proposed_ids) in proof_keys
                              and not invented_number(b, st["bridge_fact_ids"])
                              and not _unsupported_addition(b, [by_fact[fid] for fid in st["bridge_fact_ids"]]))
        else:
            # No lexical classifier can prove arbitrary uncited product prose
            # harmless. The only empty-citation alternative is this route's cue.
            bridge_allowed = " ".join(b.split()) == neutral_cues.get(st["segment_id"])
        if b and (not has_context or re.search(r"[?？]", b) or not bridge_allowed):
            st["bridge"] = ""  # no invented personal detail, ungrounded figure or hidden question
            st["bridge_dropped"] = b
        elif b and not proposed_ids:
            st["bridge"] = neutral_cues[st["segment_id"]]
        route.append(st)
    establish = [s["id"] for s in segs if s["role"] == "establish"]
    features = [s["id"] for s in segs if s["role"] == "features"]
    proof_route = [r for r in route if r["segment_id"] not in establish and r["segment_id"] not in features][:3]
    feat = [r for r in route if r["segment_id"] in features][:1] or ([{"segment_id": features[0], "bridge": "", "bridge_fact_ids": []}] if features else [])
    est = [r for r in route if r["segment_id"] in establish][:1] or ([{"segment_id": establish[0], "bridge": "", "bridge_fact_ids": []}] if establish else [])
    if not proof_route:  # fallback: plan order, first 3 proof blocks
        proof_route = [{"segment_id": s["id"], "bridge": "", "bridge_fact_ids": []} for s in segs if s["role"] == "proof"][:3]
    route = proof_route + feat + est
    scheduled_text = {" ".join(text.split()) for step in route for text in main_speech.get(step["segment_id"], [])}
    for step in route:
        if step.get("bridge") and " ".join(step["bridge"].split()) in scheduled_text:
            step["bridge_dropped"] = step["bridge"]
            step["bridge"] = ""
    # custom batches: grounded, pictured, voiced server-side (same voice as the demo — never the browser's)
    from . import visuals as _vis
    from . import voice as _voice
    vis_ids = {x["id"] for x in und.get("images", [])} | {x["id"] for x in und.get("shots", [])}
    batches = []
    for b in (p.get("custom_batches") or [])[:3]:
        proposed_ids = b.get("fact_ids", [])
        b["fact_ids"] = [x for x in proposed_ids if x in fact_ids]
        txt = (b.get("text") or "").strip()
        if (not txt or " ".join(txt.split()) in scheduled_text
                or len(txt.split()) > 38 or re.search(r"[?？]", txt) or invented_number(txt, b["fact_ids"])
                or _proof_key(txt, proposed_ids) not in proof_keys
                or _unsupported_addition(txt, [by_fact[fid] for fid in b["fact_ids"]])
                or (not b["fact_ids"] and (NUMBERISH.search(txt) or CLAIMISH.search(txt)))):
            continue
        if b.get("visual_ref") not in vis_ids:
            b["visual_ref"] = _vis.for_facts(und, b["fact_ids"]) or ""
        b["visual_ref"] = _vis.for_text_and_facts(demo_id, und, txt, b["fact_ids"], b.get("visual_ref") or "") or ""
        b["words"] = len(txt.split())
        batches.append(b)
    to_voice = [(b, "audio", b["text"]) for b in batches] + [(st, "bridge_audio", st["bridge"]) for st in route if st.get("bridge")]
    if p.get("decision_frame"):
        to_voice.append((p, "decision_frame_audio", p["decision_frame"]))
    if p.get("follow_up_question"):
        to_voice.append((p, "follow_up_audio", p["follow_up_question"]))
    if p.get("advance"):
        to_voice.append((p, "advance_audio", p["advance"]))
    if to_voice and _voice.provider_for(demo) != "browser":
        import contextvars as _cv
        from concurrent.futures import ThreadPoolExecutor as _TPE
        with _TPE(max_workers=4) as pool:
            futs = {pool.submit(_cv.copy_context().run, _voice.render_line, demo_id, text, strict=True): (obj, key) for obj, key, text in to_voice}
            for fut in futs:
                obj, key = futs[fut]
                try:
                    rel = fut.result()
                    obj[key] = f"/media/{demo_id}/{rel}" if rel else None
                except Exception:
                    obj[key] = None
    for b in batches:
        v = next((x for x in und.get("images", []) + und.get("shots", []) if x["id"] == b.get("visual_ref")), None)
        b["visual"] = {"kind": "image" if b.get("visual_ref", "").startswith("im") else "shot", "ref": b.get("visual_ref"), "source_id": v.get("source_id") if v else None, "start": v.get("start") if v else None, "end": v.get("end") if v else None, "description": v.get("description", "") if v else ""} if v else None
        b["visual"] = b["visual"] or {"kind": "none"}
    p["custom_batches"] = batches
    p["route"] = route
    ctas = {c["id"]: c for c in plan.get("ctas", [])}
    if p.get("advance_cta") not in ctas:
        prim = next((c for c in ctas.values() if c.get("primary")), next(iter(ctas.values()), None))
        p["advance_cta"] = prim["id"] if prim else ""
    # the route orders slides: each step names its slide (the player falls back to the segment id for a deck-less bundle)
    by_seg = {s["segment_id"]: s["id"] for s in (store.read_json(demo_id, "deck.json") or {}).get("slides", []) if s.get("segment_id")}
    for st in p["route"]:
        st["slide_id"] = by_seg.get(st["segment_id"])
    store.log(demo_id, "pitch", {"state": p["customer_state"], "route": [r["segment_id"] for r in p["route"]], "profile": profile})
    return p
