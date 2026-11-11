# Research brief — Admin sidebar + account avatars

## 1. Scope

- Request (user's words): "it's better to use sidebar and make sure is clean and use avatars for account page".
- Type: redesign of the existing `/admin` portal shell + the `/admin/accounts` table.
- Audience/role: the transfer company's ops admin, daily use, task-first (approve bookings, watch fleet, read messages).
- Not in scope: `/account` (customer shell stays hash-routed), marketing pages, the API, the other admin tables' data.

## 2. Project constraints

- Locked: dark-first tokens (`--paper --surface --surface-2 --line --ink --muted --yellow/--green`); lime accent belongs to chrome, status colors live in badges; server-rendered `aria-current="page"` nav (AGENTS.md rule); real `/admin/<view>` routes; no JS build, no icon library today; visible copy is i18n-keyed by exact English text.
- Reuse: `.table-wrap`/`table.data`, `.badge`, `.mini` buttons, `.form-box`, row menus, empty states.
- Current shell: centered "Operations / Admin" hero + horizontal tab row + full-width tables. No sidebar, no avatars, no photos in the users table (name/email/phone only) → **initials avatars**, no new data needed.

## 3. References (all read as text/HTML/code; visual rendering NOT verified)

| # | Source | Pattern | Why it fits | Do not copy |
|---|---|---|---|---|
| 1 | GitLab Pajamas — Navigation sidebar spec | Sidebar zones stay constant; short 1–2 word items; active = `aria-current`, never `aria-selected` | Direct match: we have exactly this IA | Hide/show cookie prefs, pinned items |
| 2 | Setproduct — sidebar anatomy (2026) | "Past 7 destinations a top bar breaks" — we have 7; 6-zone anatomy; footer = person row | Justifies sidebar over tabs for us | Overlay drawers, command palette |
| 3 | Tessera — admin dashboard guide | Frame: 250px side nav + person row at bottom; every page starts with left-aligned title + one context line + actions | This is the "clean" ask: hero dies, structure stays | Collapsible rail (extra JS) |
| 4 | Plugixa Car Rental (shipped product, transport domain) | Sidebar with grouped sections inside its own app chrome; tables with chips/rows for ops data | Closest domain product; confirms table-first, chrome-quiet ops UI | WordPress shell, charts we don't have |
| 5 | borg-ui users table commit + shadcn "Table with Avatar" | Row = 34px initials avatar + name stacked over email; role/status stay separate columns | Proven pattern for the accounts page; initials since no photos | Role-tinted avatar colors, slide-overs |
| 6 | Linear design notes (Part II / refresh) | Chrome is "a few notches dimmer" than content; fewer, softer borders | "Clean" via restraint, not decoration | Theme generator, custom theming |

## 4. Findings

- **Hierarchy:** nav in a left column, content owns the rest; page identity = left-aligned h3 + one muted line (we already have per-view `h3` + `.admin-sub`). The centered hero is chrome competing for attention — refs say kill it.
- **Density:** sidebar costs ~240px width but frees the vertical (tabs currently eat a full row + bottom border on every view). Tables keep full remaining width and scroll internally as today.
- **Interaction:** all destinations reachable at all times; active item marked by shape + contrast, not color alone (WCAG — left indicator bar + bold + white text on dark).
- **States:** portal already has loading (`say(st...)`), empty (`.tt-empty`), error and permission redirects — the shell change must not touch them.
- **Accessibility:** 44px row targets (already the house rule), visible focus (existing `outline:3px solid var(--yellow)` pattern), `nav aria-label` landmark retained.

## 5. Recommended direction

**Left-sidebar portal shell, hero removed, initials avatars on the Accounts people cell.**

- **Layout:** `.admin-shell` becomes `display:grid; grid-template-columns:240px 1fr; gap:34px; align-items:start` inside the existing `.container`. `.admin-side` is sticky (`top:20px`), background `--surface`, 1px `--line` border, radius 10px (same family as `.table-wrap`). Zones top→bottom: (1) brand row "Thomas Transfer — Admin" linking `/`; (2) the existing 7-view nav as a vertical list (same `/admin/<view>` hrefs, same `data-view`, server-rendered `aria-current` unchanged); (3) footer row: signed-in admin's initials avatar + name, then **Back to site** and **Logout** links (today's topbar content moves here and the topbar + centered `.admin-head` are deleted).
- **Active item:** 3px lime left bar + `--heading` text + `--surface-2` background; inactive `--muted`, hover as today. Rows: padding 12px 14px, min-height 44px, `.9rem/700` (existing type scale, no new tokens).
- **Avatars:** new `.avatar` component — 34px circle, `--surface-2` fill, 1px `--line` ring, `--heading` initials, `.72rem/800`; initials = first letters of first two name words (fallback: email's first letter), rendered by a small `initials()` helper in `admin.js`. Accounts table: `Name` + `Email` columns merge into one **People** cell (avatar left, name over muted email); Role/Status/Joined/Action columns unchanged.
- **Color:** existing tokens only; lime stays in chrome (nav indicator, focus), never in data. One addition justified: the `.avatar` class.
- **Motion:** none new (hover colors only, house style).
- **Mobile (<900px):** the grid collapses — `.admin-side` becomes a normal-flow block above content (brand row, horizontal-scrolling nav chips, footer row). CSS-only, no hamburger JS, nothing becomes unreachable.
- **Deliberately not doing:** icon set per nav item (no icon system in repo; text list is what Linear-era "clean" does anyway), collapsible rail, per-role avatar tints, avatars on bookings/messages/comments rows (can extend later if you like the look), touching `/account`.

## 6. Risks & open questions

- "Account page" interpreted as **/admin/accounts** (the portal). If you meant the customer `/account` screen, say so — different design.
- Sizes (240px, 34px) are conventions from refs I read as text, not measured pixels; final spacing tuned in-browser.
- Wide tables inside `1fr` on ~1280px screens get ~1000px — `.table-wrap` already scrolls horizontally; will check Bookings (9 cols) renders without squeeze.
- Merging Name+Email changes a table header word — needs i18n keys ("People" or keep "Name"), and the CSV exports are unaffected.

## 7. Approval

Approve / change direction / keep current design?
