"""Upload finished videos from ready/ to YouTube (always PRIVATE).

Put three files in ready/:
    my-video.mp4          the finished video
    my-video.json         {"video": "my-video.mp4", "title": "...", "description": "...",
                           "tags": [...], "category_id": "1", "thumbnail": "my-video.jpg"}
    my-video.jpg          optional thumbnail (1280x720)

The "Upload ready video" workflow runs this whenever a ready/*.json file is pushed.
A video whose JSON already has "url" is skipped, so nothing is uploaded twice.
"""
from __future__ import annotations

import csv
import datetime as dt
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from studio.common import LOG_FILE, load_config, log  # noqa: E402
from studio.youtube import credentials_present, upload  # noqa: E402

READY = ROOT / "ready"


def main() -> int:
    if not credentials_present():
        log("YouTube secrets are missing (YT_CLIENT_ID, YT_CLIENT_SECRET, YT_REFRESH_TOKEN).")
        return 1
    cfg = load_config()
    done = 0
    for meta_path in sorted(READY.glob("*.json")):
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        if meta.get("url"):
            log(f"Already uploaded, skipping: {meta_path.name}")
            continue
        video = READY / meta["video"]
        if not video.exists():
            log(f"Missing video file for {meta_path.name}: {video.name}")
            continue
        run_cfg = dict(cfg)
        run_cfg["channel"] = dict(cfg["channel"])
        if meta.get("category_id"):
            run_cfg["channel"]["category_id"] = str(meta["category_id"])
        run_cfg["run"] = dict(cfg.get("run", {}), privacy="private")   # never public automatically
        thumb = READY / meta["thumbnail"] if meta.get("thumbnail") else None
        vid = upload(video, meta["title"], meta.get("description", ""), meta.get("tags", []), run_cfg, thumb)
        url = f"https://youtu.be/{vid}"
        meta["url"] = url
        meta_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        new_file = not LOG_FILE.exists()
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(LOG_FILE, "a", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            if new_file:
                w.writerow(["time", "file", "title", "url", "short_url"])
            w.writerow([dt.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"), meta_path.name, meta["title"], url, ""])
        log(f"Done: {meta['title']} → {url} (Private)")
        done += 1
    log(f"Uploaded {done} video(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
