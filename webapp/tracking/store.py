"""JSON-backed storage for tracking data.

Layout under webapp/tracking/data/:
  tokens.json              ← { "<label>": { provider, refresh_token, access_token,
                                            expires_at, open_id, display_name, … } }
  snapshots/<YYYY-MM-DD>.json    ← daily fetch result, keyed by account label
                                    { "<label>": { user: {...}, videos: [...] } }
"""
from __future__ import annotations

import json
import os
import threading
import time
from typing import Optional

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(HERE, "data")
TOKENS_PATH = os.path.join(DATA_DIR, "tokens.json")
SNAPSHOTS_DIR = os.path.join(DATA_DIR, "snapshots")

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(SNAPSHOTS_DIR, exist_ok=True)

_LOCK = threading.Lock()


def _read_tokens() -> dict:
    if not os.path.exists(TOKENS_PATH):
        return {}
    try:
        with open(TOKENS_PATH) as f:
            return json.load(f)
    except Exception:
        return {}


def _write_tokens(tokens: dict) -> None:
    tmp = TOKENS_PATH + ".tmp"
    with open(tmp, "w") as f:
        json.dump(tokens, f, indent=2)
    os.replace(tmp, TOKENS_PATH)


def list_accounts() -> list[dict]:
    """Return all connected accounts, redacted (no secret tokens)."""
    with _LOCK:
        tokens = _read_tokens()
    out = []
    for label, t in tokens.items():
        out.append({
            "label": label,
            "provider": t.get("provider", "tiktok"),
            "display_name": t.get("display_name"),
            "avatar_url": t.get("avatar_url"),
            "follower_count": t.get("follower_count"),
            "video_count": t.get("video_count"),
            "connected_at": t.get("connected_at"),
            "open_id": t.get("open_id"),
        })
    out.sort(key=lambda x: (x.get("provider", ""), x.get("label", "")))
    return out


def get_account(label: str) -> Optional[dict]:
    with _LOCK:
        return _read_tokens().get(label)


def save_account(label: str, data: dict) -> None:
    with _LOCK:
        tokens = _read_tokens()
        existing = tokens.get(label, {})
        existing.update(data)
        tokens[label] = existing
        _write_tokens(tokens)


def delete_account(label: str) -> bool:
    with _LOCK:
        tokens = _read_tokens()
        if label in tokens:
            del tokens[label]
            _write_tokens(tokens)
            return True
    return False


# ---- Snapshots ----

def save_snapshot(date_str: str, payload: dict) -> str:
    p = os.path.join(SNAPSHOTS_DIR, f"{date_str}.json")
    tmp = p + ".tmp"
    with open(tmp, "w") as f:
        json.dump(payload, f, indent=2)
    os.replace(tmp, p)
    return p


def list_snapshot_dates() -> list[str]:
    if not os.path.isdir(SNAPSHOTS_DIR):
        return []
    return sorted(
        f.replace(".json", "")
        for f in os.listdir(SNAPSHOTS_DIR) if f.endswith(".json")
    )


def load_snapshot(date_str: str) -> Optional[dict]:
    p = os.path.join(SNAPSHOTS_DIR, f"{date_str}.json")
    if not os.path.exists(p):
        return None
    try:
        with open(p) as f:
            return json.load(f)
    except Exception:
        return None


def load_latest_snapshot() -> tuple[Optional[str], Optional[dict]]:
    dates = list_snapshot_dates()
    if not dates:
        return None, None
    return dates[-1], load_snapshot(dates[-1])
