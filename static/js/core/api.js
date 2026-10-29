/**
 * core/api.js — fetch wrapper: CSRF header, JSON handling, consistent errors,
 * optional Idempotency-Key (prevents double-charging) and live credit pill updates.
 */
import { newKey } from './ui.js';

export class ApiError extends Error {
  constructor(message, status, data) { super(message); this.status = status; this.data = data || {}; }
}

const csrf = () => document.querySelector('meta[name="csrf-token"]')?.content || '';

export function updateCredits(balance) {
  if (typeof balance !== 'number') return;
  const el = document.getElementById('creditBalance');
  if (el) el.textContent = balance;
}

export async function api(path, { method = 'GET', json, form, idempotent = false } = {}) {
  const headers = { 'X-CSRFToken': csrf(), 'Accept': 'application/json' };
  const opts = { method, headers, credentials: 'same-origin' };
  if (json !== undefined) { headers['Content-Type'] = 'application/json'; opts.body = JSON.stringify(json); }
  if (form) opts.body = form;
  if (idempotent) headers['Idempotency-Key'] = newKey();

  let res;
  try { res = await fetch(path, opts); }
  catch { throw new ApiError('Network error. Please check your connection and try again.', 0); }

  if (res.status === 401) { window.location.href = `/login?next=${encodeURIComponent(location.pathname)}`; throw new ApiError('Please sign in.', 401); }
  let data = {};
  try { data = await res.json(); } catch { /* non-JSON body */ }
  if (!res.ok || data.error) throw new ApiError(data.error || `Request failed (${res.status})`, res.status, data);
  if (data.credits) updateCredits(data.credits.balance);
  return data;
}

export const uploadResumeOnly = file => { const f = new FormData(); f.append('resume', file); return api('/api/resumes', { method: 'POST', form: f }); };
export const uploadAndAnalyze = file => { const f = new FormData(); f.append('resume', file); return api('/api/upload', { method: 'POST', form: f, idempotent: true }); };
export const analyzeResume = id => api(`/api/resumes/${id}/analyze`, { method: 'POST', idempotent: true });
export const refreshBalance = async () => { const d = await api('/api/credits?per_page=1'); updateCredits(d.balance); return d; };
