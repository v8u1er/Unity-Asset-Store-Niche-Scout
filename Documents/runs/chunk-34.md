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
| Implement — `impl-deep` | DONE | `report.py` + `dashboard.css`; one plan erratum found (leaf-label expectation contradicted §5.2), plan + test corrected in place; commits `chunk-34: implementation`, `chunk-34: tests (leaf-label erratum)`, `chunk-34: plan erratum (leaf-label expectation)` |
| Lead verification | DONE | pytest 761 passed; validate_traceability exit 0; import boundaries + scope prohibitions exit 0; ruff format/check clean; live Playwright re-audit below |
| Review — `spec-reviewer` (round 1) | DONE | `VERDICT: FAIL` — 1 Major (tests not ruff-format clean), 3 Minors (refused label full path; measured-zero hover lacks full path; §6.3 SQLite probe unrecorded). No Blocker |
| Review fix round 1 | DONE | Major + the two label/hover Minors fixed; probe Minor resolved as N/A with runtime evidence; commits `chunk-34: review fixes (format + refused/zero leaf guards)`, `... (refused leaf labels + zero hover)`, `... (rankable zero-population vector)` |
| Lead re-verify (round 1) | DONE | pytest 761 passed; validators exit 0; ruff format/check clean on all three changed test/src files; live re-audit below |
| Review — `spec-reviewer` (round 2) | DONE | `VERDICT: PASS` — all four round-1 findings resolved; one new cosmetic Minor (spacer hover), fixed in commit `chunk-34: review fixes (refused hover spacer wording)` |
| Gate | PENDING | |

## Reviewer round 2

`VERDICT: PASS` with one new cosmetic Minor: the refused annotation's leading `" "` spacer row
shared the refused hover template, so the spacer printed `" : n/a"`. Accepted and fixed
(`report.py`: hover now `"%{y}<br>category: %{customdata[0]}<extra></extra>"`, giving the spacer
`" "` and refused rows `<leaf> (refused)`); commit `chunk-34: review fixes (refused hover spacer
wording)`. Re-verified: `ruff format --check src/niche_scout/report.py` → "1 file already
formatted"; `pytest tests/test_report.py -q` → 55 passed; `pytest -q` → 761 passed.

Reviewer round-2 residual notes: `ruff check` on the changed files could not be re-run by the
reviewer (environment tool-permission denial), but the lead ran it clean; the §6.3 probe
disposition was accepted (no `traces` table exists).

## Reviewer round 1 and fix round 1

Reviewer `VERDICT: FAIL` (commit `d0ca884` state), findings and dispositions:

- **[Major] `tests/test_report.py` not ruff-format clean** (`_relative_luminance` generator, plan §12 /
  `LREQ-NFR-060`). **Fixed**: reformatted in place; `ruff format --check tests/test_report.py` →
  "1 file already formatted".
- **[Minor] `report.py:1759` refused annotation kept full taxonomy paths** (plan §1.1/§5.2).
  **Accepted and fixed** (operator item 1 is explicit; §1.1 says every chart category label, axis
  and hover, is the leaf). Lead-authorised in-scope minor remediation, guarded by two new
  in-place assertions on the existing leaf-label node (node ID/marker/key unchanged).
- **[Minor] `report.py:1899` measured-zero trace hover had no full-path field** (plan §5.2
  hover-collision-safety). **Accepted and fixed**, same guard node.
- **[Minor] §6.3 SQLite marker probe has no recorded evidence.** **Resolved as not applicable**:
  the plan's probe is `SELECT DISTINCT marker->>'symbol' FROM traces`, but the schema has **no
  `traces` table** — `database.py` declares only `runs`, `raw_discovery_observations`,
  `sample_members`, `enrichment_observations`, `category_scores` (`database.py:87,111,134,153,179`)
  plus `schema_metadata`. Charts are built in `report.py` and never persisted as traces, so the
  probe cannot run. Equivalent **runtime evidence** taken instead (Kilo Playwright, live figure
  state): the only explicit marker `symbol` in any of the five figures is `diamond-open`, on the
  population `measured zero` trace; all other traces carry no `symbol`.

Fix-round commands (lead-run): `python -m pytest -q` → **761 passed**;
`validate_traceability` / `check_import_boundaries` / `check_scope_prohibitions` → exit 0;
`python -m ruff format --check src/niche_scout/report.py tests/test_report.py tests/fixtures/report_fixtures.py`
→ "3 files already formatted"; `python -m ruff check` on the same three → "All checks passed!".

Live re-audit after the fix (0 console errors):

- Score-bar refused annotation `y` = `[" ", "creatures (refused)", "humanoids (refused)",
  "furniture (refused)", "weapons (refused)", "air (refused)", "land (refused)"]`; each row's
  `customdata` holds the full path (`3d/characters/creatures`, …) and the hover is
  `"%{y}: n/a<br>category: %{customdata[0]}<extra></extra>"`.
- Population `measured zero` trace `customdata` holds the full paths and hover is
  `"%{y}: measured 0<br>category: %{customdata[0]}<extra></extra>"`; marker `symbol` `diamond-open`.
- Mobile (375×800): link width 37.5 px, link center x 26.7 = icon center x 26.7 — centered.
- Re-confirmed at 1440×869: no `gtitle`; tick font mono; single-series legends empty; 30 headers.

## Lead verification (2026-10-01, after implementation)

Commands (real output):

- `python -m pytest -q` → **761 passed, 32 warnings in 32.00s**.
- `python -m niche_scout.tools.validate_traceability` → "Traceability valid: 89 required/defined
  LREQ IDs mapped, 740 matrix nodes, 0 unmarked analytical tests outside exemption (3 exempted
  non-analytical tests)" — exit 0.
- `python -m niche_scout.tools.check_import_boundaries` → exit 0.
- `python -m niche_scout.tools.check_scope_prohibitions` → exit 0.
- `python -m ruff format --check src/niche_scout/report.py` → "1 file already formatted";
  `python -m ruff check src/niche_scout/report.py` → "All checks passed!".

Live re-audit (Kilo Playwright, viewport 1440×869, run `run-2026-09-30T12:49:08.901818+00:00`,
0 console errors):

| Item | Evidence (measured) |
|---|---|
| 1 leaf labels | Score-bar / population / contribution y-ticks show leaves: `exterior`, `interior`, `guns`, `nature`, `environment`, `spells`, … Full paths still in the table cells and section text. Colliding leaves disambiguated: `fantasy · 3d/environments`, `fantasy · 3d/characters/humanoids`. |
| 2 font | Tick font computes to `ui-monospace, "Cascadia Mono", "Cascadia Code", Consolas, SFMono-Regular, Menlo, monospace` (was `"Open Sans", verdana, arial`) on all five charts. |
| 3 legends | *Composite score by rank* → `legendItems: []`; *Composite score vs quality* → `legendItems: []`. The three meaningful charts keep legends. |
| 4 population | Legend now 3 short items (`discovered population`, `measured zero`, `sample size`) below the plot; plot box 234.5×225.5 px in a 390.3×360 px wrapper, legend 193×67 px at y 1534–1601, clear of the plot bottom (1503.5). |
| 5 palette | Contribution trace colours `#9fd7ea / #b9dbb0 / #d5dd93 / #e6d489` (= `_RAMP_HEXES` in D/C/R/Q order). Policy bump 18 series cycle the same four stops for both `line.color` and `marker.color`; first trace `mode "lines+markers+text"`, direct label. Population `discovered population #9fd7ea`, `sample size #b9dbb0`, out-of-line `measured zero #e27882` (`--danger`). Scatter `#9fd7ea`. No test asserted `_RAMP_HEXES` against `report` before implementation (the new node did), so the implementation is the first writer. |
| 6 table | Still **30** headers; first 7 `column_id`s (`category`, `rank`, `market_opportunity_score`, `component_d/c/r/q`) carry no de-emphasis inline style; the remaining 23 carry `font-weight: 400; opacity: 0.82` (23 secondary headers matched). DataTable freeze is present as `dash-fixed-content` (the fixed-column wrapper class in this Dash build). |
| 7 nav | Link width 64 px in the 73 px rail; link center x 36.0, icon center x 36.0 — **centered** (was +7.5 px). Mobile top bar left unchanged (intrinsic width). |
| 8 titles | No `gtitle` in any of the five plots (card `H3` only). |

Residual observations (recorded, not blocking):

- The three chart refreshes are client-side Dash updates; the lead's full-suite and live checks
  confirm behaviour, but the population chart's responsive reflow on viewport change was not
  re-measured beyond 1440×869 and 375×800.
- The policy bump keeps its 18-item legend (plan decision: legend retained, direct labels added);
  the legend is still long, but the direct labels now carry identification, which was the
  skill-grounded fix. If a future chunk wants the legend hidden, that is a new scope decision.

## Gate walk (plan §12 bullets, evidence one by one)

| # | Gate bullet | Evidence | Result |
|---|---|---|---|
| 1 | `pytest -q` green; six new nodes; pinned nodes green; amended nodes pass amended | lead `python -m pytest -q` → 761 passed (run after the final commit) | PASS |
| 2 | `validate_traceability` exit 0; new nodes marked + keyed | exit 0; "740 matrix nodes, 0 unmarked"; six new keys | PASS |
| 3 | `check_import_boundaries` exit 0 | exit 0 | PASS |
| 4 | `check_scope_prohibitions` exit 0 | exit 0 | PASS |
| 5 | ruff format/check clean on changed Python files | `ruff format --check` on the three files → "3 files already formatted"; `ruff check` on the three → "All checks passed!" (lead, post-fix) | PASS |
| 6 | Leaf-only ticks/hover; full path in table/guide/selector/detail; collision `leaf · parent` for the whole group | live: ticks `exterior`, `interior`, `guns`, …; refused `creatures (refused)`, hover `category: 3d/characters/creatures`; colliding `fantasy · 3d/environments`, `fantasy · 3d/characters/humanoids`; table cells + detail show full paths; test node green | PASS |
| 7 | {score bar, scatter} `showlegend False`; other three keep; population legend horizontal below; no `layout.title` | live: both `legendItems []`; population legend below plot (193×67 at y 1534–1601, plot bottom 1503.5); no `gtitle` in any figure | PASS |
| 8 | All five figures: mono numeric ticks, sans axis titles; no web font/URL | live tick font `ui-monospace, "Cascadia Mono", …` on all five; `--font-sans` axis titles; offline scan clean | PASS |
| 9 | `_EVIDENCE_GRADE_COLOURS` == four ramp stops; CSS same; no retired hexes | live bar/contribution colours `#9fd7ea/#b9dbb0/#d5dd93/#e6d489`; CSS tokens asserted; `check_scope_prohibitions` exit 0 | PASS |
| 10 | Policy series `i` sets line+marker to `_RAMP_HEXES[i % len]` | live 18-series cycle `#9fd7ea/#b9dbb0/#d5dd93/#e6d489` repeated, line == marker; node green | PASS |
| 11 | DataTable freezes 7; 23 secondary conditionals; 30 columns unchanged, no removal/rename/reorder | live: 30 headers; first 7 `column_id`s carry no de-emphasis style; 23 secondary carry `font-weight: 400; opacity: 0.82`; `fixed_columns` present (`dash-fixed-content`) | PASS |
| 12 | `.nav-link { box-sizing: border-box }`; desktop rail no longer overflows | live desktop: link 64 px in 73 px rail, link center 36.0 == icon center 36.0 (was +7.5 px); mobile centered 26.7 == 26.7 | PASS |
| 13 | No forbidden import; no clock; no new callback; ids preserved | `check_import_boundaries` exit 0; no new callback; `DASHBOARD_COMPONENT_IDS` unchanged | PASS |
| 14 | `.scratch/` SQLite marker probe → one symbol `diamond-open` | **N/A as written**: no `traces` table exists (`database.py` tables only) so the probe cannot run; equivalent runtime evidence — the only explicit marker `symbol` across the five figures is `diamond-open` (population measured-zero), verified live | PASS (substituted) |
| 15 | No file outside §11 changed | commit scopes: only `report.py`, `dashboard.css`, `test_report.py`, `report_fixtures.py`, `traceability.json`, plus lead-owned `Documents/runs` + plan erratum | PASS |

**GATE: PASSED** (2026-10-01). Bullet 14 is marked **substituted**: the plan's probe targets a
`traces` table that does not exist in the schema; the runtime DOM check the reviewer accepted
covers the same intent (exactly one marker symbol, `diamond-open`). No bullet is unmet.

## Final commit list (chunk-34)

- `52b3476` preflight, live dashboard audit, skill evidence, run log
- `9be21d5` plan (frozen) · `fbd1126` plan erratum (leaf-label expectation)
- `c393a3d` tests (red) · `9aa9f86` tests (leaf-label erratum) · `d0ca884` review fixes (format + refused/zero leaf guards) · `32df676` review fixes (rankable zero-population vector)
- `c15c958` implementation · `81cc9ca` review fixes (refused leaf labels + zero hover) · `81acb04` review fixes (refused hover spacer wording)
- `dc09e8c`/`915e6d9`/`faface8`/`45ad5fa` run-log stage records

## Open items carried forward

- Reviewer Minor (round 2, fixed): refused spacer hover wording — closed.
- chunk-33 reviewer Minors still open (not chunk 34): `--font-size-numeric-md` defined but unused;
  `tests/test_report.py` above the 800–1,000-line report trigger (report item; split is a human
  scope decision).
- Standing obligations unchanged: URI trailing-identifier extraction, OI-6 CSRF sufficiency,
  `runs.taxonomy_sha256` empty-hash rejection (Chunk 10).

## Gate

| Stage | Status | Notes |
|---|---|---|
| Gate | PASSED | all 15 plan §12 bullets evidenced; bullet 14 substituted with runtime equivalent (no `traces` table) |
