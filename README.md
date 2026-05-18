# Slidecast

**Generate carousels. Post to every account. In one click.**

Slidecast solves the two real problems creator-operators have:

1. **Making the content is slow** — writing hooks, generating images, composing
   slides. Slidecast turns a one-line brief into a finished 10–12 slide carousel
   in ~30 seconds (Gemini text + Nano Banana imagery + PIL compositing).
2. **Posting at scale is even slower** — if you run 5 or 13 accounts you're
   manually uploading, re-captioning, and re-scheduling for each one. Slidecast
   pushes the carousel to every connected TikTok and Instagram account through
   Postiz, captions and hashtags already in place, on schedule.

One brief → finished slides → live on every account. Zero copy-paste.

## What's in this repo

This package combines **two services** that we want to merge into a single
product:

1. **Website / Studio UI** (`webapp/`)
   FastAPI backend + vanilla HTML/CSS/JS frontend. Template gallery, brand
   customization, bulk generation, ZIP download, tracking page.
2. **Generation pipeline** (`pipeline/` + `compilation_pipeline/`)
   Standalone CLI pipelines that the webapp wraps. Useful as the reference
   implementation when porting into another stack.

```
slidecast_carousel_engine/
├── webapp/                     ← UI + API server (port 8765)
│   ├── server.py               ← FastAPI app, all endpoints
│   ├── start.sh                ← bootstrap (deps + run)
│   ├── branding.json           ← brand colors + name + logo path
│   ├── static/                 ← single-file HTML, CSS, JS
│   ├── templates_engine/       ← 8 carousel templates + compositor + LLM
│   │                              generator (auto-discovery via registry.py)
│   └── tracking/               ← TikTok Display API (PKCE OAuth) + storage
├── pipeline/                   ← Single-recipe carousel CLI (legacy)
├── compilation_pipeline/       ← 5-recipe "compilation" carousel CLI
├── assets/                     ← fonts + parchment background + CTA card
├── examples/                   ← sample themes + briefs (text)
└── sample_output/              ← one generated JSON + 1 cover PNG (reference)
```

## Quick start

```bash
# 1. Install deps
python3 -m pip install -r requirements.txt

# 2. Copy and fill .env (Gemini + Postiz + TikTok keys)
cp .env.example .env

# 3. Run the webapp (auto-opens browser at http://localhost:8765)
cd webapp && bash start.sh
```

## What each service does

### Website (`webapp/`)
- **Template gallery** — 8 research-backed carousel formats
  (Top List, Quick Tips, Mistakes/Fixes, App Promo, Before/After,
  Curated Picks, Day in Life, Hot Take).
- **Generator UI** — pick a template, fill the brief, generate a carousel,
  download as ZIP. Brand color and logo are applied at composite time.
- **Library** — horizontal scroll rails per format, TikTok-style phone
  preview, copy caption/hashtags.
- **Tracking page** — connect owned TikTok accounts via PKCE OAuth,
  pull video stats from the Display API on a schedule.

### Pipeline (`pipeline/` and `compilation_pipeline/`)
- **`pipeline/`** — single-recipe carousels. Each post is one full recipe.
- **`compilation_pipeline/`** — 5-recipes-per-post format (the format that
  consistently outperforms in our analytics). 12 slides:
  hook → photo+page × 5 → CTA.
- Both share the same compositor pattern: Gemini 2.5 Flash for text,
  Nano Banana (gemini-2.5-flash-image) for slide imagery, PIL for compositing.
- `postiz_publish.py` (in both folders) uploads slides and schedules across
  multiple connected accounts (TikTok + Instagram).

## Merging the two services

The webapp is the long-term home — `pipeline/` and `compilation_pipeline/`
were the standalone prototypes. To merge:

1. `webapp/templates_engine/generator.py` already wraps the same Gemini flow.
   Move `compilation_pipeline/recipes_compilation.py` brief-style prompts in
   as another Template (the "compilation" format), so the studio UI can
   generate them too.
2. Move `compilation_pipeline/postiz_publish.py` into
   `webapp/publishing/postiz.py` and expose `POST /api/publish/{slug}` from
   `server.py`. Today this is invoked from the CLI; the webapp can call the
   same function.
3. The `assets/` folder is shared by both — keep at the repo root.
4. `branding.json` already drives both: webapp reads it via `/api/branding`,
   compositor reads it directly. No change needed.

## Environment variables

See `.env.example`. The webapp and pipelines read from the same `.env`.

| Key                    | Used by                          |
| ---------------------- | -------------------------------- |
| `GEMINI_API_KEY`       | text + image generation          |
| `POSTIZ_API_KEY`       | scheduling to TikTok / Instagram |
| `TIKTOK_CLIENT_KEY`    | tracking OAuth                   |
| `TIKTOK_CLIENT_SECRET` | tracking OAuth                   |
| `TIKTOK_REDIRECT_URI`  | tracking OAuth callback          |

## Sample output

`sample_output/03_5_homemade_protein_bars/` contains:
- The full carousel JSON (caption, hashtags, slide specs, 5 recipes)
- One cover slide PNG (`cover_example.png`) showing the rendered hook

The full carousel was 12 slides — only one is included as a visual reference.
