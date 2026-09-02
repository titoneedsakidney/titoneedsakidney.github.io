const PURPOSE_EVENTS = new Set([
  'start_help_flow',
  'browse_organizations',
  'view_book',
  'outbound_purchase'
]);

// The existing sitewide book links already have durable IDs on every page.
// Map those IDs here so the generated static footer does not need a markup migration.
const PURPOSE_EVENT_BY_CTA_ID = {
  book_en_info: 'view_book',
  book_es_info: 'view_book'
};

document.addEventListener('click', (e) => {
  const a = e.target.closest('a[data-evt]');
  if (!a || !window.gtag) return;

  const params = {
    cta_id: a.getAttribute('data-evt'),
    cta_text: (a.textContent || '').trim(),
    cta_loc: a.getAttribute('data-evt-loc') ||
      a.closest('[data-loc]')?.getAttribute('data-loc') || 'unknown',
    content_language: document.documentElement.lang || 'und',
    link_url: a.href
  };

  // Keep the original event for historical continuity.
  gtag('event', 'cta_click', params);

  const purposeEvent = a.getAttribute('data-analytics-event') ||
    PURPOSE_EVENT_BY_CTA_ID[params.cta_id];
  if (PURPOSE_EVENTS.has(purposeEvent)) {
    gtag('event', purposeEvent, params);
  }
});
