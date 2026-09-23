"""Runtime pitch planner — after the standard intro, personalise the route through the
approved proof blocks for THIS buyer (P02/P03/P05/P07), with grounded one-line bridges."""
from __future__ import annotations

import json
import copy
import re

from .. import schemas, store
from ..llm import runtime
from .author import CLAIMISH, NUMBERISH
from .principles import CUSTOMER_STATES, PRINCIPLES, audience_instruction, fact_context, language_instruction


class PublishedDemoChanged(ValueError):
    """A live player must refresh before using a newer published composition."""

PITCH_SYSTEM = """You are {persona_name}, the voice guide in a live demo of {product_name}. An approved standard opening
will play after the opening film. Plan the personalised route that follows it for THIS buyer.

{principles}

{states}

{delivery_rules}

Your output:
- customer_state: from their one context answer and any later clarification reply. Their name alone is not a buying need.
  Only raw why/followup wording establishes stated needs or priorities. Computed focus is a routing hint, never evidence
  that the buyer stated or ranked a preference. Do not turn a matching topic into their "main" or "stated" priority.
- decision_frame: brief acknowledgement metadata that restates THIS buyer's need in their OWN words and the route order.
  Live Explore does not narrate it after the overview; keep it within twelve words. Warm, specific, zero product specs, no question. Copy any customer numbers
  exactly from CUSTOMER; never invent a distance, budget, location or household from a persona or an example. If they gave no signal, say honestly
  that you'll give the balanced tour and they can steer at any pause. Keep this framing positive: never promise a section
  about gaps, unknowns, or "what I can't tell you"; written terms and open questions belong in the establish block.
- follow_up_question: always empty. They already had one useful intake; do not ask for their name, repeat discovery,
  or add a budget question. Later clarification belongs to Q&A in response to their question.
- route: from the LIBRARY below — on the initial plan, put the first fundamental proof first; on refinements, do not
  reserve a fundamental stop. Order the remaining proof by the buyer's strongest signal (match rear-seat needs to rear-seat proof,
  front-seat needs to front-seat proof, and a performance
  want at the drive), then 1-2 supporting blocks, then the single features block, then establish last. Never more than 3 proof blocks: the whole demo must stay near three minutes; everything else
  is for questions. Each step may carry ONE bridge sentence. If a bridge states a product fact, copy one REVIEWED SPOKEN
  PROOF item's exact text and the complete fact_ids. Do not paraphrase, extend or combine that text. Without citations,
  copy only the exact NEUTRAL ROUTE CUES entry for that segment_id, or leave the bridge empty: no other uncited prose.
  Keep the buyer's own situation in decision_frame and the selected route, not in added bridge wording.
  Do not use a factual bridge whose wording already appears in MAIN ROUTE SPEECH for a selected segment.
  Bridges are statements, not questions.
  Never put intro/outcome segments in the route (they already played).
- skipped: segments left out, with the reason.
- personalized_segments: rewrite the selected segment's spoken composition for this buyer. Select the most relevant
  complete reviewed main/deeper sentences from THAT segment, put the answer to their need first, and omit unrelated
  detail. Copy each factual sentence exactly with its complete citations, visual and delivery metadata; do not invent
  a new causal benefit or alter conditions. Supply customer_quote as at most eight consecutive words copied verbatim
  from their why/followup; code uses this to create a short personal introduction. The resulting lines REPLACE the
  segment's default narration; never repeat them as custom_batches or a bridge. Keep total proof to 28 words when
  adding personal framing; no question (narration and closing statements never wait). For unknown context leave replacements empty.
- usp_order: which USPs get covered, in order (every route step's usps).
- custom_batches: legacy recorded delivery only; LIVE ROUTE DELIVERY must return an empty list. For legacy delivery,
  when the buyer said something specific, select 2-3 relevant items from REVIEWED SPOKEN PROOF, in the
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

SEGMENT SCRIPT (reviewed main/deeper lines, with immutable evidence and delivery):
{segment_script}

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
                proofs.append({"text": text, "fact_ids": list(dict.fromkeys(ids)), "delivery": copy.deepcopy(line.get("delivery") or {})})
                seen.add(key)
    return proofs


def _live_prompt_inputs(segments: list[dict], facts: list[dict]) -> tuple[list[dict], list[dict]]:
    """Send route choices and exact speech, not media or whole provenance tables.

    The server retains the complete published snapshot for validation and copies
    its immutable voice/visual metadata after choosing approved wording.
    """
    valid_ids = {fact["id"] for fact in facts}
    needed = set()
    compact = []
    for segment in segments:
        row = {key: segment[key] for key in ("id", "role", "title", "topic") if key in segment}
        for field in ("lines", "deeper"):
            row[field] = []
            for line in segment.get(field, []):
                ids = line.get("fact_ids") or []
                if line.get("unverified") or not ids or not set(ids) <= valid_ids:
                    continue
                row[field].append({"text": line.get("text", ""), "fact_ids": ids})
                needed.update(ids)
        compact.append(row)
    assertions = [{key: fact[key] for key in ("id", "kind", "claim", "value", "conditions", "scope", "truth") if key in fact}
                  for fact in facts if fact["id"] in needed]
    return compact, assertions


def plan_pitch(demo_id: str, profile: dict, refine: bool = False, *, voice_it: bool = True,
               timeout_budget_s: float | None = None, seen_segment_ids: list[str] | None = None,
               expected_snapshot_id: str | None = None, expected_demo_version: int | None = None) -> dict:
    published = None
    if not voice_it:
        published = store.read_json(demo_id, "bundle.json") or {}
        if not published.get("segments") or not published.get("knowledge_snapshot_id"):
            raise ValueError("A published demo is required before Explore can plan its route.")
        if ((expected_snapshot_id and published.get("knowledge_snapshot_id") != expected_snapshot_id)
                or (expected_demo_version is not None and published.get("version") != expected_demo_version)):
            raise PublishedDemoChanged("The published demo changed. Refresh to explore its new version; keep the current reviewed route for this visit.")
        # Align edits belong to the next publication. A live visit must never
        # combine draft facts, voice or script with its already-published player.
        alternate = (published.get("alt_languages") or {}).get(profile.get("language"), {})
        script = {"segments": copy.deepcopy(alternate.get("segments") or published["segments"])}
        und = {"product": published.get("product", {}), "facts": copy.deepcopy(published.get("facts", [])),
               "images": copy.deepcopy(published.get("media", {}).get("images", [])), "shots": []}
        plan = {**copy.deepcopy(published.get("pitch") or {}), "voice": copy.deepcopy(published.get("voice", {}).get("persona") or {}),
                "ctas": copy.deepcopy(published.get("ctas") or []), "segments": copy.deepcopy(script["segments"])}
        demo = {"settings": {"language": profile.get("language") or published.get("language", "en-IN"),
                              "audience": published.get("audience", "everyday")}, "approvals": {"script": True}}
        route_slides = alternate.get("slides") or published.get("slides", [])
    else:
        und = store.read_json(demo_id, "understanding.json") or {}
        plan = store.read_json(demo_id, "plan.json") or {}
        script = store.read_json(demo_id, "script.json") or {}
        demo = store.load(demo_id)
        route_slides = (store.read_json(demo_id, "deck.json") or {}).get("slides", [])
    voice = plan.get("voice", {})
    previously_seen = set(seen_segment_ids or [])
    # Only an explicit refinement may reconsider reviewed material already seen.
    # A Q&A slide visit is not evidence that the buyer's revised need is settled.
    allow_revisit = bool(refine and previously_seen)
    segs = [s for s in script.get("segments", []) if (allow_revisit or s.get("id") not in previously_seen) and s.get("role") in ("proof", "features", "establish") and any(not l.get("unverified") for l in s["lines"])]
    plan_by_id = {s["id"]: s for s in plan.get("segments", [])}
    fundamental_ids = [s["id"] for s in segs if s["role"] == "proof" and s["id"] not in previously_seen
                       and s.get("fundamental", plan_by_id.get(s["id"], {}).get("fundamental", False))]
    library = "\n".join(f"{s['id']} [{s['role']}] {s['title']} — fundamental: {bool(s.get('fundamental', plan_by_id.get(s['id'], {}).get('fundamental', False)))} — outcome: {s.get('outcome') or plan_by_id.get(s['id'], {}).get('outcome','')} — topic {s['topic']} — usps {s.get('usp_ids') or plan_by_id.get(s['id'], {}).get('usp_ids', [])} — facts {sorted({f for l in s['lines'] for f in l.get('fact_ids', [])})}" for s in segs) or "(no proof blocks)"
    facts = [f for f in und.get("facts", []) if f.get("approved", True)]
    facts_txt = "\n".join(fact_context(f) for f in facts) or "(empty)"
    prompt_segments = segs
    if not voice_it:
        prompt_segments, assertions = _live_prompt_inputs(segs, facts)
        facts_txt = json.dumps(assertions, ensure_ascii=False, separators=(",", ":"))
    script_approved = (demo.get("approvals") or {}).get("script") is True
    proofs = _reviewed_proofs({"segments": segs}, facts, approved=script_approved)
    proof_keys = {_proof_key(item["text"], item["fact_ids"]) for item in proofs}
    proof_delivery = {_proof_key(item["text"], item["fact_ids"]): item["delivery"] for item in proofs}
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
        proofs=json.dumps(proofs if voice_it else [], ensure_ascii=False), neutral_cues=json.dumps(neutral_cues if voice_it else {}, ensure_ascii=False),
        main_speech=json.dumps(main_speech if voice_it else {}, ensure_ascii=False),
        segment_script=json.dumps(prompt_segments, ensure_ascii=False, separators=(",", ":")),
        delivery_rules=("LIVE ROUTE DELIVERY: the short overview is already playing. Go directly into the selected slide route. "
                        "Return personalized_segments for every selected segment when customer why/followup is present; "
                        "choose complete exact reviewed main/deeper lines from each segment. Supply a short verbatim customer_quote "
                        "only for the first selected segment. No spoken decision_frame, custom_batches, or route bridges: "
                        "custom_batches must be []; bridge must be empty. Do not add a second opening or a separate explanation of the route. "
                        "Copy only text and fact_ids from SEGMENT SCRIPT into replacement lines; code restores the approved visual, "
                        "delivery and audio metadata. FACT REGISTRY contains only those reviewed lines' assertions; do not infer "
                        "anything from an omitted fact. Existing check-in text remains unchanged and never pauses playback."
                        if not voice_it else "LEGACY RECORDED DELIVERY: reviewed optional proof batches and route cues remain available."),
    )
    ask = "Plan the route now."
    if allow_revisit:
        ask += (" This is an explicit priority refinement. The latest raw followup takes precedence over earlier priorities. "
                "Choose the smallest useful route for that revised need. Previously viewed segments remain eligible because "
                "a question may have visited their slide without completing the relevant proof. Revisit only material that "
                "directly serves the revised need; do not repeat unrelated proof, features or ownership blocks to fill a quota. "
                "A rear-passenger request needs rear-passenger proof, not a generic front-cabin comfort substitute. "
                "Select exact reviewed sentences and preserve their conditions. Leave follow_up_question empty. "
                "Previously viewed segment IDs: " + json.dumps(sorted(previously_seen)))
    elif refine:
        ask += " This is a REFINE call: the follow-up has been answered — leave follow_up_question empty and finalise the route."
    try:
        # runtime providers in order, short timeout each: the plan must land while the standard opening plays
        budget = {"timeout_budget_s": timeout_budget_s} if timeout_budget_s is not None else {}
        out = runtime.structured(sys, ask, schemas.PitchPlan, max_tokens=3000, thinking_level="low", **budget)
    except Exception as e:
        raise RuntimeError(str(e)[:300]) from e
    p = out.model_dump()
    if published:
        p["knowledge_snapshot_id"], p["demo_version"] = published["knowledge_snapshot_id"], published.get("version")
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
    proof_route = [r for r in route if r["segment_id"] not in establish and r["segment_id"] not in features]
    default_features = [sid for sid in features if not allow_revisit or sid not in previously_seen]
    default_establish = [sid for sid in establish if not allow_revisit or sid not in previously_seen]
    feat = [r for r in route if r["segment_id"] in features][:1] or ([{"segment_id": default_features[0], "bridge": "", "bridge_fact_ids": []}] if default_features else [])
    est = [r for r in route if r["segment_id"] in establish][:1] or ([{"segment_id": default_establish[0], "bridge": "", "bridge_fact_ids": []}] if default_establish else [])
    if not proof_route:  # fallback: reviewed plan order, before the same initial-only hoist
        proof_route = [{"segment_id": s["id"], "bridge": "", "bridge_fact_ids": []} for s in segs if s["role"] == "proof" and s["id"] not in previously_seen]
    if not refine and fundamental_ids:
        # Reserve exactly one unseen fundamental, even when the model omitted it.
        # Preserve an existing validated bridge and the buyer-led order after it.
        first = fundamental_ids[0]
        lead = next((step for step in proof_route if step["segment_id"] == first),
                    {"segment_id": first, "bridge": "", "bridge_fact_ids": []})
        proof_route = [lead] + [step for step in proof_route if step["segment_id"] != first]
    proof_route = proof_route[:3]
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
    for b in (p.get("custom_batches") or [])[:3] if voice_it else []:
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
        b["delivery"] = copy.deepcopy(proof_delivery.get(_proof_key(txt, proposed_ids)) or {})
        batches.append(b)
    to_voice = [(b, "audio", b["text"]) for b in batches] + [(st, "bridge_audio", st["bridge"]) for st in route if st.get("bridge")]
    if p.get("decision_frame"):
        to_voice.append((p, "decision_frame_audio", p["decision_frame"]))
    if p.get("follow_up_question"):
        to_voice.append((p, "follow_up_audio", p["follow_up_question"]))
    if p.get("advance"):
        to_voice.append((p, "advance_audio", p["advance"]))
    if voice_it and to_voice and _voice.provider_for(demo) != "browser":
        import contextvars as _cv
        from concurrent.futures import ThreadPoolExecutor as _TPE
        with _TPE(max_workers=4) as pool:
            futs = {pool.submit(_cv.copy_context().run, _voice.render_line, demo_id, text, strict=True, delivery=obj.get("delivery") or None): (obj, key) for obj, key, text in to_voice}
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
    # Code-owned permission, derived only from validated selected published IDs.
    # Model-supplied metadata cannot authorize an unrelated or nonexistent revisit.
    p["revisit_segment_ids"] = [step["segment_id"] for step in route
                                 if allow_revisit and step["segment_id"] in previously_seen]
    # Stream delivery can start with validated text without waiting for an entire
    # TTS batch. Factual speech remains reviewed copy, with its citations/style.
    by_segment = {s["id"]: s for s in segs}
    p["script_segments"] = [copy.deepcopy(by_segment[step["segment_id"]]) for step in route]
    replacements = []
    route_ids = {step["segment_id"] for step in route}
    for proposed in p.get("personalized_segments", []) if has_context and script_approved else []:
        sid = proposed.get("segment_id")
        if sid not in route_ids or any(item["segment_id"] == sid for item in replacements):
            continue
        base = by_segment[sid]
        available = {_proof_key(line.get("text", ""), line.get("fact_ids", [])): line
                     for line in [*base.get("lines", []), *base.get("deeper", [])]
                     if not line.get("unverified") and line.get("fact_ids")
                     and all(fid in by_fact for fid in line.get("fact_ids", []))}
        chosen, keys = [], set()
        for line in proposed.get("lines", []):
            key = _proof_key(line.get("text", ""), line.get("fact_ids", []))
            source = available.get(key)
            if (not source or key in keys or re.search(r"[?？]", source.get("text", ""))
                    or _unsupported_addition(source["text"], [by_fact[fid] for fid in source["fact_ids"]])):
                chosen = []
                break
            # Fresh text has fresh audio ownership; do not attach a base clip to
            # the personalized preface or accept model-supplied media paths.
            chosen.append(copy.deepcopy(source))
            chosen[-1]["base_line_index"] = next((i for i, original in enumerate(base.get("lines", [])) if original.get("id") == source.get("id")), None)
            keys.add(key)
        if not chosen or sum(len(line["text"].split()) for line in chosen) > 38:
            continue
        quote = " ".join((proposed.get("customer_quote") or "").split())
        customer_words = [" ".join(str(profile.get(k) or "").split()) for k in ("why", "followup")]
        if voice_it and quote and len(quote.split()) <= 8 and any(quote.casefold() in value.casefold() for value in customer_words) and not re.search(r"[<>\[\]?？]", quote):
            preface = f'You mentioned “{quote}”. Let’s start there.'
            if len(preface.split()) + sum(len(line["text"].split()) for line in chosen) <= 38:
                chosen.insert(0, {"id": f"{sid}-personal", "text": preface, "fact_ids": [], "step": "frame",
                                  "visual": copy.deepcopy(chosen[0].get("visual") or {"kind": "none", "ref": ""}),
                                  "delivery": {"tone": "warm", "pace": 1.0}, "audio": None, "base_line_index": None})
        replacement = {**copy.deepcopy(base), "segment_id": sid, "lines": chosen, "personalized": True,
                       "personalization_basis": "model_reviewed_selection"}
        replacements.append(replacement)
    if not voice_it and has_context and script_approved:
        # A model can omit the optional replacement field or propose wording that
        # fails review. Keep its validated route, but never substitute an extra
        # monologue. Each fallback copies complete approved main lines and media.
        for step in route:
            sid = step["segment_id"]
            if any(item["segment_id"] == sid for item in replacements):
                continue
            base = by_segment[sid]
            chosen = []
            for index, line in enumerate(base.get("lines", [])):
                ids = line.get("fact_ids") or []
                if (line.get("unverified") or not ids or any(fid not in by_fact for fid in ids)
                        or re.search(r"[?？]", line.get("text", ""))
                        or _unsupported_addition(line.get("text", ""), [by_fact[fid] for fid in ids])):
                    continue
                chosen.append({**copy.deepcopy(line), "base_line_index": index})
            if chosen and sum(len(line.get("text", "").split()) for line in chosen) <= 38:
                replacements.append({**copy.deepcopy(base), "segment_id": sid, "lines": chosen,
                                     "personalized": True, "personalization_basis": "reviewed_route_fallback"})
        if route:
            first = next((item for item in replacements if item["segment_id"] == route[0]["segment_id"]), None)
            if first:
                # Context is quoted once, not regenerated as a factual benefit.
                words = " ".join(str(profile.get("why") or profile.get("followup") or "").split()).split()
                # Do not clip a longer utterance: its contrast or negation may
                # come later. A model can select a short verbatim subspan; the
                # deterministic fallback may quote only a complete short reply.
                quote = " ".join(words).rstrip(".,!;:") if len(words) <= 8 else ""
                proposed = next((item for item in p.get("personalized_segments", []) if item.get("segment_id") == first["segment_id"]), {})
                candidate = " ".join((proposed.get("customer_quote") or "").split())
                customer_words = [" ".join(str(profile.get(k) or "").split()) for k in ("why", "followup")]
                if candidate and len(candidate.split()) <= 8 and any(candidate.casefold() in value.casefold() for value in customer_words):
                    quote = candidate
                preface = f'You said, “{quote}”.'
                if quote and not re.search(r"[<>\[\]?？]", quote) and len(preface.split()) + sum(len(line["text"].split()) for line in first["lines"]) <= 38:
                    first["lines"].insert(0, {"id": f"{first['segment_id']}-personal", "text": preface,
                        "fact_ids": [], "step": "frame", "visual": copy.deepcopy(first["lines"][0].get("visual") or {"kind": "none", "ref": ""}),
                        "delivery": {"tone": "warm", "pace": 1.0}, "audio": None, "base_line_index": None})
                else:
                    first["context_preface_omitted"] = "unsafe_quote_or_segment_budget"
        replacements.sort(key=lambda item: next(i for i, step in enumerate(route) if step["segment_id"] == item["segment_id"]))
    if not voice_it:
        p["decision_frame_audio"] = None
        for step in route:
            step["bridge"], step["bridge_audio"] = "", None
        def client_audio(path):
            if not isinstance(path, str) or not path:
                return None
            if path.startswith(f"/media/{demo_id}/"):
                return path
            if path.startswith("audio/") and ".." not in path.split("/"):
                return f"/media/{demo_id}/{path}"
            return None
        def client_segment(segment):
            # Only copied reviewed media reaches this boundary; model media was
            # discarded above. Match the bundle's checkin/media shape so saved
            # clips play and the existing answer wait survives route replacement.
            for line in [*segment.get("lines", []), *segment.get("deeper", [])]:
                line["audio"] = client_audio(line.get("audio"))
            checkin = segment.get("checkin")
            segment["checkin"] = ({"text": checkin.get("text", ""), "audio": client_audio(checkin.get("audio"))}
                                  if isinstance(checkin, dict) else
                                  {"text": checkin or "", "audio": client_audio(segment.get("checkin_audio"))})
            return segment
        replacements = [client_segment(segment) for segment in replacements]
        p["script_segments"] = [client_segment(segment) for segment in p["script_segments"]]
    p["personalized_segments"] = replacements
    if replacements:
        # Replacements are the speech for their slides, not another pre-roll.
        p["custom_batches"] = []
        for step in route:
            if any(item["segment_id"] == step["segment_id"] for item in replacements):
                step["bridge"], step["bridge_audio"] = "", None
    ctas = {c["id"]: c for c in plan.get("ctas", [])}
    if p.get("advance_cta") not in ctas:
        prim = next((c for c in ctas.values() if c.get("primary")), next(iter(ctas.values()), None))
        p["advance_cta"] = prim["id"] if prim else ""
    # the route orders slides: each step names its slide (the player falls back to the segment id for a deck-less bundle)
    by_seg = {s["segment_id"]: s["id"] for s in route_slides if s.get("segment_id")}
    for st in p["route"]:
        st["slide_id"] = by_seg.get(st["segment_id"])
    store.log(demo_id, "pitch", {"state": p["customer_state"], "route": [r["segment_id"] for r in p["route"]], "profile": profile})
    return p
