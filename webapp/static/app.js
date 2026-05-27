// RecipeVault Studio — frontend
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
  const openFolderEl  = $('#open-folder');
  const downloadZipEl = $('#download-zip');
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

  // ---------- Prompt dialog wiring ----------
  // Format selector lives in two places: the rich cards (.fmt-card) above and
  // the compact dropdown (#prompt-format) inside the new dialog. Both write to
  // `selectedFmt` and both stay visually in sync via setFormat().
  const formatSelectEl = $('#prompt-format');
  const promptClearBtn = $('#prompt-clear');
  const promptCharEl   = $('#prompt-char');

  function setFormat(fmt) {
    if (!fmt) return;
    selectedFmt = fmt;
    $$('.fmt-card').forEach((c) => {
      c.classList.toggle('selected', c.dataset.fmt === fmt);
    });
    if (formatSelectEl && formatSelectEl.value !== fmt) {
      formatSelectEl.value = fmt;
    }
  }

  // Initialise dropdown to match whichever card is .selected in markup
  const initialCard = document.querySelector('.fmt-card.selected');
  if (initialCard) setFormat(initialCard.dataset.fmt);

  // Format cards (rich) drive setFormat
  $$('.fmt-card').forEach((card) => {
    card.addEventListener('click', () => setFormat(card.dataset.fmt));
    // Magnetic glow effect
    card.addEventListener('mousemove', (e) => {
      const rect = card.getBoundingClientRect();
      card.style.setProperty('--mx', `${e.clientX - rect.left}px`);
      card.style.setProperty('--my', `${e.clientY - rect.top}px`);
    });
  });

  // Dropdown (compact) also drives setFormat
  if (formatSelectEl) {
    formatSelectEl.addEventListener('change', (e) => setFormat(e.target.value));
  }

  // Character counter — updates live, capped by maxlength on the element
  function updateCharCount() {
    if (!promptCharEl) return;
    promptCharEl.textContent = String((promptEl.value || '').length);
  }
  if (promptEl) {
    promptEl.addEventListener('input', updateCharCount);
    updateCharCount();
  }

  // Clear prompt button — empties the textarea and refocuses
  if (promptClearBtn) {
    promptClearBtn.addEventListener('click', () => {
      promptEl.value = '';
      updateCharCount();
      promptEl.focus();
    });
  }

  // ---------- Example chips ----------
  $$('.chip').forEach((chip) => {
    chip.addEventListener('click', () => {
      promptEl.value = chip.dataset.chip;
      updateCharCount();
      const fmt = chip.dataset.fmt;
      if (fmt) setFormat(fmt);
      promptEl.focus();
    });
  });

  // ---------- Generate ----------
  generateBtn.addEventListener('click', startGeneration);
  // Textarea-friendly Enter behaviour: bare Enter inserts a newline (default),
  // Cmd/Ctrl+Enter submits. Matches what people expect from chat-style boxes.
  promptEl.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
      e.preventDefault();
      startGeneration();
    }
  });

  // Smarter status messages — rotate as job runs
  const STAGE_MESSAGES_COMP = [
    'Brainstorming your hook + 5 items…',
    'Painting cinematic visuals — one per item…',
    'Laying out the detail pages…',
    'Polishing the CTA + slide titles…',
    'Almost there — adding the final touch…',
  ];
  const STAGE_MESSAGES_SINGLE = [
    'Sketching your 10-slide story…',
    'Painting overhead-style visuals…',
    'Compositing slides with auto-fit text…',
    'Adding the final CTA slide…',
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

    try {
      // Pass signed-in user email so the server can log to Firestore
      const _scUser = JSON.parse(localStorage.getItem('sc_user') || '{}');
      const res = await fetch('/api/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          format:     selectedFmt,
          input:      prompt,
          user_email: _scUser.email || null,
        }),
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
    // Format-aware wall-clock cap. Compilation = 5 recipes + 6 images + 12 slides
    // and routinely runs 8-12 min on Render; single is much quicker.
    // The cap also RESETS whenever the server's message field changes, so as
    // long as the pipeline is making forward progress we won't time out.
    const MAX_IDLE_MS = selectedFmt === 'compilation' ? 15 * 60 * 1000 : 8 * 60 * 1000;
    let lastActivity = Date.now();
    let lastServerMsg = '';
    let progress = 8;
    let stageIdx = 0;
    const messages = selectedFmt === 'compilation' ? STAGE_MESSAGES_COMP : STAGE_MESSAGES_SINGLE;

    while (true) {
      await new Promise((r) => setTimeout(r, 1500));
      progress = Math.min(progress + 3, 92);
      jobBar.style.width = `${progress}%`;

      // Cycle through stage messages only until the server gives us a real
      // status. After that, keep the UI grounded in backend state.
      if (!lastServerMsg && Math.random() < 0.45 && stageIdx < messages.length) {
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
        // Any change in the server message counts as forward progress —
        // reset the idle timer so a slow-but-working pipeline isn't killed.
        if (j.message && j.message !== lastServerMsg) {
          lastServerMsg = j.message;
          lastActivity = Date.now();
        }
        // Always prefer the server's live message over rotating placeholders.
        if (j.message) jobMsg.textContent = j.message;
        jobTitle.textContent = j.status === 'pending' ? 'Queued' : 'Working';

        if (j.status === 'done') {
          jobBar.style.width = '100%';
          jobTitle.textContent = 'Ready';
          jobMsg.textContent = j.result?.slide_urls?.length
            ? '✓ Slides uploaded to Firebase — ready to download & share'
            : 'Carousel composited and saved';
          try {
            await loadPreview(j.result.format, j.result.slug, j.result.slide_urls || []);
          } catch (renderErr) {
            console.error('renderResult error:', renderErr);
            jobMsg.textContent = 'Done — slides saved' + (j.result?.slide_urls?.length ? ' & uploaded to Firebase' : '');
          }
          break;  // always break, even if preview rendering threw
        }
        if (j.status === 'failed') {
          jobTitle.textContent = 'Failed';
          jobMsg.textContent = j.error || j.message;
          break;
        }
      } catch (e) {
        jobMsg.textContent = `Error: ${e}`;
      }

      if (Date.now() - lastActivity > MAX_IDLE_MS) {
        const mins = Math.round(MAX_IDLE_MS / 60000);
        jobTitle.textContent = 'Timed out';
        jobMsg.textContent = `No progress for ${mins} minutes — check terminal logs (job may still be running on the server)`;
        break;
      }
    }

    restoreGenerateBtn();
    refreshLibrary();
  }

  async function loadPreview(format, slug, slideUrls = []) {
    const res = await fetch(`/api/preview/${format}/${slug}`);
    if (!res.ok) {
      alert('Preview failed');
      return;
    }
    const data = await res.json();
    // Attach Firebase URLs from the job result if available
    if (slideUrls.length) data.slide_urls = slideUrls;
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

    // ── Download / path row ──────────────────────────────────────────────────
    // Re-query each time in case the DOM was built after script init
    const _dlBtn    = downloadZipEl    || document.getElementById('download-zip');
    const _folderEl = openFolderEl     || document.getElementById('open-folder');
    const firebaseUrls = data.slide_urls || [];
    if (firebaseUrls.length) {
      // Firebase URLs available → show Download slides button
      if (_dlBtn)    { _dlBtn.style.display    = 'inline-flex'; _dlBtn.onclick = () => _downloadSlidesZip(data.slug, firebaseUrls); }
      if (_folderEl) { _folderEl.style.display = 'none'; }
    } else {
      // Fallback: show local path tag
      if (_dlBtn)    { _dlBtn.style.display    = 'none'; }
      if (_folderEl) {
        const folderRel = data.format === 'single'
          ? `output/${data.slug}/slides/`
          : `output_compilations/${data.slug}/slides/`;
        _folderEl.style.display = '';
        _folderEl.title         = folderRel;
        _folderEl.textContent   = folderRel;
      }
    }

    setTimeout(() => resultPanel.scrollIntoView({ behavior: 'smooth', block: 'start' }), 200);
  }

  // Download all slides + caption.txt + metadata.json as a single ZIP
  async function _downloadSlidesZip(slug, urls) {
    const _btn = downloadZipEl || document.getElementById('download-zip');
    if (!_btn) return;

    const _origHTML = _btn.innerHTML;
    _btn.innerHTML = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="animation:spin 1s linear infinite"><path d="M21 12a9 9 0 11-6.22-8.56"/></svg> Zipping…`;
    _btn.style.pointerEvents = 'none';

    try {
      // Server builds the ZIP (slides + caption.txt + metadata.json)
      const format = currentResult?.format || 'compilation';
      const res = await fetch(`/api/download-zip/${format}/${slug}`);
      if (!res.ok) throw new Error(`Server ZIP failed: ${res.status}`);

      const blob = await res.blob();
      const a = document.createElement('a');
      a.href = URL.createObjectURL(blob);
      a.download = `${slug}.zip`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(a.href);
    } catch (e) {
      console.error('ZIP download error:', e);
      // Fallback: open slides individually in new tabs
      (urls || []).forEach(u => window.open(u, '_blank'));
    } finally {
      _btn.innerHTML = _origHTML;
      _btn.style.pointerEvents = '';
    }
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
    img.alt = 'Slide preview';
    // Clicking the image itself shouldn't dismiss — users often want to
    // long-press / save / copy. Only the backdrop and X dismiss.
    img.addEventListener('click', (e) => e.stopPropagation());

    const closeBtn = document.createElement('button');
    closeBtn.type = 'button';
    closeBtn.className = 'lightbox-close';
    closeBtn.setAttribute('aria-label', 'Close preview');
    closeBtn.innerHTML = `
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none"
           stroke="currentColor" stroke-width="2.4" stroke-linecap="round">
        <path d="M18 6L6 18M6 6l12 12"/>
      </svg>
    `;

    function dismiss() {
      lb.remove();
      document.removeEventListener('keydown', onKey);
    }
    function onKey(e) {
      if (e.key === 'Escape') dismiss();
    }
    closeBtn.addEventListener('click', (e) => { e.stopPropagation(); dismiss(); });
    lb.addEventListener('click', dismiss);
    document.addEventListener('keydown', onKey);

    lb.appendChild(img);
    lb.appendChild(closeBtn);
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
      allItems = data.items || [];
      console.log(`[RecipeVault] Library loaded ${allItems.length} items`);
      renderLibrary();
      updateStats();
      populatePhoneDeck();
    } catch (e) {
      console.error('Library fetch failed:', e);
    }
  }

  function makeCard(it) {
    const c = document.createElement('div');
    c.className = 'lib-card';
    c.dataset.format = it.format;
    c.dataset.slug   = it.slug;
    c.innerHTML = `
      <div class="lib-thumb">
        <img src="${it.thumbnail}" loading="lazy" />
        <span class="lib-fmt">${it.format === 'compilation' ? 'Compilation' : 'Single'}</span>
      </div>
      <div class="lib-meta">
        <div class="lib-title">${escapeHtml(it.title)}</div>
        <div class="lib-sub">${escapeHtml(it.subtitle || '')}</div>
      </div>
    `;
    return c;
  }

  // Delegated click for lib-cards (works on originals AND clones)
  document.addEventListener('click', async (e) => {
    const card = e.target.closest('.lib-card');
    if (!card || !card.dataset.format) return;
    const res = await fetch(`/api/preview/${card.dataset.format}/${card.dataset.slug}`);
    if (!res.ok) return;
    const data = await res.json();
    showLibraryModal(data);
  });

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

    // Kick off auto-scroll now that cards are in the DOM
    setupAutoScroll('comp');
    setupAutoScroll('single');
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

  // ---------- Auto-rotating rails (infinite marquee) ----------
  // Works by duplicating the card set so there is always overflow, then
  // pixel-scrolling with requestAnimationFrame. When the scroll reaches the
  // midpoint (end of original set) it instantly snaps back to 0 — seamless loop.
  const RAIL_PX_PER_SEC = 60; // scroll speed in pixels per second

  function setupAutoScroll(railId) {
    const rail = document.getElementById(`rail-${railId}`);
    if (!rail) return;

    // Cancel any previous RAF on this rail
    if (rail._rafId) { cancelAnimationFrame(rail._rafId); rail._rafId = null; }

    // Remove old duplicate nodes appended by a previous call
    rail.querySelectorAll('[data-clone]').forEach(n => n.remove());

    // Collect original cards
    const origCards = Array.from(rail.querySelectorAll('.lib-card'));
    if (origCards.length === 0) return;

    // Clone the full set (enough copies to always overflow even on wide screens)
    const copies = Math.max(3, Math.ceil(window.innerWidth / (origCards.length * 180)) + 1);
    for (let i = 0; i < copies; i++) {
      origCards.forEach(card => {
        const clone = card.cloneNode(true);
        clone.setAttribute('data-clone', '1');
        rail.appendChild(clone);
      });
    }

    // Remove scroll-snap so we can do pixel scrolling
    rail.style.scrollSnapType = 'none';

    let paused = false;
    let lastTs  = null;

    function tick(ts) {
      if (lastTs !== null && !paused) {
        const delta = (ts - lastTs) / 1000; // seconds
        rail.scrollLeft += RAIL_PX_PER_SEC * delta;

        // Seamless loop: once we've scrolled past the original set, snap back
        const origWidth = origCards.reduce((sum, c) => sum + c.offsetWidth + 12, 0);
        if (rail.scrollLeft >= origWidth) {
          rail.scrollLeft -= origWidth;
        }
      }
      lastTs = ts;
      rail._rafId = requestAnimationFrame(tick);
    }

    rail.addEventListener('mouseenter', () => { paused = true; });
    rail.addEventListener('mouseleave', () => { paused = false; });

    rail._rafId = requestAnimationFrame(tick);
  }

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
    const total = allItems.length;
    const single = allItems.filter((i) => i.format === 'single').length;
    const comp = allItems.filter((i) => i.format === 'compilation').length;
    animateCounter($('#stat-total'), total);
    animateCounter($('#stat-single'), single);
    animateCounter($('#stat-comp'), comp);
  }

  // ---------- Phone deck (real TikTok-style cycling) ----------
  let deckInterval = null;
  async function populatePhoneDeck() {
    const deck = $('#phone-deck');
    const progress = $('#tk-progress');
    const captionEl = $('#tk-caption');
    if (!deck || !progress) return;
    if (deckInterval) clearInterval(deckInterval);

    // Pick 1 compilation and rotate through its 12 slides — looks more like
    // a real TikTok carousel.
    const comps = allItems.filter((i) => i.format === 'compilation');
    if (comps.length === 0) return;
    const pick = comps[Math.floor(Math.random() * Math.min(comps.length, 20))];

    // Load full slide list for that compilation
    let slides = [];
    let title = pick.title;
    try {
      const res = await fetch(`/api/preview/compilation/${pick.slug}`);
      if (res.ok) {
        const data = await res.json();
        slides = data.slides;
        title = data.title;
      }
    } catch (e) { console.warn(e); }
    if (slides.length === 0) {
      slides = [pick.thumbnail];
    }

    captionEl.textContent = title;

    // Build progress segments (one per slide)
    progress.innerHTML = '';
    slides.forEach(() => {
      const s = document.createElement('span');
      progress.appendChild(s);
    });
    const segs = progress.querySelectorAll('span');

    // Build image elements
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
      if (segs[idx]) {
        segs[idx].classList.remove('active');
        segs[idx].classList.add('done');
      }
      idx = (idx + 1) % imgs.length;
      // If we wrapped, reset progress
      if (idx === 0) segs.forEach((s) => s.classList.remove('done', 'active'));
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
    // Template-batch jobs run N compilations back-to-back. Cap is per-IDLE,
    // not per-job: as long as the server message changes we keep polling.
    const MAX_IDLE_MS = 20 * 60 * 1000;
    let lastActivity = Date.now();
    let lastMsg = '';
    let progress = 8;
    while (true) {
      await new Promise((res) => setTimeout(res, 2000));
      progress = Math.min(progress + 4, 92);
      $('#tpl-job-bar').style.width = `${progress}%`;
      try {
        const r = await fetch(`/api/jobs/${jobId}`);
        if (!r.ok) break;
        const j = await r.json();
        const newMsg = j.message || j.status;
        if (newMsg !== lastMsg) {
          lastMsg = newMsg;
          lastActivity = Date.now();
        }
        $('#tpl-job-msg').textContent = newMsg;
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
      if (Date.now() - lastActivity > MAX_IDLE_MS) {
        const mins = Math.round(MAX_IDLE_MS / 60000);
        $('#tpl-job-title').textContent = 'Timed out';
        $('#tpl-job-msg').textContent = `No progress for ${mins} minutes — check terminal logs`;
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
        document.title = `${cfg.brand_name} ${cfg.studio_name || 'Studio'} — Generate viral carousels in 30s`;
      }
    } catch (e) {
      console.warn('branding fetch failed:', e);
    }
  }

  // ---------- Initial load ----------
  applyBranding();
  refreshLibrary();
  // Tracking section ("Daily impressions" + Leaderboard + Top posts) and the
  // Templates / Past Batches sections were removed from index.html. The
  // associated initializers below are commented out to avoid pointless
  // /api/tracking/* and /api/templates/* requests on every page load. The
  // function definitions themselves stay as dead code (their element lookups
  // would return null and noop) in case the sections are reintroduced.
  // loadTrackingStatus();
  // loadTrackingSummary();
  // loadTemplates();
  // loadBatches();
  // bindBuilder();
})();
