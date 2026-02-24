/* ═══════════════════════════════════════════════════
   PrepSpark — Dashboard Module
   ═══════════════════════════════════════════════════ */

async function loadDashboard() {
  const user = state.user;
  if (!user) return;

  document.getElementById('dash-name').textContent = user.full_name || user.username;
  document.getElementById('dash-username').textContent = '@' + user.username;

  try {
    const res = await fetch(`${API}/my_interviews`, { headers: authHeaders() });
    const data = await res.json();
    renderDashboard(data.interviews || []);
  } catch (e) {
    console.error('Dashboard load failed:', e);
  }
}

function renderDashboard(interviews) {
  const grid = document.getElementById('dash-grid');
  grid.innerHTML = `
    <div class="dash-card new-interview-card" onclick="goToSetup()">
      <div class="new-interview-icon">＋</div>
      <div class="new-interview-label">Start a Practice Session</div>
    </div>
  `;

  interviews.forEach(iv => {
    const card = document.createElement('div');
    card.className = 'dash-card';
    const date = new Date(iv.start_time).toLocaleDateString('en-US', {
      year: 'numeric', month: 'short', day: 'numeric'
    });
    const scoreDisplay = iv.avg_score
      ? `<div class="dash-card-score">${iv.avg_score}</div>`
      : '';

    card.innerHTML = `
      ${scoreDisplay}
      <div class="dash-card-tag tag-practice">Practice</div>
      <div class="dash-card-name">${iv.candidate_name}</div>
      <div class="dash-card-role">${iv.target_role}</div>
      <div class="dash-card-date">${date} · #${iv.session_id}</div>
    `;
    card.onclick = () => loadReport(iv.session_id);
    grid.appendChild(card);
  });
}

function goToSetup() {
  if (state.user) {
    document.getElementById('setup-name').value = state.user.full_name || '';
    document.getElementById('setup-role').value = '';
  }
  document.getElementById('setup-error').style.display = 'none';
  showPage('setup-page');
}