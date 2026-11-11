// Swap each Amazon buy button for the Amazon Attribution tag of the visitor's outreach campaign (campaign and book only, never a person).
// A visitor who arrived with utm_source=organization-outreach and utm_campaign=cmp-NN keeps that campaign id for the browser session (sessionStorage);
// everyone else uses the 'site-default' tag. No tag configured for that campaign and book means the plain Amazon address stays.
(function (root) {
  'use strict';
  var KEY = 'tnk_campaign';
  var CAMPAIGN = /^cmp-\d{2}$/;
  var BUY = /^https:\/\/www\.amazon\.com\/dp\/([A-Z0-9]{10})\/?$/;

  function param(search, name) {
    var m = new RegExp('[?&]' + name + '=([^&#]*)').exec(search || '');
    if (!m) return '';
    try { return decodeURIComponent(m[1].replace(/\+/g, ' ')); } catch (e) { return ''; }
  }

  function campaignFor(search, storage) {
    var fromUrl = param(search, 'utm_campaign').toLowerCase();
    if (param(search, 'utm_source') === 'organization-outreach' && CAMPAIGN.test(fromUrl)) {
      try { storage.setItem(KEY, fromUrl); } catch (e) { /* storage blocked: this page still works */ }
      return fromUrl;
    }
    try {
      var kept = storage && storage.getItem(KEY);
      if (kept && CAMPAIGN.test(kept)) return kept;
    } catch (e) { /* ignore */ }
    return 'site-default';
  }

  function validTag(url, asin) {
    return typeof url === 'string' && url.length < 1000 && url.indexOf('https://www.amazon.com/') === 0 && url.indexOf('maas') > -1 && url.indexOf(asin) > -1;
  }

  function run(win, doc) {
    var tags = win.TNK_ATTRIBUTION;
    if (!tags || typeof tags !== 'object' || !doc || !doc.querySelectorAll) return 0;
    var table = tags[campaignFor(win.location && win.location.search, win.sessionStorage)];
    if (!table) return 0;
    var swapped = 0;
    var anchors = doc.querySelectorAll('a[href*="amazon.com/dp/"]');
    for (var i = 0; i < anchors.length; i++) {
      var m = BUY.exec(anchors[i].getAttribute('href') || '');
      if (m && validTag(table[m[1]], m[1])) {
        anchors[i].setAttribute('href', table[m[1]]);
        swapped++;
      }
    }
    return swapped;
  }

  if (typeof module !== 'undefined' && module.exports) module.exports = { run: run, campaignFor: campaignFor, validTag: validTag };
  else if (typeof document !== 'undefined') run(root, document);
})(typeof window !== 'undefined' ? window : this);
