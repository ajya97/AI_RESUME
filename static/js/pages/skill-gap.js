import { api } from '../core/api.js';
import { setBusy, showError, loading, toast, esc } from '../core/ui.js';
import { initResumePicker } from '../core/resume-picker.js';
import { renderSkillGap } from '../core/report-render.js';

const $ = id => document.getElementById(id);
const picker = await initResumePicker($('picker'));
api('/api/career/roles').then(d => { $('roles').innerHTML = d.roles.map(r => `<option value="${esc(r)}">`).join(''); }).catch(() => {});
$('runBtn').addEventListener('click', async () => {
  $('err').innerHTML = '';
  if (!picker.id) return showError($('err'), new Error('Please select or upload a resume first.'));
  if ($('role').value.trim().length < 2) return showError($('err'), new Error('Please enter a target role.'));
  setBusy($('runBtn'), true, 'Analyzing…'); loading($('result'), 'Building your skill-gap plan…');
  try {
    const d = await api('/api/skill-gap', { method: 'POST', idempotent: true, json: { resume_id: picker.id, target_role: $('role').value, requirements: $('reqs').value } });
    renderSkillGap($('result'), d.report);
    $('result').insertAdjacentHTML('afterbegin', `<div class="row row-between" style="margin-bottom:12px"><h2 style="margin:0">Result</h2><a class="btn btn-ghost btn-sm" href="/api/reports/${d.report.id}/export.pdf">⬇ Download PDF</a></div>`);
    toast(`Done — ${d.credits.charged} credits used.`, 'success');
  } catch (e) { $('result').innerHTML = ''; showError($('err'), e); } finally { setBusy($('runBtn'), false); }
});
