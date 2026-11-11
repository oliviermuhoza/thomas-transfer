/* Support > Message: opens a dialog and sends the message to the same /api/contact as the Contact page. */
(function () {
  var dlg = document.getElementById('msg-dialog'), form = document.getElementById('support-form');
  var status = document.getElementById('support-status');
  var openBtn = document.getElementById('open-message');
  if (!dlg || !form || !status || !openBtn) { return; }
  openBtn.addEventListener('click', function (e) {
    e.preventDefault(); status.className = 'status'; status.textContent = '';
    document.body.classList.add('msg-open');
    if (dlg.showModal) { dlg.showModal(); } else { dlg.setAttribute('open', ''); }
    document.getElementById('s-name').focus();
  });
  dlg.addEventListener('close', function () { document.body.classList.remove('msg-open'); });
  document.getElementById('msg-close').addEventListener('click', function () { dlg.close(); });
  dlg.addEventListener('click', function (e) { if (e.target === dlg) { dlg.close(); } });
  form.addEventListener('submit', async function (e) {
    e.preventDefault();
    var btn = form.querySelector('button[type="submit"]');
    status.className = 'status'; status.textContent = T('Sending...'); btn.disabled = true;
    try {
      var res = await window.ttFetch('/api/contact', {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
          name: document.getElementById('s-name').value,
          email: document.getElementById('s-email').value,
          phone: document.getElementById('s-phone').value,
          service: 'Support message',
          message: document.getElementById('s-msg').value
        })
      });
      if (!res.ok) throw new Error('failed');
      form.reset();
      status.className = 'status ok'; status.textContent = T('Thank you. Your message was sent. We will reply soon.');
    } catch (err) {
      status.className = 'status bad'; status.textContent = T('Your message could not be sent. Please try again.');
    }
    btn.disabled = false;
  });
})();
