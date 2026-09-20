# Chunk 4A — run log (Canonical populations and deterministic sampling engine)

Started 2026-09-20. Branch: `chunk-4A` (created from `main`). Tree clean at preflight.

## Preflight

| Check | Result |
|---|---|
| Working tree | clean (`git status` → "nothing to commit, working tree clean") |
| Branch | created `chunk-4A` from `main` |
| Prerequisite chunks | 0, 1, 2, 3. `Documents/runs/` contains only `chunk-05.md`; no `GATE: PASSED` run logs exist for 0–3 on this tree. Prerequisites are instead evidenced by the four `Status: VERIFIED` interface files `Documents/interfaces/chunk-00.md`, `chunk-01.md`, `chunk-02.md`, `chunk-03.md`. This is the same deliberate exception recorded for Chunk 5 (`Documents/runs/chunk-05.md`, Preflight table). Operator asked for end-to-end implementation, so proceeding on that documented basis. |
| Frozen plan | none exists yet — `Documents/plans/chunk-4A-*.md` absent. Planner dispatch required. |
| Target module | `src/niche_scout/sampling.py` is a 1-line stub ("Deterministic sampling will be added by later chunks.") |
| Test file | `tests/test_sampling.py` does not exist yet |

## Stage log

| Stage | Status | Evidence / notes |
|---|---|---|
| Preflight | DONE | See table above. |

## Resume 2026-09-20

Resumed on branch `chunk-4A` (HEAD `67ae2ec`). `git status` showed the only
untracked path was this run log, created by the interrupted preflight; no other
working-tree changes. Prerequisites re-confirmed: `Documents/interfaces/chunk-00.md`,
`chunk-01.md`, `chunk-02.md`, `chunk-03.md` all `Status: VERIFIED`. No frozen plan
exists for 4A, so the next stage is the planner dispatch. Operator scope for this
session: chunks 4A through 13 in dependency order.

## Plan stage — STOPPED awaiting human answers

Planner dispatched twice: first attempt died with an upstream malformed-tool-call
provider error; retry on the same session returned `STATUS: DONE`. It wrote
`Documents/plans/chunk-4A-canonical-populations-and-deterministic-sampling.md`
with `Status: DRAFT` and **eight open questions** (Q-1 … Q-8 in §12). The planner
labels them plan-level decisions with stated defaults, but Q-2 explicitly says the
plan cannot be frozen until a human picks (a) or (b), and Q-3/Q-6/Q-7/Q-8 need
rulings that change the contract or a file-ownership question. Per chunk-lead
procedure step 3 and project-rules "Scope discipline" (an open question blocks the
plan's freeze until a human resolves it), execution is halted here and the
questions are surfaced to the user verbatim. No plan commit, no test-author or
implementer dispatch has occurred.

## Plan stage — FROZEN

Human ruled 2026-09-20: all eight questions take the planner's recommended
options (Q-1 (a), Q-2 (a), Q-3 (a), Q-4 canonical, Q-5 (a), Q-6 digest order,
Q-7 caller order, Q-8 (b) local AST purity test, purity tool untouched).
Planner re-dispatched on the same session; it applied dated corrections, resolved
§12 in place, removed the conditional purity-tool row from §6, and set
`Status: FROZEN` (`Last amended: 2026-09-20`). Verified by direct read:
line 3 `Status: FROZEN`; §6 no longer lists
`src/niche_scout/tools/check_import_boundaries.py` as touched (remaining
mentions are the correction note and the explicit-prohibition list). Commit to
follow. Routing for 4A: test-author first, then impl-deep.

## Test stage — DONE (with one recorded DISPUTE)

`test-author` wrote `tests/test_sampling.py` and `tests/fixtures/sampling_fixtures.py`,
modified `tests/fixtures/__init__.py` and `tests/traceability.json`. 35 nodes
collected, 28 traceability entries, all 33 analytical nodes carry a marker and fail
only with `AttributeError: module 'niche_scout.sampling' has no attribute ...` (one
node, `test_sampling_module_imports_are_pure`, is the unmarked AST purity gate).
Lead verification: `pytest tests/test_sampling.py -q` → 33 failed, 2 passed, no
syntax or collection errors; `validate_traceability` → exit 0, "176 matrix nodes,
89 defined LREQ IDs" (was 148 nodes); full suite → 33 failed, 152 passed (the 150
pre-existing tests still pass). Fixture F byte string
`b"1.0.0\x003D/Characters\x0012345"` → `20c3b87100bb44ce9c198328ef98b894e0773afb4f03ff99ed3f7cc1439feebb`.

**DISPUTE (open, sent to planner for adjudication):** the test-author reports that
plan §9.3's LREQ lists and §9.4's example entries disagree for 3 nodes
(`test_repeated_selection_is_identical`, `test_no_randomness_module_used`,
`test_sampling_basis_and_census_flag`); it applied §9.3's fuller lists (which match
the validator's exact marker-set == matrix-entry requirement). The plan must be
reconciled so §9.3 and §9.4 agree. Does not block implementation: the marker sets
are the plan's own §9.3 assignment and the validator passes.

## Implementation stage — DONE

`impl-deep` replaced the stub with the pure engine in
`src/niche_scout/sampling.py` (554 lines, now 570 after the lead's lint refactor).
It reported only one resolved ambiguity: plan §5.3's literal `is_reduced iff
population_count < target_count` would make every census stratum non-reduced
(census target = N), contradicting §5.4/§8/§9.2 Fixture D and LREQ-SMP-090; it
applied `is_reduced = population_count < SAMPLE_PER_STRATUM`, which every stated
expected vector and the test agree with. Also, `select_run_sample` coerces raw
observation mappings so the run-level fixture tests pass unchanged.

**Lead verification (step 6):**
- `python -m pytest -q` → **185 passed** (150 pre-existing + 35 sampling).
- `python -m niche_scout.tools.validate_traceability` → exit 0, 176 matrix nodes,
  89 defined LREQ IDs.
- `python -m ruff format --check src/niche_scout/sampling.py` → "1 file already
  formatted"; `python -m ruff check src/niche_scout/sampling.py` → clean.
- Lead-read `sampling.py` and made three lint-only edits (pure refactor + `__all__`):
  `del run_id` instead of `_ = run_id` (F841), `start_index` extracted (E501), and
  an explicit `__all__`. Re-ran: 185 passed, sampling-only 35 passed, lint clean.
- Repo-wide `ruff check src/ tests/` reports **pre-existing** debt outside this
  chunk (81 src errors incl. an `F821 Undefined name CoveoPageOutcome` in
  `collector_coveo.py`, 277 total); `src/niche_scout/sampling.py` is clean. Fixing
  other chunks' files is out of scope; recorded, not fixed.

## Review stage — round 1 (VERDICT: FAIL), dispositions

`spec-reviewer` returned `VERDICT: FAIL` with 1 Blocker, 2 Majors, 2 Minors.
Lead rulings, evidence attached:

1. **Blocker (marker/traceability for 3 nodes) — NOT A DEFECT.** The reviewer's
   premise is that the validator's "carry no lreq marker" note means those nodes
   lack markers. Read `src/niche_scout/tools/validate_traceability.py`: the note at
   `:153`/`:175-178` is populated from `unmarked_tests = {node for node, markers in
   tests.items() if not markers}`, i.e. the *opposite* condition from
   `missing_nodes` (`:144-146`) and `marker_mismatch` (`:147-151`), which fire when
   markers are present. Both problems-filters are empty (validator exits 0), so the
   three named nodes demonstrably carry markers; the note is a mislabel of the
   no-marker set (it lists all 7 unmarked nodes, including the exempt AST gate and
   three long-standing `test_collector.py` nodes). Lead independently re-parsed
   `tests/test_sampling.py` with `ast` and compared to `tests/traceability.json`:
   zero marker/matrix mismatches; the only node with an empty marker set is
   `test_sampling_module_imports_are_pure`. Blocker dismissed with evidence.
2. **Major (census docstring vs `is_reduced`) — FIXED.** `build_strata`'s docstring
   now states `target_count == N`, `is_reduced = size < SAMPLE_PER_STRATUM`, and the
   LREQ-SMP-090/§9.2 Fixture D basis; the code was already correct per the Q-3 ruling.
3. **Major (stratum boundaries not frozen literals) — FIXED.** Added frozen literal
   tuples `EXPECTED_STRATA_N101/N105/N200/N24/N1` to
   `tests/fixtures/sampling_fixtures.py` and asserted them (and the independent
   formula restatement) in the three strata tests.
4. **Minor (`_project_records` permissive mapping coerce) — accepted, no change.**
   It is required by the frozen plan's run-level API and the committed fixture tests.
5. **Minor (literal `"1.0.0"` pin) — accepted, no change.** It is a deliberate pin of
   the frozen `SAMPLING_RULE_VERSION` value, not a duplication defect.

Lead re-verification after fixes: `pytest -q` → **185 passed**; sampling-only →
35 passed; `validate_traceability` → exit 0; `ruff check` on
`src/niche_scout/sampling.py`, `tests/test_sampling.py`,
`tests/fixtures/sampling_fixtures.py` → "All checks passed!"; `ruff format` → unchanged.

Also verified the reviewer's UNVERIFIED items: repo-wide `ruff check src/ tests/`
reports pre-existing debt (81 src errors incl. `F821 Undefined name CoveoPageOutcome`
at `collector_coveo.py:1871`; 277 total) outside this chunk; `check_import_boundaries`
is not run here, but `interfaces/chunk-00.md` §1 declares it Chunk 0's and the Q-8
ruling left it untouched.

## Review stage — round 2

`spec-reviewer` returned **`VERDICT: PASS`**. It independently re-derived the
round-1 Blocker as refuted (`pytest -q -m lreq` → 34 passed, 1 deselected; the
three named nodes pass under `-m lreq`; matrix entries match AST marker sets
exactly), confirmed both Majors fixed, and found no surviving Blocker or Major.
It also read the full `d987294→57628de` test diff and confirmed no assertion was
deleted, loosened, or retargeted. Three Minors remain (all outside the chunk or
cosmetic): (a) the Chunk-0 tool's mislabeled note text at
`tools/validate_traceability.py:175-178` — outside plan §6 scope, recorded for a
tooling pass; (b) `sampling.py` docstring citing `SAMPLE_PER_STRATUM` while the
code compares the `per_stratum_target` parameter (identical at defaults);
(c) an audit note that `enrichment_identity_keys` has no set-order dependence.
Reviewer UNVERIFIED `ruff` only because its sandbox denied the command; the lead
ran it (clean) at round 1 and again after the fix.

## Gate — Chunk 4A

Gate bullets walked from `Documents/requirements-dependency-map.md` §3 Chunk 4A
(lines 594–601), each with evidence (all commands re-run on `bce4e06`):

| Gate bullet | Result | Evidence |
|---|---|---|
| Repeated selection is identical | PASS | `tests/test_sampling.py::test_repeated_selection_is_identical` (`pytest -q` → 185 passed, 0 failed); `sampling.py:422-470` sorts on `(digest, asset_identity_key)` and `:240` on `(ordinal, is_none, key)` — no set/dict-order dependence |
| Changing the sampling-rule version changes the digest/selection | PASS | `test_digest_changes_with_rule_version`; `selection_digest` (`sampling.py:265-282`) joins `(rule_version, category, key)` with NUL before SHA-256; fixture `DIGEST_F_HEX` pinned at `sampling_fixtures.py:56`, cross-checked by the test's own hash of the 25 bytes |
| Populations 0, 1, 99, 100, >100 behave as specified | PASS | `test_census_population_sizes_zero_one_99_100`, `test_census_selects_all_assets`, `test_four_strata_boundaries_at_101`; census when `size <= 100` (`sampling.py:385`), `sample_fraction is None` iff 0 (`:518-522`) |
| Early, middle, and late discovery positions represented | PASS | `test_early_middle_late_positions_represented`, `test_sample_is_not_first_page_prefix`; all four strata select (`:398-413` loop) |
| Sample fraction distinct from stratum eligibility coverage | PASS | `test_sample_fraction_distinct_from_stratum_aggregates`; `sample_fraction` is one field (`CategorySamplingResult`, `sampling.py:163-172`); no coverage/coverage-like field and no `u_*`/overlap field exists |
| Pure result carries all values for later persistence; no SQLite claim | PASS | Structures at `sampling.py:69-208` carry `sampling_basis`, `sample_is_census`, `N_h`/`n_h`/target/boundaries, keys, per-member digests and ranks; no `sqlite3`/database import; reviewer confirmed no materialization |
| Property (certified by the dependency map in this section) | PASS | `tests/test_sampling.py::test_sampling_module_imports_are_pure` — AST check of imports and clock attributes; module imports only `hashlib`, `collections.abc`, `dataclasses`, `niche_scout.models` (`sampling.py:19-31`) |

Requirement closure and suite state:
- `python -m pytest -q` → **185 passed, 0 failed**.
- `python -m pytest tests/test_sampling.py -q` → **35 passed**; `-m lreq` → 34 passed, 1 deselected (the Q-8-exempt AST gate).
- `python -m niche_scout.tools.validate_traceability` → exit 0, 176 matrix nodes, 89 defined LREQ IDs (the "no lreq marker" note is the Chunk-0 tool's mislabel recorded above).
- `tests/traceability.json` holds **28** sampling nodes referencing 10 distinct LREQs: SMP-010, 020, 030, 040, 050, 060, 070, 080, 090 plus ARCH-020. `LREQ-SMP-080` is present as the plan's boundary case only (its primary owner is Chunk 4B).
- `python -m ruff format --check` → "3 files already formatted"; `python -m ruff check` on the chunk's three files → "All checks passed!".
- `git status` → "nothing to commit, working tree clean". Branch `chunk-4A`, commits `a2de9ab` plan, `d987294` tests, `15ee5f9` implementation, `57628de` review fixes, `bce4e06` review record.

**GATE: PASSED**

Open items carried forward (not gate failures): reviewer Minors (a)–(c) above;
the pre-existing repo-wide `ruff` debt outside this chunk (81 src errors incl.
`collector_coveo.py` F821) and the Chunk-0 tool note-text defect.
