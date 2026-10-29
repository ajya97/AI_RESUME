/** App shell: mobile sidebar + profile menu. */
const sidebar = document.getElementById('sidebar');
const scrim = document.getElementById('scrim');
const menuBtn = document.getElementById('menuBtn');
const profileBtn = document.getElementById('profileBtn');
const profileMenu = document.getElementById('profileMenu');

function toggleSidebar(open) {
  sidebar.classList.toggle('open', open); scrim.classList.toggle('open', open);
  menuBtn?.setAttribute('aria-expanded', String(open));
}
menuBtn?.addEventListener('click', () => toggleSidebar(!sidebar.classList.contains('open')));
scrim?.addEventListener('click', () => toggleSidebar(false));

profileBtn?.addEventListener('click', e => {
  e.stopPropagation();
  const open = !profileMenu.classList.contains('open');
  profileMenu.classList.toggle('open', open); profileBtn.setAttribute('aria-expanded', String(open));
});
document.addEventListener('click', () => { profileMenu?.classList.remove('open'); profileBtn?.setAttribute('aria-expanded', 'false'); });
document.addEventListener('keydown', e => { if (e.key === 'Escape') { toggleSidebar(false); profileMenu?.classList.remove('open'); } });
