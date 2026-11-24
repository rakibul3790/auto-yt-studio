"""Turn a script into an MP4 with ffmpeg.

Per scene: voice (TTS) + picture with a slow zoom. Then all scenes are
joined, subtitles burned in, optional background music mixed under the
voice, and the whole video fades in from black and fades out at the end.
"""
from __future__ import annotations

import json
import random
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

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lines = []
    for start, end, text in cues:
        safe = text.replace("{", "(").replace("}", ")").replace("\n", " ")
        lines.append(f"Dialogue: 0,{_ass_time(start)},{_ass_time(end)},Default,,0,0,0,,{safe}")
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

        for s, e, c in tts.split_cues(cues, int(vcfg.get("subtitle_max_chars", 42))):
            all_cues.append((t0 + s, t0 + min(e, dur), c))
        t0 += scene_len

    if not clips:
        raise RuntimeError("No scenes fit into the video")

    # Join scenes (no re-encode)
    lst = work / f"list_{tag}.txt"
    lst.write_text("".join(f"file '{c.name}'\n" for c in clips), encoding="utf-8")
    joined = work / f"joined_{tag}.mp4"
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
    vol = float(vcfg.get("music_volume", 0.1))
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
    return {"duration": total, "first_image": first_img}
