/* Search box in the navbar: finds cars and pages. */
(function () {
  var form = document.getElementById('site-search'), input = document.getElementById('search-input'), list = document.getElementById('search-results');
  if (!form || !input || !list) { return; }
  var PAGES = [['Home', '/'], ['Cars', '/cars'], ['Transport', '/transport'], ['Tour packages', '/tours'],
               ['Car rental', '/account#available'], ['Pay online', '/pay'], ['List of cars', '/account#car-list'], ['Available cars', '/account#available'],
                ['Car bookings', '/account#bookings'], ['Contact', '/contact'], ['Comment', '/comment'], ['Login', '/login'], ['Logout', '/logout']];
  var LABEL = {available: 'Available', booked: 'Booked', maintenance: 'Maintenance'};
  var cars = [], items = [], active = -1;

  function el(tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) { e.className = cls; }
    if (text !== undefined && text !== null) { e.textContent = text; }
    return e;
  }
  function low(t) { return String(t || '').toLowerCase(); }
  async function loadCars() {
    try { var r = await fetch('/api/cars'); if (r.ok) { cars = await r.json(); } } catch (e) {}
  }
  function show(open) { list.hidden = !open; input.setAttribute('aria-expanded', open ? 'true' : 'false'); }
  function go(target) {
    var current = location.pathname + location.hash;
    if (target.charAt(0) === '#') { target = '/account' + target; }
    if (current === target) { if (window.ttPages) { window.ttPages.refresh(); } }
    else { location.assign(target); }
  }
  function choose(item) {
    input.value = ''; show(false); input.blur();
    if (item.car) {
      window.ttSelectedCar = item.car.id;
      try { sessionStorage.setItem('tt-selected-car', String(item.car.id)); } catch (e) {}
      go(item.car.status === 'available' ? '/account#available' : '/account#car-list');
    } else { go(item.href); }
  }
  function setActive(n) {
    items.forEach(function (it, i) { it.node.classList.toggle('on', i === n); it.node.setAttribute('aria-selected', i === n ? 'true' : 'false'); });
    active = n;
    if (n >= 0) { items[n].node.scrollIntoView({block: 'nearest'}); input.setAttribute('aria-activedescendant', items[n].node.id); }
    else { input.removeAttribute('aria-activedescendant'); }
  }
  function addItem(node, data) {
    node.id = 'sr-' + items.length; node.setAttribute('role', 'option'); node.setAttribute('aria-selected', 'false');
    data.node = node; items.push(data);
    node.addEventListener('click', function () { choose(data); });
    list.appendChild(node);
  }
  function build() {
    var q = low(input.value.trim());
    while (list.firstChild) { list.removeChild(list.firstChild); }
    items = []; active = -1;
    if (!q) { show(false); return; }
    var body = document.body, admin = body.classList.contains('is-admin'), logged = body.classList.contains('logged-in');

    var carHits = cars.filter(function (c) { return low(c.name + ' ' + c.type + ' ' + c.description + ' ' + T(c.type) + ' ' + T(c.description)).indexOf(q) > -1; }).slice(0, 6);
    var pages = PAGES.concat(admin ? [['Report', '/account#report']] : []).filter(function (p) {
      if (p[1] === '/login' && logged) { return false; }
      if (p[1] === '/logout' && !logged) { return false; }
      return low(p[0] + ' ' + T(p[0])).indexOf(q) > -1;
    });

    if (carHits.length) {
      var g = el('li', 'sr-group', T('Cars')); g.setAttribute('role', 'presentation'); list.appendChild(g);
      carHits.forEach(function (c) {
        var li = el('li', 'sr-item'), img = el('img', 'sr-thumb'), t = el('div', 'sr-text');
        img.src = c.image; img.alt = ''; li.appendChild(img);
        t.appendChild(el('b', '', c.name)); t.appendChild(el('span', '', T(c.type) + ' \u00B7 ' + T(LABEL[c.status] || c.status)));
        li.appendChild(t); addItem(li, {car: c});
      });
    }
    if (pages.length) {
      var g2 = el('li', 'sr-group', T('Pages')); g2.setAttribute('role', 'presentation'); list.appendChild(g2);
      pages.forEach(function (p) {
        var li = el('li', 'sr-item'), t = el('div', 'sr-text', T(p[0])); li.appendChild(t); addItem(li, {href: p[1]});
      });
    }
    if (!items.length) { var n = el('li', 'sr-none', T('No results found.')); n.setAttribute('role', 'presentation'); list.appendChild(n); }
    show(true);
  }

  input.addEventListener('focus', function () { loadCars().then(build); });
  input.addEventListener('input', build);
  input.addEventListener('keydown', function (e) {
    if (e.key === 'ArrowDown') { e.preventDefault(); if (items.length) { setActive((active + 1) % items.length); } }
    else if (e.key === 'ArrowUp') { e.preventDefault(); if (items.length) { setActive((active - 1 + items.length) % items.length); } }
    else if (e.key === 'Escape') { input.value = ''; show(false); }
  });
  form.addEventListener('submit', function (e) {
    e.preventDefault();
    if (items.length) { choose(items[active >= 0 ? active : 0]); }
  });
  document.addEventListener('click', function (e) { if (!form.contains(e.target)) { show(false); } });
})();
