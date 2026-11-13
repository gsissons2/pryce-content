"""Remove old folders from a checkout of the media branch (the workflow commits and pushes).

    python -m publish.cleanup PATH_TO_CLONE [--media-days 45] [--preview-days 14] [--now ISO] [--dry-run]

media/<id>/      age from the YYYY-MM-DD at the start of the id, else the last commit date.
previews/pr-N/   age from the last commit that touched the folder.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

DATE_ID = re.compile(r"^(\d{4}-\d{2}-\d{2})")


def last_commit_date(repo: Path, rel: str) -> datetime | None:
    out = subprocess.run(["git", "-C", str(repo), "log", "-1", "--format=%cI", "--", rel],
                         capture_output=True, text=True).stdout.strip()
    return datetime.fromisoformat(out) if out else None


def plan(repo: Path, now: datetime, media_days: int = 45, preview_days: int = 14,
         commit_date=last_commit_date) -> list[tuple[str, str]]:
    """(folder, reason) pairs to delete."""
    out = []
    media = repo / "media"
    if media.is_dir():
        for d in sorted(p for p in media.iterdir() if p.is_dir()):
            rel = f"media/{d.name}"
            m = DATE_ID.match(d.name)
            when = (datetime.fromisoformat(m.group(1)).replace(tzinfo=timezone.utc) if m
                    else commit_date(repo, rel))
            if when and now - when > timedelta(days=media_days):
                out.append((rel, f"dated {when.date()}, older than {media_days} days"))
    previews = repo / "previews"
    if previews.is_dir():
        for d in sorted(p for p in previews.iterdir() if p.is_dir()):
            rel = f"previews/{d.name}"
            when = commit_date(repo, rel)
            if when and now - when > timedelta(days=preview_days):
                out.append((rel, f"last change {when.date()}, older than {preview_days} days"))
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m publish.cleanup")
    ap.add_argument("repo")
    ap.add_argument("--media-days", type=int, default=45)
    ap.add_argument("--preview-days", type=int, default=14)
    ap.add_argument("--now")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)
    now = datetime.fromisoformat(args.now.replace("Z", "+00:00")) if args.now else datetime.now(timezone.utc)
    repo = Path(args.repo)
    todo = plan(repo, now, args.media_days, args.preview_days)
    for rel, why in todo:
        print(f"{'would delete' if args.dry_run else 'delete'} {rel} ({why})")
    if todo and not args.dry_run:
        subprocess.run(["git", "-C", str(repo), "rm", "-r", "-q", "--"] + [r for r, _ in todo], check=True)
    print(f"{len(todo)} folder(s) {'to remove' if args.dry_run else 'removed'}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
