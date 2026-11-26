"""Compositor for presenter Short v2 (Bir Tawil): vector map, cards, the Blip
presenter, captions, transitions, sound design and the final mp4. Every frame is a
pure function of its time, so frames render in parallel.

    python -m presenter.pro2 compose            # full render -> presenter/out2/final.mp4
    python -m presenter.pro2_compose preview 1.2 6.5 ...   # still frames for checking
"""
from __future__ import annotations

import json
import math
import os
import random
import re
import subprocess
import sys
import wave
from functools import lru_cache
from pathlib import Path

import cairo
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from presenter import build as B
from presenter.cartoon2 import Blip, wav_rms
from presenter.pro2 import MEDIA2, OUT2, P, TAG, load, strip_tags
from studio import motion, tts
from studio.common import MUSIC_DIR, log, run

W, H, FPS = 1080, 1920, 30
VO = 0.15                       # voice starts this late
TAIL = 0.95
WORK2 = P / "work2"
YELLOW = (255, 214, 10)
COSL = math.cos(math.radians(22))
BT_C = (33.63, 21.86)
HA_C = (35.45, 22.45)


def ease(t):
    t = min(max(t, 0.0), 1.0)
    return t * t * (3 - 2 * t)


def back(t):
    return B.back(t)


def ramp(t, a, d=0.3):
    return ease((t - a) / d) if d > 0 else float(t >= a)


def norm(s):
    return re.sub(r"[^a-z0-9]", "", s.lower())


@lru_cache(None)
def bfont(px):
    f = B.font(px)
    try:
        f.set_variation_by_name("ExtraBold")
    except Exception:  # noqa: BLE001
        pass
    return f


# ====================================================================== timeline
class TL:
    def __init__(self):
        self.data = load()
        heard = [tuple(h) for h in json.loads((OUT2 / "heard.json").read_text())]
        vdur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of",
                                     "csv=p=0", str(OUT2 / "voice.mp3")], capture_output=True,
                                    text=True).stdout.strip())
        self.vdur = vdur
        self.total = round(VO + vdur + TAIL, 3)
        text = " ".join(strip_tags(b["say"]) for b in self.data["beats"])
        words = tts.align_words(text, heard, vdur)
        self.words = [(s + VO, e + VO, w) for s, e, w in words]
        self.beats = []
        i = 0
        for k, b in enumerate(self.data["beats"]):
            toks = b["say"].split()
            # each word's tag (mood), tags precede the words they colour
            tags, cur = [], None
            j = 0
            parts = TAG.split(b["say"])
            found = TAG.findall(b["say"])
            for pi, part in enumerate(parts):
                if pi > 0:
                    cur = found[pi - 1][1:-1].lower()
                for _ in part.split():
                    tags.append(cur)
            n = len(strip_tags(b["say"]).split())
            ws = self.words[i:i + n]
            i += n
            start = ws[0][0]
            if b["say"].strip().startswith("[laughs]") and self.beats:
                start = self.beats[-1]["words"][-1][1] + 0.12
            self.beats.append({"k": k, "b": b, "words": ws, "tags": tags[:n], "start": start})
        for k, bt in enumerate(self.beats):
            bt["end"] = self.beats[k + 1]["start"] if k + 1 < len(self.beats) else self.total
        self.T1 = self.beats[5]["start"] - 0.25      # map -> face
        self.T2 = self.beats[10]["start"] - 0.25     # face -> map

    def wt(self, k, word, nth=0, end=False):
        n = norm(word)
        c = 0
        for w in self.beats[k]["words"]:
            if norm(w[2]).startswith(n):
                if c == nth:
                    return w[1] if end else w[0]
                c += 1
        raise KeyError(f"{word} not in beat {k}")

    def beat_at(self, t):
        k = 0
        for bt in self.beats:
            if t >= bt["start"] - 0.15:
                k = bt["k"]
        return k

    def layout(self, t):
        return "face" if self.T1 <= t < self.T2 else "map"


# ====================================================================== geography
GEO = json.loads((P / "assets2" / "geo.json").read_text())
RINGS = []          # (country, np.array Nx2, bbox)
for name, rings in GEO["countries"].items():
    for r in rings:
        a = np.array(r, np.float64)
        RINGS.append((name, a, (a[:, 0].min(), a[:, 1].min(), a[:, 0].max(), a[:, 1].max())))
BT = np.array(GEO["areas"]["Bir Tawil"], np.float64)
HA = np.array(GEO["areas"]["Halayib Triangle"], np.float64)
RIVERS = [np.array(r, np.float64) for r in GEO["rivers"]]
L1899 = np.array([(24.98, 22.0), (36.88, 22.0)])
# make sure the bend runs west -> east
_s = BT[6:12]
_s = _s[np.argsort(_s[:, 0])]
L1902 = np.array([(28.0, 22.0), (33.1811, 21.9954), *map(tuple, _s), (34.0842, 21.9955),
                  *map(tuple, HA[14:26])])


class Cam:
    def __init__(self, lon, lat, wid, w=W, h=H):
        self.lon, self.lat, self.wid, self.w, self.h = lon, lat, wid, w, h
        self.k = w / (wid * COSL)          # px per degree of latitude

    def p(self, lon, lat):
        return self.w / 2 + (lon - self.lon) * self.k * COSL, self.h / 2 - (lat - self.lat) * self.k

    def pa(self, a):
        x = self.w / 2 + (a[:, 0] - self.lon) * self.k * COSL
        y = self.h / 2 - (a[:, 1] - self.lat) * self.k
        return np.stack([x, y], 1)

    def bounds(self):
        dx = self.w / 2 / (self.k * COSL)
        dy = self.h / 2 / self.k
        return self.lon - dx, self.lat - dy, self.lon + dx, self.lat + dy

    def scale(self):          # line width multiplier, gentle
        return min(1.6, max(0.6, (6.0 / self.wid) ** 0.25))


def _path(c, pts, close=True):
    c.move_to(*pts[0])
    for x, y in pts[1:]:
        c.line_to(x, y)
    if close:
        c.close_path()


def _decimate(pts, step=1.6):
    """drop points closer than step px to the last kept one."""
    if len(pts) < 8:
        return pts
    d = np.hypot(*np.diff(pts, axis=0).T)
    keep = [0]
    acc = 0.0
    for i, v in enumerate(d, 1):
        acc += v
        if acc >= step:
            keep.append(i)
            acc = 0.0
    if keep[-1] != len(pts) - 1:
        keep.append(len(pts) - 1)
    return pts[keep]


def partial(pts, frac):
    if frac <= 0:
        return pts[:1]
    if frac >= 1:
        return pts
    seg = np.hypot(*np.diff(pts, axis=0).T)
    L = seg.sum() * frac
    out = [pts[0]]
    acc = 0.0
    for i, s in enumerate(seg):
        if acc + s >= L:
            f = (L - acc) / max(s, 1e-9)
            out.append(pts[i] + (pts[i + 1] - pts[i]) * f)
            break
        out.append(pts[i + 1])
        acc += s
    return np.array(out)


def lerpc(a, b, f):
    return tuple(x + (y - x) * f for x, y in zip(a, b))


SAND = (0.95, 0.83, 0.60)
SAND2 = (0.89, 0.74, 0.50)
OTHER = (0.86, 0.78, 0.63)
EGYPT = (0.86, 0.27, 0.27)
SUDAN = (0.13, 0.55, 0.36)
BTY = (1.0, 0.84, 0.04)
HAT = (0.12, 0.78, 0.72)
RED = (1.0, 0.25, 0.22)


def render_map(cam: Cam, st: dict, t: float) -> Image.Image:
    w, h = cam.w, cam.h
    surf = cairo.ImageSurface(cairo.FORMAT_RGB24, w, h)
    c = cairo.Context(surf)
    c.set_line_join(cairo.LINE_JOIN_ROUND)
    c.set_line_cap(cairo.LINE_CAP_ROUND)
    sc = cam.scale() * w / W
    # sea
    g = cairo.LinearGradient(0, 0, 0, h)
    g.add_color_stop_rgb(0, 0.17, 0.46, 0.62)
    g.add_color_stop_rgb(1, 0.06, 0.24, 0.38)
    c.set_source(g)
    c.paint()
    # graticule
    x0, y0, x1, y1 = cam.bounds()
    step = 5 if cam.wid > 8 else 1
    c.set_line_width(1.5 * w / W)
    c.set_source_rgba(1, 1, 1, 0.07)
    for lon in range(int(math.floor(x0 / step) * step), int(x1) + step, step):
        px, _ = cam.p(lon, 0)
        c.move_to(px, 0)
        c.line_to(px, h)
    for lat in range(int(math.floor(y0 / step) * step), int(y1) + step, step):
        _, py = cam.p(0, lat)
        c.move_to(0, py)
        c.line_to(w, py)
    c.stroke()
    # waves
    c.set_source_rgba(1, 1, 1, 0.06)
    c.set_line_width(3 * w / W)
    sp = 64 * w / W
    for i in range(int(h / sp) + 2):
        yy = i * sp + (t * 9 * w / W) % sp
        c.move_to(0, yy)
        for xx in range(0, w + 40, 40):
            c.line_to(xx, yy + 6 * math.sin(xx / 70 + i * 1.7 + t * 1.3))
        c.stroke()
    # visible rings
    vis = []
    for name, a, (bx0, by0, bx1, by1) in RINGS:
        if bx1 < x0 - 1 or bx0 > x1 + 1 or by1 < y0 - 1 or by0 > y1 + 1:
            continue
        vis.append((name, _decimate(cam.pa(a), 1.4 * w / W)))
    c.new_path()
    for _, pts in vis:
        _path(c, pts)
    land = c.copy_path()
    c.new_path()
    # coast halo
    c.append_path(land)
    c.set_source_rgba(0.62, 0.9, 0.95, 0.13)
    c.set_line_width(38 * sc)
    c.stroke_preserve()
    c.set_source_rgba(0.62, 0.9, 0.95, 0.20)
    c.set_line_width(16 * sc)
    c.stroke_preserve()
    c.set_source_rgba(0.28, 0.2, 0.12, 0.75)
    c.set_line_width(7 * sc)
    c.stroke()
    # land
    dimo = st.get("dim_other", 0.0)
    for name, pts in vis:
        col = SAND if name in ("Egypt", "Sudan") else lerpc(SAND, OTHER, 0.35 + 0.4 * dimo)
        g = cairo.LinearGradient(0, 0, 0, h)
        g.add_color_stop_rgb(0, *col)
        g.add_color_stop_rgb(1, *lerpc(col, SAND2, 0.6))
        c.set_source(g)
        _path(c, pts)
        c.fill()
    # Egypt / Sudan colours, split at 22N
    _, y22 = cam.p(0, 22.0)
    for key, col, rect in (("eg", EGYPT, (0, 0, w, y22)), ("sd", SUDAN, (0, y22, w, h - y22))):
        f = st.get(key, 0.0)
        if f <= 0 or rect[3] <= 0:
            continue
        c.save()
        c.rectangle(*rect)
        c.clip()
        for name, pts in vis:
            if name in ("Egypt", "Sudan"):
                _path(c, pts)
        c.set_source_rgba(*col, 0.62 * f)
        c.fill()
        c.restore()
    # other borders
    c.set_source_rgba(1, 1, 1, 0.55)
    c.set_line_width(2.4 * sc)
    c.set_dash([10 * sc, 7 * sc])
    for name, pts in vis:
        if name not in ("Egypt", "Sudan"):
            _path(c, pts)
    c.stroke()
    c.set_dash([])
    # Nile
    na = st.get("nile", 1.0)
    if na > 0:
        c.set_source_rgba(0.22, 0.58, 0.92, 0.9 * na)
        c.set_line_width(4 * sc)
        for r in RIVERS:
            pts = cam.pa(r)
            if (pts[:, 0].max() < 0) or (pts[:, 0].min() > w):
                continue
            _path(c, _decimate(pts, 2), close=False)
            c.stroke()
    # Halaib
    ha = st.get("ha", 0.0)
    if ha > 0:
        pts = cam.pa(HA)
        _path(c, pts)
        c.set_source_rgba(*HAT, 0.78 * ha)
        c.fill_preserve()
        c.set_source_rgba(0.02, 0.3, 0.3, ha)
        c.set_line_width(4 * sc)
        c.stroke()
    # Bir Tawil
    bt = st.get("bt", 0.0)
    if bt > 0:
        pts = cam.pa(BT)
        pulse = 0.5 + 0.5 * math.sin(t * 2 * math.pi * 1.2)
        for wd, al in ((34, 0.18), (18, 0.32)):
            _path(c, pts)
            c.set_source_rgba(1, 0.9, 0.2, al * bt * (0.55 + 0.45 * pulse))
            c.set_line_width(wd * sc * (1 + 0.25 * pulse))
            c.stroke()
        _path(c, pts)
        c.set_source_rgba(*BTY, 0.95 * bt)
        c.fill_preserve()
        c.set_source_rgba(0.35, 0.22, 0.0, bt)
        c.set_line_width(4 * sc)
        c.set_dash([12 * sc, 7 * sc], -t * 30)
        c.stroke()
        c.set_dash([])
    # border lines
    for key, line, col, glow in (("l99", L1899, RED, (1, 0.3, 0.25)), ("l02", L1902, (1, 1, 1), (1, 0.75, 0.3))):
        f = st.get(key, 0.0)
        if f <= 0:
            continue
        pts = partial(cam.pa(line), f)
        if len(pts) < 2:
            continue
        a = st.get(key + "_a", 1.0)
        _path(c, pts, close=False)
        c.set_source_rgba(*glow, 0.35 * a)
        c.set_line_width(20 * sc)
        c.stroke()
        _path(c, pts, close=False)
        c.set_source_rgba(*col, a)
        c.set_line_width(8 * sc)
        c.set_dash([26 * sc, 13 * sc], -t * 40)
        c.stroke()
        c.set_dash([])
        if f < 1:
            x, y = pts[-1]
            c.arc(x, y, 13 * sc, 0, 2 * math.pi)
            c.set_source_rgba(*col, 1)
            c.fill()
            c.arc(x, y, 22 * sc, 0, 2 * math.pi)
            c.set_source_rgba(*glow, 0.35)
            c.fill()
    surf.flush()
    buf = np.ndarray((h, w, 4), np.uint8, surf.get_data())
    return Image.fromarray(buf[..., [2, 1, 0]].copy(), "RGB")


def draw_pin(frame, x, y, s, alpha=1.0):
    """a map pin whose tip is at (x, y)."""
    size = int(s * 4)
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, size, size)
    c = cairo.Context(surf)
    cx, cy = size / 2, size * 0.36
    r = s * 0.9
    c.move_to(size / 2, size * 0.36 + r * 2.3)
    c.arc(cx, cy, r, math.radians(150), math.radians(30))
    c.close_path()
    c.set_source_rgb(0.9, 0.2, 0.25)
    c.fill_preserve()
    c.set_source_rgb(0.25, 0.05, 0.08)
    c.set_line_width(s * 0.12)
    c.stroke()
    c.arc(cx, cy, r * 0.4, 0, 2 * math.pi)
    c.set_source_rgb(1, 1, 1)
    c.fill()
    surf.flush()
    im = _surf_rgba(surf)
    tip = size * 0.36 + r * 2.3
    sh = Image.new("RGBA", (int(s * 2), int(s * 0.7)), (0, 0, 0, 0))
    ImageDraw.Draw(sh).ellipse((0, 0, sh.width - 1, sh.height - 1), fill=(0, 0, 0, int(110 * alpha)))
    B.safe_paste(frame, sh.filter(ImageFilter.GaussianBlur(4)), int(x - sh.width / 2), int(y - sh.height / 2))
    if alpha < 1:
        im.putalpha(im.getchannel("A").point(lambda v: int(v * alpha)))
    B.safe_paste(frame, im, int(x - size / 2), int(y - tip))


def _surf_rgba(surf):
    w, h = surf.get_width(), surf.get_height()
    buf = np.ndarray((h, w, 4), np.uint8, surf.get_data())
    rgba = buf[..., [2, 1, 0, 3]].astype(np.float32)
    a = rgba[..., 3:4] / 255.0
    rgba[..., :3] = np.where(a > 0, rgba[..., :3] / np.maximum(a, 1e-3), 0)
    return Image.fromarray(np.clip(rgba, 0, 255).astype(np.uint8), "RGBA")


# ====================================================================== text bits
@lru_cache(None)
def timg(text, px, fill=(255, 255, 255), stroke=7, glow=None):
    f = bfont(px)
    box = ImageDraw.Draw(Image.new("L", (1, 1))).textbbox((0, 0), text, font=f, stroke_width=stroke)
    pad = 40
    w, h = box[2] - box[0] + 2 * pad, box[3] - box[1] + 2 * pad
    out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    xy = (pad - box[0], pad - box[1])
    if glow:
        g = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        ImageDraw.Draw(g).text(xy, text, font=f, fill=glow + (255,), stroke_width=stroke + 8, stroke_fill=glow + (255,))
        out.alpha_composite(g.filter(ImageFilter.GaussianBlur(16)))
    sh = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(sh).text((xy[0] + 4, xy[1] + 8), text, font=f, fill=(0, 0, 0, 150), stroke_width=stroke,
                            stroke_fill=(0, 0, 0, 150))
    out.alpha_composite(sh.filter(ImageFilter.GaussianBlur(6)))
    ImageDraw.Draw(out).text(xy, text, font=f, fill=fill, stroke_width=stroke, stroke_fill=(0, 0, 0))
    return out


@lru_cache(None)
def pillc(text, px, bg=YELLOW, fg=(15, 15, 15), icon=None, isz=0):
    ic = None
    if icon:
        ic = no_icon_c(icon[1:], isz) if icon.startswith("!") else motion.emoji_image(icon, isz)
    f = bfont(px)
    tb = ImageDraw.Draw(Image.new("L", (1, 1))).textbbox((0, 0), text, font=f)
    tw, th = tb[2] - tb[0], tb[3] - tb[1]
    iw = ic.width + 10 if ic else 0
    w, h = int(tw + iw + px * 1.3), int(max(th + px * 0.95, (ic.height + 12) if ic else 0))
    sh, pad = B.shadow_for((w, h), h // 2, 14, 130)
    out = Image.new("RGBA", sh.size, (0, 0, 0, 0))
    out.alpha_composite(sh)
    body = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(body)
    d.rounded_rectangle((0, 0, w - 1, h - 1), h // 2, fill=bg + (255,))
    d.rounded_rectangle((0, 0, w - 1, h - 1), h // 2, outline=(0, 0, 0, 255), width=max(3, px // 14))
    if ic:
        body.alpha_composite(ic, (int(px * 0.45), (h - ic.height) // 2))
    d.text((int(px * 0.65) + iw - tb[0], (h - th) // 2 - tb[1]), text, font=f, fill=fg)
    out.alpha_composite(body, (pad, pad))
    return out


@lru_cache(None)
def no_icon_c(emoji, size):
    return B.no_icon(emoji, size)


@lru_cache(None)
def emoji(e, size):
    return motion.emoji_image(e, size)


@lru_cache(None)
def stamp_img(text, px=86, col=(214, 30, 30)):
    f = bfont(px)
    tb = ImageDraw.Draw(Image.new("L", (1, 1))).textbbox((0, 0), text, font=f)
    tw, th = tb[2] - tb[0], tb[3] - tb[1]
    w, h = tw + 90, th + 80
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((6, 6, w - 7, h - 7), 22, outline=col + (255,), width=12)
    d.rounded_rectangle((22, 22, w - 23, h - 23), 14, outline=col + (255,), width=4)
    d.text(((w - tw) / 2 - tb[0], (h - th) / 2 - tb[1]), text, font=f, fill=col + (255,))
    rnd = np.random.default_rng(len(text))
    noise = (rnd.random((h, w)) > 0.16).astype(np.uint8) * 255
    a = np.minimum(np.array(im.getchannel("A")), noise)
    im.putalpha(Image.fromarray(a).filter(ImageFilter.GaussianBlur(0.6)))
    return im


@lru_cache(None)
def bubble(text, px=44):
    f = bfont(px)
    tb = ImageDraw.Draw(Image.new("L", (1, 1))).textbbox((0, 0), text, font=f)
    tw, th = tb[2] - tb[0], tb[3] - tb[1]
    w, h = tw + 60, th + 46
    im = Image.new("RGBA", (w + 20, h + 50), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.polygon([(w * 0.35, h - 4), (w * 0.5, h - 4), (w * 0.38, h + 34)], fill=(255, 255, 255, 255),
              outline=(0, 0, 0, 255))
    d.rounded_rectangle((4, 4, w, h), 28, fill=(255, 255, 255, 255), outline=(0, 0, 0, 255), width=5)
    d.polygon([(w * 0.36, h - 8), (w * 0.49, h - 8), (w * 0.385, h + 26)], fill=(255, 255, 255, 255))
    d.text(((w - tw) / 2 - tb[0] + 2, (h - th) / 2 - tb[1] + 2), text, font=f, fill=(20, 20, 20))
    return im


def pop(t, a, d=0.32):
    """scale for a pop-in that starts at a (0 before)."""
    if t < a:
        return 0.0
    return back((t - a) / d)


def out_k(t, a, d=0.18):
    """1 before a, fading to 0."""
    return 1 - ease((t - a) / d)


# ====================================================================== scene: map
class Scenes:
    def __init__(self, tl: TL):
        self.tl = tl
        b = tl.beats
        wt = tl.wt
        self.cam_keys = [
            (0.0, 33.63, 21.86, 44.0),
            (3.5, 33.63, 21.86, 3.3),
            (b[1]["start"] - 0.25, 33.63, 21.86, 3.3),
            (b[1]["start"] + 1.0, 31.6, 21.4, 17.5),
            (b[2]["start"] - 0.2, 31.6, 21.4, 17.5),
            (b[2]["start"] + 0.9, 31.0, 22.0, 13.0),
            (b[3]["start"] - 0.15, 31.0, 22.0, 13.0),
            (b[3]["start"] + 0.95, 34.55, 22.3, 5.3),
            (b[4]["start"], 34.55, 22.3, 5.3),
            (b[4]["end"], 34.85, 22.35, 4.7),
            (tl.T2, 33.9, 22.0, 3.6),
            (tl.T2 + 0.5, 33.75, 21.95, 3.4),
            (wt(10, "Totally"), 33.68, 21.9, 5.0),
            (tl.total - 0.05, 33.63, 21.86, 44.0),
        ]
        self.t_patch = wt(0, "patch")
        self.t_no = wt(0, "no")
        self.t_eg = wt(1, "Egypt") - 0.1
        self.t_sd = wt(1, "Sudan") - 0.1
        self.t_bir = wt(1, "Bir")
        self.t_sq = wt(1, "squeezed")
        self.l99 = (wt(2, "drew"), wt(2, "border", end=True) + 0.3)
        self.t_straight = wt(2, "straight")
        self.l02 = (wt(3, "drew"), wt(3, "bends", end=True) + 0.25)
        self.t_second = wt(3, "second")
        self.t_tiny = wt(4, "tiny")
        self.t_hal = wt(4, "Halaib")
        self.t_tri = wt(4, "Triangle")
        self.t_ten = wt(4, "ten")
        self.t_red = wt(4, "Red")
        self.t_tot = wt(10, "Totally")
        self.t_nobody = wt(10, "nobody")

    # ---------------------------------------------------------------- camera
    def cam(self, t, w=W, h=H):
        ks = self.cam_keys
        if t <= ks[0][0]:
            k = ks[0]
            return Cam(k[1], k[2], k[3], w, h)
        for a, bb in zip(ks, ks[1:]):
            if a[0] <= t < bb[0]:
                f = ease((t - a[0]) / max(bb[0] - a[0], 1e-6))
                wid = math.exp(math.log(a[3]) + (math.log(bb[3]) - math.log(a[3])) * f)
                return Cam(a[1] + (bb[1] - a[1]) * f, a[2] + (bb[2] - a[2]) * f, wid, w, h)
        k = ks[-1]
        return Cam(k[1], k[2], k[3], w, h)

    def map_state(self, t):
        st = {"bt": ramp(t, self.t_patch, 0.35), "eg": ramp(t, self.t_eg, 0.35), "sd": ramp(t, self.t_sd, 0.35),
              "l99": ramp(t, self.l99[0], self.l99[1] - self.l99[0]) if t >= self.l99[0] else 0.0,
              "l02": ramp(t, self.l02[0], self.l02[1] - self.l02[0]) if t >= self.l02[0] else 0.0,
              "ha": ramp(t, self.t_hal, 0.3), "nile": 1.0}
        st["l99"] = min(1.0, max(0.0, (t - self.l99[0]) / (self.l99[1] - self.l99[0]))) if t >= self.l99[0] else 0
        st["l02"] = min(1.0, max(0.0, (t - self.l02[0]) / (self.l02[1] - self.l02[0]))) if t >= self.l02[0] else 0
        st["l99"] = ease(st["l99"]) if 0 < st["l99"] < 1 else st["l99"]
        st["l02"] = ease(st["l02"]) if 0 < st["l02"] < 1 else st["l02"]
        if t >= self.tl.T2:            # outro: borders fade so the end matches the start
            k = 1 - ramp(t, self.t_tot + 0.3, 1.4)
            for key in ("eg", "sd", "l99", "l02", "ha"):
                st[key] = st[key] * k if key in ("eg", "sd", "ha") else st[key]
            st["l99_a"] = st["l02_a"] = k
        st["dim_other"] = ramp(t, self.t_eg, 0.4) * (1 - ramp(t, self.t_tot + 0.3, 1.4) if t > self.tl.T2 else 1)
        return st

    def map_frame(self, t):
        tl = self.tl
        cam = self.cam(t)
        st = self.map_state(t)
        fr = render_map(cam, st, t).convert("RGBA")
        sc = cam.scale()
        btx, bty = cam.p(*BT_C)
        k = tl.beat_at(t)
        # pin on Bir Tawil (hook, countries)
        if self.t_patch <= t < tl.beats[2]["start"] + 0.2:
            d = t - self.t_patch
            drop = (1 - back(d / 0.45)) * -260
            al = out_k(t, tl.beats[2]["start"] - 0.1, 0.3)
            draw_pin(fr, btx, bty - 6 + drop, 30 * min(1.3, max(0.85, sc)), al)
        # hook label
        if t < tl.beats[1]["start"] + 0.1:
            s = pop(t, self.t_no - 0.05, 0.28)
            if s > 0:
                slam = 1 + 0.9 * (1 - ease((t - self.t_no + 0.05) / 0.16))
                al = out_k(t, tl.beats[1]["start"] - 0.2, 0.25)
                B.paste_center(fr, timg("NO COUNTRY", 132, YELLOW, 10, (255, 120, 0)), W / 2, 300, s * slam, al, -3)
                s2 = pop(t, self.t_no + 0.25, 0.28)
                B.paste_center(fr, timg("WANTS IT", 118, (255, 255, 255), 10), W / 2, 440, s2, al, -3)
            q = ramp(t, 1.0, 0.4) * out_k(t, self.t_no - 0.1, 0.2)
            if q > 0:
                B.paste_center(fr, pillc("SOMEWHERE IN AFRICA", 46, (255, 255, 255)), W / 2, 330, 0.9 + 0.1 * q, q)
        # countries: flags + names + Bir Tawil leader label
        if tl.beats[1]["start"] - 0.2 <= t < tl.beats[3]["start"] + 0.2:
            al = out_k(t, tl.beats[2]["start"] + 0.2, 0.3)
            for tt, flag, name, ll in ((self.t_eg, "🇪🇬", "EGYPT", (29.0, 26.6)), (self.t_sd, "🇸🇩", "SUDAN", (35.0, 19.2))):
                s = pop(t, tt, 0.35)
                if s > 0:
                    x, y = cam.p(*ll)
                    B.paste_center(fr, emoji(flag, 120), x, y - 30, s, al)
                    B.paste_center(fr, timg(name, 56, (255, 255, 255), 7), x, y + 70, s, al)
            s = pop(t, self.t_bir, 0.35)
            if s > 0:
                lx, ly = min(btx + 150, W - 210), bty - 250
                sq = 1 + 0.18 * math.sin(max(0, t - self.t_sq) * 14) * math.exp(-max(0, t - self.t_sq) * 3) \
                    if t > self.t_sq else 1
                d = ImageDraw.Draw(fr)
                ex, ey = btx + (lx - btx) * min(1, s), bty + (ly - bty) * min(1, s)
                d.line((btx, bty, ex, ey), fill=(255, 255, 255, int(255 * al)), width=6)
                d.ellipse((btx - 10, bty - 10, btx + 10, bty + 10), fill=(255, 255, 255, int(255 * al)))
                B.paste_center(fr, pillc("BIR TAWIL", 62), lx, ly, s * sq, al, 4)
        # 1899 chip following the pen, then the label
        if tl.beats[2]["start"] <= t < tl.beats[4]["start"]:
            st99 = st["l99"]
            if 0 < st99 < 1:
                pts = partial(cam.pa(L1899), st99)
                x, y = pts[-1]
                B.paste_center(fr, pillc("1899", 44, (230, 50, 45), (255, 255, 255)), x, y - 70, 1)
            s = pop(t, self.t_straight, 0.32)
            if s > 0:
                al = out_k(t, tl.beats[3]["start"] + 0.6, 0.3)
                x, y = cam.p(30.0, 22.0)
                B.paste_center(fr, pillc("1899 BORDER", 58, (230, 50, 45), (255, 255, 255)), x, y - 120, s, al, -3)
                B.paste_center(fr, timg("STRAIGHT LINE", 50, (255, 255, 255), 6), x, y + 95, s, al)
        if tl.beats[3]["start"] <= t < tl.beats[4]["start"] + 0.3:
            st02 = st["l02"]
            if 0 < st02 < 1:
                pts = partial(cam.pa(L1902), st02)
                x, y = pts[-1]
                B.paste_center(fr, pillc("1902", 44, (255, 255, 255)), x, y - 70, 1)
            s = pop(t, self.t_second, 0.32)
            if s > 0:
                al = out_k(t, tl.beats[4]["start"], 0.3)
                B.paste_center(fr, pillc("1902 BORDER", 58, (255, 255, 255)), W / 2, 330, s, al, 2)
                x, y = cam.p(31.0, 22.0)
                B.paste_center(fr, pillc("1899", 40, (230, 50, 45), (255, 255, 255)), x + 30, y - 60, s, al)
            bs = pop(t, wt_safe(tl, 3, "bends"), 0.3)
            if bs > 0:
                al = out_k(t, tl.beats[4]["start"], 0.3)
                x, y = cam.p(33.0, 22.75)
                B.paste_center(fr, timg("BENDS!", 64, (255, 255, 255), 8, (255, 150, 0)), x, y, bs, al, -6)
        # pieces
        if tl.beats[4]["start"] - 0.2 <= t < tl.T1 + 0.4:
            s = pop(t, self.t_tiny, 0.32)
            if s > 0:
                x, y = cam.p(33.3, 22.75)
                B.paste_center(fr, pillc("BIR TAWIL  2,060 km²", 46), x, y, s, 1, 2)
            s = pop(t, self.t_tri, 0.32)
            if s > 0:
                x, y = cam.p(35.2, 22.45)
                B.paste_center(fr, pillc("HALAIB  20,580 km²", 46, (40, 210, 195)), x, y, s, 1, -2)
            s = pop(t, self.t_ten, 0.3)
            if s > 0:
                wob = 3 * math.sin((t - self.t_ten) * 9) * math.exp(-(t - self.t_ten) * 2.5)
                B.paste_center(fr, timg("10× BIGGER", 120, YELLOW, 10, (255, 90, 0)), W / 2, 330, s, 1, wob)
            s = pop(t, self.t_red, 0.32)
            if s > 0:
                x, y = cam.p(36.4, 23.9)
                B.paste_center(fr, timg("RED SEA", 60, (200, 240, 255), 6), x, y, s, 1, -8)
                B.paste_center(fr, emoji("🌊", 70), x, y - 70, s)
        # outro
        if t >= tl.T2:
            s = pop(t, self.t_tot, 0.3)
            if s > 0:
                al = out_k(t, tl.total - 0.55, 0.4)
                B.paste_center(fr, pillc("UP FOR GRABS", 76, YELLOW, (15, 15, 15), "🏷️", 70), W / 2, 330, s, al, -3)
            s = pop(t, self.t_nobody, 0.3) * out_k(t, self.t_tot - 0.05, 0.2)
            if s > 0:
                B.paste_center(fr, timg("NOBODY'S LAND", 96, (255, 255, 255), 9), W / 2, 330, s, 1, 2)
        return fr


def wt_safe(tl, k, w):
    try:
        return tl.wt(k, w)
    except KeyError:
        return tl.beats[k]["start"]


# ====================================================================== scene: face
CARD_C = (540, 470)
CARD_S = (960, 640)


class Face:
    def __init__(self, tl: TL, sc: Scenes):
        self.tl, self.sc = tl, sc
        b = tl.beats
        wt = tl.wt
        self.groups = [(5,), (6,), (7,), (8, 9)]
        self.t = {"trap": wt(5, "trap"), "claims": wt(5, "claims"), "give": wt(5, "give"),
                  "halaib": wt(5, "Halaib"), "egypt": wt(6, "Egypt"), "sudan": wt(6, "Sudan"),
                  "bir": wt(6, "Bir"), "not": wt(6, "Not"), "towns": wt(7, "towns"), "water": wt(7, "water"),
                  "people": wt(7, "people"), "country": wt(7, "country"), "y2014": wt(8, "2014"),
                  "dad": wt(8, "dad"), "planted": wt(8, "planted"), "flag": wt(8, "flag"),
                  "daughter": wt(8, "daughter"), "princess": wt(8, "princess"), "recog": wt(9, "recognized")}
        self._bg_map = None
        self._mini = {}

    # ---------------------------------------------------------------- backgrounds
    def bg(self, t):
        k = self.tl.beat_at(t)
        if k >= 8:
            return self._video_bg("bg_desert", t, self.tl.beats[8]["start"] - 0.4)
        if k == 7:
            return self._video_bg("bg_sand", t, self.tl.beats[7]["start"] - 0.4)
        if self._bg_map is None:
            m = render_map(Cam(34.4, 22.1, 7.5, 1240, 2204), {"bt": 1, "ha": 1, "eg": 1, "sd": 1, "l99": 1,
                                                              "l02": 1, "dim_other": 1}, 1.0)
            m = m.filter(ImageFilter.GaussianBlur(14))
            arr = np.asarray(m).astype(np.float32) * 0.5 + np.array([8, 14, 30], np.float32)
            self._bg_map = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))
        f = (t - self.tl.T1) / max(self.tl.T2 - self.tl.T1, 1)
        z = 1.0 + 0.06 * f
        bw, bh = self._bg_map.size
        cw, ch = W / z * (bw / W) * 0.871, H / z * (bh / H) * 0.871
        x0 = (bw - cw) / 2 + 40 * math.sin(t * 0.2)
        y0 = (bh - ch) / 2
        return self._bg_map.resize((W, H), Image.BILINEAR, box=(x0, y0, x0 + cw, y0 + ch)).convert("RGBA")

    def _video_bg(self, name, t, t0):
        i = max(0, int((t - t0) * FPS))
        d = WORK2 / "frames" / name
        files = sorted(d.glob("*.jpg")) if not hasattr(self, "_fl_" + name) else getattr(self, "_fl_" + name)
        setattr(self, "_fl_" + name, files)
        if not files:
            return Image.new("RGBA", (W, H), (30, 25, 20, 255))
        return Image.open(files[min(i, len(files) - 1)]).convert("RGBA")

    def mini(self, key):
        if key not in self._mini:
            if key == "bt":
                cam = Cam(33.63, 21.86, 1.7, 380, 380)
                st = {"bt": 1, "eg": 1, "sd": 1, "dim_other": 1}
            else:
                cam = Cam(35.45, 22.5, 3.9, 380, 380)
                st = {"ha": 1, "eg": 1, "sd": 1, "dim_other": 1}
            im = render_map(cam, st, 0.4).convert("RGBA")
            im.putalpha(B.rounded_mask(im.size, 34))
            frame = Image.new("RGBA", (im.width + 16, im.height + 16), (0, 0, 0, 0))
            ImageDraw.Draw(frame).rounded_rectangle((0, 0, frame.width - 1, frame.height - 1), 40,
                                                    fill=(255, 255, 255, 255))
            frame.alpha_composite(im, (8, 8))
            self._mini[key] = frame
        return self._mini[key]

    # ---------------------------------------------------------------- cards
    def card_versus(self, t):
        im = Image.new("RGBA", CARD_S, (0, 0, 0, 0))
        g = vgrad(CARD_S, (22, 32, 64), (12, 18, 38))
        im.paste(g, (0, 0))
        T = self.t
        s = pop(t, T["trap"] - 0.05)
        if s > 0:
            B.paste_center(im, pillc("THE TRAP", 58, (255, 80, 60), (255, 255, 255), "⚠️", 56), 480, 78, s)
        for key, x, tt, lab, col, sub in (("bt", 245, T["claims"], "CLAIM THIS", (60, 200, 90), "2,060 km²"),
                                          ("ha", 715, T["give"], "LOSE THIS", (235, 60, 50), "20,580 km²")):
            s = pop(t, tt - 0.1, 0.35)
            if s > 0:
                B.paste_center(im, self.mini(key), x, 360, s * 0.95, 1, -3 if key == "bt" else 3)
                B.paste_center(im, pillc(lab, 44, col, (255, 255, 255)), x, 560, s)
                B.paste_center(im, timg(sub, 34, (255, 255, 255), 5), x, 175, s)
        s = pop(t, T["give"] - 0.25, 0.3)
        if s > 0:
            d = ImageDraw.Draw(im)
            cx, cy = 480, 360
            L = 60 * s
            d.line((cx - L, cy, cx + L, cy), fill=(255, 214, 10, 255), width=14)
            d.polygon([(cx + L + 26, cy), (cx + L - 8, cy - 26), (cx + L - 8, cy + 26)], fill=(255, 214, 10, 255))
        x_t = T["halaib"]
        if t > x_t:
            f = ease((t - x_t) / 0.35)
            d = ImageDraw.Draw(im)
            cx, cy, r = 715, 360, 150
            for (ax, ay, bx, by), ff in (((cx - r, cy - r, cx + r, cy + r), min(1, f * 2)),
                                         ((cx + r, cy - r, cx - r, cy + r), max(0, f * 2 - 1))):
                if ff > 0:
                    d.line((ax, ay, ax + (bx - ax) * ff, ay + (by - ay) * ff), fill=(235, 40, 40, 255), width=26)
        return im

    def card_flags(self, t):
        im = vgrad(CARD_S, (255, 244, 214), (255, 214, 140)).convert("RGBA")
        T = self.t
        shake = math.sin((t - T["not"]) * 22) * 9 * math.exp(-(t - T["not"]) * 2.2) if t > T["not"] else 0
        for tt, fl, name, x in ((T["egypt"], "🇪🇬", "EGYPT", 230), (T["sudan"], "🇸🇩", "SUDAN", 730)):
            s = pop(t, tt - 0.05, 0.35)
            if s > 0:
                B.paste_center(im, emoji(fl, 210), x, 380, s, 1, shake)
                B.paste_center(im, timg(name, 52, (255, 255, 255), 7), x, 545, s)
        s = pop(t, T["bir"] - 0.05, 0.3)
        if s > 0:
            mini = self.mini("bt")
            B.paste_center(im, mini, 480, 300, 0.42 * s, 1, 4)
            B.paste_center(im, timg("?", 120, YELLOW, 9), 480 + 75, 220, s, 1, 12)
        s = pop(t, T["not"] - 0.05, 0.3)
        if s > 0:
            B.paste_center(im, bubble("NOT OURS!"), 290, 150, s, 1, -5)
            s2 = pop(t, T["not"] + 0.12, 0.3)
            B.paste_center(im, bubble("NOT OURS!"), 760, 150, s2, 1, 5)
        return im

    def card_video(self, t):
        T = self.t
        i = max(0, int((t - (self.tl.beats[7]["start"] - 0.4)) * FPS))
        files = getattr(self, "_card7", None)
        if files is None:
            files = sorted((WORK2 / "frames" / "card_7").glob("*.jpg"))
            self._card7 = files
        im = (Image.open(files[min(i, len(files) - 1)]).convert("RGBA") if files
              else Image.new("RGBA", CARD_S, (120, 100, 80, 255)))
        for n, (key, lab, ic) in enumerate((("towns", "NO TOWNS", "🏠"), ("water", "NO WATER", "💧"),
                                            ("people", "NO PEOPLE", "👤"))):
            tt = T[key] - 0.18
            if t > tt:
                f = back((t - tt) / 0.35)
                x = -260 + (250 + 40) * f
                B.paste_center(im, pillc(lab, 48, (255, 255, 255), (20, 20, 20), "!" + ic, 62), x + 160,
                               110 + n * 135, 1)
        tt = T["country"]
        if t > tt - 0.05:
            f = ease((t - tt + 0.05) / 0.16)
            B.paste_center(im, stamp_img("NO COUNTRY", 96), 560, 470, 2.0 - f, f, -10)
        return im

    def card_story(self, t):
        T = self.t
        surf = cairo.ImageSurface(cairo.FORMAT_RGB24, *CARD_S)
        c = cairo.Context(surf)
        cw, ch = CARD_S
        g = cairo.LinearGradient(0, 0, 0, ch)
        g.add_color_stop_rgb(0, 0.98, 0.58, 0.36)
        g.add_color_stop_rgb(0.65, 1.0, 0.85, 0.58)
        g.add_color_stop_rgb(1, 1.0, 0.9, 0.66)
        c.set_source(g)
        c.paint()
        # sun
        for r, a in ((150, 0.12), (110, 0.2)):
            c.arc(730, 210, r, 0, 2 * math.pi)
            c.set_source_rgba(1, 0.97, 0.75, a)
            c.fill()
        c.arc(730, 210, 78, 0, 2 * math.pi)
        c.set_source_rgb(1, 0.96, 0.78)
        c.fill()
        # dunes
        for base, amp, col, sp, ph in ((420, 40, (0.93, 0.66, 0.42), 6, 0.0), (470, 46, (0.9, 0.58, 0.34), 11, 2.0)):
            c.move_to(0, ch)
            off = t * sp
            for x in range(0, cw + 21, 20):
                c.line_to(x, base - amp * math.sin((x + off) / 160 + ph) - 18 * math.sin((x + off) / 57 + ph))
            c.line_to(cw, ch)
            c.close_path()
            c.set_source_rgb(*col)
            c.fill()
        # front dune with the flag
        peak = (480, 405)
        c.move_to(0, ch)
        c.line_to(0, 560)
        c.curve_to(200, 520, 330, peak[1], peak[0], peak[1])
        c.curve_to(640, peak[1], 780, 520, cw, 545)
        c.line_to(cw, ch)
        c.close_path()
        gg = cairo.LinearGradient(0, peak[1], 0, ch)
        gg.add_color_stop_rgb(0, 0.99, 0.8, 0.52)
        gg.add_color_stop_rgb(1, 0.92, 0.66, 0.4)
        c.set_source(gg)
        c.fill()
        # people
        for tt, x, hgt in ((T["dad"], 330, 150), (T["daughter"], 610, 98)):
            s = pop(t, tt - 0.1, 0.35)
            if s > 0:
                gy = 470 if x < 480 else 465
                hh = hgt * s
                c.set_source_rgb(0.22, 0.13, 0.18)
                c.arc(x, gy - hh + hh * 0.13, hh * 0.13, 0, 2 * math.pi)
                c.fill()
                rr = hh * 0.17
                c.move_to(x - rr, gy)
                c.line_to(x - rr * 0.8, gy - hh * 0.72)
                c.curve_to(x - rr * 0.6, gy - hh * 0.78, x + rr * 0.6, gy - hh * 0.78, x + rr * 0.8, gy - hh * 0.72)
                c.line_to(x + rr, gy)
                c.close_path()
                c.fill()
        # flag pole
        pt = T["planted"]
        flag_xy = None
        if t > pt - 0.25:
            f = min(1.0, (t - pt + 0.25) / 0.25)
            drop = (1 - f ** 2) * -420
            px, py = peak[0], peak[1] + 6 + drop
            c.set_source_rgb(0.3, 0.22, 0.2)
            c.set_line_width(9)
            c.move_to(px, py)
            c.line_to(px, py - 250)
            c.stroke()
            c.arc(px, py - 254, 9, 0, 2 * math.pi)
            c.set_source_rgb(1, 0.8, 0.2)
            c.fill()
            fw, fh = 180, 112
            top = py - 245
            pts_t, pts_b = [], []
            for i in range(19):
                u = i / 18
                wv = 10 * math.sin(u * 5 - t * 7) * u
                pts_t.append((px + fw * u, top + wv))
                pts_b.append((px + fw * u, top + fh + wv * 1.1))
            c.move_to(*pts_t[0])
            for p_ in pts_t[1:]:
                c.line_to(*p_)
            for p_ in reversed(pts_b):
                c.line_to(*p_)
            c.close_path()
            c.set_source_rgb(0.36, 0.22, 0.7)
            c.fill_preserve()
            c.set_source_rgb(0.15, 0.08, 0.3)
            c.set_line_width(3)
            c.stroke()
            flag_xy = (px + fw * 0.5, top + fh * 0.5 + 10 * math.sin(0.5 * 5 - t * 7) * 0.5)
            # dust puff
            d = t - pt
            if 0 < d < 0.8:
                for j in range(9):
                    ang = math.pi + j / 8 * math.pi
                    rr = 30 + 160 * ease(d / 0.8)
                    c.arc(peak[0] + math.cos(ang) * rr, peak[1] + 10 + math.sin(ang) * rr * 0.25,
                          18 * (1 - d / 0.8) + 4, 0, 2 * math.pi)
                    c.set_source_rgba(1, 0.92, 0.75, 0.75 * (1 - d / 0.8))
                    c.fill()
        surf.flush()
        buf = np.ndarray((ch, cw, 4), np.uint8, surf.get_data())
        im = Image.fromarray(buf[..., [2, 1, 0]].copy(), "RGB").convert("RGBA")
        if flag_xy:
            B.paste_center(im, emoji("👑", 64), flag_xy[0], flag_xy[1], 1)
        s = pop(t, T["princess"] - 0.05, 0.35)
        if s > 0:
            B.paste_center(im, emoji("👑", 58), 610, 465 - 98 - 18, s, 1, -8)
            for j in range(6):
                a = j / 6 * 2 * math.pi + t
                rr = 70 + 30 * math.sin(t * 5 + j)
                B.paste_center(im, emoji("✨", 34), 610 + math.cos(a) * rr, 340 + math.sin(a) * rr * 0.6,
                               s * (0.6 + 0.4 * math.sin(t * 8 + j)))
            B.paste_center(im, pillc("A REAL PRINCESS?", 50, (255, 120, 190), (255, 255, 255)), 480, 585, s, 1, -2)
        s = pop(t, T["y2014"] - 0.08, 0.3)
        if s > 0:
            B.paste_center(im, pillc("2014", 56, (255, 255, 255), (20, 20, 20), "📅", 54), 150, 75, s, 1, -4)
        # beat 9: darken + stamp
        rt = T["recog"]
        k9 = self.tl.beats[9]["start"]
        if t > k9 - 0.1:
            dk = ramp(t, k9 - 0.1, 0.35) * 0.45
            im = Image.blend(im, Image.new("RGBA", im.size, (20, 10, 10, 255)), dk)
            if t > rt - 0.1:
                f = ease((t - rt + 0.1) / 0.16)
                B.paste_center(im, stamp_img("NOT RECOGNIZED", 76), 480, 320, 2.2 - 1.2 * f, f, -11)
        return im

    def card(self, t):
        tl = self.tl
        k = tl.beat_at(t)
        grp = next(g for g in self.groups if k in g)
        start = tl.beats[grp[0]]["start"] - 0.12
        end = tl.beats[grp[-1]]["end"] - 0.12
        fn = {5: self.card_versus, 6: self.card_flags, 7: self.card_video, 8: self.card_story}[grp[0]]
        inner = fn(t)
        p = (t - start) / 0.38
        s = back(p) if p < 1 else 1.0
        al = min(1.0, max(0.0, p * 2.5))
        q = (t - (end - 0.14)) / 0.14
        if 0 < q:
            s *= 1 - 0.25 * ease(q)
            al *= 1 - ease(q)
        tilt = (-1.6 if grp[0] % 2 else 1.6) - 7 * (1 - ease(p))
        y = CARD_C[1] - 60 * (1 - ease(p))
        return framed(inner), s, al, tilt, y


def vgrad(size, top, bottom):
    w, h = size
    a = np.linspace(0, 1, h)[:, None, None]
    arr = np.array(top, np.float32) * (1 - a) + np.array(bottom, np.float32) * a
    return Image.fromarray(np.repeat(arr, w, 1).astype(np.uint8), "RGB")


_frame_parts = {}


def framed(inner):
    """rounded card with a white border and a soft shadow."""
    w, h = inner.size
    r = 42
    if "sh" not in _frame_parts:
        sh, pad = B.shadow_for((w + 20, h + 20), r + 8, 26, 160)
        _frame_parts["sh"] = (sh, pad)
        _frame_parts["mask"] = B.rounded_mask((w, h), r)
    sh, pad = _frame_parts["sh"]
    out = sh.copy()
    border = Image.new("RGBA", (w + 20, h + 20), (0, 0, 0, 0))
    ImageDraw.Draw(border).rounded_rectangle((0, 0, w + 19, h + 19), r + 8, fill=(255, 255, 255, 255))
    out.alpha_composite(border, (pad, pad))
    inner = inner.copy()
    inner.putalpha(_frame_parts["mask"])
    out.alpha_composite(inner, (pad + 10, pad + 10))
    return out


# ====================================================================== presenter
CUES = {
    0: [(None, "point_up"), ("places", "talk"), ("no", "shrug")],
    1: [(None, "present"), ("Bir", "point_up"), ("squeezed", "talk2"), ("Egypt", "point_up"), ("Sudan", "talk")],
    2: [(None, "think"), ("British", "talk"), ("straight", "present"), ("here", "point_up")],
    3: [(None, "shrug"), ("they", "talk"), ("second", "count2"), ("And", "talk2"), ("bends", "wow")],
    4: [(None, "talk"), ("two", "count2"), ("tiny", "think"), ("Halaib", "point_up"), ("ten", "wow"), ("Red", "present")],
    5: [(None, "think"), ("Whoever", "whisper")],
    6: [(None, "laugh"), ("Egypt", "present"), ("Bir", "think"), ("Not", "shrug")],
    7: [(None, "count1"), ("water", "count2"), ("people", "count3"), ("And", "present")],
    8: [(None, "think"), ("American", "talk"), ("planted", "fist_up"), ("so", "talk2"), ("princess", "wow")],
    9: [(None, "laugh")],
    10: [(None, "talk"), ("nobody", "shrug"), ("Totally", "whisper")],
}
EMPH = [(0, "no"), (1, "Bir"), (1, "squeezed"), (2, "straight"), (3, "second"), (3, "bends"), (4, "tiny"),
        (4, "ten"), (5, "trap"), (6, "Not"), (7, "towns"), (7, "water"), (7, "people"), (7, "country"),
        (8, "flag"), (8, "princess"), (9, "recognized"), (10, "Totally")]
MOOD_OF = {"curious": "curious", "excited": "excited", "sighs": "sigh", "whispers": "whisper", "laughs": "laugh"}


def make_blip(tl: TL, rms):
    plan = []
    for k, cues in CUES.items():
        bt = tl.beats[k]
        times = [bt["start"] - 0.15 if w is None else tl.wt(k, w) - 0.12 for w, _ in cues]
        for i, (_, pose) in enumerate(cues):
            end = times[i + 1] if i + 1 < len(times) else bt["end"] - 0.15
            plan.append((times[i], end, pose, 1))
    moods = []
    for bt in tl.beats:
        b = bt["b"]
        segs = []          # (start, mood)
        has_tag = any(bt["tags"])
        prev = None
        for (s, e, w), tag in zip(bt["words"], bt["tags"]):
            m = MOOD_OF.get(tag) if tag else (None if has_tag else b.get("mood"))
            m = m or "neutral"
            if m != prev:
                segs.append([s - 0.25 if segs else bt["start"] - 0.1, m])
                prev = m
        for i, (s, m) in enumerate(segs):
            e = segs[i + 1][0] if i + 1 < len(segs) else bt["end"] - 0.1
            if m == "laugh" and e - s > 1.5:
                moods.append((s, s + 1.5, "laugh"))
                moods.append((s + 1.5, e, "excited"))
            else:
                moods.append((s, e, m))
    emph = [tl.wt(k, w) for k, w in EMPH]
    return Blip(rms, tl.words, plan, moods, emph)


_glow = {}


def presenter_glow(size):
    if size not in _glow:
        w, h = size
        im = Image.new("RGBA", size, (0, 0, 0, 0))
        ImageDraw.Draw(im).ellipse((w * 0.1, h * 0.12, w * 0.9, h * 0.95), fill=(255, 220, 150, 70))
        _glow[size] = im.filter(ImageFilter.GaussianBlur(w // 9))
    return _glow[size]


def place_presenter(frame, im, cx, bottom, scale, outline=False, alpha=1.0):
    if scale <= 0.01 or alpha <= 0.01:
        return
    w, h = int(im.width * scale), int(im.height * scale)
    p = im.resize((w, h), Image.BILINEAR)
    x, y = int(cx - w / 2), int(bottom - h)
    a = p.getchannel("A")
    if outline:
        edge = a.filter(ImageFilter.MaxFilter(11))
        sh = Image.new("RGBA", p.size, (0, 0, 0, 0))
        sh.paste((0, 0, 0, 120), (0, 0), edge)
        sh = sh.filter(ImageFilter.GaussianBlur(8))
        white = Image.new("RGBA", p.size, (255, 255, 255, 255))
        white.putalpha(edge)
        layer = Image.new("RGBA", p.size, (0, 0, 0, 0))
        layer.alpha_composite(sh)
        layer.alpha_composite(white)
        layer.alpha_composite(p)
        p = layer
    else:
        g = presenter_glow((w, h))
        B.safe_paste(frame, g, x, y)
        sh = Image.new("RGBA", p.size, (0, 0, 0, 0))
        sh.paste((0, 0, 0, 110), (0, 0), a)
        B.safe_paste(frame, sh.filter(ImageFilter.GaussianBlur(14)), x + 10, y + 18)
    if alpha < 1:
        p.putalpha(p.getchannel("A").point(lambda v: int(v * alpha)))
    B.safe_paste(frame, p, x, y)


# ====================================================================== whole frame
class Composer:
    def __init__(self):
        self.tl = TL()
        self.sc = Scenes(self.tl)
        self.face = Face(self.tl, self.sc)
        rms = wav_rms(WORK2 / "voice_pad.wav")
        self.blip = make_blip(self.tl, rms)
        self.chunks = B.caption_chunks(self.tl.words)
        self.punches = self._punches()
        self.shakes = [self.face.t["recog"], self.face.t["country"], self.sc.t_no, self.face.t["planted"]]
        rnd = np.random.default_rng(7)
        self.grain = [rnd.normal(0, 5.0, (H // 2, W // 2, 1)).astype(np.float32) for _ in range(6)]
        yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
        d = np.sqrt(((xx - W / 2) / (W * 0.75)) ** 2 + ((yy - H / 2) / (H * 0.72)) ** 2)
        self.vig = (1 - 0.32 * np.clip(d - 0.35, 0, 1) ** 1.5)[..., None].astype(np.float32)

    def _punches(self):
        tl = self.tl
        out = [(self.sc.t_no, 0.06), (self.sc.t_tiny, 0.05), (self.sc.t_ten, 0.06)]
        for k, w in ((5, "trap"), (6, "Not"), (7, "country"), (8, "princess"), (9, "recognized"), (10, "Totally")):
            out.append((tl.wt(k, w), 0.045))
        return out

    def scene(self, layout, t):
        tl = self.tl
        if layout == "map":
            fr = self.sc.map_frame(t)
            # presenter, small, bottom-left
            pin = pop(t, 0.55, 0.4)
            alpha = 1.0
            if t > tl.total - 0.6:
                pin *= 1 - ease((t - tl.total + 0.6) / 0.5)
            if pin > 0:
                im = self.blip.render(t)
                place_presenter(fr, im, 215, H + 30 + (1 - min(pin, 1)) * 250, 0.47 * max(pin, 0.01), True, alpha)
            return fr
        fr = self.face.bg(t)
        # dark gradient for the caption zone
        card, s, al, tilt, y = self.face.card(t)
        im = self.blip.render(t)
        enter = pop(t, tl.T1 - 0.05, 0.45)
        place_presenter(fr, im, 540, H + 70 + (1 - min(enter, 1)) * 400, 0.93)
        B.paste_center(fr, card, CARD_C[0], y, s, al, tilt)
        return fr

    def frame(self, t) -> np.ndarray:
        tl = self.tl
        d = 0.36
        lay = tl.layout(t)
        trans = None
        for T, a_lay, b_lay in ((tl.T1, "map", "face"), (tl.T2, "face", "map")):
            if T - d / 2 <= t < T + d / 2:
                trans = (T, a_lay, b_lay)
        if trans:
            T, a_lay, b_lay = trans
            p = (t - (T - d / 2)) / d
            A = self.scene(a_lay, min(t, T - 0.001)).convert("RGB")
            Bf = self.scene(b_lay, max(t, T)).convert("RGB")
            A = zoom(A, 1 + 0.55 * p * p, blur=True)
            Bf = zoom(Bf, 1 + 0.35 * (1 - p) ** 2, blur=True)
            fr = Image.blend(A, Bf, ease(p))
            flash = math.exp(-((p - 0.5) / 0.15) ** 2) * 0.22
            if flash > 0.01:
                fr = Image.blend(fr, Image.new("RGB", fr.size, (255, 255, 255)), flash)
        else:
            fr = self.scene(lay, t).convert("RGB")
        # punch-in + shake
        z = 1.0
        for te, amt in self.punches:
            dt = t - te
            if -0.05 <= dt < 0.6:
                env = ease((dt + 0.05) / 0.08) * math.exp(-max(0, dt) / 0.22)
                z += amt * env
        ox = oy = 0.0
        for te in self.shakes:
            dt = t - te
            if 0 <= dt < 0.35:
                k = (1 - dt / 0.35) * 16
                ox += k * math.sin(dt * 90)
                oy += k * math.cos(dt * 71)
        if z > 1.001 or abs(ox) + abs(oy) > 0.5:
            fr = zoom(fr, z, ox=ox, oy=oy)
        # captions
        cy = 1268 if tl.layout(t) == "map" else 905
        if not (tl.T2 - 0.05 < t < tl.T2 + 0.2):
            fr = fr.convert("RGBA")
            B.draw_caption(fr, self.chunks, t, cy)
            fr = fr.convert("RGB")
        # grade
        arr = np.asarray(fr).astype(np.float32)
        arr = (arr - 128) * 1.06 + 128 + 2
        arr *= self.vig
        g = self.grain[int(t * FPS) % len(self.grain)]
        arr += np.repeat(np.repeat(g, 2, 0), 2, 1)
        return np.clip(arr, 0, 255).astype(np.uint8)


def zoom(im, z, blur=False, ox=0.0, oy=0.0):
    w, h = im.size
    cw, ch = w / z, h / z
    x0, y0 = (w - cw) / 2 - ox / z, (h - ch) / 2 - oy / z
    out = im.resize((w, h), Image.BILINEAR, box=(x0, y0, x0 + cw, y0 + ch))
    if blur and z > 1.02:
        z2 = 1 + (z - 1) * 0.85
        cw2, ch2 = w / z2, h / z2
        x2, y2 = (w - cw2) / 2, (h - ch2) / 2
        o2 = im.resize((w, h), Image.BILINEAR, box=(x2, y2, x2 + cw2, y2 + ch2))
        out = Image.blend(out, o2, 0.45)
    return out


# ====================================================================== prep + audio
def prep_audio(tl_total=None):
    WORK2.mkdir(parents=True, exist_ok=True)
    pad = WORK2 / "voice_pad.wav"
    vdur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
                                 str(OUT2 / "voice.mp3")], capture_output=True, text=True).stdout.strip())
    total = round(VO + vdur + TAIL, 3)
    run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(OUT2 / "voice.mp3"), "-af",
         f"adelay={int(VO * 1000)},apad", "-t", f"{total:.3f}", "-ar", "48000", "-ac", "1", str(pad)])
    return pad, total


def prep_video():
    tl = TL()
    jobs = [("card_7", MEDIA2 / "card_7.mp4", tl.beats[7]["start"] - 0.4, tl.beats[8]["start"] + 0.3,
             f"scale={CARD_S[0]}:-2,crop={CARD_S[0]}:{CARD_S[1]}:0:(ih-{CARD_S[1]})*0.62,eq=saturation=1.12:contrast=1.05"),
            ("bg_sand", MEDIA2 / "bg_sand.mp4", tl.beats[7]["start"] - 0.4, tl.beats[8]["start"] + 0.3,
             f"scale=-2:{H},crop={W}:{H},gblur=sigma=10,eq=brightness=-0.13:saturation=0.85"),
            ("bg_desert", MEDIA2 / "bg_desert.mp4", tl.beats[8]["start"] - 0.4, tl.T2 + 0.4,
             f"scale=-2:{H},crop={W}:{H}:(iw-{W})*0.45:0,gblur=sigma=10,eq=brightness=-0.13:saturation=0.85")]
    for name, src, a, b, vf in jobs:
        d = WORK2 / "frames" / name
        if d.exists() and any(d.glob("*.jpg")):
            continue
        d.mkdir(parents=True, exist_ok=True)
        run(["ffmpeg", "-y", "-loglevel", "error", "-ss", "1.0", "-i", str(src), "-t", f"{b - a + 0.5:.2f}",
             "-vf", f"fps={FPS},{vf}", "-q:v", "3", str(d / "%05d.jpg")])
        log(f"frames {name}: {len(list(d.glob('*.jpg')))}")


def sfx_events(tl: TL, sc: Scenes, fc: Face):
    b = tl.beats
    T = fc.t
    ev = [("whoosh", 0.05, 0.8), ("pop", sc.t_patch + 0.3, 0.9), ("thup", sc.t_patch + 0.45, 0.6),
          ("riser", sc.t_no - 1.0, 0.8), ("thud", sc.t_no, 1.0), ("pop", sc.t_no + 0.25, 0.6),
          ("swish", b[1]["start"] - 0.2, 0.8), ("pop", sc.t_bir, 0.8), ("boing", sc.t_sq, 0.5),
          ("bubble", sc.t_eg + 0.05, 0.8), ("bubble", sc.t_sd + 0.05, 0.8),
          ("whoosh", b[2]["start"] - 0.15, 0.55), ("pop", sc.t_straight, 0.7), ("ding", sc.l99[1] - 0.1, 0.5),
          ("whoosh", b[3]["start"] - 0.1, 0.7), ("click", sc.t_second, 0.8), ("boing", tl.wt(3, "bends"), 0.6),
          ("ding", sc.l02[1] - 0.1, 0.4),
          ("pop", sc.t_tiny, 0.8), ("plink", sc.t_hal, 0.7), ("pop", sc.t_tri, 0.8), ("boing", sc.t_ten, 0.7),
          ("shimmer", sc.t_red, 0.6),
          ("whoosh", tl.T1, 1.0), ("pop", T["trap"], 0.8), ("tension", T["claims"] - 0.5, 0.55),
          ("swish", T["claims"] - 0.1, 0.7), ("swish", T["give"] - 0.1, 0.7), ("err", T["halaib"] + 0.1, 0.5),
          ("whoosh", b[6]["start"] - 0.15, 0.6), ("bubble", T["egypt"], 0.8), ("bubble", T["sudan"], 0.8),
          ("click", T["bir"], 0.6), ("boing", T["not"], 0.7), ("boing", T["not"] + 0.12, 0.5),
          ("whoosh", b[7]["start"] - 0.15, 0.6), ("pop", T["towns"] - 0.1, 0.7), ("pop", T["water"] - 0.1, 0.7),
          ("pop", T["people"] - 0.1, 0.7), ("thud", T["country"], 0.9),
          ("whoosh", b[8]["start"] - 0.15, 0.6), ("click", T["y2014"], 0.7), ("pop", T["dad"] - 0.1, 0.5),
          ("thud", T["planted"], 0.7), ("rumble", T["planted"], 0.4), ("pop", T["daughter"] - 0.1, 0.5),
          ("chime", T["princess"] - 0.05, 0.6),
          ("thud", T["recog"], 1.0),
          ("whoosh", tl.T2, 0.9), ("pop", sc.t_nobody, 0.6), ("shimmer", sc.t_tot, 0.7),
          ("whoosh", tl.total - 3.0, 0.5)]
    # pen scratches while the borders are drawn
    for a, bb in (sc.l99, sc.l02):
        x = a
        while x < bb - 0.1:
            ev.append(("type", x, 0.45))
            x += 0.32
    return sorted(ev, key=lambda e: e[1])


def wind(total, ref, out):
    sr = 48000
    n = int(sr * total)
    rnd = np.random.default_rng(3)
    x = rnd.normal(0, 1, n).astype(np.float32)
    f = np.fft.rfftfreq(n, 1 / sr)
    shape = 1 / (1 + (f / 260) ** 2) * (f > 35)          # soft low-pass: a dull desert wind
    y = np.fft.irfft(np.fft.rfft(x) * shape, n).astype(np.float32)
    tt = np.arange(n) / sr
    env = 0.6 + 0.25 * np.sin(tt * 0.7) + 0.15 * np.sin(tt * 1.9 + 1)
    y *= env
    y /= np.sqrt((y ** 2).mean()) + 1e-9
    return y * ref * 0.11


def mix(tl: TL, sc: Scenes, fc: Face, total: float) -> Path:
    from studio.pro import _mix_audio
    pad = WORK2 / "voice_pad.wav"
    sfx = WORK2 / "sfx2.wav"
    motion.write_sfx(sfx_events(tl, sc, fc), total, sfx, 0.55, voice=pad)
    with wave.open(str(sfx)) as w:
        s = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768
    ref = motion._speech_rms(pad) or 0.05
    wd = wind(total + 2, ref, None)[: len(s)]
    s = s + wd[: len(s)]
    s = np.clip(s, -1, 1)
    with wave.open(str(sfx), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(48000)
        w.writeframes((s * 32767).astype(np.int16).tobytes())
    track = MUSIC_DIR / tl.data.get("music", "sneaky-snitch.mp3")
    return _mix_audio(pad, sfx, track if track.exists() else None, total, 0.075, WORK2, "v2")


# ====================================================================== render
_C = None


def _worker(args):
    i, a, b = args
    global _C
    if _C is None:
        _C = Composer()
    out = WORK2 / f"part_{i}.mp4"
    p = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s",
                          f"{W}x{H}", "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "medium", "-crf",
                          "16", "-pix_fmt", "yuv420p", str(out)], stdin=subprocess.PIPE)
    for n in range(a, b):
        p.stdin.write(_C.frame(n / FPS).tobytes())
        if (n - a) % 60 == 0:
            print(f"part {i}: frame {n - a}/{b - a}", flush=True)
    p.stdin.close()
    p.wait()
    return str(out)


def compose():
    import multiprocessing as mp
    pad, total = prep_audio()
    prep_video()
    nfr = int(round(total * FPS))
    C = Composer()
    log(f"total {total:.2f}s, {nfr} frames")
    audio = mix(C.tl, C.sc, C.face, total)
    nw = 4
    bounds = [round(nfr * i / nw) for i in range(nw + 1)]
    with mp.get_context("fork").Pool(nw) as pool:
        parts = pool.map(_worker, [(i, bounds[i], bounds[i + 1]) for i in range(nw)])
    lst = WORK2 / "parts.txt"
    lst.write_text("".join(f"file '{Path(p).name}'\n" for p in parts))
    final = OUT2 / "final.mp4"
    run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", lst.name, "-i", str(audio),
         "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "256k", "-t", f"{total:.3f}",
         "-movflags", "+faststart", str(final)], cwd=WORK2)
    log(f"final: {final}")


def preview(times):
    prep_audio()
    prep_video()
    C = Composer()
    outd = WORK2 / ("preview" + os.environ.get("PV", ""))
    outd.mkdir(parents=True, exist_ok=True)
    import time as _t
    for t in times:
        t0 = _t.time()
        arr = C.frame(t)
        Image.fromarray(arr).save(outd / f"f_{t:06.2f}.jpg", quality=88)
        print(f"{t:.2f}s rendered in {_t.time() - t0:.2f}s", flush=True)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "preview":
        preview([float(x) for x in sys.argv[2:]])
    else:
        compose()
