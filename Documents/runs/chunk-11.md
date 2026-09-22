# Chunk 11 — run log (Report renderer and read-only dashboard)

Started 2026-09-22. Branch `chunk-11` created from `main` at `05f5632`; tree clean at preflight.
Chunk 11 depends on the frozen interfaces of Chunks 4B, 7B, 8, 9A, 9B, 10, all present and `VERIFIED`.

## Preflight

| Check | Result |
|---|---|
| Working tree | clean (`git status` → nothing to commit) |
| Branch | `chunk-11` (new, from `main` `05f5632`) |
| Prerequisite interfaces | `Documents/interfaces/chunk-4B.md`, `chunk-7B.md`, `chunk-08.md`, `chunk-9A.md`, `chunk-9B.md`, `chunk-10.md` all `Status: VERIFIED` |
| Baseline suite | `python -m pytest tests -q` → **503 passed, 0 failed** |
| Frozen plan | none — planner dispatch required |
| Routing | `chunk-planner` → advisory research → lead rulings → `impl-fast` (no test-author first) → `spec-reviewer` |

## Stage log

| Stage | Status | Evidence / notes |
|---|---|---|
| Preflight | DONE | Table above. |
| Plan — `chunk-planner` dispatch 1 | INCOMPLETE | Session `ses_f36ea3e36ffebWpGUGBlSvXOhM` completed reconnaissance (SRS §10/§6.5/§9/App C/§16, dependency-map Chunk 10/11/§6, interfaces 4B/7B/8/9A/9B/10, `models.py`/`database.py`/`pipeline.py`) but ran out of steps before writing the plan file. Re-dispatched. |
| Plan — `chunk-planner` dispatch 2 | DONE | Session `ses_f36e2c641ffe01InHeaoYO61Xs`. Plan written: `Documents/plans/chunk-11-report-renderer-and-read-only-dashboard.md` (486 lines, Status: DRAFT), with 6 open questions. |
| Plan — advisory research | DONE | Read-only `explore` session `ses_f36dd3e59ffeaat9euLOrN1IBS` independently answered all six questions against SRS-lean, the dependency map, the frozen interfaces, and the source. It confirmed Q1/Q3/Q6 as drafted, confirmed Q2's persisted-only rule and grounded it in SRS §1.2/§7.2, grounded Q4 (HTML required; text additive), grounded Q5 (no run-level limitation column) and surfaced two contract hazards. |
| Plan — lead rulings 1–6 | DONE | §12.0 added to the plan with the six rulings; plan frozen (Status: FROZEN). Two hazards recorded rather than resolved: (i) Chunk 10's `ranking_sensitivity_json="{}"` on preflight-failure rows vs dependency-map §6.3's mandatory explicit empty-candidate status — owner Chunk 10/9B; Chunk 11 treats `"{}"` and an absent/empty `ranked_categories` alike; (ii) the `NOT NULL DEFAULT 0`/`0.0` pre-scoring values on failed-preflight rows — Chunk 11 must render them as unavailable, added to plan §8 and the §9 golden vectors. |
| Implement — `impl-fast` | DONE | Session `ses_f36d3146fffecprVeS5q3Gnyou`. `report.py` (stub → 1,047 lines: read model, HTML/text renderers, `write_run_report`, `render_dashboard_html`), `tests/test_report.py` (17 nodes), `tests/fixtures/report_fixtures.py`, 18 new `tests/traceability.json` entries. Reported: 17 passed chunk, 520 passed suite. |
| Verify (lead, step 6) | DONE | `python -m pytest -q` → **520 passed, 0 failed**; `validate_traceability` → valid (506 matrix nodes, 89 LREQ IDs); `check_import_boundaries` → valid; `ruff check` + `ruff format --check` on the three chunk files → "All checks passed!" / "3 files already formatted". Working tree contained only the plan-§6 files. |
| Review — `spec-reviewer` round 1 | FAIL (1 Major, 1 Minor) | Session `ses_f36bee154ffeHr50Kzp1bq3Cc0`. Major: the LREQ-RPT-020 column test used substring assertions and did not actually certify the columns. Minor (later found false): a claimed `tests/test_database.py` reformat inside `03807dd`; the lead re-ran `git show 03807dd --stat` → **only 4 files, `report.py`, `tests/test_report.py`, `tests/fixtures/report_fixtures.py`, `tests/traceability.json`** — no `test_database.py`. |
| Fix round 1 | DONE | Session `ses_f36b21fe0ffewZIP6Jzs70y4nK`. Test rewritten to compare the rendered header set against the `_PRIMARY_COLUMNS` label set (HTML + text, row cells). |
| Review — `spec-reviewer` round 2 | FAIL (1 Major, 1 Minor) | Session `ses_f36a93830ffep0VWNap3Aywn2N`. Major: the oracle was self-referential (expected set derived from the same `_PRIMARY_COLUMNS` the renderers consume), so lockstep deletion of a column would still pass. Minor: dead `_section` parser state. |
| Fix round 2 | DONE | Session `ses_f369e277bffePTjmsVX6kCS2YG`. Expected labels replaced by a literal 30-entry tuple transcribed from SRS §10 (clause-commented); `_PRIMARY_COLUMNS` equality kept only as a secondary consistency check; `<th>` capture gated on `_section == "thead"`. Mutation check (`rank` → `rank position` in `report.py`) made the test fail; `report.py` restored. |
| Review-fix rounds used | 2 of 2 | Both rounds addressed real Major findings; the round-1 Minor was verified false by the lead. |
| Review — `spec-reviewer` round 3 | PASS | Session `ses_f369925fcffeDXPEVYiInaqfNZ`. Both findings closed; literal 30-label oracle verified order-aware; mutation-in-lockstep now fails. Commands re-run by the reviewer: `tests/test_report.py` → 17 passed; suite → 520 passed; traceability → valid; import boundaries → valid; `ruff check --no-fix` on both chunk files → clean; `ruff format --check` on both chunk files → already formatted. |
| Interface produced | DONE | `Documents/interfaces/chunk-11.md` (Status: VERIFIED) written from the frozen plan §5 and §12.0. |
| Gate | PASSED | See gate table below. |

### Review (step 7)

| Item | Result |
|---|---|
| `spec-reviewer` round 1 | `VERDICT: FAIL` — 1 Major (substring-vacuous LREQ-RPT-020 column test), 1 Minor (claimed out-of-§6 `test_database.py` reformat). The Minor was **refuted by the lead**: `git show 03807dd --stat` lists only the four plan-§6 files. |
| `spec-reviewer` round 2 | `VERDICT: FAIL` — 1 Major (self-referential oracle), 1 Minor (dead `_section` state). |
| `spec-reviewer` round 3 | `VERDICT: PASS` — no Blocker, no Major. Both findings closed; the literal 30-label oracle was verified order-aware against SRS §10 and mutation-in-lockstep now fails. |
| Round-3 Minors (open, recorded) | None reported. |
| Reviewer UNVERIFIED | Round 3 could not run `python -m ruff` (shell permission policy) and used bare `ruff --no-fix`; the lead independently ran `python -m ruff check` and `python -m ruff format --check` on the chunk files (both clean). Repo-wide pre-existing ruff debt (245 `check` errors, 14 unformatted files) is unchanged and outside this chunk. |

**Fix-round budget:** 2 of 2 used.

### Gate — Chunk 11

Gate bullets walked one by one from `Documents/requirements-dependency-map.md` §3 Chunk 11
(Gate section, lines 1030–1037), on the working tree at `9985830`, full suite green.

| Gate bullet | Result | Evidence |
|---|---|---|
| 1. `dashboard` performs database reads only | PASS | `report.py` imports only `html`, `json`, `dataclasses`, `datetime(timezone)`, `pathlib`, `.database`, `.models` (report.py:20–43); no network module, no clock read. `render_dashboard_html` (report.py:1040–1047) loads + renders only. Node `test_render_dashboard_html_is_database_read_only` (forbidden-module AST scan + clock-attr scan) passes. |
| 2. Reports include every mandatory score, sample, coverage, evidence, and sensitivity field | PASS | `_PRIMARY_COLUMNS` has 30 entries; `test_primary_table_renders_every_mandatory_column` compares the rendered HTML `<th>` sequence and the text header list against a **literal 30-entry tuple** transcribed from SRS §10 lines 1113–1119 (22 clauses, `D/C/R/Q` → 4 and per-component usable/coverage → 6: 22−2+4+6 = 30), with per-column data-cell width checks; `_PRIMARY_COLUMNS` equality is a secondary consistency check. Mutation check (rename a header in lockstep) fails the test. |
| 3. Non-rankable categories remain visible | PASS | `_order_rows` appends unranked rows after ranked (report.py:530–538); `_rankability_note` builds the reason from persisted fields only (report.py:692–706). Node `test_non_rankable_category_remains_visible` passes. |
| 4. Failed preflight runs remain visible as audit/diagnostic reports even when no metric or score rows were computed | PASS | `_fallback_row` (report.py:465–527) yields one row per requested category with `evidence_grade = "insufficient"`, `rankability_status = "not_rankable"`, `IDENTITY_PREFLIGHT_FAILED` warning, and all-None values. Node `test_failed_preflight_fallback_yields_one_row_per_category` passes. |
| 5. Report fixtures assert the required distinctions (pagination completion vs immutable snapshot completeness; page-view index vs weekly traffic rate; midranks vs inferential percentiles; sample fraction vs stratum eligibility coverage; deterministic evidence vs statistical confidence; heuristic output vs sales/revenue/conversion/traffic-rate claims) | PASS | `HEURISTIC_STATEMENT` (report.py:48–60) names all six distinctions and the two claim disclaimers; `test_report_states_heuristic_and_six_distinctions` asserts all 14 phrases present in HTML and text. `_OBSERVED_LABELS`/`_INFERRED_LABELS`/`_FORMULA_EXPLANATIONS` carry the observed-vs-inferred and formula text (report.py:77–131); `test_detail_labels_observed_versus_inferred` and `test_category_detail_shows_formulas_inputs_strata_and_timestamps` pass. |
| 6. Report language does not imply sales forecasting, statistical confidence, or representative marketplace estimation | PASS | `HEURISTIC_STATEMENT`: "has not been calibrated against sales, revenue, downloads, or conversion" and "not a statistically representative estimate"; `_FORMULA_EXPLANATIONS[0]`: "it is not a sales, revenue, or download forecast". Node `test_report_states_heuristic_and_six_distinctions` asserts both disclaimers. |

Supporting evidence: `python -m pytest tests -q` → **520 passed, 0 failed**;
`python -m pytest tests/test_report.py -q` → **17 passed**;
`python -m niche_scout.tools.validate_traceability` → valid ("7 Chunk 0 requirements
mapped, 506 matrix nodes, 89 defined LREQ IDs"; 7 pre-existing unmarked
collector/sampling tests, none a Chunk 11 node);
`python -m niche_scout.tools.check_import_boundaries` → valid for `metrics.py, scoring.py`;
`python -m ruff check src/niche_scout/report.py tests/test_report.py tests/fixtures/report_fixtures.py` → "All checks passed!";
`python -m ruff format --check` on the same three files → "3 files already formatted".

**GATE: PASSED**

### Open items carried forward (not gate failures)

- Chunk 10 hazard (recorded, owner Chunk 10/9B): `_persist_failure_limitation_rows` writes
  `ranking_sensitivity_json="{}"` on failed-preflight rows, while dependency-map §6.3 requires
  the field to retain an explicit empty-candidate/insufficient-candidate status. Chunk 11
  treats `"{}"` and an absent/empty `ranked_categories` alike (no displayed rank / no
  stability) and does not redefine the shape; the wording fix belongs to Chunk 10/9B.
- Pre-existing repo-wide `ruff` debt (245 `check` errors across `collector_coveo`/`database`/
  `validation`/tests; 14 files `ruff format --check` would reformat) is unchanged and outside
  this chunk. The chunk's own three files are clean.
- **URI trailing-identifier extraction (identity mapping rule 1.0.1) remains UNVERIFIED and
  owned by no chunk** (dependency-map §6.4). Chunk 11 parses no response and states nothing
  about it.
- **OI-6 (CSRF/session sufficiency) remains unassigned** (dependency-map §7). Chunk 11 performs
  no HTTP and neither resolves nor absorbs it.
- **`runs.taxonomy_sha256` empty-hash rejection is Chunk 10-owned** and unchanged by this chunk.
- Run-level limitations have no persisted column; Chunk 11 renders per-category warnings and
  leaves `RunReportView.limitations = ()`. Chunk 12 may surface `PipelineResult.limitations`
  at render time (plan §12.0 ruling 5).
- Dashboard run selection is Chunk 12's (plan §12.0 ruling 1); Chunk 11 added no repository
  method and touched no file outside plan §6.
