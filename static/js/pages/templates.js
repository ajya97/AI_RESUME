import { api } from '../core/api.js';
import { esc, toast, setBusy } from '../core/ui.js';
import { initResumePicker } from '../core/resume-picker.js';

const $ = id => document.getElementById(id);
const TEXT = [['name', 'Full name'], ['email', 'Email'], ['phone', 'Phone'], ['location', 'Location'], ['linkedin', 'LinkedIn'], ['github', 'GitHub']];
const LISTS = [['summary', 'Summary', 'text'], ['skills', 'Skills (comma separated)', 'skills'], ['experience', 'Experience', 'entries'], ['projects', 'Projects', 'entries'],
  ['education', 'Education', 'entries'], ['certifications', 'Certifications (one per line)', 'lines'], ['achievements', 'Achievements (one per line)', 'lines']];
let rid = null, tpl = 'classic', content = {};

function buildEditor() {
  $('editor').innerHTML = TEXT.map(([k, l]) => `<div class="field"><label for="f_${k}">${l}</label><input type="text" id="f_${k}" data-k="${k}" maxlength="200" value="${esc(content[k] || '')}"></div>`).join('') +
    LISTS.map(([k, l, kind]) => {
      const v = content[k] ?? (kind === 'text' ? '' : []);
      const val = kind === 'text' ? v : kind === 'skills' ? v.join(', ') : kind === 'lines' ? v.join('\n') : v.join('\n\n');
      return `<div class="field"><label for="f_${k}">${l}</label><textarea id="f_${k}" data-k="${k}" data-kind="${kind}">${esc(val)}</textarea></div>`;
    }).join('');
}
function collect() {
  const c = {};
  document.querySelectorAll('#editor [data-k]').forEach(el => {
    const k = el.dataset.k, kind = el.dataset.kind, v = el.value;
    if (!kind) c[k] = v; else if (kind === 'text') c[k] = v;
    else if (kind === 'skills') c[k] = v.split(',').map(s => s.trim()).filter(Boolean);
    else if (kind === 'lines') c[k] = v.split('\n').map(s => s.trim()).filter(Boolean);
    else c[k] = v.split(/\n\s*\n/).map(s => s.trim()).filter(Boolean);
  });
  return c;
}
function refreshPreview() {
  $('preview').src = `/resumes/${rid}/preview/${tpl}?t=${Date.now()}`;
  $('pdfBtn').href = `/api/resumes/${rid}/export.pdf?template=${tpl}`;
  document.querySelectorAll('.tpl-card').forEach(b => b.setAttribute('aria-pressed', String(b.dataset.key === tpl)));
}
async function load(id) {
  rid = id; $('stage').classList.toggle('hidden', !id); if (!id) return;
  const d = await api(`/api/resumes/${id}/content`); content = d.content; tpl = d.template; buildEditor(); refreshPreview();
}
async function save() {
  setBusy($('saveBtn'), true, 'Saving…');
  try { const d = await api(`/api/resumes/${rid}/content`, { method: 'PUT', json: { content: collect(), template: tpl } }); content = d.content; toast('Saved.', 'success'); refreshPreview(); }
  catch (e) { toast(e.message, 'error'); } finally { setBusy($('saveBtn'), false); }
}
document.querySelectorAll('.tpl-card').forEach(b => b.addEventListener('click', async () => { tpl = b.dataset.key; await save(); }));
$('saveBtn').addEventListener('click', save);
await initResumePicker($('picker'), { onChange: id => load(id).catch(e => toast(e.message, 'error')) });
