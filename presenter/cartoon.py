"""An original cartoon presenter for MindBlip, drawn in code.

Lip sync comes from the voice itself (loudness) and the letters of the word being
said; the eyes blink, the head bobs, and the arms gesture on cue words (pointing
at the card, counting on fingers, waving at the end). Every hand has five digits.

CartoonHost has the same interface as HostVideo in build.py: .still and .next().
"""
from __future__ import annotations

import math
import random
import wave
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

HW, HH = 1080, 1350          # host picture size
S = 2                        # supersampling for clean edges
FPS = 30

INK = (38, 26, 22, 255)
SKIN = (205, 146, 104, 255)
SKIN_SH = (178, 120, 84, 255)
HAIR = (36, 26, 24, 255)
HAIR_HI = (70, 52, 46, 255)
SHIRT = (78, 116, 62, 255)
SHIRT_SH = (60, 92, 48, 255)
MOUTH = (92, 30, 34, 255)
TONGUE = (226, 110, 110, 255)
TEETH = (250, 248, 242, 255)
IRIS = (78, 48, 30, 255)
LINE = 7                     # outline width at 1x

SHOULDER_L = (345, 905)
SHOULDER_R = (735, 905)
UPPER, FORE = 195, 178
HEAD_C = (540, 545)
HEAD_SCALE = 1.25          # head centre in host coords
HEAD_BOX = (600, 720)        # head canvas size at 1x; head centre at (300, 340) in it


def _wav_rms(path: Path) -> np.ndarray:
    """Loudness per output frame, 0..1."""
    with wave.open(str(path)) as w:
        sr = w.getframerate()
        n = w.getnframes()
        ch = w.getnchannels()
        raw = np.frombuffer(w.readframes(n), dtype=np.int16).astype(np.float32)
    if ch > 1:
        raw = raw.reshape(-1, ch).mean(1)
    hop = sr // FPS
    frames = len(raw) // hop
    rms = np.array([np.sqrt(np.mean(raw[i * hop:(i + 1) * hop] ** 2) + 1e-9) for i in range(frames)])
    ref = np.percentile(rms, 95) or 1.0
    v = np.clip(rms / ref, 0, 1.2)
    v = np.where(v < 0.08, 0, v)
    # fast open, slower close
    out = np.zeros_like(v)
    for i, x in enumerate(v):
        prev = out[i - 1] if i else 0
        out[i] = x if x > prev else prev * 0.55 + x * 0.45
    return np.clip(out, 0, 1)


def _lerp(a, b, t):
    return a + (b - a) * t


def _ease(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


# ------------------------------------------------------------------ poses
# Each arm: (upper angle, forearm angle) in degrees from straight down,
# positive = away from the body, negative forearm = across the chest.
# Hand: extension of [thumb, index, middle, ring, pinky], 0 curled .. 1 straight.
OPEN = [1, 1, 1, 1, 1]
FIST = [0.25, 0.2, 0.2, 0.2, 0.2]
POINT = [0.3, 1, 0.15, 0.15, 0.15]
RELAX = [0.7, 0.75, 0.7, 0.65, 0.6]


def count_hand(n):
    h = [0.25, 0.15, 0.15, 0.15, 0.15]
    for i in range(1, 1 + min(n, 4)):
        h[i] = 1
    if n >= 5:
        h[0] = 1
    return h


POSES = {
    "rest": ((10, 6), RELAX),
    "talk_in": ((20, -118), RELAX),
    "talk_in2": ((16, -95), OPEN),
    "talk_out": ((22, 128), OPEN),
    "wide": ((34, 150), OPEN),
    "point_up": ((24, -172), POINT),
    "wave": ((26, -168), OPEN),
}


def pose(name, fingers=None):
    (u, f), hand = POSES[name]
    return [u, f, list(fingers if fingers is not None else hand)]


def mix(a, b, t):
    return [_lerp(a[0], b[0], t), _lerp(a[1], b[1], t), [_lerp(x, y, t) for x, y in zip(a[2], b[2])]]


class CartoonHost:
    def __init__(self, tl, voice16k: Path, words: list):
        self.tl = tl
        self.words = words
        self.rms = _wav_rms(voice16k)
        self.fi = 0
        self.bg = self._room()
        self.rng = random.Random(7)
        self.blinks = self._blink_plan(tl.total)
        self.plan = self._gesture_plan()
        self.still = self.render(0.0, quiet=True)

    # ------------------------------------------------------------ planning
    def _blink_plan(self, total):
        t, out = 0.8, []
        while t < total:
            out.append(t)
            t += self.rng.uniform(2.2, 4.4)
        return out

    def _gesture_plan(self):
        """List of (start, end, left_pose, right_pose, extra) segments."""
        segs = []
        tl = self.tl
        talk_cycle = [("rest", "talk_in"), ("talk_in", "talk_in2"), ("talk_in2", "rest"),
                      ("talk_out", "talk_in"), ("rest", "talk_out")]
        cue = {  # word -> (left, right, fingers for right, hold seconds)
            "meet": ("rest", "talk_out", OPEN, 1.3),
            "smartphone": ("talk_in2", "talk_in", None, 1.0),
            "seventy": ("wide", "wide", None, 1.6),
            "three": ("rest", "point_up", count_hand(3), 1.6),
            "crazier": ("wide", "wide", None, 1.4),
            "food": ("rest", "point_up", count_hand(1), 0.0),
            "water": ("rest", "point_up", count_hand(2), 0.0),
            "landing": ("rest", "point_up", count_hand(3), 1.2),
            "sun": ("rest", "point_up", count_hand(1), 0.0),
            "stars": ("rest", "point_up", count_hand(2), 0.0),
            "magnetic": ("rest", "point_up", count_hand(3), 1.6),
            "follow": ("rest", "wave", OPEN, 99),
        }
        for k, b in enumerate(tl.beats):
            # talking gestures that change every ~1.7 s
            t = b["start"]
            j = k
            while t < b["end"]:
                L, R = talk_cycle[j % len(talk_cycle)]
                segs.append((t, min(t + 1.7, b["end"]), pose(L), pose(R), 0, 0))
                t += 1.7
                j += 1
            # point at the card as it arrives
            if b["layout"] == "face" and b.get("card"):
                segs.append((b["start"] + 0.1, b["start"] + 1.2, pose("rest"), pose("point_up"), 1, 1))
        last_count_end = None
        for a, e, w in self.words:
            key = "".join(c for c in w.lower() if c.isalpha())
            if key in cue:
                L, R, fing, hold = cue[key]
                end = a + hold if hold else None
                segs.append((a - 0.15, end, pose(L), pose(R, fing), 1 if R == "point_up" else 0, 2))
                last_count_end = segs[-1]
        # counting holds until the next counted word or 1.2 s
        fixed = []
        for i, s in enumerate(segs):
            if s[1] is None:
                nxt = [x[0] for x in segs[i + 1:] if x[5] == 2]
                end = min(nxt) if nxt else s[0] + 1.2
                s = (s[0], end, s[2], s[3], s[4], s[5])
            fixed.append(s)
        fixed.sort(key=lambda s: s[0])
        return fixed

    def _target(self, t):
        cur = None
        for s in self.plan:
            if s[0] <= t < s[1] and (cur is None or (s[5], s[0]) >= (cur[5], cur[0])):
                cur = s          # cue words beat card points beat talking
        if cur is None:
            return pose("rest"), pose("rest"), 0, 0.0
        return cur[2], cur[3], cur[4], cur[0]

    # ------------------------------------------------------------ drawing
    def _room(self) -> Image.Image:
        w, h = HW, HH
        y = np.linspace(0, 1, h)[:, None]
        top = np.array([22, 58, 74])
        bot = np.array([10, 26, 38])
        grad = (top * (1 - y) + bot * y)[:, None, :].repeat(w, 1).reshape(h, w, 3)
        img = Image.fromarray(grad.astype(np.uint8)).convert("RGB")
        d = ImageDraw.Draw(img, "RGBA")
        # back wall panels
        for x in range(-40, w, 270):
            d.rounded_rectangle((x, 120, x + 240, 760), 26, fill=(255, 255, 255, 9))
        # shelf with books (left)
        d.rectangle((40, 430, 400, 446), fill=(120, 84, 56, 255))
        bx = 60
        cols = [(230, 120, 80), (90, 170, 210), (250, 200, 90), (150, 110, 190), (110, 190, 140), (235, 90, 110)]
        r = random.Random(3)
        while bx < 380:
            bw = r.randint(22, 38)
            bh = r.randint(90, 130)
            c = cols[r.randrange(len(cols))]
            d.rounded_rectangle((bx, 430 - bh, bx + bw, 430), 5, fill=c + (255,))
            bx += bw + 4
        # plant (right)
        d.rounded_rectangle((850, 600, 960, 720), 18, fill=(205, 120, 80, 255))
        for i in range(9):
            a = math.radians(-150 + i * 15)
            cx, cy = 905 + math.cos(a) * 95, 590 + math.sin(a) * 120
            d.ellipse((cx - 30, cy - 52, cx + 30, cy + 52), fill=(70, 160, 100, 255))
        # lamp glow and bokeh
        glow = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        g = ImageDraw.Draw(glow)
        g.ellipse((700, 60, 1080, 440), fill=(255, 190, 110, 90))
        g.ellipse((300, 380, 780, 860), fill=(120, 220, 255, 60))     # rim light behind the host
        for i in range(14):
            cx, cy, rr = r.randint(0, w), r.randint(80, 700), r.randint(14, 40)
            g.ellipse((cx - rr, cy - rr, cx + rr, cy + rr), fill=(255, 230, 170, 40))
        img = img.convert("RGBA")
        img.alpha_composite(glow.filter(ImageFilter.GaussianBlur(50)))
        # lightbulb sign (top left)
        d = ImageDraw.Draw(img, "RGBA")
        d.ellipse((120, 150, 230, 260), outline=(255, 214, 10, 255), width=8)
        d.rectangle((158, 258, 192, 290), outline=(255, 214, 10, 255), width=8)
        sign = img.crop((90, 120, 260, 320)).filter(ImageFilter.GaussianBlur(10))
        img.alpha_composite(sign, (90, 120))
        return img.filter(ImageFilter.GaussianBlur(2))

    @staticmethod
    def _cap(d, p, q, w, fill):
        d.line([p, q], fill=fill, width=int(w))
        r = w / 2
        for c in (p, q):
            d.ellipse((c[0] - r, c[1] - r, c[0] + r, c[1] + r), fill=fill)

    def _arm_points(self, side, arm, dx):
        sx, sy = SHOULDER_L if side < 0 else SHOULDER_R
        sx += dx
        u, f = math.radians(arm[0]), math.radians(arm[1])
        ex, ey = sx + side * math.sin(u) * UPPER, sy + math.cos(u) * UPPER
        wx, wy = ex + side * math.sin(f) * FORE, ey + math.cos(f) * FORE
        return (sx, sy), (ex, ey), (wx, wy)

    def _hand_shapes(self, side, wrist, elbow, fingers, wobble=0.0):
        """Capsules (p, q, width) for palm and five digits, in host coords."""
        ux, uy = wrist[0] - elbow[0], wrist[1] - elbow[1]
        n = math.hypot(ux, uy) or 1
        ux, uy = ux / n, uy / n
        a = math.radians(wobble)
        ux, uy = ux * math.cos(a) - uy * math.sin(a), ux * math.sin(a) + uy * math.cos(a)
        rx, ry = -uy, ux
        if uy > 0:            # hand pointing down: keep the thumb towards the body
            rx, ry = -rx, -ry
        th = -side            # thumb side in local x

        def P(x, y):
            return (wrist[0] + x * rx + y * ux, wrist[1] + x * ry + y * uy)

        caps = [(P(0, 10), P(0, 46), 70)]                     # palm
        base_x = [th * 25, th * 8, -th * 9, -th * 25]           # index..pinky
        lens = [54, 60, 55, 44]
        for i in range(4):
            e = fingers[i + 1]
            L = 12 + (lens[i] - 12) * e
            spread = (i - 1.5) * 4 * e
            bx, by = base_x[i], 66
            ang = math.radians(spread * -th)
            tx, ty = bx + math.sin(ang) * L, by + math.cos(ang) * L
            caps.append((P(bx, by), P(tx, ty), 17))
        e = fingers[0]
        L = 14 + 30 * e
        ang = math.radians(48 - 20 * (1 - e))
        bx, by = th * 30, 30
        caps.append((P(bx, by), P(bx + th * math.sin(ang) * L, by + math.cos(ang) * L), 19))
        return caps

    def _head(self, mouth_open, shape, blink, brow, look):
        cw, ch = HEAD_BOX[0] * S, HEAD_BOX[1] * S
        im = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        k = S
        cx, cy = 300, 340
        ol = LINE

        def E(box, fill, outline=True, w=ol):
            x0, y0, x1, y1 = box
            if outline:
                d.ellipse(((x0 - w) * k, (y0 - w) * k, (x1 + w) * k, (y1 + w) * k), fill=INK)
            d.ellipse((x0 * k, y0 * k, x1 * k, y1 * k), fill=fill)

        # hair behind
        E((cx - 168, cy - 230, cx + 168, cy + 60), HAIR)
        # ears
        for s in (-1, 1):
            E((cx + s * 152 - 26, cy - 10, cx + s * 152 + 26, cy + 66), SKIN)
            d.ellipse(((cx + s * 152 - 10) * k, (cy + 14) * k, (cx + s * 152 + 10) * k, (cy + 44) * k), fill=SKIN_SH)
        # face
        E((cx - 150, cy - 190, cx + 150, cy + 200), SKIN)
        # cheeks
        blush = Image.new("RGBA", im.size, (0, 0, 0, 0))
        bd = ImageDraw.Draw(blush)
        for s in (-1, 1):
            bd.ellipse(((cx + s * 92 - 34) * k, (cy + 62) * k, (cx + s * 92 + 34) * k, (cy + 96) * k), fill=(235, 120, 110, 45))
        im.alpha_composite(blush.filter(ImageFilter.GaussianBlur(10 * k)))
        d = ImageDraw.Draw(im)
        # hair front: a swept fringe
        fr = [(cx - 160, cy - 60), (cx - 150, cy - 170), (cx - 60, cy - 235), (cx + 60, cy - 240),
              (cx + 150, cy - 180), (cx + 165, cy - 70), (cx + 120, cy - 130), (cx + 40, cy - 120),
              (cx - 20, cy - 150), (cx - 70, cy - 120), (cx - 120, cy - 120)]
        d.polygon([((x) * k, (y) * k) for x, y in fr], fill=INK)
        fr2 = [(x + (6 if x < cx else -6), y + 7) for x, y in fr]
        d.polygon([(x * k, y * k) for x, y in fr2], fill=HAIR)
        d.line([((cx - 40) * k, (cy - 205) * k), ((cx + 70) * k, (cy - 215) * k)], fill=HAIR_HI, width=10 * k)
        # brows
        for s in (-1, 1):
            by = cy - 92 - brow * 14
            p = ((cx + s * 40) * k, (by + 4) * k)
            q = ((cx + s * 98) * k, (by - 4 + s * 0) * k)
            self._cap(d, p, q, 13 * k, HAIR)
        # eyes
        lx, ly = look
        for s in (-1, 1):
            ex, ey = cx + s * 64, cy - 34
            hgt = 29 * (1 - blink)
            if hgt < 5:
                d.arc(((ex - 28) * k, (ey - 10) * k, (ex + 28) * k, (ey + 12) * k), 10, 170, fill=INK, width=6 * k)
                continue
            E((ex - 26, ey - hgt, ex + 26, ey + hgt), (255, 255, 255, 255), w=5)
            ix, iy = ex + lx * 8, ey + ly * 9
            ir = min(22, hgt)
            d.ellipse(((ix - ir) * k, (iy - ir) * k, (ix + ir) * k, (iy + ir) * k), fill=IRIS)
            d.ellipse(((ix - 11) * k, (iy - 11) * k, (ix + 11) * k, (iy + 11) * k), fill=INK)
            d.ellipse(((ix + 3) * k, (iy - 10) * k, (ix + 10) * k, (iy - 3) * k), fill=(255, 255, 255, 255))
            # upper lid line
            lid = ey - hgt * 0.62
            d.chord(((ex - 31) * k, (ey - hgt - 7) * k, (ex + 31) * k, (lid + (lid - (ey - hgt - 7))) * k), 180, 360, fill=SKIN)
            d.arc(((ex - 29) * k, (lid - 6) * k, (ex + 29) * k, (lid + 10) * k), 190, 350, fill=INK, width=6 * k)
        # nose
        d.arc(((cx - 16) * k, (cy + 18) * k, (cx + 16) * k, (cy + 48) * k), 20, 160, fill=SKIN_SH, width=6 * k)
        # mouth
        mx, my = cx, cy + 112
        o = mouth_open
        if o < 0.08:
            d.arc(((mx - 44) * k, (my - 26) * k, (mx + 44) * k, (my + 14) * k), 25, 155, fill=INK, width=7 * k)
        else:
            wdt = {"wide": 52, "round": 30, "mid": 42}[shape]
            hgt = 8 + 44 * o * (1.15 if shape == "round" else 1.0)
            box = (mx - wdt, my - hgt * 0.45, mx + wdt, my + hgt * 0.75)
            d.ellipse(((box[0] - 6) * k, (box[1] - 6) * k, (box[2] + 6) * k, (box[3] + 6) * k), fill=INK)
            d.ellipse([v * k for v in box], fill=MOUTH)
            if hgt > 18:
                d.ellipse(((mx - wdt * 0.6) * k, (box[3] - hgt * 0.45) * k, (mx + wdt * 0.6) * k, (box[3] + 2) * k), fill=TONGUE)
            if o > 0.25:
                d.chord(((box[0] + 4) * k, (box[1] - 2) * k, (box[2] - 4) * k, (box[1] + hgt * 0.7) * k), 180, 360, fill=TEETH)
        return im

    def render(self, t: float, quiet: bool = False) -> Image.Image:
        fi = int(round(t * FPS))
        o = 0.0 if quiet else float(self.rms[min(fi, len(self.rms) - 1)]) if len(self.rms) else 0.0
        # mouth shape from the letters of the current word
        shape = "mid"
        for a, e, w in self.words:
            if a <= t < e:
                letters = [c for c in w.lower() if c.isalpha()] or ["a"]
                c = letters[min(len(letters) - 1, int((t - a) / max(e - a, 0.01) * len(letters)))]
                if c in "ouw":
                    shape = "round"
                elif c in "eiy":
                    shape = "wide"
                elif c in "mbp" and o < 0.5:
                    o *= 0.25
                break
        # blink
        blink = 0.0
        for b in self.blinks:
            if 0 <= t - b < 0.16:
                blink = 1 - abs((t - b) / 0.08 - 1)
        # arms: ease from the previous target to the current one
        L, R, look_up, seg_t = self._target(t)
        Lp, Rp, _, _ = self._target(max(0.0, seg_t - 0.02))
        mixv = _ease((t - seg_t) / 0.28)
        L = mix(Lp, L, mixv)
        R = mix(Rp, R, mixv)
        wob = 0.0
        if POSES["wave"][0] == (R[0], R[1]) or abs(R[1] + 168) < 1:
            wob = 18 * math.sin(t * 9)
        # gentle life
        sway = 7 * math.sin(t * 0.9)
        bob = -8 * o + 3 * math.sin(t * 1.7)
        tilt = 2.2 * math.sin(t * 0.7) + (3 if look_up else 0)
        brow = min(1.0, o * 0.8) * 0.6 + (0.5 if look_up else 0)
        look = (0.6 * math.sin(t * 0.37), -1.0 if look_up else 0.15 * math.sin(t * 0.5))

        canvas = Image.new("RGBA", (HW * S, HH * S), (0, 0, 0, 0))
        d = ImageDraw.Draw(canvas)
        k = S
        # torso
        tx = sway * 0.6
        body = [(262, 1360), (282, 965), (330, 888), (470, 852), (610, 852), (750, 888), (798, 965), (818, 1360)]
        d.polygon([((x + tx) * k, y * k) for x, y in body], fill=INK)
        body_in = [(274, 1360), (294, 968), (338, 900), (472, 864), (608, 864), (742, 900), (786, 968), (806, 1360)]
        d.polygon([((x + tx) * k, y * k) for x, y in body_in], fill=SHIRT)
        d.polygon([((x + tx) * k, y * k) for x, y in [(560, 1360), (600, 1010), (690, 960), (786, 968), (806, 1360)]],
                  fill=SHIRT_SH)
        # neck
        nx = 540 + tx * 0.8
        d.rounded_rectangle(((nx - 46) * k, 700 * k, (nx + 46) * k, 880 * k), 20 * k, fill=INK)
        d.rounded_rectangle(((nx - 39) * k, 700 * k, (nx + 39) * k, 876 * k), 18 * k, fill=SKIN_SH)
        # collar
        d.chord(((nx - 74) * k, 818 * k, (nx + 74) * k, 902 * k), 0, 180, fill=INK)
        d.chord(((nx - 62) * k, 824 * k, (nx + 62) * k, 890 * k), 0, 180, fill=SKIN_SH)
        d.arc(((nx - 76) * k, 816 * k, (nx + 76) * k, 906 * k), 0, 180, fill=SHIRT_SH, width=12 * k)

        # head
        head = self._head(o, shape, blink, brow, look)
        head = head.resize((int(head.width * HEAD_SCALE), int(head.height * HEAD_SCALE)), Image.BICUBIC)
        head = head.rotate(tilt, resample=Image.BICUBIC, center=(300 * k * HEAD_SCALE, 420 * k * HEAD_SCALE))
        hx = int((HEAD_C[0] - 300 * HEAD_SCALE + sway) * k)
        hy = int((HEAD_C[1] - 340 * HEAD_SCALE + bob) * k)
        canvas.alpha_composite(head, (hx, hy))

        # arms: outlines, fills, sleeves
        d = ImageDraw.Draw(canvas)
        arms = []
        for side, arm in ((-1, L), (1, R)):
            sh, el, wr = self._arm_points(side, arm, tx)
            hand = self._hand_shapes(side, wr, el, arm[2], wob if side > 0 else 0)
            arms.append((sh, el, wr, hand))
        ow = LINE * 2
        for sh, el, wr, hand in arms:
            self._cap(d, (sh[0] * k, sh[1] * k), (el[0] * k, el[1] * k), (62 + ow) * k, INK)
            self._cap(d, (el[0] * k, el[1] * k), (wr[0] * k, wr[1] * k), (54 + ow) * k, INK)
            for p, q, w in hand:
                self._cap(d, (p[0] * k, p[1] * k), (q[0] * k, q[1] * k), (w + ow) * k, INK)
        for sh, el, wr, hand in arms:
            self._cap(d, (sh[0] * k, sh[1] * k), (el[0] * k, el[1] * k), 62 * k, SKIN)
            self._cap(d, (el[0] * k, el[1] * k), (wr[0] * k, wr[1] * k), 54 * k, SKIN)
            for p, q, w in hand:
                self._cap(d, (p[0] * k, p[1] * k), (q[0] * k, q[1] * k), w * k, SKIN)
            # finger gaps
            for p, q, w in hand[1:5]:
                pass
        for sh, el, wr, hand in arms:
            ux, uy = el[0] - sh[0], el[1] - sh[1]
            n = math.hypot(ux, uy) or 1
            se = (sh[0] + ux / n * 100, sh[1] + uy / n * 100)
            self._cap(d, (sh[0] * k, sh[1] * k), (se[0] * k, se[1] * k), (84 + ow) * k, INK)
            self._cap(d, (sh[0] * k, sh[1] * k), (se[0] * k, se[1] * k), 84 * k, SHIRT)

        layer = canvas.resize((HW, HH), Image.LANCZOS)
        out = self.bg.copy()
        # soft shadow of the host on the wall
        sh = Image.new("RGBA", (HW, HH), (0, 0, 0, 0))
        sh.paste((0, 0, 0, 90), (0, 0), layer.getchannel("A"))
        out.alpha_composite(sh.filter(ImageFilter.GaussianBlur(18)), (14, 10))
        out.alpha_composite(layer)
        return out.convert("RGB")

    def next(self) -> Image.Image:
        img = self.render(self.fi / FPS)
        self.fi += 1
        return img
