# Tracking — daily TikTok analytics for your accounts

This module pulls **plays, likes, comments, shares, and follower counts** for
TikTok accounts you own, via TikTok's official Display API. No scraping.

## Setup checklist (one-time, ~20 minutes)

### 1. Register a TikTok developer app

1. Go to <https://developers.tiktok.com/> and sign in with **any** of your TikTok accounts (this becomes the app owner — pick the main one, e.g. `nutrilens.ai`).
2. Click **Manage apps → Connect an app**.
3. Fill in:
   - **App name**: `Slidecast Studio Tracking` (or anything)
   - **Description**: "Internal analytics dashboard for owned accounts"
   - **Category**: Tools / Utility
   - **Web** as the platform
4. Under **Add products**, enable:
   - **Login Kit for Web**
   - **Display API**

### 2. Configure the Login Kit

Inside the Login Kit settings:

- **Redirect URI**: `http://localhost:8765/auth/tiktok/callback`
   (For localhost development. TikTok explicitly allows HTTP on localhost.)
- **Scopes requested**: tick `user.info.basic`, `user.info.profile`, `user.info.stats`, `video.list`

### 3. Add your 13 TikTok accounts as test users

While the app is still in **Sandbox / Staging** mode, you can only authorize accounts that are listed as test users. In the dev console:

- **Sandbox → Add test user** for each of:
   `nutrilens.ai`, `myrecipefolder`, `recipehackswithsusan`, `SlidecastApp`,
   `slidecast.app`, `recipediahealthy`, `recipehackdaily`, `thekitchenfolder`,
   `myrecipefinds`, `savedrecipeclub4`, `RecipeToReality5`, `Emma.healthyplates`,
   `sophiec811`

Each test user must accept the invite (TikTok sends a notification in-app). Once accepted, they can authorize the app.

(Alternative: skip sandbox and submit the app for review. Approval takes 1-3 days and removes the test-user requirement. For 13 accounts the sandbox path is faster.)

### 4. Copy the credentials into `.env`

In your dev-console **App Details** page, copy:

- **Client Key** → `TIKTOK_CLIENT_KEY`
- **Client Secret** → `TIKTOK_CLIENT_SECRET`

Then add these lines to `/Users/harshbansal/Documents/UGC_slideshow/.env`:

```
TIKTOK_CLIENT_KEY=aw...your_key
TIKTOK_CLIENT_SECRET=your_secret
TIKTOK_REDIRECT_URI=http://localhost:8765/auth/tiktok/callback
```

### 5. Restart the server

```bash
python3 webapp/server.py
```

The yellow warning on the Tracking page should disappear.

### 6. Connect each account

For each of your 13 accounts:

1. Open the webapp at <http://localhost:8765/#tracking>
2. Type a nickname (e.g. `nutrilens`) in the "Account nickname" field
3. Click **Connect TikTok** — you'll be redirected to TikTok's login
4. Sign in with that specific account (use Incognito windows or TikTok's account switcher to make this easier across 13 logins)
5. Approve the app's requested scopes
6. You're redirected back to the dashboard

Do this 13 times. Each connection stores a `refresh_token` that lasts forever (unless you revoke it). You only do this once per account.

### 7. Pull your first snapshot

Click **Refresh snapshot** on the Tracking page, or run it manually:

```bash
python3 -m webapp.tracking.fetch
```

After ~30 seconds, the dashboard will populate with totals + per-account stats + top posts.

### 8. Schedule daily refreshes

Add this to your crontab (`crontab -e`):

```cron
0 6 * * *  cd ~/Documents/UGC_slideshow && /usr/bin/python3 -m webapp.tracking.fetch >> ~/Documents/UGC_slideshow/tracking.log 2>&1
```

That runs every morning at 6am. Your dashboard always shows yesterday's close.

---

## What the API returns per video

The fields we pull (from `/v2/video/list/`):

| Field | Description |
|---|---|
| `view_count` | Plays |
| `like_count` | Hearts |
| `comment_count` | Comments |
| `share_count` | Shares |
| `title`, `video_description` | Caption text |
| `cover_image_url` | Thumbnail |
| `share_url` | Public URL of the post |
| `create_time` | Unix timestamp of when posted |
| `duration` | Length in seconds |

We do NOT have access to:
- **Watch time / average watch %** (only in TikTok Studio)
- **Profile views, traffic sources** (only in TikTok Studio)
- **Audience demographics** (need Business Account + Insights API)

For those, export TikTok Studio CSVs and drop them into `tracking/data/imports/` — we can wire up an importer if needed.

## Files

```
webapp/tracking/
  README.md                 ← this file
  tiktok_api.py             ← API client
  store.py                  ← token + snapshot storage
  fetch.py                  ← daily runner
  data/
    tokens.json             ← per-account refresh tokens (gitignore this!)
    snapshots/
      2026-05-11.json
      2026-05-12.json
      ...
```

## Security

- `data/tokens.json` contains long-lived refresh tokens — **add it to `.gitignore`** and never share.
- TikTok refresh tokens last forever but can be revoked anytime in the dev console.
- Display API is read-only — you cannot post or modify content through it.
