"""Two voices for the same 10-second Short (test only, nothing uploaded).

free: the free Edge voice, read line by line with a mood each (speed, pitch, loudness, pauses).
v3:   ElevenLabs eleven_v3 with the [tags] in "say", read ONCE. If assets/tensec/v3.mp3 is
      already there (an earlier run), it is reused and nothing is paid again.
Both get word times from the free whisper model and are written as the voice_cache that
studio/pro.py reuses, so the render itself never calls ElevenLabs.
"""
import asyncio
import json
import re
import subprocess
import sys
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
voice_tag = re.sub(r"[^A-Za-z0-9]", "", voice)[:24]
rtag = f"r{_pct(ch.get('voice_rate', '+0%')):+d}{re.sub(r'[^0-9+-]', '', str(ch.get('voice_pitch', '+0Hz')))}"
EDGE = "en-US-AndrewNeural"
# mood -> (speed, pitch, loudness, silence after the line)
MOOD = {"excited": ("+12%", "+12Hz", "+10%", 0.30),
        "whisper": ("-14%", "-6Hz", "-25%", 0.45),
        "sad": ("-15%", "-10Hz", "-15%", 0.45),
        "angry": ("+8%", "-4Hz", "+20%", 0.30),
        "": ("+4%", "+0Hz", "+0%", 0.25)}
AD = ROOT / "assets/tensec"


def write_cache(kind: str, src: Path, script: dict) -> None:
    full = " ".join(str(sc["text"]).strip() for sc in script["scenes"])
    heard = tts.heard_words(src)
    assert heard, "whisper heard nothing"
    dur = tts.media_duration(src)
    wl = tts.align_words(full, heard, dur)
    norm = lambda t: re.sub(r"[^a-z0-9]", "", t.lower())
    hn = {norm(h[2]) for h in heard}
    miss = [t for t in full.split() if norm(t) and norm(t) not in hn]
    print(f"[{kind}] {dur:.2f}s, heard: {' '.join(h[2] for h in heard)}")
    print(f"[{kind}] script words {len(full.split())}, not heard {len(miss)} {miss}")
    out = ROOT / script["voice_cache"]
    out.mkdir(parents=True, exist_ok=True)
    whole = out / f"pro_{voice_tag}_{rtag}_whole.mp3"
    whole.write_bytes(src.read_bytes())
    whole.with_suffix(".json").write_text(json.dumps([dur, wl]), encoding="utf-8")


async def edge_line(text: str, mood: str, out: Path) -> None:
    import edge_tts
    rate, pitch, vol, _ = MOOD.get(mood, MOOD[""])
    await edge_tts.Communicate(text, EDGE, rate=rate, pitch=pitch, volume=vol).save(str(out))


def free_voice(script: dict) -> Path:
    tmp = AD / "free_parts"
    tmp.mkdir(parents=True, exist_ok=True)
    inputs, filt = [], []
    for i, sc in enumerate(script["scenes"]):
        mood = str(sc.get("look", ""))
        p = tmp / f"{i:02d}.mp3"
        for attempt in range(4):
            try:
                asyncio.run(edge_line(str(sc["text"]), mood, p))
                break
            except Exception as e:
                print(f"edge-tts try {attempt + 1} failed: {e}")
        gap = MOOD.get(mood, MOOD[""])[3] if i < len(script["scenes"]) - 1 else 0.6
        inputs += ["-i", str(p)]
        filt.append(f"[{i}:a]aresample=44100,silenceremove=start_periods=1:start_threshold=-50dB,"
                    f"areverse,silenceremove=start_periods=1:start_threshold=-50dB,areverse,"
                    f"apad=pad_dur={gap}[a{i}]")
        print(f"[free] line {i + 1}: mood {mood or 'neutral'} -> {MOOD.get(mood, MOOD[''])[:3]}")
    n = len(script["scenes"])
    graph = ";".join(filt) + ";" + "".join(f"[a{i}]" for i in range(n)) + f"concat=n={n}:v=0:a=1[o]"
    out = AD / "free.mp3"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *inputs, "-filter_complex", graph,
                    "-map", "[o]", "-c:a", "libmp3lame", "-b:a", "192k", str(out)], check=True)
    return out


def v3_voice(script: dict) -> Path:
    out = AD / "v3.mp3"
    if out.exists():
        print("[v3] reusing the earlier read (no new credits)")
        return out
    say = " ".join(str(sc["say"]).strip() for sc in script["scenes"])
    print(f"[v3] {len(say)} characters: {say}")
    if len(say) > 200:
        sys.exit("[v3] over 200 characters, stopping before any paid call")
    tts.eleven_v3(say, voice.split(":", 1)[1], ch, out)
    print("[v3] read once")
    return out


free_s = json.loads((ROOT / "scripts/queue/_tensec_free.json").read_text(encoding="utf-8"))
v3_s = json.loads((ROOT / "scripts/queue/_tensec_v3.json").read_text(encoding="utf-8"))
write_cache("free", free_voice(free_s), free_s)
write_cache("v3", v3_voice(v3_s), v3_s)
