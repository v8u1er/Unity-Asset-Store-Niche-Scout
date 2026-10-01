# Chunk 34 — chart label/legend/font/color remediation + compliant table prioritization + nav centering (run log)

New remediation/feature chunk, not in `Documents/requirements-dependency-map.md` §3/§4
(chunk-14 / chunk-30 / chunk-31 / chunk-32 / chunk-33 precedent: registration = plan + run
log + branch). Do not edit the dependency map, the SRS, `AGENTS.md`, or `.kilo/`.

Branch: `chunk-34`, created from `main` @ `ad0bb70` (`chunk-33: gate PASSED; run log`).

## Origin

Operator request (2026-10-01, follow-up to chunk 33), verbatim intent — seven items:

1. Category names too long: show the **last path segment only** in charts, with the whole
   category name in a tooltip if that makes sense.
2. The **axis-label font** is disliked; consult `ui-ux-pro-max` for alternatives.
3. *Composite score by rank* and *Composite score vs quality* have a useless single-item
   legend (`trace 0`) that wastes space.
4. *Population and sample size* chart area is squished by a wide legend; optimize heavily.
5. Chart curve colors should be **analogous** — pastel cyan → pastel yellow; use a
   contrasting color only where it carries meaning (error / out-of-line data); respect
   contrast rules.
6. The table has too many columns; analyze and remove unimportant ones.
7. Sidebar icons are **not centered**.
8. (Lead-observed, not requested) every chart title is duplicated — card `H3` plus an
   identical in-plot Plotly title.

Lead ruling on item 6 (operator, 2026-10-01): **compliant visual prioritization** — all 30
`LREQ-RPT-020` columns stay in the DOM; no column is removed (option A). Reason: SRS
§10 `LREQ-RPT-020` (line 1163, **(read)**) mandates the 30-field primary table and
`Documents/interfaces/chunk-11.md` §7 states "the primary table shows **all**
`LREQ-RPT-020` labels by default". The operator declined an SRS amendment.

## Preflight

| Check | Result |
|---|---|
| Working tree | `.kilocode/`, `cssbase.py` (empty file), `out.html` untracked note: `cssbase.py` is a pre-existing untracked empty file at the repo root, not authored by this chunk. — pre-existing, from chunk 32/33 scratch; not staged. No tracked file modified. Accepted and recorded (chunk-33 precedent). |
| Branch | `main` @ `ad0bb70` → `chunk-34` |
| Prerequisite Chunk 33 | `Documents/runs/chunk-33.md` → `GATE: PASSED`; plan FROZEN |
| Prerequisite Chunk 11/12/30/31/32 | chunk-33 run log preflight rows (all PASSED / VERIFIED) |
| Appliance | `python -m niche_scout dashboard` started once as a session-lifetime background process (loopback 8050); single server only (single-writer rule) |
| Routing | `chunk-planner` → `test-author` (tests-first, `LREQ-RPT-010`) → `impl-deep` → lead verify → `spec-reviewer` → gate |

## Live-dashboard audit (lead; Kilo Playwright against the running app)

Viewport **1440×869**; measured with `browser_evaluate` on the real DOM; **0 console
errors**. Run shown: `run-2026-09-30T12:49:08.901818+00:00` (25 categories; 18 rankable,
7 refused).

### Measured findings

1. **Category labels are full taxonomy paths.** Chart ticks/legends read
   `vfx/shaders/fullscreen-camera-effects`, `2d/textures-materials/sky`, etc. — not the
   leaf. The category axis title is literally `category`.
2. **Axis font is not a deliberate token.** Every Plotly tick **and** axis title computes
   to `"Open Sans", verdana, arial, sans-serif` (Plotly's default), while the UI uses
   `system-ui, "Segoe UI", …`. Open Sans is not loaded offline, so glyph fallback is
   whatever the OS supplies.
3. **Single-item legends confirmed.** *Composite score by rank* legend items = `["trace 0"]`;
   *Composite score vs quality* = `["trace 0"]`. Toggling is meaningless with one series
   and the legend consumes plot area.
4. **Population chart legend is wide.** Three long items —
   `discovered population (observed)`, `discovered population: measured zero`,
   `sample size (observed)` — render inline in a ~390px-wide plot's SVG.
5. **Colors are partly still hard literals, partly default.** Measured trace colors:
   score bar `["#e0a458", "#8fb0bf"]` (evidence literals); population `#64bcfb` / `#46b688`;
   scatter `#48b78d`; **contribution and policy-bump traces carry no explicit color**, so
   they use the Plotly default colorway. Contrast budget (hand-computed, WCAG
   relative-luminance on sRGB, surface `#112D3B` `L≈0.0231`): `#64bcfb` ≈6.9:1,
   `#46b688` ≈5.7:1, `#48b78d` ≈5.8:1, `#e0a458` ≈6.6:1, `#8fb0bf` ≈6.2:1 — all ≥3:1 for
   non-text UI and ≥4.5:1 for adjacent text. **(hand-computed; not tool-verified.)**
6. **Primary table = exactly 30 headers** (`dash-header .column-header-name`, counted):
   identical to `report._PRIMARY_COLUMNS` in label and order.
7. **Nav icons are off-center (confirmed, geometry).** Desktop rail `width 73px`
   (64px + 2×4px padding + 1px border); `.nav-link` computes `inline-size: 100%` **plus**
   `padding: 4px 8px` under `box-sizing: content-box`, so the link is **80px** wide and
   overflows the rail by ~7px. Measured icon center `cx 44.0` vs rail center `36.5` →
   **+7.5px right of center**. Mobile top bar (375px): link `w 37.5`, icon `cx 26.7`,
   link `cx 26.7` — centered (defect is desktop-only).
8. **Chart titles are duplicated.** For all five charts the card `H3` text equals the
   in-plot Plotly `layout.title.text` (e.g. "Composite score by rank" twice). Chunk-33
   audit finding 8, never fixed.
9. **Policy bump legend is category-length noise.** 18 series in the legend list
   (`vfx/particles/environment` … `3d/characters/humanoids/fantasy`), plus the in-plot
   legend overlapping the markers band. Skill `charts.csv` "Trend Over Time" rule
   ("more than 6 series (visual noise)"; direct series labels preferred).

### What was verified vs not

- The live page, computed fonts/colors, legend items, header count, nav geometry, and
  console errors were **measured** with Kilo Playwright against the running app.
- Contrast ratios are **hand-computed** from the WCAG formula, not measured by a tool.
- Whether the specific leaf-collision cases (two categories sharing a leaf) occur in this
  run is **unverified**; the fix is specified to be collision-safe regardless.

## Skill evidence (`ui-ux-pro-max`; lead ran the CLI)

Commands run by the lead (permitted in this environment):

- `search.py "analogous pastel chart color palette sequential" --domain color -n 5`
  → **0 database matches** for that phrase (stated as such; closest known terms are
  unrelated). Chart color guidance therefore comes from the `chart` domain below plus
  hand-computed WCAG arithmetic.
- `search.py "line chart multiple series legend direct labels" --domain chart -n 8`
  → "Trend Over Time": **"more than 6 series (visual noise)"**; Color Guidance "multiple
  series: distinct colors + distinct line styles"; Accessibility Notes "use solid, dashed,
  and dotted line styles plus direct series labels; never distinguish series by hue
  alone." "Compare Categories": "Each bar: distinct color. **Always sort descending by
  value**"; a11y "use direct category/value labels … never encode category solely by bar
  color." "Correlation/Distribution": scatter/bubble, opacity 0.6–0.8, "combine marker
  shapes with direct group labels; color may reinforce but must not be the only
  distinction." "Part-to-Whole": ≤5–6 colors, "contrasting palette". "Anomaly Detection":
  "Normal: solid line. **Anomaly marker**: distinct **shape** + text annotation as well as
  color."
- `search.py "chart legend single series redundant remove" --domain ux -n 8`
  → no legend-specific guidance matched (returned Redundant Entry / Dragging Movements).
  **No verified database match**; the single-series legend decision is grounded in the
  `chart`/typography guidance above and in `SKILL.md` AGENTS "Charts" do/don't (below).
- `search.py "dashboard data monospace axis labels" --domain typography -n 6`
  → Font Pairing **"Dashboard Data"** (Category Mono + Sans; Heading Fira Code, Body Fira
  Sans; keywords dashboard/data/analytics/precise; Notes "**Code for data, Sans for
  labels**"). The pairing's Google-Fonts `@import` is **rejected** under the offline rule
  (E-4); the local/system stacks already in `dashboard.css` are the compliant
  implementation of "mono for data, sans for labels".
- `search.py "sidebar icon alignment navigation" --domain icons -n 6`
  → `sidebar`, `house`, `list`, `columns` (Phosphor outline). `SKILL.md` rule
  **"Icon Alignment: Align icons to text baseline and maintain consistent padding"** and
  **"Consistent Icon Sizing"**; **"Icon Contrast"** meaningful icons ≥3:1.
- `search.py "dark mode dashboard categorical color contrast" --domain color -n 8`
  → eight dark-mode product palettes; every one pairs a dark `#0F172A`/`#020617`/`#0E1223`
  surface with light foreground and a saturated accent, and uses **distinct
  status colors** (green positive / red destructive / amber queued) with notes like "dark
  tech + status green", "running green + failed red + queued amber". This supports a
  sequential analogous curve ramp **plus** one reserved contrasting status color.

Decision impact: leaf-only labels with a full-path access path; mono for numeric ticks and
sans for axis titles/labels; drop meaningless single-item legends; move the population
legend below the plot; one analogous cyan→yellow sequential ramp for curves and the bars
(rank-ordered) with direct labels, reserving a contrasting danger-family color **with a
distinct marker shape** for out-of-line states (refused / measured zero); fix nav centering
with `box-sizing`; stop duplicating chart titles; prioritize the 30-column table without
removing any column.

## Hard constraints (carried from chunk 31/32/33)

- **Offline/no-CDN is non-negotiable**: no external URL, CDN, `@import`, or web font.
  The Fira pairing is rejected; local/system stacks only.
- **Content preserved**: no `LREQ-RPT-020` column, no `LREQ-RPT-030` item, no
  `LREQ-RPT-050` string, and no Appendix C code may be removed from the DOM.
- **Purity**: `report.py` imports no `metrics`/`scoring`/`collector*`/`config`/`pipeline`/
  `cli`; no clock read; layout deterministic for a fixed view.
- **No live network / no `niche-scout run`** in development or tests.
- Chunk-33 pinned tests must stay green unless this chunk's plan explicitly supersedes them.
- A chart label must never change a number, a rank, or a measured value; the full category
  name stays available (table cell, detail, hover).

## Operator-authorized decisions

- **Authorize item 6 as compliant visual prioritization (option A)**: no `LREQ-RPT-020`
  column is removed; the SRS and interface §7 are untouched.
- **Authorize the analogous pastel cyan→yellow ramp for chart curves/bars**, with a
  contrasting danger-family color reserved for out-of-line data.
- **Authorize leaf-only chart labels** with the full path retained in the table/detail and
  in hover.
- **Keep offline/non-CDN**, purity, and all chunk-33 content-preservation guarantees.

## Stage log

| Stage | Status | Notes |
|---|---|---|
| Preflight (lead) | DONE | tree pre-existing untracked only; `chunk-34` from `ad0bb70`; this log |
| Live dashboard audit (lead, Kilo Playwright) | DONE | 9 measured findings above; background process `bgp_0f77dd04e001EZ87j1DnbMq8gX` |
| Skill CLI (lead) | DONE | six queries above; the color-phrase query returned 0 matches (recorded) |
| Plan — `chunk-planner` | DONE | plan frozen; three lead-verified corrections (DataTable `fixed_columns` + inline conditionals; hover customdata normalization; trace-name claim); commit `chunk-34: plan (frozen)` |
| Tests — `test-author` | DONE | six new §10.1 nodes + §10.2 (a)–(g) amended in place; two fixture names + `__all__`; six `traceability.json` keys; red step 12 failed / 43 passed; commit `chunk-34: tests (red)` |
| Implement — `impl-deep` | PENDING | |
| Lead verification | PENDING | |
| Review — `spec-reviewer` | PENDING | |
| Gate | PENDING | |

## Open items carried forward

- chunk-33 reviewer Minors still open: `--font-size-numeric-md` defined but unused
  (not chunk 34's to resolve unless the plan touches it); `tests/test_report.py` above the
  800–1,000-line report trigger (report item; split is a scope decision for a human).
- The three standing obligations (URI extraction, OI-6, `taxonomy_sha256`) remain untouched.
