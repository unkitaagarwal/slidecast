"""Slidecast Studio — local web app.

Runs a FastAPI server that wraps both pipelines:
  - "single"      : single-recipe 10-slide carousel (pipeline/)
  - "compilation" : 5-recipe 12-slide carousel       (compilation_pipeline/)

Run it:
    pip install fastapi uvicorn --break-system-packages
    python3 webapp/server.py

Then open http://localhost:8765 in your browser.
"""
from __future__ import annotations

import asyncio
import json
import os
import random as _random
import sys
import threading
import time
import traceback
import uuid
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Optional
import io as _io
import mimetypes as _mimetypes
import shutil as _shutil
import subprocess as _subprocess
import tempfile as _tempfile
import urllib.error as _urlerr
import urllib.parse as _urlparse
import urllib.request as _urlreq
import zipfile as _zipfile

# ---------------------------------------------------------------------------
# Resolve repo paths
# ---------------------------------------------------------------------------

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
STATIC = os.path.join(HERE, "static")
SINGLE_OUT = os.path.join(ROOT, "output")
COMP_OUT = os.path.join(ROOT, "output_compilations")
# Additional bundled single-recipe samples — kept separate from `output/` so
# user-generated content and ship-with-the-repo demos can coexist. Read-only
# from the API's perspective.
SINGLE_SAMPLES = os.path.join(ROOT, "Single recipes")

# Asset-folder paths (checked after the above as additional sources)
ASSETS_SINGLE = os.path.join(ROOT, "assets", "Single", "Single recipes")
ASSETS_COMP   = os.path.join(ROOT, "assets", "Compilation", "output_compilations")

# Firebase Storage — images uploaded via upload_assets_to_firebase.py are
# served directly from the CDN instead of the local filesystem.
FIREBASE_STORAGE_BUCKET = "slidecast-75f5c.firebasestorage.app"
FIREBASE_STORAGE_BASE   = f"https://storage.googleapis.com/{FIREBASE_STORAGE_BUCKET}"

def _firebase_url(format_name: str, slug: str, filename: str) -> str:
    """Return a Firebase Storage public CDN URL for a carousel slide."""
    return f"{FIREBASE_STORAGE_BASE}/carousels/{format_name}/{slug}/slides/{filename}"

def _is_assets_source(base_dir: str) -> bool:
    """True when the base directory is one of the bundled assets folders
    whose images have been uploaded to Firebase Storage."""
    return base_dir in (ASSETS_SINGLE, ASSETS_COMP)

# How many items to surface per format in /api/library. The folders can grow
# to hundreds of items; the UI rails only need a handful.
LIBRARY_LIMIT_PER_FORMAT = 20


def _resolve_single_dir(slug: str) -> Optional[str]:
    """Find which directory holds this single-recipe slug. Real generations
    land in `output/`, bundled samples live in `Single recipes/` and
    `assets/Single/Single recipes/`. Prefer real content if both exist."""
    for base in (SINGLE_OUT, SINGLE_SAMPLES, ASSETS_SINGLE):
        p = os.path.join(base, slug)
        if os.path.isdir(p):
            return p
    return None


def _resolve_comp_dir(slug: str) -> Optional[str]:
    """Find which directory holds this compilation slug."""
    for base in (COMP_OUT, ASSETS_COMP):
        p = os.path.join(base, slug)
        if os.path.isdir(p):
            return p
    return None
BRANDING_PATH     = os.path.join(HERE, "branding.json")
POSTIZ_API        = "https://api.postiz.com/public/v1"
STITCH_OUTPUT_DIR = os.path.expanduser("~/Documents/stitched_profile_videos")
os.makedirs(STITCH_OUTPUT_DIR, exist_ok=True)

# Folder of royalty-free background tracks used for Instagram Reels.
# Lives at  <repo_root>/assets/insta_audio/  (one level above webapp/).
INSTA_AUDIO_DIR = os.path.join(HERE, "..", "assets", "insta_audio")


_DEFAULT_BRANDING = {
    "brand_name":      "Slidecast",
    "studio_name":     "Studio",
    "tagline_html":    "Ship <em>30 days</em> of content<br/>across <em>30 accounts</em><br/>in <em>30 seconds.</em>",
    "subtagline":      "The fastest way to turn a one-line brief into a finished carousel — then auto-publish it to every TikTok and Instagram account you own. Captions and hashtags included. Free to start.",
    "eyebrow":         "For creators running multiple accounts",
    "primary_color":   "#ff5c7a",
    "secondary_color": "#f4c47a",
    "tiktok_handle":   "@nutrilens.ai",
    "cta_phrase":      "Made with Slidecast — generate carousels & auto-post to all your accounts. Link in bio",
    "footer_meta":     "runs locally · uses your Gemini key from .env",
}


def _load_branding() -> dict:
    if os.path.exists(BRANDING_PATH):
        try:
            with open(BRANDING_PATH) as f:
                cfg = json.load(f)
            return {**_DEFAULT_BRANDING, **{k: v for k, v in cfg.items()
                                            if not k.startswith("_")}}
        except Exception as e:
            print(f"  WARNING: branding.json failed to parse: {e}")
    return _DEFAULT_BRANDING

# =============================================================================
# Postiz Bulk Scheduler — helpers (ported from postiz-scheduler.py)
# =============================================================================

def _parse_multipart(content_type: str, data: bytes) -> dict:
    """Minimal multipart/form-data parser — no external deps.
    Returns {field_name: [{"data": bytes, "filename": str|None}, ...]}."""
    boundary = None
    for seg in content_type.split(";"):
        seg = seg.strip()
        if seg.lower().startswith("boundary="):
            boundary = seg[9:].strip("\"'")
            break
    if not boundary:
        return {}
    delim  = ("--" + boundary).encode()
    result = {}
    for chunk in data.split(delim)[1:]:
        stripped = chunk.strip()
        if stripped in (b"--", b"") or stripped.startswith(b"--"):
            continue
        sep = b"\r\n\r\n" if b"\r\n\r\n" in chunk else b"\n\n"
        if sep not in chunk:
            continue
        raw_headers, body = chunk.split(sep, 1)
        if body.endswith(b"\r\n"):
            body = body[:-2]
        name = filename = None
        for line in raw_headers.split(b"\r\n"):
            line_s = line.decode("utf-8", errors="replace")
            if line_s.lower().startswith("content-disposition:"):
                for part in line_s.split(";"):
                    part = part.strip()
                    if part.startswith("name="):
                        name = part[5:].strip("\"'")
                    elif part.startswith("filename="):
                        filename = part[9:].strip("\"'")
        if name:
            result.setdefault(name, []).append({"data": body, "filename": filename})
    return result


def _probe_format_duration_sec(path: str):
    """Best-effort container duration from ffprobe (seconds)."""
    r = _subprocess.run(
        ["ffprobe", "-v", "quiet",
         "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", path],
        capture_output=True, text=True,
    )
    s = (r.stdout or "").strip()
    try:
        return float(s) if s else None
    except ValueError:
        return None


def _stitch_videos_ffmpeg(
    video1_path: str,
    video2_path: str,
    output_path: str,
    *,
    gap_seconds: float = 0,
    source_prefix_seconds=None,
) -> str:
    """Stitch [source (trimmed)] then [CTA]. Audio from source only.
    Auto-detects portrait vs landscape from the source stream."""
    out_w, out_h = 1080, 1920  # default portrait
    _dim = _subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=width,height", "-of", "csv=p=0", video1_path],
        capture_output=True, text=True,
    )
    try:
        _parts = _dim.stdout.strip().split(",")
        if int(_parts[0]) > int(_parts[1]):
            out_w, out_h = 1920, 1080
    except Exception:
        pass

    scale_pad = (
        f"scale={out_w}:{out_h}:force_original_aspect_ratio=decrease,"
        f"pad={out_w}:{out_h}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=30"
    )
    _pr = _subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "a",
         "-show_entries", "stream=codec_type", "-print_format", "json", video1_path],
        capture_output=True, text=True,
    )
    try:
        src_has_audio = bool(json.loads(_pr.stdout or "{}").get("streams"))
    except (json.JSONDecodeError, ValueError):
        src_has_audio = False

    src_sec   = float(source_prefix_seconds) if source_prefix_seconds and float(source_prefix_seconds) > 0 else None
    gap_sec   = float(gap_seconds) if gap_seconds and float(gap_seconds) > 0 else 0.0
    v1_dur    = _probe_format_duration_sec(video1_path) or 0.0
    v2_dur    = _probe_format_duration_sec(video2_path) or 0.0
    used_v1   = float(src_sec) if src_sec else v1_dur
    total_dur = used_v1 + gap_sec + v2_dur

    parts = []
    t = (f"{src_sec:.6f}".rstrip("0").rstrip(".") if src_sec
         else (f"{v1_dur:.3f}" if v1_dur > 0 else None))
    parts.append(
        (f"[0:v]trim=start=0:duration={t},setpts=PTS-STARTPTS,{scale_pad}[vA]" if t
         else f"[0:v]{scale_pad}[vA]")
    )
    parts.append(f"[1:v]{scale_pad}[vB]")
    if gap_sec > 0:
        parts.append(f"color=c=black:size={out_w}x{out_h}:rate=30:duration={gap_sec:.3f},format=yuv420p[gv]")
        parts.append("[vA][gv][vB]concat=n=3:v=1:a=0[outv]")
    else:
        parts.append("[vA][vB]concat=n=2:v=1:a=0[outv]")

    extra_flags = []
    if src_has_audio:
        if total_dur > 0:
            parts.append(
                f"[0:a]atrim=start=0:duration={total_dur:.3f},asetpts=PTS-STARTPTS,"
                f"aresample=44100,aformat=channel_layouts=stereo[outa]"
            )
        else:
            parts.append("[0:a]aresample=44100,aformat=channel_layouts=stereo[outa]")
            extra_flags = ["-shortest"]
    else:
        if total_dur > 0:
            parts.append(
                f"aevalsrc=0|0:sample_rate=44100:channel_layout=stereo:duration={total_dur:.3f}[outa]"
            )
        else:
            parts.append("aevalsrc=0|0:sample_rate=44100:channel_layout=stereo[outa]")
            extra_flags = ["-shortest"]

    result = _subprocess.run(
        ["ffmpeg", "-y",
         "-stream_loop", "-1", "-i", video1_path,
         "-i", video2_path,
         "-filter_complex", ";".join(parts),
         "-map", "[outv]", "-map", "[outa]",
         "-c:v", "libx264", "-preset", "fast", "-crf", "23",
         "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart",
         *extra_flags, output_path],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg stitch failed:\n{result.stderr[-800:]}")
    return output_path


_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".avif"}
_os_path_basename = os.path.basename
_AUDIO_EXTS = {".mp3", ".m4a", ".wav", ".aac", ".ogg"}


def _pick_random_insta_audio() -> str:
    """Return a random audio file path from INSTA_AUDIO_DIR, or '' if none found."""
    try:
        audio_dir = os.path.realpath(INSTA_AUDIO_DIR)
        if not os.path.isdir(audio_dir):
            return ""
        tracks = [
            os.path.join(audio_dir, f)
            for f in os.listdir(audio_dir)
            if os.path.splitext(f.lower())[1] in _AUDIO_EXTS
        ]
        return _random.choice(tracks) if tracks else ""
    except Exception:
        return ""


def _slideshow_to_video_ffmpeg(
    image_paths: list,
    output_path: str,
    *,
    seconds_per_slide: float = 3.0,
    audio_path: str = "",
) -> str:
    """Stitch a list of images into a portrait 1080×1920 MP4 with an audio track.

    Always embeds a stereo audio stream so Instagram does not auto-mute the Reel.
    If ``audio_path`` points to a valid audio file (mp3/m4a/wav/aac), that file
    is looped to fill the video duration and mixed in at full volume.
    Otherwise a silent 44100 Hz stereo track is generated via lavfi anullsrc.

    The resulting video is ready to upload as an Instagram Reel; Postiz's
    ``audio_name`` setting can additionally overlay an IG library track.
    """
    total_dur = len(image_paths) * seconds_per_slide

    concat_txt = output_path + ".concat.txt"
    with open(concat_txt, "w") as fh:
        for img in image_paths:
            fh.write(f"file '{img}'\nduration {seconds_per_slide:.3f}\n")
        # FFmpeg concat demuxer: repeat last file without duration to flush
        fh.write(f"file '{image_paths[-1]}'\n")

    use_music = audio_path and os.path.isfile(audio_path)

    try:
        if use_music:
            cmd = [
                "ffmpeg", "-y",
                "-f", "concat", "-safe", "0", "-i", concat_txt,   # input 0: video
                "-stream_loop", "-1", "-i", audio_path,            # input 1: music (looped)
                "-vf", (
                    "scale=1080:1920:force_original_aspect_ratio=decrease,"
                    "pad=1080:1920:(ow-iw)/2:(oh-ih)/2:color=black,"
                    "setsar=1,fps=30"
                ),
                "-map", "0:v", "-map", "1:a",
                "-c:v", "libx264", "-preset", "fast", "-crf", "22",
                "-c:a", "aac", "-b:a", "192k",
                "-pix_fmt", "yuv420p",
                "-t", str(total_dur),           # trim to exact slideshow length
                "-movflags", "+faststart",
                output_path,
            ]
        else:
            # Generate a silent stereo track so Instagram does not auto-mute the Reel
            cmd = [
                "ffmpeg", "-y",
                "-f", "concat", "-safe", "0", "-i", concat_txt,   # input 0: video
                "-f", "lavfi", "-i",                               # input 1: silence
                f"anullsrc=r=44100:cl=stereo:d={total_dur:.3f}",
                "-vf", (
                    "scale=1080:1920:force_original_aspect_ratio=decrease,"
                    "pad=1080:1920:(ow-iw)/2:(oh-ih)/2:color=black,"
                    "setsar=1,fps=30"
                ),
                "-map", "0:v", "-map", "1:a",
                "-c:v", "libx264", "-preset", "fast", "-crf", "22",
                "-c:a", "aac", "-b:a", "128k",
                "-pix_fmt", "yuv420p",
                "-shortest",
                "-movflags", "+faststart",
                output_path,
            ]

        result = _subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(
                f"FFmpeg slideshow-to-video failed:\n{result.stderr[-600:]}"
            )
        return output_path
    finally:
        if os.path.exists(concat_txt):
            os.unlink(concat_txt)


def _read_slideshow_dir(folder_path: str):
    """Return (slides_list, metadata_dict) for a single carousel folder."""
    metadata = {}
    try:
        json_files = sorted(f for f in os.listdir(folder_path) if f.lower().endswith(".json"))
        if json_files:
            with open(os.path.join(folder_path, json_files[0]), encoding="utf-8") as fh:
                metadata = json.load(fh)
    except Exception as ex:
        print(f"  [folder] JSON error in {folder_path}: {ex}")
    slides_dir = os.path.join(folder_path, "slides")
    if not os.path.isdir(slides_dir):
        return [], metadata
    images = sorted(
        f for f in os.listdir(slides_dir)
        if os.path.splitext(f.lower())[1] in _IMAGE_EXTS
    )
    return [
        {"name": fn, "path": os.path.join(slides_dir, fn),
         "size": os.path.getsize(os.path.join(slides_dir, fn))}
        for fn in images
    ], metadata


def _postiz_proxy_get(endpoint: str, auth: str) -> Response:
    """Proxy a GET request to the Postiz public API."""
    try:
        req = _urlreq.Request(
            f"{POSTIZ_API}{endpoint}",
            headers={"Authorization": auth, "Accept": "application/json"},
        )
        with _urlreq.urlopen(req, timeout=30) as r:
            body = r.read()
        return Response(content=body, media_type="application/json")
    except _urlerr.HTTPError as e:
        return Response(content=e.read(), status_code=e.code, media_type="application/json")
    except Exception as e:
        raise HTTPException(500, str(e))


def _postiz_proxy_post(endpoint: str, auth: str, body: bytes, content_type: str) -> Response:
    """Proxy a POST request to the Postiz public API with retry."""
    headers = {
        "Authorization": auth,
        "Content-Type":  content_type,
        "Accept":        "application/json",
    }
    last_exc = None
    for attempt in range(3):
        try:
            req = _urlreq.Request(f"{POSTIZ_API}{endpoint}", data=body,
                                  headers=headers, method="POST")
            with _urlreq.urlopen(req, timeout=120) as r:
                resp_body = r.read()
            return Response(content=resp_body, media_type="application/json")
        except _urlerr.HTTPError as e:
            return Response(content=e.read(), status_code=e.code, media_type="application/json")
        except Exception as exc:
            last_exc = exc
            if attempt < 2:
                print(f"  [postiz retry {attempt+1}] {exc}")
                time.sleep(2 ** attempt)
    raise HTTPException(500, str(last_exc))


# Make pipelines importable
sys.path.insert(0, os.path.join(ROOT, "pipeline"))
sys.path.insert(0, os.path.join(ROOT, "compilation_pipeline"))


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

# Lazy imports so the server starts even if a pipeline file has issues
def _import_single():
    import run as _single_run  # pipeline/run.py
    return _single_run

def _import_compilation():
    import run_compilation as _comp_run  # compilation_pipeline/run_compilation.py
    return _comp_run

def _import_caption():
    import postiz_publish as _comp_publish  # compilation_pipeline/postiz_publish.py
    return _comp_publish


# ---------------------------------------------------------------------------
# In-memory job tracker
# ---------------------------------------------------------------------------

class JobStore:
    def __init__(self):
        self._lock = threading.Lock()
        self._jobs: dict[str, dict] = {}

    def create(self, kind: str, payload: dict) -> str:
        job_id = str(uuid.uuid4())[:8]
        with self._lock:
            self._jobs[job_id] = {
                "id": job_id,
                "kind": kind,
                "payload": payload,
                "status": "pending",
                "message": "Queued",
                "result": None,
                "error": None,
                "created_at": time.time(),
                "updated_at": time.time(),
            }
        return job_id

    def update(self, job_id: str, **kw):
        with self._lock:
            j = self._jobs.get(job_id)
            if not j:
                return
            j.update(kw)
            j["updated_at"] = time.time()

    def get(self, job_id: str) -> Optional[dict]:
        with self._lock:
            return dict(self._jobs.get(job_id) or {})


JOBS = JobStore()
EXECUTOR = ThreadPoolExecutor(max_workers=2)


# ---------------------------------------------------------------------------
# Pipeline wrappers (run in worker threads)
# ---------------------------------------------------------------------------

def _run_single(job_id: str, brief: str, user_email: Optional[str] = None):
    try:
        JOBS.update(job_id, status="running", message="Generating recipe with Gemini…")
        single = _import_single()
        rdir   = single.run_one_recipe(brief)
        slug   = os.path.basename(rdir)
        slides = sorted(
            f for f in os.listdir(os.path.join(rdir, "slides"))
            if f.endswith(".png")
        )

        # Build caption while local spec JSON still exists
        caption = ""
        try:
            sys.path.insert(0, os.path.join(ROOT, "pipeline"))
            from postiz_publish import build_caption as _sc
            spec = json.load(open(os.path.join(rdir, f"{slug}.json")))
            caption = _sc(spec)
        except Exception as _e:
            print(f"  [caption] build failed: {_e}")

        # Upload to Firebase Storage + log to Firestore
        JOBS.update(job_id, message="Uploading slides to Firebase…")
        slide_urls = _upload_slides_and_log(
            slides_dir     = os.path.join(rdir, "slides"),
            format_name    = "single",
            slug           = slug,
            user_email     = user_email,
            theme          = brief,
            slide_filenames= slides,
            caption        = caption,
        )

        # Clean up local output dir — slides are in Firebase, no need to keep them on disk
        if slide_urls and rdir.startswith(SINGLE_OUT):
            try:
                _shutil.rmtree(rdir)
                print(f"  [cleanup] removed local dir {rdir}")
            except Exception as _ce:
                print(f"  [cleanup] could not remove {rdir}: {_ce}")

        JOBS.update(
            job_id,
            status="done",
            message=f"Done — {slug}",
            result={
                "format":     "single",
                "slug":       slug,
                "slides":     slides,
                "slide_urls": slide_urls,
            },
        )
    except Exception as e:
        traceback.print_exc()
        JOBS.update(job_id, status="failed",
                    message=f"Failed: {e}", error=str(e))


def _run_compilation(job_id: str, theme: str,
                     brand_card_path: Optional[str] = None,
                     brand_name: Optional[str] = None,
                     user_email: Optional[str] = None):
    try:
        JOBS.update(job_id, status="running",
                    message="Generating 5 recipes with Gemini…")
        comp = _import_compilation()
        cdir = comp.run_one_compilation(theme)
        slug = os.path.basename(cdir)
        slides = sorted(
            f for f in os.listdir(os.path.join(cdir, "slides"))
            if f.endswith(".png")
        )

        # Build caption while local spec JSON still exists
        caption = ""
        try:
            cap_mod = _import_caption()
            spec = json.load(open(os.path.join(cdir, f"{slug}.json")))
            spec.setdefault("slug", slug)
            caption = cap_mod.build_caption(spec)
        except Exception as _e:
            print(f"  [caption] build failed: {_e}")

        # Upload to Firebase Storage + log to Firestore
        JOBS.update(job_id, message="Uploading slides to Firebase…")
        slide_urls = _upload_slides_and_log(
            slides_dir     = os.path.join(cdir, "slides"),
            format_name    = "compilation",
            slug           = slug,
            user_email     = user_email,
            theme          = theme,
            slide_filenames= slides,
            caption        = caption,
        )

        # Clean up local output dir — slides are in Firebase, no need to keep them on disk
        if slide_urls and cdir.startswith(COMP_OUT):
            try:
                _shutil.rmtree(cdir)
                print(f"  [cleanup] removed local dir {cdir}")
            except Exception as _ce:
                print(f"  [cleanup] could not remove {cdir}: {_ce}")

        JOBS.update(
            job_id,
            status="done",
            message=f"Done — {slug}",
            result={
                "format":     "compilation",
                "slug":       slug,
                "slides":     slides,
                "slide_urls": slide_urls,
            },
        )
    except Exception as e:
        traceback.print_exc()
        JOBS.update(job_id, status="failed",
                    message=f"Failed: {e}", error=str(e))


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

app = FastAPI(title="Slidecast Studio")


class GenerateBody(BaseModel):
    format: str  # "single" or "compilation"
    input: str   # brief or theme
    user_email: Optional[str] = None  # signed-in user — used to log to Firestore
    # Optional brand override (paid users only — frontend gates this).
    # When present the compilation pipeline swaps in the user's brand
    # image and brand name on the final CTA slide. Free / anon users
    # leave this unset and see the default Slidecast CTA.
    brand: Optional[dict] = None  # { name, cta_text, image_data_url }


# Where uploaded brand-kit images are stashed (paid-user CTA overrides).
BRAND_KIT_DIR = os.path.join(HERE, "uploads", "brand_kit")
os.makedirs(BRAND_KIT_DIR, exist_ok=True)


def _save_brand_image_from_data_url(data_url: str, job_id: str) -> Optional[str]:
    """Decode a data:image/...;base64,XXX URL to a real file on disk.
    Returns the file path, or None if input is unusable."""
    if not data_url or not data_url.startswith("data:image/"):
        return None
    import base64
    header, _, b64 = data_url.partition(",")
    if not b64:
        return None
    ext = ".png"
    if "jpeg" in header or "jpg" in header:
        ext = ".jpg"
    elif "webp" in header:
        ext = ".webp"
    path = os.path.join(BRAND_KIT_DIR, f"{job_id}{ext}")
    try:
        with open(path, "wb") as f:
            f.write(base64.b64decode(b64))
        return path
    except Exception as e:
        print(f"[brand-kit] decode failed: {e}")
        return None


# ---------------------------------------------------------------------------
# Firebase Storage upload + Firestore generation log
# ---------------------------------------------------------------------------

FIREBASE_STORAGE_BUCKET = "slidecast-75f5c.firebasestorage.app"  # already defined above but used here too

def _firebase_admin_init():
    """Lazy-init firebase-admin SDK.

    Credential resolution order (first match wins):
      1. GOOGLE_APPLICATION_CREDENTIALS_JSON  — full service-account JSON as
         a string (best for Render: paste the JSON directly into an env var)
      2. GOOGLE_APPLICATION_CREDENTIALS       — path to a service-account JSON
         file (works locally or with Render Secret Files)
      3. Application Default Credentials      — fallback (GCP-managed envs)
    """
    try:
        import firebase_admin
        from firebase_admin import credentials as _creds
        if not firebase_admin._apps:
            cred_json_str = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS_JSON", "").strip()
            cred_path     = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "").strip()

            if cred_json_str:
                # Inline JSON — cleanest approach for Render env vars
                sa_info = json.loads(cred_json_str)
                cred = _creds.Certificate(sa_info)
                print("  [firebase-admin] init via GOOGLE_APPLICATION_CREDENTIALS_JSON")
            elif cred_path and os.path.exists(cred_path):
                cred = _creds.Certificate(cred_path)
                print(f"  [firebase-admin] init via credential file: {cred_path}")
            else:
                cred = _creds.ApplicationDefault()
                print("  [firebase-admin] init via ApplicationDefault credentials")

            firebase_admin.initialize_app(cred, {
                "storageBucket": FIREBASE_STORAGE_BUCKET,
            })
        return firebase_admin
    except Exception as e:
        print(f"  [firebase-admin] init failed: {e}")
        return None


def _upload_slides_and_log(
    slides_dir: str,
    format_name: str,   # "compilation" | "single"
    slug: str,
    user_email: Optional[str],
    theme: str,
    slide_filenames: list,
    caption: str = "",
) -> list:
    """Upload all slide PNGs from slides_dir to Firebase Storage and write a
    generation record to Firestore under users/{email}/generations/{slug}.

    Also saves caption.txt to Firebase Storage so api_preview can retrieve it
    after the local directory has been cleaned up.

    Returns list of public CDN URLs for the uploaded slides.
    """
    try:
        fa = _firebase_admin_init()
        if fa is None:
            print("  [upload] firebase-admin unavailable — skipping upload")
            return []

        from firebase_admin import storage as _fa_storage, firestore as _fa_fs

        bucket = _fa_storage.bucket()
        slide_urls = []

        for fname in slide_filenames:
            local_path   = os.path.join(slides_dir, fname)
            storage_path = f"carousels/{format_name}/{slug}/slides/{fname}"
            blob = bucket.blob(storage_path)
            blob.upload_from_filename(local_path, content_type="image/png")
            blob.make_public()
            slide_urls.append(blob.public_url)
            print(f"  [upload] ↑ {fname}")

        # Save caption.txt to Firebase Storage so preview works after local cleanup
        if caption:
            cap_blob = bucket.blob(f"carousels/{format_name}/{slug}/caption.txt")
            cap_blob.upload_from_string(caption, content_type="text/plain; charset=utf-8")
            cap_blob.make_public()
            print(f"  [upload] ↑ caption.txt")

        # Write generation record to Firestore
        if user_email and slide_urls:
            db = _fa_fs.client()
            gen_ref = (
                db.collection("users")
                  .document(user_email)
                  .collection("generations")
                  .document(slug)
            )
            gen_ref.set({
                "slug":        slug,
                "format":      format_name,
                "theme":       theme,
                "slide_urls":  slide_urls,
                "slide_count": len(slide_urls),
                "caption":     caption,
                "created_at":  _fa_fs.SERVER_TIMESTAMP,
            })
            print(f"  [firestore] logged generation {slug} → users/{user_email}/generations/{slug}")

        return slide_urls

    except Exception as e:
        # Never crash the pipeline — upload is best-effort
        print(f"  [upload] ERROR: {e}")
        traceback.print_exc()
        return []


@app.post("/api/generate")
def api_generate(body: GenerateBody):
    if body.format not in ("single", "compilation"):
        raise HTTPException(400, "format must be 'single' or 'compilation'")
    text = (body.input or "").strip()
    if not text:
        raise HTTPException(400, "input is required")

    job_id = JOBS.create(body.format, {"input": text})

    # Extract optional brand override (paid users send this; free/anon don't)
    brand_card_path = None
    brand_name = None
    if body.brand:
        brand_name = (body.brand.get("name") or "").strip() or None
        data_url = body.brand.get("image_data_url")
        if data_url:
            brand_card_path = _save_brand_image_from_data_url(data_url, job_id)

    user_email = (body.user_email or "").strip() or None

    if body.format == "single":
        EXECUTOR.submit(_run_single, job_id, text, user_email)
    else:
        EXECUTOR.submit(_run_compilation, job_id, text,
                        brand_card_path, brand_name, user_email)
    return {"job_id": job_id}


@app.get("/api/jobs/{job_id}")
def api_job(job_id: str):
    j = JOBS.get(job_id)
    if not j:
        raise HTTPException(404, "job not found")
    # Strip internal fields
    return {
        "id": j["id"],
        "kind": j["kind"],
        "status": j["status"],
        "message": j["message"],
        "result": j["result"],
        "error": j["error"],
    }


@app.get("/api/branding")
def api_branding():
    """Brand-config endpoint. Frontend reads this on load to populate the
    studio name, tagline, colors etc. Edit webapp/branding.json and reload
    to rebrand without touching code."""
    return _load_branding()


def _firebase_list_slugs(format_name: str) -> list:
    """Query Firebase Storage REST API to list all carousel slugs for a format.
    Returns list of slug strings. No auth needed — bucket is public read."""
    try:
        prefix   = _urlparse.quote(f"carousels/{format_name}/", safe="")
        url      = (f"https://firebasestorage.googleapis.com/v0/b/{FIREBASE_STORAGE_BUCKET}"
                    f"/o?prefix={prefix}&delimiter=%2F")
        req      = _urlreq.Request(url, headers={"Accept": "application/json"})
        with _urlreq.urlopen(req, timeout=8) as r:
            data     = json.loads(r.read().decode())
        prefixes = data.get("prefixes", [])
        # Each prefix looks like "carousels/single/slug/" — extract the slug part
        slugs = []
        for p in prefixes:
            parts = p.rstrip("/").split("/")
            if len(parts) >= 3:
                slugs.append(parts[2])
        return slugs
    except Exception as e:
        print(f"[library] Firebase list error ({format_name}): {e}")
        return []


def _firebase_list_slides(format_name: str, slug: str) -> list:
    """List all slide filenames for a given carousel slug in Firebase Storage."""
    try:
        prefix = _urlparse.quote(f"carousels/{format_name}/{slug}/slides/", safe="")
        url    = (f"https://firebasestorage.googleapis.com/v0/b/{FIREBASE_STORAGE_BUCKET}"
                  f"/o?prefix={prefix}")
        req    = _urlreq.Request(url, headers={"Accept": "application/json"})
        with _urlreq.urlopen(req, timeout=8) as r:
            data   = json.loads(r.read().decode())
        items  = data.get("items", [])
        # Extract just the filename from the full storage path
        fnames = sorted(
            item["name"].split("/")[-1]
            for item in items
            if item["name"].endswith(".png")
        )
        return fnames
    except Exception as e:
        print(f"[library] Firebase slides error ({format_name}/{slug}): {e}")
        return []


def _slug_to_title(slug: str) -> str:
    """Convert a slug like 'thai_tiktok_feast' to 'Thai Tiktok Feast'."""
    return slug.replace("_", " ").title()


@app.get("/api/library")
def api_library(format: Optional[str] = None):
    """List all generated carousels — local first, then Firebase Storage."""
    def _scan_local(base_dir: str, fmt: str):
        out = []
        if not os.path.isdir(base_dir):
            return out
        for d in os.listdir(base_dir):
            if d.startswith(".") or d.startswith("_"):
                continue
            p = os.path.join(base_dir, d)
            if not os.path.isdir(p):
                continue
            jpath     = os.path.join(p, f"{d}.json")
            slides_dir = os.path.join(p, "slides")
            if not os.path.exists(jpath) or not os.path.isdir(slides_dir):
                continue
            slides = sorted(f for f in os.listdir(slides_dir) if f.endswith(".png"))
            if not slides:
                continue
            try:
                spec = json.load(open(jpath))
            except Exception:
                continue
            out.append({
                "format":     fmt,
                "slug":       d,
                "title":      spec.get("title") or spec.get("hook_caption") or _slug_to_title(d),
                "subtitle":   (spec.get("short_pitch") or
                               ", ".join(r.get("title","") for r in spec.get("recipes",[]))[:140]),
                "slide_count": len(slides),
                "thumbnail":  f"/images/{fmt}/{d}/{slides[0]}",
                "modified_at": int(os.path.getmtime(slides_dir)),
            })
        return out

    def _scan_firebase(fmt: str, seen_slugs: set):
        """Pull carousel list straight from Firebase Storage."""
        out   = []
        slugs = _firebase_list_slugs(fmt)
        for slug in slugs:
            if slug in seen_slugs:
                continue
            slides = _firebase_list_slides(fmt, slug)
            if not slides:
                continue
            thumb = _firebase_url(fmt, slug, slides[0])
            out.append({
                "format":      fmt,
                "slug":        slug,
                "title":       _slug_to_title(slug),
                "subtitle":    "",
                "slide_count": len(slides),
                "thumbnail":   thumb,
                "slides_base": "firebase",
                "modified_at": 0,
            })
        return out

    items = []

    if format in (None, "single"):
        seen = set()
        merged = []
        for entry in (_scan_local(SINGLE_OUT, "single")
                      + _scan_local(SINGLE_SAMPLES, "single")):
            if entry["slug"] not in seen:
                seen.add(entry["slug"])
                merged.append(entry)
        # Fill remaining slots from Firebase Storage
        merged += _scan_firebase("single", seen)
        merged.sort(key=lambda x: x["modified_at"], reverse=True)
        items.extend(merged[:LIBRARY_LIMIT_PER_FORMAT])

    if format in (None, "compilation"):
        seen_c = set()
        comp   = []
        for entry in _scan_local(COMP_OUT, "compilation"):
            if entry["slug"] not in seen_c:
                seen_c.add(entry["slug"])
                comp.append(entry)
        comp += _scan_firebase("compilation", seen_c)
        comp.sort(key=lambda x: x["modified_at"], reverse=True)
        items.extend(comp[:LIBRARY_LIMIT_PER_FORMAT])

    return {"items": items}


@app.get("/api/debug-paths")
def api_debug_paths():
    """Quick diagnostic — check which asset folders exist and how many carousels they contain."""
    def count_slugs(path):
        if not os.path.isdir(path):
            return {"exists": False, "path": path}
        slugs = [d for d in os.listdir(path)
                 if os.path.isdir(os.path.join(path, d)) and not d.startswith(".")]
        return {"exists": True, "path": path, "count": len(slugs), "slugs": slugs}

    return {
        "SINGLE_OUT":     count_slugs(SINGLE_OUT),
        "SINGLE_SAMPLES": count_slugs(SINGLE_SAMPLES),
        "ASSETS_SINGLE":  count_slugs(ASSETS_SINGLE),
        "COMP_OUT":       count_slugs(COMP_OUT),
        "ASSETS_COMP":    count_slugs(ASSETS_COMP),
    }


@app.get("/api/preview/{format}/{slug}")
def api_preview(format: str, slug: str):
    """Return slides + computed caption for a saved carousel.
    Falls back to Firebase Storage when local files are absent."""
    if format not in ("single", "compilation"):
        raise HTTPException(400, "bad format")

    # ── 1. Try local filesystem ──────────────────────────────────────────────
    cdir = (_resolve_single_dir(slug) if format == "single"
            else _resolve_comp_dir(slug))

    if cdir and os.path.isdir(cdir):
        jpath = os.path.join(cdir, f"{slug}.json")
        if not os.path.exists(jpath):
            raise HTTPException(404, "spec not found")
        spec   = json.load(open(jpath))
        slides = sorted(f for f in os.listdir(os.path.join(cdir, "slides"))
                        if f.endswith(".png"))

        # Build caption
        if format == "compilation":
            try:
                cap = _import_caption()
                spec.setdefault("slug", slug)
                caption = cap.build_caption(spec)
            except Exception as e:
                caption = f"(caption error: {e})"
        else:
            try:
                sys.path.insert(0, os.path.join(ROOT, "pipeline"))
                from postiz_publish import build_caption as single_caption
                caption = single_caption(spec)
            except Exception as e:
                caption = f"(caption error: {e})"

        return {
            "format":   format,
            "slug":     slug,
            "title":    spec.get("title") or spec.get("hook_caption") or _slug_to_title(slug),
            "subtitle": spec.get("short_pitch") or spec.get("theme") or "",
            "slides": [
                (_firebase_url(format, slug, s)
                 if _is_assets_source(os.path.dirname(os.path.dirname(cdir)))
                 else f"/images/{format}/{slug}/{s}")
                for s in slides
            ],
            "caption": caption,
            "spec":    spec,
        }

    # ── 2. Fall back to Firebase Storage ────────────────────────────────────
    slides = _firebase_list_slides(format, slug)
    if not slides:
        raise HTTPException(404, "slug not found")

    slide_urls = [_firebase_url(format, slug, s) for s in slides]
    title      = _slug_to_title(slug)

    # Try to fetch the caption.txt saved alongside the slides during upload
    caption = ""
    caption_url = f"{FIREBASE_STORAGE_BASE}/carousels/{format}/{slug}/caption.txt"
    try:
        caption = _urlreq.urlopen(caption_url, timeout=5).read().decode("utf-8")
    except Exception:
        pass  # caption.txt not found — will use fallback below

    if not caption:
        caption = f"✨ {title}\n\n#food #recipe #foodie #carousel"

    return {
        "format":      format,
        "slug":        slug,
        "title":       title,
        "subtitle":    "",
        "slides":      slide_urls,
        "caption":     caption,
        "spec":        {"title": title, "slug": slug},
        "slides_base": "firebase",
    }


@app.get("/api/download-zip/{format}/{slug}")
def api_download_zip(format: str, slug: str):
    """Build and stream a ZIP containing all slide PNGs + caption.txt + metadata.json."""
    from fastapi.responses import StreamingResponse
    import io as _io_z

    if format not in ("single", "compilation"):
        raise HTTPException(400, "bad format")

    # ── Gather slides & spec ─────────────────────────────────────────────────
    cdir = (_resolve_single_dir(slug) if format == "single"
            else _resolve_comp_dir(slug))

    slides_data: list[tuple[str, bytes]] = []  # [(filename, bytes), ...]
    spec: dict = {}
    caption: str = ""

    if cdir and os.path.isdir(cdir):
        # Load spec JSON
        jpath = os.path.join(cdir, f"{slug}.json")
        if os.path.exists(jpath):
            with open(jpath) as f:
                spec = json.load(f)

        # Read slides from disk
        slides_dir = os.path.join(cdir, "slides")
        for fname in sorted(os.listdir(slides_dir)):
            if fname.endswith(".png"):
                with open(os.path.join(slides_dir, fname), "rb") as f:
                    slides_data.append((fname, f.read()))

        # Build caption
        try:
            if format == "compilation":
                cap = _import_caption()
                spec.setdefault("slug", slug)
                caption = cap.build_caption(spec)
            else:
                sys.path.insert(0, os.path.join(ROOT, "pipeline"))
                from postiz_publish import build_caption as _sc
                caption = _sc(spec)
        except Exception:
            caption = f"✨ {_slug_to_title(slug)}\n\n#food #recipe #foodie"

    else:
        # Fall back to Firebase Storage — download each slide via HTTP
        slide_names = _firebase_list_slides(format, slug)
        if not slide_names:
            raise HTTPException(404, "slug not found locally or in Firebase")
        for fname in slide_names:
            url = _firebase_url(format, slug, fname)
            try:
                data = _urlreq.urlopen(url, timeout=30).read()
                slides_data.append((fname, data))
            except Exception as e:
                print(f"  [zip] failed to fetch {fname}: {e}")
        spec    = {"title": _slug_to_title(slug), "slug": slug}
        caption = f"✨ {_slug_to_title(slug)}\n\n#food #recipe #foodie"

    if not slides_data:
        raise HTTPException(404, "no slides found to zip")

    # ── Build ZIP in memory ──────────────────────────────────────────────────
    buf = _io_z.BytesIO()
    folder = slug  # files go inside a folder named after the slug
    with _zipfile.ZipFile(buf, "w", _zipfile.ZIP_DEFLATED) as zf:
        # Slides — nested inside a slides/ subfolder
        for fname, data in slides_data:
            zf.writestr(f"{folder}/slides/{fname}", data)

        # Caption
        if caption:
            zf.writestr(f"{folder}/caption.txt", caption)

        # Metadata JSON (title, subtitle, hashtags, hook, CTA copy, caption)
        _CTA_CAPTION = (
            spec.get("cta_caption") or [
                "Here's the trick for saving recipes:",
                "Like > Share > RecipeVault.",
                "That's all it takes to keep the full recipe.",
            ]
        )
        meta = {
            "slug":        slug,
            "format":      format,
            "title":       spec.get("title") or spec.get("hook_caption") or _slug_to_title(slug),
            "subtitle":    spec.get("short_pitch") or spec.get("theme") or "",
            "hashtags":    spec.get("hashtags") or "",
            "cta_caption": _CTA_CAPTION,
            "caption":     caption,
        }
        zf.writestr(f"{folder}/metadata.json", json.dumps(meta, indent=2))

    buf.seek(0)

    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{slug}.zip"'},
    )


@app.get("/images/{format}/{slug}/{filename}")
def serve_image(format: str, slug: str, filename: str):
    if format not in ("single", "compilation"):
        raise HTTPException(400, "bad format")

    # Try local filesystem first (fast path for freshly generated carousels)
    if format == "single":
        base = _resolve_single_dir(slug)
    else:
        base = _resolve_comp_dir(slug)

    if base:
        path = os.path.join(base, "slides", filename)
        if os.path.isfile(path):
            return FileResponse(path, media_type="image/png")

    # Local file missing (ephemeral disk wiped on Render restart, or never
    # written here) — redirect to Firebase Storage CDN so the browser fetches
    # it directly without hitting this server again.
    from fastapi.responses import RedirectResponse
    return RedirectResponse(
        url=_firebase_url(format, slug, filename),
        status_code=302,
    )


# =============================================================
# Template engine — universal carousel templates
# =============================================================
TEMPLATES_OUTPUT = os.path.join(ROOT, "output_templates")
BRAND_UPLOADS = os.path.join(HERE, "uploads", "brand_logos")
os.makedirs(TEMPLATES_OUTPUT, exist_ok=True)
os.makedirs(BRAND_UPLOADS, exist_ok=True)

try:
    sys.path.insert(0, HERE)
    # Importable as `templates_engine` from webapp/templates_engine/
    from templates_engine import list_templates as _list_templates
    from templates_engine import get_template as _get_template
    from templates_engine import generator as _tpl_generator
    TEMPLATES_OK = True
except Exception as e:
    import traceback as _tb
    _tb.print_exc()
    print(f"  templates_engine disabled: {e}")
    TEMPLATES_OK = False


@app.get("/api/templates")
def api_templates():
    if not TEMPLATES_OK:
        raise HTTPException(503, "templates engine disabled")
    out = []
    for t in _list_templates():
        out.append({
            "id": t.id,
            "name": t.name,
            "description": t.description,
            "slide_count_default": t.slide_count_default,
            "slide_count_min": t.slide_count_min,
            "slide_count_max": t.slide_count_max,
            "schema_fields": t.schema_fields,
        })
    return {"templates": out}


from fastapi import UploadFile, File, Form


@app.post("/api/brand/logo")
async def api_brand_logo(file: UploadFile = File(...)):
    """Save a brand logo upload. Returns a relative path we can pass back in
    the brand payload."""
    if not TEMPLATES_OK:
        raise HTTPException(503, "templates engine disabled")
    safe_name = (file.filename or "logo.png").replace("/", "_").replace("\\", "_")
    name = f"{int(time.time())}_{safe_name}"
    dest = os.path.join(BRAND_UPLOADS, name)
    content = await file.read()
    with open(dest, "wb") as f:
        f.write(content)
    return {
        "logo_path": dest,
        "logo_url": f"/uploads/brand_logos/{name}",
    }


@app.get("/uploads/brand_logos/{filename}")
def serve_brand_logo(filename: str):
    p = os.path.join(BRAND_UPLOADS, filename)
    if not os.path.isfile(p):
        raise HTTPException(404, "not found")
    return FileResponse(p)


class TemplateBatchBody(BaseModel):
    template_id: str
    inputs: dict
    brand: dict
    count: int = 1
    item_count: int = 5
    batch_label: str = ""


@app.post("/api/templates/generate")
def api_template_generate(body: TemplateBatchBody):
    if not TEMPLATES_OK:
        raise HTTPException(503, "templates engine disabled")
    if not _get_template(body.template_id):
        raise HTTPException(400, f"unknown template_id: {body.template_id}")
    body.count = max(1, min(20, int(body.count)))
    body.item_count = max(1, min(20, int(body.item_count)))

    job_id = JOBS.create("template_batch", body.dict())

    def _run():
        try:
            JOBS.update(job_id, status="running",
                        message=f"Generating {body.count} carousel(s)…")
            meta = _tpl_generator.generate_batch(
                template_id=body.template_id,
                inputs=body.inputs,
                brand=body.brand,
                count=body.count,
                item_count=body.item_count,
                batch_label=body.batch_label,
            )
            JOBS.update(job_id, status="done",
                        message=f"Generated {len(meta['results'])} carousel(s)",
                        result=meta)
        except Exception as e:
            traceback.print_exc()
            JOBS.update(job_id, status="failed",
                        message=f"Failed: {e}", error=str(e))

    EXECUTOR.submit(_run)
    return {"job_id": job_id}


@app.get("/api/templates/batches")
def api_template_batches():
    if not TEMPLATES_OK:
        raise HTTPException(503, "templates engine disabled")
    items = []
    if os.path.isdir(TEMPLATES_OUTPUT):
        for d in sorted(os.listdir(TEMPLATES_OUTPUT), reverse=True):
            meta_p = os.path.join(TEMPLATES_OUTPUT, d, "batch.json")
            if not os.path.exists(meta_p):
                continue
            try:
                with open(meta_p) as f:
                    meta = json.load(f)
            except Exception:
                continue
            # Find a thumbnail (first generated slide)
            thumb = None
            for r in meta.get("results", []):
                rd = r.get("dir")
                if rd and os.path.isdir(os.path.join(rd, "slides")):
                    sl = sorted(os.listdir(os.path.join(rd, "slides")))
                    if sl:
                        thumb = f"/output_templates/{os.path.basename(rd)}/slides/{sl[0]}"
                        # Note: above relative path assumes batch_dir == rd's parent
                        rel = os.path.relpath(os.path.join(rd, "slides", sl[0]),
                                              TEMPLATES_OUTPUT).replace(os.sep, "/")
                        thumb = f"/output_templates/{rel}"
                        break
            items.append({
                "batch_id": meta.get("batch_id"),
                "template_id": meta.get("template_id"),
                "count": meta.get("count"),
                "item_count": meta.get("item_count"),
                "created_at": meta.get("created_at"),
                "results_count": len([r for r in meta.get("results", [])
                                      if "error" not in r]),
                "label": meta.get("inputs", {}).get("topic")
                         or meta.get("inputs", {}).get("app_name")
                         or meta.get("batch_id"),
                "thumbnail": thumb,
            })
    return {"batches": items}


@app.get("/api/templates/batch/{batch_id}")
def api_template_batch(batch_id: str):
    if not TEMPLATES_OK:
        raise HTTPException(503, "templates engine disabled")
    meta_p = os.path.join(TEMPLATES_OUTPUT, batch_id, "batch.json")
    if not os.path.exists(meta_p):
        raise HTTPException(404, "not found")
    with open(meta_p) as f:
        meta = json.load(f)
    # Attach slide URLs for each carousel
    carousels = []
    for r in meta.get("results", []):
        if "error" in r:
            carousels.append(r); continue
        rd = r.get("dir")
        if not rd or not os.path.isdir(os.path.join(rd, "slides")):
            carousels.append(r); continue
        rel = os.path.relpath(rd, TEMPLATES_OUTPUT).replace(os.sep, "/")
        slides_files = sorted(os.listdir(os.path.join(rd, "slides")))
        carousels.append({
            **r,
            "slug": os.path.basename(rd),
            "slides": [f"/output_templates/{rel}/slides/{s}" for s in slides_files],
        })
    meta["carousels"] = carousels
    return meta


@app.get("/output_templates/{batch}/{carousel}/{kind}/{filename}")
def serve_template_image(batch: str, carousel: str, kind: str, filename: str):
    if kind not in ("slides", "raw"):
        raise HTTPException(400, "bad path")
    p = os.path.join(TEMPLATES_OUTPUT, batch, carousel, kind, filename)
    if not os.path.isfile(p):
        raise HTTPException(404, "not found")
    return FileResponse(p, media_type="image/png")


@app.get("/api/templates/batch/{batch_id}/download")
def api_template_download(batch_id: str):
    """Zip up the entire batch and stream it back."""
    if not TEMPLATES_OK:
        raise HTTPException(503, "templates engine disabled")
    bdir = os.path.join(TEMPLATES_OUTPUT, batch_id)
    if not os.path.isdir(bdir):
        raise HTTPException(404, "batch not found")
    import io, zipfile
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(bdir):
            # skip raw images to keep ZIP slim — only ship rendered slides + spec
            dirs[:] = [d for d in dirs if d != "raw"]
            for fn in files:
                p = os.path.join(root, fn)
                arc = os.path.relpath(p, bdir)
                zf.write(p, arc)
    buf.seek(0)
    from fastapi.responses import StreamingResponse
    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{batch_id}.zip"'},
    )


# =============================================================
# Tracking — TikTok analytics for owned accounts
# =============================================================
import secrets as _secrets

sys.path.insert(0, HERE)
try:
    from tracking import tiktok_api as tk
    from tracking import store as tk_store
    from tracking import fetch as tk_fetch
    TRACKING_OK = True
except Exception as e:
    print(f"  tracking module disabled: {e}")
    TRACKING_OK = False

# In-memory state map so we can verify the OAuth `state` round-trip.
# Keys are state strings, values are { label: str, created_at: float }.
_OAUTH_STATES: dict = {}


@app.get("/api/tracking/status")
def tracking_status():
    if not TRACKING_OK:
        return {"enabled": False, "reason": "tracking module not loaded"}
    return {
        "enabled": True,
        "credentials_configured": tk.creds_configured(),
        "connected_accounts": len(tk_store.list_accounts()),
    }


@app.get("/api/tracking/accounts")
def tracking_accounts():
    if not TRACKING_OK:
        raise HTTPException(503, "tracking disabled")
    return {"accounts": tk_store.list_accounts()}


@app.get("/api/tracking/summary")
def tracking_summary():
    """Aggregated dashboard payload — latest snapshot stats + leaderboards."""
    if not TRACKING_OK:
        raise HTTPException(503, "tracking disabled")
    date, snap = tk_store.load_latest_snapshot()
    accounts = tk_store.list_accounts()
    if not snap:
        return {
            "snapshot_date": None,
            "totals": {"plays": 0, "likes": 0, "comments": 0, "shares": 0,
                       "followers": sum((a.get("follower_count") or 0) for a in accounts)},
            "accounts": accounts,
            "top_posts": [],
        }
    totals = {"plays": 0, "likes": 0, "comments": 0, "shares": 0, "followers": 0}
    per_account = []
    top_posts = []
    for a in accounts:
        totals["followers"] += a.get("follower_count") or 0
    for label, data in snap.get("accounts", {}).items():
        vids = data.get("videos", []) or []
        a_plays = sum(int(v.get("view_count") or 0) for v in vids)
        a_likes = sum(int(v.get("like_count") or 0) for v in vids)
        a_comments = sum(int(v.get("comment_count") or 0) for v in vids)
        a_shares = sum(int(v.get("share_count") or 0) for v in vids)
        totals["plays"] += a_plays
        totals["likes"] += a_likes
        totals["comments"] += a_comments
        totals["shares"] += a_shares
        per_account.append({
            "label": label,
            "display_name": data.get("user", {}).get("display_name"),
            "follower_count": data.get("user", {}).get("follower_count"),
            "video_count": len(vids),
            "plays": a_plays, "likes": a_likes,
            "comments": a_comments, "shares": a_shares,
        })
        for v in vids:
            top_posts.append({
                "label": label,
                "title": (v.get("title") or v.get("video_description") or "")[:120],
                "view_count": int(v.get("view_count") or 0),
                "like_count": int(v.get("like_count") or 0),
                "share_url": v.get("share_url"),
                "cover_image_url": v.get("cover_image_url"),
                "create_time": v.get("create_time"),
            })
    per_account.sort(key=lambda x: x["plays"], reverse=True)
    top_posts.sort(key=lambda x: x["view_count"], reverse=True)
    return {
        "snapshot_date": date,
        "totals": totals,
        "per_account": per_account,
        "top_posts": top_posts[:20],
    }


@app.post("/api/tracking/refresh")
def tracking_refresh():
    """Trigger an immediate fetch for all connected accounts."""
    if not TRACKING_OK:
        raise HTTPException(503, "tracking disabled")

    def _run():
        try:
            tk_fetch.fetch_all()
        except Exception as e:
            traceback.print_exc()
            print(f"refresh failed: {e}")

    EXECUTOR.submit(_run)
    return {"started": True}


@app.delete("/api/tracking/accounts/{label}")
def tracking_delete(label: str):
    if not TRACKING_OK:
        raise HTTPException(503, "tracking disabled")
    ok = tk_store.delete_account(label)
    return {"deleted": ok}


# ---- TikTok OAuth flow ----

@app.get("/auth/tiktok/start")
def auth_tiktok_start(label: str = ""):
    """Generate authorize URL + PKCE pair, redirect the user to TikTok."""
    if not TRACKING_OK:
        raise HTTPException(503, "tracking disabled")
    if not tk.creds_configured():
        raise HTTPException(
            500,
            "TIKTOK_CLIENT_KEY/TIKTOK_CLIENT_SECRET not in .env",
        )
    state = _secrets.token_urlsafe(16)
    verifier = tk.generate_pkce_verifier()
    challenge = tk.pkce_challenge(verifier)
    _OAUTH_STATES[state] = {
        "label": label,
        "code_verifier": verifier,
        "created_at": time.time(),
    }
    # Prune old states
    cutoff = time.time() - 600
    for k in list(_OAUTH_STATES):
        if _OAUTH_STATES[k]["created_at"] < cutoff:
            del _OAUTH_STATES[k]
    url = tk.build_authorize_url(state, challenge, label=label)
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url, status_code=302)


@app.get("/auth/tiktok/callback")
def auth_tiktok_callback(code: str = "", state: str = "", error: str = "",
                         error_description: str = ""):
    """TikTok redirects here after the user authorizes (or denies)."""
    if not TRACKING_OK:
        raise HTTPException(503, "tracking disabled")
    if error:
        return HTMLResponse(
            f"<h2>TikTok auth error</h2><p>{error}: {error_description}</p>"
            f"<p><a href='/#tracking'>← back</a></p>",
            status_code=400,
        )
    if not code:
        raise HTTPException(400, "missing code")

    # Recover label + PKCE verifier from state (state was packed as "<state>|<label>")
    raw_state = state.split("|", 1)[0]
    label = state.split("|", 1)[1] if "|" in state else ""
    if raw_state not in _OAUTH_STATES:
        return HTMLResponse(
            "<h2>State mismatch</h2><p>Authorization expired or invalid. "
            "<a href='/#tracking'>Try again</a></p>",
            status_code=400,
        )
    saved = _OAUTH_STATES.pop(raw_state)
    code_verifier = saved.get("code_verifier", "")

    try:
        body = tk.exchange_code(code, code_verifier)
    except Exception as e:
        return HTMLResponse(
            f"<h2>Token exchange failed</h2><pre>{e}</pre>"
            f"<p><a href='/#tracking'>← back</a></p>",
            status_code=500,
        )

    open_id = body.get("open_id", "")
    final_label = (label or open_id or f"acct_{int(time.time())}").strip()
    now = int(time.time())
    tk_store.save_account(final_label, {
        "provider": "tiktok",
        "access_token": body.get("access_token"),
        "refresh_token": body.get("refresh_token"),
        "expires_at": now + int(body.get("expires_in", 3600)),
        "open_id": open_id,
        "scope": body.get("scope"),
        "connected_at": now,
    })

    # Immediately pull user info so the dashboard shows the display name + avatar
    try:
        user = tk.get_user_info(body["access_token"])
        tk_store.save_account(final_label, {
            "display_name": user.get("display_name"),
            "avatar_url": user.get("avatar_url"),
            "follower_count": user.get("follower_count"),
            "video_count": user.get("video_count"),
            "likes_count": user.get("likes_count"),
        })
    except Exception as e:
        print(f"  warning: user/info call failed: {e}")

    return HTMLResponse(f"""
      <!doctype html><html><head><meta charset='utf-8'>
      <title>Connected</title>
      <style>
        body{{font-family:-apple-system,system-ui,sans-serif;background:#0a0807;color:#fbf6ec;
              display:grid;place-items:center;min-height:100vh;margin:0;}}
        .card{{background:#14100e;border:1px solid rgba(255,247,232,0.12);padding:32px 40px;
               border-radius:14px;text-align:center;max-width:480px;}}
        h2{{margin:0 0 12px;color:#66c992;}}
        a{{color:#ff89a3;}}
      </style></head><body>
      <div class='card'>
        <h2>✓ Connected</h2>
        <p>TikTok account <strong>{final_label}</strong> is now tracked.</p>
        <p><a href='/#tracking'>← back to dashboard</a></p>
        <script>setTimeout(()=>location.href='/#tracking',1500);</script>
      </div></body></html>
    """)


# =============================================================

# =============================================================================
# Postiz Bulk Scheduler — routes
# =============================================================================

@app.get("/scheduler")
def scheduler_page():
    """Serve the Postiz Bulk Scheduler SPA."""
    p = os.path.join(STATIC, "scheduler.html")
    if not os.path.isfile(p):
        raise HTTPException(404, "scheduler.html not found")
    return FileResponse(p)


@app.get("/api/integrations")
def api_integrations(request: Request):
    """Proxy GET /integrations to the Postiz API."""
    return _postiz_proxy_get("/integrations", request.headers.get("Authorization", ""))


@app.get("/api/folder")
def api_folder(path: str = ""):
    """Scan a local folder and return slideshow metadata.
    Auto-detects single carousel vs parent folder with multiple sub-carousels."""
    folder_path = os.path.expanduser(path.strip())
    if not os.path.isdir(folder_path):
        raise HTTPException(400, f"Not a directory: {folder_path}")

    if os.path.isdir(os.path.join(folder_path, "slides")):
        slides, metadata = _read_slideshow_dir(folder_path)
        return {"mode": "single", "slides": slides, "metadata": metadata}

    try:
        entries = sorted(os.listdir(folder_path))
    except Exception as e:
        raise HTTPException(500, str(e))

    slideshows, skipped = [], []
    for entry in entries:
        sub = os.path.join(folder_path, entry)
        if not os.path.isdir(sub):
            continue
        slides, metadata = _read_slideshow_dir(sub)
        if len(slides) >= 2:
            slideshows.append({"folderName": entry, "slides": slides, "metadata": metadata})
            print(f"  [folder] ✓ {entry}: {len(slides)} slides")
        else:
            skipped.append({"folderName": entry, "slideCount": len(slides)})
            print(f"  [folder] ✗ {entry}: only {len(slides)} slide(s)")

    return {"mode": "multi", "slideshows": slideshows, "skipped": skipped}


@app.get("/api/file")
def api_file(path: str = ""):
    """Serve a local image file to the browser (for slide previews)."""
    file_path = os.path.expanduser(path.strip())
    if not os.path.isfile(file_path):
        raise HTTPException(404, "file not found")
    mime = _mimetypes.guess_type(file_path)[0] or "application/octet-stream"
    return FileResponse(file_path, media_type=mime)


_MAX_UPLOAD_BYTES = 120 * 1024 * 1024  # 120 MB hard cap

@app.post("/api/upload")
async def api_upload(request: Request):
    """Proxy multipart file upload to the Postiz API."""
    cl = int(request.headers.get("content-length", 0))
    if cl > _MAX_UPLOAD_BYTES:
        raise HTTPException(413, f"File too large (max {_MAX_UPLOAD_BYTES//1024//1024} MB)")
    auth = request.headers.get("Authorization", "")
    ct   = request.headers.get("Content-Type", "application/json")
    body = await request.body()
    result = _postiz_proxy_post("/upload", auth, body, ct)
    del body
    return result


@app.post("/api/posts")
async def api_posts(request: Request):
    """Proxy post-scheduling request to the Postiz API."""
    auth = request.headers.get("Authorization", "")
    ct   = request.headers.get("Content-Type", "application/json")
    body = await request.body()
    return _postiz_proxy_post("/posts", auth, body, ct)


@app.post("/api/upload-from-path")
async def api_upload_from_path(request: Request):
    """Read a file from a local disk path and proxy it to the Postiz upload endpoint."""
    auth = request.headers.get("Authorization", "")
    raw  = await request.body()
    req_data  = json.loads(raw)
    file_path = os.path.expanduser(req_data.get("path", "").strip())

    if not os.path.isfile(file_path):
        raise HTTPException(400, f"File not found: {file_path}")

    filename  = os.path.basename(file_path)
    mime_type = _mimetypes.guess_type(file_path)[0] or "application/octet-stream"
    file_size = os.path.getsize(file_path)
    print(f"  [upload-from-path] {filename} ({file_size//1024} KB)")
    boundary  = uuid.uuid4().hex
    part_head = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
        f"Content-Type: {mime_type}\r\n\r\n"
    ).encode()
    part_tail = f"\r\n--{boundary}--\r\n".encode()
    with open(file_path, "rb") as fh:
        file_data = fh.read()
    body = part_head + file_data + part_tail
    del file_data  # free before HTTP call
    result = _postiz_proxy_post(
        "/upload", auth, body,
        f"multipart/form-data; boundary={boundary}",
    )
    del body
    return result


@app.get("/api/stitch-download")
def api_stitch_download(path: str = ""):
    """Stream a stitched video back as a download.
    Only serves files inside STITCH_OUTPUT_DIR for safety."""
    real_path = os.path.realpath(os.path.expanduser(path.strip()))
    real_base = os.path.realpath(STITCH_OUTPUT_DIR)
    if not real_path.startswith(real_base):
        raise HTTPException(403, "forbidden")
    if not os.path.isfile(real_path):
        raise HTTPException(404, "not found")
    return FileResponse(
        real_path, media_type="video/mp4",
        headers={"Content-Disposition": f'attachment; filename="{os.path.basename(real_path)}"'},
    )


@app.get("/api/stitch-zip")
def api_stitch_zip(paths: str = "[]"):
    """Zip all stitched video paths and stream as download."""
    real_base = os.path.realpath(STITCH_OUTPUT_DIR)
    path_list = json.loads(paths)
    buf = _io.BytesIO()
    with _zipfile.ZipFile(buf, "w", _zipfile.ZIP_DEFLATED) as zf:
        for p in path_list:
            rp = os.path.realpath(p)
            if rp.startswith(real_base) and os.path.isfile(rp):
                zf.write(rp, os.path.basename(rp))
    buf.seek(0)
    from fastapi.responses import StreamingResponse as _SR
    return _SR(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": 'attachment; filename="stitched_videos.zip"'},
    )


@app.post("/api/stitch-videos")
async def api_stitch_videos(request: Request):
    """Batch-stitch source video(s) with a CTA clip using ffmpeg.

    Multipart mode (browser file picker):
        source   — video file(s), repeatable
        cta      — single CTA video file
        source_seconds — float, default 5

    JSON mode (disk paths):
        { folder_path|source_paths, cta_path|cta_url, source_seconds }
    """
    VIDEO_EXTS = {".mp4", ".mov", ".avi", ".mkv", ".webm", ".m4v"}
    os.makedirs(STITCH_OUTPUT_DIR, exist_ok=True)
    tmp_dir = _tempfile.mkdtemp(prefix="stitch_batch_")

    try:
        ct             = request.headers.get("Content-Type", "")
        source_paths   = []
        source_labels  = []
        cta_path       = None
        source_prefix_sec = 5.0

        if "multipart/form-data" in ct:
            raw  = await request.body()
            form = _parse_multipart(ct, raw)
            del raw  # release the raw buffer; bytes now live only inside `form`
            import gc as _gc; _gc.collect()

            src_entries = form.get("source", [])
            cta_entries = form.get("cta",    [])
            sec_entries = form.get("source_seconds", [])
            source_prefix_sec = float(
                (sec_entries[0]["data"].decode() if sec_entries else None) or "5"
            )
            if not src_entries:
                raise HTTPException(400, "No source video files received")
            if not cta_entries or not cta_entries[0].get("filename"):
                raise HTTPException(400, "multipart field 'cta' (file) is required")

            ext_c    = os.path.splitext(cta_entries[0]["filename"])[1] or ".mp4"
            cta_path = os.path.join(tmp_dir, f"cta{ext_c}")
            with open(cta_path, "wb") as fh:
                fh.write(cta_entries[0]["data"])
            cta_entries[0]["data"] = b""  # free after writing to disk

            for i, entry in enumerate(src_entries):
                if not entry.get("filename"):
                    continue
                base_name = os.path.basename(entry["filename"])
                ext_s = os.path.splitext(base_name)[1] or ".mp4"
                sp    = os.path.join(tmp_dir, f"src_{i}{ext_s}")
                with open(sp, "wb") as fh:
                    fh.write(entry["data"])
                entry["data"] = b""  # free after writing to disk
                source_paths.append(sp)
                source_labels.append(os.path.splitext(base_name)[0])
        else:
            raw  = await request.body()
            data = json.loads(raw)
            source_prefix_sec = float(data.get("source_seconds", 5))

            cta_url_raw  = (data.get("cta_url")  or "").strip()
            cta_path_raw = (data.get("cta_path") or "").strip()
            if cta_path_raw and os.path.isfile(cta_path_raw):
                cta_path = cta_path_raw
            elif cta_url_raw:
                cta_path = os.path.join(tmp_dir, "cta.mp4")
                req = _urlreq.Request(cta_url_raw, headers={"User-Agent": "Mozilla/5.0"})
                with _urlreq.urlopen(req, timeout=120) as r:
                    with open(cta_path, "wb") as fh:
                        fh.write(r.read())
            else:
                raise HTTPException(400, "Provide cta_path or cta_url")

            folder_path    = (data.get("folder_path") or "").strip()
            explicit_paths = data.get("source_paths") or []
            if folder_path:
                folder_path = os.path.expanduser(folder_path)
                if not os.path.isdir(folder_path):
                    raise HTTPException(400, f"folder_path not found: {folder_path}")
                for fname in sorted(os.listdir(folder_path)):
                    if os.path.splitext(fname.lower())[1] in VIDEO_EXTS:
                        source_paths.append(os.path.join(folder_path, fname))
                        source_labels.append(os.path.splitext(fname)[0])
            elif explicit_paths:
                for p in explicit_paths:
                    p = os.path.expanduser(p)
                    if os.path.isfile(p):
                        source_paths.append(p)
                        source_labels.append(os.path.splitext(os.path.basename(p))[0])
            else:
                raise HTTPException(400, "Provide folder_path or source_paths")

        if not source_paths:
            raise HTTPException(400, "No valid source video files found")
        if not cta_path or not os.path.exists(cta_path):
            raise HTTPException(400, "CTA video is missing or empty")

        source_prefix_sec = max(0.1, min(source_prefix_sec, 3600.0))

        results = []
        for i, src_path in enumerate(source_paths):
            label      = source_labels[i] if i < len(source_labels) else f"video_{i}"
            safe_label = os.path.basename(label)
            safe_label = "".join(c if c.isalnum() or c in "-_. #" else "_" for c in safe_label)
            safe_label = safe_label[:60] or f"video_{i}"
            out_name   = f"stitched_{safe_label}_{uuid.uuid4().hex[:8]}.mp4"
            out_path   = os.path.join(STITCH_OUTPUT_DIR, out_name)
            print(f"  [stitch {i+1}/{len(source_paths)}] {label} → {out_name}")
            try:
                _stitch_videos_ffmpeg(
                    src_path, cta_path, out_path,
                    gap_seconds=0,
                    source_prefix_seconds=source_prefix_sec,
                )
                results.append({
                    "label":             label,
                    "filename":          out_name,
                    "stitched_filepath": out_path,
                    "download_url":      f"/api/stitch-download?path={_urlparse.quote(out_path)}",
                    "ok":                True,
                })
                _vfy = _subprocess.run(
                    ["ffprobe", "-v", "error", "-select_streams", "v:0",
                     "-show_entries", "stream=width,height", "-of", "csv=p=0", out_path],
                    capture_output=True, text=True,
                )
                print(f"  [stitch] ✓ {out_name}  (dims: {_vfy.stdout.strip()})")
            except Exception as e:
                results.append({"label": label, "ok": False, "error": str(e)[:200]})
                print(f"  [stitch] ✗ {label}: {e}")

        ok_paths = [r["stitched_filepath"] for r in results if r.get("ok")]
        zip_url  = (
            f"/api/stitch-zip?paths={_urlparse.quote(json.dumps(ok_paths))}"
            if len(ok_paths) > 1 else ""
        )
        return {
            "total":          len(results),
            "succeeded":      sum(1 for r in results if r.get("ok")),
            "source_seconds": source_prefix_sec,
            "results":        results,
            "zip_url":        zip_url,
        }

    except HTTPException:
        raise
    except RuntimeError as e:
        raise HTTPException(500, f"FFmpeg stitching failed: {e}")
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(500, str(e))
    finally:
        _shutil.rmtree(tmp_dir, ignore_errors=True)


@app.post("/api/slideshow-to-video")
async def api_slideshow_to_video(request: Request):
    """Convert a list of image paths (disk) into a portrait MP4 Reel.

    JSON body:
        { "paths": ["/abs/path/img1.jpg", ...], "seconds_per_slide": 3.0 }

    Returns:
        { "url": "/api/stitch-download?path=...", "path": "..." }
    """
    body = await request.json()
    image_paths = body.get("paths", [])
    seconds_per_slide = float(body.get("seconds_per_slide", 3.0))
    audio_path = body.get("audio_path", "")  # optional local music file

    if not image_paths:
        raise HTTPException(400, "No image paths provided")

    for p in image_paths:
        if not os.path.isfile(p):
            raise HTTPException(400, f"File not found: {p}")

    # Auto-pick a random track if the caller didn't specify one
    if not audio_path:
        audio_path = _pick_random_insta_audio()

    tmp_dir = _tempfile.mkdtemp(prefix="slideshow_reel_")
    try:
        safe_name = "reel_" + _os_path_basename(image_paths[0]).rsplit(".", 1)[0] + ".mp4"
        out_path = os.path.join(STITCH_OUTPUT_DIR, safe_name)
        os.makedirs(STITCH_OUTPUT_DIR, exist_ok=True)
        _slideshow_to_video_ffmpeg(
            image_paths, out_path,
            seconds_per_slide=seconds_per_slide,
            audio_path=audio_path,
        )
        print(f"[insta-reel] audio={os.path.basename(audio_path) if audio_path else 'silent'} → {os.path.basename(out_path)}")
        dl_url = f"/api/stitch-download?path={_urlparse.quote(out_path, safe='')}"
        return {"url": dl_url, "path": out_path}
    except RuntimeError as e:
        raise HTTPException(500, f"FFmpeg slideshow-to-video failed: {e}")
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(500, str(e))
    finally:
        _shutil.rmtree(tmp_dir, ignore_errors=True)


@app.post("/api/slideshow-to-video-upload")
async def api_slideshow_to_video_upload(request: Request):
    """Accept image file uploads via multipart and stitch into a portrait MP4.

    Multipart fields:
        file   — image file, repeatable (one per slide, in order)
        seconds_per_slide — float, default 3.0

    Returns:
        { "url": "/api/stitch-download?path=...", "path": "..." }

    Used when slides were added via the file-picker (not Load from Folder),
    so the server does not have disk paths to work with.
    """
    ct = request.headers.get("Content-Type", "")
    if "multipart/form-data" not in ct:
        raise HTTPException(400, "Expected multipart/form-data")

    raw  = await request.body()
    form = _parse_multipart(ct, raw)
    del raw  # release buffer; bytes are inside `form` now
    import gc as _gc; _gc.collect()

    file_entries      = form.get("file", [])
    sec_entries       = form.get("seconds_per_slide", [])
    audio_entries     = form.get("audio_path", [])
    seconds_per_slide = 3.0
    if sec_entries:
        try:
            seconds_per_slide = float(sec_entries[0] if isinstance(sec_entries[0], (str, int, float)) else sec_entries[0].get("data", b"3").decode())
        except Exception:
            pass
    audio_path = ""
    if audio_entries:
        try:
            audio_path = (audio_entries[0] if isinstance(audio_entries[0], str) else audio_entries[0].get("data", b"").decode()).strip()
        except Exception:
            pass

    if not file_entries:
        raise HTTPException(400, "No image files provided")

    # Auto-pick a random track if the caller didn't specify one
    if not audio_path:
        audio_path = _pick_random_insta_audio()

    tmp_dir = _tempfile.mkdtemp(prefix="slideshow_upload_")
    try:
        image_paths = []
        for idx, entry in enumerate(file_entries):
            img_data = entry if isinstance(entry, bytes) else entry.get("data", b"")
            fname    = f"slide_{idx:04d}.jpg"
            fpath    = os.path.join(tmp_dir, fname)
            with open(fpath, "wb") as fh:
                fh.write(img_data)
            # Free slide bytes from memory immediately after writing to disk
            if isinstance(entry, dict):
                entry["data"] = b""
            image_paths.append(fpath)

        if not image_paths:
            raise HTTPException(400, "No valid image data received")

        safe_name = f"reel_upload_{len(image_paths)}slides.mp4"
        out_path  = os.path.join(STITCH_OUTPUT_DIR, safe_name)
        os.makedirs(STITCH_OUTPUT_DIR, exist_ok=True)
        _slideshow_to_video_ffmpeg(
            image_paths, out_path,
            seconds_per_slide=seconds_per_slide,
            audio_path=audio_path,
        )
        dl_url = f"/api/stitch-download?path={_urlparse.quote(out_path, safe='')}"
        return {"url": dl_url, "path": out_path}
    except RuntimeError as e:
        raise HTTPException(500, f"FFmpeg slideshow-to-video failed: {e}")
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(500, str(e))
    finally:
        _shutil.rmtree(tmp_dir, ignore_errors=True)


# =============================================================================


@app.post("/api/add-audio-to-video")
async def api_add_audio_to_video(request: Request):
    """Embed a random background track into a video that has no audio.

    Accepts either:
      • multipart/form-data  — field "file" = video bytes
      • application/json     — { "path": "/abs/path/to/video.mp4" }

    In both cases the server checks for an existing audio stream via ffprobe.
    If the video already has audio it is returned as-is (no re-encode).
    If not, a random track from assets/insta_audio/ is looped and mixed in.

    Returns: { "path": "/abs/path/to/processed.mp4" }
    The caller should then POST that path to /api/upload-from-path.
    """
    ct = request.headers.get("Content-Type", "")
    tmp_dir = _tempfile.mkdtemp(prefix="tiktok_audio_")
    try:
        # ── resolve input video to a local file path ──────────────────
        if "multipart/form-data" in ct:
            # Use FastAPI's native form parser (python-multipart) — handles
            # large video files correctly without loading into RAM all at once.
            form     = await request.form()
            upload   = form.get("file")
            if upload is None:
                raise HTTPException(400, "No file field in multipart")
            # Preserve original extension so ffprobe/ffmpeg detect format
            orig_name = getattr(upload, "filename", None) or "input.mp4"
            vid_path  = os.path.join(tmp_dir, orig_name)
            with open(vid_path, "wb") as fh:
                fh.write(await upload.read())
        else:
            body     = await request.json()
            vid_path = body.get("path", "").strip()
            if not vid_path or not os.path.isfile(vid_path):
                raise HTTPException(400, f"Video file not found: {vid_path}")

        # ── check if video already has an audio stream via ffprobe ──────
        probe = _subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "a:0",
             "-show_entries", "stream=codec_name",
             "-of", "default=noprint_wrappers=1:nokey=1", vid_path],
            capture_output=True, text=True,
        )
        had_audio = bool(probe.stdout.strip())
        print(f"[audio] {os.path.basename(vid_path)}: had_audio={had_audio}")
        if had_audio:
            # Video already has audio — return as-is, no processing needed
            return {"path": vid_path, "had_audio": True, "track": None}

        # ── pick a random background track ────────────────────────────
        audio_path = _pick_random_insta_audio()
        if not audio_path:
            raise HTTPException(500, "No audio tracks found in assets/insta_audio/")

        # ── get video duration so audio is trimmed exactly ────────────
        dur_probe = _subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", vid_path],
            capture_output=True, text=True,
        )
        try:
            duration = float(dur_probe.stdout.strip())
        except (ValueError, AttributeError):
            duration = 0

        out_name = "tiktok_audio_" + os.path.basename(vid_path)
        out_path = os.path.join(STITCH_OUTPUT_DIR, out_name)
        os.makedirs(STITCH_OUTPUT_DIR, exist_ok=True)

        # ── mix audio into video (-c:v copy = no video re-encode) ─────
        cmd = [
            "ffmpeg", "-y",
            "-i", vid_path,
            "-stream_loop", "-1", "-i", audio_path,
            "-map", "0:v:0", "-map", "1:a:0",
            "-c:v", "copy",
            "-c:a", "aac", "-b:a", "192k",
            *([ "-t", str(duration)] if duration > 0 else ["-shortest"]),
            "-movflags", "+faststart",
            out_path,
        ]
        result = _subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"ffmpeg audio-mix failed:\n{result.stderr[-600:]}")

        print(f"[audio] ✓ embedded {os.path.basename(audio_path)} → {os.path.basename(out_path)}")
        return {"path": out_path, "had_audio": had_audio, "track": os.path.basename(audio_path)}

    except HTTPException:
        raise
    except RuntimeError as e:
        raise HTTPException(500, str(e))
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(500, str(e))
    finally:
        _shutil.rmtree(tmp_dir, ignore_errors=True)


@app.post("/api/upload-tiktok-video")
async def api_upload_tiktok_video(request: Request):
    """Receive a video file, embed audio if missing, upload to Postiz in one step.

    Accepts multipart/form-data:
        file  — video file (mp4/mov etc.)

    Returns the Postiz upload response: { "id": "...", "path": "..." }
    """
    cl = int(request.headers.get("content-length", 0))
    if cl > _MAX_UPLOAD_BYTES:
        raise HTTPException(413, f"File too large (max {_MAX_UPLOAD_BYTES//1024//1024} MB)")
    auth = request.headers.get("Authorization", "")
    ct   = request.headers.get("Content-Type", "")

    if "multipart/form-data" not in ct:
        raise HTTPException(400, "Expected multipart/form-data")

    form   = await request.form()
    upload = form.get("file")
    if upload is None:
        raise HTTPException(400, "No file field")

    orig_name = getattr(upload, "filename", None) or "video.mp4"
    video_bytes = await upload.read()
    print(f"[tiktok-upload] received {orig_name} ({len(video_bytes)//1024} KB)")

    tmp_dir = _tempfile.mkdtemp(prefix="tiktok_upload_")
    try:
        vid_path = os.path.join(tmp_dir, orig_name)
        with open(vid_path, "wb") as fh:
            fh.write(video_bytes)
        del video_bytes  # free RAM — file is now on disk
        import gc as _gc; _gc.collect()

        # ── Step 1: does the video have an audio stream at all? ──────
        probe = _subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "a:0",
             "-show_entries", "stream=codec_name",
             "-of", "default=noprint_wrappers=1:nokey=1", vid_path],
            capture_output=True, text=True, timeout=30,
        )
        has_audio_stream = bool(probe.stdout.strip())
        print(f"[tiktok-upload] {orig_name}: has_audio_stream={has_audio_stream}")

        # ── Step 2: if stream exists, check whether it has real volume ─
        # volumedetect reports max_volume in dBFS; anything below -90 dBFS
        # is effectively silence (empty AAC track cameras write by default).
        is_silent = False
        if has_audio_stream:
            vol_result = _subprocess.run(
                ["ffmpeg", "-i", vid_path, "-af", "volumedetect",
                 "-f", "null", "/dev/null"],
                capture_output=True, text=True, timeout=60,
            )
            # Parse "max_volume: -91.0 dBFS" from stderr
            import re as _re
            m = _re.search(r"max_volume:\s*([-\d.]+)\s*dBFS", vol_result.stderr)
            if m:
                max_vol = float(m.group(1))
                is_silent = max_vol < -90.0
                print(f"[tiktok-upload] max_volume={max_vol} dBFS → is_silent={is_silent}")
            else:
                # Could not parse — assume silent to be safe
                is_silent = True
                print("[tiktok-upload] could not parse volumedetect output → treating as silent")

        needs_audio = (not has_audio_stream) or is_silent
        print(f"[tiktok-upload] needs_audio={needs_audio}")

        upload_path = vid_path  # fallback: upload original if ffmpeg fails or no track found

        if needs_audio:
            audio_path = _pick_random_insta_audio()
            if not audio_path:
                print("[tiktok-upload] WARNING: no tracks in assets/insta_audio/, uploading without audio")
            else:
                dur_probe = _subprocess.run(
                    ["ffprobe", "-v", "error", "-show_entries", "format=duration",
                     "-of", "default=noprint_wrappers=1:nokey=1", vid_path],
                    capture_output=True, text=True, timeout=30,
                )
                try:
                    duration = float(dur_probe.stdout.strip())
                except (ValueError, AttributeError):
                    duration = 0

                out_path = os.path.join(tmp_dir, "audio_" + orig_name)
                # Replace video audio (or add if absent) with background track
                cmd = [
                    "ffmpeg", "-y",
                    "-i", vid_path,
                    "-stream_loop", "-1", "-i", audio_path,
                    "-map", "0:v:0", "-map", "1:a:0",
                    "-c:v", "copy",
                    "-c:a", "aac", "-b:a", "192k",
                    *([ "-t", str(duration)] if duration > 0 else ["-shortest"]),
                    "-movflags", "+faststart",
                    out_path,
                ]
                result = _subprocess.run(cmd, capture_output=True, text=True, timeout=300)
                if result.returncode == 0:
                    upload_path = out_path
                    print(f"[tiktok-upload] ✓ replaced/added audio: {os.path.basename(audio_path)}")
                else:
                    print(f"[tiktok-upload] ffmpeg failed:\n{result.stderr[-400:]}")
        else:
            print(f"[tiktok-upload] video has real audio — uploading as-is")

        # ── upload processed (or original) video to Postiz ───────────
        filename  = os.path.basename(upload_path)
        mime_type = _mimetypes.guess_type(upload_path)[0] or "video/mp4"
        file_size = os.path.getsize(upload_path)
        print(f"[tiktok-upload] uploading {filename} ({file_size//1024} KB) to Postiz")
        boundary  = uuid.uuid4().hex
        part_head = (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
            f"Content-Type: {mime_type}\r\n\r\n"
        ).encode()
        part_tail = f"\r\n--{boundary}--\r\n".encode()
        # Read once, build body, then discard immediately
        with open(upload_path, "rb") as fh:
            file_data = fh.read()
        body = part_head + file_data + part_tail
        del file_data  # free before the HTTP call
        result = _postiz_proxy_post(
            "/upload", auth, body,
            f"multipart/form-data; boundary={boundary}",
        )
        del body
        return result

    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(500, str(e))
    finally:
        _shutil.rmtree(tmp_dir, ignore_errors=True)


@app.get("/")
def index():
    return FileResponse(os.path.join(STATIC, "index.html"))


@app.get("/auth")
def auth_page():
    p = os.path.join(STATIC, "auth.html")
    if not os.path.exists(p):
        raise HTTPException(404, "auth.html not found")
    return FileResponse(p)


@app.get("/pricing")
def pricing_page():
    p = os.path.join(STATIC, "pricing.html")
    if not os.path.exists(p):
        raise HTTPException(404, "pricing.html not found")
    return FileResponse(p)


# Static asset mount (CSS, JS, etc.)
app.mount("/static", StaticFiles(directory=STATIC), name="static")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def _diagnostics():
    """Print where the server is looking for your carousels so missing-content
    issues are obvious."""
    print("\n--- Paths ---")
    print(f"  __file__ resolves to: {os.path.abspath(__file__)}")
    print(f"  ROOT:       {ROOT}")
    print(f"  STATIC:     {STATIC}  (exists: {os.path.isdir(STATIC)})")
    print(f"  SINGLE_OUT: {SINGLE_OUT}")
    if os.path.isdir(SINGLE_OUT):
        n_single = sum(1 for d in os.listdir(SINGLE_OUT)
                       if os.path.isdir(os.path.join(SINGLE_OUT, d))
                       and os.path.exists(os.path.join(SINGLE_OUT, d, f"{d}.json")))
        print(f"    -> {n_single} valid single-recipe dirs (user generations)")
    else:
        print("    -> MISSING (will fall back to 'Single recipes/' samples)")
    print(f"  SINGLE_SAMPLES: {SINGLE_SAMPLES}")
    if os.path.isdir(SINGLE_SAMPLES):
        n_samples = sum(1 for d in os.listdir(SINGLE_SAMPLES)
                        if not d.startswith(".") and not d.startswith("_")
                        and os.path.isdir(os.path.join(SINGLE_SAMPLES, d))
                        and os.path.exists(os.path.join(SINGLE_SAMPLES, d, f"{d}.json")))
        print(f"    -> {n_samples} valid sample dirs")
    else:
        print("    -> not present (no bundled samples)")
    print(f"  COMP_OUT:   {COMP_OUT}")
    if os.path.isdir(COMP_OUT):
        n_comp = sum(1 for d in os.listdir(COMP_OUT)
                     if os.path.isdir(os.path.join(COMP_OUT, d))
                     and os.path.exists(os.path.join(COMP_OUT, d, f"{d}.json")))
        print(f"    -> {n_comp} valid compilation dirs")
    else:
        print("    -> MISSING (no compilations will show in library)")
    print()


def main():
    import uvicorn, threading, webbrowser, time
    # Render (and other PaaS) inject PORT; fall back to 8765 for local dev
    port = int(os.environ.get("PORT", 8765))
    # Bind to 0.0.0.0 so Render's router can reach the process;
    # on localhost this is identical to 127.0.0.1 in practice.
    host = "0.0.0.0"
    is_local = port == 8765 and not os.environ.get("RENDER")
    print("\n" + "=" * 60)
    print(f"  Slidecast Studio — http://localhost:{port}")
    print("=" * 60)
    _diagnostics()
    print("  Tip: Press Ctrl+C to stop.\n")
    if is_local:
        threading.Thread(
            target=lambda: (time.sleep(1.5), webbrowser.open(f"http://localhost:{port}")),
            daemon=True,
        ).start()
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()