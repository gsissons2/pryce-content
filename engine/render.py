#!/usr/bin/env python3
"""Render a post spec into finished files.

    python engine/render.py queue/2026-11-17-fernleaf-cafe.json --out out/

Writes out/<id>/slide-01.jpg ... carousel.pdf (carousels), video.mp4 + cover.jpg (videos)
and out/<id>/checks.json. Exits 1 if any layout check fails.
"""
import argparse, json, os, shutil, subprocess, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
KIT = ROOT / "engine" / "kit" / "render.html"
CAROUSELS = {"redesign-carousel", "stat-carousel"}
VIDEOS = {"redesign-video", "stat-video"}


def load_spec(path: Path) -> dict:
    spec = json.loads(path.read_text())
    d = spec.get("data", {})
    for side in ("before", "after"):  # inline phone screens
        if isinstance(d.get(side, {}).get("screen"), str):
            d[side]["screen"] = json.loads((ROOT / d[side]["screen"]).read_text())
    return spec


def chrome_kwargs():
    exe = os.environ.get("CHROME_PATH") or ("/usr/bin/google-chrome" if Path("/usr/bin/google-chrome").exists() else None)
    kw = {"args": ["--no-sandbox", "--font-render-hinting=none"]}
    if exe:
        kw["executable_path"] = exe
    return kw


def slide_count(spec):
    f = spec["format"]
    if f == "redesign-carousel":
        return 5
    if f == "stat-carousel":
        return len(spec["data"]["slides"])
    raise ValueError(f"not a carousel: {f}")


def render_carousel(spec, outdir: Path, page):
    checks, files = [], []
    for i in range(1, slide_count(spec) + 1):
        res = page.evaluate("([s, p]) => window.boot(s, p)", [spec, {"slide": i}])
        for c in res:
            c["slide"] = i
        checks += res
        el = page.query_selector(".slide")
        fn = outdir / f"slide-{i:02d}.jpg"
        el.screenshot(path=str(fn), type="jpeg", quality=92)
        files.append(fn)
    # LinkedIn document post
    from PIL import Image
    ims = [Image.open(f).convert("RGB") for f in files]
    ims[0].save(outdir / "carousel.pdf", save_all=True, append_images=ims[1:], resolution=96)
    return checks


def render_video(spec, outdir: Path, page):
    # Deterministic: window.renderVideo(spec) prepares, window.frame(t) draws time t.
    meta = page.evaluate("(s) => window.prepareVideo(s)", spec)
    checks = meta.get("checks", [])
    fps, dur = meta["fps"], meta["duration"]
    tmp = Path(tempfile.mkdtemp(prefix="frames_"))
    try:
        n = int(round(dur * fps))
        for k in range(n):
            page.evaluate("(t) => window.frame(t)", k / fps)
            page.screenshot(path=str(tmp / f"f{k:05d}.jpg"), type="jpeg", quality=92,
                            clip={"x": 0, "y": 0, "width": 1080, "height": 1920})
        page.evaluate("(t) => window.frame(t)", meta.get("coverAt", 1.0))
        page.screenshot(path=str(outdir / "cover.jpg"), type="jpeg", quality=92,
                        clip={"x": 0, "y": 0, "width": 1080, "height": 1920})
        cmd = ["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(fps), "-i", str(tmp / "f%05d.jpg"),
               "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=48000",
               "-shortest", "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p",
               "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", str(outdir / "video.mp4")]
        subprocess.run(cmd, check=True)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return checks


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("specs", nargs="+")
    ap.add_argument("--out", default="out")
    args = ap.parse_args()
    from playwright.sync_api import sync_playwright

    failed = False
    with sync_playwright() as p:
        browser = p.chromium.launch(**chrome_kwargs())
        for sp in args.specs:
            spec = load_spec(Path(sp))
            outdir = Path(args.out) / spec["id"]
            outdir.mkdir(parents=True, exist_ok=True)
            fmt = spec["format"]
            if fmt in CAROUSELS:
                page = browser.new_page(viewport={"width": 1080, "height": 1350}, device_scale_factor=1)
            elif fmt in VIDEOS:
                page = browser.new_page(viewport={"width": 1080, "height": 1920}, device_scale_factor=1)
            else:
                print(f"{sp}: unknown format {fmt}", file=sys.stderr)
                failed = True
                continue
            page.goto(KIT.as_uri())
            checks = render_carousel(spec, outdir, page) if fmt in CAROUSELS else render_video(spec, outdir, page)
            from factcheck import check as factcheck
            checks += factcheck(spec)
            page.close()
            (outdir / "checks.json").write_text(json.dumps(checks, indent=1, ensure_ascii=False))
            errs = [c for c in checks if c["level"] == "error"]
            warns = [c for c in checks if c["level"] == "warn"]
            status = "FAIL" if errs else "ok"
            print(f"{status}  {spec['id']}  ({len(errs)} errors, {len(warns)} warnings)")
            for c in errs + warns:
                where = f"slide {c['slide']}: " if "slide" in c else ""
                print(f"   {c['level']}: {where}{c['msg']}")
            failed |= bool(errs)
        browser.close()
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
