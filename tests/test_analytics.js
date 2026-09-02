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

function clickLink(id, location = 'book_page') {
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

clickLink('book_en_paperback');
assert.deepEqual(events, [
  [
    'event',
    'cta_click',
    { cta_id: 'book_en_paperback', cta_loc: 'book_page' }
  ],
  [
    'event',
    'outbound_purchase',
    {
      action_id: 'book_en_paperback',
      action_location: 'book_page',
      content_language: 'en',
      item_format: 'paperback'
    }
  ]
]);

events.length = 0;
clickLink('professional_en', 'homepage');
assert.deepEqual(events, [[
  'event',
  'cta_click',
  { cta_id: 'professional_en', cta_loc: 'homepage' }
]]);

events.length = 0;
clickLink('book_es_info', 'site_footer');
assert.equal(events[1][1], 'view_book');
assert.equal(events[1][2].content_language, 'es');

console.log('analytics event contract: pass');
