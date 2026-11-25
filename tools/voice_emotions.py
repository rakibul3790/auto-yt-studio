"""One emotional audio sample of voice XA3P1cj7XJexe6Zq0ATX with ElevenLabs eleven_v3 audio tags.

One take, one paid call. If eleven_v3 is refused (an error response, which is not
billed), it tries once with eleven_multilingual_v2 and expressive settings, tags removed.
Every call is checked against the budget first. The key is never printed.
"""
import json, os, pathlib, re, sys, urllib.error, urllib.request

VOICE = "XA3P1cj7XJexe6Zq0ATX"
MAX_CHARS_PER_CALL = 900
OUT = pathlib.Path(__file__).resolve().parent.parent / "samples" / "tuning" / "6-newvoice-emotions.mp3"

TEXT = (
    "Okay, so... I just found out something about octopuses, and honestly? [laughs] "
    "I cannot stop thinking about it. [excited] They have THREE hearts. Three! "
    "Two pump blood to the gills, and one pumps it to the whole body. "
    "But here's the sad part... [sighs] [sad] when an octopus swims, that main heart just... stops. "
    "It actually stops beating. So they get tired really fast, and they'd rather crawl. Poor little guys. "
    "[angry] And people still call them 'just seafood'?! Come ON! "
    "[gasps] Oh, and wait, wait, wait... their blood? It's BLUE. "
    "[whispers] And every single arm can taste whatever it touches... "
    "[chuckles] imagine tasting your keyboard every time you type. "
    "[laughs] Nature is completely ridiculous. And I love it."
)


def call(key, text, model, vs):
    body = {"text": text, "model_id": model, "voice_settings": vs}
    req = urllib.request.Request(
        f"https://api.elevenlabs.io/v1/text-to-speech/{VOICE}?output_format=mp3_44100_128",
        data=json.dumps(body).encode(),
        headers={"xi-api-key": key, "content-type": "application/json", "accept": "audio/mpeg"})
    with urllib.request.urlopen(req, timeout=180) as r:
        return r.read()


def main():
    key = os.environ.get("ELEVENLABS_API_KEY", "").strip()
    if not key:
        print("::error::ELEVENLABS_API_KEY is not set"); return 1
    if len(TEXT) > MAX_CHARS_PER_CALL:
        print(f"::error::Text is {len(TEXT)} characters, over budget, nothing sent"); return 1
    OUT.parent.mkdir(parents=True, exist_ok=True)
    print(f"eleven_v3 take: {len(TEXT)} characters")
    try:
        audio = call(key, TEXT, "eleven_v3", {"stability": 0.0, "similarity_boost": 0.8})
        OUT.write_bytes(audio); print(f"Made with eleven_v3: {len(audio)} bytes"); return 0
    except urllib.error.HTTPError as e:
        print(f"::warning::eleven_v3 refused: HTTP {e.code} {e.read().decode(errors='replace')[:300]}")
    plain = re.sub(r"\s*\[[a-z ]+\]\s*", " ", TEXT).strip()
    if len(plain) > MAX_CHARS_PER_CALL:
        print("::error::Fallback over budget, nothing sent"); return 1
    print(f"Fallback eleven_multilingual_v2 take: {len(plain)} characters")
    try:
        audio = call(key, plain, "eleven_multilingual_v2",
                     {"stability": 0.25, "similarity_boost": 0.8, "style": 0.7, "use_speaker_boost": True})
    except urllib.error.HTTPError as e:
        print(f"::error::Fallback failed too: HTTP {e.code} {e.read().decode(errors='replace')[:300]}"); return 1
    OUT.write_bytes(audio); print(f"Made with eleven_multilingual_v2 (fallback): {len(audio)} bytes"); return 0


if __name__ == "__main__":
    sys.exit(main())
