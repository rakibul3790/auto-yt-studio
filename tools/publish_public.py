"""One-off PUBLIC upload of a video the owner approved by hand (pro-shorts branch only).

The daily pipeline stays private-only (studio/youtube.py). This script is used only for
a publish-public/*.json the owner said yes to, and skips any JSON that already has "url".
"""
from __future__ import annotations

import hashlib
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from studio.youtube import _service, _tags, credentials_present  # noqa: E402


def main(meta_path: str, video_path: str) -> int:
    from googleapiclient.errors import HttpError
    from googleapiclient.http import MediaFileUpload

    meta_file = Path(meta_path)
    meta = json.loads(meta_file.read_text(encoding="utf-8"))
    if meta.get("url"):
        print(f"Already uploaded: {meta['url']}")
        return 0
    if not credentials_present():
        print("YouTube secrets missing")
        return 1
    video = Path(video_path)
    digest = hashlib.sha256(video.read_bytes()).hexdigest()
    if digest != meta["sha256"]:
        print(f"Video does not match the approved file ({digest})")
        return 1

    body = {
        "snippet": {"title": meta["title"][:100], "description": meta["description"][:4900],
                    "tags": _tags(meta["tags"]), "categoryId": str(meta.get("category_id", "27")),
                    "defaultLanguage": "en", "defaultAudioLanguage": "en"},
        "status": {"privacyStatus": "public", "selfDeclaredMadeForKids": False,
                   "containsSyntheticMedia": True},
    }
    yt = _service()
    req = yt.videos().insert(part="snippet,status", body=body,
                             media_body=MediaFileUpload(str(video), mimetype="video/mp4",
                                                        chunksize=8 * 1024 * 1024, resumable=True))
    response, tries = None, 0
    while response is None:
        try:
            status, response = req.next_chunk()
            if status:
                print(f"Uploading: {int(status.progress() * 100)}%")
        except HttpError as e:
            if e.resp.status in (500, 502, 503, 504) and tries < 6:
                tries += 1
                time.sleep(2 ** tries)
                continue
            raise
    vid = response["id"]
    meta["url"] = f"https://youtu.be/{vid}"
    meta["privacy_at_upload"] = response.get("status", {}).get("privacyStatus")
    meta["upload_status"] = response.get("status", {}).get("uploadStatus")
    print(f"Uploaded: {meta['url']} privacy={meta['privacy_at_upload']} upload={meta['upload_status']}")
    # YouTube can lock unaudited API uploads to private a little later: look again after a while
    for wait in (60, 120, 180):
        time.sleep(wait)
        try:
            items = yt.videos().list(part="status", id=vid).execute().get("items", [])
        except HttpError as e:
            print(f"Status check not allowed by this token ({e.resp.status})")
            break
        if items:
            st = items[0]["status"]
            meta["privacy_now"] = st.get("privacyStatus")
            meta["upload_status"] = st.get("uploadStatus")
            meta["rejection"] = st.get("rejectionReason", "")
            print(f"After {wait}s: privacy={meta['privacy_now']} upload={meta['upload_status']}")
            if meta["upload_status"] == "processed":
                break
    meta_file.write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1], sys.argv[2]))
