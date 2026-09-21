# Chunk 9B — run log (Sensitivity, final evidence, and final rankability)

Started 2026-09-21. Branch `chunk-9B` created from `chunk-9A` tip (`8eab2fb`).
Tree clean at preflight (`git status --short --branch` → `## chunk-9A`).
`main` is at `153042d` and does **not** contain the Chunk 9A work; Chunk 9B depends
on Chunk 9A, so the branch was cut from the `chunk-9A` tip rather than `main`.

## Preflight

| Check | Result |
|---|---|
| Working tree | clean (`git status --short --branch` → `## chunk-9A`) |
| Branch | `chunk-9B` created from `chunk-9A` tip `8eab2fb` (9A not yet merged to `main`) |
| Prerequisite Chunk 9A | `Documents/runs/chunk-9A.md` ends `GATE: PASSED` (line 78); interface `Status: VERIFIED` |
| Prerequisite Chunk 8 | `Documents/runs/chunk-08.md` ends `GATE: PASSED` (line 70); interface `Status: VERIFIED` |
| Prerequisite Chunk 5 | `Documents/interfaces/chunk-05.md` → `Status: VERIFIED` (page-view semantics consumed) |
| Baseline suite | `python -m pytest -q` → **436 passed, 0 failed** |
| Frozen plan | none yet — planner dispatch required |
| Routing | test-author first, then `impl-deep` (chunk-lead routing table) |

## Stage log

| Stage | Status | Evidence / notes |
|---|---|---|
| Preflight | DONE | See table above. |
| Plan — dispatch 1 | BLOCKED | `chunk-planner` wrote the full 862-line plan (DRAFT) with 8 open questions in §12; commit pending until frozen. |
| Plan — advisory memo | DONE | Read-only `explore` (`ses_f3a53e1e1ffegEt1R6b8WxD9D0`) researched all 8 questions against the SRS, dependency map, frozen interfaces, and live source; returned cited recommendations for Q1–Q8 with confidence labels. |
| Plan — lead rulings R1–R8 | DONE | Rulings recorded below; all eight follow the memo. Re-dispatched `chunk-planner` to apply them and freeze. |
| Plan commit | DONE | `b7819ed` — `chunk-9B: plan` (frozen plan + this run log). |
| Plan — lead consistency fix | DONE | Plan §12 R2 named a non-existent test node; corrected in place before commit (the §9 marker table and `tests/traceability.json` block — which agree with each other — govern). |
| Tests — `test-author` dispatch 1 | FAILED (empty) | Returned an empty result and wrote no files (session `ses_f3a3b8f65ffepjqolTmgue07I5`). |
| Tests — `test-author` retry | FAILED (empty) | Same session resumed and one fresh session (`ses_f3a282c4bffevdEZxta4t60oxS`) both returned empty with no files written. |
| Tests — `test-author` scoped dispatch (fixtures) | DONE | Small-scope session (`ses_f3a1cde9dffeDUzY7d6pJzKWef`) wrote `tests/fixtures/sensitivity_fixtures.py` (1089 lines, data-only); the earlier empties were a task-size/step failure, not a provider outage. Raised 3 plan-vector inconsistencies. |
| Plan — vector corrections | DONE | Lead corrected the frozen plan in place with dated notes: the §9 top-3 vector's false "every candidate breaches displacement" wording; the displacement vector's self-contradictory equal-top-3-set sentence (now `T3b=T3d={c1,c2,c3}`, `T3c={c8,c1,c2}`); the weak vector's "coverage 0.60 → WEAK" claim (a sufficient count with coverage ≥0.50 is MODERATE per SRS §9.2). |
| Tests — `test-author` scoped dispatch (test file) | DONE | Session `ses_f39fd7016ffefu4dFJndiU7O5K` wrote `tests/test_scoring_sensitivity.py` (39 nodes), updated `tests/fixtures/__init__.py`, and appended 39 entries to `tests/traceability.json`. Node count corrected to **39** (the plan §9 table and JSON block both have 39 rows; my earlier 38 was an estimate error). |
| Tests — lead verification (step 4) | DONE | `python -m pytest tests/test_scoring_sensitivity.py -q` → 1 collection ERROR: `ImportError: cannot import name 'CategorySensitivityRank' from 'niche_scout.scoring'` (required missing-implementation shape; module parsed with no syntax error). `python -m pytest tests -q --ignore=tests/test_scoring_sensitivity.py` → 436 passed. `validate_traceability` → valid, 461 matrix nodes. Node/entry counts queried: `^def test_` → 39; `test_scoring_sensitivity.py::` in traceability → 39; names match 1:1. `ruff check` → "All checks passed!"; lead ran `ruff format` (2 files reformatted, whitespace only). |
| Tests commit | PENDING | |
| Implementation — `impl-deep` dispatch | PENDING | |

### Plan rulings R1–R8 (Chunk 9B)

SRS is silent or ambiguous on the exact conjunction/boundary in several items; these are
lead rulings, each grounded in cited SRS/dependency-map/interfaces text, not invented
formulas.

- **R1 (`sensitivity_warning` type) — Q1 option (a).** Chunk 9B adds
  `SensitivityDiagnostics.warning: bool | None`; the frozen Chunk 0
  `SensitivityResult.warning: bool` is left byte-identical. Chunk 10 persists from
  `SensitivityDiagnostics.warning` (SRS §6.5 line 607; dependency-map §6.3 line 1161
  "`null` … not `false` or zero"; `models.py:507` `bool | None`).
- **R2 (warning with 1–2 candidates) — Q2 option (a).** The LREQ-SEN-030 condition is a
  disjunction; displacement is computable whenever comparable ranks exist. Per-category
  `warning` is `None` only when there are **zero** base candidates; otherwise `bool`.
  Record explicitly that the top-3 clause is *inapplicable* (not `false`) when
  `top_3_stability is None` (dependency-map §6.3 line 1160).
- **R3 (reference-set size) — Q3 option (a).** `reference_set_size = run_category_count
  - 1` (the leave-one-out peer count; interfaces/chunk-08.md:168), passed explicitly;
  the displacement threshold is `max(3, 0.25 * reference_set_size)`. Caller obligation:
  every supplied per-category `reference_size` must equal the explicit
  `reference_set_size`, else `ValueError`.
- **R4 (which rows carry the top-3 warning) — Q4 option (a).** Each base candidate's
  `warning = (top_3_stability is not None and top_3_stability < 2/3) or its own
  displacement breach`; non-candidates are `None`; the run-level warning is the OR over
  candidates (SRS §9.3 line 1077; §1.2 null discipline).
- **R5 (missing pure contract) — Q5 option (a).** Chunk 9B adds a pure
  `SampleEvidenceFacts` dataclass in `scoring.py`; census/population facts mirror
  `CategorySamplingResult` / the persisted `category_scores` columns, and the three
  `usable_*_sample_count` values mirror `CategoryRawMetrics`. It must not import
  `sampling`; `0` census is an explicit zero (SRS §7.3 lines 769–771).
- **R6 (evidence-grade conjunction) — Q6.** Adopt the plan §5.4 precedence with:
  "verified discovery" = `discovery_filter_verified is True` **and** `discovery_status
  is DiscoveryStatus.COMPLETE`; `sensitivity_warning is None` is **not** acceptable for
  `strong`; the reference condition is `run_category_count >=
  STRONG_REFERENCE_CATEGORY_COUNT` (= 21). `moderate`/`weak`/`insufficient` follow the
  SRS §9.2 table (lines 1049–1052).
- **R7 (rankability on a null warning) — Q7 option (b).** For a pre-sensitivity
  `RANKABLE` category, `sensitivity_warning is None` yields final `PROVISIONAL`
  (conservative; LREQ-EVD-040 line 1007 requires the thresholds *pass*). Under R2/R3
  this branch is unreachable for a base-rankable category (run ≥ 21 ⇒ ≥ 1 candidate),
  but the rule stays defined.
- **R8 (`ranking_sensitivity_json` shape) — Q8 option (a).** The JSON carries only the
  ranked candidate set (`ranked_categories`, per-policy scores/ranks, displacements) plus
  the explicit empty/insufficient-candidate status; non-candidates remain visible via
  their own `category_scores` rows with null rank/displacement/sensitivity fields
  (SRS §9.3 line 1077; dependency-map §6.3 line 1162).

Two plan-text corrections the planner must apply: (i) the `SampleEvidenceFacts`
docstring sources census/population from `CategorySamplingResult`/the persisted row, not
`CategoryRawMetrics`; (ii) add the R3 caller obligation that per-category `reference_size`
values agree with the explicit `reference_set_size`.