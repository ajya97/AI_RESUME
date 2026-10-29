/** Resume <select> + inline "upload another" used by every feature page. */
import { api, uploadResumeOnly } from './api.js';
import { esc, toast, fmtSize } from './ui.js';

export async function initResumePicker(root, { onChange } = {}) {
  root.innerHTML = `<label for="resumeSelect">Resume</label>
    <div class="row"><select id="resumeSelect" style="flex:1 1 220px" aria-label="Choose resume"></select>
    <button type="button" class="btn btn-ghost btn-sm" id="pickerUpload">＋ Upload PDF</button>
    <input type="file" id="pickerFile" accept="application/pdf,.pdf" hidden></div>
    <div class="hint" id="pickerHint"></div>`;
  const sel = root.querySelector('#resumeSelect'), file = root.querySelector('#pickerFile'), hint = root.querySelector('#pickerHint');

  async function load(selectId) {
    const { resumes } = await api('/api/resumes');
    if (!resumes.length) {
      sel.innerHTML = '<option value="">No resumes yet — upload a PDF</option>'; sel.disabled = true;
      hint.textContent = 'Upload a text-based PDF resume (max 5 MB). Uploading is free.';
    } else {
      sel.disabled = false;
      sel.innerHTML = resumes.map(r => `<option value="${r.id}">${esc(r.filename)} · ${esc(r.name || '')} · ${fmtSize(r.size)}</option>`).join('');
      const want = selectId || new URLSearchParams(location.search).get('resume');
      if (want && resumes.some(r => String(r.id) === String(want))) sel.value = want;
      hint.textContent = '';
    }
    onChange?.(sel.value ? Number(sel.value) : null, resumes);
  }
  sel.addEventListener('change', () => onChange?.(sel.value ? Number(sel.value) : null));
  root.querySelector('#pickerUpload').addEventListener('click', () => file.click());
  file.addEventListener('change', async () => {
    const f = file.files[0]; file.value = '';
    if (!f) return;
    if (!/\.pdf$/i.test(f.name) || f.size > 5 * 1024 * 1024) return toast('Please choose a PDF under 5 MB.', 'error');
    try {
      const d = await uploadResumeOnly(f);
      toast(d.duplicate ? 'That resume is already uploaded.' : 'Resume uploaded.', 'success');
      await load(d.resume.id);
    } catch (e) { toast(e.message, 'error'); }
  });
  try { await load(); } catch (e) { hint.textContent = e.message; }
  return { get id() { return sel.value ? Number(sel.value) : null; }, reload: load };
}
