"""AWS persistence: DynamoDB for records, S3 for files.

The local folder store (data/demos/<id>/) stays the working copy that every stage reads and writes — it is fast and
it is what the run log and Observability read. This module mirrors it:
  • DynamoDB `demo-studio-demos`  — one item per demo: name, status, version, settings, approvals, stages, sources (metadata), product.
  • DynamoDB `demo-studio-events` — sessions, leads, eval runs, stage completions (demo_id + ts#kind).
  • S3 `demo-studio-<account>`     — every file of the demo folder under demos/<id>/… (sources, derived, audio, JSON, RUN.md, traces).
Sync is incremental (a manifest of size+mtime per file), runs in a background thread after each stage, and never blocks
or fails a build. A demo that exists only in the cloud is listed from DynamoDB and restored on demand; media files are
fetched lazily by the /media route. Credentials come from the standard AWS chain (~/.aws from `aws configure`, or env)
— nothing here reads or prints a key. Disable with CLOUD_SYNC=0; mock mode never touches AWS."""
from __future__ import annotations

import json
import mimetypes
import os
import threading
import time
from decimal import Decimal
from pathlib import Path

from . import config, store

_state: dict = {"checked": False, "enabled": False, "why": "", "account": "", "region": "", "bucket": "", "tables": {}}
_lock = threading.Lock()
_pending: set[str] = set()
MANIFEST = ".cloud-manifest.json"
SKIP = {MANIFEST, ".DS_Store"}


def _session():
    import boto3
    return boto3.session.Session(region_name=os.getenv("AWS_REGION") or None)


def status() -> dict:
    return {k: v for k, v in _state.items() if k != "checked"}


def enabled() -> bool:
    """One-time probe: credentials + region resolve → on. Never raises."""
    if _state["checked"]:
        return _state["enabled"]
    with _lock:
        if _state["checked"]:
            return _state["enabled"]
        _state["checked"] = True
        if config.MOCK_LLM or os.getenv("CLOUD_SYNC", "1").strip() == "0":
            _state["why"] = "off (mock or CLOUD_SYNC=0)"
            return False
        try:
            s = _session()
            if not s.region_name:
                _state["why"] = "no AWS region configured (aws configure)"
                return False
            idn = s.client("sts").get_caller_identity()
            _state.update({"account": idn["Account"], "region": s.region_name,
                           "bucket": os.getenv("S3_BUCKET") or f"demo-studio-{idn['Account']}",
                           "tables": {"demos": os.getenv("DDB_TABLE_DEMOS") or "demo-studio-demos", "events": os.getenv("DDB_TABLE_EVENTS") or "demo-studio-events"}})
            _state["enabled"] = True
            _state["why"] = "connected"
        except Exception as e:
            _state["why"] = f"not connected: {str(e)[:120]}"
        return _state["enabled"]


# ---------- resources ----------

def ensure_resources(log=print) -> dict:
    """Create the bucket (private, encrypted, versioned) and the two on-demand tables if they do not exist. Idempotent."""
    if not enabled():
        return status()
    s = _session()
    s3, ddb = s.client("s3"), s.client("dynamodb")
    b = _state["bucket"]
    try:
        s3.head_bucket(Bucket=b)
        log(f"bucket {b} exists")
    except Exception:
        kw = {"Bucket": b}
        if s.region_name != "us-east-1":
            kw["CreateBucketConfiguration"] = {"LocationConstraint": s.region_name}
        try:
            s3.create_bucket(**kw)
            log(f"bucket {b} created")
        except s3.exceptions.BucketAlreadyOwnedByYou:
            log(f"bucket {b} already owned by you")
        for what, fn in (("public access block", lambda: s3.put_public_access_block(Bucket=b, PublicAccessBlockConfiguration={"BlockPublicAcls": True, "IgnorePublicAcls": True, "BlockPublicPolicy": True, "RestrictPublicBuckets": True})),
                         ("default encryption", lambda: s3.put_bucket_encryption(Bucket=b, ServerSideEncryptionConfiguration={"Rules": [{"ApplyServerSideEncryptionByDefault": {"SSEAlgorithm": "AES256"}}]})),
                         ("versioning", lambda: s3.put_bucket_versioning(Bucket=b, VersioningConfiguration={"Status": "Enabled"}))):
            try:
                fn()
                log(f"bucket {b}: {what} set")
            except Exception as e:  # S3 encrypts every object by default since 2023; versioning is a nice-to-have
                log(f"bucket {b}: {what} not set ({str(e)[:90]}) — attach docs/aws/iam-policy.json to the IAM user to allow it")
    existing = set(ddb.list_tables().get("TableNames", []))
    specs = {
        _state["tables"]["demos"]: {"KeySchema": [{"AttributeName": "demo_id", "KeyType": "HASH"}], "AttributeDefinitions": [{"AttributeName": "demo_id", "AttributeType": "S"}]},
        _state["tables"]["events"]: {"KeySchema": [{"AttributeName": "demo_id", "KeyType": "HASH"}, {"AttributeName": "sk", "KeyType": "RANGE"}], "AttributeDefinitions": [{"AttributeName": "demo_id", "AttributeType": "S"}, {"AttributeName": "sk", "AttributeType": "S"}]},
    }
    for name, spec in specs.items():
        if name in existing:
            log(f"table {name} exists")
            continue
        ddb.create_table(TableName=name, BillingMode="PAY_PER_REQUEST", **spec)
        ddb.get_waiter("table_exists").wait(TableName=name)
        log(f"table {name} created (on-demand)")
    return status()


# ---------- DynamoDB ----------

def _ddb_item(obj):
    """floats → Decimal, empty strings kept, drop None."""
    if isinstance(obj, float):
        return Decimal(str(obj))
    if isinstance(obj, dict):
        return {k: _ddb_item(v) for k, v in obj.items() if v is not None}
    if isinstance(obj, list):
        return [_ddb_item(v) for v in obj]
    return obj


def _plain(obj):
    if isinstance(obj, Decimal):
        return float(obj) if obj % 1 else int(obj)
    if isinstance(obj, dict):
        return {k: _plain(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_plain(v) for v in obj]
    return obj


def put_demo_record(demo_id: str) -> None:
    if not enabled():
        return
    demo = store.load(demo_id)
    item = {"demo_id": demo_id, "name": demo.get("name"), "status": demo.get("status"), "version": demo.get("version", 0), "created_at": demo.get("created_at"),
            "updated_at": time.time(), "product": demo.get("product", {}), "settings": demo.get("settings", {}), "approvals": demo.get("approvals", {}),
            "stages": demo.get("stages", {}), "sources": [{k: s.get(k) for k in ("id", "kind", "name", "role", "path", "play", "url", "use_in_demo", "size")} for s in demo.get("sources", [])],
            "mascot": demo.get("mascot"), "visual_asset": demo.get("visual_asset"), "s3_prefix": f"demos/{demo_id}/"}
    _session().resource("dynamodb").Table(_state["tables"]["demos"]).put_item(Item=_ddb_item(item))


def put_event(demo_id: str, kind: str, payload: dict) -> None:
    """sessions, leads, eval runs, stage completions — small records you can query per demo."""
    if not enabled():
        return
    try:
        item = {"demo_id": demo_id, "sk": f"{time.time():.3f}#{kind}", "kind": kind, "t": time.time(), **payload}
        _session().resource("dynamodb").Table(_state["tables"]["events"]).put_item(Item=_ddb_item(item))
    except Exception as e:
        store.log(demo_id, "cloud-error", {"op": "put_event", "kind": kind, "error": str(e)[:200]})


def list_cloud_demos() -> list[dict]:
    if not enabled():
        return []
    try:
        t = _session().resource("dynamodb").Table(_state["tables"]["demos"])
        items, kw = [], {}
        while True:
            r = t.scan(**kw)
            items += r.get("Items", [])
            if not r.get("LastEvaluatedKey"):
                break
            kw["ExclusiveStartKey"] = r["LastEvaluatedKey"]
        return [_plain(i) for i in items]
    except Exception:
        return []


def list_events(demo_id: str, kind: str | None = None, limit: int = 50) -> list[dict]:
    if not enabled():
        return []
    try:
        from boto3.dynamodb.conditions import Key
        t = _session().resource("dynamodb").Table(_state["tables"]["events"])
        r = t.query(KeyConditionExpression=Key("demo_id").eq(demo_id), ScanIndexForward=False, Limit=limit)
        rows = [_plain(i) for i in r.get("Items", [])]
        return [x for x in rows if not kind or x.get("kind") == kind]
    except Exception:
        return []


# ---------- S3 file mirror ----------

def _manifest(demo_id: str) -> dict:
    p = store.path(demo_id, MANIFEST)
    try:
        return json.loads(p.read_text()) if p.exists() else {}
    except Exception:
        return {}


def sync_files(demo_id: str, log=lambda m: None) -> int:
    """Upload every changed file of the demo folder to s3://bucket/demos/<id>/…; returns the number uploaded."""
    if not enabled():
        return 0
    root = store.demo_dir(demo_id)
    man = _manifest(demo_id)
    s3 = _session().client("s3")
    n = 0
    for p in sorted(root.rglob("*")):
        if not p.is_file() or p.name in SKIP:
            continue
        rel = str(p.relative_to(root))
        st = p.stat()
        sig = f"{st.st_size}:{int(st.st_mtime)}"
        if man.get(rel) == sig:
            continue
        mime = mimetypes.guess_type(p.name)[0] or "application/octet-stream"
        s3.upload_file(str(p), _state["bucket"], f"demos/{demo_id}/{rel}", ExtraArgs={"ContentType": mime})
        man[rel] = sig
        n += 1
    store.path(demo_id, MANIFEST).write_text(json.dumps(man))
    if n:
        log(f"cloud: {n} file(s) synced to s3://{_state['bucket']}/demos/{demo_id}/")
    return n


def sync_demo(demo_id: str, log=lambda m: None) -> None:
    """Record + files. Errors are logged to the demo's logs folder, never raised."""
    try:
        put_demo_record(demo_id)
        sync_files(demo_id, log)
    except Exception as e:
        store.log(demo_id, "cloud-error", {"op": "sync_demo", "error": str(e)[:300]})


def sync_demo_async(demo_id: str) -> None:
    """Debounced background sync: one thread per demo at a time; a request while running re-queues once."""
    if not enabled() or not store.exists(demo_id):
        return
    with _lock:
        if demo_id in _pending:
            return
        _pending.add(demo_id)

    def run():
        try:
            time.sleep(1.0)  # coalesce bursts of writes
            sync_demo(demo_id)
        finally:
            with _lock:
                _pending.discard(demo_id)
    threading.Thread(target=run, daemon=True, name=f"cloud-{demo_id}").start()


def fetch_file(demo_id: str, rel: str) -> Path | None:
    """Lazy restore of one file (media, audio, JSON) from S3 into the local cache."""
    if not enabled():
        return None
    p = store.path(demo_id, rel)
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        _session().client("s3").download_file(_state["bucket"], f"demos/{demo_id}/{rel}", str(p))
        return p if p.exists() else None
    except Exception:
        return None


def delete_file(demo_id: str, rel: str) -> None:
    """Remove one mirrored object and its manifest entry. Best effort, like the rest of cloud sync."""
    if not enabled():
        return
    try:
        _session().client("s3").delete_object(Bucket=_state["bucket"], Key=f"demos/{demo_id}/{rel}")
        man = _manifest(demo_id)
        if rel in man:
            man.pop(rel, None)
            store.path(demo_id, MANIFEST).write_text(json.dumps(man))
    except Exception as e:
        store.log(demo_id, "cloud-error", {"op": "delete_file", "path": rel, "error": str(e)[:300]})


def restore_demo(demo_id: str, log=lambda m: None) -> bool:
    """Bring a cloud-only demo back: demo.json + every JSON/MD artefact now, media on demand."""
    if not enabled():
        return False
    s3 = _session().client("s3")
    prefix = f"demos/{demo_id}/"
    got = 0
    try:
        kw = {"Bucket": _state["bucket"], "Prefix": prefix}
        while True:
            r = s3.list_objects_v2(**kw)
            for o in r.get("Contents", []):
                rel = o["Key"][len(prefix):]
                if rel.endswith((".json", ".jsonl", ".md")) and rel != MANIFEST:
                    p = store.path(demo_id, rel)
                    p.parent.mkdir(parents=True, exist_ok=True)
                    s3.download_file(_state["bucket"], o["Key"], str(p))
                    got += 1
            if not r.get("IsTruncated"):
                break
            kw["ContinuationToken"] = r["NextContinuationToken"]
        log(f"cloud: restored {got} file(s) for {demo_id}; media loads on demand")
        return got > 0
    except Exception as e:
        log(f"cloud: restore failed ({str(e)[:100]})")
        return False


IAM_POLICY = {
    "Version": "2012-10-17",
    "Statement": [
        {"Effect": "Allow", "Action": ["sts:GetCallerIdentity"], "Resource": "*"},
        {"Effect": "Allow", "Action": ["s3:CreateBucket", "s3:ListBucket", "s3:GetBucketLocation", "s3:PutBucketPublicAccessBlock", "s3:PutEncryptionConfiguration", "s3:PutBucketVersioning"], "Resource": "arn:aws:s3:::demo-studio-*"},
        {"Effect": "Allow", "Action": ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"], "Resource": "arn:aws:s3:::demo-studio-*/*"},
        {"Effect": "Allow", "Action": ["dynamodb:CreateTable", "dynamodb:DescribeTable", "dynamodb:ListTables", "dynamodb:PutItem", "dynamodb:GetItem", "dynamodb:Query", "dynamodb:Scan", "dynamodb:UpdateItem", "dynamodb:DeleteItem"], "Resource": "arn:aws:dynamodb:*:*:table/demo-studio-*"},
    ],
}
