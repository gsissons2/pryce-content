# One-time setup

About an hour, mostly logins. Everything lives in one **public** repo, `gsissons2/pryce-content`. It also hosts the images and videos the platforms fetch, on GitHub Pages, so there is no second repo and no GitHub token to make.

- **[Claude does this]** steps need no logins of yours.
- **[Graham]** steps need your accounts. Only you handle passwords, keys and tokens.

Public means anyone can read the repo, including queued posts before they go out. Secrets stay private.

**Where secrets go:** in `pryce-content` on GitHub, Settings, Secrets and variables, Actions. **Secrets** tab for secrets, **Variables** tab for variables. Names must match exactly.

## A. Repo and Pages (done 13 Nov 2026)

- Public repo `gsissons2/pryce-content` created and code pushed.
- `media` branch created (it holds the images and videos, separate from the code).
- Settings, Pages, Source: **GitHub Actions**. Tested with the Redeploy media workflow: media serves at `https://gsissons2.github.io/pryce-content/`.
- Weekly writer set up as a scheduled Claude task, Fridays 14:36 Melbourne.

## B. TikTok and YouTube (Zernio)

TikTok and YouTube keep posts private for apps that have not passed their audit. Zernio's apps have, so we post through it. Free plan: first 2 connected accounts, 60 API calls a minute (we use a handful a day).

1. **[Graham]** Sign up at zernio.com and create an API key (done 14 Nov 2026).
2. **[Graham]** In the Zernio dashboard, connect TikTok (log in as **@prycedigital**) and YouTube (the Google account that owns the **@prycedigital** channel). Allow everything it asks for.
3. **[Graham]** Add the key as secret `ZERNIO_API_KEY` (Settings, Secrets and variables, Actions, New repository secret).
4. **[Graham]** Run Actions, Token check, Run workflow. In the log you want `Zernio: tiktok @prycedigital id=...`, `Zernio: youtube ... id=...`, a line of TikTok privacy levels that includes `PUBLIC_TO_EVERYONE`, and `TikTok preflight (dry run, nothing posted): can publish True` (Zernio checks a sample photo post without creating it). Any problem opens an issue with what to fix.

That is all. The account ids are looked up from the key on every run, so there are no ids to copy. Optional variables: `ZERNIO_TIKTOK_USERNAME` / `ZERNIO_YOUTUBE_USERNAME` only if you ever connect a second TikTok or YouTube account, and `ZERNIO_TIKTOK_PRIVACY` only if Token check says TikTok does not offer `PUBLIC_TO_EVERYONE`.

If a TikTok post is still processing when the run finishes (TikTok can take hours), it is recorded as sent with a note and no link, and is never sent twice. The link shows in the Zernio dashboard.

## C. Instagram (@madebypryce)

1. **[Graham]** In the Instagram app, @madebypryce must be a professional account. Profile, menu, Settings, Account type and tools, Switch to professional account. Creator or Business both work.
2. **[Graham]** Go to developers.facebook.com, log in, My Apps, Create app. Pick the use case for managing messaging and content on Instagram. Name it `Pryce Publisher`. This gives you "Instagram API" with "API setup with Instagram login".
3. **[Graham]** App roles, Roles, Add people, **Instagram Tester**, enter `madebypryce`.
4. **[Graham]** Accept the invite as @madebypryce: open instagram.com in a browser, Settings, Apps and websites, Tester invites, Accept. (Meta moves this page around. If it is not there, search Instagram Help for "tester invite".)
5. **[Graham]** Back in the app: Instagram, API setup with Instagram login. Check the permissions list has `instagram_business_basic` and `instagram_business_content_publish`. Standard Access is enough because you own the account. No App Review.
6. **[Graham]** Under "Generate access tokens", Add account, log in as @madebypryce, allow. Click Generate token and copy it. It lasts 60 days. Add it as secret `IG_ACCESS_TOKEN`.
7. **[Graham]** The same section shows the account's id. Add it as secret `IG_USER_ID`.
8. **[Graham]** Check it: run Token check. It should print `Instagram: @madebypryce user_id=...`, and that number must equal `IG_USER_ID`. If they differ, use the printed `user_id`.
9. Leave the app in Development mode. That is fine for your own tester account.

Token check refreshes this token every week, which pushes its expiry out another 60 days. If Instagram ever hands back a different token string, Token check opens an issue and you redo step 6.

## D. LinkedIn (your personal profile)

1. **[Graham]** LinkedIn only allows a developer app that is tied to a Company Page. If Pryce Digital has no page yet: linkedin.com, the grid icon (For Business), Create a Company Page. Free.
2. **[Graham]** Go to linkedin.com/developers/apps, Create app. Name `Pryce Publisher`, LinkedIn Page: Pryce Digital, privacy policy URL from your site, a logo. Create.
3. **[Graham]** In the app's Settings tab, verify the app for the page. As the page admin, open the verification link and approve.
4. **[Graham]** Products tab: request **Share on LinkedIn** and **Sign In with LinkedIn using OpenID Connect**. Both are self-serve and normally approved straight away.
5. **[Graham]** Get a token with the token generator: linkedin.com/developers/tools/oauth/token-generator. Pick the app, tick `openid`, `profile`, `w_member_social`, Request access token, log in, Allow, copy the token. If it complains about a redirect URL, add `https://www.linkedin.com/developers/tools/oauth/redirect` in the app's Auth tab under Authorized redirect URLs, then try again.
6. **[Graham]** Add it as secret `LINKEDIN_ACCESS_TOKEN`.
7. **[Graham]** Add **variable** (not secret) `LINKEDIN_TOKEN_EXPIRES`, today plus 60 days as `YYYY-MM-DD`. Example: made on 13 Nov 2026, enter `2027-01-12`.
8. **[Graham]** Run Token check. It prints `LinkedIn: person URN is urn:li:person:...` (the `sub` from LinkedIn's `/v2/userinfo`).
9. Optional: add that whole `urn:li:person:...` as secret `LINKEDIN_PERSON_URN`. Without it the publisher reads it from the token each run.

Every 60 days: redo steps 5, 6 and 7. Self-serve LinkedIn tokens cannot be refreshed. Token check opens an issue 10 days before expiry.

## E. Test it

1. **[Graham]** Actions, Publish, Run workflow. Leave **dry_run** ticked. In **now**, put a time after a queued spec's schedule, for example `2026-11-17T19:05:00+11:00`. Run.
2. Open the run, then the Publish step. It lists every request it would send (Instagram, LinkedIn, Zernio) with tokens hidden. Nothing is posted, pushed or deployed.
3. If it says "Nothing due", no spec in `queue/` has a time before **now**. Pick a later time.
4. **[Graham]** Run Token check. You want four identity lines (Instagram, LinkedIn, TikTok, YouTube) and no warnings.
5. **[Graham]** First real post: merge a spec scheduled 30 minutes ahead for one platform and watch the next Publish runs. The spec file gets a `published` entry with the link.

## All secrets and variables

| Name | Type | What |
|---|---|---|
| `ZERNIO_API_KEY` | secret | Zernio API key |
| `ZERNIO_TIKTOK_USERNAME` | variable, optional | only if Zernio has more than one TikTok account |
| `ZERNIO_YOUTUBE_USERNAME` | variable, optional | only if Zernio has more than one YouTube account |
| `IG_ACCESS_TOKEN` | secret | Instagram token (60 days, refreshed weekly) |
| `IG_USER_ID` | secret | Instagram account id (`user_id`) |
| `LINKEDIN_ACCESS_TOKEN` | secret | LinkedIn token (60 days, cannot refresh) |
| `LINKEDIN_PERSON_URN` | secret, optional | `urn:li:person:...` (read from the token if unset) |
| `LINKEDIN_TOKEN_EXPIRES` | variable | LinkedIn token expiry, `YYYY-MM-DD` |
| `ZERNIO_TIKTOK_PRIVACY` | variable, optional | TikTok privacy level, default `PUBLIC_TO_EVERYONE` |
| `IG_REELS_UPLOAD` | variable, optional | `url` to always send Reels by link instead of direct upload |

The workflows use GitHub's built-in token for everything inside the repo, so there is no GitHub token to create.
