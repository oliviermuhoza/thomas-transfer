/* Legacy hash bookmarks: /#transport -> /transport, /#available -> /account#available.
   Browsers never send the fragment to the server, so this must run client-side. */
(function () {
  var hash = location.hash;
  if (!hash) { return; }
  var name = hash.slice(1);
  // Old admin bookmarks (/admin#fleet) point at a section of the hash-routed
  // portal, which now lives at a real route (/admin/fleet). Only the seven
  // known views are rewritten; anything else on /admin stays untouched.
  if (location.pathname === '/admin') {
    var VIEWS = ['overview', 'bookings', 'fleet', 'accounts',
                 'messages', 'comments', 'fares'];
    if (VIEWS.indexOf(name) !== -1) { location.replace('/admin/' + name); }
    return;
  }
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
  if (MAP[hash]) { location.replace(MAP[hash]); }
})();
