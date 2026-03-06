/* ═══════════════════════════════════════════════════
   PrepSpark — Dashboard Module
   Separates COMPLETED sessions (report) from
   IN_PROGRESS sessions (resume).
   ═══════════════════════════════════════════════════ */

// Maps ISO 639-1 codes to flag emoji + short name for dashboard display
const LANG_FLAG_LABELS = {
  hi: '🇮🇳 Hindi',    ta: '🇮🇳 Tamil',    te: '🇮🇳 Telugu',
  bn: '🇮🇳 Bengali',  kn: '🇮🇳 Kannada',  ml: '🇮🇳 Malayalam',
  mr: '🇮🇳 Marathi',  pa: '🇮🇳 Punjabi',  gu: '🇮🇳 Gujarati',
  ur: '🇮🇳 Urdu',     en: '🌐 English',   es: '🌐 Spanish',
  fr: '🌐 French',    de: '🌐 German',    ar: '🌐 Arabic',
  ja: '🌐 Japanese',  zh: '🌐 Chinese',   ko: '🌐 Korean',
  pt: '🌐 Portuguese',ru: '🌐 Russian',   auto: '🌐 Auto',
};

function getLangLabel(code) {
  if (!code || code === 'en') return null; // don't clutter cards with English
  return LANG_FLAG_LABELS[code] || code.toUpperCase();
}

async function loadDashboard() {
  const user = state.user;
  if (!user) return;

  const nameEl = document.getElementById('dash-name');
  const userEl = document.getElementById('dash-username');
  if (nameEl) nameEl.textContent = user.full_name || user.username;
  if (userEl) userEl.textContent = '@' + user.username;

  try {
    const res = await fetch(`${API}/my_interviews`, { headers: authHeaders() });
    const data = await res.json();
    renderDashboard(data.interviews || []);
  } catch (e) {
    console.error('Dashboard load failed:', e);
  }
}

function renderDashboard(interviews) {
  const completedGrid     = document.getElementById('dash-grid');
  const inProgressGrid    = document.getElementById('dash-inprogress-grid');
  const inProgressSection = document.getElementById('dash-inprogress-section');
  const completedSection  = document.getElementById('dash-completed-section');

  if (!completedGrid) return;

  // Separate by status
  const completed  = interviews.filter(iv => iv.status === 'COMPLETED');
  const inProgress = interviews.filter(iv => iv.status !== 'COMPLETED');

  // ── IN-PROGRESS section ──
  if (inProgress.length > 0 && inProgressGrid && inProgressSection) {
    inProgressSection.style.display = 'block';
    inProgressGrid.innerHTML = '';
    inProgress.forEach(iv => {
      const card     = document.createElement('div');
      card.className = 'dash-card resumable';
      const date     = new Date(iv.start_time).toLocaleDateString('en-US', {
        year: 'numeric', month: 'short', day: 'numeric'
      });
      const answered  = iv.response_count || 0;
      // ── NEW: show language pill if not English ──
      const langLabel = getLangLabel(iv.language);
      const langPill  = langLabel
        ? `<span style="font-size:11px;font-family:'DM Mono',monospace;
                        color:var(--accent-2);background:rgba(255,255,255,0.04);
                        border:1px solid rgba(255,255,255,0.07);border-radius:100px;
                        padding:1px 8px;margin-left:6px;">${langLabel}</span>`
        : '';

      card.innerHTML = `
        <div class="dash-card-tag" style="background:rgba(245,166,35,0.12);color:var(--warn);">In Progress</div>
        <div class="dash-card-name">${iv.candidate_name}${langPill}</div>
        <div class="dash-card-role">${iv.target_role}</div>
        <div class="dash-card-date">${date} · ${answered}/5 questions answered</div>
        <div class="dash-card-resume-btn">▶ Resume Session</div>
      `;
      card.onclick = () => resumeInterview(iv.session_id);
      inProgressGrid.appendChild(card);
    });
  } else if (inProgressSection) {
    inProgressSection.style.display = 'none';
  }

  // ── COMPLETED section ──
  completedGrid.innerHTML = `
    <div class="dash-card new-interview-card" onclick="goToSetup()">
      <div class="new-interview-icon">＋</div>
      <div class="new-interview-label">Start a Practice Session</div>
    </div>
  `;

  if (completed.length === 0 && completedSection) {
    completedGrid.innerHTML += `
      <div style="grid-column:1/-1;text-align:center;padding:48px 0;color:var(--text-dim);font-size:14px;font-family:'DM Mono',monospace;">
        No completed sessions yet. Start your first practice!
      </div>
    `;
  }

  completed.forEach(iv => {
    const card = document.createElement('div');
    card.className = 'dash-card';
    const date  = new Date(iv.start_time).toLocaleDateString('en-US', {
      year: 'numeric', month: 'short', day: 'numeric'
    });
    const scoreDisplay = iv.avg_score != null
      ? `<div class="dash-card-score" style="color:${iv.avg_score >= 7 ? 'var(--accent-2)' : iv.avg_score >= 5 ? 'var(--warn)' : 'var(--danger)'}">${iv.avg_score}</div>`
      : '';

    // ── NEW: show language pill on completed cards too ──
    const langLabel = getLangLabel(iv.language);
    const langPill  = langLabel
      ? `<span style="font-size:11px;font-family:'DM Mono',monospace;
                      color:var(--text-muted);background:rgba(255,255,255,0.04);
                      border:1px solid rgba(255,255,255,0.07);border-radius:100px;
                      padding:1px 8px;margin-left:6px;">${langLabel}</span>`
      : '';

    card.innerHTML = `
      ${scoreDisplay}
      <div class="dash-card-tag tag-practice">Completed</div>
      <div class="dash-card-name">${iv.candidate_name}${langPill}</div>
      <div class="dash-card-role">${iv.target_role}</div>
      <div class="dash-card-date">${date} · #${iv.session_id}</div>
    `;
    card.onclick = () => loadReport(iv.session_id);
    completedGrid.appendChild(card);
  });
}

function goToSetup() {
  if (state.user) {
    const nameEl = document.getElementById('setup-name');
    const roleEl = document.getElementById('setup-role');
    if (nameEl) nameEl.value = state.user.full_name || '';
    if (roleEl) roleEl.value = '';
  }
  // Reset language selector to English default each time
  const langEl = document.getElementById('setup-language');
  if (langEl) langEl.value = 'en';

  const errEl = document.getElementById('setup-error');
  if (errEl) errEl.style.display = 'none';
  showPage('setup-page');
}

// ─── Resume an incomplete interview ───
async function resumeInterview(sessionId) {
  try {
    const res = await fetch(`${API}/resume_interview?session_id=${sessionId}`, {
      headers: authHeaders()
    });
    const data = await res.json();
    if (!res.ok) { toast(data.error || 'Could not resume session.', 'error'); return; }

    // Restore state — including language from the session
    state.sessionId     = data.session_id;
    state.currentQIndex = data.next_question_index;
    state.currentQText  = data.next_question;
    state.currentQType  = data.next_question_type;
    state.totalQ        = 5;
    state.language      = data.language || 'en';   // ← NEW: restore language

    // Pre-fill setup fields so nav-role shows correctly
    const nameEl = document.getElementById('setup-name');
    const roleEl = document.getElementById('setup-role');
    if (nameEl) nameEl.value = data.candidate_name;
    if (roleEl) roleEl.value = data.target_role;

    showPage('interview-page');
    setupInterviewUI({
      session_id:      data.session_id,
      question_index:  data.next_question_index,
      question:        data.next_question,
      question_type:   data.next_question_type,
      total_questions: 5,
      language:        data.language || 'en',      // ← NEW: pass to UI setup
    });

    // Restore transcript sidebar with already-answered questions
    if (data.completed_responses && data.completed_responses.length > 0) {
      data.completed_responses.forEach(r => {
        addToTranscript(r.question_index, r.question_text, r.question_type || 'technical', r.transcript);
      });
    }

    if (data.audio_b64) {
      await playAudio(data.audio_b64);
    } else {
      enableRecording();
    }

    toast(`Resuming from question ${data.next_question_index}…`, 'success');
  } catch (e) {
    toast('Failed to resume session. Is the server running?', 'error');
    console.error(e);
  }
}