"""Shared errors, time helpers and the rendered-assets model. Standard library only."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

PLATFORMS = ("instagram", "tiktok", "youtube", "linkedin")
CAROUSEL_FORMATS = {"redesign-carousel", "stat-carousel"}
VIDEO_FORMATS = {"redesign-video", "stat-video"}
MAX_FAILURES = 3


class PublishError(Exception):
    """This attempt failed. Counts as one of the 3 tries."""


class PermanentError(PublishError):
    """Retrying cannot help (bad spec, file too big, wrong format). Gives up at once."""


class UncertainError(PublishError):
    """The final publish call was sent but we could not tell if it worked.
    Gives up at once so a retry can never double post."""


class SkipForNow(Exception):
    """Not a failure. Leave the slot alone and try on the next run
    (daily limit reached, platform not configured yet)."""


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def parse_time(value: str) -> datetime:
    dt = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    if dt.tzinfo is None:
        raise ValueError(f"time has no timezone offset: {value!r}")
    return dt


def iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def env(name: str, dry_run: bool = False) -> str:
    """Read a required setting. Missing means the platform is not set up yet, which is a skip."""
    value = os.environ.get(name, "").strip()
    if value:
        return value
    if dry_run:
        return f"<{name}>"
    raise SkipForNow(f"{name} is not set, so this platform is not configured yet")


def kind_of(spec: dict) -> str:
    fmt = spec.get("format", "")
    if fmt in CAROUSEL_FORMATS:
        return "carousel"
    if fmt in VIDEO_FORMATS:
        return "video"
    raise PermanentError(f"unknown format {fmt!r}")


@dataclass
class Assets:
    """Rendered files for one spec, plus their public URLs once hosted."""
    id: str
    kind: str
    dir: Path
    slides: list[Path] = field(default_factory=list)
    pdf: Path | None = None
    video: Path | None = None
    cover: Path | None = None
    urls: dict[str, str] = field(default_factory=dict)  # file name -> public URL

    @classmethod
    def from_dir(cls, spec: dict, out_dir: Path) -> "Assets":
        kind = kind_of(spec)
        d = Path(out_dir)
        if not d.is_dir():
            raise PublishError(f"render output missing: {d}")
        a = cls(id=spec["id"], kind=kind, dir=d)
        if kind == "carousel":
            a.slides = sorted(d.glob("slide-*.jpg"))
            a.pdf = d / "carousel.pdf" if (d / "carousel.pdf").is_file() else None
            if not a.slides:
                raise PublishError(f"no slide-*.jpg in {d}")
        else:
            a.video = d / "video.mp4" if (d / "video.mp4").is_file() else None
            a.cover = d / "cover.jpg" if (d / "cover.jpg").is_file() else None
            if not a.video:
                raise PublishError(f"no video.mp4 in {d}")
        return a

    def public_files(self) -> list[Path]:
        """Files the URL-based platforms (Instagram, Zernio) fetch from Pages."""
        if self.kind == "carousel":
            return list(self.slides)
        return [p for p in (self.video, self.cover) if p]

    def all_files(self) -> list[Path]:
        """Everything any platform needs, so publishing never has to re-render."""
        return self.public_files() + ([self.pdf] if self.pdf else [])

    def url(self, path: Path) -> str:
        try:
            return self.urls[path.name]
        except KeyError:
            raise PublishError(f"{path.name} has no public URL (media upload did not run)") from None
