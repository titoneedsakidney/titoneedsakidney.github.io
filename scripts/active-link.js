// /scripts/active-link.js
(function highlightActiveLinks() {
  // Normalize a path: strip index.html, trailing slash (except root)
  function norm(pathname) {
    return pathname
      .replace(/index\.html$/i, '')
      .replace(/\/+$/, pathname === '/' ? '/' : '');
  }

  const here = norm(location.pathname);

  // Wait for includes to land without spin-waiting forever
  const run = () => {
    const navs = document.querySelectorAll('nav.js-active-nav');
    if (!navs.length || !document.querySelector('nav.js-active-nav a')) {
      return setTimeout(run, 60);
    }

    navs.forEach(nav => {
      let exactHit = false;

      nav.querySelectorAll('a[href]').forEach(a => {
        // Ignore off-origin links
        const u = new URL(a.getAttribute('href'), location.origin);
        if (u.origin !== location.origin) return;

        const hrefPath = norm(u.pathname);

        // Exact match first
        if (hrefPath === here) {
          a.classList.add('active');
          a.setAttribute('aria-current', 'page');
          exactHit = true;
        }
      });

// 2) Fallback prefix match (pick the single longest match)
if (!exactHit) {
  var best = null, bestLen = -1;
  nav.querySelectorAll('a[data-prefix]').forEach(function(a){
    var prefix = (a.getAttribute('data-prefix') || '').replace(/index\.html$/, '');
    if (prefix && here.startsWith(prefix) && prefix.length > bestLen) {
      best = a; bestLen = prefix.length;
    }
  });
  if (best) {
    best.classList.add('active');
    best.setAttribute('aria-current', 'page');
  }
}
    });
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', run);
  } else {
    run();
  }
})();



