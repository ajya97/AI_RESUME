import { api } from '../core/api.js';
import { esc, fmtDate, toast, confirmDialog, loading, showError } from '../core/ui.js';

const $ = id => document.getElementById(id);
let page = 1, pages = 1, timer;
const del = { ats: id => `/api/reports/${id}`, job_match: id => `/api/reports/${id}`, skill_gap: id => `/api/reports/${id}`, interview: id => `/api/interview/${id}`, chat: id => `/api/chat/sessions/${id}` };
const icon = { ats: '📊', job_match: '🎯', skill_gap: '🧠', interview: '🎤', chat: '💬' };

async function load() {
  loading($('list'), 'Loading…');
  try {
    const qs = new URLSearchParams({ page, per_page: 10, q: $('q').value.trim(), type: $('type').value });
    const d = await api(`/api/history?${qs}`); pages = d.pages;
    $('list').innerHTML = d.items.length ? d.items.map(i => `<div class="list-item" style="align-items:center;justify-content:space-between">
      <div style="min-width:0"><a href="/history/${i.kind}/${i.id}"><b>${icon[i.kind] || ''} ${esc(i.title)}</b></a>
        <div class="small dim">${esc(i.kind_label)} · ${esc(fmtDate(i.created_at))} · ${esc(i.status.replace('_', ' '))}</div></div>
      <div class="row">${i.score != null ? `<span class="badge">${esc(i.score)}/${i.score_max}</span>` : ''}
        ${['ats', 'job_match', 'skill_gap'].includes(i.kind) ? `<a class="btn btn-ghost btn-sm" href="/api/reports/${i.id}/export.pdf" aria-label="Download PDF">⬇</a>` : ''}
        <button class="btn btn-danger btn-sm" data-kind="${i.kind}" data-id="${i.id}" aria-label="Delete">🗑</button></div></div>`).join('')
      : `<div class="empty"><div class="empty-icon">🕘</div>${$('q').value || $('type').value ? 'Nothing matches your filters.' : 'No activity yet.'}</div>`;
    $('pageLbl').textContent = `Page ${d.page} of ${d.pages} · ${d.total} items`;
    $('prev').disabled = page <= 1; $('next').disabled = page >= pages;
  } catch (e) { showError($('list'), e); }
}
$('list').addEventListener('click', async e => {
  const b = e.target.closest('button[data-kind]'); if (!b) return;
  if (!await confirmDialog('Delete this item permanently?')) return;
  try { await api(del[b.dataset.kind](b.dataset.id), { method: 'DELETE' }); toast('Deleted.', 'success'); load(); } catch (err) { toast(err.message, 'error'); }
});
$('prev').onclick = () => { page--; load(); }; $('next').onclick = () => { page++; load(); };
$('type').onchange = () => { page = 1; load(); };
$('q').addEventListener('input', () => { clearTimeout(timer); timer = setTimeout(() => { page = 1; load(); }, 300); });
load();
