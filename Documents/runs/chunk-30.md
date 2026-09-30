# Chunk 30 — run log (dark-mode Plotly run dashboard)

New remediation/feature chunk. Not in dependency-map §3/§4 (chunk-14 / chunk-24 precedent):
registration = plan + run log + branch. Next free id confirmed by `Documents/runs/chunk-29.md`
and the absence of any `chunk-3*` plan/run/interface artifact.

Branch: `chunk-30` (created from `main` at `092e55f` — `chunk-29: gate PASSED`).

## Origin

Operator request (2026-09-30): a beautiful dark-mode Plotly dashboard to visualise run data,
defaulting to the latest run, with four primary views (rank-by-score bar with a refusal gap,
stacked weighted-contribution bar, category × status heatmap, 3-policy rank bump chart) plus a
KPI strip and supporting population lollipop / dumbbell / scatter. "Do it in a single chunk as
best as you can design it."

## Preflight

| Check | Result |
|---|---|
| Working tree | clean (`git status` → nothing to commit) |
| Branch | `main` → `chunk-30` |
| Latest commit | `092e55f` (`chunk-29: gate PASSED`) |
| Prerequisite Chunk 11 (report renderer) | `Documents/runs/chunk-11.md` → `GATE: PASSED`; `interfaces/chunk-11.md` `Status: VERIFIED` |
| Prerequisite Chunk 12 (CLI) | `Documents/runs/chunk-12.md` → `GATE: PASSED`; `interfaces/chunk-12.md` `Status: VERIFIED` |
| Prior artifacts | no `Documents/{plans,runs,interfaces}/chunk-3*` exists |
| Routing (lead-chosen; renderer + CLI work) | `chunk-planner` → `impl-fast` (tests included; tests-first = no, per matrix rows 11/12) → `spec-reviewer` → lead gate |
| `plotly` installed | no (`pip show plotly` → not found) — must be added as a project dependency |

## Operator-authorized decisions carried into the plan brief

Recorded here as the operative authority (the operator's request itself, plus the frozen
contracts it must satisfy). None of these may be re-opened by an agent.

- **D-1 — dependency.** Add `plotly` to `pyproject.toml [project].dependencies`. The current
  dependency set is empty; the operator explicitly asked for a Plotly dashboard.
- **D-2 — self-containment (not a violation).** New renderer output stays one self-contained
  dark-mode HTML document with **inline** Plotly JS (`include_plotlyjs="inline"`, fixed
  `div_id`), no CDN and no external asset URL, because `interfaces/chunk-11.md:144-145,200-201`
  freezes self-containment and `LREQ-CLI-020` allows database reads only. The new function is a
  new contract surface; the frozen `render_run_report_html` / `render_dashboard_html` are not
  weakened.
- **D-3 — latest-run default.** `niche-scout dashboard --run-id` becomes **optional**, defaulting
  to the most recent run by `run_started_at_utc`. This deliberately **amends Ruling 3**
  (`interfaces/chunk-12.md:43,62-63`) on the operator's current explicit instruction and will
  require a documented interface delta plus, if absent, a new repository read ("list runs" /
  "latest run"). Single-run display only — never run comparison (`SRS-lean-v2.md:1187,1379`).
- **D-4 — module location.** New renderer lives in `report.py` (an authorized I/O+render file;
  growth inside it is in scope). `report.py` still must not import `metrics`, `scoring`,
  `collector*`, `config`, `pipeline`, or `cli`, and must not read the clock.

## Fixed design constraints handed to the planner

- Charts (primary): ranked horizontal bar of composite score with a visual gap before refused
  categories; stacked bar of weighted contributions (`0.35·D`, `0.30·C`, `0.20·R`, `0.15·Q`,
  renormalised over available) sorted by rank; category × status heatmap (D/C/R/Q coverage,
  evidence grade, rankability) with the SRS §14 coverage thresholds as reference lines; 3-column
  policy bump chart (`rank_balanced` / `rank_demand_heavy` / `rank_competition_heavy`) plus
  `top_3` / `top_5` / `maximum_rank_displacement` KPI tiles. Supporting: log-scale population
  lollipop with sample-size marker; optional component dumbbell; optional score-vs-quality
  scatter sized by sample fraction.
- Guardrails: refused categories never share the scored axis with rankable ones; evidence grade
  as an **ordinal** colour scale (insufficient→weak→moderate→strong), not categorical; `n/a`
  (null) visually distinct from `0`; no confidence intervals or error bars; coverage and sample
  fraction labelled as distinct quantities; every threshold sourced from the SRS constants, never
  hard-coded in the renderer.
- Purity/determinism: renders persisted values verbatim (no recomputation), no clock, fixed
  ordering, byte-identical output for a fixed view, no RNG.
- All data is already persisted (`report.py` read model; `scoring.py:1229-1231` policy ranks);
  no pipeline or schema change is expected beyond a possible latest-run read.

## Stage log

| Stage | Status | Notes |
|---|---|---|
| Preflight (lead) | DONE | tree clean; `chunk-30`; this log |
| Plan — `chunk-planner` | BLOCKED (QUESTIONS) | Plan written DRAFT: `Documents/plans/chunk-30-dark-mode-plotly-dashboard.md`. Returned 1 blocking question (Q1: no competition coverage in the frozen model, so the requested D/C/R/Q coverage heatmap cannot apply the §14 thresholds to C) and 5 non-blocking proposals (Q2–Q6). Stopped per procedure; relayed to operator. No source/test/SRS/interface file edited; nothing committed. |
| Research — `explore` (operator-requested) | DONE | Independent read-only research answering Q1–Q6 with `path:line` + LREQ evidence (board `board_272be634…`). Q1 confirmed: no competition coverage exists (`LREQ-SCR-020` gives C no coverage term; `LREQ-MET-070` gives only breadth status) → recommend D/R/Q numeric coverage + C as `breadth_completeness_status`. Q2 repoint `render_dashboard_html` (signature pinned by `tests/test_report.py:1089`). Q3 add `get_latest_run_id` (Python-side max; no SQL ORDER BY) + `EXIT_RUNTIME_ERROR` on empty DB. Q4 keep Ruling 6 stdout. Q5 zero is legal and distinct from null. Q6 PEP 508 range; all three supporting charts derivable without recomputation. Also found: no new node IDs collide; scope-prohibition tokens safe; frozen `interfaces/chunk-11.md:72,197` rank text is stale. |
| Version research (lead) | DONE | PyPI read directly: `plotly` 7.1.0 (2026-09-15, `requires_python>=3.8`); pytest 9.1.1; ruff 0.16.9; setuptools 84.0.0. `plotly` not installed locally. |
| Plan rulings + freeze (lead) | DONE | Plan §12 added with six rulings R1–R6 (matching the research) + R7 (correct the stale `chunk-11.md` rank locant). `plotly>=7.1,<8` pinned. Status → FROZEN. Interface deltas for the lead recorded in plan §2. |
| Interfaces applied (lead) | DONE | Added revision sections: `interfaces/chunk-00.md` §12 (`Repository.get_latest_run_id`), `chunk-02.md` §8 (read API + determinism note), `chunk-11.md` §10 (`RunSensitivitySummary`, four `CategoryReportRow` fields, `RunReportView.sensitivity`, new constants, `render_run_dashboard_html`, `render_dashboard_html` repoint, rank-locant correction, display rules), `chunk-12.md` §9 (optional `--run-id`, Ruling 3 amended, Ruling 6 retained). |
