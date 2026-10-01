# Chunk 31 — run log (Dash 4.4.1 + Plotly dashboard redesign)

New remediation/feature chunk, not in `Documents/requirements-dependency-map.md` §3/§4
(chunk-14 / chunk-30 precedent: registration = plan + run log + branch). The next
free id is 31 (runs/plans/interfaces stop at 30). Do not edit the dependency map,
the SRS, `AGENTS.md`, or `.kilo/`.

Branch: `chunk-31`, created from `main` @ `e869f69` (`chunk-30: gate PASSED`).

## Origin

Operator request (2026-10-01): `out.html` (the Chunk-30 dashboard output) is too long
and too text-heavy, contains unnecessary data and poor/degenerate charts. Select the
best representation per the project's analytical goals, keep mostly graphs plus a
minimal table, and plan a **Dash 4.4.1 + Plotly** dashboard that is beautiful and
best-in-class for data visualization. "Do this in a chunk." Every chart must carry a
simple plain-language explanation of what it depicts, and proper legends.

## Preflight

| Check | Result |
|---|---|
| Working tree | only `out.html` untracked (the analysis artifact); no tracked file modified. Lead will not stage `out.html`. Deviation from a strictly clean tree, accepted and recorded. |
| Branch | `main` → `chunk-31` |
| Base commit | `e869f69` (`chunk-30: gate PASSED; run log`) |
| Prerequisite Chunk 11 (report renderer) | `Documents/runs/chunk-11.md` → `GATE: PASSED`; `interfaces/chunk-11.md` `Status: VERIFIED` |
| Prerequisite Chunk 12 (CLI) | `Documents/runs/chunk-12.md` → `GATE: PASSED`; `interfaces/chunk-12.md` `Status: VERIFIED` |
| Prerequisite Chunk 30 (dark-mode Plotly dashboard) | `Documents/runs/chunk-30.md` → `GATE: PASSED`; `interfaces/chunk-11.md` §10 |
| Prior chunk-31 artifacts | none (`plans`/`runs`/`interfaces` have no `chunk-31`) |
| Shell permissions | allowed patterns include `python *`, `pytest *`, `ruff *`, `pip show/list`, `pip install -e *`, read-only `git`, and lead-only `git switch/add/commit/merge --ff-only`. |
| Routing (lead-chosen; report/CLI work) | `chunk-planner` → `impl-fast` (tests included; tests-first = no, per matrix rows 11/12) → `spec-reviewer` → lead gate |

## Operator-authorized decisions (not re-openable by agents)

- **D-1 (B1) — shell.** Operator supplied the effective permission block; the lead may
  run the allowlisted `python`/`pytest`/`ruff`/`pip`/read-only-`git` commands plus
  `git switch`/`add`/`commit`/`merge --ff-only`.
- **D-2 (B2) — Dash authorized.** The operator explicitly authorizes replacing the
  static self-contained HTML dashboard with a **Plotly Dash** application. This
  deliberately amends the frozen Chunk-11 self-containment guarantee
  (`interfaces/chunk-11.md` §1/§5/§10) and Chunk-12 Ruling 6 ("stdout, no server, no
  browser launch", `interfaces/chunk-12.md` §9). New dependency: `dash` (`dash` 4.4.1
  named by the operator) plus the existing `plotly`. The dashboard remains
  **read-only**: it may only read SQLite and shall start no Coveo/GraphQL transport
  (LREQ-CLI-020). It stays single-run and local (no historical trends, no multi-user).
- **D-3 (B3) — text minimization.** Minimize on-page prose. Context that is sensible as
  interaction goes in **tooltips / hover**. Anything not UX-sensible inline becomes a
  **small text footnote, once** (shared, not repeated per category). SRS-mandated
  content (below) must still be present somewhere reachable.
- **D-4 (B4) — new chunk.** This is new chunk 31; Chunk 30 is not edited in place.
- **D-5 — chart explanations and legends.** Every chart carries a one-line plain-language
  explanation of what it depicts and correct, human-readable legends/axis labels.

## Fixed design selection handed to the planner (from the out.html analysis)

`out.html` is 3,713 lines: ~3,620 lines are one inlined plotly.js copy; rendered content
is ~40 markup lines. Rendered: run header, 1 heuristic paragraph, 3 KPI tiles, 8 charts,
a warnings list, a 29-column × 24-row primary table, and 24 near-identical
`category-detail` blocks each repeating the same 11-bullet formula list.

Retain (primary): ranked composite-score bar with the refusal gap; weighted contribution
stack (`W_D·D`, `W_C·C`, `W_R·R`, `W_Q·Q`); policy rank bump chart + KPI tiles
(`top_3_stability`, `top_5_stability`, `maximum_rank_displacement`); population/sample
lollipop (log scale, sample-size marker).
Redesign or drop: the D/R/Q coverage heatmap is degenerate in this run (almost all
coverage = 1.0; the C column mixes a categorical status into a numeric domain) — replace
with an evidence/support view only if it carries information; the component "dumbbell"
(18 overlapping 4-point series) is redundant spaghetti — drop; keep the
score-vs-quality scatter as a secondary diagnostic.
Tables: one compact sortable decision table instead of 29 raw columns.
Details: hoist the shared formula/"how to read" list to **one** panel; per-category
formula/metric-input/strata/timestamps/observed-vs-inferred detail appears for the
selected category only (Dash interaction), not 24 repeated blocks.
Preserve: `HEURISTIC_STATEMENT` verbatim (LREQ-RPT-050); non-rankable categories
visible (LREQ-RPT-040); null is a distinct `n/a` and never `0`; no confidence intervals
or error bars; coverage and `sample_fraction` distinctly labelled; every threshold
sourced from `models`/SRS §14 (never hard-coded).

## Stage log

| Stage | Status | Notes |
|---|---|---|
| Preflight (lead) | DONE | clean-enough tree; `chunk-31`; this log |
| Plan — `chunk-planner` (2 dispatches) | DONE | DRAFT returned Q1 (BLOCKING) + Q2–Q8; after rulings, revised `Documents/plans/chunk-31-dash-plotly-dashboard.md` and froze it (§12 R1–R8). Nothing else edited by the planner. |
| Q1 resolution (lead) | DONE | PyPI JSON: `dash` latest = `4.4.1`; `4.4.1` present; `requires_python >=3.9`. `dash` not installed locally. Pin `dash==4.4.1`. |
| Operator rulings Q2–Q8 | DONE | Q2=(a) single Dash, remove both chunk-30 dashboard renderers; Q3=view-only app; Q4=omit heatmap; Q5=(b) all RPT-020 columns visible by default + plain-language tooltips; Q6/Q7/Q8 = lead recommendations accepted. |
| Interfaces applied (lead) | DONE | `interfaces/chunk-11.md` §11 (Dash app: import allowance, constants, function removal/addition, display rules, label vocabulary) and `interfaces/chunk-12.md` §10 (`dashboard_command` app-factory seam + `run_dashboard`, Ruling 6 amended). |
| Plan freeze + commit | DONE | `chunk-31: plan` (`9976cf7`) |
| Implement — `impl-fast` (3 dispatches) | DONE | Production + tests per plan §7–§8. `dash==4.4.1` pinned and installed (`pip install -e .`); `plotly>=7.1,<8` kept. WIP snapshot `cbf24be`; completed `a5ca503`. |
| Lead verification | DONE | `pytest -q` → **746 passed, 18 warnings**; `validate_traceability` → 89 IDs / 725 matrix nodes / 0 unmarked (3 exempted); `check_import_boundaries` → valid; `check_scope_prohibitions` → valid (6 tokens); `ruff format --check` + `ruff check` on the 6 changed files → clean. |
| Offline / no-CDN proof (lead) | DONE | Started a local Dash 4.4.1 app (`serve_locally=True`) on `127.0.0.1:8061`; fetched `/` → 0 occurrences of `http://`/`https://`, no `cdn.plot.ly`, local component suites present; fetched a `_dash-component-suites/.../async-graph.js` asset → HTTP 200, 13,514 bytes. Server stopped. No external asset required. |
| Review — `spec-reviewer` | PASS | **VERDICT: PASS** — no Blocker, no Major; 6 Minors (recorded below). |
| Gate | PASSED | see walk |

## Gate walk (plan §10 DoD)

| Bullet | Evidence | Result |
|---|---|---|
| Whole suite passes | `python -m pytest -q` → `746 passed, 18 warnings in 28.59s` (warnings are Dash's own `DataTable` deprecation notice) | PASS |
| Traceability exit 0, no orphan | `89 required/defined LREQ IDs mapped, 725 matrix nodes, 0 unmarked analytical tests outside exemption (3 exempted non-analytical nodes)`; 12 new report nodes + 1 new CLI node; 8 removed keys gone (reviewer confirmed the diff) | PASS |
| Import boundaries exit 0 | `Import boundaries valid for metrics.py, scoring.py` (`report.py` is not a pure module; `dash`/`plotly` permitted) | PASS |
| Scope prohibitions exit 0 | `no retired token found … (6 tokens checked)` | PASS |
| Formatter/linter clean on changed files | `ruff format --check` → `6 files already formatted`; `ruff check` → `All checks passed!` (repo-wide pre-existing findings live in untouched files) | PASS |
| `dash==4.4.1` declared and importable | `pyproject.toml` `dependencies = ["plotly>=7.1,<8", "dash==4.4.1"]`; `dash 4.4.1`, `DataTable` via `dash.dash_table` (`dash_table 7.4.1`), `serve_locally` present (default `True`) | PASS |
| `report.py` boundary held | imports stdlib + `plotly` + `dash` + `.database` + `.models` only; no `metrics`/`scoring`/`collector*`/`config`/`pipeline`/`cli`; no clock read (reviewer grep: no `datetime.now`/`utcnow`/`time.time`) | PASS |
| Layout deterministic for a fixed view | `test_build_dashboard_layout_is_deterministic_for_a_fixed_view` + `test_build_dashboard_app_layout_matches_the_layout_builder` (equal trees via `PlotlyJSONEncoder`) | PASS |
| Serves assets locally | lead live probe above: 0 external URLs, no CDN, local `_dash-component-suites` assets served HTTP 200 | PASS |
| DB reads only; no transport | CLI nodes + `test_acceptance_dashboard_reads_persisted_run_only`; app built from one `load_run_report_view`; tests never bind | PASS |
| Loopback URL, no browser, exit codes | `run_dashboard` prints the URL, `host="127.0.0.1"`, no browser call; `KeyboardInterrupt`→`EXIT_OK`; bind failure→`EXIT_RUNTIME_ERROR` (code-reviewed; tests must not bind) | PASS |
| RPT-020/030/040/050 | RPT-020 all 30 `_PRIMARY_COLUMNS` visible by default; RPT-030 detail for the selected category with the shared formula list once; RPT-040 refused rows visible and absent from the scored bar trace; RPT-050 `HEURISTIC_STATEMENT` verbatim once | PASS |
| Guardrails | no error-bar/CI trace; ordinal evidence-grade colour on the ranked bar; `n/a` ≠ `0`; coverage vs `sample_fraction` distinctly labelled; heatmap + dumbbell removed; thresholds from `models` | PASS |
| Static report path unchanged | `render_run_report_html`/`render_run_report_text`/`write_run_report` retained; their tests stay green | PASS |
| Files touched / interfaces | changed set = `pyproject.toml`, `report.py`, `cli.py`, 4 test files, `tests/traceability.json`, 2 interfaces, plan, run log | PASS |

**GATE: PASSED** (reviewer PASS; no Blocker/Major surviving).

## Review Minors recorded (do not trigger a loop; deferred)

1. `cli.py` `run_dashboard` — bind-failure text goes to `stdout` and the URL is printed before the bind; prefer `stderr` and print the URL only after a successful bind.
2. `report.py:1959-1961` — the shared-footnote provisional check uses the literal `"rankable"` instead of `RankabilityStatus.RANKABLE.value`, and its wording is over-broad for a ≥21-category all-not-rankable run. No R8 violation (fires once, never per category).
3. `tests/test_cli.py::test_dashboard_selects_completed_and_failed_runs` — the serve recorder is monkeypatched but not asserted (covered by four other nodes).
4. `tests/test_report.py` — a duplicated struct-docstring loop; a dropped explicit `component_d=0.0` contribution assertion (still covered elsewhere).
5. Plan §8.1 axis/legend-label assertion and the §5.6 offline-URL assertion are thinner than planned; offline was proven live by the lead instead.
6. `tests/test_report.py` is ~1,581 lines (≈460 dashboard lines) — over the ~1,000-line review trigger. Boundary note only, per project rules; no split, no node-ID change. A future split along requirement clusters is a scope decision.

## Open items carried forward

- **R8 provisional signal (implementer QUESTION 1).** No persisted run-level "provisional" field exists (SRS §10 defines none); the shared footnote derives provisionality from persisted ranks/sensitivity (`view.sensitivity is None` or no `rankable` row). Recorded as an interpretation; if a future chunk wants an explicit signal, that is a read-model decision, not this chunk's.
- Pre-existing repo-wide `ruff` findings in untouched test files belong to a separate remediation chunk.
- The three standing obligations (URI extraction, OI-6, `taxonomy_sha256`) remain untouched by this chunk.