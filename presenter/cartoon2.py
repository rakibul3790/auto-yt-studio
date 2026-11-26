"""Blip, the MindBlip presenter (v2): an original cartoon host drawn with cairo.

Clean ink outlines, cel shading and a rim light; the mouth follows the voice, the face
follows the mood tags of the script (curious, excited, sigh, whisper, laugh, serious) and
the hands follow cue words. Every frame is a pure function of time, so frames can be drawn
in parallel. The canvas is transparent: the compositor places Blip anywhere.
"""
from __future__ import annotations

import math
import wave

import cairo
import numpy as np
from PIL import Image

CW, CH = 1000, 1300                 # canvas (transparent)
FPS = 30
INK = (0.10, 0.08, 0.12)
SKIN = (0.80, 0.56, 0.40)
SKIN_SH = (0.66, 0.42, 0.29)
HAIR = (0.13, 0.10, 0.12)
HOOD = (0.11, 0.62, 0.62)
HOOD_SH = (0.06, 0.45, 0.48)
HOOD_LT = (0.45, 0.85, 0.82)
MUSTARD = (1.0, 0.76, 0.18)
WHITE = (1, 1, 1)
IRIS = (0.30, 0.17, 0.08)
MOUTH = (0.36, 0.08, 0.10)
TONGUE = (0.93, 0.42, 0.42)
LW = 7.0                            # outline width

HEAD = (500, 480)                   # head centre at rest
HEAD_R = 215
SHOULDER_L, SHOULDER_R = (285, 815), (715, 815)
UPPER, FORE = 175, 165


def ease(t: float) -> float:
    t = min(max(t, 0.0), 1.0)
    return t * t * (3 - 2 * t)


def lerp(a, b, t):
    if isinstance(a, (tuple, list)):
        return tuple(x + (y - x) * t for x, y in zip(a, b))
    return a + (b - a) * t


# ------------------------------------------------------------------ audio
def wav_rms(path) -> np.ndarray:
    with wave.open(str(path)) as w:
        sr = w.getframerate()
        a = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768
        if w.getnchannels() > 1:
            a = a.reshape(-1, w.getnchannels()).mean(1)
    hop = sr // FPS
    n = len(a) // hop
    r = np.sqrt((a[: n * hop].reshape(n, hop) ** 2).mean(1))
    r = r / (np.percentile(r, 95) + 1e-6)
    out = np.zeros_like(r)
    v = 0.0
    for i, x in enumerate(r):           # fast attack, slower release
        v = x if x > v else v * 0.55 + x * 0.45
        out[i] = v
    return np.clip(out, 0, 1.2)


# ------------------------------------------------------------------ poses
# A pose: hand target (x, y) for each arm, hand shape, hand angle (deg, 0 = fingers up)
POSES = {
    "rest":     {"L": ((225, 1150), "relax", 190), "R": ((775, 1150), "relax", 170)},
    "talk":     {"L": ((380, 1000), "open", 150), "R": ((640, 1010), "open", 215)},
    "talk2":    {"L": ((300, 1040), "open", 205), "R": ((700, 1000), "relax", 160)},
    "point_up": {"L": ((225, 1150), "relax", 190), "R": ((770, 640), "point", 25)},
    "point_side": {"L": ((150, 760), "point", -60), "R": ((775, 1150), "relax", 170)},
    "present":  {"L": ((170, 900), "open", -40), "R": ((830, 900), "open", 40)},
    "shrug":    {"L": ((190, 860), "open", -75), "R": ((810, 860), "open", 75)},
    "whisper":  {"L": ((225, 1150), "relax", 190), "R": ((612, 620), "cup", -35)},
    "laugh":    {"L": ((390, 1070), "fist", 120), "R": ((610, 1070), "fist", 240)},
    "think":    {"L": ((225, 1150), "relax", 190), "R": ((590, 690), "point", -15)},
    "count1":   {"L": ((225, 1150), "relax", 190), "R": ((760, 700), "count1", 8)},
    "count2":   {"L": ((225, 1150), "relax", 190), "R": ((760, 700), "count2", 8)},
    "count3":   {"L": ((225, 1150), "relax", 190), "R": ((760, 700), "count3", 8)},
    "wow":      {"L": ((230, 760), "open", -30), "R": ((770, 760), "open", 30)},
    "fist_up":  {"L": ((225, 1150), "relax", 190), "R": ((760, 650), "fist", 10)},
}


class Blip:
    """plan: list of (start, end, pose, prio); moods: list of (start, end, mood)."""

    def __init__(self, rms: np.ndarray, words: list, plan: list, moods: list, emph: list[float]):
        self.rms = rms
        self.words = words
        self.plan = sorted(plan, key=lambda s: s[0])
        self.moods = moods
        self.emph = emph                    # times of emphasis hits (little bounce)

    # ---------------------------------------------------------------- timing
    def pose_at(self, t: float) -> str:
        best, key = "rest", (-1, -1)
        for a, b, p, pr in self.plan:
            if a <= t < b and (pr, a) > key:
                best, key = p, (pr, a)
        return best

    def _pose_start(self, t: float) -> tuple[str, str, float]:
        """current pose, previous pose and when the switch happened."""
        cur = self.pose_at(t)
        # walk back to the switch
        step = 1 / FPS
        s = t
        while s > 0 and self.pose_at(s - step) == cur and t - s < 3:
            s -= step
        prev = self.pose_at(s - step) if s > 0 else "rest"
        return cur, prev, s

    def mood_at(self, t: float) -> tuple[str, float]:
        for a, b, m in self.moods:
            if a <= t < b:
                return m, min(1.0, (t - a) / 0.25, (b - t) / 0.25 + 0.0001)
        return "neutral", 1.0

    def word_at(self, t: float) -> str:
        for a, b, w in self.words:
            if a - 0.03 <= t <= b + 0.02:
                return w.lower()
        return ""

    def energy(self, t: float) -> float:
        i = int(t * FPS)
        return float(self.rms[i]) if 0 <= i < len(self.rms) else 0.0

    # ---------------------------------------------------------------- render
    def render(self, t: float) -> Image.Image:
        surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, CW, CH)
        c = cairo.Context(surf)
        c.set_line_join(cairo.LINE_JOIN_ROUND)
        c.set_line_cap(cairo.LINE_CAP_ROUND)

        mood, mk = self.mood_at(t)
        e = self.energy(t)
        cur, prev, ps = self._pose_start(t)
        k = ease((t - ps) / 0.3)
        pa, pb = POSES[prev], POSES[cur]

        # body motion
        bounce = 0.0
        for h in self.emph:
            d = t - h
            if 0 <= d < 0.45:
                bounce = max(bounce, math.sin(d / 0.45 * math.pi) * (1 - d / 0.45))
        laugh = mood == "laugh"
        sway = 10 * math.sin(t * 1.3) + (6 * math.sin(t * 17) * mk if laugh else 0)
        bob = -8 * e - 22 * bounce + (5 * abs(math.sin(t * 9)) * mk if laugh else 0)
        lean = {"whisper": 14, "curious": 6, "sigh": -4}.get(mood, 0) * mk
        tilt = 3.5 * math.sin(t * 0.9) + {"curious": 7, "whisper": 9, "laugh": -5, "sigh": -6}.get(mood, 0) * mk
        squash = 1 + 0.035 * bounce

        c.save()
        c.translate(CW / 2, CH)
        c.scale(1 / squash, squash)
        c.translate(-CW / 2, -CH)
        c.translate(sway * 0.5, 0)
        self._torso(c, bob * 0.4)
        # arms behind the head only when low; draw arms after torso
        hx, hy = HEAD[0] + sway * 0.6 + lean, HEAD[1] + bob + lean * 0.6
        late = []
        for side in ("L", "R"):
            (ta, sa, aa), (tb, sb, ab) = pa[side], pb[side]
            tx, ty = lerp(ta, tb, k)
            ang = lerp(aa, ab, k)
            shape = sb if k > 0.5 else sa
            if cur == "laugh":
                ty += 10 * math.sin(t * 17)
            if shape in ("open", "relax") and cur in ("talk", "talk2"):
                tx += 10 * math.sin(t * 3.1 + (0 if side == "L" else 1.7)) * (0.4 + e)
                ty += 14 * math.sin(t * 2.3 + (0 if side == "L" else 2.2)) * (0.4 + e)
            if ty < 720 and 380 < tx < 650:
                late.append((side, (tx + sway * 0.5 + lean, ty + bob * 0.8), shape, ang))
            else:
                self._arm(c, side, (tx, ty + bob * 0.3), shape, ang)
        self._head(c, hx, hy, tilt, mood, mk, e, t)
        for args in late:
            self._arm(c, *args)
        c.restore()
        surf.flush()
        buf = np.ndarray((CH, CW, 4), np.uint8, surf.get_data())
        rgba = buf[..., [2, 1, 0, 3]].astype(np.float32)
        a = rgba[..., 3:4] / 255.0
        rgba[..., :3] = np.where(a > 0, rgba[..., :3] / np.maximum(a, 1e-3), 0)
        return Image.fromarray(np.clip(rgba, 0, 255).astype(np.uint8), "RGBA")

    # ---------------------------------------------------------------- parts
    def _fill_stroke(self, c, fill, lw=LW):
        c.set_source_rgb(*fill)
        c.fill_preserve()
        c.set_source_rgb(*INK)
        c.set_line_width(lw)
        c.stroke()

    def _torso(self, c, dy):
        c.save()
        c.translate(0, dy)
        # hoodie body
        c.move_to(215, CH + 20)
        c.curve_to(212, 1000, 222, 860, 300, 790)
        c.curve_to(380, 752, 620, 752, 700, 790)
        c.curve_to(778, 860, 788, 1000, 785, CH + 20)
        c.close_path()
        path = c.copy_path()
        self._fill_stroke(c, HOOD)
        # cel shadow on the right side
        c.save()
        c.append_path(path)
        c.clip()
        c.move_to(610, 760)
        c.curve_to(680, 900, 660, 1120, 690, CH + 30)
        c.line_to(900, CH + 30)
        c.line_to(900, 740)
        c.close_path()
        c.set_source_rgba(*HOOD_SH, 0.85)
        c.fill()
        c.restore()
        # hood collar behind the neck
        c.move_to(345, 778)
        c.curve_to(380, 700, 620, 700, 655, 778)
        c.curve_to(600, 818, 400, 818, 345, 778)
        c.close_path()
        self._fill_stroke(c, HOOD_SH)
        # neck
        c.move_to(447, 680)
        c.line_to(442, 772)
        c.curve_to(470, 796, 530, 796, 558, 772)
        c.line_to(553, 680)
        c.close_path()
        self._fill_stroke(c, SKIN_SH)
        # drawstrings + mustard tips
        for x0, x1 in ((455, 445), (545, 555)):
            c.set_source_rgb(*WHITE)
            c.set_line_width(9)
            c.move_to(x0, 796)
            c.curve_to(x0 - 4, 860, x1, 900, x1, 945)
            c.stroke()
            c.arc(x1, 955, 11, 0, 2 * math.pi)
            self._fill_stroke(c, MUSTARD, 5)
        # front pocket
        c.move_to(380, 1170)
        c.curve_to(420, 1120, 580, 1120, 620, 1170)
        c.line_to(640, CH + 10)
        c.line_to(360, CH + 10)
        c.close_path()
        c.set_source_rgba(*HOOD_SH, 0.6)
        c.fill_preserve()
        c.set_source_rgb(*INK)
        c.set_line_width(5)
        c.stroke()
        # tiny logo: a "blip" bolt
        c.move_to(700, 980)
        c.line_to(684, 1012)
        c.line_to(698, 1012)
        c.line_to(688, 1040)
        c.line_to(716, 1002)
        c.line_to(702, 1002)
        c.close_path()
        self._fill_stroke(c, MUSTARD, 4)
        c.restore()

    def _arm(self, c, side, target, shape, ang):
        sx, sy = SHOULDER_L if side == "L" else SHOULDER_R
        tx, ty = target
        dx, dy = tx - sx, ty - sy
        d = min(math.hypot(dx, dy), UPPER + FORE - 2)
        base = math.atan2(dy, dx)
        cos_e = (UPPER ** 2 + d ** 2 - FORE ** 2) / (2 * UPPER * d)
        off = math.acos(max(-1, min(1, cos_e)))
        # elbows bend outwards
        a1 = base + (off if side == "L" else -off) * (1 if dy > 0 else -1) * (1 if side == "L" else 1)
        a1 = base - off if side == "R" else base + off
        if dy < -40:      # raised arm: elbow goes down/outwards
            a1 = base + off if side == "R" else base - off
        ex, ey = sx + UPPER * math.cos(a1), sy + UPPER * math.sin(a1)
        hx, hy = sx + d * math.cos(base), sy + d * math.sin(base)
        # sleeve: thick ink capsule then fill
        for w, col in ((86 + 2 * LW, INK), (86, HOOD)):
            c.set_source_rgb(*col)
            c.set_line_width(w)
            c.move_to(sx, sy)
            c.line_to(ex, ey)
            c.line_to(lerp(ex, hx, 0.62), lerp(ey, hy, 0.62))
            c.stroke()
        # shading stripe
        c.set_source_rgba(*HOOD_SH, 0.7)
        c.set_line_width(24)
        c.move_to(sx + 18, sy + 10)
        c.line_to(ex + 18, ey + 10)
        c.stroke()
        # cuff
        cx, cy = lerp(ex, hx, 0.62), lerp(ey, hy, 0.62)
        c.set_source_rgb(*INK)
        c.set_line_width(96)
        c.move_to(cx, cy)
        c.line_to(cx + 0.01, cy)
        c.stroke()
        c.set_source_rgb(*HOOD_SH)
        c.set_line_width(82)
        c.move_to(cx, cy)
        c.line_to(cx + 0.01, cy)
        c.stroke()
        # wrist
        c.set_source_rgb(*INK)
        c.set_line_width(44 + 2 * LW)
        c.move_to(cx, cy)
        c.line_to(hx, hy)
        c.stroke()
        c.set_source_rgb(*SKIN)
        c.set_line_width(44)
        c.move_to(cx, cy)
        c.line_to(hx, hy)
        c.stroke()
        self._hand(c, hx, hy, shape, ang, side)

    def _hand(self, c, x, y, shape, ang, side):
        c.save()
        c.translate(x, y)
        c.rotate(math.radians(ang))
        mirror = -1 if side == "L" else 1
        c.scale(mirror, 1)
        # fingers: (base x, length, angle) ; palm at origin, fingers point -y
        ext = {"open": [1, 1, 1, 1], "relax": [0.75, 0.8, 0.8, 0.7], "point": [1, 0, 0, 0],
               "fist": [0, 0, 0, 0], "cup": [0.85, 0.9, 0.9, 0.85],
               "count1": [1, 0, 0, 0], "count2": [1, 1, 0, 0], "count3": [1, 1, 1, 0]}[shape]
        thumb_out = shape in ("open", "relax", "cup")
        spread = {"open": 10, "count2": 13, "count3": 12}.get(shape, 4)
        lens = [58, 64, 60, 50]
        xs = [-26, -9, 9, 25]
        # palm
        c.new_path()
        c.move_to(-36, -18)
        c.curve_to(-40, 30, -20, 46, 0, 46)
        c.curve_to(26, 46, 40, 30, 36, -18)
        c.curve_to(30, -40, -30, -40, -36, -18)
        c.close_path()
        palm = c.copy_path()
        # fingers (ink pass then fill pass, so joins are clean)
        segs = []
        for i in range(4):
            L = lens[i] * ext[i]
            a = math.radians((i - 1.5) * spread)
            bx, by = xs[i], -28
            if L < 8:
                segs.append(((bx, by), (bx * 0.9, by - 6), 21))
            else:
                segs.append(((bx, by), (bx + math.sin(a) * L, by - math.cos(a) * L), 21))
        th0 = (-34, 8)
        th1 = (-70, -22) if thumb_out else (-14, -12)
        if shape in ("count1", "count2", "count3", "point"):
            th1 = (-20, -14)
        for wpass, col in ((2 * LW, INK), (0, SKIN)):
            c.set_source_rgb(*col)
            for (ax, ay), (bx2, by2), w in segs + [(th0, th1, 23)]:
                c.set_line_width(w + wpass)
                c.move_to(ax, ay)
                c.line_to(bx2, by2)
                c.stroke()
            c.append_path(palm)
            if wpass:
                c.set_line_width(2 * LW)
                c.stroke_preserve()
            c.fill()
        # lines between bent fingers so the hand never reads as a mitten
        c.set_source_rgba(*INK, 0.8)
        c.set_line_width(3.5)
        for i in range(3):
            if ext[i] < 0.5 or ext[i + 1] < 0.5:
                mx = (xs[i] + xs[i + 1]) / 2
                c.move_to(mx, -30)
                c.line_to(mx, -12)
                c.stroke()
        # knuckle shading
        c.set_source_rgba(*SKIN_SH, 0.55)
        c.arc(14, 18, 20, 0, math.pi)
        c.fill()
        c.restore()

    def _head(self, c, x, y, tilt, mood, mk, e, t):
        c.save()
        c.translate(x, y)
        c.rotate(math.radians(tilt))
        R = HEAD_R
        # back hair
        c.new_path()
        c.arc(0, -20, R * 1.02, math.pi * 0.95, math.pi * 2.05)
        c.close_path()
        self._fill_stroke(c, HAIR)
        # ears
        for sx in (-1, 1):
            c.save()
            c.translate(sx * R * 0.93, 20)
            c.scale(0.55, 0.75)
            c.arc(0, 0, 60, 0, 2 * math.pi)
            c.restore()
            self._fill_stroke(c, SKIN)
            c.save()
            c.translate(sx * R * 0.95, 22)
            c.scale(0.25, 0.42)
            c.arc(0, 0, 60, 0, 2 * math.pi)
            c.restore()
            c.set_source_rgb(*SKIN_SH)
            c.fill()
        # face: slightly squarish jaw
        c.new_path()
        c.move_to(-R * 0.95, -40)
        c.curve_to(-R * 0.98, R * 0.55, -R * 0.55, R * 0.98, 0, R * 1.0)
        c.curve_to(R * 0.55, R * 0.98, R * 0.98, R * 0.55, R * 0.95, -40)
        c.curve_to(R * 0.9, -R * 1.05, -R * 0.9, -R * 1.05, -R * 0.95, -40)
        c.close_path()
        face = c.copy_path()
        self._fill_stroke(c, SKIN)
        # cel shadow + cheek blush
        c.save()
        c.append_path(face)
        c.clip()
        c.move_to(R * 0.35, -R)
        c.curve_to(R * 0.75, -R * 0.2, R * 0.7, R * 0.6, R * 0.2, R * 1.1)
        c.line_to(R * 1.2, R * 1.2)
        c.line_to(R * 1.2, -R)
        c.close_path()
        c.set_source_rgba(*SKIN_SH, 0.45)
        c.fill()
        blush = 0.32 + (0.25 if mood in ("laugh", "excited") else 0) * mk
        for sx in (-1, 1):
            g = cairo.RadialGradient(sx * R * 0.55, R * 0.38, 0, sx * R * 0.55, R * 0.38, 58)
            g.add_color_stop_rgba(0, 0.95, 0.40, 0.40, blush)
            g.add_color_stop_rgba(1, 0.95, 0.40, 0.40, 0)
            c.set_source(g)
            c.paint()
        c.restore()
        # front hair: a swoop
        c.new_path()
        c.move_to(-R * 0.98, -30)
        c.curve_to(-R * 1.05, -R * 0.9, -R * 0.4, -R * 1.25, R * 0.3, -R * 1.12)
        c.curve_to(R * 0.95, -R * 1.0, R * 1.08, -R * 0.45, R * 0.97, -10)
        c.curve_to(R * 0.85, -R * 0.45, R * 0.55, -R * 0.62, R * 0.2, -R * 0.58)
        c.curve_to(-R * 0.1, -R * 0.55, -R * 0.35, -R * 0.75, -R * 0.45, -R * 0.62)
        c.curve_to(-R * 0.6, -R * 0.4, -R * 0.85, -R * 0.35, -R * 0.98, -30)
        c.close_path()
        self._fill_stroke(c, HAIR)
        c.set_source_rgba(1, 1, 1, 0.16)
        c.set_line_width(16)
        c.move_to(-R * 0.55, -R * 0.95)
        c.curve_to(-R * 0.2, -R * 1.08, R * 0.25, -R * 1.06, R * 0.55, -R * 0.92)
        c.stroke()

        # ---- eyes
        blink = 0.0
        for ph in (1.3, 3.9, 6.1):
            d = (t + ph) % 4.3
            if d < 0.14:
                blink = math.sin(d / 0.14 * math.pi)
        open_ = {"neutral": 1.0, "curious": 1.05, "excited": 1.18, "sigh": 0.55, "whisper": 0.62,
                 "laugh": 0.0, "serious": 0.82}.get(mood, 1.0)
        open_ = lerp(1.0, open_, mk) * (1 - blink)
        look = (8 * math.sin(t * 0.7), 4 * math.sin(t * 0.5))
        if mood == "whisper":
            look = (16, -2)
        ey = -R * 0.08
        for sx in (-1, 1):
            ex = sx * R * 0.38
            rw, rh = 50, 58
            if open_ < 0.12:          # closed: happy arc for laugh, line for blink
                c.new_path()
                if mood == "laugh":
                    c.move_to(ex - 38, ey + 8)
                    c.curve_to(ex - 20, ey - 26, ex + 20, ey - 26, ex + 38, ey + 8)
                else:
                    c.move_to(ex - 38, ey + 4)
                    c.curve_to(ex - 15, ey + 14, ex + 15, ey + 14, ex + 38, ey + 4)
                c.set_source_rgb(*INK)
                c.set_line_width(10)
                c.stroke()
                continue
            c.save()
            c.translate(ex, ey)
            c.scale(1, max(open_, 0.12))
            c.arc(0, 0, rw, 0, 2 * math.pi)
            c.restore()
            eye = c.copy_path()
            self._fill_stroke(c, WHITE, 6)
            c.save()
            c.append_path(eye)
            c.clip()
            ix, iy = ex + look[0], ey + look[1]
            g = cairo.RadialGradient(ix, iy - 8, 4, ix, iy, 32)
            g.add_color_stop_rgb(0, 0.55, 0.33, 0.15)
            g.add_color_stop_rgb(1, *IRIS)
            c.set_source(g)
            c.arc(ix, iy, 32, 0, 2 * math.pi)
            c.fill()
            c.set_source_rgb(0.05, 0.03, 0.04)
            c.arc(ix, iy, 16, 0, 2 * math.pi)
            c.fill()
            c.set_source_rgb(1, 1, 1)
            c.arc(ix + 11, iy - 13, 9, 0, 2 * math.pi)
            c.fill()
            c.arc(ix - 10, iy + 10, 4, 0, 2 * math.pi)
            c.fill()
            # upper lid shadow
            c.set_source_rgba(*SKIN_SH, 0.35)
            c.rectangle(ex - rw, ey - rh * open_, 2 * rw, 14)
            c.fill()
            c.restore()
            # lashes line on top
            c.new_path()
            c.save()
            c.translate(ex, ey)
            c.scale(1, max(open_, 0.12))
            c.arc(0, 0, rw, math.pi * 1.08, math.pi * 1.92)
            c.restore()
            c.set_source_rgb(*INK)
            c.set_line_width(11)
            c.stroke()
        # ---- brows
        lift = {"curious": (18, -10), "excited": (22, 22), "sigh": (-8, -8), "whisper": (6, -14),
                "laugh": (14, 14), "serious": (-12, -12), "neutral": (6, 6)}.get(mood, (6, 6))
        lift = (lift[0] * mk + 6 * (1 - mk), lift[1] * mk + 6 * (1 - mk))
        talk_lift = 8 * e
        for i, sx in enumerate((-1, 1)):
            bx = sx * R * 0.38
            by = ey - 78 - lift[i] - talk_lift
            inner = 10 if mood == "serious" else (-10 if mood == "sigh" else 0)
            c.new_path()
            c.move_to(bx - sx * 42, by + inner * mk)
            c.curve_to(bx - sx * 10, by - 16, bx + sx * 20, by - 14, bx + sx * 44, by + 6)
            c.set_source_rgb(*HAIR)
            c.set_line_width(17)
            c.stroke()
        # ---- nose
        c.new_path()
        c.move_to(-6, R * 0.12)
        c.curve_to(-16, R * 0.28, 4, R * 0.33, 16, R * 0.27)
        c.set_source_rgb(*SKIN_SH)
        c.set_line_width(7)
        c.stroke()

        # ---- mouth
        word = self.word_at(t)
        op = min(1.0, e * 1.15) if word else 0.0
        if mood == "whisper":
            op *= 0.6
        my = R * 0.55
        shape = "mid"
        if word:
            core = word.strip(".,?!:")
            mid = core[len(core) // 2] if core else "a"
            if any(ch in core[:2] for ch in "mbp") and op < 0.5:
                shape = "closed"
            elif mid in "ouw":
                shape = "round"
            elif mid in "eiy":
                shape = "wide"
        if mood == "laugh":
            op = max(op, 0.55 + 0.25 * abs(math.sin(t * 9)) * mk)
            shape = "grin"
        smile = {"excited": 1.0, "laugh": 1.0, "curious": 0.45, "sigh": -0.25, "serious": 0.0,
                 "whisper": 0.3, "neutral": 0.6}.get(mood, 0.6) * mk + 0.6 * (1 - mk)
        if op < 0.08 or shape == "closed":
            c.new_path()
            w = 62
            c.move_to(-w, my - 4)
            c.curve_to(-w * 0.4, my + 26 * smile, w * 0.4, my + 26 * smile, w, my - 4)
            c.set_source_rgb(*INK)
            c.set_line_width(9)
            c.stroke()
        else:
            w = {"round": 38, "wide": 70, "mid": 56, "grin": 80}[shape]
            h = {"round": 62, "wide": 34, "mid": 50, "grin": 58}[shape] * (0.35 + 0.75 * op)
            c.new_path()
            top = my - 6 + (-8 * smile if shape != "round" else 0)
            if shape == "round":
                c.save()
                c.translate(0, my + h * 0.3)
                c.scale(w / 50, h / 50)
                c.arc(0, 0, 50, 0, 2 * math.pi)
                c.restore()
            else:
                c.move_to(-w, top)
                c.curve_to(-w * 0.5, top - 6 * smile, w * 0.5, top - 6 * smile, w, top)
                c.curve_to(w * 0.8, top + h * 1.2, -w * 0.8, top + h * 1.2, -w, top)
                c.close_path()
            m = c.copy_path()
            self._fill_stroke(c, MOUTH, 8)
            c.save()
            c.append_path(m)
            c.clip()
            c.set_source_rgb(1, 1, 1)                     # upper teeth
            c.rectangle(-w, top - 40, 2 * w, 40 + h * 0.28)
            c.fill()
            c.set_source_rgb(*TONGUE)
            c.arc(0, top + h * 1.15, w * 0.55, 0, 2 * math.pi)
            c.fill()
            c.restore()
            c.append_path(m)
            c.set_source_rgb(*INK)
            c.set_line_width(8)
            c.stroke()
        if mood == "sigh" and mk > 0.5 and op < 0.1:       # a little puff of air
            c.set_source_rgba(1, 1, 1, 0.5 * mk)
            c.arc(R * 0.35, my + 10, 10, 0, 2 * math.pi)
            c.fill()
        c.restore()
