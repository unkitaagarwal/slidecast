# Slidecast Studio

The local web UI for Slidecast — a pipeline that does two things most tools
won't:

1. **Generate** a 10–12 slide carousel from a one-line brief (Gemini text +
   Nano Banana images + PIL compositor, ~30s end-to-end).
2. **Distribute** it to every TikTok and Instagram account you've connected via
   Postiz — with captions and hashtags already written. One click, every account.

Wraps both content pipelines (`pipeline/` for single recipes,
`compilation_pipeline/` for 5-recipe compilations) behind a clean landing page,
plus an owned-account tracking view powered by the TikTok Display API.

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

## What you can do today

- **Type a brief** — a recipe like "high-protein chicken caesar wrap" or a
  theme like "5 weekend dinners for your lazy ass". Pick a format (Single
  Recipe = 10 slides, Compilation = 12 slides covering 5 recipes).
- **Auto-generate** — Gemini writes the recipes, caption, and hashtags;
  Nano Banana renders cinematic food photos; the compositor lays out
  10–12 finished slides. ~25–30 seconds per carousel.
- **Preview the output** — every slide plus the full TikTok caption
  (with `#Slidecast` and 13 other hashtags) before you push it anywhere.
- **Browse the library** — every carousel ever generated, filtered by format.
- **Track owned accounts** — connect each TikTok account via PKCE OAuth and
  pull daily plays/likes/comments/shares snapshots from the Display API.

## Auto-posting (the second half of the pipeline)

The distribute half currently runs from the terminal:

```bash
# from the repo root, after generating a carousel
python3 compilation_pipeline/postiz_publish.py <slug>
# or for a single recipe
python3 pipeline/postiz_publish.py <slug>
```

These scripts fan the slides + caption + hashtags out across every connected
account in Postiz (TikTok + Instagram) on schedule. **Wiring this directly
into the studio UI as a "Generate + post" one-click button is the next thing
on the roadmap** — until then the script is one terminal command away.

## What's NOT in this version

- One-click "Generate + post to every account" from the UI (CLI works today —
  see above; UI integration is the next milestone).
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
  "brand_name":      "Slidecast",
  "studio_name":     "Studio",
  "tagline_html":    "Generate carousels.<br/>Post to every account.<br/>In <em>one click.</em>",
  "subtagline":      "Two problems, one pipeline. ...",
  "eyebrow":         "For creators running multiple accounts",
  "primary_color":   "#ff5c7a",
  "secondary_color": "#f4c47a",
  "tiktok_handle":   "@nutrilens.ai",
  "cta_phrase":      "Made with Slidecast — generate carousels & auto-post to all your accounts. Link in bio",
  "footer_meta":     "runs locally · uses your Gemini key from .env"
}
```

The frontend fetches `/api/branding` on page load and overrides every
`data-brand="key"` element + CSS color variables. No server restart needed
unless you change Python source code.

If you want to white-label the entire app (e.g. for a SaaS client), this is
the single file to edit. Swap the SVG brand mark in `static/index.html` too
if you want a custom logo.
