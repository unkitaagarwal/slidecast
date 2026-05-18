"""TikTok Display API v2 client.

Handles OAuth (Login Kit) and the read-only Display API endpoints used for
analytics on accounts you own:
  - POST /v2/oauth/token/             ← exchange code, refresh token
  - GET  /v2/user/info/?fields=…      ← profile counts (followers etc.)
  - POST /v2/video/list/?fields=…     ← list videos with stats
  - POST /v2/video/query/?fields=…    ← per-video detail by ID

Scopes used: user.info.basic, user.info.profile, user.info.stats, video.list

Docs: https://developers.tiktok.com/doc/display-api-get-started/
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
import time
import urllib.parse
from typing import Optional

import requests


# ---------------------------------------------------------------------------
# PKCE helpers (TikTok requires PKCE for the authorization-code grant)
# ---------------------------------------------------------------------------

def generate_pkce_verifier(length: int = 64) -> str:
    """Generate a high-entropy PKCE code_verifier (43-128 unreserved chars)."""
    # secrets.token_urlsafe gives base64url without padding; strip leftover '='
    return secrets.token_urlsafe(length)[:length]


def pkce_challenge(verifier: str) -> str:
    """Compute the S256 code_challenge for a verifier."""
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


API_HOST = "https://open.tiktokapis.com"
AUTH_HOST = "https://www.tiktok.com"

# Display API scopes we need for analytics on owned accounts
SCOPES = "user.info.basic,user.info.profile,user.info.stats,video.list"


# ---------------------------------------------------------------------------
# Config (loaded from .env at runtime)
# ---------------------------------------------------------------------------

def _get_creds() -> tuple[str, str, str]:
    """Returns (client_key, client_secret, redirect_uri)."""
    client_key = os.environ.get("TIKTOK_CLIENT_KEY", "").strip()
    client_secret = os.environ.get("TIKTOK_CLIENT_SECRET", "").strip()
    # The redirect URI MUST exactly match what's registered in the TikTok
    # developer console. Default works with `python3 webapp/server.py` on
    # localhost:8765.
    redirect_uri = os.environ.get(
        "TIKTOK_REDIRECT_URI",
        "http://localhost:8765/auth/tiktok/callback",
    ).strip()
    return client_key, client_secret, redirect_uri


def creds_configured() -> bool:
    k, s, _ = _get_creds()
    return bool(k and s)


# ---------------------------------------------------------------------------
# OAuth
# ---------------------------------------------------------------------------

def build_authorize_url(state: str, code_challenge: str, label: str = "") -> str:
    """Return the URL the user must visit to authorize a TikTok account.

    `state` is opaque to TikTok; we use it to round-trip the account label.
    `code_challenge` is the PKCE S256 challenge derived from a verifier we
    keep server-side (passed back into ``exchange_code``).
    """
    client_key, _, redirect_uri = _get_creds()
    state_payload = f"{state}|{label}" if label else state
    params = {
        "client_key": client_key,
        "scope": SCOPES,
        "response_type": "code",
        "redirect_uri": redirect_uri,
        "state": state_payload,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }
    return f"{AUTH_HOST}/v2/auth/authorize/?{urllib.parse.urlencode(params)}"


def exchange_code(code: str, code_verifier: str) -> dict:
    """Exchange an authorization code for an access + refresh token.
    Requires the PKCE ``code_verifier`` that matches the challenge sent at
    /authorize/."""
    client_key, client_secret, redirect_uri = _get_creds()
    r = requests.post(
        f"{API_HOST}/v2/oauth/token/",
        headers={"Content-Type": "application/x-www-form-urlencoded",
                 "Cache-Control": "no-cache"},
        data={
            "client_key": client_key,
            "client_secret": client_secret,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": redirect_uri,
            "code_verifier": code_verifier,
        },
        timeout=30,
    )
    r.raise_for_status()
    body = r.json()
    if "error" in body and body.get("error"):
        raise RuntimeError(f"TikTok OAuth error: {body}")
    return body


def refresh_access_token(refresh_token: str) -> dict:
    """Use a refresh_token to mint a new access_token."""
    client_key, client_secret, _ = _get_creds()
    r = requests.post(
        f"{API_HOST}/v2/oauth/token/",
        headers={"Content-Type": "application/x-www-form-urlencoded",
                 "Cache-Control": "no-cache"},
        data={
            "client_key": client_key,
            "client_secret": client_secret,
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        },
        timeout=30,
    )
    r.raise_for_status()
    body = r.json()
    if body.get("error"):
        raise RuntimeError(f"TikTok refresh error: {body}")
    return body


# ---------------------------------------------------------------------------
# Display API
# ---------------------------------------------------------------------------

USER_FIELDS = (
    "open_id,union_id,avatar_url,display_name,bio_description,"
    "is_verified,follower_count,following_count,likes_count,video_count"
)

VIDEO_FIELDS = (
    "id,title,video_description,duration,cover_image_url,share_url,"
    "embed_link,like_count,comment_count,share_count,view_count,create_time"
)


def get_user_info(access_token: str) -> dict:
    r = requests.get(
        f"{API_HOST}/v2/user/info/",
        headers={"Authorization": f"Bearer {access_token}"},
        params={"fields": USER_FIELDS},
        timeout=30,
    )
    r.raise_for_status()
    body = r.json()
    if body.get("error", {}).get("code") not in (None, "ok"):
        raise RuntimeError(f"user/info error: {body}")
    return body.get("data", {}).get("user", {})


def list_videos(access_token: str, cursor: int = 0,
                max_count: int = 20) -> dict:
    """Fetch one page of videos. Returns {'videos': [...], 'cursor': N, 'has_more': bool}."""
    r = requests.post(
        f"{API_HOST}/v2/video/list/",
        headers={"Authorization": f"Bearer {access_token}",
                 "Content-Type": "application/json"},
        params={"fields": VIDEO_FIELDS},
        json={"max_count": max_count, "cursor": cursor},
        timeout=30,
    )
    r.raise_for_status()
    body = r.json()
    if body.get("error", {}).get("code") not in (None, "ok"):
        raise RuntimeError(f"video/list error: {body}")
    data = body.get("data", {})
    return {
        "videos": data.get("videos", []) or [],
        "cursor": data.get("cursor", 0),
        "has_more": data.get("has_more", False),
    }


def list_all_videos(access_token: str, hard_cap: int = 200) -> list[dict]:
    """Paginate /video/list/ until exhausted or we hit hard_cap videos."""
    out: list[dict] = []
    cursor = 0
    while True:
        page = list_videos(access_token, cursor=cursor, max_count=20)
        out.extend(page["videos"])
        if not page["has_more"] or len(out) >= hard_cap:
            break
        cursor = page["cursor"]
    return out[:hard_cap]
