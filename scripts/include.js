function includeHTML() {
  const elements = document.querySelectorAll('[data-include]');
  elements.forEach(el => {
    const file = el.getAttribute('data-include');
    fetch(file)
      .then(res => {
        if (res.ok) return res.text();
        throw new Error(`Could not fetch ${file}`);
      })
      .then(data => {
        el.innerHTML = data;

        // NEW: execute any <script> tags inside the included file
        el.querySelectorAll("script").forEach(oldScript => {
          const s = document.createElement("script");
          // copy attributes (like src, type, defer, etc.)
          [...oldScript.attributes].forEach(attr => s.setAttribute(attr.name, attr.value));
          if (!s.src) s.textContent = oldScript.textContent;
          oldScript.replaceWith(s); // executes
        });
      })
      .catch(err => {
        el.innerHTML = `<div style="color: red;">${err.message}</div>`;
      });
  });
}

window.addEventListener('DOMContentLoaded', includeHTML);

