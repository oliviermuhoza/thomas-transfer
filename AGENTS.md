# Repository guide

Marketing/booking site: static front end in `web/`, Flask + SQLite backend in `backend/`. No JS build step, no Node, no ORM, no migrations, no lint/typecheck/CI config.

## Layout and entrypoints

- `backend/app.py` — `create_app()` plus every API and static route; module-level `app` is the WSGI target (`backend.app:app`).
- `backend/db.py` — stdlib `sqlite3` access, schema execution, `SEED_CARS`, admin bootstrap.
- `backend/schema.sql` — tables. Applied at every startup; existing tables are never altered.
- `web/` — everything the browser gets. Only `/`, `web/css`, `web/js` and `web/assets` are exposed.
- `backend/tests/` — pytest suite. `conftest.py` redirects `TT_DATABASE` before `backend.app` is imported.
- `archive/` — old reference HTML; not served and not part of the live site.

## Commands (PowerShell, from the repo root)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r backend/requirements.txt
python -m backend.app                          # http://127.0.0.1:5000
flask --app backend.app run
python -m pytest -q                            # full suite
python -m pytest backend/tests/test_api.py::test_booking_flow -q
```

Prefer `python -m backend.app` over `python backend/app.py`; the latter only works through a fallback import shim.

## Data and startup gotchas

- `backend/data/` holds the SQLite file and generated session secret. It is gitignored, created on first start, and must not be deleted or destructively migrated without user approval.
- `schema.sql` uses `CREATE TABLE IF NOT EXISTS`, so editing it does not migrate an existing database. Schema changes need explicit migration logic or a user-approved reset.
- Seeding is first-run only: cars when `cars` is empty, admin when no `is_admin=1` user exists. The first admin password comes from `TT_ADMIN_PASSWORD`; otherwise a random one is printed once to stderr.
- `SEED_CARS` in `backend/db.py` must stay in sync with the eight static car cards in `web/index.html` (same order, names, types, descriptions). The home cards referencing ids 10 and 12 are stale and have no seeded car or photo.
- Importing `backend.app` opens and seeds a database. In tests or scripts, pass an explicit temp `database`, `secret_key` and `admin_password` to `create_app()` instead of touching the dev DB.
- Keep SQL parameterized and use stdlib `sqlite3`; no ORM unless the user asks.

## Front-end gotchas

- One file, `web/index.html`; navigation is URL hashes plus CSS `:target`. There is no JS router, so no SPA fallback route is needed.
- Script order in `index.html` is load-bearing: `i18n.js` defines the global `T()`, `dashboard.js` defines `window.ttPages`.
- Visible copy is translated by exact English key in `web/js/i18n.js`; change text in HTML/JS only together with its key. Server error strings fall back to English.
- Google Sans is loaded from Google Fonts in `web/index.html`; `--font-sans` and `--font-heading` in `styles.css` use it with only the generic `sans-serif` fallback.
- Auth/UI state is CSS classes on `<body>` (`logged-in`, `is-admin`) set from `/api/me`; admin-only markup relies on those classes.
- Payments are outbound links in `web/js/pay-fares.js` and `web/js/pay-custom.js`; the backend never handles card data.

## API contract (the front end depends on exact shapes)

- JSON only, same origin, session cookie. Do not add CORS or token auth without changing `web/js/auth.js`.
- `GET /api/me` must always return HTTP 200 with `{ "user": null }` or a user object; other errors use `{ "error": "..." }` with a 4xx/5xx status.
- Status vocabularies are fixed: cars `available|booked|maintenance`; bookings `pending|confirmed|completed|cancelled`. Creating a booking marks the car `booked`; cancel/complete returns it to `available`.
- `GET /api/cars?available=1` filters; `GET /api/bookings` returns own rows or all for an admin; `/api/report` is admin-only.
- `trip_at` is a local ISO string; the UI renders it by replacing `T` with a space.

## Verification

- Backend changes: `python -m pytest -q`. Tests use temporary databases and do not touch `backend/data/`.
- Front-end changes: start the server and load the pages; there is no build, lint or typecheck step to run.
- `README.md` is the source for the full endpoint table, env vars and deployment; keep it in sync with behavior changes.
