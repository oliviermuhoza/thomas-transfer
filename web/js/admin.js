/* Admin portal: overview, bookings, fleet, accounts, messages and comments.
   Everything shown comes from the same JSON API the account dashboard uses. */
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
  function del(url) {
    return api(url, {method: 'DELETE', headers: {'Content-Type': 'application/json'}});
  }
  function patch(url, obj) {
    return api(url, {method: 'PATCH', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(obj || {})});
  }
  function say(node, cls, text) { node.className = 'status ' + cls; node.textContent = text; }
  function fail(node, r) {
    if (r.status === 401) { say(node, 'bad', T('Please log in again to continue.')); }
    else if (r.status === 403 && /csrf/i.test((r.data && r.data.error) || '')) {
      say(node, 'bad', T('Please log in again to continue.'));
    }
    else if (r.status === 403) { say(node, 'bad', T('Admin only.')); }
    else { say(node, 'bad', T((r.data && r.data.error) || NOSERVER)); }
  }
  var NOSERVER = 'Could not reach the server. Open the site through the server link.';
  var LABEL = {available: 'Available', booked: 'Booked', maintenance: 'Maintenance',
               pending: 'Pending', confirmed: 'Confirmed', completed: 'Completed', cancelled: 'Cancelled',
               open: 'Open', handled: 'Handled', active: 'Active', inactive: 'Inactive'};
  function badge(st) { return el('span', 'badge ' + st, T(LABEL[st] || st)); }
  function small(label, cls, fn) {
    var b = el('button', 'mini ' + cls, T(label));
    b.type = 'button';
    b.addEventListener('click', fn);
    return b;
  }

  /* Initials avatars: no profile photos in the data, so people are marked by
     circles of first letters (two from the name, else the email start). */
  function initials(name, email) {
    var src = (name || '').trim() || (email || '?').trim();
    var parts = src.split(/\s+/);
    var ini = parts.length > 1 ? parts[0].charAt(0) + parts[parts.length - 1].charAt(0)
                               : src.slice(0, 2);
    return ini.toUpperCase();
  }
  function avatarEl(name, email) {
    var a = el('span', 'avatar', initials(name, email));
    a.setAttribute('aria-hidden', 'true');
    return a;
  }
  function whoCell(row, u) {
    var td = cell(row, '');
    var w = el('div', 'who');
    w.appendChild(avatarEl(u.name, u.email));
    var box = el('div', 'who-text');
    box.appendChild(el('div', 'who-name', u.name));
    box.appendChild(el('div', 'who-mail', u.email));
    w.appendChild(box);
    td.appendChild(w);
    return td;
  }
  function renderMe() {
    var box = $('admin-me');
    if (!box) { return; }
    var u = window.ttUser;
    box.textContent = '';
    box.hidden = !u;
    if (u) {
      box.appendChild(avatarEl(u.name, u.email));
      var txt = el('div', 'admin-me-text');
      txt.appendChild(el('div', 'admin-me-name', u.name));
      if (u.email) { txt.appendChild(el('div', 'admin-me-mail', u.email)); }
      box.appendChild(txt);
    }
  }

  /* Sidebar counts: the two numbers that mean "something needs you" — pending
     bookings and messages nobody has handled yet. They are decoration on top of
     a server-rendered nav, so any failure just leaves the rail as it was. */
  var countsBusy = false;
  function setNavCount(key, n, word) {
    var pill = document.querySelector('.nav-count[data-count="' + key + '"]');
    if (!pill) { return; }
    var link = pill.parentNode;
    var label = link.querySelector('.nav-label');
    if (!n) {
      pill.hidden = true;
      pill.textContent = '';
      link.removeAttribute('aria-label');
      return;
    }
    pill.textContent = n > 99 ? '99+' : String(n);
    pill.hidden = false;
    link.setAttribute('aria-label',
      (label ? label.textContent : key) + ', ' + n + ' ' + T(word));
  }
  async function refreshNavCounts() {
    if (countsBusy) { return; }
    countsBusy = true;
    var view = currentView();
    try {
      var jobs = [];
      /* The view's own loader already reads these endpoints, and it sets the
         count it just fetched — no second request on Overview or Messages. */
      if (view !== 'overview') {
        jobs.push(api('/api/report').catch(function () { return {ok: false}; }).then(function (r) {
          if (r.ok && r.data && r.data.bookings) {
            setNavCount('bookings', r.data.bookings.pending, 'pending');
          }
        }));
      }
      if (view !== 'messages') {
        jobs.push(api('/api/admin/messages').catch(function () { return {ok: false}; }).then(function (r) {
          if (r.ok && Array.isArray(r.data)) {
            setNavCount('messages', r.data.filter(function (m) { return !m.handled; }).length, 'open');
          }
        }));
      }
      if (view !== 'comments') {
        jobs.push(api('/api/admin/comments').catch(function () { return {ok: false}; }).then(function (r) {
          if (r.ok && Array.isArray(r.data)) {
            setNavCount('comments', r.data.filter(function (c) { return !c.handled; }).length, 'open');
          }
        }));
      }
      await Promise.all(jobs);
    } finally {
      countsBusy = false;
    }
  }

  /* On phones the nav is a horizontal strip; centre the current section so it
     is never the one chip scrolled out of sight. Assigning scrollLeft (instead
     of scrollIntoView) cannot drag the page itself. */
  function centerActiveNav() {
    var nav = document.querySelector('.admin-nav');
    var cur = nav && nav.querySelector('a[aria-current="page"]');
    if (!nav || !cur || nav.scrollWidth <= nav.clientWidth + 1) { return; }
    var offset = cur.getBoundingClientRect().left - nav.getBoundingClientRect().left + nav.scrollLeft;
    nav.scrollLeft = Math.max(0, offset - (nav.clientWidth - cur.offsetWidth) / 2);
  }

  /* Row action menu. A row can offer three or four actions; stacking that many
     buttons in the last cell squeezed the table, so they live in one "Manage"
     control instead. The panel is positioned fixed so the table's horizontal
     scroll container cannot clip it. */
  var openRow = null;
  var CARET = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 9l6 6 6-6" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>';

  function closeRowMenu(refocus) {
    if (!openRow) { return; }
    var m = openRow;
    openRow = null;
    m.panel.remove();
    m.btn.setAttribute('aria-expanded', 'false');
    document.removeEventListener('pointerdown', onDocPointer, true);
    window.removeEventListener('keydown', onMenuKey, true);
    window.removeEventListener('resize', onMenuScroll);
    window.removeEventListener('scroll', onMenuScroll, true);
    if (refocus) { m.btn.focus(); }
  }

  /* Keep the panel attached to its button while the page or the table scrolls
     (smooth scrolling keeps emitting scroll events after the click, so closing
     here would make the menu flash and vanish). Close only once the button has
     left the viewport. */
  function onMenuScroll() {
    if (!openRow) { return; }
    var r = openRow.btn.getBoundingClientRect();
    if (r.bottom < 0 || r.top > window.innerHeight || r.right < 0 || r.left > window.innerWidth) {
      closeRowMenu();
      return;
    }
    placeRowMenu(openRow.btn, openRow.panel);
  }

  function onDocPointer(e) {
    if (!openRow) { return; }
    if (openRow.panel.contains(e.target) || openRow.btn.contains(e.target)) { return; }
    closeRowMenu();
  }

  function focusItem(item) {
    if (!item) { return; }
    try { item.focus({preventScroll: true}); } catch (e) { item.focus(); }
  }

  function onMenuKey(e) {
    if (!openRow) { return; }
    var items = Array.prototype.slice.call(openRow.panel.querySelectorAll('.rowmenu-item'));
    var i = items.indexOf(document.activeElement);
    if (e.key === 'Escape') {
      e.preventDefault();
      closeRowMenu(true);
    } else if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
      e.preventDefault();
      var next = e.key === 'ArrowDown' ? i + 1 : i - 1;
      if (next < 0) { next = items.length - 1; }
      if (next >= items.length) { next = 0; }
      if (items[next]) { focusItem(items[next]); }
    } else if (e.key === 'Tab') {
      closeRowMenu();
    }
  }

  function placeRowMenu(btn, panel) {
    var r = btn.getBoundingClientRect();
    var w = panel.offsetWidth, h = panel.offsetHeight;
    var left = Math.max(12, Math.min(r.right - w, window.innerWidth - w - 12));
    var top = r.bottom + 6;
    if (top + h > window.innerHeight - 12) { top = Math.max(12, r.top - h - 6); }
    panel.style.left = left + 'px';
    panel.style.top = top + 'px';
  }

  function rowMenu(actions) {
    var btn = el('button', 'rowmenu-btn');
    btn.type = 'button';
    btn.setAttribute('aria-haspopup', 'menu');
    btn.setAttribute('aria-expanded', 'false');
    btn.setAttribute('aria-label', T('Manage'));
    btn.appendChild(el('span', '', T('Manage')));
    btn.insertAdjacentHTML('beforeend', CARET);

    var panel = el('div', 'rowmenu-panel');
    panel.setAttribute('role', 'menu');
    panel.hidden = true;
    actions.forEach(function (a) {
      var item = el('button', 'rowmenu-item' + (a.tone ? ' ' + a.tone : ''), T(a.label));
      item.type = 'button';
      item.setAttribute('role', 'menuitem');
      item.addEventListener('click', function () {
        closeRowMenu();
        a.run();
      });
      panel.appendChild(item);
    });

    btn.addEventListener('click', function () {
      if (openRow && openRow.btn === btn) { closeRowMenu(); return; }
      closeRowMenu();
      document.body.appendChild(panel);
      panel.hidden = false;
      btn.setAttribute('aria-expanded', 'true');
      placeRowMenu(btn, panel);
      openRow = {btn: btn, panel: panel};
      document.addEventListener('pointerdown', onDocPointer, true);
      window.addEventListener('keydown', onMenuKey, true);
      window.addEventListener('resize', onMenuScroll);
      window.addEventListener('scroll', onMenuScroll, true);
      var first = panel.querySelector('.rowmenu-item');
      focusItem(first);
    });
    return btn;
  }
  function makeTable(table, cols) {
    clear(table);
    window.ttEmptyState.clear(table.parentNode);
    var tr = el('tr');
    cols.forEach(function (c) { tr.appendChild(el('th', '', T(c))); });
    var head = el('thead'); head.appendChild(tr); table.appendChild(head);
    var bodyEl = el('tbody'); table.appendChild(bodyEl); return bodyEl;
  }
  function emptyTable(tableId, opts) {
    var table = $(tableId);
    window.ttEmptyState(table.parentNode, opts);
  }
  function clearFilters(ids, render) {
    ids.forEach(function (id) { var n = $(id); if (n) { n.value = ''; } });
    render();
  }
  function cell(row, text, cls) { var td = el('td', cls || '', text); row.appendChild(td); return td; }
  function skel(cls, w) {
    var s = el('div', 'skel ' + (cls || ''));
    if (w) { s.style.width = w; }
    s.setAttribute('aria-hidden', 'true');
    return s;
  }
  function skelRows(tableId, n) {
    var table = $(tableId);
    if (!table) { return; }
    window.ttEmptyState.clear(table.parentNode);
    clear(table);
    var tb = el('tbody');
    for (var i = 0; i < n; i++) {
      var tr = el('tr');
      for (var j = 0; j < 6; j++) {
        var td = el('td'); td.appendChild(skel('skel-line', j === 0 ? '56px' : '70%')); tr.appendChild(td);
      }
      tb.appendChild(tr);
    }
    table.appendChild(tb);
  }
  /* Pulse strip: value first, label second, caption third — no icon tile. */
  function pulseCell(label, value, cap) {
    var c = el('div', 'pulse-cell');
    c.appendChild(el('div', 'pulse-value', String(value)));
    c.appendChild(el('div', 'pulse-label', T(label)));
    if (cap) { c.appendChild(el('div', 'pulse-cap', T(cap))); }
    return c;
  }
  function skelPulse(box, n) {
    if (!box) { return; }
    clear(box);
    for (var i = 0; i < n; i++) {
      var c = el('div', 'pulse-cell');
      var v = el('div', 'skel'); v.style.width = '54px'; v.style.height = '22px'; v.style.marginBottom = '12px';
      var l = el('div', 'skel'); l.style.width = '86px'; l.style.height = '10px';
      c.appendChild(v); c.appendChild(l); box.appendChild(c);
    }
  }
  /* "3 Messages" — the number is its own node so the label stays a translatable key. */
  function countLine(value, label) {
    var s = el('span');
    s.appendChild(el('b', '', String(value)));
    s.appendChild(document.createTextNode(' ' + T(label)));
    return s;
  }
  function matches(row, keys, q) {
    if (!q) { return true; }
    return keys.map(function (k) { return row[k] === undefined || row[k] === null ? '' : String(row[k]); })
      .join(' ').toLowerCase().indexOf(q) > -1;
  }
  function query(id) { return ($(id) && $(id).value || '').toLowerCase().trim(); }

  var state = {bookings: [], cars: [], accounts: [], messages: [], comments: [], fares: []};

  /* ---------- shared actions ---------- */
  async function changeBooking(id, status, node, done) {
    var res = await post('/api/bookings/' + id + '/status', {status: status});
    if (!res.ok) { say(node, 'bad', T((res.data && res.data.error) || NOSERVER)); }
    else { say(node, '', ''); }
    done();
    refreshNavCounts();
  }
  async function changeCar(id, status, node, done) {
    var res = await post('/api/cars/' + id + '/status', {status: status});
    if (!res.ok) { say(node, 'bad', T((res.data && res.data.error) || NOSERVER)); }
    else { say(node, '', ''); }
    done();
  }
  async function changeRole(id, admin, node, done) {
    var res = await post('/api/admin/users/' + id + '/admin', {admin: admin});
    if (!res.ok) { say(node, 'bad', T((res.data && res.data.error) || NOSERVER)); }
    else { say(node, '', ''); }
    done();
  }
  async function changeMessage(id, handled, node, done) {
    var res = await post('/api/admin/messages/' + id + '/handled', {handled: handled});
    if (!res.ok) { say(node, 'bad', T((res.data && res.data.error) || NOSERVER)); }
    else { say(node, '', ''); }
    done();
    refreshNavCounts();
  }
  async function changeComment(id, handled, node, done) {
    var res = await post('/api/admin/comments/' + id + '/handled', {handled: handled});
    if (!res.ok) { say(node, 'bad', T((res.data && res.data.error) || NOSERVER)); }
    else { say(node, '', ''); }
    done();
    refreshNavCounts();
  }
  async function changeActive(id, active, node, done) {
    var res = await post('/api/admin/users/' + id + '/active', {active: active});
    if (!res.ok) { say(node, 'bad', T((res.data && res.data.error) || NOSERVER)); }
    else { say(node, '', ''); }
    done();
  }
  async function resetPassword(u, node) {
    var pass = window.prompt(T('New password (at least 8 characters):'));
    if (pass === null) { return; }
    if (pass.length < 8) {
      say(node, 'bad', T('The password must have at least 8 characters.'));
      return;
    }
    var res = await post('/api/admin/users/' + u.id + '/password', {password: pass});
    if (!res.ok) { say(node, 'bad', T((res.data && res.data.error) || NOSERVER)); }
    else { say(node, 'ok', T('Password updated.')); }
  }
  async function recordPayment(b, node) {
    var amount = window.prompt(T('Paid amount (0 clears the payment):'), String(b.paid_amount || 0));
    if (amount === null) { return; }
    amount = String(amount).trim().replace(/,/g, '');
    if (!/^\d+(\.\d{1,2})?$/.test(amount)) { say(node, 'bad', T('Amount must be a number.')); return; }
    var method = '';
    if (Number(amount) > 0) {
      method = window.prompt(T('Payment method (for example MTN MoMo or Flutterwave):'), b.paid_method || '');
      if (method === null) { return; }
      method = String(method).trim();
      if (!method) { say(node, 'bad', T('Please enter how the payment was made.')); return; }
    }
    var res = await post('/api/admin/bookings/' + b.id + '/payment',
      {amount: Number(amount), method: method});
    if (!res.ok) { say(node, 'bad', T((res.data && res.data.error) || NOSERVER)); return; }
    say(node, 'ok', T('Payment saved.'));
    loadBookings();
  }
  async function removeRecord(url, question, node, done) {
    if (!window.confirm(T(question))) { return; }
    var res = await del(url);
    if (!res.ok) { say(node, 'bad', T((res.data && res.data.error) || NOSERVER)); }
    else { say(node, '', ''); }
    done();
  }
  /* Trip cell: pick-up on the first line, drop-off as a muted second line, so
     the route never breaks in the middle of a place name. */
  function tripCell(tr, b) {
    var td = cell(tr, b.pickup);
    td.appendChild(el('div', 'sub', '\u2192 ' + b.dropoff));
    return td;
  }
  /* Action cell: one flex row that packs from the right, so buttons wrap as a
     group instead of one per line when the column is narrow. */
  function actionsCell(tr) {
    var td = cell(tr, '');
    var box = el('div', 'row-actions');
    td.appendChild(box);
    return box;
  }
  function bookingActions(b, node, done) {
    var box = actionsCell(b.row);
    if (b.status === 'pending') {
      box.appendChild(small('Confirm', 'ok', function () { changeBooking(b.id, 'confirmed', node, done); }));
    }
    if (b.status === 'confirmed') {
      box.appendChild(small('Complete', 'ok', function () { changeBooking(b.id, 'completed', node, done); }));
    }
    if (b.status === 'pending' || b.status === 'confirmed') {
      box.appendChild(small('Cancel', 'warn', function () { changeBooking(b.id, 'cancelled', node, done); }));
    }
    return box;
  }

  /* ---------- overview ---------- */
  /* The chart is one blue line over a 12% fill, drawn from /api/report data.
     Geometry is measured from the box so dots stay round at any width. */
  var trend = {months: [], peak: 0};
  function svgNode(tag, attrs) {
    var n = document.createElementNS('http://www.w3.org/2000/svg', tag);
    for (var k in attrs) { if (attrs.hasOwnProperty(k)) { n.setAttribute(k, attrs[k]); } }
    return n;
  }
  function drawTrend() {
    var box = $('admin-chart');
    if (!box || !trend.months.length || !trend.peak || !box.offsetParent) { return; }
    clear(box);
    var width = Math.max(280, Math.round(box.clientWidth || 600));
    var H = 180, TOP = 14, BASE = H - 14;
    var max = Math.max(4, trend.peak);
    var step = width / trend.months.length;
    var pts = trend.months.map(function (m, i) {
      return {
        x: step * i + step / 2,
        y: BASE - (m.n / max) * (BASE - TOP),
        n: m.n, label: m.label, key: m.key
      };
    });

    var svg = svgNode('svg', {
      'class': 'chart-svg', viewBox: '0 0 ' + width + ' ' + H,
      width: width, height: H, 'aria-hidden': 'true', focusable: 'false'
    });
    [0.25, 0.5, 0.75].forEach(function (f) {
      var y = BASE - f * (BASE - TOP);
      svg.appendChild(svgNode('line', {'class': 'chart-grid', x1: 0, x2: width, y1: y, y2: y}));
    });
    svg.appendChild(svgNode('line', {'class': 'chart-base', x1: 0, x2: width, y1: BASE, y2: BASE}));

    var dArea = 'M ' + pts[0].x + ' ' + BASE + ' ' +
      pts.map(function (p) { return 'L ' + p.x + ' ' + p.y; }).join(' ') +
      ' L ' + pts[pts.length - 1].x + ' ' + BASE + ' Z';
    svg.appendChild(svgNode('path', {'class': 'chart-area', d: dArea}));

    var dLine = pts.map(function (p, i) {
      return (i ? 'L ' : 'M ') + p.x + ' ' + p.y;
    }).join(' ');
    svg.appendChild(svgNode('path', {'class': 'chart-line', d: dLine}));

    pts.forEach(function (p) {
      svg.appendChild(svgNode('circle', {'class': 'chart-dot', cx: p.x, cy: p.y, r: 3.5}));
    });
    box.appendChild(svg);

    var axis = el('div', 'chart-x');
    pts.forEach(function (p) {
      var s = el('span', '', p.label);
      s.style.left = (p.x / width * 100) + '%';
      axis.appendChild(s);
    });
    box.appendChild(axis);

    box.setAttribute('aria-label', T('Bookings per month') + ': ' + pts.map(function (p) {
      return p.label + ' ' + p.n;
    }).join(', '));
  }
  function setInsight(thisMonth, d) {
    var box = $('admin-insight');
    if (!box) { return; }
    clear(box);
    var waiting = d && d.bookings ? d.bookings.pending : 0;
    if (!thisMonth && !waiting) { box.hidden = true; return; }
    var parts = [];
    if (thisMonth) { parts.push(countLine(thisMonth, 'bookings this month')); }
    if (waiting) { parts.push(countLine(waiting, 'waiting for a decision')); }
    parts.forEach(function (n, i) {
      if (i) { box.appendChild(document.createTextNode(' \u00B7 ')); }
      box.appendChild(n);
    });
    box.hidden = false;
  }
  function renderTrend(rows, d) {
    var box = $('admin-chart');
    if (!box) { return; }
    clear(box);
    var counts = {};
    rows.forEach(function (b) {
      var key = String(b.created_at).slice(0, 7);
      counts[key] = (counts[key] || 0) + 1;
    });
    var now = new Date();
    trend.months = [];
    for (var i = 5; i >= 0; i--) {
      var dt = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth() - i, 1));
      var key = dt.toISOString().slice(0, 7);
      trend.months.push({
        key: key,
        label: dt.toLocaleString('en', {month: 'short', timeZone: 'UTC'}),
        n: counts[key] || 0
      });
    }
    trend.peak = 0;
    trend.months.forEach(function (m) { if (m.n > trend.peak) { trend.peak = m.n; } });
    if (!trend.peak) {
      window.ttEmptyState(box, {size: 'compact', title: 'No bookings in the last six months.'});
      setInsight(0, d);
      return;
    }
    drawTrend();
    setInsight(trend.months[trend.months.length - 1].n, d);
  }
  async function loadOverview() {
    var st = $('admin-overview-status'), pulse = $('admin-pulse'), note = $('admin-pulse-note');
    var insight = $('admin-insight');
    say(st, '', T('Loading...'));
    skelRows('admin-pending', 3);
    skelPulse(pulse, 4);
    if (note) { clear(note); }
    if (insight) { insight.hidden = true; }

    var report, bookings;
    try { report = await api('/api/report'); } catch (e) { report = {ok: false}; }
    try { bookings = await api('/api/bookings'); } catch (e) { bookings = {ok: false}; }
    if (!report.ok) { fail(st, report); return; }
    if (!bookings.ok) { fail(st, bookings); return; }

    var d = report.data;
    clear(pulse);
    setNavCount('bookings', d.bookings.pending, 'pending');
    pulse.appendChild(pulseCell('Pending', d.bookings.pending, 'waiting for a decision'));
    pulse.appendChild(pulseCell('Confirmed', d.bookings.confirmed, 'upcoming trips'));
    pulse.appendChild(pulseCell('Available cars', d.cars.available, 'ready to book'));
    pulse.appendChild(pulseCell('Revenue', Math.round(d.revenue.total), 'recorded payments'));

    if (note) {
      clear(note);
      [countLine(d.accounts, 'Accounts'),
       countLine(d.messages, 'Messages'),
       countLine(d.cars.booked, 'Booked cars')].forEach(function (n, i) {
        if (i) { note.appendChild(document.createTextNode(' \u00B7 ')); }
        note.appendChild(n);
      });
    }

    renderTrend(bookings.data, d);

    var pending = bookings.data.filter(function (b) { return b.status === 'pending'; });
    if (!pending.length) {
      window.ttEmptyState($('admin-pending').parentNode, {
        icon: 'clock',
        title: 'Nothing needs attention.',
        text: 'New booking requests will appear here as they arrive.'
      });
      say(st, '', '');
      return;
    }
    var tb = makeTable($('admin-pending'), ['#', 'Customer', 'Car', 'Trip', 'Date and time', 'Action']);
    pending.forEach(function (b) {
      var tr = el('tr');
      cell(tr, String(b.id));
      var tc = cell(tr, b.customer);
      tc.appendChild(el('div', 'sub contact', b.phone || b.email));
      cell(tr, b.car_name);
      tripCell(tr, b);
      cell(tr, b.trip_at.replace('T', ' '));
      bookingActions({id: b.id, status: b.status, row: tr}, st, loadOverview);
      tb.appendChild(tr);
    });
    say(st, '', '');
  }

  /* ---------- bookings ---------- */
  async function loadBookings() {
    var st = $('admin-bookings-status');
    bookingOptionsLoaded = false;
    say(st, '', T('Loading...'));
    skelRows('admin-bookings', 4);
    var r;
    try { r = await api('/api/bookings'); } catch (e) { r = {ok: false}; }
    if (!r.ok) { fail(st, r); return; }
    state.bookings = r.data;
    renderBookings();
  }
  function renderBookings() {
    var q = query('bookings-filter'), status = $('bookings-status').value;
    var rows = state.bookings.filter(function (b) {
      return (!status || b.status === status) &&
        matches(b, ['id', 'customer', 'car_name', 'pickup', 'dropoff', 'trip_at', 'email', 'phone'], q);
    });
    if (!rows.length) {
      emptyTable('admin-bookings', state.bookings.length ? {
        icon: 'tray',
        title: 'No bookings match these filters.',
        action: {label: 'Clear filters', run: function () {
          clearFilters(['bookings-filter', 'bookings-status'], renderBookings);
        }}
      } : {
        icon: 'tray',
        title: 'No bookings yet.',
        text: 'Bookings from customers will appear here.'
      });
      say($('admin-bookings-status'), '', '');
      return;
    }
    var tb = makeTable($('admin-bookings'),
      ['#', 'Customer', 'Car', 'Trip', 'Date and time', 'Passengers', 'Status', 'Paid', 'Action']);
    rows.forEach(function (b) {
      var tr = el('tr');
      cell(tr, String(b.id));
      var tc = cell(tr, b.customer);
      tc.appendChild(el('div', 'sub contact', b.phone || b.email));
      cell(tr, b.car_name);
      tripCell(tr, b);
      cell(tr, b.trip_at.replace('T', ' '));
      cell(tr, String(b.passengers));
      cell(tr, '').appendChild(badge(b.status));
      cell(tr, b.paid_amount > 0 ? String(b.paid_amount) + ' · ' + b.paid_method : '-');
      var acts = bookingActions({id: b.id, status: b.status, row: tr}, $('admin-bookings-status'), loadBookings);
      /* Secondary actions live in the row menu so the status action stays the
         one thing the eye lands on, and the row keeps a single action line. */
      var more = [];
      if (b.user_id && b.kind === 'car') {
        more.push({label: 'Edit', run: function () { openBookingForm(b); }});
      }
      if (b.status !== 'cancelled') {
        more.push({
          label: b.paid_amount > 0 ? 'Edit payment' : 'Record payment',
          run: function () { recordPayment(b, $('admin-bookings-status')); }
        });
      }
      if (more.length) { acts.appendChild(rowMenu(more)); }
      tb.appendChild(tr);
    });
    say($('admin-bookings-status'), '', '');
  }

  /* ---------- booking form (create and edit) ---------- */
  var editingBookingId = null;
  var bookingOptionsLoaded = false;
  async function ensureBookingOptions() {
    if (bookingOptionsLoaded) { return true; }
    var users, cars;
    try {
      users = await api('/api/admin/users');
      cars = await api('/api/cars');
    } catch (e) {
      users = {ok: false};
      cars = {ok: false};
    }
    if (!users.ok || !cars.ok) {
      say($('admin-bookings-status'), 'bad', T(NOSERVER));
      return false;
    }
    var uSel = $('ab-user');
    clear(uSel);
    users.data.filter(function (u) { return u.active; }).forEach(function (u) {
      var o = el('option', '', u.name + ' (' + u.email + ')');
      o.value = String(u.id);
      uSel.appendChild(o);
    });
    var cSel = $('ab-car');
    clear(cSel);
    cars.data.forEach(function (c) {
      var o = el('option', '', c.name + ' \u2014 ' + T(LABEL[c.status] || c.status));
      o.value = String(c.id);
      cSel.appendChild(o);
    });
    bookingOptionsLoaded = true;
    return true;
  }
  async function openBookingForm(b) {
    if (!await ensureBookingOptions()) { return; }
    if (!$('ab-user').options.length) {
      say($('admin-bookings-status'), 'bad', T('No accounts yet.'));
      return;
    }
    editingBookingId = b ? String(b.id) : null;
    $('ab-form-title').textContent = T(b ? 'Edit booking' : 'New booking');
    $('ab-user').value = b ? String(b.user_id) : $('ab-user').options[0].value;
    $('ab-car').value = b ? String(b.car_id) : $('ab-car').options[0].value;
    $('ab-from').value = b ? b.pickup : '';
    $('ab-to').value = b ? b.dropoff : '';
    $('ab-when').value = b ? b.trip_at : '';
    $('ab-pax').value = b ? String(b.passengers) : '1';
    $('ab-notes').value = b ? (b.notes || '') : '';
    $('ab-form').hidden = false;
    $('ab-from').focus();
  }
  function closeBookingForm() {
    var form = $('ab-form');
    if (form) { form.hidden = true; }
    editingBookingId = null;
  }
  async function saveBooking(event) {
    event.preventDefault();
    var st = $('admin-bookings-status');
    var data = {
      user_id: Number($('ab-user').value),
      car_id: Number($('ab-car').value),
      pickup: $('ab-from').value,
      dropoff: $('ab-to').value,
      trip_at: $('ab-when').value,
      passengers: Number($('ab-pax').value),
      notes: $('ab-notes').value
    };
    var res = editingBookingId === null
      ? await post('/api/bookings', data)
      : await patch('/api/bookings/' + editingBookingId, data);
    if (!res.ok) { say(st, 'bad', T((res.data && res.data.error) || NOSERVER)); return; }
    say(st, '', '');
    closeBookingForm();
    loadBookings();
  }

  /* ---------- fleet ---------- */
  async function loadFleet() {
    var st = $('admin-fleet-status');
    say(st, '', T('Loading...'));
    skelRows('admin-fleet', 5);
    var r;
    try { r = await api('/api/cars'); } catch (e) { r = {ok: false}; }
    if (!r.ok) { fail(st, r); return; }
    state.cars = r.data;
    renderFleet();
  }
  function renderFleet() {
    var q = query('fleet-filter'), status = $('fleet-status').value;
    var rows = state.cars.filter(function (c) {
      return (!status || c.status === status) && matches(c, ['id', 'name', 'type', 'description'], q);
    });
    if (!rows.length) {
      emptyTable('admin-fleet', state.cars.length ? {
        icon: 'car',
        title: 'No cars match these filters.',
        action: {label: 'Clear filters', run: function () {
          clearFilters(['fleet-filter', 'fleet-status'], renderFleet);
        }}
      } : {
        icon: 'car',
        title: 'No cars in the fleet yet.',
        text: 'Cars you add will appear here and on the public fleet page.'
      });
      say($('admin-fleet-status'), '', '');
      return;
    }
    var tb = makeTable($('admin-fleet'), ['Photo', 'Car', 'Type', 'Status', 'Action']);
    rows.forEach(function (c) {
      var tr = el('tr'), td = el('td'), img = el('img', 'thumb');
      img.src = c.image; img.alt = c.name; img.loading = 'lazy';
      td.appendChild(img); tr.appendChild(td);
      var nameCell = cell(tr, c.name);
      nameCell.appendChild(el('div', 'sub', T('Passengers') + ': ' + c.capacity));
      cell(tr, T(c.type));
      cell(tr, '').appendChild(badge(c.status));
      var ta = actionsCell(tr);
      if (c.status !== 'booked') {
        var inMaint = c.status === 'maintenance';
        ta.appendChild(small(inMaint ? 'Set available' : 'Set maintenance', 'ghost', function () {
          changeCar(c.id, inMaint ? 'available' : 'maintenance', $('admin-fleet-status'), loadFleet);
        }));
      }
      ta.appendChild(small('Edit', 'ok', function () { openCarForm(c); }));
      ta.appendChild(small('Delete', 'warn', function () {
        removeRecord('/api/admin/cars/' + c.id, 'Delete this car?',
          $('admin-fleet-status'), loadFleet);
      }));
      tb.appendChild(tr);
    });
    say($('admin-fleet-status'), '', '');
  }

  /* ---------- fleet form (create and edit) ---------- */
  var CAR_FIELDS = ['name', 'type', 'description', 'image', 'capacity', 'price', 'week', 'specs'];
  var editingCarId = null;
  function openCarForm(car) {
    editingCarId = car ? String(car.id) : null;
    CAR_FIELDS.forEach(function (f) {
      var value;
      if (car) { value = f === 'specs' ? car[f].join('\n') : car[f]; }
      else { value = f === 'capacity' ? '4' : ''; }
      $('car-' + f).value = value === null || value === undefined ? '' : String(value);
    });
    $('car-form-title').textContent = T(car ? 'Edit car' : 'New car');
    $('car-form').hidden = false;
    $('car-name').focus();
  }
  function closeCarForm() {
    var form = $('car-form');
    if (form) { form.hidden = true; }
    editingCarId = null;
  }
  async function saveCar(event) {
    event.preventDefault();
    var st = $('admin-fleet-status'), data = {};
    CAR_FIELDS.forEach(function (f) { data[f] = $('car-' + f).value; });
    var res = editingCarId === null
      ? await post('/api/admin/cars', data)
      : await patch('/api/admin/cars/' + editingCarId, data);
    if (!res.ok) { say(st, 'bad', T((res.data && res.data.error) || NOSERVER)); return; }
    say(st, '', '');
    closeCarForm();
    loadFleet();
  }

  /* ---------- accounts ---------- */
  async function loadAccounts() {
    var st = $('admin-accounts-status');
    say(st, '', T('Loading...'));
    skelRows('admin-accounts', 4);
    var r;
    try { r = await api('/api/admin/users'); } catch (e) { r = {ok: false}; }
    if (!r.ok) { fail(st, r); return; }
    state.accounts = r.data;
    renderAccounts();
  }
  function renderAccounts() {
    var q = query('accounts-filter');
    var rows = state.accounts.filter(function (u) {
      return matches(u, ['id', 'name', 'email', 'phone'], q);
    });
    if (!rows.length) {
      emptyTable('admin-accounts', state.accounts.length ? {
        icon: 'users',
        title: 'No accounts match these filters.',
        action: {label: 'Clear filters', run: function () {
          clearFilters(['accounts-filter'], renderAccounts);
        }}
      } : {
        icon: 'users',
        title: 'No accounts yet.',
        text: 'Registered customers and admins will appear here.'
      });
      say($('admin-accounts-status'), '', '');
      return;
    }
    var tb = makeTable($('admin-accounts'),
      ['#', 'People', 'Phone', 'Role', 'Status', 'Joined', 'Action']);
    var me = window.ttUser;
    rows.forEach(function (u) {
      var tr = el('tr');
      cell(tr, String(u.id));
      whoCell(tr, u);
      cell(tr, u.phone || '-');
      cell(tr, T(u.admin ? 'Admin' : 'Customer'));
      cell(tr, '').appendChild(badge(u.active ? 'active' : 'inactive'));
      cell(tr, u.created_at);
      var ta = actionsCell(tr);
      var actions = [];
      if (me && me.id === u.id) {
        ta.appendChild(el('span', 'sub', T('You')));
      } else {
        actions.push({
          label: u.admin ? 'Remove admin' : 'Make admin',
          tone: u.admin ? 'warn' : '',
          run: function () { changeRole(u.id, !u.admin, $('admin-accounts-status'), loadAccounts); }
        });
        actions.push({
          label: u.active ? 'Deactivate' : 'Activate',
          tone: u.active ? 'warn' : 'ok',
          run: function () { changeActive(u.id, !u.active, $('admin-accounts-status'), loadAccounts); }
        });
      }
      actions.push({
        label: 'Reset password',
        run: function () { resetPassword(u, $('admin-accounts-status')); }
      });
      if (!me || me.id !== u.id) {
        actions.push({
          label: 'Delete account',
          tone: 'warn',
          run: function () {
            removeRecord('/api/admin/users/' + u.id, 'Delete this account?',
              $('admin-accounts-status'), loadAccounts);
          }
        });
      }
      ta.appendChild(rowMenu(actions));
      tb.appendChild(tr);
    });
    say($('admin-accounts-status'), '', '');
  }

  /* ---------- account form ---------- */
  function openAccountForm() {
    var form = $('account-form');
    form.reset();
    form.hidden = false;
    $('af-first').focus();
  }
  function closeAccountForm() {
    var form = $('account-form');
    if (form) { form.hidden = true; }
  }
  async function saveAccount(event) {
    event.preventDefault();
    var st = $('admin-accounts-status');
    var res = await post('/api/admin/users', {
      first_name: $('af-first').value,
      last_name: $('af-last').value,
      email: $('af-email').value,
      phone: $('af-phone').value,
      password: $('af-pass').value,
      admin: $('af-admin').checked
    });
    if (!res.ok) { say(st, 'bad', T((res.data && res.data.error) || NOSERVER)); return; }
    say(st, '', '');
    closeAccountForm();
    loadAccounts();
  }

  /* ---------- messages ---------- */
  async function loadMessages() {
    var st = $('admin-messages-status');
    say(st, '', T('Loading...'));
    skelRows('admin-messages', 4);
    var r;
    try { r = await api('/api/admin/messages'); } catch (e) { r = {ok: false}; }
    if (!r.ok) { fail(st, r); return; }
    state.messages = r.data;
    setNavCount('messages', r.data.filter(function (m) { return !m.handled; }).length, 'open');
    renderMessages();
  }
  function renderMessages() {
    var q = query('messages-filter'), status = $('messages-status').value;
    var rows = state.messages.filter(function (m) {
      return (!status || (status === 'handled' ? m.handled : !m.handled)) &&
        matches(m, ['id', 'name', 'email', 'phone', 'service', 'message'], q);
    });
    if (!rows.length) {
      emptyTable('admin-messages', state.messages.length ? {
        icon: 'message',
        title: 'No messages match these filters.',
        action: {label: 'Clear filters', run: function () {
          clearFilters(['messages-filter', 'messages-status'], renderMessages);
        }}
      } : {
        icon: 'message',
        title: 'No messages yet.',
        text: 'Contact and support requests will appear here.'
      });
      say($('admin-messages-status'), '', '');
      return;
    }
    var tb = makeTable($('admin-messages'),
      ['#', 'Name', 'Email', 'Phone', 'Service', 'Message', 'Received', 'Status', 'Action']);
    rows.forEach(function (m) {
      var tr = el('tr');
      cell(tr, String(m.id));
      cell(tr, m.name);
      cell(tr, m.email);
      cell(tr, m.phone || '-');
      cell(tr, m.service || '-');
      cell(tr, m.message);
      cell(tr, m.created_at);
      cell(tr, '').appendChild(badge(m.handled ? 'handled' : 'open'));
      var ta = actionsCell(tr);
      ta.appendChild(small(m.handled ? 'Reopen' : 'Mark handled', m.handled ? 'ghost' : 'ok', function () {
        changeMessage(m.id, !m.handled, $('admin-messages-status'), loadMessages);
      }));
      ta.appendChild(small('Delete', 'warn', function () {
        removeRecord('/api/admin/messages/' + m.id, 'Delete this message?',
          $('admin-messages-status'), loadMessages);
      }));
      tb.appendChild(tr);
    });
    say($('admin-messages-status'), '', '');
  }

  /* ---------- comments ---------- */
  async function loadComments() {
    var st = $('admin-comments-status');
    say(st, '', T('Loading...'));
    skelRows('admin-comments', 4);
    var r;
    try { r = await api('/api/admin/comments'); } catch (e) { r = {ok: false}; }
    if (!r.ok) { fail(st, r); return; }
    state.comments = r.data;
    setNavCount('comments', r.data.filter(function (c) { return !c.handled; }).length, 'open');
    renderComments();
  }
  function renderComments() {
    var q = query('comments-filter');
    var rows = state.comments.filter(function (c) {
      return matches(c, ['id', 'name', 'rating', 'text'], q);
    });
    if (!rows.length) {
      emptyTable('admin-comments', state.comments.length ? {
        icon: 'star',
        title: 'No comments match these filters.',
        action: {label: 'Clear filters', run: function () {
          clearFilters(['comments-filter'], renderComments);
        }}
      } : {
        icon: 'star',
        title: 'No comments yet.',
        text: 'Ratings and private feedback will appear here.'
      });
      say($('admin-comments-status'), '', '');
      return;
    }
    var tb = makeTable($('admin-comments'), ['#', 'Name', 'Rating', 'Comment', 'Received', 'Status', 'Action']);
    rows.forEach(function (c) {
      var tr = el('tr');
      cell(tr, String(c.id));
      cell(tr, c.name);
      cell(tr, c.rating + ' / 5');
      cell(tr, c.text);
      cell(tr, c.created_at);
      cell(tr, '').appendChild(badge(c.handled ? 'handled' : 'open'));
      var ta = actionsCell(tr);
      ta.appendChild(small(c.handled ? 'Reopen' : 'Mark handled', c.handled ? 'ghost' : 'ok', function () {
        changeComment(c.id, !c.handled, $('admin-comments-status'), loadComments);
      }));
      ta.appendChild(small('Delete', 'warn', function () {
        removeRecord('/api/admin/comments/' + c.id, 'Delete this comment?',
          $('admin-comments-status'), loadComments);
      }));
      tb.appendChild(tr);
    });
    say($('admin-comments-status'), '', '');
  }

  /* ---------- fares ---------- */
  async function loadFares() {
    var st = $('admin-fares-status');
    say(st, '', T('Loading...'));
    skelRows('admin-fares', 4);
    var r;
    try { r = await api('/api/admin/fares'); } catch (e) { r = {ok: false}; }
    if (!r.ok) { fail(st, r); return; }
    state.fares = r.data;
    renderFares();
  }
  function renderFares() {
    var q = query('fares-filter');
    var rows = state.fares.filter(function (f) {
      return matches(f, ['key', 'tag', 'name', 'note', 'currency'], q);
    });
    if (!rows.length) {
      emptyTable('admin-fares', state.fares.length ? {
        icon: 'tag',
        title: 'No fares match these filters.',
        action: {label: 'Clear filters', run: function () {
          clearFilters(['fares-filter'], renderFares);
        }}
      } : {
        icon: 'tag',
        title: 'No fares yet.',
        text: 'Fares you add will appear on the Pay online page.'
      });
      say($('admin-fares-status'), '', '');
      return;
    }
    var tb = makeTable($('admin-fares'),
      ['Code', 'Name', 'Price', 'Note', 'Payment link', 'Status', 'Action']);
    rows.forEach(function (f) {
      var tr = el('tr');
      cell(tr, f.key);
      var nameCell = cell(tr, f.name);
      if (f.tag) { nameCell.appendChild(el('div', 'sub', f.tag)); }
      cell(tr, f.price);
      cell(tr, f.note || '-');
      cell(tr, f.flw_link ? T('Set') : T('WhatsApp'));
      cell(tr, '').appendChild(badge(f.active ? 'active' : 'inactive'));
      var ta = actionsCell(tr);
      ta.appendChild(small('Edit', 'ok', function () { openFareForm(f); }));
      ta.appendChild(small(f.active ? 'Hide' : 'Show', 'ghost', function () {
        patch('/api/admin/fares/' + f.id, {active: !f.active}).then(function (res) {
          if (!res.ok) { say($('admin-fares-status'), 'bad', T((res.data && res.data.error) || NOSERVER)); }
          loadFares();
        });
      }));
      ta.appendChild(small('Delete', 'warn', function () {
        removeRecord('/api/admin/fares/' + f.id, 'Delete this fare?',
          $('admin-fares-status'), loadFares);
      }));
      tb.appendChild(tr);
    });
    say($('admin-fares-status'), '', '');
  }

  /* ---------- fare form (create and edit) ---------- */
  var editingFareId = null;
  function openFareForm(f) {
    editingFareId = f ? String(f.id) : null;
    $('fr-key').value = f ? f.key : '';
    $('fr-tag').value = f ? f.tag : '';
    $('fr-name').value = f ? f.name : '';
    $('fr-amount').value = f ? String(f.amount) : '';
    $('fr-currency').value = f ? f.currency : 'RWF';
    $('fr-note').value = f ? f.note : '';
    $('fr-flw').value = f ? f.flw_link : '';
    $('fr-active').checked = f ? !!f.active : true;
    $('fare-form-title').textContent = T(f ? 'Edit fare' : 'New fare');
    $('fare-form').hidden = false;
    $('fr-name').focus();
  }
  function closeFareForm() {
    var form = $('fare-form');
    if (form) { form.hidden = true; }
    editingFareId = null;
  }
  async function saveFare(event) {
    event.preventDefault();
    var st = $('admin-fares-status');
    var data = {
      key: $('fr-key').value, tag: $('fr-tag').value, name: $('fr-name').value,
      amount: $('fr-amount').value, currency: $('fr-currency').value,
      note: $('fr-note').value, flw_link: $('fr-flw').value,
      active: $('fr-active').checked
    };
    var res = editingFareId === null
      ? await post('/api/admin/fares', data)
      : await patch('/api/admin/fares/' + editingFareId, data);
    if (!res.ok) { say(st, 'bad', T((res.data && res.data.error) || NOSERVER)); return; }
    say(st, '', '');
    closeFareForm();
    loadFares();
  }

  /* ---------- which view is open ---------- */
  /* Views are real routes (/admin/fleet), rendered and marked active by the
     server. The nav is a full page load, so no hashchange handling here. */
  var LOADERS = {
    overview: loadOverview, bookings: loadBookings, fleet: loadFleet,
    accounts: loadAccounts, messages: loadMessages, comments: loadComments,
    fares: loadFares
  };
  function currentView() {
    var m = /^\/admin\/([a-z-]+)/.exec(location.pathname);
    var view = m ? m[1] : 'overview';
    return LOADERS[view] ? view : 'overview';
  }
  function refresh() {
    var view = currentView();
    renderMe();
    if (view !== 'fleet') { closeCarForm(); }
    if (view !== 'bookings') { closeBookingForm(); }
    if (view !== 'fares') { closeFareForm(); }
    if (view !== 'accounts') { closeAccountForm(); }
    LOADERS[view]();
    refreshNavCounts();
    centerActiveNav();
  }
  window.ttPages = {refresh: refresh};
  window.addEventListener('tt:user', function () {
    renderMe();
    if (currentView() === 'accounts' && state.accounts.length) { renderAccounts(); }
  });

  /* Filters re-render cached rows; they never refetch. */
  function on(id, evt, fn) { var n = $(id); if (n) { n.addEventListener(evt, fn); } }
  on('bookings-filter', 'input', renderBookings);
  on('bookings-status', 'change', renderBookings);
  on('fleet-filter', 'input', renderFleet);
  on('fleet-status', 'change', renderFleet);
  on('accounts-filter', 'input', renderAccounts);
  on('messages-filter', 'input', renderMessages);
  on('messages-status', 'change', renderMessages);
  on('comments-filter', 'input', renderComments);
  on('car-new', 'click', function () { openCarForm(null); });
  on('car-cancel', 'click', closeCarForm);
  on('car-form', 'submit', saveCar);
  on('account-new', 'click', openAccountForm);
  on('af-cancel', 'click', closeAccountForm);
  on('account-form', 'submit', saveAccount);
  on('booking-new', 'click', function () { openBookingForm(null); });
  on('ab-cancel', 'click', closeBookingForm);
  on('ab-form', 'submit', saveBooking);
  on('fares-filter', 'input', renderFares);
  on('fare-new', 'click', function () { openFareForm(null); });
  on('fare-cancel', 'click', closeFareForm);
  on('fare-form', 'submit', saveFare);

  /* The chart is measured from its box, so redraw it when the column resizes. */
  var trendTimer;
  window.addEventListener('resize', function () {
    clearTimeout(trendTimer);
    trendTimer = setTimeout(drawTrend, 120);
  });

  refresh();
})();
