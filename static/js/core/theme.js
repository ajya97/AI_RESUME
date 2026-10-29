/**
 * core/theme.js — light/dark toggle.
 * Initial theme is applied before first paint by an inline script in base.html.
 * Signed-in users: preference is saved to PostgreSQL via /api/settings/theme.
 * Guests: saved in localStorage.
 */
const KEY = 'resumeai-theme';
const root = document.documentElement;
const csrf = () => document.querySelector('meta[name="csrf-token"]')?.content || '';
const current = () => (root.getAttribute('data-theme') === 'light' ? 'light' : 'dark');

async function setTheme(theme) {
  root.setAttribute('data-theme', theme);
  try { localStorage.setItem(KEY, theme); } catch { /* storage unavailable */ }
  if (document.body.dataset.auth === 'yes') {
    try {
      await fetch('/api/settings/theme', { method: 'POST', credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf() }, body: JSON.stringify({ theme }) });
    } catch { /* offline: local value still applies */ }
  }
}

document.querySelectorAll('[data-theme-toggle]').forEach(btn =>
  btn.addEventListener('click', () => setTheme(current() === 'light' ? 'dark' : 'light')));
document.querySelectorAll('[data-theme-set]').forEach(btn =>
  btn.addEventListener('click', () => setTheme(btn.dataset.themeSet)));
