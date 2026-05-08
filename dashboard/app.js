const API = 'http://localhost:5000';

const STATUSES = ['New', 'Interested', 'Applied', 'Interview', 'Offer', 'Rejected', 'Skipped'];

const COL_COLORS = {
  New:        '#607d8b',
  Interested: '#ff9800',
  Applied:    '#2196f3',
  Interview:  '#9c27b0',
  Offer:      '#4caf50',
  Rejected:   '#f44336',
  Skipped:    '#9e9e9e',
};

const RV_LABELS = {
  EconPolicy:        'Econ / Policy',
  FinanceConsulting: 'Finance / Consulting',
  DataAnalyst:       'Data Analyst',
  ResearchAnalyst:   'Research Analyst',
};

const NEW_COL_LIMIT = 50;

// ── State ────────────────────────────────────────────────────────────────────

let allJobs      = [];
let currentJobId = null;
let searchText   = '';
let sourceFilter = '';
let resumeFilter = '';
let colLimits    = {};   // { New: 50, ... } expanded limits per column
let dragJobId    = null;

// ── Boot ─────────────────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', () => {
  buildBoard();
  loadAll();
  bindToolbar();
  bindJobModal();
  bindAddModal();
  bindTailorModal();
  bindKeyboard();
});

async function loadAll() {
  await Promise.all([loadJobs(), loadStats()]);
}

async function loadJobs() {
  try {
    const res  = await fetch(`${API}/api/jobs`);
    const json = await res.json();
    // Dismissed jobs are soft-deleted; keep them in the DB (to block
    // re-scraping the same URL) but hide them from the board entirely.
    allJobs = (json.data || []).filter(j => j.status !== 'Dismissed');
    populateSourceFilter();
    renderBoard();
  } catch (e) {
    console.error('loadJobs failed:', e);
  }
}

async function loadStats() {
  try {
    const res  = await fetch(`${API}/api/stats`);
    const json = await res.json();
    const d    = json.data || {};
    document.getElementById('statTotal').textContent      = d.total_jobs      ?? '—';
    document.getElementById('statApplied').textContent    = d.applied_count   ?? '—';
    document.getElementById('statInterviews').textContent = d.interview_count  ?? '—';
    document.getElementById('statRate').textContent       = d.response_rate != null
      ? d.response_rate + '%' : '—';
    document.getElementById('statLastScraped').textContent = formatLastScraped(d.last_scraped);
  } catch (e) {
    console.error('loadStats failed:', e);
  }
}

// ── Board ─────────────────────────────────────────────────────────────────────

function buildBoard() {
  const board = document.getElementById('board');
  board.innerHTML = '';
  STATUSES.forEach(status => {
    const col = document.createElement('div');
    col.className      = 'column';
    col.dataset.status = status;

    col.innerHTML = `
      <div class="col-head">
        <span class="col-dot" style="background:${COL_COLORS[status]}"></span>
        <span class="col-name">${status}</span>
        <span class="col-badge" id="badge-${status}">0</span>
      </div>
      <div class="col-cards" id="col-${status}"></div>
    `;

    col.addEventListener('dragover', e => {
      e.preventDefault();
      col.classList.add('drag-over');
    });
    col.addEventListener('dragleave', e => {
      if (!col.contains(e.relatedTarget)) col.classList.remove('drag-over');
    });
    col.addEventListener('drop', e => {
      e.preventDefault();
      col.classList.remove('drag-over');
      if (dragJobId !== null && status !== getJobStatus(dragJobId)) {
        moveJob(dragJobId, status);
      }
    });

    board.appendChild(col);
  });
}

function getJobStatus(id) {
  const job = allJobs.find(j => j.id === id);
  return job ? job.status : null;
}

function renderBoard() {
  const q      = searchText.toLowerCase();
  const src    = sourceFilter;
  const rv     = resumeFilter;

  // Group jobs
  const grouped = {};
  STATUSES.forEach(s => { grouped[s] = []; });

  allJobs.forEach(job => {
    if (src && job.source !== src) return;
    if (rv  && job.resume_version !== rv) return;
    if (q) {
      const hay = `${job.title} ${job.company} ${job.location}`.toLowerCase();
      if (!hay.includes(q)) return;
    }
    grouped[job.status]?.push(job);
  });

  STATUSES.forEach(status => {
    const jobs  = grouped[status] || [];
    const body  = document.getElementById(`col-${status}`);
    const badge = document.getElementById(`badge-${status}`);
    if (!body) return;

    badge.textContent = jobs.length;
    body.innerHTML    = '';

    const limit = colLimits[status] ?? (status === 'New' ? NEW_COL_LIMIT : Infinity);
    const shown = jobs.slice(0, limit);

    shown.forEach(job => body.appendChild(createCard(job)));

    if (jobs.length > shown.length) {
      const remaining = jobs.length - shown.length;
      const btn = document.createElement('button');
      btn.className   = 'show-more';
      btn.textContent = `Show ${remaining} more`;
      btn.addEventListener('click', () => {
        colLimits[status] = Infinity;
        renderBoard();
      });
      body.appendChild(btn);
    }
  });
}

// ── Card ──────────────────────────────────────────────────────────────────────

function createCard(job) {
  const card = document.createElement('div');
  card.className       = 'card';
  card.draggable       = true;
  card.dataset.id      = job.id;
  card.dataset.rv      = job.resume_version || 'none';

  const rvLabel = job.resume_version ? (RV_LABELS[job.resume_version] || job.resume_version) : null;
  const rvTagClass = {
    EconPolicy: 'tag-econ', FinanceConsulting: 'tag-finance',
    DataAnalyst: 'tag-data', ResearchAnalyst: 'tag-research',
  }[job.resume_version] || '';

  const h1bTag  = job.h1b_status === 'Known Sponsor'
    ? `<span class="tag tag-h1b">H-1B</span>` : '';
  const rvTag   = rvLabel
    ? `<span class="tag ${rvTagClass}">${escHtml(rvLabel)}</span>` : '';
  const srcTag  = job.source
    ? `<span class="tag tag-src">${escHtml(job.source)}</span>` : '';

  card.innerHTML = `
    <div class="card-title">${escHtml(job.title)}</div>
    <div class="card-co">${escHtml(job.company)}</div>
    <div class="card-loc">${escHtml(job.location || '')}</div>
    <div class="card-tags">${rvTag}${srcTag}${h1bTag}</div>
  `;

  card.addEventListener('dragstart', e => {
    dragJobId = job.id;
    card.classList.add('dragging');
    e.dataTransfer.effectAllowed = 'move';
  });
  card.addEventListener('dragend', () => {
    dragJobId = null;
    card.classList.remove('dragging');
    document.querySelectorAll('.drag-over').forEach(el => el.classList.remove('drag-over'));
  });
  card.addEventListener('click', () => openJobModal(job.id));

  return card;
}

// ── Drag → Move ───────────────────────────────────────────────────────────────

async function moveJob(jobId, newStatus) {
  const job = allJobs.find(j => j.id === jobId);
  if (!job) return;
  job.status = newStatus;
  renderBoard();
  try {
    await fetch(`${API}/api/jobs/${jobId}`, {
      method:  'PUT',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify({ status: newStatus }),
    });
    await loadAll();
  } catch (e) {
    console.error('moveJob failed:', e);
  }
}

// ── Job Modal ─────────────────────────────────────────────────────────────────

function openJobModal(jobId) {
  const job = allJobs.find(j => j.id === jobId);
  if (!job) return;
  currentJobId = jobId;

  document.getElementById('mTitle').textContent    = job.title    || '—';
  document.getElementById('mCompany').textContent  = job.company  || '—';
  document.getElementById('mLocation').textContent = job.location || '—';

  const link = document.getElementById('mOpenLink');
  if (job.url) {
    link.href                = job.url;
    link.style.display       = '';
  } else {
    link.style.display = 'none';
  }

  // Chips
  const chips = document.getElementById('mChips');
  chips.innerHTML = '';
  if (job.source) chips.appendChild(makeChip(job.source, ''));
  if (job.h1b_status === 'Known Sponsor') chips.appendChild(makeChip('H-1B Sponsor', 'h1b'));
  if (job.date_scraped) chips.appendChild(makeChip('Scraped ' + job.date_scraped.slice(0,10), ''));

  // Salary
  const salaryEl = document.getElementById('mSalary');
  if (job.salary) {
    salaryEl.textContent = job.salary;
    salaryEl.hidden = false;
  } else {
    salaryEl.hidden = true;
  }

  // Form fields
  document.getElementById('eStatus').value       = job.status           || 'New';
  document.getElementById('eResume').value        = job.resume_version  || '';
  document.getElementById('eDateApplied').value   = job.date_applied    || '';
  document.getElementById('eH1b').value           = job.h1b_status      || 'Unknown';
  document.getElementById('eNotes').value         = job.notes           || '';

  document.getElementById('jobOverlay').hidden = false;
  document.getElementById('eStatus').focus();
}

function makeChip(text, extraClass) {
  const span = document.createElement('span');
  span.className = extraClass ? `chip chip-${extraClass}` : 'chip';
  span.textContent = text;
  return span;
}

function closeJobModal() {
  document.getElementById('jobOverlay').hidden = true;
  currentJobId = null;
}

function bindJobModal() {
  document.getElementById('jobModalClose').addEventListener('click', closeJobModal);
  document.getElementById('jobOverlay').addEventListener('click', e => {
    if (e.target === document.getElementById('jobOverlay')) closeJobModal();
  });

  document.getElementById('btnSave').addEventListener('click', async () => {
    if (currentJobId === null) return;
    const updates = {
      status:         document.getElementById('eStatus').value,
      resume_version: document.getElementById('eResume').value || null,
      date_applied:   document.getElementById('eDateApplied').value || null,
      h1b_status:     document.getElementById('eH1b').value,
      notes:          document.getElementById('eNotes').value,
    };
    try {
      const res = await fetch(`${API}/api/jobs/${currentJobId}`, {
        method:  'PUT',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify(updates),
      });
      if (!res.ok) throw new Error(await res.text());
      showSaveToast();
      await loadAll();
    } catch (e) {
      console.error('save failed:', e);
      alert('Save failed: ' + e.message);
    }
  });

  document.getElementById('btnTailor').addEventListener('click', () => {
    if (currentJobId !== null) openTailorModal(currentJobId);
  });

  document.getElementById('btnDelete').addEventListener('click', async () => {
    if (currentJobId === null) return;
    const job = allJobs.find(j => j.id === currentJobId);
    const name = job ? `${job.title} @ ${job.company}` : `Job #${currentJobId}`;
    if (!confirm(`Dismiss "${name}"? It will be hidden from the board and won't be re-scraped.`)) return;
    try {
      await fetch(`${API}/api/jobs/${currentJobId}`, { method: 'DELETE' });
      closeJobModal();
      await loadAll();
    } catch (e) {
      console.error('delete failed:', e);
    }
  });
}

function showSaveToast() {
  const toast = document.getElementById('saveToast');
  toast.classList.add('show');
  setTimeout(() => toast.classList.remove('show'), 1800);
}

// ── Add Job Modal ─────────────────────────────────────────────────────────────

function openAddModal() {
  ['aTitle','aCompany','aLocation','aUrl','aSalary'].forEach(id => {
    document.getElementById(id).value = '';
  });
  const err = document.getElementById('addErr');
  err.hidden = true;
  document.getElementById('addOverlay').hidden = false;
  document.getElementById('aTitle').focus();
}

function closeAddModal() {
  document.getElementById('addOverlay').hidden = true;
}

function bindAddModal() {
  document.getElementById('addJobBtn').addEventListener('click', openAddModal);
  document.getElementById('addModalClose').addEventListener('click', closeAddModal);
  document.getElementById('addOverlay').addEventListener('click', e => {
    if (e.target === document.getElementById('addOverlay')) closeAddModal();
  });

  document.getElementById('btnAddSubmit').addEventListener('click', async () => {
    const title    = document.getElementById('aTitle').value.trim();
    const company  = document.getElementById('aCompany').value.trim();
    const location = document.getElementById('aLocation').value.trim();
    const url      = document.getElementById('aUrl').value.trim();
    const salary   = document.getElementById('aSalary').value.trim();

    const errEl = document.getElementById('addErr');
    if (!title || !company || !location || !url) {
      errEl.textContent = 'Please fill in all required fields.';
      errEl.hidden = false;
      return;
    }
    errEl.hidden = true;

    try {
      const res = await fetch(`${API}/api/jobs`, {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify({ title, company, location, url, salary: salary || null, source: 'manual' }),
      });
      const json = await res.json();
      if (!res.ok) {
        errEl.textContent = json.error || 'Failed to add job.';
        errEl.hidden = false;
        return;
      }
      closeAddModal();
      await loadAll();
    } catch (e) {
      errEl.textContent = 'Network error: ' + e.message;
      errEl.hidden = false;
    }
  });
}

// ── Toolbar ───────────────────────────────────────────────────────────────────

function bindToolbar() {
  document.getElementById('searchInput').addEventListener('input', e => {
    searchText = e.target.value;
    renderBoard();
  });
  document.getElementById('sourceFilter').addEventListener('change', e => {
    sourceFilter = e.target.value;
    renderBoard();
  });
  document.getElementById('resumeFilter').addEventListener('change', e => {
    resumeFilter = e.target.value;
    renderBoard();
  });
}

function populateSourceFilter() {
  const sources = [...new Set(allJobs.map(j => j.source).filter(Boolean))].sort();
  const sel = document.getElementById('sourceFilter');
  const cur = sel.value;
  sel.innerHTML = '<option value="">All Sources</option>';
  sources.forEach(s => {
    const opt = document.createElement('option');
    opt.value       = s;
    opt.textContent = s;
    if (s === cur) opt.selected = true;
    sel.appendChild(opt);
  });
}

// ── Tailor & Cover Letter ─────────────────────────────────────────────────────

const RV_BADGE_LABELS = {
  EconPolicy:        'Econ / Policy',
  FinanceConsulting: 'Finance / Consulting',
  DataAnalyst:       'Data Analyst',
  ResearchAnalyst:   'Research Analyst',
};

async function openTailorModal(jobId) {
  const job = allJobs.find(j => j.id === jobId);
  if (!job) return;

  // Set header
  document.getElementById('tJobName').textContent =
    `${escHtml(job.title)} @ ${escHtml(job.company)}`;
  const rv = job.resume_version || job.matched_resume;
  document.getElementById('tResumeBadge').textContent =
    rv ? (RV_BADGE_LABELS[rv] || rv) : 'Auto-select';

  // Reset state
  document.getElementById('tailorLoading').hidden  = false;
  document.getElementById('tailorContent').hidden  = true;
  document.getElementById('tailorError').hidden    = true;
  document.getElementById('tailorOverlay').hidden  = false;

  try {
    const res  = await fetch(`${API}/api/jobs/${jobId}/generate`, { method: 'POST' });
    const json = await res.json();

    if (!res.ok) {
      showTailorError(json.error || 'Unknown error from server.');
      return;
    }

    const data = json.data;

    if (data.resume_version) {
      document.getElementById('tResumeBadge').textContent =
        RV_BADGE_LABELS[data.resume_version] || data.resume_version;
    }

    // Render download links
    const dlEl = document.getElementById('tDownloads');
    dlEl.innerHTML = '';
    const addLink = (label, rel) => {
      if (!rel) return;
      const a = document.createElement('a');
      a.className = 'kw-card';
      a.href = `${API}/api/generated/${rel}`;
      a.textContent = `⬇  ${label}`;
      a.target = '_blank';
      a.style.textDecoration = 'none';
      a.style.display = 'block';
      dlEl.appendChild(a);
    };
    addLink('Resume (PDF)',       data.resume_pdf_rel);
    addLink('Cover Letter (PDF)', data.cover_letter_pdf_rel);
    addLink('Resume (.docx)',     data.resume_docx_rel);
    addLink('Cover Letter (.docx)', data.cover_letter_docx_rel);

    // Meta line
    const metaParts = [];
    if (data.body_ordering) metaParts.push(`Ordering: ${data.body_ordering}`);
    if (typeof data.used_passion_statement === 'boolean') {
      metaParts.push(`Passion paragraph: ${data.used_passion_statement ? 'included' : 'skipped'}`);
    }
    if (data.resume_tightness > 0) {
      metaParts.push(`Resume auto-shrunk (level ${data.resume_tightness}) to fit one page`);
    }
    if (data.cover_letter_tightness > 0) {
      metaParts.push(`Cover letter auto-shrunk (level ${data.cover_letter_tightness}) to fit one page`);
    }
    if (typeof data.jd_chars === 'number') {
      const jdLabel = data.jd_chars < 800
        ? `⚠ JD fetch returned only ${data.jd_chars} chars — keywords inferred, not extracted`
        : `JD fetched: ${data.jd_chars} chars`;
      metaParts.push(jdLabel);
    }
    if (data.pdf_error) metaParts.push(`⚠ PDF conversion failed — .docx only. (${data.pdf_error})`);
    document.getElementById('tMeta').textContent = metaParts.join(' · ');

    // Render ATS keywords
    const kwEl = document.getElementById('tKeywords');
    kwEl.innerHTML = '';
    const keywords = data.ats_keywords || [];
    if (keywords.length === 0) {
      const span = document.createElement('span');
      span.textContent = '(No keywords extracted.)';
      span.style.opacity = '0.6';
      kwEl.appendChild(span);
    } else {
      keywords.forEach(k => {
        const chip = document.createElement('span');
        chip.className = 'kw-card';
        chip.textContent = k;
        chip.style.display = 'inline-block';
        chip.style.margin = '2px 4px 2px 0';
        kwEl.appendChild(chip);
      });
    }

    // Render edit summary + audit lists (shared helper)
    const renderList = (elId, items, emptyMsg) => {
      const el = document.getElementById(elId);
      el.innerHTML = '';
      if (!items || items.length === 0) {
        const li = document.createElement('li');
        li.textContent = emptyMsg;
        li.style.opacity = '0.6';
        el.appendChild(li);
      } else {
        items.forEach(c => {
          const li = document.createElement('li');
          li.textContent = c;
          el.appendChild(li);
        });
      }
    };
    renderList('tChanges',     data.changes_summary,         '(No edits reported.)');
    renderList('tResumeAudit', data.resume_audit_notes,      '(No audit findings.)');
    renderList('tCoverAudit',  data.cover_letter_audit_notes,'(No audit findings.)');

    document.getElementById('tCoverLetter').textContent = data.cover_letter_preview || '';

    document.getElementById('tailorLoading').hidden = true;
    document.getElementById('tailorContent').hidden = false;

  } catch (e) {
    showTailorError('Network error: ' + e.message);
  }
}

function showTailorError(msg) {
  document.getElementById('tailorLoading').hidden = true;
  const el = document.getElementById('tailorError');
  el.textContent = msg;
  el.hidden = false;
}

function closeTailorModal() {
  document.getElementById('tailorOverlay').hidden = true;
}

function bindTailorModal() {
  document.getElementById('tailorModalClose').addEventListener('click', closeTailorModal);
  document.getElementById('tailorOverlay').addEventListener('click', e => {
    if (e.target === document.getElementById('tailorOverlay')) closeTailorModal();
  });

  document.getElementById('btnCopyCL').addEventListener('click', () => {
    const text = document.getElementById('tCoverLetter').textContent;
    navigator.clipboard.writeText(text).then(() => {
      const btn = document.getElementById('btnCopyCL');
      btn.textContent = 'Copied!';
      btn.classList.add('copied');
      setTimeout(() => {
        btn.textContent = 'Copy';
        btn.classList.remove('copied');
      }, 2000);
    });
  });
}

// ── Keyboard ──────────────────────────────────────────────────────────────────

function bindKeyboard() {
  document.addEventListener('keydown', e => {
    if (e.key === 'Escape') {
      if (!document.getElementById('tailorOverlay').hidden) { closeTailorModal(); return; }
      if (!document.getElementById('jobOverlay').hidden)    { closeJobModal();    return; }
      if (!document.getElementById('addOverlay').hidden)      closeAddModal();
    }
  });
}

// ── Util ──────────────────────────────────────────────────────────────────────

function escHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

// Turn an ISO date (YYYY-MM-DD) into "Today", "Yesterday", or "Apr 17"
function formatLastScraped(iso) {
  if (!iso) return '—';
  const s = String(iso).slice(0, 10);
  const today = new Date(); today.setHours(0, 0, 0, 0);
  const d = new Date(s + 'T00:00:00');
  if (isNaN(d)) return s;
  const diffDays = Math.round((today - d) / (1000 * 60 * 60 * 24));
  if (diffDays === 0) return 'Today';
  if (diffDays === 1) return 'Yesterday';
  if (diffDays < 7)   return diffDays + 'd ago';
  return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
}
