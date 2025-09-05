// /assets/js/lang-switch.js
(function () {
  function normalize(p) {
    p = p || "/";
    if (p === "/index.html") p = "/";
    if (p === "/es/index.html") p = "/es/";
    p = p.replace(/\/{2,}/g, "/");
    if (p !== "/" && p !== "/es/" && p.endsWith("/")) p = p.slice(0, -1);
    return p;
  }

  function targetFor(lang) {
    const p = normalize(location.pathname);
    const isES = p.startsWith("/es/");
    if (lang === "es") {
      if (isES) return p;
      return p === "/" ? "/es/" : "/es" + p;
    } else {
      // English
      if (isES) {
        const newPath = p.replace(/^\/es(\/|$)/, "/") || "/";
        return newPath === "" ? "/" : newPath;
      }
      return p || "/";
    }
  }

  // Click to switch
  document.addEventListener("click", function (e) {
    const a = e.target.closest('a[data-lang]');
    if (!a) return;
    e.preventDefault();
    location.assign(targetFor(a.getAttribute("data-lang")));
  });

  // Mark the active button on load
  (function markActive() {
    const isES = normalize(location.pathname).startsWith("/es/");
    document.querySelectorAll(".lang-switch a").forEach((el) => {
      const wantsES = el.getAttribute("data-lang") === "es";
      const active = wantsES ? isES : !isES;
      el.classList.toggle("active", active);
      el.setAttribute("aria-current", active ? "true" : "false");
    });
  })();
})();

