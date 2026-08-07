// /assets/js/lang-switch.js
(function () {
  const SPECIAL_PAIRS = {
    "/for-professionals.html": "/es/para-profesionales.html",
    "/es/para-profesionales.html": "/for-professionals.html"
  };

  function norm(p) {
    p = p || "/";

    if (p === "/index.html") p = "/";
    if (p === "/es/index.html") p = "/es/";

    return p.replace(/\/{2,}/g, "/");
  }

  function stripEs(p) {
    return p.replace(/^\/es(\/|$)/, "/");
  }

  function applyTargets() {
    const en = document.querySelector('.lang-switch [data-lang="en"]');
    const es = document.querySelector('.lang-switch [data-lang="es"]');

    if (!en || !es) return false;

    const p = norm(location.pathname);
    const isES = p.startsWith("/es/");

    let enHref;
    let esHref;

    if (SPECIAL_PAIRS[p]) {
      if (isES) {
        enHref = SPECIAL_PAIRS[p];
        esHref = p;
      } else {
        enHref = p;
        esHref = SPECIAL_PAIRS[p];
      }
    } else {
      enHref = isES ? (stripEs(p) || "/") : (p || "/");
      esHref = isES ? p : (p === "/" ? "/es/" : "/es" + p);
    }

    en.href = enHref;
    es.href = esHref;

    // Make destination language explicit.
    en.lang = "en";
    en.hreflang = "en";
    en.setAttribute("aria-label", "English");

    es.lang = "es";
    es.hreflang = "es";
    es.setAttribute("aria-label", "Español");

    [en, es].forEach((a) => {
      a.classList.remove("active");
      a.removeAttribute("aria-current");
    });

    const active = isES ? es : en;
    active.classList.add("active");
    active.setAttribute("aria-current", "true");

    return true;
  }

  // Wait until .lang-switch exists because the header is runtime-included.
  function whenLangSwitchReady(cb, timeoutMs = 4000) {
    if (document.querySelector('.lang-switch a[data-lang]')) {
      cb();
      return;
    }

    const obs = new MutationObserver(() => {
      if (document.querySelector('.lang-switch a[data-lang]')) {
        obs.disconnect();
        cb();
      }
    });

    obs.observe(document.documentElement, {
      childList: true,
      subtree: true
    });

    setTimeout(() => obs.disconnect(), timeoutMs);
  }

  function init() {
    if (applyTargets()) return;

    whenLangSwitchReady(() => {
      applyTargets();
    });
  }

  window.addEventListener("popstate", init);

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init, { once: true });
  } else {
    init();
  }

  window.__langSwitchRefresh = init;
})();
