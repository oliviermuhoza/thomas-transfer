# Research brief — Admin sidebar polish (pass 2)

## 1. Scope

- Request: "please enhance ui-ux of that sidebar".
- Type: polish of the shipped `/admin` sidebar shell (`backend/templates/pages/admin.html`, `.admin-*` rules in `web/css/styles.css`, `renderMe()` in `web/js/admin.js`).
- Direction is unchanged from the approved brief (`docs/design-brief-admin-sidebar.md`): left sidebar portal, lime used only in chrome, server-rendered `aria-current`, no JS build, no icon library. This is states, hierarchy, density and the mobile collapse — not a new layout.
- Not in scope: the tables, forms, `/account`, the API contract.

## 2. What the rendered sidebar actually does today

Inspected in Chromium against a throwaway DB (`/admin`, 1440×900, 1100×800, 390×844):

1. **Brand is a 3-line stack.** `Thomas` / `Transfer` / `ADMIN` occupies ~110px and wraps because the wordmark is two elements inside a 208px column. It reads as a mistake, not an identity.
2. **No icons.** Seven text rows in one flat list; nothing anchors them. Every row is the same weight, so scanning is read-every-label.
3. **No signal in the nav.** A pending booking or an open message is invisible until you open Overview — the one thing an ops sidebar should tell you.
4. **Footer reads as body text.** `← Back to site` and `Logout` are `.auth-back` links at 0.85rem, same colour, no affordance; `Logout` (an exit action) looks identical to a nav link.
5. **Mobile is broken, not just tight.** At 390×844 the header block is ~650px: brand stack, person row, back link, logout, then two rows of nav chips. Content starts below the fold. Measured from the screenshot.

## 3. References

All read as text/HTML only — **no reference was rendered in a browser**, so nothing below is a claim about their pixels.

| # | Source | Pattern | Why it fits us | Do not copy |
|---|---|---|---|---|
| 1 | Setproduct — sidebar anatomy (2026) | Six zones; pin header + footer, scroll only the middle; footer belongs to the person, "keep it to one row" | We have 7 items and a full-height rail; pinning is what makes the rail feel like an app | Upgrade banners, collapse toggle, workspace switcher |
| 2 | saasui.design — SaaS sidebar UX (2026) | Order by task frequency, not launch order; long tail (settings/billing) sits low and quiet | Justifies Overview→Bookings→Fleet first, Accounts/Messages/Comments next, Fares quiet at the bottom | Command palette, nesting |
| 3 | Inspo AI — sidebar anatomy (2026) | Primary item = short label + icon; group labels optional; badge only for counts/alerts, "used sparingly" | Icons give the scan anchors; 2 live counts are exactly the "sparingly" case | Collapsible rail, inline search |
| 4 | Modrim — Linear-style sidebar pattern | Item = icon + label + right-aligned count; uppercase group labels | Proven row anatomy for icon + count in one 44px line | Their density (~32px rows) — our house target is 44px |
| 5 | shadcnblocks "Sidebar 6" / shadcn `SidebarFooter` | Footer = avatar + name + muted email, logout behind the person, not a peer nav link | Fixes our footer: person first, actions secondary | Dropdown menu (needs JS; we keep static links) |
| 6 | Byteion / SGDS sidebar docs | Active state must not be colour-only; mobile = bottom nav or drawer, never a tall stack | Confirms the 3px bar + weight change we already have; names what is wrong at 390px | Slide-over drawer JS |

## 4. Findings

- **Hierarchy:** a brand row of one line, then nav, then person. Today the brand out-shouts the nav.
- **Density:** icons + counts add information inside the same 44px row height — no extra vertical cost. Mobile should cost ~150px, not ~650px.
- **Interaction:** counts are the only new dynamic thing; they must not shift layout when they appear (reserve the badge slot, hide at 0).
- **Accessibility:** keep `<nav aria-label>` + `aria-current="page"`; add `:focus-visible` ring (house `outline:3px solid var(--yellow)`); counts need an accessible name (`aria-label="3 pending bookings"` on the link, badge `aria-hidden`); icon SVGs `aria-hidden`, label always visible (no icon-only mode).
- **States:** nav is server-rendered and always correct; counts are the only network-dependent part → render nothing, never a placeholder, until the fetch resolves.

## 5. Recommended direction

**Keep the rail, add the three things it is missing: a one-line brand, icon+count rows, and a person footer that reads as a person. Collapse it to a compact strip under 900px.**

- **Header (pinned, ~56px):** 30px square mark `TT` (existing `.avatar` shape, `--paper` fill, lime 1px ring), wordmark `Thomas Transfer` on one line at `.95rem/700`, and a small `ADMIN` chip (`--surface-2`, 1px `--line`, `.7rem/700`, letterspaced) — all inside one `<a href="/">`. 1px `--line` divider under it. `ADMIN` stops being a giant line and becomes a label.
- **Nav (the only scrolling region):** each row becomes `<svg 18px stroke 1.8 + label + count>`, padding `10px 12px`, `min-height:44px`, gap 8–10px, active = `--surface-2` fill + 3px lime left bar + white text + 700 (as today, plus the icon inherits colour). Counts: **Bookings** = pending bookings, **Messages** = open messages; pill `--surface-2` → `--yellow` fill with navy text when > 0, `aria-hidden` on the number, count folded into the link's accessible name. Hidden entirely at 0, slot reserved so rows never jump.
  - Counts come from two existing admin endpoints on boot: `/api/report` (pending) and `/api/admin/messages` (open). Refreshed after a status change / on view load — never on a timer.
- **Footer (pinned, one person row + one action row):** 32px avatar + name (600) + email (`.78rem --muted`, ellipsised) in a `--paper` card with 1px `--line`; under it a single row: `← Back to site` as a quiet `.8rem --muted` link and `Log out` as a bordered ghost button (`.mini ghost`, 36px) so exiting is visibly an action, not a destination. The `Logout` text becomes `Log out` (i18n key updated with it).
- **Mobile (<900px), CSS-only:** the rail becomes a strip of ~150px in three rows — (1) brand line with the person avatar right-aligned, (2) one horizontally-scrolling chip row with icons + counts (active chip keeps its lime underline, auto-scrolled into view by 4 lines of JS so the current section is never off-screen), (3) one tight row: `Back to site` · `Log out`. The person name/email is dropped there (the avatar carries identity).
- **Tokens:** none added. Lime stays chrome-only; badge reuse; icons are inline SVG in the template (same technique as `CARET` in `admin.js`), so no library.
- **Motion:** 120ms background/colour transitions only, `prefers-reduced-motion` respected for the mobile `scroll-behavior`.
- **i18n:** every new string (`Admin`, `Log out`, accessible count labels) goes into `web/js/i18n.js` with its exact English key.

## 6. Risks

- Two extra admin fetches on boot (~1 request each, admin-only, tiny payloads). If you would rather not, drop the counts — the rest stands alone.
- `Thomas Transfer` on one line in 232px minus the mark: the wordmark must ellipsise, not wrap, on narrow desktop widths.
- Counts need refreshing after actions; I will wire them to the existing `done` callbacks only, so no polling.

## 7. Definition of done

- Screenshots at 1440 / 1100 / 390 before and after, compared against this brief.
- `python -m pytest -q` still passes (templates must keep the same ids/routes; no API change).
- Keyboard pass: Tab order logo → nav → footer → content, visible focus on every item, `aria-current` still server-rendered.

**Approve, change direction, or drop the counts?**

## 8. Implementation notes (built 2026-11-10)

Verified in Chromium against a throwaway DB (3 pending bookings, 1 open message) at 1440 / 1100 / 1024 / 390 / 360px; `python -m pytest -q` → 115 passed.

Matched the brief:

- One-line brand (28px `TT` mark, wordmark, `ADMIN` chip) on a 1px divider; nav is the only scrolling zone; person card + action row pinned.
- Inline SVG icons, 44px rows, lime active pill drawn as a `::before` (3px, inset 9px top/bottom) so the rounded row is not cut by a border.
- Counts: Bookings = pending, Messages = open; pill hidden at 0, accessible name set on the link (`aria-label="Bookings, 3 bitegereje"`). They update after Confirm/Cancel and Mark handled — measured 3 → 2 and 1 → hidden.
- Person footer: 30px avatar, name, muted email, `Back to site` (quiet) + `Log out` (bordered) on one row, no wrapping.
- Mobile strip: 158px total at 390 and 360px (was ~650px). Brand row, scrolling chip row with the active chip centred, one action row.

Deviations from the brief, and why:

- **Rail is 240px** (brief said 236): the one-line wordmark needs the 4px; 236 clipped it by 4px (`scrollWidth` 115 vs `clientWidth` 111).
- **Counts were deduplicated**: Overview and Messages already fetch those two endpoints, so the loader sets the count and `refreshNavCounts()` skips the duplicate request for the open view.
- **Mobile keeps the person name** instead of showing the avatar in the brand row — moving the avatar into the brand row would have needed two copies in the DOM or a JS move; the card row costs 43px and keeps the signed-in identity visible.
- **Root cause found on the way**: the marketing navbar styles were written against bare `nav`, so they applied to the portal's `<nav>` (forcing `flex-wrap:wrap` and `order:3`, which stacked the footer above the nav). All header rules are now scoped to `.bar nav`; the public header was re-checked at 1440 and 390 and is unchanged.

## 9. Follow-up (11 Nov): the rail is fixed, never scrolls

Asked twice: the sidebar must be a fixed 100vh column with no scrolling of its own. It is now `position:fixed; top:0; left:0; bottom:0; width:240px; height:100vh/100dvh` and `.admin-shell` reserves the 240px with `padding-left`, so only the content column scrolls and the rail cannot move or scroll. To keep the seven rows + footer inside a short viewport, `.admin-side` tightens its own rhythm below 700px height (38px nav rows, smaller brand/footer) instead of overflowing — measured at 1440×700 and 1440×560: rail `scrollHeight == clientHeight`, footer 10px off the bottom, no scrollbar. Under ~460px height the rail falls back to an internal scroll purely so Log out cannot become unreachable. Phone strip unchanged at 158px; `pytest -q` still 115 passed.


