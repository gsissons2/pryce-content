"""Publisher tests. No network: `requests.request` is replaced by a scripted fake.

Run: python -m unittest tests.test_publish -v
"""
import contextlib
import io
import json
import os
import re
import tempfile
import unittest
from datetime import date, datetime, timezone
from pathlib import Path
from unittest import mock

from publish import captions, cleanup, instagram, linkedin, media, run as runmod, zernio
from publish.common import Assets, PermanentError, PublishError, SkipForNow, UncertainError
from publish.http import FakeResponse, Http

NOW = datetime(2026, 11, 20, 0, 0, tzinfo=timezone.utc)


def R(status=200, body=None, headers=None):
    return FakeResponse(status, body, headers)


class Transport:
    """Stands in for requests.request. Routes are (method, url regex, responses...).
    With several responses they are used in order and the last one repeats."""

    def __init__(self):
        self.routes, self.calls = [], []

    def on(self, method, pattern, *responses):
        self.routes.append((method, re.compile(pattern), list(responses)))
        return self

    def __call__(self, method, url, **kw):
        self.calls.append(dict(kw, method=method, url=url))
        for m, pat, resps in self.routes:
            if m == method and pat.search(url):
                r = resps.pop(0) if len(resps) > 1 else resps[0]
                return r(kw) if callable(r) else r
        raise AssertionError(f"unexpected request {method} {url}")

    def find(self, method, pattern):
        return [c for c in self.calls if c["method"] == method and re.search(pattern, c["url"])]


def http():
    return Http(sleep=lambda s: None)


ENV = {
    "IG_USER_ID": "1784", "IG_ACCESS_TOKEN": "igtoken",
    "LINKEDIN_ACCESS_TOKEN": "litoken", "LINKEDIN_PERSON_URN": "urn:li:person:abc",
    "ZERNIO_API_KEY": "zkey", "ZERNIO_TIKTOK_ACCOUNT_ID": "tt1", "ZERNIO_YOUTUBE_ACCOUNT_ID": "yt1",
    "IG_REELS_UPLOAD": "",
}


def make_spec(sid="2026-11-17-fernleaf-cafe", fmt="redesign-carousel", schedule=None, **extra):
    spec = {
        "id": sid, "format": fmt,
        "schedule": schedule if schedule is not None else {"instagram": "2026-11-17T19:00:00+11:00"},
        "captions": {
            "instagram": "Is this café open? (concept) #webdesign #cafe",
            "tiktok": "Can you tell if this café is open?\nConcept redesign. #webdesign",
            "youtube": {"title": "Is this café open right now?", "description": "Concept redesign."},
            "linkedin": "Concept redesign (fictional). Hours first, #webdesign.",
        },
        "alt": [f"Alt {i}" for i in range(1, 6)],
        "data": {"business": "Fernleaf Café", "hook": "Is this café open right now?"},
        "published": {},
    }
    spec.update(extra)
    return spec


def make_assets(tmp: Path, kind="carousel", video_bytes=200_000) -> Assets:
    d = tmp / "out" / "x"
    d.mkdir(parents=True, exist_ok=True)
    if kind == "carousel":
        for i in range(1, 6):
            (d / f"slide-{i:02d}.jpg").write_bytes(b"\xff\xd8jpeg" + bytes([i]) * 100)
        (d / "carousel.pdf").write_bytes(b"%PDF-1.7 fake")
    else:
        (d / "video.mp4").write_bytes(b"\x00" * video_bytes)
        (d / "cover.jpg").write_bytes(b"\xff\xd8cover")
    a = Assets.from_dir({"id": "x", "format": "redesign-carousel" if kind == "carousel" else "redesign-video"}, d)
    for p in a.public_files():
        a.urls[p.name] = f"https://gsissons2.github.io/pryce-content/media/x/{p.name}?v=abc"
    return a


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.t = Transport()
        patches = [mock.patch("publish.http.requests.request", self.t), mock.patch.dict(os.environ, ENV)]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)


# Instagram -------------------------------------------------------------------
class TestInstagram(Base):
    def limit(self, used=3, total=100):
        return R(200, {"data": [{"quota_usage": used, "config": {"quota_total": total, "quota_duration": 86400}}]})

    def test_carousel(self):
        a = make_assets(self.tmp)
        ids = iter(["c1", "c2", "c3", "c4", "c5", "CAR"])
        self.t.on("GET", r"/1784/content_publishing_limit$", self.limit())
        self.t.on("POST", r"/1784/media$", lambda kw: R(200, {"id": next(ids)}))
        self.t.on("GET", r"/CAR$", R(200, {"status_code": "IN_PROGRESS"}), R(200, {"status_code": "FINISHED"}))
        self.t.on("POST", r"/1784/media_publish$", R(200, {"id": "M1"}))
        self.t.on("GET", r"/M1$", R(200, {"permalink": "https://www.instagram.com/p/abc/"}))
        res = instagram.publish(http(), make_spec(), a)

        self.assertEqual(res["id"], "M1")
        self.assertEqual(res["url"], "https://www.instagram.com/p/abc/")
        posts = self.t.find("POST", r"/media$")
        self.assertTrue(all(c["url"].startswith("https://graph.instagram.com/") for c in self.t.calls))
        self.assertEqual(self.t.calls[0]["headers"]["Authorization"], "Bearer igtoken")
        for i, c in enumerate(posts[:5]):
            self.assertEqual(c["json"]["image_url"], a.urls[f"slide-0{i + 1}.jpg"])
            self.assertIs(c["json"]["is_carousel_item"], True)
            self.assertEqual(c["json"]["alt_text"], f"Alt {i + 1}")
            self.assertNotIn("caption", c["json"])
        carousel = posts[5]["json"]
        self.assertEqual(carousel["media_type"], "CAROUSEL")
        self.assertEqual(carousel["children"], "c1,c2,c3,c4,c5")
        self.assertIn("#webdesign", carousel["caption"])
        self.assertEqual(self.t.find("POST", r"media_publish$")[0]["json"], {"creation_id": "CAR"})
        self.assertEqual(self.t.find("GET", r"/CAR$")[0]["params"], {"fields": "status_code,status"})

    def reel_routes(self, container=None):
        self.t.on("GET", r"content_publishing_limit$", self.limit())
        self.t.on("POST", r"/1784/media$", *(container or [R(200, {
            "id": "REEL", "uri": "https://rupload.facebook.com/ig-api-upload/v27.0/REEL"})]))
        self.t.on("POST", r"^https://rupload\.facebook\.com/ig-api-upload/", R(200, {"success": True,
                                                                                    "message": "Upload successful."}))
        self.t.on("GET", r"/REEL$", R(200, {"status_code": "IN_PROGRESS"}), R(200, {"status_code": "FINISHED"}))
        self.t.on("POST", r"media_publish$", R(200, {"id": "M2"}))
        self.t.on("GET", r"/M2$", R(200, {"permalink": "https://www.instagram.com/reel/xyz/"}))

    def test_reel_resumable_upload(self):
        a = make_assets(self.tmp, "video")
        self.reel_routes()
        res = instagram.publish(http(), make_spec(fmt="redesign-video"), a)
        body = self.t.find("POST", r"/1784/media$")[0]["json"]
        self.assertEqual(body["media_type"], "REELS")
        self.assertEqual(body["upload_type"], "resumable")
        self.assertNotIn("video_url", body)
        self.assertEqual(body["cover_url"], a.urls["cover.jpg"])
        self.assertIs(body["share_to_feed"], True)
        up = self.t.find("POST", r"rupload")[0]
        self.assertEqual(up["url"], "https://rupload.facebook.com/ig-api-upload/v27.0/REEL")
        self.assertEqual(up["headers"], {"Authorization": "OAuth igtoken", "offset": "0",
                                         "file_size": str(a.video.stat().st_size)})
        self.assertEqual(up["data"], a.video.read_bytes())
        self.assertEqual(self.t.find("POST", r"media_publish$")[0]["json"], {"creation_id": "REEL"})
        self.assertEqual(res, {"id": "M2", "url": "https://www.instagram.com/reel/xyz/", "warnings": []})

    def test_reel_url_mode(self):
        a = make_assets(self.tmp, "video")
        self.reel_routes([R(200, {"id": "REEL"})])
        with mock.patch.dict(os.environ, {"IG_REELS_UPLOAD": "url"}):
            instagram.publish(http(), make_spec(fmt="redesign-video"), a)
        body = self.t.find("POST", r"/1784/media$")[0]["json"]
        self.assertEqual(body["video_url"], a.urls["video.mp4"])
        self.assertNotIn("upload_type", body)
        self.assertFalse(self.t.find("POST", r"rupload"))

    def test_reel_falls_back_to_url_when_resumable_refused(self):
        a = make_assets(self.tmp, "video")
        refused = R(400, {"error": {"message": "upload_type not supported", "code": 100}})
        self.reel_routes([refused, R(200, {"id": "REEL"})])
        with contextlib.redirect_stdout(io.StringIO()):
            res = instagram.publish(http(), make_spec(fmt="redesign-video"), a)
        first, second = [c["json"] for c in self.t.find("POST", r"/1784/media$")]
        self.assertEqual(first["upload_type"], "resumable")
        self.assertEqual(second["video_url"], a.urls["video.mp4"])
        self.assertTrue(any("used video_url" in w for w in res["warnings"]))
        self.assertEqual(len(self.t.find("POST", r"media_publish$")), 1)

    def test_rupload_never_sends_token_to_other_hosts(self):
        a = make_assets(self.tmp, "video")
        self.reel_routes([R(200, {"id": "REEL", "uri": "https://evil.example/steal"})])
        instagram.publish(http(), make_spec(fmt="redesign-video"), a)
        self.assertEqual(self.t.find("POST", r"rupload")[0]["url"],
                         f"https://rupload.facebook.com/ig-api-upload/{instagram.API_VERSION}/REEL")

    def test_reel_error_reports_details(self):
        a = make_assets(self.tmp, "video")
        self.t.on("GET", r"content_publishing_limit$", self.limit())
        self.t.on("POST", r"/media$", R(200, {"id": "REEL"}))
        self.t.on("POST", r"rupload", R(200, {"success": True}))
        self.t.on("GET", r"/REEL$", R(200, {"status_code": "ERROR", "status": "Error: video codec not supported"}))
        with self.assertRaisesRegex(PublishError, "codec not supported"):
            instagram.publish(http(), make_spec(fmt="redesign-video"), a)
        self.assertFalse(self.t.find("POST", r"media_publish$"))

    def test_limit_used_up_skips(self):
        self.t.on("GET", r"content_publishing_limit$", self.limit(100, 100))
        with self.assertRaises(SkipForNow):
            instagram.publish(http(), make_spec(), make_assets(self.tmp))
        self.assertFalse(self.t.find("POST", "."))

    def test_more_than_ten_slides_is_permanent(self):
        ig = instagram.Instagram(http())
        with self.assertRaises(PermanentError):
            ig.post_carousel([f"https://x/{i}.jpg" for i in range(11)], "c")

    def test_publish_timeout_is_uncertain(self):
        import requests
        self.t.on("GET", r"content_publishing_limit$", self.limit())
        self.t.on("POST", r"/media$", R(200, {"id": "C"}))
        self.t.on("GET", r"/C$", R(200, {"status_code": "FINISHED"}))

        def boom(kw):
            raise requests.exceptions.ReadTimeout("slow")
        self.t.on("POST", r"media_publish$", boom)
        with self.assertRaises(UncertainError):
            instagram.Instagram(http()).post_reel("c", video_url="https://x/v.mp4", mode="url")

    def test_refresh_token(self):
        self.t.on("GET", r"graph\.instagram\.com/refresh_access_token$",
                  R(200, {"access_token": "igtoken", "token_type": "bearer", "expires_in": 5183944}))
        with contextlib.redirect_stdout(io.StringIO()) as out:
            res = instagram.refresh_token(http())
        call = self.t.calls[0]
        self.assertEqual(call["params"], {"grant_type": "ig_refresh_token", "access_token": "igtoken"})
        self.assertEqual(res["expires_in"], 5183944)
        self.assertFalse(res["changed"])
        self.assertIn("Expires", out.getvalue())
        self.assertNotIn("igtoken", out.getvalue())


# LinkedIn --------------------------------------------------------------------
class TestLinkedIn(Base):
    def test_document_post(self):
        a = make_assets(self.tmp)
        self.t.on("POST", r"/rest/documents\?action=initializeUpload$",
                  R(200, {"value": {"uploadUrl": "https://www.linkedin.com/dms-uploads/D1/doc?ut=1",
                                    "document": "urn:li:document:D1"}}))
        self.t.on("PUT", r"dms-uploads/D1/doc", R(201))
        self.t.on("GET", r"/rest/documents/urn%3Ali%3Adocument%3AD1$", R(200, {"status": "PROCESSING"}),
                  R(200, {"status": "AVAILABLE"}))
        self.t.on("POST", r"/rest/posts$", R(201, {}, {"x-restli-id": "urn:li:share:999"}))
        res = linkedin.publish(http(), make_spec(), a)

        self.assertEqual(res["id"], "urn:li:share:999")
        self.assertEqual(res["url"], "https://www.linkedin.com/feed/update/urn:li:share:999/")
        init = self.t.find("POST", r"documents")[0]
        self.assertEqual(init["json"], {"initializeUploadRequest": {"owner": "urn:li:person:abc"}})
        for c in self.t.find("POST", r"/rest/"):
            self.assertEqual(c["headers"]["Linkedin-Version"], linkedin.LINKEDIN_VERSION)
            self.assertEqual(c["headers"]["X-Restli-Protocol-Version"], "2.0.0")
            self.assertEqual(c["headers"]["Authorization"], "Bearer litoken")
        self.assertRegex(linkedin.LINKEDIN_VERSION, r"^20\d{4}$")
        put = self.t.find("PUT", r"dms-uploads")[0]
        self.assertEqual(put["data"], a.pdf.read_bytes())
        post = self.t.find("POST", r"/rest/posts$")[0]["json"]
        self.assertEqual(post["author"], "urn:li:person:abc")
        self.assertEqual(post["content"]["media"], {"title": "Is this café open right now?", "id": "urn:li:document:D1"})
        self.assertEqual(post["commentary"], "Concept redesign \\(fictional\\). Hours first, {hashtag|\\#|webdesign}.")
        self.assertEqual(post["lifecycleState"], "PUBLISHED")
        self.assertEqual(post["visibility"], "PUBLIC")
        self.assertEqual(post["distribution"]["feedDistribution"], "MAIN_FEED")

    def test_video_post(self):
        size = 5_000_000
        a = make_assets(self.tmp, "video", video_bytes=size)
        self.t.on("POST", r"videos\?action=initializeUpload$", R(200, {"value": {
            "video": "urn:li:video:V1", "uploadToken": "tok",
            "uploadInstructions": [
                {"uploadUrl": "https://www.linkedin.com/dms-uploads/V1/p0", "firstByte": 0, "lastByte": 4194303},
                {"uploadUrl": "https://www.linkedin.com/dms-uploads/V1/p1", "firstByte": 4194304, "lastByte": size - 1},
            ]}}))
        self.t.on("PUT", r"/V1/p0$", R(200, None, {"ETag": '"etag-one"'}))
        self.t.on("PUT", r"/V1/p1$", R(200, None, {"etag": "etag-two"}))
        self.t.on("POST", r"videos\?action=finalizeUpload$", R(200, {}))
        self.t.on("GET", r"/rest/videos/urn%3Ali%3Avideo%3AV1$", R(200, {"status": "PROCESSING"}),
                  R(200, {"status": "AVAILABLE"}))
        self.t.on("POST", r"/rest/posts$", R(201, {}, {"x-restli-id": "urn:li:ugcPost:5"}))
        res = linkedin.publish(http(), make_spec(fmt="redesign-video"), a)

        init = self.t.find("POST", r"initializeUpload")[0]["json"]["initializeUploadRequest"]
        self.assertEqual(init["fileSizeBytes"], size)
        self.assertEqual(init["owner"], "urn:li:person:abc")
        puts = self.t.find("PUT", r"dms-uploads")
        self.assertEqual([len(p["data"]) for p in puts], [4194304, size - 4194304])
        self.assertEqual(puts[0]["headers"]["Content-Type"], "application/octet-stream")
        fin = self.t.find("POST", r"finalizeUpload")[0]["json"]["finalizeUploadRequest"]
        self.assertEqual(fin, {"video": "urn:li:video:V1", "uploadToken": "tok",
                               "uploadedPartIds": ["etag-one", "etag-two"]})
        post = self.t.find("POST", r"/rest/posts$")[0]["json"]
        self.assertEqual(post["content"]["media"]["id"], "urn:li:video:V1")
        self.assertEqual(res["id"], "urn:li:ugcPost:5")

    def test_processing_failed(self):
        a = make_assets(self.tmp)
        self.t.on("POST", r"documents", R(200, {"value": {"uploadUrl": "https://u/doc", "document": "urn:li:document:D"}}))
        self.t.on("PUT", r"https://u/doc", R(201))
        self.t.on("GET", r"/rest/documents/", R(200, {"status": "PROCESSING_FAILED"}))
        with self.assertRaisesRegex(PublishError, "PROCESSING_FAILED"):
            linkedin.publish(http(), make_spec(), a)
        self.assertFalse(self.t.find("POST", r"/rest/posts$"))

    def test_server_error_on_post_is_uncertain(self):
        self.t.on("POST", r"/rest/posts$", R(503, {"message": "busy"}))
        with self.assertRaises(UncertainError):
            linkedin.LinkedIn(http()).create_post("hi", "urn:li:document:D", "t")

    def test_token_expiry(self):
        with mock.patch.dict(os.environ, {"LINKEDIN_TOKEN_EXPIRES": "2026-12-01"}):
            self.assertEqual(linkedin.token_expires_at(), date(2026, 12, 1))
            self.assertEqual(linkedin.days_left(date(2026, 11, 25)), 6)
        with mock.patch.dict(os.environ, {"LINKEDIN_TOKEN_EXPIRES": ""}):
            self.assertIsNone(linkedin.days_left())


# Zernio ----------------------------------------------------------------------
class TestZernio(Base):
    def published(self, platform, url="https://www.tiktok.com/@prycedigital/photo/1"):
        return R(201, {"message": "ok", "post": {"_id": "P1", "status": "published", "platforms": [
            {"platform": platform, "status": "published", "platformPostId": "1", "platformPostUrl": url}]}})

    def test_tiktok_photo_post(self):
        a = make_assets(self.tmp)
        self.t.on("POST", r"^https://zernio\.com/api/v1/posts$", self.published("tiktok"))
        res = zernio.publish_tiktok(http(), make_spec(), a)
        call = self.t.calls[0]
        self.assertEqual(call["headers"]["Authorization"], "Bearer zkey")
        body = call["json"]
        self.assertEqual(body["platforms"], [{"platform": "tiktok", "accountId": "tt1"}])
        self.assertEqual([m["type"] for m in body["mediaItems"]], ["image"] * 5)
        self.assertEqual(body["mediaItems"][0]["url"], a.urls["slide-01.jpg"])
        s = body["tiktokSettings"]
        self.assertEqual(s["media_type"], "photo")
        self.assertEqual(s["privacy_level"], "PUBLIC_TO_EVERYONE")
        self.assertTrue(s["content_preview_confirmed"] and s["express_consent_given"])
        self.assertIn("#webdesign", s["description"])
        self.assertEqual(body["content"], "Can you tell if this café is open?")
        self.assertIs(body["publishNow"], True)
        self.assertNotIn("scheduledFor", body)
        self.assertEqual(res["id"], "P1")
        self.assertEqual(res["url"], "https://www.tiktok.com/@prycedigital/photo/1")

    def test_tiktok_video_waits_for_publishing(self):
        a = make_assets(self.tmp, "video")
        self.t.on("POST", r"/api/v1/posts$", R(201, {"post": {"_id": "P2", "status": "publishing",
                                                             "platforms": [{"platform": "tiktok", "status": "publishing"}]}}))
        self.t.on("GET", r"/api/v1/posts/P2$",
                  R(200, {"post": {"_id": "P2", "platforms": [{"platform": "tiktok", "status": "publishing"}]}}),
                  R(200, {"post": {"_id": "P2", "platforms": [{"platform": "tiktok", "status": "published",
                                                               "platformPostUrl": "https://www.tiktok.com/v/2"}]}}))
        res = zernio.publish_tiktok(http(), make_spec(fmt="redesign-video"), a)
        body = self.t.calls[0]["json"]
        self.assertEqual(body["mediaItems"], [{"type": "video", "url": a.urls["video.mp4"]}])
        self.assertNotEqual(body["tiktokSettings"].get("media_type"), "photo")
        self.assertIn("#webdesign", body["content"])
        self.assertEqual(res["url"], "https://www.tiktok.com/v/2")

    def test_youtube_short(self):
        a = make_assets(self.tmp, "video")
        self.t.on("POST", r"/api/v1/posts$", self.published("youtube", "https://youtube.com/shorts/abc"))
        spec = make_spec(fmt="redesign-video")
        spec["captions"]["youtube"]["title"] = "T" * 150
        res = zernio.publish_youtube(http(), spec, a)
        body = self.t.calls[0]["json"]
        target = body["platforms"][0]
        self.assertEqual(target["platform"], "youtube")
        self.assertEqual(target["accountId"], "yt1")
        psd = target["platformSpecificData"]
        self.assertLessEqual(len(psd["title"]), 100)
        self.assertEqual(psd["visibility"], "public")
        self.assertIs(psd["madeForKids"], False)
        self.assertEqual(body["content"], "Concept redesign.")
        self.assertTrue(any("title cut" in w for w in res["warnings"]))
        self.assertEqual(res["url"], "https://youtube.com/shorts/abc")

    def test_youtube_rejects_carousel(self):
        with self.assertRaises(PermanentError):
            zernio.publish_youtube(http(), make_spec(), make_assets(self.tmp))
        self.assertFalse(self.t.calls)

    def test_failed_status_raises(self):
        self.t.on("POST", r"/api/v1/posts$", R(207, {"post": {"_id": "P3", "status": "failed", "platforms": [
            {"platform": "tiktok", "status": "failed", "errorMessage": "privacy level not allowed"}]}}))
        with self.assertRaisesRegex(PublishError, "privacy level not allowed"):
            zernio.publish_tiktok(http(), make_spec(), make_assets(self.tmp))


# Captions --------------------------------------------------------------------
class TestCaptions(unittest.TestCase):
    def test_linkedin_escaping(self):
        raw = r"a|b {c} @d [e] (f) <g> \h *i _j ~k #tag #my_tag"
        want = r"a\|b \{c\} \@d \[e\] \(f\) \<g\> \\h \*i \_j \~k {hashtag|\#|tag} {hashtag|\#|my\_tag}"
        self.assertEqual(captions.linkedin_little_text(raw), want)
        self.assertEqual(captions.linkedin_little_text("#x (y)", hashtags=False), r"\#x \(y\)")
        self.assertEqual(captions.linkedin_little_text("plain text, 100% ok."), "plain text, 100% ok.")

    def test_instagram_hashtag_limit(self):
        spec = make_spec()
        spec["captions"]["instagram"] = "Hi " + " ".join(f"#t{i}" for i in range(35))
        text, warnings = captions.instagram_caption(spec)
        self.assertEqual(len(captions.HASHTAG.findall(text)), 30)
        self.assertIn("#t29", text)
        self.assertNotIn("#t30", text)
        self.assertTrue(warnings)

    def test_trim_warns(self):
        spec = make_spec()
        spec["captions"]["instagram"] = "word " * 600
        text, warnings = captions.instagram_caption(spec)
        self.assertLessEqual(len(text), 2200)
        self.assertTrue(text.endswith("…"))
        self.assertTrue(any("cut to 2200" in w for w in warnings))
        spec["captions"]["linkedin"] = "x" * 3100
        text, warnings = captions.linkedin_commentary(spec)
        self.assertEqual(len(text), 3000)
        self.assertTrue(warnings)

    def test_no_warning_when_fine(self):
        self.assertEqual(captions.instagram_caption(make_spec())[1], [])
        self.assertEqual(captions.check_spec(make_spec(schedule={"instagram": "2026-11-17T19:00:00+11:00"})), {})

    def test_youtube_on_carousel_flagged(self):
        w = captions.check_spec(make_spec(schedule={"youtube": "2026-11-17T19:00:00+11:00"}))
        self.assertIn("youtube", w)


# Media hosting ---------------------------------------------------------------
class TestMedia(Base):
    def setUp(self):
        super().setUp()
        self.file = self.tmp / "slide-01.jpg"
        self.file.write_bytes(b"\xff\xd8 jpeg bytes")

    def live(self, ctype="image/jpeg"):
        return R(200, None, {"Content-Type": ctype, "Content-Length": str(self.file.stat().st_size)})

    def test_stage_files(self):
        dest = self.tmp / "_media" / "media" / "id1"
        self.assertTrue(media.stage_files([self.file], dest))
        self.assertEqual((dest / "slide-01.jpg").read_bytes(), self.file.read_bytes())
        self.assertFalse(media.stage_files([self.file], dest))  # unchanged
        (dest / "slide-09.jpg").write_bytes(b"old")
        self.assertTrue(media.stage_files([self.file], dest))   # stale extra removed
        self.assertFalse((dest / "slide-09.jpg").exists())

    def test_too_big_fails_clearly(self):
        with mock.patch.object(media, "MAX_BYTES", 5):
            with self.assertRaisesRegex(PermanentError, "MB"):
                media.stage_files([self.file], self.tmp / "d")

    def test_urls_and_wait_for_pages(self):
        a = make_assets(self.tmp)
        a.urls.clear()
        self.t.on("HEAD", r"^https://gsissons2\.github\.io/pryce-content/media/x/slide-0\d\.jpg\?v=[0-9a-f]{10}$",
                  R(404), R(200, None, {"Content-Type": "text/html"}),
                  R(200, None, {"Content-Type": "image/jpeg", "Content-Length": str(a.slides[0].stat().st_size)}))
        media.PagesHost(http()).host_assets(a)
        self.assertEqual(len(a.urls), 5)
        self.assertEqual(a.urls["slide-01.jpg"],
                         media.PAGES_BASE + "media/x/slide-01.jpg?v=" + media.blob_sha(a.slides[0].read_bytes())[:10])
        self.assertGreaterEqual(len(self.t.find("HEAD", ".")), 7)  # 404, html, then image for each

    def test_pages_never_ready_times_out(self):
        a = make_assets(self.tmp)
        self.t.on("HEAD", r"github\.io", R(404))
        with self.assertRaisesRegex(PublishError, "Pages"):
            media.PagesHost(http()).host_assets(a)

    def test_is_live_needs_matching_type_and_size(self):
        self.t.on("HEAD", r"a$", self.live())
        self.t.on("HEAD", r"b$", self.live("video/mp4"))
        self.t.on("HEAD", r"c$", R(200, None, {"Content-Type": "image/jpeg", "Content-Length": "1"}))
        size = self.file.stat().st_size
        self.assertTrue(media.is_live(http(), "https://x/a", "image/jpeg", size))
        self.assertFalse(media.is_live(http(), "https://x/b", "image/jpeg", size))
        self.assertFalse(media.is_live(http(), "https://x/c", "image/jpeg", size))


class TestMediaBranch(unittest.TestCase):
    """Real git against a local bare remote: create the orphan branch, push, check it out again."""

    def git(self, *args, cwd):
        import subprocess
        return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True).stdout

    def test_checkout_create_push_and_reuse(self):
        tmp = Path(tempfile.mkdtemp())
        remote, repo = tmp / "remote.git", tmp / "repo"
        self.git("init", "-q", "--bare", str(remote), cwd=tmp)
        self.git("init", "-q", "-b", "main", str(repo), cwd=tmp)
        (repo / "README.md").write_text("main")
        self.git("add", ".", cwd=repo)
        self.git("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "main", cwd=repo)
        self.git("remote", "add", "origin", str(remote), cwd=repo)
        self.git("push", "-q", "origin", "main", cwd=repo)

        self.assertEqual(media.checkout(repo / "_media", repo), "created")
        self.assertEqual(sorted(p.name for p in (repo / "_media").iterdir()), [".git", ".nojekyll"])
        (repo / "_media" / "media" / "id1").mkdir(parents=True)
        (repo / "_media" / "media" / "id1" / "slide-01.jpg").write_bytes(b"jpg")
        self.assertTrue(media.push(repo / "_media", "media: id1", sleep=lambda s: None))
        self.assertFalse(media.push(repo / "_media", "nothing", sleep=lambda s: None))
        files = self.git("ls-tree", "-r", "--name-only", "media", cwd=remote).split()
        self.assertEqual(files, [".nojekyll", "media/id1/slide-01.jpg"])
        self.assertEqual(self.git("ls-tree", "-r", "--name-only", "main", cwd=remote).split(), ["README.md"])

        clone = tmp / "clone"
        self.git("clone", "-q", str(remote), str(clone), cwd=tmp)
        self.assertEqual(media.checkout(clone / "_media", clone), "existing")
        self.assertTrue((clone / "_media" / "media" / "id1" / "slide-01.jpg").is_file())


# Runner ----------------------------------------------------------------------
class FakeHost:
    def __init__(self, fail=None):
        self.calls, self.fail = 0, fail

    def host_assets(self, assets):
        self.calls += 1
        if self.fail:
            raise self.fail
        for p in assets.public_files():
            assets.urls[p.name] = f"https://example.test/{p.name}"
        return assets.urls


class TestRun(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.queue = self.tmp / "queue"
        self.out = self.tmp / "out"
        self.queue.mkdir()
        self.calls = []
        self.host = FakeHost()

    def add(self, spec, render=True):
        path = self.queue / f"{spec['id']}.json"
        path.write_text(json.dumps(spec))
        if render:
            d = self.out / spec["id"]
            d.mkdir(parents=True)
            if spec["format"].endswith("carousel"):
                for i in range(1, 6):
                    (d / f"slide-{i:02d}.jpg").write_bytes(b"jpg")
                (d / "carousel.pdf").write_bytes(b"pdf")
            else:
                (d / "video.mp4").write_bytes(b"mp4")
                (d / "cover.jpg").write_bytes(b"jpg")
        return path

    def publisher(self, name, behaviour=None):
        def fn(http, spec, assets):
            self.calls.append((name, spec["id"]))
            if behaviour:
                return behaviour(spec, assets)
            return {"id": f"{name}-id", "url": f"https://{name}.test/post"}
        return fn

    def go(self, now=NOW, publishers=None, **kw):
        pubs = {p: self.publisher(p) for p in ("instagram", "tiktok", "youtube", "linkedin")}
        pubs.update(publishers or {})
        with mock.patch.dict(runmod.PUBLISHERS, pubs), contextlib.redirect_stdout(io.StringIO()):
            return runmod.run(self.queue, self.out, now, http=object(), media_host_factory=lambda h: self.host, **kw)

    def read(self, path):
        return json.loads(path.read_text())

    def test_due_selection(self):
        spec = make_spec(schedule={
            "instagram": "2026-11-19T19:00:00+11:00",   # past
            "tiktok": "2026-11-21T19:00:00+11:00",      # future
            "linkedin": "2026-11-18T08:15:00+11:00",    # past but already published
            "youtube": "2026-11-18T08:15:00+11:00",     # past but failed 3 times
        }, published={"linkedin": {"id": "x", "url": "u", "at": "2026-11-17T21:15:00Z"}},
            failed={"youtube": {"at": "t", "error": "e", "history": [{}, {}, {}]}})
        self.add(spec)
        due = runmod.due_slots(runmod.load_specs(self.queue), NOW)
        self.assertEqual([d[2] for d in due], ["instagram"])
        self.assertEqual(runmod.due_slots(runmod.load_specs(self.queue), NOW, only="tiktok"), [])
        later = datetime(2026, 11, 22, tzinfo=timezone.utc)
        self.assertEqual([d[2] for d in runmod.due_slots(runmod.load_specs(self.queue), later)],
                         ["instagram", "tiktok"])

    def test_bad_time_and_unknown_platform_are_skipped(self):
        self.add(make_spec(schedule={"instagram": "next tuesday", "myspace": "2026-11-01T00:00:00Z",
                                     "tiktok": "2026-11-01T00:00:00"}))  # no offset
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(runmod.due_slots(runmod.load_specs(self.queue), NOW), [])

    def test_publishes_and_is_idempotent(self):
        path = self.add(make_spec(schedule={"instagram": "2026-11-19T19:00:00+11:00",
                                            "linkedin": "2026-11-19T20:00:00+11:00"}))
        s1 = self.go()
        self.assertEqual(sorted(p["platform"] for p in s1["published"]), ["instagram", "linkedin"])
        spec = self.read(path)
        self.assertEqual(spec["published"]["instagram"]["id"], "instagram-id")
        self.assertEqual(spec["published"]["instagram"]["url"], "https://instagram.test/post")
        self.assertIn("at", spec["published"]["instagram"])
        s2 = self.go()
        self.assertEqual(s2["published"], [])
        self.assertEqual(len(self.calls), 2)
        self.assertEqual(self.host.calls, 1)  # LinkedIn does not need hosting, Instagram did once

    def test_each_success_is_written_before_the_next_platform(self):
        path = self.add(make_spec(schedule={"instagram": "2026-11-19T19:00:00+11:00",
                                            "linkedin": "2026-11-19T20:00:00+11:00"}))

        def linkedin_checks_disk(spec, assets):
            self.assertIn("instagram", self.read(path)["published"])
            raise RuntimeError("crash after Instagram went live")
        s = self.go(publishers={"linkedin": self.publisher("linkedin", linkedin_checks_disk)})
        spec = self.read(path)
        self.assertIn("instagram", spec["published"])
        self.assertTrue(spec["failed"]["linkedin"]["gave_up"])  # unexpected error: never retried blindly
        self.assertEqual(s["gave_up"][0]["platform"], "linkedin")

    def test_retry_counting_then_give_up(self):
        path = self.add(make_spec())

        def flaky(spec, assets):
            raise PublishError("HTTP 500 from the platform")
        pubs = {"instagram": self.publisher("instagram", flaky)}
        for n in (1, 2):
            s = self.go(publishers=pubs)
            f = self.read(path)["failed"]["instagram"]
            self.assertEqual(len(f["history"]), n)
            self.assertNotIn("gave_up", f)
            self.assertEqual(s["gave_up"], [])
        s = self.go(publishers=pubs)
        f = self.read(path)["failed"]["instagram"]
        self.assertEqual(len(f["history"]), 3)
        self.assertTrue(f["gave_up"])
        self.assertEqual(s["gave_up"][0]["id"], "2026-11-17-fernleaf-cafe")
        self.go(publishers=pubs)
        self.assertEqual(len(self.calls), 3)  # no 4th try

    def test_success_after_a_failure(self):
        path = self.add(make_spec(failed={"instagram": {"at": "2026-11-19T00:00:00Z", "error": "timeout"}}))
        self.go()
        spec = self.read(path)
        self.assertIn("instagram", spec["published"])

    def test_spec_md_failed_shape_counts_as_one(self):
        spec = make_spec(failed={"instagram": {"at": "t", "error": "e"}})
        self.assertEqual(runmod.failure_count(spec, "instagram"), 1)
        runmod.record_failure(spec, "instagram", "again", NOW)
        self.assertEqual(runmod.failure_count(spec, "instagram"), 2)
        self.assertEqual(spec["failed"]["instagram"]["error"], "again")

    def test_permanent_and_uncertain_give_up_at_once(self):
        a = self.add(make_spec(sid="a"))
        b = self.add(make_spec(sid="b"))

        def boom(spec, assets):
            raise (PermanentError("too many slides") if spec["id"] == "a" else UncertainError("no response"))
        s = self.go(publishers={"instagram": self.publisher("instagram", boom)})
        self.assertTrue(self.read(a)["failed"]["instagram"]["gave_up"])
        self.assertTrue(self.read(b)["failed"]["instagram"]["gave_up"])
        self.assertEqual(len(s["gave_up"]), 2)

    def test_skip_is_not_a_failure(self):
        path = self.add(make_spec())

        def limit(spec, assets):
            raise SkipForNow("daily limit")
        s = self.go(publishers={"instagram": self.publisher("instagram", limit)})
        self.assertNotIn("failed", self.read(path))
        self.assertEqual(s["skipped"][0]["reason"], "daily limit")

    def test_media_upload_failure_blocks_url_platforms_only(self):
        path = self.add(make_spec(schedule={"instagram": "2026-11-19T19:00:00+11:00",
                                            "linkedin": "2026-11-19T19:00:00+11:00"}))
        self.host = FakeHost(fail=PublishError("Pages not ready"))
        self.go()
        spec = self.read(path)
        self.assertIn("linkedin", spec["published"])
        self.assertIn("media upload", spec["failed"]["instagram"]["error"])

    def test_youtube_on_carousel_gives_up(self):
        path = self.add(make_spec(schedule={"youtube": "2026-11-19T19:00:00+11:00"}))
        self.go()
        self.assertTrue(self.read(path)["failed"]["youtube"]["gave_up"])
        self.assertEqual(self.calls, [])

    def test_renders_when_output_missing(self):
        spec = make_spec()
        self.add(spec, render=False)
        seen = []

        def runner(cmd, **kw):
            seen.append(cmd)
            d = self.out / spec["id"]
            d.mkdir(parents=True)
            for i in range(1, 6):
                (d / f"slide-{i:02d}.jpg").write_bytes(b"jpg")
            return mock.Mock(returncode=0, stdout="ok", stderr="")
        self.go(runner=runner)
        self.assertEqual(seen[0][1], "engine/render.py")
        self.assertEqual(seen[0][3], "--out")
        self.assertEqual(self.calls, [("instagram", spec["id"])])

    def test_render_failure_counts_as_failure(self):
        path = self.add(make_spec(), render=False)
        self.go(runner=lambda cmd, **kw: mock.Mock(returncode=1, stdout="FAIL text overflow", stderr=""))
        f = self.read(path)["failed"]["instagram"]
        self.assertIn("render failed", f["error"])
        self.assertNotIn("gave_up", f)

    # stage-media ------------------------------------------------------------
    def fake_render(self, spec, code=0, video=False):
        calls = []

        def runner(cmd, **kw):
            calls.append(cmd)
            d = self.out / spec["id"]
            d.mkdir(parents=True, exist_ok=True)
            if video:
                (d / "video.mp4").write_bytes(b"mp4" + spec["captions"]["instagram"].encode())
                (d / "cover.jpg").write_bytes(b"jpg")
            else:
                for i in range(1, 6):
                    (d / f"slide-{i:02d}.jpg").write_bytes(b"jpg" + spec["captions"]["instagram"].encode())
                (d / "carousel.pdf").write_bytes(b"pdf")
            return mock.Mock(returncode=code, stdout="FAIL overflow" if code else "ok", stderr="")
        return runner, calls

    def stage(self, runner, live=True):
        with contextlib.redirect_stdout(io.StringIO()):
            return runmod.stage_media(self.queue, self.out, self.tmp / "_media", NOW, runner=runner,
                                      live_check=lambda u, t, s: live)

    def test_stage_media_renders_and_copies_once(self):
        spec = make_spec(schedule={"instagram": "2026-11-19T19:00:00+11:00", "linkedin": "2026-11-19T19:00:00+11:00"})
        path = self.add(spec, render=False)
        self.add(make_spec(sid="later", schedule={"instagram": "2026-12-25T09:00:00+11:00"}), render=False)
        runner, calls = self.fake_render(spec)
        res = self.stage(runner)
        staged = self.tmp / "_media" / "media" / spec["id"]
        self.assertEqual(sorted(p.name for p in staged.iterdir()),
                         ["carousel.pdf", "slide-01.jpg", "slide-02.jpg", "slide-03.jpg", "slide-04.jpg",
                          "slide-05.jpg", "spec-hash.txt"])
        self.assertEqual((res["changed"], res["deploy"], res["ids"]), (True, True, [spec["id"]]))
        self.assertEqual(len(calls), 1)  # the not-yet-due spec is not rendered
        self.assertFalse((self.tmp / "_media" / "media" / "later").exists())

        res = self.stage(runner)  # second run: already staged and live, nothing to do
        self.assertEqual((res["changed"], res["deploy"], len(calls)), (False, False, 1))
        res = self.stage(runner, live=False)  # staged but Pages not serving it: redeploy, no render
        self.assertEqual((res["changed"], res["deploy"], len(calls)), (False, True, 1))

        spec["captions"]["instagram"] = "Edited after merge"
        path.write_text(json.dumps(spec))
        res = self.stage(runner)  # spec edited: render again
        self.assertTrue(res["changed"])
        self.assertEqual(len(calls), 2)
        self.assertIn(b"Edited after merge", (staged / "slide-01.jpg").read_bytes())

    def test_stage_media_render_failure_is_recorded(self):
        spec = make_spec()
        path = self.add(spec, render=False)
        runner, _ = self.fake_render(spec, code=1)
        res = self.stage(runner)
        self.assertFalse(res["changed"])
        self.assertIn("render failed", self.read(path)["failed"]["instagram"]["error"])
        self.assertEqual(res["failed"][0]["platform"], "instagram")
        self.assertFalse((self.tmp / "_media" / "media" / spec["id"]).exists())

    def test_publish_uses_staged_media(self):
        spec = make_spec(fmt="redesign-video", schedule={"instagram": "2026-11-19T19:00:00+11:00"})
        self.add(spec, render=False)
        runner, _ = self.fake_render(spec, video=True)
        self.stage(runner)
        seen = []

        def capture(spec, assets):
            seen.append(assets)
            return {"id": "1", "url": "u"}
        self.go(publishers={"instagram": self.publisher("instagram", capture)}, media_dir=self.tmp / "_media")
        self.assertEqual(seen[0].dir, self.tmp / "_media" / "media" / spec["id"])
        self.assertEqual(seen[0].video.name, "video.mp4")
        self.assertEqual(self.host.calls, 1)

    def test_publish_skips_unstaged_spec(self):
        path = self.add(make_spec(), render=False)
        (self.tmp / "_media").mkdir()
        s = self.go(media_dir=self.tmp / "_media")
        self.assertEqual(self.calls, [])
        self.assertIn("not staged", s["skipped"][0]["reason"])
        self.assertNotIn("failed", self.read(path))

    def test_live_run_without_media_dir_only_posts_linkedin(self):
        path = self.add(make_spec(schedule={"instagram": "2026-11-19T19:00:00+11:00",
                                            "linkedin": "2026-11-19T19:00:00+11:00"}))
        pubs = {p: self.publisher(p) for p in ("instagram", "linkedin")}
        with mock.patch.dict(runmod.PUBLISHERS, pubs), contextlib.redirect_stdout(io.StringIO()):
            s = runmod.run(self.queue, self.out, NOW, http=object())
        self.assertEqual(self.calls, [("linkedin", "2026-11-17-fernleaf-cafe")])
        self.assertEqual(s["skipped"][0]["platform"], "instagram")
        self.assertNotIn("failed", self.read(path))

    def test_dry_run_sends_and_writes_nothing(self):
        carousel = make_spec(sid="c", schedule={"instagram": "2026-11-19T19:00:00+11:00",
                                                "tiktok": "2026-11-19T19:00:00+11:00",
                                                "linkedin": "2026-11-19T19:00:00+11:00"})
        video = make_spec(sid="v", fmt="redesign-video", schedule={"youtube": "2026-11-19T19:00:00+11:00",
                                                                   "instagram": "2026-11-19T19:00:00+11:00",
                                                                   "linkedin": "2026-11-19T19:00:00+11:00"})
        cp, vp = self.add(carousel), self.add(video)
        (self.out / "v" / "video.mp4").write_bytes(b"\x00" * 100_000)
        before = (cp.read_text(), vp.read_text())
        blank = {k: "" for k in ENV}
        out = io.StringIO()
        with mock.patch("publish.http.requests.request", side_effect=AssertionError("network used")), \
                mock.patch.dict(os.environ, blank), contextlib.redirect_stdout(out):
            from publish.http import Http
            s = runmod.run(self.queue, self.out, NOW, dry_run=True, http=Http(dry_run=True, out=out))
        text = out.getvalue()
        self.assertEqual((cp.read_text(), vp.read_text()), before)
        self.assertEqual(len(s["published"]), 6, text)
        self.assertNotIn("api.github.com", text)
        for expected in ("[dry-run] HEAD https://gsissons2.github.io/pryce-content/media/c/slide-01.jpg?v=",
                         "[dry-run] POST https://graph.instagram.com/", "media_publish",
                         "[dry-run] POST https://rupload.facebook.com/ig-api-upload/", '"Authorization": "OAuth ***"',
                         "[dry-run] POST https://api.linkedin.com/rest/documents?action=initializeUpload",
                         "[dry-run] POST https://api.linkedin.com/rest/videos?action=finalizeUpload",
                         "[dry-run] POST https://zernio.com/api/v1/posts", '"media_type": "photo"',
                         '"platform": "youtube"', '"Authorization": "Bearer ***"'):
            self.assertIn(expected, text)
        self.assertNotIn("igtoken", text)


class TestCleanup(unittest.TestCase):
    def test_plan(self):
        repo = Path(tempfile.mkdtemp())
        for d in ("media/2026-09-01-old", "media/2026-11-10-new", "media/undated", "previews/pr-3", "previews/pr-9"):
            (repo / d).mkdir(parents=True)
        dates = {"media/undated": datetime(2026, 8, 1, tzinfo=timezone.utc),
                 "previews/pr-3": datetime(2026, 11, 1, tzinfo=timezone.utc),
                 "previews/pr-9": datetime(2026, 11, 18, tzinfo=timezone.utc)}
        todo = cleanup.plan(repo, NOW, 45, 14, commit_date=lambda r, rel: dates.get(rel))
        self.assertEqual([t[0] for t in todo], ["media/2026-09-01-old", "media/undated", "previews/pr-3"])


if __name__ == "__main__":
    unittest.main()
