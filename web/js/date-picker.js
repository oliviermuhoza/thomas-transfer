/* Custom date & time picker for the booking form.
   Writes the selected value into the hidden #bk-when field as a local
   ISO string (YYYY-MM-DDTHH:MM), which dashboard.js posts to /api/bookings. */
(function () {
  var btn = document.getElementById('bk-when-btn'), pop = document.getElementById('bk-when-pop');
  var hidden = document.getElementById('bk-when'), text = document.getElementById('bk-when-text');
  var title = document.getElementById('dp-title'), days = document.getElementById('dp-days');
  var hourSel = document.getElementById('dp-hour'), minSel = document.getElementById('dp-min');
  if (!btn || !pop || !hidden) { return; }

  var MONTHS = ['January', 'February', 'March', 'April', 'May', 'June',
                'July', 'August', 'September', 'October', 'November', 'December'];
  var view = new Date();
  view.setDate(1);
  var selected = null; // Date or null

  (function fillHours() {
    for (var h = 0; h < 24; h++) {
      var o = document.createElement('option');
      o.value = o.textContent = String(h).padStart(2, '0');
      hourSel.appendChild(o);
    }
    hourSel.value = '12';
  })();

  function today() { var n = new Date(); n.setHours(0, 0, 0, 0); return n; }
  function fmt(d) {
    return d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0') + '-' +
      String(d.getDate()).padStart(2, '0') + 'T' + String(d.getHours()).padStart(2, '0') + ':' +
      String(d.getMinutes()).padStart(2, '0');
  }
  function commit() {
    hidden.value = selected ? fmt(selected) : '';
    text.textContent = selected
      ? selected.toLocaleDateString(undefined, {weekday: 'short', day: 'numeric', month: 'short'}) +
        ' · ' + String(selected.getHours()).padStart(2, '0') + ':' + String(selected.getMinutes()).padStart(2, '0')
      : 'Select date & time';
  }
  function render() {
    title.textContent = MONTHS[view.getMonth()] + ' ' + view.getFullYear();
    days.textContent = '';
    var t = today();
    var firstDow = (new Date(view.getFullYear(), view.getMonth(), 1).getDay() + 6) % 7; // Monday = 0
    var count = new Date(view.getFullYear(), view.getMonth() + 1, 0).getDate();
    for (var i = 0; i < firstDow; i++) { days.appendChild(document.createElement('span')); }
    for (var day = 1; day <= count; day++) {
      var date = new Date(view.getFullYear(), view.getMonth(), day);
      var b = document.createElement('button');
      b.type = 'button';
      b.className = 'dp-day';
      b.textContent = day;
      b.disabled = date < t;
      if (selected && date.getTime() === new Date(selected.getFullYear(), selected.getMonth(), selected.getDate()).getTime()) {
        b.classList.add('on'); b.setAttribute('aria-pressed', 'true');
      }
      (function (d) {
        b.addEventListener('click', function () {
          selected = new Date(d.getFullYear(), d.getMonth(), d.getDate(), Number(hourSel.value), Number(minSel.value));
          render();
        });
      })(date);
      days.appendChild(b);
    }
    document.getElementById('dp-prev').disabled = new Date(view.getFullYear(), view.getMonth(), 1) <= t;
  }
  function open() { pop.hidden = false; btn.setAttribute('aria-expanded', 'true'); render(); }
  function close() { pop.hidden = true; btn.setAttribute('aria-expanded', 'false'); }

  btn.addEventListener('click', function () { pop.hidden ? open() : close(); });
  document.addEventListener('click', function (e) { if (!pop.contains(e.target) && e.target !== btn && !btn.contains(e.target)) { close(); } });
  document.addEventListener('keydown', function (e) { if (e.key === 'Escape' && !pop.hidden) { close(); btn.focus(); } });
  document.getElementById('dp-prev').addEventListener('click', function () { view.setMonth(view.getMonth() - 1); render(); });
  document.getElementById('dp-next').addEventListener('click', function () { view.setMonth(view.getMonth() + 1); render(); });

  hourSel.addEventListener('change', function () {
    if (selected) { selected.setHours(Number(hourSel.value)); }
    else { selected = new Date(today().getTime()); selected.setHours(Number(hourSel.value)); }
  });
  minSel.addEventListener('change', function () {
    if (selected) { selected.setMinutes(Number(minSel.value)); }
    else { selected = new Date(today().getTime()); selected.setMinutes(Number(minSel.value)); }
  });
  document.getElementById('dp-apply').addEventListener('click', function () {
    if (!selected) { selected = new Date(); selected.setHours(Number(hourSel.value), Number(minSel.value), 0, 0); }
    if (selected < new Date()) { selected = new Date(); selected.setSeconds(0, 0); }
    commit(); close();
  });
  document.getElementById('dp-clear').addEventListener('click', function () {
    selected = null; commit(); render();
  });

  commit(); render();
})();
