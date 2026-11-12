const assert = require('node:assert/strict');
const { run, campaignFor, validTag } = require('../scripts/attribution.js');

const store = () => { const s = {}; return { getItem: (k) => (k in s ? s[k] : null), setItem: (k, v) => { s[k] = v; } }; };
const anchor = (href) => { const a = { href }; a.getAttribute = () => a.href; a.setAttribute = (n, v) => { a.href = v; }; return a; };
const doc = (...hrefs) => { const list = hrefs.map(anchor); return { list, querySelectorAll: () => list }; };
const TAG = (asin, id) => `https://www.amazon.com/dp/${asin}?maas=maas_adg_${id}&ref_=aa_maas&tag=maas`;
const TAGS = { 'cmp-01': { B0DSXVL84P: TAG('B0DSXVL84P', 'A') }, 'site-default': { B0DSXVL84P: TAG('B0DSXVL84P', 'D'), B0DT1N3FFG: TAG('B0DT1N3FFG', 'K') } };

// an empty table changes nothing
let d = doc('https://www.amazon.com/dp/B0DSXVL84P');
assert.equal(run({ TNK_ATTRIBUTION: {}, location: { search: '?utm_source=organization-outreach&utm_campaign=cmp-01' }, sessionStorage: store() }, d), 0);
assert.equal(d.list[0].href, 'https://www.amazon.com/dp/B0DSXVL84P');

// an outreach visitor gets the tag of that campaign and book; a book with no tag for the campaign keeps its plain address
d = doc('https://www.amazon.com/dp/B0DSXVL84P', 'https://www.amazon.com/dp/B0DT1N3FFG');
assert.equal(run({ TNK_ATTRIBUTION: TAGS, location: { search: '?utm_source=organization-outreach&utm_medium=email&utm_campaign=cmp-01&utm_content=book' }, sessionStorage: store() }, d), 1);
assert.equal(d.list[0].href, TAG('B0DSXVL84P', 'A'));
assert.equal(d.list[1].href, 'https://www.amazon.com/dp/B0DT1N3FFG');

// the campaign survives navigation inside the session; no campaign means the site-default tags
const s = store();
assert.equal(campaignFor('?utm_source=organization-outreach&utm_campaign=CMP-01', s), 'cmp-01');
assert.equal(campaignFor('', s), 'cmp-01');
d = doc('https://www.amazon.com/dp/B0DT1N3FFG');
assert.equal(run({ TNK_ATTRIBUTION: TAGS, location: { search: '' }, sessionStorage: store() }, d), 1);
assert.equal(d.list[0].href, TAG('B0DT1N3FFG', 'K'));

// other utm sources and malformed campaign ids are ignored; broken storage never breaks the page
assert.equal(campaignFor('?utm_source=newsletter&utm_campaign=cmp-01', store()), 'site-default');
assert.equal(campaignFor('?utm_source=organization-outreach&utm_campaign=cmp-1', store()), 'site-default');
assert.equal(campaignFor('?utm_source=organization-outreach&utm_campaign=cmp-01', { getItem() { throw new Error('blocked'); }, setItem() { throw new Error('blocked'); } }), 'cmp-01');

// only real Amazon Attribution tags for that book are accepted: nothing else is ever written into a link
assert.equal(validTag('https://evil.example/dp/B0DSXVL84P?maas=1', 'B0DSXVL84P'), false);
assert.equal(validTag('https://www.amazon.com/dp/B0DSXVL84P', 'B0DSXVL84P'), false);
assert.equal(validTag(TAG('B0DT1N3FFG', 'X'), 'B0DSXVL84P'), false);
assert.equal(validTag(TAG('B0DSXVL84P', 'X'), 'B0DSXVL84P'), true);
d = doc('https://www.amazon.com/dp/B0DSXVL84P', 'https://example.org/other', 'https://www.amazon.com/gp/help');
run({ TNK_ATTRIBUTION: { 'site-default': { B0DSXVL84P: 'https://evil.example/x?maas=1&B0DSXVL84P' } }, location: { search: '' }, sessionStorage: store() }, d);
assert.equal(d.list[0].href, 'https://www.amazon.com/dp/B0DSXVL84P');
console.log('attribution tests ok');

// the shipped tag table: every address is a real Amazon Attribution tag for its own book, and campaign keys are cmp-NN or site-default
global.window = {};
require('../scripts/attribution-tags.js');
for (const [campaign, table] of Object.entries(global.window.TNK_ATTRIBUTION)) {
  assert.ok(/^cmp-\d{2}$/.test(campaign) || campaign === 'site-default', `campaign key ${campaign}`);
  for (const [asin, url] of Object.entries(table)) {
    assert.ok(/^[A-Z0-9]{10}$/.test(asin), `asin ${asin}`);
    assert.ok(validTag(url, asin), `${campaign} ${asin} tag`);
    assert.ok(url.startsWith(`https://www.amazon.com/dp/${asin}?maas=`), `${campaign} ${asin} form`);
  }
}
console.log('shipped tag table ok');
