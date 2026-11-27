"""Claim the next script for this daily run, so two runs that overlap never make the same video.

    python -m studio.claim                    # claim the next script (prints file=... for GitHub)
    python -m studio.claim --release FILE     # give a claimed script back to the queue

A claim moves scripts/queue/X.json to scripts/working/X.json, writes scripts/working/X.claim
(this run's id and time) and pushes that commit straight away, before anything is rendered.
Git only accepts the push if nobody pushed in between; if another run did, this run takes the
newest state of the branch and picks again, so each script is claimed by exactly one run.
When the video is uploaded the script moves on to scripts/done/ as before; if the render
fails it goes back to the queue. A claim left behind by a run that was killed is given back
after STALE_HOURS (longer than the workflow's 5 hour limit).
"""
from __future__ import annotations

import argparse
import json
import os
import random
import shutil
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from . import queue
from .common import QUEUE_DIR, ROOT, WORKING_DIR, load_config, log

STALE_HOURS = 6
ATTEMPTS = 12


def _git(*args: str, check: bool = True) -> subprocess.CompletedProcess:
    res = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True)
    if check and res.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {res.stderr.strip()[-800:]}")
    return res


def _branch() -> str:
    b = os.environ.get("GITHUB_REF_NAME", "").strip()
    return b or _git("rev-parse", "--abbrev-ref", "HEAD").stdout.strip()


def _claims() -> list[tuple[Path, dict]]:
    out = []
    for c in sorted(WORKING_DIR.glob("*.claim")):
        try:
            info = json.loads(c.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            info = {}
        out.append((c, info))
    return out


def _age(info: dict, now: datetime) -> timedelta:
    try:
        at = datetime.strptime(str(info.get("at", "")), "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError:
        return timedelta(days=999)           # unreadable claim: treat as stale
    return now - at


def release_stale(now: datetime) -> int:
    """Give back claims older than STALE_HOURS (their run was killed or crashed)."""
    n = 0
    for c, info in _claims():
        if _age(info, now) < timedelta(hours=STALE_HOURS):
            continue
        script = c.with_suffix(".json")
        if script.exists():
            shutil.move(str(script), QUEUE_DIR / script.name)
        c.unlink()
        log(f"Gave back a stale claim: {script.name} (run {info.get('run', '?')})")
        n += 1
    # a script in working/ with no claim note at all is also given back
    for s in sorted(WORKING_DIR.glob("*.json")):
        if not s.with_suffix(".claim").exists():
            shutil.move(str(s), QUEUE_DIR / s.name)
            log(f"Gave back {s.name} (no claim note)")
            n += 1
    return n


def _output(**kv: str) -> None:
    for k, v in kv.items():
        print(f"{k}={v}", flush=True)
    path = os.environ.get("GITHUB_OUTPUT")
    if path:
        with open(path, "a", encoding="utf-8") as f:
            for k, v in kv.items():
                f.write(f"{k}={v}\n")


def claim() -> int:
    from .main import uploads_today          # the same day count the runner uses

    cfg = load_config()
    branch = _branch()
    run_id = f"{os.environ.get('GITHUB_RUN_ID', 'local')}-{os.environ.get('GITHUB_RUN_ATTEMPT', '1')}"
    for attempt in range(1, ATTEMPTS + 1):
        _git("fetch", "--quiet", "origin", branch)
        _git("reset", "--quiet", "--hard", "FETCH_HEAD")
        now = datetime.now(timezone.utc)
        queue.explode_batches()
        WORKING_DIR.mkdir(parents=True, exist_ok=True)
        release_stale(now)

        cap = int(cfg["run"].get("max_uploads_per_day", 0) or 0)
        live = len(_claims())
        if cap and uploads_today(cfg) + live >= cap:
            log(f"{uploads_today(cfg)} uploaded today and {live} being made now, the daily limit is "
                f"{cap}. Nothing to do this run.")
            _output(file="", reason="daily-limit")
            return 0
        files = queue.pending()
        if not files:
            log("The queue is empty: add new script files to scripts/queue/")
            _output(file="", reason="queue-empty")
            return 2 if cfg["run"].get("fail_when_queue_empty", True) else 0

        src = files[0]
        dst = WORKING_DIR / src.name
        shutil.move(str(src), dst)
        dst.with_suffix(".claim").write_text(
            json.dumps({"run": run_id, "at": now.strftime("%Y-%m-%dT%H:%M:%SZ")}) + "\n", encoding="utf-8")
        _git("add", "-A", "scripts")
        _git("commit", "--quiet", "-m", f"Claim {src.name} for daily run {run_id}")
        push = _git("push", "--quiet", "origin", f"HEAD:{branch}", check=False)
        if push.returncode == 0:
            rel = dst.relative_to(ROOT).as_posix()
            log(f"Claimed {src.name} for this run (attempt {attempt})")
            _output(file=rel, reason="claimed")
            return 0
        log(f"Someone else saved first (attempt {attempt}), taking the newest queue and picking again")
        time.sleep(2 + random.random() * 4)
    log("Could not claim a script after many tries")
    return 1


def main() -> int:
    ap = argparse.ArgumentParser(description="Claim a queue script for one daily run")
    ap.add_argument("--release", type=Path, help="give this claimed script back to the queue")
    args = ap.parse_args()
    if args.release:
        p = args.release if args.release.is_absolute() else ROOT / args.release
        if p.exists():
            log(f"Giving {p.name} back to the queue")
            queue.release(p)
        return 0
    return claim()


if __name__ == "__main__":
    sys.exit(main())
