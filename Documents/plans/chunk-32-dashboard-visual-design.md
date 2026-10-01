# Chunk 32 — dashboard visual design system + progressive disclosure (plan)

Status: FROZEN — 2026-10-01. Q1–Q7 resolved by the lead in §12. Every section is
implementation-ready. Operator-authorized decisions D-1..D-5 (§2) are fixed; the lead fixed
the design tokens and style (§2) and ran the `ui-ux-pro-max` CLI for the record (§12 R2).

New remediation/feature chunk, not in `Documents/requirements-dependency-map.md` §3/§4
(chunk-14 / chunk-30 / chunk-31 precedent: registration = plan + run log + branch). Do not
edit the dependency map, the SRS, `AGENTS.md`, or `.kilo/`.

Branch: `chunk-32`, base `main` @ `0d3e459` (`chunk-31: gate PASSED; run log`).

Authority: `Documents/runs/chunk-32.md` (this chunk's log; origin, D-1..D-5, the lead's
critical audit, the fixed tokens), the frozen contracts it cites, and the operator request
(2026-10-01): use the `ui-ux-pro-max` skill to audit and enhance the dashboard — a remove
list, an enhance list, a palette, and a design language.

Predecessors merged and frozen: Chunk 11 (report renderer) → `interfaces/chunk-11.md`
`Status: VERIFIED`; Chunk 12 (CLI) → gate PASSED; Chunk 30/31 (Dash dashboard) →
`interfaces/chunk-11.md` §11. This chunk **amends** nothing in the frozen `report.py`
function surface; it adds a stylesheet, packaging, and progressive-disclosure markup, and
the **lead** records the delta in a new `interfaces/chunk-11.md` §12 (§6). The planner
edits no interface file.

SRS authority: `Documents/SRS-lean-v2.md` §10 `LREQ-RPT-010`..`LREQ-RPT-050`
(lines 1155–1189 **(read)**), §12 (structure/conventions), §14 (constants), §15/§16
(deferred scope, limitations), Appendix C (warning vocabulary). `AGENTS.md` Hard rules
1–4 and "Out of scope — do not add". Every countable claim is labelled **(read)**,
**(counted)** or **(unverified)** per project-rules "Plan review and audit"; the walk is
§13.

---

## 1. Scope, non-goals, LREQ roles

### 1.1 Scope (in)

1. **New stylesheet (D-1).** `src/niche_scout/assets/dashboard.css`: a dark, data-dense
   design system for the served Dash dashboard, covering every `className` in the layout
   tree (25 classes, §5.3) plus the Dash `DataTable` generated classes and the
   `dcc.Dropdown` react-select classes. Tokens, 12-col grid, KPI cards, chart cards,
   sticky/sortable table polish, badges, `:focus-visible` rings,
   `prefers-reduced-motion`, breakpoints 375/768/1024/1440, and a readable measure.
   **No external URL, font, `@import`, or CDN (D-4).**
2. **Packaging (D-1).** `pyproject.toml` gains
   `[tool.setuptools.package-data] niche_scout = ["assets/*.css"]` so the stylesheet ships
   in the built package **and** is present at `src/niche_scout/assets/dashboard.css` for
   the Dash default asset path.
3. **Progressive-disclosure markup (D-3).** In `src/niche_scout/report.py`, targeted
   markup only:
   - the `LREQ-RPT-050` statement is wrapped in a `<details>` with a short `<summary>`;
   - `_shared_formula_panel` becomes `open=False`;
   - the observed-versus-inferred list and the sample-strata table become `<details>`;
   - `_footnote` drops the bullets that only duplicate `_FORMULA_EXPLANATIONS`;
   - `build_dashboard_app` points Dash's `assets_folder` at the package `assets/` dir.
   Every SRS-mandated string stays in the DOM (`LREQ-RPT-020/030/040/050`; Appendix C
   codes). Nothing is deleted.
4. **Tests.** New pytest nodes proving the stylesheet exists, is non-empty, is offline,
   uses the fixed token set and class set, and is declared as package data; that the app
   serves the package assets folder; and that the disclosure change kept the mandated
   content. `tests/traceability.json` gains the matching keys.
5. **Interface delta (lead).** A new `Documents/interfaces/chunk-11.md` §12 documenting the
   assets folder and the disclosure markup; listed in §6, applied by the lead.

### 1.2 Non-goals (explicitly NOT in this chunk)

- **No content removal.** No `LREQ-RPT-020/030/040/050` string, no primary-table column,
  no Appendix C warning code, and no table/selector row is removed from the DOM.
- **No external dependency.** No new runtime dependency; no CDN, Google Fonts, `@import`,
  or scheme-bearing URL anywhere in this chunk's output (D-4).
- No historical/trend/multi-run view; no scheduling, resume/checkpoint, favorite-count,
  configurable weights, confidence intervals, or sales calibration
  (`AGENTS.md` "Out of scope"; `check_scope_prohibitions` tokens unchanged).
- No schema, pipeline, `metrics.py`, or `scoring.py` change; no metric recombination or
  data recomputation; the app renders persisted values verbatim.
- **No clock read in `report.py`** (chunk-32 adds none); no `metrics`/`scoring`/
  `collector*`/`config`/`pipeline`/`cli` import (purity unchanged).
- No change to the frozen public signatures of `build_dashboard_layout` /
  `build_dashboard_app`; no change to `render_run_report_html` / `render_run_report_text` /
  `write_run_report`; the **static** report path and its inline `_INLINE_CSS` are untouched.
- No change to the data model, figures, chart ids, component ids, callbacks, or the CLI.
- No new public constant or function beyond the private helpers in §4.

### 1.3 LREQ roles

| Role | LREQs |
|---|---|
| Primary | `LREQ-RPT-010` (one-command local read-only dashboard; offline styling and packaging), `LREQ-RPT-020` (primary table / read model), `LREQ-RPT-030` (category detail items retained under disclosure) |
| Supporting contract | `LREQ-RPT-040` (non-rankable categories stay visible), `LREQ-RPT-050` (heuristic statement present exactly once in the DOM) |
| Integration completion | `LREQ-NFR-040` (public builder type hints/docstrings: `build_dashboard_layout`/`build_dashboard_app` unchanged; private helpers also typed and documented), `LREQ-ARCH-010`/`LREQ-ARCH-020` (purity: `report.py` imports no forbidden module and reads no clock; `metrics`/`scoring` untouched) |

`LREQ-RPT-010` is the LREQ whose "local read-only dashboard launched by one command"
guarantee this chunk strengthens: the page becomes offline-styled rather than unstyled
white. The "self-contained / served locally" half is unchanged (chunk-31 §11).

---

## 2. Fixed design/behaviour inputs (from run log D-1..D-5 and the lead's tokens)

Quoted as the operative authority; the plan implements them and does not re-open them.

- **D-1 — implement now.** The operator authorized the design enhancement.
- **D-2 — skill-mandated.** The lead and every subagent SHALL use `ui-ux-pro-max` and cite
  its outputs. **The CLI could not be executed in this planning environment (bash and
  background-process are denied by a global permission rule; see §11 Q2).** The skill was
  loaded and its bundled **data files** were read directly; because `search.py` only
  queries those CSVs, the citations in §5.6 are the same concrete rows the CLI would
  return. `(read)` citations with file:line.
- **D-3 — content preserved.** No `LREQ-RPT-020/030/040/050` content or Appendix C code is
  removed; verbosity is reduced by progressive disclosure and styling only.
- **D-4 — offline preserved.** No external URL, CDN, or web font.
- **D-5 — new chunk 32**; chunks 30/31 are not edited in place beyond §7's file list.

**Fixed style (lead):** Data-Dense Dashboard (skill `styles.csv:29`). **Type structure:**
mono for numerics, sans for labels (skill `typography.csv:43` "Dashboard Data"),
implemented with an **offline system font stack** (the skill's Fira/Google-Fonts `@import`
is rejected under D-4; §5.6 conflict C1). **Palette:** one dark theme, because the five
Plotly figures and the ordinal evidence scale are already dark-tuned (`_base_layout`,
`report.py:1394`; `_EVIDENCE_GRADE_COLOURS`, `report.py:256`).

**Fixed tokens (lead; verbatim — the only colour source for the stylesheet):**

```
--bg #0B1120  --surface #1B2029  --surface-2 #222833  --border #2C3440
--fg #E6E9EE  --muted-fg #9AA6B2  --primary #6EA8FE  --accent #F2C14E
--positive #8FD694  --danger #E06C75
evidence (ordinal, existing figure scale): #c98b8b / #e0a458 / #8fb9a8 / #8fd694
```

**Design language (lead):** "data-dense dark analytics console" — 12-col grid, 8px rhythm,
semantic tokens, progressive disclosure, direct labels + text (never colour alone),
sortable table primary.

Chunk-31 invariants carried over unchanged: `view.heuristic_statement` verbatim;
non-rankable categories visible; null is `n/a` and never `0`; no confidence intervals or
error bars; coverage and `sample_fraction` distinctly labelled; thresholds/weights from
`models`/SRS §14.

---

## 3. Determinism contract (normative)

- **The stylesheet is a static file.** It is not read, hashed, or templated by any Python
  code; it cannot affect the layout tree. Two runs serve byte-identical CSS.
- `build_dashboard_layout(view)` remains pure: no clock, no network, no database, no RNG.
  The disclosure wrappers are deterministic (fixed text, fixed child order). Two calls
  with the same `view` build equal trees (compared after `to_plotly_json()`
  normalization), exactly as `test_build_dashboard_layout_is_deterministic_for_a_fixed_view`
  asserts.
- `build_dashboard_app(view)` remains a pure construction: it computes
  `_dashboard_assets_dir()` (a `Path` from `__file__`; no directory read), passes it to
  `Dash(...)`, and assigns the same layout. It calls no `app.run`, opens no network, and
  reads no clock **in this module**. Dash may stat the local assets folder during
  construction; that is Dash's own local-file behaviour, not a network or clock read.
- The disclosed content is present in the DOM regardless of a `<details>` element's
  `open` attribute, so `view.heuristic_statement in json.dumps(app.layout)` and the
  mandated-string assertions hold with equal content.

---

## 4. The testable seam (unchanged public signatures; new private helpers)

No public function signature changes. `build_dashboard_layout(view)` and
`build_dashboard_app(view)` keep the exact signatures frozen in
`interfaces/chunk-11.md` §5/§11.

New **private** module-level helpers (names, parameter types, return types, and
null/edge behaviour are exact; a test author can rely on them without the body):

```python
_DASHBOARD_ASSETS_DIRNAME: str = "assets"
"""Package-relative assets directory name (Dash default; made explicit at build time)."""

def _dashboard_assets_dir() -> Path:
    """Return the absolute package assets directory ``<report.py>/assets`` (no I/O).

    Computed from ``Path(__file__).resolve().parent / _DASHBOARD_ASSETS_DIRNAME``.
    Never reads the directory, never uses the clock. If the directory is absent the
    path is still returned (Dash reports the missing folder itself).
    """

def _disclosure(
    summary: str,
    children: Sequence[object],
    *,
    open: bool = False,
    className: str | None = None,
) -> "dash_html.Details":
    """Return a ``<details>`` with a visible ``<summary>`` and ``children`` verbatim.

    ``open`` defaults to ``False`` (progressive disclosure). ``children`` are rendered
    unchanged inside the disclosure, so every mandated string stays in the DOM. An
    empty ``children`` yields a summary-only details, never an omitted element.
    ``className`` is forwarded when provided.
    """

_HEURISTIC_SUMMARY: str = "What this score is and is not"
"""Always-visible one-line label for the LREQ-RPT-050 disclosure."""

def _heuristic_banner(view: RunReportView) -> "dash_html.Details":
    """Return the LREQ-RPT-050 statement inside a labelled disclosure.

    Renders ``view.heuristic_statement`` verbatim in a single ``P(className=
    "heuristic")`` under ``_HEURISTIC_SUMMARY``. The statement appears exactly once
    in the DOM; a persisted/empty statement is rendered as-is and is never replaced
    by a fallback or by ``HEURISTIC_STATEMENT``.
    """
```

Changed private functions (same signatures; bodies only):

```python
def _shared_formula_panel() -> "dash_html.Details":
    """The single shared formula/"how to read" panel (appears once; closed by default)."""
    # CHANGE: open=True -> open=False. Same summary text and same _FORMULA_EXPLANATIONS
    # children (each list item remains in the DOM exactly once).

def _detail_panel_children(view: RunReportView, row: CategoryReportRow) -> list:
    """LREQ-RPT-030 detail for one category (observed/inferred and strata disclosed)."""
    # CHANGE: the observed-versus-inferred <Ul> is wrapped in _disclosure("Observed
    # versus inferred", [...]); the sample-strata table is wrapped in
    # _disclosure("Sample strata", [_detail_strata(row)]). The prior H4 headings for
    # those two blocks are replaced by the disclosure summaries (same strings).
    # "Metric inputs", "Warnings", "Timestamps" H4s and all other children are unchanged.

def _footnote(view: RunReportView) -> "dash_html.Div":
    """The one shared footnote (n/a-vs-0 and the provisional notice only)."""
    # CHANGE: keep the "n/a is never 0" bullet and, when provisional, the provisional
    # notice; drop the two bullets that only restate _FORMULA_EXPLANATIONS #6/#7
    # (sample_fraction and stratum eligibility coverage). Coverage/sample-fraction
    # distinction stays in the statement, the formula panel, and the table.

def build_dashboard_layout(view: RunReportView) -> "dash_html.Div":
    # CHANGE: the header's P(className="heuristic") is replaced by _heuristic_banner(view).
    # Everything else (run header, KPI strip, chart grid, table, selector, detail panel,
    # footnote, className values) is unchanged.

def build_dashboard_app(view: RunReportView) -> Dash:
    # CHANGE: Dash(__name__, serve_locally=True, assets_folder=str(_dashboard_assets_dir()),
    # title=...)  — an absolute path so it resolves to the package dir regardless of cwd.
```

Edge-case contract for the changed surface:

| Case | Behaviour |
|---|---|
| empty `view.categories` | `_heuristic_banner` still renders the statement; detail panel keeps `P("No categories recorded.", className="missing")`; disclosure wrappers do not run for a missing row |
| `row.strata` empty | `_detail_strata` returns `P("n/a", className="missing")` inside the "Sample strata" disclosure — `n/a`, never `0`/omitted |
| `row.warnings` empty | `P("n/a", className="missing")` — unchanged |
| `view.heuristic_statement` empty | rendered as an empty statement inside the disclosure; never substituted |
| non-rankable row selected | detail panel renders as before; the row stays in the table and selector (`LREQ-RPT-040`) |
| assets dir missing | `_dashboard_assets_dir()` still returns the path; no exception in `report.py` |

---

## 5. The design system (tokens, layout, components, type, accessibility)

### 5.1 Tokens (required in `:root`)

Semantic colour tokens exactly as §2 (10), the four ordinal evidence colours
(`--evidence-insufficient/weak/moderate/strong` mapped to `#c98b8b/#e0a458/#8fb9a8/
#8fd694`), and non-colour tokens:

```
--font-sans: system-ui, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
--font-mono: ui-monospace, "Cascadia Mono", "Cascadia Code", Consolas,
             "SFMono-Regular", Menlo, monospace;
--measure: 72ch;                      /* readable prose measure (ux:110/111) */
--space-1..6: 4,8,12,16,24,32px;      /* 8px rhythm (style:29) */
--radius: 8px;
--chart-height: 360px;                /* mirrors report._DASHBOARD_CHART_HEIGHT */
--focus-ring: 2px solid var(--primary); --focus-offset: 2px;  /* ux:28/102 */
--z-header: 2;                        /* sticky table header */
```

### 5.2 Layout

- `.dashboard` — dark canvas (`--bg`/`--fg`), `font-family: var(--font-sans)`,
  `max-inline-size: 1600px; margin-inline: auto; padding: var(--space-4)`.
- `.kpi-strip` and `.chart-grid` — `display: grid; grid-template-columns:
  repeat(12, 1fr); gap: var(--space-2)` (skill `styles.csv:29`: 12-column grid, 8px gap).
- `.kpi-tile` spans 12 on mobile, 4 at ≥768px (three across).
- `.chart-card` spans 12 on mobile, 6 at ≥768/1024px (two across), and 4 at ≥1440px
  (three across). `min-width: 0` on grid children so the Plotly graphs resize.
- `.run-header-block`, `.primary-table-section`, `.detail-section`, `.footnote` form the
  vertical rhythm (`--space-5`/`--space-6`).

### 5.3 Component coverage (25 classes — the stylesheet must style every one)

`dashboard`, `run-header-block`, `run-header` (grid of `dt`/`dd` pairs), `heuristic`
(the statement paragraph inside its disclosure), `kpi-strip`, `kpi-tile`, `kpi-label`,
`kpi-value` (mono), `kpi-note`, `chart-grid`, `chart-card`, `chart-caption`,
`primary-table`, `detail-panel`, `detail-section`, `primary-table-section`,
`formula-panel`, `footnote`, `component-legend`, `category-selector`, `strata` (dark
table), `metric-label`, `metric-kind` (badge-like), `missing` (muted/danger, never
`0`), `rankability` (status line).

Plus Dash-generated classes:

- `DataTable`: `.dash-table-container`, `.dash-spreadsheet-container`,
  `.dash-spreadsheet-inner`, `.dash-spreadsheet`, `.dash-cell`, `.dash-header`,
  `.dash-header.column-header--sort`, `.sort--asc`, `.sort--desc`, `.dash-cell.focused`,
  `.dash-cell.selected`, `.dash-fixed-content`, `.dash-tooltip`.
- `dcc.Dropdown` (react-select): `.Select`, `.Select-control`, `.Select-value`,
  `.Select-value-label`, `.Select-placeholder`, `.Select-input`, `.Select-arrow`,
  `.Select-menu-outer`, `.Select-menu`, `.Select-option`, `.is-focused`, `.is-selected`.
  The exact markup class names are **(unverified)** here; the implementer verifies
  against the installed Dash 4.4.1 rendered markup and keeps a defensive
  `[class*="dropdown"]` fallback (§11 Q4).

Table polish: `.primary-table` wrapper `overflow-x: auto` (ux:69/71); `.dash-header`
`position: sticky; top: 0; background: var(--surface-2); z-index: var(--z-header)`;
row height ~36px (`styles.csv:29 --table-row-height:36px`); numeric cells mono; zebra
and hover row tint. Sticky is **best-effort** — do **not** add `fixed_rows` or any other
DataTable prop (that would change markup/perf); if CSS sticky does not engage inside
Dash's scroll container, the sort affordance remains.

Badges (colour never sole indicator — ux:38): `.metric-kind` and `.rankability` get a
text label plus a subtle tinted surface/border; evidence grade stays as **text** in the
table and hover (its ordinal colour is already on the score bar).

### 5.4 Type

Sans for labels/headings/prose; mono for numerics (`.kpi-value`, `.dash-cell`, times,
counts) — skill `typography.csv:43` "Code for data, Sans for labels". Base prose
`--font-size-base: 1rem (16px)`; dense table numerics `--font-size-small: 0.8125rem
(13px)` ≥12px floor. Long prose (`.heuristic`, `.chart-caption`, `.formula-panel`,
`.footnote`) is bounded to `--measure` (ux:110/111).

### 5.5 Responsive breakpoints

Mobile-first base (≈375px single column); `@media (min-width: 375px)` small tier;
`@media (min-width: 768px)` (3 KPI / 2 chart columns, larger gutters);
`@media (min-width: 1024px)` (wider dashboard, measure); `@media (min-width: 1440px)`
(3 chart columns, max gutter). All four literal widths appear in the file.

### 5.6 Accessibility (normative)

- `:focus-visible { outline: var(--focus-ring); outline-offset: var(--focus-offset); }`
  on `summary, a, button, input, .dash-cell, .Select-control` (ux:28; ux:102).
- `@media (prefers-reduced-motion: reduce)` disables animation/transition/scroll-behavior
  (ux:9; ux:99).
- Text contrast ≥4.5:1 against its surface. Hand-computed token pairs (formula in §13):
  `--fg`/`--surface` ≈13.4:1, `--muted-fg`/`--surface` ≈6.6:1, `--primary`/`--surface`
  ≈6.8:1, `--accent`/`--surface` ≈9.7:1, `--positive`/`--surface` ≈9.5:1,
  `--danger`/`--surface` ≈5.1:1 (ux:37).
- Colour is never the only signal (ux:38): evidence grade/warnings/rankability carry text.
- Sticky header offset via `html { scroll-padding-top: … }` so focus is not obscured
  (ux:100/101).
- Dashed system option: no icons are introduced; per the skill, **no emoji as structural
  icons** and vector-only assets — this chunk adds no icons at all.

### 5.7 ux-skill citations and how each shaped a decision

All rows were **read directly from the skill's bundled CSVs** (the CLI is unavailable,
§11 Q2). The CLI-equivalent query for a new page is
`search.py "<query>" --design-system` (SKILL.md Step 2) plus `--domain style|color|
typography|chart|ux|icons` (Step 3); the underlying data is cited here.

| Skill output (file:line) | Concrete decision it shaped |
|---|---|
| `styles.csv:29` — style **Data-Dense Dashboard** (`data-dense-dashboard`), "Multiple charts/widgets, data tables, KPI cards, minimal padding, grid layout"; technical "display: grid, grid-template-columns: repeat(12, 1fr), gap: 8px, padding: 12px, font-size: 12-14px, overflow: auto for tables, compact card design, sticky headers"; vars `--grid-gap:8px, --card-padding:12px, --font-size-small:12px, --table-row-height:36px` | The whole §5.2 grid, the KPI/chart card system, 8px rhythm, table `overflow-x`, sticky header, and the 13px dense table size |
| `products.csv:8` — **Analytics Dashboard** → primary "Data-Dense Dashboard + Heat Map", dashboard style "Drill-Down Analytics + Comparative", palette "Cool→Hot gradients + neutral grey", "Clarity > aesthetics. Color-coded data priority." | Confirms the data-dense analytics direction and the drill-down (`<details>`) pattern; the **Heat Map secondary style is rejected** under chunk-31 R4 (heatmap removed) — conflict C2 |
| `products.csv:7` — **Financial Dashboard** → "Dark Mode (OLED) + Data-Dense Dashboard" | Confirms a single dark theme over the existing dark figures |
| `typography.csv:43` — **Dashboard Data** (Mono + Sans, Fira Code/Fira Sans), "Code for data, Sans for labels." | Adopted as **structure** (mono numerics, sans labels) with an offline system stack; its Google-Fonts `@import` is rejected — conflict C1 |
| `colors.csv:7/25/82/189` — dark BI palettes (`#0F172A`/`#1E293B`/`#334155` families; "Dark bg + …", "High contrast dark") | Corroborate dark-slate surfaces; the **lead's frozen tokens (§2)** are authoritative, not the skill hexes |
| `charts.csv:3` — **Compare Categories** (horizontal bar, 20–50 categories), "Always sort descending by value", "Use direct category/value labels … never encode category solely by bar color", visible sortable data table | Confirms the sortable primary table as the accessible companion to the score bar; direct labels + never colour-alone |
| `charts.csv:5` — **Correlation / Distribution** (scatter), "Combine marker shapes with direct group labels; color may reinforce but must not be the only distinction", visible data table | Confirms the scatter stays a secondary diagnostic with a text-grade companion in the table |
| `ux-guidelines.csv:9` — Reduced Motion (`@media (prefers-reduced-motion: reduce)`) | §5.6 motion rule |
| `ux-guidelines.csv:28` — Focus States ("visible focus ring on every interactive control") | §5.6 `:focus-visible` rule |
| `ux-guidelines.csv:37` — Color Contrast (≥4.5:1 normal text) | §5.6 contrast budget and §13 hand computation |
| `ux-guidelines.csv:38` — Color Only ("use icons/text in addition to color") | Badges/text grades; never colour alone |
| `ux-guidelines.csv:69/71` — Horizontal Scroll / Table Handling (`overflow-x:auto` wrapper) | `.primary-table` scroll wrapper |
| `ux-guidelines.csv:100/101` — Focus Not Obscured (`scroll-padding-top`) | Sticky-header offset rule |
| `ux-guidelines.csv:68` — Readable Font Size (≥16px body on mobile) | 16px prose base; 13px restricted to dense table numerics — conflict C3 |
| `ux-guidelines.csv:111` — Heading Line Balance / bounded measure (`max-inline-size`) | `--measure` on prose blocks |
| `ui-reasoning.csv:166/189` — Status Page / RPA dashboards → "Dark Mode (OLED) + Data-Dense Dashboard" | Corroborates the dark + data-dense pairing for operator consoles |
| `SKILL.md` Rules — "No Emoji as Structural Icons", "Vector-Only Assets", "Token-driven theming (no per-screen hardcoded hex)" | All colour via `:root` tokens; no icons/emoji introduced; no per-rule ad-hoc hexes outside `:root` |

### 5.8 Skill conflicts — constraints win

- **C1 (fonts):** `typography.csv:43` ships a `fonts.googleapis.com` `@import`. **D-4
  (offline/no-CDN) wins.** The mono/sans *structure* is kept; the fonts become a local
  system stack. No `@import`, no `url(`, no scheme-bearing string in the CSS.
- **C2 (heatmap):** `products.csv:8` lists a heat map as a secondary style. **Chunk-31
  R4 (heatmap omitted, coverage exact in the table) wins.** No heatmap styling or markup.
- **C3 (type size):** `styles.csv:29` uses 12–14px dense type; `ux-guidelines.csv:68`
  wants ≥16px body on mobile. Resolution: prose/statement/captions at 16px; only dense
  table numerics at 13px (never <12px) with ≥4.5:1 contrast. (Judgment call surfaced as
  §11 Q1's sibling; not blocking.)
- **C4 (icons):** `icons.csv` and the SKILL.md Phosphor rules are **not used** — this
  chunk introduces no icons, so no icon library and no external asset is added.

---

## 6. Interface doc deltas (explicit list for the lead; the planner edits none)

Apply consistently with the code; these are the only frozen-contract updates.

1. **`Documents/interfaces/chunk-11.md` — new §12 "Chunk 32 revision — dashboard
   stylesheet and progressive disclosure (2026-10-01)"**, superseding nothing removed but
   amending §1 (assets boundary) and §7 (display rules):
   - **§1 boundary rule.** `report.py` resolves Dash's `assets_folder` to the packaged
     directory `src/niche_scout/assets/` and ships `assets/*.css` via
     `[tool.setuptools.package-data] niche_scout = ["assets/*.css"]`. No network, no
     clock, no new dependency; all prior boundary rules unchanged.
   - **§5 functions.** Signatures of `build_dashboard_layout` and `build_dashboard_app`
     are **unchanged**. New **private** helpers only: `_dashboard_assets_dir()`,
     `_disclosure(summary, children, *, open=False, className=None)`,
     `_heuristic_banner(view)`, and the constant `_HEURISTIC_SUMMARY`. No public surface
     is added or removed.
   - **§7 display rules.** The dashboard loads the packaged `assets/dashboard.css`
     (offline; no external URL/CDN). The `LREQ-RPT-050` statement, the shared formula
     panel, the observed-versus-inferred list, and the sample-strata table are rendered
     inside `<details>` elements whose content remains in the DOM; the shared formula
     panel starts closed. The footnote keeps the `n/a`-vs-`0` and provisional notices and
     drops bullets that only restate the shared formula list. All `LREQ-RPT-020/030/040/
     050` content and Appendix C codes remain present.
2. **No delta** to `chunk-12.md` (CLI serves the same app; no option, no exit-code change)
   or `chunk-00.md`/`chunk-02.md` (no read-model change).
3. **No SRS, `AGENTS.md`, dependency-map, or `.kilo/` edit is in scope.**

---

## 7. Files touched (the plan's file-discipline list)

Production:
- `src/niche_scout/assets/dashboard.css` — **new** (§5).
- `pyproject.toml` — add `[tool.setuptools.package-data] niche_scout = ["assets/*.css"]`.
- `src/niche_scout/report.py` — private helpers `_dashboard_assets_dir`, `_disclosure`,
  `_heuristic_banner`, `_HEURISTIC_SUMMARY`, `_DASHBOARD_ASSETS_DIRNAME`; change
  `_shared_formula_panel` (`open=False`), `_detail_panel_children` (two disclosures),
  `_footnote` (trim two bullets), `build_dashboard_layout` (heuristic banner),
  `build_dashboard_app` (`assets_folder`).

Interfaces (frozen; the **lead** amends in the same change — §6):
- `Documents/interfaces/chunk-11.md` (new §12).

Tests:
- `tests/test_report.py` — four new nodes; add `from pathlib import Path` (§8.4).
- `tests/traceability.json` — four new keys.

Run log (lead): `Documents/runs/chunk-32.md` stage/gate result.

No other file is in scope. Any other file needing a change is a stop-and-flag.

---

## 8. Test plan (exact node IDs; every analytical node has `@pytest.mark.lreq(...)`)

### 8.1 New nodes in `tests/test_report.py`

| Node ID | Marker(s) | Asserts |
|---|---|---|
| `tests/test_report.py::test_dashboard_css_asset_exists_is_offline_and_uses_the_token_set` | `LREQ-RPT-010` | The stylesheet exists at `Path(report.__file__).parent / "assets" / "dashboard.css"`, is non-empty, and (after `casefold()`) contains: no `http://`/`https://`, no `@import`, no `url(`; every name in `_DASHBOARD_CSS_TOKENS`; every hex in `_DASHBOARD_CSS_HEXES` (casefolded); a selector for every class in `_DASHBOARD_CSS_CLASSES` (25, §8.3, regex word-boundary); `.dash-cell` and `.dash-header`; `":focus-visible"`; `"@media (prefers-reduced-motion: reduce)"`; and the literals `"375px"`, `"@media (min-width: 768px)"`, `"@media (min-width: 1024px)"`, `"@media (min-width: 1440px)"` |
| `tests/test_report.py::test_dashboard_css_is_declared_as_package_data` | `LREQ-RPT-010` | `(Path(report.__file__).resolve().parents[2] / "pyproject.toml")` text contains `"[tool.setuptools.package-data]"` and `'niche_scout = ["assets/*.css"]'`; the referenced file exists |
| `tests/test_report.py::test_dashboard_app_serves_the_package_assets_folder` | `LREQ-RPT-010` | With `_dashboard_view(tmp_path)`: `Path(app.config.assets_folder).resolve() == (Path(report.__file__).parent / "assets").resolve()`, and that dir contains `dashboard.css`. Building twice yields the same resolved folder. If the installed Dash exposes the resolved path as `config.assets_path`, the implementer asserts the same equality there and records which attribute is the resolved one (§11 Q3); the node ID and marker are unchanged |
| `tests/test_report.py::test_dashboard_uses_progressive_disclosure_without_dropping_mandated_content` | `LREQ-RPT-030`, `LREQ-RPT-050` | `build_dashboard_layout(view)`'s tree contains ≥3 `Details` components; one `Details` contains `view.heuristic_statement` **exactly once** and its `props.get("open") is not True`; the `formula-panel` Details has `props.get("open") is not True`; one `Details` contains `_OBSERVED_LABELS[0]` and `_INFERRED_LABELS[-1]`; one `Details` contains `"N_h (discovered population)"`; the whole-tree `_norm(layout)` still contains `"Metric inputs"`, `"Observed versus inferred"`, `"Sample strata"`, `"Warnings"`, `"Timestamps"`, and `_FORMULA_EXPLANATIONS[0]` exactly once |

Detection detail: `Details` is found with the existing
`_components_of_type(layout, "Details")` helper (§8.4). If Dash serializes the html
component type under a different `type` string in the installed 4.4.1, the implementer
verifies the serialized `type` and records the substitution; the node ID and its
assertion intent do not change. **(unverified locally — §13.)**

### 8.2 Amended nodes

**None.** Every pinned dashboard/static node keeps its ID and traceability key
byte-identical; no assertion is weakened. The pinned set that MUST stay green:

`test_report.py`: `test_build_dashboard_layout_is_deterministic_for_a_fixed_view` (`:1293`),
`test_build_dashboard_app_layout_matches_the_layout_builder` (`:1307`),
`test_dashboard_layout_shows_every_primary_table_column_by_default` (`:1321`, all 30),
`test_dashboard_detail_panel_covers_rpt_030_items_for_a_selected_category` (`:1336`),
`test_dashboard_layout_keeps_refused_categories_visible_and_off_the_scored_axis` (`:1364`),
`test_dashboard_layout_includes_the_heuristic_statement` (`:1391`),
`test_dashboard_charts_carry_explanations_and_human_labels` (`:1403`),
`test_dashboard_distinguishes_null_from_explicit_zero` (`:1426`),
`test_dashboard_has_no_confidence_interval_or_error_bars` (`:1472`),
`test_dashboard_policy_bump_and_kpi_tiles` (`:1488`),
`test_dashboard_score_bar_encodes_ordinal_evidence_grade` (`:1533`),
`test_dashboard_omits_the_coverage_heatmap` (`:1558`),
`test_html_output_is_self_contained_and_deterministic` (`:940`);
`test_end_to_end.py::test_acceptance_rendered_report_contains_required_fields` (`:507`;
`view.heuristic_statement in json.dumps(app.layout, cls=PlotlyJSONEncoder)`).

Why each survives the markup change **(read)**: the heuristic node counts the statement
in the normalized tree (a closed `<details>` still serializes its children); the RPT-030
node checks mandated strings and `_FORMULA_EXPLANATIONS[0].count == 1`; the chart/KPI
nodes read captions/titles/tile text outside the changed blocks; the null/zero,
evidence-colour, error-bar, heatmap, and determinism nodes are untouched; the static
`_INLINE_CSS` path is not modified.

### 8.3 Test-module constants (put in `tests/test_report.py`, not fixtures)

`_DASHBOARD_CSS_TOKENS` (13): `--bg`, `--surface`, `--surface-2`, `--border`, `--fg`,
`--muted-fg`, `--primary`, `--accent`, `--positive`, `--danger`, `--font-sans`,
`--font-mono`, `--measure`.
`_DASHBOARD_CSS_HEXES` (10, casefold-compared): `#0b1120`, `#1b2029`, `#222833`,
`#2c3440`, `#e6e9ee`, `#9aa6b2`, `#6ea8fe`, `#f2c14e`, `#8fd694`, `#e06c75`.
`_DASHBOARD_CSS_CLASSES` (25): the §5.3 list, in that order.

### 8.4 Test-module import

Add `from pathlib import Path` to `tests/test_report.py` (its current imports do not
include it **(read:** `test_report.py:20–33`)). `report.__file__` supplies the package
path; no new fixture is needed.

### 8.5 `tests/traceability.json`

- **Add** the four §8.1 keys with their marker lists (nodes 1–3 `["LREQ-RPT-010"]`; node 4
  `["LREQ-RPT-030", "LREQ-RPT-050"]`).
- **Change** no existing key (no amended nodes; pinned keys stay byte-identical).
- Run `python -m niche_scout.tools.validate_traceability` — exit 0 required.

---

## 9. Fixtures and golden vectors

- No new arithmetic, so **no new golden vector**. Reuse
  `tests/fixtures/report_fixtures.py::dashboard_rows()` (three rankable + one refused)
  through the existing `_dashboard_view(tmp_path)` helper
  (`test_report.py:1116–1131`) for the disclosure and assets-folder nodes.
- The CSS node needs no fixture; it derives the path from `report.__file__` and the
  constants in §8.3.
- No fixture credentials, no network, no live path.

---

## 10. Gate checklist / DoD

- [ ] `python -m pytest -q` — full suite green: four new nodes pass; every §8.2 pinned
      node still passes; no other tree changes.
- [ ] `python -m niche_scout.tools.validate_traceability` — exit 0; each new node has a
      marker and a matching key; no orphan entry.
- [ ] `python -m niche_scout.tools.check_import_boundaries` — exit 0 (`metrics.py` /
      `scoring.py` untouched; `report.py` remains a non-pure module and gains no forbidden
      import).
- [ ] `python -m niche_scout.tools.check_scope_prohibitions` — exit 0 (no retired token).
- [ ] `ruff format` and `ruff check` clean on changed Python files (`pyproject.toml`
      `include = ["*.py"]` **(read:** `pyproject.toml:27–31`); the CSS is not linted).
- [ ] `dashboard.css` exists, is non-empty, contains no `http://`/`https://`/`@import`/
      `url(`, defines the 13 tokens and 10 hexes, styles all 25 layout classes plus the
      DataTable and dropdown classes, and includes `:focus-visible`,
      `prefers-reduced-motion`, and the 375/768/1024/1440 breakpoints.
- [ ] `pyproject.toml` declares `niche_scout = ["assets/*.css"]`.
- [ ] `build_dashboard_app(view).config.assets_folder` resolves to
      `src/niche_scout/assets` and that dir holds `dashboard.css` (or `config.assets_path`
      if that is the resolved attribute — recorded).
- [ ] Progressive disclosure: the statement, formula panel, observed/inferred list, and
      strata table are inside `<details>`; the formula panel is closed by default; every
      mandated string is still in the DOM (`LREQ-RPT-020/030/040/050`; Appendix C codes);
      the statement appears exactly once and `view.heuristic_statement` is in
      `json.dumps(app.layout)`.
- [ ] The static report path is untouched and still self-contained
      (`test_html_output_is_self_contained_and_deterministic` green).
- [ ] `report.py` imports no `metrics`/`scoring`/`collector*`/`config`/`pipeline`/`cli`
      and reads no clock (`test_quality_tooling.py::test_report_module_has_no_forbidden_
      imports_or_clock_reads` green).
- [ ] No file outside §7 changed; `Documents/interfaces/chunk-11.md` §12 applied by the
      lead; `Documents/runs/chunk-32.md` updated with the gate result.

---

## 11. Open questions and implementation-time verifications

Numbered for the lead; none blocks a correct implementation.

1. **Heuristic disclosure default (`open`).** The task fixes `open=False` for
   `_shared_formula_panel` but does not state the heuristic's default. Recommendation
   **(a): `open=False`** (progressive disclosure; the one-line summary
   "What this score is and is not" stays visible; the full `LREQ-RPT-050` text is in the
   DOM exactly once). Alternative (b): `<details open>` — statement visible by default but
   collapsible. The plan implements (a). SRS reference: `LREQ-RPT-050`
   (`SRS-lean-v2.md:1177–1185`) mandates that the report *state* the text; it does not
   mandate always-visible rendering, and D-3 authorizes disclosure. **Lead to confirm.**
2. **`ui-ux-pro-max` CLI could not be run.** A global permission rule denied `bash`
   (verbatim: "The user has specified a rule which prevents you from using this specific
   tool call … {"permission":"bash","pattern":"*","action":"deny","source":"global"}") and
   the `background_process` monitor action. The skill was loaded and its bundled data CSVs
   were read directly; §5.6 cites those rows with file:line and the query each would
   answer. This is a tooling limitation, not an SRS gap. **Lead to decide whether a re-run
   of the CLI on a permitted host is required before the gate.**
3. **Dash `config.assets_folder` attribute.** Whether it returns the raw or the resolved
   assets path in Dash 4.4.1 is **(unverified)** here (no interpreter access). The plan
   passes an **absolute** path so `Path(config.assets_folder).resolve()` is the package
   dir either way; the implementer records the actual attribute used.
4. **`dcc.Dropdown` class names.** The react-select class family differs by Dash/react-
   select version; the implementer inspects the installed 4.4.1 rendered markup and keeps
   a defensive fallback. No test asserts on these names, so this cannot fail a gate.
5. **`html.Details` serialization.** `_components_of_type(layout, "Details")` assumes the
   serialized `type` is `"Details"`; the implementer confirms against `to_plotly_json()`
   and records any substitution (§8.1).
6. **CSS-only sticky header.** Best-effort inside Dash's scroll container (no DataTable
   prop change allowed); if it does not engage, sortability still holds. No gate depends
   on it.
7. **Contrast.** The hand-computed pairs in §5.6/§13 are arithmetic on the lead's tokens;
   if any pair is later changed, re-run the check before the gate.

---

## 12. Lead rulings (freeze, 2026-10-01)

All seven questions are resolved. Authority: the operator's D-1..D-5 and the lead's fixed
tokens (§2). No ruling fabricates a quantity the SRS does not define (AGENTS.md Hard rules 1–2).

- **R1 (Q1) — heuristic disclosure default = `open=False`.** Option (a). Rationale: the
  operator's explicit instruction is to cut unnecessary on-page text, and D-3 authorizes
  progressive disclosure. `LREQ-RPT-050` (`SRS-lean-v2.md:1177–1185` **(read)**) mandates that
  the report *state* the text, not that it be permanently expanded; the statement stays in the
  DOM exactly once (pinned `test_dashboard_layout_includes_the_heuristic_statement`;
  `view.heuristic_statement in json.dumps(app.layout)` in `test_end_to_end.py:530`). The summary
  "What this score is and is not" stays always-visible.
- **R2 (Q2) — skill CLI accepted as satisfied.** The **lead ran the `ui-ux-pro-max` CLI** in the
  permitted environment (design-system + `style`/`color`/`typography`/`chart`/`ux` domain
  searches); the verbatim outputs are recorded in `Documents/runs/chunk-32.md`. They corroborate
  the planner's direct CSV citations (Data-Dense Dashboard; mono-for-data / sans-for-labels;
  dark-slate palettes; ranking→horizontal bar + sortable table; focus/contrast/reduced-motion
  rules). The planner's CSV rows are accepted as **(read)** evidence. No re-run is required.
- **R3 (Q3) — assets folder.** Pass an **absolute** `assets_folder=str(_dashboard_assets_dir())`;
  the test asserts `Path(config.assets_folder).resolve()` equals the package assets dir, falling
  back to `config.assets_path` if that is the resolved attribute, and records which was used.
- **R4 (Q4/Q6) — defensive only.** `dcc.Dropdown` class names and CSS-only sticky header are
  best-effort; no gate depends on them; keep the `[class*="dropdown"]` fallback and do **not**
  add DataTable props (no `fixed_rows`).
- **R5 (Q5) — `Details` serialization.** `html.Details` must serialize under a stable type string;
  the implementer confirms it in the installed Dash 4.4.1, records it, and uses
  `_components_of_type(layout, <that type>)`. If the string differs from `"Details"`, the node ID
  and its assertion intent are unchanged.
- **R6 (Q7) — contrast.** Keep the hand-computed budget (all pairs ≥4.5:1). If any token changes,
  re-check before the gate; a failing pair is a gate failure.

### 12.1 Post-freeze implementation risks (record, do not silently resolve)

- **Dash 4.4.1 `assets_folder` attribute name** (Q3) is unverified until implementation; the
  absolute path makes the assertion robust either way — record the attribute used.
- **`html.Details` serialized `type`** (Q5) and **react-select class names** (Q4) are unverified
  until implementation; both have recorded mitigations and no gate dependency on the exact string.
- **CSS-only sticky header** (Q6) may not engage inside Dash's scroll container; best-effort only.

---

## 13. Evidence walk for the countable claims in this plan

Per project-rules "Plan review and audit", the counts asserted and the method used.
Every path below was opened and read.

- **`setup.cfg`/packaging:** `pyproject.toml` has `[tool.setuptools.packages.find]
  where=["src"]` and **no** `[tool.setuptools.package-data]` block today
  **(read:** `pyproject.toml:18–19`; the file is 37 lines **counted** by reading it to
  EOF). Ruff `include = ["*.py"]` **(read:** `pyproject.toml:27–31`).
- **25 layout classes.** Method: read `report.py` for every `className=` occurrence and
  reconcile with the task list. Query: grep `className=` in
  `src/niche_scout/report.py` → **30 matches** **(counted)**, of which 5 are the
  duplicate `missing`/`rankability`-style reuses; the distinct class tokens are the 25
  named in §5.3. Unit: distinct class strings. Anchor lines **(read)**:
  1686/1696/1706/1707/1708/1710/1720/1742/1794/1803/1804/1815/1851/1867/1868/1872/1888/
  1941/1952/1981/2003/2023/2034/2037/2045/2053/2063/2066/2070/2098.
- **13 required token names / 10 required hexes.** These are the lead's fixed set
  **(read:** `Documents/runs/chunk-32.md:89–93`) plus `--font-sans`/`--font-mono`/
  `--measure` chosen by this plan. Unit: distinct CSS custom-property names / distinct
  hex values.
- **The heuristic statement appears exactly once (today and after).** The pinned node
  asserts `.count(statement) == 1` **(read:** `test_report.py:1391–1399`); the layout
  renders it once at `report.py:2031–2035` **(read)**; the change moves that `P` inside a
  `Details` without duplicating it.
- **`_shared_formula_panel` is `open=True` today.** **(read:** `report.py:1947–1954`.)
- **`_FORMULA_EXPLANATIONS` has 11 items; `_OBSERVED_LABELS` 8; `_INFERRED_LABELS` 13.**
  **(counted** by reading the tuples `report.py:321–346`, `:292–301`, `:304–318`; unit:
  tuple elements.) The disclosure test only indexes the first observed and last inferred
  label, so exact totals are not load-bearing.
- **`_PRIMARY_COLUMNS` = 30.** **(read:** plan chunk-31 §13; and `test_report.py:1054`
  asserts `len(report._PRIMARY_COLUMNS) == 30`, `report.py:350` starts the tuple). The new
  plan does not change this; cited for continuity.
- **Pinned dashboard node line numbers.** Query: read `tests/test_report.py` at the cited
  offsets (1293, 1307, 1321, 1336, 1364, 1391, 1403, 1426, 1472, 1488, 1533, 1558) and
  `tests/test_end_to_end.py:507–534`. **(read; unit: 1-based line numbers.)**
- **`test_report.py` imports `Path`?** Query: read `test_report.py:20–34`; no `pathlib`/
  `Path` import. **(read.)**
- **`DataTable` / `dcc.Graph`/`Details` serialized `type`.** **(unverified)** — no
  interpreter access this session. Mitigation in §8.1/§11 Q5.
- **Dash `config.assets_folder`.** **(unverified)** — no interpreter access; absolute
  path makes the assertion robust either way (§11 Q3).
- **Contrast ratios.** Hand-computed from the lead's tokens using the WCAG relative-
  luminance formula `L = 0.2126 R + 0.7152 G + 0.0722 B` on linearised sRGB, ratio
  `(L_light+0.05)/(L_dark+0.05)`; surface `#1B2029` has `L≈0.0143`. Results:
  `#E6E9EE`/surface 13.4:1; `#9AA6B2`/surface 6.6:1; `#6EA8FE`/surface 6.8:1;
  `#F2C14E`/surface 9.7:1; `#8FD694`/surface 9.5:1; `#E06C75`/surface 5.1:1. All ≥4.5:1
  (ux:37). **(hand-computed; the intermediate linearisations are in §5.6's method and are
  reproducible from the formula; labelled, not tool-verified in this session.)**
- **`ui-ux-pro-max` CLI unavailable.** Verbatim denial: `{"permission":"bash",
  "pattern":"*","action":"deny","source":"global"}` for `bash` and for
  `background_process` monitor. Citations instead resolve to the skill's bundled CSVs
  (`styles.csv`, `products.csv`, `typography.csv`, `colors.csv`, `charts.csv`,
  `ux-guidelines.csv`, `ui-reasoning.csv`) at the quoted line numbers **(read)**.
