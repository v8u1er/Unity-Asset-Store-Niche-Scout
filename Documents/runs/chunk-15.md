# Chunk 15 — run log (Failure-path limitation truthfulness + operational logging)

Post-completion remediation requested by the human after a live run persisted eight
`page_failed` categories whose CLI output said only `identity_preflight_status`.
Labeled chunk (same pattern as Chunk 14): no dependency-map row; the dispatch DoD is the gate.
Plan: `Documents/plans/chunk-15-failure-path-limitations-and-logging.md`.
Interface files: **not** amended (limitation strings stay `category <repr>: <field>`).

## Preflight

| Check | Result |
|---|---|
| Working tree | UNVERIFIED — `git` is denied by a permission rule (pattern `git *`, agent scope; `git status` denied verbatim). Work proceeds on the current checkout. |
| Branch | none created (git unavailable); no branch, no commit by the lead. |
| Baseline suite | `python -m pytest -q` → **610 passed in 20.03s** (via `background_process`; the `bash` tool is globally denied but `python ...` background processes run). |
| Baseline traceability | `Traceability valid: 89 required/defined LREQ IDs mapped, 596 matrix nodes, 0 unmarked analytical tests outside exemption (3 exempted non-analytical nodes)` |
| Prerequisites | Chunks 10, 12, 14 all `GATE: PASSED` (runs/chunk-10.md:73, runs/chunk-12.md, runs/chunk-14.md:142). |
| Routing | `chunk-planner` → `test-author` → `impl-deep` → lead verify → `spec-reviewer` → lead gate. |

## Grounded findings (labels: read / counted / ran / unverified)

| # | Finding | Evidence |
|---|---|---|
| F1 | Failure-path limitation is hard-coded to the run-level field for every category, masking the category's real failing field. `_persist_failure_limitation_rows` appends `f"category {category!r}: identity_preflight_status"` unconditionally (`pipeline.py:2896`); the completed path emits `discovery_status` only when `category_status_for(...) is not HEALTHY` (`pipeline.py:2980-2987`). | read `pipeline.py:2825-2899, 2365-2397, 2920-3055` |
| F2 | `base is None` fabricates `DiscoveryStatus.REQUEST_FAILED` (`pipeline.py:2849-2855`), collapsing run-level and category-level status (AGENTS.md hard rule 7). Recon shows this branch is dead for any category that went through `_discover_all`: the adapter's `_finalize_result` always calls `set_category_status` (`collector_coveo.py:2217-2219`), and the `except` branch in `_discover_all` also writes a status (`pipeline.py:2812-2819`). | read; explore recon (unverified at runtime) |
| F3 | No production code configures logging. `src/` contains exactly one `getLogger` (`pipeline.py:164`) and one `_LOGGER.info` (`pipeline.py:1392`, LREQ-NFR-020); no handler, `basicConfig`, `dictConfig`, level, or pyproject logging config anywhere. In production the NFR-020 INFO record is discarded by Python's default `lastResort` (WARNING+); the pipeline emits no other progress/diagnostic logging. | counted (grep `src/`, `pyproject.toml`) |
| F4 | A discovery page failure leaves no persisted cause. `category_scores` has no issue/error column (`database.py` `CREATE TABLE category_scores`); a failed page writes no raw observation; the in-memory `CategoryDiscoveryResult.issues` (`collector_coveo.py:440`) are dropped by the pipeline (`_persist_failure_limitation_rows` maps only conditions → warning codes). Persisting the cause needs a schema/interface change → out of scope; surface it as logging. | read `pipeline.py:2542-2600, 2825-2899`, `collector_coveo.py:1900-1935, 2204-2236`, `database.py:178-190` |
| F5 | `run --report` on a failed run is deliberately a no-op. Chunk 12 Ruling 5 and its §11 prohibition forbid rendering on the failure path; `test_cli.py:151-192` pins it. The failed run stays viewable via `dashboard`. **Not a defect; not changed.** | read chunk-12 plan §5 Ruling 5 / §11, `cli.py:405`, `test_cli.py:190-192` |
| F6 | The exact limitation text is untested; `tests/test_pipeline.py:454-476` pins only non-emptiness and redaction-absence, and `tests/test_cli.py:486-488` pins only the substring `"preflight"`. | read |
| F7 | SRS §4.4 `insufficient` for zero attempted identities is correct; marking the run `failed` and exit 1 follows `interfaces/chunk-10.md:91-97`. | read SRS §4.4 lines 408-410 |

## Decisions (lead rulings)

- **R1 Limitations.** Per category: `category_status_for(base.discovery_status, ...) is not HEALTHY` → `category <repr>: discovery_status`; else if the gate is not `passed` → `category <repr>: identity_preflight_status`. No category-less/run-level line (keeps the frozen "category and field only" contract; no interface amendment). The run-level preflight fact with its value goes to the **log** instead (R3).
- **R2 No fabrication.** Create a missing row from the adapter's actual `discovery_by_category[category].discovery_status`; if that is also absent, raise `PipelineError` naming `category_scores` only.
- **R3 Logging.** Idempotent `_configure_logging` in `cli.py` called from `main()` only; per-category discovery outcome + exception-class + run-level preflight/run-outcome lines in `pipeline.py`. No new CLI flags, no new env vars (SRS §10 is silent on verbosity).
- **R4 Out of scope.** `collector_coveo.py`, `collector_graphql.py`, `database.py`, `report.py`, schema, persisted discovery-error columns, `run --report` on failure, and the live Coveo root cause (not reproducible offline).

## Notes on the live failure (not resolved here)

The two post-Chunk-14 live runs fail discovery for all eight categories with
`DISCOVERY_PAGE_FAILED`; the persisted cause is unavailable (F4). R3's per-category
discovery log (status + condition/issue codes + exception class) is the diagnostic hook
for the next run. The template/facet changes from Chunk 14 remain the unverified prime
suspect; the offline suite cannot exercise the live endpoint.

## Stage log

| Stage | Status | Session / evidence |
|---|---|---|
| Preflight (lead) | DONE | Table above; baseline `610 passed`; recon by `explore` `ses_f32378dabffebfBe4nUbF52XO8`. |
| Plan — `chunk-planner` | DONE | `ses_f32317a9effenEJXeRdPc9Qtdg`; wrote the FROZEN `Documents/plans/chunk-15-failure-path-limitations-and-logging.md` (932 lines). Non-blocking assumptions A1–A5; lead rulings: A1 keep the `category <repr>: category_scores` message, A2 map the two wiring nodes to LREQ-NFR-020, A3 inert roll-up arguments, A4 `stream=None` resolves to current `sys.stderr`, A5 committed traceability orientation governs. |
| Tests — `test-author` | DONE | `ses_f3228be41ffe7AC6Hn0C1SWbyu`; 8 nodes added (6 in `tests/test_pipeline.py`, 2 in `tests/test_cli.py`) + 8 `tests/traceability.json` node→LREQ entries; no fixture change. Node 5 reaches the `except` arm by replacing the `pipeline.discover_category` module global (lead-verified: a raising `transport.send` is swallowed to `PAGE_FAILED` at `collector_coveo.py:1890-1924`, so the plan's `_ExplodingCoveoTransport` could not reach it). Red run after authoring: **6 failed, 612 passed** (all 6 failures are missing-implementation; no collection/syntax error). |
| Implement — `impl-deep` | DONE | `ses_f321d78bdffe4f7GXXErqor57Q`; plan §7 E1–E8 applied to `src/niche_scout/pipeline.py` and `src/niche_scout/cli.py`. No test/artifact edited. |
| Lead verify | DONE | `python -m pytest -q` → **618 passed in 20.82s**; traceability valid (604 matrix nodes); import-boundary, scope-prohibition, secret checks valid; `ruff check` clean on the four changed files. Format caveat below. |
| Review — `spec-reviewer` | VERDICT: PASS | `ses_f32110eebffe1S32ZjczLOnukt`; no Blocker/Major, two Minors (below). It independently reran `pytest -q` → `618 passed`, the eight-node selection → `8 passed`, all four validators, `ruff check`/`ruff format --check`, and `git status/diff/log` (base `b9bde4e`). |
| Gate | PASSED | See gate table below (format caveat recorded). |

## Review (step 7)

| Item | Result |
|---|---|
| `spec-reviewer` | `VERDICT: PASS` — no Blocker, no Major. Two Minors, neither triggering a fix loop. |
| Minor 1 | Three **pre-existing** nodes (`tests/test_cli.py:200,206,215`) call `cli.main()` directly and so install a marked logging handler that no test removes; plan §7.2 E8's "monkeypatch `_configure_logging`" advice conflicts with plan §6/§9's "existing nodes unchanged". Impact benign: `_configure_logging` removes any prior marked handler before adding one, so no handler accumulates; node 7 asserts only on the marked set; full suite green. Recorded, not fixed (changing pre-existing nodes was out of the frozen plan). |
| Minor 2 | R2's `base is None` branch (`pipeline.py:2917-2935`) has no dedicated test node; plan §9 defines none and plan §8/F2 records the branch as unreachable through `_discover_all`. The DoD bullet is therefore established by reading, not execution. Recorded; a future plan could add a stub-repository unit node. |
| Notes | Pre-existing `None`→value substitutions survive on the scoring path (`pipeline.py` `discovery is None` sites); unchanged and unreachable in the completed path. Node strength: nodes 1 and 5 are the discriminating nodes; nodes 2 and 3 also pass pre-change (consistent with the 6-failure red state). |

## Gate — Chunk 15

Chunk 15 has no dependency-map §3 gate row; the gate is plan §10 (dispatch DoD + the in-scope
Chunk 10 bullets the remediation touches).

| DoD bullet (plan §10) | Result | Evidence |
|---|---|---|
| Full suite green with real counts | PASS | `python -m pytest -q` → `618 passed in 20.82s` (lead) and `618 passed in 23.32s` (reviewer, independent). |
| Four validators valid | PASS | Traceability `604 matrix nodes`; import boundaries valid; scope prohibitions valid (6 tokens); secret check valid. Outputs above and in the review. |
| `ruff format` and `ruff check` clean on changed files | PARTIAL (pre-existing) | `ruff check` on the four files: `All checks passed!`. `ruff format --check`: `cli.py`/`test_cli.py` clean; `pipeline.py` (7 hunks) and `test_pipeline.py` (4 hunks) report only **pre-existing** deviations on unchanged lines; no new format debt. The one new deviation (missing EOF newline in `test_pipeline.py`) was fixed by the lead. |
| Failure-path limitations per category, `category <repr>: (discovery_status\|identity_preflight_status)`; a discovery-failed category never reports `identity_preflight_status` | PASS | Nodes 1 and 3 (`tests/test_pipeline.py:1313-1414`) assert the exact tuples; node 1 asserts no `identity_preflight_status` for the `request_failed` categories; one limitation per category, no run-level string. |
| No fabricated discovery status on the `base is None` path; no new column/schema | PASS | `pipeline.py:2917-2935` writes `discovery.discovery_status.value` or raises `PipelineError(f"category {category!r}: category_scores")`; `DiscoveryStatus.REQUEST_FAILED` is no longer written there. No schema/DDL change (no `database.py` edit). Established by reading (Minor 2). |
| `_configure_logging` idempotent, exactly one handler on the `niche_scout` logger, invoked by `cli.main` | PASS | Nodes 7 and 8 (`tests/test_cli.py:967-1026`) pass; `cli.main` calls it first (`cli.py`). |
| Progress/diagnostic logging emitted, redaction-safe, no new discovery line contains `"enrichment"` | PASS | Nodes 4, 5, 6 (`tests/test_pipeline.py:1417-1531`) pass: per-category outcome on `niche_scout.pipeline`, except-arm class-name-only warning, run-level preflight line, run-status line; sentinels absent; no `"enrichment"` substring. |
| No new CLI flag and no new environment variable | PASS | Reviewer read the parser and env access as unchanged; scope-prohibition and secret validators valid. |

Supporting carried Chunk 10 gate bullets (unchanged, full suite green): a failed category does
not abort siblings; a failed preflight prevents enrichment; the failure path persists one
null-score limitation row per requested category; `CategoryStatus` remains a derived roll-up.

**GATE: PASSED** on every bullet except the literal `ruff format` cleanliness of `pipeline.py`
and `test_pipeline.py`, which is PARTIAL only because of **pre-existing** deviations on lines
this chunk did not touch (the same caveat Chunk 14 recorded). Two Minors are recorded and not
fixed; neither is a Blocker or Major.

## Deviations and limitations recorded

1. **Node 5 mechanism (plan §9 D-A).** The plan's `_ExplodingCoveoTransport` cannot reach `_discover_all`'s `except` arm — the adapter catches a raising `transport.send` inside its per-page `try` (`collector_coveo.py:1890-1924`) and returns `PAGE_FAILED`. The test instead replaces the `pipeline.discover_category` module global (`tests/test_pipeline.py:1279-1284,1473-1483`), restoring it in a `finally`. Node ID, markers, and matrix values unchanged; reviewer confirmed the seam is faithful.
2. **Lead one-byte formatting repair.** The `edit` tool did not preserve a final newline when `test-author` appended the Chunk 15 section; the lead normalized `tests/test_pipeline.py` to end with exactly one `\n` (verified by `endswith(b"\n")` and `ruff format --check`). No other byte changed (reviewer `git diff --numstat`: 343 insertions / 1 deletion).
3. **`git` unavailable.** `git` is denied by permission rule, so the lead could not run preflight `git status`, create a branch, or commit. The reviewer could run `git status/diff/log` and reports base `b9bde4e`, five modified files, two untracked Chunk 15 docs. **All Chunk 15 changes are uncommitted; a human must commit them.**
4. **Live Coveo root cause unresolved.** The next live run's `DISCOVERY_PAGE_FAILED` cause is still unavailable (no persisted column); the new per-category discovery log (status/conditions/issue codes) and the except-arm class-name warning are the diagnostic hook. Chunk 14's template/facet changes remain the unverified prime suspect.

## Lead verification (real output)

| Command | Real result |
|---|---|
| `python -m pytest -q` | `618 passed in 20.82s` (baseline 610 + 8 new nodes) |
| `python -m pytest -q` (red state after `test-author`) | `6 failed, 612 passed` — all six are missing-implementation (attribute/behavior absent), none a collection or syntax error |
| `validate_traceability` | `Traceability valid: 89 required/defined LREQ IDs mapped, 604 matrix nodes, 0 unmarked analytical tests outside exemption (3 exempted non-analytical nodes)` |
| `check_import_boundaries` | `Import boundaries valid for metrics.py, scoring.py` |
| `check_scope_prohibitions` | `Scope prohibitions valid: no retired token found ... (6 tokens checked)` |
| `check_secrets` | `Secret check valid: no literal credential found under src, tests, config, pyproject.toml; .gitignore ignores .env and no tracked .env exists` |
| `ruff check` (4 changed files) | `All checks passed!` |
| `ruff format --check` (4 changed files) | `cli.py` and `test_cli.py` clean. `pipeline.py` and `test_pipeline.py` report only **pre-existing** format deviations on unchanged lines; the one new deviation (missing trailing newline in `test_pipeline.py`) was fixed and is gone. |

**Verification method note.** The `bash` tool is denied for every agent in this session, so no git/pytest could be run through it. The lead ran all commands through the `background_process` tool (`python ...` is permitted), read the real captured output above, and separately confirmed the safety of the only manual repair: a one-byte trailing-newline normalization of `tests/test_pipeline.py` (the `edit` tool did not preserve a final newline), verified by `open(...,'rb').read().endswith(b'\n')` and `ruff format --check`.

**Git limitation.** `git` is denied (pattern `git *`), so the lead could not run `git status`, create a branch, or commit. All Chunk 15 changes are uncommitted on the current checkout; a human must commit them.
