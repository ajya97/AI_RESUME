import { api } from '../core/api.js';
import { esc, setBusy, showError, toast, fmtDate } from '../core/ui.js';
import { initResumePicker } from '../core/resume-picker.js';
import { renderInterviewSummary } from '../core/report-render.js';

const $ = id => document.getElementById(id);
let sid = null, questions = [], answered = new Map(), idx = 0, meta = {};

const screens = { setup: $('setup'), loading: $('loadingScr'), session: $('session'), results: $('results') };
const show = n => { Object.entries(screens).forEach(([k, el]) => el.classList.toggle('hidden', k !== n)); window.scrollTo({ top: 0, behavior: 'smooth' }); };

const picker = await initResumePicker($('picker'));

async function loadSessions() {
  try {
    const { sessions } = await api('/api/interview/sessions');
    $('sessions').innerHTML = sessions.length ? sessions.slice(0, 8).map(s => `<div class="list-item" style="justify-content:space-between;align-items:center">
      <div><b>${esc(s.target_role || 'Interview session')}</b><div class="small dim">${esc(fmtDate(s.created_at))} · ${s.answered}/${s.total_questions} · ${esc(s.difficulty)}</div></div>
      ${s.status === 'completed' ? `<a class="btn btn-ghost btn-sm" href="/history/interview/${s.id}">Review</a>` : `<button class="btn btn-primary btn-sm" data-continue="${s.id}">Continue</button>`}</div>`).join('')
      : '<div class="empty"><div class="empty-icon">🎤</div>No sessions yet.</div>';
  } catch (e) { showError($('sessions'), e); }
}
$('sessions').addEventListener('click', async e => {
  const b = e.target.closest('[data-continue]'); if (!b) return;
  try { const { session } = await api(`/api/interview/${b.dataset.continue}`); resumeSession(session); } catch (err) { toast(err.message, 'error'); }
});

function resumeSession(s) {
  sid = s.id; questions = s.questions; meta = s; answered = new Map((s.answers || []).map(a => [a.index, a]));
  idx = questions.findIndex((_, i) => !answered.has(i)); if (idx < 0) return finish();
  show('session'); renderQuestion();
}

$('startBtn').addEventListener('click', async () => {
  $('setupErr').innerHTML = '';
  if (!picker.id) return showError($('setupErr'), new Error('Please select or upload a resume first.'));
  setBusy($('startBtn'), true, 'Starting…'); show('loading');
  try {
    const d = await api('/api/generate-questions', { method: 'POST', idempotent: true,
      json: { resume_id: picker.id, difficulty: $('difficulty').value, category: $('focus').value, job_description: $('jd').value.trim() || undefined } });
    sid = d.session_id; questions = d.questions; answered = new Map(); idx = 0; meta = { candidate_name: d.candidate_name };
    show('session'); renderQuestion();
  } catch (e) { show('setup'); showError($('setupErr'), e); } finally { setBusy($('startBtn'), false); }
});

function updateTop() {
  const total = questions.length, done = answered.size;
  $('progLabel').textContent = `Question ${Math.min(idx + 1, total)} of ${total} · ${done} answered`;
  $('progFill').style.width = Math.round((done / total) * 100) + '%';
  const scores = [...answered.values()].map(a => a.score);
  $('avgBadge').textContent = scores.length ? `Avg ${(scores.reduce((a, b) => a + b, 0) / scores.length).toFixed(1)}/10` : 'Avg —';
}
function renderQuestion() {
  const q = questions[idx]; updateTop();
  $('qCat').textContent = q.category; $('qDiff').textContent = q.difficulty; $('qText').textContent = q.question;
  $('qFollow').textContent = q.follow_up ? `💬 Possible follow-up: ${q.follow_up}` : '';
  $('answer').value = ''; $('charCount').textContent = '0 characters'; $('answer').disabled = false;
  $('answerArea').classList.remove('hidden'); $('feedback').classList.add('hidden'); $('sessErr').innerHTML = '';
  $('submitBtn').disabled = false; $('skipBtn').disabled = false;
}
$('answer').addEventListener('input', () => { $('charCount').textContent = `${$('answer').value.length} characters`; });

$('submitBtn').addEventListener('click', async () => {
  const answer = $('answer').value.trim(); $('sessErr').innerHTML = '';
  if (answer.length < 10) return showError($('sessErr'), new Error('Please write a more meaningful answer (at least a few sentences).'));
  setBusy($('submitBtn'), true, 'Evaluating…'); $('answer').disabled = true; $('skipBtn').disabled = true;
  try {
    const d = await api('/api/evaluate-answer', { method: 'POST', idempotent: true, json: { session_id: sid, index: idx, answer } });
    answered.set(idx, { score: d.evaluation.score }); updateTop(); renderFeedback(d.evaluation);
  } catch (e) { showError($('sessErr'), e); $('answer').disabled = false; $('skipBtn').disabled = false; } finally { setBusy($('submitBtn'), false); }
});
$('skipBtn').addEventListener('click', async () => {
  try { await api(`/api/interview/${sid}/skip`, { method: 'POST', json: { index: idx } }); answered.set(idx, { score: 0 }); next(); }
  catch (e) { showError($('sessErr'), e); }
});

function renderFeedback(ev) {
  $('answerArea').classList.add('hidden'); const f = $('feedback'); f.classList.remove('hidden');
  const last = idx >= questions.length - 1;
  f.innerHTML = `<div class="row row-between"><div><div class="fb-score gradient-text">${esc(ev.score)}/10</div><span class="badge">${esc(ev.score_label)}</span></div>
    <button class="btn btn-primary" id="nextBtn">${last ? 'See results' : 'Next question →'}</button></div>
    <div class="fb-grid" style="margin-top:12px"><div><b class="small">Strengths</b><ul>${(ev.strengths || []).map(s => `<li>${esc(s)}</li>`).join('') || '<li class="dim">None noted</li>'}</ul></div>
    <div><b class="small">To improve</b><ul>${(ev.weaknesses || []).map(s => `<li>${esc(s)}</li>`).join('') || '<li class="dim">None noted</li>'}</ul></div></div>
    <p>${esc(ev.detailed_feedback)}</p><div class="alert alert-info small"><b>Model answer:</b> ${esc(ev.model_answer)}</div>
    <div class="alert alert-success small"><b>Tip:</b> ${esc(ev.tips_for_improvement)}</div><div class="small dim">AI feedback is practice guidance, not an objective or employer-approved assessment.</div>`;
  f.querySelector('#nextBtn').addEventListener('click', next); f.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}
function next() { idx++; if (idx >= questions.length) finish(); else renderQuestion(); }

async function finish() {
  show('results');
  try { const { session } = await api(`/api/interview/${sid}`); renderInterviewSummary($('resultsBody'), session); }
  catch (e) { showError($('resultsBody'), e); }
}
$('retryBtn').addEventListener('click', async () => {
  try { const d = await api(`/api/interview/${sid}/retry`, { method: 'POST' }); sid = d.session_id; questions = d.questions; answered = new Map(); idx = 0; show('session'); renderQuestion(); }
  catch (e) { toast(e.message, 'error'); }
});
$('newBtn').addEventListener('click', () => { show('setup'); loadSessions(); });
loadSessions();
