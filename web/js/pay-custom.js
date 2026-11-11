/* Pay by card: custom amount form. Opens Flutterwave (if a link is set) or WhatsApp with the details in a new tab. */
(function () {
  var form = document.getElementById('custom-pay-form');
  var status = document.getElementById('custom-status');
  var FLW_CUSTOM = '';
  form.addEventListener('submit', function (e) {
    e.preventDefault();
    var name = document.getElementById('cf-name').value.trim();
    var email = document.getElementById('cf-email').value.trim();
    var phone = document.getElementById('cf-phone').value.trim();
    var amount = Number(document.getElementById('cf-amount').value);
    var currency = document.getElementById('cf-currency').value;
    if (!(amount > 0)) { status.textContent = T('Please enter a valid amount.'); return; }
    var msg = 'Hello TOM Safaris! My name is ' + name + ' (' + (phone || email) + '). I would like to pay ' + amount + ' ' + currency + ' as a custom amount.';
    var url = FLW_CUSTOM || ('https://wa.me/250783689231?text=' + encodeURIComponent(msg));
    window.open(url, '_blank', 'noopener');
    status.textContent = FLW_CUSTOM ? '' : T('Opening WhatsApp — we will confirm your payment there.');
  });
})();
