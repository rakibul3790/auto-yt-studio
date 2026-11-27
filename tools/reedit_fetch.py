"""History 5 re-edit asset fetcher (runs in GitHub Actions on branch history-5 only).

Modes:
  search <job.json>  Pixabay search; saves result metadata + small thumbnails.
  get    <job.json>  downloads chosen Pixabay videos/photos at full size.
  sfx    <job.json>  makes sound effects with ElevenLabs text-to-sound (no voice calls).

Keys come from PIXABAY_API_KEY / ELEVENLABS_API_KEY and are never printed.
Everything is written under out/.
"""
import json, os, sys, time, pathlib, requests

OUT = pathlib.Path("out")
OUT.mkdir(exist_ok=True)
PB = os.environ.get("PIXABAY_API_KEY", "").strip()
XI = os.environ.get("ELEVENLABS_API_KEY", "").strip()


def pb(endpoint, **params):
    url = "https://pixabay.com/api/videos/" if endpoint == "video" else "https://pixabay.com/api/"
    params["key"] = PB
    for _ in range(4):
        r = requests.get(url, params=params, timeout=60)
        if r.status_code == 429:
            time.sleep(20)
            continue
        r.raise_for_status()
        return r.json()
    r.raise_for_status()


def dl(url, dest):
    dest.parent.mkdir(parents=True, exist_ok=True)
    with requests.get(url, stream=True, timeout=300) as r:
        r.raise_for_status()
        with open(dest, "wb") as f:
            for chunk in r.iter_content(1 << 20):
                f.write(chunk)


def search(job):
    res = {}
    for q in job:
        kind, n = q.get("kind", "video"), q.get("n", 6)
        data = pb(kind, q=q["q"], per_page=max(3, n), safesearch="true",
                  **({"image_type": "photo"} if kind == "image" else {}))
        hits = []
        for i, h in enumerate(data.get("hits", [])[:n]):
            if kind == "video":
                v = h["videos"]
                big = v.get("large") if v.get("large", {}).get("url") else v["medium"]
                thumb = v["medium"].get("thumbnail") or v["small"].get("thumbnail")
                row = {"pixabay_id": h["id"], "page": h["pageURL"], "tags": h["tags"],
                       "duration": h["duration"], "w": big["width"], "h": big["height"]}
            else:
                thumb = h["webformatURL"]
                row = {"pixabay_id": h["id"], "page": h["pageURL"], "tags": h["tags"],
                       "w": h["imageWidth"], "h": h["imageHeight"]}
            if thumb:
                try:
                    dl(thumb, OUT / "thumbs" / f"{q['id']}_{i}.jpg")
                except Exception as e:  # thumbnail is only for picking
                    print("thumb failed", q["id"], i, e)
            hits.append(row)
        res[q["id"]] = {"q": q["q"], "kind": kind, "hits": hits}
        print(f"{q['id']:<12} {len(hits)} hits  '{q['q']}'")
        time.sleep(0.7)
    (OUT / "search_results.json").write_text(json.dumps(res, indent=1))


def get(job):
    log = []
    for p in job:
        kind = p.get("kind", "video")
        data = pb(kind, id=p["pixabay_id"])
        h = data["hits"][0]
        if kind == "video":
            v = h["videos"]
            best = max((v[k] for k in ("large", "medium") if v.get(k, {}).get("url")),
                       key=lambda x: x["width"])
            ext = ".mp4"
            url = best["url"]
        else:
            url = h.get("largeImageURL") or h["webformatURL"]
            ext = ".jpg"
        name = f"{p['id']}_pb{h['id']}{ext}"
        dl(url, OUT / "stock" / name)
        log.append({"id": p["id"], "file": name, "site": "Pixabay", "pixabay_id": h["id"],
                    "page": h["pageURL"], "tags": h["tags"], "licence": "Pixabay Content License"})
        print("got", name)
    (OUT / "stock_log.json").write_text(json.dumps(log, indent=1))


def credits():
    r = requests.get("https://api.elevenlabs.io/v1/user/subscription",
                     headers={"xi-api-key": XI}, timeout=30)
    if r.ok:
        j = r.json()
        return j.get("character_count"), j.get("character_limit")
    return None, None


def sfx(job):
    if not XI:
        sys.exit("ELEVENLABS_API_KEY is not set")
    used0, limit = credits()
    print(f"credits used before: {used0} / {limit}")
    log = []
    for s in job:
        body = {"text": s["text"], "prompt_influence": s.get("influence", 0.4),
                "model_id": s.get("model", "eleven_text_to_sound_v2")}
        if s.get("duration"):
            body["duration_seconds"] = s["duration"]
        if s.get("loop"):
            body["loop"] = True
        r = requests.post("https://api.elevenlabs.io/v1/sound-generation",
                          params={"output_format": "mp3_44100_128"},
                          headers={"xi-api-key": XI, "Content-Type": "application/json"},
                          json=body, timeout=180)
        if not r.ok:
            print("FAILED", s["id"], r.status_code, r.text[:200])
            continue
        dest = OUT / "sfx" / f"{s['id']}.mp3"
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(r.content)
        cost = r.headers.get("character-cost")
        log.append({"id": s["id"], "text": s["text"], "cost": cost})
        print(f"sfx {s['id']:<20} cost={cost}")
    used1, _ = credits()
    print(f"credits used after: {used1} / {limit}")
    (OUT / "sfx_log.json").write_text(json.dumps(
        {"before": used0, "after": used1, "limit": limit, "items": log}, indent=1))


def tts(job):
    """New narration lines with the channel's ElevenLabs v3 voice, with character timings."""
    import base64
    if not XI:
        sys.exit("ELEVENLABS_API_KEY is not set")
    log = []
    for s in job:
        body = {"text": s["text"], "model_id": s.get("model", "eleven_v3"),
                "voice_settings": {"stability": s.get("stability", 0.0), "similarity_boost": s.get("similarity", 0.8)}}
        if s.get("seed") is not None:
            body["seed"] = s["seed"]
        r = requests.post(f"https://api.elevenlabs.io/v1/text-to-speech/{s['voice']}/with-timestamps",
                          params={"output_format": "mp3_44100_192"},
                          headers={"xi-api-key": XI, "Content-Type": "application/json"}, json=body, timeout=300)
        if not r.ok:
            print("FAILED", s["id"], r.status_code, r.text[:200])
            continue
        j = r.json()
        d = OUT / "tts"
        d.mkdir(parents=True, exist_ok=True)
        (d / f"{s['id']}.mp3").write_bytes(base64.b64decode(j["audio_base64"]))
        (d / f"{s['id']}_align.json").write_text(json.dumps(j.get("normalized_alignment") or j.get("alignment")))
        cost = r.headers.get("character-cost")
        log.append({"id": s["id"], "text": s["text"], "cost": cost})
        print(f"tts {s['id']:<12} cost={cost}")
    (OUT / "tts_log.json").write_text(json.dumps(log, indent=1))


def batch(job):
    for step in job:
        sub = json.loads((pathlib.Path("reedit") / step["job"]).read_text(encoding="utf-8"))
        {"search": search, "get": get, "sfx": sfx, "tts": tts}[step["mode"]](sub)


if __name__ == "__main__":
    mode, path = sys.argv[1], sys.argv[2]
    job = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
    {"search": search, "get": get, "sfx": sfx, "tts": tts, "batch": batch}[mode](job)
