# Chunk 35 — dashboard refinement: wrapped labels, chart repairs, a sixth chart, nav icons, wide layout (plan)

Status: FROZEN — 2026-10-02. The lead has settled the one blocking item (D35-3 sixth chart =
Demand-vs-Competition opportunity scatter, threshold-free; run log `Documents/runs/chunk-35.md`
and the lead's resolution note). This plan fixes the code-level contracts for D35-1..D35-8,
the supersession of a named subset of chunk-34 decisions, and the test surface. Open
questions: one non-blocking, informational item only (§15).

New remediation/feature chunk, not in `Documents/requirements-dependency-map.md` §3/§4
(chunk-14 / 30 / 31 / 32 / 33 / 34 precedent: registration = plan + run log + branch). Do not
edit the dependency map, the SRS, `AGENTS.md`, `kilo.jsonc`, or anything under `.kilo/`.

Branch: `chunk-35`, created from `main` @ `dd0db32`.

Authority: `Documents/runs/chunk-35.md` (this chunk's log: preflight with the operator-authored
uncommitted `_RAMP_HEXES` colour hunk that is now the chunk baseline, the live-dashboard audit,
and the read-only data probe); `Documents/plans/chunk-34-dashboard-chart-and-table-remediation.md`
(the immediately preceding dashboard plan this chunk builds on and partly supersedes, §3);
SRS §7.2/§7.3, §8.2 (`LREQ-SCR-010`/`LREQ-SCR-020` — grepped and read at `SRS-lean-v2.md:961–979`),
§1.3 (product scope, `:102–128`), §10 (`LREQ-RPT-010`..`LREQ-RPT-050`, `:1153–1189`). Every
countable claim is labelled **(read)** (opened and read), **(counted)** (queried with a stated
method and unit), or **(CLI query)** (produced by the `ui-ux-pro-max` CLI).

> **Addendum (lead, 2026-10-02) — CLI queries now run.** The planning subagent could not execute
> the `ui-ux-pro-max` CLI (its shell paths were denied), so the plan's skill grounding was
> originally labelled **(read from skill data files)**. The lead then ran the CLI and the returns
> are recorded below; where the two agree the row is CLI-verified. **§2.1a** holds the six
> verbatim CLI returns; §2.1 rows that a §2.1a query reproduced are now **(CLI query)**-verified,
> the rest stay **(read from skill data files)**. No design decision changed.

---

## 1. Scope, non-goals, LREQ roles

### 1.1 Scope (in)

1. **Two-line wrapped category labels (item 1).** Replace the chunk-34 leaf-only, single-line
   chart category label with a **two-line wrapped label** that keeps the leaf and enough of its
   parent path to be identifiable, applied to **all** chart category axes/legends consistently,
   and error-tolerant for Plotly multi-line tick labels (SVG `<tspan>`). The full taxonomy path
   stays in hover `customdata`, the primary table, the column guide, the selector, and the detail
   heading (§5, D35-5).
2. **Contribution legend fits its content (item 2).** The 4-item *Weighted component
   contributions* legend must fit inside the card without scrolling; the legend/plot geometry is
   pinned so the plot keeps a usable area (§6, D35-6).
3. **Policy-rank comparison de-spaghetti (item 3).** Keep the persisted per-policy ranks; drop
   the redundant legend; show a concrete, readable presentation for the categories whose rank
   actually changes across policies, without hiding any category that has a persisted rank (§7,
   D35-7).
4. **Population chart sample-size series removed (item 4).** Remove the constant `sample size`
   series from the figure and its legend; keep discovered population, the explicit measured-zero
   marker (`diamond-open`, `--danger`), and the log-scale x-axis (§8, D35-8).
5. **Single colour source of truth (item 5).** `report.py` colour literals (`_RAMP_HEXES` and the
   figure literals) are the single functional source. The non-functional `--ramp-*`/`--evidence-*`
   colour tokens are removed from `dashboard.css`; the misleading header comment is corrected
   (§4, D35-2).
6. **Phosphor outline nav icons (item 6).** Keep the single Phosphor outline family (the skill's
   curated `icons.csv` catalog is Phosphor-only, §2.1a) and replace the wrong metaphors —
   Run→`play-circle` (no `house`), KPIs→`gauge`, Charts→`chart-bar`, Table→`table`,
   Detail→`file-text` — inlined as SVG path data in `report.py` like today's paths. Icons stay
   `aria-hidden="true"` decorative beside their visible text label; no external URL (§4, D35-1).
7. **Sixth chart (item 7).** Add a sixth pure figure — the **Demand vs Competition opportunity
   scatter** — reading only persisted `CategoryReportRow` fields, so the desktop 2×3 / 3×2 grid is
   even (§3, D35-3; lead-decided).
8. **Ultrawide fill (item 8).** Let the content area grow past 1600px on large screens without
   breaking responsiveness; the 1/2/3-column grid breakpoints are unchanged (§9, D35-4).
9. **Preservation.** Every existing pinned dashboard node stays green (amended-in-place nodes keep
   their node ID, marker, and `tests/traceability.json` key); no content, number, public
   signature, callback, import, or clock read changes (§10–§12).

### 1.2 Non-goals (explicitly NOT in this chunk)

- **No content removal.** No `LREQ-RPT-020` primary-table column, no `LREQ-RPT-030` detail item,
  no `LREQ-RPT-050` string, and no Appendix C warning code may be removed from the DOM. The
  two-line chart label is a *display* transform of a chart tick only.
- **No data or number change.** No metric, component, score, rank, evidence grade, rankability, or
  sensitivity value is recomputed or altered; figures render persisted values verbatim. `n/a ≠ 0`;
  a missing component is a gap, never a zero-height stack segment; a missing scatter component is
  no marker, never a marker at `0`.
- **No external dependency.** No CDN, web font, `@import`, `url(`, or scheme-bearing external
  asset in CSS or figure data. Figures bake colour/font literals because they serialize to JSON.
- **No new Dash callback** beyond the single existing `_render_selected_detail`; no clientside JS.
  The sixth chart is a pure figure built from the same `RunReportView`; no new `dcc.Store`.
- **No purity change.** `report.py` imports no `metrics`/`scoring`/`collector*`/`config`/
  `pipeline`/`cli`, performs no file/network I/O, reads no clock;
  `build_dashboard_layout(view)` stays pure and deterministic for a fixed view.
- No change to the frozen public signatures of `build_dashboard_layout` / `build_dashboard_app`;
  no change to `render_run_report_html` / `render_run_report_text` / `write_run_report`.
- No test-node-ID change: this chunk adds new nodes and amends existing nodes **in place** (§11).
- **No SRS/dependency-map edit**; no schema/pipeline/`metrics.py`/`scoring.py` change; no static
  (`run --report`) change; no CLI change.
- The standing obligations — URI trailing-identifier extraction, OI-6 CSRF/session sufficiency,
  `runs.taxonomy_sha256` empty-hash rejection — are out of scope and **untouched** by this chunk.

### 1.3 LREQ roles

| Role | LREQs |
|---|---|
| Primary | `LREQ-RPT-010` (one-command local read-only dashboard; offline styling/packaging) — the chart/legend/icon/layout remediation strengthens the served-page guarantee |
| Supporting contract | `LREQ-RPT-020` (30-column primary table unchanged; the sixth chart carries persisted values only), `LREQ-RPT-030` (detail heading keeps the full path), `LREQ-RPT-040` (non-rankable rows stay visible and off the scored axes), `LREQ-RPT-050` (heuristic statement unchanged) |
| Chart-semantics citation | `LREQ-SCR-010` (Demand orientation) and `LREQ-SCR-020` (Competition = `clamp(1 - P_ref(BreadthRaw))`, higher = less crowded) — cited in the sixth chart's caption/title wording only; no formula is restated or recomputed |
| Integration completion | `LREQ-NFR-040` (no public builder signature change), `LREQ-ARCH-010`/`LREQ-ARCH-020` (purity; `metrics`/`scoring` untouched) |

Per the tool's mapping rule, new markers use only `LREQ-RPT-010`/`020`/`030`/`040`; no new marker
cites `LREQ-ARCH-*`/`LREQ-NFR-*` (purity and determinism are asserted by the existing
`test_quality_tooling.py` node and the determinism node, both of which must stay green — §11.3).
`LREQ-SCR-010`/`020` are cited in the caption text, not as pytest markers on the new chart node.

---

## 2. Grounding facts

Each fact is labelled **(read)**, **(counted)**, **(CLI query)**, or **(read from skill data
files)**. No fact is restated from memory; run-log-only facts say so.

- **`report.py` is 2646 lines; `dashboard.css` is 868 lines; `tests/test_report.py` is 2458 lines**
  — **(counted:** `(Get-Content <path>).Count` for each of the three files).
- **`_RAMP_HEXES` is the operator's colour hunk** `("#73adf0", "#59e082", "#d0df4d", "#e68d52")`
  — **(read:** `report.py:274`; the values match the run-log preflight, `Documents/runs/chunk-35.md:9–14`).
  This is the chunk baseline and **breaks** the two chunk-34 nodes that hard-pin the old ramp
  (§3.1).
- **`DASHBOARD_CHART_IDS` has five entries and `DASHBOARD_COMPONENT_IDS` has ten** — **(read:**
  `report.py:91–116`). The five chart keys are `score_bar`, `contribution_stack`, `policy_bump`,
  `population_lollipop`, `score_quality_scatter`; the `div_id` prefix is `niche-scout-` and the
  component-id prefix is `chart-`.
- **`_DASHBOARD_CHART_CAPTIONS` and `_DASHBOARD_CHART_TITLES` are keyed by the same five chart
  keys** — **(read:** `report.py:200–234`). The population title is
  `"Population and sample size (log scale)"` (`:232`).
- **The `builders` dict in `_chart_figure` has five key→function entries** — **(read:**
  `report.py:1986–1992`).
- **The five figure builders and their category axes** — `_score_bar_figure` (`report.py:1714`),
  `_contribution_figure` (`:1777`), `_policy_bump_figure` (`:1807`),
  `_population_lollipop_figure` (`:1843`), `_score_quality_scatter_figure` (`:1933`) — **(read:**
  each builder body).
- **`_category_leaf_label(row, view)` at `report.py:1366`** returns the leaf, suffixing
  `" · <parent>"` only for a colliding leaf group — **(read:** `:1366–1390`). This is the helper
  chunk 35 supersedes with a two-line wrapper (§5).
- **`_base_layout()` at `report.py:1514`** is the single shared style seam; it carries
  `paper_bgcolor`/`plot_bgcolor` `#112d3b`, `font` `#e6f0f4`, `margin {"l":8,"r":56,"t":48,"b":40}`,
  `legend {"bgcolor":"#0c2432","font":{...mono}}`, and both axes' `tickfont`/`title.font` — and it
  has **no** `title` key — **(read:** `:1514–1552`).
- **The population figure's three trace `name=` values** are `"discovered population"`
  (`report.py:1882`), `"measured zero"` (`:1894`), `"sample size"` (`:1914`); the explicit-zero
  marker is `diamond-open` `#e27882` (`:1898`) — **(read:** the cited lines). The `sample size`
  trace is the constant series item 4 removes (§8).
- **The policy-bump builder currently draws one `go.Scatter` per `_policy_rank_rows(view)` row with
  `mode="lines+markers+text"`, `text=[label, "", ""]`, a per-series ramp colour, and a legend that
  repeats the names** — **(read:** `report.py:1807–1840`).
- **`COMPONENT_WEIGHTS`/`COMPONENT_RENDER_ORDER` and the `_DASHBOARD_LABELS` vocabulary** exist and
  the component letters `D`/`C` map to `"Demand"`/`"Competition"` — **(read:** `report.py:61–71`,
  `:133–195`).
- **`CategoryReportRow` carries `component_d`, `component_c`, `sample_fraction` (each
  `float | None`) and `rank` (`int | None`)** — **(read:** `report.py:590–601`).
- **The nav is data-driven**: `_DASHBOARD_NAV_ITEMS` maps each anchor to an icon key
  (`house`, `grid-four`, `chart-bar`, `list-bullets`, `list`) — **(read:** `report.py:1561–1567`);
  the inline SVG is 256×256 (`viewBox="0 0 256 256"`, `report.py:1619`). Chunk 35 keeps the
  256×256 Phosphor geometry and changes only the five keys/paths (§4.1).
- **The contribution legend does not yet pin an orientation/position**; it inherits the
  `_base_layout` legend dict — **(read:** `report.py:1532–1535`, `:1800–1801`).
- **`dashboard.css` tokens**: `--ramp-1`..`--ramp-4` and the four `--evidence-*` values are
  declared at `dashboard.css:40–49` — **(read:**). A grep of the whole stylesheet for
  `var(--ramp-` and `var(--evidence-` returned **zero matches** — **(counted:** ripgrep,
  pattern `var\(--ramp-|var\(--evidence-`, unit = matching source lines). So these tokens are
  consumed by no rule and are the non-functional second colour source item 5 removes.
- **`.dashboard` carries `max-inline-size: 1600px`** — **(read:** `dashboard.css:116`); the grid
  breakpoints are `.chart-card { grid-column: span 6 }` at `≥768` (`:814`), `span 6` at `≥1024`
  (`:835`), and `span 4` at `≥1440` (`:864`) — **(read:**). `.dashboard` at `≥1024` uses
  `margin-inline-start: calc(var(--nav-rail-width) + var(--space-6))` (`:832`).
- **The run log's live audit** (dead space, contribution-legend scroll, policy spaghetti,
  population constant series, nav icon dislike, misleading CSS tokens) is recorded at
  `Documents/runs/chunk-35.md:22–42` — **(read from run log**; not re-measured by this planner).
- **The read-only DB probe** reports `component_d` 0.31..0.92, `component_c` 0.087..1.00,
  `component_r` 0.00..0.99, `component_q` 0.056..1.00, 24 categories, `enriched_sample_count` = 100
  for every row, `overlap_category_count` = 0 for all, `maximum_rank_displacement` = 5 for all,
  `quality_stratum_eligibility_coverage` 0.25..1.00 — **(read from run log/probe**,
  `Documents/runs/chunk-35.md:44–54`). The run log's own line writes `component_c 0.09..1.00`
  (`:48`); the dispatch brief writes `0.087..1.00`. This plan uses the **brief/probe value
  0.087..1.00** and does not depend on the second decimal (it fixes no threshold; §3, D35-3).
- **`_score_quality_scatter_figure`'s `sample_fraction` handling** uses
  `_SAMPLE_FRACTION_FALLBACK_MARKER` for a `None` `sample_fraction` and
  `_SAMPLE_FRACTION_MIN_MARKER + sample_fraction * 40.0` otherwise — **(read:** `report.py:1933–1976`).
  Chunk 35's sixth chart **omits marker sizing entirely** (simpler; the lead's preferred option),
  so these constants are not reused.

### 2.1 Skill grounding (CLI unavailable — see the note above)

- **Charts — opportunity scatter** **(read from skill data files:**
  `.kilocode/skills/ui-ux-pro-max/data/charts.csv` row 4, `Data Type = "Correlation /
  Distribution"`): `Best Chart Type = "Scatter Plot or Bubble Chart"`, `When to Use = "Exploring
  relationship between two continuous variables; identifying clusters or outliers"`, `When NOT to
  Use` includes `"fewer than 20 points (patterns aren't meaningful)"`, `Accessibility Notes =
  "Combine marker shapes with direct group labels; color may reinforce but must not be the only
  distinction."` **This has not been confirmed as CLI output; flag as unverified-as-CLI.**
- **Charts — many-series / de-spaghetti** **(read from skill data files:** `charts.csv` row 1,
  `Trend Over Time`): `When NOT to Use` includes `"more than 6 series (visual noise)"`,
  `Accessibility Notes = "Use solid, dashed, and dotted line styles plus direct series labels;
  never distinguish series by hue alone."` **Flag as unverified-as-CLI.**
- **UX — truncated/wrapped labels** **(read from skill data files:** `ux-guidelines.csv` rows 84
  (`Content,Truncation`) and 113 (`Content,Essential Text Truncation`) and 116 (`Content,Compact
  Label Overflow`)): row 84 `Do = "Truncate with ellipsis and expand option"`; row 113
  `Do = "Wrap stack resize or provide a visible full-detail path"`, severity Critical; row 116
  `Do = "Bound only unpredictable values; use nowrap with a shrinkable label; expose full text to
  keyboard pointer and touch users"`. **Flag as unverified-as-CLI.**
- **UX — wide containers / line length** **(read from skill data files:** `ux-guidelines.csv` rows
  21 (`Layout,Container Width`) and 73 (`Typography,Line Length`)): row 21 `Do = "Limit max-width
  for text content (65-75ch)"`; row 73 `Do = "Limit to 65-75 characters per line"`. These bound
  prose (`.heuristic`, `.chart-caption`, `.column-guide ol`) which already use `--measure: 72ch`;
  they do **not** require the whole grid to stay narrow. **Flag as unverified-as-CLI.**
- **Icons — nav** **(read from skill data files:** `icons.csv` rows 1 (`list`), 6 (`house`),
  53 (`chart-bar`), 60 (`file-text`), 67 (`list-bullets`)): every row's `Style = "Outline"` and the
  `Usage` column says `"if decorative beside visible text, set aria-hidden=\"true\"..."`. The
  `Semantic Role` column gives `house`/`chart-bar`/`file-text`/`list-bullets` = `meaningful` and
  `list` = `interactive`; **all** nav icons here sit beside a visible text label, so they are
  decorative (`aria-hidden="true"`) per the skill's own rule. **Flag as unverified-as-CLI.**

### 2.1a Lead CLI returns (run 2026-10-02; verbatim search headers and the rows relied on)

- `search.py "demand competition opportunity quadrant scatter bubble" --domain chart -n 4`
  → "**Found: 3 results**"; **Result 1** `Data Type = "Correlation / Distribution"`,
  `Best Chart Type = "Scatter Plot or Bubble Chart"`, `When to Use = "Exploring relationship
  between two continuous variables; identifying clusters or outliers in a dataset"`,
  `When NOT to Use` includes `"fewer than 20 points (patterns aren't meaningful)"`,
  `Accessibility Notes = "Combine marker shapes with direct group labels; color may reinforce but
  must not be the only distinction."` → **verifies §2.1 row 1.** Note the 24-category run is ≥20
  points, so the scatter is inside the skill's own point-count guard.
- `search.py "slope rank change dumbbell small multiples too many series" --domain chart -n 4`
  → "**Found: 4 results**"; **Result 1** `Data Type = "Trend Over Time"`,
  `When NOT to Use` includes `"more than 6 series (visual noise)"`,
  `Accessibility Notes = "Use solid, dashed, and dotted line styles plus direct series labels;
  never distinguish series by hue alone."` → **verifies §2.1 row 2.** (No dedicated "slope/bump"
  row exists in `charts.csv`; the plan's de-spaghetti presentation is grounded on this
  many-series rule, not on a slope-chart row.)
- `search.py "axis label wrapping multiline long category names" --domain ux -n 5`
  → "**Found: 5 results**"; **Result 1** `Layout, Long Token Wrapping` `Do = "Use overflow-wrap
  anywhere and let flex or grid text children shrink"`; **Result 2** `Content, Truncation`
  `Do = "Truncate with ellipsis and expand option"`; **Result 4** `Content, Compact Label
  Overflow` `Do = "Bound only unpredictable values; use nowrap with a shrinkable label; expose
  full text to keyboard pointer and touch users"`. → supports the two-line wrapped label with a
  full-path disclosure path; the plan's label is a wrap (not a truncation) and keeps the full path
  in hover/table/detail.
- `search.py "ultrawide monitor container max width fill" --domain ux -n 5`
  → "**Found: 2 results**"; **Result 1** `Layout, Container Width` `Do = "Limit max-width for text
  content (65-75ch)"`, `Don't = "Let text span full viewport width"`. → **verifies §2.1 row 4.**
  The rule constrains prose, not the chart grid; the plan keeps `--measure: 72ch` on prose and
  lets only the grid grow.
- `search.py "navigation menu dashboard icon outline" --domain icons -n 6`
  → "**Found: 6 results**"; rows `list`, `house`, `sidebar`, `icon-context-accessibility`,
  `grid-four`, `academia-icon-system`; the `icon-context-accessibility` row states the
  decorative/meaningful rule. → **verifies §2.1 row 5** (the skill's curated catalog is
  Phosphor-branded; see the note below).
- `search.py "metrics gauge performance data tile" --domain icons -n 6` → "**Found: 6 results**";
  rows `chart-bar`, `database`, `chart-pie`, `pulse`, `trend-up`, `trend-down`.
- `search.py "table grid rows data" --domain icons -n 5` → "**Found: 5 results**"; rows
  `list-bullets`, `grid-four`, `database`, `chart-pie`, `pulse`.
- `search.py "document detail text page article" --domain icons -n 5` → "**Found: 5 results**";
  rows `file-text`, `file`, `printer`, `gear`, `house`.
- `search.py "play run action execute icon" --domain icons -n 5` → "**Found: 0 results**"; the
  CLI reports "No matches … the query did not hit the database" and offers closest term
  `caution`. **No database match for a play/run icon** — recorded as such, not invented.

**Icon-set consequence (lead ruling, D35-1 refined).** The skill's curated `icons.csv` catalog is
**Phosphor-only** (every row's `Library = "Phosphor"`); Material Symbols is not a curated family
in the skill data. The operator's item 6 asks to replace the disliked icons with a better modern
set, and the skill's actionable rule is "keep **one** consistent outline family per surface,
decorative beside a visible label → `aria-hidden`". The layout **already uses Phosphor-derived
paths**; the defect the operator named is the **house icon for "Run"** (a wrong metaphor: Run is
an executed pipeline, not a home page) plus the incoherent grid/bars/list mix for the other
sections. The plan therefore uses the skill-grounded **Phosphor outline** family with clearer
metaphors — Run→`play-circle` (no `house` anywhere), KPIs→`gauge`, Charts→`chart-bar`,
Table→`table`, Detail→`file-text` — instead of swapping to a family the skill does not carry.
The keys/names in §4.1 are the ones fixed below; only the underlying SVG path data differs from
the Material Symbols strings the earlier draft named.

---

## 3. Supersession and the four named changes that touch frozen chunk-34 surface

This chunk **builds on** chunk 34. Everything in chunk 34 stands except the items named below,
which chunk 35 **supersedes** or **amends in place**. No public signature changes.

### 3.1 Superseded chunk-34 decisions (named)

1. **Chunk-34 §5.2 leaf-only single-line chart labels (L34-3) is superseded** by the two-line
   wrapped label (§5, D35-5). `_category_leaf_label` is retained as a private building block but
   its single-line return is no longer the chart tick text; a new private helper
   `_category_wrapped_label(row, view)` produces the two-line label. The full path still stays in
   the table/detail/hover; the operator rejected leaf-only because `environment` no longer
   identifies `vfx/particles/environment` (run log item 1).
2. **Chunk-34 §5.1's `category (leaf)` axis titles** are reworded to plain-language axis titles
   in §5.3 (the leaf-only vocabulary no longer describes a two-line label). The axis-title text is
   asserted by the amended-in-place node `test_dashboard_figures_use_mono_numeric_and_sans_label_fonts`
   (§11.2), which keeps its node ID, marker, and key.
3. **The chunk-34 `_RAMP_HEXES` stop values are superseded by the operator hunk** (see §3.2).
4. **Chunk-34's policy-bump presentation (legacy §5.3 direct labels on every series plus a
   legend)** is replaced by the de-spaghetti presentation in §7 (D35-7).

Nothing else in chunk 34 is superseded. The chunk-34 contrast budget (§4.2) is re-derived for the
new ramp in §4.4 because the stop hexes changed.

### 3.2 The `_RAMP_HEXES` baseline breaks two chunk-34 nodes and two CSS constants

The operator's hunk changes `_RAMP_HEXES` to `("#73adf0", "#59e082", "#d0df4d", "#e68d52")`
**(read:** `report.py:274`). The following hard-pin the retired ramp and must be amended **in
place** (same node ID, same marker, same `tests/traceability.json` key):

| Artifact | Current value | What chunk 35 changes it to |
|---|---|---|
| `tests/test_report.py::test_dashboard_policy_bump_has_direct_series_labels_in_ramp_order` (`:2309`; marker `LREQ-RPT-020` `:2308`; key `["LREQ-RPT-020"]` at `tests/traceability.json:1635–1637` **(read)**) | `assert report._RAMP_HEXES == ("#9fd7ea", "#b9dbb0", "#d5dd93", "#e6d489")` (`:2323`) | assert the operator ramp `("#73adf0", "#59e082", "#d0df4d", "#e68d52")` (single source `report._RAMP_HEXES`, not a second literal) |
| `tests/test_report.py::test_dashboard_evidence_scale_is_retuned_to_the_reference_palette` (`:2112`; marker `LREQ-RPT-020` `:2111`; key `["LREQ-RPT-020"]` at `tests/traceability.json:1507–1509` **(read)**) | `expected = ("#9fd7ea", "#b9dbb0", "#d5dd93", "#e6d489")` and asserts the four `--evidence-*` CSS values equal them (`:2122–2136`) | since chunk 35 **removes** the `--evidence-*`/`--ramp-*` CSS tokens (§4), the node keeps `report._EVIDENCE_GRADE_COLOURS == tuple(zip(EVIDENCE_GRADE_ORDER, report._RAMP_HEXES))` and drops the CSS-value assertions; the div-on-white `< 3.0` contrast floor is recomputed for the operator ramp (§4.4) |
| `tests/test_report.py::_EVIDENCE_SCALE_HEXES` module constant (`:1845` **(read)**) | `("#9fd7ea", "#b9dbb0", "#d5dd93", "#e6d489")` | operator ramp; consumed by `test_dashboard_css_uses_the_reference_palette_and_explicit_type_scale` (`:1882`), which is amended in place (§11.2) |
| `tests/test_report.py::_DASHBOARD_CSS_HEXES` module constant (`:1117–1132` **(read)**) | includes `#9fd7ea/#b9dbb0/#d5dd93/#e6d489` (the ramp stops) | replace those four with the operator ramp; no other hex added or removed; consumed by `test_dashboard_css_asset_exists_is_offline_and_uses_the_token_set` (`:1701`), amended in place (§11.2) |

The stylesheet's `--ramp-1..4` / `--evidence-*` values (`dashboard.css:40–49`) are **removed**
outright (§4), so no CSS value mirrors the ramp after this chunk; the header comment that claims
the CSS values mirror `_RAMP_HEXES` is corrected.

### 3.3 The sixth chart adds a chart key, a `div_id`, a component id, and a builder entry

Adding a chart key to `DASHBOARD_CHART_IDS` (`report.py:91–97`) grows the tuple 5→6 and therefore
changes the behaviour of every existing node that **loops** over it. Exact contract in §11.4; the
key/ids are fixed in §3.4.

### 3.4 Exact identifiers for the sixth chart (proposed and fixed here)

| Constant | Value |
|---|---|
| chart key | `demand_competition_scatter` |
| `div_id` | `niche-scout-demand-competition-scatter` |
| component id / role | `("chart-demand-competition-scatter", "demand-competition-scatter")` |
| position in `DASHBOARD_CHART_IDS` | **last**, after `score_quality_scatter` |
| position in `DASHBOARD_COMPONENT_IDS` | **last of the chart entries**, after `chart-score-quality-scatter` and before `kpi-strip` (so the `zip` at `report.py:120–125` stays one-to-one for the chart prefix) |

The `_DASHBOARD_COMPONENT_CHART_IDS` zip (`report.py:120–125`) relies on the chart component ids
appearing first and in the same order as `DASHBOARD_CHART_IDS`; appending the new pair to both
tuples at the same index preserves that invariant.

---

## 4. D35-1 / D35-2 — icon set and colour single source of truth

### 4.1 D35-1 — Phosphor outline nav icons (inline SVG, offline)

Keep **one consistent outline family** and fix the metaphors. The layout already uses
Phosphor-derived paths; the skill's curated `icons.csv` catalog is Phosphor-only (§2.1a), so this
chunk stays in that family and replaces the wrong "house = Run" metaphor and the incoherent
`grid-four`/`list-bullets`/`list` mix. This is a **private** change: `_DASHBOARD_NAV_ITEMS`
(`report.py:1561`) keeps its `(href, label, icon_key)` shape; the icon **keys** and the path data
change.

New nav item mapping (replaces `house`/`grid-four`/`chart-bar`/`list-bullets`/`list`):

| Section | Label | New icon key | Phosphor name | Why |
|---|---|---|---|---|
| `#run-header-block` | Run | `play-circle` | `PlayCircle` | Run is an executed pipeline; `house` implied a home page (the operator's complaint) |
| `#kpi-strip` | KPIs | `gauge` | `Gauge` | A gauge reads as a summary metric tile |
| `#chart-grid` | Charts | `chart-bar` | `ChartBar` | Unchanged — already correct |
| `#primary-table-section` | Table | `table` | `Table` | A table glyph, not a bullet list |
| `#detail-section` | Detail | `file-text` | `FileText` | A detail/article glyph |

Contract:

- `_NAV_ICON_PATHS: dict[str, str]` holds **one path per key**, each in the existing
  `viewBox="0 0 256 256"` Phosphor geometry (so `_nav_svg`'s viewBox is **unchanged**); keys are
  the five above only.
- `_nav_svg(icon_key)` keeps `width="20" height="20"`, `fill="#8fb0bf"` (the `--muted-fg`
  reference value), `aria-hidden="true"`, `focusable="false"`. The data-URI percent-encoding path
  (`_svg_data_uri`, `report.py:1626`) is unchanged.
- The icon stays a `dash_html.Img` with `alt=""` and `aria-hidden="true"` (decorative beside the
  visible `.nav-label` text) — `_nav_icon` (`report.py:1644`) is unchanged.
- **Offline:** no URL, no font load, no `<use>` referencing an external sheet. The XML namespace
  inside the data URI remains the only scheme-bearing string; the existing node
  `test_dashboard_layout_has_minimal_anchor_navigation_with_inline_svg_and_skip_link` (`:1917`)
  asserts this and stays green unchanged.

The icon path data (the five Phosphor outline glyph `d` strings) is fixed at implementation time
from the Phosphor `256×256` outline set, matching the existing path style; the plan fixes the
**keys, names, viewBox, and attributes**, not the literal `d` strings (which are data, like
today's paths).

### 4.2 D35-2 — remove non-functional CSS colour tokens

In `src/niche_scout/assets/dashboard.css`, **remove** the following declared tokens, because a
grep of the stylesheet proves no rule consumes them **(counted:** pattern
`var\(--ramp-|var\(--evidence-`, zero matches):

- `--ramp-1`, `--ramp-2`, `--ramp-3`, `--ramp-4` (`dashboard.css:40–43`)
- `--evidence-insufficient`, `--evidence-weak`, `--evidence-moderate`, `--evidence-strong`
  (`dashboard.css:46–49`)

Keep every token a rule actually consumes: `--bg`, `--surface`, `--surface-2`, `--border`, `--fg`,
`--muted-fg`, `--primary`, `--accent`, `--positive`, `--danger`, the `--font-sans`/`--font-mono`
stacks, the size/weight scales, spacing/radius/focus tokens, `--measure`, `--table-row-height`,
`--nav-topbar-height`, `--nav-rail-width`, `--chart-height`, `--z-header`.

Correct the two header/definition comments that frame the ramp/evidence tokens as mirrors of
`_RAMP_HEXES`:

- The file header comment (`dashboard.css:1–21`) currently lists "reference palette" tokens; it
  must not claim a CSS colour token mirrors `_RAMP_HEXES`.
- The block comment at `dashboard.css:36–39` ("Figures bake the same hexes as literals … these
  tokens document the ramp and mirror `report._RAMP_HEXES`") and the comment at `:45` are removed
  with the tokens.

After this chunk the only functional colour source is `report.py` (`_RAMP_HEXES` and the figure
literals). The stylesheet's remaining semantic tokens (`--primary`, `--accent`, `--positive`,
`--danger`, surfaces) are consumed by rules and stay.

### 4.3 D35-2 test consequence

`test_dashboard_evidence_scale_is_retuned_to_the_reference_palette` (`:2112`) currently asserts the
four `--evidence-*` CSS values (`:2128–2136`); those assertions are removed (the tokens no longer
exist) and the node keeps its `report._EVIDENCE_GRADE_COLOURS == zip(EVIDENCE_GRADE_ORDER,
_RAMP_HEXES)` assertion plus the contrast floor (§11.2). `_DASHBOARD_CSS_TOKENS` (`:1077–1109`)
already does **not** list any `--ramp-*`/`--evidence-*` token **(read:** the tuple), so the
token-set node needs no token-set edit — only the four hex values in `_DASHBOARD_CSS_HEXES` change.

### 4.4 Contrast budget for the operator ramp (re-derived; hand-computed)

Surfaces: plot/card `--surface #112d3b`. Ratio `(L_light + 0.05) / (L_dark + 0.05)` on linearised
sRGB. The operator ramp is a **diverging-style** four-stop ramp (blue → green → lime → orange), not
the chunk-34 analogous ramp; the contrast floor is re-checked rather than inherited.
**Hand-computed with the WCAG relative-luminance formula; reproducible from the formula; not
tool-verified this session.** Implementers/tests must compute the actual ratios with the existing
`_relative_luminance`/`_contrast_ratio` helpers (`tests/test_report.py:2089–2108`) and, if any stop
is below 3:1 on `#112d3b`, stop and flag rather than silently accepting it. The mode bar stays
disabled (`report.py:1923`, `config={"displayModeBar": False}`), so no ramp colour is placed on the
white `#modeBar` surface.

---

## 5. D35-5 — two-line wrapped category labels (item 1)

### 5.1 New private helper (exact signature)

```python
def _category_wrapped_label(row: CategoryReportRow, view: RunReportView) -> str:
    """Return the two-line chart label for ``row``: leaf plus its parent segment.

    The returned string is a Plotly multi-line tick label: line 1 is the final
    ``/``-segment (the leaf), line 2 is the immediately preceding segment, joined
    by ``"<br>"``. ``"vfx/particles/environment"`` -> ``"environment<br>particles"``.
    A category with one segment is returned unchanged (one line). A category with
    exactly two segments -> ``"leaf<br>first-segment"``.

    When two or more rows in ``view`` share the same *two-line* label, the label
    is disambiguated deterministically by appending ``" · <full parent path>"`` to
    line 2, so no two visible ticks collide; the suffix is applied to every member
    of a colliding group, never to a non-colliding row. Deterministic: counts are
    taken over ``view.categories`` (an ordered tuple); no set/dict iteration; no
    clock, no I/O. Never changes a number, rank, or measured value. The full path
    stays in the primary table cell, the column guide, the selector, and the
    category detail heading; hover ``customdata`` also carries the full path.
    """
```

Wrapping rule (fixed):

1. `segments = row.category.split("/")`.
2. If `len(segments) == 1`: `leaf = segments[0]`, parent line = `None` (single line).
3. Else: `leaf = segments[-1]`, `parent = segments[-2]`; base label `f"{leaf}<br>{parent}"`.
4. Collision count over the **base two-line label** across `view.categories` (a `dict`/`Counter`
   keyed by the base label; the iterated view is ordered). If a base label occurs more than once,
   every member returns `f"{leaf}<br>{parent} · {row.category.rsplit('/', 1)[0]}"`; otherwise the
   base label.

This replaces **leaf-only** entirely: `environment` now reads `environment<br>particles`, so
`vfx/particles/environment` is identifiable, satisfying the operator's item 1.

### 5.2 Multi-line tick error tolerance (Plotly `<tspan>`)

Plotly renders a tick string containing `<br>` as multiple SVG `<tspan>` lines. The helper returns
a plain string with the literal substring `"<br>"`; no HTML is constructed. This is error-tolerant:
a label with no `<br>` is one `<tspan>`; a label with one `<br>` is two. No `\n` is used (a bare
newline is not a Plotly line break and would render literally), and the helper never emits raw
`<`/`>` other than the exact `"<br>"` join token.

### 5.3 Call sites (all chart category axes/legends; full path preserved in hover)

| Builder | Label site | Change |
|---|---|---|
| `_score_bar_figure` (`report.py:1714`) | `y=labels` (`:1726`, `:1743`) and the refused annotation (`:1760`) | `labels = [_category_wrapped_label(row, view) for row in scored]`; `customdata = [[row.category, row.evidence_grade] for row in scored]` (unchanged from chunk 34); refused annotation uses the wrapped label + `" (refused)"` |
| `_contribution_figure` (`:1777`) | `x=labels` (`:1785`, `:1791`) | `labels = [_category_wrapped_label(row, view) for row in scored]` |
| `_population_lollipop_figure` (`:1843`) | `y=labels` (`:1858`, `:1880`, `:1893`) | `labels.append(_category_wrapped_label(row, view))`; `customdata` keeps `[[row.category] …]` |
| `_policy_bump_figure` (`:1807`) | series label / `legendgroup` | wrapped label (see §7) |
| `_score_quality_scatter_figure` (`:1933`) | `text=labels` (`:1956`, `:1963`) | `labels.append(_category_wrapped_label(row, view))`; `customdata` keeps `[row.category, text]` |
| `_demand_competition_scatter_figure` (new) | hover `text` | wrapped label; `customdata` carries `[row.category]` (§3/§10) |

The axis-title label is reworded from `"category (leaf)"` (chunk 34 §5.1) to a plain-language
title that describes the two-line label:
`"category (leaf, then parent)"`. This title is asserted by the amended-in-place node
`test_dashboard_figures_use_mono_numeric_and_sans_label_fonts` (§11.2). The full path remains in
the DataTable cell, the Column guide, the selector option, and the detail heading
(`report.py:2206`), all untouched.

---

## 6. D35-6 — contribution legend fits its content (item 2)

Make the 4-item legend fit inside the card without scrolling by moving it **horizontal, below the
plot**, exactly as the population chart already does, and reclaiming plot height:

```python
figure.update_layout(**_base_layout())
figure.update_layout(
    barmode="stack",
    legend={
        "orientation": "h",
        "yanchor": "top",
        "y": -0.28,
        "xanchor": "center",
        "x": 0.5,
        "font": {"color": "#e6f0f4", "family": _FIGURE_FONT_MONO, "size": 11},
    },
)
```

- Four entries (D/C/R/Q) at font size 11 in a horizontal row fit the 360px card width; no vertical
  scroll and no clipped "Demand" (run log item 2).
- The margin bottom is raised from the `_base_layout` value so the horizontal legend is not
  clipped: add `margin={"l": 8, "r": 56, "t": 48, "b": 64}` on this figure only (the shared
  `_base_layout` is unchanged).
- The plot keeps a usable area (≈360 − title/caption − 64px legend band); the legend no longer
  consumes plot width.

---

## 7. D35-7 — policy-rank comparison de-spaghetti (item 3)

The operator's constraint is that the chart is unreadable. Keep the persisted per-policy ranks as
the data; drop the legend; show only the categories whose rank **actually changes** across the
persisted policies, with direct labels at both endpoints; never hide a category that has a
persisted rank (those appear in a "stable" note rendered inside the card, not a legend).

Grounding **(read from skill data files:** `charts.csv` row 1, `Trend Over Time`): more than 6
series is visual noise; use direct series labels and line styles, never hue alone. The run log
counted 18 series in the legend for the audited run (`Documents/runs/chunk-35.md:34`) **(read from
run log)**. Flag the skill citation as unverified-as-CLI.

Contract for `_policy_bump_figure(view)`:

1. Build `rows = _policy_rank_rows(view)` as today (unchanged; the persisted tuple is untouched).
2. For each row, compute the set of its **non-`None`** ranks. A row is **changing** iff that set
   has ≥2 distinct values; otherwise it is **stable**. A row with <2 non-`None` ranks keeps its
   current behaviour (it is drawn as a gap-only series or skipped exactly as today; no rank is
   invented).
3. Draw one `go.Scatter` per **changing** row (same axes, `connectgaps=False`), with the wrapped
   label as `name`/`legendgroup` and direct endpoint text; stable rows are collected into a single
   in-card text line under the plot: `"Stable across policies: <comma-separated wrapped labels>"`.
4. **Legend off:** `figure.update_layout(showlegend=False)`; the direct labels and the stable note
   carry identity. No legend repeats the chart-area names.
5. Direct labels: first policy point carries the wrapped label (`text=[label, "", ""]`,
   `textposition="middle right"`); a follow-up empty trace or annotation is not added. The
   presentation must remain readable at 18 series: because stable rows (the majority in flat runs)
   collapse to the note, the number of drawn lines is the number of genuinely changing categories.

This keeps every category with a persisted rank visible (changing ones as lines, stable ones as the
note) and removes the duplicated legend. It does not recompute, reorder, or drop a persisted rank.

---

## 8. D35-8 — population chart: remove the constant sample-size series (item 4)

In `_population_lollipop_figure` (`report.py:1843`), **delete** the third `go.Scatter` trace
(`name="sample size"`, `:1909–1917`) and its `samples` list construction (`:1854`, `:1874`); keep:

- the `discovered population` trace (`:1877–1888`) with its ramp-1 colour, `size=12`;
- the `measured zero` trace (`:1889–1908`) with `diamond-open`, `#e27882`, `line.width 2`;
- the log-scale x-axis (`update_xaxes(type="log", …)`) and the horizontal legend (now two items).

Rationale (run log item 4): `enriched_sample_count` is 100 for every row in large categories, so
the sample-size marker is a vertical column of identical dots with no signal.

The **title** `"Population and sample size (log scale)"` (`report.py:232`) is now inaccurate. It is
changed to **`"Discovered population (log scale)"`**. No existing pinned node asserts the old title
— **(counted:** the string `"Population and sample size"` occurs only in `report.py:232` and in the
caption keyed to `population_lollipop` (`report.py:215–219` carries the word "population … sample
size"); grep of `tests/` for the exact title returned no match). The caption at
`report.py:215–219` is updated to drop the sample-size clause while keeping the explicit-zero note.
`test_dashboard_charts_carry_explanations_and_human_labels` (`:1507`) asserts
`_DASHBOARD_CHART_TITLES[chart_key] in held` and `_DASHBOARD_CHART_CAPTIONS[chart_key] in held`
**(read:** `:1513–1517`), so it reads the new values automatically and stays green **unchanged**.

---

## 9. D35-3 / D35-4 — the sixth chart and the ultrawide layout

### 9.1 D35-3 — Demand vs Competition opportunity scatter (fixed)

New private builder (exact signature):

```python
def _demand_competition_scatter_figure(view: RunReportView) -> go.Figure:
    """Demand-vs-Competition scatter of scored categories (no threshold lines).

    x is persisted ``row.component_d`` and y is persisted ``row.component_c`` for
    :func:`_scored_rows` only. A row whose ``component_d`` **or** ``component_c``
    is ``None`` renders **no marker** (a gap), never a marker at ``0`` — the
    missing-not-zero contract. No quadrant, median, or split reference line and no
    threshold value is drawn or implied: the SRS defines no "high demand / low
    competition" threshold (SRS §8.2 LREQ-SCR-010 / LREQ-SCR-020), so none may be
    invented. Fixed ``xaxis``/``yaxis`` range ``[0, 1]`` (the components' clamp
    domain), monochrome ramp-1 markers, marker size fixed. Hover shows the wrapped
    label and the full category path.
    """
```

Implementation contract:

- `rows = _scored_rows(view)`; `xs = [r.component_d if not None else None]`;
  `ys = [r.component_c …]`; a row with either `None` renders no marker (Plotly skips `None`).
  **No `or 0`, `.get(..., 0)`, or fallback.** Size is **fixed** (e.g. `size=10`), colour
  `_RAMP_HEXES[0]`; the sixth chart does **not** size by `sample_fraction` (the lead's preference;
  avoids a second `None` policy on the card).
- `mode="markers"`; `text=[_category_wrapped_label(r, view) for r in rows]`;
  `customdata=[[r.category] for r in rows]`;
  `hovertemplate="%{text}<br>category: %{customdata[0]}<br>Demand %{x}<br>Competition %{y}<extra></extra>"`.
- `figure.update_layout(**_base_layout())`; `update_layout(showlegend=False)` (single series);
  `update_xaxes(range=[0.0, 1.0], title={"text": "Demand (higher = more demand)"})`;
  `update_yaxes(range=[0.0, 1.0], title={"text": "Competition (higher = less crowded)"})`.
- **No shape/annotation/reference line** is added anywhere in the figure.

The four constant additions (fixed):

```python
# in DASHBOARD_CHART_IDS, appended last:
("demand_competition_scatter", "niche-scout-demand-competition-scatter"),

# in DASHBOARD_COMPONENT_IDS, appended after the score-quality-scatter pair:
("chart-demand-competition-scatter", "demand-competition-scatter"),

# in _DASHBOARD_CHART_TITLES:
"demand_competition_scatter": "Demand vs competition (scored categories)",

# in _DASHBOARD_CHART_CAPTIONS:
"demand_competition_scatter": (
    "This shows each scored category by its Demand and Competition components; "
    "read top-left as higher demand with less crowding (higher Competition = "
    "less crowded), and a missing component as no plotted point. This is a "
    "within-run heuristic, not a sales or demand prediction."
),
```

and in `_chart_figure`'s `builders` dict (`report.py:1986–1992`):
`"demand_competition_scatter": _demand_competition_scatter_figure`.

The title/caption orientation is grounded in SRS §8.2 `LREQ-SCR-010` (Demand: higher = more
demand) and `LREQ-SCR-020` (`C = clamp(1 - P_ref(BreadthRaw))`: higher = less crowded). **No
threshold, no split line, no quadrant is drawn or named.** A future chunk may add a split only if a
human rules an SRS threshold (§15).

### 9.2 D35-4 — ultrawide fill (item 8)

Change `.dashboard` (`dashboard.css:109–124`) so it grows past 1600px on large screens while the
1/2/3-column grid breakpoints are unchanged:

- Remove `max-inline-size: 1600px` and replace it with a large-screen cap:
  `max-inline-size: none;` in the base rule, plus a **large-screen cap** so the page does not
  become unreadable on very wide monitors:
  ```css
  @media (min-width: 1800px) {
    .dashboard {
      max-inline-size: 2200px;
    }
  }
  ```
  Between 1024px and 1800px the container fills available width
  (`margin-inline: auto` with a `none` cap); above 1800px it is capped at 2200px and centred. At
  2560×1080 the content right edge moves from ~1760 to ~2450, eliminating the measured 800px dead
  space (run log item 8).
- Keep the existing `.dashboard` padding progression (base `--space-4`, `≥768 --space-5`,
  `≥1024 --space-6`) and the `≥1024` `margin-inline-start: calc(var(--nav-rail-width) +
  var(--space-6))`.
- `.chart-card` grid columns stay `span 12` (base), `span 6` (`≥768`), `span 6` (`≥1024`),
  `span 4` (`≥1440`) — **unchanged**. With the sixth card, `≥1440` gives a clean 3×2 grid and
  `≥768`/`≥1024` a clean 2×3 grid (no empty slot; the run log's empty-sixth-slot defect at 5 cards
  is resolved by the sixth chart, item 7).
- `overflow-wrap`/`min-inline-size: 0` on the chart cards (already `min-width: 0`) is retained, so
  wide containers do not force horizontal scroll.

---

## 10. Files touched (file-discipline list)

- `src/niche_scout/report.py` — `_NAV_ICON_PATHS` + `_DASHBOARD_NAV_ITEMS` + `_nav_svg` viewBox
  (D35-1); `_category_wrapped_label` and its five call-site rewires + axis-title reword (D35-5);
  `_contribution_figure` legend/margin (D35-6); `_policy_bump_figure` de-spaghetti (D35-7);
  `_population_lollipop_figure` trace removal + title/caption (D35-8); `_demand_competition_scatter_figure`
  + the four constant additions + `builders` entry (D35-3).
- `src/niche_scout/assets/dashboard.css` — remove `--ramp-*`/`--evidence-*` tokens and the two
  comments that mirror them (D35-2); `.dashboard` ultrawide change + `@media (min-width: 1800px)`
  (D35-4).
- `tests/test_report.py` — new nodes (§11.1); amended-in-place nodes and constants (§11.2).
- `tests/traceability.json` — new keys (§11.1); amended-in-place nodes keep their keys.
- `tests/fixtures/report_fixtures.py` — only if the test author needs a new two-segment/short-path
  category constant for the wrapped-label collision vector (§11.5); no other fixture change.
- `Documents/runs/chunk-35.md` (lead-owned) and this plan — not edited by the implementer.

No other file is in scope. Any other file needing a change is a stop-and-flag.

---

## 11. Test plan (proportionate)

Every analytical node carries `@pytest.mark.lreq(...)` and a matching `tests/traceability.json`
key. New markers use only `LREQ-RPT-010/020/030/040`. No existing node ID or traceability key is
renamed or removed. Per the operator, dashboard testing is not a breaking point: this is a small set
of new nodes plus in-place amendments, not an exhaustive matrix.

### 11.1 New nodes in `tests/test_report.py`

| Node ID | Marker(s) | Asserts |
|---|---|---|
| `tests/test_report.py::test_dashboard_chart_labels_wrap_leaf_then_parent_on_two_lines` | `LREQ-RPT-010` | `_category_wrapped_label` returns `"<leaf><br><parent>"` for a multi-segment category (e.g. `vfx/particles/environment` → `environment<br>particles`); a one-segment category is unchanged; a colliding base label appends `" · <parent path>"` for every member of the group; the score-bar/contribution/population/scatter figures carry the wrapped strings; the full path is still present in the layout (`row.category in _norm(layout)`); two builds are equal; the new `.split("<br>")` count is 2 for a wrapped label |
| `tests/test_report.py::test_dashboard_population_figure_drops_the_constant_sample_series` | `LREQ-RPT-010` | The population figure has exactly **two** traces (`discovered population`, `measured zero`); no trace `name == "sample size"`; the `diamond-open`/`#e27882` measured-zero marker survives; `xaxis.type == "log"`; `"Population and sample size"` no longer appears; `_DASHBOARD_CHART_TITLES["population_lollipop"] == "Discovered population (log scale)"` |
| `tests/test_report.py::test_dashboard_policy_bump_drops_legend_and_keeps_only_changing_series` | `LREQ-RPT-020` | `_policy_rank_rows(view)` equality is unchanged (persisted tuple); the bump figure `layout.showlegend is False`; only rows whose non-`None` ranks are not all equal are drawn as traces; every stable scored row's wrapped label appears in an in-card text line; `connectgaps is False` on every drawn trace; no category with a persisted rank is absent from the figure text |
| `tests/test_report.py::test_dashboard_demand_competition_scatter_reads_persisted_components_only` | `LREQ-RPT-010` | The sixth figure exists under `niche-scout-demand-competition-scatter`; `x`/`y` equal the scored rows' `component_d`/`component_c` with `None` preserved (no `0` substitution); axes range `[0,1]`; **no** shape/annotation/reference line exists in `figure["layout"]` (assert `"shapes" not in layout` and `"annotations" not in layout`); `showlegend is False`; hover carries the full path; the title is `"Demand vs competition (scored categories)"` and the caption contains the `LREQ-SCR-010`/`LREQ-SCR-020` orientation wording; `DASHBOARD_CHART_IDS` last entry is the new pair; `len(DASHBOARD_CHART_IDS) == 6` and `len(DASHBOARD_COMPONENT_IDS) == 11` |
| `tests/test_report.py::test_dashboard_nav_icons_are_phosphor_outline_and_offline` | `LREQ-RPT-010` | `_DASHBOARD_NAV_ITEMS` icon keys are exactly `("play-circle","gauge","chart-bar","table","file-text")` in document order; `_NAV_ICON_PATHS` has exactly those five keys and no retired key (`house`/`grid-four`/`list-bullets`/`list`); `_nav_svg` emits `viewBox="0 0 256 256"`; each nav `Img` is `alt=""`/`aria-hidden="true"` and its data URI is inline SVG (no external URL) |
| `tests/test_report.py::test_dashboard_css_removes_the_duplicate_colour_tokens` | `LREQ-RPT-010` | `dashboard.css` contains **no** `--ramp-1`..`--ramp-4` and **no** `--evidence-*` declaration; the header no longer claims a CSS ramp mirrors `_RAMP_HEXES`; offline assertions (`http`/`https`/`@import`/`url(`) hold; a retained consumed token (e.g. `--danger`, `--muted-fg`) is still declared |
| `tests/test_report.py::test_dashboard_css_fills_ultrawide_and_keeps_grid_breakpoints` | `LREQ-RPT-010` | `.dashboard` base rule has no `max-inline-size: 1600px` (or `max-inline-size: none`); `@media (min-width: 1800px)` sets a large cap (`max-inline-size: 2200px`); the `≥768`/`≥1024`/`≥1440` `.chart-card` `span` rules are unchanged; offline assertions hold |

`tests/traceability.json` new keys (node-ID → LREQ list):

- `...::test_dashboard_chart_labels_wrap_leaf_then_parent_on_two_lines` → `["LREQ-RPT-010"]`
- `...::test_dashboard_population_figure_drops_the_constant_sample_series` → `["LREQ-RPT-010"]`
- `...::test_dashboard_policy_bump_drops_legend_and_keeps_only_changing_series` → `["LREQ-RPT-020"]`
- `...::test_dashboard_demand_competition_scatter_reads_persisted_components_only` → `["LREQ-RPT-010"]`
- `...::test_dashboard_nav_icons_are_phosphor_outline_and_offline` → `["LREQ-RPT-010"]`
- `...::test_dashboard_css_removes_the_duplicate_colour_tokens` → `["LREQ-RPT-010"]`
- `...::test_dashboard_css_fills_ultrawide_and_keeps_grid_breakpoints` → `["LREQ-RPT-010"]`

### 11.2 Amended in place (same node ID, same marker, same `tests/traceability.json` key)

Verified by reading each node this session:

- **(a)** `test_dashboard_policy_bump_has_direct_series_labels_in_ramp_order` (`:2309`; marker
  `LREQ-RPT-020` `:2308`; key `["LREQ-RPT-020"]` `tests/traceability.json:1635–1637`): the
  `_RAMP_HEXES` literal assertion (`:2323`) becomes the operator ramp **read from
  `report._RAMP_HEXES`**, and the series-count/colour assertions adapt to the de-spaghetti
  presentation (§7): only changing series are drawn, and the legacy per-series count assertion
  (`len(bump["data"]) == len(_policy_rank_rows(view))`) is replaced by "drawn series == changing
  rows; stable rows appear in the in-card note". `connectgaps is False` on every drawn trace stays.
- **(b)** `test_dashboard_evidence_scale_is_retuned_to_the_reference_palette` (`:2112`; marker
  `LREQ-RPT-020` `:2111`; key `["LREQ-RPT-020"]` `tests/traceability.json:1507–1509`): `expected`
  becomes `report._RAMP_HEXES` (operator ramp); the four `--evidence-*` CSS-value assertions are
  removed (tokens deleted, §4.2); the div-on-white `< 3.0` contrast floor is recomputed for the
  operator ramp with the existing helpers.
- **(c)** `test_dashboard_figures_use_mono_numeric_and_sans_label_fonts` (`:2272`; marker
  `LREQ-RPT-010` `:2271`; key `["LREQ-RPT-010"]` `tests/traceability.json:1632–1634`): iterates
  `DASHBOARD_CHART_IDS`, so it now covers the sixth figure automatically; the axis-title assertion
  (`:2303`) changes `"category (leaf)"` → `"category (leaf, then parent)"`.
- **(d)** `test_dashboard_css_uses_the_reference_palette_and_explicit_type_scale` (`:1882`; marker
  `LREQ-RPT-010` `:1881`; key `["LREQ-RPT-010"]` `tests/traceability.json:1494–1496`):
  `_EVIDENCE_SCALE_HEXES` (`:1845`) becomes the operator ramp; the reference-palette and
  type/weight-token assertions are unchanged.
- **(e)** `test_dashboard_css_asset_exists_is_offline_and_uses_the_token_set` (`:1701`; marker
  `LREQ-RPT-010` `:1700`; key `["LREQ-RPT-010"]` `tests/traceability.json:1475–1477`):
  `_DASHBOARD_CSS_HEXES` (`:1117–1132`) replaces the four retired ramp stops with the operator
  ramp; no other hex changes; the token-set/class/breakpoint assertions are unchanged.
- **(f)** `test_dashboard_css_recolors_evidence_ramp_and_boxes_nav_links` (`:2422`; marker
  `LREQ-RPT-010` `:2421`; key `["LREQ-RPT-010"]` `tests/traceability.json:1641–1643`): the
  `--ramp-*`/`--evidence-*` value assertions are **removed** (the tokens no longer exist, §4.2);
  the offline assertions and `box-sizing` nav-link assertion stay.

### 11.3 Pinned nodes that MUST stay green **unchanged**

Verified by reading each; none asserts a chart count or a five-element tuple. `DASHBOARD_CHART_IDS`
grows 5→6; the following either loop over the tuple (and therefore absorb the sixth chart) or do not
touch it:

1. `test_build_dashboard_layout_is_deterministic_for_a_fixed_view` (`:1397`) — loops
   `DASHBOARD_COMPONENT_IDS`; absorbs the new component id.
2. `test_build_dashboard_app_layout_matches_the_layout_builder` (`:1411`).
3. `test_dashboard_layout_shows_every_primary_table_column_by_default` (`:1425`) — 30 columns.
4. `test_dashboard_detail_panel_covers_rpt_030_items_for_a_selected_category` (`:1440`).
5. `test_dashboard_layout_keeps_refused_categories_visible_and_off_the_scored_axis` (`:1468`).
6. `test_dashboard_layout_includes_the_heuristic_statement` (`:1495`).
7. `test_dashboard_distinguishes_null_from_explicit_zero` (`:1532`).
8. `test_dashboard_has_no_confidence_interval_or_error_bars` (`:1578`) — the sixth chart must add
   no `error_x`/`error_y` and no "confidence interval"/"error bar" wording.
9. `test_dashboard_policy_bump_and_kpi_tiles` (`:1594`) — loops bump `["data"]`; under §7 the
   drawn series are a subset, and the node only asserts `connectgaps is False` and a non-empty
   first `text`. **Risk:** the fixture's three scored rows have distinct per-policy ranks (changing
   rows), so all three are still drawn; the node's per-trace assertions hold. If the fixture ever
   makes a row stable, the node's `"text" in trace["mode"]` loop still holds only for drawn
   traces — the implementer must confirm this node passes unchanged or move it to §11.2.
10. `test_dashboard_score_bar_encodes_ordinal_evidence_grade` (`:1643`).
11. `test_dashboard_omits_the_coverage_heatmap` (`:1669`) — loops `DASHBOARD_CHART_IDS` as a set;
    asserts only that `status_heatmap`/`component_dumbbell` are absent (still true).
12. `test_html_output_is_self_contained_and_deterministic`, `test_write_run_report_*`, the static
    path nodes.
13. `test_dashboard_css_is_declared_as_package_data` (`:1736`).
14. `test_dashboard_app_serves_the_package_assets_folder` (`:1747`).
15. `test_dashboard_uses_progressive_disclosure_without_dropping_mandated_content` (`:1769`).
16. `test_public_report_functions_have_hints_and_docstrings` (`:1023`) — the new private builder
    `_demand_competition_scatter_figure` and `_category_wrapped_label` are private; if this node
    scans public functions only, it is unaffected. **(read:** its scope is the public report API).
17. `test_dashboard_layout_has_minimal_anchor_navigation_with_inline_svg_and_skip_link` (`:1917`) —
    loops `DASHBOARD_COMPONENT_IDS` and asserts nav anchors; the icon path/viewBox change is
    compatible (asserts `src.startswith("data:image/svg+xml")`, `aria-hidden`, `alt=""`, no
    external URL).
18. `test_dashboard_column_guide_discloses_every_primary_column_label` (`:2029`).
19. `test_dashboard_charts_use_automargin_for_long_category_labels` (`:2060`) — checks three named
    charts only; the sixth chart also sets `automargin` via `_base_layout`, harmless.
20. `tests/test_end_to_end.py::test_acceptance_rendered_report_contains_required_fields`.
21. `tests/test_quality_tooling.py::test_report_module_has_no_forbidden_imports_or_clock_reads`.

`test_dashboard_charts_carry_explanations_and_human_labels` (`:1507`) loops `DASHBOARD_CHART_IDS`
and reads `_DASHBOARD_CHART_TITLES`/`_DASHBOARD_CHART_CAPTIONS` for each key; with the new
title/caption entries it stays green **unchanged** and is therefore in §11.3, not §11.2.

### 11.4 Chart-count / loop audit (counted claim)

**Counted:** reading `tests/test_report.py` returned exactly these loop/iterate sites over
`DASHBOARD_CHART_IDS` or `DASHBOARD_COMPONENT_IDS`: `:1404` (component ids), `:1513` (captions/
titles), `:1673` (chart-key set), `:2021` (component ids), `:2072` (`div_ids` lookups of three
named keys), `:2161` (`div_ids` lookups), `:2235` (`div_ids["population_lollipop"]`), `:2256`
(`div_ids` lookups of two named keys), `:2283–2284` (font node, loops all div_ids), `:2321`/`:2362`
(`div_ids["policy_bump"]`). Unit = matched source lines. **No site asserts a literal chart count or
a five-element length**; the only literal lengths are `len(bump["data"]) == len(_policy_rank_rows)`
at `:2324`/`:2364`/`:2365`, which §11.2(a) adapts. No `div_id` string equal to the new
`niche-scout-demand-competition-scatter` occurs in the test file before this chunk.

### 11.5 Fixtures

Reuse `tests/fixtures/report_fixtures.py::dashboard_rows()` via `_dashboard_view(tmp_path)`. The
allowed-label collision vector reuses the existing `CATEGORY_COLLISION_FIRST="a/x/Foo"` /
`CATEGORY_COLLISION_SECOND="b/y/Foo"` constants (both have two path segments; their wrapped base
labels collide on `Foo<br>x`/`Foo<br>y`? no — `a/x/Foo` → `Foo<br>x`, `b/y/Foo` → `Foo<br>y`, which
do not collide; the test author may add a two-segment collision pair to `report_fixtures.py` and its
`__all__` if a same-base collision is needed, mirroring the existing pattern). No new arithmetic, so
no new golden vector; no fixture credentials, no network, no live path.

---

## 12. Definition of Done / gate bullets

- [ ] `python -m pytest -q` — full suite green: the seven new nodes pass; every §11.3 pinned node
      passes **unchanged**; every §11.2 amended node passes in its amended form; no other tree
      change.
- [ ] `python -m niche_scout.tools.validate_traceability` — exit 0; each new node has a marker and
      a matching key; no orphan entry.
- [ ] `python -m niche_scout.tools.check_import_boundaries` — exit 0.
- [ ] `python -m niche_scout.tools.check_scope_prohibitions` — exit 0.
- [ ] `ruff format --check` and `ruff check` clean on changed Python files (CSS is not linted).
- [ ] Chart category ticks show the two-line `leaf<br>parent` label on every category axis/legend;
      the full path remains in the primary table cell, the column guide, the selector, and the
      detail heading; collisions are disambiguated deterministically; the label is error-tolerant
      for Plotly `<tspan>` (test asserts the `<br>` count).
- [ ] The contribution legend is horizontal, below the plot, fits 4 entries with no scroll; the
      population figure has exactly two traces (no `sample size`); the policy-bump figure has no
      legend and draws only changing series with stable rows in an in-card note; no category with a
      persisted rank is hidden.
- [ ] The sixth chart is the threshold-free Demand-vs-Competition scatter reading only
      `component_d`/`component_c` of scored rows; `None` renders no marker; no shape/annotation/
      threshold exists; `DASHBOARD_CHART_IDS`/`DASHBOARD_COMPONENT_IDS`/captions/titles/`builders`
      all carry the new key at the **last** chart position.
- [ ] `dashboard.css` contains no `--ramp-*`/`--evidence-*` tokens and no comment claiming a CSS
      ramp mirrors `_RAMP_HEXES`; consumed semantic tokens remain; offline assertions hold.
- [ ] `.dashboard` grows past 1600px and caps at 2200px above 1800px; the `≥768`/`≥1024`/`≥1440`
      `.chart-card` span rules are unchanged; no horizontal scroll at 2560.
- [ ] Nav icons are the five Phosphor outline keys with the existing 256×256 viewBox,
      `aria-hidden="true"`, `alt=""`, inline data URI, no external URL, and no `house` key.
- [ ] `report.py` imports no `metrics`/`scoring`/`collector*`/`config`/`pipeline`/`cli` and reads no
      clock; no new Dash callback; every `DASHBOARD_COMPONENT_IDS` id preserved; two builds equal.
- [ ] No file outside §10 changed; the standing obligations (URI extraction, OI-6, `taxonomy_sha256`)
      are untouched.
- [ ] Lead UI verification (§13) recorded in `Documents/runs/chunk-35.md`.

---

## 13. UI verification (lead, Kilo Playwright — required)

The lead must re-measure the served dashboard (`python -m niche_scout dashboard`, loopback) after
implementation, at three viewports, and record the results in the run log:

1. **1920×1080** — `.dashboard` right edge now near the viewport right (dead space ≈ 0 ± padding);
   6 chart cards in two rows of 3 at ≥1440; contribution legend fully visible (no scroll, "Demand"
   not clipped); population chart has no green constant column; policy bump shows only changing
   lines with no legend.
2. **2560×1080** — content fills to the 2200px cap and centres; the previously measured 800px dead
   space (run log item 8) is gone; the 2×3/3×2 grid is even (no empty sixth slot).
3. **375×1080** — single-column cards, no horizontal overflow, wrapped labels readable, nav top-bar
   intact, no clipped axis text.
4. **Chart close-ups** — one screenshot per chart card (six), plus a nav-rail close-up showing the
   five new icons; verify each icon is decorative beside its visible text and loads offline (no
   network request to any external host in the Playwright network log).

Run-log-only prior measurements (dead space 800px/160px; contribution-legend scroll) are the
baseline to compare against; this plan does not re-measure them.

---

## 14. Evidence walk for the countable claims in this plan

- **"`report.py` 2646 / `dashboard.css` 868 / `tests/test_report.py` 2458 lines"** —
  **(counted:** `(Get-Content <path>).Count`; unit = source lines).
- **"`DASHBOARD_CHART_IDS` has 5 entries; `DASHBOARD_COMPONENT_IDS` has 10"** — **(read:**
  `report.py:91–116`; unit = tuple entries).
- **"`builders` dict has 5 entries"** — **(read:** `report.py:1986–1992`; unit = dict entries).
- **"zero CSS rules consume `--ramp-*`/`--evidence-*`"** — **(counted:** ripgrep pattern
  `var\(--ramp-|var\(--evidence-` over `dashboard.css`; unit = matching lines; result = 0).
- **"no test asserts a literal chart count or a 5-element tuple"** — **(counted:** grep of
  `tests/test_report.py` for `DASHBOARD_CHART_IDS`/`DASHBOARD_COMPONENT_IDS` and `len(`; unit =
  matched lines; the enumerated loop sites are listed in §11.4).
- **"`_RAMP_HEXES` is `#73adf0/#59e082/#d0df4d/#e68d52`"** — **(read:** `report.py:274`).
- **"`--ramp-*`/`--evidence-*` declared at `dashboard.css:40–49` and consumed by no rule"** —
  **(read + counted:** declaration lines read; consumption grep = 0).
- **"the population title occurs only in `report.py:232` and no test asserts it"** —
  **(counted:** grep of `tests/` for the literal; unit = matched lines; result = 0).
- **Skill citations** — **(read from skill data files:** `charts.csv` rows 1 and 4;
  `ux-guidelines.csv` rows 21, 73, 84, 113, 116; `icons.csv` rows 1, 6, 53, 60, 67); **not
  CLI-verified** (CLI unavailable to this planner; see the note at the top).
- **Run-log facts** (dead space, legend scroll, 18 policy series, probe ranges) — **(read from run
  log** `Documents/runs/chunk-35.md`; not re-measured).
- **Contrast budget (§4.4)** — hand-computed with the WCAG formula; **not tool-verified this
  session**; the implementation/test must compute it with the existing helpers.

---

## 15. Open questions

**One non-blocking, informational item:**

1. **A future "high demand / low competition" split line (D35-3).** The SRS defines no threshold
   for this split (SRS §8.2 `LREQ-SCR-010`/`LREQ-SCR-020` define the components, not a cut point),
   so chunk 35 draws **no** quadrant/median/split line and implies none in the figure, caption, or
   title. If the operator later wants a split, a human must first rule an SRS-grounded threshold;
   only then may a future chunk add a reference line. Chunk 35 is complete and frozen without it.

Everything else the lead settled: D35-3 (option (a), threshold-free), D35-1, D35-2, D35-4,
D35-5, D35-6, D35-7, D35-8. The standing obligations — URI trailing-identifier extraction, OI-6
CSRF, `runs.taxonomy_sha256` — are unchanged and are not chunk 35's.

**Process gap (not a scope question):** the `ui-ux-pro-max` CLI could not be executed from this
planner (all shell paths denied); the lead should re-run the five queries
(`chart ×2`, `ux ×2`, `icons ×1`) and paste the verbatim returns into the run log so the skill
citations in §2.1 become CLI-verified.
