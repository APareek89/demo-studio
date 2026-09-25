"""Local, opt-in LiveKit transport for the existing validated demo runtime.

The room replaces the WebSocket wire only. The private facade calls runtime_live
unchanged; it does not create another agent, STT policy, answerer or delivery path.
"""
from __future__ import annotations

import asyncio
import base64
from collections import deque
from datetime import timedelta
import ipaddress
import json
import os
import re
import secrets
import time
from urllib.parse import urlsplit

from fastapi import APIRouter, HTTPException, Request, Response
from starlette.websockets import WebSocketDisconnect

from . import runtime_live, store

router = APIRouter()
TOPIC = "demo.runtime.v1"
CHUNK_BYTES, PACKET_BYTES, MESSAGE_BYTES = 8000, 12288, 1024 * 1024
MAX_PARTS, MAX_INFLIGHT, FRAGMENT_SECONDS = 128, 4, 10
MAX_BRIDGES, JOIN_SECONDS, IDLE_SECONDS, VISIT_SECONDS = 4, 30, 90, 3600
CONNECT_SECONDS, DISCONNECT_SECONDS = 5, 5
READY_ATTEMPTS, READY_RETRY_SECONDS = 4, .5
PRE_ROLL_FRAMES, INPUT_QUEUE_SIZE = 400, 512
_ID = re.compile(r"[A-Za-z0-9_-]{1,80}\Z")
_SESSION = re.compile(r"[A-Za-z0-9_-]{1,100}\Z")
_bridges: dict[str, "TrialBridge"] = {}


def _loopback(host: str | None) -> bool:
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host or "").is_loopback
    except ValueError:
        return False


def _authorize(request: Request) -> None:
    if os.getenv("LIVEKIT_TRIAL_ENABLED") != "1":
        raise HTTPException(404, "LiveKit trial is disabled")
    # Forwarded headers are deliberately not accepted as local authorization.
    if not request.client or not _loopback(request.client.host):
        raise HTTPException(403, "LiveKit trial is local only")
    origin = request.headers.get("origin", "")
    try:
        parsed = urlsplit(origin)
    except ValueError:
        raise HTTPException(403, "A matching local origin is required") from None
    if (parsed.scheme not in ("http", "https") or parsed.scheme != request.url.scheme or not _loopback(parsed.hostname)
            or parsed.netloc != request.headers.get("host")
            or parsed.path or parsed.query or parsed.fragment or parsed.username):
        raise HTTPException(403, "A matching local origin is required")


def _configuration() -> tuple[str, str, str]:
    url = os.getenv("LIVEKIT_URL", "")
    key, secret = os.getenv("LIVEKIT_API_KEY", ""), os.getenv("LIVEKIT_API_SECRET", "")
    try:
        parsed = urlsplit(url)
        port = parsed.port
    except ValueError:
        raise HTTPException(503, "Local LiveKit trial is not configured") from None
    if (parsed.scheme not in ("ws", "wss") or not _loopback(parsed.hostname)
            or port is None or port == 8896
            or parsed.username or parsed.password or parsed.path not in ("", "/")
            or parsed.query or parsed.fragment or not key or len(secret) < 32):
        raise HTTPException(503, "Local LiveKit trial is not configured")
    _stun_url()
    return url, key, secret


def _stun_url() -> str:
    # An empty SDK ICE list inherits the SFU's public STUN defaults. Supply a
    # nonempty local override; host candidates carry this single-machine trial.
    value = os.getenv("LIVEKIT_TRIAL_STUN_URL", "stun:127.0.0.1:7882")
    try:
        parsed = urlsplit("stun://" + value.removeprefix("stun:"))
        valid = (value.startswith("stun:") and _loopback(parsed.hostname)
                 and parsed.port is not None and 1 <= parsed.port <= 65535 and parsed.port != 8896
                 and not parsed.username and not parsed.password and not parsed.path
                 and not parsed.query and not parsed.fragment)
    except ValueError:
        valid = False
    if not valid:
        raise HTTPException(503, "Trial ICE must use a local STUN address")
    return value


def _sdk():
    # The normal app remains importable with no optional LiveKit installation.
    try:
        from livekit import api, rtc
    except ImportError:
        raise HTTPException(503, "LiveKit trial dependencies are not installed") from None
    return api, rtc


def _token(api, key, secret, room, identity, *, viewer):
    grants = api.VideoGrants(room_join=True, room=room, can_publish=viewer,
                             can_publish_sources=["microphone"] if viewer else [],
                             can_publish_data=True, can_subscribe=True,
                             can_update_own_metadata=False)
    return (api.AccessToken(key, secret).with_identity(identity)
            .with_ttl(timedelta(seconds=120)).with_grants(grants).to_jwt())


def fragments(event: dict) -> list[bytes]:
    raw = json.dumps(event, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    if not raw or len(raw) > min(MESSAGE_BYTES, MAX_PARTS * CHUNK_BYTES):
        raise ValueError("trial message too large")
    chunks = [raw[index:index + CHUNK_BYTES] for index in range(0, len(raw), CHUNK_BYTES)]
    message_id = secrets.token_hex(12)
    packets = [json.dumps({"v": 1, "id": message_id, "part": index, "parts": len(chunks),
                          "payload": base64.b64encode(chunk).decode("ascii")},
                         separators=(",", ":")).encode() for index, chunk in enumerate(chunks)]
    if any(len(packet) > PACKET_BYTES for packet in packets):
        raise ValueError("trial packet too large")
    return packets


class Reassembler:
    """Bounded, ordered fragments; a broken message fails the visit visibly."""
    def __init__(self):
        self.pending = {}
        self.completed = {}

    def expired(self, now=None):
        now = time.monotonic() if now is None else now
        return any(now - value["time"] > FRAGMENT_SECONDS for value in self.pending.values())

    def feed(self, packet: bytes, now=None):
        now = time.monotonic() if now is None else now
        if len(packet) > PACKET_BYTES or self.expired(now):
            raise ValueError("trial packet limit or fragment timeout")
        frame = json.loads(packet)
        if not isinstance(frame, dict) or set(frame) != {"v", "id", "part", "parts", "payload"}:
            raise ValueError("invalid trial envelope")
        mid, part, parts = frame["id"], frame["part"], frame["parts"]
        if (type(frame["v"]) is not int or frame["v"] != 1 or not isinstance(mid, str)
                or not _ID.fullmatch(mid) or type(part) is not int or type(parts) is not int
                or not 1 <= parts <= MAX_PARTS or not 0 <= part < parts
                or not isinstance(frame["payload"], str)):
            raise ValueError("invalid trial fragment")
        self.completed = {key: stamp for key, stamp in self.completed.items() if now - stamp <= FRAGMENT_SECONDS}
        if mid in self.completed:
            return None
        chunk = base64.b64decode(frame["payload"], validate=True)
        if not chunk or len(chunk) > CHUNK_BYTES:
            raise ValueError("invalid trial chunk")
        entry = self.pending.get(mid)
        if entry is None:
            if part != 0 or len(self.pending) >= MAX_INFLIGHT:
                raise ValueError("trial fragment order or concurrency")
            entry = self.pending[mid] = {"time": now, "parts": parts, "chunks": [], "size": 0}
        if part != len(entry["chunks"]) or parts != entry["parts"]:
            raise ValueError("trial fragment order changed")
        entry["chunks"].append(chunk)
        entry["size"] += len(chunk)
        if entry["size"] > MESSAGE_BYTES:
            raise ValueError("trial message limit")
        if part + 1 != parts:
            return None
        del self.pending[mid]
        self.completed[mid] = now
        if len(self.completed) > 64:
            del self.completed[next(iter(self.completed))]
        result = json.loads(b"".join(entry["chunks"]).decode("utf-8"))
        if not isinstance(result, dict):
            raise ValueError("trial message must be an object")
        return result


class TrialBridge:
    """Private WebSocket-shaped session backed by one owner-bound local room."""
    def __init__(self, demo_id, session_id, room_name, identity, agent_identity, rtc):
        self.demo_id, self.session_id = demo_id, session_id
        self.room_name, self.identity, self.agent_identity = room_name, identity, agent_identity
        self.rtc, self.room = rtc, rtc.Room()
        self.headers, self.query_params = {}, {"session_id": session_id}
        self.incoming = asyncio.Queue(maxsize=INPUT_QUEUE_SIZE)
        self.assembler, self.send_lock = Reassembler(), asyncio.Lock()
        self.closed, self.owner_joined = False, False
        self.protocol_started = False
        self.started = self.last_activity = time.monotonic()
        self.runtime_task = self.watch_task = self.audio_task = None
        self.ready_task = None
        self.connect_task = self.dispose_task = None
        self.close_task = None
        self.pending_generation = self.active_generation = self.track_generation = 0
        self.mic_enabled = False
        self.track_publication = None
        self.rtc_frames_received = self.rtc_frames_forwarded = 0
        self.track_ready = asyncio.Event()
        self.pre_roll = deque()
        self.early_tracks = {}
        self._install_events()

    def _install_events(self):
        self.room.on("data_received", self._data)
        self.room.on("track_subscribed", self._track)
        self.room.on("track_unsubscribed", self._untrack)
        self.room.on("participant_connected", self._joined)
        self.room.on("participant_active", self._joined)
        self.room.on("participant_disconnected", self._left)
        self.room.on("disconnected", lambda *_: self._fail())
        # Fail closed rather than silently replaying turns across a reconnect.
        self.room.on("reconnecting", lambda *_: self._fail())

    def _fail(self):
        if not self.closed and self.close_task is None:
            self.close_task = asyncio.create_task(self.close())

    def _joined(self, participant):
        if not self.closed and participant.identity == self.identity:
            self.owner_joined = True
            self.last_activity = time.monotonic()
            if self.ready_task is None:
                self.ready_task = asyncio.create_task(self._announce_ready())

    async def _announce_ready(self):
        # Native RTC can deliver data before the SDK has learned its participant
        # identity. Only invite controls after the exact viewer is visible here.
        try:
            for _ in range(READY_ATTEMPTS):
                if self.closed or self.protocol_started:
                    return
                await self.send_json({"type": "trial.ready", "session_id": self.session_id})
                # Reliable RTC data is still best-effort before the peer becomes
                # active. Retry only this control invitation, never a user turn.
                await asyncio.sleep(READY_RETRY_SECONDS)
        except Exception:
            self._fail()

    def _left(self, participant):
        if participant.identity == self.identity:
            self._fail()

    async def connect(self, url, token):
        options = self.rtc.RoomOptions(rtc_config=self.rtc.RtcConfiguration(
            ice_servers=[self.rtc.IceServer(urls=[_stun_url()])]))
        self.connect_task = asyncio.create_task(self.room.connect(url, token, options=options))
        # Cancelling the Python await does not cancel the native SDK's ICE join.
        # Keep its owner alive; on timeout close() retains this pool reservation
        # until the native result arrives and can be disconnected safely.
        await asyncio.wait_for(asyncio.shield(self.connect_task), timeout=CONNECT_SECONDS)
        self.runtime_task = asyncio.create_task(runtime_live.live(self, self.demo_id))
        self.runtime_task.add_done_callback(lambda _: self._fail())
        self.watch_task = asyncio.create_task(self._watch())

    async def _watch(self):
        while not self.closed:
            await asyncio.sleep(1)
            now = time.monotonic()
            if (now - self.started > VISIT_SECONDS or now - self.last_activity > IDLE_SECONDS
                    or (not self.owner_joined and now - self.started > JOIN_SECONDS)
                    or self.assembler.expired(now)):
                self._fail()
                return

    def _put(self, event):
        if self.closed:
            return False
        try:
            self.incoming.put_nowait(json.dumps(event, separators=(",", ":")))
            return True
        except asyncio.QueueFull:
            self._fail()
            return False

    def _data(self, packet):
        if (self.closed or packet.topic != TOPIC or packet.participant is None
                or packet.participant.identity != self.identity
                or packet.kind != self.rtc.DataPacketKind.KIND_RELIABLE):
            return
        try:
            message = self.assembler.feed(packet.data)
            if message is None:
                return
            if len(json.dumps(message)) > 100_000:
                raise ValueError("runtime message too large")
            if message.get("session_id", self.session_id) != self.session_id:
                raise ValueError("session ownership changed")
            message["session_id"] = self.session_id
            self.last_activity = time.monotonic()
            self.owner_joined = True
            if message.get("type") == "trial.ping":
                # Ping does not enter or advance the runtime graph.
                self._put({"type": "trial.ping"})
                return
            if message.get("type") == "audio.input":
                raise ValueError("microphone input must use the bound RTC track")
            if message.get("type") == "session.start" and message.get("mic") is True:
                # Capture activation must be explicit and have a named RTC track.
                raise ValueError("use mic.set for trial microphone activation")
            if message.get("type") == "session.start":
                self.protocol_started = True
            if message.get("type") == "mic.set":
                generation = message.get("input_generation")
                if type(generation) is not int or not 0 <= generation <= 1_000_000:
                    raise ValueError("invalid microphone generation")
                if message.get("enabled") is True and generation > self.pending_generation:
                    self.pending_generation, self.active_generation = generation, 0
                    self.mic_enabled = True
                    if self.audio_task:
                        self.audio_task.cancel()
                    self.track_generation = 0
                    self.track_publication = None
                    self.pre_roll.clear()
                    self.track_ready.clear()
                    early = self.early_tracks.pop(generation, None)
                    self.early_tracks.clear()
                    if early:
                        self._track(*early)
                elif message.get("enabled") is False and generation == self.pending_generation:
                    self.mic_enabled = False
                    self.active_generation = 0
                    self.pre_roll.clear()
                    self.track_ready.set()
            self._put(message)
        except (ValueError, TypeError, UnicodeError):
            self._fail()

    def _track(self, track, publication, participant):
        if (self.closed or participant.identity != self.identity
                or publication.source != self.rtc.TrackSource.SOURCE_MICROPHONE
                or track.kind != self.rtc.TrackKind.KIND_AUDIO):
            return
        match = re.fullmatch(r"demo-mic-([1-9][0-9]{0,6})", publication.name)
        if not match:
            return
        generation = int(match[1])
        # TrackSubscribed and reliable data travel independently. Keep at most
        # the next capture when its track reaches us before mic.set does.
        if generation == self.pending_generation + 1 and generation <= 1_000_000:
            self.early_tracks[generation] = (track, publication, participant)
            return
        if generation != self.pending_generation or generation <= 0 or not self.mic_enabled:
            return
        if self.track_generation == generation and self.audio_task and not self.audio_task.done():
            return  # one physical capture owns each generation
        if self.audio_task:
            self.audio_task.cancel()
        self.track_generation = self.pending_generation
        self.track_publication = publication
        self.track_ready.set()
        self.audio_task = asyncio.create_task(self._audio(track, self.track_generation))

    def _untrack(self, track, publication, participant):
        if participant.identity == self.identity:
            for generation, (_, cached, _) in list(self.early_tracks.items()):
                if cached is publication:
                    self.early_tracks.pop(generation, None)
        if participant.identity == self.identity and publication is self.track_publication:
            if self.mic_enabled:
                self._fail()
            if self.audio_task:
                self.audio_task.cancel()
            self.track_generation = 0
            self.track_publication = None
            self.track_ready.clear()
            self.active_generation = 0
            self.pre_roll.clear()

    async def _audio(self, track, generation):
        stream = None
        try:
            stream = self.rtc.AudioStream(track, sample_rate=16000, num_channels=1, frame_size_ms=20)
            async for event in stream:
                if self.closed or not self.mic_enabled or generation != self.pending_generation or generation != self.track_generation:
                    return
                raw = bytes(event.frame.data)
                if len(raw) != 640:
                    raise ValueError("unexpected microphone frame size")
                self.rtc_frames_received += 1
                if self.active_generation != generation:
                    if len(self.pre_roll) >= PRE_ROLL_FRAMES:
                        self._fail()
                        return
                    self.pre_roll.append(raw)
                    continue
                if not self._pcm(raw, generation):
                    return
        except asyncio.CancelledError:
            raise
        except Exception:
            self._fail()
        finally:
            if stream is not None:
                await stream.aclose()
            if not self.closed and self.mic_enabled and generation == self.pending_generation:
                self._fail()

    def _pcm(self, raw, generation):
        accepted = self._put({"type": "audio.input", "input_generation": generation,
                              "audio": base64.b64encode(raw).decode("ascii")})
        if accepted:
            self.rtc_frames_forwarded += 1
        return accepted

    async def accept(self):
        pass

    async def receive_text(self):
        while not self.closed:
            event = await self.incoming.get()
            if event is None:
                break
            if json.loads(event).get("type") == "trial.ping":
                await self.send_json({"type": "trial.pong", "session_id": self.session_id,
                                      "rtc_frames_received": self.rtc_frames_received,
                                      "rtc_frames_forwarded": self.rtc_frames_forwarded})
                continue
            return event
        raise WebSocketDisconnect(1001)

    async def send_json(self, event):
        if self.closed:
            raise WebSocketDisconnect(1001)
        if event.get("type") == "mic.ready":
            generation = event.get("input_generation")
            try:
                await asyncio.wait_for(self.track_ready.wait(), timeout=5)
            except asyncio.TimeoutError:
                self._fail()
                raise WebSocketDisconnect(1001) from None
            if self.closed or not self.mic_enabled or generation != self.pending_generation or generation != self.track_generation:
                return
            self.active_generation = generation
            while self.pre_roll:
                if not self._pcm(self.pre_roll.popleft(), generation):
                    raise WebSocketDisconnect(1001)
        packets = fragments({**event, "session_id": self.session_id})
        async with self.send_lock:
            for packet in packets:
                if self.closed:
                    raise WebSocketDisconnect(1001)
                try:
                    await asyncio.wait_for(self.room.local_participant.publish_data(
                        packet, reliable=True, destination_identities=[self.identity], topic=TOPIC), timeout=5)
                except Exception:
                    self._fail()
                    raise WebSocketDisconnect(1001) from None

    async def close(self, code=1000):
        if self.closed:
            return
        self.closed = True
        self.active_generation = self.pending_generation = 0
        self.mic_enabled = False
        self.pre_roll.clear()
        self.early_tracks.clear()
        self.track_ready.set()
        while not self.incoming.empty():
            self.incoming.get_nowait()
        self.incoming.put_nowait(None)
        current = asyncio.current_task()
        tasks = [task for task in (self.runtime_task, self.watch_task, self.audio_task, self.ready_task)
                 if task is not None and task is not current]
        for task in tasks:
            task.cancel()
        if tasks:
            try:
                await asyncio.wait_for(asyncio.gather(*tasks, return_exceptions=True), timeout=5)
            except asyncio.TimeoutError:
                pass
        self.dispose_task = asyncio.create_task(self._dispose_room())
        if not self.connect_task or self.connect_task.done():
            try:
                await asyncio.wait_for(asyncio.shield(self.dispose_task), timeout=DISCONNECT_SECONDS)
            except asyncio.TimeoutError:
                pass  # keep the room's reservation until native disconnect ends

    async def _dispose_room(self):
        if self.connect_task:
            try:
                await self.connect_task
            except Exception:
                pass
        try:
            await self.room.disconnect()
        except Exception:
            return  # an uncertain native disconnect must not free capacity
        _bridges.pop(self.room_name, None)


@router.post("/api/demos/{demo_id}/run/livekit/token")
async def trial_token(demo_id: str, request: Request, response: Response = None):
    _authorize(request)
    if not store.exists(demo_id):
        raise HTTPException(404, "Demo not found")
    bundle = store.read_json(demo_id, "bundle.json") or {}
    if (store.load(demo_id).get("status") != "ready" or bundle.get("runtime", {}).get("version") != 1
            or not bundle.get("knowledge_snapshot_id")):
        raise HTTPException(409, "Publish a runtime v1 demo before starting the trial")
    raw = bytearray()
    async for chunk in request.stream():
        if len(raw) + len(chunk) > 2048:
            raise HTTPException(413, "Trial request too large")
        raw.extend(chunk)
    try:
        body = json.loads(raw)
    except ValueError:
        raise HTTPException(400, "Invalid trial request") from None
    session_id = body.get("session_id") if isinstance(body, dict) else None
    if not isinstance(session_id, str) or not _SESSION.fullmatch(session_id):
        raise HTTPException(400, "A valid session_id is required")
    url, key, secret = _configuration()
    api, rtc = _sdk()
    # No await between capacity check and reservation; safe on the app loop.
    if len(_bridges) >= MAX_BRIDGES:
        raise HTTPException(429, "Four local trials are already running")
    if any(value.demo_id == demo_id and value.session_id == session_id for value in _bridges.values()):
        raise HTTPException(409, "This trial session is already connected")
    room = "trial_" + secrets.token_hex(12)
    identity, agent_identity = "viewer_" + secrets.token_hex(8), "runtime_" + secrets.token_hex(8)
    bridge = TrialBridge(demo_id, session_id, room, identity, agent_identity, rtc)
    _bridges[room] = bridge
    try:
        await bridge.connect(url, _token(api, key, secret, room, agent_identity, viewer=False))
        token = _token(api, key, secret, room, identity, viewer=True)
    except asyncio.CancelledError:
        await bridge.close()
        raise
    except Exception:
        await bridge.close()
        raise HTTPException(503, "Local LiveKit trial could not connect") from None
    if response is not None:
        response.headers["Cache-Control"] = "no-store"
    return {"url": url, "token": token, "room": room, "identity": identity,
            "agent_identity": agent_identity, "session_id": session_id, "transport": "livekit-trial"}


@router.on_event("shutdown")
async def close_trials():
    await asyncio.gather(*(bridge.close() for bridge in list(_bridges.values())), return_exceptions=True)
