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
      })
      .catch(err => {
        el.innerHTML = `<div style="color: red;">${err.message}</div>`;
      });
  });
}

window.addEventListener('DOMContentLoaded', includeHTML);
