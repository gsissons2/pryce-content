"""Caption limits per platform. Nothing is ever trimmed silently: every change comes back as a warning."""
from __future__ import annotations

import re

INSTAGRAM_CAPTION = 2200
INSTAGRAM_HASHTAGS = 30
INSTAGRAM_MENTIONS = 20
INSTAGRAM_ALT_TEXT = 1000
TIKTOK_VIDEO_CAPTION = 2200      # counted in UTF-16 units, like TikTok does
TIKTOK_PHOTO_TITLE = 90
TIKTOK_PHOTO_DESCRIPTION = 4000
YOUTUBE_TITLE = 100
YOUTUBE_DESCRIPTION = 5000       # YouTube counts bytes, so we count UTF-8 bytes
LINKEDIN_COMMENTARY = 3000
LINKEDIN_MEDIA_TITLE = 100       # our own cap for the document/video title line

HASHTAG = re.compile(r"(?<![\w#&])#(\w+)")
MENTION = re.compile(r"(?<![\w@])@([\w.]+)")
LINKEDIN_RESERVED = set("|{}@[]()<>#\\*_~")


def utf16_len(s: str) -> int:
    return len(s.encode("utf-16-le")) // 2


def utf8_len(s: str) -> int:
    return len(s.encode("utf-8"))


def trim(text: str, limit: int, length=len) -> tuple[str, bool]:
    """Cut to fit `limit`, at a word boundary when one is close, ending with an ellipsis."""
    if length(text) <= limit:
        return text, False
    cut = text[:limit]
    while cut and length(cut) + length("…") > limit:
        cut = cut[:-1]
    space = max(cut.rfind(" "), cut.rfind("\n"))
    if space >= int(len(cut) * 0.6):
        cut = cut[:space]
    return cut.rstrip() + "…", True


def first_line(text: str) -> str:
    for line in (text or "").splitlines():
        line = HASHTAG.sub("", line).strip()
        if line:
            return line
    return ""


def first_sentence(text: str) -> str:
    line = first_line(text)
    return re.split(r"(?<=[.?!])\s+", line, maxsplit=1)[0] if line else ""


def _caption(spec: dict, platform: str) -> str:
    value = (spec.get("captions") or {}).get(platform)
    return value if isinstance(value, str) else ""


def instagram_caption(spec: dict) -> tuple[str, list[str]]:
    warnings = []
    text = _caption(spec, "instagram")
    if not text:
        warnings.append("instagram: no caption, posting without one")
    tags = HASHTAG.findall(text)
    if len(tags) > INSTAGRAM_HASHTAGS:
        seen = 0

        def keep(m):
            nonlocal seen
            seen += 1
            return m.group(0) if seen <= INSTAGRAM_HASHTAGS else ""
        text = re.sub(r"[ \t]{2,}", " ", HASHTAG.sub(keep, text)).rstrip()
        warnings.append(f"instagram: {len(tags)} hashtags, removed the last {len(tags) - INSTAGRAM_HASHTAGS} "
                        f"(max {INSTAGRAM_HASHTAGS})")
    mentions = MENTION.findall(text)
    if len(mentions) > INSTAGRAM_MENTIONS:
        warnings.append(f"instagram: {len(mentions)} @mentions, max is {INSTAGRAM_MENTIONS}, the post may be rejected")
    text, cut = trim(text, INSTAGRAM_CAPTION)
    if cut:
        warnings.append(f"instagram: caption cut to {INSTAGRAM_CAPTION} characters")
    return text, warnings


def instagram_alt(spec: dict, count: int) -> tuple[list[str], list[str]]:
    alts = [a if isinstance(a, str) else "" for a in (spec.get("alt") or [])]
    warnings = []
    if len(alts) < count:
        warnings.append(f"instagram: {count} slides but {len(alts)} alt texts")
    out = []
    for i in range(count):
        a, cut = trim(alts[i] if i < len(alts) else "", INSTAGRAM_ALT_TEXT)
        if cut:
            warnings.append(f"instagram: alt text {i + 1} cut to {INSTAGRAM_ALT_TEXT} characters")
        out.append(a)
    return out, warnings


def tiktok_caption(spec: dict, kind: str) -> tuple[dict, list[str]]:
    """Video: {"caption"}. Photo post: {"title", "description"} (title is the first sentence, no hashtags)."""
    warnings = []
    text = _caption(spec, "tiktok")
    if not text:
        text = _caption(spec, "instagram")
        warnings.append("tiktok: no caption, using the Instagram caption")
    if kind == "video":
        caption, cut = trim(text, TIKTOK_VIDEO_CAPTION, utf16_len)
        if cut:
            warnings.append(f"tiktok: caption cut to {TIKTOK_VIDEO_CAPTION} characters")
        return {"caption": caption}, warnings
    title, cut = trim(first_sentence(text), TIKTOK_PHOTO_TITLE, utf16_len)
    if cut:
        warnings.append(f"tiktok: photo title (first sentence of the caption) cut to {TIKTOK_PHOTO_TITLE} characters")
    description, cut = trim(text, TIKTOK_PHOTO_DESCRIPTION, utf16_len)
    if cut:
        warnings.append(f"tiktok: photo description cut to {TIKTOK_PHOTO_DESCRIPTION} characters")
    return {"title": title, "description": description}, warnings


def youtube_meta(spec: dict) -> tuple[str, str, list[str]]:
    warnings = []
    yt = (spec.get("captions") or {}).get("youtube")
    yt = yt if isinstance(yt, dict) else {}
    title = (yt.get("title") or "").strip()
    description = yt.get("description") or ""
    if not title:
        title = first_line(_caption(spec, "tiktok") or _caption(spec, "instagram"))
        warnings.append("youtube: no captions.youtube.title, using the first line of another caption")
    if not title:
        title = spec.get("id", "Pryce Digital")
    for name, value in (("title", title), ("description", description)):
        if "<" in value or ">" in value:
            warnings.append(f"youtube: removed < and > from the {name} (YouTube rejects them)")
    title = title.replace("<", "").replace(">", "")
    description = description.replace("<", "").replace(">", "")
    title, cut = trim(title, YOUTUBE_TITLE)
    if cut:
        warnings.append(f"youtube: title cut to {YOUTUBE_TITLE} characters")
    description, cut = trim(description, YOUTUBE_DESCRIPTION, utf8_len)
    if cut:
        warnings.append(f"youtube: description cut to {YOUTUBE_DESCRIPTION} bytes")
    return title, description, warnings


def linkedin_commentary(spec: dict) -> tuple[str, list[str]]:
    """Plain text, limit checked before escaping. Escape with linkedin_little_text() before sending."""
    warnings = []
    text = _caption(spec, "linkedin")
    if not text:
        warnings.append("linkedin: no caption, posting without text")
    text, cut = trim(text, LINKEDIN_COMMENTARY)
    if cut:
        warnings.append(f"linkedin: post text cut to {LINKEDIN_COMMENTARY} characters")
    return text, warnings


def linkedin_title(spec: dict) -> tuple[str, list[str]]:
    data = spec.get("data") or {}
    title = data.get("hook") or data.get("title") or data.get("business") or spec.get("id", "")
    title, cut = trim(str(title), LINKEDIN_MEDIA_TITLE)
    return title, ([f"linkedin: media title cut to {LINKEDIN_MEDIA_TITLE} characters"] if cut else [])


def escape_little(text: str) -> str:
    return "".join("\\" + c if c in LINKEDIN_RESERVED else c for c in text)


def linkedin_little_text(text: str, hashtags: bool = True) -> str:
    """Escape LinkedIn "little text" reserved characters  | { } @ [ ] ( ) < > # \\ * _ ~ .
    With hashtags=True, #word becomes the hashtag template {hashtag|\\#|word} so it stays a real hashtag."""
    if not hashtags:
        return escape_little(text)
    out, pos = [], 0
    for m in HASHTAG.finditer(text):
        out.append(escape_little(text[pos:m.start()]))
        out.append("{hashtag|\\#|" + escape_little(m.group(1)) + "}")
        pos = m.end()
    out.append(escape_little(text[pos:]))
    return "".join(out)


def check_spec(spec: dict) -> dict[str, list[str]]:
    """Warnings for every scheduled platform, without changing anything. Used by the PR preview."""
    from .common import kind_of, PermanentError
    result: dict[str, list[str]] = {}
    try:
        kind = kind_of(spec)
    except PermanentError as e:
        return {"spec": [str(e)]}
    for platform in (spec.get("schedule") or {}):
        if platform == "instagram":
            w = instagram_caption(spec)[1]
            if kind == "carousel":
                w += instagram_alt(spec, len(spec.get("alt") or []))[1]
        elif platform == "tiktok":
            w = tiktok_caption(spec, kind)[1]
        elif platform == "youtube":
            w = youtube_meta(spec)[2] if kind == "video" else ["youtube: only takes video formats, this slot will fail"]
        elif platform == "linkedin":
            w = linkedin_commentary(spec)[1] + linkedin_title(spec)[1]
        else:
            w = [f"{platform}: unknown platform, it will be skipped"]
        if w:
            result[platform] = w
    return result
