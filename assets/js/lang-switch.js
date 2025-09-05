// assets/js/lang-switch.js
(function () {
  function normalizedPathname() {
    let p = location.pathname || "/";
    if (p === "/index.html") p = "/";
    if (p === "/es/index.html") p = "/es/";
    // prevent accidental double slashes, remove trailing slash (except root and /es/)
    p = p.replace(/\/{2,}/g, "/");
    if (p !== "/" && p !== "/es/" && p.endsWith("/")) p = p.slice(0, -1);
    return p;
  }

  function targetFor(lang) {
    const p = normalizedPathname();
    const isES = p.startsWith("/es/");
    if (lang === "es") {
      if (isES) return p;            // already Spanish
      if (p === "/") return "/es/";  // home → /es/
      return "/es" + p;              // page → /es/page
    }
    // lang === 'en'
    if (isES) {
      const newPath = p.replace(/^\/es(\/|$)/, "/") || "/";
      return newPath === "" ? "/" : newPath;
    }
    return p;                         // already English
  }

  document.addEventListener("click", function (e) {
    const a = e.target.closest('a[data-lang]');
    if (!a) return;
    e.preventDefault();
    const lang = a.getAttribute("data-lang");
    if (!lang) return;
    location.assign(targetFor(lang));
  });

  // Nice-to-have: mark the active toggle
  (function markActive() {
    const isES = normalizedPathname().startsWith("/es/");
    document.querySelectorAll("[data-lang]").forEach((el) => {
      const wantsES = el.getAttribute("data-lang") === "es";
      const active = wantsES ? isES : !isES;
      el.classList.toggle("active", active);
      el.setAttribute("aria-current", active ? "true" : "false");
    });
  })();
})();

