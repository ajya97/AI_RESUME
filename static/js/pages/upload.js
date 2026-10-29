import { api, uploadAndAnalyze, analyzeResume } from '../core/api.js';
import { esc, fmtSize, fmtDate, toast, setBusy, showError, confirmDialog } from '../core/ui.js';
import { renderAts } from '../core/ats-render.js';

const $ = id => document.getElementById(id);
let file = null;
const COST = 100;

const drop = $('dropZone'), input = $('fileInput'), chip = $('fileChip'), btn = $('analyzeBtn');
drop.addEventListener('click', () => input.click());
drop.addEventListener('keydown', e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); input.click(); } });
['dragenter', 'dragover'].forEach(ev => drop.addEventListener(ev, e => { e.preventDefault(); drop.classList.add('drag'); }));
['dragleave', 'drop'].forEach(ev => drop.addEventListener(ev, e => { e.preventDefault(); drop.classList.remove('drag'); }));
drop.addEventListener('drop', e => pick(e.dataTransfer.files[0]));
input.addEventListener('change', () => pick(input.files[0]));
$('fileRemove').addEventListener('click', () => reset());

function pick(f) {
  if (!f) return;
  $('uploadError').innerHTML = '';
  if (!/\.pdf$/i.test(f.name)) return showError($('uploadError'), new Error('Only PDF files are allowed.'));
  if (f.size > 5 * 1024 * 1024) return showError($('uploadError'), new Error('File is too large. Maximum size is 5 MB.'));
  file = f; drop.classList.add('hidden'); chip.classList.remove('hidden');
  $('fileName').textContent = f.name; $('fileSize').textContent = fmtSize(f.size);
  btn.disabled = false; btn.textContent = `Analyze (${COST} credits)`;
}
function reset() {
  file = null; input.value = ''; drop.classList.remove('hidden'); chip.classList.add('hidden');
  btn.disabled = true; btn.textContent = 'Select a PDF to analyze'; $('progressWrap').classList.add('hidden');
}

function progress(on) {
  const wrap = $('progressWrap'); wrap.classList.toggle('hidden', !on);
  if (!on) return () => {};
  const steps = [[18, 'Uploading PDF…'], [38, 'Extracting resume content…'], [58, 'Calculating ATS score…'], [80, 'Running AI analysis…'], [94, 'Finalising…']];
  let i = 0; const tick = () => { if (i < steps.length) { $('progressFill').style.width = steps[i][0] + '%'; $('progressLabel').textContent = steps[i++][1]; } };
  tick(); const t = setInterval(tick, 1400);
  return () => { clearInterval(t); $('progressFill').style.width = '100%'; };
}

async function run(fn, button, resultsLabel) {
  $('uploadError').innerHTML = ''; $('results').innerHTML = '';
  setBusy(button, true, 'Analyzing…'); const done = progress(true);
  try {
    const d = await fn(); done();
    $('progressLabel').textContent = 'Analysis complete!';
    renderResults(d);
    toast(`Done — ${d.credits.charged} credits used.`, 'success');
  } catch (e) {
    done(); $('progressWrap').classList.add('hidden');
    showError($('uploadError'), e);
    if (e.data?.resume_id) toast('Resume saved. Credits refunded — you can retry from "Your resumes".', 'info', 7000);
  } finally { setBusy(button, false); if (button === btn && !file) btn.disabled = true; loadList(); }
}

btn.addEventListener('click', () => file && run(() => uploadAndAnalyze(file), btn));

function renderResults(d) {
  const root = $('results');
  root.innerHTML = `<div class="row row-between" style="margin-bottom:12px"><h2 style="margin:0">Analysis report</h2>
    <div class="row"><a class="btn btn-ghost btn-sm" href="/api/reports/${d.report_id}/export.pdf">⬇ Download PDF</a>
    <a class="btn btn-ghost btn-sm" href="/job-match?resume=${d.resume_id}">Match a job</a>
    <a class="btn btn-primary btn-sm" href="/interview?resume=${d.resume_id}">🎤 Mock interview</a></div></div><div id="atsRoot"></div>`;
  renderAts($('atsRoot'), d);
  root.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

async function loadList() {
  const box = $('resumeList');
  try {
    const { resumes } = await api('/api/resumes');
    box.innerHTML = resumes.length ? resumes.map(r => `<div class="list-item" data-id="${r.id}">
      <div style="min-width:0;flex:1"><div class="name" style="font-weight:700;word-break:break-all">${esc(r.filename)}</div>
        <div class="small dim">${esc(r.name || '')} · ${esc(fmtSize(r.size))} · ${esc(fmtDate(r.uploaded_at))}</div>
        ${r.latest_ats_score != null ? `<span class="badge" style="margin-top:6px">Last ATS: ${esc(r.latest_ats_score)}/100</span>` : '<span class="badge badge-warning" style="margin-top:6px">Not analyzed</span>'}</div>
      <div class="row"><button class="btn btn-primary btn-sm" data-act="analyze">Analyze</button>
        <a class="btn btn-ghost btn-sm" href="/resumes/${r.id}/file" aria-label="Download PDF">⬇</a>
        <button class="btn btn-danger btn-sm" data-act="delete" aria-label="Delete resume">🗑</button></div></div>`).join('')
      : '<div class="empty"><div class="empty-icon">📂</div>No resumes yet. Upload one to begin.</div>';
  } catch (e) { showError(box, e); }
}

$('resumeList').addEventListener('click', async e => {
  const b = e.target.closest('button[data-act]'); if (!b) return;
  const id = b.closest('[data-id]').dataset.id;
  if (b.dataset.act === 'analyze') run(() => analyzeResume(id), b);
  if (b.dataset.act === 'delete') {
    if (!await confirmDialog('Delete this resume? Its stored PDF and all reports, interviews and chats based on it will be permanently removed.')) return;
    try { await api(`/api/resumes/${id}`, { method: 'DELETE' }); toast('Resume deleted.', 'success'); $('results').innerHTML = ''; loadList(); }
    catch (err) { toast(err.message, 'error'); }
  }
});
loadList();
