const assert = require('node:assert/strict');

let clickHandler;
const listeners = {};
const events = [];

global.document = {
  addEventListener(type, handler) {
    listeners[type] = listeners[type] || [];
    listeners[type].push(handler);
    if (type === 'click') {
      assert.equal(clickHandler, undefined, 'only one delegated click listener is registered');
      clickHandler = handler;
    }
  },
  removeEventListener(type, handler) {
    listeners[type] = (listeners[type] || []).filter((h) => h !== handler);
  }
};
const store = {};
global.window = {
  gtag: true,
  sessionStorage: {
    getItem: (k) => (k in store ? store[k] : null),
    setItem: (k, v) => { store[k] = v; }
  }
};
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

// The human-interaction signal: only a trusted press, key, touch or wheel counts, and only once.
const SIGNALS = ['pointerdown', 'keydown', 'touchstart', 'wheel'];
for (const type of SIGNALS) {
  assert.equal(listeners[type].length, 1, `one ${type} listener is registered`);
}
const signalHandler = listeners.pointerdown[0];

events.length = 0;
signalHandler({ type: 'pointerdown', isTrusted: false });
assert.deepEqual(events, [], 'a script-made event is not a person');
assert.equal(store.tnk_human_signal, undefined);

signalHandler({ type: 'pointerdown', isTrusted: true });
assert.deepEqual(events, [['event', 'human_interaction']], 'the first trusted action sends one parameterless event');
assert.equal(store.tnk_human_signal, '1');
for (const type of SIGNALS) {
  assert.equal(listeners[type].length, 0, `${type} listener is removed after it fires`);
}

// A later page in the same tab session registers nothing and sends nothing.
for (const type of Object.keys(listeners)) listeners[type] = [];
clickHandler = undefined;
delete require.cache[require.resolve('../scripts/analytics.js')];
require('../scripts/analytics.js');
for (const type of SIGNALS) {
  assert.equal(listeners[type].length, 0, `${type} is not registered again in the same tab session`);
}

// Blocked storage must not break the page: the signal still arms and fires once.
for (const type of Object.keys(listeners)) listeners[type] = [];
clickHandler = undefined;
global.window.sessionStorage = {
  getItem() { throw new Error('blocked'); },
  setItem() { throw new Error('blocked'); }
};
delete require.cache[require.resolve('../scripts/analytics.js')];
require('../scripts/analytics.js');
events.length = 0;
listeners.keydown[0]({ type: 'keydown', isTrusted: true });
assert.deepEqual(events, [['event', 'human_interaction']]);

console.log('analytics event contract: pass');
