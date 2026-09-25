#!/usr/bin/env python3
"""Exercise the feedback proxy with REAL Caddy and a loopback-only stub.

No app imports, production requests, provider calls, or production Caddy reloads.
Run: python3 docs/aws/check_feedback_proxy.py [--caddy /usr/bin/caddy]
The JSON result contains no generated password or password hash.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import http.client
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import secrets
import shutil
import socket
import subprocess
import tempfile
import threading
import time
from urllib.parse import parse_qs, urlsplit


DEMO = "dm_29df0418"
PREFIX = "/api/demos/" + DEMO
MEDIA = "/media/" + DEMO
SHARE = "/api/share/" + DEMO + "/s_contract"
SHARE_KEY = "1234567890abcdef1234"  # Deliberately synthetic; stub only.


class Stub(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    calls: list[tuple[str, str]] = []

    def log_message(self, *_args):
        pass

    def handle_request(self):
        self.calls.append((self.command, self.path))
        length = int(self.headers.get("Content-Length", "0"))
        if length:
            self.rfile.read(length)
        if self.headers.get("Upgrade", "").lower() == "websocket":
            key = self.headers.get("Sec-WebSocket-Key", "")
            accept = base64.b64encode(hashlib.sha1(
                (key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode()
            ).digest()).decode()
            self.send_response(101)
            self.send_header("Upgrade", "websocket")
            self.send_header("Connection", "Upgrade")
            self.send_header("Sec-WebSocket-Accept", accept)
            self.end_headers()
            self.close_connection = True
            return
        status = 200
        if urlsplit(self.path).path == SHARE:
            status = 200 if parse_qs(urlsplit(self.path).query).get("k") == [SHARE_KEY] else 403
        body = b"stub: public or authenticated request reached upstream"
        self.send_response(status)
        self.send_header("Content-Type", "text/plain")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Feedback-Contract-Upstream", "yes")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    do_GET = do_HEAD = do_POST = do_PATCH = do_PUT = do_DELETE = do_OPTIONS = handle_request


def unused_port() -> int:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return listener.getsockname()[1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--caddy", default=shutil.which("caddy"))
    parser.add_argument("--template", type=Path, default=Path(__file__).with_name("Caddyfile.feedback.template"))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if not args.caddy:
        parser.error("Caddy is not installed; run this contract on the staging host with --caddy /usr/bin/caddy")

    results: list[dict] = []
    upstream = ThreadingHTTPServer(("127.0.0.1", 0), Stub)
    upstream.daemon_threads = True
    worker = threading.Thread(target=upstream.serve_forever, daemon=True)
    worker.start()
    proc = None
    try:
        with tempfile.TemporaryDirectory(prefix="feedback-proxy-contract-") as raw_tmp:
            tmp = Path(raw_tmp)
            env = os.environ.copy()
            env.update(HOME=str(tmp), XDG_CONFIG_HOME=str(tmp / "config"), XDG_DATA_HOME=str(tmp / "data"))
            password = secrets.token_urlsafe(32)
            hashed = subprocess.run(
                [args.caddy, "hash-password", "--plaintext", password], env=env,
                text=True, capture_output=True, check=True, timeout=30,
            ).stdout.strip()
            auth_file = tmp / "admin.auth"
            auth_file.write_text("contract_admin " + hashed + "\n")
            auth_file.chmod(0o600)
            port = unused_port()
            source = args.template.read_text()
            replacements = {
                "13-202-0-79.sslip.io {": f"http://127.0.0.1:{port} {{\n\tbind 127.0.0.1",
                "127.0.0.1:8877": f"127.0.0.1:{upstream.server_port}",
                "import /etc/caddy/demo-studio-admin.auth": f"import {auth_file}",
            }
            for old, new in replacements.items():
                if source.count(old) != 1:
                    raise RuntimeError(f"Expected exactly one fixture replacement for {old!r}")
                source = source.replace(old, new)
            # Prevent touching port 2019, production state, or any ACME endpoint.
            source = "{\n\tadmin off\n\tauto_https off\n}\n\n" + source
            config_file = tmp / "Caddyfile"
            config_file.write_text(source)
            adapted = subprocess.run(
                [args.caddy, "adapt", "--config", str(config_file), "--adapter", "caddyfile", "--validate"],
                env=env, text=True, capture_output=True, check=True, timeout=30,
            )
            parsed = json.loads(adapted.stdout)

            def descendants(value):
                if isinstance(value, dict):
                    yield value
                    for child in value.values():
                        yield from descendants(child)
                elif isinstance(value, list):
                    for child in value:
                        yield from descendants(child)

            objects = list(descendants(parsed))
            sizes = [x["max_size"] for x in objects if "max_size" in x]
            for timeout_name in ("read_timeout", "write_timeout", "response_header_timeout"):
                timeouts = [x[timeout_name] for x in objects if timeout_name in x]
                results.append({"name": "all upstream transports retain 600-second " + timeout_name, "passed": bool(timeouts) and all(t == 600_000_000_000 for t in timeouts)})
            results.append({"name": "request body limit remains one gigabyte", "passed": sizes == [1_000_000_000]})
            with (tmp / "caddy.log").open("wb") as log:
                proc = subprocess.Popen([args.caddy, "run", "--config", str(config_file), "--adapter", "caddyfile"], env=env, stdout=log, stderr=log)
                deadline = time.monotonic() + 15
                while time.monotonic() < deadline:
                    if proc.poll() is not None:
                        raise RuntimeError("Fixture Caddy failed to start; exit " + str(proc.returncode))
                    try:
                        with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                            break
                    except OSError:
                        time.sleep(0.05)
                else:
                    raise RuntimeError("Fixture Caddy did not listen within 15 seconds")

                def check(name, method, path, expected=200, auth=None, websocket=False):
                    headers = {}
                    if auth is not None:
                        headers["Authorization"] = "Basic " + base64.b64encode(("contract_admin:" + auth).encode()).decode()
                    if websocket:
                        headers.update({"Connection": "Upgrade", "Upgrade": "websocket", "Sec-WebSocket-Version": "13", "Sec-WebSocket-Key": base64.b64encode(b"fixture-ws-key-16").decode()})
                    before = len(Stub.calls)
                    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=8)
                    try:
                        connection.request(method, path, body=b"{}" if method == "POST" else None, headers=headers)
                        response = connection.getresponse()
                        status = response.status
                        if status != 101:
                            response.read()
                        reached = len(Stub.calls) > before
                        passed = status == expected and reached == (expected in (200, 101, 403))
                        if expected == 401:
                            passed = passed and "Basic" in (response.getheader("WWW-Authenticate") or "")
                        results.append({"name": name, "passed": passed, "method": method, "path": path, "status": status, "upstream_reached": reached})
                    finally:
                        connection.close()

                for path in ("/", "/api/health", "/web/app.js", "/web/player/player.js", "/web/styles.css", PREFIX + "/bundle", PREFIX + "/export.mp4"):
                    for method in ("GET", "HEAD"):
                        check("public player read", method, path)
                for path in ("sources/photo.jpg", "sources/car%20front.JPG", "derived/pdf-images/src_123/a.png", "media/mascot.png", "audio/voice.wav", "audio/voice.mp3", "sources/intro.mp4", "media/preview.webm"):
                    for method in ("GET", "HEAD"):
                        check("public player media", method, MEDIA + "/" + path)
                for action in ("qa", "tts", "pitch", "lead", "stt", "session"):
                    check("public customer action", "POST", PREFIX + "/run/" + action)
                    check("customer action GET stays private", "GET", PREFIX + "/run/" + action, 401)
                check("public websocket upgrade", "GET", PREFIX + "/run/live?session_id=s_fixture", 101, websocket=True)
                check("non-upgrade live request stays private", "GET", PREFIX + "/run/live", 401)
                for method in ("POST", "HEAD"):
                    check("live wrong method stays private", method, PREFIX + "/run/live", 401, websocket=True)
                check("signed summary delegated to app", "GET", SHARE + "?k=" + SHARE_KEY)
                check("signed summary HEAD delegated to app", "HEAD", SHARE + "?k=" + SHARE_KEY)
                check("invalid signature remains denied by app", "GET", SHARE + "?k=invalid", 403)
                check("missing share key stays private", "GET", SHARE, 401)
                check("share cannot be mutated", "POST", SHARE + "?k=" + SHARE_KEY, 401)

                private = (
                    ("GET", "/api/demos"), ("POST", "/api/demos"),
                    ("GET", PREFIX), ("PATCH", PREFIX), ("DELETE", PREFIX),
                    ("GET", PREFIX + "/sessions"), ("GET", PREFIX + "/sessions/s_fixture"),
                    ("GET", PREFIX + "/trace"), ("GET", PREFIX + "/runlog"),
                    ("GET", PREFIX + "/usage"), ("GET", PREFIX + "/events"),
                    ("GET", PREFIX + "/readiness"), ("GET", PREFIX + "/evals"),
                    ("POST", PREFIX + "/read"), ("POST", PREFIX + "/build"),
                    ("POST", PREFIX + "/feedback"), ("POST", PREFIX + "/sync"),
                    ("POST", PREFIX + "/align"), ("PATCH", PREFIX + "/align/script"),
                    ("POST", PREFIX + "/approve/script"), ("POST", PREFIX + "/sources"),
                    ("POST", PREFIX + "/rehearsal"), ("GET", "/api/cloud"),
                    ("POST", "/api/cloud/setup"), ("GET", "/docs"),
                    ("GET", "/openapi.json"), ("GET", "/redoc"),
                    ("POST", "/"), ("DELETE", "/web/app.js"),
                    ("POST", PREFIX + "/bundle"), ("DELETE", PREFIX + "/export.mp4"),
                    ("POST", MEDIA + "/sources/photo.jpg"),
                )
                for method, path in private:
                    check("private endpoint requires credentials", method, path, 401)
                for relative in ("demo.json", "trace.jsonl", "understanding.json", "sessions/s_fixture.json", "sources/private.json", "sources/private.jsonl", "sources/brochure.pdf", "sources/active.html", "sources/active.svg", "sources/active.SVG", "audio/private.json", "derived/metadata.json", "sources/photo.jpg/private.json", "sources/private.json/photo.jpg/", "private/photo.jpg", "sources/.hidden.jpg"):
                    for method in ("GET", "HEAD"):
                        check("private media or extension stays private", method, MEDIA + "/" + relative, 401)
                for path in (
                    PREFIX + "/bundle/trace", PREFIX + "/bundle.json", PREFIX + "/bundle/",
                    "/api/demos/dm_invalid/bundle", "/api/demos/dm_29df04180/bundle",
                    "/api/demos/dm_29df0418evil/run/session", "/api/demos/other/bundle",
                    "/web/../api/demos", "/web/%2e%2e/api/demos", "/web/%252e%252e/api/demos",
                    "/web/app.js/../../api/demos", "/web/%2f..%2fapi%2fdemos",
                    MEDIA + "/sources/../demo.json", MEDIA + "/sources/%2e%2e/demo.json",
                    MEDIA + "/sources/%252e%252e/demo.json", MEDIA + "/sources/%2e%2e%2fdemo.json",
                    MEDIA + "/sources/%252e%252e%252fdemo.json", MEDIA + "/sources/../sessions/private.jpg",
                    MEDIA + "/sources/%2e%2e/sessions/private.jpg", MEDIA + "/sources/%252e%252e/sessions/private.jpg",
                    MEDIA + "/sources/%5c..%5cdemo.json", MEDIA + "/sources/photo.jpg%00.json",
                    MEDIA + "/sources/photo.jpg%252fprivate.json", MEDIA + "/sources/photo.jpg%2f..%2f..%2fdemo.json",
                ):
                    check("ambiguous or traversing path stays private", "GET", path, 401)
                for path in ("/api/demos", PREFIX + "/sessions", PREFIX + "/trace", MEDIA + "/demo.json"):
                    check("wrong password denied", "GET", path, 401, auth="deliberately-wrong")
                    check("correct admin password accepted", "GET", path, auth=password)
                check("authorized editor mutation accepted", "PATCH", PREFIX + "/align/script", auth=password)
                check("authorization does not change public player", "GET", PREFIX + "/bundle", auth="deliberately-wrong")

                proc.terminate()
                proc.wait(timeout=10)
                proc = None
    finally:
        if proc is not None:
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=5)
        upstream.shutdown()
        upstream.server_close()
        worker.join(timeout=5)

    report = {"contract": "feedback proxy with real Caddy and isolated loopback upstream", "passed": sum(bool(x["passed"]) for x in results), "total": len(results), "failures": [x for x in results if not x["passed"]], "checks": results, "production_requests": 0, "provider_calls": 0}
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({key: value for key, value in report.items() if key != "checks"}, indent=2))
    return 0 if report["passed"] == report["total"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
