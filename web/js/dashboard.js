/* List of cars, available cars + booking, bookings and report. Everything shown comes from the server. */
(function () {
  var body = document.body;
  function $(id) { return document.getElementById(id); }
  function el(tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) { e.className = cls; }
    if (text !== undefined && text !== null) { e.textContent = text; }
    return e;
  }
  function clear(n) { while (n.firstChild) { n.removeChild(n.firstChild); } }
  async function api(url, opts) {
    var res = await fetch(url, opts), data = null;
    try { data = await res.json(); } catch (e) {}
    return {ok: res.ok, status: res.status, data: data};
  }
  function post(url, obj) {
    return api(url, {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(obj || {})});
  }
  function isAdmin() { return body.classList.contains('is-admin'); }
  function say(node, cls, text) { node.className = 'status ' + cls; node.textContent = text; }
  var NOSERVER = 'Could not reach the server. Open the site through the server link.';
  var LABEL = {available: 'Available', booked: 'Booked', maintenance: 'Maintenance', pending: 'Pending',
               confirmed: 'Confirmed', completed: 'Completed', cancelled: 'Cancelled'};
  function badge(st) { return el('span', 'badge ' + st, T(LABEL[st] || st)); }
  function small(label, cls, fn) {
    var b = el('button', 'mini ' + cls, T(label)); b.type = 'button'; b.addEventListener('click', fn); return b;
  }
  function makeTable(table, cols) {
    clear(table);
    var tr = el('tr'); cols.forEach(function (c) { tr.appendChild(el('th', '', T(c))); });
    var head = el('thead'); head.appendChild(tr); table.appendChild(head);
    var bodyEl = el('tbody'); table.appendChild(bodyEl); return bodyEl;
  }
  function cell(row, text, cls) { var td = el('td', cls || '', text); row.appendChild(td); return td; }

  /* ---------- List of cars ---------- */
  async function loadCars() {
    var st = $('car-list-status');
    var r;
    try { r = await api('/api/cars'); } catch (e) { r = {ok: false}; }
    if (!r.ok) { say(st, 'bad', T(NOSERVER)); return; }
    say(st, '', '');
    var cols = ['Photo', 'Car', 'Type', 'Status']; if (isAdmin()) { cols.push('Action'); }
    var tb = makeTable($('car-table'), cols);
    r.data.forEach(function (c) {
      var tr = el('tr'), td = el('td'), img = el('img', 'thumb');
      img.src = c.image; img.alt = c.name; img.loading = 'lazy'; td.appendChild(img); tr.appendChild(td);
      cell(tr, c.name); cell(tr, T(c.type));
      cell(tr, '').appendChild(badge(c.status));
      if (isAdmin()) {
        var ta = cell(tr, '');
        if (c.status !== 'booked') {
          var inMaint = c.status === 'maintenance';
          ta.appendChild(small(inMaint ? 'Set available' : 'Set maintenance', 'ghost', async function () {
            await post('/api/cars/' + c.id + '/status', {status: inMaint ? 'available' : 'maintenance'});
            loadCars();
          }));
        }
      }
      tb.appendChild(tr);
    });
  }

  /* ---------- Available cars + booking form ---------- */
  async function loadAvailable() {
    var grid = $('available-cars'), sel = $('bk-car'), empty = $('available-empty');
    var r;
    try { r = await api('/api/cars?available=1'); } catch (e) { r = {ok: false}; }
    if (!r.ok) { say(empty, 'bad', T(NOSERVER)); return; }
    var wanted = window.ttSelectedCar || sel.value;
    clear(grid); clear(sel);
    var first = el('option', '', T('Car')); first.value = ''; sel.appendChild(first);
    r.data.forEach(function (c) {
      var o = el('option', '', c.name); o.value = String(c.id); sel.appendChild(o);
      var card = el('div', 'car-card'), img = el('img', 'car-photo');
      img.src = c.image; img.alt = c.name; img.loading = 'lazy'; card.appendChild(img);
      var info = el('div', 'car-info');
      info.appendChild(el('h3', '', c.name)); info.appendChild(el('p', '', T(c.description)));
      var price = el('div', 'price'); price.appendChild(badge(c.status));
      var book = el('button', 'btn', T('Book')); book.type = 'button';
      book.addEventListener('click', function () {
        if (!body.classList.contains('logged-in')) { location.hash = '#login'; return; }
        sel.value = String(c.id); $('booking-form').scrollIntoView({behavior: 'smooth', block: 'center'});
      });
      price.appendChild(book); info.appendChild(price); card.appendChild(info); grid.appendChild(card);
    });
    if (wanted) { sel.value = String(wanted); }
    window.ttSelectedCar = null;
    say(empty, '', r.data.length ? '' : T('No cars are available right now.'));
  }

  (function setupBookingForm() {
    var form = $('booking-form'), when = $('bk-when');
    var d = new Date(); d.setMinutes(d.getMinutes() - d.getTimezoneOffset()); when.min = d.toISOString().slice(0, 16);
    form.addEventListener('submit', async function (e) {
      e.preventDefault();
      var st = $('booking-status'), btn = form.querySelector('button[type="submit"]');
      say(st, '', T('Sending...')); btn.disabled = true;
      try {
        var r = await post('/api/bookings', {
          car_id: $('bk-car').value, pickup: $('bk-from').value, dropoff: $('bk-to').value,
          trip_at: when.value, passengers: $('bk-pax').value, notes: $('bk-notes').value
        });
        if (r.ok) {
          form.reset(); say(st, 'ok', T('Your booking was sent. We will confirm it soon.'));
          setTimeout(function () { location.hash = '#bookings'; st.textContent = ''; }, 1200);
        } else { say(st, 'bad', T(r.data && r.data.error) || T('Please fill in all the fields.')); }
      } catch (err) { say(st, 'bad', T(NOSERVER)); }
      btn.disabled = false;
    });
  })();

  /* ---------- Car bookings ---------- */
  async function loadBookings() {
    var st = $('bookings-status'), r;
    try { r = await api('/api/bookings'); } catch (e) { return; }
    if (r.status === 401) { return; }            /* the "please login" note is shown instead */
    if (!r.ok) { say(st, 'bad', T((r.data && r.data.error) || NOSERVER)); return; }
    var admin = isAdmin(), cols = ['#'];
    if (admin) { cols.push('Customer'); }
    cols = cols.concat(['Car', 'Trip', 'Date and time', 'Passengers', 'Status', 'Action']);
    var tb = makeTable($('booking-table'), cols);
    async function change(id, status) {
      var res = await post('/api/bookings/' + id + '/status', {status: status});
      if (!res.ok) { say(st, 'bad', T(res.data && res.data.error) || T('Could not reach the server. Open the site through the server link.')); } else { say(st, '', ''); }
      loadBookings();
    }
    r.data.forEach(function (b) {
      var tr = el('tr'); cell(tr, String(b.id));
      if (admin) { var tc = cell(tr, b.customer); tc.appendChild(el('div', 'sub', b.phone || b.email)); tc.lastChild.style.fontSize = '.85rem'; tc.lastChild.style.color = 'var(--muted)'; }
      cell(tr, b.car_name); cell(tr, b.pickup + ' \u2192 ' + b.dropoff);
      cell(tr, b.trip_at.replace('T', ' ')); cell(tr, String(b.passengers));
      cell(tr, '').appendChild(badge(b.status));
      var ta = cell(tr, '');
      if (admin && b.status === 'pending') { ta.appendChild(small('Confirm', 'ok', function () { change(b.id, 'confirmed'); })); }
      if (admin && b.status === 'confirmed') { ta.appendChild(small('Complete', 'ok', function () { change(b.id, 'completed'); })); }
      if (b.status === 'pending' || b.status === 'confirmed') { ta.appendChild(small('Cancel', 'warn', function () { change(b.id, 'cancelled'); })); }
      tb.appendChild(tr);
    });
    say(st, '', r.data.length ? '' : T('No bookings yet.'));
  }

  /* ---------- Report (admin only) ---------- */
  function tile(label, value, cls, sym) {
    var t = el('div', 'tile'), w = el('div');
    t.appendChild(el('div', 'ico ' + cls, sym));
    w.appendChild(el('b', '', String(value))); w.appendChild(el('span', '', T(label)));
    t.appendChild(w); return t;
  }
  async function loadReport() {
    if (!isAdmin()) { return; }
    var msg = $('report-msg'), r;
    try { r = await api('/api/report'); } catch (e) { r = {ok: false}; }
    if (!r.ok) { say(msg, 'bad', T((r.data && r.data.error) || NOSERVER)); return; }
    say(msg, '', '');
    var d = r.data, tiles = $('report-tiles'); clear(tiles);
    [['Total cars', d.cars.total, 'navy', '\u25A0'], ['Available', d.cars.available, 'green', '\u2713'],
     ['Booked', d.cars.booked, 'red', '\u2605'], ['Maintenance', d.cars.maintenance, 'gold', '!'],
     ['Total bookings', d.bookings.total, 'navy', '\u25A4'], ['Pending', d.bookings.pending, 'gold', '\u23F1'],
     ['Confirmed', d.bookings.confirmed, 'green', '\u2713'], ['Completed', d.bookings.completed, 'green', '\u2605'],
     ['Accounts', d.accounts, 'navy', '\u263A'], ['Comments', d.comments.count, 'gold', '\u270E'],
     ['Average rating', d.comments.average === null ? '-' : d.comments.average, 'red', '\u2605'],
     ['Messages received', d.messages, 'navy', '\u2709']
    ].forEach(function (t) { tiles.appendChild(tile(t[0], t[1], t[2], t[3])); });

    var tb = makeTable($('report-status'), ['Status', 'Count']);
    ['pending', 'confirmed', 'completed', 'cancelled'].forEach(function (k) {
      var tr = el('tr'); cell(tr, '').appendChild(badge(k)); cell(tr, String(d.bookings[k])); tb.appendChild(tr);
    });
    var tc = makeTable($('report-cars'), ['Car', 'Type', 'Total', 'Completed']);
    d.per_car.forEach(function (c) {
      var tr = el('tr'); cell(tr, c.name); cell(tr, T(c.type)); cell(tr, String(c.total)); cell(tr, String(c.completed)); tc.appendChild(tr);
    });
  }
  $('print-report').addEventListener('click', function () { window.print(); });

  /* ---------- which page is open ---------- */
  function refresh() {
    var h = location.hash;
    if (h === '#car-list') { loadCars(); } else if (h === '#available') { loadAvailable(); }
    else if (h === '#bookings') { loadBookings(); } else if (h === '#report') { loadReport(); }
  }
  window.ttPages = {refresh: refresh};
  window.addEventListener('hashchange', refresh);
  document.addEventListener('click', function (e) {
    var a = e.target.closest ? e.target.closest('[data-book]') : null;
    if (a) { window.ttSelectedCar = a.getAttribute('data-book'); }
  });
  refresh();
})();
