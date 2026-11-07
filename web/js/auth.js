/* Login, create account and logout talk to the Flask server. */
(function () {
  var body = document.body;
  function setUser(u) {
    body.classList.toggle('logged-in', !!u);
    body.classList.toggle('is-admin', !!(u && u.admin));
    if (window.ttPages) { window.ttPages.refresh(); }
  }
  async function post(url, data) {
    var res = await fetch(url, {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(data || {})});
    var json = {};
    try { json = await res.json(); } catch (e) {}
    return {ok: res.ok, data: json};
  }
  function show(el, cls, text) { el.className = 'status ' + cls; el.textContent = text; }

  fetch('/api/me').then(function (r) { return r.json(); }).then(function (j) { setUser(j.user); }).catch(function () {});

  function onHash() {
    if (location.hash === '#logout') { post('/api/logout').then(function () { setUser(null); }).catch(function () {}); }
  }
    document.getElementById('login-form').addEventListener('submit', async function (e) {
    e.preventDefault();
    var form = e.target, st = document.getElementById('login-status'), btn = form.querySelector('button');
    show(st, '', T('Checking...')); btn.disabled = true;
    try {
      var r = await post('/api/login', {email: document.getElementById('l-email').value, password: document.getElementById('l-pass').value});
      if (r.ok) {
        setUser(r.data.user); form.reset();
        show(st, 'ok', T('Welcome back, ') + r.data.user.name + '.');
        setTimeout(function () { location.hash = '#home'; st.textContent = ''; }, 900);
      } else { show(st, 'bad', T(r.data.error) || T('Login failed. Please try again.')); }
    } catch (err) { show(st, 'bad', T('Could not reach the server. Open the site through the server link.')); }
    btn.disabled = false;
  });

  document.getElementById('register-form').addEventListener('submit', async function (e) {
    e.preventDefault();
    var form = e.target, st = document.getElementById('register-status'), btn = form.querySelector('button');
    var pass = document.getElementById('c-pass').value;
    if (pass !== document.getElementById('c-pass2').value) { show(st, 'bad', T('The two passwords are not the same.')); return; }
    show(st, '', T('Creating your account...')); btn.disabled = true;
    try {
      var r = await post('/api/register', {
        first_name: document.getElementById('c-first').value,
        last_name: document.getElementById('c-last').value,
        email: document.getElementById('c-email').value,
        phone: document.getElementById('c-phone').value,
        password: pass
      });
      if (r.ok) {
        setUser(r.data.user); form.reset();
        show(st, 'ok', T('Account created. Welcome, ') + r.data.user.name + '.');
        setTimeout(function () { location.hash = '#home'; st.textContent = ''; }, 1100);
      } else { show(st, 'bad', T(r.data.error) || T('Could not create the account.')); }
    } catch (err) { show(st, 'bad', T('Could not reach the server. Open the site through the server link.')); }
    btn.disabled = false;
  });
})();
