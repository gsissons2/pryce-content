"""TikTok and YouTube through Zernio (zernio.com).

Both platforms lock unaudited apps to private posts; Zernio's apps are audited.

Checked against Zernio's generated API types (@zernio/node 0.2.1645, Nov 2026):
- POST /v1/posts with publishNow=true publishes in the same request (the cron decides timing).
  HTTP 201 on success, 207 when the platform failed. Per-platform options go in
  platforms[].platformSpecificData (TikTokPlatformData / YouTubePlatformData, camelCase).
- Idempotency-Key: a retry with the same key within 24 h returns the original post, never a
  second one. The key includes the attempt number, so a retry after a real failure is a new post.
- Content-hash dedup: the same content and media to the same account within 24 h is refused with 409.
- Per-platform status: pending, processing, uploading, published, failed, cancelled. TikTok can sit
  in "uploading" for up to 48 h and settles on its own, so a post Zernio accepted is never re-sent.
- GET /v1/accounts lists connected accounts (_id, platform, username, isActive, needsReconnection).
  The account ids are looked up from the API key, so the only secret needed is ZERNIO_API_KEY.
"""
from __future__ import annotations

import os

from . import captions
from .common import PermanentError, PublishError, SkipForNow, UncertainError, env
from .http import Http

BASE = "https://zernio.com/api/v1"
# Must be one of the levels TikTok reports for the account (Token check prints them).
# Accounts connected through the TikTok for Business app post videos as public only.
TIKTOK_PRIVACY = os.environ.get("ZERNIO_TIKTOK_PRIVACY") or "PUBLIC_TO_EVERYONE"
TIKTOK_AUTO_MUSIC = (os.environ.get("ZERNIO_TIKTOK_AUTO_MUSIC") or "true").lower() == "true"
MAX_TIKTOK_PHOTOS = 35
POLL_INTERVAL = 15
SETTLE_WAIT = 180          # how long to wait for the post URL before recording it as accepted
CONFLICT_WAIT_MAX = 60     # cap on Retry-After for an idempotency conflict
DONE = {"published"}
FAILED = {"failed", "error", "cancelled"}
NAMES = {"tiktok": "TikTok", "youtube": "YouTube"}


def accounts(http: Http, key: str) -> list[dict]:
    r = http.request("GET", f"{BASE}/accounts", headers={"Authorization": f"Bearer {key}"},
                     dry={"accounts": [{"_id": "<tiktok account>", "platform": "tiktok", "username": "prycedigital",
                                        "isActive": True},
                                       {"_id": "<youtube account>", "platform": "youtube", "username": "prycedigital",
                                        "isActive": True}]})
    body = http.check(r, "Zernio accounts").json()
    rows = body if isinstance(body, list) else (body.get("accounts") or body.get("data") or [])
    return [a for a in rows if isinstance(a, dict)]


def pick_account(rows: list[dict], platform: str, username: str | None = None) -> str:
    """The Zernio account id for this platform. Skip (not a failure) when none is connected."""
    name = NAMES.get(platform, platform)
    found = [a for a in rows if a.get("platform") == platform]
    if username:
        want = username.lstrip("@").lower()
        found = [a for a in found if str(a.get("username") or "").lstrip("@").lower() == want]
    live = [a for a in found if a.get("isActive", True) and not a.get("needsReconnection")]
    if not live:
        if found:
            raise PublishError(f"Zernio: the {name} account needs reconnecting in the Zernio dashboard")
        who = f" @{username.lstrip('@')}" if username else ""
        raise SkipForNow(f"no {name}{who} account connected in Zernio yet")
    if len(live) > 1:
        names = ", ".join(f"@{a.get('username')}" for a in live)
        raise PermanentError(f"Zernio has several {name} accounts ({names}). Set variable "
                             f"ZERNIO_{platform.upper()}_USERNAME to the one to post as.")
    return str(live[0].get("_id") or live[0].get("id"))


def idempotency_key(spec: dict, platform: str) -> str:
    """Same key for a resend of the same attempt; a new key after each recorded failure."""
    failed = (spec.get("failed") or {}).get(platform)
    tries = 0
    if isinstance(failed, dict):
        tries = len(failed.get("history") or []) or (1 if failed.get("error") else 0)
    elif isinstance(failed, list):
        tries = len(failed)
    return f"pryce-{spec.get('id')}-{platform}-{tries + 1}"[:255]


class Zernio:
    def __init__(self, http: Http, key: str | None = None):
        self.http = http
        self.key = key or env("ZERNIO_API_KEY", http.dry_run)

    def _headers(self, idem: str | None = None) -> dict:
        h = {"Authorization": f"Bearer {self.key}", "Content-Type": "application/json"}
        if idem:
            h["Idempotency-Key"] = idem
        return h

    def account_id(self, platform: str) -> str:
        override = os.environ.get(f"ZERNIO_{platform.upper()}_ACCOUNT_ID", "").strip()
        if override:
            return override
        username = os.environ.get(f"ZERNIO_{platform.upper()}_USERNAME", "").strip() or None
        return pick_account(accounts(self.http, self.key), platform, username)

    @staticmethod
    def _entry(body: dict, platform: str) -> tuple[dict, dict]:
        post = body.get("post") if isinstance(body.get("post"), dict) else body
        entry = next((p for p in post.get("platforms") or [] if p.get("platform") == platform), {})
        return post, entry

    @staticmethod
    def _error(body: dict, post: dict, entry: dict, platform: str) -> str:
        result = next((p for p in body.get("platformResults") or [] if p.get("platform") == platform), {})
        return str(entry.get("errorMessage") or result.get("error") or entry.get("error") or body.get("error")
                   or post.get("errorMessage") or body.get("message") or "no details given")

    def _create(self, body: dict, platform: str, idem: str):
        """POST the post. Resends once with the same Idempotency-Key if the answer is lost or a 5xx,
        which returns the original post rather than making a second one."""
        what = f"Zernio create {platform} post"
        dry = {"message": "dry run", "post": {"_id": "DRYRUN-POST", "status": "published", "platforms": [
            {"platform": platform, "status": "published", "platformPostId": "DRYRUN",
             "platformPostUrl": f"https://{platform}.example/DRYRUN"}]}}
        for attempt in (1, 2):
            try:
                r = self.http.request("POST", f"{BASE}/posts", headers=self._headers(idem), json_body=body,
                                      timeout=300, final=True, dry_status=201, dry=dry)
                if r.status_code >= 500:
                    self.http.check(r, what, final=True)   # raises UncertainError
            except UncertainError:
                if attempt == 2:
                    raise
                self.http.sleep(30)
                continue
            if r.status_code == 409:
                try:
                    err = r.json()
                except ValueError:
                    err = {}
                if err.get("code") == "idempotency_conflict" and attempt == 1:
                    wait = min(CONFLICT_WAIT_MAX, float((r.headers or {}).get("Retry-After") or 10))
                    self.http.sleep(wait)
                    continue
                if err.get("code") == "idempotency_conflict":
                    raise UncertainError(f"{what}: Zernio is still processing the first send. "
                                         "It may or may not have posted.")
                raise PermanentError(f"{what}: Zernio refused it as a duplicate of a post made in the last "
                                     f"24 hours (409: {err.get('error') or err.get('message') or 'duplicate'}). "
                                     "Check the account; if it is not there, retry it from the Zernio dashboard.")
            if r.status_code not in (200, 201, 207):
                self.http.check(r, what, final=True)
            return r.json()
        raise UncertainError(f"{what}: no clear answer after a resend.")   # not reached

    def create_and_wait(self, body: dict, platform: str, idem: str) -> dict:
        res = self._create(body, platform, idem)
        post, entry = self._entry(res, platform)
        post_id = post.get("_id") or post.get("id")
        status = (entry.get("status") or post.get("status") or "").lower()
        if status in FAILED:
            raise PublishError(f"Zernio {platform} publish failed: {self._error(res, post, entry, platform)}")
        if status not in DONE and post_id:
            # Accepted but not live yet. Wait a little for the URL; after that Zernio finishes on its own.
            def check():
                g = self.http.request("GET", f"{BASE}/posts/{post_id}", headers=self._headers(),
                                      dry={"post": {"_id": post_id, "status": "published"}})
                b = self.http.check(g, f"Zernio get post {post_id}").json()
                p, e = self._entry(b, platform)
                s = (e.get("status") or p.get("status") or "").lower()
                if s in FAILED:
                    raise PublishError(f"Zernio {platform} publish failed: {self._error(b, p, e, platform)}")
                return s in DONE, (p, e, s)
            try:
                post, entry, status = self.http.poll(check, interval=POLL_INTERVAL, timeout=SETTLE_WAIT,
                                                     what=f"Zernio {platform} publishing")
            except PublishError as e:
                if "publish failed" in str(e):
                    raise
                # Still processing (TikTok can take up to 48 h) or the status read failed. Zernio has
                # the post, so record it as sent; sending it again would post it twice.
                return {"id": str(post_id), "platform_id": entry.get("platformPostId"),
                        "url": entry.get("platformPostUrl") or None, "zernio_status": status or "pending",
                        "note": "accepted by Zernio, still processing; link appears in the Zernio dashboard"}
        elif status not in DONE:
            raise UncertainError(f"Zernio {platform}: status {status!r} and no post id to follow up. "
                                 "It may or may not have posted.")
        return {"id": str(post_id), "platform_id": entry.get("platformPostId"),
                "url": entry.get("platformPostUrl") or None}


def tiktok_body(spec: dict, assets, account_id: str) -> tuple[dict, list[str]]:
    text, warnings = captions.tiktok_caption(spec, assets.kind)
    settings = {
        "privacyLevel": TIKTOK_PRIVACY,
        "allowComment": True,
        # Graham approves by merging the PR that shows the rendered preview, so these are true.
        "contentPreviewConfirmed": True,
        "expressConsentGiven": True,
    }
    if assets.kind == "carousel":
        if len(assets.slides) > MAX_TIKTOK_PHOTOS:
            raise PermanentError(f"{len(assets.slides)} slides, TikTok photo posts take at most {MAX_TIKTOK_PHOTOS}")
        media = [{"type": "image", "url": assets.url(p)} for p in assets.slides]
        content = text["title"]   # photo titles are cut at 90 characters, the full caption goes in description
        settings.update({"mediaType": "photo", "photoCoverIndex": 0, "description": text["description"],
                         "autoAddMusic": TIKTOK_AUTO_MUSIC})
    else:
        media = [{"type": "video", "url": assets.url(assets.video)}]
        content = text["caption"]
        settings.update({"mediaType": "video", "allowDuet": True, "allowStitch": True})
    body = {
        "content": content,
        "mediaItems": media,
        "platforms": [{"platform": "tiktok", "accountId": account_id, "platformSpecificData": settings}],
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
                       "platformSpecificData": {"title": title, "visibility": "public", "madeForKids": False,
                                                "containsSyntheticMedia": False}}],
        "publishNow": True,
        "metadata": {"specId": spec.get("id")},
    }
    return body, warnings


def publish_tiktok(http: Http, spec: dict, assets) -> dict:
    z = Zernio(http)
    body, warnings = tiktok_body(spec, assets, z.account_id("tiktok"))
    result = z.create_and_wait(body, "tiktok", idempotency_key(spec, "tiktok"))
    result["warnings"] = warnings
    return result


def publish_youtube(http: Http, spec: dict, assets) -> dict:
    if assets.kind != "video":
        raise PermanentError("YouTube only takes video formats")
    z = Zernio(http)
    body, warnings = youtube_body(spec, assets, z.account_id("youtube"))
    result = z.create_and_wait(body, "youtube", idempotency_key(spec, "youtube"))
    result["warnings"] = warnings
    return result
