/* Pay by card: fares come from the database (see /admin#fares). Buttons carry
   their name, price and (optional) Flutterwave link as data attributes. With no
   link set the button opens WhatsApp in a new tab with the current fare text. */
(function () {
  var status = document.getElementById('fare-status');

  function waText(name, price, note) {
    var msg = "Hello Thomas Transfer! I'd like to book and pay for " + name + ' (' + price;
    if (note) { msg += ', ' + note.charAt(0).toLowerCase() + note.slice(1); }
    return msg + ').';
  }

  document.querySelectorAll('.fare-btn[data-svc]').forEach(function (btn) {
    btn.addEventListener('click', function () {
      var link = (btn.getAttribute('data-flw') || '').trim();
      var url = link || ('https://wa.me/250784659514?text=' + encodeURIComponent(
        waText(btn.getAttribute('data-name') || 'a service',
               btn.getAttribute('data-price') || '',
               btn.getAttribute('data-note') || '')));
      window.open(url, '_blank', 'noopener');
      status.textContent = link ? '' : T('Opening WhatsApp — we will confirm your payment there.');
    });
  });
})();
