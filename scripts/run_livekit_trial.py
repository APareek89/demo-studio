#!/usr/bin/env python3
"""Run the opt-in LiveKit trial locally, with a separate copy of one publication.

Use a Python environment containing requirements.txt + requirements-livekit-trial.txt.
Provider calls are mocked unless the operator explicitly passes --live-providers.
This starts only owned local processes and never stops an existing app.
API/signaling bind loopback; RTC UDP uses one explicitly validated private host IP.
"""
from __future__ import annotations

import argparse
import fcntl
import importlib.util
import ipaddress
import json
import os
from pathlib import Path
import secrets
import shutil
import signal
import socket
import subprocess
import sys
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
FILES = {"demo.json", "bundle.json", "understanding.json", "faq.json", "deck.json",
         "plan.json", "script.json", "fillers.json", "playbook.json", "visual-audit.json"}
DIRS = {"sources", "derived", "media", "audio", "knowledge"}
KEYS = ("ANTHROPIC_API_KEY", "GEMINI_API_KEY", "RUNWARE_API_KEY", "GCLOUD_TTS_API_KEY", "SARVAM_API_KEY")


def copy_publication(source: Path, state: Path) -> str:
    source, state = source.resolve(), state.resolve()
    if source.name == "dm_41513908" or not source.name.startswith("dm_"):
        raise ValueError("Choose a published demo other than the protected demo.")
    if state == source or state.is_relative_to(source) or source.is_relative_to(state):
        raise ValueError("Trial storage and source demo must be separate directories.")
    bundle = json.loads((source / "bundle.json").read_text())
    if bundle.get("runtime", {}).get("version") != 1 or not bundle.get("knowledge_snapshot_id"):
        raise ValueError("The source must be a published runtime-v1 demo with pinned evidence.")
    destination = state / "data" / source.name
    if (state / "data").is_symlink() or destination.is_symlink() or not destination.resolve().is_relative_to(state):
        raise ValueError("Trial data must stay inside its own storage directory.")
    if destination.exists():
        saved = json.loads((destination / "bundle.json").read_text())
        if saved != bundle:
            raise ValueError("Trial already has a different publication; choose a fresh --state-dir.")
        return source.name  # retain this trial's own visits; never recopy over them
    staging = state / "data" / (source.name + ".copying")
    staging.mkdir(parents=True, exist_ok=False)
    try:
        for entry in source.iterdir():
            if entry.name not in FILES | DIRS:
                continue  # exclude previous visits, contacts, logs, usage and mutable runtime
            paths = [entry, *entry.rglob("*")] if entry.is_dir() else [entry]
            if any(path.is_symlink() for path in paths):
                raise ValueError("Trial source assets must be local regular files, not symlinks.")
            if entry.is_dir():
                shutil.copytree(entry, staging / entry.name)
            else:
                shutil.copy2(entry, staging / entry.name)
        staging.rename(destination)
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)  # this invocation's incomplete copy only
        raise
    return source.name


def validate_rtc_host(host: str) -> str:
    """Accept only a private IPv4 address actually owned by this machine."""
    address = ipaddress.ip_address(host)
    if (address.version != 4 or not address.is_private or address.is_unspecified
            or address.is_multicast or address.is_link_local or address.is_loopback):
        raise ValueError("RTC requires this machine's private IPv4 address, not a public or loopback address.")
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
        probe.bind((str(address), 0))  # ownership check, no packet or DNS request
    return str(address)


def check_ports(ports: list[int], rtc_host: str = "127.0.0.1") -> None:
    if len(set(ports)) != len(ports) or any(p == 8896 or not 1024 <= p <= 65535 for p in ports):
        raise ValueError("Use distinct unprivileged ports; port 8896 is protected.")
    for index, port in enumerate(ports):
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM if index == 2 else socket.SOCK_STREAM) as test:
            test.bind((rtc_host if index == 2 else "127.0.0.1", port))


def config_text(key: str, secret: str, signal_port: int, udp_port: int, rtc_host: str = "127.0.0.1") -> str:
    # Empty STUN falls back to public servers in LiveKit 1.13.7. Explicit local
    # STUN plus a host candidate keeps media on this machine. Native libwebrtc
    # does not offer loopback candidates, so RTC uses the explicit private host
    # address. TCP is off because its listener ignores bind_addresses.
    return f"""port: {signal_port}
bind_addresses: [127.0.0.1]
rtc:
  tcp_port: 0
  udp_port: {udp_port}
  node_ip: {rtc_host}
  use_external_ip: false
  enable_loopback_candidate: true
  ips:
    includes: [{rtc_host}/32]
  stun_servers: [127.0.0.1:{udp_port}]
keys:
  {key}: {secret}
logging:
  level: warn
"""


def wait_http(url: str, process: subprocess.Popen, timeout: float = 25) -> None:
    until = time.monotonic() + timeout
    while time.monotonic() < until:
        if process.poll() is not None:
            raise RuntimeError("Trial process exited; inspect its local log.")
        try:
            with urllib.request.urlopen(url, timeout=1) as response:
                if response.status == 200:
                    return
        except OSError:
            pass
        time.sleep(.15)
    raise TimeoutError("Trial startup did not become ready; inspect its local log.")


def stop_owned(process: subprocess.Popen) -> None:
    if process.poll() is not None:
        return
    os.killpg(process.pid, signal.SIGTERM)
    try:
        process.wait(timeout=6)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGKILL)
        process.wait(timeout=3)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-demo", type=Path, required=True)
    parser.add_argument("--livekit-server", type=Path, default=shutil.which("livekit-server"))
    parser.add_argument("--state-dir", type=Path, default=Path("/tmp/demo-studio-livekit-review"))
    parser.add_argument("--port", type=int, default=8920)
    parser.add_argument("--signal-port", type=int, default=7880)
    parser.add_argument("--rtc-udp-port", type=int, default=7882)
    parser.add_argument("--rtc-host", required=True, help="This machine's private IPv4 address (for example, ipconfig getifaddr en0 on macOS). API/signaling remain loopback-only.")
    parser.add_argument("--live-providers", action="store_true", help="Use configured paid providers for an explicitly requested live trial.")
    args = parser.parse_args()
    if not args.livekit_server or not args.livekit_server.is_file():
        parser.error("Install LiveKit Server or pass --livekit-server /path/to/livekit-server.")
    try:
        for package in ("livekit.rtc", "livekit.api", "uvicorn"):
            if importlib.util.find_spec(package) is None:
                raise ImportError(package)
    except (ImportError, ModuleNotFoundError):
        parser.error("Use a Python environment with the application and optional LiveKit requirements installed.")
    rtc_host = validate_rtc_host(args.rtc_host)
    check_ports([args.port, args.signal_port, args.rtc_udp_port], rtc_host)
    state = args.state_dir.resolve()
    state.mkdir(parents=True, exist_ok=True, mode=0o700)
    for name in ("data", "graph.sqlite", "graph.sqlite-wal", "graph.sqlite-shm", "launcher.lock", "livekit.private.yaml", "livekit.log", "app.log"):
        if (state / name).is_symlink():
            raise ValueError("Trial state files must not link into another storage directory.")
    lock = (state / "launcher.lock").open("a")
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    demo_id = copy_publication(args.source_demo, state)
    secret = secrets.token_urlsafe(36)
    config = state / "livekit.private.yaml"
    descriptor = os.open(config, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, "w") as stream:
        stream.write(config_text("demo_trial", secret, args.signal_port, args.rtc_udp_port, rtc_host))
    config.chmod(0o600)
    env = {**os.environ, "LIVEKIT_TRIAL_ENABLED": "1", "LIVEKIT_URL": f"ws://127.0.0.1:{args.signal_port}",
           "LIVEKIT_API_KEY": "demo_trial", "LIVEKIT_API_SECRET": secret,
           "LIVEKIT_TRIAL_STUN_URL": f"stun:127.0.0.1:{args.rtc_udp_port}",
           "MOCK_LLM": "0" if args.live_providers else "1", "CLOUD_SYNC": "0", "STORAGE_BACKEND": "local",
           "DEMO_STUDIO_DATA": str(state / "data"), "DEMO_STUDIO_GRAPH_DB": str(state / "graph.sqlite")}
    if not args.live_providers:
        env.update({key: "" for key in KEYS})
    children = []
    def halt(*_):
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, halt)
    try:
        with (state / "livekit.log").open("ab") as lklog, (state / "app.log").open("ab") as applog:
            server = subprocess.Popen([str(args.livekit_server.resolve()), "--config", str(config)], stdout=lklog, stderr=subprocess.STDOUT, start_new_session=True)
            children.append(server)
            wait_http(f"http://127.0.0.1:{args.signal_port}/", server)
            app = subprocess.Popen([sys.executable, str(ROOT / "scripts/livekit_trial_server.py"), str(args.port)], cwd=ROOT, env=env, stdout=applog, stderr=subprocess.STDOUT, start_new_session=True)
            children.append(app)
            wait_http(f"http://127.0.0.1:{args.port}/api/health", app)
            url = f"http://127.0.0.1:{args.port}/?voice_transport=livekit#/play/{demo_id}"
            print(("LIVE providers (configured usage charges apply)." if args.live_providers else "MOCK providers: real local LiveKit connection; no provider calls."), flush=True)
            print(url, flush=True)
            print(f"Trial data/logs: {state}\nCtrl-C stops only these trial processes.", flush=True)
            while all(child.poll() is None for child in children):
                time.sleep(.5)
            raise RuntimeError("A trial process stopped; inspect the local logs.")
    except KeyboardInterrupt:
        pass
    finally:
        for child in reversed(children):
            stop_owned(child)
        lock.close()


if __name__ == "__main__":
    main()
