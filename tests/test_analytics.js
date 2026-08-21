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

const trackedLink = {
  textContent: 'Buy the Paperback',
  href: 'https://www.amazon.com/dp/B0DSXVL84P',
  getAttribute(name) {
    return {
      'data-evt': 'book_en_paperback',
      'data-evt-loc': 'book_page'
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

assert.deepEqual(events, [[
  'event',
  'cta_click',
  {
    cta_id: 'book_en_paperback',
    cta_text: 'Buy the Paperback',
    cta_loc: 'book_page',
    link_url: 'https://www.amazon.com/dp/B0DSXVL84P'
  }
]]);

console.log('analytics event contract: pass');
