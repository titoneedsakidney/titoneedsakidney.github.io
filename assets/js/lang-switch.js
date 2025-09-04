(function(){
  const a = document.querySelector('[data-lang-toggle]');
  if(!a) return;
  const p = location.pathname;
  const isES = p.startsWith('/es/');
  a.href = isES ? (p.replace(/^\/es/, '') || '/') : ('/es' + p);
})();
