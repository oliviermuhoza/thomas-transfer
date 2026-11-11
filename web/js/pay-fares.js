/* Pay by card: paste your Flutterwave payment links here. Leave a link empty and the button opens WhatsApp in a new tab instead. */
(function () {
  var FLW = {airport: '', allday: '', akagera: '', volcanoes: '', nyungwe: '', gisenyi: '', palace: '', custom: ''};
  var FARE = {airport: 'Kigali Airport ⇄ City (25,000 RWF, fixed fare)', allday: 'Kigali All-Day Service (150,000 RWF, until 21:00)',
              akagera: 'Akagera National Park ($315 per person)', volcanoes: 'Volcanoes National Park ($270 per person)',
              nyungwe: 'Nyungwe National Park ($270 per person)', gisenyi: 'Gisenyi — Lake Kivu ($225 per person)',
              palace: "King's Palace Museum ($90 per person)", custom: 'a custom amount'};
  var status = document.getElementById('fare-status');
  function waUrl(svc) { return 'https://wa.me/250783689231?text=' + encodeURIComponent("Hello Thomas Transfer! I'd like to book and pay for " + (FARE[svc] || 'a service') + '.'); }
  document.querySelectorAll('.fare-btn').forEach(function (btn) {
    btn.addEventListener('click', function () {
      var svc = btn.getAttribute('data-svc');
      var url = FLW[svc] || waUrl(svc);
      window.open(url, '_blank', 'noopener');
      status.textContent = FLW[svc] ? '' : T('Opening WhatsApp — we will confirm your payment there.');
    });
  });
})();
