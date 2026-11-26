#!/usr/bin/env bash
# Smooth Scribble (s2): the whole pipeline for one film folder.
#
#   bash s2/tools/render_s2.sh <dir> [record options]      e.g.  bash s2/tools/render_s2.sh work/meet --w 1920 --h 1080 --fps 30 --blur 2
#
# <dir> holds film.src.html and film.audio.json (voices + emotional lines + sfx/beds/music).
# Optional <dir>/FINISH holds finish.py options (default: --grade warm --paper 0.05 --grain 0.25 --vignette 0.25).
# Steps: emotional Kokoro voices (free) → build → record (v2 recorder, motion blur) → mix (v2) → finish (v2, -14 LUFS).
# Uses the v2 tools read-only. Set PYTHON=python if python3 is not the interpreter with numpy/soundfile (Windows). Writes <dir>/final.mp4, <dir>/timing.json, <dir>/finish.json; scratch in <dir>/work/.
set -euo pipefail
D="${1:?usage: render_s2.sh <dir> [record options]}"; shift
PY="${PYTHON:-python3}"
S2="$(cd "$(dirname "$0")/.." && pwd)"; V2="$S2/../v2"
W="$D/work"; mkdir -p "$W"
: "${FABELO_MODELS:?set FABELO_MODELS (run tools/setup.sh, then source .env.sh)}"
echo "== 1/5 voices (free Kokoro, emotion shaped)"; "$PY" "$S2/tools/emo_voice.py" --spec "$D/film.audio.json" --models "$FABELO_MODELS" --out "$W/voice"
cp "$W/voice/timing.json" "$D/timing.json"
echo "== 2/5 build";  "$PY" "$S2/tools/build_s2.py" "$D/film.src.html" "$D/film.html" --timing "$W/voice/timing.json"
echo "== 3/5 record"; node "$V2/tools/record2.js" "$D/film.html" "$W/master.mp4" ${CHROME_PATH:+--chrome "$CHROME_PATH"} "$@"
echo "== 4/5 mix";    "$PY" "$V2/tools/mix.py" --spec "$D/film.audio.json" --voice "$W/voice" --out "$W/mix.wav"
echo "== 5/5 finish"
ffmpeg -y -v error -i "$W/mix.wav" -af "loudnorm=I=-14:TP=-2:LRA=11,aresample=48000" -ar 48000 "$W/mix_n.wav"
FIN="--grade warm --paper 0.05 --grain 0.25 --vignette 0.25"; [ -f "$D/FINISH" ] && FIN="$(cat "$D/FINISH")"
"$PY" "$V2/tools/finish.py" --video "$W/master.mp4" --audio "$W/mix_n.wav" --out "$D/final.mp4" --report "$D/finish.json" $FIN
echo "done → $D/final.mp4   (now QC: 2 fps contact sheets of final.mp4, look at every tile)"
