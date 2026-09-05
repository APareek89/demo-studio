"""Free deterministic checks for the spoken-line → visual-stage contract."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from server.agents import author, faq, qa, visuals
from server.llm import claude

results: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, ok, detail))


literal = {"ref": "im01"}
check("generic exterior overview keeps 3D", visuals.display_mode("This everyday SUV has more character in how it looks and drives.", literal) == "model")
check("airbag line requires exact evidence", visuals.display_mode("Six airbags are standard.", literal) == "evidence")
check("cabin line requires exact evidence", visuals.display_mode("Inside, the twin screens sit across the cabin.", literal) == "evidence")
check("gearbox line requires exact evidence", visuals.display_mode("Choose the manual or automatic transmission.", literal) == "evidence")
check("unseen detail becomes a card", visuals.display_mode("Six airbags are standard.", None) == "card")
check("written warranty becomes a card", visuals.display_mode("The written warranty is three years, terms applying.", literal) == "card")
check("mixed visible and written claims become a card", visuals.display_mode("Six airbags are standard, backed by a three-year warranty.", literal) == "card")
check("summary card takes over the stage", visuals.display_mode("The strongest fit is a daily SUV.", literal, "summary") == "card")

source_synced = []
for candidate in (ROOT / "data" / "demos").glob("dm_*/demo.json"):
    try:
        if "Source-Synced" in json.loads(candidate.read_text()).get("name", ""):
            source_synced.append(candidate.parent / "bundle.json")
    except Exception:
        pass
demo_bundle = max(source_synced, key=lambda p: p.stat().st_mtime) if source_synced else ROOT / "data" / "demos" / "dm_af65dad8" / "bundle.json"
if demo_bundle.exists():
    bundle = json.loads(demo_bundle.read_text())
    lines = [line for seg in bundle.get("segments", []) for line in [*(seg.get("lines") or []), *(seg.get("deeper") or [])]] + list(bundle.get("closing") or [])
    modes = [(line["id"], visuals.display_mode(line.get("text", ""), line.get("visual"), line.get("card", "none")), line) for line in lines]
    bad_model = [line_id for line_id, mode, line in modes if mode == "model" and (visuals.VISIBLE_DETAIL.search(line.get("text", "")) or visuals.ABSTRACT_EVIDENCE.search(line.get("text", "")))]
    missing_evidence = [line_id for line_id, mode, line in modes if mode == "evidence" and not (line.get("visual") or {}).get("url")]
    check("ready demo never uses 3D for a hidden/detail/source claim", not bad_model, ", ".join(bad_model))
    check("every evidence-mode line has an exact media URL", not missing_evidence, ", ".join(missing_evidence))
    check("ready demo exercises all three stage modes", {mode for _, mode, _ in modes} == {"model", "evidence", "card"}, str(sorted({mode for _, mode, _ in modes})))

player = (ROOT / "web" / "player" / "player.js").read_text()
align_ui = (ROOT / "web" / "studio" / "align.js").read_text()
align_source = (ROOT / "server" / "agents" / "align.py").read_text()
visuals_source = (ROOT / "server" / "agents" / "visuals.py").read_text()
pitch = (ROOT / "server" / "agents" / "pitch.py").read_text()
styles = (ROOT / "web" / "styles.css").read_text()
source_ui = (ROOT / "web" / "studio" / "sources.js").read_text()
rehearse_ui = (ROOT / "web" / "studio" / "rehearse.js").read_text()
graph_source = (ROOT / "server" / "graph.py").read_text()
check("player never rotates repeated evidence to another image", "nextImageUrl" not in player)
check("player has mutually exclusive evidence and card stages", "evidence-on" in player and "card-on" in player and ".pl-card.dominant" in styles)
check("missing literal evidence uses a card over the 3D placeholder", 'mode = "card"' in player and "mode = showVisual" in player and 'mode === "card" && !asset' in player)
check("personalised roadmap gets its own card before speech", 'present(null, plan.decision_frame, "statement")' in player)
check("typed intake replies queue instead of triggering Q&A", "pendingIntakeAnswer" in player and "if (S.intakeOpen)" in player)
check("multi-claim runtime proof uses a cited card", 'len(set(b.get("fact_ids") or [])) > 1' in pitch and '"card"' in pitch)
check("runtime bridges carry their own citations and stage decision", "bridge_fact_ids" in player and 'display_mode: ""' in player)
check("typed confirmations resolve the active wait instead of starting Q&A", "if (S.waiter)" in player and "S.waitChips" in player)
check("runtime asks only one intake question", "const q2 = bundle.intake?.q2" not in player and "refine: true" in player)
check("unknown answers show the model and open lead capture without a source card", 'showLeadPrompt("unknown"' in player and 'showCard("none")' in player)
check("runtime fact cards are keyword-sized and omit source locators", "function compactRow" in player and 'title = "Key points"' in player and 'title = "Sources for that answer"' not in player)
check("post-script audit inspects real images with Gemini", "_vision_batches" in visuals_source and "gemini.structured" in visuals_source and 'store.write_json(demo_id, "visual-audit.json"' in visuals_source)
check("alignment preview exposes feature coverage and gaps", "Gemini confirms:" in align_ui and '"visual check"' in align_ui and "missing_features" in align_ui)
check("Align times narration separately from its pause-point question", "sg.spoken ?? sg.duration" in align_ui and "s spoken" in align_ui)
check("a skipped pixel audit is never labelled full visual coverage", "Pixel audit unavailable" in align_ui and "Human visual approval is still required" in align_ui)
check("Align card data carries the narration-only duration", '"spoken": s.get("spoken")' in align_source)
check("lead capture triggers at two questions or sixty percent", "S.questions.length >= 2 || progress >= 0.6" in player)
check("temporary mute covers narration, browser voice and the opening film", 'a.muted = S.muted' in player and 'u.volume = S.muted ? 0 : 1' in player and 'v.muted = S.muted' in player)
check("mute control is keyboard and screen-reader accessible", 'aria-label": "Mute audio"' in player and 'aria-pressed' in player and 'onclick: () => toggleMute()' in player)
check("catalogue copy documents every accepted tabular format", "PDF, DOCX, TXT, MD, CSV." in source_ui and 'accept: ".pdf,.docx,.txt,.md,.csv"' in source_ui)
check("build guidance consistently names all six Align cards", "Approve all five cards" not in graph_source and "approve the five cards" not in rehearse_ui and "Approve all six cards" in graph_source and "approve the six cards" in rehearse_ui)
check("FAQ parser reads an inline numbered question and answer", faq.question_from_line("1. **What is the current price?** Ask the dealer.") == "What is the current price?")
check("FAQ parser still reads a question-only line", faq.question_from_line("Q: Which warranty applies?") == "Which warranty applies?")
check("FAQ retries checkpoint progress against a registry hash", '"registry_hash": registry_hash' in (ROOT / "server" / "agents" / "faq.py").read_text() and '"partial": len(entries) < len(questions)' in (ROOT / "server" / "agents" / "faq.py").read_text())
check("provider fallback recognizes exhausted primary credit", claude._provider_unavailable(RuntimeError("Your credit balance is too low")))
check("provider fallback rejects unrelated validation errors", not claude._provider_unavailable(RuntimeError("JSON failed validation")))
understand_source = (ROOT / "server" / "agents" / "understand.py").read_text()
check("PDF registry extraction has a text-only secondary-provider path", "Primary document reader unavailable" in understand_source and "gemini.text_structured(FACTS_SYSTEM" in understand_source)
check("competitor pages stay out of the product fact-registry prompt", 's.get("role") != "competitor"' in understand_source)
check("a human-verified fact manifest is the no-guess dual-provider fallback", "def _verified_manifest" in understand_source and "using the explicit verified-fact manifest" in understand_source)
check("reviewed plan and script bundles are available only as provider-outage fallbacks", "def _verified_plan" in (ROOT / "server" / "agents" / "plan.py").read_text() and "def _verified_script" in (ROOT / "server" / "agents" / "author.py").read_text())
check("reviewed control bundles stay out of fact extraction", "verified-plan.json.md" in understand_source and "control_sources" in understand_source)
gemini_source = (ROOT / "server" / "llm" / "gemini.py").read_text()
check("hard Gemini quota exhaustion enters a cooldown instead of retrying every later stage", "def _is_hard_quota" in gemini_source and "_hard_quota_until" in gemini_source)
check("FAQ retry clears a stale error status before doing work", 'def faq(state: DemoState)' in graph_source and 'orch._set_status(d, "building" if state.get("entry") == "build"' in graph_source)
check("an explicit FAQ retry reruns even after a completed-but-bad bank", 'and not explicit_retry' in graph_source and 'state.get("instruction", "") if explicit_retry else ""' in graph_source)
check("an instructed FAQ retry bypasses same-registry cached answers", "if not force and previous.get" in (ROOT / "server" / "agents" / "faq.py").read_text() and "force=bool(instruction)" in (ROOT / "server" / "orchestrator.py").read_text())
check("FAQ can be retried without re-running source analysis", '"understand", "plan", "author", "faq"' in (ROOT / "server" / "app.py").read_text())
check("questionable facts have a direct reject and restore control", "setFactApproval" in align_ui and "/approval`" in align_ui and "Fact {fact_id} {'restored' if approved else 'rejected'} directly" in (ROOT / "server" / "app.py").read_text())
check("local QA fallback declines unsupported crash ratings", not qa._local_grounded_answer("What is the current crash rating?", {"facts": []}, {"ctas": []}).answered)
check("hyphenated crash-test rating cannot collide with test drive", not qa._local_grounded_answer("Does it have a current crash-test rating?", {"facts": [{"id": "F1", "approved": True, "claim": "Test drive availability", "value": "Available at your nearest dealership"}]}, {"ctas": []}).answered)
comparison = qa._local_grounded_answer("How does its starting price compare with the Hyundai Creta?", {"product": {"name": "Taigun"}, "facts": [
    {"id": "F1", "approved": True, "claim": "Starting price", "value": "₹10.99 lakh"},
    {"id": "F2", "approved": True, "claim": "Comparison — Hyundai CRETA starting price", "value": "₹10,90,700", "conditions": "reviewed 2026-09-05"},
    {"id": "F3", "approved": True, "claim": "Comparison response rule", "value": "Verify live prices"},
]}, {"ctas": []})
check("local competitor price answer compares both products and carries the verification rule", comparison.answered and comparison.fact_ids == ["F1", "F2", "F3"] and "Taigun" in comparison.answer and "Hyundai CRETA" in comparison.answer and "dealer verification" in comparison.answer)
generic_comparison = qa._local_grounded_answer("Is it cheaper than the X3?", {"product": {"name": "Q5"}, "facts": [
    {"id": "F1", "approved": True, "claim": "Starting price", "value": "₹70 lakh"},
    {"id": "F2", "approved": True, "claim": "Comparison — BMW X3 starting price", "value": "₹75 lakh"},
]}, {"ctas": []})
check("local competitor matching comes from the uploaded registry rather than a Taigun-only list", generic_comparison.answered and generic_comparison.fact_ids == ["F1", "F2"] and "BMW X3" in generic_comparison.answer)
structured_comparison = qa._local_grounded_answer("How does it start against MG Hector?", {"product": {"name": "Harrier"}, "facts": [
    {"id": "F1", "approved": True, "claim": "Starting price", "value": "₹12.99 lakh"},
], "competitors": [{"name": "MG Hector", "facts": [
    {"id": "C1-001", "approved": True, "claim": "Starting price", "value": "₹11.99 lakh"},
]}]}, {"ctas": []})
check("local comparison fallback also reads the structured competitor registry", structured_comparison.answered and structured_comparison.fact_ids == ["F1", "C1-001"] and "MG Hector" in structured_comparison.answer)
harrier_local = {"product": {"name": "Tata Harrier"}, "facts": [
    {"id": "F1", "approved": True, "claim": "Seating capacity", "value": "5 seater"},
    {"id": "F2", "approved": True, "claim": "Powered driver seat", "value": "6-way powered"},
    {"id": "F3", "approved": True, "claim": "Manual transmission", "value": "6-speed manual — all combinations"},
    {"id": "F4", "approved": True, "claim": "Automatic transmission", "value": "6-speed automatic — Pure X onwards"},
    {"id": "F5", "approved": True, "claim": "Official Flexi-scheme starting EMI", "value": "₹12,199", "conditions": "final EMI is at the financier's discretion"},
    {"id": "F6", "approved": True, "claim": "Comparison — Mahindra XUV 7XO seating", "value": "7-seat entry range; selected higher variants offer 6-seat layouts"},
    {"id": "F7", "approved": True, "claim": "Comparison response rule", "value": "verify current trims"},
    {"id": "F8", "approved": True, "claim": "Powered tailgate", "value": "Gesture-controlled powered tailgate"},
    {"id": "F9", "approved": True, "claim": "Variant count", "value": "55 variants available"},
    {"id": "F10", "approved": True, "claim": "Vehicle warranty", "value": "3 years or 1 lakh km"},
    {"id": "F11", "approved": True, "claim": "Global NCAP applicability", "value": "Applies across diesel variants, excluding Fearless Ultra and above"},
]}
seat_answer = qa._local_grounded_answer("How many people does the Harrier seat?", harrier_local, {"ctas": []})
check("local fallback distinguishes seating capacity from powered-seat features", seat_answer.fact_ids == ["F1"])
transmission_answer = qa._local_grounded_answer("Which transmissions are available with diesel?", harrier_local, {"ctas": []})
check("local fallback answers fuel transmission questions from transmission facts", transmission_answer.fact_ids == ["F3", "F4"])
emi_answer = qa._local_grounded_answer("Can you guarantee the EMI shown?", harrier_local, {"ctas": []})
check("local fallback answers an EMI guarantee question with the lender caveat", emi_answer.fact_ids == ["F5"] and emi_answer.answer.startswith("No."))
real_mileage = qa._local_grounded_answer("What real-world diesel mileage will I definitely get?", harrier_local, {"ctas": []})
check("local fallback declines guaranteed real-world mileage", not real_mileage.answered and not real_mileage.fact_ids)
xuv_answer = qa._local_grounded_answer("How does its seating differ from the XUV 7XO?", harrier_local, {"ctas": []})
check("local fallback compares seating when a non-price rival is named", xuv_answer.fact_ids == ["F1", "F6", "F7"])
check("local fallback declines universal feature scope without variant-level evidence", not qa._local_grounded_answer("Is the powered tailgate standard on every variant?", harrier_local, {"ctas": []}).answered)
check("local fallback still answers a plain powered-tailgate availability question", qa._local_grounded_answer("Does it have a powered tailgate?", harrier_local, {"ctas": []}).fact_ids == ["F8"])
check("local fallback declines a cheapest-variant question when only a variant count exists", not qa._local_grounded_answer("Which is the cheapest Harrier variant?", harrier_local, {"ctas": []}).answered)
check("local fallback still answers the reviewed variant count", qa._local_grounded_answer("How many variants are currently listed?", harrier_local, {"ctas": []}).fact_ids == ["F9"])
check("strict intent narrowing still recognizes a vehicle-warranty fact", qa._local_grounded_answer("What warranty does the Harrier include?", harrier_local, {"ctas": []}).fact_ids == ["F10"])
global_scope = qa._local_grounded_answer("Does the Global NCAP result apply to every Harrier variant sold today?", harrier_local, {"ctas": []})
check("Global NCAP scope beats a generic variant-count intent and states the exclusion", global_scope.fact_ids == ["F11"] and "not every current variant" in global_scope.answer)
finance = qa._local_grounded_answer("Show me synthetic EMI illustration A", {"facts": [
    {"id": "F1", "approved": True, "claim": "SYNTHETIC EMI illustration A", "value": "₹21,139", "conditions": "Not a finance offer"},
    {"id": "F2", "approved": True, "claim": "SYNTHETIC EMI illustration B", "value": "₹26,469", "conditions": "Not a finance offer"},
]}, {"ctas": []})
check("a named synthetic finance illustration returns only that scenario with its caveat", finance.answered and finance.fact_ids == ["F1"] and "₹21,139" in finance.answer and "₹26,469" not in finance.answer and "Not a finance offer" in finance.answer)
check("local QA fallback never substitutes ex-showroom for city on-road price", not qa._local_grounded_answer("What will the on-road price be in my city?", {"facts": [{"id": "F1", "approved": True, "claim": "Starting price", "value": "10 lakh", "conditions": "ex-showroom"}]}, {"ctas": []}).answered)
rejected_script = {"segments": [{"id": "s", "role": "intro", "lines": [{"id": "l", "text": "Six airbags.", "fact_ids": ["F1"], "visual": {"kind": "none", "ref": ""}}]}], "closing": []}
author.validate(rejected_script, {"facts": [{"id": "F1", "approved": False}], "shots": [], "images": []})
check("rejected facts are stripped from script citations", rejected_script["segments"][0]["lines"][0]["fact_ids"] == [] and rejected_script["segments"][0]["lines"][0]["unverified"])
check("direct script editor can repair both wording and citations", "Approved fact ids" in align_ui and '"fact_ids" in edit' in (ROOT / "server" / "app.py").read_text())
check("direct script editor can clear a misleading visual binding", "Visual ref (blank keeps unsupported details on a fact card)" in align_ui and '"visual_ref" in edit' in (ROOT / "server" / "app.py").read_text())
check("minor direct wording edits can keep an already-reviewed visual map", 'body.get("realign_visuals", True)' in (ROOT / "server" / "app.py").read_text())
check("direct pitch editor avoids a second model call", "Edit pitch brief" in align_ui and '/align/plan`' in align_ui and "async def edit_aligned_plan" in (ROOT / "server" / "app.py").read_text())
app_py = (ROOT / "server" / "app.py").read_text()
check("validated direct edits preserve completed model stages", all(marker in app_py for marker in (
    'set_stage(demo_id, "understand", "done", message="direct fact edit saved and validated")',
    'set_stage(demo_id, "understand", "done", message="fact approval reviewed directly")',
    'set_stage(demo_id, "understand", "done", message="product framing edited directly")',
    'set_stage(demo_id, "author", "done", message="direct script edits saved and validated")',
    'set_stage(demo_id, "plan", "done", message="direct pitch edits saved and validated")',
)))
check("extracted product framing has a direct correction path", "Edit product summary" in align_ui and "async def edit_aligned_product" in (ROOT / "server" / "app.py").read_text())
check("QA provider outage uses a cooldown instead of retrying per question", "_qa_reasoning_unavailable_until" in (ROOT / "server" / "agents" / "qa.py").read_text())
check("local QA fallback records required trace latency", 'latency_ms=(time.monotonic() - started) * 1000' in (ROOT / "server" / "agents" / "qa.py").read_text())
check("runtime image map excludes non-visual capacities and hidden safety claims", "NON_VISUAL_FACT.search(cue)" in visuals_source)
check("direct script correction refreshes the safe runtime image map", 'und["image_map"] = visuals.build_map(und, demo)' in (ROOT / "server" / "app.py").read_text())
check("voice sample re-record updates the reviewed persona artifact", 'plan["voice_sample_audio"] = rel' in (ROOT / "server" / "app.py").read_text() and "voice_agent.voice_name_for" in (ROOT / "server" / "agents" / "align.py").read_text())
check("a build cannot report ready with a partially voiced FAQ bank", "Voice bank incomplete" in (ROOT / "server" / "agents" / "voice.py").read_text() and "partial audio was checkpointed" in (ROOT / "server" / "agents" / "voice.py").read_text())
styles = (ROOT / "web" / "styles.css").read_text()
check("mobile studio and player tracks can shrink to the viewport", "grid-template-columns:minmax(0,1fr);min-width:0" in styles and ".player-host{min-width:0}" in styles)
check("mobile player controls wrap instead of forcing horizontal scroll", ".pl-top .left,.pl-top .right{width:100%;max-width:100%}" in styles and ".pl{overflow:hidden;grid-template-rows:88px" in styles)
check("the closed desktop conversation drawer cannot widen the document", ".player-host{position:relative;min-height:0;display:flex;flex-direction:column;overflow:hidden}" in styles and ".pl{flex:1;display:grid;grid-template-rows:52px 1fr;min-height:0;background:var(--bg);overflow:hidden}" in styles)

failed = [item for item in results if not item[1]]
for name, ok, detail in results:
    print(("✅" if ok else "❌"), name, ("— " + detail) if detail else "")
print(f"\n{len(results) - len(failed)}/{len(results)} visual-sync cases passed")
if failed:
    raise SystemExit(1)
