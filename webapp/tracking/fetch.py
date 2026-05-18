"""Daily TikTok stats fetcher.

For every account connected via OAuth, this:
  1. Refreshes the access token using the stored refresh_token
  2. Pulls fresh user info (follower / video / total likes counts)
  3. Pulls up to 200 most recent videos with per-video stats
  4. Writes a snapshot to webapp/tracking/data/snapshots/<YYYY-MM-DD>.json

Run it manually or via cron:
    0 6 * * *  cd ~/Documents/UGC_slideshow && python3 -m webapp.tracking.fetch
"""
from __future__ import annotations

import os
import sys
import time
import traceback
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.dirname(HERE))

# Load env from repo root
def _load_env() -> None:
    env_path = os.path.join(ROOT, ".env")
    if os.path.exists(env_path):
        for line in open(env_path):
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            os.environ.setdefault(k, v)


_load_env()
from tracking import tiktok_api, store  # noqa: E402


def fetch_one_account(label: str) -> dict:
    """Refresh token + pull latest stats for a single TikTok account."""
    acct = store.get_account(label)
    if not acct:
        raise RuntimeError(f"no stored account for label '{label}'")
    if acct.get("provider") != "tiktok":
        raise RuntimeError(f"provider not tiktok for label '{label}'")

    # 1. Refresh token if expired or close to expiring
    now = int(time.time())
    exp = acct.get("expires_at") or 0
    if exp - now < 60:  # refresh if within 60s of expiry
        rt = acct.get("refresh_token")
        if not rt:
            raise RuntimeError(f"no refresh_token for '{label}', re-auth needed")
        body = tiktok_api.refresh_access_token(rt)
        access_token = body["access_token"]
        new_refresh = body.get("refresh_token", rt)
        new_exp = now + int(body.get("expires_in", 3600))
        store.save_account(label, {
            "access_token": access_token,
            "refresh_token": new_refresh,
            "expires_at": new_exp,
        })
    else:
        access_token = acct["access_token"]

    # 2. User info
    user = tiktok_api.get_user_info(access_token)
    store.save_account(label, {
        "open_id": user.get("open_id"),
        "display_name": user.get("display_name"),
        "avatar_url": user.get("avatar_url"),
        "follower_count": user.get("follower_count"),
        "video_count": user.get("video_count"),
        "likes_count": user.get("likes_count"),
        "is_verified": user.get("is_verified"),
        "last_fetched_at": now,
    })

    # 3. Videos
    videos = tiktok_api.list_all_videos(access_token, hard_cap=200)
    return {"user": user, "videos": videos, "fetched_at": now}


def fetch_all() -> dict:
    """Run a daily snapshot for every connected account."""
    accounts = store.list_accounts()
    print(f"Fetching {len(accounts)} account(s)…")
    payload: dict = {"accounts": {}, "errors": {}}
    for a in accounts:
        label = a["label"]
        try:
            print(f"  → {label}")
            payload["accounts"][label] = fetch_one_account(label)
        except Exception as e:
            print(f"  !! {label} failed: {e}")
            traceback.print_exc()
            payload["errors"][label] = str(e)

    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    payload["snapshot_date"] = date_str
    payload["snapshot_time"] = int(time.time())
    p = store.save_snapshot(date_str, payload)
    print(f"\nSaved snapshot: {p}")
    return payload


if __name__ == "__main__":
    if len(sys.argv) > 1:
        # python -m webapp.tracking.fetch <label>
        label = sys.argv[1]
        result = fetch_one_account(label)
        print(f"OK — {label}: {len(result['videos'])} videos pulled")
    else:
        fetch_all()
