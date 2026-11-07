/* Legacy hash bookmarks: /#transport -> /transport, /#available -> /account#available.
   Browsers never send the fragment to the server, so this must run client-side. */
(function () {
  var MAP = {
    '#home': '/',
    '#transport': '/transport',
    '#tours': '/tours',
    '#cars': '/cars',
    '#contact': '/contact',
    '#pay': '/pay',
    '#comment': '/comment',
    '#car-list': '/account#car-list',
    '#available': '/account#available',
    '#bookings': '/account#bookings',
    '#report': '/account#report',
    '#login': '/account#login',
    '#create-account': '/account#create-account',
    '#logout': '/account#logout'
  };
  var hash = location.hash;
  if (hash && MAP[hash]) { location.replace(MAP[hash]); }
})();
