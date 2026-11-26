"""Presenter Short: an AI-made host talks to camera while cards, maps and labels
pop up around them, like a face-cam YouTuber's edited Short.

    python -m presenter.build prep      # free Edge voice, host picture, stock, cutouts
    python -m presenter.build compose   # draw every frame, sound design, final mp4

The talking-head video (presenter/out/talk.mp4) is made between the two steps by
SadTalker (free, open source) in the workflow presenter-test.yml. Nothing here
uploads anything, and nothing uses ElevenLabs.
"""
from __future__ import annotations

import asyncio
import hashlib
import io
import json
import math
import os
import random
import subprocess
import sys
import time
import urllib.parse
from pathlib import Path

import numpy as np
import requests
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from studio import motion, tts, visuals
from studio.common import MUSIC_DIR, ROOT, log, media_duration, run

P = ROOT / "presenter"
OUT = P / "out"
WORK = P / "work"
W, H, FPS = 1080, 1920, 30
HOST_W, HOST_H = 1080, 1350          # the host's picture, placed at the bottom of the frame
HOST_Y = H - HOST_H
FONT = ROOT / "assets" / "fonts" / "Montserrat.ttf"
YELLOW = (255, 214, 10)
CYAN = (90, 220, 255)
TAIL = 1.3                           # seconds after the last word

CARD = (70, 140, 1010, 760)          # face layout: floating card box
PIP = (48, 1150, 48 + 380, 1150 + 475)   # map/globe layout: the host, bottom left
CAP_Y = {"face": 1470, "map": 1050, "globe": 1050}

ROUTES = {   # lon, lat
    "tern": [(-45, 71), (-30, 64), (-20, 50), (-17, 33), (-22, 15), (-15, 0), (-8, -18),
             (0, -38), (8, -55), (12, -68)],
    "godwit": [(-163, 60), (-168, 45), (-173, 28), (-178, 10), (-182, -10), (-185, -27), (-186, -38)],
}


def font(px: float) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONT), max(8, int(px)))


def ease(t: float) -> float:
    t = min(max(t, 0.0), 1.0)
    return t * t * (3 - 2 * t)


def back(t: float) -> float:          # ease-out with a small overshoot
    t = min(max(t, 0.0), 1.0)
    c = 1.70158
    return 1 + (c + 1) * (t - 1) ** 3 + c * (t - 1) ** 2


def load_script() -> dict:
    return json.loads((P / "script.json").read_text(encoding="utf-8"))


def full_text(data: dict) -> str:
    return " ".join(b["text"] for b in data["beats"])


# ====================================================================== prep
def prep() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    WORK.mkdir(parents=True, exist_ok=True)
    data = load_script()
    make_voice(data)
    make_host(data)
    make_cutouts()


def make_voice(data: dict) -> None:
    text = full_text(data)
    key = hashlib.md5(f"{text}|{data['voice']}|{data['voice_rate']}".encode()).hexdigest()
    kf = OUT / "voice.key"
    if kf.exists() and kf.read_text().strip() == key and (OUT / "voice.wav").exists():
        log("voice: unchanged, kept")
        return
    mp3 = WORK / "voice.mp3"
    heard = []
    for attempt in range(4):
        try:
            heard = asyncio.run(tts._edge_words(text, data["voice"], data["voice_rate"], "+0Hz", mp3))
            if mp3.stat().st_size > 1000:
                break
        except Exception as e:  # noqa: BLE001
            log(f"edge-tts attempt {attempt + 1} failed: {e}")
    dur = media_duration(mp3)
    words = tts.align_words(text, heard, dur)
    run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(mp3), "-ar", "48000", "-ac", "1",
         str(OUT / "voice.wav")])
    run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(mp3), "-ar", "16000", "-ac", "1",
         str(OUT / "voice16k.wav")])
    (OUT / "words.json").write_text(json.dumps([[round(a, 3), round(b, 3), t] for a, b, t in words]))
    kf.write_text(key)
    (OUT / "talk.mp4").unlink(missing_ok=True)      # lips must follow the new voice
    log(f"voice: {dur:.1f}s, {len(words)} words")


def _host_from_square(img: Image.Image) -> Image.Image:
    """A square face photo on a 1080x1350 canvas, with a soft blurred copy filling the top."""
    from PIL import ImageFilter
    sq = img.resize((HOST_W, HOST_W), Image.LANCZOS)
    bg = cover(img, (HOST_W, HOST_H)).filter(ImageFilter.GaussianBlur(40))
    canvas = bg.copy()
    mask = Image.new("L", (HOST_W, HOST_W), 255)
    fade = 140
    for y in range(fade):
        for_line = int(255 * y / fade)
        mask.paste(for_line, (0, y, HOST_W, y + 1))
    canvas.paste(sq, (0, HOST_H - HOST_W), mask)
    return canvas


def make_host(data: dict) -> None:
    out = OUT / "presenter.png"
    if out.exists():
        log("host picture: kept")
        return
    prompt = data["presenter_prompt"]
    ua = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124 Safari/537.36"}
    tries = []
    for seed in (101, 202):
        tries.append(("https://image.pollinations.ai/prompt/" + urllib.parse.quote(prompt),
                      {"width": 1080, "height": 1350, "seed": seed, "model": "flux", "nologo": "true"}))
    tries.append(("https://image.pollinations.ai/prompt/" + urllib.parse.quote(prompt),
                  {"width": 1080, "height": 1350, "seed": 303}))
    for url, params in tries:
        try:
            r = requests.get(url, timeout=180, params=params, headers=ua)
            ctype = r.headers.get("content-type", "")
            if r.status_code != 200 or not ctype.startswith("image"):
                log(f"host picture: pollinations said {r.status_code} {ctype}: {r.text[:200]!r}")
                time.sleep(5)
                continue
            img = Image.open(io.BytesIO(r.content)).convert("RGB")
            if img.width >= 700:
                img = cover(img, (HOST_W, HOST_H))
                img.save(out)
                log(f"host picture: made by pollinations ({params.get('seed')}, {img.size})")
                return
        except Exception as e:  # noqa: BLE001
            log(f"host picture attempt failed: {type(e).__name__}: {e}")
    # Fallback: a made-up face from a StyleGAN generator (not a real person).
    for _ in range(3):
        try:
            r = requests.get("https://thispersondoesnotexist.com/", timeout=60, headers=ua)
            if r.status_code == 200 and r.headers.get("content-type", "").startswith("image"):
                img = Image.open(io.BytesIO(r.content)).convert("RGB")
                _host_from_square(img).save(out)
                log(f"host picture: made by thispersondoesnotexist ({img.size})")
                return
            log(f"host picture: fallback said {r.status_code} {r.headers.get('content-type')}")
        except Exception as e:  # noqa: BLE001
            log(f"host picture fallback failed: {type(e).__name__}: {e}")
        time.sleep(3)
    raise SystemExit("Could not make the host picture")


def make_cutouts() -> None:
    """Bird pictures without their background (stickers for the map and globe)."""
    for name, query, subject in [("tern", "arctic tern flying", "tern"),
                                 ("godwit", "godwit", "godwit")]:
        out = OUT / f"cut_{name}.png"
        if out.exists():
            continue
        img = visuals.pixabay_photo(query, False, 7, subject)
        if img is None:
            log(f"cutout {name}: no photo")
            continue
        img.thumbnail((1400, 1400))
        try:
            from rembg import new_session, remove
            cut = remove(img, session=new_session("u2net"))
            bbox = cut.getbbox()
            cut = cut.crop(bbox) if bbox else cut
            cut.save(out)
            log(f"cutout {name}: {cut.size}")
        except Exception as e:  # noqa: BLE001
            log(f"cutout {name} failed: {type(e).__name__}: {e}")


# =================================================================== helpers
def cover(img: Image.Image, size: tuple[int, int], fx: float = 0.5, fy: float = 0.5) -> Image.Image:
    w, h = size
    s = max(w / img.width, h / img.height)
    im = img.resize((max(w, round(img.width * s)), max(h, round(img.height * s))), Image.LANCZOS)
    x = int((im.width - w) * fx)
    y = int((im.height - h) * fy)
    return im.crop((x, y, x + w, y + h))


def rounded_mask(size: tuple[int, int], r: int) -> Image.Image:
    m = Image.new("L", size, 0)
    ImageDraw.Draw(m).rounded_rectangle((0, 0, size[0] - 1, size[1] - 1), r, fill=255)
    return m


def shadow_for(size: tuple[int, int], r: int, blur: int = 26, alpha: int = 150) -> tuple[Image.Image, int]:
    pad = blur * 2
    s = Image.new("RGBA", (size[0] + 2 * pad, size[1] + 2 * pad), (0, 0, 0, 0))
    ImageDraw.Draw(s).rounded_rectangle((pad, pad + 12, pad + size[0], pad + size[1] + 12), r,
                                        fill=(0, 0, 0, alpha))
    return s.filter(ImageFilter.GaussianBlur(blur)), pad


def text_img(text: str, px: int, fill=(255, 255, 255), stroke=6, glow: tuple | None = None,
             stroke_fill=(0, 0, 0)) -> Image.Image:
    f = font(px)
    box = ImageDraw.Draw(Image.new("L", (1, 1))).textbbox((0, 0), text, font=f, stroke_width=stroke)
    pad = 40
    w, h = box[2] - box[0] + 2 * pad, box[3] - box[1] + 2 * pad
    out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    xy = (pad - box[0], pad - box[1])
    if glow:
        g = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        ImageDraw.Draw(g).text(xy, text, font=f, fill=glow + (255,), stroke_width=stroke + 6,
                               stroke_fill=glow + (255,))
        out.alpha_composite(g.filter(ImageFilter.GaussianBlur(14)))
    sh = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(sh).text((xy[0] + 3, xy[1] + 6), text, font=f, fill=(0, 0, 0, 140),
                            stroke_width=stroke, stroke_fill=(0, 0, 0, 140))
    out.alpha_composite(sh.filter(ImageFilter.GaussianBlur(5)))
    ImageDraw.Draw(out).text(xy, text, font=f, fill=fill, stroke_width=stroke, stroke_fill=stroke_fill)
    return out


def pill(text: str, px: int, bg=YELLOW, fg=(15, 15, 15), icon: Image.Image | None = None) -> Image.Image:
    f = font(px)
    tb = ImageDraw.Draw(Image.new("L", (1, 1))).textbbox((0, 0), text, font=f)
    tw, th = tb[2] - tb[0], tb[3] - tb[1]
    iw = icon.width + 14 if icon else 0
    w, h = tw + iw + px * 1.3, th + px * 0.9
    w, h = int(w), int(h)
    sh, pad = shadow_for((w, h), h // 2, 14, 120)
    out = Image.new("RGBA", sh.size, (0, 0, 0, 0))
    out.alpha_composite(sh)
    body = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(body).rounded_rectangle((0, 0, w - 1, h - 1), h // 2, fill=bg + (255,))
    if icon:
        body.alpha_composite(icon, (int(px * 0.55), (h - icon.height) // 2))
    ImageDraw.Draw(body).text((int(px * 0.65) + iw - tb[0], (h - th) // 2 - tb[1]), text, font=f, fill=fg)
    out.alpha_composite(body, (pad, pad))
    return out


def paste_center(frame: Image.Image, im: Image.Image, cx: float, cy: float, scale: float = 1.0,
                 alpha: float = 1.0, angle: float = 0.0) -> None:
    if scale <= 0.01 or alpha <= 0.01:
        return
    if abs(scale - 1) > 0.002:
        im = im.resize((max(1, int(im.width * scale)), max(1, int(im.height * scale))), Image.BILINEAR)
    if abs(angle) > 0.05:
        im = im.rotate(angle, resample=Image.BICUBIC, expand=True)
    if alpha < 0.999:
        a = im.getchannel("A").point(lambda v: int(v * alpha))
        im = im.copy()
        im.putalpha(a)
    x, y = int(cx - im.width / 2), int(cy - im.height / 2)
    safe_paste(frame, im, x, y)


def safe_paste(frame: Image.Image, im: Image.Image, x: int, y: int) -> None:
    x0, y0 = max(x, 0), max(y, 0)
    x1, y1 = min(x + im.width, frame.width), min(y + im.height, frame.height)
    if x1 <= x0 or y1 <= y0:
        return
    crop = im.crop((x0 - x, y0 - y, x1 - x, y1 - y))
    frame.alpha_composite(crop, (x0, y0)) if frame.mode == "RGBA" else frame.paste(crop, (x0, y0), crop)


def sticker(cut: Image.Image, size: int, outline: int = 7) -> Image.Image:
    im = cut.copy()
    im.thumbnail((size, size), Image.LANCZOS)
    pad = outline + 12
    canvas = Image.new("RGBA", (im.width + 2 * pad, im.height + 2 * pad), (0, 0, 0, 0))
    a = Image.new("L", canvas.size, 0)
    a.paste(im.getchannel("A"), (pad, pad))
    edge = a.filter(ImageFilter.MaxFilter(outline * 2 + 1))
    sh = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    sh.paste((0, 0, 0, 120), (4, 8), edge)
    canvas.alpha_composite(sh.filter(ImageFilter.GaussianBlur(6)))
    white = Image.new("RGBA", canvas.size, (255, 255, 255, 255))
    white.putalpha(edge)
    canvas.alpha_composite(white)
    canvas.alpha_composite(im, (pad, pad))
    return canvas


def no_icon(emoji: str, size: int) -> Image.Image:
    em = motion.emoji_image(emoji, int(size * 0.62))
    out = Image.new("RGBA", (size + 20, size + 20), (0, 0, 0, 0))
    d = ImageDraw.Draw(out)
    d.ellipse((10, 10, size + 10, size + 10), fill=(255, 255, 255, 235))
    out.alpha_composite(em, ((out.width - em.width) // 2, (out.height - em.height) // 2))
    lw = max(6, size // 11)
    d.ellipse((10 + lw // 2, 10 + lw // 2, size + 10 - lw // 2, size + 10 - lw // 2), outline=(230, 40, 40, 255),
              width=lw)
    c, r = (size + 20) / 2, size / 2 - lw
    k = r * 0.707
    d.line((c - k, c - k, c + k, c + k), fill=(230, 40, 40, 255), width=lw)
    return out


# ============================================================== timeline
class Timeline:
    def __init__(self, data: dict, words: list):
        self.data = data
        self.words = words
        self.beats = []
        i = 0
        n_words = len(words)
        for b in data["beats"]:
            n = len(b["text"].split())
            ws = words[i:i + n]
            self.beats.append({**b, "words": ws, "w0": i})
            i += n
        assert i == n_words, (i, n_words)
        self.voice_end = words[-1][1]
        self.total = self.voice_end + TAIL
        for k, b in enumerate(self.beats):
            b["start"] = 0.0 if k == 0 else max(b["words"][0][0] - 0.12, 0)
        for k, b in enumerate(self.beats):
            b["end"] = self.beats[k + 1]["start"] if k + 1 < len(self.beats) else self.total

    def word_time(self, beat: dict, word: str | None, default: float) -> float:
        if not word:
            return beat["start"] + default
        for a, _, t in beat["words"]:
            if tts._norm(t).startswith(tts._norm(word)):
                return a
        return beat["start"] + default

    def beat_at(self, t: float) -> tuple[int, dict]:
        for k, b in enumerate(self.beats):
            if b["start"] <= t < b["end"]:
                return k, b
        return len(self.beats) - 1, self.beats[-1]


# ================================================================ sources
class HostVideo:
    """Frames of the talking host, in step with the output frames."""

    def __init__(self):
        talk = OUT / "talk.mp4"
        self.still = Image.open(OUT / "presenter.png").convert("RGB").resize((HOST_W, HOST_H))
        self.proc = None
        self.last = self.still
        self.n = 0
        if talk.exists():
            self.proc = subprocess.Popen(
                ["ffmpeg", "-loglevel", "error", "-i", str(talk), "-vf",
                 f"fps={FPS},scale={HOST_W}:{HOST_H}:flags=lanczos", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                stdout=subprocess.PIPE)
            log("host: using the talking video")
        else:
            log("host: talk.mp4 missing, using the still picture (no lip movement)")

    def next(self) -> Image.Image:
        self.n += 1
        if self.proc:
            raw = self.proc.stdout.read(HOST_W * HOST_H * 3)
            if len(raw) == HOST_W * HOST_H * 3:
                self.last = Image.frombuffer("RGB", (HOST_W, HOST_H), raw, "raw", "RGB", 0, 1)
        return self.last


class ClipFrames:
    """A stock video clip decoded at card size."""

    def __init__(self, path: Path, size: tuple[int, int]):
        self.size = size
        w, h = size
        self.proc = subprocess.Popen(
            ["ffmpeg", "-loglevel", "error", "-ss", "0.5", "-stream_loop", "-1", "-i", str(path), "-vf",
             f"fps={FPS},scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h}",
             "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE)
        self.last = Image.new("RGB", size, (20, 30, 40))

    def next(self) -> Image.Image:
        raw = self.proc.stdout.read(self.size[0] * self.size[1] * 3)
        if len(raw) == self.size[0] * self.size[1] * 3:
            self.last = Image.frombuffer("RGB", self.size, raw, "raw", "RGB", 0, 1)
        return self.last


def card_media(tl: Timeline) -> dict:
    """Photo or clip for every face-layout card (Pixabay, free licence)."""
    media = {}
    cw, ch = CARD[2] - CARD[0], CARD[3] - CARD[1]
    for k, b in enumerate(tl.beats):
        c = b.get("card")
        if not c or c["kind"] not in ("photo", "video"):
            continue
        if c["kind"] == "photo":
            img = visuals.pixabay_photo(c["query"], False, 11 + k, c.get("subject"))
            if img is None and c.get("subject"):
                img = visuals.pixabay_photo(c["subject"], False, 11 + k, c.get("subject"))
            if img is not None:
                media[k] = ("photo", img)
        else:
            out = WORK / f"clip_{k}.mp4"
            got = visuals.pixabay_video(c["query"], 0, out, c.get("subject"))
            if got:
                media[k] = ("video", ClipFrames(got, (cw, ch)))
        log(f"card {k}: {media.get(k, ('none',))[0]}")
    return media


# ================================================================== world
class Map:
    def __init__(self):
        self.world = motion.World()
        self.stars = motion._stars((W, H))
        self.vignette = self._vignette()

    def _vignette(self) -> Image.Image:
        y, x = np.mgrid[0:H, 0:W].astype(np.float32)
        d = np.sqrt(((x - W / 2) / (W * 0.75)) ** 2 + ((y - H / 2) / (H * 0.7)) ** 2)
        a = np.clip((d - 0.55) * 260, 0, 150).astype(np.uint8)
        v = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        v.putalpha(Image.fromarray(a))
        return v

    def cam(self, lon, lat, wd):
        w = self.world
        wd = min(max(wd, 360.0 * W * 0.55 / w.w), 180.0 * W / H)
        hdeg = wd * H / W
        lat = min(max(lat, -90 + hdeg / 2), 90 - hdeg / 2)
        return lon, lat, wd

    def project(self, cam, lon, lat):
        clon, clat, wd = cam
        x = (lon - clon) / wd * W + W / 2
        y = (clat - lat) / wd * W + H / 2
        return x, y

    def view(self, cam) -> Image.Image:
        return self.world.view(cam[0], cam[1], cam[2], (W, H)).convert("RGBA")


def smooth(points: list[tuple[float, float]], n: int = 200) -> list[tuple[float, float]]:
    pts = [points[0]] + points + [points[-1]]
    out = []
    for i in range(1, len(pts) - 2):
        p0, p1, p2, p3 = pts[i - 1], pts[i], pts[i + 1], pts[i + 2]
        for s in range(n // (len(points) - 1)):
            t = s / (n // (len(points) - 1))
            t2, t3 = t * t, t * t * t
            out.append(tuple(0.5 * ((2 * p1[j]) + (-p0[j] + p2[j]) * t + (2 * p0[j] - 5 * p1[j] + 4 * p2[j] - p3[j]) * t2
                                    + (-p0[j] + 3 * p1[j] - 3 * p2[j] + p3[j]) * t3) for j in range(2)))
    out.append(points[-1])
    return out


ROUTE_PTS = {k: smooth(v) for k, v in ROUTES.items()}


def route_prog(m: dict, bt: float, blen: float) -> float:
    a, z = m.get("route_draw", [0, 0])
    if [a, z] == [0, 0]:
        return 1.0
    return ease((bt / blen - a) / max(z - a, 0.05))


def draw_route(frame: Image.Image, mp: Map, cam, name: str, prog: float) -> tuple[float, float] | None:
    pts = ROUTE_PTS[name]
    n = max(2, int(len(pts) * prog))
    if prog <= 0.001:
        return None
    xy = [mp.project(cam, *p) for p in pts[:n]]
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    gd.line(xy, fill=CYAN + (200,), width=26, joint="curve")
    frame.alpha_composite(glow.filter(ImageFilter.GaussianBlur(14)))
    d = ImageDraw.Draw(frame)
    d.line(xy, fill=(150, 235, 255, 255), width=9, joint="curve")
    d.line(xy, fill=(255, 255, 255, 255), width=4, joint="curve")
    return xy[-1]


def dashed_lat(frame: Image.Image, mp: Map, cam, lat: float, color, label: str, prog: float) -> None:
    _, y = mp.project(cam, cam[0], lat)
    if not -50 < y < H + 50:
        return
    d = ImageDraw.Draw(frame)
    end = W * prog
    x = 0
    while x < end:
        d.line((x, y, min(x + 34, end), y), fill=color + (240,), width=6)
        x += 56
    if prog > 0.5:
        t = text_img(label, 34, fill=color, stroke=4)
        paste_center(frame, t, W - t.width / 2 - 20, y - 34, alpha=min(1, (prog - 0.5) * 3))


# ================================================================ compose
def compose() -> None:
    data = load_script()
    words = [tuple(w) for w in json.loads((OUT / "words.json").read_text())]
    tl = Timeline(data, words)
    log(f"compose: {tl.total:.1f}s, {len(tl.beats)} beats")
    WORK.mkdir(parents=True, exist_ok=True)
    host = HostVideo()
    mp = Map()
    media = card_media(tl)
    cuts = {}
    for name in ("tern", "godwit"):
        f = OUT / f"cut_{name}.png"
        if f.exists():
            cuts[name] = Image.open(f).convert("RGBA")
    stick = {k: sticker(v, 150) for k, v in cuts.items()}
    big_tern = sticker(cuts["tern"], 430, 9) if "tern" in cuts else None

    # face layout background: the top of the room, blurred
    still = host.still
    top = cover(still.crop((0, 0, HOST_W, int(HOST_H * 0.45))), (W, HOST_Y + 300))
    face_bg = Image.new("RGB", (W, H))
    face_bg.paste(top.filter(ImageFilter.GaussianBlur(28)), (0, 0))
    dark = Image.new("RGBA", (W, HOST_Y + 300), (8, 12, 22, 110))
    face_bg = face_bg.convert("RGBA")
    face_bg.alpha_composite(dark)
    host_mask = Image.new("L", (HOST_W, HOST_H), 255)
    ramp = np.linspace(0, 255, 220).astype(np.uint8)[:, None].repeat(HOST_W, 1)
    host_mask.paste(Image.fromarray(ramp), (0, 0))

    cw, ch = CARD[2] - CARD[0], CARD[3] - CARD[1]
    card_shadow, card_pad = shadow_for((cw, ch), 38)
    card_round = rounded_mask((cw, ch), 38)
    pw, ph = PIP[2] - PIP[0], PIP[3] - PIP[1]
    pip_round = rounded_mask((pw, ph), 34)
    pip_shadow, pip_pad = shadow_for((pw + 12, ph + 12), 40, 20, 160)

    globe_glow = Image.new("RGBA", (W, W), (0, 0, 0, 0))
    ImageDraw.Draw(globe_glow).ellipse((W / 2 - 470, W / 2 - 470, W / 2 + 470, W / 2 + 470), fill=(60, 200, 255, 150))
    globe_glow = globe_glow.filter(ImageFilter.GaussianBlur(40))

    chunks = caption_chunks(words)
    sfx: list[tuple[str, float, float]] = []
    pre = prerender(tl, sfx)

    nframes = int(math.ceil(tl.total * FPS))
    raw_video = WORK / "video.mp4"
    enc = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
                            "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "medium",
                            "-crf", "18", "-pix_fmt", "yuv420p", str(raw_video)], stdin=subprocess.PIPE)
    shots = {}
    prev_layout = None
    only = {int(float(x) * FPS) for x in os.environ.get("PREVIEW_TIMES", "").split(",") if x}
    if only:
        enc.stdin.close()
    for fi in range(nframes):
        t = fi / FPS
        if only and fi not in only:
            host.next()
            continue
        k, b = tl.beat_at(t)
        bt = t - b["start"]
        blen = b["end"] - b["start"]
        lay = b["layout"]
        hf = host.next()
        if k not in shots:
            shots[k] = True
            if prev_layout is not None and lay != prev_layout:
                sfx.append(("whoosh", max(b["start"] - 0.12, 0), 0.9))
            prev_layout = lay
        if lay == "face":
            frame = face_bg.copy()
            z = 1.0 + 0.035 * (bt / blen if k % 2 == 0 else 1 - bt / blen)
            hz = hf.resize((int(HOST_W * z), int(HOST_H * z)), Image.BILINEAR)
            ox = (hz.width - HOST_W) // 2
            hz = hz.crop((ox, 0, ox + HOST_W, HOST_H))
            frame.paste(hz, (0, HOST_Y), host_mask)
            draw_card(frame, tl, k, b, bt, blen, media, pre, card_shadow, card_pad, card_round)
        else:
            if lay == "map":
                m = b["map"]
                pr = ease(bt / max(blen, 0.1))
                c = [m["from"][i] + (m["to"][i] - m["from"][i]) * pr for i in range(3)]
                if m.get("follow") and m.get("route") in ROUTE_PTS:
                    rp = route_prog(m, bt, blen)
                    pts = ROUTE_PTS[m["route"]]
                    hx, hy = pts[min(len(pts) - 1, int((len(pts) - 1) * rp))]
                    c[0] = c[0] * 0.35 + hx * 0.65
                    c[1] = c[1] * 0.2 + (hy - 6) * 0.8
                cam = mp.cam(*c)
                frame = mp.view(cam)
                draw_map_layer(frame, mp, cam, tl, k, b, bt, blen, stick, pre)
            else:
                frame = mp.stars.convert("RGBA")
                spin = -75 + 40 * (bt / blen) if not b.get("end") else -20 + 30 * (bt / blen)
                r = 420
                gl = mp.world.globe(spin, r, tilt=32)
                cy = 800
                frame.alpha_composite(globe_glow, (0, int(cy - W / 2)))
                frame.alpha_composite(gl, (W // 2 - r, cy - r))
                if big_tern is not None:
                    p = bt / blen
                    x = -250 + (W + 500) * ease(min(p * 1.05, 1)) if not b.get("end") else 540 + 40 * math.sin(bt * 2)
                    y = 470 + 40 * math.sin(bt * 3.2) if not b.get("end") else 380 + 18 * math.sin(bt * 3)
                    paste_center(frame, big_tern, x, y, scale=0.9 + 0.1 * math.sin(bt * 6), angle=4 * math.sin(bt * 3))
                lab = pre["labels"].get(k)
                if lab:
                    lt = tl.word_time(b, b.get("label_word"), 0.35) - b["start"]
                    s = back((bt - lt) / 0.35)
                    paste_center(frame, lab, W / 2, 230, scale=s, alpha=min(1, max(0, (bt - lt) / 0.15)))
                    if 0 <= bt - lt < 1 / FPS:
                        sfx.append(("pop", t, 1.0))
            frame.alpha_composite(mp.vignette)
            draw_pip(frame, hf, pip_round, pip_shadow, pip_pad)
        draw_caption(frame, chunks, t, CAP_Y[lay])
        # punch-in on a layout change
        if k > 0 and lay != tl.beats[k - 1]["layout"] and bt < 0.2:
            s = 1 + 0.08 * (1 - ease(bt / 0.2))
            big = frame.resize((int(W * s), int(H * s)), Image.BILINEAR)
            ox, oy = (big.width - W) // 2, (big.height - H) // 2
            frame = big.crop((ox, oy, ox + W, oy + H))
            fl = Image.new("RGBA", (W, H), (255, 255, 255, int(110 * (1 - bt / 0.2))))
            frame.alpha_composite(fl)
        # fade in / out
        fade = min(1.0, t / 0.18, (tl.total - t) / 0.8)
        if fade < 1:
            blk = Image.new("RGBA", (W, H), (0, 0, 0, int(255 * (1 - max(fade, 0)))))
            frame.alpha_composite(blk)
        rgb = frame.convert("RGB")
        if only:
            rgb.save(WORK / f"preview_{t:05.2f}.jpg", quality=88)
            continue
        enc.stdin.write(rgb.tobytes())
        if fi in pre["previews"]:
            (OUT / "frames").mkdir(exist_ok=True)
            rgb.resize((540, 960)).save(OUT / "frames" / f"f{fi:05d}.jpg", quality=85)
        if fi % 300 == 0:
            log(f"frame {fi}/{nframes}")
    if only:
        return
    enc.stdin.close()
    enc.wait()

    # sound
    sfx_wav = WORK / "sfx.wav"
    motion.write_sfx(sorted(sfx, key=lambda e: e[1]), tl.total, sfx_wav, volume=0.55, voice=OUT / "voice.wav")
    voice_pad = WORK / "voice_full.wav"
    run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(OUT / "voice.wav"), "-af",
         f"apad=whole_dur={tl.total:.3f}", "-ar", "48000", str(voice_pad)])
    from studio.pro import _mix_audio
    track = MUSIC_DIR / data.get("music", "investigations.mp3")
    mix = _mix_audio(voice_pad, sfx_wav, track if track.exists() else None, tl.total, 0.07, WORK, "presenter")
    final = OUT / "final.mp4"
    run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(raw_video), "-i", str(mix), "-map", "0:v", "-map", "1:a",
         "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", "-shortest", str(final)])
    log(f"final: {final} {media_duration(final):.2f}s")


def prerender(tl: Timeline, sfx: list) -> dict:
    labels, tags, chips, nums = {}, {}, {}, {}
    previews = set()
    for k, b in enumerate(tl.beats):
        mid = (b["start"] + b["end"]) / 2
        previews.add(int(mid * FPS))
        previews.add(int((b["start"] + 0.9) * FPS))
        lab = b.get("label") or (b.get("map") or {}).get("label")
        if lab:
            labels[k] = text_img(lab, 84 if len(lab) < 18 else 70, stroke=5, glow=(40, 170, 255))
        c = b.get("card") or {}
        if c.get("tag"):
            tags[k] = pill(c["tag"], 44, bg=(255, 255, 255), fg=(20, 20, 20))
        cl = []
        if c.get("chip"):
            cl.append((pill(c["chip"], 52), tl.word_time(b, c.get("chip_word"), 1.0)))
        for label, word in c.get("chips", []):
            em = {"SUN": "☀️", "STARS": "⭐", "MAGNETIC FIELD": "🧲"}.get(label)
            icon = motion.emoji_image(em, 46) if em else None
            cl.append((pill(label, 46, icon=icon), tl.word_time(b, word, 1.0)))
        if cl:
            chips[k] = cl
        for _, at in cl:
            sfx.append(("pop", at, 1.0))
        if c:
            sfx.append(("swish", b["start"] + 0.02, 0.8))
            if c.get("tag"):
                sfx.append(("click", b["start"] + 0.35, 0.8))
            sfx.append(("swish", b["end"] - 0.25, 0.5))
        if c.get("kind") == "number":
            st = tl.word_time(b, c.get("start_word"), 0.5)
            nums[k] = st
            for i in range(14):
                sfx.append(("tick", st + i * 0.07, 0.8))
            sfx.append(("ding", st + 1.0, 0.7))
        m = b.get("map") or {}
        if m.get("label"):
            sfx.append(("pop", tl.word_time(b, m.get("label_word"), 0.6), 1.0))
        if m.get("route") and m.get("route_draw", [0, 0]) != [0, 0]:
            a, _ = m["route_draw"]
            sfx.append(("riser", b["start"] + a * (b["end"] - b["start"]), 0.7))
        for i, _ in enumerate(m.get("nests", [])):
            sfx.append(("bubble", b["start"] + 0.9 + i * 0.35, 0.9))
        for icon, word in m.get("icons", []):
            sfx.append(("thud", tl.word_time(b, word, 0.5), 0.9))
    sfx.append(("whoosh", 0.0, 0.8))
    return {"labels": labels, "tags": tags, "chips": chips, "nums": nums, "previews": previews}


def draw_card(frame, tl, k, b, bt, blen, media, pre, card_shadow, card_pad, card_round) -> None:
    c = b.get("card")
    if not c:
        return
    cw, ch = CARD[2] - CARD[0], CARD[3] - CARD[1]
    # content
    kind = c["kind"]
    if kind == "number":
        body = Image.new("RGBA", (cw, ch), (0, 0, 0, 255))
        g = np.linspace(0, 1, ch)[:, None, None]
        arr = (np.array([12, 40, 90]) * (1 - g) + np.array([10, 110, 170]) * g) * np.ones((ch, cw, 3))
        body = Image.fromarray(arr.astype(np.uint8)).convert("RGBA")
        st = pre["nums"][k] - b["start"]
        v = c["value"] * ease((bt - st) / 1.0)
        txt = f"{int(round(v / 100) * 100):,}{c.get('suffix', '')}" if bt > st else f"0{c.get('suffix', '')}"
        num = text_img(txt, 130, stroke=6, glow=(255, 200, 40))
        paste_center(body, num, cw / 2, ch / 2 - 40)
        sub = text_img(c.get("sub", ""), 54, fill=YELLOW, stroke=5)
        paste_center(body, sub, cw / 2, ch / 2 + 95, alpha=min(1, max(0, (bt - st - 0.8) / 0.3)))
    else:
        m = media.get(k)
        if m and m[0] == "photo":
            img = m[1]
            p = bt / max(blen, 0.1)
            zoom = 1.08 + 0.12 * p
            base = cover(img, (int(cw * zoom), int(ch * zoom)))
            ox = int((base.width - cw) * (0.3 + 0.4 * p))
            oy = (base.height - ch) // 2
            body = base.crop((ox, oy, ox + cw, oy + ch)).convert("RGBA")
        elif m and m[0] == "video":
            body = m[1].next().convert("RGBA")
        else:
            body = Image.new("RGBA", (cw, ch), (30, 60, 90, 255))
    body.putalpha(card_round)
    card = Image.new("RGBA", card_shadow.size, (0, 0, 0, 0))
    card.alpha_composite(card_shadow)
    border = Image.new("RGBA", (cw + 12, ch + 12), (0, 0, 0, 0))
    ImageDraw.Draw(border).rounded_rectangle((0, 0, cw + 11, ch + 11), 44, fill=(255, 255, 255, 255))
    card.alpha_composite(border, (card_pad - 6, card_pad - 6))
    card.alpha_composite(body, (card_pad, card_pad))
    tag = pre["tags"].get(k)
    if tag:
        s = back((bt - 0.35) / 0.3)
        if s > 0.01:
            tg = tag.resize((max(1, int(tag.width * s)), max(1, int(tag.height * s))), Image.BILINEAR)
            card.alpha_composite(tg, (card_pad + 20, card_pad + ch - tg.height // 2 - 10)) \
                if card_pad + ch - tg.height // 2 - 10 + tg.height <= card.height else None
    # entry / exit motion
    cx, cy = (CARD[0] + CARD[2]) / 2, (CARD[1] + CARD[3]) / 2
    if bt < 0.38:
        e = back(bt / 0.38)
        x = cx + (1 - e) * 900
        scale, ang, alpha = 0.86 + 0.14 * e, -6 * (1 - e), min(1, bt / 0.12)
    elif bt > blen - 0.25 and k + 1 < len(tl.beats):
        e = ease((bt - (blen - 0.25)) / 0.25)
        x = cx - e * 1000
        scale, ang, alpha = 1 - 0.1 * e, 5 * e, 1 - e * 0.6
    else:
        x, scale, ang, alpha = cx, 1.0, 0.0, 1.0
        y_float = 6 * math.sin(bt * 1.6)
        cy += y_float
    paste_center(frame, card, x, cy, scale=scale, alpha=alpha, angle=ang)
    for im, at in pre["chips"].get(k, []):
        lt = at - b["start"]
        s = back((bt - lt) / 0.3)
        if s <= 0.01:
            continue
        idx = [a for _, a in pre["chips"][k]].index(at)
        n = len(pre["chips"][k])
        if n == 1:
            px, py = CARD[2] - im.width / 2 + 10, CARD[3] - 10
        else:
            px, py = W / 2, CARD[3] + 70 + idx * 105
        if bt > blen - 0.25 and k + 1 < len(tl.beats):
            continue
        paste_center(frame, im, px, py, scale=s, alpha=min(1, (bt - lt) / 0.1))


def draw_map_layer(frame, mp, cam, tl, k, b, bt, blen, stick, pre) -> None:
    m = b["map"]
    t_abs = b["start"] + bt
    if m.get("arctic_circle"):
        dashed_lat(frame, mp, cam, 66.56, (255, 230, 120), "ARCTIC CIRCLE", ease(bt / 1.0))
    if m.get("equator"):
        dashed_lat(frame, mp, cam, 0.0, (255, 214, 10), "EQUATOR", ease((bt - 0.5) / 1.0))
    for name, lon, lat in m.get("place_labels", []):
        x, y = mp.project(cam, lon, lat)
        im = text_img(name, 46, stroke=5)
        paste_center(frame, im, x, y, alpha=min(1, max(0, (bt - 0.4) / 0.4)))
    for i, (lon, lat) in enumerate(m.get("nests", [])):
        x, y = mp.project(cam, lon, lat)
        s = back((bt - 0.9 - i * 0.35) / 0.3)
        if "tern" in stick:
            paste_center(frame, stick["tern"], x, y, scale=s * 0.8)
    routes = []
    if m.get("route") in ("tern", "godwit"):
        routes = [m["route"]]
    for name in routes:
        prog = route_prog(m, bt, blen)
        head = draw_route(frame, mp, cam, name, prog)
        st = stick.get(name)
        if head and st is not None:
            paste_center(frame, st, head[0], head[1], scale=0.75, angle=3 * math.sin(bt * 5))
    lab = pre["labels"].get(k)
    if lab:
        lt = tl.word_time(b, m.get("label_word"), 0.6) - b["start"]
        s = back((bt - lt) / 0.35)
        paste_center(frame, lab, W / 2, 300, scale=s, alpha=min(1, max(0, (bt - lt) / 0.12)))
    icons = m.get("icons", [])
    for i, (icon, word) in enumerate(icons):
        lt = tl.word_time(b, word, 0.5) - b["start"]
        s = back((bt - lt) / 0.3)
        em = {"no_food": "🍔", "no_water": "💧", "no_landing": "🛬"}[icon]
        im = no_icon(em, 170)
        x = W / 2 + (i - (len(icons) - 1) / 2) * 250
        paste_center(frame, im, x, 520, scale=s)


def draw_pip(frame, hf, pip_round, pip_shadow, pip_pad) -> None:
    pw, ph = PIP[2] - PIP[0], PIP[3] - PIP[1]
    face = hf.crop((int(HOST_W * 0.12), 0, int(HOST_W * 0.88), int(HOST_H * 0.95)))
    face = cover(face, (pw, ph), 0.5, 0.2).convert("RGBA")
    face.putalpha(pip_round)
    frame.alpha_composite(pip_shadow, (PIP[0] - pip_pad - 6, PIP[1] - pip_pad - 6))
    border = Image.new("RGBA", (pw + 12, ph + 12), (0, 0, 0, 0))
    ImageDraw.Draw(border).rounded_rectangle((0, 0, pw + 11, ph + 11), 40, fill=(255, 255, 255, 255))
    frame.alpha_composite(border, (PIP[0] - 6, PIP[1] - 6))
    frame.alpha_composite(face, (PIP[0], PIP[1]))


# ================================================================ captions
def caption_chunks(words: list) -> list[dict]:
    chunks, cur = [], []
    for w in words:
        cur.append(w)
        if len(cur) >= 3 or w[2][-1:] in ",.?!":
            chunks.append(cur)
            cur = []
    if cur:
        chunks.append(cur)
    out = []
    for i, c in enumerate(chunks):
        end = chunks[i + 1][0][0] if i + 1 < len(chunks) else c[-1][1] + 0.6
        out.append({"words": c, "start": c[0][0], "end": min(end, c[-1][1] + 0.6)})
    return out


_cap_cache: dict = {}


def draw_caption(frame: Image.Image, chunks: list[dict], t: float, y: float) -> None:
    for ci, c in enumerate(chunks):
        if c["start"] <= t < c["end"]:
            active = max([i for i, w in enumerate(c["words"]) if w[0] <= t] or [0])
            key = (ci, active)
            if key not in _cap_cache:
                _cap_cache[key] = caption_img(c["words"], active)
            im = _cap_cache[key]
            s = 1 + 0.12 * (1 - ease((t - c["start"]) / 0.12))
            paste_center(frame, im, W / 2, y, scale=s)
            return


def caption_img(words: list, active: int) -> Image.Image:
    f = font(68)
    toks = [w[2] for w in words]
    d = ImageDraw.Draw(Image.new("L", (1, 1)))
    space = 22
    widths = [d.textbbox((0, 0), t, font=f, stroke_width=7)[2] for t in toks]
    tw = sum(widths) + space * (len(toks) - 1)
    hgt = 120
    out = Image.new("RGBA", (tw + 80, hgt + 40), (0, 0, 0, 0))
    sh = Image.new("RGBA", out.size, (0, 0, 0, 0))
    x = 40
    for i, (tok, wd) in enumerate(zip(toks, widths)):
        ImageDraw.Draw(sh).text((x + 3, 30 + 7), tok, font=f, fill=(0, 0, 0, 150), stroke_width=7,
                                stroke_fill=(0, 0, 0, 150))
        x += wd + space
    out.alpha_composite(sh.filter(ImageFilter.GaussianBlur(5)))
    x = 40
    dd = ImageDraw.Draw(out)
    for i, (tok, wd) in enumerate(zip(toks, widths)):
        dd.text((x, 30), tok, font=f, fill=YELLOW if i == active else (255, 255, 255), stroke_width=7,
                stroke_fill=(0, 0, 0))
        x += wd + space
    return out


if __name__ == "__main__":
    step = sys.argv[1] if len(sys.argv) > 1 else "prep"
    {"prep": prep, "compose": compose}[step]()
