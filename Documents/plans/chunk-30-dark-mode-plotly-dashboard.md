# Chunk 30 — dark-mode Plotly run dashboard (plan)

Status: FROZEN — 2026-09-30. Q1–Q6 resolved by the lead from the independent research dispatch
plus the operator direction of 2026-09-30; see §12 Rulings. Every section is
implementation-ready.
Chunk 30 is a new remediation/feature chunk not present in
`Documents/requirements-dependency-map.md` §3/§4 (chunk-14/chunk-24 precedent: registration =
plan + run log + branch). Do not edit the dependency map, the SRS, `AGENTS.md`, or `.kilo/`.

Branch: `chunk-30` (per `Documents/runs/chunk-30.md` §Branch), base `main` @ `092e55f`.
Authority: `Documents/runs/chunk-30.md` and the frozen contracts it cites. The four
operator-authorized decisions D-1..D-4 in that log are **fixed** and are not re-opened here.

Predecessors merged and frozen: Chunk 0 (`models`), Chunk 2 (`database`), Chunk 11 (report
renderer/dashboard), Chunk 12 (CLI), Chunk 24 (stratum geometry). This chunk amends the frozen
`interfaces/chunk-00.md` (`Repository` protocol), `interfaces/chunk-02.md` (read API),
`interfaces/chunk-11.md` (report public surface and `CategoryReportRow`/`RunReportView`), and
`interfaces/chunk-12.md` (CLI contract, Ruling 3 amendment). The lead applies those interface
edits; the implementer uses the amended text.

SRS authority: `Documents/SRS-lean-v2.md` §10 `LREQ-RPT-010`..`LREQ-RPT-050` and
`LREQ-CLI-020` (lines 1155–1200), the §10 no-trends paragraph (lines 1187–1189), §12 (module
conventions, lines 1235–1270), §14 constants (lines 1332–1361), §15/§16 (lines 1365–1416), and
Appendix C (warning vocabulary). AGENTS.md "Out of scope — do not add" and Hard rules 1–4.

---

## 1. Scope, non-goals, LREQ roles, files touched

### 1.1 Scope (in)

1. **Dependency (D-1).** Add `plotly` to `pyproject.toml` `[project].dependencies`.
2. **New renderer (D-2, D-4).** A new dark-mode, self-contained HTML renderer in `report.py`
   that emits **inline** Plotly JS (no CDN, no external asset, no network), fixed chart
   `div_id`s, deterministic/byte-identical for a fixed view.
3. **Charts.** (a) ranked horizontal composite-score bar with a visual gap before refused
   categories; (b) stacked bar of weighted contributions (`W_D·D, W_C·C, W_R·R, W_Q·Q`
   renormalised over available components), rank-sorted; (c) category × status heatmap with the
   SRS §14 coverage thresholds as reference lines (D/R/Q numeric coverage + a C status column;
   see §12 R1); (d) 3-policy rank bump chart plus
   `top_3_stability` / `top_5_stability` / `maximum_rank_displacement` KPI tiles; supporting
   log-scale population lollipop with sample-size marker, component dumbbell, score-vs-quality
   scatter sized by `sample_fraction`.
4. **Latest-run default (D-3).** `niche-scout dashboard --run-id` becomes optional and defaults
   to the most recent run by `run_started_at_utc`; single-run display only. Requires a new
   additive repository read (§3) and the Ruling 3 amendment.
5. **Read model extension.** Expose the persisted per-policy ranks, breadth status, and
   run-level sensitivity summary needed by the charts (§4).

### 1.2 Non-goals (explicitly NOT in this chunk)

- No historical trend, cross-run comparison, run-over-run chart, or multi-run overlay
  (SRS §10 line 1187; §15 line 1379; AGENTS.md out-of-scope list). The dashboard renders exactly
  one selected run.
- No confidence intervals, error bars, or statistical-precision claim anywhere (AGENTS.md
  out-of-scope; Appendix C vocabulary).
- No configurable weights; `W_D/W_C/W_R/W_Q` and the sensitivity policies come from `models`
  (SRS §14 line 1353).
- No schema change, no new table/column/index, no pipeline change, no change to
  `metrics.py`/`scoring.py` (purity boundary held).
- No recomputation of any metric, component, score, evidence grade, rankability, or sensitivity
  value; the renderer renders persisted values verbatim (Chunk 11 §1, §7).
- No clock read anywhere in `report.py`; `scoring_cutoff_utc` remains an explicit persisted
  value.
- No enrichment/discovery from the dashboard (LREQ-CLI-020).
- No browser launch, no server, no file write from `dashboard` (Ruling 6 retained; see Q4).
- No change to `render_run_report_html` / `render_run_report_text` / `write_run_report` output.

### 1.3 LREQ roles

| Role | LREQs |
|---|---|
| Primary | `LREQ-RPT-010` (one-command local dashboard, self-contained), `LREQ-RPT-020` (primary table / read model), `LREQ-CLI-020` (dashboard reads the database only) |
| Supporting contract | `LREQ-RPT-030` (category details retained), `LREQ-RPT-040` (non-rankable stay visible and off the scored axis), `LREQ-RPT-050` (heuristic statement present), `LREQ-SEN-020` (3-policy ranks and stability outputs rendered from persisted values) |
| Integration completion | `LREQ-NFR-040` (public renderer type hints/docstrings), `LREQ-ARCH-010`/`LREQ-ARCH-020` (purity: `report.py` imports no forbidden module and reads no clock; `metrics`/`scoring` untouched) |

### 1.4 Files touched (the plan's file-discipline list)

Production:
- `pyproject.toml` — `[project].dependencies` gains `plotly` (D-1).
- `src/niche_scout/database.py` — new `SqliteRepository.get_latest_run_id`; add the same method
  to the `Repository` protocol (`src/niche_scout/database.py:270-308`).
- `src/niche_scout/report.py` — read-model fields + `RunSensitivitySummary`; new dark-mode
  Plotly renderer and its private pure helpers; `render_dashboard_html` body repointed (same
  signature).
- `src/niche_scout/cli.py` — `build_parser` dashboard `--run-id` optional; `dashboard_command`
  resolves the latest run when absent.

Interfaces (frozen; the **lead** amends them in the same change — §2):
- `Documents/interfaces/chunk-00.md`, `Documents/interfaces/chunk-02.md`,
  `Documents/interfaces/chunk-11.md`, `Documents/interfaces/chunk-12.md`.

Tests:
- `tests/test_report.py`, `tests/test_cli.py`, `tests/test_database.py`,
  `tests/fixtures/report_fixtures.py`, `tests/fixtures/cli_fixtures.py`, `tests/traceability.json`.
- `tests/test_contracts.py` only if the widened `Repository` protocol breaks an exact-set
  assertion (the existing assertion is a subset check at `tests/test_contracts.py:948`, so no
  change is expected).

No other file is in scope. Any other file needing a change is a stop-and-flag.

---

## 2. Interface doc deltas (explicit list for the lead)

Apply all of these consistently with the code; they are the frozen-contract updates.

1. **`Documents/interfaces/chunk-00.md`** — add to the `Repository` protocol (current lines
   322–335) the signature
   `def get_latest_run_id(self) -> Optional[str]: ...` with the §3 semantics (deterministic,
   no clock). No other protocol name changes.
2. **`Documents/interfaces/chunk-02.md`** — add `get_latest_run_id(self) -> Optional[str]` to
   §2.8 "Read and count APIs" with the §3 semantics and the determinism note; add a one-line
   note to §3 "Behavioral contracts" that run selection is deterministic and never uses the
   clock.
3. **`Documents/interfaces/chunk-11.md`** —
   - §4: add the frozen dataclass `RunSensitivitySummary`; add fields
     `rank_demand_heavy: int | None`, `rank_competition_heavy: int | None`,
     `breadth_completeness_status: str | None`, `breadth_source: str | None` to
     `CategoryReportRow`; add `sensitivity: RunSensitivitySummary | None` to `RunReportView`.
   - §5: add `render_run_dashboard_html(view: RunReportView) -> str` and record that
     `render_dashboard_html(repository, run_id)` keeps its exact signature and self-containment
     guarantee but now returns the dark-mode Plotly document (its body is repointed).
   - §2: add the new constants `COMPONENT_WEIGHTS`, `EVIDENCE_GRADE_ORDER`,
     `COVERAGE_REFERENCE_THRESHOLDS`, `DASHBOARD_CHART_IDS`.
   - §7: extend the display rules: null is a distinct "n/a" marker/absent trace, explicit `0`
      renders as `0`, refused categories never share the scored axis with rankable ones, evidence
      grade is an ordinal colour scale, no confidence interval/error bar, coverage and
      `sample_fraction` labelled as distinct quantities.
   - §4/§7: **correct the stale rank locant** (§12 R7) — `chunk-11.md:72` and `chunk-11.md:197`
      state the display rank comes from `ranking_sensitivity_json.ranked_categories`; the
      implemented contract reads `rank_balanced` from the `categories` list
      (`report.py:550-579`, `LREQ-SEN-020`,
      `tests/test_report.py::test_rank_from_sensitivity_reads_rank_balanced_not_position`). Fix
      both lines to "rank = `rank_balanced` from `ranking_sensitivity_json.categories`".
4. **`Documents/interfaces/chunk-12.md`** —
   - §4: `CliOptions.run_id` is now the **optional** dashboard selector
     (`--run-id` or the most-recent run by `run_started_at_utc`).
   - §5: `build_parser` — `dashboard` accepts `--run-id` with `required=False`, `default=None`
     (still no `--latest`); `dashboard_command` resolves the latest run when `options.run_id`
     is `None`.
   - §6: **remove** "`dashboard` without `--run-id` is an argparse usage error (exit 2)" and
     replace it with: absent `--run-id` selects the most recent run; an empty `runs` table is a
     runtime failure (`EXIT_RUNTIME_ERROR`) that calls no renderer; a given-but-unknown run id
     still maps `RunNotFoundError` to `EXIT_RUNTIME_ERROR`. Note the deliberate amendment of
     Ruling 3 (D-3) and that Ruling 6 (stdout, no file write) is retained.
   - §8: drop the Ruling 3 no-default statement; keep OI-6 and the other open obligations
     unchanged.

No SRS, `AGENTS.md`, dependency-map, or `.kilo/` edit is in scope.

---

## 3. Repository read (additive)

Add to `SqliteRepository` and to the `Repository` protocol:

```python
def get_latest_run_id(self) -> str | None:
    """Return the run_id of the run with the greatest ``run_started_at_utc``.

    Reads ``SELECT run_id, run_started_at_utc FROM runs`` and selects in Python:
    the greatest decoded timezone-aware UTC ``run_started_at_utc``; a tie is broken
    by the lexicographically smallest ``run_id``. Returns ``None`` when ``runs``
    is empty. Read-only, deterministic, no clock read, no network.

    Python-side selection (not a SQL ``ORDER BY`` on the TEXT column) is required
    because ``database._encode_column`` writes ``datetime.isoformat()``, whose
    fractional-second part is present only when non-zero, so lexicographic TEXT
    order is not reliably chronological.
    """
```

Behavior (exact, for the test author):

- Empty `runs` table → `None`.
- Distinct timestamps → the row with the maximum decoded `run_started_at_utc`.
- Equal timestamps → the row with the lexicographically smallest `run_id`
  (§12 R3, confirmed).
- Never reads the clock; never writes anything; raises `ClosedRepositoryError` after `close()`
  like every other method (`_check_open` first).

Supporting fact already in place: `runs.run_started_at_utc` is `NOT NULL`
(`src/niche_scout/database.py` DDL) and `RunRecord.run_started_at_utc` is an aware-UTC
`datetime`.

---

## 4. Read-model additions (`report.py`, frozen after §2 is applied)

### 4.1 New dataclass

```python
@dataclass(frozen=True, slots=True)
class RunSensitivitySummary:
    """Run-level persisted ranking-sensitivity summary (parsed from
    ``ranking_sensitivity_json``; never recomputed).

    Every field is ``None`` when the persisted value is null/absent. ``None`` is
    never coerced to ``0``/``0.0``/``False``. ``policies`` is ``()`` when absent.
    """

    policies: tuple[str, ...]
    top_3_stability: float | None
    top_5_stability: float | None
    maximum_score_delta: float | None
    maximum_rank_displacement: int | None
    warning: bool | None
    reference_set_size: int | None
    displacement_threshold: float | None
```

### 4.2 `CategoryReportRow` additions (appended fields)

```python
    rank_demand_heavy: int | None          # from ranking_sensitivity_json.categories; None absent
    rank_competition_heavy: int | None     # from ranking_sensitivity_json.categories; None absent
    breadth_completeness_status: str | None  # persisted category_scores.breadth_completeness_status
    breadth_source: str | None               # persisted category_scores.breadth_source
```

`__bool__`/int rule applies as for `rank`: `bool` is never accepted as an `int`; an
unparseable/absent value is `None`.

### 4.3 `RunReportView` addition

```python
    sensitivity: RunSensitivitySummary | None
```

`None` when no `category_scores` row exists (failed-preflight fallback) or the persisted
payload is invalid JSON / a non-object / `{}`. When the payload exists but its outputs are
null (e.g. an 8–20 category provisional run), the object is non-`None` with `None` fields.

### 4.4 New constants (all sourced from `models`/SRS; never hard-coded)

```python
COMPONENT_WEIGHTS: tuple[tuple[str, float], ...]        # (("D", W_D), ("C", W_C), ("R", W_R), ("Q", W_Q))
EVIDENCE_GRADE_ORDER: tuple[str, ...]                   # ("insufficient", "weak", "moderate", "strong")
COVERAGE_REFERENCE_THRESHOLDS: tuple[tuple[str, float], ...]  # (("minimum", MIN_REQUIRED_COMPONENT_COVERAGE),
                                                              #  ("strong", STRONG_COMPONENT_COVERAGE))
DASHBOARD_CHART_IDS: tuple[tuple[str, str], ...]        # fixed (chart key, div_id) pairs, e.g.
                                                        # ("score_bar", "niche-scout-score-bar"), ...
```

`EVIDENCE_GRADE_ORDER` must equal `tuple(g.value for g in reversed(list(EvidenceGrade)))`; a test
pins that equality so the ordinal source is the enum, not a second literal.
`COMPONENT_WEIGHTS` is built from the imported `models.W_D/W_C/W_R/W_Q`;
`COVERAGE_REFERENCE_THRESHOLDS` from `models.MIN_REQUIRED_COMPONENT_COVERAGE` (0.50) and
`models.STRONG_COMPONENT_COVERAGE` (0.80) (SRS §14 lines 1343–1344).
`DASHBOARD_CHART_IDS` fixes every `div_id` (D-2) so Plotly does not generate a random one.

### 4.5 Private pure helpers (testable; not frozen in an interface file)

```python
def _ranks_from_sensitivity(payload: str, category: str) -> tuple[int | None, int | None, int | None]:
    """Return (rank_balanced, rank_demand_heavy, rank_competition_heavy) for
    ``category`` from ``ranking_sensitivity_json``. Any element is None for an
    invalid payload, a non-object, a missing/empty/non-list ``categories``, no
    matching entry, a non-mapping entry, or a missing/non-int value (``bool`` is
    not an int)."""

def _run_sensitivity(scores: Sequence[CategoryScoreRecord]) -> RunSensitivitySummary | None:
    """Parse the run-level summary from the first row's ``ranking_sensitivity_json``
    (rows are category-sorted and carry one identical payload). None when ``scores``
    is empty, the JSON is invalid/non-object, or it is ``{}``. Every present-but-null
    output stays None."""

def _scored_rows(view: RunReportView) -> tuple[CategoryReportRow, ...]:
    """Rows with ``rank is not None``, in view order. The only rows allowed on the
    scored axis."""

def _refused_rows(view: RunReportView) -> tuple[CategoryReportRow, ...]:
    """Rows with ``rank is None`` (refused/unranked), in view order. Never on the
    scored axis."""

def _component_contributions(row: CategoryReportRow) -> tuple[tuple[str, float], ...]:
    """Renormalised weighted contributions of the composite score, ordered D, C, R, Q.

    contribution_i = W_i * x_i / sum(W_j for available j), where an available
    component is one whose value is not None. All four available -> the four
    contributions sum to the persisted composite score. A missing component is
    omitted (not zero). No component available -> (). A None component is never
    rendered as a zero-height stack segment."""

def _evidence_grade_position(grade: str) -> int | None:
    """Ordinal position in EVIDENCE_GRADE_ORDER (insufficient=0 .. strong=3); None
    for an unknown grade. The colour scale is ordinal, not categorical."""

def _policy_rank_rows(view: RunReportView) -> tuple[tuple[str, int | None, int | None, int | None], ...]:
    """One (category, rank_balanced, rank_demand_heavy, rank_competition_heavy) tuple
    per scored row, in view order, for the bump chart. No recomputation."""

def _kpi_tiles(view: RunReportView) -> tuple[tuple[str, float | int | None], ...]:
    """The three run-level KPI tiles in fixed order: top_3_stability, top_5_stability,
    maximum_rank_displacement, read from ``view.sensitivity``; ``None`` -> an 'n/a'
    tile (never 0)."""
```

`_rank_from_sensitivity` (existing, `report.py:550`) is retained unchanged (its tests stay).

---

## 5. Renderer design

### 5.1 Public functions

```python
def render_run_dashboard_html(view: RunReportView) -> str:
    """One self-contained dark-mode HTML document for ``view``.

    Includes inline Plotly JS (``include_plotlyjs="inline"`` on the first figure and
    False on the rest), fixed ``div_id``s from DASHBOARD_CHART_IDS, inline CSS, no
    ``<script src>``, no ``<link>``, no CDN reference, no network, no clock. Also
    includes HEURISTIC_STATEMENT, the sorted primary table, and the per-category
    detail panel (so LREQ-RPT-020/030/040/050 hold in the dashboard). Deterministic
    and byte-identical for a fixed ``view``."""

def render_dashboard_html(repository: SqliteRepository, run_id: str) -> str:
    """Existing frozen signature; body repointed to
    ``render_run_dashboard_html(load_run_report_view(repository, run_id))``.
    Database reads only; no clock; raises RunNotFoundError when absent."""
```

### 5.2 Determinism and self-containment rules (normative)

- One inline `<script>` carrying plotly.js; every chart's `Plotly.newPlot` uses a fixed
  `div_id` from `DASHBOARD_CHART_IDS`.
- No `chart_id` randomness: never call Plotly with an auto-generated div id.
- Every series/trace order is explicit and derived from `view.categories` order or a fixed
  constant; no set/dict iteration determines an order.
- No `datetime.now`/`utcnow`/`time.time` in `report.py`.
- The support/JS side is client-side only; the emitted bytes assert
  `render_run_dashboard_html(view) == render_run_dashboard_html(view)`.
- Plotly's `to_html` determinism for a fixed figure/div_id is **not yet verified in this repo**
  (see UNVERIFIED). If the implementer finds any non-deterministic byte (e.g. a random id in
  the emitted script), STOP and report; D-2 requires byte-identical output and this plan does not
  authorize a non-deterministic dashboard.

### 5.3 Charts (each with its guardrail)

(a) **Score bar** (`score_bar`, horizontal). One categorical y-axis. Entries are
`_scored_rows(view)` in view order (rank ascending), then one empty gap band, then
`_refused_rows(view)` in view order. The bar trace has a value only for scored rows; refused
rows are annotations rendering `n/a` and **no bar** (they never sit on the scored axis). A null
score renders `n/a`; an explicit `0.0` renders a zero-length bar labelled `0`.

(b) **Contribution stack** (`contribution_stack`), rank-sorted. One stacked bar per scored row
using `_component_contributions`; the stack height equals the persisted composite score; each
segment is a component (D/C/R/Q) in fixed order. Refused rows are absent. A missing component
contributes no segment and is never a zero segment.

(c) **Category × status heatmap** (`status_heatmap`). Rows = categories (view order); columns: the
three numeric **D/R/Q** stratum eligibility coverages, then `evidence_grade` (ordinal colour
scale via `_evidence_grade_position`), `rankability_status`, and a **C column carrying
`breadth_completeness_status` / `breadth_source` (categorical), never labelled "coverage"**
(§12 R1: the frozen model defines no competition coverage; `LREQ-SCR-020` gives C no coverage
shrinkage term). Reference lines at the values in `COVERAGE_REFERENCE_THRESHOLDS` (0.50, 0.80)
are drawn **only** on the three numeric coverage columns. `sample_fraction` is labelled as sample
fraction and never merged with stratum eligibility coverage.

(d) **Policy bump chart** (`policy_bump`) from `_policy_rank_rows(view)`: three x positions
(`balanced`, `demand_heavy`, `competition_heavy`) and one line per scored category whose rank is
non-null in at least two policies; a null rank is a gap, never a 0. Plus the `_kpi_tiles` strip
(`top_3_stability`, `top_5_stability`, `maximum_rank_displacement`), each `n/a` when `None`.

Supporting charts: **population lollipop** (`population_lollipop`), log x-axis, marker at
`discovered_population_count` and a sample-size marker at `enriched_sample_count`; a measured
`0` population is a distinct explicit-zero marker labelled `0`, a `None` is absent plus `n/a`
(see Q5). **Component dumbbell** (`component_dumbbell`) and **score-vs-quality scatter**
(`score_quality_scatter`, marker size from `sample_fraction`) are secondary but in scope; where
`sample_fraction` is `None` the marker uses the documented fixed fallback size and is labelled
`n/a` (never treated as `0`).

Common guardrails: no confidence interval or error-bar trace anywhere; refused categories never
share the scored axis with rankable ones; evidence grade is ordinal; `n/a` (null) is visually
distinct from `0`; every threshold/weight comes from `models`/SRS constants; `HEURISTIC_STATEMENT`
appears verbatim.

### 5.4 Plotly usage detail

- `plotly.io.to_html(fig, include_plotlyjs="inline", full_html=False, div_id=<fixed>, config={...})`
  for the first chart; `include_plotlyjs=False` for the rest, so exactly one inline copy of
  plotly.js is emitted.
- `config` disables the modebar (e.g. `{"displayModeBar": False}`) so no modebar link to an
  external site is emitted.
- The document is assembled by `report.py` itself (its own `<!DOCTYPE html>` head/body/CSS) and
  must not use `to_html(..., full_html=True)` (which would emit one document per figure).
- `report.py` may import `plotly`; it must still not import `metrics`, `scoring`, `collector*`,
  `config`, `pipeline`, or `cli`, and must not read the clock (D-4; Chunk 11 §1).

---

## 6. Ordered implementation steps

1. **Dependency.** `pyproject.toml`: `dependencies = ["plotly>=7.1,<8"]` (§12 R6; PyPI latest is
   `plotly` 7.1.0, 2026-09-15). Install into the dev env before running the dashboard tests.
2. **Repository read.** Add `get_latest_run_id` to `Repository` and `SqliteRepository` (§3).
3. **Read model.** Add `RunSensitivitySummary`, the four `CategoryReportRow` fields, the
   `RunReportView.sensitivity` field, the constants, and the private helpers (§4). Populate the
   new fields in `_row_from_score` and `_fallback_row` (fallback → all `None`), and build
   `sensitivity` in `load_run_report_view`.
4. **Renderer.** Add `render_run_dashboard_html` and its chart builders (§5); repoint
   `render_dashboard_html`.
5. **CLI.** `build_parser`: `--run-id` optional. `dashboard_command`: if `options.run_id` is
   `None`, `run_id = repository.get_latest_run_id()`; if that is `None`, print a redacted error
   to `stderr` and return `EXIT_RUNTIME_ERROR`; else call `report_renderer(repository, str(run_id))`
   as today. Keep the existing `report_renderer` injection seam and signature.
6. **Tests** (§7) and `tests/traceability.json`.
7. **Formatter/linter** per `pyproject.toml` (`ruff format`, `ruff check`) and the validators.

---

## 7. Test plan (exact node IDs; every analytical node has `@pytest.mark.lreq(...)`)

### 7.1 `tests/test_report.py` — new nodes

| Node ID | Marker(s) | Asserts |
|---|---|---|
| `tests/test_report.py::test_load_run_report_view_exposes_policy_ranks_and_run_sensitivity` | LREQ-RPT-020, LREQ-SEN-020 | the three per-policy ranks and `breadth_completeness_status`/`breadth_source` are read verbatim from the fixture; `view.sensitivity` carries the fixture's run-level values; a `{}` payload yields `sensitivity is None`; an all-null payload yields a non-None summary with None fields |
| `tests/test_report.py::test_component_contributions_renormalise_over_available_components` | LREQ-RPT-020 | all-four vector sums to the composite; a two-component vector renormalises by the available weight sum; a missing component is omitted (never a zero segment); no available component → `()` |
| `tests/test_report.py::test_evidence_grade_order_is_the_enum_reversed` | LREQ-RPT-020 | `EVIDENCE_GRADE_ORDER == tuple(g.value for g in reversed(list(EvidenceGrade)))`; `_evidence_grade_position` maps insufficient→0 … strong→3 and an unknown grade→None |
| `tests/test_report.py::test_run_dashboard_html_is_self_contained_dark_mode_and_deterministic` | LREQ-RPT-010 | `"<script src" not in html`, `"<link" not in html`, `"cdn.plot.ly" not in html`, `"@import" not in html`; `<script>` present; every fixed `div_id` present; `html == render_run_dashboard_html(view)` |
| `tests/test_report.py::test_run_dashboard_includes_heuristic_statement_primary_table_and_details` | LREQ-RPT-050, LREQ-RPT-020, LREQ-RPT-030 | `HEURISTIC_STATEMENT in html`; the primary table header set equals the LREQ-RPT-020 label set; category detail sections present |
| `tests/test_report.py::test_run_dashboard_keeps_refused_categories_off_the_scored_axis` | LREQ-RPT-040 | `_refused_rows(view)` are non-empty and disjoint from `_scored_rows(view)`; each refused category appears with `n/a` and no numeric score; rankable rows remain visible |
| `tests/test_report.py::test_run_dashboard_distinguishes_null_from_explicit_zero` | LREQ-RPT-020 | a `0.0` component/score renders `0`; a `None` renders `n/a`/absent; the two strings differ |
| `tests/test_report.py::test_run_dashboard_has_no_confidence_interval_or_error_bars` | LREQ-RPT-010 | no error-bar trace key (`"error_y"`, `"error_x"`) and no CI wording in the document |
| `tests/test_report.py::test_run_dashboard_policy_bump_and_kpi_tiles` | LREQ-SEN-020, LREQ-RPT-020 | `_policy_rank_rows` matches the persisted three ranks; a null rank is a gap not 0; `_kpi_tiles` renders the three values, `n/a` for None |
| `tests/test_report.py::test_run_dashboard_heatmap_uses_persisted_coverage_and_ordinal_grade` | LREQ-RPT-020 | the three numeric D/R/Q coverage cells; the C column is `breadth_completeness_status` and is never labelled "coverage"; the ordinal grade scale; reference lines equal `COVERAGE_REFERENCE_THRESHOLDS` (§12 R1) |

Update `tests/test_report.py::test_public_report_functions_have_hints_and_docstrings`
(LREQ-NFR-040): add `report.render_run_dashboard_html` to its `public_functions` tuple. Node ID
and traceability key unchanged.

### 7.2 `tests/test_cli.py` — replaced/added nodes

| Node ID | Marker | Asserts |
|---|---|---|
| `tests/test_cli.py::test_dashboard_without_run_id_renders_latest_run` (**replaces** `test_dashboard_requires_run_id`) | LREQ-CLI-020 | with a repository holding two runs of different `run_started_at_utc` and `run_id=None`, the renderer is called once with the later run id |
| `tests/test_cli.py::test_dashboard_without_run_id_on_empty_database_is_nonzero` | LREQ-CLI-020 | empty `runs` → `EXIT_RUNTIME_ERROR`, no renderer call, non-empty stderr |
| `tests/test_cli.py::test_parser_accepts_dashboard_without_run_id` (**replaces** `test_parser_rejects_dashboard_without_run_id`) | LREQ-CLI-020 | `cli.parse_options(["dashboard"])` returns with `run_id is None` (no `SystemExit`) |

`test_dashboard_reads_database_only_and_never_constructs_a_transport`,
`test_dashboard_missing_run_is_nonzero`, `test_dashboard_selects_completed_and_failed_runs`, and
`test_parser_exposes_two_subcommands_with_none_defaults` keep their node IDs; verify the last one
still holds (`--run-id` present, `--latest` absent) and update only its docstring if needed.

### 7.3 `tests/test_database.py` — new nodes

| Node ID | Marker | Asserts |
|---|---|---|
| `tests/test_database.py::test_get_latest_run_id_selects_greatest_started_at` | LREQ-CLI-020 | three runs with distinct `run_started_at_utc` → the greatest; round-trips via fixed aware-UTC literals |
| `tests/test_database.py::test_get_latest_run_id_tie_break_is_deterministic` | LREQ-CLI-020 | two runs with equal timestamps → the lexicographically smallest `run_id` (Q3 proposal), stable across two calls |
| `tests/test_database.py::test_get_latest_run_id_none_when_no_runs` | LREQ-CLI-020 | empty `runs` → `None` |

### 7.4 `tests/traceability.json`

- **Remove** the two replaced keys
  `tests/test_cli.py::test_dashboard_requires_run_id` and
  `tests/test_cli.py::test_parser_rejects_dashboard_without_run_id` (they would otherwise become
  orphan nodes).
- **Add** every new node ID from §7.1–§7.3 with its marker list.
- Keep every `LREQ-CLI-020`, `LREQ-RPT-010/020/030/040/050`, `LREQ-SEN-020`, `LREQ-NFR-040` key
  non-empty.
- Run `python -m niche_scout.tools.validate_traceability` — exit 0 required.

---

## 8. Golden vectors and fixtures

### 8.1 Fixture additions

`tests/fixtures/report_fixtures.py`:
- Extend `ranking_sensitivity_json(...)` with an optional
  `policy_ranks: Mapping[str, Mapping[str, int]] | None = None` argument that, when supplied,
  emits `rank_balanced`/`rank_demand_heavy`/`rank_competition_heavy` per category (today it emits
  only `rank_balanced`, `report_fixtures.py:179-181`). The existing `balanced_ranks` path stays
  byte-compatible so old vectors are unchanged.
- Add a `dashboard_rows()` helper returning three rankable rows + one refused row with fixed
  components (all four present for the first) for the chart tests, and export it.

`tests/fixtures/cli_fixtures.py`:
- Add a `multi_run_dashboard_repository(path)` helper seeding two completed runs with distinct
  fixed `run_started_at_utc` values (reuse `report_fixtures`), for §7.2.

### 8.2 Hand-computed component contributions (all four available)

Components `D=0.70, C=0.55, R=0.60, Q=0.65`; weights `0.35, 0.30, 0.20, 0.15`
(`models.W_*`). With all available, `sum(W)=1.0`:

| Component | W·x | contribution |
|---|---:|---:|
| D | 0.2450 | 0.2450000000 |
| C | 0.1650 | 0.1650000000 |
| R | 0.1200 | 0.1200000000 |
| Q | 0.0975 | 0.0975000000 |
| **stack height** | | **0.6275000000** |

Total equals the persisted composite `0.63` (fixture) — assert within `1e-9`.

Two-component vector (`D`/`C` only, `R`/`Q` missing): available weight sum `0.65`; contributions
`0.35·0.70/0.65 = 0.3769230769…`, `0.30·0.55/0.65 = 0.2538461538…`, sum `0.6307692307…`.

### 8.3 Other pinned values

- `EVIDENCE_GRADE_ORDER == ("insufficient", "weak", "moderate", "strong")`.
- `COVERAGE_REFERENCE_THRESHOLDS` values `0.50` and `0.80` (SRS §14).
- Latest-run vector: `run_started_at_utc` values `2025-01-02T03:04:05Z`, `2025-01-02T03:04:06Z`,
  `2024-12-31T23:59:59Z` → the `…:06Z` run id.
- Tie vector: both `2025-01-02T03:04:05Z`; run ids `"b-run"`, `"a-run"` → `"a-run"` (Q3).

---

## 9. Gate checklist / DoD

- [ ] `python -m pytest -q` — the whole suite passes, with the §7 nodes added and the two
      replaced CLI nodes removed/renamed.
- [ ] `python -m niche_scout.tools.validate_traceability` — exit 0; every new node has a marker
      and a `tests/traceability.json` entry; no orphan entry for the two removed nodes.
- [ ] `python -m niche_scout.tools.check_import_boundaries` — exit 0 (`metrics.py`/`scoring.py`
      untouched and pure).
- [ ] `python -m niche_scout.tools.check_scope_prohibitions` — exit 0 (no retired token; the
      dashboard adds no historical/trend/resume feature).
- [ ] Formatter and linter per `pyproject.toml` (`ruff format`, `ruff check`) run clean.
- [ ] `plotly` is a declared dependency and importable in the test environment (D-1).
- [ ] `report.py` still imports none of `metrics`, `scoring`, `collector*`, `config`, `pipeline`,
      `cli`, and reads no clock (D-4; the existing AST test stays green).
- [ ] `render_run_dashboard_html(view) == render_run_dashboard_html(view)` byte-identical and
      self-contained (no `<script src`, no `<link`, no CDN) (D-2).
- [ ] `dashboard` with no `--run-id` renders the most recent run; empty DB is non-zero and calls
      no renderer; a given run id is unaffected (D-3).
- [ ] Refused categories never on the scored axis; evidence grade ordinal; `n/a` ≠ `0`; no
      confidence interval/error bars; coverage and sample fraction distinctly labelled.
- [ ] `HEURISTIC_STATEMENT` present (LREQ-RPT-050).
- [ ] No file outside §1.4 changed; the four interface files in §2 amended by the lead.
- [ ] Run log `Documents/runs/chunk-30.md` updated with the gate result.

---

## 10. Questions raised before freeze (all resolved — see §12)

**Q1 (BLOCKING) — competition ("C") in the category × status heatmap.**
The frozen data model persists only three numeric coverages:
`demand_stratum_eligibility_coverage`, `recent_supply_stratum_eligibility_coverage`,
`quality_stratum_eligibility_coverage` (`src/niche_scout/database.py:201-203`;
`src/niche_scout/models.py:494-496`). There is **no competition coverage**; C's persisted
facts are `component_c` (a normalized score), `breadth_source`, and
`breadth_completeness_status` (`complete` / `incomplete_estimate`). The request's
"D/C/R/Q coverage" therefore cannot be satisfied for C as a numeric coverage, and the §14
coverage thresholds (0.50 / 0.80) cannot apply to it.
Options:
- (a) *(recommended)* Heatmap component columns = D/R/Q stratum eligibility coverage (numeric,
  with the reference lines) **plus** a separate C column showing `breadth_completeness_status`
  (categorical status) and/or `component_c` availability — never labelled "coverage".
- (b) Show only D/R/Q coverage in the coverage block; omit C from it (C remains visible in the
  primary table / component charts).
- (c) Treat `component_c` as "C coverage" — rejected: a normalized component is not a coverage
  and this would misstate the SRS distinction (SRS §14; §16 item 11).
Consequence: (a)/(b) require only §4.2's already-listed read-model fields and pin the heatmap
test in §7.1; (c) violates the missing/coverage semantics and is not authorized.
**This question blocks the freeze and the heatmap test's exact assertions.**

**Q2 — repoint `render_dashboard_html` vs add a separate repository-taking entry point.**
- (a) *(recommended, least churn)* Keep the frozen signature of
  `render_dashboard_html(repository, run_id)` and repoint its body to the new
  `render_run_dashboard_html(view)`; the CLI default seam is unchanged.
- (b) Leave `render_dashboard_html` as the Chunk 11 table dashboard and add a second
  repository-taking convenience for the CLI; this keeps two dashboard entry points.
D-2's wording ("the new function is a new contract surface; the frozen … `render_dashboard_html`
[is] not weakened") supports (a): the **function** is added and the frozen name keeps its
signature/self-containment. Confirm (a) or authorize (b).

**Q3 — latest-run tie-break and the empty-database exit code.**
- Tie-break (SRS silent): (a) smallest `run_id` (proposed); (b) largest `run_id`; (c) reject a
  tie. Any is deterministic; the plan implements (a).
- Empty database with no `--run-id`: (a) `EXIT_RUNTIME_ERROR` (proposed; consistent with the
  existing missing-run mapping); (b) `EXIT_USAGE_ERROR`. Confirm.

**Q4 — output channel for the dashboard.**
Ruling 6 (print HTML to stdout, no file write, no browser) is frozen and D-3 amends only
Ruling 3, so this plan keeps stdout. Confirm that a no-argument `niche-scout dashboard` printing
a large inline-JS document to stdout is still the intended UX (an optional `--out PATH` write
would be a new Ruling and is not proposed here).

**Q5 — explicit zero on the log-scale population axis.**
`discovered_population_count == 0` is a measured zero; `None` is unavailable. Proposed: zero
rows are excluded from the log trace and drawn as a distinct explicit-zero marker labelled `0`;
`None` rows are absent plus an `n/a` annotation. Confirm, or specify an alternative that keeps
`0` and `None` distinct.

**Q6 — `plotly` version constraint and secondary-chart scope.**
- Proposed constraint `plotly>=6,<7` (no version is named by the SRS; D-1 only says "add
  plotly"). Confirm the range or name another.
- The three supporting charts are described as "optional" in the request; this plan treats them
  as in scope but secondary to the four primary charts. Confirm they ship in this chunk (if not,
  drop their nodes/assertions from §5/§7).

---

## 11. Status

Plan is **FROZEN** as of 2026-09-30 by the lead after the Q1–Q6 rulings in §12. No interface
file, SRS, dependency-map, `AGENTS.md`, or `.kilo/` file was edited by the planner. The lead
applies the §2 interface deltas in the same change as the implementation.

---

## 12. Lead rulings (freeze, 2026-09-30)

All six questions are resolved. Authority: the operator instruction of 2026-09-30 ("dispatch a
sub-agent to find the best answers to the questions, also make sure the plan is using the latest
versions"), the independent read-only research dispatch (board id
`board_272be634-fbdd-4318-8003-e29a99a17284`; evidence cited below), and the SRS-consistency
constraint that no ruling may fabricate a quantity the SRS does not define (AGENTS.md Hard rules
1–2). PyPI facts were read directly (`python -c` querying `https://pypi.org/pypi/<pkg>/json`).

- **R1 (Q1) — heatmap columns.** Adopt option (a). Numeric coverage columns are exactly **D/R/Q**
  (`demand`/`recent_supply`/`quality_stratum_eligibility_coverage`; `database.py:201-203`) and
  carry the 0.50/0.80 reference lines; the map also has ordinal `evidence_grade`,
  `rankability_status`, and a separate **C column** showing `breadth_completeness_status` /
  `breadth_source`, explicitly **never labelled "coverage"**. Basis: the frozen model defines no
  competition coverage; `LREQ-SCR-020` (SRS:973-979) gives C no coverage-shrinkage term, and only
  `LREQ-MET-060/080/090` define eligibility coverage; `LREQ-MET-070` gives C only breadth status.
  Option (c) (`component_c` as coverage) is rejected as a missing-not-zero / coverage-vs-score
  conflation. This is an SRS-silent **presentation** choice resolved under the operator's explicit
  delegation, not the invention of a competing metric.
- **R2 (Q2) — repoint.** Adopt option (a): repoint `render_dashboard_html`'s body to
  `render_run_dashboard_html(view)` while keeping the exact `{repository, run_id}` signature
  (`report.py:1063-1070`; `tests/test_report.py:1089` pins only the signature). No second entry
  point. Requires the §2 `chunk-11.md` delta.
- **R3 (Q3) — latest-run selection.** Tie-break = lexicographically smallest `run_id`; an empty
  `runs` table with no `--run-id` → `EXIT_RUNTIME_ERROR` (`cli.py:48-55`) with no renderer call,
  consistent with the existing missing-run mapping (`cli.py:512-515`). The SRS is silent
  (`SRS-lean-v2.md:1199-1200`); both choices are deterministic.
- **R4 (Q4) — output channel.** Retain Ruling 6: print to stdout, no file write, no browser
  launch (D-3 amends only Ruling 3). An optional `--out PATH` is explicitly **out of this chunk**.
- **R5 (Q5) — explicit zero.** `discovered_population_count == 0` is a legal measured zero
  (SRS:819-820; `models.py:480`; `database.py:187`) and renders as a distinct explicit-zero marker
  labelled `0`, off the log axis; `None` (the failed-preflight fallback, `report.py:495`) is absent
  plus an `n/a` annotation. The `0` and `n/a` markers/labels are distinct strings.
- **R6 (Q6) — dependency and secondary charts.** Pin **`plotly>=7.1,<8`**; PyPI latest is
  `plotly` **7.1.0** (2026-09-15; `requires_python>=3.8`, satisfied by the project's `>=3.11`).
  Convention is a PEP 508 range, not an exact pin (`pyproject.toml:13`). The three supporting
  charts (population lollipop, component dumbbell, score-vs-quality scatter) **ship** in this
  chunk, secondary to the four primary charts. Observed latest for context — pytest 9.1.1,
  ruff 0.16.9, setuptools 84.0.0; the existing `pytest>=8` / `setuptools>=68` lower bounds are
  left unchanged (out of scope).
- **R7 (deliverable found in research).** The frozen `interfaces/chunk-11.md:72` and `:197`
  "rank comes from `ranked_categories`" text is stale and contradicts the implemented
  `rank_balanced` contract (`report.py:550-579`, `tests/test_report.py:474`, `LREQ-SEN-020`). The
  §2 interface delta corrects both lines in the same change.

### 12.1 Post-freeze implementation risk (unchanged)

Plotly's `to_html` byte-determinism for a fixed `div_id` remains **unverified in this repo**
(plotly is not yet installed). §5.2 is unchanged: the implementer must render twice and compare,
and STOP-and-report if any non-deterministic byte appears (D-2 requires byte-identical output).