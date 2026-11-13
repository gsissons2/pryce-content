#!/usr/bin/env python3
"""Download photos listed in assets/photos/manifest.json.

The repo only keeps small previews (about 400 px wide) so it stays light.

    python engine/fetch_photos.py              # full-size versions over the previews (CI, before rendering)
    python engine/fetch_photos.py --previews   # only photos with no file yet: save a 400 px preview

CI runs --previews on every PR and commits the new previews to the PR branch, because the
Claude workspace cannot reach Unsplash. Safe to run repeatedly."""
import io, json, re, sys, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PHOTOS = ROOT / "assets" / "photos"
PREVIEW_W = 400


def download(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "pryce-content/1.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def preview_bytes(url: str) -> bytes:
    """A 400 px JPEG. Unsplash URLs are asked for that width; anything else is resized here."""
    if "images.unsplash.com" in url:
        url = re.sub(r"([?&])w=\d+", rf"\g<1>w={PREVIEW_W}", url) if re.search(r"[?&]w=\d+", url) \
            else url + ("&" if "?" in url else "?") + f"w={PREVIEW_W}"
    data = download(url)
    from PIL import Image
    im = Image.open(io.BytesIO(data)).convert("RGB")
    if im.width > PREVIEW_W:
        im = im.resize((PREVIEW_W, round(im.height * PREVIEW_W / im.width)), Image.LANCZOS)
    out = io.BytesIO()
    im.save(out, "JPEG", quality=80, optimize=True)
    return out.getvalue()


def main(argv=None):
    previews = "--previews" in (argv if argv is not None else sys.argv[1:])
    manifest = json.loads((PHOTOS / "manifest.json").read_text())
    failed = 0
    for rel, url in manifest.items():
        if rel.startswith("_"):
            continue
        dest = PHOTOS / rel
        if previews and dest.exists():
            continue
        if not previews and dest.exists() and dest.stat().st_size > 150_000:
            continue
        try:
            data = preview_bytes(url) if previews else download(url)
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(data)
            print(f"{'preview' if previews else 'fetched'} {rel} ({len(data) // 1024} KB)")
        except Exception as e:  # keep what is there, the render check reports anything missing
            failed += 1
            print(f"WARN could not fetch {rel}: {e}", file=sys.stderr)
    if failed:
        print(f"{failed} photo(s) not downloaded", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
