(function () {
  var btn = document.getElementById('menuBtn');
  var nav = document.getElementById('nav');
  if (btn && nav) {
    btn.addEventListener('click', function () {
      var open = nav.classList.toggle('open');
      btn.setAttribute('aria-expanded', open ? 'true' : 'false');
    });
    nav.addEventListener('click', function (e) {
      if (e.target.tagName === 'A') { nav.classList.remove('open'); btn.setAttribute('aria-expanded', 'false'); }
    });
  }

  var main = document.getElementById('galleryMain');
  var mainBtn = document.querySelector('.gallery-main');
  var caption = document.getElementById('galleryCaption');
  document.querySelectorAll('.thumb').forEach(function (t) {
    t.addEventListener('click', function () {
      if (!main) return;
      main.src = t.dataset.src;
      main.alt = t.dataset.alt || '';
      if (mainBtn) mainBtn.dataset.full = t.dataset.src;
      document.querySelectorAll('.thumb').forEach(function (x) { x.classList.remove('on'); });
      t.classList.add('on');
    });
  });

  var box = document.getElementById('lightbox');
  if (box && mainBtn) {
    var img = box.querySelector('img');
    mainBtn.addEventListener('click', function () { img.src = mainBtn.dataset.full; box.hidden = false; });
    box.addEventListener('click', function () { box.hidden = true; });
    document.addEventListener('keydown', function (e) { if (e.key === 'Escape') box.hidden = true; });
  }
})();
