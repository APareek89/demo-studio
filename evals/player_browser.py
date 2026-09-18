#!/usr/bin/env python3
"""Serve the free browser contract at http://127.0.0.1:8892/.

Open it in the in-app browser and press Run checks. The page exercises the real
player with local fakes; this server exposes only the harness and /web files.
"""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import argparse
import mimetypes
from pathlib import Path
import subprocess
from urllib.parse import unquote, urlsplit


ROOT = Path(__file__).resolve().parents[1]
WEB = (ROOT / "web").resolve()
HARNESS = Path(__file__).with_name("player_contract.html")
PLAYER_OVERRIDE = None


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        path = unquote(urlsplit(self.path).path)
        if path in ("/", "/player_contract.html"):
            target = HARNESS
        elif path.startswith("/web/"):
            target = (WEB / path.removeprefix("/web/")).resolve()
            if not target.is_relative_to(WEB):
                self.send_error(404)
                return
        else:
            self.send_error(404)
            return
        if not target.is_file():
            self.send_error(404)
            return
        data = PLAYER_OVERRIDE if path == "/web/player/player.js" and PLAYER_OVERRIDE is not None else target.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", mimetypes.guess_type(target.name)[0] or "application/octet-stream")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Security-Policy", "default-src 'none'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'none'; media-src 'none'; font-src 'self'")
        self.end_headers()
        self.wfile.write(data)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--player-revision", help="Serve the player from a Git revision for a reproducible baseline; all other files remain current.")
    args = parser.parse_args()
    if args.player_revision:
        PLAYER_OVERRIDE = subprocess.check_output(["git", "show", f"{args.player_revision}:web/player/player.js"], cwd=ROOT)
    print("Free player contract: http://127.0.0.1:8892/ — press Run checks", flush=True)
    ThreadingHTTPServer(("127.0.0.1", 8892), Handler).serve_forever()
