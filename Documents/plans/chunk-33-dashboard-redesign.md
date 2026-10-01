# Chunk 33 — dashboard visual redesign: reference palette, type scale, truncation fix, minimal navigation (plan)

Status: FROZEN — 2026-10-01. Open questions: none. The five design decisions the planner
raised are resolved by the lead in §12 (LR1–LR5) and are fixed here; the plan implements them
and does not re-open them.

New remediation/feature chunk, not in `Documents/requirements-dependency-map.md` §3/§4
(chunk-14 / chunk-30 / chunk-31 / chunk-32 precedent: registration = plan + run log + branch).
Do not edit the dependency map, the SRS, `AGENTS.md`, or `.kilo/`.

Branch: `chunk-33`, base `main` @ `3750882` (`chunk-32: gate PASSED; run log`).

Authority: `Documents/runs/chunk-33.md` (this chunk's log: origin E-1..E-5, the reference
image read, the Pillow palette extraction and R1 token table, the live-dashboard audit with
measured findings 1–8, and the five `ui-ux-pro-max` CLI queries); the frozen contracts it
cites (`Documents/plans/chunk-32-dashboard-visual-design.md`,
`Documents/interfaces/chunk-11.md` §11/§12); and the operator request (2026-10-01, quoted in
the run log §Origin). This chunk **builds on** chunk 32 and **supersedes** a named subset of
its decisions (§3). It amends no frozen public signature.

SRS authority: `Documents/SRS-lean-v2.md` §10 `LREQ-RPT-010`..`LREQ-RPT-050`
(lines 1155–1189 **(read)**), §12 (structure/conventions), §14 (constants), §15/§16
(deferred scope, limitations), Appendix C (warning vocabulary). `AGENTS.md` Hard rules 1–4
and "Out of scope — do not add". Every countable claim is labelled **(read)**,
**(counted)** or **(unverified)** per project-rules "Plan review and audit"; the walk is §13.

---

## 1. Scope, non-goals, LREQ roles

### 1.1 Scope (in)

1. **Reference palette (E-3, R1).** Replace the nine semantic colour tokens in
   `src/niche_scout/assets/dashboard.css` with the reference-image values (run log R1 table,
   reproduced verbatim in §4). `--accent` moves from amber `#F2C14E` to the image green
   `#46B688`. Re-tune the four ordinal evidence colours to the image family (LR1, §4.2) in
   both the stylesheet and `report.py`'s `_EVIDENCE_GRADE_COLOURS` (`report.py:273`).
2. **Explicit type/weight scale (§5).** Replace the ad-hoc heading/KPI sizes and the
   undifferentiated 400/600/700 histogram (run-log finding 3: `{400:1008, 600:34, 700:23}`)
   with named size and weight tokens and a fixed weight per role. Mono for data, sans for
   labels (skill `typography.csv:43`).
3. **Truncation fix (§6).** (a) Replace the fixed Plotly left margin `l: 140`
   (`report.py:1418`, inside `_base_layout` at `report.py:1411`) with `automargin` on the
   category axes so long category names are not clipped, for the affected figure builders
   (`_score_bar_figure`, `_population_lollipop_figure`, `_contribution_figure`).
   (b) Disclose DataTable header/cell clips with `text-overflow: ellipsis` **and** a native
   `<details>` "Column guide" above the primary table listing all 30 `_PRIMARY_COLUMNS`
   labels verbatim (LR4).
4. **Minimal navigation (§7).** A presentational, anchor-based `dash_html.Nav`: icon rail on
   desktop, top bar on mobile; Phosphor-style **inline SVG** icons emitted through
   `dcc.Markdown(..., dangerously_allow_html=True)` (LR2); anchors to the run header, KPI
   strip, charts, primary table, and category detail; a "skip to main content" link;
   `:target` active-section indication; `scroll-margin-top` sticky offset; sequential
   headings; `cursor: pointer` and visible focus on every operable control. **No new Dash
   callback.**
5. **Tests.** New pytest nodes (§9) proving the palette/type tokens, the navigation/skip
   link/inline SVG, the Column guide, the `automargin` change, and the re-tuned evidence
   scale; plus the amended chunk-32 CSS constants. `tests/traceability.json` gains the
   matching keys.

### 1.2 Non-goals (explicitly NOT in this chunk)

- **No content removal.** No `LREQ-RPT-020/030/040/050` string, no primary-table column, no
  Appendix C warning code, and no table/selector row is removed from the DOM. The Column
  guide **adds** text; it renames and removes nothing.
- **No external dependency.** No new runtime dependency; no CDN, web font, `@import`,
  `url(`, or scheme-bearing external asset anywhere in this chunk's output (E-4). Icons are
  inline SVG; the font stack stays the local/system stack from chunk 32.
- **No new Dash callback.** The navigation is anchors only; the single existing
  `detail-panel` callback (`report.py:2156`) is unchanged. No `app.clientside_callback`.
- No historical/trend/multi-run view; no scheduling, resume/checkpoint, favorite-count,
  configurable weights, confidence intervals, or sales calibration (`AGENTS.md`
  "Out of scope"; `check_scope_prohibitions` tokens unchanged).
- No schema, pipeline, `metrics.py`, or `scoring.py` change; no metric recombination or data
  recomputation; the app renders persisted values verbatim.
- **No clock read in `report.py`**; no `metrics`/`scoring`/`collector*`/`config`/`pipeline`/
  `cli` import (purity unchanged).
- No change to the frozen public signatures of `build_dashboard_layout` /
  `build_dashboard_app`; no change to `render_run_report_html` / `render_run_report_text` /
  `write_run_report`; the **static** report path and its inline `_INLINE_CSS`
  (`report.py:403`) are untouched.
- No change to the data model, figures' data, chart ids, existing component ids, callbacks,
  or the CLI.

### 1.3 LREQ roles

| Role | LREQs |
|---|---|
| Primary | `LREQ-RPT-010` (one-command local read-only dashboard; offline styling and packaging) |
| Supporting contract | `LREQ-RPT-020` (primary table / read model; the Column guide discloses all 30 labels), `LREQ-RPT-030` (category detail items retained), `LREQ-RPT-040` (non-rankable categories stay visible), `LREQ-RPT-050` (heuristic statement present exactly once in the DOM) |
| Integration completion | `LREQ-NFR-040` (public builder type hints/docstrings unchanged), `LREQ-ARCH-010`/`LREQ-ARCH-020` (purity: `report.py` imports no forbidden module and reads no clock; `metrics`/`scoring` untouched) |

`LREQ-RPT-010` is the LREQ whose "local read-only dashboard launched by one command"
guarantee this chunk strengthens: the served page becomes palette-consistent, type-ramped,
non-clipping, and navigable, while remaining offline and locally served.

---

## 2. Grounding facts (established; the plan is self-contained)

- **Reference palette** was extracted by the lead with Pillow median-cut + HSV scan; the
  applied nine-token table is run-log R1 (reproduced verbatim in §4.1).
- **Live audit** (Kilo Playwright against the running app; run-log findings 1–8): truncated
  category labels are in the **Plotly figures** (fixed left margin), the primary table's
  headers read as truncated because `.dash-header` is uppercase/letter-spaced and clipped,
  leaf-text weight histogram `{400:1008, 600:34, 700:23}`, font sizes incoherent
  (`{12.48px:750, 12px:118, 16px:85, 13px:77, 17px:11, 14px:10, 20px:2, 24px:4, 9px:4,
  15px:4}`), KPI value 24px vs base 16px with no numeric tier, sticky header inert, page
  height 4115px with no in-page navigation.
- **`_base_layout` fixed left margin is `l: 140` at `report.py:1418`** (the dict at
  `report.py:1411–1423`); `_base_layout` sets `xaxis`/`yaxis` dicts there and is reused by
  every figure.
- **Dash 4.4.1 platform check (read):** the installed `dash/html/` package has **no**
  `Svg`/`Path`/`Circle`/`Rect`/`Polyline` components (`dash/html/_imports_.py` and the
  component file listing contain none), so inline SVG cannot be emitted with `dash_html`
  tags; `dash/dcc/Markdown.py:44` declares `dangerously_allow_html (boolean; default
  False)`, so `dcc.Markdown(svg_markup, dangerously_allow_html=True)` is the offline
  mechanism for inline SVG (LR2). `dcc` is already imported at `report.py:39`.
- **`tests/traceability.json` actual format is node-ID → list of `LREQ-*` IDs** (authoritative;
  verified at `tests/traceability.json:2`, `:1472`, `:1481`). The prose in `tests/AGENTS.md`
  (LREQ → node list) is **stale** and contradicts the file; the plan follows the file.
- **Contrast (hand-computed, WCAG relative luminance on linearised sRGB; background
  `--surface #112D3B`, `L≈0.0231`):** `--fg #E6F0F4` ≈12.4:1; `--muted-fg #8FB0BF` ≈6.2:1;
  `--primary #64BCFB` ≈6.9:1; `--accent #46B688` ≈5.7:1; `--positive #48B78D` ≈5.8:1;
  `--danger #E27882` ≈5.0:1 — all ≥4.5:1 for normal text. Evidence bar fills
  `#C98B8B`≈5.2:1, `#E0A458`≈6.6:1, `#8FB0BF`≈6.2:1, `#46B688`≈5.7:1 on the plot background
  `#112D3B` — all ≥3:1 for non-text UI. (Hand-computed; not tool-verified this session.)

---

## 3. Supersession (chunk-32 decisions chunk 33 replaces)

Chunk 33 amends the following chunk-32 decisions; everything else in chunk 32 stands.

1. **Token hex values — `_DASHBOARD_CSS_HEXES` at `tests/test_report.py:1092–1103`.**
   The expected tuple changes from the ten chunk-32 hexes to the ten new token hexes
   (casefold-compared by
   `test_dashboard_css_asset_exists_is_offline_and_uses_the_token_set`,
   `tests/test_report.py:1658`). The **node ID and its marker are unchanged**; only the
   constant's expected values change. New expected tuple:
   `#0c1d27`, `#112d3b`, `#0c2432`, `#1f394e`, `#e6f0f4`, `#8fb0bf`, `#64bcfb`, `#46b688`,
   `#48b78d`, `#e27882`. The CSS must **not** contain the retired amber `#f2c14e`.
2. **`.dash-header` uppercase / letter-spacing (chunk-32 CSS `dashboard.css:311–323`).**
   Disposition per LR4: **retained as-is** (uppercase + `letter-spacing: 0.04em`). No test
   asserts or forbids them; keeping them is the lower-risk choice and the full label is
   disclosed by the Column guide (§6.2). If implementation finds a test that depends on
   them, they stay; if a test forbids them, that is a stop-and-flag.
3. **`.dash-cell` / `.dash-header` overflow (chunk-32 CSS `dashboard.css:284–294`,
   `:311–323`).** Superseded: both selectors gain `overflow: hidden` +
   `text-overflow: ellipsis` (keeping `white-space: nowrap`), so an unavoidable clip is
   disclosed with an ellipsis instead of a hard cut.
4. **`_DASHBOARD_CSS_TOKENS` / `_DASHBOARD_CSS_CLASSES` at `tests/test_report.py:1076–1131`.**
   Extended (not replaced): the token tuple gains the new size/weight/nav tokens; the class
   tuple gains the new nav/Column-guide classes. The node ID and marker are unchanged.
5. **`_DASHBOARD_CSS_HEXES`'s ten-hex coverage and the old `.dash-header`/`.dash-cell`
   overflow rules are the minimum superseded set; `_EVIDENCE_GRADE_COLOURS` in
   `report.py:273` is also superseded per LR1 (§4.2).** The pinned test
   `test_dashboard_score_bar_encodes_ordinal_evidence_grade` derives its expectation from
   `report._evidence_colour`, so it stays green when the constant changes.

No other chunk-32 decision is superseded.

---

## 4. Palette

### 4.1 Nine semantic tokens (run-log R1, verbatim; the only colour source for the stylesheet)

| Token | Old (chunk 32) | New (from image) | Role |
|---|---|---|---|
| `--bg` | `#0B1120` | `#0C1D27` | page canvas |
| `--surface` | `#1B2029` | `#112D3B` | card / panel |
| `--surface-2` | `#222833` | `#0C2432` | inset, table zebra |
| `--border` | `#2C3440` | `#1F394E` | hairline |
| `--fg` | `#E6E9EE` | `#E6F0F4` | primary text |
| `--muted-fg` | `#9AA6B2` | `#8FB0BF` | secondary text |
| `--primary` | `#6EA8FE` | `#64BCFB` | accent / action |
| `--accent` | `#F2C14E` | `#46B688` | secondary accent (image green; active-nav marker) |
| `--positive` | `#8FD694` | `#48B78D` | positive |
| `--danger` | `#E06C75` | `#E27882` | alert |

`--accent` moves from amber to the image green `#46B688`; amber is no longer a token.

### 4.2 Evidence ordinal scale (LR1 — retained/re-tuned)

| Token | Value | Source |
|---|---|---|
| `--evidence-insufficient` | `#C98B8B` | retained (chunk-32) |
| `--evidence-weak` | `#E0A458` | retained (chunk-32) |
| `--evidence-moderate` | `#8FB0BF` | re-tuned to the image muted blue |
| `--evidence-strong` | `#46B688` | re-tuned to the image green |

`report.py:273` `_EVIDENCE_GRADE_COLOURS` is updated to the same four values, in
`EVIDENCE_GRADE_ORDER` order (`insufficient, weak, moderate, strong`). The ordinal source
stays the enum (`report.py:273–275`); no second literal is introduced.

### 4.3 Contrast budget

- **Normal text ≥4.5:1** against its surface. Hand-computed on `--surface #112D3B`
  (`L≈0.0231`): `--fg` ≈12.4:1, `--muted-fg` ≈6.2:1, `--primary` ≈6.9:1, `--accent` ≈5.7:1,
  `--positive` ≈5.8:1, `--danger` ≈5.0:1 (skill `ux-guidelines.csv:37` Color Contrast,
  ≥4.5:1 normal text).
- **Non-text UI ≥3:1** (skill `ux-guidelines.csv` dark-mode rule; `SKILL.md` "Icon Contrast"
  row: meaningful icons/control boundaries ≥3:1). Evidence bar fills ≈5.2–6.6:1; the
  `--primary` focus ring ≈6.9:1. Colour is never the only signal
  (`ux-guidelines.csv:38` Color Only): evidence grade and rankability carry text.

---

## 5. Type and weight scale (replaces the ad-hoc values)

Font stacks are unchanged from chunk 32 (local/system only; the skill's Google-Fonts
`@import` is rejected under E-4). Structure follows skill `typography.csv:43` "Dashboard
Data — code for data, sans for labels" and skill `ux-guidelines.csv:75` Font Size Scale
("Type scale (12 14 16 18 24 32)").

### 5.1 Size tokens

| Token | Value | Use |
|---|---|---|
| `--font-size-label` | `0.75rem` (12px) | uppercase labels, nav labels, table headers |
| `--font-size-small` | `0.8125rem` (13px) | dense table numerics (≥12px floor) |
| `--font-size-body` | `1rem` (16px) | body, prose, captions, muted |
| `--font-size-subhead` | `1.125rem` (18px) | detail `h4` subheads |
| `--font-size-card-title` | `1.25rem` (20px) | `h3` chart/KPI card titles |
| `--font-size-section-title` | `1.5rem` (24px) | `h2` section titles |
| `--font-size-page-title` | `2rem` (32px) | `h1` page title |
| `--font-size-numeric-md` | `1.25rem` (20px) | secondary numeric (detail values) |
| `--font-size-numeric-lg` | `2rem` (32px) | KPI value (numeric tier) |

The KPI value moves from 24px to the 32px numeric tier so a numeric tier exists between body
(16px) and the page title (run-log finding 5).

### 5.2 Weight tokens and the exact weight per role

| Token | Value |
|---|---|
| `--weight-body` | `400` |
| `--weight-muted` | `400` |
| `--weight-label` | `500` |
| `--weight-numeric` | `600` |
| `--weight-card-title` | `600` |
| `--weight-section-title` | `600` |
| `--weight-page-title` | `700` |

| Role | Size | Weight |
|---|---|---|
| Page title (`h1`) | `--font-size-page-title` (32px) | `--weight-page-title` (700) |
| Section title (`h2`) | `--font-size-section-title` (24px) | `--weight-section-title` (600) |
| Card title (`h3`) | `--font-size-card-title` (20px) | `--weight-card-title` (600) |
| Label (uppercase small) | `--font-size-label` (12px) | `--weight-label` (500) |
| Body | `--font-size-body` (16px) | `--weight-body` (400) |
| Numeric (KPI) | `--font-size-numeric-lg` (32px) | `--weight-numeric` (600) |
| Numeric (table cell) | `--font-size-small` (13px) | `--weight-numeric` (600) |
| Muted | `--font-size-body` (16px) | `--weight-muted` (400) |

Mono for data (`.kpi-value`, `.dash-cell`, timestamps, counts); sans for labels/headings/
prose (skill `typography.csv:43`). Headings stand out from body by size **and** weight
(skill `ux-guidelines.csv:77` Heading Clarity). The Dash `DataTable` default `0.78rem`
(run-log finding 4, 750 nodes) is overridden to `--font-size-small` via
`.dash-spreadsheet-container/.dash-cell`.

---

## 6. Truncation fix (both root causes from the audit)

### 6.1 Plotly fixed left margin → `automargin` (root cause 1)

`_base_layout` (`report.py:1411`) currently sets a fixed `margin` with `l: 140`
(`report.py:1418`) and fixed `xaxis`/`yaxis` dicts. Fix:

- Change the shared margin to `{"l": 8, "r": 24, "t": 48, "b": 40}` (small static floor).
- Add `"automargin": True` to the shared `xaxis` and `yaxis` dicts, so Plotly expands the
  margin to fit the longest tick label plus the axis title. This is deterministic for a
  fixed view because the labels come from the view; two calls produce equal figures.
- Affected figure builders (the ones whose category axis carries long category names):
  `_score_bar_figure` (`y=category`, `report.py:1484–1486`),
  `_population_lollipop_figure` (`y=category`, `report.py:1612–1614`), and
  `_contribution_figure` (`x=category`, `report.py:1512–1514`). `_policy_bump_figure` and
  `_score_quality_scatter_figure` keep short/numeric axes; the shared `automargin` covers
  them harmlessly.

### 6.2 DataTable header visual clip (root cause 2, LR4)

- `.dash-cell` and `.dash-header` gain `overflow: hidden; text-overflow: ellipsis;`
  (keeping `white-space: nowrap`) so an unavoidable clip is disclosed visually. The
  accessible column name stays complete in the DOM (`column-header-name`).
- **Keep** the `.dash-header` uppercase + `letter-spacing` (LR4).
- Add a native `<details className="column-guide">` "Column guide" **directly above the
  primary table** (inside `primary-table-section`, before the table), with a `<summary>`
  and an ordered list of all **30** `_PRIMARY_COLUMNS` labels verbatim plus a short meaning
  for each. It is keyboard- and pointer-operable (native `<details>`/`<summary>`, not a
  hover-only tooltip), and it renames/removes no column. This satisfies skill
  `ux-guidelines.csv:117` Compact Label Overflow ("expose full text to keyboard, pointer and
  touch users; never a hover-only tooltip"), `ux-guidelines.csv:114` Essential Text
  Truncation (Critical: "wrap, stack, resize, or provide a visible full-detail path"), and
  `ux-guidelines.csv:85` Truncation ("truncate with ellipsis and expand option").
- New private helper `_column_guide() -> "dash_html.Details"` builds it from
  `_PRIMARY_COLUMNS` (no new literal column names).

---

## 7. Minimal navigation (purely presentational; no new callback)

### 7.1 Structure and anchors

- New private helper `_dashboard_nav() -> "dash_html.Nav"` returning
  `dash_html.Nav(..., className="dashboard-nav", **{"aria-label": "Dashboard sections"})`.
- Anchors target the five existing sections. New **presentational** anchor ids are added to
  the existing containers (LR3): `run-header-block` (the `Header`, `report.py:2096`),
  `chart-grid` (the charts `Div`, `report.py:2105`), `primary-table-section` (the `Section`,
  `report.py:2112`), `detail-section` (the `Section`, `report.py:2120`); `kpi-strip`
  already carries its id (`report.py:1736`). **Every existing id in
  `DASHBOARD_COMPONENT_IDS` is preserved unchanged** (LR3), and
  `test_build_dashboard_app_layout_matches_the_layout_builder` stays green.
- The page content is wrapped in `dash_html.Main(id="main-content", ...)` so the skip link
  has a target; the root `.dashboard` `Div` and all section classes are unchanged.
- Nav order mirrors the document: run header → KPI strip → charts → primary table →
  category detail.
- A "skip to main content" link is the first focusable element:
  `dash_html.A("Skip to main content", href="#main-content", className="skip-link")`
  (skill `ux-guidelines.csv:46` Skip Links).
- Sequential heading order is preserved: the `h1` stays in the run header; sections keep
  `h2`, cards/subheads keep `h3`/`h4` (skill `ux-guidelines.csv:40` Heading Hierarchy).

### 7.2 Icons — inline SVG (LR2)

- Each nav item is `dash_html.A([icon, dash_html.Span(label, className="nav-label")],
  href="#<target>", className="nav-link")`. The icon is
  `dcc.Markdown("<svg ...>...</svg>", dangerously_allow_html=True)` containing the
  Phosphor outline path inline (no `dash_html` SVG components exist in Dash 4.4.1; §2).
- Icons are decorative beside the visible text label, so the `<svg>` carries
  `aria-hidden="true"` and `focusable="false"` (skill `icons.csv` Usage column for each row:
  "if decorative beside visible text, set aria-hidden='true'"). Icon names, by target:
  `house` (`icons.csv:7`), `grid-four` (`icons.csv:67`), `chart-bar` (`icons.csv:54`),
  `list-bullets` (`icons.csv:68`), `list` (`icons.csv:2`). No emoji (skill `SKILL.md`
  "No Emoji as Structural Icons"); no icon font, no CDN, no `@import`.
- **Text fallback (LR2, required):** every nav item has a visible text label
  (`.nav-label`), so navigation works even if the SVG does not render. The SVG `xmlns`
  attribute is `http://www.w3.org/2000/svg`; this is an inline XML namespace, not an
  external asset fetch, and the offline rule (no external URL/CDN) is about fetched
  resources. **Verification step:** after implementation the lead confirms with Kilo
  Playwright that the SVG renders in the served page; if it does not, the text labels keep
  the nav fully operable and the failure is recorded at the gate.

### 7.3 Responsive rail/top-bar, active state, sticky offset

- **Desktop (`@media (min-width: 1024px)`):** `.dashboard-nav` is a fixed left icon rail
  (skill `styles.csv:29` `--sidebar-width`; `icons.csv:72` `sidebar`). **Mobile (base):**
  `.dashboard-nav` is a top bar. The dashboard body gets a leading inset so the rail does
  not cover content (skill `ux-guidelines.csv:3` Sticky Navigation: "fixed nav should not
  obscure content; add padding").
- **Active-section indication (LR5, lead clarification 2026-10-01):** CSS-only `:target` on
  the destination section (`accent marker / --accent left border`). Additionally, the active
  nav item is indicated **without `:has()` and without JS** by pairing each nav link with a
  persistent rule keyed on the destination: each `.nav-link` gets
  `.nav-link:focus-visible { ... }`, and the current section is marked by the `:target`
  section's own `outline`/`border-left` in `--accent`. Because CSS cannot select the link
  from the target section without `:has()`, the **active link** marker is implemented with
  `:has()` **guarded by `@supports selector(:has(*))`**, with the `:target`-on-section marker
  as the unconditional fallback. Where `:has()` is unsupported the section marker alone
  shows the active section; no JS and no callback. This is the accepted limitation of a
  JS-free nav and is recorded as such in the run log. The nav link also gets `:hover` and
  `:focus-visible` styling.
- **Sticky offset:** `--nav-topbar-height: 56px`; `html { scroll-padding-top:
  var(--nav-topbar-height); }` and `scroll-margin-top: var(--nav-topbar-height)` on each
  target section so a focused/anchored target is not obscured (skill `ux-guidelines.csv:101`
  Focus Not Obscured; `:102` Focus Appearance; `ux-guidelines.csv:3`).
- **Operable-control affordances:** `cursor: pointer` on `.nav-link` and `summary`
  (`styles.csv:29` / SKILL.md pre-delivery checklist "cursor-pointer on all clickable
  elements"); `:focus-visible { outline: var(--focus-ring); outline-offset:
  var(--focus-offset); }` extended to `.nav-link`, `.skip-link`, and `summary`
  (skill `ux-guidelines.csv:29` Focus States). The skip link is visually hidden until
  focused.
- The navigation is anchors only; the only app callback remains
  `_render_selected_detail` (`report.py:2156`). No new callback (LR5, §1.2).

---

## 8. Determinism and purity

- `build_dashboard_layout(view)` remains pure: no clock, no network, no database, no RNG.
  `_dashboard_nav()` and `_column_guide()` emit fixed text, fixed child order, fixed ids,
  and fixed SVG markup, so two calls with the same `view` build equal trees (compared after
  `to_plotly_json()` normalization, as
  `test_build_dashboard_layout_is_deterministic_for_a_fixed_view` asserts).
- `automargin` is a layout property computed by Plotly from the view's own labels; it adds
  no clock/IO and is deterministic for a fixed view.
- `build_dashboard_app(view)` remains a pure construction (no `app.run`, no network, no
  clock read in this module); `assets_folder=str(_dashboard_assets_dir())` is unchanged.
- `report.py` gains no forbidden import (`dcc` is already imported at `report.py:39`);
  `metrics.py`/`scoring.py` are untouched. The stylesheet stays a static file that no Python
  code reads, hashes, or templates.

---

## 9. Test plan

Every analytical node carries `@pytest.mark.lreq(...)` and a matching
`tests/traceability.json` key (node-ID → LREQ list).

### 9.1 New nodes in `tests/test_report.py`

| Node ID | Marker(s) | Asserts |
|---|---|---|
| `tests/test_report.py::test_dashboard_css_uses_the_reference_palette_and_explicit_type_scale` | `LREQ-RPT-010` | The stylesheet contains every new token hex (§4.1) and the four evidence hexes (§4.2); does **not** contain the retired amber `#f2c14e`; defines every size/weight token in §5; contains no `http://`/`https://`/`@import`/`url(` |
| `tests/test_report.py::test_dashboard_layout_has_minimal_anchor_navigation_with_inline_svg_and_skip_link` | `LREQ-RPT-010` | The tree contains ≥1 `Nav`; a `.skip-link` anchor with `href="#main-content"`; anchors whose `href` are `#run-header-block`, `#kpi-strip`, `#chart-grid`, `#primary-table-section`, `#detail-section`; each nav item has a visible text label; ≥1 `Markdown` whose children string contains `<svg` and `aria-hidden="true"`; every `DASHBOARD_COMPONENT_IDS` id is still present |
| `tests/test_report.py::test_dashboard_column_guide_discloses_every_primary_column_label` | `LREQ-RPT-020`, `LREQ-RPT-010` | Exactly one `Details` with `className == "column-guide"`; its normalized tree contains all 30 `_PRIMARY_COLUMNS` labels; the DataTable's default `columns` names are unchanged (`== [label for label,_ in report._PRIMARY_COLUMNS]`) |
| `tests/test_report.py::test_dashboard_charts_use_automargin_for_long_category_labels` | `LREQ-RPT-010` | For each figure with a category axis (`score_bar`, `population_lollipop`, `contribution_stack`), `figure["layout"]["xaxis"|"yaxis"]["automargin"] is True`; the shared margin's `l` is no longer `140`; two layout builds are still equal |
| `tests/test_report.py::test_dashboard_evidence_scale_is_retuned_to_the_reference_palette` | `LREQ-RPT-020` | `report._EVIDENCE_GRADE_COLOURS == tuple(zip(report.EVIDENCE_GRADE_ORDER, ("#c98b8b", "#e0a458", "#8fb0bf", "#46b688")))`; the CSS defines the same four `--evidence-*` values |

### 9.2 Amended nodes (node IDs and markers unchanged)

- `tests/test_report.py::test_dashboard_css_asset_exists_is_offline_and_uses_the_token_set`
  (`:1658`, `LREQ-RPT-010`): `_DASHBOARD_CSS_HEXES` (`:1092–1103`) is replaced with the ten
  new hexes (§3.1); `_DASHBOARD_CSS_TOKENS` and `_DASHBOARD_CSS_CLASSES` are extended with
  the new tokens/classes. The assertion intent is unchanged.
- No other existing node's ID or traceability key changes.

### 9.3 `tests/traceability.json` keys to add (node-ID → LREQ list)

- `tests/test_report.py::test_dashboard_css_uses_the_reference_palette_and_explicit_type_scale` → `["LREQ-RPT-010"]`
- `tests/test_report.py::test_dashboard_layout_has_minimal_anchor_navigation_with_inline_svg_and_skip_link` → `["LREQ-RPT-010"]`
- `tests/test_report.py::test_dashboard_column_guide_discloses_every_primary_column_label` → `["LREQ-RPT-020", "LREQ-RPT-010"]`
- `tests/test_report.py::test_dashboard_charts_use_automargin_for_long_category_labels` → `["LREQ-RPT-010"]`
- `tests/test_report.py::test_dashboard_evidence_scale_is_retuned_to_the_reference_palette` → `["LREQ-RPT-020"]`

Run `python -m niche_scout.tools.validate_traceability` — exit 0 required.

### 9.4 Existing tests that MUST stay green

Pinned dashboard nodes in `tests/test_report.py` (all 13, chunk-32 §8.2 list):

1. `test_build_dashboard_layout_is_deterministic_for_a_fixed_view`
2. `test_build_dashboard_app_layout_matches_the_layout_builder`
3. `test_dashboard_layout_shows_every_primary_table_column_by_default`
4. `test_dashboard_detail_panel_covers_rpt_030_items_for_a_selected_category`
5. `test_dashboard_layout_keeps_refused_categories_visible_and_off_the_scored_axis`
6. `test_dashboard_layout_includes_the_heuristic_statement`
7. `test_dashboard_charts_carry_explanations_and_human_labels`
8. `test_dashboard_distinguishes_null_from_explicit_zero`
9. `test_dashboard_has_no_confidence_interval_or_error_bars`
10. `test_dashboard_policy_bump_and_kpi_tiles`
11. `test_dashboard_score_bar_encodes_ordinal_evidence_grade`
12. `test_dashboard_omits_the_coverage_heatmap`
13. `test_html_output_is_self_contained_and_deterministic`

Plus:

- `tests/test_report.py::test_dashboard_css_is_declared_as_package_data`
- `tests/test_report.py::test_dashboard_app_serves_the_package_assets_folder`
- `tests/test_report.py::test_dashboard_uses_progressive_disclosure_without_dropping_mandated_content`
- `tests/test_report.py::test_public_report_functions_have_hints_and_docstrings`
- `tests/test_end_to_end.py::test_acceptance_rendered_report_contains_required_fields`
- `tests/test_quality_tooling.py::test_report_module_has_no_forbidden_imports_or_clock_reads`

### 9.5 Fixtures

No new arithmetic, so no new golden vector. Reuse
`tests/fixtures/report_fixtures.py::dashboard_rows()` through `_dashboard_view(tmp_path)`
(`test_report.py:1185`) for the nav, Column-guide, and automargin nodes. No fixture
credentials, no network, no live path.

---

## 10. Files touched (the plan's file-discipline list)

- `src/niche_scout/assets/dashboard.css` — new palette, evidence scale, type/weight tokens,
  ellipsis on `.dash-cell`/`.dash-header`, nav/rail/top-bar/skip-link/`:target`/
  `scroll-margin-top`/focus styles, `.column-guide`.
- `src/niche_scout/report.py` — `_base_layout` margin + `automargin`; `_EVIDENCE_GRADE_COLOURS`
  (LR1); new private helpers `_dashboard_nav()`, `_column_guide()`; new presentational ids on
  the run-header/chart-grid/primary-table-section/detail-section containers; `Main(id="main-content")`
  wrapper; the nav inserted in `build_dashboard_layout`.
- `tests/test_report.py` — five new nodes (§9.1); amended `_DASHBOARD_CSS_HEXES`/`_DASHBOARD_CSS_TOKENS`/
  `_DASHBOARD_CSS_CLASSES` (§3, §9.2).
- `tests/traceability.json` — five new keys (§9.3).

No other file is in scope. Any other file needing a change is a stop-and-flag. (Run log
`Documents/runs/chunk-33.md` and the interface delta, if any, are the lead's, not the
planner's or implementer's.)

---

## 11. Definition of Done / gate bullets

- [ ] `python -m pytest -q` — full suite green: five new nodes pass; all §9.4 pinned nodes
      still pass; no other tree changes.
- [ ] `python -m niche_scout.tools.validate_traceability` — exit 0; each new node has a
      marker and a matching key; no orphan entry.
- [ ] `python -m niche_scout.tools.check_import_boundaries` — exit 0 (`metrics.py`/
      `scoring.py` untouched; `report.py` gains no forbidden import).
- [ ] `python -m niche_scout.tools.check_scope_prohibitions` — exit 0.
- [ ] `ruff format` and `ruff check` clean on changed Python files (`pyproject.toml:30–38`;
      the CSS is not linted).
- [ ] `dashboard.css` contains the ten new token hexes and none of `#f2c14e`; defines the
      size/weight tokens (§5); contains no `http://`/`https://`/`@import`/`url(`.
- [ ] The nav renders as an icon rail (≥1024px) / top bar (mobile); skip link is first and
      focusable; all five anchors resolve; each nav item has a visible text label; inline
      SVG present (LR2 verification with Kilo Playwright recorded).
- [ ] Exactly one `column-guide` `Details` lists all 30 `_PRIMARY_COLUMNS` labels; the
      DataTable default columns are unchanged; `.dash-cell`/`.dash-header` show ellipsis.
- [ ] Category-axis figures set `automargin: True`; the shared margin `l` is no longer 140.
- [ ] `_EVIDENCE_GRADE_COLOURS` equals the LR1 four values in `EVIDENCE_GRADE_ORDER` order.
- [ ] `report.py` imports no `metrics`/`scoring`/`collector*`/`config`/`pipeline`/`cli` and
      reads no clock; no new Dash callback; every `DASHBOARD_COMPONENT_IDS` id preserved.
- [ ] No file outside §10 changed.

---

## 12. Lead rulings (freeze, 2026-10-01)

- **LR1 — evidence scale.** Evidence ordinal scale becomes `insufficient #C98B8B` /
  `weak #E0A458` / `moderate #8FB0BF` / `strong #46B688`, and `_EVIDENCE_GRADE_COLOURS`
  (`report.py:273`) is updated to match. The four values are asserted in a new test
  (`test_dashboard_evidence_scale_is_retuned_to_the_reference_palette`).
- **LR2 — inline SVG mechanism.** Icons are inline SVG emitted through
  `dcc.Markdown(..., dangerously_allow_html=True)`, because Dash 4.4.1 `dash.html` has no
  SVG components. After implementation the lead confirms with Kilo Playwright that the SVG
  renders in the served page; the implementation provides a CSS-styled text fallback (the
  nav item's visible text label) so navigation works even if the SVG does not render.
- **LR3 — anchor ids.** New presentational anchor ids may be added to existing section
  containers; every existing id in `DASHBOARD_COMPONENT_IDS` is preserved unchanged, and
  `test_build_dashboard_app_layout_matches_the_layout_builder` stays green.
- **LR4 — full-text path for clipped table headers.** A native `<details>` "Column guide"
  disclosure placed directly above the primary table lists all 30 column labels verbatim
  with their meaning; it is keyboard- and pointer-operable and removes/renames no column.
  `text-overflow: ellipsis` is added to `.dash-cell`/`.dash-header`. The uppercase transform
  is retained (no test depends on removing it); the Column guide carries the full text.
- **LR5 — active section (clarified 2026-10-01).** Active-section indication is CSS-only.
  The unconditional marker is `:target` on the destination section (an `--accent` left
  border/outline). The active **nav link** marker uses `:has()` inside an
  `@supports selector(:has(*))` guard, with the `:target`-on-section marker as the fallback
  when `:has()` is unsupported. There is **no JS, no `aria-current` mutation, and no Dash
  callback** for navigation; `scroll-margin-top` provides the sticky offset. The `:has()`
  guard plus fallback is the resolved form of the earlier "non-`:has()` fallback" wording.

---

## 13. Evidence walk for the countable claims in this plan

- **Nine semantic tokens / ten new hexes** — run-log R1 table **(read)**; unit: distinct CSS
  custom-property names / distinct hex values.
- **Four evidence colours (LR1)** — lead ruling; unit: distinct hex values, asserted in the
  new evidence node.
- **`_base_layout` margin `l: 140`** — **(read:** `report.py:1418`; the dict is
  `report.py:1411–1423`).
- **Affected figure builders** — **(read:** `_score_bar_figure` `report.py:1484–1486`,
  `_population_lollipop_figure` `report.py:1612–1614`, `_contribution_figure`
  `report.py:1512–1514`; unit: builder functions).
- **30 primary columns** — **(read:** `test_report.py:1399` asserts `len(names) == 30`;
  `report._PRIMARY_COLUMNS` at `report.py`; chunk-31 plan §13). The Column guide lists the
  same 30.
- **Dash 4.4.1 has no SVG html components** — **(read:** `dash/html/_imports_.py` and the
  `dash/html/` file listing contain no `Svg`/`Path`/`Circle`/`Rect`/`Polyline`;
  `dash/dcc/Markdown.py:44` declares `dangerously_allow_html`).
- **`tests/traceability.json` format** — **(read:** `:2`, `:1472`, `:1481`; node-ID →
  LREQ list). `tests/AGENTS.md` prose is **stale**.
- **Contrast ratios** — hand-computed with the WCAG relative-luminance formula
  (`L = 0.2126R + 0.7152G + 0.0722B` on linearised sRGB; ratio `(L_light+0.05)/(L_dark+0.05)`;
  `--surface #112D3B` `L≈0.0231`): `--fg` 12.4:1, `--muted-fg` 6.2:1, `--primary` 6.9:1,
  `--accent` 5.7:1, `--positive` 5.8:1, `--danger` 5.0:1; evidence fills 5.2–6.6:1.
  **(hand-computed; reproducible from the formula; not tool-verified this session.)**
- **Pinned node line numbers** — **(read:** `tests/test_report.py:1362`, `:1376`, `:1390`,
  `:1405`, `:1433`, `:1460`, `:1472`, `:1495`, `:1541`, `:1557`, `:1602`, `:1627`, `:941`;
  `tests/test_end_to_end.py` acceptance node). Unit: 1-based line numbers.
- **`ui-ux-pro-max` citations** — read directly from the bundled CSVs (the CLI could not run
  in the planning environment: bash denied by the global permission rule). Cited by
  file:line in §4.3, §5, §6.2, §7.

---

## 14. Open questions

None. LR1–LR5 in §12 resolve every decision this plan raised. No SRS gap remains open for
chunk 33. (The standing obligations — URI trailing-identifier extraction, OI-6,
`runs.taxonomy_sha256` — are unchanged and are not chunk 33's.)