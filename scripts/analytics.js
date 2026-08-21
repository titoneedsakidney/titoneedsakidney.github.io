document.addEventListener('click', (e) => {
  const a = e.target.closest('a[data-evt]');
  if (!a || !window.gtag) return;
  gtag('event', 'cta_click', {
    cta_id: a.getAttribute('data-evt'),              // e.g., "kofi"
    cta_text: (a.textContent || '').trim(),
    cta_loc: a.getAttribute('data-evt-loc') ||
      a.closest('[data-loc]')?.getAttribute('data-loc') || 'unknown',
    link_url: a.href
  });
});
