"""Presenter Short v2 (map + weird fact, ElevenLabs eleven_v3 voice).

    python -m presenter.pro2 voice     # ONE ElevenLabs read of the whole script (GitHub only)
    python -m presenter.pro2 media     # Pixabay card photos/clips (GitHub only)
    python -m presenter.pro2 compose   # every frame, sound design, final mp4 (local)

The voice is made once and kept in presenter/out2; "voice" refuses to run again when
voice.mp3 already matches the script, so credits are never spent twice.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
P = ROOT / "presenter"
OUT2 = P / "out2"
MEDIA2 = OUT2 / "media"
TAG = re.compile(r"\[[A-Za-z][A-Za-z ]{0,24}\]")


def log(msg: str) -> None:
    print(msg, flush=True)


def load() -> dict:
    return json.loads((P / "script2.json").read_text(encoding="utf-8"))


def strip_tags(text: str) -> str:
    return " ".join(TAG.sub(" ", str(text)).split())


def say_text(data: dict) -> str:
    return " ".join(b["say"] for b in data["beats"])


def voice_key(data: dict) -> str:
    return hashlib.md5(f"{say_text(data)}|{data['voice_id']}|{data['model']}|{data['stability']}|"
                       f"{data['similarity']}".encode()).hexdigest()


# ===================================================================== voice
def voice() -> None:
    data = load()
    OUT2.mkdir(parents=True, exist_ok=True)
    mp3, kf = OUT2 / "voice.mp3", OUT2 / "voice.key"
    key = voice_key(data)
    if mp3.exists() and kf.exists() and kf.read_text().strip() == key:
        log("voice: already made for this script, not spending credits again")
    else:
        api = os.environ.get("ELEVENLABS_API_KEY", "").strip()
        if not api:
            raise SystemExit("ELEVENLABS_API_KEY is not set")
        text = say_text(data)
        log(f"voice: one eleven_v3 read, {len(text)} characters")
        body = {"text": text, "model_id": data["model"],
                "voice_settings": {"stability": float(data["stability"]),
                                   "similarity_boost": float(data["similarity"])}}
        req = urllib.request.Request(
            f"https://api.elevenlabs.io/v1/text-to-speech/{data['voice_id']}?output_format=mp3_44100_192",
            data=json.dumps(body).encode(),
            headers={"xi-api-key": api, "content-type": "application/json", "accept": "audio/mpeg"})
        audio, last = None, None
        for attempt in range(1, 3):
            try:
                with urllib.request.urlopen(req, timeout=240) as r:
                    audio = r.read()
                break
            except urllib.error.HTTPError as e:      # an error answer is not billed
                last = f"HTTP {e.code} {e.read().decode(errors='replace')[:300]}"
                if 400 <= e.code < 500:
                    break
            except Exception as e:  # noqa: BLE001
                last = str(e)
            log(f"attempt {attempt} failed: {last}")
            time.sleep(6)
        if not audio or len(audio) < 2000:
            raise SystemExit(f"ElevenLabs failed: {last}")
        mp3.write_bytes(audio)
        kf.write_text(key)
        log(f"voice: saved {len(audio)} bytes")
    # word times from the free faster-whisper model
    from faster_whisper import WhisperModel
    model = WhisperModel("small.en", device="cpu", compute_type="int8")
    segs, _ = model.transcribe(str(mp3), word_timestamps=True, beam_size=5, language="en")
    heard = [[round(float(w.start), 3), round(float(w.end), 3), w.word.strip()] for sg in segs for w in sg.words]
    (OUT2 / "heard.json").write_text(json.dumps(heard))
    log(f"heard {len(heard)} words: {' '.join(h[2] for h in heard)[:400]}")


# ===================================================================== media
def media() -> None:
    import shutil
    sys.path.insert(0, str(ROOT))
    from studio import visuals
    data = load()
    MEDIA2.mkdir(parents=True, exist_ok=True)
    work = P / "work2"
    work.mkdir(parents=True, exist_ok=True)
    for k, b in enumerate(data["beats"]):
        c = b.get("card") or {}
        if c.get("kind") == "photo":
            img = visuals.pixabay_photo(c["query"], False, 11 + k, c.get("subject"))
            if img is None and c.get("subject"):
                img = visuals.pixabay_photo(c["subject"], False, 11 + k, c.get("subject"))
            if img is not None:
                img.thumbnail((1600, 1600))
                img.convert("RGB").save(MEDIA2 / f"card_{k}.jpg", quality=90)
                log(f"card {k}: photo")
        elif c.get("kind") == "video":
            got = visuals.pixabay_video(c["query"], 0, work / f"clip_{k}.mp4", c.get("subject"))
            if got and got.stat().st_size < 60_000_000:
                shutil.copy(got, MEDIA2 / f"card_{k}.mp4")
                log(f"card {k}: video")
    # extra background clips
    for name, q, subj in [("bg_desert", "sahara desert aerial", "desert"),
                          ("bg_sand", "sand blowing wind desert", "sand")]:
        got = visuals.pixabay_video(q, 1, work / f"{name}.mp4", subj)
        if got and got.stat().st_size < 60_000_000:
            shutil.copy(got, MEDIA2 / f"{name}.mp4")
            log(f"{name}: video")


if __name__ == "__main__":
    step = sys.argv[1] if len(sys.argv) > 1 else "compose"
    if step == "compose":
        from presenter.pro2_compose import compose
        compose()
    else:
        {"voice": voice, "media": media}[step]()
