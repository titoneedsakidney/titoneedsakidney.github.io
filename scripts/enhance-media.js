
(function () {
  // Add lazy loading/async decoding to images that don't have them
  document.querySelectorAll('img:not([loading])').forEach(img => img.loading = 'lazy');
  document.querySelectorAll('img:not([decoding])').forEach(img => img.decoding = 'async');

  // Dev aid: flag images missing alt text (doesn't affect SEO; just helps you fix)
  document.querySelectorAll('img:not([alt])').forEach(img => {
    img.alt = ""; // avoid failing validators; still log for you
    console.warn('Image missing alt:', img.src);
    img.style.outline = '2px dashed #d33'; img.style.outlineOffset = '4px';
  });
})();


