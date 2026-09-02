const SEMANTIC_EVENTS = {
  book_en_paperback: {
    name: 'outbound_purchase',
    content_language: 'en',
    item_format: 'paperback'
  },
  book_en_kindle: {
    name: 'outbound_purchase',
    content_language: 'en',
    item_format: 'kindle'
  },
  book_es_paperback: {
    name: 'outbound_purchase',
    content_language: 'es',
    item_format: 'paperback'
  },
  book_es_kindle: {
    name: 'outbound_purchase',
    content_language: 'es',
    item_format: 'kindle'
  },
  book_en_info: {
    name: 'view_book',
    content_language: 'en',
    item_format: 'information'
  },
  book_es_info: {
    name: 'view_book',
    content_language: 'es',
    item_format: 'information'
  },
  start_help_flow: { name: 'start_help_flow' },
  browse_organizations: { name: 'browse_organizations' }
};

document.addEventListener('click', (e) => {
  const a = e.target.closest('a[data-evt]');
  if (!a || !window.gtag) return;

  const ctaId = a.getAttribute('data-evt');
  const ctaLoc = a.getAttribute('data-evt-loc') ||
    a.closest('[data-loc]')?.getAttribute('data-loc') || 'unknown';

  gtag('event', 'cta_click', {
    cta_id: ctaId,
    cta_loc: ctaLoc
  });

  const semantic = SEMANTIC_EVENTS[ctaId];
  if (!semantic) return;

  const { name, ...attributes } = semantic;
  gtag('event', name, {
    action_id: ctaId,
    action_location: ctaLoc,
    ...attributes
  });
});
