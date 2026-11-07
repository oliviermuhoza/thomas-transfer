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
│   ├── schema.sql              # Tables for users, cars, bookings, comments, messages
│   ├── requirements.txt        # Runtime dependency (Flask)
│   ├── requirements-dev.txt    # Adds pytest
│   ├── data/                   # Created at runtime; holds the database
│   ├── templates/              # Jinja templates
│   │   ├── layout.html         # Shared head, header, footer, support dialog, scripts
│   │   ├── partials/
│   │   │   ├── header.html     # Logo, nav, search, menu, support, settings
│   │   │   ├── footer.html
│   │   │   └── support-dialog.html
│   │   ├── pages/              # home, transport, tours, cars, contact, pay, comment, account
│   │   └── errors/404.html
│   └── tests/
│       ├── conftest.py         # Keeps tests away from the development database
│       ├── test_api.py         # API, auth, booking and report tests
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
│   │   ├── search.js           # Navbar search (cars + pages, real URLs)
│   │   ├── faq.js              # FAQ open/close buttons
│   │   ├── comment.js          # Comment form -> POST /api/comment
│   │   ├── pay-fares.js        # Fixed-fare payment buttons
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

`/` and `/index.html` redirect to the template home page. Old bookmarks
(`/login`, `/register`, `/car-list`, `/available`, `/bookings`, `/report`,
`/logout`) are 302 redirects to the matching `/account#...` section, and
`legacy-hash.js` maps old `/#hash` links to the new routes on the client
(servers never see fragments).

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
| `users` | Accounts, password hashes, admin flag |
| `cars` | Fleet entries, status (`available`, `booked`, `maintenance`) |
| `bookings` | Customer bookings and their status |
| `comments` | Private feedback with a 1–5 rating |
| `messages` | Support and contact messages |

The car seed in `backend/db.py` mirrors the eight cards in the static fleet
markup in `backend/templates/pages/cars.html`. If you add or rename a vehicle
on the page, update the seed (or edit the `cars` table) so the "List of cars"
and "Available cars" pages match.

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
| `TT_ADMIN_EMAIL` | `admin@thomastransfer.com` | Seeded admin email |
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

- **Page routing** is real URLs rendered by Jinja; only the `/account` sections
  still use URL hashes (`.page` rules are scoped to `body[data-page="account"]`).
  `legacy-hash.js` redirects old `/#hash` bookmarks.
- **Script order matters.** `legacy-hash.js` must run first in the head,
  `i18n.js` defines the global `T()` translation helper, and `dashboard.js`
  defines `window.ttPages`. Keep the order in `backend/templates/layout.html`.
- **Translations** are keyed by the exact English text in the markup. If you
  edit visible copy, update the matching key in `web/js/i18n.js`.
- **Fonts:** `backend/templates/layout.html` loads Google Sans (400/500/700)
  from Google Fonts. `--font-sans` and `--font-heading` in `styles.css` use
  Google Sans with the generic `sans-serif` fallback.
- **Theme and language** are stored in `localStorage` under `tt-theme` and
  `tt-lang`.
- **Contact details** (`0783882549`, `wa.me/250783882549`) are repeated inline
  in the markup and a few scripts.
- **Payments** are not processed by the backend. The pay buttons in
  `js/pay-fares.js` and `js/pay-custom.js` open Flutterwave links when they are
  filled in, otherwise WhatsApp.

## API endpoints

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/csrf` | CSRF token for mutating API requests (`{csrf_token}`) |
| GET | `/api/me` | Current session user and CSRF token (`{user: null, csrf_token}` when signed out) |
| POST | `/api/login` | Sign in (returns `user`, `csrf_token`) |
| POST | `/api/logout` | Sign out (returns `ok`, `csrf_token`) |
| POST | `/api/register` | Create account (returns `user`, `csrf_token`) |
| GET | `/api/cars` | Fleet list; `?available=1` filters free cars |
| POST | `/api/cars/:id/status` | Set car status (admin) |
| GET | `/api/bookings` | Bookings (own, or all for admin) |
| POST | `/api/bookings` | Create a booking |
| POST | `/api/bookings/:id/status` | Change booking status |
| GET | `/api/report` | Admin summary |
| POST | `/api/comment` | Submit a private comment |
| POST | `/api/contact` | Contact / support message |

Mutating (`POST`) API requests require `Content-Type: application/json`, a valid
`X-CSRF-Token`, and a same-origin request (Origin/Referer checked as defense in depth).

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
