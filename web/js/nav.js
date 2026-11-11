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

  /* ===== Signed-in avatar menu (desktop only; the drawer shows identity) ===== */
  var userBox = document.getElementById('nav-user');
  var avatarToggle = document.getElementById('avatar-toggle');
  var avatarMenu = document.getElementById('avatar-menu');
  var initialsEl = document.getElementById('avatar-initials');
  var adminItem = avatarMenu && avatarMenu.querySelector('.avatar-admin');

  function closeAvatar() {
    if (!avatarMenu || avatarMenu.hidden) { return; }
    avatarMenu.hidden = true;
    avatarToggle.setAttribute('aria-expanded', 'false');
  }

  function setText(selector, value) {
    document.querySelectorAll(selector).forEach(function (node) { node.textContent = value || ''; });
  }

  if (avatarToggle && avatarMenu && userBox) {
    avatarToggle.addEventListener('click', function () {
      if (!wide.matches) { location.assign('/account'); return; }
      if (avatarMenu.hidden) {
        avatarMenu.hidden = false;
        avatarToggle.setAttribute('aria-expanded', 'true');
      } else {
        closeAvatar();
      }
    });

    avatarMenu.addEventListener('click', function (event) {
      if (event.target.closest('a')) { closeAvatar(); }
    });

    /* Login and logout happen over fetch on /account; session.js emits this. */
    window.addEventListener('tt:user', function (event) {
      var user = event.detail;
      closeAvatar();
      if (!user) { return; }
      if (initialsEl) { initialsEl.textContent = user.initials || ''; }
      setText('.js-user-name', user.name);
      setText('.js-user-email', user.email);
      setText('.nav-user-name', user.name);
      setText('.nav-user-email', user.email);
      if (adminItem) { adminItem.hidden = !user.admin; }
    });
  }

  document.addEventListener('keydown', function (event) {
    if (event.key !== 'Escape') { return; }
    if (menuOpen()) {
      setMenu(false);
      toggle.focus();
    } else if (avatarMenu && !avatarMenu.hidden) {
      closeAvatar();
      avatarToggle.focus();
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
    if (avatarToggle && avatarMenu && !avatarMenu.hidden && userBox &&
        !userBox.contains(event.target)) {
      closeAvatar();
    }
    if (wide.matches && bar.classList.contains('search-open') &&
        !form.contains(event.target) && !event.target.closest('[data-search-toggle]')) {
      setSearch(false);
    }
  });

  function onBreakpoint() {
    setMenu(false);
    if (avatarMenu) { closeAvatar(); }
  }
  if (wide.addEventListener) { wide.addEventListener('change', onBreakpoint); }
  else if (wide.addListener) { wide.addListener(onBreakpoint); }
})();
