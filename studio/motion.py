"""Map-style motion graphics (like the "every second on Earth" Shorts).

A scene in a "style": "map" script can say where the camera goes and what pops up:

    {"text": "Around four babies are born.",
     "region": "asia",              # a name from REGIONS, or "space" for the globe
     "icons": ["👶"], "icon_count": 6,
     "number": "4", "label": "babies"}

The video is drawn frame by frame with Pillow and piped into ffmpeg. A matching
sound-effects track (pops, whooshes, ticks, a ding) is built at the same time.
Everything used is free: NASA Blue Marble (public domain), Noto Color Emoji
(SIL Open Font License) and sound effects made here in code.
"""
from __future__ import annotations

import json
import math
import random
import re
import subprocess
import wave
from functools import lru_cache
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

from .common import ROOT, font_file, log

MAP_DIR = ROOT / "assets" / "map"
SR = 48000

# lon, lat, visible width in degrees (portrait frame shows width * 16/9 of height)
REGIONS = {
    "world": (20, 15, 100), "earth": (20, 15, 100),
    "asia": (95, 30, 70), "south_asia": (80, 22, 40), "india": (79, 22, 32),
    "bangladesh": (90, 23.7, 12), "china": (104, 34, 42), "japan": (138, 37, 20),
    "korea": (127.5, 36.5, 12), "indonesia": (118, -2, 40), "southeast_asia": (110, 10, 40),
    "russia": (95, 60, 80), "middle_east": (45, 27, 35), "arabia": (45, 23, 28),
    "europe": (15, 50, 42), "uk": (-2, 54, 12), "france": (2.5, 46.5, 12),
    "italy": (12.5, 42.5, 12), "scandinavia": (15, 63, 25),
    "africa": (20, 3, 70), "sahara": (10, 23, 40), "egypt": (30, 26, 18),
    "east_africa": (37, 0, 28), "madagascar": (47, -19, 14),
    "north_america": (-100, 45, 75), "usa": (-98, 39, 50), "canada": (-100, 58, 60),
    "mexico": (-102, 23, 28), "alaska": (-152, 63, 30), "greenland": (-42, 70, 45),
    "south_america": (-60, -17, 62), "brazil": (-52, -10, 42), "amazon": (-62, -4, 28),
    "andes": (-70, -20, 30), "australia": (134, -25, 48), "new_zealand": (172, -41, 18),
    "pacific": (-160, 0, 90), "atlantic": (-35, 20, 80), "indian_ocean": (75, -15, 80),
    "arctic": (0, 72, 90), "antarctica": (0, -68, 90), "himalaya": (86, 28, 18),
    "hawaii": (-157, 20.5, 8), "caribbean": (-72, 18, 25),
}
SPACE = {"space", "globe", "orbit", "planet", "sun"}

# sound effect played when an icon with one of these emoji pops in
ICON_SFX = {"⚡": "thunder", "🌩": "thunder", "💰": "cash", "💵": "cash", "💸": "cash",
            "🪙": "cash", "💥": "boom", "🌋": "boom", "🔥": "boom", "❤": "ding",
            "⏰": "tick", "⏱": "tick"}


# ----------------------------------------------------------------- helpers
def _ease(t: float) -> float:            # ease in-out cubic, 0..1
    t = min(max(t, 0.0), 1.0)
    return 4 * t * t * t if t < .5 else 1 - (-2 * t + 2) ** 3 / 2


def _back(t: float) -> float:            # ease-out with a small overshoot
    t = min(max(t, 0.0), 1.0)
    c1, c3 = 1.9, 2.9
    return 1 + c3 * (t - 1) ** 3 + c1 * (t - 1) ** 2


def _out(t: float) -> float:
    t = min(max(t, 0.0), 1.0)
    return 1 - (1 - t) ** 3


@lru_cache(maxsize=None)
def _font(size: int) -> ImageFont.FreeTypeFont:
    try:
        return ImageFont.truetype(font_file("Noto Sans", bold=True), size)
    except (SystemExit, OSError):
        return ImageFont.truetype("DejaVuSans-Bold.ttf", size)


def _emoji_font_path() -> str | None:
    out = subprocess.run(["fc-match", "-f", "%{file}", "Noto Color Emoji"],
                         capture_output=True, text=True).stdout.strip()
    return out if out and "Emoji" in out else None


@lru_cache(maxsize=None)
def emoji_image(ch: str, size: int) -> Image.Image:
    """An emoji as a picture (with a soft shadow), size px tall."""
    path = _emoji_font_path()
    if not path:
        raise SystemExit("Noto Color Emoji font missing (apt install fonts-noto-color-emoji)")
    font = ImageFont.truetype(path, 109)          # the only size this bitmap font has
    canvas = Image.new("RGBA", (180, 160), (0, 0, 0, 0))
    ImageDraw.Draw(canvas).text((10, 10), ch, font=font, embedded_color=True)
    box = canvas.getbbox() or (0, 0, 1, 1)
    em = canvas.crop(box)
    em = em.resize((max(1, round(em.width * size / em.height)), size), Image.LANCZOS)
    pad = size // 6
    out = Image.new("RGBA", (em.width + 2 * pad, em.height + 2 * pad), (0, 0, 0, 0))
    shadow = Image.new("RGBA", out.size, (0, 0, 0, 0))
    shadow.paste((0, 0, 0, 150), (pad + size // 25, pad + size // 18), em)
    shadow = shadow.filter(ImageFilter.GaussianBlur(size / 22))
    out.alpha_composite(shadow)
    out.alpha_composite(em, (pad, pad))
    return out


def parse_number(s: str) -> tuple[str, float, str, int, bool]:
    """'1,200 BBL' -> ('', 1200, ' BBL', decimals 0, commas True)."""
    m = re.search(r"\d[\d,]*(?:\.\d+)?", s)
    if not m:
        return s, 0.0, "", 0, False
    num = m.group(0)
    dec = len(num.split(".")[1]) if "." in num else 0
    return s[:m.start()], float(num.replace(",", "")), s[m.end():], dec, "," in num


def format_number(v: float, dec: int, commas: bool) -> str:
    return f"{v:,.{dec}f}" if commas else f"{v:.{dec}f}"


# ------------------------------------------------------------------- map
def load_map() -> Image.Image:
    """The world map (equirectangular). NASA Blue Marble if present, else drawn."""
    jpg = MAP_DIR / "blue-marble.jpg"
    if jpg.exists():
        img = Image.open(jpg).convert("RGB")
        if img.width > 5400:
            img = img.resize((5400, 2700), Image.LANCZOS)
        img = ImageEnhance.Color(img).enhance(1.25)
        img = ImageEnhance.Contrast(img).enhance(1.08)
        return img
    return _drawn_map()


def _drawn_map(w: int = 4096) -> Image.Image:
    h = w // 2
    y = np.linspace(0, 1, h)[:, None]
    ocean = np.dstack([(12 + 20 * (1 - abs(y - .5) * 2)) * np.ones((h, w)),
                       (60 + 50 * (1 - abs(y - .5) * 2)) * np.ones((h, w)),
                       (110 + 60 * (1 - abs(y - .5) * 2)) * np.ones((h, w))]).astype(np.uint8)
    img = Image.fromarray(ocean, "RGB")
    land = Image.new("L", (w, h), 0)
    d = ImageDraw.Draw(land)
    src = MAP_DIR / "ne_110m_land.geojson"
    if src.exists():
        for feat in json.loads(src.read_text())["features"]:
            g = feat["geometry"]
            polys = g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]
            for poly in polys:
                pts = [((lo + 180) / 360 * w, (90 - la) / 180 * h) for lo, la in poly[0]]
                d.polygon(pts, fill=255)
    land = land.filter(ImageFilter.GaussianBlur(1.2))
    green = Image.new("RGB", (w, h), (74, 128, 70))
    img.paste(green, (0, 0), land)
    return img


class World:
    def __init__(self) -> None:
        img = load_map()
        self.w, self.h = img.size
        self.ppd = self.w / 360.0
        # three copies side by side so the camera can cross the date line
        wide = Image.new("RGB", (self.w * 3, self.h))
        for k in range(3):
            wide.paste(img, (k * self.w, 0))
        self.wide = wide
        self.arr = np.asarray(img)
        self._globe_cache: dict = {}

    def view(self, lon: float, lat: float, width_deg: float, size: tuple[int, int]) -> Image.Image:
        W, H = size
        width_deg = min(width_deg, 180.0 * W / H)
        hdeg = width_deg * H / W
        lat = min(max(lat, -90 + hdeg / 2), 90 - hdeg / 2)
        cx = (lon + 180) / 360 * self.w + self.w
        cy = (90 - lat) / 180 * self.h
        sw = width_deg * self.ppd
        scale = sw / W
        x0, y0 = cx - sw / 2, cy - scale * H / 2
        return self.wide.transform((W, H), Image.AFFINE, (scale, 0, x0, 0, scale, y0),
                                   resample=Image.BILINEAR)

    @property
    def sun_tex(self) -> np.ndarray:
        """A boiling-looking sun surface, made once from smoothed noise."""
        if getattr(self, "_sun", None) is None:
            rnd = np.random.default_rng(3)
            tex = np.zeros((self.h, self.w), np.float32)
            for cell, amp in [(8, .5), (24, .3), (64, .2)]:
                small = Image.fromarray((rnd.random((self.h // cell + 1, self.w // cell + 1)) * 255).astype(np.uint8))
                tex += np.asarray(small.resize((self.w, self.h), Image.BICUBIC), np.float32) / 255 * amp
            tex = (tex - tex.min()) / (tex.max() - tex.min())
            r = 255 * np.ones_like(tex)
            g = 120 + 120 * tex
            b = 20 + 60 * tex ** 2
            self._sun = np.dstack([r, g, b]).astype(np.uint8)
        return self._sun

    def globe(self, spin: float, radius: int, tilt: float = 18.0, sun: bool = False) -> Image.Image:
        """An orthographic globe (RGBA) turned to longitude `spin`."""
        key = (radius, tilt)
        if key not in self._globe_cache:
            n = 2 * radius
            yy, xx = np.mgrid[0:n, 0:n].astype(np.float32)
            x = (xx - radius + .5) / radius
            y = (radius - yy - .5) / radius
            r2 = x * x + y * y
            inside = r2 <= 1
            z = np.sqrt(np.clip(1 - r2, 0, 1))
            t = math.radians(tilt)
            lat = np.degrees(np.arcsin(np.clip(y * math.cos(t) + z * math.sin(t), -1, 1)))
            lonterm = np.degrees(np.arctan2(x, z * math.cos(t) - y * math.sin(t)))
            rows = np.clip(((90 - lat) / 180 * self.h).astype(np.int32), 0, self.h - 1)
            # light from the upper left, darker towards the edge
            shade = np.clip(0.35 + 0.75 * (0.55 * z + 0.3 * (-x) + 0.25 * y), 0.15, 1.15)
            alpha = np.clip((1 - np.sqrt(r2)) * radius * 1.5, 0, 1) * 255
            self._globe_cache[key] = (rows, lonterm, shade[..., None], inside, alpha.astype(np.uint8))
        rows, lonterm, shade, inside, alpha = self._globe_cache[key]
        cols = (((lonterm + spin + 180) / 360 * self.w) % self.w).astype(np.int32)
        if sun:          # a star glows evenly, a little brighter in the middle
            rgb = self.sun_tex[rows, cols].astype(np.float32) * (0.8 + 0.35 * shade / shade.max())
        else:
            rgb = self.arr[rows, cols].astype(np.float32) * shade
        rgba = np.dstack([np.clip(rgb, 0, 255).astype(np.uint8), alpha])
        return Image.fromarray(rgba, "RGBA")


def _stars(size: tuple[int, int], seed: int = 7) -> Image.Image:
    W, H = size
    rnd = random.Random(seed)
    y = np.linspace(0, 1, H)[:, None, None]
    bg = (np.array([4, 6, 18]) * (1 - y) + np.array([10, 14, 40]) * y) * np.ones((H, W, 3))
    img = Image.fromarray(bg.astype(np.uint8), "RGB")
    d = ImageDraw.Draw(img)
    for _ in range(420):
        x, yy = rnd.uniform(0, W), rnd.uniform(0, H)
        r = rnd.choice([1, 1, 1, 1.5, 2, 2.5])
        b = rnd.randint(140, 255)
        d.ellipse((x - r, yy - r, x + r, yy + r), fill=(b, b, min(255, b + 20)))
    return img


# ----------------------------------------------------------------- frames
class Scene:
    def __init__(self, raw: dict, start: float, end: float, index: int, prev_cam):
        self.raw, self.start, self.end, self.i = raw, start, end, index
        self.dur = end - start
        reg = str(raw.get("region", "")).strip().lower().replace(" ", "_").replace("-", "_")
        self.space = reg in SPACE
        if "lon" in raw and "lat" in raw:
            cam = (float(raw["lon"]), float(raw["lat"]), float(raw.get("zoom", 40)))
        elif reg in REGIONS:
            cam = REGIONS[reg]
        else:
            cam = prev_cam or REGIONS["world"]
        if "zoom" in raw and "lon" not in raw:
            cam = (cam[0], cam[1], float(raw["zoom"]))
        self.cam = cam
        self.prev_cam = prev_cam or (cam[0] - 25, cam[1], cam[2] * 1.5)
        self.move = 0.9 if self.prev_cam != cam else 0.0
        icons = raw.get("icons") or []
        if isinstance(icons, str):
            icons = [icons]
        count = int(raw.get("icon_count", 0) or 0) or (len(icons) if len(icons) > 1 else 5 if icons else 0)
        count = min(count, 14)
        rnd = random.Random(f"{index}-{raw.get('text', '')}")
        self.icons = []          # (emoji, x frac, y frac, appear time, size)
        if icons and count:
            spread = min(0.17, max(0.06, (self.dur * 0.55) / count))
            spots = _spots(count, rnd, self.space) if count > 1 else [(0.5, 0.5)]
            for k in range(count):
                ch = icons[k % len(icons)]
                x, y = spots[k]
                size = 320 if count == 1 else rnd.choice([150, 165, 180, 200])
                self.icons.append((ch, x, y, 0.25 + self.move * 0.6 + k * spread, size))
        self.number = str(raw["number"]).strip() if raw.get("number") not in (None, "") else ""
        self.label = str(raw.get("label", "")).strip()
        self.count_at = 0.15 + self.move * 0.5
        self.count_len = 0.9 if self.number else 0.0

    def camera(self, t: float):
        a = _ease(t / self.move) if self.move else 1.0
        p, c = self.prev_cam, self.cam
        dl = ((c[0] - p[0] + 180) % 360) - 180
        lon, lat = p[0] + dl * a, p[1] + (c[1] - p[1]) * a
        # zoom out a little in the middle of a move, then push in slowly
        width = p[2] + (c[2] - p[2]) * a
        width *= 1 + 0.35 * math.sin(math.pi * a) * (1 if self.move else 0)
        push = 1 - 0.07 * max(0.0, t - self.move) / max(self.dur, 1)
        return lon, lat, width * push


def _spots(n: int, rnd: random.Random, space: bool) -> list[tuple[float, float]]:
    pts: list[tuple[float, float]] = []
    lo_y, hi_y = (0.30, 0.70)
    for _ in range(n):
        best, best_d = None, -1.0
        for _ in range(40):
            p = (rnd.uniform(0.12, 0.88), rnd.uniform(lo_y, hi_y))
            if space and (p[0] - .5) ** 2 + ((p[1] - .5) * 1.77) ** 2 < 0.04:
                continue                       # keep the middle of the globe clear
            d = min((((p[0] - q[0]) ** 2 + ((p[1] - q[1]) * 1.77) ** 2) for q in pts), default=9)
            if d > best_d:
                best, best_d = p, d
        pts.append(best)
    return pts


def _text_img(text: str, size: int, fill=(255, 255, 255), stroke=(0, 0, 0)) -> Image.Image:
    f = _font(size)
    sw = max(3, size // 14)
    l, t, r, b = f.getbbox(text, stroke_width=sw)
    img = Image.new("RGBA", (r - l + 20, b - t + 20), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.text((10 - l + size // 30, 10 - t + size // 22), text, font=f, fill=(0, 0, 0, 120),
           stroke_width=sw, stroke_fill=(0, 0, 0, 120))
    d.text((10 - l, 10 - t), text, font=f, fill=fill, stroke_width=sw, stroke_fill=stroke)
    return img


def _label_img(text: str, size: int) -> Image.Image:
    f = _font(size)
    l, t, r, b = f.getbbox(text)
    px, py = size // 2, size // 4
    img = Image.new("RGBA", (r - l + 2 * px, b - t + 2 * py), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((0, 0, img.width - 1, img.height - 1), radius=size // 3, fill=(255, 214, 0, 245))
    d.text((px - l, py - t), text, font=f, fill=(20, 20, 20))
    return img


def _paste_scaled(frame: Image.Image, img: Image.Image, cx: float, cy: float,
                  scale: float, alpha: float = 1.0) -> None:
    if scale <= 0.02 or alpha <= 0.01:
        return
    w, h = max(1, int(img.width * scale)), max(1, int(img.height * scale))
    im = img.resize((w, h), Image.BILINEAR) if (w, h) != img.size else img
    if alpha < 1:
        im = im.copy()
        im.putalpha(im.getchannel("A").point(lambda v: int(v * alpha)))
    x, y = int(cx - w / 2), int(cy - h / 2)
    frame.alpha_composite(im, (x, y)) if x >= 0 and y >= 0 and x + w <= frame.width and y + h <= frame.height \
        else _safe_paste(frame, im, x, y)


def _safe_paste(frame: Image.Image, im: Image.Image, x: int, y: int) -> None:
    box = (max(0, -x), max(0, -y), min(im.width, frame.width - x), min(im.height, frame.height - y))
    if box[2] > box[0] and box[3] > box[1]:
        frame.alpha_composite(im.crop(box), (max(0, x), max(0, y)))


class Painter:
    def __init__(self, world: World, size: tuple[int, int]):
        self.world, self.size = world, size
        self.stars = _stars(size).convert("RGBA")
        W, H = size
        # dark band at top and bottom so numbers and captions stay readable
        g = np.zeros((H, 1), np.float32)
        yy = np.linspace(0, 1, H)
        g[:, 0] = np.clip((0.22 - yy) / 0.22, 0, 1) * 150 + np.clip((yy - 0.66) / 0.34, 0, 1) * 170
        self.vignette = Image.fromarray(
            np.dstack([np.zeros((H, W, 3), np.uint8), np.repeat(g, W, 1).astype(np.uint8)]), "RGBA")

    def background(self, sc: Scene, t: float) -> Image.Image:
        W, H = self.size
        if sc.space:
            frame = self.stars.copy()
            radius = int(W * 0.36)
            grow = 0.85 + 0.15 * _out(t / 1.2)
            is_sun = str(sc.raw.get("region", "")).lower() == "sun"
            spin = (sc.cam[0] if sc.raw.get("region") else 60) + t * (14 if is_sun else 9)
            gl = self.world.globe(spin, radius, sun=is_sun)
            # blue glow around the planet
            glow = Image.new("RGBA", (int(radius * 3.2), int(radius * 3.2)), (0, 0, 0, 0))
            gd = ImageDraw.Draw(glow)
            c = glow.width / 2
            for k in range(14, 0, -1):
                rr = radius * (1 + k * 0.022)
                col = (255, 150, 30) if is_sun else (80, 160, 255)
                gd.ellipse((c - rr, c - rr, c + rr, c + rr), fill=(*col, int((9 + (14 - k) * 4) * (2.2 if is_sun else 1))))
            glow = glow.filter(ImageFilter.GaussianBlur(radius / 18))
            _paste_scaled(frame, glow, W / 2, H * 0.47, grow)
            if sc.raw.get("orbit"):
                self._orbit(frame, t, radius * grow, back=True)
            _paste_scaled(frame, gl, W / 2, H * 0.47, grow)
            if sc.raw.get("orbit"):
                self._orbit(frame, t, radius * grow, back=False)
            return frame
        lon, lat, width = sc.camera(t)
        return self.world.view(lon, lat, width, self.size).convert("RGBA")

    def _orbit(self, frame: Image.Image, t: float, radius: float, back: bool) -> None:
        """A glowing orbit ring; the far half is drawn behind the planet."""
        W, H = self.size
        rx, ry = radius * 1.45, radius * 0.42
        cx, cy = W / 2, H * 0.47
        box = (cx - rx, cy - ry, cx + rx, cy + ry)
        start, end = (180, 360) if back else (0, 180)
        layer = Image.new("RGBA", self.size, (0, 0, 0, 0))
        d = ImageDraw.Draw(layer)
        d.arc(box, start, end, fill=(255, 200, 80, 220 if not back else 150), width=9)
        layer = layer.filter(ImageFilter.GaussianBlur(4))
        d = ImageDraw.Draw(layer)
        d.arc(box, start, end, fill=(255, 240, 190, 255 if not back else 170), width=3)
        a = (t * 1.6) % (2 * math.pi)
        on_back = math.sin(a) < 0
        if on_back == back:
            px, py = cx + rx * math.cos(a), cy + ry * math.sin(a)
            d.ellipse((px - 15, py - 15, px + 15, py + 15), fill=(255, 250, 225, 255))
        frame.alpha_composite(layer)

    def frame(self, sc: Scene, t: float, prev: Scene | None) -> Image.Image:
        W, H = self.size
        frame = self.background(sc, t)
        if prev is not None and prev.space != sc.space and t < 0.45:
            old = self.background(prev, prev.dur + t)
            frame = Image.blend(old, frame, _ease(t / 0.45))
        frame.alpha_composite(self.vignette)
        fade_out = 1 - _ease((t - (sc.dur - 0.22)) / 0.22)
        for ch, x, y, at, size in sc.icons:
            k = t - at
            if k < 0:
                continue
            s = _back(k / 0.35) * fade_out
            bob = math.sin((t + x * 7) * 2.2) * 9
            _paste_scaled(frame, emoji_image(ch, size), x * W, y * H + bob, s)
        if sc.number:
            pre, val, suf, dec, commas = parse_number(sc.number)
            k = (t - sc.count_at) / sc.count_len
            if k >= 0:
                shown = val * _out(k) if val else 0
                txt = pre + format_number(shown if k < 1 else val, dec, commas) + suf
                pop = 1 + 0.18 * math.sin(math.pi * min(max((k - 1) / 0.25, 0), 1))
                appear = _back(min(k * 2.5, 1))
                size = 175 if len(txt) <= 8 else int(175 * 8 / len(txt))
                _paste_scaled(frame, _text_img(txt, size), W / 2, H * 0.16, appear * pop * fade_out)
                if sc.label:
                    _paste_scaled(frame, _label_img(sc.label, 66), W / 2, H * 0.25,
                                  _back((k - 0.3) / 0.4) * fade_out)
        elif sc.label:
            _paste_scaled(frame, _label_img(sc.label, 78), W / 2, H * 0.17,
                          _back((t - sc.count_at) / 0.4) * fade_out)
        return frame


# ------------------------------------------------------------------- sound
def _env(n: int, attack: float, decay: float) -> np.ndarray:
    t = np.arange(n) / SR
    return np.minimum(t / max(attack, 1e-4), 1) * np.exp(-t / decay)


def make_sfx(kind: str, seed: int = 0) -> np.ndarray:
    rnd = np.random.default_rng(seed)
    if kind == "pop":
        n = int(SR * 0.16)
        t = np.arange(n) / SR
        f = 900 * (1 + rnd.uniform(-.15, .15)) * np.exp(-t * 18) + 220
        s = np.sin(2 * np.pi * np.cumsum(f) / SR) * _env(n, 0.002, 0.045)
        s += rnd.normal(0, 1, n) * _env(n, 0.0005, 0.006) * 0.4
        return s * 0.9
    if kind == "whoosh":
        n = int(SR * 0.6)
        noise = rnd.normal(0, 1, n)
        t = np.arange(n) / n
        env = np.sin(np.pi * t) ** 2.2
        out, y, k = np.zeros(n), 0.0, 0.0
        cut = 0.02 + 0.25 * np.sin(np.pi * t)          # sweeping low-pass
        for i in range(n):
            y += cut[i] * (noise[i] - y)
            k += cut[i] * (y - k)
            out[i] = k
        return out / (np.abs(out).max() + 1e-9) * env * 0.8
    if kind == "tick":
        n = int(SR * 0.03)
        t = np.arange(n) / SR
        return np.sin(2 * np.pi * 2400 * t) * _env(n, 0.0005, 0.006) * 0.5
    if kind == "ding":
        n = int(SR * 1.0)
        t = np.arange(n) / SR
        s = sum(a * np.sin(2 * np.pi * 1318.5 * m * t) * np.exp(-t * (3 + 2 * m))
                for a, m in [(1, 1), (.5, 2.01), (.25, 3.02), (.15, 4.1)])
        return s * _env(n, 0.002, 10) * 0.45
    if kind == "cash":
        a = make_sfx("ding", seed)
        n = int(SR * 0.12)
        b = rnd.normal(0, 1, n) * _env(n, 0.001, 0.03) * 0.35
        out = np.zeros(len(a) + int(SR * 0.09))
        out[:n] += b
        out[int(SR * 0.09):] += a * 0.8
        return out
    if kind in ("thunder", "boom"):
        n = int(SR * (1.6 if kind == "thunder" else 0.9))
        noise = rnd.normal(0, 1, n)
        out, y = np.zeros(n), 0.0
        for i in range(n):
            y += 0.03 * (noise[i] - y)
            out[i] = y
        out /= np.abs(out).max() + 1e-9
        crack = rnd.normal(0, 1, n) * _env(n, 0.001, 0.05) * 0.5
        return (out * _env(n, 0.01, 0.5 if kind == "thunder" else 0.25) + crack) * 0.9
    raise ValueError(kind)


@lru_cache(maxsize=64)
def _sfx_cached(kind: str, seed: int) -> np.ndarray:
    return make_sfx(kind, seed)


def build_sfx(scenes: list[Scene], total: float, out: Path, volume: float = 0.5) -> Path:
    track = np.zeros(int(SR * (total + 2)), np.float32)

    def add(kind: str, at: float, gain: float, seed: int = 0) -> None:
        s = _sfx_cached(kind, seed % 6).astype(np.float32) * gain
        i = int(at * SR)
        if 0 <= i < len(track):
            j = min(len(track), i + len(s))
            track[i:j] += s[:j - i]

    for sc in scenes:
        if sc.move or sc.i == 0:
            add("whoosh", sc.start, 0.55, sc.i)
        for k, (ch, *_rest) in enumerate(sc.icons):
            at = sc.start + sc.icons[k][3]
            kind = next((v for key, v in ICON_SFX.items() if key in ch), "pop")
            if kind == "pop" or k == 0:
                add(kind, at, 0.5 if kind == "pop" else 0.55, sc.i * 31 + k)
        if sc.number:
            t0 = sc.start + sc.count_at
            for m in range(int(sc.count_len / 0.07)):
                add("tick", t0 + m * 0.07, 0.25)
            add("ding", t0 + sc.count_len, 0.5)
    track *= volume
    peak = np.abs(track).max()
    if peak > 0.98:
        track *= 0.98 / peak
    pcm = (np.clip(track, -1, 1) * 32767).astype(np.int16)
    with wave.open(str(out), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())
    return out


# ------------------------------------------------------------------ render
def render_track(raw_scenes: list[dict], timings: list[tuple[float, float]], total: float,
                 size: tuple[int, int], fps: int, out_video: Path, out_sfx: Path,
                 sfx_volume: float = 0.5) -> None:
    """Draw the whole picture track (no audio) and the matching sound effects."""
    world = World()
    painter = Painter(world, size)
    scenes: list[Scene] = []
    prev_cam = None
    for i, (raw, (s, e)) in enumerate(zip(raw_scenes, timings)):
        sc = Scene(raw, s, e, i, prev_cam)
        scenes.append(sc)
        if not sc.space:
            prev_cam = sc.cam
    W, H = size
    enc = subprocess.Popen(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
         "-s", f"{W}x{H}", "-r", str(fps), "-i", "-", "-c:v", "libx264", "-preset", "veryfast",
         "-crf", "19", "-pix_fmt", "yuv420p", str(out_video)], stdin=subprocess.PIPE)
    n = int(math.ceil(total * fps))
    k = 0
    for f in range(n):
        t = f / fps
        while k + 1 < len(scenes) and t >= scenes[k + 1].start:
            k += 1
        sc = scenes[k]
        img = painter.frame(sc, t - sc.start, scenes[k - 1] if k else None)
        enc.stdin.write(img.convert("RGB").tobytes())
    enc.stdin.close()
    if enc.wait():
        raise RuntimeError("ffmpeg failed while encoding the motion track")
    build_sfx(scenes, total, out_sfx, sfx_volume)
    log(f"Drew {n} frames of map animation")
