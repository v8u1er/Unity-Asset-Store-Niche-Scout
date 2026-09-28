# Chunk 24 — run log (Systematic strata sampling-rule revision)

Started 2026-09-28. Branch `chunk-24` off `main` at `aa6eb46` (`chunk-23: gate passed`).
Remediation chunk: no dependency-map §3/§4 row (chunk-14 precedent). Registration = plan +
run log + branch. Next free id confirmed by `chunk-23.md:60-62` (which explicitly reserved
"chunk-24" for the deferred sampling-rule revision).

## Preflight

| Check | Result |
|---|---|
| Working tree | clean at start (`git status` → nothing to commit) |
| Prior gate | Chunk 23 `GATE: PASSED` (`aa6eb46`) |
| Branch | `chunk-24` created |
| Existing artifacts | no `Documents/plans/chunk-24*`, no `Documents/runs/chunk-24*` |
| Routing (lead-chosen; remediation chunk) | `chunk-planner` → `test-author` (tests-first, yes) → `impl-deep` → `spec-reviewer` → lead gate |

## Operator authorization (2026-09-28)

Verbatim operator messages in this session:

1. "is there a sound scientific statistically better logical way to form the strata so this
   distribution that no review assets are always towards the latest strata is remedied?"
2. "ok, i want the best clean effective scientifically sound change, that suits the project
   goals, i dont care if more work is necessary or srs needs revision. maybe dispatch your
   agents for thorough analysis if questions remain, and set the path forward"
3. "go ahead"

Message 3 is the response to the lead's fork request (support-rule choice). The operator
did not name the fork explicitly; the lead proceeds with the **recommended** option and
records it here as the operative, correctable decision (chunk-23 surface-naming precedent).

## Design decision (frozen for planning)

- **D1 — partition.** Replace the four *contiguous* ordinal strata (`LREQ-SMP-050`) with a
  **systematic (interleaved) partition** over the same stable discovery ordinal
  (`LREQ-SMP-020`): stratum `h = (i - 1 + offset) mod SAMPLE_STRATA` for 1-based ordinal `i`,
  where `offset` is a deterministic, persisted per-category constant derived from
  `sha256(sampling_rule_version, category) mod SAMPLE_STRATA`. Within-stratum selection
  (`LREQ-SMP-060`), census behavior (`LREQ-SMP-040`), and reduced-stratum behavior
  (`LREQ-SMP-090`) are unchanged.
- **D2 — support rule.** Lower the `MIN_USABLE_SAMPLES_PER_STRATUM` default from 5 to 1
  (`SRS §14:1291`; the constant stays "Configurable = Yes"). The coverage formula is
  unchanged (`sum(N_h/N)` over strata with `u_h >= MIN_USABLE`, `LREQ-MET-090`). The pooled
  eligible gate (`usable_quality_sample_count >= QUALITY_MIN_ELIGIBLE_ASSETS`) already
  exists in the SRS (§7.5) and in `metrics.py`; it remains the evidence-strength guard.  Rationale: with `n_h = 25` and a measured eligible rate `p ≈ 0.185`, `E[X_h] = 4.6 < 5`,
  so a floor of 5 makes each stratum a coin flip and is miscalibrated for any partition.
- **D3 — versioning/representation.** `SAMPLING_RULE_VERSION` bumps; the persisted
  `stratum_start_ordinal`/`stratum_end_ordinal` interval is not expressible for an
  interleaved set and needs an `(offset, stride)` representation → interface + likely
  `SCHEMA_VERSION` change (chunk-23 precedent).

## Grounded evidence carried into the dispatch (labels: read / counted / model)

- Discovery order is the only pre-enrichment covariate; rating/date/price are phase-2 or
  excluded by `LREQ-EXT-040`. Contiguous strata become popularity bands; measured per-stratum
  eligible counts collapse to the head (`[18,1,0,0]`, `[12,0,0,0]`, `[23,16,5,2]`). Q coverage
  `< 0.50` for 11/24 at floor=1 and 22/24 at floor=5 in the latest run (read, lead).
- Independent binomial model (`n_h=25`, `p≈0.185`): interleaved + floor=1 → ~24/24 clear
  coverage; floor=5 → ~16/24 (model, explore agent; analytic, not simulated).
- `metrics.py` has no contiguity/equal-size assumption; only `sampling.py`
  (`build_strata`, `select_stratum_members`) and the persisted interval contract encode it
  (read, explore agent).
- Blast radius (read-derived counts, not scripted): 72 distinct pytest node IDs across the 8
  affected LREQ keys; `LREQ-SMP-080` alone = 45 distinct nodes. Interfaces 4A/4B/7B/11,
  `database.py` DDL + `STRATUM_STATISTICS_KEYS` + `SCHEMA_VERSION`, `report.py`, SRS §1.4/§5.1/
  §6.5/§14, `models.py:27`. (explore agent; programmatic count still owed at verification.)

## Open items recorded (not silently resolved)

- Whether the support/evidence re-baseline (`MIN_USABLE` 5→1 changes usable counts and may
  shift evidence grades) is one chunk or must split into a follow-on `chunk-25`. Decision
  delegated to the planner; lead prefers a reviewable split if the re-baseline is large.
- SRS text edit ownership: the planner does not edit the SRS; the plan must enumerate the
  exact edits and assign their application to the implementation stage under this operator
  authorization (chunk-23 precedent).

## Stage log

| Stage | Status | Session / evidence |
|---|---|---|
| Preflight (lead) | DONE | git clean; branch `chunk-24`; this log |
| Plan — `chunk-planner` | DONE | First pass `ses_f1883d0f7ffe0VYrixQ3ZxYUX0` hit its step cap with 3 questions; operator answered A1-A3. New session `ses_f1874bac0ffeHCQuzjKoFZb9B6` wrote the 577-line plan; a follow-up froze it. Committed `3214668` (draft), `3387037` (frozen). |
| Tests — `test-author` | INCOMPLETE (stopped) | `ses_f18651be7ffeBeVkupX832LkzQ` hit its step cap mid-edit; `test_sampling.py` + `sampling_fixtures.py` partially migrated; scope still incomplete |
| Implement — `impl-deep` | PENDING | — |
| Review — `spec-reviewer` | PENDING | — |
| Gate (lead) | PENDING | — |

## Planner outcome — BLOCKED (2026-09-28)

The planner read the run log, SRS §1.4/§5/§6.3-6.5/§7.2-7.5/§9/§10/§11/§13/§14,
interfaces 4A/4B/7B/11, `sampling.py` (full), `models.py`, `database.py`, `report.py`,
`pipeline.py`, `config.py`/`default.toml`, and parts of the test/fixture set, but reached its
step cap before writing `Documents/plans/chunk-24-systematic-strata.md`. No file was created
and no git operation was run. It returned BLOCKED with three questions (see below). It also
recommended a **split**: chunk-24 = D1+D3 (partition rule, `(offset, stride)` representation,
`SAMPLING_RULE_VERSION`/`SCHEMA_VERSION` bumps, SRS partition edits); chunk-25 = D2
(`MIN_USABLE` 5→1 and the coverage/evidence re-baseline), on the ground that D2 changes
`usable_status`, `eligibility_rule` tokens (`usable:5`→`usable:1`), the three coverages,
evidence grades, and rankability — a different test class and golden-vector set.

### Questions raised (relayed to operator, verbatim intent)

- **Q1 (split).** One chunk or split chunk-24 = D1+D3 and chunk-25 = D2?
- **Q2 (representation).** How to persist the interleaved stratum geometry: replace
  `sample_members.stratum_start_ordinal`/`stratum_end_ordinal` with `stratum_offset`/
  `stratum_stride` (and the same keys in `stratum_statistics_json`), or add alongside, or
  carry it only in `stratum_statistics_json`? Requires `SCHEMA_VERSION` bump (currently
  `1.1.0`) under operator authorization.
- **Q3 (offset derivation).** D1's `sha256(sampling_rule_version, category) mod SAMPLE_STRATA`
  does not specify the join delimiter, digest-byte vs hex reduction, or casing. Needs a
  precise, deterministic convention.

### Operator answers (2026-09-28) — "go with recommendations"

- **A1 — split approved.** `chunk-24` = D1+D3 (interleaved partition rule, `(offset, stride)`
  representation, `SAMPLING_RULE_VERSION`/`SCHEMA_VERSION` bumps, SRS partition edits).
  `chunk-25` = D2 (`MIN_USABLE` 5→1 and the coverage/evidence/rankability re-baseline).
  chunk-24's plan records chunk-25 as a declared follow-on, out of this chunk's scope.
- **A2 — replace.** `sample_members.stratum_start_ordinal`/`stratum_end_ordinal` are replaced
  by `stratum_offset`/`stratum_stride` (same two keys replace the interval keys in
  `stratum_statistics_json`). `SCHEMA_VERSION` `1.1.0` → `1.2.0`. A member's discovery ordinal
  remains recoverable from `raw_discovery_observations.discovery_ordinal`.
- **A3 — offset derivation.** `offset = int.from_bytes(sha256(utf8(sampling_rule_version + NUL
  + category)).digest()[:8], "big") mod SAMPLE_STRATA`; deterministic, no RNG, persisted.

### Operator answers to plan open questions (2026-09-28) — "go with recommendations"

Plan `Documents/plans/chunk-24-systematic-strata.md` §11 had six open questions; the
operator accepted the lead's recommendations for all six:

- **OQ-1:** census encodes as `stratum_offset = 0`, `stratum_stride = 1`.
- **OQ-2:** `SAMPLING_RULE_VERSION = "2.0.0"`.
- **OQ-3:** the offset is always reduced `mod SAMPLE_STRATA`; a non-default `sample_strata`
  argument is test-only and does not change the offset modulus.
- **OQ-4:** follow the real `tests/traceability.json` (keyed node ID → LREQ list); do not edit
  `tests/AGENTS.md` (pre-existing doc bug, out of scope).
- **OQ-5:** add an SRS revision-history row (next label `Lean 1.0.2`).
- **OQ-6:** `LREQ-SMP-070` is covered by a structural membership assertion (every stratum's
  ordinals intersect the first-page, middle, and last-page ranges); no quantitative span
  threshold.

## Tests stage — INCOMPLETE (stopped, 2026-09-28)

`test-author` session `ses_f18651be7ffeBeVkupX832LkzQ` reached its step cap mid-edit. Its
partial work is on disk, uncommitted. The lead reproduced the suite and its failure mode
rather than accepting the subagent's claim.

### Lead-reproduced state (real output)

| Command | Real result |
|---|---|
| `python -m py_compile tests/test_sampling.py tests/fixtures/sampling_fixtures.py` | exit 0 (both files parse): no syntax error introduced |
| `python -m pytest -q` | **22 failed, 665 passed in 27.05s** |
| `python -m pytest tests/test_sampling_persistence.py tests/test_database.py tests/test_contracts.py tests/test_enrichment.py tests/test_end_to_end.py tests/test_report.py -q` | 152 passed |
| `python -m pytest -q -k "not test_sampling and not test_traceability_validator"` | 607 passed, 80 deselected |
| `python -m niche_scout.tools.validate_traceability` | exit 1: 12 new nodes lack matrix entries + marker/mismatch; 3 retired contiguous nodes still in the matrix |
| Fixture import + literals (`python -c`, lead) | `OFFSET_RULE_VERSION=2.0.0`; `EXPECTED_OFFSET_LARGE_CATEGORY=0`; N101 vectors `26/25/25/25`; N104 `26` each — all match the plan §8.2 hand-computed values |

### Gap analysis (what remains undone)

1. **All 20 non-traceability failures are missing-implementation failures** — every one is an
   `AssertionError` on an absent symbol/field (`stratum_offset`, `stratum_stride`,
   `stratum_member_ordinals`, `category_stratum_offset`, `SAMPLING_RULE_VERSION == "2.0.0"`)
   from `sampling.py`/`models.py`. No syntax or collection error. Oracle condition met.
2. **Two failures are test-authoring gaps, not implementation gaps:**
   - `test_default_constants_are_not_configurable` fails at `assert sampling.SAMPLING_RULE_VERSION == "2.0.0"` (implementation gap, expected initially). It is also a *pre-existing* node edited in place.
   - `test_sample_fraction_distinct_from_stratum_aggregates` fails on the new member field list (implementation gap), but the node was edited in place rather than split.
3. **`tests/traceability.json` was not updated at all** (no new entries, no retired-node removal, no atomic `1_1_0`→`1_2_0` key move). This is the largest remaining tests-stage item.
4. **Fixtures not yet migrated** (still encode the old interval): `sampling_persistence_fixtures.py` (O8 tuple, O9 byte-exact JSON, `O9_STRATUM_KEYS`), `report_fixtures.py`, `enrichment_fixtures.py`. The 152-passing stratum-touching modules pass only because they still exercise the *old* interval, so they will break when the implementation lands and must be migrated in the same change.
5. **The independent offset literal** for the plan's required `(2.0.0, category)` capture is computed by a hashlib transcription inside the fixture (independent of `src/`) but the plan requires a captured one-liner with its command recorded. Still owed.

### Decision

Per the chunk-lead procedure, an `INCOMPLETE` subagent may be resumed at most twice. The
remaining tests work is too large for one more bounded continuation step; the honest call is
to **stop the tests-first stage here** and record it. The lead does not write or repair tests
itself (role boundary). The implementation stage cannot start cleanly until the tests/fixtures
are consistent, so chunk-24 is **BLOCKED at the tests stage** pending either (a) a fresh
tests-first dispatch scoped to the remainder (fixtures + traceability + the two in-place
nodes), or (b) an explicit operator decision to proceed with the implementation against the
partially migrated suite.

### Uncommitted files (not staged, not committed by the lead)

- `tests/test_sampling.py` (modified, partially migrated)
- `tests/fixtures/sampling_fixtures.py` (modified, partially migrated)

Nothing was committed for this stage: the tests-first commit requires a suite whose failures
are only missing-implementation failures **and** a validator-clean traceability matrix, which
is not yet true. Working tree is therefore dirty and chunk-24 is paused.