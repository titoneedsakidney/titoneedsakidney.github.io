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
  book_en_availability: {
    name: 'browse_book_availability',
    content_language: 'en',
    availability_channel: 'all_verified'
  },
  book_es_availability: {
    name: 'browse_book_availability',
    content_language: 'es',
    availability_channel: 'all_verified'
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

// A visit that does something only a person does. Mail-security software opens every link in a message
// in a real browser; those visits load the page but never press, type, touch or use the wheel.
// The first trusted pointer press, key press, touch or wheel turn in a tab session sends one
// `human_interaction` event, so reports can count sessions where a person acted. It carries no
// parameter, no identifier and no content, and it fires once per tab session.
(() => {
  const SIGNAL_KEY = 'tnk_human_signal';
  const SIGNALS = ['pointerdown', 'keydown', 'touchstart', 'wheel'];

  try {
    if (window.sessionStorage && window.sessionStorage.getItem(SIGNAL_KEY) === '1') return;
  } catch (_) {
    // Storage may be blocked; the listeners below still send at most one event per page load.
  }

  function onSignal(e) {
    if (!e || e.isTrusted !== true) return;
    for (const type of SIGNALS) document.removeEventListener(type, onSignal, true);
    try {
      if (window.sessionStorage) window.sessionStorage.setItem(SIGNAL_KEY, '1');
    } catch (_) {
      // Ignored: see above.
    }
    if (window.gtag) gtag('event', 'human_interaction');
  }

  for (const type of SIGNALS) {
    document.addEventListener(type, onSignal, { capture: true, passive: true });
  }
})();
