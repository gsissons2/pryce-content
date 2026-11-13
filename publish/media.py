"""Media hosting on GitHub Pages from this repo's orphan `media` branch.

The Publish workflow copies rendered files into a checkout of `media` (folder `_media`),
pushes it with GITHUB_TOKEN and deploys it to Pages. This module does no uploading:
it stages files, builds public URLs and waits until Pages serves them.

    python -m publish.media checkout _media      # check out `media`, or create it as an orphan
    python -m publish.media push _media -m MSG   # commit everything in _media and push `media`
"""
from __future__ import annotations

import argparse
import hashlib
import shutil
import subprocess
import sys
from pathlib import Path
from urllib.parse import quote

from .common import PermanentError, PublishError

BRANCH = "media"
PAGES_BASE = "https://gsissons2.github.io/pryce-content/"
RAW_BASE = f"https://raw.githubusercontent.com/gsissons2/pryce-content/{BRANCH}/"
MAX_BYTES = 25 * 1024 * 1024
PUBLIC_TIMEOUT = 600
PUBLIC_INTERVAL = 15
CONTENT_TYPES = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".mp4": "video/mp4",
                 ".pdf": "application/pdf"}
GIT_USER = ["-c", "user.name=github-actions[bot]",
            "-c", "user.email=41898282+github-actions[bot]@users.noreply.github.com"]


def blob_sha(data: bytes) -> str:
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


def content_type(path: Path) -> str:
    try:
        return CONTENT_TYPES[Path(path).suffix.lower()]
    except KeyError:
        raise PermanentError(f"{Path(path).name}: no known content type") from None


def url_for(rel_path: str, data: bytes, base: str = PAGES_BASE) -> str:
    # ?v= changes whenever the bytes change, so CDN caches never serve an old version.
    return f"{base}{quote(rel_path)}?v={blob_sha(data)[:10]}"


# Staging -------------------------------------------------------------------
def stage_files(files: list[Path], dest: Path) -> bool:
    """Make `dest` hold exactly `files`. Returns True if anything changed."""
    dest = Path(dest)
    for f in files:
        size = Path(f).stat().st_size
        if size > MAX_BYTES:
            raise PermanentError(f"{Path(f).name} is {size / 1048576:.1f} MB. Media files can be at most "
                                 f"{MAX_BYTES // 1048576} MB, so shorten or compress it.")
    changed = False
    dest.mkdir(parents=True, exist_ok=True)
    wanted = {Path(f).name for f in files}
    for old in dest.iterdir():
        if old.name not in wanted and old.is_file():
            old.unlink()
            changed = True
    for f in files:
        target = dest / Path(f).name
        data = Path(f).read_bytes()
        if not target.is_file() or target.read_bytes() != data:
            shutil.copyfile(f, target)
            changed = True
    return changed


# Waiting for Pages ---------------------------------------------------------
def is_live(http, url: str, ctype: str, size: int) -> bool:
    try:
        r = http.request("HEAD", url, headers={"Accept-Encoding": "identity"}, timeout=30,
                         dry_headers={"Content-Type": ctype, "Content-Length": str(size)})
    except PublishError:
        return False
    if r.status_code != 200:
        return False
    got = r.headers.get("Content-Type", "").split(";")[0].strip().lower()
    if got.split("/")[0] not in ("image", "video") or got.split("/")[0] != ctype.split("/")[0]:
        return False
    length = r.headers.get("Content-Length")
    return length is None or int(length) == size  # a stale deploy has the old size


class PagesHost:
    """Builds Pages URLs for an Assets bundle and waits until every one is served."""

    def __init__(self, http, base: str = PAGES_BASE, prefix: str = "media"):
        self.http, self.base, self.prefix = http, base, prefix

    def host_assets(self, assets) -> dict[str, str]:
        items = []
        for p in assets.public_files():
            data = p.read_bytes()
            url = url_for(f"{self.prefix}/{assets.id}/{p.name}", data, self.base)
            assets.urls[p.name] = url
            items.append({"url": url, "type": content_type(p), "size": len(data), "name": p.name})

        def check():
            pending = [i for i in items if not i.get("live")]
            for i in pending:
                i["live"] = is_live(self.http, i["url"], i["type"], i["size"])
            left = [i["name"] for i in items if not i["live"]]
            return (not left), ", ".join(left)
        try:
            self.http.poll(check, interval=PUBLIC_INTERVAL, timeout=PUBLIC_TIMEOUT, what="GitHub Pages")
        except PublishError as e:
            raise PublishError(f"{e}. Check the Pages deploy in this run and Settings, Pages "
                               "(source: GitHub Actions).") from None
        return assets.urls


# The media branch ----------------------------------------------------------
def _git(*args, cwd=None, check=True) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=check)


def checkout(dest: Path, repo: Path = Path("."), branch: str = BRANCH) -> str:
    """Check out `branch` from origin into `dest` as a worktree, or create it as an orphan with .nojekyll."""
    dest = Path(dest)
    fetched = _git("fetch", "--no-tags", "origin", f"+refs/heads/{branch}:refs/remotes/origin/{branch}",
                   cwd=repo, check=False).returncode == 0
    if fetched:
        _git("worktree", "add", "-f", "-B", branch, str(dest), f"origin/{branch}", cwd=repo)
        return "existing"
    _git("worktree", "add", "-f", "--detach", str(dest), cwd=repo)
    _git("checkout", "-q", "--orphan", branch, cwd=dest)
    _git("rm", "-rfq", "--ignore-unmatch", ".", cwd=dest)
    for leftover in dest.iterdir():
        if leftover.name != ".git":
            shutil.rmtree(leftover) if leftover.is_dir() else leftover.unlink()
    (dest / ".nojekyll").write_text("")
    _git("add", ".nojekyll", cwd=dest)
    return "created"


def push(dest: Path, message: str, branch: str = BRANCH, tries: int = 5, sleep=None) -> bool:
    """Commit everything in `dest` and push it to origin/<branch>. Returns False if nothing changed."""
    import time
    sleep = sleep or time.sleep
    dest = Path(dest)
    _git("add", "-A", cwd=dest)
    if _git("diff", "--cached", "--quiet", cwd=dest, check=False).returncode == 0 and \
            _git("rev-parse", "--verify", "-q", "HEAD", cwd=dest, check=False).returncode == 0:
        return False
    _git(*GIT_USER, "commit", "-q", "-m", message, cwd=dest)
    for attempt in range(tries):
        if _git("push", "-q", "origin", f"HEAD:refs/heads/{branch}", cwd=dest, check=False).returncode == 0:
            return True
        # Someone else pushed (a PR preview). Paths never overlap, so a rebase is safe.
        _git(*GIT_USER, "pull", "-q", "--rebase", "origin", branch, cwd=dest, check=False)
        sleep(5 * (attempt + 1))
    raise PublishError(f"could not push the {branch} branch after {tries} tries")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m publish.media")
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("checkout")
    c.add_argument("dest")
    p = sub.add_parser("push")
    p.add_argument("dest")
    p.add_argument("-m", "--message", required=True)
    args = ap.parse_args(argv)
    if args.cmd == "checkout":
        print(f"media branch: {checkout(Path(args.dest))} in {args.dest}")
    else:
        print("pushed" if push(Path(args.dest), args.message) else "nothing to push")
    return 0


if __name__ == "__main__":
    sys.exit(main())
