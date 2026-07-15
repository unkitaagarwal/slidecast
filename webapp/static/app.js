// RecipeVault Studio — frontend
(() => {
  const $ = (s) => document.querySelector(s);
  const $$ = (s) => document.querySelectorAll(s);

  const promptFields = $('#prompt-fields');
  const promptAddBtn = $('#prompt-add');
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
  const cancelBtn = $('#cancel-btn');

  let selectedFmt = 'compilation';
  let currentResult = null;
  let allItems = [];
  // Set to true by the cancel button to break the pollJob loop
  let _cancelRequested = false;

  // ---------- Prompt dialog wiring ----------
  // Format selector lives in two places: the rich cards (.fmt-card) above and
  // the compact dropdown (#prompt-format) inside the new dialog. Both write to
  // `selectedFmt` and both stay visually in sync via setFormat().
  const formatSelectEl = $('#prompt-format');
  const promptClearBtn = $('#prompt-clear');

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

  const promptLinesEl = $('#prompt-lines');
  const promptLinesPluralEl = $('#prompt-lines-plural');
  const MAX_FIELDS = 12;

  // ---------- Dynamic prompt fields ----------
  // Each prompt lives in its own row. Users add as many as they need; every
  // non-empty field becomes its own slideshow, all generated in parallel.

  // Collect the trimmed, non-empty prompts across all fields.
  function parsePrompts() {
    return Array.from(promptFields.querySelectorAll('.prompt-field'))
      .map((el) => (el.value || '').trim())
      .filter(Boolean);
  }

  // Renumber the row badges and update the counter + Add-button state.
  function refreshFields() {
    const rows = promptFields.querySelectorAll('.prompt-field-row');
    rows.forEach((row, i) => {
      const num = row.querySelector('.prompt-field-num');
      // Don't clobber the spinner / tick / cross shown during & after a run.
      if (num && (row.dataset.state || 'idle') === 'idle') {
        num.className = 'prompt-field-num';
        num.textContent = String(i + 1);
      }
      // Only show the remove button when there's more than one row (idle only).
      const rm = row.querySelector('.prompt-field-remove');
      if (rm) rm.style.visibility =
        (rows.length > 1 && (row.dataset.state || 'idle') === 'idle') ? 'visible' : '';
    });
    if (promptLinesEl) promptLinesEl.textContent = String(rows.length);
    if (promptLinesPluralEl) promptLinesPluralEl.textContent = rows.length === 1 ? '' : 's';
    if (promptAddBtn) promptAddBtn.disabled = rows.length >= MAX_FIELDS;
  }

  // Create one prompt row. Returns the textarea element.
  function addField(value = '', { focus = false } = {}) {
    const rows = promptFields.querySelectorAll('.prompt-field-row');
    if (rows.length >= MAX_FIELDS) return null;
    const row = document.createElement('div');
    row.className = 'prompt-field-row';
    row.dataset.state = 'idle';
    row.innerHTML = `
      <span class="prompt-field-num">1</span>
      <div class="prompt-field-body">
        <textarea class="prompt-field" rows="1" maxlength="500"
          placeholder="Describe a slideshow… e.g. &quot;5 habits that quietly wreck your sleep&quot;"
          autocomplete="off"></textarea>
        <div class="prompt-field-progress hidden"><div class="job-bar"><div class="job-bar-fill" style="width:4%"></div></div></div>
        <div class="prompt-field-msg hidden"></div>
      </div>
      <div class="prompt-field-actions">
        <button class="btn-ghost prompt-field-download hidden" type="button" title="Download slides">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="3" x2="12" y2="15"/></svg>
          Download
        </button>
        <button class="btn-ghost prompt-field-cancel hidden" type="button" title="Cancel">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><path d="M18 6L6 18M6 6l12 12"/></svg>
          Cancel
        </button>
        <button class="prompt-field-remove" type="button" title="Remove this prompt" aria-label="Remove this prompt">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><path d="M18 6L6 18M6 6l12 12"/></svg>
        </button>
      </div>`;
    const ta = row.querySelector('.prompt-field');
    ta.value = value;
    // Auto-grow the textarea as the user types.
    const autoGrow = () => { ta.style.height = 'auto'; ta.style.height = `${ta.scrollHeight}px`; };
    ta.addEventListener('input', autoGrow);
    // Cmd/Ctrl+Enter submits the whole batch; plain Enter inserts a newline.
    ta.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
        e.preventDefault();
        startGeneration();
      }
    });
    row.querySelector('.prompt-field-remove').addEventListener('click', () => {
      row.remove();
      // Never leave zero fields — keep at least one empty row.
      if (promptFields.querySelectorAll('.prompt-field-row').length === 0) addField();
      refreshFields();
    });
    promptFields.appendChild(row);
    refreshFields();
    requestAnimationFrame(autoGrow);
    if (focus) ta.focus();
    return ta;
  }

  // Put a value into the first empty field, or add a new one if all are full.
  function fillNextField(value) {
    const empty = Array.from(promptFields.querySelectorAll('.prompt-field'))
      .find((el) => !(el.value || '').trim());
    if (empty) {
      empty.value = value;
      empty.dispatchEvent(new Event('input'));
      empty.focus();
      return empty;
    }
    return addField(value, { focus: true });
  }

  // Seed the first field on load.
  addField();

  if (promptAddBtn) {
    promptAddBtn.addEventListener('click', () => addField('', { focus: true }));
  }

  // Clear button — reset to a single empty field.
  if (promptClearBtn) {
    promptClearBtn.addEventListener('click', () => {
      promptFields.innerHTML = '';
      addField('', { focus: true });
    });
  }

  // ---------- Example chips ----------
  $$('.chip').forEach((chip) => {
    chip.addEventListener('click', () => {
      // Drop the example into the next open field, building up a batch.
      fillNextField(chip.dataset.chip);
      const fmt = chip.dataset.fmt;
      if (fmt) setFormat(fmt);
    });
  });

  // ---------- Generate ----------
  generateBtn.addEventListener('click', startGeneration);
  // (Per-field Cmd/Ctrl+Enter also submits — wired up in addField.)

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

  // SVG glyphs for the row status badge.
  const _ICON_CHECK = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3.2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12l5 5L20 7"/></svg>`;
  const _ICON_CROSS = `<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round"><path d="M18 6L6 18M6 6l12 12"/></svg>`;

  // Drive a single prompt row's badge, progress bar, message, and action buttons.
  function setRowState(row, state, msg) {
    row.dataset.state = state;
    const num   = row.querySelector('.prompt-field-num');
    const prog  = row.querySelector('.prompt-field-progress');
    const msgEl = row.querySelector('.prompt-field-msg');
    const cancel= row.querySelector('.prompt-field-cancel');
    const remove= row.querySelector('.prompt-field-remove');
    const dl    = row.querySelector('.prompt-field-download');
    if (msg != null) { msgEl.textContent = msg; msgEl.classList.remove('hidden'); }

    const running = state === 'pending' || state === 'running';
    prog.classList.toggle('hidden', !running);
    cancel.classList.toggle('hidden', !running);
    remove.classList.toggle('hidden', running);

    if (running) {
      num.className = 'prompt-field-num spinning';
      num.innerHTML = '';
      dl.classList.add('hidden');
      msgEl.classList.remove('hidden', 'is-error', 'is-ok');
    } else if (state === 'done') {
      num.className = 'prompt-field-num done';
      num.innerHTML = _ICON_CHECK;
      dl.classList.remove('hidden');
      msgEl.classList.add('is-ok');
      msgEl.classList.remove('is-error');
    } else if (state === 'failed' || state === 'cancelled') {
      num.className = 'prompt-field-num failed';
      num.innerHTML = _ICON_CROSS;
      dl.classList.add('hidden');
      msgEl.classList.add('is-error');
      msgEl.classList.remove('is-ok');
    }
  }

  // Entry point wired to the Generate button. Each non-empty field becomes its
  // own job; all run in parallel with progress shown inline under the field.
  async function startGeneration() {
    const rows = Array.from(promptFields.querySelectorAll('.prompt-field-row'))
      .filter((r) => (r.querySelector('.prompt-field').value || '').trim());
    if (rows.length === 0) {
      const first = promptFields.querySelector('.prompt-field');
      if (first) first.focus();
      return;
    }

    const fmt = selectedFmt;
    generateBtn.disabled = true;
    generateBtn.querySelector('svg')?.style && (generateBtn.querySelector('svg').style.opacity = '0');
    generateBtn.firstChild && (generateBtn.firstChild.nodeValue =
      rows.length > 1 ? `Generating ${rows.length}` : 'Generating');
    if (promptAddBtn) promptAddBtn.disabled = true;
    if (promptClearBtn) promptClearBtn.disabled = true;

    // Legacy single-result panels are unused in the inline flow.
    if (jobPanel) jobPanel.classList.add('hidden');
    if (resultPanel) resultPanel.classList.add('hidden');

    const _scUser = JSON.parse(localStorage.getItem('sc_user') || '{}');
    const userEmail = _scUser.email || null;

    await Promise.allSettled(rows.map((r) => generateOne(r, fmt, userEmail)));

    restoreGenerateBtn();
    refreshFields();
    refreshLibrary();
  }

  function restoreGenerateBtn() {
    generateBtn.disabled = false;
    generateBtn.innerHTML = `Generate <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><path d="M5 12h14M13 5l7 7-7 7"/></svg>`;
    if (promptAddBtn) promptAddBtn.disabled =
      promptFields.querySelectorAll('.prompt-field-row').length >= MAX_FIELDS;
    if (promptClearBtn) promptClearBtn.disabled = false;
    if (cancelBtn) cancelBtn.style.display = 'none';
  }

  // Submit one prompt (from its row), then poll its job, updating the row inline.
  async function generateOne(row, fmt, userEmail) {
    const ta = row.querySelector('.prompt-field');
    const prompt = (ta.value || '').trim();
    const barFill = row.querySelector('.job-bar-fill');
    if (barFill) barFill.style.width = '4%';
    ta.readOnly = true;
    let jobId = null;

    // Per-row cancel
    const cancelBtnEl = row.querySelector('.prompt-field-cancel');
    cancelBtnEl.onclick = async () => {
      if (!jobId) return;
      cancelBtnEl.disabled = true;
      setRowState(row, 'running', 'Cancelling…');
      try { await fetch(`/api/jobs/${jobId}/cancel`, { method: 'POST' }); }
      catch (e) { console.warn('Cancel failed:', e); }
    };

    setRowState(row, 'pending', 'Queued…');

    try {
      const res = await fetch('/api/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ format: fmt, input: prompt, user_email: userEmail }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}: ${await res.text()}`);
      jobId = (await res.json()).job_id;
    } catch (e) {
      setRowState(row, 'failed', String(e));
      if (barFill) barFill.style.width = '0%';
      ta.readOnly = false;
      return;
    }

    await pollRow(jobId, row, fmt);
    ta.readOnly = false;
  }

  // Poll a single job and drive its row's progress bar, message, and download.
  async function pollRow(jobId, row, fmt) {
    const barFill = row.querySelector('.job-bar-fill');
    const cancelBtnEl = row.querySelector('.prompt-field-cancel');
    const MAX_IDLE_MS = fmt === 'compilation' ? 15 * 60 * 1000 : 8 * 60 * 1000;
    const messages = fmt === 'compilation' ? STAGE_MESSAGES_COMP : STAGE_MESSAGES_SINGLE;
    let lastActivity = Date.now();
    let lastServerMsg = '';
    let progress = 8;
    let stageIdx = 0;

    while (true) {
      await new Promise((r) => setTimeout(r, 1500));
      progress = Math.min(progress + 3, 92);
      if (barFill && row.dataset.state !== 'done') barFill.style.width = `${progress}%`;

      if (!lastServerMsg && Math.random() < 0.45 && stageIdx < messages.length) {
        setRowState(row, 'running', messages[stageIdx]);
        stageIdx += 1;
      }

      let j;
      try {
        const res = await fetch(`/api/jobs/${jobId}`);
        if (!res.ok) { setRowState(row, 'failed', 'Server error fetching job'); break; }
        j = await res.json();
      } catch (e) {
        setRowState(row, 'running', `Error: ${e}`);
        if (Date.now() - lastActivity > MAX_IDLE_MS) break;
        continue;
      }

      if (j.message && j.message !== lastServerMsg) {
        lastServerMsg = j.message;
        lastActivity = Date.now();
      }
      if (j.status !== 'done' && j.message) {
        setRowState(row, j.status === 'pending' ? 'pending' : 'running', j.message);
      }

      if (j.status === 'cancelled') {
        setRowState(row, 'cancelled', 'Cancelled.');
        if (barFill) barFill.style.width = '0%';
        break;
      }
      if (j.status === 'failed') {
        setRowState(row, 'failed', j.error || j.message || 'Generation failed.');
        break;
      }
      if (j.status === 'done') {
        if (barFill) barFill.style.width = '100%';
        setRowState(row, 'done', '✓ Ready to download');
        attachDownload(row, j.result.format, j.result.slug, j.result.slide_urls || []);
        break;
      }

      if (Date.now() - lastActivity > MAX_IDLE_MS) {
        const mins = Math.round(MAX_IDLE_MS / 60000);
        setRowState(row, 'failed', `No progress for ${mins} min — check server logs (job may still be running).`);
        break;
      }
    }
  }

  // Wire the row's Download button to the server-built ZIP for that carousel.
  function attachDownload(row, format, slug, urls) {
    const dl = row.querySelector('.prompt-field-download');
    dl.onclick = () => _downloadSlidesZip(format, slug, urls, dl);
  }

  // Download all slides + caption + metadata as a single ZIP for one carousel.
  async function _downloadSlidesZip(format, slug, urls, btn) {
    if (!btn) return;
    const _origHTML = btn.innerHTML;
    btn.innerHTML = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="animation:spin 1s linear infinite"><path d="M21 12a9 9 0 11-6.22-8.56"/></svg> Zipping…`;
    btn.style.pointerEvents = 'none';
    try {
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
      (urls || []).forEach((u) => window.open(u, '_blank'));
    } finally {
      btn.innerHTML = _origHTML;
      btn.style.pointerEvents = '';
    }
  }

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
    const elTotal  = $('#stat-total');
    const elSingle = $('#stat-single');
    const elComp   = $('#stat-comp');
    if (elTotal)  animateCounter(elTotal, total);
    if (elSingle) animateCounter(elSingle, single);
    if (elComp)   animateCounter(elComp, comp);
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
    let candidates = allItems.filter((i) => i.format === 'compilation');
    if (candidates.length === 0) candidates = allItems.filter((i) => i.format === 'single');
    if (candidates.length === 0) return;
    const pick = candidates[Math.floor(Math.random() * Math.min(candidates.length, 20))];

    // Load full slide list for that carousel
    let slides = [];
    let title = pick.title;
    try {
      const res = await fetch(`/api/preview/${pick.format}/${pick.slug}`);
      if (res.ok) {
        const data = await res.json();
        slides = (data.slides || []).filter(Boolean);
        title = data.title || title;
      }
    } catch (e) { console.warn('[phone-deck] preview fetch failed:', e); }
    if (slides.length === 0 && pick.thumbnail) {
      slides = [pick.thumbnail];
    }
    if (slides.length === 0) {
      console.warn('[phone-deck] no slides found for', pick.slug);
      return;
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
  // Cancel button is only visible during active generation
  if (cancelBtn) cancelBtn.style.display = 'none';

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
