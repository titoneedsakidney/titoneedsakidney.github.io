// /scripts/active-link.js
(function highlightActiveLinks() {
  var here = location.pathname.replace(/index\.html$/, '');
  var navs = document.querySelectorAll('nav.js-active-nav');
  if (!navs.length) { return setTimeout(highlightActiveLinks, 50); } // wait for includes

  navs.forEach(function(nav){
    var exactHit = false;

    // 1) Exact match pass
    nav.querySelectorAll('a').forEach(function(a){
      var href = (a.getAttribute('href') || '').replace(/index\.html$/, '');
      if (href && href === here) {
        a.classList.add('active');
        a.setAttribute('aria-current', 'page');
        exactHit = true;
      }
    });

    // 2) Fallback prefix match (only if no exact match in this nav)
    if (!exactHit) {
      nav.querySelectorAll('a[data-prefix]').forEach(function(a){
        var prefix = a.getAttribute('data-prefix');
        if (prefix && here.startsWith(prefix)) {
          a.classList.add('active');
          a.setAttribute('aria-current', 'page');
        }
      });
    }
  });
})();

