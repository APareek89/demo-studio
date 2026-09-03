"""Media helpers: image codecs the models can't read (AVIF/HEIC → JPEG for the model, original kept
for the browser) and optional ffmpeg proxies for large videos (agent gets a 720p proxy, the demo
plays the original)."""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from . import store

MODEL_IMAGE_TYPES = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
CONVERT_TYPES = {".avif", ".heic", ".heif"}
_codecs_ready = False


def _codecs():
    global _codecs_ready
    if _codecs_ready:
        return
    try:
        import pillow_avif  # noqa: F401  (registers AVIF)
    except Exception:
        pass
    try:
        from pillow_heif import register_heif_opener
        register_heif_opener()
    except Exception:
        pass
    _codecs_ready = True


def model_image_path(demo_id: str, src: dict) -> Path:
    """Path to an image the models can read. AVIF/HEIC are converted once to a derived JPEG."""
    p = store.path(demo_id, src["path"])
    if p.suffix.lower() in MODEL_IMAGE_TYPES:
        return p
    derived = store.path(demo_id, "derived", p.stem + ".jpg")
    if derived.exists():
        return derived
    _codecs()
    from PIL import Image
    derived.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(p) as im:
        im = im.convert("RGB")
        if max(im.size) > 2048:
            im.thumbnail((2048, 2048))
        im.save(derived, "JPEG", quality=88)
    return derived


def image_size(demo_id: str, src: dict) -> tuple[int, int] | None:
    try:
        _codecs()
        from PIL import Image
        with Image.open(store.path(demo_id, src["path"])) as im:
            return im.size
    except Exception:
        return None


# ---------- video ----------

def ffmpeg() -> str | None:
    p = shutil.which("ffmpeg")
    if p:
        return p
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return None


def ffprobe_duration(p: Path) -> float | None:
    fp = shutil.which("ffprobe")
    if not fp:
        return None
    try:
        out = subprocess.run([fp, "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", str(p)], capture_output=True, text=True, timeout=60)
        return float(out.stdout.strip())
    except Exception:
        return None


def prepare_video(demo_id: str, src: dict, emit=lambda m: None) -> dict:
    """Returns {'model': path for Gemini, 'play': media-relative path for the player, 'proxy': bool}.
    With ffmpeg: >60 MB originals get a 720p proxy for the agent and a fast-start remux for playback.
    Without ffmpeg: the original is used for both (works; large files just upload slower)."""
    p = store.path(demo_id, src["path"])
    out = {"model": p, "play": src["path"], "proxy": False}
    ff = ffmpeg()
    size_mb = p.stat().st_size / 1e6 if p.exists() else 0
    if not ff:
        return out
    try:
        if size_mb > 60:
            proxy = store.path(demo_id, "derived", p.stem + "_proxy720.mp4")
            if not proxy.exists():
                emit(f"Making a 720p proxy of {src['name']} for the agent ({size_mb:.0f} MB original kept for playback)…")
                proxy.parent.mkdir(parents=True, exist_ok=True)
                subprocess.run([ff, "-y", "-v", "error", "-i", str(p), "-vf", "scale=-2:720", "-c:v", "libx264", "-preset", "veryfast", "-crf", "28", "-c:a", "aac", "-b:a", "96k", "-movflags", "+faststart", str(proxy)], check=True, timeout=1800)
            out["model"], out["proxy"] = proxy, True
        play = store.path(demo_id, "derived", p.stem + "_play.mp4")
        if p.suffix.lower() in (".mp4", ".m4v", ".mov") and not play.exists():
            play.parent.mkdir(parents=True, exist_ok=True)
            subprocess.run([ff, "-y", "-v", "error", "-i", str(p), "-c", "copy", "-movflags", "+faststart", str(play)], check=True, timeout=1800)
        if play.exists():
            out["play"] = f"derived/{play.name}"
    except Exception as e:
        emit(f"ffmpeg step skipped ({str(e)[:80]}) — using the original video.")
    return out
