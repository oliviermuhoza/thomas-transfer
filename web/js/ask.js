/* Ask Tom: floating button opens a dialog, the question is sent to /api/contact. */
(function () {
  var dlg = document.getElementById('ask-dialog'), form = document.getElementById('ask-form');
  var status = document.getElementById('ask-status'), openBtn = document.getElementById('ask-float');
  if (!dlg || !form || !status || !openBtn) { return; }

  openBtn.addEventListener('click', function () {
    status.className = 'status'; status.textContent = '';
    var u = window.ttUser;
    if (u) {
      if (u.name) { document.getElementById('ask-name').value = u.name; }
      if (u.email) { document.getElementById('ask-email').value = u.email; }
    }
    document.body.classList.add('msg-open');
    if (dlg.showModal) { dlg.showModal(); } else { dlg.setAttribute('open', ''); }
    document.getElementById('ask-question').focus();
  });

  document.getElementById('ask-close').addEventListener('click', function () { dlg.close(); });
  dlg.addEventListener('close', function () { document.body.classList.remove('msg-open'); });
  dlg.addEventListener('click', function (e) { if (e.target === dlg) { dlg.close(); } });

  form.addEventListener('submit', async function (e) {
    e.preventDefault();
    var btn = form.querySelector('button[type="submit"]');
    status.className = 'status'; status.textContent = T('Sending...'); btn.disabled = true;
    try {
      var headers = {'Content-Type': 'application/json'};
      if (window.ttCsrf) { headers['X-CSRF-Token'] = window.ttCsrf; }
      var res = await fetch('/api/contact', {
        method: 'POST', headers: headers,
        body: JSON.stringify({
          name: document.getElementById('ask-name').value,
          email: document.getElementById('ask-email').value,
          service: 'Ask Tom',
          message: document.getElementById('ask-question').value
        })
      });
      if (!res.ok) throw new Error('failed');
      form.reset();
      status.className = 'status ok'; status.textContent = T('Thank you. Your question was sent. We will reply soon.');
    } catch (err) {
      status.className = 'status bad'; status.textContent = T('Your question could not be sent. Please try again.');
    }
    btn.disabled = false;
  });
})();
