# Chunk 12 — run log (CLI commands and configuration precedence)

Started 2026-09-22. Branch `chunk-12` created from `main` at `3b5d202`; tree clean at preflight.
Chunk 12 depends on the frozen interfaces of Chunks 0, 1, 6A, 6B, 8, 10, 11
(LREQ-CLI-010..040 ownership row, dependency-map §3 lines 117–120).

## Preflight

| Check | Result |
|---|---|
| Working tree | clean (`git status` → nothing to commit) |
| Branch | `chunk-12` (new, from `main` `3b5d202`) |
| Prerequisite interfaces | `Documents/interfaces/chunk-00/01/6A/6B/08/10/11.md` all `Status: VERIFIED` |
| Prerequisite run logs | `chunk-6A.md`, `chunk-6B.md`, `chunk-08.md`, `chunk-10.md`, `chunk-11.md` all `GATE: PASSED`; Chunks 0/1 evidenced by VERIFIED interfaces (documented exception) |
| Frozen plan | none — planner dispatch required |
| Routing | `chunk-planner` → `impl-fast` (no test-author first) → `spec-reviewer` |

## Stage log

| Stage | Status | Evidence / notes |
|---|---|---|
| Preflight | DONE | Table above. |
| Plan — `chunk-planner` dispatch 1 | BLOCKED | Session `ses_f368a19ecffedx0ZdIGV4ATX8e`. Wrote plan (501 lines, DRAFT) with 6 open questions. |
| Plan — advisory research | DONE | Session `ses_f3680d328ffebR0v7NLxuPosXf` (read-only). Answered all questions with file:line citations; flagged Q1 (GraphQL transport), Q3 default selection, Q2 plan-§6 addition as unresolved. |
| Plan — user approval of recommendations | DONE | User: "go with the recommendation for all" (2026-09-22). Rulings 1–8 authorized. |
| Plan — `chunk-planner` freeze | DONE | Session `ses_f3679a431ffejdM88y8m4TaJlP`. Plan §12 replaced with Rulings 1–8; §6 amended for `__main__.py`/`pyproject.toml`; Status: FROZEN. Commit `e937ea6` (`chunk-12: plan`). |
| Implement — `impl-fast` dispatch 1 | INTERRUPTED | Session `ses_f368...` (interrupted by tool execution). Left `cli.py`, `__main__.py`, `pyproject.toml`, `tests/test_cli.py`, `tests/fixtures/cli_fixtures.py`, `tests/traceability.json` changed but 12/28 CLI tests failing. |
| Implement — `impl-fast` dispatch 2 | DONE | Session `ses_f35c25205ffe00XDpEqTTKg55G` (first attempt hit a provider "Connection reset by server"; resumed once). Fixed all 12 failures: config-override flags for the SRS §14 "Configurable? Yes" settings, supplied-ness via `CliOptions.config_overrides`, parser cleanup, repository lifetime (close only self-opened), test-side bugs. Reported 28 CLI tests passed, 548 suite passed. |
| Verify (lead, step 6) | DONE | `python -m pytest -q` → **548 passed, 0 failed**; `python -m niche_scout.tools.validate_traceability` → valid (7 Chunk 0 reqs, 534 matrix nodes, 89 LREQ IDs; note lists 7 pre-existing unmarked tests in `test_collector.py`/`test_sampling.py`); `python -m niche_scout.tools.check_import_boundaries` → valid; `python -m ruff check` + `python -m ruff format --check` on the four chunk Python files → clean. Commit `70ece5b` (`chunk-12: implementation`). |
| Review — `spec-reviewer` round 1 | PASS (would-be; ran out of steps) | Session `ses_f35a6a0e5ffesL6Zfa1IikWFDY`. No Blocker, no Major. Two items it could not run (ruff; traceability semantic diff) were supplied by the lead: ruff clean on the four files; matrix 506→534 keys, +28/−0, 0 changed values, all 28 additions `tests/test_cli.py::*`; plan §9 has 18 nodes and 18/18 are in the module and the matrix. |
| Review — `spec-reviewer` round 2 | PASS | Same session, resumed. `VERDICT: PASS` — no Blocker, no Major. Two Minors recorded: (i) `tests/traceability.json` compact→pretty-print churn (value-equal, validator passes); (ii) a truncated comment at `cli.py:62–65`. |
| Fix round 1 (Minor) | DONE | Rewrote the `cli.py:60–65` comment (the only actionable Minor; the JSON formatting churn is cosmetic and the file is formatter-owned). `python -m pytest -q` → 548 passed; `ruff check`/`format --check` clean. Commit `ab4b3c5` (`chunk-12: review fixes`). |
| Review-fix rounds used | 1 of 2 | One Minor fix round; no Blocker or Major ever raised. |

### Review (step 7)

| Item | Result |
|---|---|
| `spec-reviewer` round 1 | No Blocker/Major found; ran out of steps before running ruff and the traceability semantic diff. |
| Lead-supplied evidence | `ruff check`/`format --check` on the four chunk files → clean; matrix diff `HEAD~1` → `506 → 534` keys, `+28 / −0`, `0` changed values, all 28 additions `tests/test_cli.py::*`; plan §9 has 18 node IDs, 18/18 present in the module and the matrix. |
| `spec-reviewer` round 2 | `VERDICT: PASS` — no Blocker, no Major. Minors: (i) `tests/traceability.json` compact→pretty churn (value-equal, validator passes); (ii) truncated comment at `cli.py:62–65`. |
| Round-2 Minors disposition | (ii) fixed in `ab4b3c5`; (i) recorded below as cosmetic and not actionable (the file is formatter-owned and no value changed). |
| Reviewer UNVERIFIED | Interface files chunk-00/03/05/6A/6B/08/10/11 not re-read directly (relied on source + the plan's quoted contracts); repo-wide pre-existing ruff debt not assessed (out of chunk scope). |

**Fix-round budget:** 1 of 2 used.

### Gate — Chunk 12

Gate bullets walked one by one from `Documents/requirements-dependency-map.md` §3 Chunk 12
(lines 1057–1062), on the working tree at `ab4b3c5`, full suite green (548 passed).

| Gate bullet | Result | Evidence |
|---|---|---|
| 1. `run` invokes pipeline orchestration and may call the report renderer only after completion | PASS | `run_command` calls `pipeline.run_pipeline(**run_kwargs)` (cli.py:402) and calls `write_report(...)` only inside `if options.report_path is not None and pipeline_result.succeeded:` after it returns (cli.py:405–412). Nodes `test_run_command_calls_renderer_only_after_pipeline_returns`, `test_run_command_does_not_render_on_failure_path`. |
| 2. `dashboard` calls the report renderer and performs database reads only | PASS | `dashboard_command` calls `report_renderer(repository, run_id)` (default `report.render_dashboard_html`, cli.py:442/471) and constructs no transport; prints HTML to stdout (cli.py:485). Node `test_dashboard_reads_database_only_and_never_constructs_a_transport`; `report.py` imports no `cli`/`pipeline`/`collector` (AST check → empty). |
| 3. Fewer than 8 categories are rejected before ranking | PASS | `PipelineConfigurationError` → `EXIT_USAGE_ERROR` (cli.py:413–415); the node asserts no run row is persisted and no transport is called. Node `test_run_command_rejects_fewer_than_min_categories_before_ranking`; pipeline-side `tests/test_pipeline.py::test_run_with_fewer_than_min_categories_is_rejected` (LREQ-CLI-040). |
| 4. Unrecoverable run errors exit non-zero while preserving run status and limitations | PASS | `PipelineError`/`ReportError`/OSError → `EXIT_RUNTIME_ERROR` (cli.py:416–424); `return EXIT_OK if pipeline_result.succeeded else EXIT_RUNTIME_ERROR` (cli.py:432); limitations printed to stderr (cli.py:403–404); `cli.py` writes no `runs.status`. Node `test_run_command_preflight_failed_exits_nonzero_and_surfaces_limitations`. |

Supporting evidence: `python -m pytest -q` → **548 passed, 0 failed**;
`python -m pytest tests/test_cli.py -q` → **28 passed**;
`python -m niche_scout.tools.validate_traceability` → valid ("7 Chunk 0 requirements
mapped, 534 matrix nodes, 89 defined LREQ IDs"; note lists 7 pre-existing unmarked
`test_collector.py`/`test_sampling.py` tests, none a Chunk 12 node);
`python -m niche_scout.tools.check_import_boundaries` → valid for `metrics.py, scoring.py`;
`python -m ruff check` + `python -m ruff format --check` on the four chunk Python files →
"All checks passed!" / "4 files already formatted".

**GATE: PASSED**

### Findings and open items carried forward (not gate failures)

- Minor (recorded, not actionable): `tests/traceability.json` was rewritten from compact
  one-line entries to pretty-printed form in `70ece5b` (+28 / −0 keys, 0 changed values).
  Cosmetic churn only; the validator passes and the file is formatter-owned.
- `CliOptions.config_overrides` and the `run_command` `template_path` seam are additive
  extensions beyond the plan §5 six-field surface; the reviewer judged both documented and
  plan-consistent (supplied-ness carrier for LREQ-CLI-030; test seam). Recorded in
  `Documents/interfaces/chunk-12.md` §4–§5.
- **OI-6 (CSRF/session sufficiency) remains open and unassigned** (dependency-map §7).
  `cli.py` sends the frozen `X-CSRF-Token` header only and adds no `Cookie` header.
- **URI trailing-identifier extraction (rule 1.0.1) remains UNVERIFIED and owned by no
  chunk**; Chunk 12 parses no response and states nothing about it.
- **`runs.taxonomy_sha256` empty-hash rejection remains Chunk 10-owned**; unchanged here.
- Pre-existing repo-wide `ruff` debt is unchanged and outside this chunk.
- Interface produced: `Documents/interfaces/chunk-12.md` (Status: VERIFIED).