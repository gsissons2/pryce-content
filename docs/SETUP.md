# One-time setup

About an hour, mostly logins. Everything lives in one **public** repo, `gsissons2/pryce-content`. It also hosts the images and videos the platforms fetch, on GitHub Pages, so there is no second repo and no GitHub token to make.

- **[Claude does this]** steps need no logins of yours.
- **[Graham]** steps need your accounts. Only you handle passwords, keys and tokens.

Public means anyone can read the repo, including queued posts before they go out. Secrets stay private.

**Where secrets go:** in `pryce-content` on GitHub, Settings, Secrets and variables, Actions. **Secrets** tab for secrets, **Variables** tab for variables. Names must match exactly.

## A. Repo and Pages

1. **[Claude does this]** Create the public repo `gsissons2/pryce-content` and push the code.
2. **[Claude does this]** Create the `media` branch (it holds the images and videos, separate from the code).
3. **[Claude does this]** Settings, Pages, Source: **GitHub Actions**. The Publish workflow deploys the `media` branch there, at `https://gsissons2.github.io/pryce-content/`.
4. **[Graham]** Quick check on your phone: Settings, Pages shows Source "GitHub Actions". Nothing else to do.

## B. TikTok and YouTube (Zernio)

TikTok and YouTube keep posts private for apps that have not passed their audit. Zernio's apps have, so we post through it.

1. **[Graham]** Sign up at zernio.com. The free plan covers your first 2 connected accounts.
2. **[Graham]** Connect TikTok, log in as **@prycedigital**, allow.
3. **[Graham]** Connect YouTube, log in with the Google account that owns the **@prycedigital** channel, allow.
4. **[Graham]** In Zernio settings, create an API key. Add it as secret `ZERNIO_API_KEY`.
5. **[Graham]** Get the account ids: Actions, Token check, Run workflow. Open the run, then "Check and refresh tokens". It prints lines like `Zernio: tiktok @prycedigital id=...`.
6. **[Graham]** Add secrets `ZERNIO_TIKTOK_ACCOUNT_ID` and `ZERNIO_YOUTUBE_ACCOUNT_ID` with those ids.
7. Optional: TikTok posts go out as `PUBLIC_TO_EVERYONE`. If a post fails with a privacy error, add variable `ZERNIO_TIKTOK_PRIVACY` with a level TikTok allows for the account.

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
9. **[Graham]** Add that whole `urn:li:person:...` as secret `LINKEDIN_PERSON_URN`.

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
| `ZERNIO_TIKTOK_ACCOUNT_ID` | secret | Zernio id for TikTok @prycedigital |
| `ZERNIO_YOUTUBE_ACCOUNT_ID` | secret | Zernio id for YouTube @prycedigital |
| `IG_ACCESS_TOKEN` | secret | Instagram token (60 days, refreshed weekly) |
| `IG_USER_ID` | secret | Instagram account id (`user_id`) |
| `LINKEDIN_ACCESS_TOKEN` | secret | LinkedIn token (60 days, cannot refresh) |
| `LINKEDIN_PERSON_URN` | secret | `urn:li:person:...` |
| `LINKEDIN_TOKEN_EXPIRES` | variable | LinkedIn token expiry, `YYYY-MM-DD` |
| `ZERNIO_TIKTOK_PRIVACY` | variable, optional | TikTok privacy level, default `PUBLIC_TO_EVERYONE` |
| `IG_REELS_UPLOAD` | variable, optional | `url` to always send Reels by link instead of direct upload |

The workflows use GitHub's built-in token for everything inside the repo, so there is no GitHub token to create.
