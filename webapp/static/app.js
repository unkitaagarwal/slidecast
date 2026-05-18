// Slidecast Studio — frontend
(() => {
  const $ = (s) => document.querySelector(s);
  const $$ = (s) => document.querySelectorAll(s);

  const promptEl = $('#prompt');
  const generateBtn = $('#generate-btn');
  const jobPanel = $('#job-panel');
  const jobTitle = $('#job-title');
  const jobMsg = $('#job-msg');
  const jobBar = $('#job-bar');
  const resultPanel = $('#result-panel');
  const slidesGrid = $('#slides-grid');
  const captionText = $('#caption-text');
  const resultTitle = $('#result-title');
  const resultSubtitle = $('#result-subtitle');
  const copyCaptionBtn = $('#copy-caption');
  const openFolderEl = $('#open-folder');
  const railComp = $('#rail-comp');
  const railSingle = $('#rail-single');
  const countComp = $('#count-comp');
  const countSingle = $('#count-single');
  const modal = $('#modal');
  const modalBody = $('#modal-body');
  const modalClose = $('#modal-close');

  let selectedFmt = 'compilation';
  let currentResult = null;
  let allItems = [];
  let demoMode = false;

  // =========================================================================
  // Demo library — shown when the user has not generated anything yet so the
  // page never looks empty. Procedurally-rendered SVG slides; replaced the
  // moment the user generates real content.
  // =========================================================================
  const DEMO_THEMES = {
    warm:      { bgTop: '#3a1818', bgBot: '#0d0606', glow: '#ff5c7a', text: '#ffffff', sub: 'rgba(255,255,255,0.55)' },
    charcoal:  { bgTop: '#1c1820', bgBot: '#0a070d', glow: '#c084fc', text: '#ffffff', sub: 'rgba(255,255,255,0.6)' },
    forest:    { bgTop: '#1f3a2e', bgBot: '#08160f', glow: '#34d399', text: '#ffffff', sub: 'rgba(255,255,255,0.6)' },
    berry:     { bgTop: '#3d1b3d', bgBot: '#160a18', glow: '#ec4899', text: '#ffffff', sub: 'rgba(255,255,255,0.6)' },
    rust:      { bgTop: '#3d2516', bgBot: '#180c05', glow: '#fb923c', text: '#ffffff', sub: 'rgba(255,255,255,0.6)' },
  };

  function _svgEsc(s) {
    return String(s == null ? '' : s)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
  }

  // Word-wrap helper for SVG <text> — splits a string into N-line chunks.
  function _wrap(text, maxChars) {
    const words = String(text || '').split(/\s+/);
    const lines = [];
    let cur = '';
    for (const w of words) {
      if ((cur + ' ' + w).trim().length > maxChars && cur) {
        lines.push(cur);
        cur = w;
      } else {
        cur = (cur + ' ' + w).trim();
      }
    }
    if (cur) lines.push(cur);
    return lines;
  }

  function _demoSvg(cfg) {
    const t = DEMO_THEMES[cfg.theme] || DEMO_THEMES.warm;
    let body = '';

    if (cfg.type === 'hook') {
      const lines = _wrap((cfg.title || '').toUpperCase(), 14).slice(0, 5);
      const lh = 145;
      const startY = 960 - ((lines.length - 1) * lh) / 2 - 30;
      body = `
        <text x="540" text-anchor="middle" fill="${t.text}" font-family="'Fraunces','Times New Roman',serif" font-size="118" font-weight="800" letter-spacing="-3">
          ${lines.map((l, i) => `<tspan x="540" y="${startY + i * lh}">${_svgEsc(l)}</tspan>`).join('')}
        </text>
        <text x="540" y="1760" text-anchor="middle" fill="${t.sub}" font-family="'Plus Jakarta Sans',sans-serif" font-size="36" font-weight="700" letter-spacing="5">
          ${_svgEsc((cfg.subtitle || '→ SWIPE FOR ALL').toUpperCase())}
        </text>`;
    } else if (cfg.type === 'photo') {
      const recipeLines = _wrap((cfg.title || '').toUpperCase(), 16).slice(0, 3);
      body = `
        <text x="540" y="500" text-anchor="middle" fill="${t.text}" fill-opacity="0.7" font-family="'Plus Jakarta Sans',sans-serif" font-size="48" font-weight="800" letter-spacing="8">
          ${cfg.num} / ${cfg.total}
        </text>
        <circle cx="540" cy="930" r="320" fill="${t.glow}" fill-opacity="0.14"/>
        <circle cx="540" cy="930" r="220" fill="${t.glow}" fill-opacity="0.22"/>
        <circle cx="540" cy="930" r="120" fill="${t.glow}" fill-opacity="0.35"/>
        <text x="540" text-anchor="middle" fill="${t.text}" font-family="'Fraunces',serif" font-size="96" font-weight="800" letter-spacing="-2">
          ${recipeLines.map((l, i) => `<tspan x="540" y="${1340 + i * 115}">${_svgEsc(l)}</tspan>`).join('')}
        </text>`;
    } else if (cfg.type === 'recipe') {
      const ings = (cfg.ingredients || []).slice(0, 6);
      const stps = (cfg.steps || []).slice(0, 4);
      body = `
        <rect x="60" y="160" width="960" height="1600" rx="24" fill="#f4e8d0"/>
        <text x="540" y="320" text-anchor="middle" fill="#7c2d12" font-family="'Plus Jakarta Sans',sans-serif" font-size="28" font-weight="800" letter-spacing="6">RECIPE ${cfg.num} / ${cfg.total}</text>
        <text x="540" y="430" text-anchor="middle" fill="#2a1810" font-family="'Fraunces',serif" font-size="68" font-weight="800">
          ${_wrap(cfg.title || '', 20).slice(0, 2).map((l, i) => `<tspan x="540" dy="${i === 0 ? 0 : 80}">${_svgEsc(l)}</tspan>`).join('')}
        </text>
        <line x1="180" y1="540" x2="900" y2="540" stroke="#b91c1c" stroke-width="3"/>
        <text x="120" y="640" fill="#7c2d12" font-family="'Plus Jakarta Sans',sans-serif" font-size="32" font-weight="800" letter-spacing="4">INGREDIENTS</text>
        ${ings.map((ing, i) => `<text x="120" y="${720 + i * 58}" fill="#2a1810" font-family="'Plus Jakarta Sans',sans-serif" font-size="34">• ${_svgEsc(ing)}</text>`).join('')}
        <text x="120" y="${720 + ings.length * 58 + 60}" fill="#7c2d12" font-family="'Plus Jakarta Sans',sans-serif" font-size="32" font-weight="800" letter-spacing="4">STEPS</text>
        ${stps.map((st, i) => {
          const yBase = 720 + ings.length * 58 + 140 + i * 80;
          const stepLines = _wrap(st, 38).slice(0, 2);
          return stepLines.map((l, j) => `<text x="120" y="${yBase + j * 38}" fill="#2a1810" font-family="'Plus Jakarta Sans',sans-serif" font-size="30">${j === 0 ? `<tspan font-weight="800">${i + 1}. </tspan>` : '<tspan>   </tspan>'}${_svgEsc(l)}</text>`).join('');
        }).join('')}`;
    } else if (cfg.type === 'cta') {
      body = `
        <text x="540" y="800" text-anchor="middle" fill="${t.text}" font-family="'Fraunces',serif" font-size="100" font-weight="800" letter-spacing="-2">
          <tspan x="540" dy="0">MADE WITH</tspan>
        </text>
        <text x="540" y="970" text-anchor="middle" fill="${t.glow}" font-family="'Fraunces',serif" font-size="160" font-weight="800" font-style="italic">Slidecast</text>
        <rect x="220" y="1170" width="640" height="130" rx="65" fill="${t.glow}" fill-opacity="0.95"/>
        <text x="540" y="1255" text-anchor="middle" fill="#fff" font-family="'Plus Jakarta Sans',sans-serif" font-size="44" font-weight="800" letter-spacing="3">→ TAP LINK IN BIO</text>
        <text x="540" y="1450" text-anchor="middle" fill="${t.sub}" font-family="'Plus Jakarta Sans',sans-serif" font-size="34" font-weight="600">
          Generate &amp; auto-post to every account
        </text>`;
    }

    const svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1080 1920">
      <defs>
        <linearGradient id="bg" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stop-color="${t.bgTop}"/>
          <stop offset="100%" stop-color="${t.bgBot}"/>
        </linearGradient>
        <radialGradient id="glow" cx="50%" cy="35%" r="55%">
          <stop offset="0%" stop-color="${t.glow}" stop-opacity="0.32"/>
          <stop offset="100%" stop-color="${t.glow}" stop-opacity="0"/>
        </radialGradient>
      </defs>
      <rect width="1080" height="1920" fill="url(#bg)"/>
      <rect width="1080" height="1920" fill="url(#glow)"/>
      ${body}
    </svg>`;
    return 'data:image/svg+xml;utf8,' + encodeURIComponent(svg);
  }

  // Build the 12-slide spread for a compilation (hook + 5×(photo+recipe) + cta).
  function _compSlides(theme, hookText, recipes) {
    const slides = [{ type: 'hook', title: hookText, subtitle: '→ swipe for all 5' }];
    recipes.forEach((r, i) => {
      slides.push({ type: 'photo', num: i + 1, total: recipes.length, title: r.title });
      slides.push({ type: 'recipe', num: i + 1, total: recipes.length, title: r.title, ingredients: r.ingredients, steps: r.steps });
    });
    slides.push({ type: 'cta' });
    return slides.map(cfg => _demoSvg({ theme, ...cfg }));
  }

  // Build a short 4-slide spread for singles / secondary items.
  function _singleSlides(theme, hookText, recipe) {
    return [
      { type: 'hook', title: hookText, subtitle: '↓ swipe for the recipe' },
      { type: 'photo', num: 1, total: 1, title: recipe.title },
      { type: 'recipe', num: 1, total: 1, title: recipe.title, ingredients: recipe.ingredients, steps: recipe.steps },
      { type: 'cta' },
    ].map(cfg => _demoSvg({ theme, ...cfg }));
  }

  const DEMO_RECIPES = {
    bulgogi:   { title: 'Korean beef bulgogi bowl',    ingredients: ['500g ribeye, thin-sliced','4 tbsp soy sauce','2 tbsp brown sugar','4 cloves garlic, minced','1 tbsp sesame oil','Rice + scallions'], steps: ['Marinate beef 20 min in soy + sugar + garlic','Sear hot 3 min per side','Reduce marinade into glaze','Spoon over rice, top with scallions'] },
    salmon:    { title: 'Lemon garlic salmon',         ingredients: ['4 salmon fillets','4 tbsp butter','6 cloves garlic','2 lemons','Fresh dill','Olive oil + salt + pepper'], steps: ['Pat fillets dry, season generously','Sear skin-down 4 min','Add butter, garlic, lemon zest','Baste 2 min, finish with juice + dill'] },
    orzo:      { title: 'Creamy mushroom orzo',        ingredients: ['1.5 cups orzo','500g mixed mushrooms','2 shallots, minced','1 cup chicken stock','1 cup heavy cream','Parmesan + thyme'], steps: ['Brown mushrooms hard, don\'t crowd','Sweat shallots, deglaze with wine','Add orzo, toast, then stock','Finish with cream, parm, thyme'] },
    sesame:    { title: 'Honey sesame chicken',        ingredients: ['1kg chicken thighs','¼ cup honey','3 tbsp soy sauce','2 tbsp rice vinegar','Garlic + ginger','Sesame seeds + scallions'], steps: ['Sear chicken golden in batches','Whisk honey, soy, vinegar, ginger','Reduce sauce until syrupy','Toss chicken, garnish, serve'] },
    chorizo:   { title: 'One-pot chorizo pasta',       ingredients: ['400g rigatoni','300g chorizo, sliced','1 onion + 4 garlic cloves','1 can crushed tomatoes','1 cup chicken stock','Cream + parmesan'], steps: ['Render chorizo until crispy','Sweat onion + garlic in fat','Add tomatoes, stock, pasta','Simmer 12 min, finish with cream'] },
    wrap:      { title: 'High-protein chicken caesar wrap', ingredients: ['2 grilled chicken breasts','2 large flour tortillas','¼ cup Greek-yogurt caesar','Romaine + parmesan','Cracked pepper','Lemon zest'], steps: ['Slice chicken thin','Toss greens in caesar','Layer in tortilla, roll tight','Sear seam-down in dry pan'] },
  };

  const DEMO_ITEMS = [
    {
      is_demo: true, format: 'compilation', slug: 'demo-lazy-dinners',
      title: '5 weekend dinners for your LAZY ASS 😏',
      subtitle: 'For when the work week ate your brain · 12 slides',
      theme: 'warm',
      caption: '5 weekend dinners for your LAZY ASS 😏\n\nSave this carousel for when the work week ate your brain. 🍳\n\nMade with Slidecast — generate carousels & auto-post to all your accounts. Link in bio 📝🍳\n\n#Slidecast #mealplan #weekenddinners #cozydinner #lazydinners #dinnerideas #whattocook #DinnerIdeas',
      _slidesFactory: () => _compSlides('warm', '5 weekend dinners for your lazy ass 😏', [DEMO_RECIPES.bulgogi, DEMO_RECIPES.salmon, DEMO_RECIPES.orzo, DEMO_RECIPES.sesame, DEMO_RECIPES.chorizo]),
    },
    {
      is_demo: true, format: 'compilation', slug: 'demo-protein-lunches',
      title: '5 high-protein lunches under 600 cal',
      subtitle: 'Gym-bro approved, desk-job tested · 12 slides',
      theme: 'forest',
      caption: '5 high-protein lunches under 600 cal 💪\n\nGym-bro approved, desk-job tested.\n\nMade with Slidecast — generate carousels & auto-post to all your accounts. Link in bio 📝\n\n#Slidecast #mealprep #highprotein #lunchideas #fitfood #healthyrecipes',
      _slidesFactory: () => _compSlides('forest', '5 high-protein lunches under 600 cal', [DEMO_RECIPES.wrap, DEMO_RECIPES.salmon, DEMO_RECIPES.bulgogi, DEMO_RECIPES.sesame, DEMO_RECIPES.orzo]),
    },
    {
      is_demo: true, format: 'compilation', slug: 'demo-cozy-fall',
      title: '5 cozy fall dinners for cold rainy nights',
      subtitle: 'Sweater-weather food · 12 slides',
      theme: 'berry',
      caption: '5 cozy fall dinners for cold rainy nights 🍂\n\nSweater weather. Hearty bowls. Save for later.\n\nMade with Slidecast — generate carousels & auto-post to all your accounts. Link in bio 📝\n\n#Slidecast #cozyseason #falldinner #comfortfood #mealideas #dinneridea',
      _slidesFactory: () => _compSlides('berry', '5 cozy fall dinners for cold rainy nights', [DEMO_RECIPES.chorizo, DEMO_RECIPES.orzo, DEMO_RECIPES.sesame, DEMO_RECIPES.bulgogi, DEMO_RECIPES.salmon]),
    },
    {
      is_demo: true, format: 'single', slug: 'demo-bulgogi',
      title: 'Korean spicy beef bulgogi bowl',
      subtitle: '15 minutes · feeds 2 · 10 slides',
      theme: 'charcoal',
      caption: 'Korean spicy beef bulgogi bowl 🍚 15 min · serves 2.\n\nFast, punchy, dinner-party-worthy on a Tuesday.\n\nMade with Slidecast — generate carousels & auto-post to all your accounts. Link in bio 📝\n\n#Slidecast #koreanfood #bulgogi #ricebowl #weeknight',
      _slidesFactory: () => _singleSlides('charcoal', 'Korean spicy beef bulgogi bowl', DEMO_RECIPES.bulgogi),
    },
    {
      is_demo: true, format: 'single', slug: 'demo-orzo',
      title: 'Creamy mushroom orzo with parmesan',
      subtitle: 'One pan · 20 minutes · 10 slides',
      theme: 'rust',
      caption: 'Creamy mushroom orzo with parmesan 🍄 one pan · 20 min.\n\nThe one your roommate keeps stealing.\n\nMade with Slidecast — generate carousels & auto-post to all your accounts. Link in bio 📝\n\n#Slidecast #orzo #mushroomrecipes #onepot #pasta',
      _slidesFactory: () => _singleSlides('rust', 'Creamy mushroom orzo with parmesan', DEMO_RECIPES.orzo),
    },
  ];

  function _hydrateDemoItem(it) {
    if (it._hydrated) return it;
    const slides = it._slidesFactory();
    it.slides = slides;
    it.thumbnail = slides[0];
    it._hydrated = true;
    return it;
  }
  // Build thumbnails up front so the rail cards have covers.
  DEMO_ITEMS.forEach(_hydrateDemoItem);
  // ============================== end demo lib ==============================

  // ---------- Format selector ----------
  $$('.fmt-card').forEach((card) => {
    card.addEventListener('click', () => {
      $$('.fmt-card').forEach((c) => c.classList.remove('selected'));
      card.classList.add('selected');
      selectedFmt = card.dataset.fmt;
    });
    // Magnetic glow effect
    card.addEventListener('mousemove', (e) => {
      const rect = card.getBoundingClientRect();
      card.style.setProperty('--mx', `${e.clientX - rect.left}px`);
      card.style.setProperty('--my', `${e.clientY - rect.top}px`);
    });
  });

  // ---------- Example chips ----------
  $$('.chip').forEach((chip) => {
    chip.addEventListener('click', () => {
      promptEl.value = chip.dataset.chip;
      const fmt = chip.dataset.fmt;
      if (fmt) {
        selectedFmt = fmt;
        $$('.fmt-card').forEach((c) => {
          c.classList.toggle('selected', c.dataset.fmt === fmt);
        });
      }
      promptEl.focus();
    });
  });

  // ---------- Generate ----------
  generateBtn.addEventListener('click', startGeneration);
  promptEl.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') startGeneration();
  });

  // Smarter status messages — rotate as job runs
  const STAGE_MESSAGES_COMP = [
    'Drafting hooks + 5 recipes via Gemini…',
    'Generating cinematic hero photos with Nano Banana…',
    'Rendering parchment recipe pages…',
    'Compositing CTA + slide titles…',
    'Almost there — final layer of polish…',
  ];
  const STAGE_MESSAGES_SINGLE = [
    'Drafting recipe + slide breakdown via Gemini…',
    'Generating bowl shots with Nano Banana…',
    'Compositing slides with auto-fit text…',
    'Adding the final Slidecast CTA…',
    'Wrapping it up…',
  ];

  async function startGeneration() {
    const prompt = (promptEl.value || '').trim();
    if (!prompt) {
      promptEl.focus();
      return;
    }
    generateBtn.disabled = true;
    generateBtn.querySelector('svg')?.style && (generateBtn.querySelector('svg').style.opacity = '0');
    generateBtn.firstChild && (generateBtn.firstChild.nodeValue = 'Generating');

    resultPanel.classList.add('hidden');
    jobPanel.classList.remove('hidden');
    jobPanel.scrollIntoView({ behavior: 'smooth', block: 'center' });
    jobTitle.textContent = 'Sending to pipeline…';
    jobMsg.textContent = `Format: ${selectedFmt}`;
    jobBar.style.width = '4%';

    // Brand override is sent ONLY for paid users with an uploaded brand
    // image. Free / anon generate with the default Slidecast CTA card —
    // that's the "preview only" promise. Once a user upgrades and goes
    // through onboarding (which captures brand.imageDataUrl + brand.name),
    // every subsequent generation swaps in their image on slide 06.
    const _user = (function () {
      try { return (JSON.parse(localStorage.getItem('slidecast.state.v1')) || {}).user; }
      catch (e) { return null; }
    })();
    const _isPaid = !!_user && (_user.tier === 'basic' || _user.tier === 'pro');
    const reqBody = { format: selectedFmt, input: prompt };
    if (_isPaid && _user.brand && _user.brand.imageDataUrl) {
      reqBody.brand = {
        name: _user.brand.name || null,
        cta_text: _user.brand.cta || null,
        image_data_url: _user.brand.imageDataUrl,
      };
    }

    try {
      const res = await fetch('/api/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(reqBody),
      });
      if (!res.ok) {
        const err = await res.text();
        throw new Error(`HTTP ${res.status}: ${err}`);
      }
      const data = await res.json();
      const jobId = data.job_id;
      jobTitle.textContent = 'Working';
      jobMsg.textContent = `Job ${jobId} accepted`;
      pollJob(jobId);
    } catch (e) {
      jobTitle.textContent = 'Failed';
      jobMsg.textContent = String(e);
      restoreGenerateBtn();
    }
  }

  function restoreGenerateBtn() {
    generateBtn.disabled = false;
    generateBtn.innerHTML = `Generate <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><path d="M5 12h14M13 5l7 7-7 7"/></svg>`;
  }

  async function pollJob(jobId) {
    const startTime = Date.now();
    let progress = 8;
    let stageIdx = 0;
    const messages = selectedFmt === 'compilation' ? STAGE_MESSAGES_COMP : STAGE_MESSAGES_SINGLE;

    while (true) {
      await new Promise((r) => setTimeout(r, 1500));
      progress = Math.min(progress + 3, 92);
      jobBar.style.width = `${progress}%`;

      // Cycle through stage messages so the UI feels lively
      if (Math.random() < 0.45 && stageIdx < messages.length) {
        jobMsg.textContent = messages[stageIdx];
        stageIdx += 1;
      }

      try {
        const res = await fetch(`/api/jobs/${jobId}`);
        if (!res.ok) {
          jobTitle.textContent = 'Lost job';
          jobMsg.textContent = 'Server error fetching job';
          break;
        }
        const j = await res.json();
        // Use server's message if it's more specific
        if (j.message && (j.message.includes('Generating') || j.message.includes('Done'))) {
          jobMsg.textContent = j.message;
        }

        if (j.status === 'done') {
          jobBar.style.width = '100%';
          jobTitle.textContent = 'Ready';
          jobMsg.textContent = 'Carousel composited and saved to disk';
          await loadPreview(j.result.format, j.result.slug);
          break;
        }
        if (j.status === 'failed') {
          jobTitle.textContent = 'Failed';
          jobMsg.textContent = j.error || j.message;
          break;
        }
      } catch (e) {
        jobMsg.textContent = `Error: ${e}`;
      }

      if (Date.now() - startTime > 5 * 60 * 1000) {
        jobTitle.textContent = 'Timed out';
        jobMsg.textContent = 'Generation took longer than 5 minutes — check terminal logs';
        break;
      }
    }

    restoreGenerateBtn();
    refreshLibrary();
  }

  async function loadPreview(format, slug) {
    const res = await fetch(`/api/preview/${format}/${slug}`);
    if (!res.ok) {
      alert('Preview failed');
      return;
    }
    const data = await res.json();
    renderResult(data);
  }

  function renderResult(data) {
    currentResult = data;
    resultPanel.classList.remove('hidden');
    resultTitle.textContent = data.title || data.slug;
    resultSubtitle.textContent = data.subtitle || '';
    captionText.textContent = data.caption || '';

    slidesGrid.innerHTML = '';
    data.slides.forEach((url, i) => {
      const t = document.createElement('div');
      t.className = 'thumb';
      t.innerHTML = `<span class="thumb-num">${String(i + 1).padStart(2, '0')}</span>`;
      const img = document.createElement('img');
      img.src = url;
      img.loading = 'lazy';
      t.appendChild(img);
      t.addEventListener('click', () => openLightbox(url));
      slidesGrid.appendChild(t);
    });

    const folderRel = data.format === 'single'
      ? `output/${data.slug}/slides/`
      : `output_compilations/${data.slug}/slides/`;
    openFolderEl.title = folderRel;
    openFolderEl.textContent = folderRel;
    setTimeout(() => resultPanel.scrollIntoView({ behavior: 'smooth', block: 'start' }), 200);
  }

  copyCaptionBtn.addEventListener('click', async () => {
    if (!currentResult) return;
    try {
      await navigator.clipboard.writeText(currentResult.caption);
      const original = copyCaptionBtn.innerHTML;
      copyCaptionBtn.innerHTML = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round"><path d="M5 12l5 5L20 7"/></svg> Copied`;
      setTimeout(() => (copyCaptionBtn.innerHTML = original), 1500);
    } catch (e) {
      alert('Copy failed: ' + e);
    }
  });

  // ---------- Lightbox ----------
  function openLightbox(url) {
    const lb = document.createElement('div');
    lb.className = 'lightbox';
    const img = document.createElement('img');
    img.src = url;
    lb.appendChild(img);
    lb.addEventListener('click', () => lb.remove());
    document.body.appendChild(lb);
  }

  // ---------- Library ----------
  async function refreshLibrary() {
    try {
      const res = await fetch('/api/library', { cache: 'no-store' });
      if (!res.ok) {
        console.error('Library API returned', res.status);
        return;
      }
      const data = await res.json();
      const realItems = data.items || [];
      if (realItems.length === 0) {
        // Empty library → show bundled demo content so the page doesn't look bare.
        allItems = DEMO_ITEMS.slice();
        demoMode = true;
        console.log(`[Slidecast] Library empty — showing ${allItems.length} demo items`);
      } else {
        allItems = realItems;
        demoMode = false;
        console.log(`[Slidecast] Library loaded ${allItems.length} items`);
      }
      renderLibrary();
      updateStats();
      populatePhoneDeck();
      _updateDemoBanner();
    } catch (e) {
      console.error('Library fetch failed:', e);
      // Network error too → fall back to demo content so the page isn't blank.
      allItems = DEMO_ITEMS.slice();
      demoMode = true;
      renderLibrary();
      updateStats();
      populatePhoneDeck();
      _updateDemoBanner();
    }
  }

  function _updateDemoBanner() {
    const card = document.querySelector('.float-card-1 .fc-text');
    if (!card) return;
    if (demoMode) {
      card.innerHTML = 'Sample of what <em>you\'ll create</em>';
    } else {
      card.innerHTML = 'Real carousels from <em>your library</em>';
    }
  }

  function makeCard(it) {
    const c = document.createElement('div');
    c.className = 'lib-card' + (it.is_demo ? ' lib-card-demo' : '');
    const demoPill = it.is_demo
      ? `<span class="lib-demo-pill">Demo</span>`
      : '';
    c.innerHTML = `
      <div class="lib-thumb">
        <img src="${it.thumbnail}" loading="lazy" />
        <span class="lib-fmt">${it.format === 'compilation' ? 'Compilation' : 'Single'}</span>
        ${demoPill}
      </div>
      <div class="lib-meta">
        <div class="lib-title">${escapeHtml(it.title)}</div>
        <div class="lib-sub">${escapeHtml(it.subtitle || '')}</div>
      </div>
    `;
    c.addEventListener('click', async () => {
      if (it.is_demo) {
        showLibraryModal({
          format: it.format,
          slug: it.slug,
          title: it.title,
          subtitle: it.subtitle,
          slides: it.slides,
          caption: it.caption,
          is_demo: true,
        });
        return;
      }
      const res = await fetch(`/api/preview/${it.format}/${it.slug}`);
      if (!res.ok) return;
      const data = await res.json();
      showLibraryModal(data);
    });
    return c;
  }

  function renderLibrary() {
    const comps = allItems.filter((i) => i.format === 'compilation');
    const singles = allItems.filter((i) => i.format === 'single');
    countComp.textContent = `(${comps.length})`;
    countSingle.textContent = `(${singles.length})`;

    railComp.innerHTML = '';
    if (comps.length === 0) {
      railComp.innerHTML = `<div style="color: var(--ink-mute); padding: 30px 0;">No compilations yet — generate your first one above.</div>`;
    } else {
      comps.forEach((it) => railComp.appendChild(makeCard(it)));
    }

    railSingle.innerHTML = '';
    if (singles.length === 0) {
      railSingle.innerHTML = `<div style="color: var(--ink-mute); padding: 30px 0;">No single recipes yet — pick "Single Recipe" above and generate one.</div>`;
    } else {
      singles.forEach((it) => railSingle.appendChild(makeCard(it)));
    }
  }

  // Rail arrow buttons — scroll left/right by ~80% of the rail width
  $$('.rail-arrow').forEach((btn) => {
    btn.addEventListener('click', () => {
      const railId = btn.dataset.rail;
      const dir = parseInt(btn.dataset.dir, 10);
      const rail = document.querySelector(`#rail-${railId}`);
      if (!rail) return;
      rail.scrollBy({ left: dir * rail.clientWidth * 0.8, behavior: 'smooth' });
    });
  });

  // ---------- Animated counter ----------
  function animateCounter(el, target, duration = 1400) {
    const start = parseInt(el.textContent) || 0;
    const t0 = performance.now();
    function tick(now) {
      const p = Math.min(1, (now - t0) / duration);
      const eased = 1 - Math.pow(1 - p, 3);
      el.textContent = Math.round(start + (target - start) * eased);
      if (p < 1) requestAnimationFrame(tick);
    }
    requestAnimationFrame(tick);
  }

  function updateStats() {
    // Hero stats always show REAL library counts (demo items don't inflate them).
    const real = demoMode ? [] : allItems;
    const total = real.length;
    const single = real.filter((i) => i.format === 'single').length;
    const comp = real.filter((i) => i.format === 'compilation').length;
    animateCounter($('#stat-total'), total);
    animateCounter($('#stat-single'), single);
    animateCounter($('#stat-comp'), comp);
  }

  // ---------- Phone deck (real TikTok-style cycling) ----------
  // Picks a pool of up to 10 compilations and cycles through them: each
  // comp's slides play once, then we switch to a different comp. Gives the
  // hero a sense of "look at all the variety this thing makes."
  let deckInterval = null;
  let deckPool = [];
  let deckPoolIdx = 0;

  async function populatePhoneDeck() {
    const deck = $('#phone-deck');
    const progress = $('#tk-progress');
    const captionEl = $('#tk-caption');
    if (!deck || !progress) return;
    if (deckInterval) { clearInterval(deckInterval); deckInterval = null; }

    const comps = allItems.filter((i) => i.format === 'compilation');
    if (comps.length === 0) return;

    // Build a fresh shuffled pool (up to 10) and start at a random index.
    deckPool = comps.slice(0, 10).sort(() => Math.random() - 0.5);
    deckPoolIdx = Math.floor(Math.random() * deckPool.length);
    _loadNextComp();
  }

  async function _loadNextComp() {
    const deck = $('#phone-deck');
    const progress = $('#tk-progress');
    const captionEl = $('#tk-caption');
    if (!deck || !progress || deckPool.length === 0) return;

    const pick = deckPool[deckPoolIdx % deckPool.length];
    deckPoolIdx += 1;

    let slides = [];
    let title = pick.title;
    if (pick.is_demo) {
      slides = pick.slides || [];
    } else {
      try {
        const res = await fetch(`/api/preview/compilation/${pick.slug}`);
        if (res.ok) {
          const data = await res.json();
          slides = data.slides;
          title = data.title;
        }
      } catch (e) { console.warn(e); }
    }
    if (slides.length === 0) slides = [pick.thumbnail];

    captionEl.textContent = title;

    progress.innerHTML = '';
    slides.forEach(() => progress.appendChild(document.createElement('span')));
    const segs = progress.querySelectorAll('span');

    deck.innerHTML = '';
    slides.forEach((url, i) => {
      const img = document.createElement('img');
      img.src = url;
      img.loading = 'lazy';
      if (i === 0) img.classList.add('active');
      deck.appendChild(img);
    });
    if (segs[0]) segs[0].classList.add('active');

    let idx = 0;
    deckInterval = setInterval(() => {
      const imgs = deck.querySelectorAll('img');
      if (imgs.length === 0) return;
      imgs[idx].classList.remove('active');
      if (segs[idx]) { segs[idx].classList.remove('active'); segs[idx].classList.add('done'); }
      idx = (idx + 1) % imgs.length;
      if (idx === 0) {
        // Full cycle done. If we have variety in the pool, switch comps.
        if (deckPool.length > 1) {
          clearInterval(deckInterval);
          deckInterval = null;
          _loadNextComp();
          return;
        }
        segs.forEach((s) => s.classList.remove('done', 'active'));
      }
      imgs[idx].classList.add('active');
      if (segs[idx]) segs[idx].classList.add('active');
    }, 2400);
  }

  function showLibraryModal(data) {
    const slidesHtml = data.slides
      .map(
        (url, i) => `
      <div class="thumb" data-url="${url}">
        <span class="thumb-num">${String(i + 1).padStart(2, '0')}</span>
        <img src="${url}" loading="lazy" />
      </div>`,
      )
      .join('');
    modalBody.innerHTML = `
      <div class="modal-body">
        <div class="result-eyebrow">${data.format === 'compilation' ? 'Compilation · 12 slides' : 'Single recipe · 10 slides'}</div>
        <h3>${escapeHtml(data.title)}</h3>
        <p>${escapeHtml(data.subtitle || '')}</p>
        <div class="slides-grid">${slidesHtml}</div>
        <div class="caption-block">
          <h4>Caption</h4>
          <pre>${escapeHtml(data.caption)}</pre>
        </div>
        <div style="display: flex; gap: 10px; margin-top: 20px; align-items: center; flex-wrap: wrap;">
          <button class="btn-ghost" id="modal-copy">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1"/></svg>
            Copy caption
          </button>
          <span class="folder-tag">${data.format === 'single' ? 'output' : 'output_compilations'}/${data.slug}/slides/</span>
        </div>
      </div>
    `;
    modalBody.querySelectorAll('.thumb').forEach((t) => {
      t.addEventListener('click', () => openLightbox(t.dataset.url));
    });
    modalBody.querySelector('#modal-copy').addEventListener('click', async () => {
      await navigator.clipboard.writeText(data.caption);
      const b = modalBody.querySelector('#modal-copy');
      const original = b.innerHTML;
      b.innerHTML = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round"><path d="M5 12l5 5L20 7"/></svg> Copied`;
      setTimeout(() => (b.innerHTML = original), 1500);
    });
    modal.classList.remove('hidden');
  }

  modalClose.addEventListener('click', () => modal.classList.add('hidden'));
  modal.querySelector('.modal-backdrop').addEventListener('click', () =>
    modal.classList.add('hidden'),
  );
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      modal.classList.add('hidden');
      $$('.lightbox').forEach((lb) => lb.remove());
    }
  });

  function escapeHtml(s) {
    return String(s || '').replace(/[&<>"']/g, (c) =>
      ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]),
    );
  }

  // ---------- Template builder ----------
  let _allTemplates = [];
  let _currentTpl = null;
  let _uploadedLogoPath = null;

  async function loadTemplates() {
    try {
      const r = await fetch('/api/templates');
      if (!r.ok) return;
      const d = await r.json();
      _allTemplates = d.templates || [];
      renderTplGallery();
    } catch (e) { console.warn('templates load:', e); }
  }

  function renderTplGallery() {
    const g = $('#tpl-gallery');
    if (!g) return;
    g.innerHTML = '';
    _allTemplates.forEach((t) => {
      const card = document.createElement('button');
      card.className = 'tpl-card';
      card.innerHTML = `
        <span class="tpl-card-tag">${t.slide_count_min === t.slide_count_max ? t.slide_count_min : t.slide_count_min + '–' + t.slide_count_max} slides</span>
        <h3>${escapeHtml(t.name)}</h3>
        <p>${escapeHtml(t.description)}</p>
      `;
      card.addEventListener('mousemove', (e) => {
        const rect = card.getBoundingClientRect();
        card.style.setProperty('--mx', `${e.clientX - rect.left}px`);
        card.style.setProperty('--my', `${e.clientY - rect.top}px`);
      });
      card.addEventListener('click', () => pickTemplate(t));
      g.appendChild(card);
    });
  }

  function pickTemplate(t) {
    _currentTpl = t;
    document.querySelectorAll('.tpl-card').forEach((c, i) => {
      c.classList.toggle('selected', _allTemplates[i].id === t.id);
    });
    const b = $('#tpl-builder');
    b.classList.remove('hidden');
    $('#tpl-builder-title').textContent = t.name;
    $('#tpl-item-range').textContent = `(${t.slide_count_min}–${t.slide_count_max})`;
    $('#tpl-item-count').min = t.slide_count_min;
    $('#tpl-item-count').max = t.slide_count_max;
    $('#tpl-item-count').value = t.slide_count_default;
    // Render template-specific fields
    const fieldsEl = $('#tpl-fields');
    fieldsEl.innerHTML = '';
    (t.schema_fields || []).forEach((f) => {
      const row = document.createElement('div');
      row.className = 'tpl-row';
      let input;
      if (f.type === 'select') {
        input = `<select data-field="${f.key}">${(f.options || []).map((o) => `<option value="${o}"${o === f.default ? ' selected' : ''}>${o}</option>`).join('')}</select>`;
      } else {
        input = `<input data-field="${f.key}" type="text" placeholder="${escapeHtml(f.placeholder || '')}" />`;
      }
      row.innerHTML = `<label>${escapeHtml(f.label)}</label>${input}`;
      fieldsEl.appendChild(row);
    });
    b.scrollIntoView({ behavior: 'smooth', block: 'start' });
    updateCostEstimate();
  }

  function updateCostEstimate() {
    const count = parseInt($('#tpl-count').value, 10) || 1;
    const items = parseInt($('#tpl-item-count').value, 10) || 5;
    // Each carousel = ~items+2 slides, each slide ~1 Gemini image = $0.039
    const imgs = count * (items + 2);
    const text = count;  // 1 Gemini text call per carousel
    const imgCost = imgs * 0.039;
    $('#tpl-cost-est').textContent =
      `~${imgs} images + ${text} text calls · est. $${imgCost.toFixed(2)} (Gemini)`;
    $('#tpl-generate-count').textContent = count;
    $('#tpl-generate-plural').textContent = count === 1 ? '' : 's';
  }

  function bindBuilder() {
    const closeBtn = $('#tpl-builder-close');
    if (closeBtn) closeBtn.addEventListener('click', () => {
      $('#tpl-builder').classList.add('hidden');
      document.querySelectorAll('.tpl-card').forEach((c) => c.classList.remove('selected'));
      _currentTpl = null;
    });
    $('#tpl-count').addEventListener('input', updateCostEstimate);
    $('#tpl-item-count').addEventListener('input', updateCostEstimate);

    // Color picker syncs with hex input
    const colorEl = $('#tpl-brand-color');
    const hexEl = $('#tpl-brand-color-hex');
    colorEl.addEventListener('input', () => { hexEl.value = colorEl.value; });
    hexEl.addEventListener('input', () => {
      if (/^#[0-9a-fA-F]{6}$/.test(hexEl.value)) colorEl.value = hexEl.value;
    });

    // Logo upload
    $('#tpl-logo-file').addEventListener('change', async (e) => {
      const file = e.target.files[0];
      if (!file) return;
      const fd = new FormData();
      fd.append('file', file);
      const r = await fetch('/api/brand/logo', { method: 'POST', body: fd });
      if (!r.ok) { alert('Logo upload failed'); return; }
      const d = await r.json();
      _uploadedLogoPath = d.logo_path;
      $('#tpl-logo-preview').style.backgroundImage = `url('${d.logo_url}')`;
    });

    // Generate
    $('#tpl-generate').addEventListener('click', startTplGenerate);
  }

  async function startTplGenerate() {
    if (!_currentTpl) return;
    // Gather inputs
    const inputs = {};
    document.querySelectorAll('#tpl-fields [data-field]').forEach((el) => {
      inputs[el.dataset.field] = el.value || '';
    });
    const brand = {
      name: $('#tpl-brand-name').value || 'Your Brand',
      primary_color: $('#tpl-brand-color-hex').value || '#ff5c7a',
      cta_text: $('#tpl-brand-cta-text').value || 'Get the app',
      cta_url: $('#tpl-brand-cta-url').value || '',
      logo_path: _uploadedLogoPath || null,
    };
    const count = parseInt($('#tpl-count').value, 10) || 1;
    const item_count = parseInt($('#tpl-item-count').value, 10) || 5;

    const body = {
      template_id: _currentTpl.id,
      inputs, brand, count, item_count,
      batch_label: inputs.topic || inputs.app_name || _currentTpl.id,
    };

    $('#tpl-generate').disabled = true;
    $('#tpl-job').classList.remove('hidden');
    $('#tpl-job-title').textContent = 'Generating';
    $('#tpl-job-msg').textContent = 'Sending to Gemini…';
    $('#tpl-job-bar').style.width = '6%';

    let r;
    try {
      r = await fetch('/api/templates/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
    } catch (e) {
      $('#tpl-job-title').textContent = 'Failed';
      $('#tpl-job-msg').textContent = String(e);
      $('#tpl-generate').disabled = false;
      return;
    }
    if (!r.ok) {
      const t = await r.text();
      $('#tpl-job-title').textContent = 'Failed';
      $('#tpl-job-msg').textContent = `HTTP ${r.status}: ${t}`;
      $('#tpl-generate').disabled = false;
      return;
    }
    const d = await r.json();
    pollTplJob(d.job_id, count);
  }

  async function pollTplJob(jobId, expectedCount) {
    const t0 = Date.now();
    let progress = 8;
    while (true) {
      await new Promise((res) => setTimeout(res, 2000));
      progress = Math.min(progress + 4, 92);
      $('#tpl-job-bar').style.width = `${progress}%`;
      try {
        const r = await fetch(`/api/jobs/${jobId}`);
        if (!r.ok) break;
        const j = await r.json();
        $('#tpl-job-msg').textContent = j.message || j.status;
        if (j.status === 'done') {
          $('#tpl-job-bar').style.width = '100%';
          $('#tpl-job-title').textContent = 'Ready';
          await loadBatches();
          break;
        }
        if (j.status === 'failed') {
          $('#tpl-job-title').textContent = 'Failed';
          break;
        }
      } catch (e) { console.warn(e); }
      if (Date.now() - t0 > 15 * 60 * 1000) {
        $('#tpl-job-title').textContent = 'Timed out';
        break;
      }
    }
    $('#tpl-generate').disabled = false;
  }

  async function loadBatches() {
    try {
      const r = await fetch('/api/templates/batches');
      if (!r.ok) return;
      const d = await r.json();
      const grid = $('#tpl-batches');
      const list = d.batches || [];
      $('#tpl-batch-count').textContent = `(${list.length})`;
      grid.innerHTML = '';
      if (list.length === 0) {
        grid.innerHTML = `<div style="color: var(--ink-mute); padding: 30px; grid-column: 1/-1; text-align: center; border: 1px dashed var(--border); border-radius: 14px;">No batches yet — pick a template and hit Generate.</div>`;
        return;
      }
      list.forEach((b) => {
        const card = document.createElement('div');
        card.className = 'tpl-batch';
        const dt = new Date((b.created_at || 0) * 1000);
        card.innerHTML = `
          <div class="tpl-batch-thumb" style="${b.thumbnail ? `background-image:url('${b.thumbnail}')` : ''}"></div>
          <div class="tpl-batch-meta">
            <div class="tpl-batch-label">${escapeHtml(b.label || b.batch_id)}</div>
            <div class="tpl-batch-sub">${b.results_count}/${b.count} carousels · ${b.item_count} items · ${dt.toLocaleDateString()}</div>
            <a class="tpl-batch-dl" href="/api/templates/batch/${encodeURIComponent(b.batch_id)}/download" target="_blank">Download ZIP ↓</a>
          </div>
        `;
        grid.appendChild(card);
      });
    } catch (e) { console.warn('batches:', e); }
  }

  // ---------- Tracking ----------
  const tkLabel = $('#tk-label');
  const tkConnectBtn = $('#tk-connect-btn');
  const tkRefreshBtn = $('#tracking-refresh');
  const tkCredsWarn = $('#tk-creds-warn');

  function fmtN(n) {
    n = Number(n || 0);
    if (n >= 1_000_000) return (n / 1_000_000).toFixed(n >= 10_000_000 ? 0 : 1) + 'M';
    if (n >= 1_000) return (n / 1_000).toFixed(n >= 10_000 ? 0 : 1) + 'K';
    return String(n);
  }

  async function loadTrackingStatus() {
    try {
      const r = await fetch('/api/tracking/status');
      if (!r.ok) return;
      const s = await r.json();
      if (!s.credentials_configured) {
        tkCredsWarn.classList.add('show');
        tkCredsWarn.innerHTML = `<strong>Setup needed.</strong> Add <code>TIKTOK_CLIENT_KEY</code> and <code>TIKTOK_CLIENT_SECRET</code> to your <code>.env</code> file, then restart the server. See <code>webapp/tracking/README.md</code> for the dev-app setup steps.`;
        tkConnectBtn.disabled = true;
      } else {
        tkCredsWarn.classList.remove('show');
        tkConnectBtn.disabled = false;
      }
    } catch (e) { console.warn('tracking status:', e); }
  }

  async function loadTrackingSummary() {
    try {
      const r = await fetch('/api/tracking/summary');
      if (!r.ok) return;
      const d = await r.json();
      $('#tk-total-plays').textContent = fmtN(d.totals.plays);
      $('#tk-total-likes').textContent = fmtN(d.totals.likes);
      $('#tk-total-comments').textContent = fmtN(d.totals.comments);
      $('#tk-total-shares').textContent = fmtN(d.totals.shares);
      $('#tk-total-followers').textContent = fmtN(d.totals.followers);
      $('#tk-snap-info').textContent = d.snapshot_date
        ? `Latest snapshot: ${d.snapshot_date} · ${(d.per_account || []).length} account(s)`
        : 'No snapshot yet — connect at least one account and click "Refresh snapshot".';

      // Accounts leaderboard
      const accts = d.per_account || [];
      $('#tk-acct-count').textContent = `(${accts.length})`;
      const accountsEl = $('#tk-accounts');
      accountsEl.innerHTML = '';
      if (accts.length === 0) {
        accountsEl.innerHTML = `<div style="color: var(--ink-mute); padding: 24px; text-align: center; border: 1px dashed var(--border); border-radius: 12px;">No accounts connected yet.</div>`;
      } else {
        accts.forEach((a) => {
          const initials = (a.display_name || a.label || '?').slice(0, 2).toUpperCase();
          const el = document.createElement('div');
          el.className = 'tk-acct';
          el.innerHTML = `
            <div class="tk-acct-avatar">${escapeHtml(initials)}</div>
            <div class="tk-acct-meta">
              <div class="name">${escapeHtml(a.display_name || a.label)}</div>
              <div class="sub">${escapeHtml(a.label)} · ${fmtN(a.follower_count)} followers · ${a.video_count} videos</div>
            </div>
            <div style="text-align: right;">
              <div class="tk-acct-num">${fmtN(a.plays)}</div>
              <div class="tk-acct-num-label">plays</div>
            </div>
            <button class="tk-acct-del" title="Disconnect" data-label="${escapeHtml(a.label)}">×</button>
          `;
          accountsEl.appendChild(el);
        });
        accountsEl.querySelectorAll('.tk-acct-del').forEach((btn) => {
          btn.addEventListener('click', async (e) => {
            e.stopPropagation();
            const label = btn.dataset.label;
            if (!confirm(`Disconnect ${label}?`)) return;
            await fetch(`/api/tracking/accounts/${encodeURIComponent(label)}`, { method: 'DELETE' });
            loadTrackingSummary();
          });
        });
      }

      // Top posts
      const posts = d.top_posts || [];
      const postsEl = $('#tk-top-posts');
      postsEl.innerHTML = '';
      if (posts.length === 0) {
        postsEl.innerHTML = `<div style="color: var(--ink-mute); padding: 24px; text-align: center; border: 1px dashed var(--border); border-radius: 12px;">Post-level metrics will appear after the first refresh.</div>`;
      } else {
        posts.forEach((p) => {
          const a = document.createElement('a');
          a.className = 'tk-post';
          a.href = p.share_url || '#';
          a.target = '_blank';
          a.rel = 'noopener noreferrer';
          a.innerHTML = `
            <div class="tk-post-thumb" style="${p.cover_image_url ? `background-image:url('${p.cover_image_url}')` : ''}"></div>
            <div class="tk-post-meta">
              <div class="label">${escapeHtml(p.label)}</div>
              <div class="title">${escapeHtml(p.title || '(no title)')}</div>
            </div>
            <div>
              <div class="tk-post-num">${fmtN(p.view_count)}</div>
              <div class="tk-post-num-label">plays</div>
            </div>
          `;
          postsEl.appendChild(a);
        });
      }
    } catch (e) { console.warn('tracking summary:', e); }
  }

  if (tkConnectBtn) {
    tkConnectBtn.addEventListener('click', () => {
      const label = (tkLabel.value || '').trim();
      if (!label) { tkLabel.focus(); return; }
      window.location.href = `/auth/tiktok/start?label=${encodeURIComponent(label)}`;
    });
  }
  if (tkRefreshBtn) {
    tkRefreshBtn.addEventListener('click', async () => {
      tkRefreshBtn.disabled = true;
      tkRefreshBtn.innerHTML = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round"><path d="M21 12a9 9 0 11-3-6.7L21 8M21 3v5h-5"/></svg> Fetching…`;
      try {
        await fetch('/api/tracking/refresh', { method: 'POST' });
        // Poll for results — fetch usually finishes in 5-15s per account
        await new Promise((r) => setTimeout(r, 5000));
        await loadTrackingSummary();
      } finally {
        tkRefreshBtn.disabled = false;
        tkRefreshBtn.innerHTML = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round"><path d="M21 12a9 9 0 11-3-6.7L21 8M21 3v5h-5"/></svg> Refresh snapshot`;
      }
    });
  }

  // ---------- Apply branding (from /api/branding) ----------
  async function applyBranding() {
    try {
      const res = await fetch('/api/branding');
      if (!res.ok) return;
      const cfg = await res.json();

      // Replace any element with data-brand="<key>" — set as text
      $$('[data-brand]').forEach((el) => {
        const k = el.dataset.brand;
        if (cfg[k] != null) el.textContent = cfg[k];
      });
      // Replace any element with data-brand-html="<key>" — set as innerHTML
      $$('[data-brand-html]').forEach((el) => {
        const k = el.dataset.brandHtml;
        if (cfg[k] != null) el.innerHTML = cfg[k];
      });

      // Apply colors via CSS vars (only if values look like valid hex)
      const isHex = (v) => typeof v === 'string' && /^#([0-9a-f]{3,8})$/i.test(v);
      if (isHex(cfg.primary_color)) {
        document.documentElement.style.setProperty('--coral', cfg.primary_color);
      }
      if (isHex(cfg.secondary_color)) {
        document.documentElement.style.setProperty('--gold', cfg.secondary_color);
      }

      // Update <title> too
      if (cfg.brand_name) {
        document.title = `${cfg.brand_name} ${cfg.studio_name || 'Studio'} — Generate carousels & auto-post to every account`;
      }
    } catch (e) {
      console.warn('branding fetch failed:', e);
    }
  }

  // =========================================================================
  // PAYWALL FLOW (mock — replace with real auth/Stripe in parallel codebase)
  // localStorage-backed state machine driving signup → checkout → paid UI.
  // =========================================================================
  const STATE_KEY = 'slidecast.state.v1';
  const TIER_QUOTA = {
    anon:  { max: 1,  cap: 'lifetime' },
    free:  { max: 3,  cap: 'lifetime' },
    basic: { max: 10, cap: 'monthly'  },
    pro:   { max: 30, cap: 'monthly'  },
  };
  const PRICE = { basic: 20.99, pro: 69.99 };

  function getState() {
    try { return JSON.parse(localStorage.getItem(STATE_KEY)) || { user: null }; }
    catch (e) { return { user: null }; }
  }
  function setState(updater) {
    const cur = getState();
    const next = typeof updater === 'function' ? updater(cur) : { ...cur, ...updater };
    localStorage.setItem(STATE_KEY, JSON.stringify(next));
    applyStateToUI();
    return next;
  }
  function getTier() {
    const s = getState();
    if (!s.user) return 'anon';
    return s.user.tier || 'free';
  }
  function quotaInfo() {
    const tier = getTier();
    const used = getState().user?.gensUsed || 0;
    const max = TIER_QUOTA[tier].max;
    return { tier, used, max, remaining: Math.max(0, max - used), cap: TIER_QUOTA[tier].cap, isPaid: tier === 'basic' || tier === 'pro' };
  }

  function applyStateToUI() {
    const q = quotaInfo();
    const state = getState();
    const qtyInput = document.getElementById('gen-qty');
    const genLabel = document.getElementById('generate-btn-label');
    const genBtnEl = document.getElementById('generate-btn');
    const qtyNote = document.getElementById('qty-note');
    const planBadge = document.getElementById('studio-plan-badge');

    // Plan badge
    if (planBadge) {
      const brand = state.user?.brand;
      const brandLine = brand?.name ? ` · Brand: <em>${escapeHtml(brand.name)}</em>` : '';
      const postizLine = state.user?.postizConnected ? ' · Postiz ✓' : '';
      if (q.tier === 'anon') {
        planBadge.innerHTML = `<span class="plan-badge-dot"></span> <strong>Free preview</strong> · 1 carousel, no signup needed`;
      } else if (q.tier === 'free') {
        planBadge.innerHTML = `<span class="plan-badge-dot"></span> <strong>Free</strong> · ${q.remaining} of ${q.max} generations left${brandLine}`;
      } else {
        const tierName = q.tier === 'pro' ? 'Pro' : 'Basic';
        planBadge.innerHTML = `<span class="plan-badge-dot plan-badge-dot-paid"></span> <strong>${tierName}</strong> · ${q.remaining} of ${q.max} this month${brandLine}${postizLine}`;
      }
    }

    // Qty slider max + label
    if (qtyInput) {
      const maxAllowed = q.tier === 'anon' ? 1 : Math.max(1, q.remaining || 1);
      qtyInput.max = maxAllowed;
      let v = parseInt(qtyInput.value, 10) || 1;
      if (v > maxAllowed) { v = maxAllowed; qtyInput.value = v; }
      if (v < 1) { v = 1; qtyInput.value = v; }
    }
    const qty = parseInt(qtyInput?.value, 10) || 1;

    // Generate button label + intent
    if (genLabel && genBtnEl) {
      genBtnEl.disabled = false;
      if (q.tier === 'anon' && qty > 1) {
        genLabel.textContent = `Sign up free to generate ${qty}`;
        genBtnEl.dataset.action = 'signup';
      } else if (q.remaining <= 0) {
        genLabel.textContent = q.isPaid ? 'Out of generations this month' : 'Upgrade to keep going';
        genBtnEl.dataset.action = q.isPaid ? 'wait' : 'upgrade';
      } else {
        genLabel.textContent = `Generate ${qty} carousel${qty > 1 ? 's' : ''}`;
        genBtnEl.dataset.action = 'generate';
      }
    }

    // Qty note
    if (qtyNote) {
      if (q.tier === 'anon') {
        qtyNote.innerHTML = `First carousel <strong>free</strong> · sign up for 3 more`;
      } else if (q.tier === 'free') {
        qtyNote.innerHTML = q.remaining > 0
          ? `<strong>${q.remaining}</strong> of ${q.max} free generations left · then upgrade to keep going`
          : `Out of free generations — <strong>upgrade</strong> below to keep going`;
      } else {
        qtyNote.innerHTML = `<strong>${q.remaining}</strong> of ${q.max} generations this month · refills monthly`;
      }
    }

    // Result panel CTAs adapt to state
    refreshResultCtas();
    refreshUploadCtas();
  }

  function refreshResultCtas() {
    const q = quotaInfo();
    const downloadBtn = document.getElementById('result-download');
    const postBtn = document.getElementById('result-post');
    const note = document.getElementById('result-paywall-note');
    if (!downloadBtn || !postBtn || !note) return;

    if (q.tier === 'anon') {
      downloadBtn.disabled = true;
      postBtn.disabled = true;
      note.classList.remove('hidden');
      note.innerHTML = `<strong>Free preview only.</strong> <a href="#" data-trigger="signup">Sign up free</a> to download · upgrade to post to your accounts.`;
    } else if (q.tier === 'free') {
      downloadBtn.disabled = false;
      postBtn.disabled = true;
      note.classList.remove('hidden');
      note.innerHTML = `Final slide shows the Slidecast CTA. <a href="#" data-trigger="pricing">Upgrade</a> to use your own brand + auto-post.`;
    } else {
      const state = getState();
      downloadBtn.disabled = false;
      postBtn.disabled = !state.user?.postizConnected;
      if (!state.user?.postizConnected) {
        note.classList.remove('hidden');
        note.innerHTML = `<a href="#" data-trigger="postiz">Connect your Postiz API key</a> to auto-post — download works without it.`;
      } else {
        note.classList.add('hidden');
      }
    }
  }

  function refreshUploadCtas() {
    const q = quotaInfo();
    const downloadBtn = document.getElementById('upload-download');
    const postBtn = document.getElementById('upload-post');
    const note = document.getElementById('upload-paywall-note');
    if (!downloadBtn || !postBtn) return;

    const hasFiles = (uploadState.files || []).length > 0;
    if (q.tier === 'anon' || q.tier === 'free') {
      downloadBtn.disabled = true;
      postBtn.disabled = true;
      if (note) {
        note.classList.remove('hidden');
        note.innerHTML = q.tier === 'anon'
          ? `<a href="#" data-trigger="signup">Sign up</a> + upgrade to use upload-and-post.`
          : `<a href="#" data-trigger="pricing">Upgrade</a> to upload your own slides and auto-post.`;
      }
    } else {
      downloadBtn.disabled = !hasFiles;
      postBtn.disabled = !hasFiles || !getState().user?.postizConnected;
      if (note) note.classList.add('hidden');
    }
  }

  // ---- Modal helpers ----
  function openPaywall(id) {
    const el = document.getElementById(id);
    if (!el) return;
    el.classList.remove('hidden');
    document.body.classList.add('paywall-open');
  }
  function closePaywall(id) {
    const el = document.getElementById(id);
    if (!el) return;
    el.classList.add('hidden');
    if (!document.querySelector('.paywall-modal:not(.hidden)')) {
      document.body.classList.remove('paywall-open');
    }
  }
  document.querySelectorAll('[data-close]').forEach((el) => {
    el.addEventListener('click', () => closePaywall(el.dataset.close));
  });

  // ---- Mock signup ----
  function mockSignup(email, method) {
    setState({
      user: {
        email: email || 'demo@slidecast.app',
        method: method || 'google',
        tier: 'free',
        gensUsed: 0,
        brand: null,
        postizKey: null,
        postizConnected: false,
      },
    });
    closePaywall('signup-modal');
    showToast(`Signed in as ${email || 'demo@slidecast.app'} · 3 free generations unlocked`);
  }
  document.getElementById('signup-google')?.addEventListener('click', () => mockSignup(null, 'google'));
  document.getElementById('signup-magic')?.addEventListener('click', () => {
    const v = document.getElementById('signup-email')?.value;
    mockSignup(v || 'demo@slidecast.app', 'magic');
  });

  // ---- Mock checkout ----
  let pendingTier = null;
  function openCheckout(tier) {
    pendingTier = tier;
    const title = tier === 'pro' ? 'Pro · $69.99/mo' : 'Basic · $20.99/mo';
    document.getElementById('checkout-plan-title').textContent = title;
    document.getElementById('checkout-pay-amount').textContent = `$${PRICE[tier]}`;
    const summary = tier === 'pro'
      ? `<ul><li>30 carousels per month</li><li>30 connected accounts</li><li>Brand kit + your own CTA on every slide</li><li>Auto-post via your Postiz key</li><li>Analytics dashboard + scheduling</li><li>Priority generation queue</li></ul>`
      : `<ul><li>10 carousels per month</li><li>10 connected accounts</li><li>Brand kit + your own CTA on every slide</li><li>Auto-post via your Postiz key</li><li>Upload + post your own slides</li></ul>`;
    document.getElementById('checkout-summary').innerHTML = summary;
    openPaywall('checkout-modal');
  }
  document.getElementById('checkout-pay')?.addEventListener('click', () => {
    if (!pendingTier) return;
    const ensureUser = (s) => s.user || { email: 'demo@slidecast.app', method: 'auto', brand: null, postizKey: null, postizConnected: false };
    setState((s) => ({
      ...s,
      user: { ...ensureUser(s), tier: pendingTier, gensUsed: 0 },
    }));
    closePaywall('checkout-modal');
    showToast(`Welcome to ${pendingTier === 'pro' ? 'Pro' : 'Basic'} — let's set up your brand`);
    setTimeout(() => openOnboarding(), 400);
  });

  // Pricing CTAs
  document.querySelectorAll('[data-cta]').forEach((btn) => {
    btn.addEventListener('click', () => {
      const cta = btn.dataset.cta;
      if (cta === 'get-started') {
        document.getElementById('generator')?.scrollIntoView({ behavior: 'smooth' });
      } else if (cta === 'upgrade-basic' || cta === 'upgrade-pro') {
        const tier = cta === 'upgrade-pro' ? 'pro' : 'basic';
        if (getTier() === 'anon') {
          openPaywall('signup-modal');
        } else {
          openCheckout(tier);
        }
      }
    });
  });

  // Trigger links inside paywall notes
  document.body.addEventListener('click', (e) => {
    const trig = e.target.closest('[data-trigger]');
    if (!trig) return;
    e.preventDefault();
    const t = trig.dataset.trigger;
    if (t === 'signup') openPaywall('signup-modal');
    else if (t === 'pricing') document.getElementById('pricing')?.scrollIntoView({ behavior: 'smooth' });
    else if (t === 'postiz') openOnboarding(3);
  });

  // ---- Onboarding modal (3 steps) ----
  let onboardStep = 1;
  function openOnboarding(step = 1) {
    onboardStep = step;
    showOnboardStep(onboardStep);
    openPaywall('onboard-modal');
  }
  function showOnboardStep(n) {
    document.querySelectorAll('.onboard-step').forEach((el) => {
      el.classList.toggle('active', parseInt(el.dataset.step, 10) === n);
      el.classList.toggle('done', parseInt(el.dataset.step, 10) < n);
    });
    document.querySelectorAll('.onboard-page').forEach((el) => {
      el.classList.toggle('hidden', parseInt(el.dataset.page, 10) !== n);
    });
    const backBtn = document.getElementById('onboard-back');
    const nextBtn = document.getElementById('onboard-next');
    if (backBtn) backBtn.style.visibility = n === 1 ? 'hidden' : 'visible';
    if (nextBtn) nextBtn.textContent = n === 3 ? 'Finish setup' : 'Next →';
  }
  document.getElementById('onboard-next')?.addEventListener('click', () => {
    if (onboardStep < 3) { onboardStep++; showOnboardStep(onboardStep); }
    else { saveOnboardingState(); closePaywall('onboard-modal'); showToast('Brand kit saved · ready to generate'); }
  });
  document.getElementById('onboard-back')?.addEventListener('click', () => {
    if (onboardStep > 1) { onboardStep--; showOnboardStep(onboardStep); }
  });
  document.getElementById('onboard-skip')?.addEventListener('click', () => {
    saveOnboardingState();
    closePaywall('onboard-modal');
  });
  function saveOnboardingState() {
    const brandName = document.getElementById('onboard-brand-name')?.value || '';
    const brandColor = document.getElementById('onboard-brand-color')?.value || '';
    const brandCta = document.getElementById('onboard-brand-cta')?.value || '';
    const postizKey = document.getElementById('onboard-postiz-key')?.value || '';
    setState((s) => ({
      ...s,
      user: {
        ...s.user,
        brand: {
          ...(s.user?.brand || {}),
          name: brandName || s.user?.brand?.name || '',
          color: brandColor || s.user?.brand?.color || '#ff5c7a',
          cta: brandCta || s.user?.brand?.cta || '',
        },
        postizKey: postizKey || s.user?.postizKey || '',
        postizConnected: !!postizKey || !!s.user?.postizConnected,
      },
    }));
  }
  // Brand image dropzone
  document.getElementById('onboard-brand-dropzone')?.addEventListener('click', () => {
    document.getElementById('onboard-brand-file')?.click();
  });
  document.getElementById('onboard-brand-file')?.addEventListener('change', (e) => {
    const f = e.target.files?.[0];
    if (!f) return;
    const reader = new FileReader();
    reader.onload = (ev) => {
      const preview = document.getElementById('onboard-brand-preview');
      if (preview) preview.innerHTML = `<img src="${ev.target.result}" alt="brand"/>`;
      setState((s) => ({
        ...s,
        user: { ...s.user, brand: { ...(s.user?.brand || {}), imageDataUrl: ev.target.result } },
      }));
    };
    reader.readAsDataURL(f);
  });
  // Color sync
  document.getElementById('onboard-brand-color')?.addEventListener('input', (e) => {
    const hex = document.getElementById('onboard-brand-color-hex');
    if (hex) hex.value = e.target.value;
  });
  document.getElementById('onboard-brand-color-hex')?.addEventListener('input', (e) => {
    const c = e.target.value;
    if (/^#[0-9a-f]{6}$/i.test(c)) {
      const picker = document.getElementById('onboard-brand-color');
      if (picker) picker.value = c;
    }
  });
  // Postiz test (mock)
  document.getElementById('onboard-postiz-test')?.addEventListener('click', (e) => {
    const btn = e.currentTarget;
    const key = document.getElementById('onboard-postiz-key')?.value;
    if (!key) { showToast('Paste a key first'); return; }
    btn.textContent = 'Testing…';
    btn.disabled = true;
    setTimeout(() => {
      btn.textContent = '✓ Connected · 5 accounts found';
      btn.disabled = false;
    }, 800);
  });

  // ---- Mode picker (Generate / Upload) ----
  document.querySelectorAll('.studio-mode').forEach((btn) => {
    btn.addEventListener('click', () => {
      const mode = btn.dataset.mode;
      document.querySelectorAll('.studio-mode').forEach((b) => b.classList.toggle('active', b === btn));
      document.getElementById('studio-generate')?.classList.toggle('hidden', mode !== 'generate');
      document.getElementById('studio-upload')?.classList.toggle('hidden', mode !== 'upload');
    });
  });

  // ---- Qty controls ----
  document.querySelectorAll('.qty-step').forEach((btn) => {
    btn.addEventListener('click', () => {
      const step = parseInt(btn.dataset.step, 10);
      const input = document.getElementById('gen-qty');
      const next = (parseInt(input.value, 10) || 1) + step;
      const max = parseInt(input.max, 10) || 1;
      input.value = Math.max(1, Math.min(max, next));
      applyStateToUI();
    });
  });
  document.getElementById('gen-qty')?.addEventListener('input', applyStateToUI);

  // ---- Paywall gate on Generate button (capture phase, runs before existing handler) ----
  // The click only GATES — it never consumes quota. Quota is decremented in the
  // result-panel MutationObserver below, AFTER a generation actually completes
  // and renders. This way the user sees the preview before any paywall change.
  document.getElementById('generate-btn')?.addEventListener('click', (e) => {
    const action = e.currentTarget.dataset.action;
    if (action === 'signup') {
      e.stopImmediatePropagation();
      e.preventDefault();
      openPaywall('signup-modal');
      return;
    }
    if (action === 'upgrade') {
      e.stopImmediatePropagation();
      e.preventDefault();
      document.getElementById('pricing')?.scrollIntoView({ behavior: 'smooth' });
      return;
    }
    if (action === 'wait') {
      e.stopImmediatePropagation();
      e.preventDefault();
      showToast(`You're out of generations this month. Refills on your billing cycle.`);
      return;
    }
    // action === 'generate' — let propagation continue. The existing
    // startGeneration() handler will run, the spinner will show, and once the
    // result-panel transitions hidden→visible the MutationObserver below will
    // decrement quota and update the paywall UI.
  }, { capture: true });

  // Force "anon used" check into quotaInfo
  const _origQuotaInfo = quotaInfo;
  function _tierOverride() {
    const s = getState();
    if (!s.user && localStorage.getItem('slidecast.anonUsed') === '1') {
      // Pretend used=1, max=1 → remaining=0
      return { tier: 'anon', used: 1, max: 1, remaining: 0, cap: 'lifetime', isPaid: false };
    }
    return _origQuotaInfo();
  }
  // Re-wire to use override
  // (just shadow it in scope)
  // eslint-disable-next-line no-func-assign
  // quotaInfo = _tierOverride; — JS const so we use a helper below
  function effectiveQuota() { return _tierOverride(); }
  // Re-bind applyStateToUI to use effectiveQuota
  function applyStateToUI2() {
    const q = effectiveQuota();
    const state = getState();
    const qtyInput = document.getElementById('gen-qty');
    const genBtnEl = document.getElementById('generate-btn');
    // The existing generation flow clobbers genBtnEl.innerHTML; rebuild our
    // structured label+arrow once each render so we don't lose the hook.
    if (genBtnEl && !document.getElementById('generate-btn-label')) {
      genBtnEl.innerHTML = '<span id="generate-btn-label">Generate</span> <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><path d="M5 12h14M13 5l7 7-7 7"/></svg>';
    }
    const genLabel = document.getElementById('generate-btn-label');
    const qtyNote = document.getElementById('qty-note');
    const planBadge = document.getElementById('studio-plan-badge');

    if (planBadge) {
      const brand = state.user?.brand;
      const brandLine = brand?.name ? ` · Brand: <em>${escapeHtml(brand.name)}</em>` : '';
      const postizLine = state.user?.postizConnected ? ' · Postiz ✓' : '';
      if (q.tier === 'anon') {
        if (q.remaining === 0) {
          planBadge.innerHTML = `<span class="plan-badge-dot"></span> <strong>Free preview used</strong> · <a href="#" data-trigger="signup">Sign up</a> for 3 more`;
        } else {
          planBadge.innerHTML = `<span class="plan-badge-dot"></span> <strong>Free preview</strong> · 1 carousel, no signup needed`;
        }
      } else if (q.tier === 'free') {
        planBadge.innerHTML = `<span class="plan-badge-dot"></span> <strong>Free</strong> · ${q.remaining} of ${q.max} generations left${brandLine}`;
      } else {
        const tierName = q.tier === 'pro' ? 'Pro' : 'Basic';
        planBadge.innerHTML = `<span class="plan-badge-dot plan-badge-dot-paid"></span> <strong>${tierName}</strong> · ${q.remaining} of ${q.max} this month${brandLine}${postizLine}`;
      }
    }

    if (qtyInput) {
      const maxAllowed = q.tier === 'anon' ? 1 : Math.max(1, q.remaining || 1);
      qtyInput.max = maxAllowed;
      let v = parseInt(qtyInput.value, 10) || 1;
      if (v > maxAllowed) { v = maxAllowed; qtyInput.value = v; }
      if (v < 1) { v = 1; qtyInput.value = v; }
    }
    const qty = parseInt(qtyInput?.value, 10) || 1;

    if (genLabel && genBtnEl) {
      genBtnEl.disabled = false;
      if (q.tier === 'anon' && qty > 1) {
        genLabel.textContent = `Sign up free to generate ${qty}`;
        genBtnEl.dataset.action = 'signup';
      } else if (q.remaining <= 0) {
        genLabel.textContent = q.isPaid ? 'Out of generations this month' : 'Upgrade to keep going';
        genBtnEl.dataset.action = q.isPaid ? 'wait' : 'upgrade';
      } else {
        genLabel.textContent = `Generate ${qty} carousel${qty > 1 ? 's' : ''}`;
        genBtnEl.dataset.action = 'generate';
      }
    }

    if (qtyNote) {
      if (q.tier === 'anon') {
        qtyNote.innerHTML = q.remaining === 0
          ? `Free preview used. <a href="#" data-trigger="signup">Sign up free</a> for 3 more.`
          : `First carousel <strong>free</strong> · sign up for 3 more`;
      } else if (q.tier === 'free') {
        qtyNote.innerHTML = q.remaining > 0
          ? `<strong>${q.remaining}</strong> of ${q.max} free generations left · then upgrade to keep going`
          : `Out of free generations — <strong>upgrade</strong> below to keep going`;
      } else {
        qtyNote.innerHTML = `<strong>${q.remaining}</strong> of ${q.max} generations this month · refills monthly`;
      }
    }
    refreshResultCtas();
    refreshUploadCtas();
  }
  // Override
  window._applyStateToUI = applyStateToUI2;
  applyStateToUI = applyStateToUI2;  // shadows the earlier const since this scope is fresh

  // ---- Result panel observer: decrement quota AFTER a successful generation ----
  // Every time #result-panel transitions hidden → visible we know one full
  // generation cycle just completed. That's when we charge the user a "use"
  // against their quota (anon flag, or gensUsed++ for signed-in tiers).
  const resultPanelEl = document.getElementById('result-panel');
  if (resultPanelEl) {
    let wasHidden = resultPanelEl.classList.contains('hidden');
    new MutationObserver(() => {
      const isHidden = resultPanelEl.classList.contains('hidden');
      if (wasHidden && !isHidden) {
        // Generation just finished. Decrement quota, mark anon-used if applicable.
        setState((s) => ({
          ...s,
          user: s.user ? { ...s.user, gensUsed: (s.user.gensUsed || 0) + 1 } : s.user,
        }));
        if (!getState().user) {
          localStorage.setItem('slidecast.anonUsed', '1');
        }
        applyStateToUI();
      }
      wasHidden = isHidden;
    }).observe(resultPanelEl, { attributes: true, attributeFilter: ['class'] });
  }

  // ---- Result-panel buttons ----
  document.getElementById('result-download')?.addEventListener('click', () => {
    showToast('Mock download — ZIP would save to your Downloads folder');
  });
  document.getElementById('result-post')?.addEventListener('click', () => openPostModal());

  // ---- Upload mode (BYO slides) ----
  const uploadState = { files: [], previews: [] };
  const upDrop = document.getElementById('upload-dropzone');
  const upInput = document.getElementById('upload-files');
  const upPreview = document.getElementById('upload-preview');
  upDrop?.addEventListener('click', () => upInput?.click());
  upDrop?.addEventListener('dragover', (e) => { e.preventDefault(); upDrop.classList.add('drag'); });
  upDrop?.addEventListener('dragleave', () => upDrop.classList.remove('drag'));
  upDrop?.addEventListener('drop', (e) => {
    e.preventDefault();
    upDrop.classList.remove('drag');
    handleUploadFiles(e.dataTransfer.files);
  });
  upInput?.addEventListener('change', (e) => handleUploadFiles(e.target.files));
  function handleUploadFiles(fileList) {
    const arr = Array.from(fileList || []).filter((f) => f.type.startsWith('image/'));
    uploadState.files = arr;
    if (upPreview) {
      upPreview.classList.toggle('hidden', arr.length === 0);
      upPreview.innerHTML = '';
      arr.forEach((f, i) => {
        const url = URL.createObjectURL(f);
        const div = document.createElement('div');
        div.className = 'upload-thumb';
        div.innerHTML = `<img src="${url}" alt="slide ${i+1}"/><span>${String(i+1).padStart(2,'0')}</span>`;
        upPreview.appendChild(div);
      });
    }
    refreshUploadCtas();
  }
  document.getElementById('upload-download')?.addEventListener('click', () => {
    showToast(`Mock download — ${uploadState.files.length} slide${uploadState.files.length === 1 ? '' : 's'} would zip locally`);
  });
  document.getElementById('upload-post')?.addEventListener('click', () => openPostModal());

  // ---- Post-to-accounts modal (mock) ----
  const MOCK_ACCOUNTS = [
    '@nutrilens.ai', '@myrecipefolder', '@recipediahealthy',
    '@recipehackswithsusan', '@thekitchenfolder', '@cookwithlibby',
    '@dailyfoodfeed', '@hungrycollegekid',
  ];
  function openPostModal() {
    const tier = getTier();
    if (tier === 'anon' || tier === 'free') {
      document.getElementById('pricing')?.scrollIntoView({ behavior: 'smooth' });
      showToast('Posting unlocks with Basic or Pro');
      return;
    }
    if (!getState().user?.postizConnected) {
      openOnboarding(3);
      return;
    }
    const maxAccounts = tier === 'pro' ? 30 : 10;
    const acctList = document.getElementById('post-accounts');
    if (acctList) {
      acctList.innerHTML = MOCK_ACCOUNTS.slice(0, Math.min(MOCK_ACCOUNTS.length, maxAccounts)).map((a, i) => `
        <label class="post-account">
          <input type="checkbox" ${i < 5 ? 'checked' : ''} />
          <span>${a}</span>
        </label>`).join('');
    }
    openPaywall('post-modal');
  }
  document.getElementById('post-confirm')?.addEventListener('click', () => {
    const n = document.querySelectorAll('#post-accounts input:checked').length;
    closePaywall('post-modal');
    showToast(`Mock posted to ${n} account${n === 1 ? '' : 's'} via Postiz`);
  });

  // ---- Debug reset button ----
  document.getElementById('state-reset-btn')?.addEventListener('click', () => {
    if (!confirm('Reset paywall state? This clears localStorage so you can test the flow from anon again.')) return;
    localStorage.removeItem(STATE_KEY);
    localStorage.removeItem('slidecast.anonUsed');
    applyStateToUI();
    showToast('Paywall state reset — back to anon');
  });

  // ---- Toast ----
  function showToast(msg) {
    let t = document.getElementById('slidecast-toast');
    if (!t) {
      t = document.createElement('div');
      t.id = 'slidecast-toast';
      t.className = 'slidecast-toast';
      document.body.appendChild(t);
    }
    t.textContent = msg;
    t.classList.add('show');
    clearTimeout(showToast._timer);
    showToast._timer = setTimeout(() => t.classList.remove('show'), 2800);
  }

  // ---------- Initial load ----------
  applyBranding();
  refreshLibrary();
  // Tracking section is hidden right now — only load if the DOM is present
  if (document.getElementById('tk-totals')) {
    loadTrackingStatus();
  }
  loadTrackingSummary();
  loadTemplates();
  loadBatches();
  bindBuilder();
  applyStateToUI();  // paywall state on first paint
})();
