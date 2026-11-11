/* Custom select: every native <select> gets a themed listbox instead of the
   browser's own dropdown. The <select> itself stays in the DOM — form
   submission, .value, change events, required validation and option lists
   rebuilt by other scripts keep working; only the visible control is new.

   Usage: just write a normal <select>. Opt out with data-native or multiple. */
(function () {
  var seq = 0;
  var openInst = null;
  var byEl = new WeakMap();

  function optText(sel) {
    var o = sel.options[sel.selectedIndex];
    return o ? o.text : '';
  }

  function tick() {
    var svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    svg.setAttribute('class', 'tt-sel-tick');
    svg.setAttribute('viewBox', '0 0 24 24');
    svg.setAttribute('aria-hidden', 'true');
    svg.setAttribute('focusable', 'false');
    svg.innerHTML = '<path d="M5 12.8l4.2 4.2L19 7.4" fill="none" stroke="currentColor" ' +
      'stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/>';
    return svg;
  }

  function enhance(sel) {
    if (!sel || sel.tagName !== 'SELECT') { return; }
    if (sel.dataset.ttSel || sel.multiple || (sel.size && sel.size > 1) ||
        sel.hasAttribute('data-native')) { return; }
    sel.dataset.ttSel = '1';

    var n = ++seq;
    var id = sel.id || ('tt-sel-src-' + n);
    var menuId = id + '-menu';

    var wrap = document.createElement('div');
    wrap.className = 'tt-sel';

    var btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'tt-sel-btn';
    btn.id = id + '-btn';
    btn.setAttribute('role', 'combobox');
    btn.setAttribute('aria-haspopup', 'listbox');
    btn.setAttribute('aria-expanded', 'false');
    btn.setAttribute('aria-controls', menuId);

    var label = document.createElement('span');
    label.className = 'tt-sel-value';

    var caret = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    caret.setAttribute('class', 'tt-sel-caret');
    caret.setAttribute('viewBox', '0 0 24 24');
    caret.setAttribute('aria-hidden', 'true');
    caret.setAttribute('focusable', 'false');
    caret.innerHTML = '<path d="M6 9.5l6 6 6-6" fill="none" stroke="currentColor" ' +
      'stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>';

    var menu = document.createElement('ul');
    menu.className = 'tt-sel-menu';
    menu.id = menuId;
    menu.setAttribute('role', 'listbox');
    menu.hidden = true;

    btn.appendChild(label);
    btn.appendChild(caret);
    wrap.appendChild(btn);
    wrap.appendChild(menu);
    sel.parentNode.insertBefore(wrap, sel);
    wrap.appendChild(sel);
    sel.classList.add('tt-sel-src');
    sel.setAttribute('aria-hidden', 'true');
    sel.tabIndex = -1;

    /* The <label for="…"> should name the visible control. The select keeps
       its id so every $('id') in the page keeps working. */
    if (sel.id) {
      var lab = document.querySelector('label[for="' + sel.id + '"]');
      if (lab) { lab.htmlFor = btn.id; }
    }
    var aria = sel.getAttribute('aria-label');
    if (aria) { btn.setAttribute('aria-label', aria); }

    var active = -1;

    function sync() {
      var txt = optText(sel);
      label.textContent = txt;
      wrap.classList.toggle('is-empty', !txt);
      btn.disabled = !!sel.disabled;
      if (btn.disabled && openInst === inst) { close(); }
      if (!menu.hidden) { build(); }
    }

    function build() {
      menu.textContent = '';
      Array.prototype.forEach.call(sel.options, function (o, i) {
        var li = document.createElement('li');
        li.className = 'tt-sel-opt';
        li.id = menuId + '-' + i;
        li.dataset.index = String(i);
        li.setAttribute('role', 'option');
        li.setAttribute('aria-selected', o.selected ? 'true' : 'false');
        if (o.disabled) { li.setAttribute('aria-disabled', 'true'); }
        var text = document.createElement('span');
        text.className = 'tt-sel-opt-label';
        text.textContent = o.text;
        li.appendChild(text);
        if (o.selected) { li.appendChild(tick()); }
        menu.appendChild(li);
      });
      setActive(nearestEnabled(sel.selectedIndex >= 0 ? sel.selectedIndex : 0));
    }

    function options() { return menu.children; }

    function nearestEnabled(from) {
      var list = options(), len = list.length;
      if (!len) { return -1; }
      from = ((from % len) + len) % len;
      for (var k = 0; k < len; k++) {
        var i = (from + k) % len;
        if (!list[i].getAttribute('aria-disabled')) { return i; }
      }
      return -1;
    }

    function setActive(i) {
      var list = options();
      if (!list.length || i < 0) {
        active = -1;
        btn.removeAttribute('aria-activedescendant');
        return;
      }
      if (i >= list.length) { i = list.length - 1; }
      active = i;
      for (var k = 0; k < list.length; k++) {
        list[k].classList.toggle('is-active', k === i);
      }
      btn.setAttribute('aria-activedescendant', list[i].id);
      var li = list[i];
      if (li.offsetTop < menu.scrollTop) {
        menu.scrollTop = li.offsetTop;
      } else if (li.offsetTop + li.offsetHeight > menu.scrollTop + menu.clientHeight) {
        menu.scrollTop = li.offsetTop + li.offsetHeight - menu.clientHeight;
      }
    }

    function move(delta) {
      var list = options(), len = list.length;
      if (!len) { return; }
      var start = active < 0 ? (delta > 0 ? -1 : 0) : active;
      for (var step = 1; step <= len; step++) {
        var i = ((start + delta * step) % len + len) % len;
        if (!list[i].getAttribute('aria-disabled')) { setActive(i); return; }
      }
    }

    function lastEnabled() {
      var list = options();
      for (var i = list.length - 1; i >= 0; i--) {
        if (!list[i].getAttribute('aria-disabled')) { return i; }
      }
      return -1;
    }

    function openMenu() {
      if (btn.disabled) { return; }
      if (openInst && openInst !== inst) { openInst.close(); }
      build();
      menu.hidden = false;
      wrap.classList.remove('tt-sel-up');
      btn.setAttribute('aria-expanded', 'true');
      var r = btn.getBoundingClientRect();
      var h = menu.offsetHeight;
      if (r.bottom + 6 + h > window.innerHeight - 8 && r.top - 6 - h > 8) {
        wrap.classList.add('tt-sel-up');
      }
      openInst = inst;
    }

    function close(refocus) {
      if (menu.hidden) { return; }
      menu.hidden = true;
      wrap.classList.remove('tt-sel-up');
      btn.setAttribute('aria-expanded', 'false');
      btn.removeAttribute('aria-activedescendant');
      active = -1;
      if (openInst === inst) { openInst = null; }
      if (refocus) { btn.focus(); }
    }

    function choose(i) {
      var list = options();
      if (!list[i] || list[i].getAttribute('aria-disabled')) { return; }
      sel.selectedIndex = Number(list[i].dataset.index);
      sel.dispatchEvent(new Event('change', {bubbles: true}));
      sync();
      close(true);
    }

    var typed = '', typedAt = 0;
    function typeahead(ch) {
      var now = Date.now();
      typed = now - typedAt > 700 ? ch.toLowerCase() : typed + ch.toLowerCase();
      typedAt = now;
      var list = options();
      for (var k = 0; k < list.length; k++) {
        var i = (active + 1 + k) % list.length;
        if (list[i].getAttribute('aria-disabled')) { continue; }
        if (list[i].textContent.trim().toLowerCase().indexOf(typed) === 0) {
          setActive(i);
          return;
        }
      }
    }

    btn.addEventListener('click', function (e) {
      e.preventDefault();
      if (menu.hidden) { openMenu(); } else { close(); }
    });

    btn.addEventListener('keydown', function (e) {
      if (e.altKey || e.ctrlKey || e.metaKey) { return; }
      var isOpen = !menu.hidden;
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        if (isOpen) { move(1); } else { openMenu(); }
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        if (isOpen) { move(-1); } else { openMenu(); }
      } else if (e.key === 'Home' && isOpen) {
        e.preventDefault();
        setActive(nearestEnabled(0));
      } else if (e.key === 'End' && isOpen) {
        e.preventDefault();
        setActive(lastEnabled());
      } else if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        if (isOpen) { choose(active); } else { openMenu(); }
      } else if (e.key === 'Escape') {
        if (isOpen) { e.preventDefault(); close(true); }
      } else if (e.key === 'Tab') {
        if (isOpen) { close(); }
      } else if (e.key.length === 1) {
        if (!isOpen) { openMenu(); }
        typeahead(e.key);
      }
    });

    menu.addEventListener('pointerdown', function (e) { e.preventDefault(); });
    menu.addEventListener('pointermove', function (e) {
      var li = e.target.closest ? e.target.closest('.tt-sel-opt') : null;
      if (!li) { return; }
      var i = Array.prototype.indexOf.call(options(), li);
      if (i !== active) { setActive(i); }
    });
    menu.addEventListener('click', function (e) {
      var li = e.target.closest ? e.target.closest('.tt-sel-opt') : null;
      if (li) { choose(Array.prototype.indexOf.call(options(), li)); }
    });

    /* Programmatic .value = x (filters being cleared, a form opening on an
       existing row, the date picker clamping its hour) updates the label too. */
    try {
      var desc = Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, 'value');
      Object.defineProperty(sel, 'value', {
        configurable: true,
        get: function () { return desc.get.call(sel); },
        set: function (v) { desc.set.call(sel, v); sync(); }
      });
    } catch (err) {}

    sel.addEventListener('change', sync);

    if (sel.form) {
      sel.form.addEventListener('reset', function () { setTimeout(sync, 0); });
    }

    if (window.MutationObserver) {
      new MutationObserver(sync).observe(sel, {
        childList: true, subtree: true, characterData: true, attributes: true,
        attributeFilter: ['disabled', 'label', 'selected']
      });
    }

    var inst = {wrap: wrap, btn: btn, close: close, sync: sync};
    byEl.set(sel, inst);
    sync();
  }

  function all(root) {
    var scope = root || document;
    Array.prototype.forEach.call(scope.querySelectorAll('select'), enhance);
  }

  window.ttSelect = {
    enhance: enhance,
    refresh: function (target) {
      var el = typeof target === 'string' ? document.getElementById(target) : target;
      var inst = el && byEl.get(el);
      if (inst) { inst.sync(); }
    },
    refreshAll: function () { all(document); }
  };

  document.addEventListener('pointerdown', function (e) {
    if (openInst && !openInst.wrap.contains(e.target)) { openInst.close(); }
  }, true);

  window.addEventListener('resize', function () {
    if (openInst) { openInst.close(); }
  });

  all();
})();
