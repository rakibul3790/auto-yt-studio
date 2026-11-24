"""Pictures for each scene, and the thumbnail.

- With a free PEXELS_API_KEY or PIXABAY_API_KEY secret, each scene's English
  "visual" hint is searched on Pexels first, then Pixabay (free stock photos,
  free for YouTube use, no credit needed).
- Without a key (or if nothing is found) a clean gradient slide is drawn.
The scene's short "on_screen" headline is written on the picture.
"""
from __future__ import annotations

import hashlib
import os
import random
from io import BytesIO
from pathlib import Path

import requests
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from .common import font_family_for, font_file, log

PEXELS_URL = "https://api.pexels.com/v1/search"
PIXABAY_URL = "https://pixabay.com/api/"


# ------------------------------------------------------------------ helpers
def _hex(c: str) -> tuple[int, int, int]:
    c = c.lstrip("#")
    return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


def _font(text: str, size: int) -> ImageFont.FreeTypeFont:
    path = font_file(font_family_for(text), bold=True)
    try:
        return ImageFont.truetype(path, size, layout_engine=ImageFont.Layout.RAQM)
    except Exception:
        return ImageFont.truetype(path, size)


def _wrap(draw: ImageDraw.ImageDraw, text: str, font, max_w: int) -> list[str]:
    lines, line = [], ""
    for word in text.split():
        trial = f"{line} {word}".strip()
        if draw.textlength(trial, font=font) <= max_w or not line:
            line = trial
        else:
            lines.append(line)
            line = word
    if line:
        lines.append(line)
    return lines


def _fit_text(draw, text: str, max_w: int, max_h: int, start: int, min_size: int = 28):
    """Largest font size where the wrapped text fits the box."""
    size = start
    while size >= min_size:
        font = _font(text, size)
        lines = _wrap(draw, text, font, max_w)
        line_h = int(size * 1.35)
        if line_h * len(lines) <= max_h and all(
                draw.textlength(l, font=font) <= max_w for l in lines):
            return font, lines, line_h
        size -= 4
    font = _font(text, min_size)
    return font, _wrap(draw, text, font, max_w), int(min_size * 1.35)


def _draw_block(img: Image.Image, text: str, box: tuple[int, int, int, int],
                start_size: int, stroke: int = 0,
                fill: tuple[int, int, int] = (255, 255, 255)) -> None:
    """Centre `text` inside box=(x, y, w, h)."""
    draw = ImageDraw.Draw(img)
    x, y, w, h = box
    font, lines, line_h = _fit_text(draw, text, w, h, start_size)
    total = line_h * len(lines)
    cy = y + (h - total) // 2
    for line in lines:
        lw = draw.textlength(line, font=font)
        draw.text((x + (w - lw) / 2, cy), line, font=font, fill=fill,
                  stroke_width=stroke, stroke_fill=(0, 0, 0))
        cy += line_h


def _gradient(size: tuple[int, int], c1: str, c2: str, seed: int) -> Image.Image:
    w, h = size
    a, b = _hex(c1), _hex(c2)
    base = Image.new("RGB", (1, 256))
    for i in range(256):
        t = i / 255
        base.putpixel((0, i), tuple(int(a[k] + (b[k] - a[k]) * t) for k in range(3)))
    img = base.resize((w, h)).rotate(0)
    # Soft decorative circles so slides don't look flat
    rnd = random.Random(seed)
    layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    for _ in range(6):
        r = rnd.randint(min(w, h) // 8, min(w, h) // 2)
        cx, cy = rnd.randint(-r // 2, w + r // 2), rnd.randint(-r // 2, h + r // 2)
        d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=(255, 255, 255, rnd.randint(10, 28)))
    layer = layer.filter(ImageFilter.GaussianBlur(min(w, h) // 30))
    return Image.alpha_composite(img.convert("RGBA"), layer).convert("RGB")


def _cover(img: Image.Image, size: tuple[int, int]) -> Image.Image:
    """Resize + centre-crop to exactly fill `size`."""
    w, h = size
    scale = max(w / img.width, h / img.height)
    img = img.resize((int(img.width * scale) + 1, int(img.height * scale) + 1), Image.LANCZOS)
    left, top = (img.width - w) // 2, (img.height - h) // 2
    return img.crop((left, top, left + w, top + h))


# ------------------------------------------------------------------- pexels
def pexels_photo(query: str, portrait: bool, seed: int) -> Image.Image | None:
    key = os.environ.get("PEXELS_API_KEY", "").strip()
    if not key or not query:
        return None
    try:
        r = requests.get(PEXELS_URL, headers={"Authorization": key}, timeout=30, params={
            "query": query, "per_page": 15,
            "orientation": "portrait" if portrait else "landscape"})
        r.raise_for_status()
        photos = r.json().get("photos", [])
        if not photos:
            log(f"Pexels: nothing for '{query}', using a slide")
            return None
        photo = random.Random(seed).choice(photos[:8])
        img = requests.get(photo["src"]["large2x"], timeout=60)
        img.raise_for_status()
        return Image.open(BytesIO(img.content)).convert("RGB")
    except Exception as e:
        log(f"Pexels failed for '{query}': {e}")
        return None


# ------------------------------------------------------------------ pixabay
def pixabay_photo(query: str, portrait: bool, seed: int) -> Image.Image | None:
    key = os.environ.get("PIXABAY_API_KEY", "").strip()
    query = " ".join(query.split())[:100]          # Pixabay allows max 100 chars
    if not key or not query:
        return None
    try:
        r = requests.get(PIXABAY_URL, timeout=30, params={
            "key": key, "q": query, "image_type": "photo", "safesearch": "true",
            "orientation": "vertical" if portrait else "horizontal",
            "order": "popular", "per_page": 20})
        if r.status_code != 200:
            # Pixabay answers errors as plain text; never log the URL (it holds the key)
            log(f"Pixabay error {r.status_code} for '{query}': {r.text.strip()[:120]}")
            return None
        hits = r.json().get("hits", [])
        if not hits:
            log(f"Pixabay: nothing for '{query}', using a slide")
            return None
        hit = random.Random(seed).choice(hits[:8])
        url = hit.get("largeImageURL") or hit.get("webformatURL")
        img = requests.get(url, timeout=60)
        img.raise_for_status()
        return Image.open(BytesIO(img.content)).convert("RGB")
    except Exception as e:
        log(f"Pixabay failed for '{query}': {type(e).__name__}")
        return None


def stock_photo(query: str, portrait: bool, seed: int) -> Image.Image | None:
    """Pexels if its key is set, then Pixabay, else None (gradient slide)."""
    for name, fetch in (("Pexels", pexels_photo), ("Pixabay", pixabay_photo)):
        photo = fetch(query, portrait, seed)
        if photo is not None:
            log(f"Photo from {name} for '{query}' ({photo.width}x{photo.height})")
            return photo
    if not (os.environ.get("PEXELS_API_KEY", "").strip()
            or os.environ.get("PIXABAY_API_KEY", "").strip()):
        log(f"No photo key set: slide for '{query}'")
    return None


# ------------------------------------------------------------------- public
def scene_image(scene: dict, index: int, title: str, cfg: dict,
                size: tuple[int, int], out: Path) -> Path:
    """Draw one scene picture (2x size, so the slow zoom stays sharp)."""
    w, h = size[0] * 2, size[1] * 2
    portrait = h > w
    seed = int(hashlib.md5(f"{title}-{index}".encode()).hexdigest()[:8], 16)
    headline = str(scene.get("on_screen") or "").strip()

    photo = None
    if cfg["video"].get("visuals", "auto") == "auto":
        photo = stock_photo(str(scene.get("visual", "")), portrait, seed)

    bg_path = out.with_name(out.stem + "_bg.jpg")   # clean copy for the thumbnail
    if photo is not None:
        img = _cover(photo, (w, h))
        img.save(bg_path, quality=90)
        if headline:
            # dark band at the top so the headline is readable on any photo
            shade = Image.new("RGBA", (w, h), (0, 0, 0, 0))
            d = ImageDraw.Draw(shade)
            band = int(h * (0.28 if not portrait else 0.22))
            for y in range(band):
                d.line([(0, y), (w, y)], fill=(0, 0, 0, int(170 * (1 - y / band))))
            img = Image.alpha_composite(img.convert("RGBA"), shade).convert("RGB")
            # kept away from the edges: the slow zoom crops up to ~4% per side
            _draw_block(img, headline, (int(w * .08), int(h * .06), int(w * .84), int(band * .7)),
                        start_size=int(h * 0.07), stroke=3)
    else:
        palette = cfg["video"].get("palette") or [["#0f2027", "#2c5364"]]
        c1, c2 = palette[index % len(palette)]
        img = _gradient((w, h), c1, c2, seed)
        img.save(bg_path, quality=90)
        text = headline or title
        box_h = int(h * (0.45 if not portrait else 0.35))
        _draw_block(img, text, (int(w * .1), int(h * .5 - box_h * .75), int(w * .8), box_h),
                    start_size=int(h * (0.11 if not portrait else 0.065)), stroke=2)

    img.save(out, quality=92)
    return out


def thumbnail(data: dict, first_scene_img: Path, out: Path) -> Path:
    """1280x720 thumbnail: first picture, darkened, with big bold text."""
    text = str(data.get("thumbnail_text") or data["title"]).strip()
    bg = first_scene_img.with_name(first_scene_img.stem + "_bg.jpg")
    src = bg if bg.exists() else first_scene_img
    base = _cover(Image.open(src).convert("RGB"), (1280, 720))
    base = Image.blend(base, Image.new("RGB", base.size, (0, 0, 0)), 0.35)
    _draw_block(base, text, (70, 80, 1140, 560), start_size=130, stroke=7,
                fill=(255, 214, 0))
    base.save(out, "JPEG", quality=90)
    return out
