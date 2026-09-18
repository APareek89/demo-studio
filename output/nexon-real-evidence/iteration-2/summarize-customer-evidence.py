"""Read local records and print a safe JSON summary; never call the app/providers.

Run only after the customer sessions end, redirecting stdout to a NEW evidence file.
Costs use usage rows, not duplicated wrapper/transport trace rows. No contact,
share capability, raw prompt, answer or transcript text is emitted.
"""
from __future__ import annotations

import argparse
import ast
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import time
from types import SimpleNamespace


STAMPS = ("voice_ended", "stt_done", "qa_done", "answer_audio")
PAIRS = {"stt_ms": (0, 1), "qa_ms": (1, 2), "post_qa_to_audio_ms": (2, 3), "total_ms": (0, 3)}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def number(value):
    return not isinstance(value, bool) and isinstance(value, (int, float)) and math.isfinite(value)


def stats(values):
    values = sorted(values)
    # Match the app's existing selected-rank percentile, including Python round.
    def pct(q):
        return round(values[round(q * (len(values) - 1))]) if values else None
    return {"n": len(values), "p50": pct(.5), "p95": pct(.95), "worst": round(values[-1]) if values else None}


def turn_record(turn, index):
    stamps = [turn.get(key) for key in STAMPS]
    complete = all(number(value) and value > 0 for value in stamps)
    monotonic = complete and all(a <= b for a, b in zip(stamps, stamps[1:]))
    source = "bank" if turn.get("from_bank") is True else "model" if turn.get("from_bank") is False else "unclassified"
    via = turn.get("via") if turn.get("via") in ("typed", "server", "browser") else "unknown"
    return {"index": index, "source": source, "via": via, "answered": turn.get("answered"),
            "client_error": bool(turn.get("error")), "route": turn.get("route"),
            "stamps_ms": dict(zip(STAMPS, stamps)), "complete": monotonic,
            "excluded_reason": None if monotonic else "non-monotonic stamps" if complete else "missing or invalid stamps",
            "latency": {key: stamps[b] - stamps[a] for key, (a, b) in PAIRS.items()} if monotonic else {}}


def group_turns(turns):
    good = [row for row in turns if row["complete"]]
    return {"turns": len(turns), "complete": len(good), "excluded": len(turns) - len(good),
            "answered": sum(row["answered"] is True for row in turns),
            "declined": sum(row["answered"] is False for row in turns),
            "client_errors": sum(row["client_error"] for row in turns),
            "latency": {key: stats([row["latency"][key] for row in good]) for key in PAIRS}}


def latency_groups(turns):
    return {"all": group_turns(turns),
            "by_source": {source: group_turns([row for row in turns if row["source"] == source])
                          for source in ("bank", "model", "unclassified")},
            "by_input": {via: group_turns([row for row in turns if row["via"] == via])
                         for via in ("typed", "server", "browser", "unknown")},
            "by_source_and_input": {f"{source}/{via}": group_turns([row for row in turns if row["source"] == source and row["via"] == via])
                                    for source in ("bank", "model", "unclassified")
                                    for via in ("typed", "server", "browser", "unknown")}}


def pricing(repo):
    # Read only the pricing expressions/function, without importing config/store
    # (which create data directories) or any SDK/provider modules.
    from dotenv import dotenv_values
    file_values = dotenv_values(repo / ".env")
    price_env = {key: value for key, value in file_values.items() if key.startswith("PRICE_") or key == "FX_INR"}
    price_env.update({key: value for key, value in os.environ.items() if key.startswith("PRICE_") or key == "FX_INR"})
    source = (repo / "server/usage.py").read_bytes()
    wanted = {"PRICES", "_RUNWARE_MODELS", "_GEMINI_38_STANDARD_FROM", "FX_INR"}
    nodes = [node for node in ast.parse(source).body if
             (isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id in wanted for target in node.targets))
             or (isinstance(node, ast.FunctionDef) and node.name == "_cost_usd")]
    namespace = {"os": SimpleNamespace(getenv=lambda key, default=None: price_env.get(key, default)),
                 "datetime": datetime, "timezone": timezone, "time": time}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), "<read-only usage pricing>", "exec"), namespace)
    return namespace["_cost_usd"], {"prices": namespace["PRICES"], "fx_inr": namespace["FX_INR"],
                                   "usage_source_sha256": digest(source)}


def error_kind(error):
    text = (error or "").lower()
    if not text:
        return "none"
    if "credit" in text or "balance" in text:
        return "credits"
    if "429" in text or "quota" in text or "rate limit" in text:
        return "quota_or_rate_limit"
    if "timeout" in text or "timed out" in text or "deadline" in text:
        return "timeout"
    if "validation" in text or "invalid json" in text or "json_invalid" in text:
        return "schema_or_json"
    if "refus" in text or "blocked" in text or "sensitive" in text:
        return "refusal"
    return "other"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--demo", default="dm_36d47b86")
    parser.add_argument("--after", type=float, default=1789743348, help="Exclusive lower bound: Build2 customer cutoff")
    parser.add_argument("--before", type=float, default=None, help="Inclusive upper bound; defaults to capture time")
    parser.add_argument("--allow-active", action="store_true", help="Preparation only; label active sessions honestly")
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[3]
    demo_dir = repo / "data/demos" / args.demo
    if demo_dir.parent != repo / "data/demos" or not args.demo.startswith("dm_"):
        parser.error("Expected a local demo ID")
    cutoff = args.before if args.before is not None else time.time()
    sources, parse_issues = {}, []

    def read(path, jsonl=False):
        raw = path.read_bytes()
        sources[str(path.relative_to(repo))] = {"sha256": digest(raw), "bytes": len(raw)}
        if not jsonl:
            return json.loads(raw)
        rows = []
        for index, line in enumerate(raw.splitlines(), 1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
                row["_row"] = index
                rows.append(row)
            except (json.JSONDecodeError, TypeError):
                parse_issues.append({"file": str(path.relative_to(repo)), "row": index})
        return rows

    sessions, all_turns = [], []
    for path in sorted((demo_dir / "sessions").glob("*.json")):
        session = read(path)
        if not session.get("ended") and not args.allow_active:
            parser.error(f"Session {session.get('id')} is still active; wait for the root's all-ended signal")
        turns = [turn_record(turn, index) for index, turn in enumerate(session.get("turns") or [], 1)]
        all_turns.extend(turns)
        summary = session.get("summary")
        transcript_n = len(session.get("transcript") or [])
        summary_state = "pending" if not summary else "error" if summary.get("error") else "present"
        sessions.append({"id": session.get("id"), "ended": bool(session.get("ended")),
                         "saved_at": session.get("saved_at"), "minutes_recorded": session.get("minutes"),
                         "transcript_lines": transcript_n, "leads": len(session.get("leads") or []),
                         "summary": {"state": summary_state, "model": (summary or {}).get("model"),
                                     "generated_at": (summary or {}).get("generated_at"),
                                     "transcript_lines": (summary or {}).get("transcript_lines"),
                                     "matches_saved_transcript": bool(summary and summary_state == "present"
                                                                      and summary.get("transcript_lines") == transcript_n)},
                         "groups": latency_groups(turns), "turns": turns})

    trace = [row for row in read(demo_dir / "trace.jsonl", True) if args.after < row.get("t", 0) <= cutoff]
    usage = [row for row in read(demo_dir / "usage.jsonl", True) if args.after < row.get("t", 0) <= cutoff]
    cost, assumptions = pricing(repo)
    usage_groups = defaultdict(list)
    for row in usage:
        usage_groups[(row.get("stage"), row.get("kind"), row.get("model"))].append(row)
    costs = [{"stage": key[0], "kind": key[1], "model": key[2], "recorded_rows": len(rows),
              "estimated_usd": round(sum(cost(row) for row in rows), 6),
              "native_cost_rows": sum(row.get("usd") is not None for row in rows),
              "unpriced_rows": sum(bool(row.get("cost_note")) for row in rows)}
             for key, rows in sorted(usage_groups.items())]
    trace_groups = defaultdict(list)
    for row in trace:
        trace_groups[(row.get("stage"), row.get("kind"), row.get("model"))].append(row)
    events = [{"stage": key[0], "kind": key[1], "model": key[2], "trace_events": len(rows),
               "error_events": sum(bool(row.get("error")) for row in rows),
               "error_categories": dict(Counter(error_kind(row.get("error")) for row in rows if row.get("error"))),
               "latency_ms": stats([row["latency_ms"] for row in rows if number(row.get("latency_ms"))]),
               "source_rows": [row["_row"] for row in rows]}
              for key, rows in sorted(trace_groups.items())]
    result = {"demo_id": args.demo, "captured_at": datetime.now(timezone.utc).isoformat(),
              "customer_window": {"after_exclusive": args.after, "before_inclusive": cutoff},
              "sessions": sessions, "combined_latency": latency_groups(all_turns),
              "cost": {"basis": "Usage records at configured rates, not an invoice; never sum duplicated trace wrappers.",
                       "estimated_usd": round(sum(cost(row) for row in usage), 6), "recorded_rows": len(usage),
                       "by_stage_kind_model": costs, "assumptions": assumptions},
              "provider_trace_events": events,
              "all_providers_failed_events": sum(row.get("kind") == "qa-providers-failed" for row in trace),
              "source_files": sources, "malformed_jsonl_rows": parse_issues,
              "limits": ["All four finite non-decreasing stamps are required for every latency percentile; incomplete turns remain counted.",
                         "Percentiles match the app's selected-rank calculation; small samples do not establish production latency.",
                         "Typed STT is zero by construction. Browser STT also stamps voice end and completion together; it is not measured recognition latency.",
                         "Post-QA-to-audio includes the player transition and scheduling; it is not pure synthesis latency.",
                         "Trace wrapper and transport events can describe the same request; event counts are not paid-attempt counts.",
                         "Trace/usage rows have no session ID; costs and provider events are for the stated customer window, not assigned to individual sessions.",
                         "A matching summary transcript count establishes freshness only; summary content accuracy requires separate review.",
                         "Rows without reported usage, including failed calls, may have unrecorded actual costs. Acoustic intelligibility is not measured."]}
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
