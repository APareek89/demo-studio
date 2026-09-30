"""Private S3 durability and immutable published assets, never an arbitrary proxy."""
from __future__ import annotations

import hashlib
import mimetypes
import os
from pathlib import Path
import secrets
import shutil


def _bucket() -> str:
    return os.getenv("PORTFOLIO_STORAGE_BUCKET", "").strip()


def _client():
    import boto3
    from botocore.config import Config
    return boto3.client("s3", region_name=os.getenv("AWS_REGION", "ap-south-1"),
                        config=Config(connect_timeout=5, read_timeout=60, retries={"max_attempts": 2}))


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _source(demo_id: str, rel: str) -> Path:
    from . import portfolio_auth as auth, store
    auth.safe_media_path(rel)
    path = store.media_path(demo_id, rel)
    if not path.is_file() or path.is_symlink():
        raise RuntimeError("Media file is unavailable")
    return path


def _cache(demo_id: str, row: dict) -> Path:
    from . import store
    suffix = Path(row["path"]).suffix.lower()
    if row["version"]:
        return store.path(demo_id, ".published-media", str(row["version"]), row["sha256"] + suffix)
    return store.media_path(demo_id, row["path"])


def _upload(path: Path, key: str, digest: str, content_type: str) -> str | None:
    if not _bucket():
        return None
    from boto3.s3.transfer import TransferConfig
    s3 = _client()
    s3.upload_file(str(path), _bucket(), key,
                   ExtraArgs={"ContentType": content_type, "Metadata": {"sha256": digest}, "ServerSideEncryption": "AES256"},
                   Config=TransferConfig(max_concurrency=2, multipart_chunksize=8 * 1024 * 1024))
    head = s3.head_object(Bucket=_bucket(), Key=key)
    version = head.get("VersionId")
    if not version or version == "null":
        raise RuntimeError("Media bucket must have versioning enabled")
    # Verify actual version bytes, not only the metadata we supplied ourselves.
    obj = s3.get_object(Bucket=_bucket(), Key=key, VersionId=version)
    received, total = hashlib.sha256(), 0
    try:
        for chunk in obj["Body"].iter_chunks(1024 * 1024):
            total += len(chunk)
            received.update(chunk)
    finally:
        obj["Body"].close()
    if received.hexdigest() != digest or total != path.stat().st_size:
        raise RuntimeError("Stored media integrity verification failed")
    return version


def prepare(demo_id: str, rel: str, *, version: int = 0) -> dict:
    from . import portfolio_auth as auth
    owner = auth.owner_for(demo_id)
    if not owner:
        raise RuntimeError("Media has no active creator")
    path = _source(demo_id, rel)
    digest, size = _sha(path), path.stat().st_size
    content_type = mimetypes.guess_type(rel)[0] or "application/octet-stream"
    suffix = path.suffix.lower()
    key = (f"published/demos/{demo_id}/{version}/{digest}{suffix}" if version else
           f"private/users/{owner}/demos/{demo_id}/{digest}{suffix}")
    row = {"demo_id": demo_id, "path": rel, "version": version, "sha256": digest,
           "byte_size": size, "content_type": content_type, "object_key": key if _bucket() else None,
           "object_version": None}
    target = _cache(demo_id, row)
    if version:
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_name("." + target.name + "." + secrets.token_hex(6))
        try:
            shutil.copyfile(path, temporary)
            if _sha(temporary) != digest:
                raise RuntimeError("Media changed during publication")
            temporary.replace(target)
        finally:
            temporary.unlink(missing_ok=True)
        path = target
    row["object_version"] = _upload(path, key, digest, content_type)
    return row


def save_record(conn, row: dict) -> None:
    conn.execute("""INSERT INTO media_objects(demo_id,path,version,sha256,byte_size,content_type,object_key,object_version)
      VALUES(%(demo_id)s,%(path)s,%(version)s,%(sha256)s,%(byte_size)s,%(content_type)s,%(object_key)s,%(object_version)s)
      ON CONFLICT(demo_id,path,version) DO UPDATE SET sha256=excluded.sha256,byte_size=excluded.byte_size,
      content_type=excluded.content_type,object_key=excluded.object_key,object_version=excluded.object_version""", row)


def persist_private(demo_id: str, rel: str) -> None:
    from . import portfolio_auth as auth
    if not auth.enabled():
        return
    path = _source(demo_id, rel)
    with auth.connection() as conn:
        existing = conn.execute("SELECT sha256,object_version FROM media_objects WHERE demo_id=%s AND path=%s AND version=0", (demo_id, rel)).fetchone()
    if existing and existing["sha256"] == _sha(path) and (not _bucket() or existing["object_version"]):
        return
    row = prepare(demo_id, rel)
    with auth.connection() as conn:
        save_record(conn, row)


def hydrate(demo_id: str, row: dict) -> Path:
    """Read only a DB-owned object key/version; verify bytes before atomic install."""
    from . import portfolio_auth as auth
    auth.safe_media_path(row["path"])
    path = _cache(demo_id, row)
    if path.is_file() and path.stat().st_size == row["byte_size"] and _sha(path) == row["sha256"]:
        return path
    if not _bucket() or not row.get("object_key") or not row.get("object_version"):
        raise RuntimeError("Stored media is unavailable")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name("." + path.name + "." + secrets.token_hex(6))
    obj = _client().get_object(Bucket=_bucket(), Key=row["object_key"], VersionId=row["object_version"])
    digest, size = hashlib.sha256(), 0
    try:
        with temporary.open("wb") as stream:
            for chunk in obj["Body"].iter_chunks(1024 * 1024):
                size += len(chunk)
                if size > row["byte_size"]:
                    raise RuntimeError("Stored media size mismatch")
                stream.write(chunk)
                digest.update(chunk)
        if size != row["byte_size"] or digest.hexdigest() != row["sha256"]:
            raise RuntimeError("Stored media integrity verification failed")
        temporary.replace(path)
    finally:
        obj["Body"].close()
        temporary.unlink(missing_ok=True)
    return path


def resolve(request, demo_id: str, rel: str) -> Path:
    from . import portfolio_auth as auth, store
    auth.require_media(request, demo_id, rel)
    user = auth.current_user(request)
    owner = bool(user and auth.owner_for(demo_id) == user["id"])
    publication = auth._publication(demo_id)
    with auth.connection() as conn:
        row = None
        if not owner and publication:
            declared = conn.execute("SELECT 1 FROM published_media WHERE demo_id=%s AND path=%s AND version=%s", (demo_id, rel, publication["published_version"])).fetchone()
            if declared:
                row = conn.execute("SELECT * FROM media_objects WHERE demo_id=%s AND path=%s AND version=%s", (demo_id, rel, publication["published_version"])).fetchone()
                if row is None:
                    raise RuntimeError("Published media version is unavailable")
        if row is None:
            row = conn.execute("SELECT * FROM media_objects WHERE demo_id=%s AND path=%s AND version=0", (demo_id, rel)).fetchone()
    if owner:
        file = store.media_path(demo_id, rel)
        if file.is_file():
            return file
    if row:
        return hydrate(demo_id, row)
    # Registered grants with no durable object are not an arbitrary local read.
    raise RuntimeError("Stored media is unavailable")
