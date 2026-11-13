"""LinkedIn personal profile posts via the self-serve "Share on LinkedIn" product (scope w_member_social).

Versioned REST API, docs at learn.microsoft.com/linkedin/marketing/community-management/shares/
  Carousel -> PDF document post: documents?action=initializeUpload, PUT the PDF, wait AVAILABLE, POST /rest/posts.
  Video: videos?action=initializeUpload, PUT each part, finalizeUpload with the ETags, wait AVAILABLE, POST /rest/posts.
Self-serve tokens last 60 days and cannot be refreshed. LINKEDIN_TOKEN_EXPIRES drives the reminder.
"""
from __future__ import annotations

import os
from datetime import date, datetime
from urllib.parse import quote

from . import captions
from .common import PermanentError, PublishError, env
from .http import Http

API = "https://api.linkedin.com/rest"
# LinkedIn supports each monthly version for at least a year. 202510 was at the end of its window in
# Nov 2026 (202511 sunsets 16 Nov 2026), so default to 202610. Override with the LINKEDIN_VERSION env var.
LINKEDIN_VERSION = os.environ.get("LINKEDIN_VERSION") or "202610"
POLL_INTERVAL = 10
DOCUMENT_TIMEOUT = 300
VIDEO_TIMEOUT = 600
MAX_DOCUMENT_BYTES = 100 * 1024 * 1024
MIN_VIDEO_BYTES = 75 * 1024
MAX_VIDEO_BYTES = 500 * 1024 * 1024


def token_expires_at() -> date | None:
    raw = os.environ.get("LINKEDIN_TOKEN_EXPIRES", "").strip()
    if not raw:
        return None
    try:
        return date.fromisoformat(raw[:10])
    except ValueError:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).date()


def days_left(today: date | None = None) -> int | None:
    exp = token_expires_at()
    if exp is None:
        return None
    return (exp - (today or date.today())).days


def feed_url(urn: str) -> str:
    return f"https://www.linkedin.com/feed/update/{urn}/"


class LinkedIn:
    def __init__(self, http: Http, token: str | None = None, person: str | None = None):
        self.http = http
        self.token = token or env("LINKEDIN_ACCESS_TOKEN", http.dry_run)
        person = person or os.environ.get("LINKEDIN_PERSON_URN", "").strip() or self.whoami()
        self.person = person if person.startswith("urn:li:") or person.startswith("<") else f"urn:li:person:{person}"

    def whoami(self) -> str:
        """The member id behind the token (OpenID userinfo `sub`), so LINKEDIN_PERSON_URN is optional."""
        r = self.http.request("GET", "https://api.linkedin.com/v2/userinfo",
                              headers={"Authorization": f"Bearer {self.token}"}, dry={"sub": "<member id>"})
        sub = self.http.check(r, "LinkedIn userinfo").json().get("sub")
        if not sub:
            raise PublishError("LinkedIn userinfo returned no member id. The token needs the openid and profile scopes.")
        return str(sub)

    def _headers(self, content_type: str | None = "application/json") -> dict:
        h = {"Authorization": f"Bearer {self.token}", "Linkedin-Version": LINKEDIN_VERSION,
             "X-Restli-Protocol-Version": "2.0.0"}
        if content_type:
            h["Content-Type"] = content_type
        return h

    def _post(self, path: str, body: dict, what: str, dry: dict, final: bool = False, dry_headers=None):
        r = self.http.request("POST", f"{API}/{path}", headers=self._headers(), json_body=body, timeout=120,
                              final=final, dry=dry, dry_status=201 if final else 200, dry_headers=dry_headers)
        return self.http.check(r, what, final=final)

    def wait_available(self, kind: str, urn: str, timeout: float) -> str:
        url = f"{API}/{kind}/{quote(urn, safe='')}"

        def check():
            r = self.http.request("GET", url, headers=self._headers(None), dry={"status": "AVAILABLE"})
            status = self.http.check(r, f"LinkedIn {kind} status").json().get("status")
            if status == "AVAILABLE":
                return True, status
            if status == "PROCESSING_FAILED":
                raise PublishError(f"LinkedIn could not process {urn} (PROCESSING_FAILED)")
            return False, status
        return self.http.poll(check, interval=POLL_INTERVAL, timeout=timeout, what=f"LinkedIn {kind} processing")

    def upload_document(self, path) -> str:
        data = path.read_bytes()
        if len(data) > MAX_DOCUMENT_BYTES:
            raise PermanentError(f"{path.name} is over LinkedIn's 100 MB document limit")
        init = self._post("documents?action=initializeUpload", {"initializeUploadRequest": {"owner": self.person}},
                          "LinkedIn document initializeUpload",
                          dry={"value": {"uploadUrl": "https://www.linkedin.com/dms-uploads/DRYRUN-DOC",
                                         "document": "urn:li:document:DRYRUN"}}).json()["value"]
        r = self.http.request("PUT", init["uploadUrl"], headers={"Authorization": f"Bearer {self.token}"},
                              data=data, describe=f"<{len(data)} bytes from {path}>", timeout=300, dry_status=201)
        self.http.check(r, "LinkedIn document upload")
        urn = init["document"]
        self.wait_available("documents", urn, DOCUMENT_TIMEOUT)
        return urn

    def upload_video(self, path) -> str:
        data = path.read_bytes()
        size = len(data)
        if not MIN_VIDEO_BYTES <= size <= MAX_VIDEO_BYTES:
            raise PermanentError(f"{path.name} is {size} bytes, LinkedIn takes 75 KB to 500 MB")
        dry_parts = [{"uploadUrl": f"https://www.linkedin.com/dms-uploads/DRYRUN-VIDEO/part{i}",
                      "firstByte": start, "lastByte": min(start + 4194303, size - 1)}
                     for i, start in enumerate(range(0, max(size, 1), 4194304))]
        init = self._post("videos?action=initializeUpload",
                          {"initializeUploadRequest": {"owner": self.person, "fileSizeBytes": size,
                                                       "uploadCaptions": False, "uploadThumbnail": False}},
                          "LinkedIn video initializeUpload",
                          dry={"value": {"video": "urn:li:video:DRYRUN", "uploadToken": "",
                                         "uploadInstructions": dry_parts}}).json()["value"]
        etags = []
        for n, part in enumerate(init.get("uploadInstructions") or [], 1):
            first, last = int(part["firstByte"]), int(part["lastByte"])
            chunk = data[first:last + 1]
            r = self.http.request("PUT", part["uploadUrl"], headers={"Content-Type": "application/octet-stream"},
                                  data=chunk, describe=f"<bytes {first} to {last} of {path}>", timeout=300,
                                  dry_headers={"ETag": f"dry-etag-{n}"})
            self.http.check(r, f"LinkedIn video part {n} upload")
            etag = (r.headers.get("ETag") or "").strip().strip('"')
            if not etag:
                raise PublishError(f"LinkedIn video part {n}: no ETag in the upload response")
            etags.append(etag)
        if not etags:
            raise PublishError("LinkedIn video initializeUpload returned no upload instructions")
        self._post("videos?action=finalizeUpload",
                   {"finalizeUploadRequest": {"video": init["video"], "uploadToken": init.get("uploadToken", ""),
                                              "uploadedPartIds": etags}},
                   "LinkedIn video finalizeUpload", dry={})
        self.wait_available("videos", init["video"], VIDEO_TIMEOUT)
        return init["video"]

    def create_post(self, commentary: str, media_urn: str, title: str) -> str:
        body = {
            "author": self.person,
            "commentary": captions.linkedin_little_text(commentary),
            "visibility": "PUBLIC",
            "distribution": {"feedDistribution": "MAIN_FEED", "targetEntities": [],
                             "thirdPartyDistributionChannels": []},
            "content": {"media": {"title": title, "id": media_urn}},
            "lifecycleState": "PUBLISHED",
            "isReshareDisabledByAuthor": False,
        }
        r = self._post("posts", body, "LinkedIn create post", dry={}, final=True,
                       dry_headers={"x-restli-id": "urn:li:share:DRYRUN"})
        urn = r.headers.get("x-restli-id")
        if not urn:
            raise PublishError("LinkedIn create post: no x-restli-id header in the response")
        return urn


def publish(http: Http, spec: dict, assets) -> dict:
    text, warnings = captions.linkedin_commentary(spec)
    title, w = captions.linkedin_title(spec)
    warnings += w
    li = LinkedIn(http)
    if assets.kind == "carousel":
        if not assets.pdf:
            raise PublishError(f"no carousel.pdf in {assets.dir}")
        media = li.upload_document(assets.pdf)
    else:
        media = li.upload_video(assets.video)
    urn = li.create_post(text, media, title)
    return {"id": urn, "url": feed_url(urn), "warnings": warnings}
