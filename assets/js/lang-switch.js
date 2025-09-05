// /assets/js/lang-switch.js
(function () {
  function norm(p) {
    p = p || "/";
    if (p === "/index.html") p = "/";
    if (p === "/es/index.html") p = "/es/";
    return p.replace(/\/{2,}/g, "/");
  }
  function stripEs(p) { return p.replace(/^\/es(\/|$)/, "/"); }

  function computeTargets() {
    var p = norm(location.pathname);
    var isES = p.startsWith("/es/");
    var enHref = isES ? (stripEs(p) || "/") : (p || "/");
    var esHref = isES ? p : (p === "/" ? "/es/" : "/es" + p);
    return { p, isES, enHref, esHref };
  }

  function applyTargets() {
    var links = document.querySelectorAll(".lang-switch a[data-lang]");
    if (!links.length) {
      console.warn("[lang] .lang-switch links not found in DOM");
      return false;
    }
    var en = document.querySelector('.lang-switch [data-lang="en"]');
    var es = document.querySelector('.lang-switch [data-lang="es"]');
    if (!en || !es) {
      console.warn("[lang] EN/ES link missing");
      return false;
    }

    var { p, isES, enHref, esHref } = computeTargets();
    en.href = enHref;
    es.href = esHref;

    // Clear then paint active (in case of turbolinks, partial reloads, etc.)
    [en, es].forEach(a => { a.classList.remove("active"); a.removeAttribute("aria-current"); });
    (isES ? es : en).classList.add("active");
    (isES ? es : en).setAttribute("aria-current", "true");

    console.log("[lang] OK",
      { path: p, isES, EN: enHref, ES: esHref,
        enInDom: !!en, esInDom: !!es,
        langSwitchCount: document.querySelectorAll(".lang-switch").length });
    return true;
  }

  // Run after DOM is parsed (defensive even with defer)
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", applyTargets, { once: true });
  } else {
    applyTargets();
  }

  // If someone hot-swaps content (PJAX/htmx), expose a manual kick:
  window.__langSwitchRefresh = applyTargets;
})();
