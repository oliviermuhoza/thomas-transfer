/* Three-dots menu: opens on click, closes on outside click, Escape or when a page link is chosen. */
(function () {
  var box = document.querySelector('.more'), btn = document.getElementById('more-btn');
  var sBtn = document.getElementById('settings-toggle'), sPanel = document.getElementById('settings-panel');
  function setOpen(open) { box.classList.toggle('open', open); btn.setAttribute('aria-expanded', open ? 'true' : 'false'); }
  btn.addEventListener('click', function (e) { e.stopPropagation(); setOpen(!box.classList.contains('open')); });
  document.addEventListener('click', function (e) { if (!box.contains(e.target)) { setOpen(false); } });
  document.addEventListener('keydown', function (e) { if (e.key === 'Escape' && box.classList.contains('open')) { setOpen(false); btn.focus(); } });
  box.querySelectorAll('.menu-list a').forEach(function (a) { a.addEventListener('click', function () { setOpen(false); }); });
  var supBtn = document.getElementById('support-toggle'), supPanel = document.getElementById('support-panel');
  supBtn.addEventListener('click', function () {
    var show = supPanel.hasAttribute('hidden');
    if (show) { supPanel.removeAttribute('hidden'); } else { supPanel.setAttribute('hidden', ''); }
    supBtn.setAttribute('aria-expanded', show ? 'true' : 'false');
  });
  sBtn.addEventListener('click', function () {
    var show = sPanel.hasAttribute('hidden');
    if (show) { sPanel.removeAttribute('hidden'); } else { sPanel.setAttribute('hidden', ''); }
    sBtn.setAttribute('aria-expanded', show ? 'true' : 'false');
  });
})();
