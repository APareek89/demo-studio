"""Hosted LiveKit policy, grants and ownership; isolated data, fake RTC, no sockets."""
import asyncio
import base64
from contextlib import ExitStack
from datetime import timedelta
import json
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch

scratch = tempfile.TemporaryDirectory(prefix="livekit-hosted-contract-")
os.environ.update(MOCK_LLM="1", CLOUD_SYNC="0", STORAGE_BACKEND="local",
                  DEMO_STUDIO_DATA=scratch.name, DEMO_STUDIO_GRAPH_DB=str(Path(scratch.name) / "graph.sqlite"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fastapi import HTTPException, Response
from starlette.requests import Request
from server import livekit_trial as transport, store, knowledge, runtime_graph

ORIGIN = "https://demo.example"
PUBLIC = "wss://rtc.example"
SETTINGS = {"LIVEKIT_ENABLED":"1", "LIVEKIT_TRIAL_ENABLED":"0", "LIVEKIT_URL":PUBLIC,
            "LIVEKIT_INTERNAL_URL":"ws://127.0.0.1:7880", "LIVEKIT_ALLOWED_ORIGINS":ORIGIN,
            "LIVEKIT_API_KEY":"test-key", "LIVEKIT_API_SECRET":"contract-secret-not-for-production-123",
            "LIVEKIT_MAX_ROOMS":"4", "LIVEKIT_ICE_TRANSPORT_POLICY":"all"}


class Room:
    gate = None
    on_connect = None
    def __init__(self):
        self.callbacks = {}
        self.local_participant = self
        self.disconnected = False
    def on(self, event, callback): self.callbacks[event] = callback
    async def connect(self, url, token, options):
        self.url, self.token, self.options = url, token, options
        if Room.gate: await Room.gate.wait()
        if Room.on_connect: Room.on_connect()
    async def disconnect(self): self.disconnected = True
    async def publish_data(self, *args, **kwargs): pass


class Token:
    created = []
    def __init__(self, key, secret):
        self.key, self.secret = key, secret
        self.created.append(self)
    def with_identity(self, identity): self.identity = identity; return self
    def with_ttl(self, ttl): self.ttl = ttl; return self
    def with_grants(self, grants): self.grants = grants; return self
    def to_jwt(self): return "fake-token-" + self.identity


RTC = NS(Room=Room, RoomOptions=lambda **kw:NS(**kw), RtcConfiguration=lambda **kw:NS(**kw),
         IceServer=lambda **kw:NS(**kw), DataPacketKind=NS(KIND_RELIABLE=0))
API = NS(AccessToken=Token, VideoGrants=lambda **kw:NS(**kw))


def request(body=None, *, origin=ORIGIN, client="198.51.100.20", extra=None, raw=None, receive=None):
    headers = {"host":"untrusted-proxy-host", **(extra or {})}
    if origin is not None: headers["origin"] = origin
    raw = json.dumps(body if body is not None else {"session_id":"s_hosted"}).encode() if raw is None else raw
    async def default_receive(): return {"type":"http.request", "body":raw}
    return Request({"type":"http", "method":"POST", "scheme":"http", "path":"/token", "query_string":b"",
                    "client":(client,1234), "server":("127.0.0.1",8877),
                    "headers":[(key.encode(),value.encode()) for key,value in headers.items()]}, receive or default_receive)


async def idle_runtime(*args):
    await asyncio.Event().wait()


class HostedTransport(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.patches = ExitStack()
        for target in ("socket.create_connection", "socket.getaddrinfo", "socket.socket.connect", "socket.socket.connect_ex", "socket.socket.sendto"):
            self.patches.enter_context(patch(target, side_effect=AssertionError("Hosted contract blocks sockets")))
        self.patches.enter_context(patch.dict(os.environ, SETTINGS))
        self.sdk = self.patches.enter_context(patch.object(transport, "_sdk", return_value=(API,RTC)))
        self.patches.enter_context(patch.object(transport.runtime_live, "live", idle_runtime))
        transport._token_attempts.clear()
        Token.created.clear()
        Room.gate = Room.on_connect = None
        self.demo = store.new_demo("Hosted fixture")
        self.did = self.demo["id"]
        store.update(self.did, lambda demo:demo.update(status="ready"))
        self.fact={"id":"F001","kind":"feature","claim":"Airbags","value":"Six airbags are standard.",
                   "source":{"ref":"src_doc","quote":"Six airbags are standard.","locator":"page 2"},
                   "confidence":1,"conditions":"","truth":"stated","approved":True}
        self.understanding={"product":{"name":"Hosted fixture"},"facts":[self.fact],"competitors":[],"images":[],"shots":[],"brand":{}}
        store.write_json(self.did,"understanding.json",self.understanding)
        store.write_json(self.did,"plan.json",{"voice":{},"segments":[],"ctas":[]})
        self.snapshot=knowledge.snapshot(self.did)
        self.bundle = {"version":3, "runtime":{"version":1}, "knowledge_snapshot_id":self.snapshot["id"]}
        store.write_json(self.did, "bundle.json", self.bundle)

    async def asyncTearDown(self):
        if Room.gate: Room.gate.set()
        await transport.close_trials()
        self.patches.close()
        transport._token_attempts.clear()

    async def error(self, status, req=None, did=None):
        with self.assertRaises(HTTPException) as raised:
            await transport.trial_token(did or self.did, req or request())
        self.assertEqual(raised.exception.status_code, status, raised.exception.detail)
        return raised.exception

    async def test_hosted_private_worker_uses_server_ice_and_public_grant_only(self):
        response = Response()
        result = await transport.trial_token(self.did, request(), response)
        bridge = transport._bridges[result["room"]]
        self.assertEqual(bridge.room.url, SETTINGS["LIVEKIT_INTERNAL_URL"])
        self.assertFalse(hasattr(bridge.room.options, "rtc_config"))
        self.assertEqual((result["url"],result["transport"],result["rtc_mode"],result["rtc_policy"]), (PUBLIC,"livekit","hosted","all"))
        self.assertEqual(response.headers["Cache-Control"], "no-store")
        for private in (SETTINGS["LIVEKIT_API_KEY"], SETTINGS["LIVEKIT_API_SECRET"], SETTINGS["LIVEKIT_INTERNAL_URL"]):
            self.assertNotIn(private, json.dumps(result))

    async def test_short_room_bound_grants_publish_microphone_only(self):
        result = await transport.trial_token(self.did, request())
        worker, viewer = Token.created
        self.assertEqual(viewer.ttl, timedelta(seconds=120))
        self.assertEqual(viewer.grants.room, result["room"])
        self.assertEqual(viewer.grants.can_publish_sources, ["microphone"])
        self.assertTrue(viewer.grants.can_publish and viewer.grants.can_subscribe and viewer.grants.can_publish_data)
        self.assertFalse(viewer.grants.can_update_own_metadata or worker.grants.can_publish)
        self.assertNotEqual(worker.identity, viewer.identity)
        self.assertNotIn(worker.to_jwt(), json.dumps(result))

    async def test_public_url_is_worker_fallback_only_when_internal_url_absent(self):
        with patch.dict(os.environ,{"LIVEKIT_INTERNAL_URL":""}):
            result = await transport.trial_token(self.did, request())
        self.assertEqual(transport._bridges[result["room"]].room.url, PUBLIC)

    async def test_relay_policy_is_viewer_only_and_worker_keeps_default_ice(self):
        with patch.dict(os.environ,{"LIVEKIT_ICE_TRANSPORT_POLICY":"relay"}):
            result = await transport.trial_token(self.did, request())
        self.assertEqual(result["rtc_policy"], "relay")
        self.assertFalse(hasattr(transport._bridges[result["room"]].room.options, "rtc_config"))

    async def test_origin_is_exact_configuration_not_host_or_forwarded_headers(self):
        for origin in (None, "null", "http://demo.example", "https://demo.example.evil", "https://demo.example/", "https://other.example"):
            with self.subTest(origin=origin):
                await self.error(403, request(origin=origin, extra={"host":"other.example", "x-forwarded-host":"demo.example", "x-forwarded-proto":"https", "x-forwarded-for":"127.0.0.1"}))
        self.sdk.assert_not_called()
        self.assertFalse(transport._bridges)

    async def test_public_origin_works_behind_http_reverse_proxy_without_host_reflection(self):
        grant = await transport.trial_token(self.did, request(extra={"host":"127.0.0.1:8877", "x-forwarded-host":"evil.example"}))
        self.assertEqual(grant["transport"], "livekit")

    async def test_public_origin_configuration_rejects_wildcard_insecure_paths_and_credentials(self):
        for origin in ("", "*", "http://demo.example", "https://user@demo.example", ORIGIN+"/", ORIGIN+"/path", ORIGIN+"?x=1", ORIGIN+"#x"):
            with self.subTest(origin=origin), patch.dict(os.environ,{"LIVEKIT_ALLOWED_ORIGINS":origin}):
                self.assertFalse(transport.transport_capability()["livekit_available"])
        self.sdk.assert_not_called()

    async def test_hosted_signal_configuration_requires_tls_or_explicit_local_development(self):
        for url in ("ws://rtc.example", "wss://user:secret@rtc.example", "wss://rtc.example/path", "wss://rtc.example?secret=1", "wss://rtc.example#x", "ws://127.0.0.1:7880", "wss://rtc.example:8896"):
            with self.subTest(url=url), patch.dict(os.environ,{"LIVEKIT_URL":url}):
                self.assertFalse(transport.transport_capability()["livekit_available"])

    async def test_private_signal_config_rejects_public_plaintext_and_metadata_hosts(self):
        for url in ("ws://rtc.example:7880", "ws://169.254.169.254:80", "ws://8.8.8.8:7880", "file:///tmp/socket", "ws://127.0.0.1:8896"):
            with self.subTest(url=url), patch.dict(os.environ,{"LIVEKIT_INTERNAL_URL":url}):
                self.assertFalse(transport.transport_capability()["livekit_available"])
        for url in ("ws://10.2.3.4:7880", "ws://192.168.1.2:7880", "ws://[fd00::1]:7880", "wss://rtc.internal.example"):
            with self.subTest(url=url), patch.dict(os.environ,{"LIVEKIT_INTERNAL_URL":url}):
                self.assertTrue(transport.transport_capability()["livekit_available"])

    async def test_explicit_local_development_rejects_remote_peer_even_with_spoofed_forwarding(self):
        origin = "http://127.0.0.1:8920"
        with patch.dict(os.environ,{"LIVEKIT_ALLOWED_ORIGINS":origin}):
            await self.error(403, request(origin=origin, extra={"x-forwarded-for":"127.0.0.1"}))
            result = await transport.trial_token(self.did, request(origin=origin,client="127.0.0.1"))
            self.assertEqual(result["transport"], "livekit")
            with patch.dict(os.environ,{"LIVEKIT_URL":"ws://127.0.0.1:7880"}):
                self.assertFalse(transport.transport_capability()["livekit_available"])

    async def test_capability_contains_only_nonsecret_status_and_no_connection(self):
        self.assertEqual(transport.transport_capability(), {"transport":"livekit","livekit_enabled":True,"livekit_available":True,"mode":"hosted"})
        self.assertFalse(transport._bridges or Token.created)
        with patch.object(transport,"_sdk",side_effect=HTTPException(503,"Missing SDK")):
            self.assertEqual(transport.transport_capability()["transport"], "livekit")
            self.assertFalse(transport.transport_capability()["livekit_available"])

    async def test_actual_capability_route_is_no_store_nonsecret_and_never_connects(self):
        import httpx
        from server.app import app
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url=ORIGIN) as client:
            response=await client.get("/api/runtime/transport")
            self.assertEqual(response.status_code,200)
            self.assertEqual(response.headers["Cache-Control"],"no-store")
            self.assertEqual(response.json(),{"transport":"livekit","livekit_enabled":True,"livekit_available":True,"mode":"hosted"})
            for value in (PUBLIC,SETTINGS["LIVEKIT_INTERNAL_URL"],SETTINGS["LIVEKIT_API_KEY"],SETTINGS["LIVEKIT_API_SECRET"]):
                self.assertNotIn(value,response.text)
            with patch.dict(os.environ,{"LIVEKIT_ENABLED":"0","LIVEKIT_TRIAL_ENABLED":"0"}):
                disabled=await client.get("/api/runtime/transport")
                self.assertEqual(disabled.json(),{"transport":"websocket","livekit_enabled":False,"livekit_available":False,"mode":"disabled"})
        self.assertFalse(transport._bridges or Token.created)

    async def test_disabled_configuration_does_not_import_sdk_or_create_rate_state(self):
        with patch.dict(os.environ,{"LIVEKIT_ENABLED":"0","LIVEKIT_TRIAL_ENABLED":"0"}):
            self.assertEqual(transport.transport_capability(), {"transport":"websocket","livekit_enabled":False,"livekit_available":False,"mode":"disabled"})
            await self.error(404)
        self.sdk.assert_not_called()
        self.assertFalse(transport._token_attempts)

    async def test_unpublished_bundle_and_absent_pin_never_create_room(self):
        store.update(self.did,lambda demo:demo.update(status="draft"))
        await self.error(409)
        store.update(self.did,lambda demo:demo.update(status="ready"))
        store.write_json(self.did,"bundle.json",{"runtime":{"version":1},"version":3})
        await self.error(409)
        self.assertFalse(transport._bridges or Token.created)

    async def test_stale_requested_version_or_snapshot_rejected_before_sdk(self):
        for pins in ({"demo_version":2}, {"demo_version":True}, {"knowledge_snapshot_id":"ks_old"}):
            with self.subTest(pins=pins):
                await self.error(409,request({"session_id":"s_hosted",**pins}))
        self.sdk.assert_not_called()
        result = await transport.trial_token(self.did,request({"session_id":"s_hosted","demo_version":3,"knowledge_snapshot_id":self.snapshot["id"]}))
        self.assertEqual(result["session_id"],"s_hosted")

    async def test_missing_or_mismatched_archive_never_creates_room(self):
        path=f"knowledge/snapshots/{self.snapshot['id']}.json"
        store.write_json(self.did,path,{"id":"kb_"+"0"*24})
        await self.error(409)
        store.path(self.did,path).unlink()
        await self.error(409)
        self.assertFalse(transport._bridges or Token.created)

    async def test_first_question_after_republish_uses_granted_archive_in_actual_graph(self):
        grant=await transport.trial_token(self.did,request())
        bridge=transport._bridges[grant["room"]]
        new_fact={**self.fact,"value":"Eight airbags are standard.","source":{"ref":"src_doc","quote":"Eight airbags are standard."}}
        store.write_json(self.did,"understanding.json",{**self.understanding,"facts":[new_fact]})
        new_snapshot=knowledge.snapshot(self.did)
        self.assertNotEqual(new_snapshot["id"],self.snapshot["id"])
        store.write_json(self.did,"bundle.json",{**self.bundle,"version":4,"knowledge_snapshot_id":new_snapshot["id"]})
        for packet in transport.fragments({"type":"turn.ask","question":"How many airbags?","turn_id":"first_after_publish","skip_bank":True}):
            bridge._data(NS(data=packet,topic=transport.TOPIC,participant=NS(identity=bridge.identity),kind=0))
        message=json.loads(await bridge.receive_text())
        self.assertEqual((message["demo_version"],message["snapshot_id"]),(3,self.snapshot["id"]))
        result=await runtime_graph.run_turn(self.did,message)
        self.assertEqual(result["snapshot_id"],self.snapshot["id"])
        self.assertEqual(result["demo_version"],3)
        self.assertTrue(result["result"]["answered"],result["result"])
        self.assertIn("Six airbags",result["result"]["answer"])
        self.assertNotIn("Eight airbags",result["result"]["answer"])

    async def test_question_cannot_override_the_room_publication(self):
        for index,pin in enumerate(({"demo_version":4},{"demo_version":True},{"snapshot_id":"kb_"+"0"*24},{"knowledge_snapshot_id":"kb_"+"0"*24})):
            with self.subTest(pin=pin):
                grant=await transport.trial_token(self.did,request({"session_id":f"s_pin{index}"}))
                bridge=transport._bridges[grant["room"]]
                for packet in transport.fragments({"type":"turn.ask","question":"Airbags?",**pin}):
                    bridge._data(NS(data=packet,topic=transport.TOPIC,participant=NS(identity=bridge.identity),kind=0))
                await bridge.close_task
                self.assertTrue(bridge.closed and bridge.room.disconnected)
                self.assertNotIn(grant["room"],transport._bridges)

    async def test_publication_change_during_join_closes_worker_without_viewer_token(self):
        Room.on_connect = lambda:store.write_json(self.did,"bundle.json",{**self.bundle,"version":4})
        await self.error(409)
        self.assertFalse(transport._bridges)
        self.assertEqual(len(Token.created),1)

    async def test_bad_body_and_session_bounds_fail_before_reservation(self):
        for raw,status in ((b"x"*2049,413),(b"not json",400),(b"[]",400),(b'{"session_id":"../../other"}',400)):
            with self.subTest(raw=raw[:25]): await self.error(status,request(raw=raw))
        self.assertFalse(transport._bridges)

    async def test_deep_json_under_http_size_limit_is_rejected_without_room(self):
        raw = b"[" * 1000 + b"0" + b"]" * 1000
        self.assertLess(len(raw),2048)
        await self.error(400,request(raw=raw))
        self.assertFalse(transport._bridges or Token.created)
        self.sdk.assert_not_called()

    async def test_deep_rtc_envelope_or_payload_closes_owner_without_callback_error(self):
        raw = b"[" * 1000 + b"0" + b"]" * 1000
        envelope = json.dumps({"v":1,"id":"nested","part":0,"parts":1,
                               "payload":base64.b64encode(raw).decode()}).encode()
        for index,packet in enumerate((raw,envelope)):
            with self.subTest(layer="envelope" if index==0 else "payload"):
                grant=await transport.trial_token(self.did,request({"session_id":f"s_nested{index}"}))
                bridge=transport._bridges[grant["room"]]
                bridge._data(NS(data=packet,topic=transport.TOPIC,participant=NS(identity=bridge.identity),kind=0))
                self.assertIsNotNone(bridge.close_task)
                await bridge.close_task
                self.assertTrue(bridge.closed and bridge.room.disconnected)
                self.assertNotIn(grant["room"],transport._bridges)

    async def test_slow_body_is_bounded_without_reserving_room(self):
        async def slow(): await asyncio.Event().wait()
        with patch.object(transport,"TOKEN_BODY_SECONDS",.01):
            await self.error(408,request(receive=slow))
        self.assertFalse(transport._bridges or Token.created)

    async def test_denied_attempts_consume_client_rate_budget_before_sdk(self):
        for _ in range(transport.TOKEN_ATTEMPT_LIMIT):
            await self.error(403,request(origin="https://wrong.example"))
        error = await self.error(429)
        self.assertIn("Retry-After",error.headers)
        self.sdk.assert_not_called()

    async def test_raw_forwarded_headers_cannot_rotate_client_rate_identity(self):
        with patch.object(transport,"TOKEN_ATTEMPT_LIMIT",2):
            await self.error(403,request(origin=None,extra={"x-forwarded-for":"1.1.1.1"}))
            await self.error(403,request(origin=None,extra={"x-forwarded-for":"2.2.2.2"}))
            await self.error(429,request(extra={"x-forwarded-for":"3.3.3.3"}))
        self.assertEqual(len(transport._token_attempts),1)

    async def test_rate_expiry_and_client_table_are_bounded(self):
        with patch.object(transport.time,"monotonic",return_value=100):
            with patch.object(transport,"MAX_TOKEN_CLIENTS",1):
                await self.error(403,request(origin=None))
                await self.error(429,request(client="198.51.100.21"))
        with patch.object(transport.time,"monotonic",return_value=161):
            await self.error(403,request(origin=None,client="198.51.100.21"))
        self.assertEqual(set(transport._token_attempts),{"198.51.100.21"})

    async def test_capacity_config_is_strict_and_bounded(self):
        for value in ("0","33","many","-1"):
            with self.subTest(value=value),patch.dict(os.environ,{"LIVEKIT_MAX_ROOMS":value}):
                self.assertFalse(transport.transport_capability()["livekit_available"])
        for value in ("1","4","32"):
            with patch.dict(os.environ,{"LIVEKIT_MAX_ROOMS":value}): self.assertEqual(transport._max_bridges(),int(value))
        with patch.dict(os.environ,{"LIVEKIT_ICE_TRANSPORT_POLICY":"other"}):
            self.assertFalse(transport.transport_capability()["livekit_available"])

    async def test_capacity_is_reserved_before_native_join_await(self):
        Room.gate=asyncio.Event()
        with patch.dict(os.environ,{"LIVEKIT_MAX_ROOMS":"1"}):
            pending=asyncio.create_task(transport.trial_token(self.did,request()))
            for _ in range(20):
                if transport._bridges: break
                await asyncio.sleep(0)
            self.assertEqual(len(transport._bridges),1)
            await self.error(429,request({"session_id":"s_second"}))
            Room.gate.set();await pending

    async def test_same_session_has_only_one_room_owner(self):
        await transport.trial_token(self.did,request())
        await self.error(409)
        self.assertEqual(len(transport._bridges),1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
