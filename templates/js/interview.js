/* ═══════════════════════════════════════════════════
   PrepSpark — Interview Room Module
   ═══════════════════════════════════════════════════ */

/* Question type map: based on index what type each question is.
   Index 1 = Intro, 2-4 = Technical, 5 = Behavioural.
   The LLM decides the actual question content, but we label them here. */
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

// ─── Start Interview ───
async function startInterview() {
  const name = document.getElementById('setup-name').value.trim();
  const role = document.getElementById('setup-role').value.trim();
  const errEl = document.getElementById('setup-error');
  errEl.style.display = 'none';

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
    state.currentQType = Q_TYPES[1];
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
  }
}

function setupInterviewUI(data) {
  const qType = Q_TYPES[data.question_index] || 'technical';
  document.getElementById('session-badge').textContent = '#' + data.session_id;
  document.getElementById('nav-role').textContent = document.getElementById('setup-role').value;
  updateQuestionCard(data.question_index, data.question, qType);
  document.getElementById('stat-q').textContent = `${data.question_index} / ${data.total_questions}`;
  document.getElementById('stat-status').textContent = 'Listening';
  buildQPips(data.question_index);
  // Reset transcript log
  document.getElementById('transcript-log').innerHTML = `
    <div style="color:var(--text-dim);font-family:'DM Mono',monospace;font-size:12px;text-align:center;padding:40px 0;">
      Transcript will appear here after each answer.
    </div>
  `;
}

function updateQuestionCard(index, text, type) {
  const label = document.getElementById('q-label-text');
  const tag = document.getElementById('q-type-tag');
  const qText = document.getElementById('q-text');

  if (label) label.textContent = `Question ${index} of 5`;
  if (tag) {
    tag.textContent = Q_TYPE_LABELS[type] || type;
    tag.className = `q-type-tag ${type}`;
  }
  if (qText) qText.textContent = text;
}

function buildQPips(current) {
  const container = document.getElementById('q-pips');
  container.innerHTML = '';
  for (let i = 1; i <= 5; i++) {
    const pip = document.createElement('div');
    pip.className = 'q-pip' + (i < current ? ' done' : i === current ? ' active' : '');
    pip.title = Q_TYPE_LABELS[Q_TYPES[i]] || '';
    container.appendChild(pip);
  }
}

// ─── Camera ───
async function initCamera() {
  try {
    state.mediaStream = await navigator.mediaDevices.getUserMedia({ video: true, audio: true });
    document.getElementById('candidate-video').srcObject = state.mediaStream;
    document.getElementById('sen-camera').textContent = 'Active';
    document.getElementById('sen-camera').className = 'sensor-badge badge-ok';
    document.getElementById('sen-mic').textContent = 'Active';
    document.getElementById('sen-mic').className = 'sensor-badge badge-ok';
  } catch (e) {
    toast('Camera/microphone access denied. Please allow permissions and refresh.', 'error');
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
      document.getElementById('speaking-anim').classList.add('active');
      document.getElementById('question-card').classList.add('speaking');
      document.getElementById('stat-status').textContent = 'Interviewer speaking…';
      document.getElementById('btn-record').disabled = true;
      document.getElementById('sidebar-hint').innerHTML =
        'The interviewer is speaking. The record button will enable once they finish.';

      audio.onended = () => {
        state.isSpeaking = false;
        document.getElementById('speaking-anim').classList.remove('active');
        document.getElementById('question-card').classList.remove('speaking');
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
  document.getElementById('stat-status').textContent = 'Ready to record';
  document.getElementById('btn-record').disabled = false;
  document.getElementById('sidebar-hint').innerHTML =
    'Press <strong style="color:var(--text)">Start Recording</strong> to answer. '
    + 'When done, click <strong style="color:var(--text)">Submit Answer</strong>.';
}

// ─── Recording ───
function toggleRecord() {
  if (state.isRecording) stopRecord();
  else startRecord();
}

function startRecord() {
  if (!state.mediaStream) { toast('Camera not ready. Please refresh.', 'error'); return; }

  state.recordedChunks = [];
  let options;
  try { options = { mimeType: 'video/webm;codecs=vp9,opus' }; new MediaRecorder(state.mediaStream, options); }
  catch (e) { options = {}; }

  state.mediaRecorder = new MediaRecorder(state.mediaStream, options);
  state.mediaRecorder.ondataavailable = e => { if (e.data.size > 0) state.recordedChunks.push(e.data); };
  state.mediaRecorder.start(100);
  state.isRecording = true;

  const btn = document.getElementById('btn-record');
  btn.classList.add('recording');
  document.getElementById('btn-record-label').textContent = 'Stop Recording';
  document.getElementById('rec-indicator').classList.add('active');
  document.getElementById('timer-badge').classList.add('active');
  document.getElementById('stat-status').textContent = 'Recording…';
  document.getElementById('btn-submit').classList.remove('visible');

  state.recSeconds = 0;
  state.recordTimer = setInterval(() => {
    state.recSeconds++;
    const m = Math.floor(state.recSeconds / 60);
    const s = state.recSeconds % 60;
    document.getElementById('timer-badge').textContent = `${m}:${s.toString().padStart(2, '0')}`;
  }, 1000);
}

function stopRecord() {
  if (!state.mediaRecorder) return;
  state.mediaRecorder.stop();
  state.isRecording = false;
  clearInterval(state.recordTimer);

  const btn = document.getElementById('btn-record');
  btn.classList.remove('recording');
  document.getElementById('btn-record-label').textContent = 'Re-record';
  document.getElementById('rec-indicator').classList.remove('active');
  document.getElementById('stat-status').textContent = 'Ready to submit';
  document.getElementById('btn-submit').classList.add('visible');
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

    // Add to sidebar transcript
    addToTranscript(state.currentQIndex, state.currentQText, state.currentQType, data.transcript || '');

    if (data.status === 'completed') {
      toast('Session complete! Generating your report…', 'success');
      setTimeout(() => loadReport(state.sessionId), 1500);
    } else {
      // Advance to next question
      const nextIndex = data.next_index;
      const nextType = Q_TYPES[nextIndex] || 'technical';

      state.currentQIndex = nextIndex;
      state.currentQText = data.next_question;
      state.currentQType = nextType;
      state.recordedChunks = [];

      updateQuestionCard(nextIndex, data.next_question, nextType);
      document.getElementById('stat-q').textContent = `${nextIndex} / 5`;
      document.getElementById('btn-submit').classList.remove('visible');
      document.getElementById('btn-record').disabled = true;
      document.getElementById('btn-record-label').textContent = 'Start Recording';
      document.getElementById('timer-badge').classList.remove('active');
      document.getElementById('timer-badge').textContent = '0:00';
      buildQPips(nextIndex);

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
  // Remove placeholder
  const placeholder = log.querySelector('[style*="text-align:center"]');
  if (placeholder) placeholder.remove();

  const typeLabel = Q_TYPE_LABELS[qType] || qType;
  const typeColors = { intro: 'var(--accent-2)', technical: 'var(--accent)', behavioural: 'var(--warn)' };
  const color = typeColors[qType] || 'var(--accent)';

  const item = document.createElement('div');
  item.style.cssText = 'margin-bottom:20px;padding-bottom:20px;border-bottom:1px solid var(--border)';
  item.innerHTML = `
    <div style="display:flex;align-items:center;gap:8px;margin-bottom:6px;">
      <span style="font-size:11px;font-family:'DM Mono',monospace;color:${color};text-transform:uppercase;letter-spacing:0.1em;">Q${qIndex}</span>
      <span style="font-size:10px;font-family:'DM Mono',monospace;color:${color};background:rgba(255,255,255,0.05);padding:1px 7px;border-radius:100px;">${typeLabel}</span>
    </div>
    <div style="font-size:13px;color:var(--text);margin-bottom:6px;font-weight:500;line-height:1.4;">${question}</div>
    <div style="font-size:12px;color:var(--text-muted);font-style:italic;line-height:1.6;">${transcript || '(No transcription)'}</div>
  `;
  log.appendChild(item);
}