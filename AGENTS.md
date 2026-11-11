# Repository guide

Marketing/booking site: Jinja templates in `backend/templates/`, static
assets in `web/`, Flask + SQLite backend in `backend/`. No JS build step, no
Node, no ORM, no migrations, no lint/typecheck/CI config.

## Layout and entrypoints

- `backend/app.py` — `create_app()` plus every API route; module-level `app` is the WSGI target (`backend.app:app`).
- `backend/pages.py` — page blueprint: `/`, `/transport`, `/tours`, `/cars`, `/contact`, `/pay`, `/comment`, `/account`, `/admin` and `/admin/<view>` (whitelisted in `ADMIN_VIEWS`), plus 302 aliases (`/login` etc.).
- `backend/templates/layout.html` — shared head, header, footer, support dialog, shared scripts; per-page `<title>`/meta via `PAGE_META` in `pages.py`.
- `backend/db.py` — stdlib `sqlite3` access, schema execution, additive `_migrate()`, `SEED_CARS`/`SEED_FARES`, admin bootstrap.
- `backend/schema.sql` — tables. Applied at every startup; missing tables are created, and additive column changes are applied by `_migrate()` in `backend/db.py` (existing columns are never altered).
- `web/` — static source only (`css/`, `js/`, `assets/`); served at `/css/...`, `/js/...`, `/assets/...`. `web/index.html` is gone (now `archive/thomas-transfer-spa.html`).
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
- `SEED_CARS` and `SEED_FARES` in `backend/db.py` only populate an empty database on first run; after that the database is the source of truth. `/cars`, `/api/cars`, booking capacity checks and `/pay` fares all read from the DB; fleet rows are editable in `/admin/fleet` and standard fares in `/admin/fares` (price text, `week`, `specs`, `capacity` are columns now — there is no `CAR_DISPLAY` dict). The `Popular vehicles` cards in `pages/home.html` still hardcode images and link to fixed fleet ids (1,3,4,5,6,7), so keep those ids when deleting cars.
- Importing `backend.app` opens and seeds a database. In tests or scripts, pass an explicit temp `database`, `secret_key`, `admin_password` and `admin_email` to `create_app()` instead of touching the dev DB. The test suite sets `TT_NO_ENV_FILE=1` so a developer's local `.env` cannot change test behaviour.
- `.env` (gitignored, see `.env.example`) is loaded by `load_env_file()` in `backend/app.py` before `create_app()` runs; existing environment variables win over the file. Keep secrets out of `.env.example`.
- Keep SQL parameterized and use stdlib `sqlite3`; no ORM unless the user asks.

## Front-end gotchas

- Marketing pages are Jinja (`backend/templates/pages/*.html`) with real URLs; only `/account` is a hash-routed shell. `/admin` sections are real routes (`/admin`, `/admin/fleet`, ...) whitelisted in `ADMIN_VIEWS` in `pages.py`, with the active nav link and visible section server-rendered (admin section `.admin-view` hiding is class-based in `styles.css`, not `:target`). `.page` hiding/default rules are scoped to `body[data-page="account"]`; nav active state is server-rendered `aria-current="page"`.
- `web/js/legacy-hash.js` maps old `/#hash` bookmarks to new routes client-side (servers never receive fragments); `/index.html` redirects to `/`.
- Script order in `layout.html` is load-bearing: `legacy-hash.js` in `<head>`, then `i18n.js` defines the global `T()`, and `dashboard.js` (account only) or `admin.js` (portal only) defines `window.ttPages`. `session.js` runs on every page; `dashboard.js`/`admin.js`/`auth-forms.js`/`pay-*`/`comment.js`/`faq.js` are per-page blocks.
- `web/js/select.js` upgrades every native `<select>` into a button + themed `role="listbox"` menu. The `<select>` stays in the DOM (clipped, `aria-hidden`, `tabindex="-1"`) so `.value`, `change` events, form submission and option lists rebuilt by other scripts keep working; the trigger also syncs when options are edited (i18n) or `.value` is set programmatically. Add `data-native` to opt a select out.
- The `/admin` sidebar (`.admin-side` in `pages/admin.html`) has three zones: one-line brand, icon nav (count pills filled by `refreshNavCounts()` in `admin.js`), and the person footer. The rail is `position:fixed` at `100vh` — the shell reserves its 240px — so it never scrolls and only the content column moves; under 700px viewport height the rail tightens its spacing instead of scrolling. Under 900px wide it becomes a 3-row strip: brand, one scrolling chip row (the active chip is centred by `centerActiveNav()`), action row. Keep the marketing navbar rules scoped to `.bar nav` in `styles.css` — a bare `nav` selector leaks into the portal and overrides its nav direction/order.
- Portal/account components (`.pulse`, `.panel`, `.panel-list`, `.chart-*`, `.mini`, `.row-actions` in `styles.css`): each admin list view is one `<section class="panel panel-list">` that wraps the filter toolbar, the optional "New …" form and `.table-wrap`, so rows share one surface with hairline dividers. One filled control per view (`.mini.primary`); row actions are text-style `.mini` buttons or the `rowMenu()` control (bookings: status action inline, `Edit`/`Record payment` inside "Manage"). `#admin-bookings{min-width:1100px}` keeps its 9 columns at 70px rows and makes the panel scroll below that.
- The overview pulse strip and chart are built in `admin.js` (`pulseCell`, `drawTrend`, `setInsight`) from `/api/report`; the chart measures `clientWidth` and redraws on a debounced resize. `.tiles`/`.tile` now only remain for `#report-tiles` on `/account` (`tile()` in `dashboard.js`).
- `#bookings`, `#report` and `#car-list` exist both as `/account` sections and as `/admin/<view>` section ids, so account layout rules in `styles.css` are scoped to `body[data-page="account"]`. Adding a bare `#bookings …` rule silently restyles the admin table.
- `/account` fleet cards reuse `.car-card`/`.reserve-btn` but are restyled under `.booking-fleet` only (neutral hairline cards; lime marks the selected card and its pressed pill). The booking panel is a numbered rail (`.booking-steps-list`, one `li.current`).
- `session.js` is the global session script (`/api/me`, `logged-in`/`is-admin` body classes, logout, `sessionStorage` selected-car persistence); `auth-forms.js` only wires the login/register forms on `/account` and must not run elsewhere.
- Visible copy is translated by exact English key in `web/js/i18n.js`; change text in templates/JS only together with its key. Server error strings fall back to English.
- Google Sans is loaded from Google Fonts in `backend/templates/layout.html`; `--font-sans` and `--font-heading` in `styles.css` use it with only the generic `sans-serif` fallback.
- Auth/UI state is CSS classes on `<body>` (`logged-in`, `is-admin`) set from `/api/me`; admin-only markup relies on those classes. The layout also server-renders them from the session.
- Payments are outbound links: the `/pay` fare cards render from the `fares` table and each row can store its own Flutterwave link (managed in `/admin/fares`); `web/js/pay-custom.js` opens the amount the visitor entered. The backend never handles card data.

## API contract (the front end depends on exact shapes)

- JSON only, same origin, session cookie. Do not add CORS or token auth without changing `web/js/session.js`.
- `GET /api/me` must always return HTTP 200 with `{ "user": null }` or a user object; other errors use `{ "error": "..." }` with a 4xx/5xx status.
- Status vocabularies are fixed: cars `available|booked|maintenance`; bookings `pending|confirmed|completed|cancelled`. Creating a booking marks the car `booked`; cancel/complete returns it to `available`.
- `GET /api/cars?available=1` filters; `GET /api/bookings` returns own rows or all for an admin; `/api/report` and every `/api/admin/*` route are admin-only. Fare rows are editable via `/api/admin/fares*`; the public `/pay` page renders the `fares` table server-side.
- `trip_at` is a local ISO string; the UI renders it by replacing `T` with a space.

## Verification

- Backend changes: `python -m pytest -q`. Tests use temporary databases and do not touch `backend/data/`.
- Front-end changes: start the server and load the pages; there is no build, lint or typecheck step to run.
- `README.md` is the source for the full endpoint table, env vars and deployment; keep it in sync with behavior changes.
