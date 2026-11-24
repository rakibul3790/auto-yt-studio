"""Free text-to-speech.

1st choice: Microsoft Edge voices through `edge-tts` (natural, English and Bengali
voices, no key needed). Voices written as "kokoro:af_heart" or
"chatterbox:excited" use those free open-source voices instead (they run on the
GitHub runner itself, no key, no account). If that fails, it falls back to Google's free
`gTTS` voice so the daily run still produces a video.

Returns the audio file plus timed text pieces used for subtitles.
"""
from __future__ import annotations

import asyncio
import re
import time
from pathlib import Path

from .common import log, media_duration

# (start_seconds, end_seconds, text)
Cue = tuple[float, float, str]


async def _edge(text: str, voice: str, rate: str, pitch: str, out: Path) -> list[Cue]:
    import edge_tts

    comm = edge_tts.Communicate(text, voice, rate=rate, pitch=pitch,
                                boundary="SentenceBoundary")
    cues: list[Cue] = []
    with open(out, "wb") as f:
        async for chunk in comm.stream():
            if chunk["type"] == "audio":
                f.write(chunk["data"])
            elif chunk["type"] in ("SentenceBoundary", "WordBoundary"):
                start = chunk["offset"] / 10_000_000          # 100-ns ticks
                end = start + chunk["duration"] / 10_000_000
                cues.append((start, end, chunk["text"]))
    return cues


_MODELS: dict = {}


def _save_wav_mp3(samples, rate: int, out: Path) -> None:
    import subprocess
    import soundfile as sf
    wav = out.with_suffix(".tmp.wav")
    sf.write(str(wav), samples, rate)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(wav), "-ar", "24000",
                    "-b:a", "128k", str(out)], check=True)
    wav.unlink(missing_ok=True)


def _kokoro(text: str, voice: str, speed: float, out: Path) -> None:
    import numpy as np
    from kokoro import KPipeline
    pipe = _MODELS.get("kokoro") or _MODELS.setdefault("kokoro", KPipeline(lang_code=voice[0]))
    parts = [np.asarray(a) for _, _, a in pipe(text, voice=voice, speed=speed)]
    _save_wav_mp3(np.concatenate(parts), 24000, out)


CHATTERBOX_MOODS = {"natural": (0.5, 0.5), "excited": (0.8, 0.35), "calm": (0.35, 0.5)}


def _chatterbox(text: str, mood: str, out: Path) -> None:
    from chatterbox.tts import ChatterboxTTS
    model = _MODELS.get("chatterbox") or _MODELS.setdefault(
        "chatterbox", ChatterboxTTS.from_pretrained(device="cpu"))
    ex, cfg_w = CHATTERBOX_MOODS.get(mood, CHATTERBOX_MOODS["natural"])
    wav = model.generate(text, exaggeration=ex, cfg_weight=cfg_w)
    _save_wav_mp3(wav.squeeze(0).numpy(), model.sr, out)


def _rate_to_speed(rate: str) -> float:
    m = re.match(r"([+-]?\d+)%", str(rate or "+0%"))
    return 1 + int(m.group(1)) / 100 if m else 1.0


def _gtts(text: str, lang: str, out: Path) -> None:
    from gtts import gTTS

    gTTS(text, lang=lang).save(str(out))


def speak(text: str, out: Path, cfg: dict) -> tuple[float, list[Cue]]:
    """Make `out` (mp3) from text. Returns (duration_seconds, cues)."""
    ch = cfg["channel"]
    voice = ch.get("voice", "en-US-AndrewNeural")
    lang = ch.get("language", "en")
    cues: list[Cue] = []

    engine, _, name = voice.partition(":") if voice.split(":")[0] in ("kokoro", "chatterbox") \
        else ("edge", "", voice)
    if engine != "edge":
        try:
            if engine == "kokoro":
                _kokoro(text, name or "af_heart", _rate_to_speed(ch.get("voice_rate")), out)
            else:
                _chatterbox(text, name or "natural", out)
            duration = media_duration(out)
            return duration, [(0.05, max(duration - 0.1, 0.1), text)]
        except Exception as e:
            log(f"{engine} voice failed ({e}); using the Edge voice instead")
            voice = "en-US-AvaNeural"

    for attempt in range(1, 4):
        try:
            cues = asyncio.run(_edge(text, voice, ch.get("voice_rate", "+0%"),
                                     ch.get("voice_pitch", "+0Hz"), out))
            if out.exists() and out.stat().st_size > 1000:
                break
        except Exception as e:  # network hiccup, voice name typo, ...
            log(f"edge-tts attempt {attempt} failed: {e}")
            time.sleep(3 * attempt)
    else:
        log("Falling back to gTTS voice")
        _gtts(text, lang, out)
        cues = []

    duration = media_duration(out)
    if not cues:
        cues = [(0.0, duration, text)]
    return duration, cues


# ---------------------------------------------------------------- subtitles
_SENT_SPLIT = re.compile(r"(?<=[।!?.;:,])\s+")


def split_cues(cues: list[Cue], max_chars: int) -> list[Cue]:
    """Break long sentences into short subtitle lines.

    Timing inside a sentence is shared out by text length, which is close
    enough for narration and works for every language.
    """
    result: list[Cue] = []
    for start, end, text in cues:
        pieces = _chunks(text.strip(), max_chars)
        total = sum(len(p) for p in pieces) or 1
        t = start
        for p in pieces:
            d = (end - start) * len(p) / total
            result.append((t, t + d, p))
            t += d
    return result


def _chunks(text: str, max_chars: int) -> list[str]:
    parts: list[str] = []
    for clause in _SENT_SPLIT.split(text):
        words, line = clause.split(), ""
        for w in words:
            if line and len(line) + 1 + len(w) > max_chars:
                parts.append(line)
                line = w
            else:
                line = f"{line} {w}".strip()
        if line:
            parts.append(line)
    # Merge tiny leftovers ("আর", "and") into the previous line
    merged: list[str] = []
    for p in parts:
        if merged and len(p) < 8 and len(merged[-1]) + len(p) + 1 <= max_chars + 8:
            merged[-1] += " " + p
        else:
            merged.append(p)
    return merged or [text]
