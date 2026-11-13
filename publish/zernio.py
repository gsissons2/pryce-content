"""TikTok and YouTube through Zernio (formerly Late, getlate.dev).

Both platforms lock unaudited apps to private posts; Zernio's apps are audited.
POST https://zernio.com/api/v1/posts with publishNow=true (the cron decides timing).
Docs: docs.zernio.com/posts/create-post, /platforms/tiktok, /guides/platform-settings, zernio.com/youtube
"""
from __future__ import annotations

import os

from . import captions
from .common import PermanentError, PublishError, env
from .http import Http

BASE = "https://zernio.com/api/v1"
# Must be one of the levels TikTok reports for the account. Business connections post videos public only.
TIKTOK_PRIVACY = os.environ.get("ZERNIO_TIKTOK_PRIVACY") or "PUBLIC_TO_EVERYONE"
TIKTOK_AUTO_MUSIC = (os.environ.get("ZERNIO_TIKTOK_AUTO_MUSIC") or "true").lower() == "true"
MAX_TIKTOK_PHOTOS = 35
POLL_INTERVAL = 15
TIMEOUT = 600
DONE = {"published"}
FAILED = {"failed", "error", "cancelled"}


class Zernio:
    def __init__(self, http: Http, key: str | None = None):
        self.http = http
        self.key = key or env("ZERNIO_API_KEY", http.dry_run)

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self.key}", "Content-Type": "application/json"}

    @staticmethod
    def _entry(body: dict, platform: str) -> tuple[dict, dict]:
        post = body.get("post") if isinstance(body.get("post"), dict) else body
        entry = next((p for p in post.get("platforms") or [] if p.get("platform") == platform), {})
        return post, entry

    @staticmethod
    def _error(body: dict, post: dict, entry: dict) -> str:
        return str(entry.get("errorMessage") or entry.get("error") or body.get("error")
                   or post.get("errorMessage") or "no details given")

    def create_and_wait(self, body: dict, platform: str) -> dict:
        r = self.http.request("POST", f"{BASE}/posts", headers=self._headers(), json_body=body, timeout=300,
                              final=True, dry_status=201,
                              dry={"post": {"_id": "DRYRUN-POST", "status": "published",
                                            "platforms": [{"platform": platform, "status": "published",
                                                           "platformPostId": "DRYRUN",
                                                           "platformPostUrl": f"https://{platform}.example/DRYRUN"}]}})
        if r.status_code not in (200, 201, 207):
            self.http.check(r, f"Zernio create {platform} post", final=True)
        res = r.json()
        post, entry = self._entry(res, platform)
        post_id = post.get("_id") or post.get("id")
        status = (entry.get("status") or post.get("status") or "").lower()
        if status in FAILED:
            raise PublishError(f"Zernio {platform} publish failed: {self._error(res, post, entry)}")
        if status not in DONE:
            if not post_id:
                raise PublishError(f"Zernio {platform}: status {status!r} and no post id to follow up")

            def check():
                g = self.http.request("GET", f"{BASE}/posts/{post_id}", headers=self._headers(),
                                      dry={"post": {"_id": post_id, "status": "published"}})
                body = self.http.check(g, f"Zernio get post {post_id}").json()
                p, e = self._entry(body, platform)
                s = (e.get("status") or p.get("status") or "").lower()
                if s in FAILED:
                    raise PublishError(f"Zernio {platform} publish failed: {self._error(body, p, e)}")
                return s in DONE, (p, e) if s in DONE else s
            post, entry = self.http.poll(check, interval=POLL_INTERVAL, timeout=TIMEOUT,
                                         what=f"Zernio {platform} publishing")
        return {"id": str(post_id), "platform_id": entry.get("platformPostId"), "url": entry.get("platformPostUrl")}


def tiktok_body(spec: dict, assets, account_id: str) -> tuple[dict, list[str]]:
    text, warnings = captions.tiktok_caption(spec, assets.kind)
    settings = {
        "privacy_level": TIKTOK_PRIVACY,
        "allow_comment": True,
        # Graham approves by merging the PR that shows the rendered preview, so these are true.
        "content_preview_confirmed": True,
        "express_consent_given": True,
    }
    if assets.kind == "carousel":
        if len(assets.slides) > MAX_TIKTOK_PHOTOS:
            raise PermanentError(f"{len(assets.slides)} slides, TikTok photo posts take at most {MAX_TIKTOK_PHOTOS}")
        media = [{"type": "image", "url": assets.url(p)} for p in assets.slides]
        content = text["title"]
        settings.update({"media_type": "photo", "photo_cover_index": 0, "description": text["description"],
                         "auto_add_music": TIKTOK_AUTO_MUSIC})
    else:
        media = [{"type": "video", "url": assets.url(assets.video)}]
        content = text["caption"]
        settings.update({"allow_duet": True, "allow_stitch": True})
    body = {
        "content": content,
        "mediaItems": media,
        "platforms": [{"platform": "tiktok", "accountId": account_id}],
        "tiktokSettings": settings,
        "publishNow": True,
        "metadata": {"specId": spec.get("id")},
    }
    return body, warnings


def youtube_body(spec: dict, assets, account_id: str) -> tuple[dict, list[str]]:
    if assets.kind != "video":
        raise PermanentError("YouTube only takes video formats")
    title, description, warnings = captions.youtube_meta(spec)
    body = {
        "content": description,
        "mediaItems": [{"type": "video", "url": assets.url(assets.video)}],
        "platforms": [{"platform": "youtube", "accountId": account_id,
                       "platformSpecificData": {"title": title, "visibility": "public", "madeForKids": False}}],
        "publishNow": True,
        "metadata": {"specId": spec.get("id")},
    }
    return body, warnings


def publish_tiktok(http: Http, spec: dict, assets) -> dict:
    z = Zernio(http)
    body, warnings = tiktok_body(spec, assets, env("ZERNIO_TIKTOK_ACCOUNT_ID", http.dry_run))
    result = z.create_and_wait(body, "tiktok")
    result["warnings"] = warnings
    return result


def publish_youtube(http: Http, spec: dict, assets) -> dict:
    if assets.kind != "video":
        raise PermanentError("YouTube only takes video formats")
    z = Zernio(http)
    body, warnings = youtube_body(spec, assets, env("ZERNIO_YOUTUBE_ACCOUNT_ID", http.dry_run))
    result = z.create_and_wait(body, "youtube")
    result["warnings"] = warnings
    return result
