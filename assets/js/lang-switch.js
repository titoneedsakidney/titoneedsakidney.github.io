// /assets/js/lang-switch.js
(function () {
  function norm(p) {
    p = p || "/";
    if (p === "/index.html") p = "/";
    if (p === "/es/index.html") p = "/es/";
    return p.replace(/\/{2,}/g, "/");
  }
  function stripEs(p) { return p.replace(/^\/es(\/|$)/, "/"); }

  function applyTargets() {
    const en = document.querySelector('.lang-switch [data-lang="en"]');
    const es = document.querySelector('.lang-switch [data-lang="es"]');
    if (!en || !es) return false;

    const p = norm(location.pathname);
    const isES = p.startsWith("/es/");
    const enHref = isES ? (stripEs(p) || "/") : (p || "/");
    const esHref = isES ? p : (p === "/" ? "/es/" : "/es" + p);

    en.href = enHref;
    es.href = esHref;

    [en, es].forEach(a => { a.classList.remove("active"); a.removeAttribute("aria-current"); });
    (isES ? es : en).classList.add("active");
    (isES ? es : en).setAttribute("aria-current", "true");
    return true;
  }

  // Wait until .lang-switch exists (handles include loaders)
  function whenLangSwitchReady(cb, timeoutMs = 4000) {
    if (document.querySelector('.lang-switch a[data-lang]')) return void cb();

    const obs = new MutationObserver(() => {
      if (document.querySelector('.lang-switch a[data-lang]')) {
        obs.disconnect();
        cb();
      }
    });
    obs.observe(document.documentElement, { childList: true, subtree: true });

    // safety timeout (don’t watch forever)
    setTimeout(() => obs.disconnect(), timeoutMs);
  }

  function init() {
    // try immediately
    if (applyTargets()) return;

    // if not present yet, wait for includes to finish
    whenLangSwitchReady(() => { applyTargets(); });
  }

  // Re-apply on back/forward navigations (SPA-ish navs, history pops)
  window.addEventListener('popstate', init);

  // Run as soon as parsing is done (even if defer is used)
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init, { once: true });
  } else {
    init();
  }

  // expose manual refresh if needed
  window.__langSwitchRefresh = init;
})();

