"""
upload_assets_to_firebase.py

Uploads all carousel slide images from:
  assets/Single/Single recipes/{slug}/slides/*.png
  assets/Compilation/output_compilations/{slug}/slides/*.png

to Firebase Storage under:
  carousels/single/{slug}/slides/{filename}
  carousels/compilation/{slug}/slides/{filename}

Usage:
    pip install firebase-admin --break-system-packages
    python upload_assets_to_firebase.py

Requires GOOGLE_APPLICATION_CREDENTIALS env var pointing to your
service account JSON (same one used by the server).
"""

import os
import sys

try:
    import firebase_admin
    from firebase_admin import credentials, storage
except ImportError:
    print("ERROR: firebase-admin not installed.")
    print("Run: pip install firebase-admin --break-system-packages")
    sys.exit(1)

# ── Config ────────────────────────────────────────────────────────────────────

ROOT         = os.path.dirname(os.path.abspath(__file__))
SINGLE_DIR   = os.path.join(ROOT, "assets", "Single", "Single recipes")
COMP_DIR     = os.path.join(ROOT, "assets", "Compilation", "output_compilations")
BUCKET_NAME  = "slidecast-75f5c.firebasestorage.app"

# ── Init Firebase ─────────────────────────────────────────────────────────────

cred_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
if not cred_path or not os.path.exists(cred_path):
    print("ERROR: GOOGLE_APPLICATION_CREDENTIALS not set or file not found.")
    print("Set it to your service account JSON path, e.g.:")
    print("  export GOOGLE_APPLICATION_CREDENTIALS=/path/to/serviceAccount.json")
    sys.exit(1)

cred = credentials.Certificate(cred_path)
firebase_admin.initialize_app(cred, {"storageBucket": BUCKET_NAME})
bucket = storage.bucket()

# ── Upload helper ─────────────────────────────────────────────────────────────

def upload_folder(local_base: str, format_name: str):
    if not os.path.isdir(local_base):
        print(f"  Folder not found: {local_base}")
        return

    slugs = [d for d in os.listdir(local_base)
             if os.path.isdir(os.path.join(local_base, d)) and not d.startswith(".")]

    print(f"\n{'='*60}")
    print(f"  Format : {format_name}  ({len(slugs)} carousels)")
    print(f"{'='*60}")

    total_uploaded = 0
    total_skipped  = 0

    for slug in sorted(slugs):
        slides_dir = os.path.join(local_base, slug, "slides")
        if not os.path.isdir(slides_dir):
            print(f"  [{slug}] no slides/ folder — skipping")
            continue

        pngs = sorted(f for f in os.listdir(slides_dir) if f.endswith(".png"))
        print(f"\n  [{slug}]  {len(pngs)} slides")

        for fname in pngs:
            local_path   = os.path.join(slides_dir, fname)
            storage_path = f"carousels/{format_name}/{slug}/slides/{fname}"
            blob         = bucket.blob(storage_path)

            if blob.exists():
                print(f"    ✓ skip  {fname}  (already uploaded)")
                total_skipped += 1
                continue

            blob.upload_from_filename(local_path, content_type="image/png")
            # Make publicly readable
            blob.make_public()
            print(f"    ↑ done  {fname}")
            total_uploaded += 1

    print(f"\n  Done — {total_uploaded} uploaded, {total_skipped} skipped")

# ── Run ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print(f"Bucket : {BUCKET_NAME}")
    upload_folder(SINGLE_DIR, "single")
    upload_folder(COMP_DIR,   "compilation")

    print("\n\nAll done! Images are live at:")
    print(f"  https://storage.googleapis.com/{BUCKET_NAME}/carousels/single/{{slug}}/slides/{{filename}}")
    print(f"  https://storage.googleapis.com/{BUCKET_NAME}/carousels/compilation/{{slug}}/slides/{{filename}}")
