/* ═══════════════════════════════════════════════════
   PrepSpark — Report Module
   Loads from cached DB report. Generates only if not yet cached.
   ═══════════════════════════════════════════════════ */

const Q_TYPE_MAP = {
  1: 'intro',
  2: 'technical',
  3: 'technical',
  4: 'technical',
  5: 'behavioural'
};

// Keys to exclude from the "Insights" section (shown elsewhere)
const SKIP_REPORT_KEYS = new Set([
  'recommendation', 'Recommendation', 'verdict', 'Verdict',
  'hiring_recommendation', 'Hiring Recommendation',
  'executive_summary', 'Executive Summary',
  'summary', 'Summary'
]);

const INSIGHT_LABELS = {
  technical_depth:        'Technical Depth',
  'Technical Depth':      'Technical Depth',
  technical_analysis:     'Technical Analysis',
  behavioral_signals:     'Behavioural Signals',
  behavioural_signals:    'Behavioural Signals',   // ← NEW key from updated backend
  'Behavioral Signals':   'Behavioural Signals',
  behavioral_analysis:    'Behavioural Analysis',
  communication:          'Communication Style',
  communication_style:    'Communication Style',   // ← NEW key from updated backend
  'Communication Style':  'Communication Style',
  key_observations:       'Key Observations',
  'Key Observations':     'Key Observations',
  strengths:              'Strengths',
  Strengths:              'Strengths',
  areas_for_improvement:  'Areas to Improve',
  'Areas for Improvement':'Areas to Improve',
  weaknesses:             'Weaknesses',
  Weaknesses:             'Weaknesses',
  content_analysis:       'Content Analysis',
  'Content Analysis':     'Content Analysis',
  mental_state:           'Mental State',
  'Mental State':         'Mental State',
  coaching_tips:          'Coaching Tips',         // ← NEW key from updated backend
  'Coaching Tips':        'Coaching Tips',
};

// Maps language codes to display names for the report header
const LANG_DISPLAY = {
  hi: 'Hindi — हिन्दी',    ta: 'Tamil — தமிழ்',   te: 'Telugu — తెలుగు',
  bn: 'Bengali — বাংলা',   kn: 'Kannada — ಕನ್ನಡ', ml: 'Malayalam — മലയാളം',
  mr: 'Marathi — मराठी',   pa: 'Punjabi — ਪੰਜਾਬੀ',gu: 'Gujarati — ગુજરાતી',
  ur: 'Urdu — اردو',       en: 'English',          es: 'Spanish',
  fr: 'French',             de: 'German',           ar: 'Arabic',
  ja: 'Japanese',           zh: 'Chinese',          ko: 'Korean',
  pt: 'Portuguese',         ru: 'Russian',
};

async function loadReport(sessionId) {
  showPage('report-page');
  // Reset
  document.getElementById('rpt-title').textContent = 'Loading report…';
  document.getElementById('score-grid').innerHTML = '';
  document.getElementById('analysis-grid').innerHTML = '';
  document.getElementById('qa-history').innerHTML = '';
  document.getElementById('executive-summary-body').textContent = '';
  document.getElementById('verdict-banner').className = 'verdict-banner verdict-neutral';
  document.getElementById('verdict-title').textContent = '…';
  document.getElementById('verdict-sub').textContent = '';

  // ── NEW: clear language badge if it exists from a previous load ──
  const existingLangBadge = document.getElementById('rpt-lang-badge');
  if (existingLangBadge) existingLangBadge.remove();

  try {
    const res = await fetch(`${API}/generate_report?session_id=${sessionId}`, {
      headers: authHeaders()
    });
    const data = await res.json();

    if (!res.ok) {
      document.getElementById('rpt-title').textContent = 'Error loading report';
      toast(data.error || 'Failed to load report.', 'error');
      return;
    }
    renderReport(data);
  } catch (e) {
    document.getElementById('rpt-title').textContent = 'Error loading report';
    toast('Network error loading report.', 'error');
    console.error(e);
  }
}

function renderReport(data) {
  const { candidate, role, session_id, start_time, responses, report, language } = data;

  // ── Header ──
  document.getElementById('rpt-title').textContent = candidate;
  document.getElementById('rpt-role').textContent  = role;
  document.getElementById('rpt-date').textContent  = start_time
    ? new Date(start_time).toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' })
    : 'Unknown date';
  document.getElementById('rpt-session').textContent = '#' + session_id;

  // ── NEW: Language badge next to session ID ──
  if (language && language !== 'en') {
    const langText = LANG_DISPLAY[language] || language.toUpperCase();
    const langBadge = document.createElement('span');
    langBadge.id = 'rpt-lang-badge';
    langBadge.style.cssText = [
      'display:inline-block',
      'font-family:"DM Mono",monospace',
      'font-size:11px',
      'color:var(--accent-2)',
      'background:rgba(255,255,255,0.04)',
      'border:1px solid rgba(255,255,255,0.08)',
      'border-radius:100px',
      'padding:2px 10px',
      'margin-left:8px',
      'vertical-align:middle',
    ].join(';');
    langBadge.textContent = '🌐 ' + langText;

    // Insert it after the session ID element
    const sessionEl = document.getElementById('rpt-session');
    if (sessionEl && sessionEl.parentNode) {
      sessionEl.parentNode.insertBefore(langBadge, sessionEl.nextSibling);
    }
  }

  // ── Verdict ──
  const verdictRaw = (
    report?.recommendation || report?.Recommendation ||
    report?.verdict || report?.Verdict ||
    report?.hiring_recommendation || report?.['Hiring Recommendation'] || ''
  ).toString().trim();

  const banner = document.getElementById('verdict-banner');
  const icon   = document.getElementById('verdict-icon');
  const vTitle = document.getElementById('verdict-title');
  const vSub   = document.getElementById('verdict-sub');

  banner.className = 'verdict-banner';

  if (!verdictRaw) {
    banner.classList.add('verdict-neutral');
    icon.textContent  = '📋';
    vTitle.textContent = 'Practice Session Complete';
    vSub.textContent   = 'Review the detailed feedback below.';
  } else {
    const v = verdictRaw.toLowerCase();
    const isHire = (v.includes('hire') || v.includes('yes') || v.includes('strong') || v.includes('ready'))
      && !v.includes('no hire') && !v.includes('not recommend');
    const isNoHire = v.includes('no hire') || v.includes('not recommend')
      || v.includes('reject') || v.includes('more practice');

    if (isHire) {
      banner.classList.add('verdict-hire');
      icon.textContent   = '✅';
      vTitle.textContent = 'Interview-Ready';
    } else if (isNoHire) {
      banner.classList.add('verdict-no-hire');
      icon.textContent   = '📌';
      vTitle.textContent = 'More Practice Recommended';
    } else {
      banner.classList.add('verdict-training');
      icon.textContent   = '📈';
      vTitle.textContent = 'Getting There — Keep Practising';
    }
    vSub.textContent = verdictRaw;
  }

  // ── Executive Summary ── (clean prose, not JSON)
  const execSummary =
    report?.executive_summary || report?.['Executive Summary'] ||
    report?.summary || report?.Summary || null;

  const summaryEl = document.getElementById('executive-summary-body');
  if (execSummary && typeof execSummary === 'string') {
    summaryEl.textContent = execSummary;
  } else if (execSummary && typeof execSummary === 'object') {
    summaryEl.textContent = Object.values(execSummary).join(' ');
  } else {
    document.getElementById('exec-summary-section').style.display = 'none';
  }

  // ── Scores ──
  const scoreGrid = document.getElementById('score-grid');
  scoreGrid.innerHTML = '';
  let totalScore = 0;

  responses.forEach(r => {
    const s   = r.ai_score || 0;
    totalScore += s;
    const cls = s >= 8 ? 'high' : s >= 5 ? 'mid' : 'low';
    const card = document.createElement('div');
    card.className = 'score-card';
    card.innerHTML = `
      <div class="score-q-label">Question ${r.question_index}</div>
      <div class="score-number ${cls}">${s}<span style="font-size:18px;opacity:0.4">/10</span></div>
      <div class="score-bar ${cls}" style="width:0" data-w="${s * 10}%"></div>
    `;
    scoreGrid.appendChild(card);
  });

  // Overall card
  const avg    = responses.length ? (totalScore / responses.length).toFixed(1) : 0;
  const avgCls = avg >= 8 ? 'high' : avg >= 5 ? 'mid' : 'low';
  const overallCard = document.createElement('div');
  overallCard.className = 'score-card';
  overallCard.innerHTML = `
    <div class="score-q-label">Overall Avg</div>
    <div class="score-number ${avgCls}">${avg}<span style="font-size:18px;opacity:0.4">/10</span></div>
    <div class="score-bar ${avgCls}" style="width:0" data-w="${avg * 10}%"></div>
  `;
  scoreGrid.appendChild(overallCard);
  setTimeout(() => {
    document.querySelectorAll('.score-bar').forEach(b => { b.style.width = b.dataset.w; });
  }, 100);

  // ── Insights Grid (everything except summary/verdict) ──
  const analysisGrid = document.getElementById('analysis-grid');
  analysisGrid.innerHTML = '';

  if (report && typeof report === 'object') {
    Object.entries(report).forEach(([key, value]) => {
      if (SKIP_REPORT_KEYS.has(key) || !value) return;
      const label = INSIGHT_LABELS[key] || key.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());

      let content = '';
      if (typeof value === 'string') {
        content = value;
      } else if (Array.isArray(value)) {
        content = value.map(item =>
          typeof item === 'string'
            ? `• ${item}`
            : `• ${JSON.stringify(item)}`
        ).join('\n');
      } else if (typeof value === 'object') {
        content = Object.entries(value)
          .map(([k, v]) => `${k.replace(/_/g, ' ')}: ${v}`)
          .join('\n');
      }

      if (!content) return;
      const card = document.createElement('div');
      card.className = 'analysis-card';
      card.innerHTML = `
        <div class="analysis-card-title">${label}</div>
        <div class="analysis-card-body">${content}</div>
      `;
      analysisGrid.appendChild(card);
    });
  }

  if (analysisGrid.children.length === 0) {
    document.getElementById('insights-section').style.display = 'none';
  }

  // ── Q&A Transcript & Feedback ──
  const qaHistory = document.getElementById('qa-history');
  qaHistory.innerHTML = '';

  responses.forEach(r => {
    const s          = r.ai_score || 0;
    const scoreColor = s >= 8 ? 'var(--score-high)' : s >= 5 ? 'var(--score-mid)' : 'var(--score-low)';
    const qType      = Q_TYPE_MAP[r.question_index] || 'technical';
    const qTypeLabel = { intro: 'Introduction', technical: 'Technical', behavioural: 'Behavioural' }[qType];

    // Audio & video behavioral chips
    let chips = '';
    try {
      const am = typeof r.audio_metrics === 'string' ? JSON.parse(r.audio_metrics) : (r.audio_metrics || {});
      if (am.wpm)                    chips += `<span class="beh-chip">${am.wpm} WPM</span>`;
      if (am.jitter_percent != null) chips += `<span class="beh-chip">Jitter ${am.jitter_percent}%</span>`;
      if (am.avg_pitch_hz)           chips += `<span class="beh-chip">${am.avg_pitch_hz} Hz</span>`;
    } catch (e) {}
    try {
      const vm = typeof r.video_metrics === 'string' ? JSON.parse(r.video_metrics) : (r.video_metrics || {});
      if (vm.gaze_screen_pct != null) chips += `<span class="beh-chip">Eye contact ${vm.gaze_screen_pct}%</span>`;
      if (vm.dominant_emotion)        chips += `<span class="beh-chip">${vm.dominant_emotion}</span>`;
      if (vm.blink_rate)              chips += `<span class="beh-chip">${vm.blink_rate} blinks/min</span>`;
    } catch (e) {}

    const item = document.createElement('div');
    item.className = 'qa-item';
    item.innerHTML = `
      <div class="qa-header" onclick="toggleQA(this)">
        <div class="qa-header-left">
          <div class="qa-q-meta">
            <span class="qa-q-num">Question ${r.question_index} of 5</span>
            <span class="qa-q-type ${qType}">${qTypeLabel}</span>
          </div>
          <div class="qa-q-text">${r.question || '—'}</div>
        </div>
        <div class="qa-score-pill" style="color:${scoreColor}">${s}/10</div>
      </div>
      <div class="qa-body">
        <div class="qa-section-label">Your Answer</div>
        <div class="qa-transcript">${r.transcript || '(No transcription recorded)'}</div>
        <div class="qa-section-label">Feedback</div>
        <div class="qa-feedback">${r.ai_feedback || '—'}</div>
        ${chips ? `<div class="behavioral-chips">${chips}</div>` : ''}
      </div>
    `;
    qaHistory.appendChild(item);
  });
}

function toggleQA(header) {
  const body = header.nextElementSibling;
  body.classList.toggle('open');
}