const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const source = fs.readFileSync(
  path.join(__dirname, '..', 'scripts', 'active-link.js'),
  'utf8'
);

function makeLink(attributes) {
  return {
    attributes: { ...attributes },
    classList: { add() {}, remove() {} },
    getAttribute(name) { return this.attributes[name] || null; },
    setAttribute(name, value) { this.attributes[name] = value; },
    removeAttribute(name) { delete this.attributes[name]; },
    hasAttribute(name) { return Object.hasOwn(this.attributes, name); }
  };
}

function loadLanguageSwitch({ pathname, alternates }) {
  const en = makeLink({ 'data-lang': 'en', href: '/' });
  const es = makeLink({ 'data-lang': 'es', href: '/es/' });
  const document = {
    readyState: 'complete',
    querySelectorAll(selector) {
      if (selector === '.lang-switch a[data-lang]') return [en, es];
      if (selector === 'nav.js-active-nav') return [];
      throw new Error(`Unexpected selector: ${selector}`);
    },
    querySelector(selector) {
      const match = selector.match(/hreflang="(en|es)"/);
      return match && alternates[match[1]]
        ? makeLink({ href: alternates[match[1]] })
        : null;
    }
  };

  vm.runInNewContext(source, {
    URL,
    location: { origin: 'https://titoneedsakidney.com', pathname },
    document
  });
  return { en, es };
}

let links = loadLanguageSwitch({
  pathname: '/hub/dialysis/side-effects.html',
  alternates: {
    en: 'https://titoneedsakidney.com/hub/dialysis/side-effects.html',
    es: 'https://titoneedsakidney.com/es/hub/dialysis/side-effects.html'
  }
});
assert.equal(links.en.getAttribute('href'), '/hub/dialysis/side-effects.html');
assert.equal(links.es.getAttribute('href'), '/es/hub/dialysis/side-effects.html');

links = loadLanguageSwitch({
  pathname: '/es/hub/transplant/postop/recovery.html',
  alternates: {
    en: 'https://titoneedsakidney.com/hub/transplant/postop/recovery.html',
    es: 'https://titoneedsakidney.com/es/hub/transplant/postop/recovery.html'
  }
});
assert.equal(links.en.getAttribute('href'), '/hub/transplant/postop/recovery.html');
assert.equal(links.es.getAttribute('href'), '/es/hub/transplant/postop/recovery.html');

links = loadLanguageSwitch({
  pathname: '/about.html',
  alternates: { en: 'https://titoneedsakidney.com/about.html' }
});
assert.equal(links.en.getAttribute('href'), '/about.html');
assert.equal(links.es.getAttribute('href'), '/es/');

console.log('language switch continuity contract: pass');
