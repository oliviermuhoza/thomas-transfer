/* The home page photo cards reuse the pictures of the Cars page. */
document.querySelectorAll('img[data-car]').forEach(function (img) {
  var src = document.querySelector('#cars .cars .car-card:nth-child(' + img.getAttribute('data-car') + ') img');
  if (src) { img.src = src.src; }
});
