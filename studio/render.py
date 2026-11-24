"""Turn a script into an MP4 with ffmpeg.

Per scene: voice (TTS) + picture with a slow zoom. Then all scenes are
joined, subtitles burned in, optional background music mixed under the
voice, and the whole video fades in from black and fades out at the end.
"""
from __future__ import annotations

import json
import random
import re
from pathlib import Path

from . import tts, visuals
from .common import MUSIC_DIR, font_family_for, log, media_duration, run

ENC = ["-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p"]
AUD = ["-c:a", "aac", "-b:a", "160k", "-ar", "48000", "-ac", "2"]


def _ass_time(t: float) -> str:
    t = max(t, 0)
    h, rem = divmod(t, 3600)
    m, s = divmod(rem, 60)
    return f"{int(h)}:{int(m):02d}:{s:05.2f}"


# ------------------------------------------------------------- highlights
JOIN = "\u2060"   # invisible "word joiner": keeps a highlighted phrase on one line
_NUM_WORDS = ("zero one two three four five six seven eight nine ten eleven twelve "
              "thirteen fourteen fifteen sixteen seventeen eighteen nineteen twenty "
              "thirty forty fifty sixty seventy eighty ninety hundred thousand "
              "million billion trillion half").split()
_AUTO = re.compile(
    r"\b(?:\d[\d,.]*|(?:" + "|".join(_NUM_WORDS) + r"))"
    r"(?:[\s-]+(?:and\s+)?(?:\d[\d,.]*|(?:" + "|".join(_NUM_WORDS) + r")))*"
    r"(?:\s+[A-Za-z]+)?\b", re.IGNORECASE)


def scene_highlights(scene: dict, text: str) -> list[str]:
    """Phrases to show on a yellow box: the scene's "highlight" list if given,
    otherwise numbers (with the word after them, like "three hearts")."""
    given = scene.get("highlight")
    if isinstance(given, str):
        given = [given]
    if given:
        return [g.strip() for g in given if str(g).strip()]
    found = []
    for m in _AUTO.finditer(text):
        words = m.group(0).split()
        stop = {"and", "a", "an", "the", "of", "to", "too", "but", "or", "is", "are",
                "was", "were", "in", "on", "at", "it", "that", "so", "for", "by", "with"}
        while words and words[-1].lower() in stop:
            words = words[:-1]
        if len(words) == 1 and words[0].lower() in _NUM_WORDS:
            continue    # a lone "one" or "two" is rarely the point
        if words and len(words) <= 5:
            found.append(" ".join(words))
    return found


def protect(text: str, phrases: list[str]) -> str:
    """Glue the words of each phrase together so a caption line never splits it."""
    for ph in sorted(phrases, key=len, reverse=True):
        pat = re.compile(r"(?<!\w)" + r"\s+".join(map(re.escape, ph.split())) + r"(?!\w)",
                         re.IGNORECASE)
        text = pat.sub(lambda m: JOIN.join(m.group(0).split()), text)
    return text


def write_ass(cues: list[tuple[float, float, str]], size: tuple[int, int],
              sample_text: str, out: Path) -> Path:
    w, h = size
    portrait = h > w
    font = font_family_for(sample_text)
    fs = int(h * (0.055 if not portrait else 0.034))
    margin_v = int(h * (0.07 if not portrait else 0.22))
    head = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {w}
PlayResY: {h}
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{font},{fs},&H00FFFFFF,&H00FFFFFF,&H00000000,&H96000000,1,0,0,0,100,100,0,0,1,{max(2, fs // 14)},1,2,{int(w * .06)},{int(w * .06)},{margin_v},1
Style: Hi,{font},{fs},&H00141414,&H00141414,&H0000D6FF,&H0000D6FF,1,0,0,0,100,100,0,0,3,{max(4, fs // 10)},0,2,{int(w * .06)},{int(w * .06)},{margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lines = []
    hide, show = r"{\1a&HFF&\3a&HFF&}", r"{\1a&H00&\3a&H00&}"
    for start, end, text in cues:
        safe = text.replace("{", "(").replace("}", ")").replace("\n", " ")
        t0, t1 = _ass_time(start), _ass_time(end)
        lines.append(f"Dialogue: 0,{t0},{t1},Default,,0,0,0,,{safe.replace(JOIN, chr(92) + 'h')}")
        # yellow boxes: same text on a top layer, only the glued phrases visible
        parts = re.split(r"(\S*" + JOIN + r"\S*)", safe)
        if len(parts) > 1:
            hi = hide
            for k, part in enumerate(parts):
                if k % 2:
                    word = part.strip(".,!?;:")
                    lead, trail = part[:part.find(word)], part[part.find(word) + len(word):]
                    hi += lead + show + word.replace(JOIN, chr(92) + "h") + hide + trail
                else:
                    hi += part
            lines.append(f"Dialogue: 1,{t0},{t1},Hi,,0,0,0,,{hi}")
    out.write_text(head + "\n".join(lines) + "\n", encoding="utf-8")
    return out


def render(data: dict, cfg: dict, work: Path, out_file: Path,
           size: tuple[int, int], max_seconds: float | None = None) -> dict:
    """Render one video. Returns info incl. duration and first image path."""
    vcfg = cfg["video"]
    fps = int(vcfg.get("fps", 30))
    pause = float(vcfg.get("scene_pause", 0.35))
    work.mkdir(parents=True, exist_ok=True)
    w, h = size
    tag = f"{w}x{h}"

    clips: list[Path] = []
    all_cues: list[tuple[float, float, str]] = []
    t0 = 0.0
    first_img: Path | None = None

    map_style = str(data.get("style", "")).lower() == "map"
    timings: list[tuple[float, float]] = []
    voice_parts: list[Path] = []

    for i, scene in enumerate(data["scenes"]):
        text = str(scene["text"]).strip()
        audio = work / f"scene{i:02d}.mp3"
        if not audio.exists():                       # 16:9 and 9:16 share voice
            dur, cues = tts.speak(text, audio, cfg)
            (work / f"scene{i:02d}.cues").write_text(json.dumps(cues, ensure_ascii=False), encoding="utf-8")
        else:
            dur = media_duration(audio)
            cues = [tuple(c) for c in json.loads((work / f"scene{i:02d}.cues").read_text(encoding="utf-8"))]
        scene_len = dur + pause
        if max_seconds and t0 + scene_len > max_seconds:
            log(f"Stopping at scene {i} to stay under {max_seconds}s")
            break

        if map_style:
            part = work / f"voice{i:02d}.wav"
            run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(audio), "-af",
                 f"apad=whole_dur={scene_len:.3f}", "-t", f"{scene_len:.3f}",
                 "-ar", "48000", "-ac", "1", str(part)])
            voice_parts.append(part)
            timings.append((t0, t0 + scene_len))
            if vcfg.get("highlight", True):
                phrases = scene_highlights(scene, text)
                cues = [(cs, ce, protect(ct, phrases)) for cs, ce, ct in cues]
            for s_, e_, c_ in tts.split_cues(cues, int(vcfg.get("subtitle_max_chars", 42))):
                all_cues.append((t0 + s_, t0 + min(e_, dur), c_))
            t0 += scene_len
            continue

        img = visuals.scene_image(scene, i, data["title"], cfg, size, work / f"img{i:02d}_{tag}.jpg")
        first_img = first_img or img

        frames = max(int(scene_len * fps), 1)
        zoom = (f"1+0.07*on/{frames}" if i % 2 == 0 else f"1.07-0.07*on/{frames}")
        clip = work / f"clip{i:02d}_{tag}.mp4"
        run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(img), "-i", str(audio),
             "-filter_complex",
             f"[0:v]zoompan=z='{zoom}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
             f":d={frames}:s={w}x{h}:fps={fps},setsar=1[v];"
             f"[1:a]apad=whole_dur={scene_len:.3f}[a]",
             "-map", "[v]", "-map", "[a]", "-t", f"{scene_len:.3f}",
             *ENC, *AUD, str(clip)])
        clips.append(clip)

        if vcfg.get("highlight", True):
            phrases = scene_highlights(scene, text)
            cues = [(cs, ce, protect(ct, phrases)) for cs, ce, ct in cues]
        for s, e, c in tts.split_cues(cues, int(vcfg.get("subtitle_max_chars", 42))):
            all_cues.append((t0 + s, t0 + min(e, dur), c))
        t0 += scene_len

    joined = work / f"joined_{tag}.mp4"
    if map_style:
        if not voice_parts:
            raise RuntimeError("No scenes fit into the video")
        joined, first_img = _map_joined(data, voice_parts, timings, t0, size, fps, vcfg, work, tag)
    else:
        if not clips:
            raise RuntimeError("No scenes fit into the video")
        # Join scenes (no re-encode)
        lst = work / f"list_{tag}.txt"
        lst.write_text("".join(f"file '{c.name}'\n" for c in clips), encoding="utf-8")
        run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
             "-i", lst.name, "-c", "copy", joined.name], cwd=work)
    total = media_duration(joined)

    # Final pass: subtitles + music + fades
    fade = float(vcfg.get("fade_seconds", 0.8))
    vf = []
    if vcfg.get("subtitles", True) and all_cues:
        ass = write_ass(all_cues, size, data["title"], work / f"subs_{tag}.ass")
        vf.append(f"ass={ass.name}")
    vf.append(f"fade=t=in:st=0:d={fade}")
    vf.append(f"fade=t=out:st={max(total - fade, 0):.3f}:d={fade}")

    inputs = ["-i", joined.name]
    music = sorted(MUSIC_DIR.glob("*.mp3"))
    vol = float(vcfg.get("map_music_volume" if map_style else "music_volume",
                         vcfg.get("music_volume", 0.1)))
    track = None
    afade = f"afade=t=in:st=0:d={fade},afade=t=out:st={max(total - fade, 0):.3f}:d={fade}"
    if music and vol > 0:
        track = random.Random(data["title"]).choice(music)
        inputs += ["-stream_loop", "-1", "-i", str(track)]
        fc = (f"[0:v]{','.join(vf)}[v];[1:a]volume={vol}[m];"
              f"[0:a][m]amix=inputs=2:duration=first:dropout_transition=0:normalize=0,{afade}[a]")
    else:
        fc = f"[0:v]{','.join(vf)}[v];[0:a]{afade}[a]"

    run(["ffmpeg", "-y", "-loglevel", "error", *inputs, "-filter_complex", fc,
         "-map", "[v]", "-map", "[a]", "-t", f"{total:.3f}", *ENC, *AUD,
         "-r", str(fps), "-movflags", "+faststart", str(out_file.resolve())], cwd=work)
    log(f"Rendered {out_file.name} ({total:.1f}s, {tag})")
    return {"duration": total, "first_image": first_img, "music": track.name if track else None}


def _map_joined(data: dict, voice_parts: list[Path], timings: list[tuple[float, float]],
                total: float, size: tuple[int, int], fps: int, vcfg: dict,
                work: Path, tag: str) -> tuple[Path, Path]:
    """Map-style picture track + voice + sound effects in one file."""
    from . import motion
    lst = work / "voice_list.txt"
    lst.write_text("".join(f"file '{p.name}'\n" for p in voice_parts), encoding="utf-8")
    voice = work / "voice_all.wav"
    if not voice.exists():
        run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
             "-i", lst.name, "-c", "copy", voice.name], cwd=work)
    pic, sfx = work / f"motion_{tag}.mp4", work / f"sfx_{tag}.wav"
    motion.render_track(data["scenes"][:len(timings)], timings, total, size, fps, pic, sfx,
                        float(vcfg.get("sfx_volume", 0.5)))
    joined = work / f"joined_{tag}.mp4"
    run(["ffmpeg", "-y", "-loglevel", "error", "-i", pic.name, "-i", voice.name, "-i", sfx.name,
         "-filter_complex", "[1:a][2:a]amix=inputs=2:duration=first:normalize=0[a]",
         "-map", "0:v", "-map", "[a]", "-t", f"{total:.3f}", "-c:v", "copy", *AUD,
         joined.name], cwd=work)
    thumb = work / f"map_first_{tag}.jpg"
    run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{min(2.5, total / 2):.2f}", "-i", str(pic),
         "-frames:v", "1", str(thumb)])
    return joined, thumb
