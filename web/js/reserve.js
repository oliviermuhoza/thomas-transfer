/* Reserve on the car rental page: opens a form, then stores a guest booking. */
(function () {
  var dlg = document.getElementById('reserve-dialog'), form = document.getElementById('reserve-form');
  var status = document.getElementById('reserve-status');
  var nameEl = document.getElementById('reserve-car-name'), idEl = document.getElementById('reserve-car-id');
  var thumbEl = document.getElementById('reserve-car-thumb'), typeEl = document.getElementById('reserve-car-type'), rateEl = document.getElementById('reserve-car-rate');
  var triggers = document.querySelectorAll('[data-reserve]');
  if (!dlg || !form || !status || !nameEl || !idEl || !triggers.length) { return; }

  function open(id, name, image, type, rate) {
    idEl.value = id;
    nameEl.textContent = name;
    if (thumbEl) { thumbEl.src = image || ''; thumbEl.alt = name || ''; }
    if (typeEl) { typeEl.textContent = type || ''; }
    if (rateEl) { rateEl.textContent = rate ? rate + ' / day' : ''; }
    status.className = 'status'; status.textContent = '';
    document.body.classList.add('reserve-open');
    if (dlg.showModal) { dlg.showModal(); } else { dlg.setAttribute('open', ''); }
    document.getElementById('reserve-first').focus();
  }

  triggers.forEach(function (t) {
    t.addEventListener('click', function (e) {
      e.preventDefault();
      open(
        t.getAttribute('data-reserve'),
        t.getAttribute('data-car-name') || '',
        t.getAttribute('data-car-image') || '',
        t.getAttribute('data-car-type') || '',
        t.getAttribute('data-car-rate') || ''
      );
    });
  });

  document.getElementById('reserve-close').addEventListener('click', function () { dlg.close(); });
  dlg.addEventListener('close', function () { document.body.classList.remove('reserve-open'); });
  dlg.addEventListener('click', function (e) { if (e.target === dlg) { dlg.close(); } });

  form.addEventListener('submit', async function (e) {
    e.preventDefault();
    var date = document.getElementById('reserve-date').value;
    if (!date) {
      status.className = 'status bad'; status.textContent = T('Please choose a pick-up date.');
      return;
    }
    var btn = form.querySelector('button[type="submit"]');
    status.className = 'status'; status.textContent = T('Sending...'); btn.disabled = true;
    var lines = [
      'Car: ' + nameEl.textContent + ' (#' + idEl.value + ')',
      'Type: ' + (typeEl ? typeEl.textContent : ''),
      'Pick-up location: ' + document.getElementById('reserve-pickup').value,
      'Pick-up date: ' + date,
      'Number of days: ' + document.getElementById('reserve-days').value,
      'Driver: ' + (document.getElementById('reserve-driver').checked ? 'Yes' : 'No'),
      '',
      document.getElementById('reserve-message').value
    ];
    try {
      var headers = {'Content-Type': 'application/json'};
      if (window.ttCsrf) { headers['X-CSRF-Token'] = window.ttCsrf; }
      var res = await fetch('/api/bookings/guest', {
        method: 'POST', headers: headers,
        body: JSON.stringify({
          kind: 'car',
          car_id: Number(idEl.value),
          name: (document.getElementById('reserve-first').value + ' ' + document.getElementById('reserve-last').value).trim(),
          email: document.getElementById('reserve-email').value,
          phone: document.getElementById('reserve-phone').value,
          pickup: document.getElementById('reserve-pickup').value,
          trip_at: date ? date + 'T00:00' : '',
          passengers: Number(document.getElementById('reserve-pax').value),
          notes: lines.join('\n')
        })
      });
      if (!res.ok) throw new Error('failed');
      form.reset();
      status.className = 'status ok'; status.textContent = T('Thank you. Your reservation request was received. We will confirm it shortly.');
    } catch (err) {
      status.className = 'status bad'; status.textContent = T('Your request could not be sent. Please try again.');
    }
    btn.disabled = false;
  });
})();
