# Weekly writer brief

This is the instruction file for the weekly writing run (a scheduled Claude task, or Graham in a Claude Code session). The run drafts next week's posts as spec files, renders them, and opens one pull request. Graham approves by merging. Nothing is ever posted from a branch.

## The run, step by step

1. Clone `gsissons2/pryce-content`, create branch `week/<YYYY-MM-DD>` (the Monday the batch starts).
2. Read `docs/SPEC.md`, `docs/FORMATS.md`, `docs/BLOCKS.md`, `data/README.md`, and the last 4 weeks of `queue/` so nothing repeats (same business type two weeks in a row, same stat angle within a month).
3. If `data/performance.json` exists, weight next week's mix toward the formats and topics with the best saves, shares and watch time. Never drop a format entirely on one bad week.
4. Write the specs for the week (mix below) into `queue/`.
5. Run `python engine/fetch_photos.py` then `python engine/render.py queue/<new files> --out out/`. Fix every error and every warning by editing the spec, never the templates. Re-render until clean.
6. Look at every rendered slide and the video cover frames yourself. If anything looks wrong (marker on top of text, awkward line break, photo that does not fit the business), fix it.
7. Commit the specs (not `out/`), push the branch, open a PR titled `Posts for week of <date>`. The PR body is a table: date, time, platforms, format, hook. The render-preview workflow adds the images.
8. Stop. Do not merge.

## Weekly mix (start here, adjust with data)

| Per week | What | Becomes |
|---|---|---|
| 4 | Concept redesigns (fictional business) | 4 `redesign-carousel` + 4 `redesign-video` |
| 3 | Data posts from the study | 3 `stat-carousel` + 3 `stat-video` |

That is 7 carousels and 7 videos a week. Daily slots (Melbourne time):

| Platform | Carousels | Videos |
|---|---|---|
| Instagram | 1 a day, 19:00 | 1 a day, 12:30 (Reel) |
| TikTok | 1 a day, 19:30 (photo post) | 1 a day, 12:45 |
| YouTube | none | 1 a day, 18:00 (Short) |
| LinkedIn | Mon, Wed, Fri 08:15 (PDF) | Tue, Thu 08:15 |

LinkedIn caps at 5 posts a week (more cuts reach). Raise video volume only when a new video format is added (see "Formats wanted" below), not by repeating the same video.

## Concept redesigns

- The business is invented. Before using a name, web search it with "Australia" and the trade. If a real business uses it, pick another. Never use the name of any real hotel, restaurant, venue or trade business.
- Use only industries the block kit supports (see `docs/BLOCKS.md`): cafes, bakeries, restaurants (the cafe kit), plumbers, electricians, other trades (the trades kit), motels, B&Bs, caravan parks, small hotels (the booking kit). For a new industry, write it in the PR body under "Needs a new kit" instead of forcing it.
- Real suburbs are fine (Brunswick East, Port Melbourne). Real street addresses are not.
- Phone numbers only from the ACMA fiction range (0491 570 006, 0491 570 156 to 159, 0491 570 110, 0491 570 313, 0491 570 737). Licence numbers: "12345".
- The "before" problems must be things real small-business sites actually do: photo sliders, PDF menus, hidden phone numbers, stock photos, long forms, booking engines that drop the dates, slow loading, no prices, pop-ups. Do not invent absurd problems to make the fix look better.
- The "after" fixes must be things Pryce would actually build.
- Four items a side at most. Each item title fits on one line where possible (about 24 characters), the body on two lines.
- Photos: reuse `assets/photos/` where they fit. To add one, find an Unsplash photo, add it to `assets/photos/manifest.json` and save a 400 px preview at the same path.

## Data posts

- Every number comes from `data/lighthouse-2026.json`. The render fails if a number is not in it. Put the source line in `sources`.
- Respect the caveats in `data/README.md`: lab test wording, medians, groups of 80 plus.
- Good angles: one industry against the median, platform comparisons, the lab vs real-visitor gap, how many sites take over 4 or 10 seconds, best and worst industries, a state comparison, page weight.
- One idea per post. The first slide carries the hook number. Last slide is the call to action.

## Words

- Plain and direct. Short sentences. No jargon on slides (no "LCP", say "time to show the main content"). No hype, no "game-changer", no emojis on slides.
- Australian spelling. No em dashes, use commas or full stops.
- Hooks are questions or blunt statements a business owner would stop for: "Is this café open right now?", "11 seconds."
- Captions: Instagram 2 to 4 short paragraphs, then 4 or 5 hashtags. TikTok one or two lines, 3 hashtags. LinkedIn plain text in Graham's voice, first person is fine, no hashtags needed. YouTube title under 70 characters.
- Every redesign caption says it is a concept of a fictional business and not a client project.
- The call to action is the free review at prycedigital.com/book. Never promise prices or timelines in captions.

## Never

- No real businesses in a negative light, no screenshots of real sites, no competitor names.
- No testimonials, ratings, review counts or client results.
- No numbers that are not in the data bank.
- Never merge the PR, never edit the publish workflow, never touch `published` fields.

## Formats wanted (build these next, in a Claude Code session)

- `stat-flash`: a 6 to 8 second single-number video for TikTok and Shorts volume.
- `spot-the-problem`: a before screen shown for 3 seconds with "what's wrong here?", then the answer.
- Voiceover: once Graham's ElevenLabs voice exists, a `vo` field per spec with a script, rendered to audio and mixed into the video.
