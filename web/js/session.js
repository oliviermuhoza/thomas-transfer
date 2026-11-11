/* Session state shared by every page: /api/me, CSRF token, body classes,
   logout and remembering which car a "book" link pointed at. */
(function () {
  var body = document.body;

  function setCsrf(token) {
    if (token) { window.ttCsrf = token; }
  }

  function setUser(user, rerender) {
    body.classList.toggle('logged-in', !!user);
    body.classList.toggle('is-admin', !!(user && user.admin));
    window.ttUser = user || null;
    window.dispatchEvent(new CustomEvent('tt:user', {detail: user || null}));
    if (rerender !== false && window.ttPages) { window.ttPages.refresh(); }
  }

  window.ttSetUser = function (user, csrfToken) { setCsrf(csrfToken); setUser(user, true); };
  window.ttSetCsrf = setCsrf;
  window.ttCsrfHeaders = function (headers) {
    headers = headers || {'Content-Type': 'application/json'};
    if (window.ttCsrf) { headers['X-CSRF-Token'] = window.ttCsrf; }
    return headers;
  };

  /* CSRF bootstrap. Forms used to send the header only when the token happened
     to be known already, so a submit that beat /api/me went out without it and
     the server answered "Invalid or missing CSRF token". Every caller now waits
     on the same token source. */
  var csrfPromise = null;
  var bootstrap = null;

  function readToken(url) {
    return fetch(url, {credentials: 'same-origin'})
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (json) { setCsrf(json && json.csrf_token); return window.ttCsrf || null; })
      .catch(function () { return null; });
  }

  function refreshToken() {
    if (!csrfPromise) {
      csrfPromise = readToken('/api/csrf')
        .then(function (token) { return token || readToken('/api/me'); })
        .then(function (token) { csrfPromise = null; return token || window.ttCsrf || null; });
    }
    return csrfPromise;
  }

  function ensureCsrf() {
    if (window.ttCsrf) { return Promise.resolve(window.ttCsrf); }
    if (bootstrap) {
      return bootstrap.then(function () { return window.ttCsrf || refreshToken(); });
    }
    return refreshToken();
  }
  window.ttEnsureCsrf = ensureCsrf;

  /* All mutating calls go through here: the token is fetched first when it is
     not known yet, and a stale token (login or logout in another tab rotates it)
     is refreshed once instead of reaching the user as a 403. */
  window.ttFetch = function (url, options) {
    options = options || {};
    function attempt() {
      return ensureCsrf().then(function () {
        var opts = {
          method: options.method || 'GET',
          credentials: 'same-origin',
          headers: window.ttCsrfHeaders(Object.assign({}, options.headers || {}))
        };
        if (options.body !== undefined) { opts.body = options.body; }
        return fetch(url, opts);
      });
    }
    return attempt().then(function (res) {
      if (res.status !== 403) { return res; }
      return res.clone().json().catch(function () { return {}; }).then(function (json) {
        if (!json || !/csrf/i.test(json.error || '')) { return res; }
        window.ttCsrf = null;
        csrfPromise = null;
        bootstrap = null;
        return attempt();
      });
    });
  };

  function logout() {
    window.ttFetch('/api/logout', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: '{}'
    })
      .then(function (r) { return r.json().catch(function () { return {}; }); })
      .then(function (json) { setCsrf(json.csrf_token); setUser(null, true); })
      .catch(function () { setUser(null, true); });
  }

  /* The page's own session lookup also yields the token. Forms wait on it while
     it is in flight instead of opening a second session that could mint a
     different token. */
  bootstrap = fetch('/api/me', {credentials: 'same-origin'})
    .then(function (r) { return r.json(); })
    .then(function (json) { setCsrf(json.csrf_token); setUser(json.user, false); return window.ttCsrf || null; })
    .catch(function () { return null; });

  if (location.hash === '#logout') { logout(); }
  window.addEventListener('hashchange', function () {
    if (location.hash === '#logout') { logout(); }
  });

  function updateAuthMode() {
    var h = location.hash;
    body.classList.toggle(
      'auth-mode',
      body.dataset.page === 'account' && (h === '#login' || h === '#create-account' || h === '#logout')
    );
  }
  window.addEventListener('hashchange', updateAuthMode);
  updateAuthMode();

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
