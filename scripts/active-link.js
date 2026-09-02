// /scripts/active-link.js
(function highlightActiveLinks() {
  // Normalize a path: strip index.html, trailing slash (except root)
  function norm(pathname) {
    const normalized = pathname.replace(/index\.html$/i, '');
    return normalized === '/' ? '/' : normalized.replace(/\/+$/, '');
  }

  const here = norm(location.pathname);

  function syncLanguageSwitch() {
    document.querySelectorAll('.lang-switch a[data-lang]').forEach(link => {
      const language = link.getAttribute('data-lang');
      const alternate = document.querySelector(
        `link[rel~="alternate"][hreflang="${language}"]`
      );

      // Metadata declares an alternate only when the translated counterpart
      // exists. Keep the include's homepage fallback for pages without one.
      if (alternate) {
        const destination = new URL(alternate.getAttribute('href'), location.origin);
        link.setAttribute('href', destination.pathname + destination.hash);
      }
    });
  }

  // Includes are expanded at build time, so one pass after DOM readiness is enough.
  const run = () => {
    syncLanguageSwitch();
    const navs = document.querySelectorAll('nav.js-active-nav');

    navs.forEach(nav => {
      const links = Array.from(nav.querySelectorAll('a[href]'));
      let match = null;

      links.forEach(a => {
        a.classList.remove('active');
        a.removeAttribute('aria-current');
      });

      // Exact matching takes priority over hierarchical navigation.
      match = links.find(a => {
        const url = new URL(a.getAttribute('href'), location.origin);
        return url.origin === location.origin && norm(url.pathname) === here;
      });

      // Otherwise, use the most-specific declared prefix in this region.
      if (!match) {
        let bestLength = -1;
        links.filter(a => a.hasAttribute('data-prefix')).forEach(a => {
          const prefix = norm(new URL(
            a.getAttribute('data-prefix'), location.origin
          ).pathname);

          if (prefix && here.startsWith(prefix) && prefix.length > bestLength) {
            match = a;
            bestLength = prefix.length;
          }
        });
      }

      if (match) {
        match.classList.add('active');
        match.setAttribute('aria-current', 'page');
      }
    });
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', run);
  } else {
    run();
  }
})();
