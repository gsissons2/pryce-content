"""Publish every due platform slot in queue/*.json.

    python -m publish.run --check                    list due slots (no network, standard library only)
    python -m publish.run --stage-media _media       render due specs into the media branch checkout
    python -m publish.run --media-dir _media         publish due slots using the staged media
    python -m publish.run --dry-run                  print every request, send nothing, write nothing
    common flags: [--now ISO] [--only platform] [--summary FILE]

A slot is due when its schedule time is <= now, it is not in `published`, and it has failed
fewer than 3 times (and was not given up). After each platform succeeds the spec JSON is
written straight away, so a crash later in the run can never cause a double post.
See docs/PUBLISHING.md.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

from .common import (MAX_FAILURES, MAX_LATE_HOURS, PLATFORMS, Assets, PermanentError, PublishError, SkipForNow, UncertainError,
                     iso, kind_of, now_utc, parse_time)

ROOT = Path(__file__).resolve().parent.parent
RENDER_TIMEOUT = 900

# platform -> "module:function". Loaded lazily so --check needs only the standard library.
PUBLISHERS = {
    "instagram": "publish.instagram:publish",
    "linkedin": "publish.linkedin:publish",
    "tiktok": "publish.zernio:publish_tiktok",
    "youtube": "publish.zernio:publish_youtube",
}
URL_PLATFORMS = {"instagram", "tiktok", "youtube"}  # fetch media from GitHub Pages


def get_publisher(platform: str):
    target = PUBLISHERS[platform]
    if callable(target):
        return target
    module, func = target.split(":")
    return getattr(importlib.import_module(module), func)


# Spec state ----------------------------------------------------------------
def load_specs(queue_dir: Path) -> list[tuple[Path, dict]]:
    specs = []
    for path in sorted(Path(queue_dir).glob("*.json")):
        try:
            spec = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as e:
            print(f"! {path.name}: cannot read ({e}), skipped", file=sys.stderr)
            continue
        if not isinstance(spec, dict) or not spec.get("id"):
            print(f"! {path.name}: no id, skipped", file=sys.stderr)
            continue
        specs.append((path, spec))
    return specs


def failure_count(spec: dict, platform: str) -> int:
    f = (spec.get("failed") or {}).get(platform)
    if not f:
        return 0
    if isinstance(f, list):
        return len(f)
    if isinstance(f, dict):
        if isinstance(f.get("history"), list):
            return len(f["history"])
        return int(f.get("count", 1))
    return 1


def given_up(spec: dict, platform: str) -> bool:
    f = (spec.get("failed") or {}).get(platform)
    return failure_count(spec, platform) >= MAX_FAILURES or (isinstance(f, dict) and bool(f.get("gave_up")))


MAX_LATE = timedelta(hours=MAX_LATE_HOURS)


def due_slots(specs: list[tuple[Path, dict]], now: datetime, only: str | None = None) -> list[tuple]:
    """(path, spec, platform, when) for every slot to try now, oldest first.

    A slot more than MAX_LATE in the past is dropped with a note, never posted late. This covers
    a platform that was not configured yet, a long Actions outage, or a post merged after its time.
    """
    due = []
    for path, spec in specs:
        published = spec.get("published") or {}
        for platform, when_raw in (spec.get("schedule") or {}).items():
            if only and platform != only:
                continue
            if platform not in PLATFORMS:
                print(f"! {spec['id']}: unknown platform {platform!r}, skipped", file=sys.stderr)
                continue
            if platform in published or given_up(spec, platform):
                continue
            try:
                when = parse_time(str(when_raw))
            except ValueError as e:
                print(f"! {spec['id']} {platform}: bad schedule time ({e}), skipped", file=sys.stderr)
                continue
            if when <= now:
                if now - when > MAX_LATE:
                    print(f"- {spec['id']} {platform}: missed its slot ({when_raw}) by more than "
                          f"{MAX_LATE_HOURS} h, not posting late", file=sys.stderr)
                    continue
                due.append((path, spec, platform, when))
    due.sort(key=lambda d: (d[3], d[1]["id"], d[2]))
    return due


def record_success(spec: dict, platform: str, result: dict, now: datetime):
    entry = {"id": result.get("id"), "url": result.get("url"), "at": iso(now)}
    for k, v in result.items():
        if k not in entry and k != "warnings" and v is not None:
            entry[k] = v
    spec.setdefault("published", {})[platform] = entry


def record_failure(spec: dict, platform: str, error: str, now: datetime, give_up: bool = False) -> bool:
    """Add one failure. Returns True if this platform is now given up for this spec."""
    failed = spec.setdefault("failed", {})
    prev = failed.get(platform)
    history = []
    if isinstance(prev, dict):
        history = list(prev.get("history") or ([{"at": prev.get("at"), "error": prev.get("error")}]
                                               if prev.get("error") else []))
    elif isinstance(prev, list):
        history = list(prev)
    history.append({"at": iso(now), "error": error[:1000]})
    entry = {"at": iso(now), "error": error[:1000], "history": history}
    if give_up or len(history) >= MAX_FAILURES:
        entry["gave_up"] = True
    failed[platform] = entry
    return bool(entry.get("gave_up"))


def write_spec(path: Path, spec: dict):
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(spec, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def spec_hash(spec: dict) -> str:
    """Changes when anything that affects the render changes (spec content or a screen it uses)."""
    content = {k: v for k, v in spec.items() if k not in ("published", "failed")}
    h = hashlib.sha256(json.dumps(content, sort_keys=True, ensure_ascii=False).encode())
    for ref in sorted(set(_strings(spec.get("data")))):
        if ref.startswith("screens/") and (ROOT / ref).is_file():
            h.update((ROOT / ref).read_bytes())
    return h.hexdigest()[:16]


def _strings(o):
    if isinstance(o, str):
        yield o
    elif isinstance(o, dict):
        for v in o.values():
            yield from _strings(v)
    elif isinstance(o, list):
        for v in o:
            yield from _strings(v)


def gh_output(**values):
    path = os.environ.get("GITHUB_OUTPUT")
    if path:
        with open(path, "a", encoding="utf-8") as f:
            for k, v in values.items():
                f.write(f"{k}={v}\n")


# Rendering -----------------------------------------------------------------
def render(spec_path: Path, out_dir: Path, runner=subprocess.run) -> tuple[int, str]:
    rel = os.path.relpath(spec_path, ROOT)
    out = os.path.relpath(out_dir, ROOT)
    try:
        proc = runner([sys.executable, "engine/render.py", rel, "--out", out], cwd=ROOT, capture_output=True,
                      text=True, timeout=RENDER_TIMEOUT)
    except (OSError, subprocess.TimeoutExpired) as e:
        return 1, f"render could not run: {type(e).__name__}: {e}"
    return proc.returncode, ((proc.stdout or "") + (proc.stderr or ""))[-1500:]


def ensure_rendered(spec_path: Path, spec: dict, out_dir: Path, runner=subprocess.run) -> Assets:
    target = Path(out_dir) / spec["id"]
    if not target.is_dir():
        code, log = render(spec_path, out_dir, runner)
        print(log.rstrip())
        if code != 0:
            raise PublishError(f"render failed (exit {code}): {log.strip()[-500:]}")
    return Assets.from_dir(spec, target)


# Staging -------------------------------------------------------------------
HASH_FILE = "spec-hash.txt"


def staged_dir(media_dir: Path, sid: str) -> Path:
    return Path(media_dir) / "media" / sid


def is_staged(media_dir: Path, spec: dict) -> bool:
    d = staged_dir(media_dir, spec["id"])
    f = d / HASH_FILE
    return f.is_file() and f.read_text().strip() == spec_hash(spec)


def stage_media(queue_dir: Path, out_dir: Path, media_dir: Path, now: datetime, only: str | None = None,
                runner=subprocess.run, live_check=None) -> dict:
    """Render every due spec whose media is missing or stale and copy its files into
    <media_dir>/media/<id>/. Render failures are recorded in the spec like any failure.
    Returns {"changed", "deploy", "ids", "failed", "gave_up"} (gave_up rows feed the issue step)."""
    from . import media
    result = {"changed": False, "deploy": False, "ids": [], "failed": [], "gave_up": []}
    groups: dict[Path, tuple[dict, list[str]]] = {}
    for path, spec, platform, _ in due_slots(load_specs(queue_dir), now, only):
        groups.setdefault(path, (spec, []))[1].append(platform)
    for path, (spec, platforms) in groups.items():
        sid = spec["id"]
        if is_staged(media_dir, spec):
            # Already staged. Make sure Pages actually serves it (a deploy may have failed last run).
            if any(p in URL_PLATFORMS for p in platforms) and not result["deploy"]:
                assets = Assets.from_dir(spec, staged_dir(media_dir, sid))
                first = assets.public_files()[0]
                data = first.read_bytes()
                url = media.url_for(f"media/{sid}/{first.name}", data)
                check = live_check or (lambda u, t, s: media.is_live(_live_http(), u, t, s))
                if not check(url, media.content_type(first), len(data)):
                    result["deploy"] = True
            print(f"staged already: {sid}")
            continue
        code, log = render(path, out_dir, runner)
        print(log.rstrip())
        try:
            if code != 0:
                raise PublishError(f"render failed (exit {code}): {log.strip()[-500:]}")
            assets = Assets.from_dir(spec, Path(out_dir) / sid)
            target = staged_dir(media_dir, sid)
            media.stage_files(assets.all_files(), target)
            (target / HASH_FILE).write_text(spec_hash(spec) + "\n")
        except PublishError as e:
            for p in platforms:
                gave = record_failure(spec, p, str(e), now_utc(), give_up=isinstance(e, PermanentError))
                row = {"id": sid, "platform": p, "error": str(e), "file": os.path.relpath(path, ROOT)}
                result["failed"].append(row)
                if gave:
                    result["gave_up"].append(row)
            write_spec(path, spec)
            print(f"   {sid}: staging FAILED: {e}")
            continue
        print(f"staged: {sid}")
        result["changed"] = result["deploy"] = True
        result["ids"].append(sid)
    return result


def _live_http():
    from .http import Http
    return Http()


# Main loop -----------------------------------------------------------------
def run(queue_dir: Path, out_dir: Path, now: datetime, dry_run: bool = False, only: str | None = None,
        http=None, media_host_factory=None, runner=subprocess.run, media_dir: Path | None = None) -> dict:
    summary = {"now": iso(now), "dry_run": dry_run, "published": [], "failed": [], "gave_up": [], "skipped": [],
               "warnings": []}
    due = due_slots(load_specs(queue_dir), now, only)
    if not due:
        print(f"Nothing due at {iso(now)}.")
        return summary
    if http is None:
        from .http import Http
        http = Http(dry_run=dry_run)
    hosting_note = None
    if media_host_factory is None:
        if media_dir is None and not dry_run:
            hosting_note = "media is only hosted inside the Publish workflow (run with --media-dir)"

        def media_host_factory(h):
            from .media import PagesHost
            return PagesHost(h)

    groups: dict[Path, tuple[dict, list[str]]] = {}
    for path, spec, platform, _ in due:
        groups.setdefault(path, (spec, []))[1].append(platform)

    for path, (spec, platforms) in groups.items():
        sid = spec["id"]
        print(f"\n== {sid}: {', '.join(platforms)}{' (dry run)' if dry_run else ''}")

        def fail(platform, error, give_up=False):
            print(f"   {platform}: FAILED: {error}")
            gave = record_failure(spec, platform, str(error), now_utc(), give_up)
            row = {"id": sid, "platform": platform, "error": str(error), "file": os.path.relpath(path, ROOT)}
            summary["failed"].append(row)
            if gave:
                summary["gave_up"].append(row)
            if not dry_run:
                write_spec(path, spec)

        try:
            if "youtube" in platforms and kind_of(spec) != "video":
                platforms.remove("youtube")
                fail("youtube", "YouTube only takes video formats", give_up=True)
            if media_dir is not None:
                if not is_staged(media_dir, spec):
                    raise SkipForNow("media not staged for this spec (staging failed or is out of date)")
                assets = Assets.from_dir(spec, staged_dir(media_dir, sid))
            else:
                assets = ensure_rendered(path, spec, out_dir, runner)
        except SkipForNow as e:
            for p in platforms:
                print(f"   {p}: skipped, {e}")
                summary["skipped"].append({"id": sid, "platform": p, "reason": str(e)})
            continue
        except PublishError as e:
            for p in platforms:
                fail(p, e, give_up=isinstance(e, PermanentError))
            continue

        blocked: set[str] = set()
        needs_urls = [p for p in platforms if p in URL_PLATFORMS]
        if needs_urls:
            try:
                if hosting_note:
                    raise SkipForNow(hosting_note)
                media_host_factory(http).host_assets(assets)
            except SkipForNow as e:
                for p in needs_urls:
                    print(f"   {p}: skipped, {e}")
                    summary["skipped"].append({"id": sid, "platform": p, "reason": str(e)})
                blocked.update(needs_urls)
            except PublishError as e:
                for p in needs_urls:
                    fail(p, f"media upload: {e}", give_up=isinstance(e, PermanentError))
                blocked.update(needs_urls)

        for platform in platforms:
            if platform in blocked:
                continue
            try:
                result = get_publisher(platform)(http, spec, assets)
            except SkipForNow as e:
                print(f"   {platform}: skipped, {e}")
                summary["skipped"].append({"id": sid, "platform": platform, "reason": str(e)})
                continue
            except (PermanentError, UncertainError) as e:
                fail(platform, e, give_up=True)
                continue
            except PublishError as e:
                fail(platform, e)
                continue
            except Exception as e:  # a bug after the post may have gone live: never retry blindly
                fail(platform, f"unexpected {type(e).__name__}: {e}. Check {platform} before retrying.",
                     give_up=True)
                continue
            for w in result.get("warnings") or []:
                print(f"   warning: {w}")
                summary["warnings"].append({"id": sid, "platform": platform, "warning": w})
            record_success(spec, platform, result, now_utc())
            if not dry_run:
                write_spec(path, spec)  # straight away, before anything else can go wrong
            print(f"   {platform}: published {result.get('url') or result.get('id')}")
            summary["published"].append({"id": sid, "platform": platform, "url": result.get("url"),
                                         "post_id": result.get("id")})
    return summary


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m publish.run", description=__doc__.split("\n\n")[0])
    ap.add_argument("--dry-run", action="store_true", help="print the HTTP requests, send nothing, write nothing")
    ap.add_argument("--now", help="pretend it is this ISO time (with offset)")
    ap.add_argument("--only", choices=PLATFORMS, help="only this platform")
    ap.add_argument("--queue", default=str(ROOT / "queue"))
    ap.add_argument("--out", default=str(ROOT / "out"))
    ap.add_argument("--summary", help="write a JSON summary here (the workflow reads it)")
    ap.add_argument("--check", action="store_true", help="only list due slots, no network")
    ap.add_argument("--stage-media", metavar="DIR", help="render due specs into DIR/media/<id>/ (media branch)")
    ap.add_argument("--media-dir", metavar="DIR", help="publish using media staged in DIR")
    args = ap.parse_args(argv)
    now = parse_time(args.now) if args.now else now_utc()

    if args.check:
        due = due_slots(load_specs(Path(args.queue)), now, args.only)
        for _, spec, platform, when in due:
            print(f"due: {spec['id']} {platform} ({iso(when)})")
        if not due:
            print(f"Nothing due at {iso(now)}.")
        gh_output(due="true" if due else "false")
        return 0

    if args.stage_media:
        res = stage_media(Path(args.queue), Path(args.out), Path(args.stage_media), now, args.only)
        print(f"\nStaged {len(res['ids'])} spec(s), {len(res['failed'])} failure(s). Deploy Pages: {res['deploy']}.")
        gh_output(changed=str(res["changed"]).lower(), deploy=str(res["deploy"]).lower(), ids=" ".join(res["ids"]),
                  failed=str(bool(res["failed"])).lower())
        if args.summary:
            Path(args.summary).write_text(json.dumps(res, indent=2, ensure_ascii=False), encoding="utf-8")
        return 0

    summary = run(Path(args.queue), Path(args.out), now, dry_run=args.dry_run, only=args.only,
                  media_dir=Path(args.media_dir) if args.media_dir else None)
    if args.summary:
        Path(args.summary).write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nDone: {len(summary['published'])} published, {len(summary['failed'])} failed, "
          f"{len(summary['skipped'])} skipped.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
