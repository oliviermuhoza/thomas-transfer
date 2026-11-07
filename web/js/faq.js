/* FAQ: the X button hides the answer; pressing it again shows it. */
(function () {
  document.querySelectorAll('.faq-toggle').forEach(function (btn) {
    btn.addEventListener('click', function () {
      var closed = btn.closest('.faq-card').classList.toggle('closed');
      btn.setAttribute('aria-expanded', String(!closed));
    });
  });
})();
