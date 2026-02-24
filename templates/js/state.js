/* ═══════════════════════════════════════════════════
   PrepSpark — App State & Configuration
   ═══════════════════════════════════════════════════ */

const API = 'http://localhost:5000';

const APP_NAME = 'PrepSpark';

const state = {
  token: localStorage.getItem('psToken') || null,
  user: JSON.parse(localStorage.getItem('psUser') || 'null'),
  sessionId: null,
  currentQIndex: 1,
  currentQText: '',
  currentQType: 'intro',   // 'intro' | 'technical' | 'behavioural'
  totalQ: 5,
  mediaStream: null,
  mediaRecorder: null,
  recordedChunks: [],
  isRecording: false,
  recordTimer: null,
  recSeconds: 0,
  isSpeaking: false,
};

function authHeaders() {
  return { 'Authorization': `Bearer ${state.token}` };
}

function saveSession() {
  localStorage.setItem('psToken', state.token);
  localStorage.setItem('psUser', JSON.stringify(state.user));
}

function clearSession() {
  state.token = null;
  state.user = null;
  localStorage.removeItem('psToken');
  localStorage.removeItem('psUser');
}