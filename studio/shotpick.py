"""AI shot picker: chooses the stock clip that really shows what a beat asks for.

Stock sites match on loose tags, so a search for "octopus close up" can return a
pastry or a shark tank. Here every candidate (Pexels clips, Pixabay clips and
Pixabay photos) is judged on its preview picture with CLIP, a free open-source
image-text model, and the best fresh match wins. Pictures that look like nudity
are skipped. If CLIP isn't installed or anything fails, the caller falls back to
the older tag-based search, so nothing breaks.
"""
from __future__ import annotations

import io
import json
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests
from PIL import Image

from . import visuals
from .common import log

MODEL, PRETRAINED = "ViT-B-32", "laion2b_s34b_b79k"
GOOD_SCORE = 0.215           # above this the picture clearly shows the thing
MIN_SCORE = 0.17             # below this it almost surely doesn't
PHOTO_PENALTY = 0.025        # a moving clip beats a still of the same quality
REUSE_PENALTY = 0.06
UNSAFE = ["a photo of a nude person", "a naked statue", "a photo of underwear", "a bloody wound"]

_clip = None                 # (model, preprocess, tokenizer) or False when unavailable
_USED: set[str] = set()


def _load():
    global _clip
    if _clip is None:
        try:
            import open_clip
            import torch
            torch.set_num_threads(max(1, os.cpu_count() or 1))
            model, _, pre = open_clip.create_model_and_transforms(MODEL, pretrained=PRETRAINED)
            model.eval()
            _clip = (model, pre, open_clip.get_tokenizer(MODEL))
            log("Shot picker: CLIP loaded")
        except Exception as e:
            log(f"Shot picker off ({type(e).__name__}): using tag search")
            _clip = False
    return _clip or None


def available() -> bool:
    return _load() is not None


def _texts(texts: list[str]):
    import torch
    model, _, tok = _clip
    with torch.no_grad():
        t = model.encode_text(tok(texts))
    return t / t.norm(dim=-1, keepdim=True)


def score(images: list[Image.Image], prompts: list[str], weights: list[float]) -> list[tuple[float, bool]]:
    """(relevance, unsafe) for each picture: weighted cosine similarity to the prompts."""
    import torch
    model, pre, _ = _clip
    with torch.no_grad():
        x = torch.stack([pre(im.convert("RGB")) for im in images])
        f = model.encode_image(x)
        f = f / f.norm(dim=-1, keepdim=True)
        sim = f @ _texts(prompts + UNSAFE).T
    out = []
    n = len(prompts)
    for row in sim.tolist():
        rel = sum(w * s for w, s in zip(weights, row[:n])) / sum(weights)
        bad = max(row[n:]) > max(0.26, max(row[:n]) + 0.02)
        out.append((rel, bad))
    return out


# ------------------------------------------------------------------ candidates
def _pixabay_videos(key: str, q: str) -> list[dict]:
    r = requests.get(visuals.PIXABAY_VIDEO_URL, timeout=30, params={
        "key": key, "q": q[:100], "video_type": "film", "safesearch": "true", "per_page": 30})
    if r.status_code != 200:
        return []
    out = []
    for h in r.json().get("hits", []):
        if not 3 <= float(h.get("duration", 0)) <= 60:
            continue
        vids = h.get("videos") or {}
        f = next((vids[s] for s in ("large", "medium") if (vids.get(s) or {}).get("url")
                  and vids[s].get("height", 0) >= 720 and 0 < vids[s].get("size", 0) < 60_000_000), None)
        thumb = next((vids[s].get("thumbnail") for s in ("small", "tiny", "medium", "large")
                      if (vids.get(s) or {}).get("thumbnail")), None)
        if f and thumb:
            out.append({"id": f"pb{h['id']}", "kind": "vid", "url": f["url"], "thumb": thumb,
                        "dur": float(h["duration"]), "w": f.get("width"), "h": f.get("height"), "site": "Pixabay"})
    return out


def _pixabay_photos(key: str, q: str) -> list[dict]:
    r = requests.get(visuals.PIXABAY_URL, timeout=30, params={
        "key": key, "q": q[:100], "image_type": "photo", "safesearch": "true", "per_page": 20,
        "min_width": 1000})
    if r.status_code != 200:
        return []
    return [{"id": f"pbi{h['id']}", "kind": "img", "url": h.get("largeImageURL"), "thumb": h.get("webformatURL"),
             "w": h.get("imageWidth"), "h": h.get("imageHeight"), "site": "Pixabay"}
            for h in r.json().get("hits", []) if h.get("largeImageURL") and h.get("webformatURL")]


def _pexels_videos(key: str, q: str) -> list[dict]:
    out = []
    for orient in ("portrait", "landscape"):
        r = requests.get("https://api.pexels.com/videos/search", headers={"Authorization": key}, timeout=30,
                         params={"query": q, "orientation": orient, "per_page": 15})
        if r.status_code != 200:
            break
        for v in r.json().get("videos", []):
            if not 3 <= float(v.get("duration") or 0) <= 90 or not v.get("image"):
                continue
            files = [f for f in v.get("video_files", []) if f.get("link") and (f.get("height") or 0) >= 720
                     and (f.get("file_type") or "").endswith("mp4")]
            if not files:
                continue
            port = [f for f in files if f["height"] > f["width"]]
            f = min(port or files, key=lambda f: abs(f["height"] - (1920 if f["height"] > f["width"] else 1080)))
            out.append({"id": f"px{v['id']}", "kind": "vid", "url": f["link"], "thumb": v["image"],
                        "dur": float(v["duration"]), "w": f["width"], "h": f["height"], "site": "Pexels"})
    return out


def _thumb(url: str) -> Image.Image | None:
    try:
        r = requests.get(url, timeout=20)
        r.raise_for_status()
        im = Image.open(io.BytesIO(r.content))
        im.load()
        return im
    except Exception:
        return None


def _prompts(query: str, subject: str | None) -> tuple[list[str], list[float]]:
    q = " ".join(query.split())
    prompts, weights = [f"a photo of {q}", f"stock footage of {q}"], [1.0, 1.0]
    if subject and subject.lower() not in q.lower():
        prompts.append(f"a photo of a {subject}")
        weights.append(1.2)
    elif subject:
        prompts.append(f"a photo of a {subject}")
        weights.append(0.8)
    return prompts, weights


# ------------------------------------------------------------------ public
def pick(query: str, subject: str | None, out_stem: Path) -> dict | None:
    """Choose and download the best picture for a beat.

    Returns {"kind": "vid"|"img", "src": Path, "start": s, "dur": s} or None."""
    query = " ".join(str(query or "").split())
    if not query:
        return None
    meta = out_stem.with_suffix(".pick.json")
    if meta.exists():                              # same render again: same choice
        m = json.loads(meta.read_text())
        src = Path(m["src"])
        if src.exists():
            _USED.add(m["id"])
            return {"kind": m["kind"], "src": src, "start": m.get("start", 0.0), "dur": m.get("dur")}
    if not available():
        return None
    pb, px = os.environ.get("PIXABAY_API_KEY", "").strip(), os.environ.get("PEXELS_API_KEY", "").strip()
    if not (pb or px):
        return None
    need = visuals.subject_words(query, subject)
    searches = list(dict.fromkeys([query, " ".join(need)] if need else [query]))
    try:
        cands: dict[str, dict] = {}
        jobs = []
        with ThreadPoolExecutor(6) as ex:
            for q in searches:
                if px:
                    jobs.append(ex.submit(_pexels_videos, px, q))
                if pb:
                    jobs.append(ex.submit(_pixabay_videos, pb, q))
                    jobs.append(ex.submit(_pixabay_photos, pb, q))
            for j in jobs:
                try:
                    for c in j.result():
                        cands.setdefault(c["id"], c)
                except Exception:
                    pass
            pool = list(cands.values())[:60]
            thumbs = list(ex.map(lambda c: _thumb(c["thumb"]), pool))
        pool = [(c, t) for c, t in zip(pool, thumbs) if t is not None]
        if not pool:
            log(f"Shot picker: nothing found for '{query}'")
            return None
        prompts, weights = _prompts(query, subject)
        scores = score([t for _, t in pool], prompts, weights)
        ranked = []
        for (c, _), (rel, bad) in zip(pool, scores):
            if bad:
                continue
            s = rel - (PHOTO_PENALTY if c["kind"] == "img" else 0) - (REUSE_PENALTY if c["id"] in _USED else 0)
            if c["kind"] == "vid" and c.get("h") and c.get("w") and c["h"] > c["w"]:
                s += 0.01                          # already vertical: less cropping
            ranked.append((s, rel, c))
        if not ranked:
            return None
        ranked.sort(key=lambda r: -r[0])
        s, rel, c = ranked[0]
        if rel < MIN_SCORE:
            log(f"Shot picker: no real match for '{query}' (best {rel:.3f})")
            return None
        if rel < GOOD_SCORE:
            log(f"Shot picker: weak match for '{query}' (best {rel:.3f}), using it")
        data = requests.get(c["url"], timeout=180)
        data.raise_for_status()
        ext = ".mp4" if c["kind"] == "vid" else ".jpg"
        src = out_stem.with_suffix(ext)
        reused = c["id"] in _USED
        if c["kind"] == "vid":
            src.write_bytes(data.content)
            dur = c.get("dur") or 0.0
            start = round(dur * 0.5, 2) if reused and dur > 8 else round(min(0.6, dur * 0.05), 2)
        else:
            img = Image.open(io.BytesIO(data.content)).convert("RGB")
            img.save(src, quality=93)
            dur, start = None, 0.0
        _USED.add(c["id"])
        meta.write_text(json.dumps({"id": c["id"], "kind": c["kind"], "src": str(src), "start": start,
                                    "dur": dur, "score": round(rel, 4)}))
        log(f"Shot picker: {c['site']} {'clip' if c['kind'] == 'vid' else 'photo'} {c['id']} for '{query}' "
            f"(match {rel:.3f}, {len(pool)} looked at{', reused' if reused else ''})")
        return {"kind": c["kind"], "src": src, "start": start, "dur": dur}
    except Exception as e:
        log(f"Shot picker failed for '{query}': {type(e).__name__}: {str(e)[:80]}")
        return None
