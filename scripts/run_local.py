#!/usr/bin/env python3
"""Start the local workspace app and its owned LiveKit server, without a URL flag.

Example (existing workspace and configured live providers):
  .venv/bin/python scripts/run_local.py --live-providers --data /path/to/demos \\
    --graph-db /path/to/graph.sqlite

No publication or previous visit is copied, rebuilt or edited by this launcher.
Omit --live-providers for mock providers and blocked external Python sockets.
On macOS the private RTC interface is detected from en0/en1; elsewhere pass
--rtc-host with a private IPv4 address owned by this machine. Signaling and the
app stay on loopback. Ctrl-C stops only the two processes this invocation owns.
"""
from __future__ import annotations

import argparse
import fcntl
import importlib.util
import os
from pathlib import Path
import secrets
import shutil
import signal
import stat
import subprocess
import sys
import time

from run_livekit_trial import ROOT, KEYS, check_ports, config_text, stop_owned, validate_rtc_host, wait_http
from livekit_trial_server import install_socket_guard

PRIVATE_FILES = {"launcher.lock", "livekit.private.yaml", "livekit.log", "app.log"}
PROTECTED_DEMO = "dm_41513908"


def parser() -> argparse.ArgumentParser:
    command = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    command.add_argument("--data", type=Path, default=Path(os.getenv("DEMO_STUDIO_DATA") or ROOT / "data/demos"))
    command.add_argument("--graph-db", type=Path, default=Path(os.environ["DEMO_STUDIO_GRAPH_DB"]) if os.getenv("DEMO_STUDIO_GRAPH_DB") else None)
    command.add_argument("--state-dir", type=Path, default=Path.home() / ".local/state/demo-studio/livekit")
    command.add_argument("--livekit-server", type=Path, default=Path(shutil.which("livekit-server") or Path.home() / ".local/lib/demo-studio/livekit-1.13.7/livekit-server"))
    command.add_argument("--port", type=int, default=8910)
    command.add_argument("--signal-port", type=int, default=7890)
    command.add_argument("--rtc-udp-port", type=int, default=7892)
    command.add_argument("--rtc-host", help="This machine's private IPv4 address; macOS can detect en0/en1 automatically.")
    command.add_argument("--live-providers", action="store_true", help="Use the configured live answer, speech and build providers (usage charges apply).")
    return command


def rtc_host(explicit: str | None) -> str:
    if explicit:
        return validate_rtc_host(explicit)
    if sys.platform == "darwin":
        for interface in ("en0", "en1"):
            try:
                found = subprocess.run(["/usr/sbin/ipconfig", "getifaddr", interface], check=True,
                                       capture_output=True, text=True, timeout=3).stdout.strip()
                if found:
                    return validate_rtc_host(found)
            except (OSError, ValueError, subprocess.SubprocessError):
                pass
    raise ValueError("Pass --rtc-host with this machine's private IPv4 address; no public network probe is used.")


def storage_paths(args) -> tuple[Path, Path, Path]:
    raw_state = args.state_dir.expanduser().absolute()
    # Reject redirects before resolving them, including a symlinked state parent.
    if any(path.is_symlink() for path in (raw_state, *raw_state.parents)):
        raise ValueError("Local launcher state must not use symlinks; supply its real filesystem path.")
    state = raw_state.resolve()
    data = args.data.expanduser().resolve()
    graph = (args.graph_db.expanduser() if args.graph_db else data.parent / "graph.sqlite").resolve()
    if any(PROTECTED_DEMO in path.parts for path in (state, data, graph)):
        raise ValueError("The protected demo cannot be used as launcher storage.")
    if data.exists() and not data.is_dir():
        raise ValueError("--data must name the directory containing demos.")
    if graph.exists() and not graph.is_file():
        raise ValueError("--graph-db must name a SQLite file.")
    if (state == data or state.is_relative_to(data) or data.is_relative_to(state)
            or graph == state or graph.is_relative_to(state)
            or state == ROOT or state.is_relative_to(ROOT) or ROOT.is_relative_to(state)):
        raise ValueError("Keep private launcher state outside the repository and separate from demo/graph storage.")
    return state, data, graph


def prepare_state(state: Path) -> None:
    previous = os.umask(0o077)
    try:
        state.mkdir(parents=True, exist_ok=True, mode=0o700)
    finally:
        os.umask(previous)
    if state.is_symlink() or state.stat().st_uid != os.getuid():
        raise ValueError("Local launcher state must be owned by the current user.")
    for name in PRIVATE_FILES:
        if (state / name).is_symlink():
            raise ValueError("Local launcher state files must not be symlinks.")
    state.chmod(0o700)


def private_file(state: Path, name: str, *, truncate=False, append=False):
    if name not in PRIVATE_FILES:
        raise ValueError("Unexpected private launcher file")
    flags = os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | (os.O_APPEND if append else 0)
    descriptor = os.open(state / name, flags, 0o600)
    try:
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_uid != os.getuid():
            raise ValueError("Local launcher files must be regular, singly linked and user-owned.")
        os.fchmod(descriptor, 0o600)
        if truncate:
            os.ftruncate(descriptor, 0)
        return os.fdopen(descriptor, "a+b" if append else "r+b")
    except BaseException:
        os.close(descriptor)
        raise


def application_environment(args, data: Path, graph: Path, secret: str) -> dict:
    env = {**os.environ, "LIVEKIT_ENABLED":"0", "LIVEKIT_TRIAL_ENABLED":"1",
           "LIVEKIT_URL":f"ws://127.0.0.1:{args.signal_port}", "LIVEKIT_INTERNAL_URL":"",
           "LIVEKIT_ALLOWED_ORIGINS":"", "LIVEKIT_ICE_TRANSPORT_POLICY":"all",
           "LIVEKIT_API_KEY":"demo_local", "LIVEKIT_API_SECRET":secret,
           "LIVEKIT_TRIAL_STUN_URL":f"stun:127.0.0.1:{args.rtc_udp_port}",
           "MOCK_LLM":"0" if args.live_providers else "1", "CLOUD_SYNC":"0", "STORAGE_BACKEND":"local",
           "DEMO_STUDIO_DATA":str(data), "DEMO_STUDIO_GRAPH_DB":str(graph)}
    if not args.live_providers:
        env.update({key:"" for key in KEYS})
    return env


def require_runtime(binary: Path) -> Path:
    binary = binary.expanduser().resolve()
    if not binary.is_file() or not os.access(binary, os.X_OK):
        raise ValueError("Install the local LiveKit server or pass --livekit-server /path/to/livekit-server.")
    try:
        for package in ("livekit.rtc", "livekit.api", "uvicorn"):
            if importlib.util.find_spec(package) is None:
                raise ImportError(package)
    except (ImportError, ModuleNotFoundError):
        raise ValueError("Use the app .venv with requirements.txt installed, including LiveKit.") from None
    return binary


def main(argv=None) -> None:
    command = parser()
    args = command.parse_args(argv)
    try:
        binary = require_runtime(args.livekit_server)
        state, data, graph = storage_paths(args)
        host = rtc_host(args.rtc_host)
        check_ports([args.port, args.signal_port, args.rtc_udp_port], host)
        prepare_state(state)
    except (ValueError, OSError) as exc:
        command.error(str(exc))
    children = []
    previous_handler = signal.getsignal(signal.SIGTERM)
    def halt(*_): raise KeyboardInterrupt
    with private_file(state, "launcher.lock") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            command.error("This local launcher state is already in use; the running app was not stopped.")
        secret = secrets.token_urlsafe(36)
        with private_file(state, "livekit.private.yaml", truncate=True) as config:
            config.write(config_text("demo_local", secret, args.signal_port, args.rtc_udp_port, host).encode())
        env = application_environment(args, data, graph, secret)
        if not args.live_providers:
            install_socket_guard()
        signal.signal(signal.SIGTERM, halt)
        try:
            with private_file(state, "livekit.log", append=True) as lklog, private_file(state, "app.log", append=True) as applog:
                # The SFU must not inherit unrelated hosted LiveKit overrides.
                sfu_env = {key:value for key,value in os.environ.items() if not key.startswith("LIVEKIT_") and key not in KEYS}
                server = subprocess.Popen([str(binary), "--config", str(state / "livekit.private.yaml")],
                    env=sfu_env, stdout=lklog, stderr=subprocess.STDOUT, start_new_session=True)
                children.append(server)
                wait_http(f"http://127.0.0.1:{args.signal_port}/", server)
                app = subprocess.Popen([sys.executable, str(ROOT / "scripts/livekit_trial_server.py"), str(args.port)],
                    cwd=ROOT, env=env, stdout=applog, stderr=subprocess.STDOUT, start_new_session=True)
                children.append(app)
                wait_http(f"http://127.0.0.1:{args.port}/api/health", app)
                print("Live providers enabled." if args.live_providers else "Mock providers; external Python sockets blocked.", flush=True)
                print(f"http://127.0.0.1:{args.port}/", flush=True)
                print(f"Workspace data: {data}\nLocal service logs: {state}\nCtrl-C stops only this launcher's processes.", flush=True)
                while all(child.poll() is None for child in children):
                    time.sleep(.5)
                raise RuntimeError("A local process stopped; inspect the local service logs.")
        except KeyboardInterrupt:
            pass
        finally:
            cleanup_errors = []
            for child in reversed(children):
                try:
                    stop_owned(child)
                except ProcessLookupError:
                    pass  # The owned child exited between poll() and killpg().
                except Exception as exc:
                    cleanup_errors.append(exc)
            signal.signal(signal.SIGTERM, previous_handler)
            if cleanup_errors:
                raise RuntimeError("An owned local process could not be stopped; inspect the launcher logs.") from cleanup_errors[0]


if __name__ == "__main__":
    main()
