(() => {
  'use strict';

  const MEASUREMENT_ID = 'G-JHT0DBJBHH';
  const PRODUCTION_ORIGIN = 'https://titoneedsakidney.com';
  const AUDIT_QUERY_PARAMETER = 'analytics_test';
  const AUDIT_SESSION_KEY = 'tnk_analytics_test';

  let auditSession = false;
  try {
    auditSession = new URLSearchParams(window.location.search)
      .get(AUDIT_QUERY_PARAMETER) === '1';
    if (auditSession) {
      window.sessionStorage.setItem(AUDIT_SESSION_KEY, '1');
    } else {
      auditSession = window.sessionStorage.getItem(AUDIT_SESSION_KEY) === '1';
    }
  } catch (_) {
    // A restrictive browser may block storage. The hostname guard still applies.
  }

  if (window.location.origin !== PRODUCTION_ORIGIN || auditSession) {
    window[`ga-disable-${MEASUREMENT_ID}`] = true;
    return;
  }

  const googleTag = document.createElement('script');
  googleTag.async = true;
  googleTag.src = `https://www.googletagmanager.com/gtag/js?id=${MEASUREMENT_ID}`;
  document.head.appendChild(googleTag);
})();
