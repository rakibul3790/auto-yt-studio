"""ElevenLabs v3 voice for the long history video, made ONCE part by part.

- Checks the ElevenLabs balance first and stops if it would not cover what is left to make.
- Each part (a few paragraphs) is one v3 read with its [tags]. A part already in
  assets/history5/parts/ (from an earlier run) is reused, so nothing is ever paid twice.
- Only a refused or rate-limited request (not billed) is tried again; a network error is not,
  so a read is never charged twice.
- Word times come from the free whisper model; the parts are joined with short pauses
  and written as the voice_cache studio/pro.py reuses (the render never calls ElevenLabs).
"""
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import yaml  # noqa: E402

from studio import tts  # noqa: E402
from studio.pro import _pct  # noqa: E402

cfg = yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8"))
ch = cfg["channel"]
voice = str(ch["voice"])
assert voice.startswith("elevenlabs:"), voice
VOICE_ID = voice.split(":", 1)[1]
voice_tag = re.sub(r"[^A-Za-z0-9]", "", voice)[:24]
rtag = f"r{_pct(ch.get('voice_rate', '+0%')):+d}{re.sub(r'[^0-9+-]', '', str(ch.get('voice_pitch', '+0Hz')))}"
KEY = os.environ.get("ELEVENLABS_API_KEY", "").strip()
SR = 48000

script = json.loads((ROOT / "scripts/queue/_history5.json").read_text(encoding="utf-8"))
scenes = script["scenes"]
starts = script["voice_parts"]
story_starts = {si for si, _ in script["music_sections"]}
PARTS = ROOT / "assets/history5/parts"
PARTS.mkdir(parents=True, exist_ok=True)
groups = [list(range(a, b)) for a, b in zip(starts, starts[1:] + [len(scenes)])]
assert groups[0][0] == 0


def balance() -> tuple[int, int] | None:
    req = urllib.request.Request(f"{tts.ELEVEN_API}/user/subscription", headers={"xi-api-key": KEY})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            j = json.loads(r.read())
        return int(j["character_count"]), int(j["character_limit"])
    except Exception as e:
        print(f"Balance check failed: {type(e).__name__}")
        return None


def v3_once(text: str, out: Path) -> None:
    body = {"text": text, "model_id": "eleven_v3",
            "voice_settings": {"stability": float(ch.get("eleven_v3_stability", 0.0)),
                               "similarity_boost": float(ch.get("eleven_v3_similarity", 0.8))}}
    req = urllib.request.Request(
        f"{tts.ELEVEN_API}/text-to-speech/{VOICE_ID}?output_format=mp3_44100_128",
        data=json.dumps(body).encode(),
        headers={"xi-api-key": KEY, "content-type": "application/json", "accept": "audio/mpeg"})
    for attempt in range(1, 4):
        try:
            with urllib.request.urlopen(req, timeout=300) as r:
                audio = r.read()
            if len(audio) < 2000:
                raise RuntimeError("empty audio")
            out.write_bytes(audio)
            return
        except urllib.error.HTTPError as e:
            msg = e.read().decode(errors="replace")[:200]
            if e.code in (429, 500, 502, 503) and attempt < 3:      # refused, not billed: wait and retry
                print(f"ElevenLabs busy (HTTP {e.code}), waiting")
                time.sleep(15 * attempt)
                continue
            raise RuntimeError(f"ElevenLabs v3 HTTP {e.code}: {msg}")


texts = [" ".join(str(scenes[i]["say"]).strip() for i in g) for g in groups]
todo = [k for k in range(len(groups)) if not (PARTS / f"p{k:02d}.mp3").exists()]
need = sum(len(texts[k]) for k in todo)
print(f"Parts: {len(groups)}, already made: {len(groups) - len(todo)}, to make now: {len(todo)} ({need} characters)")
if todo:
    if not KEY:
        sys.exit("ELEVENLABS_API_KEY is not set")
    b = balance()
    if b is None:
        sys.exit("Could not read the ElevenLabs balance, stopping before any paid call")
    used, limit = b
    print(f"ElevenLabs balance before: {limit - used} characters left ({used} of {limit} used)")
    if need > 9000:
        sys.exit(f"Would use {need} characters, over 9000: stopping")
    if limit - used < need + 200:
        sys.exit("Not enough ElevenLabs characters left: stopping before any paid call")
    for k in todo:
        print(f"Part {k + 1}/{len(groups)}: {len(texts[k])} characters")
        v3_once(texts[k], PARTS / f"p{k:02d}.mp3")
    b = balance()
    if b:
        print(f"ElevenLabs balance after: {b[1] - b[0]} characters left (this run: {b[0] - used})")

# ---- join the parts with pauses, word times from whisper
wav_list, words, offsets, t = [], [], [], 0.0
report = []
for k, g in enumerate(groups):
    src = PARTS / f"p{k:02d}.mp3"
    clean = " ".join(str(scenes[i]["text"]).strip() for i in g)
    heard = tts.heard_words(src)
    dur = tts.media_duration(src)
    wl = tts.align_words(clean, heard, dur)
    norm = lambda x: re.sub(r"[^a-z0-9]", "", x.lower())
    hn = {norm(h[2]) for h in heard}
    miss = [w for w in clean.split() if norm(w) and norm(w) not in hn]
    print(f"Part {k + 1}: {dur:.1f}s, words {len(clean.split())}, not heard {len(miss)} {miss[:12]}")
    nxt = groups[k + 1][0] if k + 1 < len(groups) else None
    gap = 1.3 if nxt in story_starts else (0.6 if nxt is not None else 0.0)
    wav = PARTS / f"p{k:02d}.wav"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(src), "-af",
                    f"aresample={SR},apad=pad_dur={gap}", "-ar", str(SR), "-ac", "1", str(wav)], check=True)
    real = tts.media_duration(wav)
    words += [(a + t, b + t, w) for a, b, w in wl]
    offsets.append(t)
    report.append({"part": k + 1, "first_scene": g[0], "start": round(t, 2), "seconds": round(dur, 2),
                   "characters": len(texts[k]), "not_heard": miss})
    t += real
    wav_list.append(wav)
lst = PARTS / "list.txt"
lst.write_text("".join(f"file '{w.name}'\n" for w in wav_list), encoding="utf-8")
cache = ROOT / script["voice_cache"]
cache.mkdir(parents=True, exist_ok=True)
whole = cache / f"pro_{voice_tag}_{rtag}_whole.mp3"
joined = PARTS / "joined.wav"
subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", lst.name,
                "-c", "copy", joined.name], check=True, cwd=PARTS)
subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(joined), "-c:a", "libmp3lame", "-b:a", "192k",
                str(whole)], check=True)
total = tts.media_duration(joined)
assert len(words) == sum(len(str(s["text"]).split()) for s in scenes)
whole.with_suffix(".json").write_text(json.dumps([total, words]), encoding="utf-8")
(ROOT / "assets/history5/voice_report.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
print(f"Whole voice: {total:.1f}s ({total / 60:.2f} min), {len(words)} words")
for r in report:
    print(f"  part {r['part']:2d} starts {int(r['start'] // 60)}:{int(r['start'] % 60):02d}")
