function includeHTML() {
  const elements = document.querySelectorAll('[data-include]');
  const promises = [];

  elements.forEach(el => {
    const file = el.getAttribute('data-include');
    if (file) {
      promises.push(
        fetch(file)
          .then(response => response.text())
          .then(data => {
            el.innerHTML = data;
            el.removeAttribute('data-include');
          })
      );
    }
  });

  // After all includes are done, run again to catch nested includes
  Promise.all(promises).then(() => {
    if (document.querySelector('[data-include]')) {
      includeHTML();
    }
  });
}

document.addEventListener('DOMContentLoaded', includeHTML);

