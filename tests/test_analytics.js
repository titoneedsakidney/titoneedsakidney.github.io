const assert = require('node:assert/strict');

let clickHandler;
const events = [];

global.document = {
  documentElement: { lang: 'en' },
  addEventListener(type, handler) {
    assert.equal(type, 'click');
    assert.equal(clickHandler, undefined, 'only one delegated click listener is registered');
    clickHandler = handler;
  }
};
global.window = { gtag: true };
global.gtag = (...args) => events.push(args);

require('../scripts/analytics.js');

function clickTrackedLink({ id, eventName, text, href, location }) {
  const trackedLink = {
    textContent: text,
    href,
    getAttribute(name) {
      return {
        'data-evt': id,
        'data-evt-loc': location,
        'data-analytics-event': eventName
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
    id: 'help_en_dialysis',
    eventName: 'start_help_flow',
    text: 'Dialysis Hub',
    href: 'https://titoneedsakidney.com/hub/dialysis/',
    location: 'homepage_resources'
  },
  {
    id: 'organization_donor_shield',
    eventName: 'browse_organizations',
    text: 'Donor Shield',
    href: 'https://www.donor-shield.org/',
    location: 'donor_story'
  },
  {
    id: 'book_en_info',
    eventName: null,
    expectedEventName: 'view_book',
    text: 'Buy the Book',
    href: 'https://titoneedsakidney.com/book.html',
    location: 'site_footer'
  },
  {
    id: 'book_en_paperback',
    eventName: 'outbound_purchase',
    text: 'Buy the Paperback',
    href: 'https://www.amazon.com/dp/B0DSXVL84P',
    location: 'book_page'
  }
];

for (const item of cases) clickTrackedLink(item);

const expectedEvents = cases.flatMap((item) => {
  const params = {
    cta_id: item.id,
    cta_text: item.text,
    cta_loc: item.location,
    content_language: 'en',
    link_url: item.href
  };
  return [
    ['event', 'cta_click', params],
    ['event', item.expectedEventName || item.eventName, params]
  ];
});

assert.deepEqual(events, expectedEvents);

clickTrackedLink({
  id: 'ordinary_link',
  eventName: 'unapproved_event',
  text: 'Ordinary link',
  href: 'https://titoneedsakidney.com/about.html',
  location: 'content'
});
assert.equal(events.at(-1)[1], 'cta_click', 'unapproved purpose events are not emitted');

console.log('analytics event contract: pass');
