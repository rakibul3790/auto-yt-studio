"""Word times for the ready-made octopus voice (no paid call).

Listens to assets/octopus/voice.mp3 with the free faster-whisper model, matches the
words to the script, and writes the "whole read" files that studio/pro.py already
knows how to reuse (voice_cache), so the render never calls ElevenLabs.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import yaml  # noqa: E402
from faster_whisper import WhisperModel  # noqa: E402

from studio import tts  # noqa: E402
from studio.pro import _pct  # noqa: E402

script = json.loads((ROOT / "scripts/queue/_octopus.json").read_text(encoding="utf-8"))
cfg = yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8"))
ch = cfg["channel"]
voice = str(ch["voice"])
assert voice.startswith("elevenlabs:"), voice
voice_tag = re.sub(r"[^A-Za-z0-9]", "", voice)[:24]
rate = _pct(script.get("voice_rate", ch.get("voice_rate", "+0%")))
pitch = str(script.get("voice_pitch", ch.get("voice_pitch", "+0Hz")))
rtag = f"r{rate:+d}{re.sub(r'[^0-9+-]', '', pitch)}"

src = ROOT / "assets/octopus/voice.mp3"
out = ROOT / script["voice_cache"]
out.mkdir(parents=True, exist_ok=True)
whole = out / f"pro_{voice_tag}_{rtag}_whole.mp3"

model = WhisperModel("small.en", device="cpu", compute_type="int8")
segs, _ = model.transcribe(str(src), word_timestamps=True, beam_size=5, language="en")
heard = [(float(w.start), float(w.end), w.word.strip()) for s in segs for w in s.words]
print("Heard:", " ".join(h[2] for h in heard))

full = " ".join(str(sc["text"]).strip() for sc in script["scenes"])
dur = tts.media_duration(src)
wl = tts.align_words(full, heard, dur)
tokens = full.split()
assert len(wl) == len(tokens), (len(wl), len(tokens))
norm = lambda t: re.sub(r"[^a-z0-9]", "", t.lower())
hn = {norm(h[2]) for h in heard}
miss = [t for t in tokens if norm(t) and norm(t) not in hn]
print(f"Script words: {len(tokens)}, heard words: {len(heard)}, script words not heard: {len(miss)} {miss[:20]}")
whole.write_bytes(src.read_bytes())
whole.with_suffix(".json").write_text(json.dumps([dur, wl], ensure_ascii=False), encoding="utf-8")
print(f"Wrote {whole.name} ({dur:.2f}s) and its word times")
