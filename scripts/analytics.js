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
  book_en_hero: {
    name: 'view_book',
    content_language: 'en',
    item_format: 'information'
  },
  book_es_hero: {
    name: 'view_book',
    content_language: 'es',
    item_format: 'information'
  },
  help_en_dialysis: {
    name: 'start_help_flow',
    content_language: 'en',
    help_topic: 'dialysis'
  },
  help_en_transplant: {
    name: 'start_help_flow',
    content_language: 'en',
    help_topic: 'transplant'
  },
  help_en_donation: {
    name: 'start_help_flow',
    content_language: 'en',
    help_topic: 'living_donation'
  },
  help_es_dialysis: {
    name: 'start_help_flow',
    content_language: 'es',
    help_topic: 'dialysis'
  },
  help_es_transplant: {
    name: 'start_help_flow',
    content_language: 'es',
    help_topic: 'transplant'
  },
  help_es_donation: {
    name: 'start_help_flow',
    content_language: 'es',
    help_topic: 'living_donation'
  },
  organization_en_nkf_paired_donation: {
    name: 'browse_organizations',
    content_language: 'en',
    organization: 'national_kidney_foundation'
  },
  organization_en_donor_shield: {
    name: 'browse_organizations',
    content_language: 'en',
    organization: 'donor_shield'
  },
  organization_es_nkf_paired_donation: {
    name: 'browse_organizations',
    content_language: 'es',
    organization: 'national_kidney_foundation'
  },
  organization_es_donor_shield: {
    name: 'browse_organizations',
    content_language: 'es',
    organization: 'donor_shield'
  }
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
