# Chunk 31 — Dash 4.4.1 + Plotly dashboard redesign (plan)

Status: FROZEN — 2026-10-01. Q1–Q8 resolved by the lead; see §12 Rulings. Every section is
implementation-ready.

New remediation/feature chunk, not in `Documents/requirements-dependency-map.md` §3/§4
(chunk-14 / chunk-30 precedent: registration = plan + run log + branch). Do not edit the
dependency map, the SRS, `AGENTS.md`, or `.kilo/`.

Branch: `chunk-31`, base `main` @ `e869f69` (`chunk-30: gate PASSED`).

Authority: `Documents/runs/chunk-31.md` (this chunk's log) and the frozen contracts it cites.
The operator-authorized decisions **D-1..D-5** in that log are fixed and are **not re-opened**
here; the lead rulings R1–R8 in §12 resolve the questions this plan raised.

This plan **removes** the Chunk-30 dashboard surface (`render_dashboard_html`,
`render_run_dashboard_html`, the dashboards' figure set) and replaces it with a Dash app. The
Chunk-30 **read model** (`RunReportView`, `CategoryReportRow`, `RunSensitivitySummary`),
`render_run_report_html`, `render_run_report_text`, and `write_run_report` are **retained
unchanged**: `niche-scout run --report PATH` still writes a static **report file** (not a
dashboard). Only the pure figure builders reused by the app are kept.

Predecessors merged and frozen: Chunk 0/2 (`models`, `database`, read API incl.
`get_latest_run_id`), Chunk 11 (report renderer/read-only dashboard), Chunk 12 (CLI), Chunk 30
(dark-mode Plotly dashboard). This chunk **deliberately amends** the frozen self-containment
guarantee `interfaces/chunk-11.md` §1/§5/§10 and Chunk 12 Ruling 6
(`interfaces/chunk-12.md` §9). The lead applies the interface deltas in §6; the planner does
not edit interface files.

SRS authority: `Documents/SRS-lean-v2.md` §10 (`LREQ-RPT-010`..`LREQ-RPT-050` lines
1155–1189; `LREQ-CLI-020` lines 1199–1200), §12 (module conventions), §14 (constants),
§15/§16 (out-of-scope, limitations), Appendix C (warning vocabulary). `AGENTS.md` Hard rules
1–4 and "Out of scope — do not add". Every countable claim is labelled **(read)**,
**(counted)** or **(unverified)** per project-rules "Plan review and audit"; the walk is §13.

---

## 1. Scope, non-goals, LREQ roles

### 1.1 Scope (in)

1. **Dependency (D-2, R1).** Add `dash==4.4.1` to `pyproject.toml` `[project].dependencies`
   next to the existing `plotly>=7.1,<8`. Verified: PyPI latest `dash` = `4.4.1`,
   `requires_python >= 3.9` (§12 R1, §13).
2. **Dash application (D-2, D-4, R2).** Replace the Chunk-30 dashboard with a local,
   read-only Plotly **Dash application**: one browser page for exactly one persisted run,
   launched by the existing `niche-scout dashboard` command. This is the **only** dashboard;
   both chunk-30 dashboard renderers are removed (R2).
3. **Redesigned layout (D-3, D-5, R4/R5).**
   - KEEP the ranked composite-score bar with the refusal gap; the weighted contribution
     stack (`W_D·D`, `W_C·C`, `W_R·R`, `W_Q·Q`); the policy rank bump chart + KPI tiles
     (`top_3_stability`, `top_5_stability`, `maximum_rank_displacement`); the population/sample
     lollipop (log scale, sample marker); and the score-vs-quality scatter as a **secondary**
     diagnostic.
   - DROP the component "dumbbell" entirely (redundant; 18 overlapping 4-point series).
   - **OMIT the D/R/Q coverage heatmap entirely (R4).** Do not redesign it. Coverage stays
     exact in the primary table; evidence grade is encoded as an **ordinal colour on the
     ranked score bar**, with exact values in the hover and in the table.
   - Primary **table**: show **all 30** `LREQ-RPT-020` labels (`_PRIMARY_COLUMNS` **(counted:
     30 rows, `report.py:226–260`)**) by default; the table is compact and horizontally
     scrollable (R5). No column picker is required.
   - Per-category **detail** (`LREQ-RPT-030`): the shared formula/"how to read" list is hoisted
     to **one** panel; per-category formulas/metric inputs/strata/warnings/timestamps/
     observed-vs-inferred render for the **selected category only**, driven by Dash
     callbacks.
4. **Chart prose and human vocabulary (D-3, D-5, R5).** Every chart carries a one-line
   plain-language "what it depicts" caption and correct, human-readable legends/axis labels.
   Tooltips and the shared footnote are written in plain human language ("what this means /
   what to watch for"), never raw field-name jargon or bare acronyms; §5.7 defines the
   label/tooltip vocabulary (D = "Demand", C = "Competition", R = "Recent supply",
   Q = "Quality", each with a one-line plain explanation). Interaction-only context is a
   hover/tooltip; anything else becomes the **single** shared footnote.
5. **Offline asset serving (R6).** The app relies on Dash's **default local asset serving**
   (no CDN); the implementer verifies whether `serve_locally` still exists in the installed
   4.4.1 and, if it does not, relies on the default.
6. **Testable seam (R2, R3).** A pure `build_dashboard_layout(view) -> html.Div` and
   `build_dashboard_app(view) -> dash.Dash` (testable without serving) are separated from
   `run_dashboard(app, ...)`, which calls `app.run` (§4).

### 1.2 Non-goals (explicitly NOT in this chunk)

- No historical trend, cross-run comparison, run-over-run view, or multi-run overlay
  (SRS §10 line 1187). The app renders exactly one selected run.
- No multi-user, hosted, or cloud mode; no authentication; binds loopback (`127.0.0.1`) only.
- No confidence intervals, error bars, or statistical-precision claim anywhere (AGENTS.md
  out-of-scope; Appendix C vocabulary).
- No configurable weights; `W_D/W_C/W_R/W_Q` and the sensitivity policies stay from `models`
  (SRS §14).
- No schema change, no pipeline change, no `metrics.py`/`scoring.py` change.
- No recomputation of any metric, component, score, evidence grade, rankability, or
  sensitivity value; the app renders persisted values verbatim (Chunk 11 §1, §7).
- No clock read anywhere in `report.py`; `scoring_cutoff_utc` stays an explicit persisted value.
  Dash's own runtime may read the clock for HTTP/server internals; **this project's code SHALL
  NOT**, and no displayed value is derived from a clock.
- No Coveo/GraphQL transport and no discovery/enrichment from the dashboard
  (`LREQ-CLI-020`); SQLite reads only.
- No scheduling, resume, checkpoint, or favourite-count (AGENTS.md out-of-scope;
  `check_scope_prohibitions` tokens unchanged). **(read:** `RETIRED_FEATURES` contains the
  `--resume`/`--checkpoint` tokens and the SRS-deferral set; a Dash callback id or the word
  "refresh" is not one of them — R7 confirms.)**
- No change to `render_run_report_html`/`render_run_report_text`/`write_run_report` output; the
  `run` report path is untouched (R2). `--report`/`--report-format` and `write_run_report`
  remain the only file-output surface.
- **No `--out`**, no file write, no static-HTML export from the dashboard (R2, R7): the app is
  served.

### 1.3 LREQ roles

| Role | LREQs |
|---|---|
| Primary | `LREQ-RPT-010` (one-command local read-only dashboard), `LREQ-RPT-020` (primary table / read model), `LREQ-CLI-020` (dashboard reads the database only) |
| Supporting contract | `LREQ-RPT-030` (category details via progressive disclosure), `LREQ-RPT-040` (non-rankable stay visible and off the scored axis), `LREQ-RPT-050` (heuristic statement present), `LREQ-SEN-020` (3-policy ranks and stability outputs rendered from persisted values) |
| Integration completion | `LREQ-NFR-040` (public builder type hints/docstrings), `LREQ-ARCH-010`/`LREQ-ARCH-020` (purity: `report.py` imports no forbidden module and reads no clock; `metrics`/`scoring` untouched) |

`LREQ-RPT-010` is the LREQ whose frozen guarantee (self-contained HTML, one command) this chunk
amends: the "one command" half stays; the "self-contained HTML document" half becomes "served
local app" (R2, §6.1). The **static report** keeps its self-contained-HTML guarantee.

---

## 2. Fixed design/behaviour inputs (from run log D-1..D-5)

Quoted as the operative authority; the plan implements them and does not re-open them.

- **D-2.** Dash authorized; amends `interfaces/chunk-11.md` §1/§5/§10 and
  `interfaces/chunk-12.md` §9 Ruling 6. Read-only: SQLite reads only; no Coveo/GraphQL; single
  run; local. New dependency `dash` 4.4.1 + existing `plotly`. No clock read; render persisted
  values verbatim.
- **D-3.** Minimize on-page prose; interaction context in tooltips/hover; non-sensible inline
  context as **one** shared footnote; SRS-mandated content stays reachable somewhere.
- **D-4.** New chunk 31; chunk 30 is not edited in place.
- **D-5.** Every chart carries a one-line plain-language explanation and correct,
  human-readable legends/axis labels.

Chunk-30 invariants that carry over unchanged: `HEURISTIC_STATEMENT` verbatim
(`LREQ-RPT-050`); non-rankable categories visible (`LREQ-RPT-040`); null is a distinct `n/a`
and never `0`; no confidence intervals or error bars; coverage and `sample_fraction` distinctly
labelled; every threshold/weight sourced from `models`/SRS §14, never hard-coded.

---

## 3. Determinism contract (normative)

For a fixed `RunReportView`, the app's figures and its initial layout are deterministic:

- Every figure is produced by a **pure** builder `def _x_figure(view) -> go.Figure` (the
  retained chunk-30 builders, with the dumbbell and heatmap builders removed — R2/R4) with
  explicit series order derived from `view.categories` order or a fixed constant tuple; **no
  set/dict iteration determines an order**; no RNG; no clock.
- The Dash **layout tree** is assembled by a pure `build_dashboard_layout(view) -> html.Div`
  with fixed component `id`s from the frozen tuple `DASHBOARD_COMPONENT_IDS` (§5.1). Two calls
  with the same view produce equal component trees (compared after `to_plotly_json()`
  normalization, §8.1 test 1).
- Callbacks are **selection-driven only**: they receive an already-built figure or a persisted
  field and return a re-rendered figure/detail. No callback reads the clock, queries the
  network, or recomputes a metric.
- The app is constructed from a `RunReportView`, never from a repository handle, so no callback
  can re-enter `load_run_report_view` (which would be a second DB read). The read happens once
  in `dashboard_command` before `build_dashboard_app(view)` (R3).

---

## 4. The testable seam (R2, R3)

Two new public functions in `report.py` plus one CLI-side runner:

```python
def build_dashboard_layout(view: RunReportView) -> "html.Div":
    """Return the deterministic initial layout tree for ``view`` (no server, no I/O).

    Pure: no clock, no network, no database. Two calls with the same ``view`` build
    equal trees. Every chart's figure is produced by a pure ``_x_figure(view)``
    builder; every component carries a fixed ``id`` from ``DASHBOARD_COMPONENT_IDS``.
    ``HEURISTIC_STATEMENT`` appears verbatim exactly once; the primary table carries
    every ``_PRIMARY_COLUMNS`` label; the selected-category detail covers every
    ``LREQ-RPT-030`` item.
    """

def build_dashboard_app(view: RunReportView) -> "dash.Dash":
    """Return a ``dash.Dash`` whose layout is ``build_dashboard_layout(view)``.

    Pure construction (no ``app.run``, no network, no clock read by this module, no
    repository access). The returned object is safe to construct in a test: assert on
    ``app.layout`` and invoke a callback function directly. Dash's default local asset
    serving is relied on (no CDN); see §5.6.
    """
```

CLI side (`cli.py`):

```python
def run_dashboard(
    app: "dash.Dash", *,
    host: str = "127.0.0.1",
    port: int = _DEFAULT_DASHBOARD_PORT,
    stdout: TextIO = sys.stdout,
) -> int:
    """Serve ``app`` on loopback, print the local URL to ``stdout``, and block.

    Does NOT open a browser. Returns ``EXIT_OK`` on ``KeyboardInterrupt`` (normal
    stop) and ``EXIT_RUNTIME_ERROR`` if the bind fails (R7). Production only; tests
    monkeypatch or replace this function, never call it.
    """
```

`dashboard_command` keeps its existing parameter names and `report_renderer` seam, whose
**default and return type change**: it becomes an **app factory**
`Callable[[RunReportView], dash.Dash]` defaulting to `report.build_dashboard_app` (R2/R3/Q3).
The read happens once (`view = load_run_report_view(repository, run_id)`), then
`app = report_renderer(view)`, then `run_dashboard(app, stdout=stdout)`. The frozen-contract
delta is §6.2.

---

## 5. Dash app design

### 5.1 Component ids (frozen constant)

```python
DASHBOARD_COMPONENT_IDS: tuple[tuple[str, str], ...] = (
    ("chart-score-bar", "score-bar"),
    ("chart-contribution-stack", "contribution-stack"),
    ("chart-policy-bump", "policy-bump"),
    ("chart-population-lollipop", "population-lollipop"),
    ("chart-score-quality-scatter", "score-quality-scatter"),
    ("kpi-strip", "kpi-strip"),
    ("primary-table", "primary-table"),
    ("detail-panel", "detail-panel"),
    ("category-selector", "category-selector"),
    ("footnote", "footnote"),
)
```

Every Plotly figure keeps its existing fixed `div_id` from `DASHBOARD_CHART_IDS`
(`report.py:80–89`), so chart-level determinism and figure assertions still hold.
`DASHBOARD_CHART_IDS` is **amended**: the `component_dumbbell` and `status_heatmap` pairs are
**removed** (R2/R4); the remaining five pairs stay (score_bar, contribution_stack, policy_bump,
population_lollipop, score_quality_scatter).

### 5.2 Layout (mostly graphs, minimal prose)

Top-to-bottom, one page:

1. **Header** — run id, run status, `run_started_at_utc`, `scoring_cutoff_utc`,
   `identity_preflight_status`; the `HEURISTIC_STATEMENT` in a banner element (verbatim,
   present in the layout exactly once for `LREQ-RPT-050`).
2. **KPI tiles** — the three `_kpi_tiles(view)` values; `None` renders `n/a` (never `0`); R8.
3. **Chart grid** — score bar with refusal gap; contribution stack; policy bump;
   population/sample lollipop; score-vs-quality scatter (secondary). Each chart is a card with
   a one-line **"what it depicts" caption** (D-5) under the title.
4. **Primary table** — Dash `dash_table.DataTable` (or an html table), **all 30
   `_PRIMARY_COLUMNS` labels visible by default**, compact and horizontally scrollable (R5).
   No column picker. Sortable; non-rankable rows visible.
5. **Selected-category detail panel** — driven by `category-selector`; renders the
   `LREQ-RPT-030` items for one category (formulas/concise explanations, metric inputs, sample
   strata, warnings, timestamps, observed-vs-inferred), reusing the existing pure helpers
   `_rankability_note`/`_raw_metric_entries`/`_FORMULA_EXPLANATIONS`/`_render_strata_html`
   semantics. Non-rankable rows are selectable (they are simply not on
   the scored axis).
6. **One shared footnote** — coverage-vs-`sample_fraction` distinction; the `n/a`-vs-`0`
   convention; the provisional / no-rankable-candidate notice for 8–20 category runs (R8,
   once, never per category); and the interpretation caveats that are not UX-sensible inline
   (D-3). Rendered **once**.

### 5.3 Charts (each with guardrails)

- **Score bar** (horizontal): scored rows in view order, one empty gap band, then refused rows
  as `n/a` annotations and **no bar** (they never sit on the scored axis); an explicit `0.0`
  renders a zero-length bar labelled `0`. **Evidence grade is encoded as an ordinal colour on
  this bar** (R4) with the exact grade text in the hover and the table; the colour scale is
  ordinal via `EVIDENCE_GRADE_ORDER`/`_evidence_grade_position`. Caption: "Composite score by
  rank; refused categories are shown at the bottom and are not on the score axis."
- **Contribution stack**: one stacked bar per scored row; segments D/C/R/Q in fixed order; a
  missing component contributes **no segment**; stack height = persisted composite. Legend
  uses the plain names (§5.7).
- **Policy bump**: three x positions (`balanced`, `demand_heavy`, `competition_heavy`); a null
  rank is a **gap**, never `0`; y-axis title "rank (1 = best)".
- **Population lollipop**: log x-axis; population marker + sample-size marker; a measured `0`
  is a distinct explicit-zero marker labelled `0` off the log axis; `None` is absent + `n/a`.
- **Score-vs-quality scatter** (secondary): marker size from `sample_fraction`; `None` uses the
  documented fixed fallback size and is labelled `n/a`, never `0`.

Common guardrails: no error-bar trace; refused rows never share the scored axis; `n/a`
visually distinct from `0`; thresholds from `models`/SRS §14; `HEURISTIC_STATEMENT` verbatim;
coverage and `sample_fraction` distinctly labelled.

### 5.4 Coverage heatmap — omitted (R4)

The D/R/Q coverage heatmap is **omitted entirely** (do not redesign it). Justification: the
`out.html` artifact shows it degenerate (nearly all coverage cells `1.0`; it also mixed a
categorical C status into a numeric domain — §13). Coverage stays exact in the primary table
(the three numeric coverage columns), and evidence grade moves to an ordinal colour on the
ranked score bar with exact values in hover/table. The `status_heatmap`/`evidence-support`
chart id, figure builder, and tests are removed.

### 5.5 Callbacks

| Callback | Input | Output | Reads |
|---|---|---|---|
| category-selector | selected category | detail panel children | the already-loaded `view` row |
| (optional) table row click | selected row | category-selector value | none |

All callbacks are pure functions over the loaded `view` (or a prebuilt lookup
`{category: row}`); no I/O, no clock, no recomputation. Each callback is unit-testable by
calling it directly.

### 5.6 Local (offline) asset serving (R6)

`build_dashboard_app` constructs `dash.Dash(__name__)`. This plan **relies on Dash's default
local asset serving (no CDN)**. If the installed 4.4.1 still exposes the `serve_locally`
parameter, the implementer sets `serve_locally=True` explicitly; if it does not, the default
local serving is what the plan relies on. This dependency is verified on the installed package
at implementation time (the exact keyword is otherwise **unverified** here — §13). "How you
know" the app is offline: (i) the resolved local-serving setting; (ii) a test asserting no
scheme-bearing external URL in this project's own asset/config references (§8.1); (iii) a
manual smoke run by the lead with the network disconnected.

### 5.7 Human label / tooltip vocabulary (D-5, R5)

Plain-language names and one-line explanations; tooltips use these instead of raw field names
or bare acronyms.

| Field / token | Human label | One-line plain explanation |
|---|---|---|
| D (`component_d`) | **Demand** | How much demand the category shows, from the discovered page-view index — a trailing-7-day view count. |
| C (`component_c`) | **Competition** | How crowded the category is by verified catalog breadth; incomplete breadth makes it unavailable. |
| R (`component_r`) | **Recent supply** | How much recent supply and how new the assets are. |
| Q (`component_q`) | **Quality** | How highly rated the assets are. |
| composite score | **Composite score (within-run heuristic)** | A deterministic blend of Demand/Competition/Recent supply/Quality; not a sales or revenue forecast. |
| stratum eligibility coverage | **Data coverage** | The share of the discovered population in strata with enough usable observations; **not** the same as sample fraction. |
| `sample_fraction` | **Sample fraction** | The share of the discovered population that was sampled; **not** the same as data coverage. |
| evidence grade | **Evidence strength** | An ordinal label (insufficient → weak → moderate → strong); **not** statistical confidence. |
| `top_3_stability` / `top_5_stability` | **Top-3 / Top-5 rank stability** | How stable the top ranks are across scoring policies; `n/a` when there are too few rankable candidates. |
| `maximum_rank_displacement` | **Max rank shift across policies** | The largest rank movement of any category between scoring policies. |
| rankability status | **Rankable?** | Whether the category has enough evidence to be ranked; non-rankable categories stay visible. |

Throwaway phrasing guidance (D-3): every chart caption is one sentence of the form "This shows
…; read it as …"; every tooltip says what the number means and what to watch for, in words.

---

## 6. Interface doc deltas (explicit list for the lead; the planner edits none)

Apply all of these consistently with the code; they are the frozen-contract updates.

1. **`Documents/interfaces/chunk-11.md` — new §11 "Chunk 31 revision — Dash app (2026-10-01)"**,
   superseding the affected lines (§1/§2/§5/§7/§10):
   - **§1 boundary rule** — `report.py` may import `dash` (and `plotly`); all other boundary
     rules are unchanged (no `metrics`/`scoring`/`collector*`/`config`/`pipeline`/`cli`, no
     clock). The self-containment guarantee is **amended**: the **dashboard** is a **served
     local app**, not a self-contained HTML document. `render_run_report_html` /
     `render_run_report_text` / `write_run_report` **keep** the self-contained-HTML guarantee
     and the `run --report` file behaviour unchanged (R2).
   - **§2 constants** — add `DASHBOARD_COMPONENT_IDS`; **remove** the `component_dumbbell` and
     `status_heatmap` pairs from `DASHBOARD_CHART_IDS`.
   - **§5 functions** — **remove** `render_dashboard_html` and `render_run_dashboard_html`;
     add `build_dashboard_layout(view) -> html.Div` and `build_dashboard_app(view) ->
     dash.Dash`; add `run_dashboard` is a CLI function (§6.2, not in this file).
   - **§7 display rules** — add: every chart carries a one-line plain-language caption and
     correct legends/axis labels (D-5); per-category `LREQ-RPT-030` detail is
     progressive-disclosure for the selected category with the shared formula list hoisted once
     (D-3); the primary table shows **all** `LREQ-RPT-020` labels by default (R5); the coverage
     heatmap is removed (R4) and coverage stays exact in the table; the human label vocabulary
     (§5.7) is normative for UI text.
2. **`Documents/interfaces/chunk-12.md` — new §10 "Chunk 31 revision — dashboard serves a local
   app (2026-10-01)"**, **amending Ruling 6**:
   - **§5 `dashboard_command`** — retains its parameter names; the `report_renderer` seam becomes
     an **app factory** `Callable[[RunReportView], dash.Dash]` defaulting to
     `report.build_dashboard_app`; the command loads the view once
     (`load_run_report_view`), builds the app, then calls `run_dashboard(app, stdout=stdout)`
     which **binds `127.0.0.1` and blocks**, printing the local URL to `stdout`. No file write;
     no browser launch. Exit codes (R7): `EXIT_OK` on `KeyboardInterrupt` after a successful
     bind; `EXIT_RUNTIME_ERROR` for a missing/unknown run, an empty `runs` table, an open
     failure, or a bind failure. Add `run_dashboard(app, *, host="127.0.0.1",
     port=_DEFAULT_DASHBOARD_PORT, stdout=sys.stdout) -> int`.
   - **§6 behavioral contract** — the Ruling 6 wording "print to `stdout`, no file write, no
     browser launch" is superseded: the command binds loopback, **prints the URL (not the
     HTML)** to `stdout`, performs no file write, and launches no browser.
   - **§8 open obligations** — unchanged (OI-6 stays open and unassigned).
3. **`Documents/interfaces/chunk-00.md` / `chunk-02.md`** — **no delta**: the app is view-only
   (R3); `get_latest_run_id` already exists. No repository read is added.
4. **No SRS, `AGENTS.md`, dependency-map, or `.kilo/` edit is in scope.**

---

## 7. Read model, constants, and files touched

### 7.1 Read model

**No read-model change.** `RunReportView`, `CategoryReportRow`, `RunSensitivitySummary`, and
all persisted fields the surviving charts need already exist (chunk-30). The Dash layer
consumes the same view. Any per-row projection is a **private pure helper** in `report.py`
(not a frozen type change).

### 7.2 Constants

- `DASHBOARD_COMPONENT_IDS` (new, `report.py`) — fixed Dash component ids (§5.1).
- `DASHBOARD_CHART_IDS` (amended) — remove `component_dumbbell` and `status_heatmap`; five pairs
  remain.
- `COMPONENT_WEIGHTS`, `EVIDENCE_GRADE_ORDER`, `COVERAGE_REFERENCE_THRESHOLDS` — unchanged
  (`COVERAGE_REFERENCE_THRESHOLDS` is retained for the table/legend semantics even though the
  heatmap is gone; if unused it may remain as a documented constant — implementer's call,
  no interface change).
- `HEURISTIC_STATEMENT` — unchanged, rendered verbatim.

### 7.3 Files touched (the plan's file-discipline list)

Production:
- `pyproject.toml` — `[project].dependencies` gains `dash==4.4.1` (D-2; R1).
- `src/niche_scout/report.py` — **remove** `render_dashboard_html`, `render_run_dashboard_html`,
  the dumbbell figure builder, the heatmap figure builder and its helpers; add
  `build_dashboard_layout`, `build_dashboard_app`, `DASHBOARD_COMPONENT_IDS`; amend
  `DASHBOARD_CHART_IDS`; retain the read model and the five surviving pure figure builders.
- `src/niche_scout/cli.py` — `dashboard_command` builds the app and serves it via the new
  `run_dashboard`; add `run_dashboard` and `_DEFAULT_DASHBOARD_PORT`; `build_parser` unchanged
  (no new options; no `--out`).

Interfaces (frozen; the **lead** amends them in the same change — §6):
- `Documents/interfaces/chunk-11.md`, `Documents/interfaces/chunk-12.md`.

Tests:
- `tests/test_report.py`, `tests/test_cli.py`, `tests/test_end_to_end.py`,
  `tests/fixtures/report_fixtures.py`, `tests/fixtures/cli_fixtures.py`,
  `tests/traceability.json`.

No other file is in scope. Any other file needing a change is a stop-and-flag.

---

## 8. Test plan (exact node IDs; every analytical node has `@pytest.mark.lreq(...)`)

### 8.1 `tests/test_report.py` — new nodes

| Node ID | Marker(s) | Asserts |
|---|---|---|
| `tests/test_report.py::test_build_dashboard_layout_is_deterministic_for_a_fixed_view` | LREQ-RPT-010 | two `build_dashboard_layout(view)` calls produce equal trees (normalize via `json.dumps(..., sort_keys=True)` of `to_plotly_json()`); every `DASHBOARD_COMPONENT_IDS` id present; no clock read |
| `tests/test_report.py::test_build_dashboard_app_layout_matches_the_layout_builder` | LREQ-RPT-010 | `build_dashboard_app(view).layout.to_plotly_json()` equals the `build_dashboard_layout(view)` tree; building twice is equal; no `app.run` is called |
| `tests/test_report.py::test_dashboard_layout_shows_every_primary_table_column_by_default` | LREQ-RPT-020 | all 30 `_PRIMARY_COLUMNS` labels are present in the table's default columns (not only in a picker); R5 |
| `tests/test_report.py::test_dashboard_detail_panel_covers_rpt_030_items_for_a_selected_category` | LREQ-RPT-030 | the detail panel for a selected row contains formulas/concise explanations, metric inputs, strata, warnings, timestamps, and the observed-vs-inferred lists; the shared formula list appears **once** in the whole layout |
| `tests/test_report.py::test_dashboard_layout_keeps_refused_categories_visible_and_off_the_scored_axis` | LREQ-RPT-040 | refused categories are present in the layout (table/detail) and absent from the score-bar trace values; `_refused_rows` disjoint from `_scored_rows` |
| `tests/test_report.py::test_dashboard_layout_includes_the_heuristic_statement` | LREQ-RPT-050 | `HEURISTIC_STATEMENT` appears verbatim exactly once in the layout |
| `tests/test_report.py::test_dashboard_charts_carry_explanations_and_human_labels` | LREQ-RPT-010 | each rendered chart card carries a non-empty one-line caption; each figure has a non-empty title and axis/legend labels; captions/legends use the §5.7 plain vocabulary; D-5 |
| `tests/test_report.py::test_dashboard_distinguishes_null_from_explicit_zero` | LREQ-RPT-020 | the score-bar figure trace JSON shows explicit `0.0`/`"0"` for a measured zero and the `n/a` placeholder for a `None`; the two label strings differ |
| `tests/test_report.py::test_dashboard_has_no_confidence_interval_or_error_bars` | LREQ-RPT-010 | no `error_y`/`error_x` trace key in this module's figures; no CI wording |
| `tests/test_report.py::test_dashboard_policy_bump_and_kpi_tiles` | LREQ-SEN-020, LREQ-RPT-020 | `_policy_rank_rows` matches persisted ranks; a null rank is a gap; `_kpi_tiles` renders three values with `n/a` for `None` (never `0`); R8 |
| `tests/test_report.py::test_dashboard_score_bar_encodes_ordinal_evidence_grade` | LREQ-RPT-020 | the score bar's marker colour is driven by `_evidence_grade_position` (ordinal via `EVIDENCE_GRADE_ORDER`); exact grade text present in hover/table; R4 |
| `tests/test_report.py::test_dashboard_omits_the_coverage_heatmap` | LREQ-RPT-010 | `status_heatmap` is absent from `DASHBOARD_CHART_IDS` and from the layout; no figure builder emits it; R4 |

### 8.2 `tests/test_report.py` — amended nodes

Because both dashboard renderers are removed (R2), node IDs that named them are removed or
renamed. **Removed** (their traceability keys are removed, §8.5):
`test_render_dashboard_html_is_database_read_only`,
`test_run_dashboard_html_is_self_contained_dark_mode_and_deterministic`,
`test_run_dashboard_includes_heuristic_statement_primary_table_and_details`,
`test_run_dashboard_keeps_refused_categories_off_the_scored_axis`,
`test_run_dashboard_distinguishes_null_from_explicit_zero`,
`test_run_dashboard_has_no_confidence_interval_or_error_bars`,
`test_run_dashboard_policy_bump_and_kpi_tiles`,
`test_run_dashboard_heatmap_uses_persisted_coverage_and_ordinal_grade`.
Their coverage is re-homed into the §8.1 new nodes (same or stronger assertions, now against
`build_dashboard_layout`). `test_load_run_report_view_raises_for_unknown_run` (line 1004) keeps
its ID and drops only the `report.render_dashboard_html(repository, "missing-run")` call from
its body; the `load_run_report_view`/`write_run_report` raises stay.

Amended (node ID and traceability key unchanged):
| Node ID | Change |
|---|---|
| `tests/test_report.py::test_public_report_functions_have_hints_and_docstrings` | add `report.build_dashboard_layout` and `report.build_dashboard_app` to `public_functions`; **remove** `report.render_dashboard_html` and `report.render_run_dashboard_html` from it |
| `tests/test_report.py::test_load_run_report_view_raises_for_unknown_run` | drop the `render_dashboard_html` call only; keep the read-model/write assertions |

### 8.3 `tests/test_cli.py` — amended nodes

All dashboard nodes keep their IDs and traceability keys; only the injected seam and the
"serve" step change. In each, monkeypatch/replace `cli.run_dashboard` with a recorder (returns
`EXIT_OK`) so no server binds.

| Node ID | Change |
|---|---|
| `tests/test_cli.py::test_dashboard_reads_database_only_and_never_constructs_a_transport` | keep the poisoned-transport assertions; the injected recorder now represents the **app factory** (`(view) -> object`); assert it is called once, the app's view is the resolved run, and `run_dashboard` is called once with that app; update the docstring's cross-reference from `test_render_dashboard_html_is_database_read_only` to the new `test_build_dashboard_app_layout_matches_the_layout_builder`. Node ID unchanged. |
| `tests/test_cli.py::test_dashboard_missing_run_is_nonzero` | default `report_renderer` is now the app factory; assert `EXIT_RUNTIME_ERROR`, empty `stdout`, non-empty `stderr`, and `run_dashboard` not called. Node ID unchanged. |
| `tests/test_cli.py::test_dashboard_selects_completed_and_failed_runs` | assert both runs build an app (finished run and failed-fallback run) and `run_dashboard` is called; the URL is printed. Node ID unchanged. |
| `tests/test_cli.py::test_dashboard_without_run_id_renders_latest_run` | recorder gets the later run id. Node ID unchanged. |
| `tests/test_cli.py::test_dashboard_without_run_id_on_empty_database_is_nonzero` | unchanged behaviour; assert no factory call, no `run_dashboard` call. Node ID unchanged. |
| `tests/test_cli.py::test_parser_exposes_two_subcommands_with_none_defaults` | unchanged (no new option). Node ID unchanged. |

**New node:** `tests/test_cli.py::test_dashboard_command_serves_the_built_app_without_writing_files`
(marker `LREQ-CLI-020`): with a recording factory and a recording `run_dashboard`, assert the
factory is called once with the loaded view, `run_dashboard` is called once, and no file is
written to `tmp_path`.

### 8.4 `tests/test_end_to_end.py` — amended nodes

| Node ID | Change |
|---|---|
| `tests/test_end_to_end.py::test_acceptance_rendered_report_contains_required_fields` | line 519 currently calls `report.render_dashboard_html(repository, artifacts.run_id)` (removed). Repoint to `report.render_run_report_html(view)` for the static-report assertions, and additionally build `report.build_dashboard_app(view)` and assert its layout contains the heuristic statement. Keep `LREQ-TST-080`/`LREQ-RPT-020`. Node ID unchanged. |
| `tests/test_end_to_end.py::test_acceptance_dashboard_reads_persisted_run_only` | line 749 calls `dashboard_command(..., stdout=...)`; under the new contract it binds/serves. Repoint: inject a recording app factory and monkeypatch `cli.run_dashboard` to a recorder; assert the command returns `EXIT_OK`, the app was built from the persisted run, `run_dashboard` was called, and no transport was constructed. Node ID unchanged. |
| `tests/test_end_to_end.py::test_acceptance_full_mocked_run...` (line 153) | line 153 calls `report.render_dashboard_html(same_repo, artifacts.run_id)`; repoint to `report.render_run_report_html(report.load_run_report_view(same_repo, artifacts.run_id))`. Node ID unchanged. |

### 8.5 `tests/traceability.json`

- **Remove** the eight removed `tests/test_report.py` keys (§8.2 raw list).
- **Add** every new node from §8.1 and §8.3 with its marker list.
- Keep every `LREQ-RPT-010/020/030/040/050`, `LREQ-CLI-020`, `LREQ-SEN-020`, `LREQ-NFR-040` key
  non-empty (the removed nodes' LREQs are all re-homed in the new nodes).
- Node IDs whose body changed but name stayed keep their keys **byte-identical**.
- Run `python -m niche_scout.tools.validate_traceability` — exit 0 required. (Validator contract
  read: marker set must equal the matrix LREQ list exactly; orphan nodes and marker/matrix
  mismatches both fail — `validate_traceability.py:204–227`.)

---

## 9. Golden vectors and fixtures

- **Reuse** `tests/fixtures/report_fixtures.py::dashboard_rows()` (three rankable + one refused;
  components `D=0.70, C=0.55, R=0.60, Q=0.65`; composite `0.63`; persisted contribution sum
  `0.6275` **(counted from `test_report.py:1266`)**) and `_dashboard_view(tmp_path)` for the new
  layout tests.
- **New fixture** `tests/fixtures/cli_fixtures.py::dashboard_app_recorder()` — a callable
  app-factory recording `(view)` and returning a minimal `object()`, plus a `run_dashboard`
  recorder/poison helper for the CLI and end-to-end nodes.
- Hand-computed values unchanged from chunk 30 (contribution vector, KPI tiles, policy ranks);
  no new arithmetic is introduced by this chunk. The heatmap reference-line vector is no longer
  rendered (R4).

---

## 10. Gate checklist / DoD

- [ ] `python -m pytest -q` — the whole suite passes with §8 nodes added, the eight removed
      report nodes gone, and the amended nodes repointed.
- [ ] `python -m niche_scout.tools.validate_traceability` — exit 0; every new node has a marker
      and a `tests/traceability.json` entry; no orphan entries for the removed nodes.
- [ ] `python -m niche_scout.tools.check_import_boundaries` — exit 0 (`metrics.py`/`scoring.py`
      untouched and pure; `report.py` is not a pure module).
- [ ] `python -m niche_scout.tools.check_scope_prohibitions` — exit 0 (no retired token; R7).
- [ ] Formatter and linter per `pyproject.toml` (`ruff format`, `ruff check`) run clean on
      changed files.
- [ ] `dash==4.4.1` is declared and importable in the test environment (D-2; R1).
- [ ] `report.py` still imports none of `metrics`, `scoring`, `collector*`, `config`,
      `pipeline`, `cli`, and reads no clock (`test_quality_tooling.py:377` AST scan stays green
      — it checks a fixed forbidden set, not an allowlist, so `dash`/`plotly` are permitted
      **(read)**).
- [ ] `build_dashboard_layout(view)` is deterministic (two equal trees) for a fixed view.
- [ ] The app serves assets locally (Dash default; `serve_locally=True` if the keyword exists,
      R6); a manual disconnected-network smoke run by the lead renders every chart.
- [ ] `dashboard` performs database reads only; no transport constructed (`LREQ-CLI-020`); the
      app is built from one `load_run_report_view` call; `run_dashboard` is never called by a
      real bind in tests.
- [ ] `dashboard` binds `127.0.0.1`, prints the URL to `stdout`, opens no browser;
      `KeyboardInterrupt` → `EXIT_OK`; bind failure → `EXIT_RUNTIME_ERROR` (R7).
- [ ] Mandatory content obligations verified: `LREQ-RPT-020` all 30 labels visible by default;
      `LREQ-RPT-030` all items for the selected category; `LREQ-RPT-040` non-rankable visible;
      `LREQ-RPT-050` statement present.
- [ ] Refused rows off the scored axis; ordinal evidence grade on the score bar; `n/a` ≠ `0`;
      no confidence interval/error bars; coverage and `sample_fraction` distinctly labelled;
      the heatmap is absent.
- [ ] `render_run_report_html` / `write_run_report` unchanged and still self-contained
      (`test_html_output_is_self_contained_and_deterministic` stays green).
- [ ] No file outside §7.3 changed; the two interface files in §6 amended by the lead.
- [ ] Run log `Documents/runs/chunk-31.md` updated with the gate result.

---

## 11. Questions resolved before freeze

Q1–Q8 were raised in the DRAFT and are all resolved by the lead rulings R1–R8 in §12. No open
question remains.

---

## 12. Lead rulings (freeze, 2026-10-01)

All eight questions are resolved. Authority: the operator's rulings relayed to the planner on
2026-10-01, plus the run log's D-1..D-5. No ruling fabricates a quantity the SRS does not
define (AGENTS.md Hard rules 1–2).

- **R1 (Q1) — dependency.** `dash==4.4.1` is pinned. Evidence: the lead queried the PyPI JSON
  API directly and found `dash` latest = `4.4.1`, release `4.4.1` present, `requires_python
  >= 3.9`; `dash` is not installed locally. Existing `plotly>=7.1,<8` stays. Method recorded
  in §13.
- **R2 (Q2) — single dashboard; remove both renderers.** Adopt option (a). Both
  `render_dashboard_html(repository, run_id)` and `render_run_dashboard_html(view)` are removed
  from `report.py`; the Dash app is the **only** dashboard. Every consumer is repointed (CLI
  default, `test_report.py`, `test_cli.py`, `test_end_to_end.py` including the
  `render_dashboard_html` calls at `test_end_to_end.py:153`/`:519`). The **static report path is
  retained**: `render_run_report_html`, `render_run_report_text`, `write_run_report` stay for
  `niche-scout run --report` — that is a report **file**, not a dashboard. No `--out`. Node
  renames/removals/additions and traceability bookkeeping are in §8.2/§8.3/§8.4/§8.5.
- **R3 (Q3) — view-only app.** The app is built from a `RunReportView`
  (`build_dashboard_layout(view)` / `build_dashboard_app(view)`); the CLI loads the view once via
  `load_run_report_view`; no callback re-queries the database. No `chunk-00`/`chunk-02`
  repository delta. The read-once, read-only, no-transport property (`LREQ-CLI-020`) is kept.
- **R4 (Q4) — omit the coverage heatmap.** Do not redesign it. Coverage stays exact in the
  primary table; evidence grade is encoded as an **ordinal colour on the ranked score bar** with
  exact values in hover/table. The heatmap figure, its tests, its `DASHBOARD_CHART_IDS` entry,
  and its traceability contributions are removed.
- **R5 (Q5) — all `LREQ-RPT-020` fields visible by default.** Option (b): the primary table
  shows all 30 labels by default (compact, horizontally scrollable). Tooltips/footnotes are
  plain human language ("what this means / what to watch for"), never raw field-name jargon or
  bare acronyms; the vocabulary is defined in §5.7 (D = "Demand", C = "Competition",
  R = "Recent supply", Q = "Quality", each with a one-line explanation). Every chart keeps its
  one-line "what it depicts" caption and correct legends/axis labels (D-5).
- **R6 (Q6) — local asset serving.** Rely on Dash's default local asset serving (no CDN); the
  implementer verifies the exact 4.4.1 keyword on the installed package; if `serve_locally` is
  gone, the default local serving is what the plan relies on.
- **R7 (Q7) — output channel and exit codes.** Option (a): bind `127.0.0.1`, print the local URL
  to `stdout`, do **not** auto-open a browser. `KeyboardInterrupt` → `EXIT_OK`; bind failure →
  `EXIT_RUNTIME_ERROR`. This amends Ruling 6 (print URL instead of print HTML). No new
  scope-prohibition token.
- **R8 (Q8) — provisional-run tiles and notice.** Null `top_3_stability`/`top_5_stability`
  render as `n/a` tiles (never `0`); the provisional / no-rankable-candidate notice appears
  exactly once in the shared footnote, never per category.

### 12.1 Post-freeze implementation risks (record, do not silently resolve)

- **Dash 4.4.1 local-asset API (R6).** Whether `serve_locally` still exists in 4.4.1 is
  **unverified** here (§13); the implementer verifies on the installed package and relies on the
  default local serving if the keyword is absent. If neither is true (i.e. any CDN is
  required), STOP and report — the offline requirement is not negotiable.
- **`dash_table` availability.** The primary table assumes `dash_table.DataTable` (a Dash
  dependency) or an `html.Table`; the implementer uses whichever is present in 4.4.1 and
  records it. **(unverified** — not installed locally. Q5/R5 requires all columns visible
  either way.**)**
- **`to_plotly_json()` normalization.** The determinism tests assume Dash component trees
  normalize via `to_plotly_json()`; if a component lacks it, the test uses the documented
  equivalent and records the substitution.

---

## 13. Evidence walk for the countable claims in this plan

Per project-rules "Plan review and audit", the counts asserted above and the method used:

- **`_PRIMARY_COLUMNS` = 30 labels.** Query: read `src/niche_scout/report.py:226–260`; the tuple
  literal has 30 `(label, attribute)` rows (unit: tuple rows; 1-based lines 226–260).
  **(counted by reading the tuple; not by cross-reading a second document.)**
- **Heatmap degeneracy in `out.html`.** Query: read `out.html:3674` (the
  `niche-scout-status-heatmap` `Plotly.newPlot` JSON); the three coverage columns are `1.0` in
  nearly every row (a handful of ~0.75/0.5 quality cells), and the separate C column carries a
  status string. Unit: `z` cells equal to 1.0. **(counted from the emitted figure JSON; the
  exact cell count is not enumerated here — see UNVERIFIED in the result block.)**
- **Contribution sum 0.6275.** Query: read `tests/test_report.py:1266`
  (`assert sum(values.values()) == pytest.approx(0.6275, abs=1e-9)`). Unit: the summed
  contribution value. **(read.)**
- **`check_import_boundaries` checks only `metrics.py`/`scoring.py`.** Query: read
  `src/niche_scout/tools/check_import_boundaries.py:17` (`PURE_MODULES`) and `:135` (loop over
  `PURE_MODULES`). **(read.)**
- **`validate_traceability` requires marker set == matrix list, and rejects orphans.** Query:
  read `src/niche_scout/tools/validate_traceability.py:204–227`. **(read.)**
- **Removed report nodes still carry LREQ keys.** Query: read `tests/traceability.json:1486`
  (`test_html_output_is_self_contained_and_deterministic`), `:1532`, `:1535`, `:1566` — the
  eight removed dashboard node keys and their LREQ lists appear at the cited lines.
  **(read; the exact eight-key enumeration is in §8.2.)**
- **`dash` 4.4.1 / `requires_python >= 3.9` / not installed locally.** The lead queried the PyPI
  JSON API directly (R1); the planner's own shell probe was denied by the environment
  permission rule and returned no version. **(lead-verified; planner-unverified locally.)**
- **`test_end_to_end.py` line numbers 153 / 519 / 749.** Query: read `tests/test_end_to_end.py`
  at those offsets (`:153` and `:519` call `report.render_dashboard_html`; `:749` calls
  `cli_module.dashboard_command` with `stdout`). **(read.)**
