const assert = require('node:assert/strict');

let clickHandler;
const events = [];

global.document = {
  addEventListener(type, handler) {
    assert.equal(type, 'click');
    assert.equal(clickHandler, undefined, 'only one delegated click listener is registered');
    clickHandler = handler;
  }
};
global.window = { gtag: true };
global.gtag = (...args) => events.push(args);

require('../scripts/analytics.js');

function clickLink(id, location) {
  const trackedLink = {
    getAttribute(name) {
      return {
        'data-evt': id,
        'data-evt-loc': location
      }[name] || null;
    },
    closest() {
      return null;
    }
  };

  clickHandler({
    target: {
      closest(selector) {
        return selector === 'a[data-evt]' ? trackedLink : null;
      }
    }
  });
}

const cases = [
  {
    id: 'book_en_paperback',
    location: 'book_page',
    eventName: 'outbound_purchase',
    attributes: { content_language: 'en', item_format: 'paperback' }
  },
  {
    id: 'book_es_info',
    location: 'site_footer',
    eventName: 'view_book',
    attributes: { content_language: 'es', item_format: 'information' }
  },
  {
    id: 'book_en_availability',
    location: 'book_page_hero',
    eventName: 'browse_book_availability',
    attributes: { content_language: 'en', availability_channel: 'all_verified' }
  },
  {
    id: 'help_en_dialysis',
    location: 'homepage_resources',
    eventName: 'start_help_flow',
    attributes: { content_language: 'en', help_topic: 'dialysis' }
  },
  {
    id: 'organization_es_donor_shield',
    location: 'donor_story',
    eventName: 'browse_organizations',
    attributes: { content_language: 'es', organization: 'donor_shield' }
  }
];

for (const item of cases) {
  events.length = 0;
  clickLink(item.id, item.location);
  assert.deepEqual(events, [
    [
      'event',
      'cta_click',
      { cta_id: item.id, cta_loc: item.location }
    ],
    [
      'event',
      item.eventName,
      {
        action_id: item.id,
        action_location: item.location,
        ...item.attributes
      }
    ]
  ]);
}

events.length = 0;
clickLink('professional_en', 'homepage');
assert.deepEqual(events, [[
  'event',
  'cta_click',
  { cta_id: 'professional_en', cta_loc: 'homepage' }
]]);

console.log('analytics event contract: pass');
