"""Vercel serverless entry point.

Vercel runs the app on a fresh, read-only machine per request, with only /tmp writable
and nothing surviving between invocations. The overrides below are what let the app
*import* there; they do not make demo state persist. See Handoff.MD for the limits.
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

os.environ.setdefault("DEMO_STUDIO_DATA", "/tmp/demo-studio/demos")
os.environ.setdefault("DEMO_STUDIO_GRAPH_DB", "/tmp/demo-studio/graph.sqlite")
os.environ.setdefault("CLOUD_SYNC", "0")

from server.app import app  # noqa: E402,F401
