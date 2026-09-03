"""Ten-second live probe of every provider key (costs a few paise). Run after adding a key or on any provider 4xx."""
import io, sys, time, wave, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from server import config
from server.llm import claude, gemini, sarvam
from pydantic import BaseModel
class Ping(BaseModel):
    word: str
def run(name, fn):
    t0 = time.time()
    try: print(f"{name:12s} ✓ {fn()!s:.60} ({time.time()-t0:.1f}s)")
    except Exception as e: print(f"{name:12s} ✗ {str(e)[:200]}")
run("anthropic", lambda: claude.text("Reply with the single word OK.", "ping", max_tokens=20))
run("gemini", lambda: gemini.structured("Reply with the single word OK in 'word'.", [], Ping).word)
wav = {}
def tts():
    wav["hi"], _ = sarvam.tts("नमस्ते, मैं आपकी गाइड हूँ।", None, "hi-IN"); return f"{len(wav['hi'])//1024} KB"
run("sarvam_tts", tts)
run("sarvam_stt", lambda: sarvam.stt(wav["hi"], "t.wav", "hi-IN"))
run("gemini_tts", lambda: f"{len(gemini.tts('Hello.', 'Sulafat', '')[0])//1024} KB")
