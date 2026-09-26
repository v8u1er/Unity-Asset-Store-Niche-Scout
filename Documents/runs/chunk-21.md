# Chunk 21 — run log

Labeled post-completion remediation (Chunks 14–20 pattern): no
`requirements-dependency-map.md` §3/§4 gate row, no new interface file unless the
plan finds one is forced, no downstream chunk. Scope is the quality-component
usability findings from the 2026-09-25/26 live-run audit of
`run-2026-09-25T17:59:00.573213+00:00`.

Branch: `chunk-21` (created from `main` at `ebd3d3a chunk-20: gate passed`).
Routing: TBD by plan (expected `test-author` first, then `impl-deep`, then
`spec-reviewer`).

## Stage 0 — Preflight

- `git status --short` → clean; `HEAD` = `ebd3d3a chunk-20: gate passed`.
- Prerequisite done: `Documents/runs/chunk-20.md` → `GATE: PASSED` (line 61).
- Frozen surfaces consumed unchanged: `Documents/interfaces/chunk-7A.md`,
  `chunk-7B.md`, `chunk-10.md` (Status: VERIFIED).

## Audit findings carried into the dispatch brief

Labels: **read** = opened this session; **counted** = queried against
`runtime/niche_scout.sqlite3`; **unverified** = not re-checked.

- **F1 (read/counted).** Latest run scores all 8 categories `not_rankable`;
  `rankability note` is `missing components: C, Q` for icons/humanoids/land and
  `missing components: Q` for the other five. Q null for all 8 because
  `quality_stratum_eligibility_coverage < MIN_REQUIRED_COMPONENT_COVERAGE (0.50)`
  at the frozen `MIN_USABLE_SAMPLES_PER_STRATUM (5)`; max is humanoids `0.4997`.
- **F2 (counted).** Enumerated coverage grid (latest run, `sample_members` ⋈
  `enrichment_observations`, `N_h` from `stratum_start/end_ordinal`): the binding
  lever is `min_usable_samples_per_stratum` (M), not `quality_min_rating_count`.
  At `M=1` and `count>=3 & average>0`: icons 0.5000, stone 0.4974, mammals
  0.4995, humanoids 1.0, trees 0.25, land 0.2499, orchestral 0.2494, vfx 0.7511
  — 3 clear the gate, only vfx has all four components. trees/land/orchestral
  have zero rated assets in strata 1–3, so coverage is pinned at ~0.25 for any Q
  and any M. At `M=5`, no Q value changes any category's coverage.
- **F3 (read/counted).** `quality_min_rating_count` is **inert**: documented at
  `metrics.py:766-773, 793-798`; enforced only by the module constant in 7A
  `quality_observation_eligibility` (`metrics.py:322`); `pipeline.py:3415` writes
  the config value into an unused field. This contradicts SRS §14 marking it
  configurable (`Yes`). `min_usable_samples_per_stratum`, `quality_min_eligible_assets`,
  `min_age_days_for_rate`, `recent_window_days` are consumed (`pipeline.py:3412-3416`).
- **F4 (counted).** `rating_average = 0` occurs only at `rating_count ∈ {0,1,2}`
  (105 rows with `count>=1`; 0 rows with `count>=3`). SRS §7.5 accepts
  `rating_average ∈ [0,5]`. Whether `average=0` means "unrated" or a real
  0-star rating is unresolved (live capture `.scratch/chunk18-capture.json`
  `341506`: `average 0, count 1`).
- **F5 (unverified).** Whether vfx becomes `provisional` (LREQ-EVD-030) once Q is
  available is derived from the SRS, not executed through `scoring.py`.

## Decisions surfaced to the human (may block plan freeze)

1. May `min_usable_samples_per_stratum` drop 5 → 1? Shared by D/R/Q.
2. Wire `quality_min_rating_count` to match SRS §14, or amend SRS §14 to `No`?
   (May force a frozen 7A interface change.)
3. `rating_average = 0` semantics: "no rating" (SRS §7.5 revision) vs real zero.
4. Accept Q-unavailable for trees/land/orchestral, or a sampling-design revision
   (`SAMPLE_STRATA`/`SAMPLE_PER_STRATUM`)?
5. Expand `config/categories.json` toward 21 (rankable needs ≥21), preserving
   its captured-artifact provenance?

## Human rulings (2026-09-26, adopted from the independent assessment)

1. **Q1 → (b).** Keep the SRS §14 default `MIN_USABLE_SAMPLES_PER_STRATUM = 5`; an
   operator may override per run via CLI/TOML. No code scope. A default change is an
   SRS §14 revision and is deferred.
2. **Q2 → (a), authorized.** Wire `quality_min_rating_count` as a **default-preserving,
   keyword-only additive** parameter. **Explicit authorization given for the additive
   frozen-interface change** to `Documents/interfaces/chunk-7A.md`. Justification is
   conformance with SRS §14 line 1296, not usability.
3. **Q3 → (a), deferred.** Treat `rating_average == 0` as "unrated" (require `> 0` for
   quality eligibility). This is an SRS §7.5 revision, behaviorally inert at the frozen
   minimum 5; **must not block chunk-21**. Interim guard recorded: never set the rating
   minimum below 3.
4. **Q4 → (a).** Accept Q-unavailable for trees/land/orchestral; report with Appendix C
   vocabulary. No sampling revision.
5. **Q5 → (c).** Category expansion to ≥21 is a separate chunk requiring a fresh
   `ec_category` capture (the committed capture is hash-verified by
   `tests/test_live_endpoint_compatibility.py:298-311`) plus taxonomy work.
6. **Q6 → re-plan narrowly.** Do not bundle. Chunk-21 is re-planned to exactly one
   authorized item: **Q2(a)**. Not left as a DRAFT — BLOCKED plan.

Record corrections carried forward (from the assessment):

- F2's "at M=5 no Q value changes coverage" holds **only because the knob is inert**;
  state that precondition.
- F1's `["C","Q"]` for icons/humanoids/land is a **separate truncation defect**
  (breadth at the 2000 cap), not a quality defect.
- F4's `105` is the **latest-run** subset; the all-runs total is 210 rows.

## Stages

| # | Stage | Status | Notes |
|---|---|---|---|
| 0 | Preflight | DONE | Tree clean at `ebd3d3a`; branch `chunk-21` created. |
| 1 | Plan | BLOCKED | `chunk-planner` authored `Documents/plans/chunk-21-quality-component-usability-remediation.md` as **DRAFT — BLOCKED**. Every candidate scope item is gated by an unresolved human ruling, so no signature, file, or test could be frozen. Stopped per `AGENTS.md` (surface, never resolve). |
| 1b | Re-plan | BLOCKED | `chunk-planner` re-dispatched to freeze the single item Q2(a). The plan was rewritten to S-A but cannot freeze: end-to-end wiring requires additive keyword-only parameters on `finalize_stratum_counts` / `finalize_enrichment` (frozen public contract in `Documents/interfaces/chunk-6B.md` lines 274–316; `pipeline.py:1730`) and falsifies the frozen INERT note in `Documents/interfaces/chunk-7B.md` (lines 106–109). Only the `chunk-7A.md` change was authorized. Stopped per procedure. |
| 1c | Re-plan | DONE | Independent assessment adopted as ruling **(c)**; plan rewritten and **FROZEN** as a single-concern config-vs-constant reconciliation (`Documents/plans/chunk-21-quality-component-usability-remediation.md`). Committed `412ce49 chunk-21: plan`. |
| 2 | Tests first | DONE | `test-author`; five `tests/` files, committed `6757a58 chunk-21: tests`. Lead re-ran: `python -m pytest -q tests/test_validation.py tests/test_enrichment.py tests/test_metrics.py` → **6 failed, 129 passed**; failures are missing-implementation (`TypeError: unexpected keyword argument` ×5, one `assert 0.0 == 1.0`) — no syntax/collection errors. `validate_traceability` → 645 matrix nodes (six added keys). |
| 3 | Implement | DONE | `impl-deep` (S1–S3) + `chunk-planner` (S4 interface docs + plan amendment). `src/niche_scout/metrics.py`, `src/niche_scout/pipeline.py`, four interface docs, plan amended. One accepted forced deviation (below). |
| 4 | Verify (lead) | DONE | See "Gate evidence". Lead re-ran every command; all pass. |
| 5 | Review | DONE | `spec-reviewer` pass 1: `VERDICT: FAIL` (1 Major record gap + 2 Minors; no code defect); fixed by adding the "Gate evidence" section (`889e1a1 chunk-21: review fixes`). Pass 2: **`VERDICT: PASS`**, no findings. |
| 6 | Gate | DONE | Every plan §9 DoD-1…DoD-6 bullet has evidence in "Gate evidence"; reviewer independently reproduced pytest 664, the four validators, and `ruff check`. **GATE: PASSED.** |

## Accepted deviation (recorded 2026-09-26)

`metrics.quality_raw`'s `METRIC_REASON_ELIGIBLE_SET_TOO_SMALL` branch now returns the
accumulated `usable_sample_count` / `eligible_population_count` instead of a forced `0`.
Required so check B's 7B count equals the finalized count under
`min_usable_samples_per_stratum=1` (the committed §8.2 tests enforce it); default-preserving
because at `MIN_USABLE_SAMPLES_PER_STRATUM=5` the guard fires only when no stratum is usable,
so the values are true zeros. Consistent with frozen `chunk-7B.md` §4.2 and SRS §6.5 line
637. It extends Chunk 20's two-path fix to the third path. Plan §5/§7 amended to name
`quality_raw`; recorded as an accepted deviation.

### Blocker question (planner, verbatim, 2026-09-26)

1. Chunk-21 S-A requires passing `config.quality_min_rating_count` into
   `pipeline.py:1730`, which needs additive default-preserving keyword-only parameters
   on `finalize_stratum_counts` (`pipeline.py:1650–1659`) and `finalize_enrichment`
   (`pipeline.py:1901–1909`), both frozen public contract in
   `Documents/interfaces/chunk-6B.md` (lines 274–283, 308–316); and making
   `CategoryMetricInput.quality_min_rating_count` live falsifies the frozen INERT note in
   `Documents/interfaces/chunk-7B.md` (line 77 comment and lines 106–109). The human
   authorized only the `chunk-7A.md` additive change. Options: (a) extend authorization
   to the analogous additive keyword-only changes and permit updating `chunk-6B.md` and
   the `chunk-7B.md` INERT note, so S-A freezes whole; (b) formally drop the brief's
   `pipeline.py:1730` requirement and scope S-A to the metric surface only, accepting
   that a non-default minimum then changes coverage/eligibility but not the persisted
   `u_quality_h` / `usable_quality_sample_count`; (c) other ruling. (SRS §14 line 1296;
   LREQ-MET-090; LREQ-SMP-080; chunk-20 plan §11.3 precedent that adding a parameter is a
   frozen-interface change.)

**Lead verification of the blocker:** confirmed by reading `pipeline.py:1650–1741` and
`Documents/interfaces/chunk-6B.md:274–316`. Note the same wall already exists for
`min_usable_samples_per_stratum` / `min_age_days_for_rate` (the chunk-20 recorded Minor
"config-vs-constant split"); Q2(a) would resolve the rating knob only.

## Planner result (verbatim, 2026-09-26)

`STATUS: BLOCKED`. Questions Q1–Q6:

1. **Decision 1** — may the SRS §14 default `MIN_USABLE_SAMPLES_PER_STRATUM` drop 5 → 1?
   (SRS §14 line 1291 configurable `Yes`; default `5`; LREQ-MET-090 §7.5 lines 817–833;
   F2 says M is the binding lever.) Options: (a) change the default (SRS §14 line 1291
   revision + `models.py:46`, and the pinned value in `tests/test_contracts.py`);
   (b) keep 5 and use an operator per-run config override (no code change, so no chunk-21
   code scope for F1/F2); (c) defer to a separate policy chunk. A behavior cannot be
   chosen here.
2. **Decision 2** — wire `quality_min_rating_count` to match SRS §14, or amend SRS §14 to
   `No`? (SRS §14 line 1296 `Yes`; LREQ-MET-090 §7.5 line 811; F3; `metrics.py:766-773,
   793-798, 322`; frozen `interfaces/chunk-7A.md` §4 `quality_observation_eligibility` has
   no rating-minimum parameter.) Options: (a) wire it, which forces a frozen-interface
   change — an additive keyword parameter on 7A's `quality_observation_eligibility` plus an
   interface-file update, which the planner may not author without explicit authorization;
   (b) amend SRS §14 line 1296 to `No` (a human SRS edit); (c) leave it inert and record
   the inconsistency. Which path, and if (a), is a frozen 7A interface change authorized?
3. **Decision 3** — `rating_average = 0` semantics: "no rating" (SRS §7.5 revision) vs a
   real 0-star rating? (SRS §7.5 lines 809–811 accept `[0,5]`; F4 shows average=0 only at
   rating_count in {0,1,2}.) Options: (a) treat 0 as "unrated" (SRS §7.5 revision);
   (b) treat 0 as a real 0-star rating (no change); (c) defer. Note: under the frozen
   `QUALITY_MIN_RATING_COUNT = 5` this is behaviorally inert because every average=0 row is
   already ineligible via `_classify_rating_count` (`metrics.py:322, 616-618`); it becomes
   live only if Q1/Q2 lower the rating minimum.
4. **Decision 4** — accept Q-unavailable for trees/land/orchestral, or make a
   sampling-design revision? (F2: those categories have zero rated assets in strata 1–3,
   coverage pinned ~0.25; LREQ-SMP-030 §5.1 lines 445–447 require a new sampling-rule
   version and SRS revision to change `SAMPLE_STRATA`/`SAMPLE_PER_STRATUM`.) Options:
   (a) accept Q-unavailable for those categories; (b) revise the sampling design (SRS
   revision + new sampling-rule version); (c) defer to a separate chunk.
5. **Decision 5** — expand `config/categories.json` toward 21 (rankable needs ≥ 21 per
   SRS §9.1 lines 1013–1014), preserving its captured-artifact provenance? Options:
   (a) yes, expand the config artifact; (b) no, keep the captured set; (c) handle in a
   separate chunk.
6. **Cross-cutting** — is any of Q1–Q5 within chunk-21's intended scope at all, or should
   chunk-21 remain a diagnosis-only record and the remediation be deferred until a policy
   ruling lands? (Determines whether this plan is unblocked by one ruling or superseded.)

`DISPUTES: none`. `UNVERIFIED`: F5 (vfx → `provisional` via LREQ-EVD-030 not executed
through `scoring.py`); the live-run F1/F2/F4 counts were carried from this run log, not
re-queried by the planner; the `scoring.py` null-Q → `not_rankable` path and exact
`MIN_REQUIRED_COMPONENT_COVERAGE` application site were not re-read; the
`tests/traceability.json` mapping for the cited quality nodes was not re-read.

## Assessment verification and adopted ruling (2026-09-26)

A second independent assessment disputed the record's mechanism. **Lead re-read the
cited code and confirms it:**

- **The "check B would fire" claim in this run log and in `chunk-20.md:112–116` is
  wrong.** Check B builds `CategoryMetricInput` with only `category`,
  `scoring_cutoff_utc`, `page_view_semantics_status`, `strata`
  (`pipeline.py:2190–2196`), so all thresholds default to the module constants; check A
  hardcodes `MIN_USABLE_SAMPLES_PER_STRATUM` (`pipeline.py:2116/2128/2140`); and
  `finalize_enrichment` calls `finalize_stratum_counts` with no threshold args
  (`pipeline.py:1997–2002`). Constant-vs-constant agrees, so a non-default config is
  **silently uncaught**, not flagged. The assessment is correct and this supersedes the
  earlier statement.
- The config-vs-constant split is real for **M** and **min_age** (`metrics.py:620–626`
  vs `metrics.py:1013–1016`); `recent_window_days` is not window-gated in finalize;
  `quality_min_eligible_assets` is already consistent (`metrics.py:1572`).
- The assessment also notes `assert_finalization_consistency` is itself frozen in
  `chunk-6B.md:342` — a third signature, so a whole fix touches three frozen 6B
  signatures plus the assertion internals.

**Adopted ruling (c).** Re-scope chunk-21 from "wire the rating knob" to a single
**config-vs-constant reconciliation** concern: one policy-parameter source feeding both
the finalization path and `CategoryMetricInput`, with the consistency assertion
comparing like-for-like, covering `min_usable_samples_per_stratum`,
`min_age_days_for_rate`, and `quality_min_rating_count`. This supersedes Q2-only (S-A).
The assessment's "separate dedicated chunk" is executed inside chunk-21 to avoid branch
proliferation; numbering is cosmetic and the diagnosis stays here.

**Authorization recorded.** Adopting (c) authorizes the additive frozen-interface updates
to `Documents/interfaces/chunk-6B.md`, `chunk-7A.md`, `chunk-7B.md` (INERT note), and
`chunk-10.md` that the reconciliation requires, and the `models.py` policy carrier if the
plan chooses one. The plan must name every frozen signature it changes.

**Correction owed elsewhere.** `Documents/runs/chunk-20.md:112–116` ("would flag check B")
is inaccurate per the reading above; it is noted here rather than edited (chunk-20 is a
closed record; change-control is the human's).

## Gate evidence (plan §9 DoD-1…DoD-6)

Lead-run, verbatim, on branch `chunk-21` at `d3b81bc chunk-21: implementation`.

- **DoD-1 (offline suite).** `python -m pytest -q` → **664 passed in 23.05s**.
- **DoD-2 (validators).** All exit 0, verbatim:
  `python -m niche_scout.tools.validate_traceability` → "Traceability valid: 89
  required/defined LREQ IDs mapped, 645 matrix nodes, 0 unmarked analytical tests outside
  exemption (3 exempted non-analytical nodes)";
  `check_import_boundaries` → "Import boundaries valid for metrics.py, scoring.py";
  `check_scope_prohibitions` → "Scope prohibitions valid: no retired token found … (6
  tokens checked)";
  `check_secrets` → "Secret check valid: no literal credential found under src, tests,
  config, pyproject.toml; .gitignore ignores .env and no tracked .env exists".
- **DoD-3 (lint/format).** `python -m ruff check src/niche_scout/metrics.py
  src/niche_scout/pipeline.py` → "All checks passed!". `ruff format --check` → metrics.py
  clean; `pipeline.py` reports **8 hunks that pre-exist on `main`** — verified byte-exact:
  `git show main:src/niche_scout/pipeline.py` written to `.scratch/` as bytes (via
  `subprocess`, byte-exact) and `ruff format --check` on that copy reports the same 8
  hunks at shifted line numbers; none lies in this chunk's changed hunks. Not a new
  violation.
- **DoD-4 (traceability reconciliation).** `tests/traceability.json` diff is **+21/−0**
  (six added node-ID keys, no key changed or removed); reused node IDs byte-identical.
  `git diff --name-only ebd3d3a..d3b81bc -- src tests` → `src/niche_scout/metrics.py`,
  `src/niche_scout/pipeline.py`, and the five `tests/` files from commit `6757a58`.
- **DoD-5 (prohibitions).** `git diff --stat ebd3d3a d3b81bc -- src/niche_scout/models.py
  src/niche_scout/config.py src/niche_scout/scoring.py Documents/SRS-lean.md
  tests/test_contracts.py` → empty. No import, purity, clock, or dependency change. No
  live network.
- **DoD-6 (records).** Plan (FROZEN + accepted-deviation amendment) and this run log
  updated; residual obligations stay open.

## Review findings (spec-reviewer, first pass)

`VERDICT: FAIL` — one **Major** and two **Minors**, no code defect. The Major was a record
gap (this run log lacked the §9 "Gate evidence" section the stage table deferred to); it is
resolved by the section above.

- **Minor (format-only, accepted).** `tests/test_validation.py:1859-1861, 1881-1883`: two
  new `assert (` blocks `ruff format` would collapse to one line; same pattern as the
  pre-existing flagged line 1826. Recorded, not changed (tests are `test-author`'s;
  no loop).
- **Minor (wording, accepted).** `Documents/interfaces/chunk-6B.md:306-310` and
  `pipeline.py:1682-1686`: "forwarded to `stratum_is_usable`,
  `age_normalized_page_view_index`, and `quality_observation_eligibility` respectively"
  omits that `min_age_days_for_rate` also reaches the quality verdict through
  `quality_observation_eligibility`. Recorded, not changed (no loop).
- **UNVERIFIED (reviewer).** Pre-change red state not independently re-executed (6 failed
  / 129 passed) — the environment denies the needed commands; verified by inspection.

### Second pass (after fix round 1)

`VERDICT: PASS` — no Blocker, Major, or Minor. The reviewer independently reproduced
`pytest` 664 passed, the four validators (exit 0, matching text), `ruff check` on both
changed source files ("All checks passed!"), and the `+21/−0` six-key traceability diff;
confirmed `889e1a1` touches only the run log and that tests are unchanged since `6757a58`;
and mapped the 8 `pipeline.py` format hunks outside the chunk's changed lines.

**GATE: PASSED.**