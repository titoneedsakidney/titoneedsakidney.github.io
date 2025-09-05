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
    var en = document.querySelector('.lang-switch [data-lang="en"]');
    var es = document.querySelector('.lang-switch [data-lang="es"]');
    if (!en || !es) return false;

    var s = computeTargets();
    en.href = s.enHref;
    es.href = s.esHref;

    // paint active
    [en, es].forEach(a => { a.classList.remove("active"); a.removeAttribute("aria-current"); });
    (s.isES ? es : en).classList.add("active");
    (s.isES ? es : en).setAttribute("aria-current", "true");
    return true;
  }

  // Run after DOM is parsed
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", applyTargets, { once: true });
  } else {
    applyTargets();
  }
})();

