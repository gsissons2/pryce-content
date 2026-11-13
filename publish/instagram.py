"""Instagram API with Instagram Login (graph.instagram.com), Standard Access, own account as tester.

Docs: developers.facebook.com/docs/instagram-platform/content-publishing
Carousel: one image container per slide (is_carousel_item), a CAROUSEL container with the
children and caption, wait for FINISHED, then media_publish.
Reel (default, IG_REELS_UPLOAD=resumable): a REELS container with upload_type=resumable, then the
video bytes POSTed to rupload.facebook.com, wait for FINISHED, then media_publish. Meta documents
resumable upload under Facebook Login for Business only, so if Instagram refuses it we fall back to
video_url from Pages in the same attempt (nothing is live yet, so this cannot double post).
IG_REELS_UPLOAD=url skips resumable and always uses video_url.
"""
from __future__ import annotations

import itertools
import os
from datetime import timedelta

from . import captions
from .common import PermanentError, PublishError, SkipForNow, UncertainError, env, iso, now_utc
from .http import Http

HOST = "https://graph.instagram.com"
RUPLOAD = "https://rupload.facebook.com/ig-api-upload"
API_VERSION = os.environ.get("IG_API_VERSION") or "v27.0"
MAX_CAROUSEL_ITEMS = 10      # the IG Media reference says children takes up to 10
POLL_INTERVAL = 15
CAROUSEL_TIMEOUT = 180
VIDEO_TIMEOUT = 600
UPLOAD_TIMEOUT = 900

_dry_ids = itertools.count(1)


class Instagram:
    def __init__(self, http: Http, user_id: str | None = None, token: str | None = None):
        self.http = http
        self.user_id = user_id or env("IG_USER_ID", http.dry_run)
        self.token = token or env("IG_ACCESS_TOKEN", http.dry_run)
        self.base = f"{HOST}/{API_VERSION}"
        self.warnings: list[str] = []

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"}

    def _get(self, path: str, params: dict, what: str, dry: dict) -> dict:
        r = self.http.request("GET", f"{self.base}/{path}", headers=self._headers(), params=params, dry=dry)
        return self.http.check(r, what).json()

    def _post(self, path: str, body: dict, what: str, dry: dict, final: bool = False) -> dict:
        r = self.http.request("POST", f"{self.base}/{path}", headers=self._headers(), json_body=body,
                              final=final, timeout=120, dry=dry)
        return self.http.check(r, what, final=final).json()

    # Limits -------------------------------------------------------------
    def quota(self) -> tuple[int, int]:
        data = self._get(f"{self.user_id}/content_publishing_limit", {"fields": "quota_usage,config"},
                         "Instagram publishing limit",
                         dry={"data": [{"quota_usage": 0, "config": {"quota_total": 100, "quota_duration": 86400}}]})
        row = (data.get("data") or [{}])[0]
        used = int(row.get("quota_usage") or 0)
        total = int((row.get("config") or {}).get("quota_total") or 0)
        return used, total

    def ensure_quota(self):
        used, total = self.quota()
        if total and used >= total:
            raise SkipForNow(f"Instagram daily publishing limit used up ({used} of {total} in the last 24 h)")

    # Steps --------------------------------------------------------------
    def create_container(self, body: dict, what: str) -> str:
        res = self._post(f"{self.user_id}/media", body, f"Create {what} container",
                         dry={"id": f"DRY-CONTAINER-{next(_dry_ids)}"})
        cid = res.get("id")
        if not cid:
            raise PublishError(f"Create {what} container: no id in response {res}")
        return str(cid)

    def wait_ready(self, cid: str, timeout: float, what: str) -> str:
        def check():
            data = self._get(cid, {"fields": "status_code,status"}, f"{what} container status",
                             dry={"status_code": "FINISHED"})
            code = data.get("status_code")
            if code in ("FINISHED", "PUBLISHED"):
                return True, code
            if code in ("ERROR", "EXPIRED"):
                raise PublishError(f"{what} container {cid} is {code}: {data.get('status') or 'no details given'}")
            return False, code
        return self.http.poll(check, interval=POLL_INTERVAL, timeout=timeout, what=f"Instagram {what} processing")

    def publish_container(self, cid: str) -> str:
        res = self._post(f"{self.user_id}/media_publish", {"creation_id": cid}, "Instagram media_publish",
                         dry={"id": "DRY-MEDIA-ID"}, final=True)
        mid = res.get("id")
        if not mid:
            raise PublishError(f"media_publish: no id in response {res}")
        return str(mid)

    def permalink(self, media_id: str) -> str | None:
        try:
            data = self._get(media_id, {"fields": "permalink"}, "Instagram permalink",
                             dry={"permalink": "https://www.instagram.com/p/DRYRUN/"})
            return data.get("permalink")
        except PublishError:
            return None  # the post is live; a missing link is not worth a retry

    # Posts --------------------------------------------------------------
    def post_carousel(self, image_urls: list[str], caption: str, alts: list[str] | None = None) -> dict:
        n = len(image_urls)
        if n == 0:
            raise PermanentError("no slides to post")
        if n > MAX_CAROUSEL_ITEMS:
            raise PermanentError(f"{n} slides, the Instagram API takes at most {MAX_CAROUSEL_ITEMS} per carousel")
        alts = alts or []
        self.ensure_quota()
        if n == 1:
            body = {"image_url": image_urls[0], "caption": caption}
            if alts and alts[0]:
                body["alt_text"] = alts[0]
            cid = self.create_container(body, "image")
        else:
            children = []
            for i, url in enumerate(image_urls):
                body = {"image_url": url, "is_carousel_item": True}
                if i < len(alts) and alts[i]:
                    body["alt_text"] = alts[i]
                children.append(self.create_container(body, f"slide {i + 1}"))
            cid = self.create_container({"media_type": "CAROUSEL", "children": ",".join(children),
                                         "caption": caption}, "carousel")
        self.wait_ready(cid, CAROUSEL_TIMEOUT, "carousel")
        mid = self.publish_container(cid)
        return {"id": mid, "url": self.permalink(mid)}

    def resumable_container(self, body: dict, video_path) -> str:
        """Create a resumable REELS container and upload the file bytes to rupload.facebook.com."""
        data = video_path.read_bytes()
        res = self._post(f"{self.user_id}/media", dict(body, upload_type="resumable"), "Create resumable reel container",
                         dry={"id": "DRY-REEL", "uri": f"{RUPLOAD}/{API_VERSION}/DRY-REEL"})
        cid = res.get("id")
        if not cid:
            raise PublishError(f"Create resumable reel container: no id in response {res}")
        uri = res.get("uri") or ""
        if not uri.startswith(RUPLOAD + "/"):
            uri = f"{RUPLOAD}/{API_VERSION}/{cid}"  # never send the token anywhere but rupload.facebook.com
        r = self.http.request("POST", uri, headers={"Authorization": f"OAuth {self.token}", "offset": "0",
                                                    "file_size": str(len(data))},
                              data=data, describe=f"<{len(data)} bytes from {video_path}>", timeout=UPLOAD_TIMEOUT,
                              dry={"success": True, "message": "Upload successful."})
        self.http.check(r, "Instagram rupload")
        try:
            ok = r.json()
        except ValueError:
            ok = {}
        if ok.get("success") is not True:
            raise PublishError(f"Instagram rupload did not succeed: {ok.get('debug_info') or ok or r.text[:300]}")
        return str(cid)

    def post_reel(self, caption: str, *, video_path=None, video_url: str | None = None,
                  cover_url: str | None = None, mode: str = "resumable") -> dict:
        self.ensure_quota()
        body = {"media_type": "REELS", "caption": caption, "share_to_feed": True}
        if cover_url:
            body["cover_url"] = cover_url
        cid = None
        if mode == "resumable" and video_path is not None:
            try:
                cid = self.resumable_container(body, video_path)
            except UncertainError:
                raise
            except PublishError as e:
                if not video_url:
                    raise
                self.warnings.append(f"instagram: resumable upload failed ({str(e)[:200]}), used video_url instead")
                print(f"   instagram: resumable upload failed, falling back to video_url: {e}")
        if cid is None:
            if not video_url:
                raise PermanentError("no video URL and resumable upload not used")
            cid = self.create_container(dict(body, video_url=video_url), "reel")
        self.wait_ready(cid, VIDEO_TIMEOUT, "reel")
        mid = self.publish_container(cid)
        return {"id": mid, "url": self.permalink(mid)}


def publish(http: Http, spec: dict, assets) -> dict:
    caption, warnings = captions.instagram_caption(spec)
    ig = Instagram(http)
    if assets.kind == "carousel":
        alts, w = captions.instagram_alt(spec, len(assets.slides))
        warnings += w
        result = ig.post_carousel([assets.url(p) for p in assets.slides], caption, alts)
    else:
        mode = (os.environ.get("IG_REELS_UPLOAD") or "resumable").strip().lower()
        if mode not in ("resumable", "url"):
            raise PermanentError(f"IG_REELS_UPLOAD must be resumable or url, not {mode!r}")
        cover = assets.urls.get(assets.cover.name) if assets.cover else None
        video_url = assets.urls.get(assets.video.name)
        result = ig.post_reel(caption, video_path=assets.video, video_url=video_url, cover_url=cover, mode=mode)
    result["warnings"] = warnings + ig.warnings
    return result


def refresh_token(http: Http | None = None, token: str | None = None) -> dict:
    """Refresh the long-lived token (must be at least 24 h old and not expired).
    Returns {"access_token", "expires_in", "expires_at", "changed"}. Never prints the token."""
    http = http or Http()
    token = token or env("IG_ACCESS_TOKEN", http.dry_run)
    r = http.request("GET", f"{HOST}/refresh_access_token",
                     params={"grant_type": "ig_refresh_token", "access_token": token},
                     dry={"access_token": token, "token_type": "bearer", "expires_in": 5183944})
    body = http.check(r, "Instagram token refresh").json()
    new = body.get("access_token") or ""
    expires_in = int(body.get("expires_in") or 0)
    expires_at = now_utc() + timedelta(seconds=expires_in)
    if os.environ.get("GITHUB_ACTIONS") and new and new != token:
        print(f"::add-mask::{new}")
    print(f"Instagram token refreshed. Expires {iso(expires_at)} (in {expires_in // 86400} days).")
    if new and new != token:
        print("Instagram returned a different token string. The IG_ACCESS_TOKEN secret still holds the old one, "
              "which keeps its own expiry. Generate a fresh token in the Meta dashboard and update the secret "
              "before the old one runs out.")
    return {"access_token": new, "expires_in": expires_in, "expires_at": iso(expires_at), "changed": new != token}
