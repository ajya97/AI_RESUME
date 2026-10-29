/** Small shared UI helpers (no dependencies). */
export function esc(v) {
  return String(v ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}
export const $ = (sel, root = document) => root.querySelector(sel);
export const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];

export function toast(message, kind = 'info', ms = 4500) {
  const host = document.getElementById('toasts');
  if (!host) return;
  const t = document.createElement('div');
  t.className = `toast toast-${kind}`;
  t.textContent = message;
  host.appendChild(t);
  setTimeout(() => t.remove(), ms);
}

export function setBusy(btn, busy, label) {
  if (!btn) return;
  if (busy) { btn.dataset.label = btn.innerHTML; btn.disabled = true; btn.innerHTML = `<span class="spinner"></span> ${esc(label || 'Working…')}`; }
  else { btn.disabled = false; if (btn.dataset.label) btn.innerHTML = btn.dataset.label; }
}

export function fmtDate(iso) {
  try { return new Date(iso).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' }); } catch { return iso; }
}
export function fmtSize(b) { return b < 1024 ? `${b} B` : b < 1048576 ? `${(b / 1024).toFixed(1)} KB` : `${(b / 1048576).toFixed(1)} MB`; }
export function newKey() { return (crypto.randomUUID ? crypto.randomUUID() : String(Date.now()) + Math.random().toString(16).slice(2)).replace(/[^A-Za-z0-9_-]/g, ''); }

export function showError(container, err) {
  const msg = err?.message || 'Something went wrong.';
  const extra = err?.data?.code === 'insufficient_credits'
    ? ` <a href="/credits">View credits</a>` : '';
  container.innerHTML = `<div class="alert alert-error" role="alert">${esc(msg)}${extra}</div>`;
}

export function loading(container, text = 'Working on it…') {
  container.innerHTML = `<div class="loading-overlay" role="status"><span class="spinner"></span><div>${esc(text)}</div></div>`;
}

export function confirmDialog(message, okLabel = 'Delete') {
  return new Promise(resolve => {
    const d = document.createElement('dialog');
    d.innerHTML = `<p>${esc(message)}</p><div class="row" style="justify-content:flex-end"><button class="btn btn-ghost" value="no">Cancel</button><button class="btn btn-danger" value="yes">${esc(okLabel)}</button></div>`;
    d.addEventListener('click', e => { if (e.target.tagName === 'BUTTON') d.close(e.target.value); });
    d.addEventListener('close', () => { resolve(d.returnValue === 'yes'); d.remove(); });
    document.body.appendChild(d); d.showModal();
  });
}

/** Accessible tab widget: buttons [role=tab][data-tab] and panels #panel-<name>. */
export function initTabs(root) {
  const tabs = $$('[role=tab]', root);
  tabs.forEach(t => t.addEventListener('click', () => {
    tabs.forEach(x => x.setAttribute('aria-selected', String(x === t)));
    $$('.tab-panel', root).forEach(p => { p.hidden = p.id !== `panel-${t.dataset.tab}`; });
  }));
}
