"""Scheduled publishing for the daily Shorts.

cron-job.org starts each daily run 3 hours 40 minutes before its publish slot (1:00, 2:00 and
3:00 AM Bangladesh time for the 4:40, 5:40 and 6:40 AM slots), and sends the slot as the
dispatch input "slot". The run renders, uploads the
video as Private with YouTube's publishAt set to the slot, and YouTube itself makes it
Public at that time.

Which slot a run belongs to:
  1. the dispatch input "slot" ("04:40", or "now" for an immediate Public upload), if given;
  2. otherwise the time the run was started (RUN_STARTED_AT, the run's created_at from
     GitHub, so a run that waits in GitHub's queue keeps its slot) plus run.publish_lead_minutes:
     the slot within 30 minutes of that time. 1:00 + 220 min = 4:40, 2:00 + 220 min = 5:40, ...
If no slot matches (a manual run at another time, or the old 4:40/5:40/6:40 cron times) or
the slot is already too close or past when the upload starts, the video goes Public at
once, exactly as before.

config.yaml -> run:
  publish_slots: ["04:40", "05:40", "06:40"]   # empty list = always Public at once
  publish_lead_minutes: 220
"""
from __future__ import annotations

import os
import re
from datetime import datetime, timedelta, timezone

from .common import log

try:
    from zoneinfo import ZoneInfo
    TZ = ZoneInfo("Asia/Dhaka")
except Exception:                     # no tz database: Bangladesh has no daylight saving
    TZ = timezone(timedelta(hours=6))

MATCH_WINDOW = timedelta(minutes=30)  # slots are an hour apart, so a run can only match one
MIN_AHEAD = timedelta(minutes=10)     # closer than this, publishAt is pointless (or refused)
_HHMM = re.compile(r"^\s*(\d{1,2}):(\d{2})\s*$")


def _parse_hhmm(text: str) -> tuple[int, int] | None:
    m = _HHMM.match(str(text or ""))
    if not m:
        return None
    h, mi = int(m.group(1)), int(m.group(2))
    return (h, mi) if h < 24 and mi < 60 else None


def _parse_utc(text: str) -> datetime | None:
    text = str(text or "").strip()
    if not text:
        return None
    try:
        t = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    return t if t.tzinfo else t.replace(tzinfo=timezone.utc)


def _slots(cfg: dict) -> list[tuple[int, int]]:
    out = []
    for s in (cfg.get("run") or {}).get("publish_slots") or []:
        p = _parse_hhmm(s)
        if p:
            out.append(p)
    return out


def slot_for(started: datetime, cfg: dict, wanted: str = "") -> datetime | None:
    """The publish time (aware, UTC) this run belongs to, or None for Public at once."""
    wanted = str(wanted or "").strip().lower()
    local = started.astimezone(TZ)
    if wanted == "now":
        return None
    asked = _parse_hhmm(wanted)
    if asked:                                       # the next time this clock time comes round
        t = local.replace(hour=asked[0], minute=asked[1], second=0, microsecond=0)
        if t <= local:
            t += timedelta(days=1)
        return t.astimezone(timezone.utc)
    slots = _slots(cfg)
    if not slots:
        return None
    lead = timedelta(minutes=float((cfg.get("run") or {}).get("publish_lead_minutes", 220) or 0))
    target = local + lead
    best = None
    for day in (-1, 0, 1):
        base = (target + timedelta(days=day)).date()
        for h, mi in slots:
            t = datetime(base.year, base.month, base.day, h, mi, tzinfo=TZ)
            diff = abs(t - target)
            if diff <= MATCH_WINDOW and (best is None or diff < best[0]):
                best = (diff, t)
    return best[1].astimezone(timezone.utc) if best else None


def run_started() -> datetime:
    """When this run was started (GitHub's created_at, passed in by the workflow), else now."""
    return _parse_utc(os.environ.get("RUN_STARTED_AT", "")) or datetime.now(timezone.utc)


def publish_at(cfg: dict, now: datetime | None = None) -> str | None:
    """RFC 3339 publishAt for the upload that starts now, or None to upload Public at once."""
    if (cfg.get("run") or {}).get("publish_at"):    # set by hand in config.yaml: keep it
        return str(cfg["run"]["publish_at"])
    now = now or datetime.now(timezone.utc)
    started = run_started()
    slot = slot_for(started, cfg, os.environ.get("PUBLISH_SLOT", ""))
    if slot is None:
        log(f"Publish: no slot for a run started {started.astimezone(TZ):%H:%M} (Bangladesh), Public at once")
        return None
    if slot - now < MIN_AHEAD:
        log(f"Publish: the {slot.astimezone(TZ):%H:%M} slot has already passed or is too close, Public at once")
        return None
    log(f"Publish: scheduled for {slot.astimezone(TZ):%Y-%m-%d %H:%M} Bangladesh time")
    return slot.strftime("%Y-%m-%dT%H:%M:%SZ")
