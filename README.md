# Thomas Transfer

Marketing and booking website for Thomas Transfer, a transport and car-rental
business in Kigali, Rwanda.

The front end is plain HTML, CSS and JavaScript with no build step. It lives in
`web/` (CSS/JS/assets only) and is served by a small Flask backend that also
provides the JSON API under `/api/*` and stores accounts, cars, bookings,
comments and messages in SQLite.

## Structure

```
.
├── backend/                    # All server-side code lives here
│   ├── __init__.py
│   ├── app.py                  # Flask app: API routes + static file serving
│   ├── pages.py                # Page blueprint: marketing pages + /account + redirects
│   ├── db.py                   # SQLite connection, schema setup, seed data
│   ├── schema.sql              # Tables for users, cars, bookings, comments, messages, fares
│   ├── requirements.txt        # Runtime dependency (Flask)
│   ├── requirements-dev.txt    # Adds pytest
│   ├── data/                   # Created at runtime; holds the database
│   ├── templates/              # Jinja templates
│   │   ├── layout.html         # Shared head, header, footer, support dialog, scripts
│   │   ├── partials/
│   │   │   ├── header.html     # Logo, nav, search, menu, support, settings
│   │   │   ├── footer.html
│   │   │   └── support-dialog.html
│   │   ├── pages/              # home, transport, tours, cars, contact, pay, comment, account, admin
│   │   └── errors/404.html
│   └── tests/
│       ├── conftest.py         # Keeps tests away from the development database
│       ├── test_api.py         # API, auth, booking and report tests
│       ├── test_admin_api.py   # Admin portal API, migrations and /admin page guards
│       └── test_pages.py       # Page routes, redirects, nav state, 404
├── web/                        # Static assets served by Flask
│   ├── css/
│   │   └── styles.css          # Theme tokens, components, responsive rules
│   ├── js/
│   │   ├── theme-init.js       # Applies the saved theme before paint (head)
│   │   ├── legacy-hash.js      # Old #hash bookmarks -> real routes (client-side)
│   │   ├── i18n.js             # EN/RW dictionary, language + theme toggle
│   │   ├── session.js          # /api/me, body classes, logout, selected car
│   │   ├── dashboard.js        # Cars, available cars, bookings, report (account only)
│   │   ├── date-picker.js      # Shared date/time picker used by the booking form
│   │   ├── admin.js            # /admin portal: all operations views (admin only)
│   │   ├── search.js           # Navbar search (cars + pages, real URLs)
│   │   ├── select.js           # Wraps every <select> in a themed custom listbox
│   │   ├── faq.js              # FAQ open/close buttons
│   │   ├── comment.js          # Comment form -> POST /api/comment
│   │   ├── pay-fares.js        # Fixed-fare payment buttons (fares come from the DB)
│   │   ├── pay-custom.js       # Custom-amount payment form
│   │   ├── auth-forms.js       # Login + register forms (account only)
│   │   └── support.js          # Support message dialog -> POST /api/contact
│   └── assets/
│       ├── images/             # Page, fleet and brand images
│       │   ├── cars/           # Fleet photos (01-08)
│       │   └── logo.png
│       └── video/
│           └── kigali.mp4      # Home hero video
└── archive/
    ├── thomas-transfer-v1.html           # Original single-file version
    ├── thomas-transfer-v1.mangled.bak.html # Older damaged backup
    └── thomas-transfer-spa.html          # Previous hash-routed single page
```

The `archive/` files are reference copies only. They are not linked from the
site, are not served by Flask, and their asset paths still point at the old flat
layout.

## Pages

Marketing pages are Jinja templates with real URLs:

| URL | Template |
| --- | --- |
| `/` | `pages/home.html` |
| `/transport` | `pages/transport.html` |
| `/tours` | `pages/tours.html` |
| `/cars` | `pages/cars.html` |
| `/contact` | `pages/contact.html` |
| `/pay` | `pages/pay.html` |
| `/comment` | `pages/comment.html` |
| `/account` | `pages/account.html` (hash sections: `#car-list`, `#available`, `#bookings`, `#report`, `#login`, `#create-account`, `#logout`) |
| `/admin` | `pages/admin.html` (real section routes: `/admin/overview`, `/admin/bookings`, `/admin/fleet`, `/admin/accounts`, `/admin/messages`, `/admin/comments`, `/admin/fares`; unknown views 404, non-admins are redirected) |

`/` and `/index.html` redirect to the template home page. Old bookmarks
(`/login`, `/register`, `/car-list`, `/available`, `/bookings`, `/report`,
`/logout`) are 302 redirects to the matching `/account#...` section, and
`legacy-hash.js` maps old `/#hash` links to the new routes on the client
(servers never see fragments). Old admin bookmarks like `/admin#fleet`
are rewritten to `/admin/fleet` the same way.

The nav marks the current page with `aria-current="page"` (set server-side),
not CSS `:target`.

## Running locally

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r backend/requirements.txt
python -m backend.app
```

Then open <http://127.0.0.1:5000/>.

On the first start the backend creates `backend/data/thomas.db`, adds the eight
cars from the fleet page and creates one admin account. Set the admin
credentials before that first start if you want to choose them:

```powershell
$env:TT_ADMIN_EMAIL = 'you@example.com'
$env:TT_ADMIN_PASSWORD = 'a-long-password'
python -m backend.app
```

If `TT_ADMIN_PASSWORD` is not set, a random password is generated and printed
to the terminal once. You can also start with Flask's CLI:

```powershell
flask --app backend.app run
```

## Database

SQLite, using Python's built-in `sqlite3` module (no ORM). The default file is
`backend/data/thomas.db`; the `backend/data/` directory is ignored by git. The
schema in `backend/schema.sql` is applied automatically on startup and is safe
to run repeatedly.

| Table | Holds |
| --- | --- |
| `users` | Accounts, password hashes, admin flag, active flag |
| `cars` | Fleet entries: capacity, display `price`/`week`/`specs`, status (`available`, `booked`, `maintenance`) |
| `bookings` | Customer bookings, their status and recorded payments |
| `comments` | Private feedback with a 1–5 rating |
| `messages` | Support and contact messages with a `handled` flag |
| `fares` | Standard /pay amounts, optional Flutterwave link, active flag |

`CREATE TABLE IF NOT EXISTS` never alters an existing table, so additive column
changes are applied by `_migrate()` in `backend/db.py` at startup:
`messages.handled`, `cars.capacity/price/week/specs` (backfilled from the seed),
`users.active`, and `bookings.paid_amount/paid_method/paid_at`.

The car seed in `backend/db.py` inserts the initial fleet on the first run
only. Every fleet page (`/cars`, "List of cars", "Available cars", booking
validation, prices) reads the `cars` table, so the fleet is maintained from the
admin portal — no code deploy needed for price changes. The `Popular vehicles`
cards in `backend/templates/pages/home.html` link to fixed car ids with their
own images, so keep those ids in mind when removing cars.

Booking rules enforced by the API:

- A booking starts as `pending` and puts the car in `booked`.
- Only an admin can move it to `confirmed` or `completed`; a customer can only
  cancel their own pending or confirmed booking.
- Cancelling or completing a booking returns the car to `available`.
- A car in `maintenance` or already `booked` cannot be booked.
- Deleting `backend/data/thomas.db` resets everything; the next start reseeds
  the cars and creates a new admin account.

## Configuration

Environment variables:

| Variable | Default | Purpose |
| --- | --- | --- |
| `TT_ENV` | unset | Set to `production` to enable production checks (HTTPS cookie required, `SECRET_KEY` required, no generated admin password printed). |
| `SECRET_KEY` | generated in `backend/data/secret_key` (non-production) | Signs session cookies. **Required in production.** |
| `TT_DATABASE` | `backend/data/thomas.db` | SQLite file path |
| `TT_ADMIN_EMAIL` | `tomsafaris@gmail.com` | Seeded admin email |
| `TT_ADMIN_PASSWORD` | generated/printed once in non-production bootstrap | Seeded admin password. **Required before first start in production if no admin exists.** |
| `TT_HOST` | `127.0.0.1` | Bind address used by `python -m backend.app` |
| `TT_PORT` | `5000` | Port used by `python -m backend.app` |
| `TT_DEBUG` | off | Set to `1` for Flask debug mode |
| `TT_COOKIE_SECURE` | off | Set to `1` when served over HTTPS. **Required in production.** |
| `TT_TRUST_PROXY_HEADERS` | off | Set to `1` only behind a trusted reverse proxy; enables Werkzeug `ProxyFix`. |
| `TT_TRUSTED_PROXY_HOPS` | `1` | Number of trusted proxy hops when `TT_TRUST_PROXY_HEADERS=1`. |
| `TT_RATE_LIMIT_BACKEND` | `memory` | `memory` (per-process) or `redis` (shared). |
| `TT_REDIS_URL` | unset | Required when `TT_RATE_LIMIT_BACKEND=redis` (needs optional `redis` package). |

Sessions are signed cookies (`HttpOnly`, `SameSite=Lax`), passwords are stored
with Werkzeug's PBKDF2 hash, and every query uses parameters. Mutating `/api/*`
requests require `Content-Type: application/json` and a valid `X-CSRF-Token`
(from `GET /api/csrf` or the `csrf_token` field in `GET /api/me` / auth responses).
The API is intended to be served from the same origin as the pages.

## Testing

```powershell
pip install -r backend/requirements-dev.txt
python -m pytest -q
```

The tests use a temporary database and cover registration/login, permissions,
the booking lifecycle, car status rules, comments, contact messages, the
admin report, page routes, redirects, nav state and 404 handling.

## Runtime notes

- **Page routing** is real URLs rendered by Jinja. `/admin` sections are real
  routes (`/admin/fleet` etc.) and the active one is server-rendered; only
  `/account` still uses URL hash sections (`.page` hiding rules are scoped to
  `body[data-page="account"]`, admin `.admin-view` hiding is class-based).
  `legacy-hash.js` redirects old `/#hash` bookmarks and rewrites old
  `/admin#section` hashes to `/admin/section`.
- **Script order matters.** `legacy-hash.js` must run first in the head,
  `i18n.js` defines the global `T()` translation helper, and `dashboard.js`
  (account) or `admin.js` (portal) defines `window.ttPages`. Keep the order in
  `backend/templates/layout.html`.
- **Translations** are keyed by the exact English text in the markup. If you
  edit visible copy, update the matching key in `web/js/i18n.js`.
- **Fonts:** `backend/templates/layout.html` loads Google Sans (400/500/700)
  from Google Fonts. `--font-sans` and `--font-heading` in `styles.css` use
  Google Sans with the generic `sans-serif` fallback.
- **Theme and language** are stored in `localStorage` under `tt-theme` and
  `tt-lang`.
- **Contact details** (`0788652120`, `wa.me/250788652120`) are repeated inline
  in the markup and a few scripts.
- **Payments** are not processed by the backend. The fare list on `/pay` comes
  from the `fares` table (managed in `/admin/fares`). Each fare can carry a
  Flutterwave payment link; the button opens it when set, otherwise it opens
  WhatsApp with the current fare text. `js/pay-custom.js` behaves the same with
  one globally configured link for custom amounts.

## API endpoints

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/csrf` | CSRF token for mutating API requests (`{csrf_token}`) |
| GET | `/api/me` | Current session user and CSRF token (`{user: null, csrf_token}` when signed out) |
| POST | `/api/login` | Sign in (returns `user`, `csrf_token`) |
| POST | `/api/logout` | Sign out (returns `ok`, `csrf_token`) |
| POST | `/api/register` | Create account (returns `user`, `csrf_token`) |
| GET | `/api/cars` | Fleet list from the `cars` table; `?available=1` filters free cars. Rows include `capacity` and display fields `specs` (list), `price`, `week` |
| POST | `/api/cars/:id/status` | Set car status (admin) |
| POST | `/api/admin/cars` | Create a car (admin) |
| PATCH | `/api/admin/cars/:id` | Update car fields (admin) |
| DELETE | `/api/admin/cars/:id` | Delete a car without bookings (admin) |
| GET | `/api/admin/fares` | All fares, including hidden ones (admin) |
| POST | `/api/admin/fares` | Create a fare (admin) |
| PATCH | `/api/admin/fares/:id` | Update or hide a fare (admin) |
| DELETE | `/api/admin/fares/:id` | Delete a fare (admin) |
| GET | `/api/bookings` | Bookings (own, or all for admin) |
| POST | `/api/bookings` | Create a booking; admins may pass `user_id` to book for a customer |
| POST | `/api/bookings/:id/status` | Change booking status |
| PATCH | `/api/bookings/:id` | Edit a booking (admin) |
| POST | `/api/admin/bookings/:id/payment` | Record or clear a payment (admin) |
| GET | `/api/report` | Admin summary |
| GET | `/api/admin/users` | Account list without password hashes (admin) |
| POST | `/api/admin/users` | Create an account, optionally with admin access (admin) |
| DELETE | `/api/admin/users/:id` | Delete an account without booking history (admin) |
| POST | `/api/admin/users/:id/admin` | Grant or revoke admin access (admin) |
| POST | `/api/admin/users/:id/active` | Deactivate or reactivate an account (admin) |
| POST | `/api/admin/users/:id/password` | Set an account's new password (admin) |
| GET | `/api/admin/messages` | Contact messages with `handled` flag (admin) |
| POST | `/api/admin/messages/:id/handled` | Mark a message handled or reopened (admin) |
| DELETE | `/api/admin/messages/:id` | Delete a message (admin) |
| GET | `/api/admin/comments` | All comments and ratings (admin) |
| DELETE | `/api/admin/comments/:id` | Delete a comment (admin) |
| GET | `/api/admin/export/bookings.csv` | Download all bookings as CSV (admin) |
| GET | `/api/admin/export/messages.csv` | Download contact messages as CSV (admin) |
| POST | `/api/comment` | Submit a private comment |
| POST | `/api/contact` | Contact / support message |

Mutating (`POST`, `PUT`, `PATCH`, `DELETE`) API requests require
`Content-Type: application/json`, a valid `X-CSRF-Token`, and a same-origin
request (Origin/Referer checked as defense in depth).

## Deploying

Point any WSGI server at `backend.app:app`. For example, on Windows with
Waitress:

```powershell
pip install waitress
waitress-serve --listen=0.0.0.0:8000 backend.app:app
```

On Linux, `gunicorn -w 2 -b 0.0.0.0:8000 backend.app:app` works the same way.

For production, serve behind HTTPS and set:
`TT_ENV=production`, `SECRET_KEY`, `TT_COOKIE_SECURE=1`, and `TT_ADMIN_PASSWORD`
before the first boot if no admin exists. If running behind a trusted reverse
proxy, set `TT_TRUST_PROXY_HEADERS=1` (and `TT_TRUSTED_PROXY_HOPS` as needed).
In-memory rate limits are per-process; use `TT_RATE_LIMIT_BACKEND=redis` with
`TT_REDIS_URL` (optional `redis` package) or enforce rate limiting at the
edge/WAF. Keep `backend/data/` on a persistent disk (or set `TT_DATABASE` to a
writable path outside the deployment folder) and back up the SQLite file regularly.

### Vercel

Vercel detects Flask from the root `requirements.txt` and routes every request
to the Flask app. Depending on the entrypoint it resolves (`app.py` at the root,
or `backend/app.py`), `backend/app.py` imports its siblings either as a package
(`from .db`) or as top-level modules (`from db`). `vercel.json` intentionally
has no rewrites, so `api/index.py` (legacy file-based function) is no longer
used.

The deployment filesystem is read-only except for `/tmp`. The backend picks the
first writable database location at startup (`TT_DATABASE`, then
`backend/data/`, then `/tmp/thomas-transfer-data/`), so a bad `TT_DATABASE`
value no longer crashes the function. SQLite data on Vercel is ephemeral and is
recreated on cold starts; use a managed database for persistence.

Recommended Vercel environment variables: `SECRET_KEY` (stable sessions),
`TT_ADMIN_PASSWORD` (enables admin login), and optionally `TT_ADMIN_EMAIL`.
`TT_ENV=production` works on Vercel without extra settings: secure cookies are
enabled automatically because Vercel serves HTTPS, and the app boots even when
`TT_ADMIN_PASSWORD` is missing (the admin account is simply not created).
