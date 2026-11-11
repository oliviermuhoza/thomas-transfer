/* Book a tour package: opens the form, then stores a guest tour booking. */
(function () {
  var dlg = document.getElementById('tour-dialog'), form = document.getElementById('tour-book-form');
  var status = document.getElementById('tour-book-status'), nameEl = document.getElementById('tour-book-name');
  var triggers = document.querySelectorAll('[data-tour-book]');
  if (!dlg || !form || !status || !nameEl || !triggers.length) { return; }

  var current = '';

  function open(name) {
    current = name;
    nameEl.textContent = name;
    status.className = 'status'; status.textContent = '';
    document.body.classList.add('reserve-open');
    if (dlg.showModal) { dlg.showModal(); } else { dlg.setAttribute('open', ''); }
    document.getElementById('tour-first').focus();
  }

  triggers.forEach(function (t) {
    t.addEventListener('click', function (e) {
      e.preventDefault();
      var card = t.closest('.car-card');
      var title = card ? card.querySelector('h3') : null;
      open(title ? title.textContent.trim() : '');
    });
  });

  document.getElementById('tour-book-close').addEventListener('click', function () { dlg.close(); });
  dlg.addEventListener('close', function () { document.body.classList.remove('reserve-open'); });
  dlg.addEventListener('click', function (e) { if (e.target === dlg) { dlg.close(); } });

  form.addEventListener('submit', async function (e) {
    e.preventDefault();
    var btn = form.querySelector('button[type="submit"]');
    status.className = 'status'; status.textContent = T('Sending...'); btn.disabled = true;
    try {
      var headers = {'Content-Type': 'application/json'};
      if (window.ttCsrf) { headers['X-CSRF-Token'] = window.ttCsrf; }
      var date = document.getElementById('tour-date').value;
      var res = await fetch('/api/bookings/guest', {
        method: 'POST', headers: headers,
        body: JSON.stringify({
          kind: 'tour',
          tour_name: current || 'Tour package',
          name: (document.getElementById('tour-first').value + ' ' + document.getElementById('tour-last').value).trim(),
          email: document.getElementById('tour-email').value,
          phone: document.getElementById('tour-phone').value,
          pickup: document.getElementById('tour-pickup').value,
          trip_at: date ? date + 'T00:00' : '',
          passengers: Number(document.getElementById('tour-travellers').value),
          notes: document.getElementById('tour-message').value
        })
      });
      if (!res.ok) throw new Error('failed');
      form.reset();
      status.className = 'status ok'; status.textContent = T('Thank you. Your booking request was received. We will confirm it shortly.');
    } catch (err) {
      status.className = 'status bad'; status.textContent = T('Your request could not be sent. Please try again.');
    }
    btn.disabled = false;
  });
})();
