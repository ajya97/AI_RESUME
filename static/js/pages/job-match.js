import { api } from '../core/api.js';
import { setBusy, showError, loading, toast } from '../core/ui.js';
import { initResumePicker } from '../core/resume-picker.js';
import { renderJobMatch } from '../core/report-render.js';

const $ = id => document.getElementById(id);
const picker = await initResumePicker($('picker'));
$('jd').addEventListener('input', () => { $('jdCount').textContent = $('jd').value.length; });
$('runBtn').addEventListener('click', async () => {
  $('err').innerHTML = '';
  if (!picker.id) return showError($('err'), new Error('Please select or upload a resume first.'));
  if ($('jd').value.trim().length < 40) return showError($('err'), new Error('Please paste a longer job description (at least 40 characters).'));
  setBusy($('runBtn'), true, 'Comparing…'); loading($('result'), 'Comparing your resume with the job…');
  try {
    const d = await api('/api/job-match', { method: 'POST', json: { resume_id: picker.id, job_description: $('jd').value }, idempotent: true });
    renderJobMatch($('result'), d.report);
    $('result').insertAdjacentHTML('afterbegin', `<div class="row row-between" style="margin-bottom:12px"><h2 style="margin:0">Result</h2><a class="btn btn-ghost btn-sm" href="/api/reports/${d.report.id}/export.pdf">⬇ Download PDF</a></div>`);
    toast(`Done — ${d.credits.charged} credits used.`, 'success');
  } catch (e) { $('result').innerHTML = ''; showError($('err'), e); } finally { setBusy($('runBtn'), false); }
});
