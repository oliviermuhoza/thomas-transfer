/* Login and create-account forms. Loaded only on /account. */
(function () {
  function post(url, data) {
    return fetch(url, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(data || {})
    }).then(async function (res) {
      var json = {};
      try { json = await res.json(); } catch (e) {}
      return {ok: res.ok, data: json};
    });
  }
  function show(el, cls, text) { el.className = 'status ' + cls; el.textContent = text; }

  var loginForm = document.getElementById('login-form');
  if (loginForm) {
    loginForm.addEventListener('submit', async function (e) {
      e.preventDefault();
      var form = e.target, st = document.getElementById('login-status'), btn = form.querySelector('button[type="submit"]');
      show(st, '', T('Checking...')); btn.disabled = true;
      try {
        var r = await post('/api/login', {
          email: document.getElementById('l-email').value,
          password: document.getElementById('l-pass').value
        });
        if (r.ok) {
          window.ttSetUser(r.data.user);
          form.reset();
          show(st, 'ok', T('Welcome back, ') + r.data.user.name + '.');
          setTimeout(function () { location.hash = '#available'; st.textContent = ''; }, 900);
        } else {
          show(st, 'bad', T(r.data.error) || T('Login failed. Please try again.'));
        }
      } catch (err) {
        show(st, 'bad', T('Could not reach the server. Open the site through the server link.'));
      }
      btn.disabled = false;
    });
  }

  var registerForm = document.getElementById('register-form');
  if (registerForm) {
    registerForm.addEventListener('submit', async function (e) {
      e.preventDefault();
      var form = e.target, st = document.getElementById('register-status'), btn = form.querySelector('button[type="submit"]');
      var pass = document.getElementById('c-pass').value;
      if (pass !== document.getElementById('c-pass2').value) {
        show(st, 'bad', T('The two passwords are not the same.'));
        return;
      }
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
          window.ttSetUser(r.data.user);
          form.reset();
          show(st, 'ok', T('Account created. Welcome, ') + r.data.user.name + '.');
          setTimeout(function () { location.hash = '#available'; st.textContent = ''; }, 1100);
        } else {
          show(st, 'bad', T(r.data.error) || T('Could not create the account.'));
        }
      } catch (err) {
        show(st, 'bad', T('Could not reach the server. Open the site through the server link.'));
      }
      btn.disabled = false;
    });
  }

  document.querySelectorAll('.auth-toggle[data-toggle]').forEach(function (btn) {
    btn.addEventListener('click', function () {
      var input = document.getElementById(btn.getAttribute('data-toggle'));
      if (!input) return;
      var show = input.type === 'password';
      input.type = show ? 'text' : 'password';
      btn.setAttribute('aria-pressed', show ? 'true' : 'false');
      btn.setAttribute('aria-label', show ? T('Hide password') : T('Show password'));
    });
  });
})();
