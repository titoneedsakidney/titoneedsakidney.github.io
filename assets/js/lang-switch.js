(function(){
  function switchTo(lang){
    var path = window.location.pathname;
    if (lang === 'es') {
      if (path === '/' || path === '/index.html') { window.location.href = '/es/'; return; }
      if (path.startsWith('/es/')) return;
      window.location.href = '/es' + (path.startsWith('/') ? path : '/' + path);
    } else { // en
      if (path.startsWith('/es/')) {
        var newPath = path.replace(/^\/es(\/|$)/, '/');
        window.location.href = newPath === '' ? '/' : newPath;
      }
    }
  }
  document.addEventListener('click', function(e){
    var a = e.target.closest('a[data-lang]');
    if (!a) return;
    e.preventDefault();
    switchTo(a.getAttribute('data-lang'));
  });
})();

