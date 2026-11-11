/* Header: expands the search field and drives the mobile drawer.
   No framework, no dependency. The links are server-rendered and stay in the
   DOM, so with JavaScript off the drawer simply renders as a stacked list. */
(function () {
  var header = document.querySelector('header');
  var bar = header && header.querySelector('.bar');
  var panel = document.getElementById('nav-panel');
  var toggle = document.getElementById('nav-toggle');
  var form = document.getElementById('site-search');
  var input = document.getElementById('search-input');
  var searchToggles = document.querySelectorAll('[data-search-toggle]');
  if (!header || !bar || !panel || !toggle || !form || !input || !searchToggles.length) { return; }

  var wide = window.matchMedia('(min-width: 1100px)');
  var desktopSearch = document.getElementById('search-toggle');
  var mobileSearch = document.querySelector('.nav-search-mobile');

  function menuOpen() { return document.body.classList.contains('nav-open'); }

  function visibleSearchToggle() {
    return wide.matches && desktopSearch ? desktopSearch : (mobileSearch || desktopSearch);
  }

  function setSearch(open) {
    bar.classList.toggle('search-open', open);
    searchToggles.forEach(function (button) {
      button.setAttribute('aria-expanded', open ? 'true' : 'false');
    });
    if (open) { input.focus(); }
  }

  function setMenu(open) {
    document.body.classList.toggle('nav-open', open);
    toggle.setAttribute('aria-expanded', open ? 'true' : 'false');
    if (!open) { setSearch(false); }
  }

  toggle.addEventListener('click', function () {
    var open = !menuOpen();
    setMenu(open);
    if (open) {
      var first = panel.querySelector('.nav-links a');
      if (first) { first.focus(); }
    }
  });

  searchToggles.forEach(function (button) {
    button.addEventListener('click', function () {
      if (wide.matches) {
        setSearch(!bar.classList.contains('search-open'));
      } else if (menuOpen()) {
        input.focus();
      } else {
        setMenu(true);
        input.focus();
      }
    });
  });

  panel.addEventListener('click', function (event) {
    if (event.target.closest('a')) { setMenu(false); }
  });

  /* Keep Tab inside the drawer while it covers the page. */
  panel.addEventListener('keydown', function (event) {
    if (event.key !== 'Tab' || !menuOpen()) { return; }
    var focusable = panel.querySelectorAll('a[href], button:not([disabled]), input, [tabindex]:not([tabindex="-1"])');
    if (!focusable.length) { return; }
    var first = focusable[0], last = focusable[focusable.length - 1];
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  });

  document.addEventListener('keydown', function (event) {
    if (event.key !== 'Escape') { return; }
    if (menuOpen()) {
      setMenu(false);
      toggle.focus();
    } else if (bar.classList.contains('search-open')) {
      setSearch(false);
      visibleSearchToggle().focus();
    }
  });

  document.addEventListener('click', function (event) {
    if (menuOpen() && !panel.contains(event.target) && !toggle.contains(event.target) &&
        !event.target.closest('[data-search-toggle]')) {
      setMenu(false);
    }
    if (wide.matches && bar.classList.contains('search-open') &&
        !form.contains(event.target) && !event.target.closest('[data-search-toggle]')) {
      setSearch(false);
    }
  });

  function onBreakpoint() { setMenu(false); }
  if (wide.addEventListener) { wide.addEventListener('change', onBreakpoint); }
  else if (wide.addListener) { wide.addListener(onBreakpoint); }
})();
