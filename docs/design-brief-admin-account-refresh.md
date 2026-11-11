# Research brief — `/admin` + `/account` visual refresh

Direction: dark, lime, borrowed structure from the Wellow shot. No palette change.

---

## 1. Scope

- **Request:** "take from this shot" — the user's reference is
  `dribbble.com/shots/27860851` (Wellow, a mental-wellness SaaS dashboard).
- **Approved scope:** `/admin/*` and `/account` only. Marketing pages untouched.
- **Approved palette decision:** stay dark `#0B0B0C` + lime `#C6F432`. Borrow
  structure, hierarchy and density — not the light surfaces or indigo accent.
- **Type:** redesign of existing screens. No new screens, no new routes.
- **Audience:** two different jobs on two surfaces.
  - `/admin` — the operator, daily, at a desk, scanning for what needs a
    decision. Density and scannability win.
  - `/account` — the customer, occasionally, choosing a car and sending a
    request. Clarity of the next step wins.
- **Explicitly not in scope:** the shared marketing header/footer, the sidebar
  structure (only its surface polish), API shapes, status vocabularies, the
  custom select we just shipped, i18n key strategy, `web/` build story.

## 2. Project constraints

**Locked**

- Tokens only; no new palette. Palette stays `--paper #0B0B0C`,
  `--surface #171718`, `--surface-2 #222223`, `--line #2E2E30`,
  `--muted #B4B4B9`, `--yellow #C6F432`.
- Lime stays chrome-only (actions, selection, focus). It must not become a
  decorative fill on every card — that is the current problem.
- Status vocabularies are fixed: cars `available|booked|maintenance`,
  bookings `pending|confirmed|completed|cancelled`.
- Server-rendered `aria-current="page"`, `ADMIN_VIEWS` whitelist, `.admin-view`
  class-based section switching.
- No JS build step, no icon library, no new dependency. Inline SVG only.
- `window.ttPages.refresh()`, `refreshNavCounts()`, `centerActiveNav()` keep
  working.
- Visible copy translated by exact English key in `web/js/i18n.js`.

**Shared components that must be reused**

`.admin-shell` / `.admin-side` (fixed 100vh rail, 240px) · `.admin-filter` ·
`.data` table + `.table-wrap` · `.mini` / `.ghost` / `.ok` buttons · `.status`
live region · `.form-box` · `.tt-sel` custom select · `.dp-*` date picker ·
`window.ttEmptyState` · `.skel` skeletons.

**Tokens available:** color as above · radius 8 / 12 / 14 / 16 / 20 / 32 / 999 ·
spacing on a 4px rhythm · type `Google Sans` 400/500/700.

**Related screens that must stay consistent:** `/cars`, `/pay`, `/account`
share `.car-card` and `.btn`; `/admin` shares `.data` with nothing else.

## 3. References

| # | Source | Pattern | Why it fits | Do not copy |
|---|---|---|---|---|
| 1 | Dribbble — Wellow dashboard (user's shot, rendered 3200×2400) | Card anatomy: title + tiny tinted pill + info glyph, big value, muted caption, one tinted status pill with an arrow; section header = title + muted subtitle; dark pill = primary, outline pill = secondary; single-line chart with area fill + insight strip | This is the exact request. The *anatomy* transfers to dark unchanged: value first, caption second, status third | Light `#F8F8FA` canvas, indigo `#6F62DB`, greeting-with-name hero, emoji mood faces, invented metrics, "gentle" copy |
| 2 | Grafana Play → Dashboards (rendered, dark `#040608`) | Fixed rail + one content panel per view; a toolbar row (search, filter chips, sort) sits *inside* the panel; rows separated by hairlines, no card per row; active nav = tinted pill | Closest real analogue to `/admin`: same rail + filter + table job, proven at operational density | Dense 38px rows, checkbox chips, `ctrl+k` affordance, Grafana's own orange accent |
| 3 | GitHub → `vercel/next.js` issues (rendered, dark `#0d1117`) | Counts as small pill tabs (`Open 1,128`); filters as compact outlined controls in one toolbar; label chips with colored borders; hairline row dividers; one solid primary button per view | Shows how to keep status visible without spending a card or a filled icon on it | 86px two-line rows, label-chip rainbow, issue-page chrome |
| 4 | Cloudflare Radar → Traffic (rendered, dark `oklch(.192)`) | Card header = 18–20px title + 13px muted subtitle + small inline tools; stat block = one large number + label + ranked list; chart with dashed grid, legend dots, dashed "previous period" line | Best pattern for the admin overview numbers and the bookings chart, in dark | Dense multi-series charts, ranked country lists, `RADAR` branding, 160px pill radii everywhere |
| 5 | Linear (rendered, dark `#08090A`) | Type: 64px/510 headings, tight tracking, high contrast white on near-black; pill + 8/12px radius mix; restrained borders | Confirms the type scale and the radii mix already in `styles.css` | Its hero video content (did not render), marketing copy |

**Access notes:** all five were rendered in real Chromium at 1440×900 and
inspected as screenshots plus computed styles. Dribbble needed a headed browser
(headless returns `HTTP 202` + empty body). Linear's hero is a lazy video and
rendered blank — only its header and computed type/radii were usable, so no
layout claim is made from it. `play.grafana.org` needed the `/dashboards` route
(the shot URL 404s).

## 4. Findings

What the four dashboard references agree on, in plain language:

- **Hierarchy.** A number and its label carry the screen; the icon does not.
  Wellow, Radar and Grafana all lead with the value and put the glyph last or
  omit it. Our overview does the opposite: a 44px filled icon tile first, the
  number second.
- **Density.** Operational screens are lists, not card grids. Grafana and
  GitHub put rows in one panel with hairline dividers. Cards are reserved for
  *aggregates* (a stat, a chart), never for rows.
- **Interaction.** The primary action appears once per view and is the only
  filled control. Row actions are text or a single overflow menu. We currently
  put two solid buttons (`Confirm` lime-green, `Cancel` red) on every row.
- **States.** All four show real empty/loading structure (skeletons, "No
  dashboards", zero counts as `0` with a muted label, not a hidden card).
- **Accessibility.** Dark surfaces carry 1px borders at ~10–14% white, never
  shadows; muted text sits one step above the surface, not at 50% grey; focus
  rings are the accent color, 2–3px, offset. Targets ≥ 36px; row actions ≥ 32px.

Current state, measured on our own screens (1440×900):

- `/admin` overview: **7** stat cards, wrapping 4 + 3, each with a 44px filled
  lime/dark icon tile, a number and a one-word label. No delta, no period, no
  link. This is the "icon + heading + number grid" anti-pattern.
- "Bookings per month": bars render as ~2px hairlines (`Jun`–`Oct` look empty,
  `Nov` is one grey block). No axis, no grid, no value labels.
- Bookings table: 6 columns, ~58px rows, two solid 80×40 buttons per row.
- `/account`: the "Book in three steps" aside has a lime-tinted border plus a
  lime glow while every other card is plain — the accent is doing decoration,
  not signalling state. Car cards use a lime price and a lime `Book` pill
  directly under a lime-bordered aside, so the eye has three competing accents.

## 5. Recommended direction

**One direction: "operator's ledger".** Keep the dark lime identity; replace
decoration with hierarchy. The accent marks *action and selection only*.

**Layout**

- `/admin` overview, top to bottom: page header (title 22px + subtitle 13px
  muted + one right-aligned primary action) → **one** pulse strip → chart card
  → "Needs attention" list. The 7 cards collapse into a single 4-cell strip
  separated by hairlines (Pending, Confirmed, Available cars, Revenue), each
  cell = 28px value, 12px uppercase label, 12px muted caption. The three
  remaining counts (Accounts, Messages, Booked cars) lose their cards: Messages
  and Bookings already carry nav pills; Accounts becomes a 13px muted line under
  the strip. Net: 7 boxes → 1 strip.
- Chart card: header row (title + subtitle + `Last 6 months` as plain text, no
  chip), then a 200px plot with a 1px dashed grid at 25/50/75%, lime line +
  `rgba(198,244,50,.12)` area fill, month labels at 11px muted. One insight line
  under the plot: `3 bookings this month · 3 waiting for a decision` — real
  numbers only, hidden when zero.
- `/admin` list views: toolbar inside the panel (search, status select, primary
  action) exactly as `.admin-filter` works today, then a full-bleed `.data`
  table with 44px rows and hairline dividers, no outer border. Row actions:
  text buttons (`Confirm`, `Cancel`) at 13px, `Confirm` in `--green-text`, no
  solid fills. Row status becomes a `.pill` with a 6px dot.
- `/account`: booking panel becomes a numbered rail — `1 Choose a car`,
  `2 Trip details`, `3 Confirm` — with 1px connectors between circles, on
  `--surface` with a normal `--line` border. Lime appears only on the current
  step's circle and on the `Book` pill of the selected car. Unselected car cards
  get a plain 1px `--line` border.

**Type**

- Page titles 22px/700 → **20px/600**, letter-spacing `-0.01em`.
- Section titles 16px/600, subtitle 13px/500 `--muted`.
- Stat value 28px/700 tabular; stat label 12px/700 uppercase `.08em` `--muted`.
- Table body 13px/500; header 11px/700 uppercase `.08em` `--muted`.
- Numbers use `font-variant-numeric: tabular-nums`.

**Color**

- Accent usage budget per view: **one** filled lime control, plus selection
  state. Everything else: 1px `--line` borders, `--surface` fills, `--muted`
  secondary text.
- One justified token addition: `--line-soft: rgba(255,255,255,.07)` for
  in-card row dividers (the existing `--line` is too strong at 44px row height),
  and `--lime-soft: rgba(198,244,50,.12)` for pill/step fills. Both are derived
  from existing colors, no new hues.

**Components**

- Reuse: `.admin-shell`, `.admin-side`, `.admin-filter`, `.data`, `.mini`,
  `.pill`/status, `.status`, `.form-box`, `.tt-sel`, `.skel`, `ttEmptyState`.
- Additions, each justified by a reference: `.pulse` (hairline stat strip,
  Radar/Grafana), `.chart` (line + area, Wellow/Radar), `.insight` (single muted
  line under the chart), `.step-rail` (numbered connector, Wellow's step list).
  No other new classes.

**Motion**

- 120–160ms on `border-color`, `background-color`, `transform` for the chart
  line draw (one `stroke-dashoffset` run on first paint only). No entrance
  animations on content the operator came to read. `prefers-reduced-motion`
  disables the line draw.

**What we are deliberately not doing**

- No light theme, no indigo, no greeting hero, no emoji/icons per stat.
- No card around every table row.
- No new charting library — inline SVG built from `/api/report` data, as the
  current chart already is.
- No change to the shared marketing header on `/account`, even though it
  clashes with the dashboard language; that is a site-wide decision, not this
  brief.
- No new admin features. This is presentation only.

## 6. Risks and open questions

- **Chart honesty.** The current chart looks broken because bars are ~2px. If
  `/api/report` has no data for a month we must render `0`, not an invisible
  bar. Needs a check against the real report payload.
- **`/account` header clash** — the marketing navbar (blue-grey search pill,
  `Book now` lime pill) sits directly above a quieter dashboard. Accepting that
  mismatch is a decision, not an oversight.
- **Touch targets.** Text row actions at 13px need ≥32px tall hit areas;
  verify at 390px.
- **RTL/font scaling** not applicable (EN/RW only), but 200% text zoom must not
  clip the pulse strip — needs a browser check.
- **Empty DB** renders zero everywhere; the pulse strip must not look broken
  with four zeros and no caption.

## 7. Approval

Reply with one of:

- **approve** — implement as written, in batches (admin overview → admin lists →
  account), verifying each in Chromium.
- **change direction** — tell me what to alter in this brief.
- **keep current design** — stop here.
