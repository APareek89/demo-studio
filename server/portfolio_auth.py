"""Hosted account and publication boundaries, separate from the pure demo store.

Off only for explicit local fixture runs. Hosted mode never falls back when its
database, TLS, cookie or session configuration is invalid. Background jobs carry
immutable registry scopes instead of relying on HTTP ContextVars.
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import hashlib
import hmac
import json
import os
from pathlib import Path, PurePosixPath
import re
import secrets
import threading
import time
from urllib.parse import urlsplit
import uuid

from fastapi import APIRouter, HTTPException, Request, Response
from starlette.concurrency import run_in_threadpool

CREATOR_COOKIE = "demo_creator"
VISITOR_COOKIE = "demo_visitor"
SESSION_SECONDS = 7 * 86400
VISIT_SECONDS = 12 * 3600
_DEMO = re.compile(r"dm_[a-z0-9]{8}\Z")
_SESSION = re.compile(r"s_[a-f0-9]{32}\Z")
_TOKEN = re.compile(r"[A-Za-z0-9_-]{40,64}\Z")
_MEDIA_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".avif", ".bmp", ".ico",
                   ".mp3", ".wav", ".ogg", ".m4a", ".aac", ".flac", ".opus", ".mp4", ".webm", ".mov", ".m4v"}
_dummy_password_hash = None
# Gallery requests share the app role's finite PostgreSQL connection allowance.
# Bound connection creation (including failed connects), not authorization results:
# each request still checks its current session and owner using a fresh transaction.
_connection_slots = threading.BoundedSemaphore(6)
_CONNECTION_WAIT_SECONDS = 10


def enabled() -> bool:
    setting = os.getenv("PORTFOLIO_AUTH_ENABLED")
    if setting not in {None, "0", "1"}:
        raise RuntimeError("Invalid hosted authentication setting")
    if setting == "0" and os.getenv("MOCK_LLM") != "1":
        raise RuntimeError("Authentication can only be disabled in an explicit mock fixture")
    return setting == "1" or (setting is None and os.getenv("MOCK_LLM") != "1")


def _base() -> str:
    value = os.getenv("PUBLIC_BASE_URL", "").rstrip("/")
    parsed = urlsplit(value)
    local = (parsed.hostname in {"localhost", "127.0.0.1", "::1"}
             and os.getenv("PORTFOLIO_ALLOW_INSECURE_LOCAL") == "1")
    if (not parsed.netloc or parsed.username or parsed.query or parsed.fragment or parsed.path
            or parsed.scheme not in ({"http", "https"} if local else {"https"})):
        raise RuntimeError("Hosted auth requires a valid HTTPS PUBLIC_BASE_URL")
    return value


def _secure() -> bool:
    return urlsplit(_base()).scheme == "https"


def _digest(value: str) -> str:
    secret = os.getenv("AUTH_SECRET", "")
    if len(secret) < 32:
        raise RuntimeError("Hosted auth requires AUTH_SECRET of at least 32 characters")
    return hmac.new(secret.encode(), value.encode(), hashlib.sha256).hexdigest()


@contextmanager
def connection():
    import psycopg
    from psycopg.conninfo import conninfo_to_dict
    from psycopg.rows import dict_row
    dsn = os.getenv("DATABASE_URL", "")
    if not dsn:
        raise RuntimeError("Hosted auth requires DATABASE_URL")
    options = conninfo_to_dict(dsn)
    local_test = (options.get("host") in {"localhost", "127.0.0.1", "::1"}
                  and os.getenv("PORTFOLIO_ALLOW_INSECURE_LOCAL") == "1"
                  and os.getenv("DATABASE_SSL") == "disable")
    if local_test:
        options.update(sslmode="disable")
    else:
        ca = os.getenv("DATABASE_SSL_CA_FILE", "")
        if not ca or not Path(ca).is_file():
            raise RuntimeError("Hosted auth requires a PostgreSQL CA file")
        options.update(sslmode="verify-full", sslrootcert=ca)
    options.update(connect_timeout=5, application_name="demo-studio-auth")
    if not _connection_slots.acquire(timeout=_CONNECTION_WAIT_SECONDS):
        raise RuntimeError("Account storage is busy; please try again")
    try:
        with psycopg.connect(**options, row_factory=dict_row) as conn:
            yield conn
    except psycopg.Error as exc:
        # Never expose DB URIs, credentials or row values in HTTP error strings.
        raise RuntimeError("Account storage is unavailable") from None
    finally:
        _connection_slots.release()


def initialize() -> None:
    if not enabled():
        return
    _base()
    _digest("configuration-check")
    with connection() as conn:
        conn.execute((Path(__file__).resolve().parents[1] / "migrations/001_portfolio_auth.sql").read_text())


def _user(row) -> dict | None:
    return {"id": str(row["id"]), "email": row["email"], "name": row["name"]} if row else None


def current_user(request) -> dict | None:
    if not enabled():
        return None
    token = request.cookies.get(CREATOR_COOKIE, "")
    if not _TOKEN.fullmatch(token):
        return None
    with connection() as conn:
        row = conn.execute("SELECT u.id,u.email,u.name FROM auth_sessions s JOIN users u ON u.id=s.user_id WHERE token_hash=%s AND expires_at>now()", (_digest(token),)).fetchone()
    return _user(row)


def require_user(request) -> dict:
    if not enabled():
        return {"id": "fixture", "email": "", "name": ""}
    user = current_user(request)
    if not user:
        raise HTTPException(401, "Sign in to continue")
    return user


def owner_for(demo_id: str, *, include_creating: bool = False) -> str | None:
    if not enabled():
        return "fixture"
    if not _DEMO.fullmatch(demo_id):
        return None
    states = ["active", "creating"] if include_creating else ["active"]
    with connection() as conn:
        row = conn.execute("SELECT owner_user_id FROM demo_owners WHERE demo_id=%s AND state=ANY(%s)", (demo_id, states)).fetchone()
    return str(row["owner_user_id"]) if row else None


def require_owner(request, demo_id: str) -> dict:
    user = require_user(request)
    if enabled() and owner_for(demo_id) != user["id"]:
        raise HTTPException(404, "Demo not found")
    return user


def owned_demo_ids(user_id: str) -> set[str]:
    if not enabled():
        from . import store
        return {demo["id"] for demo in store.list_demos()}
    with connection() as conn:
        rows = conn.execute("SELECT demo_id FROM demo_owners WHERE owner_user_id=%s AND state='active'", (user_id,)).fetchall()
    return {row["demo_id"] for row in rows}


def reserve_demo(owner_id: str | None, demo_id: str) -> None:
    if not enabled():
        return
    if not owner_id or not _DEMO.fullmatch(demo_id):
        raise HTTPException(401, "A verified creator is required")
    try:
        uuid.UUID(owner_id)
    except (ValueError, TypeError):
        raise HTTPException(401, "A verified creator is required") from None
    with connection() as conn:
        conn.execute("INSERT INTO demo_owners(demo_id,owner_user_id) VALUES(%s,%s)", (demo_id, owner_id))


def activate_demo(owner_id: str, demo_id: str) -> None:
    if not enabled():
        return
    with connection() as conn:
        row = conn.execute("UPDATE demo_owners SET state='active' WHERE demo_id=%s AND owner_user_id=%s AND state='creating' RETURNING demo_id", (demo_id, owner_id)).fetchone()
    if not row:
        raise RuntimeError("Demo ownership activation failed")


def retire_demo(demo_id: str) -> None:
    if not enabled():
        return
    with connection() as conn:
        conn.execute("UPDATE demo_owners SET state='deleted' WHERE demo_id=%s", (demo_id,))


@dataclass(frozen=True)
class JobScope:
    demo_id: str
    owner_id: str


def capture_job_scope(demo_id: str) -> JobScope:
    owner = owner_for(demo_id)
    if owner is None:
        raise RuntimeError("Demo has no active owner")
    return JobScope(demo_id, owner)


def run_scoped_job(scope: JobScope, function, *args, **kwargs):
    if not isinstance(scope, JobScope) or owner_for(scope.demo_id) != scope.owner_id:
        raise RuntimeError("Demo ownership changed before the job started")
    return function(*args, **kwargs)


def safe_media_path(rel: str) -> str:
    if (not isinstance(rel, str) or not rel or len(rel) > 1024 or rel.startswith("/")
            or "\\" in rel or "%" in rel or any(ord(c) < 32 for c in rel)):
        raise HTTPException(404, "Media not found")
    path = PurePosixPath(rel)
    if any(part in {"", ".", ".."} for part in rel.split("/")) or str(path) != rel:
        raise HTTPException(404, "Media not found")
    return rel


def publication_media(demo_id: str, bundle: dict) -> set[str]:
    prefix = f"/media/{demo_id}/"
    result = set()
    def visit(value):
        if isinstance(value, str) and value.startswith(prefix):
            rel = safe_media_path(value[len(prefix):])
            if PurePosixPath(rel).suffix.lower() in _MEDIA_SUFFIXES:
                result.add(rel)
        elif isinstance(value, dict):
            for item in value.values():
                visit(item)
        elif isinstance(value, list):
            for item in value:
                visit(item)
    visit(bundle)
    return result


def prepare_publication(demo_id: str, bundle: dict) -> list[dict]:
    if not enabled():
        return []
    if type(bundle.get("version")) is not int or bundle["version"] < 1 or bundle.get("id") != demo_id:
        raise RuntimeError("Invalid publication identity")
    from . import portfolio_media, store
    # Original inputs remain private even when selected derived assets publish.
    for source in store.load(demo_id).get("sources", []):
        if source.get("path"):
            portfolio_media.persist_private(demo_id, source["path"])
    return [portfolio_media.prepare(demo_id, rel, version=bundle["version"])
            for rel in sorted(publication_media(demo_id, bundle))]


def mark_published(demo_id: str, bundle: dict, prepared: list[dict] | None = None) -> None:
    """Called only after normal Bundle validates approvals, citations and duration."""
    if not enabled():
        return
    version, snapshot = bundle.get("version"), bundle.get("knowledge_snapshot_id")
    if (type(version) is not int or version < 1 or bundle.get("id") != demo_id
            or not isinstance(snapshot, str) or not re.fullmatch(r"kb_[a-f0-9]{24}", snapshot)):
        raise RuntimeError("Invalid publication identity")
    media = publication_media(demo_id, bundle)
    from . import portfolio_media
    if prepared is None:
        prepared = prepare_publication(demo_id, bundle)
    with connection() as conn:
        row = conn.execute("UPDATE demo_owners SET published_version=%s,snapshot_id=%s,published_at=now() WHERE demo_id=%s AND state='active' RETURNING demo_id", (version, snapshot, demo_id)).fetchone()
        if not row:
            raise RuntimeError("Publication has no active creator")
        for rel in media:
            conn.execute("INSERT INTO published_media(demo_id,version,path) VALUES(%s,%s,%s) ON CONFLICT DO NOTHING", (demo_id, version, rel))
        for item in prepared:
            portfolio_media.save_record(conn, item)


def _publication(demo_id: str) -> dict | None:
    if not _DEMO.fullmatch(demo_id):
        return None
    from . import store
    if not enabled():
        bundle = store.read_json(demo_id, "bundle.json") or {}
        return {"published_version": bundle.get("version", 0), "snapshot_id": bundle.get("knowledge_snapshot_id", "")} if bundle else None
    with connection() as conn:
        row = conn.execute("SELECT published_version,snapshot_id FROM demo_owners WHERE demo_id=%s AND state='active' AND published_version>0", (demo_id,)).fetchone()
    if not row:
        return None
    bundle = store.read_json(demo_id, "bundle.json") or {}
    if (bundle.get("version"), bundle.get("knowledge_snapshot_id")) != (row["published_version"], row["snapshot_id"]):
        return None
    return row


def is_public_demo(demo_id: str) -> bool:
    return _publication(demo_id) is not None


def _visitor(request) -> str | None:
    token = request.cookies.get(VISITOR_COOKIE, "")
    return _digest(token) if _TOKEN.fullmatch(token) else None


def require_visit(request, demo_id: str, session_id: str) -> dict:
    if not enabled():
        return {"session_id": session_id, "demo_id": demo_id}
    if not isinstance(session_id, str) or not _SESSION.fullmatch(session_id):
        raise HTTPException(403, "Start a new published demo visit")
    visitor = _visitor(request)
    publication = _publication(demo_id)
    if not visitor or not publication:
        raise HTTPException(403, "Start a new published demo visit")
    with connection() as conn:
        row = conn.execute("SELECT session_id,demo_id,published_version,snapshot_id FROM public_visits WHERE session_id=%s AND demo_id=%s AND visitor_hash=%s AND expires_at>now()", (session_id, demo_id, visitor)).fetchone()
    if not row:
        raise HTTPException(403, "This visit is not available")
    if (row["published_version"], row["snapshot_id"]) != (publication["published_version"], publication["snapshot_id"]):
        raise HTTPException(409, "The published demo changed; start a new visit")
    return row


def grant_visit_media(request, demo_id: str, session_id: str, rel: str) -> None:
    if not enabled():
        return
    require_visit(request, demo_id, session_id)
    rel = safe_media_path(rel)
    if not rel.startswith("audio/") or PurePosixPath(rel).suffix.lower() not in _MEDIA_SUFFIXES:
        raise HTTPException(404, "Media not found")
    from . import portfolio_media
    portfolio_media.persist_private(demo_id, rel)
    with connection() as conn:
        conn.execute("INSERT INTO visit_media(session_id,demo_id,path) VALUES(%s,%s,%s) ON CONFLICT DO NOTHING", (session_id, demo_id, rel))


def grant_response_audio(request, demo_id: str, session_id: str, event) -> None:
    """Grant only server-returned audio fields, never free-form answer text URLs."""
    if not enabled():
        return
    prefix = f"/media/{demo_id}/"
    if isinstance(event, dict):
        for key, value in event.items():
            if key == "audio" and isinstance(value, str) and value.startswith(prefix):
                grant_visit_media(request, demo_id, session_id, value[len(prefix):])
            elif isinstance(value, (dict, list)):
                grant_response_audio(request, demo_id, session_id, value)
    elif isinstance(event, list):
        for value in event:
            grant_response_audio(request, demo_id, session_id, value)


def require_media(request, demo_id: str, rel: str) -> None:
    if not enabled():
        return
    rel = safe_media_path(rel)
    user = current_user(request)
    if user and owner_for(demo_id) == user["id"]:
        return
    publication = _publication(demo_id)
    visitor = _visitor(request)
    with connection() as conn:
        if publication and conn.execute("SELECT 1 FROM published_media WHERE demo_id=%s AND version=%s AND path=%s", (demo_id, publication["published_version"], rel)).fetchone():
            return
        if visitor and publication and conn.execute("SELECT 1 FROM visit_media m JOIN public_visits v USING(session_id) WHERE m.demo_id=%s AND m.path=%s AND v.visitor_hash=%s AND v.expires_at>now() AND v.published_version=%s AND v.snapshot_id=%s", (demo_id, rel, visitor, publication["published_version"], publication["snapshot_id"])).fetchone():
            return
    raise HTTPException(404, "Media not found")


def media_file(request, demo_id: str, rel: str) -> Path:
    from . import portfolio_media, store
    if not enabled():
        return store.media_path(demo_id, rel)
    try:
        return portfolio_media.resolve(request, demo_id, rel)
    except RuntimeError:
        raise HTTPException(503, "Stored media is temporarily unavailable") from None


def check_origin(request) -> None:
    if not enabled():
        return
    if request.headers.get("origin") != _base():
        raise HTTPException(403, "A matching application origin is required")
    if request.headers.get("sec-fetch-site", "same-origin") not in {"same-origin", "none"}:
        raise HTTPException(403, "Cross-site request denied")


def _rate(request, action: str, limit: int = 15, seconds: int = 900) -> None:
    # The socket peer is authoritative; deployment trust-forwarding is configured
    # only for the local reverse proxy, never a client-supplied arbitrary header.
    peer = request.client.host if request.client else "unknown"
    _rate_key(_digest(f"rate:{action}:{peer}"), limit, seconds)


def _rate_key(key: str, limit: int, seconds: int) -> None:
    with connection() as conn:
        row = conn.execute("""INSERT INTO auth_rates(key,window_start,count) VALUES(%s,now(),1)
          ON CONFLICT(key) DO UPDATE SET
          count=CASE WHEN auth_rates.window_start<now()-(%s*interval '1 second') THEN 1 ELSE auth_rates.count+1 END,
          window_start=CASE WHEN auth_rates.window_start<now()-(%s*interval '1 second') THEN now() ELSE auth_rates.window_start END
          RETURNING count""", (key, seconds, seconds)).fetchone()
    if row["count"] > limit:
        raise HTTPException(429, "Too many attempts; try again later", headers={"Retry-After": str(seconds)})


def limit_action(request, action: str, limit: int = 30, seconds: int = 900) -> None:
    if enabled():
        _rate(request, action, limit, seconds)


def limit_owner_action(user_id: str, action: str, limit: int = 10, seconds: int = 3600) -> None:
    """Budget a verified creator across peers, independently of the IP budget."""
    if enabled():
        if not user_id:
            raise HTTPException(401, "Sign in to continue")
        _rate_key(_digest(f"owner-rate:{action}:{user_id}"), limit, seconds)


async def _body(request: Request) -> dict:
    raw = bytearray()
    async for part in request.stream():
        raw.extend(part)
        if len(raw) > 8192:
            raise HTTPException(413, "Account request is too large")
    try:
        result = json.loads(raw)
    except (ValueError, RecursionError):
        raise HTTPException(400, "Invalid account request") from None
    if not isinstance(result, dict):
        raise HTTPException(400, "Invalid account request")
    return result


def _credentials(body: dict) -> tuple[str, str]:
    email, password = body.get("email"), body.get("password")
    if not isinstance(email, str) or not isinstance(password, str):
        raise HTTPException(400, "Enter an email and password")
    email = email.strip().lower()
    if len(email) > 254 or not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
        raise HTTPException(400, "Enter a valid email")
    if len(password) < 12 or len(password.encode()) > 72:
        raise HTTPException(400, "Use a password with at least 12 characters and at most 72 bytes")
    return email, password


def _cookie(response: Response, name: str, token: str, seconds: int) -> None:
    response.set_cookie(name, token, max_age=seconds, httponly=True, secure=_secure(), samesite="lax", path="/")
    response.headers["Cache-Control"] = "no-store"


def _session(response: Response, user_id: str) -> None:
    token = secrets.token_urlsafe(32)
    with connection() as conn:
        conn.execute("INSERT INTO auth_sessions(token_hash,user_id,expires_at) VALUES(%s,%s,now()+(%s*interval '1 second'))", (_digest(token), user_id, SESSION_SECONDS))
    _cookie(response, CREATOR_COOKIE, token, SESSION_SECONDS)


router = APIRouter()


@router.get("/api/auth/session")
def session_status(request: Request, response: Response):
    response.headers["Cache-Control"] = "no-store"
    user = current_user(request)
    return {"enabled": enabled(), "authenticated": bool(user), "user": user}


@router.post("/api/auth/signup")
async def signup(request: Request, response: Response):
    if not enabled():
        raise HTTPException(404, "Accounts are disabled in the local fixture")
    check_origin(request)
    await run_in_threadpool(_rate, request, "account")
    email, password = _credentials(await _body(request))
    import bcrypt
    password_hash = (await run_in_threadpool(bcrypt.hashpw, password.encode(), bcrypt.gensalt(rounds=12))).decode()
    user_id = str(uuid.uuid4())
    def create():
        with connection() as conn:
            return conn.execute("INSERT INTO users(id,email,password_hash) VALUES(%s,%s,%s) ON CONFLICT DO NOTHING RETURNING id,email,name", (user_id, email, password_hash)).fetchone()
    row = await run_in_threadpool(create)
    if not row:
        raise HTTPException(409, "An account cannot be created with these details")
    await run_in_threadpool(_session, response, user_id)
    return {"enabled": True, "authenticated": True, "user": _user(row)}


@router.post("/api/auth/signin")
async def signin(request: Request, response: Response):
    if not enabled():
        raise HTTPException(404, "Accounts are disabled in the local fixture")
    check_origin(request)
    await run_in_threadpool(_rate, request, "account")
    email, password = _credentials(await _body(request))
    def authenticate():
        import bcrypt
        global _dummy_password_hash
        with connection() as conn:
            row = conn.execute("SELECT id,email,name,password_hash FROM users WHERE lower(email)=%s", (email,)).fetchone()
        if _dummy_password_hash is None:
            _dummy_password_hash = bcrypt.hashpw(secrets.token_bytes(32), bcrypt.gensalt(rounds=12))
        stored = row["password_hash"].encode() if row else _dummy_password_hash
        try:
            valid = bcrypt.checkpw(password.encode(), stored)
        except ValueError:
            valid = False
        return row if row and valid else None
    row = await run_in_threadpool(authenticate)
    if not row:
        raise HTTPException(401, "Email or password is incorrect")
    await run_in_threadpool(_session, response, str(row["id"]))
    return {"enabled": True, "authenticated": True, "user": _user(row)}


@router.post("/api/auth/signout")
def signout(request: Request, response: Response):
    if enabled():
        check_origin(request)
        token = request.cookies.get(CREATOR_COOKIE, "")
        if _TOKEN.fullmatch(token):
            with connection() as conn:
                conn.execute("DELETE FROM auth_sessions WHERE token_hash=%s", (_digest(token),))
        response.delete_cookie(CREATOR_COOKIE, path="/", secure=_secure(), httponly=True, samesite="lax")
    response.headers["Cache-Control"] = "no-store"
    return {"enabled": enabled(), "authenticated": False, "user": None}


@router.post("/api/demos/{demo_id}/run/visit")
def new_visit(demo_id: str, request: Request, response: Response):
    if not enabled():
        return {"session_id": "s_" + uuid.uuid4().hex}
    check_origin(request)
    _rate(request, "visit", 60)
    publication = _publication(demo_id)
    if not publication:
        raise HTTPException(404, "Published demo not found")
    token = request.cookies.get(VISITOR_COOKIE, "")
    if not _TOKEN.fullmatch(token):
        token = secrets.token_urlsafe(32)
    session_id = "s_" + uuid.uuid4().hex
    with connection() as conn:
        conn.execute("INSERT INTO public_visits(session_id,demo_id,visitor_hash,published_version,snapshot_id,expires_at) VALUES(%s,%s,%s,%s,%s,now()+(%s*interval '1 second'))", (session_id, demo_id, _digest(token), publication["published_version"], publication["snapshot_id"], VISIT_SECONDS))
    _cookie(response, VISITOR_COOKIE, token, VISIT_SECONDS)
    return {"session_id": session_id}


def install(app) -> None:
    app.include_router(router)
    app.router.add_event_handler("startup", initialize)
