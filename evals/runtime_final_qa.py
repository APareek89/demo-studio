"""One isolated paid acceptance journey, deliberately split at human review.

Default `prepare` is offline. Root runs `read --execute-paid` only after the
complete free QA is green, inspects the exported draft, then writes review.json
and runs `build --execute-paid`. Browser QA is separate and bounded. This file
never changes production data, bypasses readiness/validation, or submits a lead.
"""
from __future__ import annotations

import argparse
from contextlib import ExitStack
import hashlib
import json
import mimetypes
import os
from pathlib import Path
import shutil
import socket
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
WORK = Path("/tmp/demo-runtime-final-20260924").resolve()
ASSETS = Path("/Users/macbook/Documents/Hyundai Creta Official/Demo files")
BASE = "http://127.0.0.1:8910"
PROTECTED = "dm_41513908"
CARDS = ("visuals", "facts", "script", "faq", "persona", "ctas")
ARTIFACTS = ("understanding.json", "playbook.json", "plan.json", "script.json", "deck.json", "faq.json")
EVIDENCE_REVISION_INSTRUCTION = (
    "Read all retained source material and capture customer-relevant categorical, gearbox, feature and ownership facts "
    "with their exact source quotes, locators, units, applicability and conditions. Preserve explicit warnings about "
    "stale or conflicting FAQ evidence. Do not invent claims, infer missing table cells, or remove evidence conflicts."
)


def save(name, value):
    WORK.mkdir(parents=True, exist_ok=True)
    (WORK / name).write_text(json.dumps(value, indent=2, ensure_ascii=False))


def load(name, default=None):
    path = WORK / name
    return json.loads(path.read_text()) if path.exists() else default


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prepare():
    files = [{"path":str(path), "name":path.name, "bytes":path.stat().st_size, "sha256":digest(path)}
             for path in sorted(ASSETS.iterdir()) if path.suffix.lower() in {".jpg", ".pdf"}]
    assert len(files) == 17 and sum(row["name"].endswith(".jpg") for row in files) == 16
    manifest = {"files":files, "source_folder":str(ASSETS), "base_url":BASE,
                "storage":str(WORK / "data"), "graph":str(WORK / "graph.sqlite"), "port":8910}
    save("upload-manifest.json", manifest)
    os.environ.update(MOCK_LLM="1", CLOUD_SYNC="0", STORAGE_BACKEND="local",
                      DEMO_STUDIO_DATA=manifest["storage"], DEMO_STUDIO_GRAPH_DB=manifest["graph"])
    sys.path.insert(0, str(ROOT))
    from server import config
    readiness = config.health()
    readiness["inspection_only"] = True
    save("configured-readiness.json", readiness)
    assert readiness["gemini"] and readiness["sarvam"], "Vision and streaming speech keys must exist"
    print(json.dumps({"manifest":str(WORK / "upload-manifest.json"), "files":len(files),
                      "bytes":sum(row["bytes"] for row in files), "configured_only":True,
                      "model_tier":readiness["model_tier"], "tts_provider":readiness["tts_provider"]}))


class Journey:
    def __init__(self, args):
        import httpx
        assert args.execute_paid, "Paid phases require explicit root dispatch after free QA"
        self.args = args
        self.client = httpx.Client(base_url=BASE, timeout=180, trust_env=False)
        self.record = load("journey.json", {"attempted":{}, "checks":[]})
        self.did = self.record.get("demo_id")
        # A storage identity file is created by the safe server command below.
        identity = load("server-identity.json", {})
        assert (identity.get("storage") == str(WORK / "data") and identity.get("port") == 8910
                and identity.get("graph") == str(WORK / "graph.sqlite"))
        os.kill(int(identity["pid"]), 0)  # Refuse a stale identity from a stopped process.
        health = self.request("GET", "/api/health")
        assert health.get("mock") is False and health.get("storage") == "local", "Paid run needs a real, isolated app"
        if self.did:
            assert self.did != PROTECTED and (WORK / "data" / self.did / "demo.json").is_file()

    def request(self, method, path, **kwargs):
        assert PROTECTED not in path and "override_readiness" not in path
        response = self.client.request(method, path, **kwargs)
        response.raise_for_status()
        return response.json()

    def api(self, method, tail="", **kwargs):
        assert self.did and self.did != PROTECTED
        return self.request(method, f"/api/demos/{self.did}" + ("/" + tail if tail else ""), **kwargs)

    def persist(self):
        save("journey.json", self.record)

    def once(self, name):
        assert name not in self.record["attempted"], f"{name} already attempted; no automatic paid repeat"
        # Exclusive creation also rejects concurrent dispatches and preserves
        # uncertain attempts even if the process exits before saving its ledger.
        with (WORK / f"attempt-{name}.json").open("x") as marker:
            json.dump({"phase":name,"demo_id":self.did,"at":time.time()},marker)
        self.record["attempted"][name] = time.time()
        self.persist()

    def guard(self):
        usage = self.api("GET", "usage")
        save("usage-latest.json", usage)
        assert usage["total_usd"] < self.args.max_usd, "Recorded cost ceiling reached; no next paid action"
        assert usage["rows"] < 250, "Recorded provider-call ceiling reached; no next paid action"
        return usage

    def wait(self, status, phase, timeout=1800):
        deadline, last = time.monotonic()+timeout, 0
        while time.monotonic() < deadline:
            state = self.api("GET")
            save("state-latest.json", state)
            if state["demo"]["status"] == "error":
                raise AssertionError(json.dumps(state["demo"]["stages"]))
            if not state["running"]:
                assert state["demo"]["status"] == status, f"{phase} returned to {state['demo']['status']}; inspect draft, do not auto-retry"
                return state
            if time.monotonic()-last >= 20:
                usage = self.api("GET", "usage")
                save("usage-latest.json", usage)
                print(json.dumps({"phase":phase, "running":state["demo"].get("running"),
                                  "status":state["demo"]["status"], "recorded_usd":usage["total_usd"]}), flush=True)
                last = time.monotonic()
            time.sleep(2)
        raise TimeoutError(f"{phase} deadline reached; inspect isolated worker before doing anything else")

    def export_review(self, state):
        folder = WORK / "data" / self.did
        hashes = {}
        for name in ARTIFACTS:
            path = folder / name
            if path.exists():
                save("review-"+name, json.loads(path.read_text()))
                hashes[name] = digest(path)
        save("review-state.json", state)
        save("review-required.json", {"demo_id":self.did, "artifact_hashes":hashes,
             "reviewed_by":"", "facts_citations_checked":False, "script_issues_checked":False,
             "cards":{card:{"approved":False,"notes":""} for card in CARDS},
             "instructions":"Inspect facts against the uploaded PDF, supported script, pictures, issues and six cards. Write completed review.json; do not blindly copy approval booleans."})
        print(json.dumps({"review_required":str(WORK / "review-required.json"),
                          "align_url":BASE+f"/#/studio/{self.did}/align", "demo_id":self.did}), flush=True)

    def read(self):
        assert not self.did, "A fresh Read is allowed only once"
        manifest = load("upload-manifest.json")
        assert manifest["source_folder"] == str(ASSETS) and manifest["base_url"] == BASE
        assert len(manifest["files"]) == 17
        for row in manifest["files"]:
            assert Path(row["path"]).parent == ASSETS and Path(row["path"]).suffix.lower() in {".jpg", ".pdf"}
            assert digest(Path(row["path"])) == row["sha256"], "Source changed after manifest"
        self.once("create")
        demo = self.request("POST", "/api/demos", json={"name":"Hyundai CRETA · runtime final QA"})
        self.did = demo["id"]
        self.record["demo_id"] = self.did
        self.persist()
        self.api("PATCH", json={"settings":{"tts_provider":"sarvam", "sarvam_speaker":"priya",
                 "language":"en-IN", "languages":["en-IN"], "pitch_minutes":3, "visual_theme":"marine"}})
        with ExitStack() as stack:
            files = [("files", (row["name"], stack.enter_context(open(row["path"], "rb")), mimetypes.guess_type(row["name"])[0]))
                     for row in manifest["files"]]
            uploaded = self.api("POST", "sources", files=files, data={"role":"product"})
        assert len(uploaded["added"]) == 17
        self.once("readiness")
        ready = self.api("POST", "readiness/probe")
        save("observed-readiness.json", ready)
        assert ready.get("ready"), "Provider capability probe failed; no paid Read attempted"
        self.guard(); self.once("read")
        self.api("POST", "read")
        state = self.wait("align", "Read")
        self.export_review(state)

    def evidence_revision(self):
        """One normal Understand revision after a failed paid Read; never a hidden repeat."""
        assert self.did == "dm_7bbf10d0", "Only the existing isolated paid QA demo may be revised"
        assert "read" in self.record["attempted"] and "build" not in self.record["attempted"]
        assert "evidence-revision" not in self.record["attempted"], "Evidence revision already attempted"
        assert not (WORK / "attempt-evidence-revision.json").exists(), "Uncertain revision must not repeat"
        state = self.api("GET")
        assert not state["running"] and state["demo"]["status"] == "align", "Inspect any existing worker first"
        self.guard()
        # Exclusive snapshot creation fails closed rather than replacing evidence
        # from the original paid Read on an accidental second dispatch.
        initial = WORK / "read-initial"
        initial.mkdir()
        files = [*WORK.glob("review*.json"), *WORK.glob("attempt-*.json")]
        files.extend(WORK / name for name in ("journey.json", "state-latest.json", "usage-latest.json",
                     "observed-readiness.json", "upload-manifest.json", "server-identity.json"))
        for path in sorted(set(files)):
            if path.is_file():
                shutil.copy2(path, initial / path.name)
        (initial / "state-before-revision.json").write_text(json.dumps(state, indent=2, ensure_ascii=False))
        original = initial / "artifacts"
        original.mkdir()
        for name in (*ARTIFACTS, "demo.json", "trace.jsonl", "usage.jsonl"):
            path = WORK / "data" / self.did / name
            if path.is_file():
                shutil.copy2(path, original / name)
        manifest = {str(path.relative_to(initial)): digest(path) for path in sorted(initial.rglob("*")) if path.is_file()}
        (initial / "snapshot-manifest.json").write_text(json.dumps(manifest, indent=2))
        payload = {"stage":"understand", "rebuild":False, "instruction":EVIDENCE_REVISION_INSTRUCTION}
        receipt = {"demo_id":self.did, "phase":"evidence-revision", "status":"prepared",
                   "reason":"The initial paid Read under-extracted retained source evidence, leaving an incomplete narration draft. "
                            "After free regression checks, use the existing Understand revision path once; preserve the initial failed Read.",
                   "initial_snapshot":str(initial), "initial_artifact_hashes":manifest,
                   "request":payload, "new_demo":False, "new_read":False, "build":False}
        save("evidence-revision-receipt.json", receipt)
        self.once("evidence-revision")
        try:
            receipt.update(status="dispatched", dispatched_at=time.time())
            save("evidence-revision-receipt.json", receipt)
            receipt["response"] = self.api("POST", "revise", json=payload)
            state = self.wait("align", "Evidence revision")
            self.export_review(state)
            usage = self.guard()
            receipt.update(status="align-review-required", completed_at=time.time(),
                           recorded_usd=usage["total_usd"], provider_calls=usage["rows"],
                           revised_artifact_hashes=load("review-required.json")["artifact_hashes"])
        except Exception as exc:
            receipt.update(status="stopped-inspect-before-any-next-action", error=str(exc)[:1000])
            raise
        finally:
            save("evidence-revision-receipt.json", receipt)

    def build(self):
        review = load("review.json", {})
        required = load("review-required.json", {})
        assert review.get("demo_id") == self.did and review.get("reviewed_by")
        assert review.get("facts_citations_checked") and review.get("script_issues_checked")
        assert review.get("artifact_hashes") == required.get("artifact_hashes") and review.get("artifact_hashes")
        assert all(review.get("cards", {}).get(card, {}).get("approved") and
                   review["cards"][card].get("notes") for card in CARDS), "Document actual review of all cards first"
        for name, expected in review["artifact_hashes"].items():
            assert digest(WORK / "data" / self.did / name) == expected, "Draft changed after review"
        state = self.api("GET")
        assert state["cards"]["script"]["preparation"]["status"] in {"ready", "needs_recording"}
        for card in CARDS:
            self.api("POST", "approve/"+card)
        assert all(self.api("GET")["demo"]["approvals"].values())
        self.guard(); self.once("build")
        self.api("POST", "build")
        self.wait("ready", "Build")
        bundle = self.api("GET", "bundle")
        minimum = bundle["runtime"]["narration_minimum"]
        assert minimum["measured"] and minimum["sufficient"] and minimum["seconds"] >= 180
        assert bundle["runtime"]["version"] == 1 and bundle.get("knowledge_snapshot_id")
        save("published-bundle.json", bundle)
        self.record["publication"] = {"minimum":minimum, "version":bundle["version"]}
        self.persist(); self.guard()
        print(json.dumps({"demo_url":BASE+f"/?mute=1&presentation=walkthrough#/play/{self.did}", "minimum":minimum}), flush=True)


def serve(args):
    assert args.execute_paid, "Root starts the real isolated server only after full mock QA"
    os.environ.update(MOCK_LLM="0", CLOUD_SYNC="0", STORAGE_BACKEND="local",
                      DEMO_STUDIO_DATA=str(WORK / "data"), DEMO_STUDIO_GRAPH_DB=str(WORK / "graph.sqlite"))
    sys.path.insert(0, str(ROOT))
    from server import config
    assert config.DATA_DIR == WORK / "data" and config.GRAPH_DB == WORK / "graph.sqlite" and not config.MOCK_LLM
    import uvicorn
    # Do not overwrite identity while a different process owns the port.
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        listener.bind(("127.0.0.1",8910))
        save("server-identity.json", {"storage":str(config.DATA_DIR), "graph":str(config.GRAPH_DB), "port":8910, "pid":os.getpid()})
        server = uvicorn.Server(uvicorn.Config("server.app:app", host="127.0.0.1", port=8910, access_log=False))
        server.run(sockets=[listener])
    finally:
        listener.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("prepare", "serve", "read", "evidence-revision", "build", "browser"), nargs="?", default="prepare")
    parser.add_argument("--execute-paid", action="store_true")
    parser.add_argument("--max-usd", type=float, default=10.0, help="Stop before the next action at this recorded cost; not a provider invoice guarantee")
    parser.add_argument("--question", default="What engine and gearbox choices does this CRETA offer?")
    args = parser.parse_args()
    if args.phase == "prepare":
        prepare()
    elif args.phase == "serve":
        serve(args)
    else:
        journey = Journey(args)
        if args.phase == "browser":
            from runtime_final_browser import run
            run(journey)
        else:
            getattr(journey,args.phase.replace("-", "_"))()


if __name__ == "__main__":
    main()
