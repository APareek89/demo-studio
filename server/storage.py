"""Storage — one interface in front of the folder store, two backends.

local (default): sessions/ and leads/ under data/demos/<id>/, media served by the app itself.
aws: the same local files stay the working copy, PLUS one DynamoDB row per session and per lead
     (table `demo-studio-sessions`: PK demo_id · SK sk = session#<id> | lead#<id> · TTL expires_at), the S3 mirror from
     cloud.py for every file, and media served by a short-lived pre-signed URL so the small instance does not stream video.
Selection: STORAGE_BACKEND=local|aws. `aws` without resolvable credentials falls back to local and says why in status().
Credentials come from the instance role or the standard AWS chain — never from code, never from a key in a file."""
from __future__ import annotations

import json
import time

from . import cloud, config, store


def _brief(s: dict) -> dict:
    """The list row: enough to pick a session, never the transcript."""
    sm = s.get("summary") or {}
    return {"id": s.get("id"), "saved_at": s.get("saved_at"), "profile": s.get("profile"), "cta": s.get("cta"), "questions": len(s.get("questions", [])),
            "intent": s.get("intent"), "drop_point": s.get("drop_point"), "escalations": s.get("escalations", []), "minutes": s.get("minutes"), "ended": bool(s.get("ended")),
            "summary": {k: sm.get(k) for k in ("context", "opening_line", "customer_name")} if sm else None, "leads": len(s.get("leads", []))}


class Local:
    name = "local"
    fallback_reason = ""

    def put_session(self, demo_id: str, record: dict) -> None:
        store.write_json(demo_id, f"sessions/{record['id']}.json", record)

    def get_session(self, demo_id: str, sid: str) -> dict | None:
        return store.read_json(demo_id, f"sessions/{sid}.json")

    def list_sessions(self, demo_id: str, limit: int = 50) -> list[dict]:
        out = []
        d = store.path(demo_id, "sessions")
        if d.exists():
            for p in sorted(d.glob("*.json"), reverse=True)[:limit]:
                try:
                    out.append(_brief(json.loads(p.read_text())))
                except Exception:
                    pass
        return out

    def put_lead(self, demo_id: str, lead: dict) -> None:
        store.write_json(demo_id, f"leads/{lead['id']}.json", lead)

    def list_leads(self, demo_id: str, limit: int = 50) -> list[dict]:
        out = []
        d = store.path(demo_id, "leads")
        if d.exists():
            for p in sorted(d.glob("*.json"), reverse=True)[:limit]:
                try:
                    out.append(json.loads(p.read_text()))
                except Exception:
                    pass
        return out

    def media_url(self, demo_id: str, rel: str) -> str | None:
        return None  # the app serves the file

    def after_write(self, demo_id: str) -> None:
        pass

    def status(self) -> dict:
        return {"backend": self.name, "fallback_reason": self.fallback_reason}


class Aws(Local):
    name = "aws"

    def __init__(self) -> None:
        self.table = config.DDB_TABLE_SESSIONS

    def _table(self):
        return cloud._session().resource("dynamodb").Table(self.table)

    def _put(self, demo_id: str, sk: str, payload: dict) -> None:
        try:
            item = {"demo_id": demo_id, "sk": sk, "kind": sk.split("#", 1)[0], "t": time.time(), "expires_at": int(time.time() + config.SESSION_TTL_DAYS * 86400), **payload}
            self._table().put_item(Item=cloud._ddb_item(item))
        except Exception as e:  # never fail a customer request on a storage hiccup; the local file is the working copy
            store.log(demo_id, "storage-error", {"op": "put", "sk": sk, "error": str(e)[:200]})

    def put_session(self, demo_id: str, record: dict) -> None:
        super().put_session(demo_id, record)
        self._put(demo_id, f"session#{record['id']}", record)

    def get_session(self, demo_id: str, sid: str) -> dict | None:
        local = super().get_session(demo_id, sid)
        if local:
            return local
        try:
            item = self._table().get_item(Key={"demo_id": demo_id, "sk": f"session#{sid}"}).get("Item")
            return cloud._plain({k: v for k, v in item.items() if k not in ("sk", "kind", "t", "expires_at")}) if item else None
        except Exception:
            return None

    def list_sessions(self, demo_id: str, limit: int = 50) -> list[dict]:
        local = super().list_sessions(demo_id, limit)
        if local:
            return local
        try:  # a fresh box: the rows outlive the folder
            from boto3.dynamodb.conditions import Key
            r = self._table().query(KeyConditionExpression=Key("demo_id").eq(demo_id) & Key("sk").begins_with("session#"), ScanIndexForward=False, Limit=limit)
            return [_brief(cloud._plain(i)) for i in r.get("Items", [])]
        except Exception:
            return []

    def put_lead(self, demo_id: str, lead: dict) -> None:
        super().put_lead(demo_id, lead)
        self._put(demo_id, f"lead#{lead['id']}", lead)

    def media_url(self, demo_id: str, rel: str) -> str | None:
        """A pre-signed GET for a mirrored object; None (serve locally) when the mirror has not caught up yet."""
        try:
            if rel not in cloud._manifest(demo_id):
                return None
            return cloud._session().client("s3").generate_presigned_url("get_object", Params={"Bucket": cloud._state["bucket"], "Key": f"demos/{demo_id}/{rel}"}, ExpiresIn=config.MEDIA_SIGNED_URL_SECONDS)
        except Exception:
            return None

    def after_write(self, demo_id: str) -> None:
        cloud.sync_demo_async(demo_id)

    def ensure_table(self, log=print) -> None:
        """Create the sessions table (on-demand, TTL on expires_at) if it does not exist. Idempotent."""
        ddb = cloud._session().client("dynamodb")
        if self.table in ddb.list_tables().get("TableNames", []):
            log(f"table {self.table} exists")
        else:
            ddb.create_table(TableName=self.table, BillingMode="PAY_PER_REQUEST", KeySchema=[{"AttributeName": "demo_id", "KeyType": "HASH"}, {"AttributeName": "sk", "KeyType": "RANGE"}],
                             AttributeDefinitions=[{"AttributeName": "demo_id", "AttributeType": "S"}, {"AttributeName": "sk", "AttributeType": "S"}])
            ddb.get_waiter("table_exists").wait(TableName=self.table)
            log(f"table {self.table} created (on-demand)")
        try:
            ttl = ddb.describe_time_to_live(TableName=self.table)["TimeToLiveDescription"]["TimeToLiveStatus"]
            if ttl not in ("ENABLED", "ENABLING"):
                ddb.update_time_to_live(TableName=self.table, TimeToLiveSpecification={"Enabled": True, "AttributeName": "expires_at"})
                log(f"table {self.table}: TTL on expires_at ({config.SESSION_TTL_DAYS} days)")
        except Exception as e:
            log(f"table {self.table}: TTL not set ({str(e)[:80]})")

    def status(self) -> dict:
        return {"backend": self.name, "table": self.table, "signed_media_seconds": config.MEDIA_SIGNED_URL_SECONDS, **{k: v for k, v in cloud.status().items() if k in ("account", "region", "bucket", "why")}}


_backend: Local | None = None


def backend() -> Local:
    global _backend
    if _backend is None:
        if config.STORAGE_BACKEND == "aws" and cloud.enabled():
            _backend = Aws()
        else:
            _backend = Local()
            if config.STORAGE_BACKEND == "aws":
                _backend.fallback_reason = "aws requested but " + (cloud.status().get("why") or "cloud not connected")
    return _backend


def reset() -> None:
    global _backend
    _backend = None
