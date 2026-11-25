"""Three short audio samples of the same ElevenLabs voice with different delivery.

Budget: about 500 credits in total (1 credit per character). The script counts the
characters first and stops before any call if the total would pass the budget.
Each sample is tried once only, so a failure never spends twice. The key is read
from ELEVENLABS_API_KEY and never printed.
"""
import json
import os
import pathlib
import sys
import urllib.error
import urllib.request

VOICE = "eVbXsk380msCd98VvvmQ"
MODEL = "eleven_multilingual_v2"
BUDGET = 500
OUT = pathlib.Path(__file__).resolve().parent.parent / "samples" / "tuning"

PLAIN = ("There is an animal in Australia that makes poop shaped like little cubes. "
         "It is the wombat. Nature really does think outside the box.")
PLAYFUL = ("There's an animal in Australia... that makes poop shaped like little cubes. "
           "It's the wombat! Nature really does think outside the box.")

SAMPLES = [
    ("1-now", "the settings the daily videos use now", PLAIN,
     {"stability": 0.42, "similarity_boost": 0.85, "style": 0.25, "speed": 1.04}),
    ("2-lively", "lower stability, more style: more ups and downs in the tone", PLAIN,
     {"stability": 0.30, "similarity_boost": 0.85, "style": 0.55, "speed": 1.04}),
    ("3-playful", "lively settings plus a pause before the surprise and a lighter, happier read", PLAYFUL,
     {"stability": 0.32, "similarity_boost": 0.85, "style": 0.50, "speed": 1.06}),
]


def main() -> int:
    key = os.environ.get("ELEVENLABS_API_KEY", "").strip()
    if not key:
        print("::error::ELEVENLABS_API_KEY is not set")
        return 1
    total = sum(len(t) for _, _, t, _ in SAMPLES)
    print(f"Characters to send: {total} (budget {BUDGET})")
    if total > BUDGET:
        print("::error::Over budget, nothing sent")
        return 1
    OUT.mkdir(parents=True, exist_ok=True)
    notes = []
    for name, note, text, vs in SAMPLES:
        body = {"text": text, "model_id": MODEL,
                "voice_settings": {**vs, "use_speaker_boost": True}}
        req = urllib.request.Request(
            f"https://api.elevenlabs.io/v1/text-to-speech/{VOICE}?output_format=mp3_44100_128",
            data=json.dumps(body).encode(),
            headers={"xi-api-key": key, "content-type": "application/json", "accept": "audio/mpeg"})
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                audio = r.read()
        except urllib.error.HTTPError as e:
            print(f"::warning::{name} failed: HTTP {e.code} {e.read().decode(errors='replace')[:200]}")
            continue
        (OUT / f"{name}.mp3").write_bytes(audio)
        print(f"Made {name}: {len(text)} characters, {len(audio)} bytes")
        notes.append(f"- {name}.mp3: {note} ({len(text)} characters) {json.dumps(vs)}")
    (OUT / "README.md").write_text("# Voice tuning samples\n\n" + "\n".join(notes) + "\n")
    return 0 if notes else 1


if __name__ == "__main__":
    sys.exit(main())
