/* Reserve on the car rental page: opens a form, then sends it to /api/contact. */
(function () {
  var dlg = document.getElementById('reserve-dialog'), form = document.getElementById('reserve-form');
  var status = document.getElementById('reserve-status');
  var nameEl = document.getElementById('reserve-car-name'), idEl = document.getElementById('reserve-car-id');
  var triggers = document.querySelectorAll('[data-reserve]');
  if (!dlg || !form || !status || !nameEl || !idEl || !triggers.length) { return; }

  function open(id, name) {
    idEl.value = id;
    nameEl.textContent = name;
    status.className = 'status'; status.textContent = '';
    document.body.classList.add('reserve-open');
    if (dlg.showModal) { dlg.showModal(); } else { dlg.setAttribute('open', ''); }
    document.getElementById('reserve-name').focus();
  }

  triggers.forEach(function (t) {
    t.addEventListener('click', function (e) {
      e.preventDefault();
      open(t.getAttribute('data-reserve'), t.getAttribute('data-car-name') || '');
    });
  });

  document.getElementById('reserve-close').addEventListener('click', function () { dlg.close(); });
  dlg.addEventListener('close', function () { document.body.classList.remove('reserve-open'); });
  dlg.addEventListener('click', function (e) { if (e.target === dlg) { dlg.close(); } });

  form.addEventListener('submit', async function (e) {
    e.preventDefault();
    var btn = form.querySelector('button[type="submit"]');
    status.className = 'status'; status.textContent = T('Sending...'); btn.disabled = true;
    var lines = [
      'Car: ' + nameEl.textContent + ' (#' + idEl.value + ')',
      'Pick-up location: ' + document.getElementById('reserve-pickup').value,
      'Drop-off location: ' + document.getElementById('reserve-dropoff').value,
      'Pick-up date: ' + document.getElementById('reserve-date').value,
      'Number of days: ' + document.getElementById('reserve-days').value,
      '',
      document.getElementById('reserve-message').value
    ];
    try {
      var headers = {'Content-Type': 'application/json'};
      if (window.ttCsrf) { headers['X-CSRF-Token'] = window.ttCsrf; }
      var res = await fetch('/api/contact', {
        method: 'POST', headers: headers,
        body: JSON.stringify({
          name: document.getElementById('reserve-name').value,
          email: document.getElementById('reserve-email').value,
          phone: document.getElementById('reserve-phone').value,
          service: 'Car reservation',
          message: lines.join('\n')
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
