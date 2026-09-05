"""One-time, reproducible repair for the approved Creta source-synced demo.

Splits overloaded narration by visible subject, removes decorative visual assignments where
the sources only support a fact card, records only changed lines, and rebuilds the bundle.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from server import runlog, store
from server.agents import author, bundle, voice


def visual(ref: str | None, focus: str) -> dict | None:
    return {"kind": "image", "ref": ref, "focus": focus} if ref else None


def fresh(old: dict, *, line_id: str, text: str, fact_ids: list[str], ref: str | None, focus: str,
          step: str | None = None, card: str = "none") -> dict:
    return {
        "text": text, "step": step or old.get("step", "show"), "visual": visual(ref, focus),
        "fact_ids": fact_ids, "card": card, "unverified": False, "id": line_id,
    }


def main(demo_id: str) -> None:
    demo = store.load(demo_id)
    if "CRETA N Line" not in demo.get("product", {}).get("name", ""):
        raise SystemExit("This repair is scoped to the approved CRETA N Line demo")
    script = store.read_json(demo_id, "script.json")
    und = store.read_json(demo_id, "understanding.json")
    by_seg = {seg["id"]: seg for seg in script["segments"]}
    existing = {line["id"]: line for seg in script["segments"] for line in [*(seg.get("lines") or []), *(seg.get("deeper") or [])]}
    changed: list[dict] = []

    def record(line: dict) -> dict:
        old = existing.get(line["id"], {})
        if old.get("text") == line["text"] and old.get("audio"):
            line["audio"] = old["audio"]
        else:
            line["audio"] = voice.render_line(demo_id, line["text"], demo=demo, strict=True)
            changed.append({"id": line["id"], "text": line["text"], "visual": (line.get("visual") or {}).get("ref"), "audio": line["audio"]})
        return line

    q2 = "And what's the one thing I should make sure you see — comfort, performance, safety, or something else?"
    if script.get("intake_q2") != q2:
        script["intake_q2"] = q2
        script.setdefault("intake_audio", {})["q2"] = voice.render_line(demo_id, q2, demo=demo, strict=True)
        changed.append({"id": "intake-q2", "text": q2, "visual": None, "audio": script["intake_audio"]["q2"]})

    promise = by_seg["the-promise"]
    p_old = promise["lines"][1]
    promise["lines"][1:] = [
        record(fresh(p_old, line_id="the-promise-L2", text="Inside, the twin ten-point-two-five-inch screens sit together across the dashboard.", fact_ids=["F033", "F034"], ref="im13", focus="Twin 10.25-inch screens")),
        record(fresh(p_old, line_id="the-promise-L3", text="And six airbags are standard.", fact_ids=["F027"], ref="im01", focus="Six airbags standard")),
    ]

    outcome = by_seg["three-things"]
    o_old = outcome["lines"][0]
    outcome["lines"] = [
        record(fresh(o_old, line_id="three-things-L1", text="Three things I'd note — a cabin with ventilated seats and dual-zone climate.", fact_ids=["F043", "F042"], ref="im03", focus="Ventilated seats, dual zone")),
        record(fresh(o_old, line_id="three-things-L2", text="The turbo's headline is nought to hundred in eight point nine seconds.", fact_ids=["F004"], ref=None, focus="", card="none")),
        record(fresh(o_old, line_id="three-things-L3", text="And six airbags standard, backed by a three-year unlimited-kilometre warranty. Start anywhere.", fact_ids=["F027", "F055"], ref="im01", focus="Airbags and written warranty")),
    ]

    who = by_seg["who-its-for"]
    d_old = who["deeper"][0]
    who["deeper"][0] = record(fresh(d_old, line_id=d_old["id"], text="The N Line look isn't a badge job. Up front: quad beam LED headlamps, a black grille and red bumper inserts.", fact_ids=["F049"], ref="im09", focus="Headlamps, grille, red inserts"))

    trust = by_seg["trust-safety"]
    t_old1, t_old2 = trust["lines"][0], trust["lines"][1]
    trust["lines"] = [
        record(fresh(t_old1, line_id="trust-safety-L1", text="Now the trust part — six airbags are standard.", fact_ids=["F027"], ref="im01", focus="Six airbags standard")),
        record(fresh(t_old2, line_id="trust-safety-L2", text="Disc brakes are fitted all round.", fact_ids=["F016"], ref="im12", focus="Four-wheel disc brakes")),
        record(fresh(t_old2, line_id="trust-safety-L3", text="On the automatic, the electric parking brake with auto hold keeps it still on a slope.", fact_ids=["F030"], ref="im02", focus="Electric brake and auto hold")),
        record(fresh(t_old2, line_id="trust-safety-L4", text="SmartSense helps, but never drives for you.", fact_ids=["F025", "F062"], ref=None, focus="")),
    ]

    drive = by_seg["drive-moment"]
    drive_old1, drive_old2 = drive["lines"][0], drive["lines"][1]
    drive["lines"] = [
        record(fresh(drive_old1, line_id="drive-moment-L1", text=drive_old1["text"], fact_ids=drive_old1["fact_ids"], ref="im11", focus="Turbo response")),
        record(fresh(drive_old2, line_id="drive-moment-L2", text="One firm squeeze handles a highway overtake.", fact_ids=["F003"], ref="im11", focus="Highway response")),
        record(fresh(drive_old2, line_id="drive-moment-L3", text="Paddles come only with the automatic.", fact_ids=["F008", "F021"], ref="im07", focus="Automatic paddle shifter")),
        record(fresh(drive_old2, line_id="drive-moment-L4", text="The automatic also gets drive modes.", fact_ids=["F023"], ref=None, focus="")),
    ]
    drive_old = next(line for line in drive["deeper"] if line["id"] == "drive-moment-D2")
    drive_d1 = next(line for line in drive["deeper"] if line["id"] == "drive-moment-D1")
    drive_d3 = next(line for line in drive["deeper"] if line["id"] == "drive-moment-D3")
    drive["deeper"] = [drive_d1,
        record(fresh(drive_old, line_id="drive-moment-D2", text="The automatic gets Smart Cruise Control with Stop and Go rather than plain cruise control.", fact_ids=["F025"], ref=None, focus="")),
        record(fresh(drive_old, line_id="drive-moment-D2b", text="It also adds snow, mud and sand traction modes.", fact_ids=["F025"], ref="im06", focus="Snow, mud and sand modes")),
        drive_d3]

    daily = by_seg["daily-cabin"]
    daily_old1, daily_old2 = daily["lines"][0], daily["lines"][-1]
    daily["lines"] = [
        record(fresh(daily_old1, line_id="daily-cabin-L1", text="Now the part you'd live with daily — ventilated front seats.", fact_ids=["F043"], ref="im03", focus="Ventilated front seats")),
        record(fresh(daily_old1, line_id="daily-cabin-L2", text="Dual-zone climate lets each of you pick your own temperature.", fact_ids=["F042"], ref="im13", focus="Dual-zone climate")),
        record(fresh(daily_old2, line_id="daily-cabin-L3", text="On a hot afternoon in traffic, your back stays dry and the cabin stays comfortable.", fact_ids=["F043", "F042"], ref="im03", focus="Cool on a hot commute")),
    ]

    family = by_seg["family-practicality"]
    family_old1, family_old2 = family["lines"][0], family["lines"][-1]
    family["lines"] = [
        record(fresh(family_old1, line_id="family-practicality-L1", text="The family side — the rear seat reclines two steps and has a centre armrest.", fact_ids=["F048"], ref="im03", focus="Reclining rear seat and armrest")),
        record(fresh(family_old1, line_id="family-practicality-L2", text="Rear passengers also get their own air vents and sunshades.", fact_ids=["F048"], ref=None, focus="")),
        record(fresh(family_old2, line_id="family-practicality-L3", text="So on long drives, people at the back stay cool and comfortable.", fact_ids=["F048"], ref="im03", focus="Comfort in the back")),
    ]

    ownership = by_seg["ownership-honesty"]
    own_old1, own_old2 = ownership["lines"][0], ownership["lines"][-1]
    ownership["lines"] = [
        record(fresh(own_old1, line_id="ownership-honesty-L1", text="One N10 variant, with a manual or an automatic.", fact_ids=["F019", "F008"], ref=None, focus="")),
        record(fresh(own_old1, line_id="ownership-honesty-L2", text="In writing: three-year unlimited-kilometre warranty and roadside assistance, terms applying.", fact_ids=["F055", "F057"], ref=None, focus="")),
        record(fresh(own_old2, line_id="ownership-honesty-L3", text=own_old2["text"], fact_ids=own_old2.get("fact_ids", []), ref=None, focus="", step=own_old2.get("step"))),
    ]

    # Correct existing literal mismatches. None means the source card should replace the product stage.
    assignments = {
        "who-its-for-D2": None,
        "the-promise-D1": None,
        "three-things-D2": None,
        "first-look-D1": None, "first-look-D2": None, "first-look-D3": None,
        "daily-cabin-D1": "im03",
        "family-practicality-D1": None, "family-practicality-D3": None,
        "drive-moment-D1": None, "drive-moment-D3": None,
        "trust-safety-D1": None, "trust-safety-D2": None, "trust-safety-D3": None,
        "few-more-L1": None, "few-more-D2": None, "few-more-D3": "im13",
        "ownership-honesty-D1": None, "ownership-honesty-D2": None, "ownership-honesty-D3": None,
    }
    all_lines = [line for seg in script["segments"] for line in [*(seg.get("lines") or []), *(seg.get("deeper") or [])]] + list(script.get("closing") or [])
    for line in all_lines:
        if line["id"] not in assignments:
            continue
        ref = assignments[line["id"]]
        if ref:
            line.setdefault("visual", {})["kind"] = "image"
            line["visual"]["ref"] = ref
        else:
            line["visual"] = None

    issues = author.validate(script, und, demo.get("settings", {}).get("audience", "everyday"))
    serious = [issue for issue in issues if "unverified" in issue.lower() or "does not exist" in issue.lower()]
    if serious:
        raise RuntimeError("Source-sync validation failed: " + "; ".join(serious))
    author.timeline(script, demo_id)
    store.write_json(demo_id, "script.json", script)
    built = bundle.build(demo_id, lambda _message: None)
    store.log(demo_id, "source-sync", {"changed_audio": changed, "visual_assignments": assignments, "validator_issues": issues,
                                       "stage_modes": {line["id"]: line["visual"].get("display_mode") for seg in built["segments"] for line in [*(seg.get("lines") or []), *(seg.get("deeper") or [])]}})
    runlog.event(demo_id, "Source-sync revision applied", f"{len(changed)} spoken lines recorded; {len(assignments)} literal picture assignments repaired; bundle v{built['version']}.")
    print({"demo_id": demo_id, "bundle_version": built["version"], "changed_audio": len(changed), "validator_issues": issues,
           "timeline_seconds": script["timeline"]["total_seconds"]})


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: revise_creta_source_sync.py <demo_id>")
    main(sys.argv[1])
