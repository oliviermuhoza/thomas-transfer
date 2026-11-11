/* Shared empty-state block for lists that can have no rows.
   Loading and error messages stay in the .status paragraphs; this only fills
   the space where a table or a grid of cards would be. */
(function () {
  var STROKE = 'fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"';
  var ICONS = {
    tray: '<svg viewBox="0 0 24 24" aria-hidden="true"><path ' + STROKE + ' d="M4.2 13.6 6 7.3a2.3 2.3 0 0 1 2.2-1.7h7.6A2.3 2.3 0 0 1 18 7.3l1.8 6.3"/><path ' + STROKE + ' d="M4.2 13.6h4.1l1.3 2.3h4.8l1.3-2.3h4.1v4.1a1.8 1.8 0 0 1-1.8 1.8H6a1.8 1.8 0 0 1-1.8-1.8z"/></svg>',
    users: '<svg viewBox="0 0 24 24" aria-hidden="true"><circle ' + STROKE + ' cx="9" cy="8.4" r="3.3"/><path ' + STROKE + ' d="M3.6 19.2c.5-3 2.8-4.7 5.4-4.7s4.9 1.7 5.4 4.7"/><path ' + STROKE + ' d="M15.6 6.1a3.1 3.1 0 0 1 0 5.9M17.1 14.9c2 .4 3.2 1.9 3.5 4.3"/></svg>',
    car: '<svg viewBox="0 0 24 24" aria-hidden="true"><path ' + STROKE + ' d="M3.8 14.8v-2.3l1.9-4.2A2.2 2.2 0 0 1 7.7 7h8.6a2.2 2.2 0 0 1 2 1.3l1.9 4.2v2.3"/><path ' + STROKE + ' d="M3.8 14.8h16.4"/><circle ' + STROKE + ' cx="7.4" cy="16" r="1.7"/><circle ' + STROKE + ' cx="16.6" cy="16" r="1.7"/></svg>',
    message: '<svg viewBox="0 0 24 24" aria-hidden="true"><rect ' + STROKE + ' x="3.5" y="5.5" width="17" height="13" rx="2.2"/><path ' + STROKE + ' d="m4.6 7.2 7.4 5.4 7.4-5.4"/></svg>',
    star: '<svg viewBox="0 0 24 24" aria-hidden="true"><path ' + STROKE + ' d="m12 4.4 2.4 4.9 5.3.8-3.8 3.7.9 5.3-4.8-2.5-4.8 2.5.9-5.3-3.8-3.7 5.3-.8z"/></svg>',
    tag: '<svg viewBox="0 0 24 24" aria-hidden="true"><path ' + STROKE + ' d="M4 12.1V5.6A1.6 1.6 0 0 1 5.6 4h6.5l7.9 7.9-8.1 8.1z"/><circle ' + STROKE + ' cx="8.2" cy="7.8" r="1.3"/></svg>',
    clock: '<svg viewBox="0 0 24 24" aria-hidden="true"><circle ' + STROKE + ' cx="12" cy="12" r="8.2"/><path ' + STROKE + ' d="M12 7.4V12l3.1 1.9"/></svg>'
  };

  function el(tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) { e.className = cls; }
    if (text !== undefined && text !== null) { e.textContent = text; }
    return e;
  }
  function t(text) { return window.T ? window.T(text) : text; }
  function dropBlocks(container) {
    var old = container.querySelectorAll('.empty-state');
    for (var i = 0; i < old.length; i++) { old[i].remove(); }
  }

  function block(opts) {
    var wrap = el('div', 'empty-state' + (opts.size ? ' empty-state--' + opts.size : ''));
    if (opts.icon && ICONS[opts.icon]) { wrap.insertAdjacentHTML('beforeend', ICONS[opts.icon]); }
    wrap.appendChild(el('p', 'empty-state-title', t(opts.title)));
    if (opts.text) { wrap.appendChild(el('p', 'empty-state-text', t(opts.text))); }
    if (opts.action) {
      var row = el('div', 'empty-state-actions');
      var b = el('button', 'mini ' + (opts.action.tone || 'ghost'), t(opts.action.label));
      b.type = 'button';
      b.addEventListener('click', opts.action.run);
      row.appendChild(b);
      wrap.appendChild(row);
    }
    return wrap;
  }

  /* Replace the table (or the previous empty block) inside container. */
  function emptyState(container, opts) {
    if (!container) { return; }
    var table = container.querySelector('table');
    if (table) {
      while (table.firstChild) { table.removeChild(table.firstChild); }
      table.hidden = true;
    }
    dropBlocks(container);
    container.appendChild(block(opts));
  }
  /* Restore the container before the next render builds real rows. */
  emptyState.clear = function (container) {
    if (!container) { return; }
    dropBlocks(container);
    var table = container.querySelector('table');
    if (table) { table.hidden = false; }
  };

  window.ttEmptyState = emptyState;
})();
