# pryce-content

The Pryce Digital content machine. Post specs go in, finished carousels and videos come out, and they get posted on schedule.

```
weekly writer (Claude)  ->  PR with next week's specs + previews  ->  Graham merges  ->  publisher posts on schedule
```

- `queue/` post specs, one JSON per post. Merged to `main` = approved. See `docs/SPEC.md`.
- `screens/` phone screens for concept redesigns, built from the block kit (`docs/BLOCKS.md`).
- `engine/` renderer: `python engine/render.py queue/<spec>.json --out out/`. Checks layout, labels and numbers, fails loudly.
- `data/` the 12,621-site study. The only source for numbers in data posts.
- `publish/` posting to Instagram, LinkedIn (own apps, free) and TikTok + YouTube (Zernio free tier).
- `.github/workflows/` render previews on PRs, publish every 15 minutes, token reminders, media cleanup.
- `docs/WRITER.md` the brief the weekly writer follows. `docs/SETUP.md` Graham's one-time setup.

Local setup: `pip install -r requirements.txt && python -m playwright install chromium`, plus ffmpeg.
