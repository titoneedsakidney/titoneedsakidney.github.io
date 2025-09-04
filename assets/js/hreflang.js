(() => {
  try {
    const head = document.head || document.getElementsByTagName('head')[0];
    if (!head) return;

    const origin = (location.origin && location.origin !== 'null')
      ? location.origin
      : (location.protocol + '//' + location.host);

    const norm = (p) => {
      if (!p) return '/';
      if (p[0] !== '/') p = '/' + p;
      p = p.replace(/\/index\.html$/i, '/');
      p = p.replace(/\/{2,}/g, '/');
      if (p !== '/' && p.endsWith('/')) p = p.slice(0, -1);
      return p;
    };

    const path   = norm(location.pathname);
    const enPath = path.startsWith('/es/') ? norm(path.replace(/^\/es/, '')) : path;
    const esPath = path.startsWith('/es/') ? path : (enPath === '/' ? '/es/' : '/es' + enPath);

    const enHref = origin + (enPath === '/' ? '/' : enPath);
    const esHref = origin + (esPath === '/es/' ? '/es/' : esPath);

    const ensureAlt = (hreflang, href) => {
      if (document.querySelector(`link[rel="alternate"][hreflang="${hreflang}"]`)) return;
      const l = document.createElement('link');
      l.rel = 'alternate';
      l.hreflang = hreflang;
      l.href = href;
      head.appendChild(l);
    };

    ensureAlt('en', enHref);
    ensureAlt('es', esHref);

    // Homepage gets x-default
    if (enPath === '/' || enPath === '/index.html') {
      ensureAlt('x-default', enHref);
    }
  } catch (_) { /* no-op */ }
})();
