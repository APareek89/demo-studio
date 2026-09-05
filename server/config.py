"""Central configuration. Keys come from .env (never from the browser)."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

DATA_DIR = Path(os.getenv("DEMO_STUDIO_DATA")).resolve() if os.getenv("DEMO_STUDIO_DATA") else ROOT / "data" / "demos"  # tests set DEMO_STUDIO_DATA=data/test-demos
WEB_DIR = ROOT / "web"
DATA_DIR.mkdir(parents=True, exist_ok=True)

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "").strip()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GCLOUD_TTS_API_KEY = os.getenv("GCLOUD_TTS_API_KEY", "").strip()
SARVAM_API_KEY = os.getenv("SARVAM_API_KEY", "").strip()
RUNWARE_API_KEY = os.getenv("RUNWARE_API_KEY", "").strip()
RUNWARE_MODEL = os.getenv("RUNWARE_MODEL", "microsoft:trellis-2@4b").strip() or "microsoft:trellis-2@4b"
RUNWARE_RESOLUTION = int(os.getenv("RUNWARE_RESOLUTION", "1024"))
SARVAM_TTS_MODEL = os.getenv("SARVAM_TTS_MODEL", "bulbul:v3").strip() or "bulbul:v3"  # v2 deprecated Sep 2026
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

CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-opus-5").strip() or "claude-opus-5"  # script, registry, Q&A — the customer-facing words
CLAUDE_PLAN_MODEL = os.getenv("CLAUDE_PLAN_MODEL", "claude-opus-5").strip() or "claude-opus-5"  # demo plan + runtime route
CLAUDE_LITE_MODEL = os.getenv("CLAUDE_LITE_MODEL", "claude-haiku-4-5-20251001").strip() or "claude-haiku-4-5-20251001"  # mechanical passes: translation, picture matching
GEMINI_IMAGE_MODEL = os.getenv("GEMINI_IMAGE_MODEL", "gemini-3.1-flash-lite-image").strip() or "gemini-3.1-flash-lite-image"  # background clean-up + mascot
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.6-flash").strip() or "gemini-3.6-flash"  # the proven vision tier (video shots + image tags); lite was the MVP downgrade
GEMINI_TTS_MODEL = "gemini-2.5-flash-preview-tts"
GCLOUD_TTS_VOICE = "en-IN-Chirp3-HD-Aoede"
GEMINI_TTS_VOICE = "Sulafat"

# Rehearsal: how many likely customer questions to generate and answer at build time.
# Each one is a paid Claude call — kept small on purpose; raise in demo settings.
REHEARSAL_QUESTIONS = int(os.getenv("REHEARSAL_QUESTIONS", "12"))

MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "1024"))  # Gemini Files API takes up to 2 GB; playback streams the original


def health() -> dict:
    return {
        "anthropic": bool(ANTHROPIC_API_KEY),
        "gemini": bool(GEMINI_API_KEY),
        "gcloud_tts": bool(GCLOUD_TTS_API_KEY),
        "sarvam": bool(SARVAM_API_KEY),
        "runware": bool(RUNWARE_API_KEY),
        "tts_provider": TTS_PROVIDER,
        "stt_provider": STT_PROVIDER,
        "mock": MOCK_LLM,
        "claude_model": CLAUDE_MODEL, "claude_plan_model": CLAUDE_PLAN_MODEL, "claude_lite_model": CLAUDE_LITE_MODEL, "gemini_image_model": GEMINI_IMAGE_MODEL,
        "gemini_model": GEMINI_MODEL,
        "runware_model": RUNWARE_MODEL,
    }
