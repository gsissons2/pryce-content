"""Render changed specs on a PR, stage previews on the media branch, and write one PR comment.

    python -m publish.preview --pr 12 --changed changed.txt --comment comment.md --media-dir _media

Previews go to _media/previews/pr-<n>/<id>/ (the workflow pushes the branch) and the comment links
them through raw.githubusercontent.com, so PRs never deploy Pages.
Exit code 1 if any render check failed (the workflow still posts the comment first).
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

from . import captions
from . import media
from .common import Assets, PublishError, kind_of
from .run import ROOT, render

MARKER = "<!-- pryce-preview -->"


def specs_to_render(changed: list[str], queue_dir: Path) -> list[Path]:
    """Changed queue/*.json files, plus any queue spec that uses a changed screen."""
    changed = [c.strip() for c in changed if c.strip()]
    picked = []
    for c in changed:
        p = ROOT / c
        if c.startswith("queue/") and c.endswith(".json") and p.is_file() and p.parent == queue_dir:
            picked.append(p)
    screens = {c for c in changed if c.startswith("screens/")}
    if screens:
        for p in sorted(queue_dir.glob("*.json")):
            text = p.read_text(encoding="utf-8")
            if p not in picked and any(f'"{s}"' in text for s in screens):
                picked.append(p)
    return picked


def _checks_table(checks) -> str:
    if not isinstance(checks, list) or not checks:
        return "No layout or fact-check problems.\n"
    rows = ["| level | where | problem |", "|---|---|---|"]
    for c in checks:
        if not isinstance(c, dict):
            continue
        where = f"slide {c['slide']}" if "slide" in c else ""
        msg = str(c.get("msg", "")).replace("|", "\\|").replace("\n", " ")
        rows.append(f"| {c.get('level', '')} | {where} | {msg} |")
    return "\n".join(rows) + "\n"


def build_section(spec: dict, code: int, log: str, checks, assets: Assets | None, urls: dict, note: str) -> str:
    sid = spec["id"]
    status = "PASS" if code == 0 else "FAIL"
    lines = [f"### {status} `{sid}` ({spec.get('format', '?')})", ""]
    sched = spec.get("schedule") or {}
    if sched:
        lines.append("Schedule: " + ", ".join(f"{p} {t}" for p, t in sched.items()))
        lines.append("")
    if assets and urls:
        if assets.kind == "carousel":
            lines.append(" ".join(f'<a href="{urls[p.name]}"><img src="{urls[p.name]}" width="200"></a>'
                                  for p in assets.slides if p.name in urls))
            if assets.pdf and assets.pdf.name in urls:
                lines += ["", f"LinkedIn PDF: [carousel.pdf]({urls[assets.pdf.name]})"]
        else:
            if assets.cover and assets.cover.name in urls:
                lines.append(f'<a href="{urls[assets.video.name]}"><img src="{urls[assets.cover.name]}" width="200"></a>')
            lines += ["", f"Video: [video.mp4]({urls[assets.video.name]}) (tap the cover to open it)"]
        lines.append("")
    elif note:
        lines += [f"_{note}_", ""]
    lines += ["**Checks**", "", _checks_table(checks)]
    warnings = captions.check_spec(spec)
    if warnings:
        lines += ["**Caption warnings**", ""]
        lines += [f"- {w}" for ws in warnings.values() for w in ws]
        lines.append("")
    if code != 0:
        lines += ["<details><summary>Render log</summary>", "", "```", log.strip()[-1500:], "```", "</details>", ""]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m publish.preview")
    ap.add_argument("--pr", required=True)
    ap.add_argument("--changed", required=True, help="file with one changed path per line")
    ap.add_argument("--comment", required=True, help="write the comment markdown here")
    ap.add_argument("--queue", default=str(ROOT / "queue"))
    ap.add_argument("--out", default=str(ROOT / "out"))
    ap.add_argument("--media-dir", help="media branch checkout to stage previews into")
    args = ap.parse_args(argv)

    queue_dir = Path(args.queue).resolve()
    paths = specs_to_render(Path(args.changed).read_text(encoding="utf-8").splitlines(), queue_dir)
    sections, failed = [], False
    media_root = None
    if args.media_dir:
        media_root = Path(args.media_dir) / "previews" / f"pr-{args.pr}"
        if media_root.exists():
            shutil.rmtree(media_root)  # each run replaces this PR's previews
    for path in paths:
        spec = json.loads(path.read_text(encoding="utf-8"))
        code, log = render(path, Path(args.out))
        print(log.rstrip())
        failed |= code != 0
        out_dir = Path(args.out) / spec["id"]
        checks = []
        if (out_dir / "checks.json").is_file():
            checks = json.loads((out_dir / "checks.json").read_text(encoding="utf-8"))
        assets, urls, note = None, {}, ""
        try:
            kind_of(spec)
            assets = Assets.from_dir(spec, out_dir)
            if media_root is None:
                note = "Previews not staged (no --media-dir)."
            else:
                files = assets.all_files()
                media.stage_files(files, media_root / spec["id"])
                urls = {f.name: media.url_for(f"previews/pr-{args.pr}/{spec['id']}/{f.name}", f.read_bytes(),
                                              media.RAW_BASE) for f in files}
        except PublishError as e:
            note = f"Previews not staged: {e}"
        sections.append(build_section(spec, code, log, checks, assets, urls, note))

    head = [MARKER, "## Render preview", ""]
    if not paths:
        head.append("No post specs changed in this PR, nothing to render.")
    else:
        head.append(f"{len(paths)} spec(s) rendered. {'Some checks FAILED, fix before merging.' if failed else 'All checks passed.'}")
        head.append("Merging this PR approves these posts for publishing on their schedule.")
    Path(args.comment).write_text("\n".join(head) + "\n\n" + "\n---\n\n".join(sections), encoding="utf-8")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
