# Fabelo Studio kit

Everything needed to make a Fabelo Studio video with **Scribble** (ink stick figure, red scarf, warm paper),
from a one-line prompt, in any fresh workspace.

```
lib/scribble.js         the character + scene engine (poses, expressions, costumes, props, ink draw-on)
lib/caveat700.b64       embedded Caveat font (offline-safe titles)
CHARACTER.md            the character canon — what may and may not change
API.md                  library reference (scene, character methods, names, adding poses/props/costumes)
templates/scene.src.html  starter scene (copy for every new video)
templates/sheet.html    reference sheet of every pose / expression / costume / prop
tools/setup.sh          one-time install (Kokoro TTS models, puppeteer-core, Chrome)
tools/build.py          scene.src.html -> self-contained scene.html
tools/record.js         frame-exact recorder -> MP4 (any size: 1920x1080, 1080x1920, 1080x1080)
tools/soundtrack.py     voices + SFX + beds + piano/strings score from one JSON spec -> final MP4
examples/stand/         "Stand On Your Mistakes" — 137 s emotional short (silent hero, inner critic)
examples/night/         "How People Slept 500 Years Ago" — 120 s explainer
```

## Pipeline

```bash
bash tools/setup.sh && source .env.sh
cp templates/scene.src.html work/film.src.html      # write the scene
python3 tools/build.py work/film.src.html work/film.html
node tools/record.js work/film.html work/film_silent.mp4 --w 1920 --h 1080 --fps 30 --chrome "$CHROME_PATH"
python3 tools/soundtrack.py --spec work/film.audio.json --video work/film_silent.mp4 --models "$FABELO_MODELS" --out work/film_final.mp4
```

Recording speed is about 13–14 frames per second at 1080p (a 60 s video takes about 2–3 minutes).
