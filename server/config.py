"""Central configuration. Keys come from .env (never from the browser)."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

DATA_DIR = ROOT / "data" / "demos"
WEB_DIR = ROOT / "web"
DATA_DIR.mkdir(parents=True, exist_ok=True)

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "").strip()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GCLOUD_TTS_API_KEY = os.getenv("GCLOUD_TTS_API_KEY", "").strip()
SARVAM_API_KEY = os.getenv("SARVAM_API_KEY", "").strip()
SARVAM_TTS_MODEL = os.getenv("SARVAM_TTS_MODEL", "bulbul:v2").strip() or "bulbul:v2"
SARVAM_STT_MODEL = os.getenv("SARVAM_STT_MODEL", "saarika:v2.5").strip() or "saarika:v2.5"
# Speech: Sarvam is primary for the Indian context when its key is present; Gemini / Cloud TTS / browser fall back.
_default_tts = "sarvam" if SARVAM_API_KEY else "gemini"
TTS_PROVIDER = os.getenv("TTS_PROVIDER", "").strip() or _default_tts
if TTS_PROVIDER == "sarvam" and not SARVAM_API_KEY:
    TTS_PROVIDER = "gemini"
STT_PROVIDER = os.getenv("STT_PROVIDER", "").strip() or ("sarvam" if SARVAM_API_KEY else "browser")
if STT_PROVIDER == "sarvam" and not SARVAM_API_KEY:
    STT_PROVIDER = "browser"
MOCK_LLM = os.getenv("MOCK_LLM", "").strip() == "1"  # schema-shaped fake outputs, no keys, no spend

CLAUDE_MODEL = "claude-opus-5"
GEMINI_MODEL = "gemini-2.5-flash"
GEMINI_TTS_MODEL = "gemini-2.5-flash-preview-tts"
GCLOUD_TTS_VOICE = "en-IN-Chirp3-HD-Aoede"
GEMINI_TTS_VOICE = "Sulafat"

# Rehearsal: how many likely customer questions to generate and answer at build time.
# Each one is a paid Claude call — kept small on purpose; raise in demo settings.
REHEARSAL_QUESTIONS = int(os.getenv("REHEARSAL_QUESTIONS", "12"))

MAX_UPLOAD_MB = 500


def health() -> dict:
    return {
        "anthropic": bool(ANTHROPIC_API_KEY),
        "gemini": bool(GEMINI_API_KEY),
        "gcloud_tts": bool(GCLOUD_TTS_API_KEY),
        "sarvam": bool(SARVAM_API_KEY),
        "tts_provider": TTS_PROVIDER,
        "stt_provider": STT_PROVIDER,
        "mock": MOCK_LLM,
        "claude_model": CLAUDE_MODEL,
        "gemini_model": GEMINI_MODEL,
    }
