"""Build the History 5 edit pack folder from the render's -sources export.

usage: python build_pack.py <sources_dir> <final_mp4> <plan.json> <voice_parts_dir> <voice_report.json> <out_dir>
"""
import json, re, shutil, subprocess, sys
from pathlib import Path

src, final, plan_f, parts_dir, vrep_f, out = map(Path, sys.argv[1:7])
plan = json.loads(plan_f.read_text(encoding="utf-8"))
vrep = json.loads(vrep_f.read_text(encoding="utf-8"))
timeline = json.loads((src / "timeline.json").read_text(encoding="utf-8"))
stock = json.loads((src / "stock_sources.json").read_text(encoding="utf-8"))
music = json.loads((src / "audio/music_sections.json").read_text(encoding="utf-8")) \
    if (src / "audio/music_sections.json").exists() else []

if out.exists():
    shutil.rmtree(out)
D = {k: out / k for k in ("01_MAIN_FINAL_VIDEO", "02_AUDIO", "03_VIDEO_ONLY", "04_ELEMENTS", "05_ORIGINAL_SOURCES")}
for d in D.values():
    d.mkdir(parents=True)


def cp(a, b):
    b.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(a, b)


def dur(p):
    return float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                                          "-of", "csv=p=0", str(p)]).decode().strip())


def tc(t):
    m, s = divmod(max(t, 0.0), 60)
    return f"{int(m)}:{s:05.2f}"


# 1 main
cp(final, D["01_MAIN_FINAL_VIDEO"] / "History5_FINAL_video_with_voice_music_captions.mp4")
total = dur(final)

# 2 audio
A = D["02_AUDIO"]
cp(src / "audio/voice.wav", A / "voice_FULL_lined_up_to_video.wav")
subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(src / "audio/voice.wav"), "-b:a", "256k",
                str(A / "voice_FULL_lined_up_to_video.mp3")], check=True)
for p in sorted(parts_dir.glob("p*.mp3")):
    cp(p, A / "voice_parts" / f"voice_part_{int(p.stem[1:]) + 1:02d}.mp3")
for name in ("music_ducked.wav", "music_bed_before_ducking.wav", "sound_effects.wav", "final_mix_-14LUFS.wav",
             "music_sections.json"):
    if (src / "audio" / name).exists():
        cp(src / "audio" / name, A / name)
for m in (src / "audio/music-original").glob("*"):
    cp(m, A / "music_tracks" / m.name)

# 3 video only
V = D["03_VIDEO_ONLY"]
for a, b in (("03_video_only_no_audio_no_captions.mp4", "video_ONLY_no_voice_no_music_no_captions.mp4"),
             ("04_video_only_no_audio_with_captions.mp4", "video_ONLY_no_voice_no_music_WITH_captions.mp4"),
             ("02_video_no_captions.mp4", "video_no_captions_WITH_voice_and_music.mp4")):
    if (src / a).exists():
        cp(src / a, V / b)

# 4 elements
E = D["04_ELEMENTS"]
shutil.copytree(src / "shots", E / "shots")
shutil.copytree(src / "overlays", E / "overlays_transparent")
shutil.copytree(src / "captions", E / "captions")
cp(src / "timeline.json", E / "timeline.json")
cp(plan_f, E / "plan_used_for_render.json")

# 5 original sources
O = D["05_ORIGINAL_SOURCES"]
shutil.copytree(src / "stock-original", O / "stock_footage_as_downloaded")
for n in ("stock_sources.csv", "stock_sources.json"):
    t = (src / n).read_text(encoding="utf-8").replace("stock-original/", "stock_footage_as_downloaded/")
    (O / n).write_text(t, encoding="utf-8")
for m in (src / "audio/music-original").glob("*"):
    cp(m, O / "music_as_downloaded" / m.name)
for p in sorted(parts_dir.glob("p*.mp3")):
    cp(p, O / "voice_parts_as_made_by_elevenlabs" / f"voice_part_{int(p.stem[1:]) + 1:02d}.mp3")

# narration text (what was spoken, with emotion tags)
scenes = plan["scenes"]
vp = plan["voice_parts"] + [len(scenes)]
lines = []
for k in range(len(vp) - 1):
    lines.append(f"--- Voice part {k + 1:02d} ---")
    lines += [scenes[i]["say"] for i in range(vp[k], vp[k + 1])]
    lines.append("")
(out / "narration_with_emotion_tags.txt").write_text("\n".join(lines), encoding="utf-8")

# ---------------- README
part_starts = [r["start"] for r in vrep] if isinstance(vrep, list) else []
mood_by_scene = {i: s.get("look") for i, s in enumerate(scenes) if s.get("look")}
story_names = {0: "Hook (cold open)", 11: "Story 1: The Great Emu War (Western Australia 1932)",
               34: "Story 2: The Dancing Plague (Strasbourg 1518)",
               55: "Story 3: The Great Molasses Flood (Boston 1919)",
               77: "Story 4: The man who sold the Eiffel Tower (Paris 1925)",
               98: "Story 5: Hiroo Onoda, the soldier who kept fighting (Lubang Island 1944)",
               121: "Ending"}
R = []
w = R.append
w("# History 5: \"5 Moments in History That Sound Fake (But Really Happened)\"")
w("")
w("Edit pack for re-editing. Everything used to make the video is here, separated, with where it came from.")
w("")
w("## Quick facts")
w("")
w(f"- Length: {tc(total)} ({total:.2f} s). 1920x1080, 30 fps, H.264 (libx264, CRF 18, preset medium, High profile,"
  " yuv420p), AAC 192 kbps 48 kHz stereo, faststart.")
w("- Loudness: final mix levelled to -14 LUFS integrated, true peak about -1.5 dB (YouTube standard).")
w("- Voice: ElevenLabs, voice id XA3P1cj7XJexe6Zq0ATX, model eleven_v3, with inline emotion tags."
  " Made in 13 parts, each part once. Total cost 3,529 credits.")
w("- Known voice slip: in Story 1 (Emu War) the voice skipped the word \"later\" in \"Meredith later said\". The captions still"
  " show it. Fix it in the edit if you want (cut the caption word or re-record that one line).")
w("- Mid-roll ad point: end of Story 2, right before the BOSTON 1919 title card (see table below).")
w("- Not uploaded anywhere.")
w("")
w("## Folders")
w("")
w("- `01_MAIN_FINAL_VIDEO/`: the finished video (picture, captions, voice, music, effects).")
w("- `02_AUDIO/`: audio only.")
w("  - `voice_FULL_lined_up_to_video.wav/.mp3`: the whole narration, already lined up from 0:00 to match the video.")
w("  - `voice_parts/voice_part_01..13.mp3`: each ElevenLabs part as generated (see the part table).")
w("  - `music_tracks/`: the 7 music tracks exactly as downloaded. `music_sections.json` says where each plays.")
w("  - `music_bed_before_ducking.wav`: the 7 tracks joined with crossfades, before dipping under the voice.")
w("  - `music_ducked.wav`: the music as heard in the video (dips under the voice).")
w("  - `sound_effects.wav`: whooshes, impacts, shimmers etc. on their own track.")
w("  - `final_mix_-14LUFS.wav`: the finished mix. voice + effects + ducked music = this mix (before levelling).")
w("- `03_VIDEO_ONLY/`: picture without sound.")
w("  - `video_ONLY_no_voice_no_music_no_captions.mp4`: clean picture (title cards and number graphics are in it).")
w("  - `video_ONLY_no_voice_no_music_WITH_captions.mp4`: same picture with the captions burned in.")
w("  - `video_no_captions_WITH_voice_and_music.mp4`: no captions, full sound.")
w("- `04_ELEMENTS/`: building blocks.")
w("  - `shots/`: every shot as rendered (crop, camera move, colour grade, graphic), in timeline order.")
w("  - `overlays_transparent/`: title cards, number graphics and the animated captions as transparent .mov"
  " (PNG codec, alpha). Put them on a track above the picture.")
w("  - `captions/`: `captions_animated.ass` (exact animated style), `captions_plain.srt` (plain subtitles),"
  " `Montserrat-ExtraBold.ttf` (the font).")
w("  - `timeline.json`: every shot with start, length, transition, camera, sound effect, stock search, files.")
w("  - `plan_used_for_render.json`: the full scene plan the renderer used (text, tags, beats, graphics).")
w("- `05_ORIGINAL_SOURCES/`: every original file, untouched.")
w("  - `stock_footage_as_downloaded/`: each stock clip and photo, whole, full resolution, exactly as downloaded.")
w("  - `stock_sources.csv` / `.json`: for each file: site, id, page link, the search used, and which shots use it"
  " (the .json also says from which second of the original each shot starts).")
w("  - `music_as_downloaded/`, `voice_parts_as_made_by_elevenlabs/`: the original music and voice files.")
w("- `narration_with_emotion_tags.txt`: the exact text that was spoken, with every emotion tag, by voice part.")
w("")
w("## Sections, voice parts and music")
w("")
w("| Part | Starts at | Section | Music (Kevin MacLeod) |")
w("|---|---|---|---|")
mus_by_scene = {m.get("from_scene"): m for m in music}
for k in range(len(vp) - 1):
    si = vp[k]
    st = part_starts[k] if k < len(part_starts) else None
    sec = story_names.get(si, "")
    m = mus_by_scene.get(si)
    w(f"| {k + 1} | {tc(st) if st is not None else '-'} | {sec} | {m['track'] + ' from ' + tc(m['start']) if m else ''} |")
w("")
w("Music: each track starts 1 s before its story begins and crossfades over 2 s. Each track is levelled to"
  " -20 LUFS, then ducked under the voice (it rises in pauses and falls while the voice talks). Mood scenes change"
  " the music level: sad x0.45, whisper x0.6, excited x1.15, angry x1.25.")
w("")
w("Music licence: all tracks by Kevin MacLeod (incompetech.com), Creative Commons Attribution 4.0. Put this in the"
  " YouTube description:")
w("")
w("```")
for m in music:
    w(f"\"{Path(m['track']).stem.replace('-', ' ').title()}\" Kevin MacLeod (incompetech.com)")
w("Licensed under Creative Commons: By Attribution 4.0 License")
w("http://creativecommons.org/licenses/by/4.0/")
w("```")
w("")
w("## Emotion")
w("")
w("Voice tags used (ElevenLabs v3 inline tags, in square brackets in the narration file): " + ", ".join(
    sorted({t for s in scenes for t in re.findall(r"\[([a-z ]+)\]", s["say"])})) + ".")
w("")
w("Picture follows the mood of each scene (colour grade added on top of the stock clip):")
w("")
w("| Look | Grade (ffmpeg) | Used on scenes |")
w("|---|---|---|")
looks = {"excited": "saturation 1.25, contrast 1.06, brightness +0.02",
         "sad": "saturation 0.5, slightly darker, blue tint, vignette",
         "angry": "saturation 1.3, contrast 1.14, red tint, vignette, small camera shake",
         "whisper": "saturation 0.8, gamma 1.08 (soft), vignette"}
for lk, desc in looks.items():
    sc = [str(i + 1) for i, l in mood_by_scene.items() if l == lk]
    w(f"| {lk} | {desc} | {', '.join(sc) or '-'} |")
w("")
w("Scenes with no look keep the clip's own colours. Any clip that came out too dark is brightened"
  " (gamma 1.45, brightness +0.04).")
w("")
w("## Captions")
w("")
w("- Font: Montserrat ExtraBold (file in `04_ELEMENTS/captions/`).")
w("- Size: 6.2% of the frame height (about 67 px at 1080p). Position: centred, lower third (centre at 80% of the height).")
w("- White text, thick black outline, soft shadow. A few words per line, timed to each spoken word.")
w("- Key words pop onto a yellow pill (#FFD60A, rounded) with dark text (#121212); words pop in with a small scale bounce.")
w("- `captions_plain.srt` has the same words without animation, for YouTube subtitles or another editor.")
w("")
w("## Title cards and graphics")
w("")
w("Title cards (big text over footage): MARCH 1974, WESTERN AUSTRALIA 1932, STRASBOURG 1518, BOSTON 1919, PARIS 1925,"
  " LUBANG ISLAND 1944, and the end card SUBSCRIBE FOR MORE.")
w("Number graphics: 20,000 EMUS, 10,000 ROUNDS, 400 DANCERS, 2.3M GALLONS, 35 MPH, 29 YEARS; and a compare graphic"
  " 986 EMUS vs 9,860 BULLETS. All are in `overlays_transparent/` as separate transparent files and in the shots.")
w("")
w("## Transitions and camera")
w("")
w("- Transitions overlap the next shot by their length: whip 0.22 s (with motion blur), zoom 0.30 s, slide 0.26 s,"
  " fade, flash and glitch are short. A plain cut has none. Each shot's transition is in the shot list.")
w("- Camera moves on every shot: slow push in / pull out / drift / pan, done as a crop on the stock clip.")
w("- Sound effects sit on transitions and title cards (whoosh, impact, shimmer, riser etc.).")
w("")
w("## Shot list")
w("")
w("Times are in the final video. \"Original\" is the file in `05_ORIGINAL_SOURCES/stock_footage_as_downloaded/`.")
w("")
w("| # | Start | Length | Transition in | Kind | Camera | Sound | Stock search | Original | Site and id |")
w("|---|---|---|---|---|---|---|---|---|---|")
by_file = {}
for s in stock:
    for u in s["used_in_shots"]:
        by_file[u["shot"]] = s
for r in timeline:
    s = by_file.get(r["no"])
    orig = Path(s["file"]).name if s else "-"
    site = f"{s['site']} {s['id']}" if s and s.get("site") else "-"
    w(f"| {r['no']} | {tc(r['start'])} | {r['length']:.2f}s | {r['transition']} | {r['kind']} | {r['camera'] or '-'} |"
      f" {r['sfx'] or '-'} | {r['query']} | {orig} | {site} |")
w("")
w("Page links for every original are in `05_ORIGINAL_SOURCES/stock_sources.csv`.")
w("")
w("Stock footage licences: Pexels and Pixabay content licences (free to use and edit, no credit needed)."
  " No news photos and no copyrighted archive footage were used.")
w("")
w("## How to rebuild or change it")
w("")
w("1. Put `03_VIDEO_ONLY/video_ONLY_no_voice_no_music_no_captions.mp4` on video track 1 (or the separate shots).")
w("2. Add `02_AUDIO/voice_FULL_lined_up_to_video.wav` at 0:00. It is already in sync.")
w("3. Add `02_AUDIO/sound_effects.wav` at 0:00 and `02_AUDIO/music_ducked.wav` at 0:00 (or rebuild the music from"
  " `music_tracks/` using the times in `music_sections.json`).")
w("4. Add captions: `04_ELEMENTS/overlays_transparent/captions_transparent.mov` on top, or import"
  " `captions_animated.ass` / `captions_plain.srt`.")
w("5. Export 1920x1080, 30 fps, and level the mix to -14 LUFS.")
w("")
w("To swap a shot: find it in the shot list, take another clip (or another part of the original), keep the same start"
  " and length.")
(out / "README.md").write_text("\n".join(R) + "\n", encoding="utf-8")
if (src / "README.txt").exists():
    cp(src / "README.txt", out / "README_render_log_timeline.txt")
print("pack ready", out, f"{total:.2f}s", len(timeline), "shots", len(stock), "originals")
