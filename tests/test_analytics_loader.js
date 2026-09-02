const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const source = fs.readFileSync(
  path.join(__dirname, '..', 'scripts', 'analytics-loader.js'),
  'utf8'
);
const measurementId = 'G-JHT0DBJBHH';

function loadAnalytics({
  origin = 'https://titoneedsakidney.com',
  search = '',
  storedAuditSession = false
} = {}) {
  const appended = [];
  const storage = new Map();
  if (storedAuditSession) storage.set('tnk_analytics_test', '1');

  const context = {
    URLSearchParams,
    document: {
      createElement(tagName) {
        assert.equal(tagName, 'script');
        return {};
      },
      head: {
        appendChild(element) {
          appended.push(element);
        }
      }
    },
    window: {
      location: { origin, search },
      sessionStorage: {
        getItem(key) {
          return storage.get(key) || null;
        },
        setItem(key, value) {
          storage.set(key, value);
        }
      }
    }
  };

  vm.runInNewContext(source, context);
  return { appended, storage, window: context.window };
}

const production = loadAnalytics();
assert.equal(production.appended.length, 1);
assert.equal(production.appended[0].async, true);
assert.equal(
  production.appended[0].src,
  `https://www.googletagmanager.com/gtag/js?id=${measurementId}`
);
assert.equal(production.window[`ga-disable-${measurementId}`], undefined);

for (const origin of [
  'http://127.0.0.1:8000',
  'http://localhost:8000',
  'https://titoneedsakidney.github.io',
  'https://www.titoneedsakidney.com',
  'null'
]) {
  const preview = loadAnalytics({ origin });
  assert.equal(preview.appended.length, 0, `${origin} must not load Google Analytics`);
  assert.equal(preview.window[`ga-disable-${measurementId}`], true);
}

const auditEntry = loadAnalytics({ search: '?analytics_test=1' });
assert.equal(auditEntry.appended.length, 0);
assert.equal(auditEntry.storage.get('tnk_analytics_test'), '1');
assert.equal(auditEntry.window[`ga-disable-${measurementId}`], true);

const auditNavigation = loadAnalytics({ storedAuditSession: true });
assert.equal(auditNavigation.appended.length, 0);
assert.equal(auditNavigation.window[`ga-disable-${measurementId}`], true);

const ordinaryQuery = loadAnalytics({ search: '?utm_medium=email' });
assert.equal(ordinaryQuery.appended.length, 1);

console.log('analytics loader hygiene contract: pass');
