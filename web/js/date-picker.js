/* Booking date & time picker. The chosen value is written to the hidden
   #bk-when field as a local ISO string (YYYY-MM-DDTHH:MM); dashboard.js posts
   it to /api/bookings. Changes are only kept when Apply is pressed. */
(function () {
  var btn = document.getElementById('bk-when-btn'), pop = document.getElementById('bk-when-pop');
  var hidden = document.getElementById('bk-when'), text = document.getElementById('bk-when-text');
  var title = document.getElementById('dp-title'), days = document.getElementById('dp-days');
  var hourSel = document.getElementById('dp-hour'), minSel = document.getElementById('dp-min');
  var prev = document.getElementById('dp-prev'), next = document.getElementById('dp-next');
  var todayBtn = document.getElementById('dp-today'), clearBtn = document.getElementById('dp-clear');
  var applyBtn = document.getElementById('dp-apply'), msg = document.getElementById('dp-msg');
  if (!btn || !pop || !hidden || !days) { return; }

  var MINUTES = [0, 15, 30, 45];
  var committed = null;   // Date last applied, or null
  var view = null;        // first day of the month being shown
  var picked = null;      // day chosen in the calendar (midnight), or null
  var draftHour = 12, draftMin = 0;

  function startOfDay(d) { return new Date(d.getFullYear(), d.getMonth(), d.getDate()); }
  function startOfMonth(d) { return new Date(d.getFullYear(), d.getMonth(), 1); }
  function sameDay(a, b) { return !!a && !!b && a.getTime() === b.getTime(); }
  function pad(n) { return String(n).padStart(2, '0'); }
  function locale() { return document.documentElement.lang === 'rw' ? 'rw' : 'en-GB'; }
  function fmtDay(d) {
    return new Intl.DateTimeFormat(locale(), {weekday: 'short', day: 'numeric', month: 'short'}).format(d);
  }
  function fmtTitle(d) {
    return new Intl.DateTimeFormat(locale(), {month: 'long', year: 'numeric'}).format(d);
  }
  function fmtIso(d) {
    return d.getFullYear() + '-' + pad(d.getMonth() + 1) + '-' + pad(d.getDate()) +
      'T' + pad(d.getHours()) + ':' + pad(d.getMinutes());
  }
  function fmtLabel(d) { return fmtDay(d) + ' · ' + pad(d.getHours()) + ':' + pad(d.getMinutes()); }
  function setMsg(t) {
    if (!msg) { return; }
    msg.className = t ? 'status bad' : 'status';
    msg.textContent = t || '';
  }

  (function fillHours() {
    for (var h = 0; h < 24; h++) {
      var o = document.createElement('option');
      o.value = o.textContent = pad(h);
      hourSel.appendChild(o);
    }
  })();

  /* Keep the time on or after "now" when the chosen day is today. */
  function clampTime() {
    var now = new Date();
    if (!picked || !sameDay(picked, startOfDay(now))) { return; }
    if (draftHour < now.getHours()) { draftHour = now.getHours(); }
    if (draftHour === now.getHours() && draftMin < now.getMinutes()) {
      var later = MINUTES.filter(function (m) { return m >= now.getMinutes(); })[0];
      if (later === undefined) { draftHour = Math.min(23, draftHour + 1); later = 0; }
      draftMin = later;
    }
  }

  function syncTimeControls() {
    clampTime();
    var now = new Date();
    var isToday = !!picked && sameDay(picked, startOfDay(now));
    hourSel.value = pad(draftHour);
    minSel.value = pad(draftMin);
    Array.prototype.forEach.call(hourSel.options, function (o) {
      o.disabled = isToday && Number(o.value) < now.getHours();
    });
    Array.prototype.forEach.call(minSel.options, function (o) {
      o.disabled = isToday && draftHour === now.getHours() && Number(o.value) < now.getMinutes();
    });
  }

  function render() {
    title.textContent = fmtTitle(view);
    days.textContent = '';
    var t = startOfDay(new Date());
    var firstDow = (new Date(view.getFullYear(), view.getMonth(), 1).getDay() + 6) % 7; // Monday = 0
    var count = new Date(view.getFullYear(), view.getMonth() + 1, 0).getDate();
    for (var i = 0; i < firstDow; i++) { days.appendChild(document.createElement('span')); }
    for (var day = 1; day <= count; day++) {
      (function (date) {
        var b = document.createElement('button');
        b.type = 'button';
        b.className = 'dp-day';
        b.textContent = date.getDate();
        b.setAttribute('aria-label', fmtDay(date));
        b.disabled = date < t;
        if (sameDay(date, t)) { b.classList.add('is-today'); }
        if (sameDay(date, picked)) { b.classList.add('on'); b.setAttribute('aria-pressed', 'true'); }
        b.addEventListener('click', function () {
          picked = date;
          syncTimeControls();
          setMsg('');
          render();
        });
        days.appendChild(b);
      })(new Date(view.getFullYear(), view.getMonth(), day));
    }
    prev.disabled = startOfMonth(view) <= startOfMonth(t);
    applyBtn.disabled = !picked;
    syncTimeControls();
  }

  function open() {
    picked = committed ? startOfDay(committed) : null;
    draftHour = committed ? committed.getHours() : 12;
    draftMin = committed ? committed.getMinutes() : 0;
    view = startOfMonth(picked || new Date());
    setMsg('');
    pop.hidden = false;
    btn.setAttribute('aria-expanded', 'true');
    render();
    var focusTarget = days.querySelector('.dp-day.on:not(:disabled)') || days.querySelector('.dp-day.is-today') ||
      days.querySelector('.dp-day:not(:disabled)');
    if (focusTarget) { focusTarget.focus(); }
  }

  function close() {
    pop.hidden = true;
    btn.setAttribute('aria-expanded', 'false');
  }

  function showValue() {
    text.textContent = committed ? fmtLabel(committed) : T('Select date & time');
    btn.classList.toggle('has-value', !!committed);
    hidden.value = committed ? fmtIso(committed) : '';
  }

  function apply() {
    if (!picked) { return; }
    var c = new Date(picked.getFullYear(), picked.getMonth(), picked.getDate(), draftHour, draftMin, 0, 0);
    var nowMinute = new Date();
    nowMinute.setSeconds(0, 0);
    if (c < nowMinute) {
      setMsg(T('Please choose a date and time in the future.'));
      syncTimeControls();
      return;
    }
    committed = c;
    showValue();
    close();
    btn.focus();
  }

  function reset() {
    committed = null;
    picked = null;
    showValue();
    setMsg('');
    close();
  }
  window.ttDatePicker = {reset: reset};

  btn.addEventListener('click', function () { pop.hidden ? open() : close(); });
  document.addEventListener('mousedown', function (e) {
    if (!pop.hidden && !pop.contains(e.target) && !btn.contains(e.target)) { close(); }
  });
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape' && !pop.hidden) { close(); btn.focus(); }
  });

  prev.addEventListener('click', function () { view = new Date(view.getFullYear(), view.getMonth() - 1, 1); render(); });
  next.addEventListener('click', function () { view = new Date(view.getFullYear(), view.getMonth() + 1, 1); render(); });
  todayBtn.addEventListener('click', function () {
    var now = new Date();
    view = startOfMonth(now);
    picked = startOfDay(now);
    setMsg('');
    render();
  });
  hourSel.addEventListener('change', function () { draftHour = Number(hourSel.value); syncTimeControls(); setMsg(''); });
  minSel.addEventListener('change', function () { draftMin = Number(minSel.value); syncTimeControls(); setMsg(''); });
  applyBtn.addEventListener('click', apply);
  clearBtn.addEventListener('click', reset);

  days.addEventListener('keydown', function (e) {
    var steps = {ArrowLeft: -1, ArrowRight: 1, ArrowUp: -7, ArrowDown: 7};
    if (!(e.key in steps)) { return; }
    var buttons = Array.prototype.slice.call(days.querySelectorAll('.dp-day'));
    var idx = buttons.indexOf(document.activeElement);
    if (idx < 0) { return; }
    e.preventDefault();
    var j = idx + steps[e.key];
    while (j >= 0 && j < buttons.length && buttons[j].disabled) { j += steps[e.key]; }
    if (j >= 0 && j < buttons.length) { buttons[j].focus(); }
  });

  showValue();
})();
