"""Daily runner.

    python -m studio.main                 # make + upload the next video(s)
    python -m studio.main --no-upload     # only render (test), keep the queue
    python -m studio.main --validate      # check every script in the queue
    python -m studio.main --file scripts/queue/001-sample.json --no-upload
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

from . import queue
from .common import OUTPUT_DIR, WORK_DIR, load_config, log, require_tools


def music_credit(track: str | None) -> str:
    """The credit line a CC BY music track needs (assets/music/CREDITS.txt)."""
    from .common import MUSIC_DIR
    f = MUSIC_DIR / "CREDITS.txt"
    if not track or not f.exists():
        return ""
    for line in f.read_text(encoding="utf-8").splitlines():
        name, _, credit = line.partition("|")
        if name.strip() == track:
            return "Music: " + credit.strip()
    return ""


def description_for(data: dict, cfg: dict, shorts: bool = False, credit: str = "") -> str:
    parts = [str(data.get("description", "")).strip()]
    footer = str(cfg["channel"].get("description_footer", "") or "").strip()
    if footer:
        parts.append(footer)
    tags = data.get("hashtags") or []
    if shorts:
        tags = list(tags) + ["#Shorts"]
    if tags:
        parts.append(" ".join(t if str(t).startswith("#") else f"#{t}" for t in tags))
    if credit:
        parts.append(credit)
    return "\n\n".join(p for p in parts if p)


def process(path: Path, cfg: dict, upload: bool, voice: str | None = None) -> None:
    from . import render, visuals, voices, youtube   # heavy imports only when rendering

    data = queue.load(path)
    # Voice: a voice asked for by name (not counted in the test), else the voice test's turn
    test_voice = None
    if voice:
        chosen = voices.find(cfg, voice)
        if chosen is None:
            chosen = {"label": voice, "voice": voice}
        cfg = voices.apply(cfg, chosen)
    else:
        test_voice = voices.next_voice(cfg)
        cfg = voices.apply(cfg, test_voice)
    slug = path.stem
    work = WORK_DIR / slug
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    vcfg, scfg = cfg["video"], cfg["shorts"]

    short_only = str(data.get("format", "")).lower() == "short"

    # ---- main 16:9 video (skipped for "format": "short" scripts)
    main_mp4 = thumb = None
    credit = ""
    if not short_only:
        size = (int(vcfg.get("width", 1920)), int(vcfg.get("height", 1080)))
        main_mp4 = OUTPUT_DIR / f"{slug}.mp4"
        info = render.render(data, cfg, work, main_mp4, size)
        credit = music_credit(info.get("music"))
        if len(info.get("chapters") or []) >= 3:       # YouTube chapters (first one must be 0:00)
            ch = info["chapters"]
            lines = [f"{'0:00' if k == 0 else f'{int(t0 // 60)}:{int(t0 % 60):02d}'} {name}" for k, (t0, name) in enumerate(ch)]
            data = {**data, "description": str(data.get("description", "")).rstrip() + "\n\nChapters\n" + "\n".join(lines)}
        if data.get("thumbnail_spec") and info.get("first_image"):     # a ready drawn thumbnail
            thumb = OUTPUT_DIR / f"{slug}-thumb.jpg"
            shutil.copy(info["first_image"], thumb)
        else:
            thumb = visuals.thumbnail(data, info["first_image"], OUTPUT_DIR / f"{slug}-thumb.jpg")

    # ---- 9:16 Short (always for "format": "short", else optional)
    short_mp4 = None
    if short_only or data.get("shorts", scfg.get("enabled", False)):
        short_mp4 = OUTPUT_DIR / f"{slug}-short.mp4"
        sinfo = render.render(data, cfg, work, short_mp4, (1080, 1920),
                              max_seconds=float(scfg.get("max_seconds", 180)) - 1)
        credit = credit or music_credit(sinfo.get("music"))

    if not upload:
        log(f"Test render done (not uploaded): {main_mp4 or short_mp4}")
        return

    tags = list(cfg["channel"].get("default_tags") or []) + list(data.get("tags") or [])
    result = {"uploaded_at": queue.now_utc()}
    if short_only:
        st = data.get("short_title") or data["title"]
        if "#shorts" not in st.lower() and len(st) <= 92:
            st += " #Shorts"
        sid = youtube.upload(short_mp4, st, description_for(data, cfg, shorts=True, credit=credit), tags, cfg)
        result["short_id"] = sid
        result["short_url"] = f"https://youtube.com/shorts/{sid}"
        short_mp4 = None                      # already uploaded
    else:
        vid = youtube.upload(main_mp4, data["title"], description_for(data, cfg, credit=credit), tags, cfg, thumb)
        result["video_id"] = vid
        result["video_url"] = f"https://youtu.be/{vid}"
    if short_mp4:
        st = data.get("short_title") or data["title"]
        if "#shorts" not in st.lower() and len(st) <= 92:
            st += " #Shorts"
        try:
            sid = youtube.upload(short_mp4, st, description_for(data, cfg, shorts=True, credit=credit), tags, cfg)
            result["short_id"] = sid
            result["short_url"] = f"https://youtube.com/shorts/{sid}"
        except Exception as e:  # main video is already up: don't upload it twice
            log(f"Short upload failed: {e}")
            result["short_error"] = str(e)[:300]
    queue.mark_done(path, data, result)
    if test_voice:
        voices.record(test_voice, path.name, data["title"],
                      result.get("short_url") or result.get("video_url", ""))
    shutil.rmtree(work, ignore_errors=True)


def main() -> int:
    ap = argparse.ArgumentParser(description="Auto YT Studio")
    ap.add_argument("--count", type=int, default=None, help="videos to make now")
    ap.add_argument("--no-upload", action="store_true", help="render only")
    ap.add_argument("--validate", action="store_true", help="check queue files")
    ap.add_argument("--file", type=Path, help="process just this script file")
    ap.add_argument("--voice", help="use this voice (a label from voice_test, or a voice name)")
    args = ap.parse_args()

    cfg = load_config()

    if args.validate:
        files = [args.file] if args.file else queue.pending()
        bad = videos = 0
        for f in files:
            try:
                for d in queue.check_file(f):
                    videos += 1
                    log(f"OK   {f.name}: {d['title']} ({len(d['scenes'])} scenes)")
            except queue.ScriptError as e:
                bad += 1
                log(f"FAIL {e}")
        log(f"{videos} video(s) ready, {bad} file(s) with problems")
        return 1 if bad else 0

    if not args.file:
        queue.explode_batches()
    files = [args.file] if args.file else queue.pending()

    require_tools()
    if not files:
        log("The queue is empty: add new script files to scripts/queue/")
        return 2 if cfg["run"].get("fail_when_queue_empty", True) else 0

    from . import youtube

    upload = not args.no_upload
    if upload and not youtube.credentials_present():
        log("YouTube secrets are not set yet, so this is a TEST run (no upload).")
        upload = False

    count = args.count or int(cfg["run"].get("videos_per_run", 1))
    done = 0
    for f in files:
        if done >= count:
            break
        try:
            log(f"=== {f.name} ===")
            process(f, cfg, upload, args.voice)
            done += 1
        except queue.ScriptError as e:
            log(f"Skipping broken script: {e}")
            queue.copy_to_failed(f)
    log(f"Finished: {done} video(s)")
    return 0 if done else 1


if __name__ == "__main__":
    sys.exit(main())
