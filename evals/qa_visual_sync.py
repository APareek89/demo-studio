"""Free deterministic checks for the spoken-line → visual-stage contract."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from server.agents import visuals

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
visuals_source = (ROOT / "server" / "agents" / "visuals.py").read_text()
pitch = (ROOT / "server" / "agents" / "pitch.py").read_text()
styles = (ROOT / "web" / "styles.css").read_text()
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
check("lead capture triggers at two questions or sixty percent", "S.questions.length >= 2 || progress >= 0.6" in player)
check("temporary mute covers narration, browser voice and the opening film", 'a.muted = S.muted' in player and 'u.volume = S.muted ? 0 : 1' in player and 'v.muted = S.muted' in player)
check("mute control is keyboard and screen-reader accessible", 'aria-label": "Mute audio"' in player and 'aria-pressed' in player and 'onclick: () => toggleMute()' in player)

failed = [item for item in results if not item[1]]
for name, ok, detail in results:
    print(("✅" if ok else "❌"), name, ("— " + detail) if detail else "")
print(f"\n{len(results) - len(failed)}/{len(results)} visual-sync cases passed")
if failed:
    raise SystemExit(1)
