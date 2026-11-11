# Research brief: shared header navigation

Status: approved (2026-11-11). Implemented in `backend/templates/partials/header.html`,
`web/css/styles.css`, `web/js/nav.js`, `web/js/i18n.js`, `backend/templates/layout.html`.

## 1. Scope

- Request: "i think we need to enhance this header links."
- Type: redesign of the shared header's navigation cluster (used by every page).
- Audience: visitors choosing a transfer, tour, or rental — mostly first-time, on
  phones, often arriving from WhatsApp.
- Not in scope: footer, search result logic, admin sidebar, page heroes, i18n wording
  beyond new control labels.

## 2. Project constraints

- Locked: dark `#0B0B0C` + lime `rgb(198,244,50)`; one filled lime control per view;
  no new dependencies, no icon library, no build step; inline SVG only.
- Must preserve: server-rendered `aria-current="page"`, `body.logged-in` /
  `body.is-admin` visibility (`.nav-account-item`, `.nav-admin-item`), the search
  markup contract (`#site-search`, `#search-input`, `#search-results`), EN/RW keys.
- Tokens: `--surface`, `--surface-2`, `--line`, `--line-soft`, `--yellow`, `--font-sans`;
  44px minimum target.
- Baseline: 10 controls in one row; 85px tall at 1440, 145px at 1024, 259px at 390
  because the row wrapped three times.

## 3. References (rendered in Chromium at 1440×900)

| # | Source | Pattern | Why it fits | Do not copy |
|---|---|---|---|---|
| 1 | [Blacklane](https://www.blacklane.com/en/) | 4 top-level items, two with chevrons; `English (US) ▾` as quiet text; `Sign in` as a thin outlined pill; no search, no CTA in the bar | Same premium-chauffeur domain; proves a header can carry identity with very few items | Translucent nav over a photo; no CTA at all |
| 2 | [Suntransfers](https://www.suntransfers.com/) | 64px bar: brand, `Agencies`, `Help Centre`, flag + `English ▾`, `€ EUR ▾`, one outlined `My booking` pill | Closest business model (airport transfers); restrained utility cluster | Flag icons; light theme; currency selector |
| 3 | [DiscoverCars](https://www.discovercars.com/) | Brand + `EUR ▾`, `English ▾`, `Help`, `Manage booking`, outlined `Log in` — five controls total | Rental customer with the same "manage my booking" need as Pay online | Red/blue palette and heavy logo lockup |
| 4 | [Talixo](https://www.talixo.com/en/) | Flat dark bar: `EN ▾`, `SIGN IN`, `SELF SERVICE` as plain text; services in a mega-panel below | Dark theme, same transfer niche; text-weight utilities keep the bar calm | All-caps micro-links, no visible primary action |
| 5 | [Booking.com](https://www.booking.com/) | Two tiers: utility row above product tabs with a selected pill | Shows grouping several services when they genuinely compete | Two-tier height and icon-per-tab density |

Access notes: the five above were rendered. Welcome Pickups (bot check), Sixt
(403), GetYourGuide (error page), Klook (blank) and Emirates (maintenance page)
could not be rendered and were not studied.

## 4. Findings

- Hierarchy: brand first, then 2–5 destinations, a thin utility cluster, at most one
  primary action. None carries eight equally weighted links.
- No reference spends a slot on "Home"; the logo is home.
- Search is rare in the bar (0 of 5); it belongs to the hero or a single icon.
- Language is quiet text, never a filled segmented control.
- Density: 64–88px single-row bars; two tiers only when products compete.
- Mobile: compact bar plus a menu — never wrapped rows.

## 5. Recommended direction

A quiet single-row bar with one utility cluster and a mobile drawer.

- Row (≥1100px): logo · Transport · Tour packages · Car rental · Contact · Pay online ·
  search icon · EN | RW · Login · Book now.
- Type: existing `.9rem/600` links; utilities at `.85rem`, muted white warming to white.
- Color: Book now is the only filled lime control. The pressed language is white text
  with a 1px lime underline; search becomes `--surface-2` with a `--line` border.
- Search: icon expands the same `#site-search` field in place; Escape closes and
  returns focus; results list untouched except stacking correctly.
- Components: existing header pieces plus one addition — a drawer
  (`button[aria-expanded]` + panel) holding the links, language, Login/Account/Admin
  and a full-width Book now, with server-rendered links and a no-JS fallback.
- Motion: 160–180ms opacity/width; nothing on load; reduced motion respected.
- Deliberately not doing: no "Services" dropdown (would bury three revenue pages), no
  second header tier, no taller sticky header.

## 6. Risks and open questions

- Removing "Home" is the one judgement call; the logo carries it and shows
  `aria-current="page"`.
- The drawer is new JS in `nav.js`; it received a keyboard/focus pass and a no-JS
  fallback check.
- Header height at 1024 dropped from 145px to 67px.
- Search results were rendering as a flex row (pre-existing) and are now `display:block`.

## 7. Approval

Approved as briefed on 2026-11-11.
