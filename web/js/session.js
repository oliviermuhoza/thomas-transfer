/* Session state shared by every page: /api/me, body classes, logout and
   remembering which car a "book" link pointed at. */
(function () {
  var body = document.body;

  function setUser(user, rerender) {
    body.classList.toggle('logged-in', !!user);
    body.classList.toggle('is-admin', !!(user && user.admin));
    window.ttUser = user || null;
    window.dispatchEvent(new CustomEvent('tt:user', {detail: user || null}));
    if (rerender !== false && window.ttPages) { window.ttPages.refresh(); }
  }

  window.ttSetUser = function (user) { setUser(user, true); };

  function logout() {
    fetch('/api/logout', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: '{}'})
      .then(function () { setUser(null, true); })
      .catch(function () {});
  }

  fetch('/api/me')
    .then(function (r) { return r.json(); })
    .then(function (json) { setUser(json.user, false); })
    .catch(function () {});

  if (location.hash === '#logout') { logout(); }
  window.addEventListener('hashchange', function () {
    if (location.hash === '#logout') { logout(); }
  });

  /* Remember a car chosen on a marketing page so /account#available can
     preselect it after the full page navigation. */
  document.addEventListener('click', function (e) {
    var link = e.target.closest ? e.target.closest('[data-book]') : null;
    if (!link) { return; }
    var id = link.getAttribute('data-book');
    window.ttSelectedCar = id;
    try { sessionStorage.setItem('tt-selected-car', id); } catch (err) {}
  });
})();
