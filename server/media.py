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


# ---------- image clean-up: local first (transparent cut-outs, fringes, small images), Gemini image model when allowed ----------
CLEAN_BG_TOP = (246, 248, 252)
CLEAN_BG_BOTTOM = (226, 232, 241)


def needs_cleanup(demo_id: str, src: dict) -> tuple[bool, str]:
    """Does this image need a clean background or a size bump before it goes on stage?"""
    try:
        _codecs()
        from PIL import Image
        with Image.open(store.path(demo_id, src["path"])) as im:
            w, h = im.size
            has_alpha = im.mode in ("RGBA", "LA") or (im.mode == "P" and "transparency" in im.info)
            if has_alpha:
                a = im.convert("RGBA").getchannel("A")
                hist = a.histogram()
                total = w * h
                transparent = sum(hist[:16]) / total
                soft = sum(hist[16:240]) / total
                if transparent > 0.02:
                    return True, f"transparent background ({transparent:.0%} of pixels) with a {soft:.1%} soft edge that shows as a white fringe"
            if min(w, h) < 600:
                return True, f"small image ({w}×{h})"
            return False, "fine as uploaded"
    except Exception as e:
        return False, f"could not inspect ({str(e)[:60]})"


def clean_background_local(demo_id: str, src: dict) -> str:
    """Composite a cut-out onto a soft studio background with a floor shadow; erode the alpha edge so the
    white fringe disappears. No model involved. Returns the media-relative path of the JPEG."""
    _codecs()
    from PIL import Image, ImageDraw, ImageFilter
    p = store.path(demo_id, src["path"])
    out = store.path(demo_id, "derived", p.stem + "_clean.jpg")
    if out.exists():
        return f"derived/{out.name}"
    with Image.open(p) as im:
        im = im.convert("RGBA")
        w, h = im.size
        alpha = im.getchannel("A").filter(ImageFilter.MinFilter(3)).filter(ImageFilter.GaussianBlur(0.8))
        im.putalpha(alpha)
        scale = 1.0
        if min(w, h) < 900:
            scale = 900 / min(w, h)
            im = im.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
            alpha = im.getchannel("A")
            w, h = im.size
        cw = int(max(w * 1.16, h * 1.16 * 4 / 3))
        ch = int(max(h * 1.2, cw * 3 / 4))
        cw = int(ch * 4 / 3)
        bg = Image.new("RGB", (cw, ch), CLEAN_BG_TOP)
        draw = ImageDraw.Draw(bg)
        for y in range(ch):
            t = y / max(1, ch - 1)
            draw.line([(0, y), (cw, y)], fill=tuple(int(CLEAN_BG_TOP[i] * (1 - t) + CLEAN_BG_BOTTOM[i] * t) for i in range(3)))
        bbox = alpha.getbbox() or (0, 0, w, h)
        ox, oy = (cw - w) // 2, (ch - h) // 2
        bw, bh = bbox[2] - bbox[0], bbox[3] - bbox[1]
        sh = Image.new("L", (cw, ch), 0)
        ImageDraw.Draw(sh).ellipse([ox + bbox[0] + int(bw * 0.06), oy + bbox[3] - max(6, int(bh * 0.05)), ox + bbox[2] - int(bw * 0.06), oy + bbox[3] + max(8, int(bh * 0.06))], fill=120)
        sh = sh.filter(ImageFilter.GaussianBlur(max(8, cw // 70)))
        bg.paste(Image.new("RGB", (cw, ch), (110, 122, 140)), (0, 0), sh)
        bg.paste(im, (ox, oy), im)
        out.parent.mkdir(parents=True, exist_ok=True)
        bg.save(out, "JPEG", quality=90)
    return f"derived/{out.name}"


def clean_background_gemini(demo_id: str, src: dict) -> str | None:
    """Ask the Gemini image model for a clean studio version of the same product (no redraw). Raises on quota."""
    from ..llm import gemini
    p = model_image_path(demo_id, src)
    out = store.path(demo_id, "derived", store.path(demo_id, src["path"]).stem + "_ai.png")
    if out.exists():
        return f"derived/{out.name}"
    res = gemini.generate_image([gemini.bytes_part(p)], "Place this exact product on a clean, softly lit light studio background with a subtle floor shadow. Keep the product pixel-accurate: same shape, colours, logos, proportions and viewpoint. Do not add, remove or redraw any part of the product. Remove any jagged white fringe around the edges. Output one photo, 4:3.")
    if not res:
        return None
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(res[0])
    return f"derived/{out.name}"


def enhance_images(demo_id: str, emit=lambda m: None) -> list[dict]:
    """For every image used in the demo: decide whether it needs clean-up, do it (local, or Gemini when
    settings.enhance_images == 'ai'), and record why on the source. The original file is never touched."""
    demo = store.load(demo_id)
    mode = demo.get("settings", {}).get("enhance_images", "auto")
    done = []
    if mode == "off":
        return done
    for src in demo["sources"]:
        if src.get("kind") != "image" or src.get("use_in_demo", True) is False:
            continue
        need, why = needs_cleanup(demo_id, src)
        if not need:
            store.patch_source(demo_id, src["id"], {"enhanced": {"how": "none", "why": why}})
            continue
        how, rel = "local", None
        if mode == "ai":
            try:
                rel = clean_background_gemini(demo_id, src)
                how = "gemini"
            except Exception as e:
                emit(f"Gemini image model unavailable for {src['name']} ({str(e)[:70]}) — using the local clean-up.")
        if not rel:
            try:
                rel = clean_background_local(demo_id, src)
                how = "local"
            except Exception as e:
                emit(f"Could not clean {src['name']} ({str(e)[:70]}) — keeping the original.")
                continue
        store.patch_source(demo_id, src["id"], {"play": rel, "enhanced": {"how": how, "why": why}})
        done.append({"source": src["id"], "name": src["name"], "how": how, "why": why, "play": rel})
    if done:
        emit(f"Cleaned {len(done)} image(s) for the stage ({', '.join(d['name'] for d in done)}) — originals kept; the demo shows the clean versions.")
    return done


def generate_mascot(demo_id: str, persona: dict | None, emit=lambda m: None) -> str | None:
    """A friendly mascot for the guide, generated once per demo by the Gemini image model. Returns the
    media-relative path, or None when generation is not possible (then the player uses the built-in mascot)."""
    from ..llm import gemini
    out = store.path(demo_id, "media", "mascot.png")
    if out.exists():
        return "media/mascot.png"
    persona = persona or {}
    tone = persona.get("tone") or "warm, friendly, confident"
    prompt = (f"Design a friendly mascot for a voice-guided product demo: a small, rounded, warm character with big bright eyes, a gentle smile "
              f"and a tiny headset, personality {tone}, modern flat illustration with soft gradients in light blue and white, no text, "
              f"centered, plain white background, square.")
    try:
        res = gemini.generate_image([], prompt)
    except Exception as e:
        emit(f"Mascot not generated ({str(e)[:80]}) — the guide uses the built-in mascot.")
        return None
    if not res:
        return None
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(res[0])
    emit("Mascot ready.")
    return "media/mascot.png"
