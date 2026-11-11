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
    var res = await window.ttFetch(url, opts), data = null;
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
    window.ttEmptyState.clear(table.parentNode);
    var tr = el('tr'); cols.forEach(function (c) { tr.appendChild(el('th', '', T(c))); });
    var head = el('thead'); head.appendChild(tr); table.appendChild(head);
    var bodyEl = el('tbody'); table.appendChild(bodyEl); return bodyEl;
  }
  function cell(row, text, cls) { var td = el('td', cls || '', text); row.appendChild(td); return td; }
  function skel(cls, w) {
    var s = el('div', 'skel ' + (cls || ''));
    if (w) { s.style.width = w; }
    s.setAttribute('aria-hidden', 'true');
    return s;
  }
  function skelCards(n) {
    var out = [];
    for (var i = 0; i < n; i++) {
      var card = el('div', 'skel-card');
      card.appendChild(skel('skel-img'));
      var b = el('div', 'skel-body');
      b.appendChild(skel('skel-line', '55%')); b.appendChild(skel('skel-line', '85%'));
      b.appendChild(skel('skel-line', '40%'));
      card.appendChild(b);
      out.push(card);
    }
    return out;
  }
  function skelRows(tableId, n) {
    var table = $(tableId);
    if (!table) { return; }
    window.ttEmptyState.clear(table.parentNode);
    clear(table);
    var tb = el('tbody');
    for (var i = 0; i < n; i++) {
      var tr = el('tr');
      for (var j = 0; j < 4; j++) { tr.appendChild(el('td')).appendChild(skel('skel-line', j === 0 ? '56px' : '70%')); }
      tb.appendChild(tr);
    }
    table.appendChild(tb);
  }

  /* ---------- List of cars ---------- */
  async function loadCars() {
    var st = $('car-list-status');
    say(st, '', T('Loading...'));
    skelRows('car-table', 5);
    var r;
    try { r = await api('/api/cars'); } catch (e) { r = {ok: false}; }
    if (!r.ok) { say(st, 'bad', T(NOSERVER)); return; }
    var table = $('car-table');
    if (!r.data.length) {
      window.ttEmptyState(table.parentNode, {
        icon: 'car',
        title: 'No cars in the fleet yet.',
        text: 'Vehicles will appear here once they are added to the fleet.'
      });
      say(st, '', '');
      return;
    }
    say(st, '', '');
    var cols = ['Photo', 'Car', 'Type', 'Status']; if (isAdmin()) { cols.push('Action'); }
    var tb = makeTable(table, cols);
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

  /* ---------- Available cars + booking panel ---------- */
  var selectedId = null;
  var carsById = {};
  var loadSeq = 0;

  function mobilePanel() {
    return window.matchMedia('(max-width: 980px)').matches;
  }

  function resetPanelPosition() {
    var slot = $('booking-panel-slot'), panel = $('booking-panel');
    if (!panel) { return; }
    if (slot) { slot.hidden = false; }
    if (slot && panel.parentNode !== slot) { slot.appendChild(panel); }
    panel.classList.remove('inline');
  }

  function placePanel(card) {
    var panel = $('booking-panel'), slot = $('booking-panel-slot');
    if (!panel) { return; }
    if (mobilePanel() && card) {
      if (panel.parentNode !== card) { card.insertAdjacentElement('afterend', panel); }
      panel.classList.add('inline');
      if (slot) { slot.hidden = true; }
    } else {
      resetPanelPosition();
    }
  }

  function markSelected(id) {
    document.querySelectorAll('#available-cars .car-card').forEach(function (card) {
      var on = id !== null && card.getAttribute('data-car-id') === String(id);
      card.classList.toggle('is-selected', on);
      var btn = card.querySelector('[data-book-id]');
      if (btn) {
        btn.setAttribute('aria-pressed', on ? 'true' : 'false');
        btn.textContent = T(on ? 'Selected' : 'Book');
      }
    });
  }

  function renderSummary(car) {
    var box = $('booking-summary');
    if (!box) { return; }
    clear(box);
    if (!car) { return; }

    var img = el('img', 'booking-summary-photo');
    img.src = car.image; img.alt = car.name;
    var info = el('div', 'booking-summary-info');
    info.appendChild(el('span', 'booking-summary-label', T('Selected car')));
    info.appendChild(el('h3', '', car.name));
    info.appendChild(el('p', 'booking-summary-type', T(car.type)));

    var rate = el('p', 'booking-summary-rate');
    if (car.price) {
      rate.appendChild(el('span', 'rate-price', car.price));
      rate.appendChild(el('span', 'rate-per', T('Per day')));
    } else {
      rate.appendChild(el('span', 'rate-price', T('Ask for a quote')));
    }
    info.appendChild(rate);

    var change = el('button', 'link-btn', T('Change car'));
    change.type = 'button';
    change.addEventListener('click', function () { closePanel({focusGrid: true}); });
    info.appendChild(change);

    box.appendChild(img);
    box.appendChild(info);
  }

  function openPanel(car, opts) {
    opts = opts || {};
    selectedId = String(car.id);
    $('bk-car').value = selectedId;
    renderSummary(car);
    markSelected(selectedId);
    $('booking-intro').hidden = true;
    $('booking-form-wrap').hidden = false;
    var layout = document.querySelector('.booking-layout');
    if (layout) { layout.classList.add('has-sheet'); }
    if ($('sheet-backdrop')) { $('sheet-backdrop').hidden = mobilePanel(); }
    placePanel(document.querySelector('#available-cars .car-card[data-car-id="' + selectedId + '"]'));

    if (opts.focus) {
      if (mobilePanel()) {
        $('booking-panel').scrollIntoView({behavior: 'smooth', block: 'start'});
        setTimeout(function () {
          try { $('bk-from').focus({preventScroll: true}); } catch (e) { $('bk-from').focus(); }
        }, 260);
      } else {
        try { $('bk-from').focus({preventScroll: true}); } catch (e) { $('bk-from').focus(); }
      }
    }
  }

  function closePanel(opts) {
    opts = opts || {};
    var previous = selectedId;
    selectedId = null;
    $('bk-car').value = '';
    renderSummary(null);
    markSelected(null);
    var wrap = $('booking-form-wrap'), intro = $('booking-intro');
    if (wrap) { wrap.hidden = true; }
    if (intro) { intro.hidden = false; }
    var layout = document.querySelector('.booking-layout');
    if (layout) { layout.classList.remove('has-sheet'); }
    if ($('sheet-backdrop')) { $('sheet-backdrop').hidden = true; }
    if (window.ttDatePicker) { window.ttDatePicker.reset(); }
    resetPanelPosition();
    if (opts.focusGrid) {
      var grid = $('available-cars');
      if (grid) { grid.scrollIntoView({behavior: 'smooth', block: 'start'}); }
    }
    if (opts.restoreFocus && previous !== null) {
      var back = document.querySelector('#available-cars [data-book-id="' + previous + '"]');
      if (back) { back.focus(); }
    }
  }

  function renderCarCard(c) {
    var card = el('div', 'car-card');
    card.setAttribute('data-car-id', String(c.id));

    var img = el('img', 'car-photo');
    img.src = c.image; img.alt = c.name; img.loading = 'lazy';
    card.appendChild(img);

    var info = el('div', 'car-info');
    var top = el('div', 'car-card-top');
    top.appendChild(el('span', 'car-badge', T(c.type)));
    info.appendChild(top);

    var statusBadge = el('span', 'car-status', T('Available'));
    card.appendChild(statusBadge);

    info.appendChild(el('h3', '', c.name));
    info.appendChild(el('p', '', T(c.description)));

    if (c.specs && c.specs.length) {
      var specs = el('ul', 'car-specs');
      c.specs.forEach(function (spec) { specs.appendChild(el('li', '', spec)); });
      info.appendChild(specs);
    }

    var foot = el('div', 'car-foot');
    var rate = el('div', 'car-rate');
    if (c.price) {
      rate.appendChild(el('span', 'rate-price', c.price));
      rate.appendChild(el('span', 'rate-per', T('Per day')));
      if (c.week) { rate.appendChild(el('span', 'rate-week', c.week)); }
    } else {
      rate.appendChild(el('span', 'rate-price', T('Ask for a quote')));
    }
    foot.appendChild(rate);

    var book = el('button', 'reserve-btn', T('Book'));
    book.type = 'button';
    book.setAttribute('data-book-id', String(c.id));
    book.setAttribute('aria-pressed', 'false');
    book.addEventListener('click', function () {
      openPanel(c, {focus: true});
    });
    foot.appendChild(book);
    info.appendChild(foot);
    card.appendChild(info);
    return card;
  }

  async function loadAvailable() {
    var grid = $('available-cars'), status = $('available-status'), empty = $('available-empty');
    var seq = ++loadSeq;
    clear(grid);
    window.ttEmptyState.clear(empty);
    skelCards(6).forEach(function (c) { grid.appendChild(c); });
    say(status, '', T('Loading...'));
    var r;
    try { r = await api('/api/cars?available=1'); } catch (e) { r = {ok: false}; }
    if (seq !== loadSeq) { return; }
    if (!r.ok) { say(status, 'bad', T(NOSERVER)); return; }

    var wanted = window.ttSelectedCar;
    window.ttSelectedCar = null;
    if (!wanted) {
      try { wanted = sessionStorage.getItem('tt-selected-car'); } catch (e) {}
    }

    resetPanelPosition();
    clear(grid);
    closePanel();
    carsById = {};
    r.data.forEach(function (c) {
      carsById[String(c.id)] = c;
      grid.appendChild(renderCarCard(c));
    });

    if (wanted && carsById[String(wanted)]) {
      openPanel(carsById[String(wanted)], {focus: true});
      try { sessionStorage.removeItem('tt-selected-car'); } catch (e) {}
    } else if (wanted) {
      try { sessionStorage.removeItem('tt-selected-car'); } catch (e) {}
    }

    say(status, '', '');
    if (!r.data.length) {
      window.ttEmptyState(empty, {
        size: 'inline',
        icon: 'car',
        title: 'No cars are available right now.',
        text: 'Check back soon or message us on WhatsApp.',
        action: {label: 'Contact us', tone: 'ok', run: function () { location.href = '/contact'; }}
      });
    } else {
      window.ttEmptyState.clear(empty);
    }
  }

  (function setupBookingForm() {
    var form = $('booking-form'), when = $('bk-when');
    if (!form || !when) { return; }
    form.addEventListener('submit', async function (e) {
      e.preventDefault();
      var st = $('booking-status'), btn = form.querySelector('button[type="submit"]');
      if (!when.value) { say(st, 'bad', T('Please choose a date and time in the future.')); return; }
      say(st, '', T('Sending...')); btn.disabled = true;
      try {
        var r = await post('/api/bookings', {
          car_id: $('bk-car').value, pickup: $('bk-from').value, dropoff: $('bk-to').value,
          trip_at: when.value, passengers: $('bk-pax').value, notes: $('bk-notes').value
        });
        if (r.ok) {
          say(st, 'ok', T('Your booking was sent. We will confirm it soon.'));
          setTimeout(function () {
            form.reset();
            closePanel();
            location.hash = '#bookings';
            st.textContent = '';
          }, 1400);
        } else if (r.status === 401) {
          window.ttSelectedCar = $('bk-car').value || selectedId;
          try { sessionStorage.setItem('tt-selected-car', $('bk-car').value || selectedId); } catch (e) {}
          say(st, 'bad', T('Please login to send your booking.'));
          setTimeout(function () { location.hash = '#login'; }, 1200);
        } else { say(st, 'bad', T(r.data && r.data.error) || T('Please fill in all the fields.')); }
      } catch (err) { say(st, 'bad', T(NOSERVER)); }
      btn.disabled = false;
    });
  })();

  (function setupSheetDismiss() {
    function dismiss() { if (selectedId !== null) { closePanel({restoreFocus: true}); } }
    $('sheet-close').addEventListener('click', dismiss);
    $('sheet-backdrop').addEventListener('click', dismiss);
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape') { dismiss(); }
    });
  })();

  window.addEventListener('resize', function () {
    if (selectedId === null) { resetPanelPosition(); return; }
    placePanel(document.querySelector('#available-cars .car-card[data-car-id="' + selectedId + '"]'));
  });

  /* ---------- Car bookings ---------- */
  async function loadBookings() {
    var st = $('bookings-status'), r;
    say(st, '', T('Loading...'));
    skelRows('booking-table', 4);
    try { r = await api('/api/bookings'); } catch (e) { return; }
    if (r.status === 401) { return; }            /* the "please login" note is shown instead */
    if (!r.ok) { say(st, 'bad', T((r.data && r.data.error) || NOSERVER)); return; }
    if (!r.data.length) {
      window.ttEmptyState($('booking-table').parentNode, isAdmin() ? {
        icon: 'tray',
        title: 'No bookings yet.',
        text: 'Customer bookings will appear here.'
      } : {
        icon: 'tray',
        title: 'No bookings yet.',
        text: 'Your trips will appear here after you book a car.',
        action: {label: 'Book a car', tone: 'ok', run: function () { location.hash = '#available'; }}
      });
      say(st, '', '');
      return;
    }
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
    say(st, '', '');
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
    if (!d.per_car.length) {
      window.ttEmptyState($('report-cars').parentNode, {
        icon: 'car',
        title: 'No bookings per car yet.',
        text: 'Bookings will be counted here once customers start travelling.'
      });
      return;
    }
    var tc = makeTable($('report-cars'), ['Car', 'Type', 'Total', 'Completed']);
    d.per_car.forEach(function (c) {
      var tr = el('tr'); cell(tr, c.name); cell(tr, T(c.type)); cell(tr, String(c.total)); cell(tr, String(c.completed)); tc.appendChild(tr);
    });
  }
  $('print-report').addEventListener('click', function () { window.print(); });

  /* ---------- which page is open ---------- */
  function refresh() {
    var h = location.hash;
    if (h === '#car-list') { loadCars(); } else if (h === '#available' || h === '') { loadAvailable(); }
    else if (h === '#bookings') { loadBookings(); } else if (h === '#report') { loadReport(); }
  }
  window.ttPages = {refresh: refresh};
  window.addEventListener('hashchange', refresh);
  refresh();
})();
