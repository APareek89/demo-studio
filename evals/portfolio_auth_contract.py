"""Real PostgreSQL auth/owner/visitor checks; disposable loopback DB only, no providers."""
from __future__ import annotations

import os
from pathlib import Path
import secrets
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

os.environ.update(MOCK_LLM="1", PORTFOLIO_AUTH_ENABLED="1", CLOUD_SYNC="0", STORAGE_BACKEND="local",
                  PYTHON_DOTENV_DISABLED="1", PORTFOLIO_ALLOW_INSECURE_LOCAL="1", DATABASE_SSL="disable",
                  PUBLIC_BASE_URL="http://127.0.0.1:8950", AUTH_SECRET=secrets.token_hex(32))
dsn = os.environ.get("PORTFOLIO_TEST_DATABASE_URL", "postgresql://macbook@127.0.0.1:55443/demo_studio_auth_test")
from psycopg.conninfo import conninfo_to_dict
options = conninfo_to_dict(dsn)
if options.get("host") != "127.0.0.1" or options.get("dbname") != "demo_studio_auth_test":
    raise RuntimeError("This destructive synthetic test requires its dedicated loopback database")
os.environ["DATABASE_URL"] = dsn
temporary = tempfile.TemporaryDirectory(prefix="demo-auth-contract-")
os.environ.update(DEMO_STUDIO_DATA=str(Path(temporary.name) / "demos"), DEMO_STUDIO_GRAPH_DB=str(Path(temporary.name) / "graph.sqlite"))

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from server import portfolio_auth as auth, store
from server import runtime_live, livekit_trial

app = FastAPI()
auth.install(app)
app.include_router(runtime_live.router)
app.include_router(livekit_trial.router)


@app.get("/probe/owner/{demo_id}")
def owner_probe(demo_id: str, request: Request):
    auth.require_owner(request, demo_id)
    return {"ok": True}


@app.get("/probe/visit/{demo_id}/{session_id}")
def visit_probe(demo_id: str, session_id: str, request: Request):
    auth.require_visit(request, demo_id, session_id)
    return {"ok": True}


@app.get("/probe/media/{demo_id}/{rel:path}")
def media_probe(demo_id: str, rel: str, request: Request):
    auth.require_media(request, demo_id, rel)
    return {"ok": True}


class AccountsAndOwnership(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        auth.initialize()
        with auth.connection() as conn:
            conn.execute("TRUNCATE auth_rates,users CASCADE")
        cls.a, cls.b, cls.anon = [TestClient(app, base_url=os.environ["PUBLIC_BASE_URL"]) for _ in range(3)]
        cls.password = secrets.token_urlsafe(24)
        cls.header = {"Origin": os.environ["PUBLIC_BASE_URL"]}
        cls.users = []
        for client in (cls.a, cls.b):
            body = {"email": secrets.token_hex(8) + "@example.invalid", "password": cls.password}
            response = client.post("/api/auth/signup", json=body, headers=cls.header)
            if response.status_code != 200:
                raise AssertionError("Synthetic signup failed")
            cls.users.append(response.json()["user"])
        cls.demo = store.new_demo("Synthetic ownership test", owner_user_id=cls.users[0]["id"])["id"]
        cls.other = store.new_demo("Other synthetic owner", owner_user_id=cls.users[1]["id"])["id"]
        cls.snapshot = "kb_" + "a" * 24
        cls.bundle = {"id": cls.demo, "version": 1, "knowledge_snapshot_id": cls.snapshot,
                      "media": {"image": f"/media/{cls.demo}/sources/published.png"}}
        store.path(cls.demo, "sources/published.png").write_bytes(b"synthetic original public image")
        store.write_json(cls.demo, "bundle.json", cls.bundle)
        cls.visits = []
        for client in (cls.a, cls.b):
            response = client.post(f"/api/demos/{cls.demo}/run/visit", headers=cls.header)
            if response.status_code != 200:
                raise AssertionError("Synthetic visit bootstrap failed")
            cls.visits.append(response.json()["session_id"])

    def tearDown(self):
        with auth.connection() as conn:
            conn.execute("DELETE FROM auth_rates")

    def test_creator_owner_and_collection_boundaries(self):
        self.assertEqual(self.a.get(f"/probe/owner/{self.demo}").status_code, 200)
        self.assertEqual(self.b.get(f"/probe/owner/{self.demo}").status_code, 404)
        self.assertEqual(self.anon.get(f"/probe/owner/{self.demo}").status_code, 401)
        self.assertTrue({d["id"] for d in store.list_demos(self.users[0]["id"])} == {self.demo})
        with self.assertRaises(PermissionError):
            store.list_demos()
        with self.assertRaises(Exception):
            store.new_demo("No verified creator")

    def test_visit_isolation_and_concurrent_binding(self):
        mine = f"/probe/visit/{self.demo}/{self.visits[0]}"
        self.assertEqual(self.a.get(mine).status_code, 200)
        self.assertEqual(self.b.get(mine).status_code, 403)
        self.assertEqual(self.anon.get(mine).status_code, 403)
        response = self.a.post(f"/api/demos/{self.demo}/run/visit", headers=self.header)
        self.assertEqual(response.status_code, 200)
        self.assertNotEqual(response.json()["session_id"], self.visits[0])
        self.assertEqual(self.a.get(mine).status_code, 200)
        self.assertEqual(self.a.post(f"/api/demos/{self.other}/run/visit", headers=self.header).status_code, 404)

    def test_media_publication_and_private_audio(self):
        prefix = f"/probe/media/{self.demo}/"
        self.assertEqual(self.anon.get(prefix + "sources/published.png").status_code, 200)
        self.assertEqual(self.anon.get(prefix + "sources/draft.png").status_code, 404)
        self.assertEqual(self.a.get(prefix + "sources/draft.png").status_code, 200)
        req = SimpleNamespace(cookies=dict(self.a.cookies))
        rel = "audio/" + "f" * 20 + ".wav"
        store.path(self.demo, rel).write_bytes(b"synthetic visitor audio")
        auth.grant_response_audio(req, self.demo, self.visits[0], {"answer": f"/media/{self.demo}/{rel}"})
        self.assertEqual(self.b.get(prefix + rel).status_code, 404)
        with auth.connection() as conn:
            self.assertTrue(conn.execute("SELECT count(*) n FROM visit_media WHERE path=%s", (rel,)).fetchone()["n"] == 0)
        auth.grant_response_audio(req, self.demo, self.visits[0], {"result": {"audio": f"/media/{self.demo}/{rel}"}})
        self.assertEqual(self.b.get(prefix + rel).status_code, 404)
        self.assertEqual(self.anon.get(prefix + rel).status_code, 404)
        self.assertEqual(self.a.get(prefix + rel).status_code, 200)
        for path in ("../demo.json", "sources/../demo.json", "/demo.json", "audio/%2e%2e/private"):
            with self.assertRaises(Exception):
                auth.safe_media_path(path)

    def test_job_scope_rechecks_owner_and_absence(self):
        scope = auth.capture_job_scope(self.demo)
        self.assertEqual(auth.run_scoped_job(scope, lambda: "ok"), "ok")
        bad = auth.JobScope(self.demo, self.users[1]["id"])
        with self.assertRaises(RuntimeError):
            auth.run_scoped_job(bad, lambda: self.fail("Wrong owner entered job"))
        with self.assertRaises(RuntimeError):
            auth.capture_job_scope("dm_00000000")

    def test_websocket_visit_pin_and_cost_budget_precede_model(self):
        from unittest.mock import AsyncMock
        from starlette.websockets import WebSocketDisconnect
        endpoint = os.environ["PUBLIC_BASE_URL"].replace("http:", "ws:") + f"/api/demos/{self.demo}/run/live?session_id={self.visits[0]}"
        with patch.object(runtime_live, "run_turn", new_callable=AsyncMock) as model:
            with self.assertRaises(WebSocketDisconnect):
                with self.b.websocket_connect(endpoint, headers=self.header):
                    self.fail("Another visitor opened the socket")
            with self.a.websocket_connect(endpoint, headers=self.header) as socket:
                for forged in ({"snapshot_id": "kb_" + "b" * 24}, {"session_id": self.visits[1]}, {"demo_version": 99}):
                    socket.send_json({"type":"turn.ask", "question":"Synthetic question", **forged})
                    self.assertEqual(socket.receive_json()["code"], "visit_mismatch")
                socket.send_json({"type":"session.end"})
            self.assertEqual(model.await_count, 0)
            with auth.connection() as conn:
                key = auth._digest("rate:runtime-question:testclient")
                conn.execute("INSERT INTO auth_rates(key,window_start,count) VALUES(%s,now(),30)", (key,))
            with self.a.websocket_connect(endpoint, headers=self.header) as socket:
                socket.send_json({"type":"turn.ask", "question":"Synthetic question"})
                with self.assertRaises(WebSocketDisconnect):
                    socket.receive_json()
            self.assertEqual(model.await_count, 0)

    def test_cached_examples_reject_live_provider_transports(self):
        from unittest.mock import AsyncMock
        from starlette.websockets import WebSocketDisconnect
        store.update(self.demo, lambda record: record.update(example_kind="curated_cached", status="ready"))
        try:
            with patch.object(runtime_live, "run_turn", new_callable=AsyncMock) as model:
                with self.assertRaises(WebSocketDisconnect) as rejected:
                    with self.a.websocket_connect(os.environ["PUBLIC_BASE_URL"].replace("http:", "ws:") + f"/api/demos/{self.demo}/run/live?session_id={self.visits[0]}", headers=self.header):
                        self.fail("A cached-only example opened live voice")
                self.assertEqual(rejected.exception.code, 1008)
                self.assertIn("cached example", rejected.exception.reason)
                self.assertEqual(model.await_count, 0)
            read_json = store.read_json
            def published(demo_id, name):
                if demo_id == self.demo and name == "bundle.json":
                    return {**self.bundle, "runtime":{"version":1}}
                if demo_id == self.demo and name == f"knowledge/snapshots/{self.snapshot}.json":
                    return {"id":self.snapshot}
                return read_json(demo_id, name)
            with patch.object(livekit_trial,"_authorize"), patch.object(store,"read_json",side_effect=published), \
                 patch.object(livekit_trial,"_configuration",side_effect=AssertionError("Provider configuration reached")), \
                 patch.object(livekit_trial,"_sdk",side_effect=AssertionError("Provider SDK reached")):
                response=self.a.post(f"/api/demos/{self.demo}/run/livekit/token", json={"session_id":self.visits[0]}, headers=self.header)
                self.assertEqual(response.status_code,409)
                self.assertIn("cached example",response.json()["detail"])
        finally:
            store.update(self.demo, lambda record: record.pop("example_kind",None))

    def test_owner_budget_is_independent_of_peer(self):
        auth.limit_owner_action(self.users[0]["id"], "fixture", 1, 3600)
        with self.assertRaises(Exception):
            auth.limit_owner_action(self.users[0]["id"], "fixture", 1, 3600)
        auth.limit_owner_action(self.users[1]["id"], "fixture", 1, 3600)

    def test_livekit_rejects_other_visit_and_forged_publication_before_sdk(self):
        store.update(self.demo, lambda record: record.update(status="ready"))
        read_json = store.read_json
        def published(demo_id, name):
            if demo_id == self.demo and name == "bundle.json":
                return {**self.bundle,"runtime":{"version":1}}
            if demo_id == self.demo and name == f"knowledge/snapshots/{self.snapshot}.json":
                return {"id":self.snapshot}
            return read_json(demo_id,name)
        with patch.object(livekit_trial,"_authorize"), patch.object(store,"read_json",side_effect=published), \
             patch.object(livekit_trial,"_configuration",side_effect=AssertionError("Provider configuration reached")), \
             patch.object(livekit_trial,"_sdk",side_effect=AssertionError("Provider SDK reached")):
            endpoint=f"/api/demos/{self.demo}/run/livekit/token"
            self.assertEqual(self.b.post(endpoint,json={"session_id":self.visits[0]},headers=self.header).status_code,403)
            for forged in ({"knowledge_snapshot_id":"kb_"+"b"*24},{"demo_version":99}):
                self.assertEqual(self.a.post(endpoint,json={"session_id":self.visits[0],**forged},headers=self.header).status_code,409)

    def test_immutable_public_media_and_verified_hydration(self):
        from server import portfolio_media as media
        rel = "sources/published.png"
        request = SimpleNamespace(cookies={})
        original = auth.media_file(request, self.demo, rel).read_bytes()
        store.path(self.demo, rel).write_bytes(b"a changed private draft at the same source path")
        media.persist_private(self.demo, rel)
        self.assertTrue(auth.media_file(request, self.demo, rel).read_bytes() == original)
        with auth.connection() as conn:
            row = conn.execute("SELECT * FROM media_objects WHERE demo_id=%s AND path=%s AND version=1", (self.demo, rel)).fetchone()
            conn.execute("DELETE FROM media_objects WHERE demo_id=%s AND path=%s AND version=1", (self.demo, rel))
        try:
            with self.assertRaises(Exception):
                auth.media_file(request, self.demo, rel)
        finally:
            with auth.connection() as conn:
                media.save_record(conn, row)
        cache = media._cache(self.demo, row)
        class Body:
            def __init__(self, content): self.content = content
            def iter_chunks(self, size): yield self.content
            def close(self): pass
        from unittest.mock import Mock
        client = Mock()
        remote = {**row, "object_key": "published/synthetic", "object_version": "synthetic-version"}
        with patch.object(media, "_bucket", return_value="synthetic-private-bucket"), patch.object(media, "_client", return_value=client):
            cache.unlink()
            client.get_object.return_value = {"Body": Body(original)}
            self.assertTrue(media.hydrate(self.demo, remote).read_bytes() == original)
            self.assertEqual(client.get_object.call_args.kwargs["VersionId"], "synthetic-version")
            cache.unlink()
            client.get_object.return_value = {"Body": Body(b"corrupt content")}
            with self.assertRaises(RuntimeError):
                media.hydrate(self.demo, remote)
            self.assertFalse(cache.exists())
        cache.write_bytes(original)

    def test_origin_rate_and_password_bounds(self):
        response = self.anon.post("/api/auth/signin", json={"email": self.users[0]["email"], "password": self.password})
        self.assertEqual(response.status_code, 403)
        for password in ("short", "€" * 25):
            response = self.anon.post("/api/auth/signup", headers=self.header, json={"email": "synthetic@example.invalid", "password": password})
            self.assertEqual(response.status_code, 400)
        for _ in range(16):
            response = self.anon.post("/api/auth/signin", headers=self.header, json={"email": "synthetic@example.invalid", "password": "not-a-real-password"})
        self.assertEqual(response.status_code, 429)

    def test_password_bcrypt_signin_and_revocation(self):
        client = TestClient(app, base_url=os.environ["PUBLIC_BASE_URL"])
        response = client.post("/api/auth/signin", headers=self.header, json={"email": self.users[0]["email"].upper(), "password": self.password})
        self.assertEqual(response.status_code, 200)
        self.assertIn("httponly", response.headers["set-cookie"].lower())
        self.assertIn("samesite=lax", response.headers["set-cookie"].lower())
        old = dict(client.cookies)
        self.assertTrue(client.get("/api/auth/session").json()["authenticated"])
        self.assertEqual(client.post("/api/auth/signout", headers=self.header).status_code, 200)
        self.assertFalse(client.get("/api/auth/session", cookies=old).json()["authenticated"])
        with auth.connection() as conn:
            row = conn.execute("SELECT password_hash FROM users WHERE id=%s", (self.users[0]["id"],)).fetchone()
        self.assertTrue(row["password_hash"].startswith("$2b$"))

    def test_publication_failure_retains_previous_bundle(self):
        with patch.object(auth, "mark_published", side_effect=RuntimeError("Synthetic registry failure")):
            with self.assertRaises(RuntimeError):
                store.write_json(self.demo, "bundle.json", {**self.bundle, "version": 2})
        self.assertTrue(store.read_json(self.demo, "bundle.json") == self.bundle)
        self.assertTrue(auth.is_public_demo(self.demo))

    def test_duplicate_strips_customer_records_and_unpublished_access(self):
        store.write_json(self.demo, "sessions/private.json", {"private": "synthetic visitor"})
        store.write_json(self.demo, "faq.json", {"entries": [{"source": "customer", "session_id": self.visits[0]}]})
        runtime = store.path(self.demo, "audio", "e" * 20 + ".wav")
        runtime.write_bytes(b"synthetic runtime audio")
        copied = store.duplicate_demo(self.demo, owner_user_id=self.users[0]["id"])
        self.assertFalse(store.path(copied["id"], "sessions/private.json").exists())
        self.assertFalse(store.path(copied["id"], "audio", runtime.name).exists())
        self.assertFalse(store.read_json(copied["id"], "faq.json")["entries"])
        self.assertFalse(auth.is_public_demo(copied["id"]))
        self.assertFalse(any(copied["approvals"].values()))
        with self.assertRaises(PermissionError):
            store.duplicate_demo(self.demo, owner_user_id=self.users[1]["id"])

    def test_tls_configuration_fails_closed(self):
        with patch.dict(os.environ, {"DATABASE_SSL": "require", "DATABASE_SSL_CA_FILE": ""}):
            with self.assertRaises(RuntimeError):
                with auth.connection():
                    self.fail("Missing CA accepted")


if __name__ == "__main__":
    unittest.main()
