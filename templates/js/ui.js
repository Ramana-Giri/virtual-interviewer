/* ═══════════════════════════════════════════════════
   PrepSpark — UI Utilities
   ═══════════════════════════════════════════════════ */

function showPage(id) {
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
  document.getElementById(id).classList.add('active');
}

function toast(msg, type = 'success') {
  const container = document.getElementById('toast-container');
  const t = document.createElement('div');
  t.className = `toast ${type}`;
  t.innerHTML = `<span>${type === 'success' ? '✓' : '✕'}</span> ${msg}`;
  container.appendChild(t);
  setTimeout(() => t.remove(), 4000);
}

function showError(el, msg) {
  el.textContent = msg;
  el.style.display = 'block';
}

function hideError(el) {
  el.style.display = 'none';
}

// Processing overlay steps
const PROC_STEPS = ['step-video', 'step-audio', 'step-timeline', 'step-ai'];
let stepTimer = null;

function showProcessing() {
  document.getElementById('processing-overlay').classList.add('active');
  PROC_STEPS.forEach(id => {
    const el = document.getElementById(id);
    el.classList.remove('done', 'active');
  });
  document.getElementById('step-video').classList.add('active');
  let i = 0;
  stepTimer = setInterval(() => {
    if (i < PROC_STEPS.length) {
      if (i > 0) document.getElementById(PROC_STEPS[i - 1]).classList.replace('active', 'done');
      if (document.getElementById(PROC_STEPS[i])) {
        document.getElementById(PROC_STEPS[i]).classList.add('active');
      }
      i++;
    }
  }, 4500);
}

function hideProcessing() {
  clearInterval(stepTimer);
  PROC_STEPS.forEach(id => {
    const el = document.getElementById(id);
    if (el) el.classList.add('done');
  });
  setTimeout(() => document.getElementById('processing-overlay').classList.remove('active'), 400);
}

function switchSidebar(tab) {
  document.querySelectorAll('.sidebar-tab').forEach((b, i) => {
    b.classList.toggle('active', (i === 0) === (tab === 'status'));
  });
  document.getElementById('panel-status').classList.toggle('active', tab === 'status');
  document.getElementById('panel-transcript').classList.toggle('active', tab === 'transcript');
}