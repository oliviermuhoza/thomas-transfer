/* Tour package filters on /tours: ALL / National Parks / Lakes & Leisure / Culture & Heritage */
(function () {
  var bar = document.querySelector('.tour-filters');
  if (!bar) return;

  var buttons = bar.querySelectorAll('[data-filter]');
  var grid = document.querySelector('#tours .cars');
  var cards = grid ? grid.querySelectorAll('[data-cat]') : [];

  function apply(filter) {
    Array.prototype.forEach.call(cards, function (card) {
      card.hidden = filter !== 'all' && card.getAttribute('data-cat') !== filter;
    });
    Array.prototype.forEach.call(buttons, function (btn) {
      var active = btn.getAttribute('data-filter') === filter;
      btn.classList.toggle('is-active', active);
      btn.setAttribute('aria-pressed', active ? 'true' : 'false');
    });
  }

  bar.addEventListener('click', function (event) {
    var btn = event.target.closest('[data-filter]');
    if (!btn) return;
    apply(btn.getAttribute('data-filter'));
  });

  apply('all');
})();
