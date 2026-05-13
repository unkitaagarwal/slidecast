# RecipeVault Studio

A local web tool that wraps both content pipelines (`pipeline/` for single
recipes, `compilation_pipeline/` for 5-recipe compilations) behind a clean
landing page. Type a theme, click Generate, get a 10–12 slide carousel ready
for TikTok in ~30 seconds.

## Quick start

From the repo root:

```bash
bash webapp/start.sh
```

That installs the few extra deps (`fastapi`, `uvicorn`, plus the existing
`google-genai`, `openai`, `requests`, `Pillow`) and launches the server at
[http://localhost:8765](http://localhost:8765). On macOS the browser opens
automatically.

If you'd rather run it yourself:

```bash
pip install fastapi uvicorn --break-system-packages
python3 webapp/server.py
```

## What you can do

- **Pick a format** — Single Recipe (10 slides) or Compilation (12 slides, 5 recipes).
- **Type a prompt** — a recipe brief like "high-protein chicken caesar wrap"
  or a theme like "5 weekend dinners for your lazy ass".
- **Watch progress** — the server runs the same Gemini + Nano Banana pipeline
  you've been using. Compilations take ~30 seconds; single recipes ~25 seconds.
- **Preview the output** — all 10 or 12 slides + the auto-generated TikTok
  caption (with `#RecipeVault` and 13 other hashtags).
- **Browse the library** — every carousel ever generated, filtered by format.

## What's NOT in this version

- Publishing to TikTok from the UI (use `compilation_pipeline/postiz_publish.py`
  or `pipeline/postiz_publish.py` from the terminal — those are unchanged and
  battle-tested).
- Editing recipes after generation (open the JSON in `output/<slug>/<slug>.json`
  or `output_compilations/<slug>/<slug>.json` and re-composite manually).
- Multi-user / cloud deployment (this is a single-user local tool).

## Files

```
webapp/
  server.py        — FastAPI server (~300 lines)
  start.sh         — one-line launcher
  static/
    index.html     — landing page + UI
    style.css      — dark theme with coral accent
    app.js         — generate flow + library + lightbox
```

## Environment

Reads `.env` from the repo root. Needs at minimum:

```
GEMINI_API_KEY=...     # for both text gen and Nano Banana images
POSTIZ_API_KEY=...     # only required if you publish from CLI
```

OpenAI key is no longer required — both pipelines run on Gemini now.

## Rebrand it (product-ize)

The studio is built so it can ship as a generic product. Open
`webapp/branding.json` and change any of these values, then refresh the page:

```json
{
  "brand_name":      "RecipeVault",
  "studio_name":     "Studio",
  "tagline_html":    "Generate viral<br/>TikTok carousels<br/>in <em>30 seconds.</em>",
  "subtagline":      "Pick a format. Type a vibe. ...",
  "eyebrow":         "For RecipeVault creators",
  "primary_color":   "#ff5c7a",
  "secondary_color": "#f4c47a",
  "tiktok_handle":   "@nutrilens.ai",
  "cta_phrase":      "Save these recipes easily with RecipeVault app! Link in bio",
  "footer_meta":     "runs locally · uses your Gemini key from .env"
}
```

The frontend fetches `/api/branding` on page load and overrides every
`data-brand="key"` element + CSS color variables. No server restart needed
unless you change Python source code.

If you want to white-label the entire app (e.g. for a SaaS client), this is
the single file to edit. Swap the SVG brand mark in `static/index.html` too
if you want a custom logo.
