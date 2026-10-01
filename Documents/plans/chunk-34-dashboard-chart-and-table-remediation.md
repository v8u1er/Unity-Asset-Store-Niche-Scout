# Chunk 34 — dashboard chart label/legend/color/font remediation + compliant table prioritization + nav centering (plan)

Status: FROZEN — 2026-10-01. The lead has already frozen the eight scope decisions (run log
`Documents/runs/chunk-34.md`, "Operator-authorized decisions"); this plan fixes the palette
stop hexes, the shared types, and the test surface, and re-opens none of the eight. Open
questions: none (see §15).

New remediation/feature chunk, not in `Documents/requirements-dependency-map.md` §3/§4
(chunk-14 / chunk-30 / chunk-31 / chunk-32 / chunk-33 precedent: registration = plan + run log
+ branch). Do not edit the dependency map, the SRS, `AGENTS.md`, or `.kilo/`.

Branch: `chunk-34`, created from `main` @ `ad0bb70` (`chunk-33: gate PASSED; run log`).

Authority: `Documents/runs/chunk-34.md` (this chunk's log: the operator's eight request items,
the lead's live-dashboard audit findings 1–9, the six `ui-ux-pro-max` CLI queries, the hard
constraints, and the operator-authorized decisions); the frozen contracts it cites
(`Documents/plans/chunk-33-dashboard-redesign.md`, `Documents/interfaces/chunk-11.md` §7/§11/
§12); and SRS §10 (`LREQ-RPT-010`, `LREQ-RPT-020` — grepped at
`Documents/SRS-lean-v2.md:1153–1189`, read). This chunk **builds on** chunk 33 and
**supersedes** a named subset of its decisions (§3). It amends no frozen public signature.

SRS authority: `Documents/SRS-lean-v2.md` §10 `LREQ-RPT-010`..`LREQ-RPT-050`
(lines 1153–1189 **(read)**), §8 (normalization/composite), §14 (constants), Appendix C
(warning vocabulary). `AGENTS.md` Hard rules 1–4 and "Out of scope — do not add". Every
countable claim is labelled **(read)** or **(counted)** per project-rules "Plan review and
audit"; the walk is §14.

---

## 1. Scope, non-goals, LREQ roles

### 1.1 Scope (in)

1. **Leaf-only chart category labels + collision-safe disambiguation.** Every chart that
   renders a category label on an axis or in a hover shows only the final `/`-segment
   (e.g. `fullscreen-camera-effects`). The full taxonomy path is retained in the primary
   table cell, the category detail heading, and the chart hover. A private helper
   `_category_leaf_label(row, view)` returns the leaf, and appends `" · <parent path>"`
   **only** when two or more rows in the same view share the same leaf (collision-safe). The
   chart `category` axis title is reworded to the plain-language "category (leaf)".
2. **Figure font fix.** Numeric ticks and all marker/text annotations use the existing local
   mono stack (`--font-mono` values, baked as a literal because figures serialize to JSON);
   axis titles/labels and hyphenated non-numeric text use the local sans stack (`--font-sans`
   values). No web font, no `@import`, no URL.
3. **Drop meaningless legends.** `showlegend: False` for *Composite score by rank* and
   *Composite score vs quality*; *Population and sample size*, *Weighted component
   contributions*, and *Policy rank comparison* keep legends.
4. **Population chart optimization.** Population legend moved horizontal below the plot; the
   redundant in-plot Plotly `layout.title` dropped on all five figures (the card `H3` stays)
   to reclaim vertical space.
5. **Analogous sequential curve palette.** One sequential analogous ramp from pastel cyan to
   pastel yellow (§4.1), applied by a deterministic index: contribution stack (4 segments = the
   ramp's 4 stops), policy bump (series index cycled over the ramp, with direct series labels),
   population (population/sample markers from the ramp), scatter (ramp). The evidence ordinal
   ramp `_EVIDENCE_GRADE_COLOURS` (`report.py:273`) is re-tuned to 4 stops of the same ramp,
   ordered insufficient→strong. A reserved `--danger`-family colour **with a distinct marker
   shape** is used for out-of-line states (refused rows, measured-explicit-zero) — colour is
   never the only signal. Stop hexes are fixed in §4; all are analogous, pastel, and
   hand-computed ≥3:1 non-text contrast on `#112D3B` (≥4.5:1 where used as adjacent text).
   This continues chunk-33 LR1 and stays within SRS §8/§14 (no configurable weights; the
   evidence grade stays ordinal).
6. **Compliant table prioritization (option A).** All 30 `LREQ-RPT-020` columns stay in the
   DOM; none is removed or renamed. The leading identity/score columns are frozen with the
   DataTable's native `fixed_columns={"headers": False, "data": 7}` (indices 0–6: `category`,
   `rank`, `composite score`, `D`, `C`, `R`, `Q`), and the secondary-column group
   (indices 7–29) is lightly de-emphasized with **inline DataTable conditional style
   properties** (no `className` hook), keeping values verbatim and `n/a`/`0` distinct. No
   column picker; no `LREQ-RPT-020` removal.
7. **Nav icon centering.** `.nav-link` gains `box-sizing: border-box` so the desktop rail
   link fits the 73 px rail and the icon/label center. CSS-only; no callback.
8. **Chart fidelity preserved.** Every existing pinned chunk-33/31/32 dashboard node stays
   green, including: one bar trace of scored rows only with refused rows as `n/a` text off the
   scored axis; `n/a` ≠ `0`; no confidence interval or error bars; deterministic layout for a
   fixed view; every `DASHBOARD_COMPONENT_IDS` id unchanged; no new Dash callback; no
   forbidden import; no clock read.

### 1.2 Non-goals (explicitly NOT in this chunk)

- **No content removal.** No `LREQ-RPT-020` column label, no `LREQ-RPT-030` detail item, no
  `LREQ-RPT-050` string, and no Appendix C warning code is removed from the DOM. The leaf
  label is a *display* transform of a chart tick only; the DataTable cell, the column guide,
  the selector, and the detail heading keep the full path.
- **No data or number change.** No metric, component, score, rank, evidence grade,
  rankability, or sensitivity value is recomputed; the figures render persisted values
  verbatim. A chart label never changes a number, a rank, or a measured value.
- **No external dependency.** No CDN, web font, `@import`, `url(`, or scheme-bearing external
  asset anywhere in this chunk's output (CSS or figure data). The `--font-sans`/`--font-mono`
  stacks are baked as literals; they name local fonts only.
- **No new Dash callback.** The only app callback remains `_render_selected_detail`
  (`report.py:2386`). No `app.clientside_callback`, no JS added.
- **No SRS/interface/dependency-map edit.** Interface §7/§11/§12 are untouched.
- No schema, pipeline, `metrics.py`, or `scoring.py` change; no static-report (`run --report`)
  change; no CLI change.
- **No clock read in `report.py`**; no `metrics`/`scoring`/`collector*`/`config`/`pipeline`/
  `cli` import (purity unchanged; §8).
- No change to the frozen public signatures of `build_dashboard_layout` /
  `build_dashboard_app`; no change to `render_run_report_html` / `render_run_report_text` /
  `write_run_report`.
- No test-node-ID change: this chunk adds new nodes and amends two existing constants plus
  three existing nodes in
  `tests/test_report.py` (§10), never renames or removes a node ID or a
  `tests/traceability.json` key.

### 1.3 LREQ roles

| Role | LREQs |
|---|---|
| Primary | `LREQ-RPT-010` (one-command local read-only dashboard; offline styling and packaging) — the chart/table/nav remediation strengthens the served-page guarantee |
| Supporting contract | `LREQ-RPT-020` (primary table; the 30 columns stay in the DOM and the DataTable default columns are unchanged), `LREQ-RPT-030` (category detail heading keeps the full path), `LREQ-RPT-040` (non-rankable/refused rows stay visible and off the scored axis), `LREQ-RPT-050` (heuristic statement unchanged) |
| Integration completion | `LREQ-NFR-040` (no public builder signature change), `LREQ-ARCH-010`/`LREQ-ARCH-020` (purity: `report.py` imports no forbidden module and reads no clock; `metrics`/`scoring` untouched) |

Per the tool's mapping rule, new markers use only `LREQ-RPT-010`/`020`/`030`/`040`; no new
marker cites `LREQ-ARCH-*`/`LREQ-NFR-*` (purity and determinism are asserted by existing
`test_quality_tooling.py::test_report_module_has_no_forbidden_imports_or_clock_reads` and the
determinism node, both of which must stay green — §10.3).

---

## 2. Grounding facts (established; the plan is self-contained)

Each fact is labelled **(read)** (opened and read a file/line) or **(counted)** (queried an
artifact with a stated method and unit). No fact is restated from memory.

- **`report.py` is 2535 lines; `dashboard.css` is 858 lines; `tests/test_report.py` is 2099
  lines** — **(counted:** `(Get-Content <path>).Count` for each of the three files).
- **`_base_layout(title)` at `report.py:1457`** returns one shared dict; its `title.font`,
  `font`, `legend`, `xaxis`, `yaxis`, and `margin` are the single shared style seam for all
  five figures — **(read:** `report.py:1457–1485`). The function's docstring already says the
  colour literals deliberately mirror the CSS tokens because figures serialize to JSON
  **(read:** `report.py:1460–1463`).
- **The five figure builders and their category axes** — `_score_bar_figure`
  (`report.py:1647`; `yaxis` title `"category"`, in-plot title "Composite score by rank" at
  `:1700–1702`), `_contribution_figure` (`:1706`; `xaxis` title `"category"` at `:1730`),
  `_policy_bump_figure` (`:1735`), `_population_lollipop_figure` (`:1758`; `yaxis` title
  `"category"` at `:1830`), `_score_quality_scatter_figure` (`:1834`) — **(read:** each
  builder body).
- **Category labels currently come from `row.category` verbatim** in `_score_bar_figure`
  (`labels = [row.category for row in scored]`, `:1659`), `_contribution_figure` (`:1714`),
  `_population_lollipop_figure` (`:1773`), the policy-bump trace `name=category` (`:1748`),
  and the scatter `text=labels` where `labels.append(row.category)` (`:1857`) — **(read:** the
  cited lines).
- **The three charts that keep legends and the two that do not**: `_base_layout` sets
  `"showlegend": True` (`:1471`); the score bar's refused annotation already sets
  `showlegend=False` (`:1696`); the score bar's bar trace (`:1674`) and the scatter trace
  (`:1859`) carry **no** `showlegend` key, so they inherit the shared `True` (run-log
  finding 3 confirms the rendered single-item legends) — **(read:** `:1471`, `:1696`,
  `:1674–1685`, `:1859–1871`).
- **The population figure's three trace `name=` values** are
  `"discovered population (observed)"` (`:1796`), `"discovered population: measured zero"`
  (`:1807`), `"sample size (observed)"` (`:1824`); marker colours are hard literals `#64bcfb`
  (`:1797`) and `#46b688` (`:1812`, `:1825`) — **(read:** the cited lines).
- **`_EVIDENCE_GRADE_COLOURS` at `report.py:273–275`** is
  `tuple(zip(EVIDENCE_GRADE_ORDER, ("#c98b8b", "#e0a458", "#8fb0bf", "#46b688")))`;
  `_evidence_colour` maps an unknown grade to the weakest colour (`:1444–1454`) — **(read:**).
- **`_PRIMARY_COLUMNS` has 30 entries** — **(counted:** `report.py:367–401`, the tuple spans
  34 source lines because four labels are wrapped; `test_report.py:1056` asserts
  `len(report._PRIMARY_COLUMNS) == 30`, and `tests/test_report.py:1426` asserts the rendered
  DataTable header count is 30. The run log independently counted 30
  `dash-header .column-header-name` elements in the live DOM). **The "30" claims in §11 are
  pinned by these two existing assertions, not asserted again.**
- **No secondary-column grouping exists today**: the DataTable has no `style_data_conditional`
  and the CSS has no `nth-child` column rule; `.dash-cell`/`.dash-header` are class-based only
  **(read:** `report.py:2010–2026`; `dashboard.css:481–545`). The DataTable's verified native
  column-prioritization mechanisms are `fixed_columns` (`DataTable.py:311–330`: a dict with
  `headers` (bool) and `data` (number); fixes columns left-to-right so they stay visible
  during horizontal scroll) and the conditional-style props `style_cell_conditional`
  (`:949–961`), `style_data_conditional` (`:963–983`), and `style_header_conditional`
  (`:1001–1017`), whose only documented `if` sub-keys are `column_id`/`column_type`/…, with
  free-form CSS style properties applied inline — **no `className` key is documented or
  applied** (lead-verified by reading the installed `dash_table/DataTable.py`). This chunk
  therefore uses `fixed_columns` for the freeze and inline conditional style properties keyed
  by `column_id` for the de-emphasis; it adds no CSS class hook.
- **The nav rail defect**: `.nav-link { inline-size: 100% }` under the `@media
  (min-width: 1024px)` rail (`dashboard.css:843–845`) plus `padding: var(--space-1)
  var(--space-2)` (`:204`) under the default `content-box` sizing; the rail is
  `--nav-rail-width: 64px` with `padding: var(--space-3) var(--space-1)` and a 1 px inline-end
  border (`:830–841`) — **(read:** the cited lines) — reproduced the lead's measured 73 px
  rail / 80 px link overflow (run-log finding 7, measured with Kilo Playwright).
- **`--font-sans` / `--font-mono` local stacks** — **(read:** `dashboard.css:43–45`):
  `system-ui, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif` and
  `ui-monospace, "Cascadia Mono", "Cascadia Code", Consolas, "SFMono-Regular", Menlo,
  monospace`.
- **The CSS offline assertion forbids `url(`** — **(read:** `test_report.py:1702`) — so a
  font stack may not embed a `url()`; the stacks above contain none.
- **Existing pinned node IDs and their markers** — **(read:** `tests/test_report.py`):
  score-bar refused/scored (`:1459–1483`), null-vs-zero (`:1521–1564`), no-CI (`:1567–1579`),
  policy-bump (`:1582–1625`), ordinal evidence (`:1628–1650`), automargin (`:2044–2071`),
  evidence-scale retune (`:2074–2099`), chart captions/human labels (`:1498–1518`),
  determinism (`:1389–1399`), component ids (`:1403–1413`).
- **`tests/traceability.json` existing keys** for the two nodes this chunk supersedes:
  `test_dashboard_evidence_scale_is_retuned_to_the_reference_palette` →
  `["LREQ-RPT-020"]` (`tests/traceability.json:1507–1509`); the CSS-scale node →
  `["LREQ-RPT-010"]` (`:1494–1496`) — **(read:**).
- **Contrast ratios** are hand-computed with the WCAG relative-luminance formula
  (`L = 0.2126R + 0.7152G + 0.0722B` on linearised sRGB; ratio
  `(L_light + 0.05) / (L_dark + 0.05)`; `--surface #112D3B` already computed at
  `L ≈ 0.0231` in chunk-33 §2, reused). Recomputed here for the new ramp in §4.2
  **(hand-computed; reproducible from the formula; not tool-verified this session).**

---

## 3. Supersession (chunk-33 decisions chunk 34 replaces)

Chunk 34 amends the following chunk-33 decisions; everything else in chunk 33 stands and its
pinned nodes stay green (§10.3).

1. **Chunk-33 §4.2 evidence scale (LR1).** `_EVIDENCE_GRADE_COLOURS`
   (`report.py:273`) and the four `--evidence-*` CSS values move from
   `#c98b8b / #e0a458 / #8fb0bf / #46b688` to the four §4.1 ramp stops
   `#9fd7ea / #b9dbb0 / #d5dd93 / #e6d489` (still `EVIDENCE_GRADE_ORDER` order). The pinned
   node `tests/test_report.py::test_dashboard_evidence_scale_is_retuned_to_the_reference_palette`
   (`:2074–2099`) keeps its **node ID**, its **marker** `LREQ-RPT-020`, and its
   `tests/traceability.json` key (`:1507–1509`); only its expected four hexes change, plus a
   new div-on-white contrast assertion added by `test-author`.
2. **Chunk-33 §9.2 amended constant `_DASHBOARD_CSS_HEXES` (`tests/test_report.py:1113`) and
   the chunk-33 `_EVIDENCE_SCALE_HEXES` constant (`:1830`).** Both lose the retired evidence
   hexes. The node
   `tests/test_report.py::test_dashboard_css_asset_exists_is_offline_and_uses_the_token_set`
   keeps its **node ID** and its key `["LREQ-RPT-010"]` (`tests/traceability.json:1475–1477`);
   only the four retired hexes are replaced with the four §4.1 ramp stops (no other hex is
   added or removed; `--danger #e27882` is already present). `_REFERENCE_PALETTE_HEXES`
   (`:1815–1826`) is unchanged (it holds the ten semantic tokens, not evidence colours).
3. **Chunk-33 §9.1 node
   `test_dashboard_css_uses_the_reference_palette_and_explicit_type_scale` (`:1866`).** Its
   `_EVIDENCE_SCALE_HEXES` loop still runs; because the chunk-33 module-level constant still
   holds the retired hexes, **the node goes red until the constant is amended** — the test
   author amends the constant (or makes the node read the expected values from
   `report._EVIDENCE_GRADE_COLOURS`) as part of this chunk's first red step. The node ID and
   its key `["LREQ-RPT-010"]` (`tests/traceability.json:1494–1496`) are unchanged.
4. **Chunk-33 §6.2 `.dash-header` uppercase / letter-spacing** is **retained as-is** (no test
   asserts or forbids it; the Column guide still discloses the full label).
5. **The retired `#c98b8b`, `#e0a458` evidence literals** appear in no chunk-34 output; the
   CSS must not contain them after this chunk (the new assert in §10.2(a)).

### 3.1 Existing chunk-31/33 pins amended in place (not new nodes)

Three existing pinned nodes are **amended in place** because this chunk's §5 figure changes
their asserted shape. Each keeps its node ID, its marker, and its `tests/traceability.json`
key (§10.2); it leaves the §10.3 "must stay green unchanged" set.

1. **`tests/test_report.py::test_dashboard_score_bar_encodes_ordinal_evidence_grade`**
   (`:1628–1650`; marker `@pytest.mark.lreq("LREQ-RPT-020")` at `:1628`; key
   `["LREQ-RPT-020"]` at `tests/traceability.json:1535–1537`, **(read)**). §5.2 changes the
   score-bar `customdata` from `[row.evidence_grade, …]` to
   `[[row.category, row.evidence_grade], …]`, so the node's
   `trace["customdata"] == [row.evidence_grade …]` assertion is amended to the list-of-lists
   form (§10.2(f)); the grade text still lives at `customdata[i][1]` and colour still comes
   from `_evidence_colour`.
2. **`tests/test_report.py::test_dashboard_charts_carry_explanations_and_human_labels`**
   (`:1498–1518`; marker `@pytest.mark.lreq("LREQ-RPT-010")` at `:1498`; key
   `["LREQ-RPT-010"]` at `tests/traceability.json:1491–1493`, **(read)**). §5.1 drops the
   in-plot `layout.title`, so the node's `figure["layout"]["title"]["text"]` assertion is
   amended to assert the card `H3` title is present and the figure has **no** in-plot title
   (§10.2(g)).
3. **`tests/test_report.py::test_dashboard_policy_bump_and_kpi_tiles`** (`:1582`) is amended
   only optionally (§10.2(c)): the cyclic ramp wiring in §5.3 does not change
   `_policy_rank_rows`, so its equality assertion stands.

The §4.1 policy-series ramp index is corrected to the deterministic cyclic rule
`i % len(_RAMP_HEXES)` (§4.1) so 18 series cannot index past the 4-stop tuple; this is
chunk-34's own rule, not a chunk-33 supersession.

Nothing else in chunk 33 is superseded.

---

## 4. Palette (the plan fixes the ramp)

### 4.1 One sequential analogous ramp, pastel cyan → pastel yellow

Four stops, in rank order (stop 1 = best rank). All are pastel, analogous (hue steps
cyan → green-cyan → chartreuse → yellow), and *different* from the §4.3 reserved danger colour.

| Stop | Hex | Semantic use |
|---|---|---|
| ramp-1 | `#9fd7ea` | rank-1 best / component D / population-observed marker / evidence-insufficient / policy series 0, 4, 8, … |
| ramp-2 | `#b9dbb0` | rank-2 / component C / sample-size marker / evidence-weak / policy series 1, 5, 9, … |
| ramp-3 | `#d5dd93` | rank-3 / component R / evidence-moderate / policy series 2, 6, 10, … |
| ramp-4 | `#e6d489` | rank-4 / component Q / evidence-strong / policy series 3, 7, 11, … |

**Composition rule (deterministic, no config):** the ramp index is an explicit integer, never a
set/dict iteration —
- for a `view`, the i-th `_scored_rows(view)` row (i = 0..n−1) uses
  `_RAMP_HEXES[i % len(_RAMP_HEXES)]`; with the fixture's ≤4 scored rows this is the plain
  rank order, and the modulo keeps it defined for a run with more than 4 scored rows;
- for a contribution stack the segment index in `COMPONENT_WEIGHTS` order (D, C, R, Q) uses
  `_RAMP_HEXES[index]`;
- for the policy bump the series index `i` (0-based over `_policy_rank_rows(view)` order) uses
  **`_RAMP_HEXES[i % len(_RAMP_HEXES)]`**, applied to **both** the trace's `line.color` and
  `marker.color`; the modulo is required because `_policy_rank_rows` can hold up to 18 series
  while `_RAMP_HEXES` has 4 stops;
- for the population figure the observed-population marker uses ramp-1 and the sample-size
  marker uses ramp-2;
- the scatter uses ramp-1 for all points.

The rule is a fixed index map, so two builds for a fixed view are byte-identical (§8).

The four stops are held in one module constant in `report.py` (single literal source; the CSS
`--ramp-1`…`--ramp-4` values mirror it):

```python
_RAMP_HEXES: tuple[str, ...] = ("#9fd7ea", "#b9dbb0", "#d5dd93", "#e6d489")
```

`_EVIDENCE_GRADE_COLOURS` is `tuple(zip(EVIDENCE_GRADE_ORDER, _RAMP_HEXES))`, so the evidence
scale and the curve ramp cannot drift apart.

### 4.2 Contrast budget for the ramp (hand-computed, WCAG on sRGB)

Surfaces: plot/card `--surface #112D3B` (`L ≈ 0.0231`, chunk-33 §2); white `#FFFFFF`
(`L = 1.0000`, for the light-mode `#modeBar` glyphs that Plotly paints white). Ratio
`(L_light + 0.05) / (L_dark + 0.05)`.

| Stop | L | vs `#112D3B` | vs white |
|---|---|---|---|
| `#9fd7ea` | 0.6271 | **10.29:1** | 1.86:1 |
| `#b9dbb0` | 0.6622 | **10.83:1** | 1.76:1 |
| `#d5dd93` | 0.7091 | **11.52:1** | 1.66:1 |
| `#e6d489` | 0.7076 | **11.50:1** | 1.67:1 |

All four are ≥3:1 non-text and ≥4.5:1 adjacent text on `#112D3B`. None reaches 3:1 against
white, so **the mode bar is disabled** (`config={"displayModeBar": False}` already at
`report.py:1924`; §5.4) and no ramp colour is ever placed on a white surface. The policy
bump's cyclic reuse of the four stops (§4.1) does not change any ratio: each series still
paints one of the four measured stops, so the contrast floor holds for every repeated stop.

### 4.3 Reserved danger (out-of-line states; colour is never the only signal)

| Token | Value | Role | Contrast vs `#112D3B` |
|---|---|---|---|
| `--danger` (existing) | `#e27882` | refused-row `n/a` text and measured-explicit-zero markers | **5.05:1** (≥4.5:1) |

Out-of-line states carry a **shape** as well as the danger colour: the measured-explicit-zero
population marker is `diamond-open` (`report.py:1811`, retained), and the refused rows are
`n/a` **text** annotations (`report.py:1693`) with no bar — text and shape, never colour alone
(run log skill evidence "Anomaly Detection": "distinct shape + text annotation as well as
color"). No new danger-family hex is introduced; `--danger` is reused.

**Explicitly rejected:** a 12 % white wash over `#112D3B` yields `#313F4B` (`L ≈ 0.0504`,
1.38:1 vs surface) — an invisible surface-only cue that also adds a new hex and weakens text
contrast without helping colour-blind users. The table de-emphasis (§6.2) instead reuses the
existing `--surface-2` (`#0c2432`) and `--muted-fg` (`#8fb0bf`, 6.2:1) values, introducing no
new surface token.

### 4.4 CSS token changes in `src/niche_scout/assets/dashboard.css`

- Replace the four `--evidence-*` values (`:37–40`) with the §4.1 ramp stops
  (`--evidence-insufficient: #9fd7ea`, `--evidence-weak: #b9dbb0`,
  `--evidence-moderate: #d5dd93`, `--evidence-strong: #e6d489`).
- Add the `--ramp-1`…`--ramp-4` tokens (documentation of the figure ramp; figures bake the
  same hexes as literals because they serialize to JSON). No `--washer` token is added: the
  secondary-column de-emphasis is expressed as inline DataTable conditional styles (§6.1/§6.2)
  using the existing `--surface-2`/`--muted-fg` reference values.
- The retired `#c98b8b` and `#e0a458` must not appear in the file after this chunk.

---

## 5. Figure remediation (`report.py`, private surface only)

### 5.1 Shared layout: fonts and the dropped title

`_base_layout(title)` becomes `_base_layout()` — the shared dict loses `title` (decision 4:
the card `H3` is the only chart title) but **gains** the two font literals:

| `_base_layout` key | New value |
|---|---|
| `title` | **removed** (no in-plot title) |
| `font` | `{"color": "#e6f0f4", "size": 12, "family": _FIGURE_FONT_SANS}` |
| `xaxis.tickfont` | `{"family": _FIGURE_FONT_MONO, "color": "#e6f0f4"}` |
| `xaxis.title.font` | `{"family": _FIGURE_FONT_SANS, "color": "#e6f0f4"}` |
| `yaxis.tickfont` | `{"family": _FIGURE_FONT_MONO, "color": "#e6f0f4"}` |
| `yaxis.title.font` | `{"family": _FIGURE_FONT_SANS, "color": "#e6f0f4"}` |
| `legend` | `{"bgcolor": "#0c2432", "font": {"color": "#e6f0f4", "family": _FIGURE_FONT_MONO}}` |

Two module constants (single literal source; the CSS stacks are not readable by `report.py`):

```python
_FIGURE_FONT_SANS: str = (
    'system-ui, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif'
)
_FIGURE_FONT_MONO: str = (
    'ui-monospace, "Cascadia Mono", "Cascadia Code", Consolas, '
    '"SFMono-Regular", Menlo, monospace'
)
```

Each builder calls `figure.update_layout(**_base_layout())` and then sets its axes' **titles**
via `update_xaxes`/`update_yaxes` exactly as today, **except** the reworded category axis
title:

- `_score_bar_figure`: `figure.update_yaxes(autorange="reversed", title={"text": "category (leaf)"})`.
- `_contribution_figure`: `figure.update_xaxes(title={"text": "category (leaf)"})`.
- `_population_lollipop_figure`: `figure.update_yaxes(title={"text": "category (leaf)"})`.
- `_policy_bump_figure` and `_score_quality_scatter_figure`: keep their non-category titles
  (`"scoring policy"`, `"rank (1 = best)"`, `"composite score"`, `"Quality"`).

`"category (leaf)"` is the chunk-31 §5.7 plain-language vocabulary (a parenthetical qualifier,
like the existing `"Population and sample size (log scale)"` title).

### 5.2 Leaf-only labels + collision-safe disambiguation

New private helper (exact signature for the test author):

```python
def _category_leaf_label(row: CategoryReportRow, view: RunReportView) -> str:
    """Return the chart label for ``row``: the final ``/``-segment of its category.

    ``"vfx/shaders/fullscreen-camera-effects"`` -> ``"fullscreen-camera-effects"``;
    a category with no ``/`` is returned unchanged. When two or more rows in
    ``view`` share the same leaf, the label is suffixed with the remaining parent
    path so the labels stay unique and deterministic:
    ``"fullscreen-camera-effects · vfx/shaders"``. The suffix is appended for
    *every* member of a colliding leaf group, never for a non-colliding row, so
    two calls with a fixed view return equal labels (explicit, order-independent
    collision count). No number, rank, or measured value is changed; the full
    path stays in the primary table cell, the column guide, the selector, and the
    category detail heading.
    """
```

Implementation contract (deterministic, no I/O, no clock):

1. `leaf = row.category.rsplit("/", 1)[-1]`, `parent = row.category.rsplit("/", 1)[0]` when a
   `/` is present, else `leaf = row.category` and no suffix.
2. Count occurrences of each leaf across `view.categories` (a `collections.Counter` over the
   tuple, iterated in view order for the return; the *count* is order-independent).
3. If `counts[leaf] > 1`, return `f"{leaf} · {parent}"`; else return `leaf`.

Builder wiring (all category labels, axes **and** hover, use the helper; the full path stays
in hover `customdata`):

| Builder | Label site | Change |
|---|---|---|
| `_score_bar_figure` | `y=labels` (`:1676`) | `labels = [_category_leaf_label(row, view) for row in scored]`; `customdata = [[row.category, row.evidence_grade] for row in scored]`; hover `"%{y}: %{text}<br>category: %{customdata[0]}<br>evidence strength: %{customdata[1]}<extra></extra>"` |
| `_contribution_figure` | `x=labels` (`:1720`) | `labels = [_category_leaf_label(row, view) for row in scored]` |
| `_population_lollipop_figure` | `y=labels` (`:1773`) | `labels.append(_category_leaf_label(row, view))`; `customdata = [[row.category] for row in scored]`; hover `"%{y}<br>category: %{customdata[0]}<extra></extra>"` |
| `_policy_bump_figure` | trace `name=category` (`:1748`) | `name=_category_leaf_label(row, view)` with the returned row rebuilt to carry the leaf label; trace `legendgroup=label`; direct on-series labels (see §5.3) |
| `_score_quality_scatter_figure` | `text=labels` (`:1857`) | `labels.append(_category_leaf_label(row, view))`; `customdata = [[row.category, text] for ...]` (two-element list of lists); hover `"%{text}<br>category: %{customdata[0]}<br>composite score %{x}<br>quality %{y}<br>sample fraction %{customdata[1]}<extra></extra>"` |

The score-bar `customdata` **shape changes** from a flat `list[str]` of evidence grades to a
`list[list[str]]` of `[category, evidence_grade]` pairs (to carry the full path in the hover).
The existing pinned node
`tests/test_report.py::test_dashboard_score_bar_encodes_ordinal_evidence_grade` asserts the old
flat shape, so it is **amended in place** (§3.1 item 1, §10.2(f)); it keeps its node ID, its
marker `LREQ-RPT-020`, and its `tests/traceability.json` key
(`tests/traceability.json:1535–1537`). The exact grade text is still at `customdata[i][1]` and
the colour still comes from `_evidence_colour`.

`_policy_rank_rows(view)` currently returns `(category, balanced, demand_heavy,
competition_heavy)`; the policy-bump builder's loop is changed to iterate the same tuple and
call `_category_leaf_label` **by looking the row up from `view`** — no new public function,
no signature change. The tuple itself is unchanged (the pinned node
`test_dashboard_policy_bump_and_kpi_tiles` asserts its equality).

**Hover collision-safety:** the hover always prints the full `row.category` in its own
`category:` field, so even a non-colliding leaf is one hover away from the full path.

### 5.3 Legends and direct labels

- `_score_bar_figure`: after `update_layout(**_base_layout())`, add
  `figure.update_layout(showlegend=False)` (decision 3).
- `_score_quality_scatter_figure`: same `showlegend=False`.
- `_contribution_figure`: keeps the legend, ordered D→C→R→Q (already); each segment's
  marker colour is `_RAMP_HEXES[i]` for the i-th `COMPONENT_WEIGHTS` entry. Legend font is mono
  (numeric keys); the component *names* are words, so the legend title is left unset.
- `_population_lollipop_figure`: keeps the legend, moved below the plot:
  `figure.update_layout(legend={"orientation": "h", "yanchor": "top", "y": -0.28,
  "xanchor": "center", "x": 0.5})`, merged with the `_base_layout` legend dict. The legend
  text is the trace `name=` value, so the three trace names are shortened to plain-language
  labels `"discovered population"`, `"measured zero"`, `"sample size"` — a display-label-only
  change. **No test reads the population figure's trace `name=` values** (the pinned
  `test_dashboard_distinguishes_null_from_explicit_zero` reads trace data and `text`, not
  `name`). Note the literal `"discovered population (observed)"` still exists in
  `_OBSERVED_LABELS` (`report.py:310`) and is asserted via the detail disclosure in
  `test_dashboard_uses_progressive_disclosure_without_dropping_mandated_content`; that is a
  different occurrence, untouched by this rename.
- `_policy_bump_figure`: keeps the legend **and** adds direct series labels. For each series
  with 0-based index `i` over `_policy_rank_rows(view)` order, set the colour
  `c = _RAMP_HEXES[i % len(_RAMP_HEXES)]` and pass **both** `line={"color": c}` and
  `marker={"color": c}` to the `go.Scatter`, plus `mode="lines+markers+text"`,
  `text=[label, "", ""]` on the first policy point only, and `textposition="middle right"`.
  The modulo is required because there can be up to 18 series against 4 stops (§4.1); the
  index is explicit and deterministic. The 18-item legend no longer has to be read to identify
  a line; the direct label is the collision-safe `_category_leaf_label` too.
- **No marker-shape channel** (`symbol=`) is added to chart markers. Every visible series
  keeps its default symbol; the reserved `diamond-open` is used **only** for the
  measured-explicit-zero out-of-line marker (`report.py:1811`), so "colour is never the only
  signal" is runtime-verifiable with §6.3's SQLite query, not merely referential.

### 5.4 Mode bar and the two font literals

- The mode bar is already disabled (`config={"displayModeBar": False}`,
  `report.py:1924`) — **retained unchanged**. Because the ramp stops are ~1.6–1.9:1 against
  white, the mode-bar glyph surface stays off-canvas; this is the reason no ramp colour is
  ever placed on the `#modeBar` white background.
- The two font literals (§5.1) are the only font-family strings in `report.py`.

---

## 6. Compliant table prioritization (option A)

### 6.1 DataTable render options (deterministic, no callback)

Two **verified** DataTable mechanisms replace the earlier className hook (lead-verified against
the installed `dash 4.4.1` package, `dash_table/DataTable.py` — see §2).

**Freeze (native `fixed_columns`).** `fixed_columns` (`DataTable.py:311–330`) is a dict with
`headers` (bool) and `data` (number); it fixes leading columns left-to-right so they remain
visible during horizontal scroll. This chunk adds:

```python
_FROZEN_COLUMN_COUNT: int = 7   # indices 0..6: category, rank, composite score, D, C, R, Q
```

and passes `fixed_columns={"headers": False, "data": _FROZEN_COLUMN_COUNT}`. N = 7 is the
smallest count that keeps `category` (0) plus the score columns (`composite score` 2, `D` 3,
`C` 4, `R` 5, `Q` 6) visible; because columns fix left-to-right, `rank` (1) is included
automatically. `_FROZEN_COLUMN_COUNT` is a single private int constant derived from the
`_PRIMARY_COLUMNS` order, not a second `_PRIMARY_COLUMNS` literal.

**De-emphasis (inline conditional styles).** The conditional-style props
(`style_cell_conditional` `:949–961`, `style_data_conditional` `:963–983`,
`style_header_conditional` `:1001–1017`) apply **inline CSS only** and document only the `if`
sub-keys (`column_id`, `column_type`, `header_index`, …); **no `className` key is documented
or applied**. The secondary columns are the `column_id`s at
`[attribute for _, attribute in _PRIMARY_COLUMNS][_FROZEN_COLUMN_COUNT:]` (indices 7–29),
passed to `style_data_conditional` and `style_header_conditional`:

```python
secondary_ids = [attr for _, attr in _PRIMARY_COLUMNS][_FROZEN_COLUMN_COUNT:]
style_header_conditional=[
    {"if": {"column_id": col}, "fontWeight": "400", "opacity": 0.85}
    for col in secondary_ids
]
style_data_conditional=[
    {"if": {"column_id": col}, "fontWeight": "400", "opacity": 0.82}
    for col in secondary_ids
]
```

- The de-emphasis property is **`fontWeight` + `opacity`**, deliberately not `color` or
  `backgroundColor`: the existing authoritative token guards
  (`.dash-cell { color/background: ... !important }`, `.dash-header { … !important }`,
  `dashboard.css:481–545`) outrank a **non-important inline** declaration, so an inline
  `color`/`backgroundColor` would be silently shadowed. `fontWeight`
  (`.dash-cell { font-weight: var(--weight-numeric) }`, `.dash-header { font-weight:
  var(--weight-label) }`) and `opacity` are not pinned with `!important`, so the inline
  values apply. The secondary data cells drop from weight 600 to 400 with opacity 0.82; the
  secondary headers from 500 to 400 with opacity 0.85.
- Headers are already `--muted-fg` (6.2:1 on `#112D3B`, chunk-33 §2); 0.85 opacity keeps the
  combined contrast well above 4.5:1. Values stay verbatim; the de-emphasis is weight/opacity,
  never truncation or hiding.
- The selection is by `column_id` from `_PRIMARY_COLUMNS`, so it is byte-identical for a fixed
  `_PRIMARY_COLUMNS`.

### 6.2 CSS for the table (`dashboard.css`)

No new table CSS class is introduced. `.dash-cell`/`.dash-header` keep
`overflow: hidden; text-overflow: ellipsis` (chunk-33 §6.2), the `!important` token guards,
and the sticky `.dash-header` rule unchanged; the freeze and the de-emphasis are driven by the
DataTable props in §6.1, which the renderer emits into the table's own inline markup.

- No column is removed, renamed, reordered, or hidden. The DataTable default `columns` list is
  unchanged (`== [label for label, _ in report._PRIMARY_COLUMNS]`), which is exactly what the
  pinned node `test_dashboard_layout_shows_every_primary_table_column_by_default` asserts.
- The full label stays in the DOM (`column-header-name`, the column guide).

### 6.3 Runtime out-of-line shape assertion (lead verification step)

After implementation the lead (not a test, to keep the offline/no-live-DB rule) runs one
one-shot probe against a **scratch copy** of the dev-run SQLite (`Copy-Item` into
`.scratch/`, per project-rules "Temporary scripts and scratch space"):

```sql
SELECT DISTINCT marker->>'symbol' FROM traces;
```

Expected: exactly one distinct non-null symbol, `diamond-open` (the measured-explicit-zero
marker); every visible series uses the default plotly symbol and the ramp colours from §4.1.
Any other marker symbol (and any hue-only series distinction) is a stop-and-flag.

---

## 7. Nav centering (CSS-only)

`.nav-link` gains `box-sizing: border-box` (applied at all widths, so the mobile top-bar link
geometry is unchanged because it is `inline-flex` with intrinsic width):

```css
.nav-link {
  box-sizing: border-box;   /* desktop rail: 100% of the rail minus padding/border */
  ...
}
```

With `border-box`, the desktop rail link is `min(100%, 64px − padding)`, so it no longer
overflows the 73 px rail and the icon/label center on the rail. No callback, no JS, no
`:has()` change, no new class. The `@media (min-width: 1024px) .nav-link { inline-size: 100% }`
rule (`dashboard.css:843–845`) is retained; `box-sizing: border-box` is added to the base
`.nav-link` block (`:198–211`).

---

## 8. Determinism and purity

- `build_dashboard_layout(view)` stays pure: no clock, no network, no database, no RNG.
  Leaf labels, collision counts, ramp indices, legend positions, font literals, the
  `fixed_columns` freeze, and the DataTable conditional-style props are all fixed functions of
  `view`; two calls build byte-identical trees (the pinned
  `test_build_dashboard_layout_is_deterministic_for_a_fixed_view` still asserts `_norm(first)
  == _norm(second)`).
- The ramp index map is an explicit index, not a set/dict traversal; the collision count is a
  `Counter` over `view.categories` (an ordered tuple) and the suffix rule applies to the whole
  group, so equal views give equal labels.
- `report.py` gains no import; the only fonts are the two module string literals (§5.1); no
  clock read; `metrics.py`/`scoring.py` untouched. The stylesheet stays a static file no Python
  code reads, hashes, or templates.
- The new DataTable `fixed_columns` dict and conditional-style lists are plain
  constants/dicts; Dash renders them without RNG.
- No new Dash callback: the single existing callback `_render_selected_detail`
  (`report.py:2386`) is unchanged.

---

## 9. Interface contract this chunk produces

No public surface is added, removed, or renamed. `build_dashboard_layout` /
`build_dashboard_app` signatures are unchanged; `_base_layout` loses its `title` parameter but
remains **private**. New private names this chunk introduces (for the test author and the
implementation):
`_category_leaf_label(row, view) -> str`, `_FIGURE_FONT_SANS`, `_FIGURE_FONT_MONO`,
`_RAMP_HEXES`, `_EVIDENCE_GRADE_COLOURS` (re-tuned), `_FROZEN_COLUMN_COUNT`. The interface
delta is the lead's; the planner edits no interface file.

---

## 10. Test plan

Every analytical node carries `@pytest.mark.lreq(...)` and a matching `tests/traceability.json`
key (node-ID → LREQ list). New markers use only `LREQ-RPT-010/020/030/040`. No existing node
ID or traceability key is renamed or removed.

### 10.1 New nodes in `tests/test_report.py`

| Node ID | Marker(s) | Asserts |
|---|---|---|
| `tests/test_report.py::test_dashboard_chart_labels_use_the_final_path_segment_and_stay_unique` | `LREQ-RPT-010` | For the fixture view, the score-bar `y` labels are `Alpha`, `Bravo`, `Charlie` (the final segments), **not** `Alpha/Ranked`; the full `Alpha/Ranked` still appears in the layout (table/detail); the scatter `text` labels are the leaves; a synthetic two-row view whose categories share the leaf (`a/x/Foo`, `b/y/Foo`) yields the two distinct labels `Foo · a/x` and `Foo · b/y`; a non-colliding leaf has no suffix; two builds are equal |
| `tests/test_report.py::test_dashboard_charts_drop_single_series_legends_and_keep_meaningful_ones` | `LREQ-RPT-010` | The score-bar figure `layout.showlegend is False`; the scatter figure `layout.showlegend is False`; the contribution, population, and policy-bump figures `layout.showlegend is not False` (truthy/absent → default True) |
| `tests/test_report.py::test_dashboard_figures_use_mono_numeric_and_sans_label_fonts` | `LREQ-RPT-010` | For all five figures: `layout.font.family == report._FIGURE_FONT_SANS`; `xaxis.tickfont.family == report._FIGURE_FONT_MONO`; `yaxis.tickfont.family == report._FIGURE_FONT_MONO`; `xaxis.title.font.family == report._FIGURE_FONT_SANS` and likewise `yaxis.title.font.family`; no `"title"` key in `layout` (the in-plot title is dropped); the score bar's `yaxis.title.text == "category (leaf)"`, the population `yaxis.title.text == "category (leaf)"`, the contribution `xaxis.title.text == "category (leaf)"` |
| `tests/test_report.py::test_dashboard_policy_bump_has_direct_series_labels_in_ramp_order` | `LREQ-RPT-020` | The bump figure has one trace per `_policy_rank_rows` row; trace `i` has `line["color"] == report._RAMP_HEXES[i % len(report._RAMP_HEXES)]` **and** `marker["color"] == report._RAMP_HEXES[i % len(report._RAMP_HEXES)]` (§4.1 cyclic rule); each trace carries `mode` containing `"text"` and a non-empty `text` on the first policy point; `connectgaps is False` on every trace |
| `tests/test_report.py::test_dashboard_primary_table_freezes_leading_columns_and_dims_secondaries` | `LREQ-RPT-020` | The DataTable `fixed_columns == {"headers": False, "data": report._FROZEN_COLUMN_COUNT}` with `report._FROZEN_COLUMN_COUNT == 7`; `style_header_conditional` and `style_data_conditional` each contain entries whose `if.column_id` is exactly the 23 secondary `_PRIMARY_COLUMNS` attributes (indices 7–29) and whose style sets `fontWeight`/`opacity`, with no entry targeting any of the 7 frozen `column_id`s; the default `columns` names are unchanged (30, `_PRIMARY_COLUMNS` order); no column is added, removed, renamed, or reordered |
| `tests/test_report.py::test_dashboard_css_recolors_evidence_ramp_and_boxes_nav_links` | `LREQ-RPT-010` | The stylesheet defines `.nav-link` with `box-sizing: border-box`; defines the `--ramp-1`..`--ramp-4` tokens and the four new `--evidence-*` values and contains **neither** `#c98b8b` nor `#e0a458`; contains no scheme-bearing URL, `@import`, or `url(` |

### 10.2 Amended nodes (node IDs, markers, and traceability keys unchanged)

- **(a)** `tests/test_report.py::test_dashboard_css_asset_exists_is_offline_and_uses_the_token_set`
  (`:1686`): `_DASHBOARD_CSS_HEXES` (`:1113`) replaces the four retired evidence hexes with the
  four §4.1 ramp stops (no other hex is added or removed; `--danger #e27882` is already
  present). Intent unchanged.
- **(b)** `tests/test_report.py::test_dashboard_evidence_scale_is_retuned_to_the_reference_palette`
  (`:2074`): the expected four hexes become `#9fd7ea`, `#b9dbb0`, `#d5dd93`, `#e6d489` (in
  `EVIDENCE_GRADE_ORDER` order), and the node additionally asserts a div-on-white contrast
  floor: for each ramp stop the WCAG ratio against `#ffffff` is `< 3.0` (documenting why the
  mode bar is disabled). Marker `LREQ-RPT-020`; key `["LREQ-RPT-020"]`
  (`tests/traceability.json:1507–1509`) unchanged.
- **(c)** `tests/test_report.py::test_dashboard_policy_bump_and_kpi_tiles` (`:1582`): the
  `trace["connectgaps"] is False` loop still holds; the test may additionally assert each
  bump trace carries a direct `text` label. Marker/key unchanged (`LREQ-SEN-020`,
  `LREQ-RPT-020`).
- **(d)** `tests/test_report.py::test_dashboard_charts_use_automargin_for_long_category_labels`
  (`:2044`): unchanged (automargin stays `True`; the `l != 140` assertion still holds because
  `_base_layout` keeps a static floor of 8).
- **(e)** `tests/test_report.py::test_dashboard_css_uses_the_reference_palette_and_explicit_type_scale`
  (`:1866`): `_EVIDENCE_SCALE_HEXES` (`:1830`) must be updated to the §4.1 stops, otherwise the
  node fails on the retired hexes (§3.3). Node ID, marker `LREQ-RPT-010`, and key
  (`tests/traceability.json:1494–1496`) unchanged.
- **(f)** `tests/test_report.py::test_dashboard_score_bar_encodes_ordinal_evidence_grade`
  (`:1628–1650`; marker line `:1628` is `@pytest.mark.lreq("LREQ-RPT-020")` **(read)**; key
  `["LREQ-RPT-020"]` at `tests/traceability.json:1535–1537` **(read)**). §5.2 changes the
  score-bar `customdata` to `list[list[str]]`; the node's
  `assert trace["customdata"] == [row.evidence_grade …]` is amended to
  `assert trace["customdata"] == [[row.category, row.evidence_grade] for row in report._scored_rows(view)]`
  (still asserting the exact grade text is at `customdata[i][1]` and
  `"evidence strength" in trace["hovertemplate"]`). The `marker["color"]`,
  `_evidence_colour`, and `_EVIDENCE_GRADE_COLOURS` assertions are unchanged. Node ID, marker,
  and key unchanged.
- **(g)** `tests/test_report.py::test_dashboard_charts_carry_explanations_and_human_labels`
  (`:1498–1518`; marker line `:1498` is `@pytest.mark.lreq("LREQ-RPT-010")` **(read)**; key
  `["LREQ-RPT-010"]` at `tests/traceability.json:1491–1493` **(read)**). §5.1 drops the
  in-plot `layout.title`, so the loop's
  `assert figure["layout"]["title"]["text"]` is amended to assert the card `H3` title is
  present (`report._DASHBOARD_CHART_TITLES[chart_key] in held`, already at `:1509`) **and** the
  figure has no in-plot title (`assert "title" not in figure["layout"]`). The caption and
  component-name assertions are unchanged. Node ID, marker, and key unchanged.

### 10.3 Pinned nodes that MUST stay green **unchanged** (chunk 33/31/32)

`test_dashboard_charts_carry_explanations_and_human_labels` and
`test_dashboard_score_bar_encodes_ordinal_evidence_grade` are **not** here: they are amended in
place (§10.2(f),(g)) and stay green in their amended form.

1. `test_build_dashboard_layout_is_deterministic_for_a_fixed_view`
2. `test_build_dashboard_app_layout_matches_the_layout_builder`
3. `test_dashboard_layout_shows_every_primary_table_column_by_default`
4. `test_dashboard_detail_panel_covers_rpt_030_items_for_a_selected_category`
5. `test_dashboard_layout_keeps_refused_categories_visible_and_off_the_scored_axis`
6. `test_dashboard_layout_includes_the_heuristic_statement`
7. `test_dashboard_distinguishes_null_from_explicit_zero`
8. `test_dashboard_has_no_confidence_interval_or_error_bars`
9. `test_dashboard_policy_bump_and_kpi_tiles`
10. `test_dashboard_omits_the_coverage_heatmap`
11. `test_html_output_is_self_contained_and_deterministic`
12. `test_dashboard_css_asset_exists_is_offline_and_uses_the_token_set`
13. `test_dashboard_css_is_declared_as_package_data`
14. `test_dashboard_app_serves_the_package_assets_folder`
15. `test_dashboard_uses_progressive_disclosure_without_dropping_mandated_content`
16. `test_public_report_functions_have_hints_and_docstrings`
17. `test_dashboard_layout_has_minimal_anchor_navigation_with_inline_svg_and_skip_link`
18. `test_dashboard_column_guide_discloses_every_primary_column_label`
19. `test_dashboard_charts_use_automargin_for_long_category_labels`
20. `tests/test_end_to_end.py::test_acceptance_rendered_report_contains_required_fields`
21. `tests/test_quality_tooling.py::test_report_module_has_no_forbidden_imports_or_clock_reads`

### 10.4 `tests/traceability.json` keys to add (node-ID → LREQ list)

- `tests/test_report.py::test_dashboard_chart_labels_use_the_final_path_segment_and_stay_unique` → `["LREQ-RPT-010"]`
- `tests/test_report.py::test_dashboard_charts_drop_single_series_legends_and_keep_meaningful_ones` → `["LREQ-RPT-010"]`
- `tests/test_report.py::test_dashboard_figures_use_mono_numeric_and_sans_label_fonts` → `["LREQ-RPT-010"]`
- `tests/test_report.py::test_dashboard_policy_bump_has_direct_series_labels_in_ramp_order` → `["LREQ-RPT-020"]`
- `tests/test_report.py::test_dashboard_primary_table_freezes_leading_columns_and_dims_secondaries` → `["LREQ-RPT-020"]`
- `tests/test_report.py::test_dashboard_css_recolors_evidence_ramp_and_boxes_nav_links` → `["LREQ-RPT-010"]`

Run `python -m niche_scout.tools.validate_traceability` — exit 0 required.

The two amended-in-place nodes (§10.2(f),(g)) **keep their existing keys** — no new key is
added for them and no key is removed:
`tests/test_report.py::test_dashboard_charts_carry_explanations_and_human_labels` →
`["LREQ-RPT-010"]` (`tests/traceability.json:1491–1493`);
`tests/test_report.py::test_dashboard_score_bar_encodes_ordinal_evidence_grade` →
`["LREQ-RPT-020"]` (`tests/traceability.json:1535–1537`).

### 10.5 Fixtures

No new arithmetic, so no new golden vector. Reuse
`tests/fixtures/report_fixtures.py::dashboard_rows()` through `_dashboard_view(tmp_path)`
(`test_report.py:1212`) for the leaf, legend, font, table, and CSS nodes. The collision
node's synthetic two-row view (`a/x/Foo`, `b/y/Foo`) is built with the **existing**
`rf.category_score_record(...)` + `rf.run_record(...)` + `_view_with_row(tmp_path, row)` helpers
(`test_report.py:1670`); **the test author adds two category-name constants to
`tests/fixtures/report_fixtures.py` (leaf-collision vector, mirroring the existing
`CATEGORY_LOW_INPUT_FIRST`/`CATEGORY_HIGH_INPUT_SECOND` pattern) and must add them to the
fixture's `__all__` list** (`report_fixtures.py:525–535`) unless the test uses local string
literals. No fixture credentials, no network, no live path.

### 10.6 Offline scan

Grep `src/niche_scout/report.py` for the ramp/evidence hexes and confirm each `figure.update_*`
colour is one of the §4.1/§4.3 hexes; grep the file for `http`/`url(`/`@import` and confirm
zero matches (outside the existing SVG namespace string). Grep `dashboard.css` for
`#c98b8b`/`#e0a458` and confirm zero matches.

---

## 11. Files touched (the plan's file-discipline list)

- `src/niche_scout/report.py` — `_FIGURE_FONT_SANS`/`_FIGURE_FONT_MONO` literals;
  `_EVIDENCE_GRADE_COLOURS` re-tune (§3.1); `_base_layout` loses `title`, gains the font keys
  (§5.1); `_category_leaf_label` (§5.2); the five builders' label/legend/colour/hover/axis-
  title changes (§5.2–§5.4); the `_FROZEN_COLUMN_COUNT` constant, `fixed_columns`, and the
  DataTable conditional-style props (§6.1).
- `src/niche_scout/assets/dashboard.css` — four `--evidence-*` values re-tuned;
  `--ramp-1`..`--ramp-4` tokens; `box-sizing: border-box` on `.nav-link` (§4.4, §7). No table
  class hook is added for the freeze/de-emphasis (§6.2 is DataTable-prop driven).
- `tests/test_report.py` — six new nodes (§10.1); amended constants `_DASHBOARD_CSS_HEXES`
  and `_EVIDENCE_SCALE_HEXES`; the nodes amended in place in §10.2 (including
  `test_dashboard_score_bar_encodes_ordinal_evidence_grade` and
  `test_dashboard_charts_carry_explanations_and_human_labels`).
- `tests/traceability.json` — six new keys (§10.4); the two amended-in-place nodes keep their
  existing keys.
- `tests/fixtures/report_fixtures.py` — two optional leaf-collision category constants + their
  `__all__` entries (§10.5); only if the test author needs shared names.

No other file is in scope. Any other file needing a change is a stop-and-flag. (Run log
`Documents/runs/chunk-34.md` and the interface delta, if any, are the lead's.)

---

## 12. Definition of Done / gate bullets

- [ ] `python -m pytest -q` — full suite green: six new nodes pass; every §10.3 pinned node
      passes **unchanged**; the two §10.2(f),(g) amended nodes pass in their amended form; no
      other tree changes.
- [ ] `python -m niche_scout.tools.validate_traceability` — exit 0; each new node has a marker
      and a matching key; no orphan entry.
- [ ] `python -m niche_scout.tools.check_import_boundaries` — exit 0 (`metrics.py`/
      `scoring.py` untouched; `report.py` gains no forbidden import).
- [ ] `python -m niche_scout.tools.check_scope_prohibitions` — exit 0.
- [ ] `ruff format --check` and `ruff check` clean on changed Python files (the CSS is not
      linted).
- [ ] Chart category ticks/hover show the final `/`-segment; the full path remains in the
      primary table cell, the column guide, the selector, and the detail heading; two
      same-leaf categories are disambiguated (`leaf · parent`) and the suffix appears for the
      whole colliding group only.
- [ ] The pair {score bar, scatter} has `showlegend is False`; the other three keep legends;
      the population legend is horizontal below the plot; no figure has a `layout.title` (the
      card `H3` remains).
- [ ] For all five figures, numeric ticks use `_FIGURE_FONT_MONO` and axis titles use
      `_FIGURE_FONT_SANS`; no web font, `@import`, or URL is introduced.
- [ ] `_EVIDENCE_GRADE_COLOURS` equals the four §4.1 ramp stops in `EVIDENCE_GRADE_ORDER`
      order; the CSS defines the same four values and contains neither `#c98b8b` nor `#e0a458`.
- [ ] The policy-bump series index `i` (over `_policy_rank_rows(view)` order) sets both
      `line.color` and `marker.color` to `_RAMP_HEXES[i % len(_RAMP_HEXES)]`, so 18 series
      never index past the 4-stop tuple.
- [ ] The DataTable freezes the leading 7 columns (`fixed_columns == {"headers": False,
      "data": report._FROZEN_COLUMN_COUNT}`, `_FROZEN_COLUMN_COUNT == 7`); the secondary
      conditional-style entries target exactly the `_PRIMARY_COLUMNS` attribute `column_id`s at
      indices 7–29 with `fontWeight`/`opacity`; the default columns are unchanged (30,
      `_PRIMARY_COLUMNS` order); no column is removed, renamed, or reordered.
- [ ] `.nav-link { box-sizing: border-box }` is present; the desktop rail link no longer
      overflows (lead re-measures with Kilo Playwright the +7.5 px icon offset).
- [ ] `report.py` imports no `metrics`/`scoring`/`collector*`/`config`/`pipeline`/`cli` and
      reads no clock; no new Dash callback; every `DASHBOARD_COMPONENT_IDS` id preserved.
- [ ] The `.scratch/` SQLite probe (§6.3) reports exactly one distinct non-null marker symbol
      (`diamond-open`).
- [ ] No file outside §11 changed.

---

## 13. Lead rulings carried (from the run log; not re-opened)

- **L34-1 — item 6 is compliant visual prioritization (option A).** All 30 `LREQ-RPT-020`
  columns stay in the DOM; no column is removed; the SRS and interface §7 are untouched. This
  plan implements it with the native DataTable `fixed_columns` freeze on the leading 7 columns
  plus a light `fontWeight`/`opacity` de-emphasis of the secondary group only.
- **L34-2 — one analogous pastel cyan→yellow ramp** for chart curves/bars, with a reserved
  contrasting `--danger`-family colour *with a distinct marker shape* for out-of-line data.
  The stop hexes are the plan's to fix (§4.1) and are hand-computed in §4.2.
- **L34-3 — leaf-only chart labels**, with the full path retained in the table/detail and in
  hover; collision-safe.
- **L34-4 — offline/no-CDN, purity, and all chunk-33 content-preservation guarantees are
  retained.** No web font; local/system stacks only, baked as literals.
- **L34-5 — every pinned chunk-33/31/32 node stays green** unless this plan explicitly
  supersedes it (§3 names the only three touched nodes/constants, all amended in place with
  unchanged IDs and keys).

---

## 14. Evidence walk for the countable claims in this plan

- **"30 primary columns" (§1.2, §6.2, §10.3)** — **(counted:** `report._PRIMARY_COLUMNS` is
  pinned by `tests/test_report.py:1056` (`len(...) == 30`) and `:1426` (rendered header count
  == 30)); unit: tuple entries / rendered headers. The run log independently counted 30 live
  DOM headers. This plan adds no new "30" assertion.
- **"five figure builders" (§2, §5)** — **(counted:** the `builders` dict at
  `report.py:1887–1893` has exactly five key→function entries). Unit: dict entries.
- **"three trace `name=` values in the population figure" (§5.3)** — **(counted:** grep for
  `go.Scatter(`/`name=` in `report.py` returned three population `name=` arguments at `:1796`,
  `:1807`, `:1824`). Unit: distinct string arguments in that builder.
- **"no test reads the population figure's trace `name=` values"** — **(counted:** grep for
  `name=` string literals in `tests/test_report.py` returned no match against the figure
  trace names; the pinned node reads trace data/`text`, not `name`). The literal
  `discovered population (observed)` **does** occur as `_OBSERVED_LABELS[0]` (`report.py:310`)
  and is asserted through the detail disclosure; that is a different occurrence and is not
  renamed by this chunk. Unit: matched test lines.
- **"`fixed_columns` is a real prop and conditional styles have no `className` key"
  (§2, §6.1)** — **(read:** the installed package
  `C:\Users\<redacted-user>\AppData\Local\Programs\Python\Python312\Lib\site-packages\dash\dash_table\
  DataTable.py`: `fixed_columns` described at `:311–330` (dict with `headers`/`data`);
  `style_cell_conditional` `:949–961`, `style_data_conditional` `:963–983`,
  `style_header_conditional` `:1001–1017` document only the `if` sub-keys plus free-form CSS
  style properties; no `className` key appears). Unit: prop docstring line ranges.
- **"the two chunk-33 hex constants holding the retired evidence values" (§3.2–§3.3)** —
  **(read:** `tests/test_report.py:1113–1124` (`_DASHBOARD_CSS_HEXES`) and `:1830`
  (`_EVIDENCE_SCALE_HEXES`)); unit: constant names.
- **"`_base_layout` is the single shared style seam" (§5.1)** — **(read:** `report.py:1457–
  1485`; every builder calls `figure.update_layout(**_base_layout(...))` at `:1700`, `:1728`,
  `:1752`, `:1828`, `:1872`). Unit: call sites.
- **"the mode bar is already disabled" (§5.4)** — **(read:** `report.py:1924`,
  `config={"displayModeBar": False, "responsive": True}`). Unit: config key.
- **"`connectgaps is False` on every bump trace" (§10.2c)** — **(read:** `report.py:1749`;
  the pinned node asserts it at `tests/test_report.py:1603–1604`). Unit: trace key.
- **"the two amended-in-place nodes keep their markers and keys" (§3.1, §10.2(f),(g))** —
  **(read:** `tests/test_report.py:1628` is `@pytest.mark.lreq("LREQ-RPT-020")` for
  `test_dashboard_score_bar_encodes_ordinal_evidence_grade`, key `["LREQ-RPT-020"]` at
  `tests/traceability.json:1535–1537`; `tests/test_report.py:1498` is
  `@pytest.mark.lreq("LREQ-RPT-010")` for
  `test_dashboard_charts_carry_explanations_and_human_labels`, key `["LREQ-RPT-010"]` at
  `tests/traceability.json:1491–1493`). Unit: 1-based line numbers / JSON keys.
- **"the policy bump can hold more series than the 4-stop ramp" (§4.1, §5.3, §10.1)** —
  **(counted:** the run-log live-audit finding 9 counted 18 policy series in the legend;
  `_RAMP_HEXES` has 4 stops by the §4.1 table). 18 > 4, so the series index must be taken
  modulo 4; unit: series count vs distinct hex count.
- **Contrast ratios (§4.2–§4.3)** — hand-computed with the WCAG relative-luminance formula;
  reproducible from the formula; **not tool-verified this session.** Unit: ratio to two decimals.
- **"the retired `#c98b8b`/`#e0a458` appear nowhere in chunk-34 output" (§4.4, §10.1)** — the
  claim is an assertion the new node enforces; it is **not** independently verified in this
  planning session.
- **Run-log findings 1–9** — the lead measured the live page (fonts, colours, legend items,
  header count, nav geometry, console errors) with Kilo Playwright; this plan consumes those
  numbers and labels them **(read** from the run log), not re-measured here.

---

## 15. Open questions

None. The lead's eight frozen scope decisions settle every open item; this plan fixes the only
two values the scope contract left to the plan (the ramp stop hexes §4.1 and the shared font
literals §5.1) by direct hand-computation and by copying the existing `--font-*` stacks. No
SRS gap remains open for chunk 34: `LREQ-RPT-010` (one-command local read-only dashboard) and
`LREQ-RPT-020` (the 30-column primary table) are read at `SRS-lean-v2.md:1153–1189` and are
satisfied by preserving content and changing presentation only. The standing obligations —
URI trailing-identifier extraction, OI-6, `runs.taxonomy_sha256` — are unchanged and are not
chunk 34's.

Note for the test author: a non-blocking fixture-admin detail is recorded in §10.5 (add the
two leaf-collision category constants to `report_fixtures.__all__` if the test shares them);
that is a fixture-bookkeeping instruction, not an open question.
