/* Custom date & time picker for every [data-datepicker] field. The markup comes
   from partials/date-field.html. The chosen value is written to the hidden
   input as a local ISO string — YYYY-MM-DDTHH:MM for data-mode="datetime",
   YYYY-MM-DD for data-mode="date" — so the page scripts keep reading the same
   ids they always have. Changes are only kept when Apply is pressed.

   data-min="today" disables past days; data-min="none" leaves them open (the
   admin edit form needs old bookings). window.ttDatePicker.set() lets a script
   fill the field programmatically, and form.reset() clears it. */
(function () {
  var MINUTES = [0, 15, 30, 45];
  var byRoot = new WeakMap();
  var byInput = new WeakMap();
  var openInst = null;

  function pad(n) { return String(n).padStart(2, '0'); }
  function startOfDay(d) { return new Date(d.getFullYear(), d.getMonth(), d.getDate()); }
  function startOfMonth(d) { return new Date(d.getFullYear(), d.getMonth(), 1); }
  function sameDay(a, b) { return !!a && !!b && a.getTime() === b.getTime(); }
  function locale() { return document.documentElement.lang === 'rw' ? 'rw' : 'en-GB'; }
  function fmtDay(d) {
    return new Intl.DateTimeFormat(locale(), {weekday: 'short', day: 'numeric', month: 'short'}).format(d);
  }
  function fmtTitle(d) {
    return new Intl.DateTimeFormat(locale(), {month: 'long', year: 'numeric'}).format(d);
  }
  function fmtIso(d, dateOnly) {
    var date = d.getFullYear() + '-' + pad(d.getMonth() + 1) + '-' + pad(d.getDate());
    return dateOnly ? date : date + 'T' + pad(d.getHours()) + ':' + pad(d.getMinutes());
  }
  function fmtLabel(d, dateOnly) {
    return dateOnly ? fmtDay(d) : fmtDay(d) + ' \u00b7 ' + pad(d.getHours()) + ':' + pad(d.getMinutes());
  }
  /* Accept both value shapes (and a space instead of T) so a record read from
     the API can be dropped straight into a picker. */
  function parseValue(raw) {
    var m = /^(\d{4})-(\d{2})-(\d{2})(?:[T ](\d{2}):(\d{2}))?/.exec(String(raw || '').trim());
    if (!m) { return null; }
    return new Date(Number(m[1]), Number(m[2]) - 1, Number(m[3]),
      m[4] ? Number(m[4]) : 0, m[5] ? Number(m[5]) : 0, 0, 0);
  }

  function enhance(root) {
    if (!root || byRoot.has(root)) { return; }
    var input = root.querySelector('input[type="hidden"]');
    var btn = root.querySelector('.dp-trigger');
    var pop = root.querySelector('.dp-pop');
    var text = root.querySelector('[data-dp-text]');
    var title = root.querySelector('[data-dp-title]');
    var days = root.querySelector('[data-dp-days]');
    var timeRow = root.querySelector('[data-dp-time]');
    var hourSel = root.querySelector('[data-dp-hour]');
    var minSel = root.querySelector('[data-dp-min]');
    var prev = root.querySelector('[data-dp-prev]');
    var next = root.querySelector('[data-dp-next]');
    var todayBtn = root.querySelector('[data-dp-today]');
    var clearBtn = root.querySelector('[data-dp-clear]');
    var applyBtn = root.querySelector('[data-dp-apply]');
    var msg = root.querySelector('[data-dp-msg]');
    if (!input || !btn || !pop || !days || !title || !prev || !next) { return; }

    var dateOnly = root.getAttribute('data-mode') === 'date';
    var allowPast = root.getAttribute('data-min') === 'none';
    if (dateOnly && timeRow) { timeRow.hidden = true; }

    var committed = null;   // Date last applied, or null
    var view = null;        // first day of the month being shown
    var picked = null;      // day chosen in the calendar (midnight), or null
    var draftHour = 12, draftMin = 0;

    function setMsg(t) {
      if (!msg) { return; }
      msg.className = t ? 'status bad' : 'status';
      msg.textContent = t || '';
    }

    if (hourSel && !hourSel.options.length) {
      for (var h = 0; h < 24; h++) {
        var o = document.createElement('option');
        o.value = o.textContent = pad(h);
        hourSel.appendChild(o);
      }
    }

    /* Keep the time on or after "now" when the chosen day is today. */
    function clampTime() {
      if (dateOnly || !hourSel || !minSel) { return; }
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
      if (dateOnly || !hourSel || !minSel) { return; }
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
          b.disabled = !allowPast && date < t;
          if (sameDay(date, t)) { b.classList.add('is-today'); }
          if (sameDay(date, picked)) { b.classList.add('on'); b.setAttribute('aria-pressed', 'true'); }
          b.addEventListener('click', function () {
            picked = date;
            syncTimeControls();
            setMsg('');
            render();
            positionPopup();
          });
          days.appendChild(b);
        })(new Date(view.getFullYear(), view.getMonth(), day));
      }
      prev.disabled = !allowPast && startOfMonth(view) <= startOfMonth(t);
      applyBtn.disabled = !picked;
      syncTimeControls();
    }

    function clearFixed() {
      pop.style.position = '';
      pop.style.left = '';
      pop.style.top = '';
      pop.style.bottom = '';
      pop.style.right = '';
      pop.style.width = '';
      pop.style.transform = '';
    }

    function positionPopup() {
      if (pop.hidden) { return; }
      root.classList.remove('dp-up', 'dp-sheet');
      // On narrow screens the CSS fixed bottom sheet owns the layout.
      if (window.innerWidth <= 560) {
        clearFixed();
        return;
      }
      // JS-positioned fixed popup so it cannot be clipped by scroll containers
      // (for example the admin booking modal). Re-run after render and on
      // scroll/resize to stay attached to the trigger.
      pop.style.position = 'fixed';
      pop.style.bottom = 'auto';
      pop.style.right = 'auto';
      pop.style.transform = 'none';
      var r = btn.getBoundingClientRect();
      var w = Math.min(320, window.innerWidth - 24);
      var h = pop.offsetHeight || 360;
      var left = Math.max(12, Math.min(r.left, window.innerWidth - w - 12));
      var top = r.bottom + 8;
      if (top + h > window.innerHeight - 12 && r.top - 8 - h >= 12) {
        top = r.top - 8 - h;
      }
      if (top < 12 || top + h > window.innerHeight - 12) {
        // Short window or field mid-page: use the same centred bottom sheet as
        // phones so the month header and Apply stay reachable.
        clearFixed();
        root.classList.add('dp-sheet');
        return;
      }
      pop.style.left = left + 'px';
      pop.style.top = top + 'px';
      pop.style.width = w + 'px';
    }

    function onViewportChange() {
      if (openInst !== inst) { return; }
      var r = btn.getBoundingClientRect();
      // If the trigger has scrolled out of view, close instead of floating.
      if (r.bottom < 0 || r.top > window.innerHeight || r.right < 0 || r.left > window.innerWidth) {
        close();
        return;
      }
      positionPopup();
    }

    function open() {
      if (openInst && openInst !== inst) { openInst.close(); }
      picked = committed ? startOfDay(committed) : null;
      draftHour = committed ? committed.getHours() : 12;
      draftMin = committed ? committed.getMinutes() : 0;
      view = startOfMonth(picked || new Date());
      setMsg('');
      root.classList.remove('dp-up', 'dp-sheet');
      clearFixed();
      pop.hidden = false;
      btn.setAttribute('aria-expanded', 'true');
      openInst = inst;
      document.body.classList.add('dp-open');
      render();
      positionPopup();
      window.addEventListener('resize', onViewportChange);
      window.addEventListener('scroll', onViewportChange, true);
      var focusTarget = days.querySelector('.dp-day.on:not(:disabled)') || days.querySelector('.dp-day.is-today') ||
        days.querySelector('.dp-day:not(:disabled)');
      if (focusTarget) { focusTarget.focus(); }
    }

    function close() {
      pop.hidden = true;
      btn.setAttribute('aria-expanded', 'false');
      root.classList.remove('dp-up', 'dp-sheet');
      clearFixed();
      window.removeEventListener('resize', onViewportChange);
      window.removeEventListener('scroll', onViewportChange, true);
      if (openInst === inst) {
        openInst = null;
        document.body.classList.remove('dp-open');
      }
    }

    function showValue() {
      text.textContent = committed ? fmtLabel(committed, dateOnly) : T(dateOnly ? 'Select date' : 'Select date & time');
      btn.classList.toggle('has-value', !!committed);
      input.value = committed ? fmtIso(committed, dateOnly) : '';
    }

    function apply() {
      if (!picked) { return; }
      var c = new Date(picked.getFullYear(), picked.getMonth(), picked.getDate(),
        dateOnly ? 0 : draftHour, dateOnly ? 0 : draftMin, 0, 0);
      var now = new Date();
      now.setSeconds(0, 0);
      var tooEarly = dateOnly ? startOfDay(c) < startOfDay(now) : c < now;
      if (!allowPast && tooEarly) {
        setMsg(T(dateOnly ? 'Please choose a date in the future.' : 'Please choose a date and time in the future.'));
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

    /* Programmatic value: a form opening on an existing row, or a page script
       clearing the field. opts.allowPast flips the past-date rule. */
    function set(raw, opts) {
      if (opts && 'allowPast' in opts) { allowPast = !!opts.allowPast; }
      committed = parseValue(raw);
      showValue();
      if (!pop.hidden) {
        picked = committed ? startOfDay(committed) : null;
        draftHour = committed ? committed.getHours() : 12;
        draftMin = committed ? committed.getMinutes() : 0;
        view = startOfMonth(picked || new Date());
        setMsg('');
        render();
        positionPopup();
      }
    }

    var inst = {root: root, close: close, reset: reset, set: set};
    byRoot.set(root, inst);
    byInput.set(input, inst);

    btn.addEventListener('click', function () { pop.hidden ? open() : close(); });

    prev.addEventListener('click', function () { view = new Date(view.getFullYear(), view.getMonth() - 1, 1); render(); });
    next.addEventListener('click', function () { view = new Date(view.getFullYear(), view.getMonth() + 1, 1); render(); });
    todayBtn.addEventListener('click', function () {
      var now = new Date();
      view = startOfMonth(now);
      picked = startOfDay(now);
      setMsg('');
      render();
    });
    if (hourSel) {
      hourSel.addEventListener('change', function () { draftHour = Number(hourSel.value); syncTimeControls(); setMsg(''); });
    }
    if (minSel) {
      minSel.addEventListener('change', function () { draftMin = Number(minSel.value); syncTimeControls(); setMsg(''); });
    }
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

    /* A form reset clears the hidden input natively; repaint the trigger after
       the browser has finished resetting the rest of the form. */
    var form = root.closest('form');
    if (form) {
      form.addEventListener('reset', function () { setTimeout(reset, 0); });
    }

    showValue();
  }

  document.addEventListener('mousedown', function (e) {
    if (openInst && !openInst.root.contains(e.target)) { openInst.close(); }
  });
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape' && openInst) {
      var trigger = openInst.root.querySelector('.dp-trigger');
      openInst.close();
      if (trigger) { trigger.focus(); }
    }
  });

  function all(root) {
    Array.prototype.forEach.call((root || document).querySelectorAll('[data-datepicker]'), enhance);
  }

  window.ttDatePicker = {
    enhance: enhance,
    refresh: all,
    /* target: element id or the hidden input itself */
    set: function (target, value, opts) {
      var input = typeof target === 'string' ? document.getElementById(target) : target;
      var inst = input && byInput.get(input);
      if (inst) { inst.set(value, opts); } else if (input) { input.value = value || ''; }
    },
    reset: function (target) {
      if (target === undefined) {
        Array.prototype.forEach.call(document.querySelectorAll('[data-datepicker]'), function (root) {
          var inst = byRoot.get(root);
          if (inst) { inst.reset(); }
        });
        return;
      }
      var input = typeof target === 'string' ? document.getElementById(target) : target;
      var inst = input && byInput.get(input);
      if (inst) { inst.reset(); } else if (input) { input.value = ''; }
    }
  };

  all();
})();
