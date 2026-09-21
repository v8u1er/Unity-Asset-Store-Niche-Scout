# Chunk 9A — run log (Pre-sensitivity evidence checks and immutable base candidates)

Started 2026-09-21. Branch: `chunk-9A` (created from `main`, HEAD `153042d`). Tree clean at preflight.

## Preflight

| Check | Result |
|---|---|
| Working tree | clean (`git status --short --branch` → `## main`) |
| Branch | `chunk-9A` created from `main` (HEAD `153042d`) |
| Prerequisite Chunk 8 | `Documents/runs/chunk-08.md` ends `GATE: PASSED` (line 70); interface `Status: VERIFIED` |
| Prerequisite Chunk 7B | `Documents/interfaces/chunk-7B.md` → `Status: VERIFIED`; run log `GATE: PASSED` |
| Prerequisite Chunk 6A | `Documents/interfaces/chunk-6A.md` → `Status: VERIFIED`; run log `GATE: PASSED` |
| Prerequisite Chunk 5 | `Documents/interfaces/chunk-05.md` → `Status: VERIFIED` |
| Prerequisite Chunk 3 | `Documents/interfaces/chunk-03.md` → `Status: VERIFIED` |
| Baseline suite | `python -m pytest -q` → **400 passed in 13.26s** |
| Frozen plan | none yet — planner dispatch required |
| Routing | test-author first, then `impl-deep` (chunk-lead routing table) |

## Stage log

| Stage | Status | Evidence / notes |
|---|---|---|
| Preflight | DONE | See table above. |
| Plan — dispatch 1 | INCOMPLETE (step limit) | `chunk-planner` hit its 40-step limit after completing research; **it wrote no plan file** (`FILES: none created or modified`). It returned 6 open questions (field-specific reference support; "material discovery failure"; preflight input; `request_failed`; `pre_sensitivity_evidence_state` vocabulary; preliminary-rankability naming) plus a reading that 9–20-category runs get an empty base candidate set and are provisional. |
| Plan — advisory memo | DONE | Lead dispatched `explore` for an independent SRS-backed recommendation memo (resumable session `ses_f3ad85223ffee3RM6k1RiZ1FQo`). Full memo is in the transcript. It classified Q3/Q5/Q6 and the 9–20 reading as settled by quoted lines, and Q1/Q2/Q4 as structural readings needing a ruling. |
| Plan — lead rulings recorded | DONE | See "Chunk 9A plan rulings" below. The lead read the cited SRS lines itself (§9.1 LREQ-EVD-010/020/030/040; §7.3 LREQ-MET-070; §9.3 LREQ-SEN-030; §8.3 LREQ-SCR-060; App. C) and the dependency-map rows (103–105, 246–250, 258) before recording them. |
| Plan — re-dispatch | PENDING | — |

### Chunk 9A plan rulings (lead, SRS-backed)

Recorded so the planner does not re-open them. Cited lines were opened and read by the lead.

- **R1 — 9–20-category runs.** For a run with 9–20 categories, `base_rankable_candidates` is empty (LREQ-EVD-020, SRS §9.1: base candidacy requires "at least `STRONG_REFERENCE_CATEGORY_COUNT` categories", `= 21`, §9.1 line 1014); a run with 8–20 categories may be `provisional` and SHALL never be `rankable` (LREQ-EVD-040, SRS §9.1 lines 1003–1008); dependency-map §6.2 ("may calculate provisional scores, but they do not produce a rankable candidate set"). A run of exactly 8 categories still computes a score (SRS §8.3 "the composite MAY be persisted as `partial`"); fewer than `MIN_CATEGORIES_PER_RUN = 8` is rejected before ranking (LREQ-CLI-040).
- **R2 — `pre_sensitivity_evidence_state` and preliminary rankability are internal, non-persisted, and distinct.** Dependency-map Chunk 9A gate bullets (lines 915, 917) and its §3 implement list line 898: "these are not silently treated as final persisted evidence fields". The persisted `evidence_grade` / `rankability_status` are Chunk 9B's final values (dependency map lines 953–954) written by Chunk 10. Chunk 9A must not reuse `EvidenceGrade` for the pre-sensitivity state.
- **R3 — `base_candidates` is an ordered, immutable-in-contract `tuple[str, ...]`** (consistent with the frozen Chunk 8 style: `tuple[float, ...]`, `COMPONENT_WEIGHT_KEYS`). Ordering is the input `all_metrics` order, so it is deterministic and independent of set/dict iteration (LREQ-ARCH-030).
- **R4 — per-category `not_rankable` reasons are a fixed, deterministic vocabulary.** Dependency-map lines 246–248 describe the tests as "State-transition unit test" / "Rankability matrix test"; determinism (LREQ-ARCH-030) requires an explicit order. The plan SHALL define a `StrEnum` of reason codes plus a documented evaluation order, and return an ordered `tuple` of reasons (empty for a candidate). The reason set SHALL cover LREQ-EVD-020's clause list (SRS §9.1 lines 980–987): discovery filtering unverified; unresolved/conflicting identity remaining; required demand data unavailable; recent-supply minimum evidence not met; quality unavailable under the required-component policy; page-view semantics contradicted; no valid leave-one-out reference; identity preflight failure; unrecoverable data-integrity error; and material discovery failure / unbounded breadth making competition non-rankable.
- **R5 — "material discovery failure or unbounded breadth" = exactly the §7.3 competition-unavailability conditions.** SRS §7.3 LREQ-MET-070: "Competition is unavailable when filtering is unverified, a material page failed, identity incompleteness makes breadth an unbounded lower bound, or the fallback breadth cannot be bounded." No new enum or numeric threshold is invented; the predicate is expressed through the statuses already present (`DiscoveryStatus`, `BreadthSource`, `BreadthCompletenessStatus`, `PageViewSemanticsStatus`).
- **R6 — identity preflight is a run-level input.** `runs.identity_preflight_status` is run-level (SRS §6.1; `models.IdentityPreflightStatus`); a failed preflight marks the run failed (LREQ-ID-040). Chunk 9A takes `identity_preflight_status: IdentityPreflightStatus` as an explicit typed parameter and, when it is `FAILED` (dependency-map §6.1: "affected categories may also be shown as `not_rankable`"), records the category-level preflight reason while leaving the run status separate. Chunk 9A does not invent a per-category preflight field.
- **R7 — `request_failed` and `page_failed` categories are `not_rankable`, never zero-breadth.** LREQ-EXT-050 (SRS §4.1): "a failed or truncated page SHALL never be interpreted as zero assets"; LREQ-EXT-090: a failed page / unverified filter / category mismatch / material identity incompleteness prevents a fully rankable competition result; LREQ-EVD-020's "unrecoverable data-integrity error" clause covers it. The pure function consumes the already-persisted `DiscoveryStatus` as an argument; it does not re-derive it.
- **R8 — field-specific reference support.** LREQ-EVD-020 requires "field-specific reference support passes" but the SRS does not state a predicate; dependency-map lines 246–250 list no edge case for it. The plan MUST raise this as a numbered open question with the option set rather than inventing a threshold: (a) every field in `LeaveOneOutReference.field_usable_counts` > 0 (requires `reference_size > 0`; vacuous for a one-category run); (b) support only for the fields each *available* component consumes (§8.2: D → `demand_per_asset`/`demand_median`, C → `breadth`, R → `recent_share`/`median_age`, Q → `quality`); (c) not a separate gate at all, i.e. already implied by "all four components are available". `STATUS: BLOCKED` is unconditional for the plan freeze when this is open (project rule: "An open question blocks the plan's freeze until a human resolves it").
- **R9 — supporting contract for LREQ-SEN-030 is a threshold-predicate input only.** Dependency-map lines 258 and 110: `LREQ-SEN-030`'s primary owner and completion chunk is Chunk 9B; the Chunk 9A gate has no warning-threshold bullet. Chunk 9A supplies the fixed candidate set and the pre-sensitivity rankability state that the threshold is later interpreted against, and must not compute `top_3_stability` or the warning.
- **R10 — discovery-integrity inputs are explicit typed parameters; Chunk 9A performs no aggregation and no I/O.** `CountRecord`s, `DiscoveryStatus`, coverage, `breadth_source`/`breadth_completeness_status`, `reference_size`, and `field_usable_counts` all arrive as arguments, consistent with the `score_category` contract in `interfaces/chunk-08.md` §3 and LREQ-ARCH-010. Chunk 9A adds no SQLite or pipeline imports.