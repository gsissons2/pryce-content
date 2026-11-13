# Post spec format

Every post is one JSON file in `queue/`. File name: `YYYY-MM-DD-<slug>.json` (the date is the first publish day).

Merging a spec into `main` is the approval. The publisher only ever posts specs that are on `main`.

```json
{
  "id": "2026-11-17-fernleaf-cafe",
  "format": "redesign-carousel",
  "schedule": {
    "instagram": "2026-11-17T19:00:00+11:00",
    "tiktok": "2026-11-17T19:30:00+11:00",
    "linkedin": "2026-11-18T08:15:00+11:00"
  },
  "captions": {
    "instagram": "Caption text. Hashtags at the end.",
    "tiktok": "Caption text.",
    "youtube": { "title": "Max 100 chars", "description": "Text" },
    "linkedin": "Post text."
  },
  "alt": ["Alt text for slide 1", "..."],
  "sources": ["Only for stat posts: where every number comes from"],
  "data": { "...": "format-specific, see below" },
  "published": {}
}
```

- `schedule`: one ISO time per platform. A platform that is missing is skipped. YouTube only takes video formats.
- `published`: written by the publisher, never by hand. Shape: `{ "instagram": { "id": "...", "url": "...", "at": "ISO time" } }`. A platform listed here is never posted again.
- `failed`: written by the publisher on error, `{ "linkedin": { "at": "...", "error": "..." } }`. It retries on the next run up to 3 times, then stops and opens an issue.

## Formats

| format | outputs | platforms |
|---|---|---|
| `redesign-carousel` | `slide-01.jpg` to `slide-05.jpg` (1080×1350), `carousel.pdf` | instagram, tiktok (photo post), linkedin (PDF) |
| `stat-carousel` | `slide-NN.jpg` (1080×1350), `carousel.pdf` | instagram, tiktok, linkedin |
| `redesign-video` | `video.mp4` (1080×1920, H.264, AAC silent track), `cover.jpg` | instagram (Reel), tiktok, youtube (Short), linkedin |
| `stat-video` | `video.mp4`, `cover.jpg` | instagram, tiktok, youtube, linkedin |

Render: `python engine/render.py queue/<file>.json --out out/` writes `out/<id>/...` and `out/<id>/checks.json`. Exit code is non-zero when a layout check fails (text overflow, missing image, missing label).

## `redesign-carousel` and `redesign-video` data

```json
{
  "business": "Fernleaf Café",
  "post": "06",
  "hook": "Is this café open right now?",
  "hookSub": "Its homepage won't tell you. Here's how we'd fix it.",
  "before": {
    "screen": "screens/fernleaf-before.json",
    "title": "Pretty. No answers.",
    "stat": "Hours: bottom of the page",
    "items": [
      { "title": "Photos fill the screen", "body": "Five slides to swipe before anything useful.", "mark": "slider" }
    ]
  },
  "after": { "screen": "screens/fernleaf-after.json", "title": "...", "stat": "...", "items": [] },
  "cta": "review"
}
```

`mark` names a block id in the phone screen. The renderer measures that block and pins the numbered marker to it, so markers never need coordinates. Leave `mark` out for a problem that is an absence (for example "no licence number").

Phone screens live in `screens/*.json` and are built from the block kit in `engine/kit/blocks.js`. See `docs/BLOCKS.md`.

## `stat-carousel` and `stat-video` data

See `docs/FORMATS.md`. Every number on a stat post must appear in `sources`.

## Rules every spec must follow

- Businesses in redesign posts are fictional. No real business names, logos, phone numbers or addresses. Phone numbers use the ACMA fiction range (0491 570 006, 0491 570 156 to 0491 570 159, 0491 570 110, 0491 570 313, 0491 570 737).
- Every redesign slide carries "Concept · not a client project". The renderer adds it; do not remove it.
- No made-up statistics. Stat posts only use numbers from Pryce's own dataset or a cited source.
- No reviews, testimonials or client results that did not happen.
