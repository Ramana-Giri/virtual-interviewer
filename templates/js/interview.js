/* ═══════════════════════════════════════════════════
   PrepSpark — Interview Room Module
   ═══════════════════════════════════════════════════ */

const Q_TYPES = {
  1: 'intro',
  2: 'technical',
  3: 'technical',
  4: 'technical',
  5: 'behavioural'
};

const Q_TYPE_LABELS = {
  intro: 'Introduction',
  technical: 'Technical',
  behavioural: 'Behavioural'
};

// ─── Start New Interview ───
async function startInterview() {
  const name = document.getElementById('setup-name')?.value.trim();
  const role = document.getElementById('setup-role')?.value.trim();
  const errEl = document.getElementById('setup-error');
  if (errEl) errEl.style.display = 'none';

  if (!name || !role) {
    showError(errEl, 'Please enter your name and the target role.');
    return;
  }

  try {
    const res = await fetch(`${API}/start_interview`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...authHeaders() },
      body: JSON.stringify({ name, role })
    });
    const data = await res.json();
    if (!res.ok) { showError(errEl, data.error); return; }

    state.sessionId = data.session_id;
    state.currentQIndex = 1;
    state.currentQText = data.question;
    state.currentQType = 'intro';
    state.totalQ = 5;

    await initCamera();
    showPage('interview-page');
    setupInterviewUI(data);

    if (data.audio_b64) {
      await playAudio(data.audio_b64);
    } else {
      enableRecording();
    }
  } catch (e) {
    showError(errEl, 'Failed to start session. Is the server running?');
    console.error(e);
  }
}

// ─── Setup UI ───
function setupInterviewUI(data) {
  const qType = Q_TYPES[data.question_index] || data.question_type || 'technical';

  // Topbar
  const sessionBadge = document.getElementById('session-badge');
  const navRole = document.getElementById('nav-role');
  const setupRole = document.getElementById('setup-role');
  if (sessionBadge) sessionBadge.textContent = '#' + data.session_id;
  if (navRole && setupRole) navRole.textContent = setupRole.value;

  updateQuestionCard(data.question_index, data.question, qType);
  buildQPips(data.question_index);

  // Reset transcript log
  const log = document.getElementById('transcript-log');
  if (log) log.innerHTML = '<div class="iv-transcript-empty">Your answers will appear here after submission.</div>';

  setInterviewerStatus('Ready to ask', false);
}

function updateQuestionCard(index, text, type) {
  const labelEl = document.getElementById('q-label-text');
  const typeTag = document.getElementById('q-type-tag');
  const textEl = document.getElementById('q-text');
  const progressLabel = document.getElementById('iv-progress-label');

  if (labelEl) labelEl.textContent = `Question ${index} of 5`;
  if (progressLabel) progressLabel.textContent = `Question ${index} of 5`;
  if (typeTag) {
    typeTag.textContent = Q_TYPE_LABELS[type] || type;
    typeTag.className = `iv-q-type-badge ${type}`;
  }
  if (textEl) textEl.textContent = text;
}

function buildQPips(current) {
  const container = document.getElementById('q-pips');
  if (!container) return;
  container.innerHTML = '';
  for (let i = 1; i <= 5; i++) {
    const pip = document.createElement('div');
    pip.className = 'q-pip' + (i < current ? ' done' : i === current ? ' active' : '');
    pip.title = Q_TYPE_LABELS[Q_TYPES[i]] || '';
    container.appendChild(pip);
  }
}

function setInterviewerStatus(msg, isSpeaking) {
  const statusEl = document.getElementById('iv-interviewer-status');
  const ring = document.getElementById('iv-avatar-ring');
  const wave = document.getElementById('speaking-anim');
  const qCard = document.getElementById('question-card');

  if (statusEl) {
    statusEl.textContent = msg;
    statusEl.className = 'iv-interviewer-status' + (isSpeaking ? ' speaking' : '');
  }
  if (ring) ring.className = 'iv-avatar-ring' + (isSpeaking ? ' speaking' : '');
  if (wave) wave.className = 'iv-avatar-wave' + (isSpeaking ? ' active' : '');
  if (qCard) qCard.className = 'iv-question-card' + (isSpeaking ? ' speaking' : '');
}

// ─── Camera ───
async function initCamera() {
  const noCamera = document.getElementById('iv-no-camera');
  try {
    state.mediaStream = await navigator.mediaDevices.getUserMedia({ video: true, audio: true });
    const video = document.getElementById('candidate-video');
    if (video) video.srcObject = state.mediaStream;
    if (noCamera) noCamera.classList.add('hidden');

    const senCamera = document.getElementById('sen-camera');
    const senMic = document.getElementById('sen-mic');
    if (senCamera) { senCamera.textContent = 'Active'; senCamera.className = 'sensor-badge badge-ok'; }
    if (senMic) { senMic.textContent = 'Active'; senMic.className = 'sensor-badge badge-ok'; }
  } catch (e) {
    if (noCamera) noCamera.classList.remove('hidden');
    toast('Camera/microphone access denied. Please allow permissions.', 'error');
  }
}

// ─── TTS Playback ───
async function playAudio(base64mp3) {
  return new Promise((resolve) => {
    try {
      const bytes = atob(base64mp3);
      const arr = new Uint8Array(bytes.length);
      for (let i = 0; i < bytes.length; i++) arr[i] = bytes.charCodeAt(i);
      const blob = new Blob([arr], { type: 'audio/mpeg' });
      const url = URL.createObjectURL(blob);
      const audio = new Audio(url);

      state.isSpeaking = true;
      setInterviewerStatus('Speaking…', true);

      const recordBtn = document.getElementById('btn-record');
      if (recordBtn) recordBtn.disabled = true;

      const hintEl = document.getElementById('sidebar-hint');
      if (hintEl) hintEl.textContent = 'The AI interviewer is speaking. Recording will enable when they finish.';

      audio.onended = () => {
        state.isSpeaking = false;
        URL.revokeObjectURL(url);
        enableRecording();
        resolve();
      };
      audio.onerror = () => { resolve(); enableRecording(); };
      audio.play().catch(() => { resolve(); enableRecording(); });
    } catch (e) {
      resolve();
      enableRecording();
    }
  });
}

function enableRecording() {
  setInterviewerStatus('Waiting for your answer…', false);
  const recordBtn = document.getElementById('btn-record');
  if (recordBtn) recordBtn.disabled = false;
  const hintEl = document.getElementById('sidebar-hint');
  if (hintEl) hintEl.innerHTML = 'Press <strong>Start Recording</strong> to answer. When done, click <strong>Submit Answer</strong>.';
}

// ─── Recording ───
function toggleRecord() {
  if (state.isRecording) stopRecord();
  else startRecord();
}

function startRecord() {
  if (!state.mediaStream) { toast('Camera not ready. Please refresh.', 'error'); return; }

  state.recordedChunks = [];
  let options = {};
  try {
    options = { mimeType: 'video/webm;codecs=vp9,opus' };
    new MediaRecorder(state.mediaStream, options);
  } catch (e) { options = {}; }

  state.mediaRecorder = new MediaRecorder(state.mediaStream, options);
  state.mediaRecorder.ondataavailable = e => {
    if (e.data.size > 0) state.recordedChunks.push(e.data);
  };
  state.mediaRecorder.start(100);
  state.isRecording = true;

  const btn = document.getElementById('btn-record');
  const labelEl = document.getElementById('btn-record-label');
  const recBadge = document.getElementById('rec-indicator');
  const timerEl = document.getElementById('timer-badge');
  const liveIndicator = document.getElementById('iv-live-indicator');
  const submitBtn = document.getElementById('btn-submit');

  if (btn) btn.classList.add('recording');
  if (labelEl) labelEl.textContent = 'Stop Recording';
  if (recBadge) recBadge.classList.add('active');
  if (liveIndicator) liveIndicator.classList.add('active');
  if (submitBtn) submitBtn.classList.remove('visible');

  setInterviewerStatus('Listening to your answer…', false);

  state.recSeconds = 0;
  state.recordTimer = setInterval(() => {
    state.recSeconds++;
    const m = Math.floor(state.recSeconds / 60);
    const s = state.recSeconds % 60;
    if (timerEl) timerEl.textContent = `${m}:${s.toString().padStart(2, '0')}`;
  }, 1000);
}

function stopRecord() {
  if (!state.mediaRecorder) return;
  state.mediaRecorder.stop();
  state.isRecording = false;
  clearInterval(state.recordTimer);

  const btn = document.getElementById('btn-record');
  const labelEl = document.getElementById('btn-record-label');
  const recBadge = document.getElementById('rec-indicator');
  const liveIndicator = document.getElementById('iv-live-indicator');
  const submitBtn = document.getElementById('btn-submit');

  if (btn) btn.classList.remove('recording');
  if (labelEl) labelEl.textContent = 'Re-record';
  if (recBadge) recBadge.classList.remove('active');
  if (liveIndicator) liveIndicator.classList.remove('active');
  if (submitBtn) submitBtn.classList.add('visible');

  setInterviewerStatus('Review your answer, then submit.', false);

  const hintEl = document.getElementById('sidebar-hint');
  if (hintEl) hintEl.innerHTML = 'Happy with your answer? Click <strong>Submit Answer</strong>. Or press <strong>Re-record</strong> to try again.';
}

// ─── Submit Response ───
async function submitResponse() {
  if (state.recordedChunks.length === 0) {
    toast('Please record your answer first.', 'error');
    return;
  }

  const blob = new Blob(state.recordedChunks, { type: 'video/webm' });
  const formData = new FormData();
  formData.append('video', blob, 'response.webm');
  formData.append('session_id', state.sessionId);
  formData.append('question_index', state.currentQIndex);
  formData.append('question_text', state.currentQText);
  formData.append('question_type', state.currentQType);

  showProcessing();

  try {
    const res = await fetch(`${API}/submit_response`, {
      method: 'POST',
      headers: authHeaders(),
      body: formData
    });
    const data = await res.json();
    hideProcessing();

    if (!res.ok) { toast(data.error || 'Submission failed.', 'error'); return; }

    addToTranscript(state.currentQIndex, state.currentQText, state.currentQType, data.transcript || '');

    if (data.status === 'completed') {
      toast('Session complete! Loading your report…', 'success');
      // Stop camera stream
      if (state.mediaStream) {
        state.mediaStream.getTracks().forEach(t => t.stop());
        state.mediaStream = null;
      }
      setTimeout(() => loadReport(state.sessionId), 1200);
    } else {
      const nextIndex = data.next_index;
      const nextType = Q_TYPES[nextIndex] || 'technical';

      state.currentQIndex = nextIndex;
      state.currentQText = data.next_question;
      state.currentQType = nextType;
      state.recordedChunks = [];

      updateQuestionCard(nextIndex, data.next_question, nextType);
      buildQPips(nextIndex);

      const submitBtn = document.getElementById('btn-submit');
      const recordBtn = document.getElementById('btn-record');
      const labelEl = document.getElementById('btn-record-label');
      const timerEl = document.getElementById('timer-badge');

      if (submitBtn) submitBtn.classList.remove('visible');
      if (recordBtn) recordBtn.disabled = true;
      if (labelEl) labelEl.textContent = 'Start Recording';
      if (timerEl) timerEl.textContent = '0:00';

      if (data.audio_b64) {
        await playAudio(data.audio_b64);
      } else {
        enableRecording();
      }
    }
  } catch (e) {
    hideProcessing();
    toast('Network error submitting response.', 'error');
    console.error(e);
  }
}

// ─── Transcript Log ───
function addToTranscript(qIndex, question, qType, transcript) {
  const log = document.getElementById('transcript-log');
  if (!log) return;

  const emptyEl = log.querySelector('.iv-transcript-empty');
  if (emptyEl) emptyEl.remove();

  const typeColors = { intro: 'var(--accent-2)', technical: 'var(--accent)', behavioural: 'var(--warn)' };
  const color = typeColors[qType] || 'var(--accent)';
  const typeLabel = Q_TYPE_LABELS[qType] || qType;

  const item = document.createElement('div');
  item.className = 'iv-transcript-item';
  item.innerHTML = `
    <div class="iv-transcript-item-meta">
      <span class="iv-transcript-item-q" style="color:${color}">Q${qIndex}</span>
      <span style="font-size:10px;font-family:'DM Mono',monospace;color:${color};background:rgba(255,255,255,0.04);padding:1px 7px;border-radius:100px;border:1px solid rgba(255,255,255,0.06);">${typeLabel}</span>
    </div>
    <div class="iv-transcript-item-text">${transcript || '(No transcription recorded)'}</div>
  `;
  log.appendChild(item);
  // Scroll to bottom
  log.scrollTop = log.scrollHeight;
}