/* Forgot-password and reset-password forms. Loaded only on /forgot and /reset. */
(function () {
  function post(url, data) {
    return window.ttFetch(url, {
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

  var forgot = document.getElementById('forgot-form');
  if (forgot) {
    forgot.addEventListener('submit', async function (e) {
      e.preventDefault();
      var st = document.getElementById('forgot-status'), btn = forgot.querySelector('button[type="submit"]');
      show(st, '', T('Sending...')); btn.disabled = true;
      try {
        var r = await post('/api/password/forgot', {email: document.getElementById('f-email').value});
        if (r.ok) {
          show(st, 'ok', T(r.data.message));
          forgot.reset();
        } else {
          show(st, 'bad', T(r.data.error) || T('Something went wrong. Please try again.'));
        }
      } catch (err) {
        show(st, 'bad', T('Could not reach the server. Open the site through the server link.'));
      }
      btn.disabled = false;
    });
  }

  var reset = document.getElementById('reset-form');
  if (reset) {
    reset.addEventListener('submit', async function (e) {
      e.preventDefault();
      var st = document.getElementById('reset-status'), btn = reset.querySelector('button[type="submit"]');
      var pass = document.getElementById('r-pass').value;
      if (pass !== document.getElementById('r-pass2').value) {
        show(st, 'bad', T('The two passwords are not the same.'));
        return;
      }
      show(st, '', T('Saving...')); btn.disabled = true;
      try {
        var r = await post('/api/password/reset', {
          token: document.getElementById('r-token').value,
          password: pass
        });
        if (r.ok) {
          show(st, 'ok', T(r.data.message));
          reset.reset();
          setTimeout(function () { location.assign('/account#login'); }, 1400);
        } else {
          show(st, 'bad', T(r.data.error) || T('Something went wrong. Please try again.'));
        }
      } catch (err) {
        show(st, 'bad', T('Could not reach the server. Open the site through the server link.'));
      }
      btn.disabled = false;
    });
  }
})();
