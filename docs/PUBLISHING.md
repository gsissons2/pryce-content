# How publishing works

Merging a spec into `main` approves it. From then on the Publish workflow posts it on schedule. Setup is in `docs/SETUP.md`.

## The cycle

Every 15 minutes GitHub runs **Publish**:

1. A quick check job reads every `queue/*.json` on `main` (not `queue/examples/`) and lists due slots: schedule time is now or earlier, the platform is not in `published`, it has not failed 3 times or been given up, and it is no more than 6 hours late (older slots are dropped, never posted late, so adding a platform's keys later cannot set off a backlog). Nothing due: done in about 20 seconds.
2. Otherwise the publish job checks out the `media` branch into `_media` (creating it if missing).
3. **Stage:** any due spec whose files are not already in `_media/media/<id>/`, or whose spec or screens changed since, is rendered and its files copied in (slides, PDF, video, cover).
4. **Deploy:** if `_media` changed, it commits and pushes the `media` branch and deploys it to GitHub Pages at `https://gsissons2.github.io/pryce-content/`. It also redeploys if staged files are not being served.
5. **Publish:** posts each due platform, oldest slot first, using the staged files. It waits until Pages serves each file Instagram and Zernio will fetch (usually instant after the deploy, at most 10 minutes).
6. Right after each platform succeeds, it writes `published.<platform>` into the spec file.
7. Commits the changed spec files to `main` as `publish: <ids> [skip ci]`.
8. Opens a GitHub issue for any slot it has given up on.

A slot whose time passed while the workflow was off (or before you merged) posts on the next run, as long as it is no more than 6 hours late. Older slots are dropped and never posted late. To post one anyway, give it a new time in a PR.

## What each platform gets

| Platform | Carousel formats | Video formats | How the file gets there |
|---|---|---|---|
| Instagram | Carousel of the slide JPGs, alt text from `alt` | Reel with `cover.jpg`, shared to feed | Slides by Pages link. Reels uploaded directly (see below) |
| TikTok | Photo post (title, description, auto music) | Video | Pages link, via Zernio |
| YouTube | Not allowed, gives up at once | Short (vertical video) | Pages link, via Zernio |
| LinkedIn | PDF document post from `carousel.pdf` | Native video | Uploaded directly |

**Instagram Reels** upload the video bytes straight to Instagram (`upload_type=resumable`, then rupload.facebook.com). Meta documents this for Facebook Login apps, and we use Instagram Login, so it may be refused. If it is, the same attempt falls back to the Pages link (`video_url`) and the run log notes it. Set variable `IG_REELS_UPLOAD` to `url` to always use the link.

LinkedIn's document or video title is `data.hook`. TikTok photo title is the first sentence of `captions.tiktok` (no hashtags, max 90 characters) and the description is the whole caption.

## No double posts

- A platform listed in `published` is never posted again.
- `published` is written to disk the moment a platform succeeds, before the next platform starts.
- The commit step runs even if the run crashed or timed out.
- Only one Publish (or Media cleanup) run at a time, queued, never cancelled.
- If the final publish call was sent but no answer came back (timeout or a 5xx error), we cannot know if it went live. The publisher gives up on that slot at once and opens an issue instead of retrying. Same for unexpected errors in the code.
- If pushing the results fails 5 times, the run goes red with "Could not push". Check `queue/` straight away, because the next run could post the same thing again.

## Failures and retries

- **Normal failure** (network, platform error, render failed, Pages slow): recorded in `failed.<platform>` and tried again on the next run, 15 minutes later. After 3 failures it gives up and opens an issue titled `Publish failed: <id> on <platform>`.
- **Permanent failure** (YouTube on a carousel, more than 10 slides, file over 25 MB, unknown format): gives up at once.
- **Skip, not a failure**: Instagram daily limit used up, or a platform's secrets are not set yet. Nothing is written, it tries again next run, for up to 6 hours after the slot.

The shape is in `docs/SPEC.md`: `at` and `error` hold the latest failure, `history` has one entry per failure, `gave_up: true` appears when it stops.

## Limits

- **Instagram**: Meta's guide says 100 API posts per account per 24 hours, the limit endpoint's reference says 50. We read the real number before every post and skip if it is used up. A carousel counts as one post. Max 10 items per carousel through the API (ours have 5 or 6). Caption 2,200 characters, 30 hashtags, 20 @mentions. JPEG only. Reels get up to 10 minutes to process.
- **TikTok** (via Zernio): about 15 posts a day per account, shared with anything you post in the app. Photo posts up to 35 images, title 90, description 4,000. Video caption 2,200.
- **YouTube** (via Zernio): video formats only. Our 1080x1920 videos under 3 minutes count as Shorts. Title max 100 characters, no `<` or `>`.
- **LinkedIn**: token lasts 60 days and cannot be refreshed on a self-serve app. Post text 3,000 characters. PDF up to 100 MB and 300 pages. Video 75 KB to 500 MB, 3 seconds to 30 minutes. API version is `202610` (`LINKEDIN_VERSION` in `publish/linkedin.py`). LinkedIn retires each version after about a year, so bump it each autumn.
- **Media**: 25 MB per file. Pages sites should stay under 1 GB, and the monthly cleanup keeps it well below that.
- **GitHub Actions**: free for public repos, so the 15-minute schedule costs nothing. If the repo ever goes private, use the budget schedule commented in `publish.yml` (about 1,300 short runs a month, only in Melbourne posting windows). Scheduled runs can start 5 to 20 minutes late when GitHub is busy.

## Captions

Nothing is cut silently. Over-limit text is trimmed at a word with "…" and a warning shows in the run log and in the PR preview comment, so you can fix it before merging. LinkedIn text has its reserved characters escaped, and `#tags` become real LinkedIn hashtags.

## When something fails

1. Open the issue. It names the spec, the platform and the last error.
2. Check the platform itself. Did it post anyway? This matters most for "may or may not have posted".
3. **It did post:** on `main`, edit the spec and remove that platform from `schedule`. Close the issue.
4. **It did not post and you want it to:** fix the cause (see below), then on `main` delete `failed.<platform>` from the spec. The next run posts it, straight away if its time has passed. Close the issue.

| Error says | Fix |
|---|---|
| `... is not set, so this platform is not configured yet` | Add the missing secret (docs/SETUP.md) |
| Instagram error code 190 or `OAuthException` | Token expired. Redo SETUP.md C6 |
| LinkedIn `HTTP 401` | Token expired. Redo SETUP.md D5 to D7 |
| `Instagram daily publishing limit used up` | Nothing. It waits and retries |
| `GitHub Pages ... still not ready` | Open the run and check the deploy-pages step. Settings, Pages must say Source: GitHub Actions |
| `render failed` | The spec does not render on `main`. Fix it in a PR, the preview shows the problem |
| Zernio `privacy level` | Set variable `ZERNIO_TIKTOK_PRIVACY` |
| Zernio `HTTP 402` | Zernio plan limit. Check the Zernio dashboard |
| `Could not push` (red run) | Check `queue/` on `main` now, before the next run |

## Running it by hand

```
python -m publish.run --dry-run --now 2026-11-17T19:05:00+11:00
python -m publish.run --check
python -m unittest tests.test_publish
```

`--dry-run` renders into `out/`, prints every HTTP request (method, URL, headers with tokens hidden, JSON body) and sends nothing. In GitHub: Actions, Publish, Run workflow, dry_run ticked. A live run outside the workflow posts to LinkedIn only, because Pages hosting happens inside the workflow.

## Other workflows

- **Render preview** (every PR touching `queue/`, `screens/` or `assets/photos/`): renders changed specs, commits previews to `previews/pr-<n>/` on the `media` branch, and posts one comment with the slides inline (via raw.githubusercontent.com), video links, checks and caption warnings. PRs never deploy Pages. The PR goes red if a render check fails. A first job saves 400 px previews of new manifest photos and commits them to the PR branch.
- **Token check** (weekly, Monday morning): prints who each credential belongs to, refreshes the Instagram token, and opens an issue if a token expires within 10 days.
- **Redeploy media** (manual): publishes the `media` branch to Pages again. Use it if a Publish run failed at the Pages step.
- **Media cleanup** (monthly): on the `media` branch, deletes `media/` folders older than 45 days and `previews/` older than 14 days, squashes the branch to one commit so old videos stop taking space, force-pushes only `media`, and redeploys Pages. Preview links on old PRs stop working after that.
