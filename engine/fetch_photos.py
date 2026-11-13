#!/usr/bin/env python3
"""Download full-resolution photos listed in assets/photos/manifest.json.

The repo only keeps small previews so it stays light. CI runs this before rendering so
posts use the full-size images. Safe to run repeatedly: skips files already at full size."""
import json, sys, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PHOTOS = ROOT / "assets" / "photos"


def main():
    manifest = json.loads((PHOTOS / "manifest.json").read_text())
    failed = 0
    for rel, url in manifest.items():
        if rel.startswith("_"):
            continue
        dest = PHOTOS / rel
        if dest.exists() and dest.stat().st_size > 150_000:
            continue
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "pryce-content/1.0"})
            with urllib.request.urlopen(req, timeout=60) as r:
                data = r.read()
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(data)
            print(f"fetched {rel} ({len(data) // 1024} KB)")
        except Exception as e:  # keep the preview, render still works
            failed += 1
            print(f"WARN could not fetch {rel}: {e}", file=sys.stderr)
    if failed:
        print(f"{failed} photo(s) kept at preview size", file=sys.stderr)


if __name__ == "__main__":
    main()
