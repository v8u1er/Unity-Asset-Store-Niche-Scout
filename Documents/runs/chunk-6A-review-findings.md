# Chunk 6A review — follow-up findings (lead, 2026-09-21)

Follow-up to the `spec-reviewer` pass on commit `94df8e9`. The reviewer hit its step
budget before issuing a verdict but left three open items; the lead adjudicated them
against the frozen contract. This file records the adjudications so the next reviewer
does not have to re-derive them. **No `VERDICT` is recorded here.**

## Item 4 (reviewer) — the `_run_adapter` sleep clamp: MAJOR, and fixed

- Reviewer evidence (read): `Documents/interfaces/chunk-05.md:795-810` says
  `execute_graphql_batch` "sleeps the return of `retry_delay_seconds` between attempts
  through the **injected** `sleep`", and that `min_request_interval_seconds` "is
  enforced by the caller passing the same `sleep`".
- The implementation wrapped the caller's `sleep` in `_sleep`, clamping every delay to
  `_RETRY_SLEEP_CEILING_SECONDS = 0.05`. That silently overrides the caller's seam and
  makes the public `sleep` argument a lie — a contract violation, not a test detail.
- `GraphQLRetryPolicy.min_request_interval_seconds` is declared in
  `collector_graphql.py:1921` and never referenced in its execution loop (counted:
  one occurrence, the declaration). The `0.05` ceiling is not a substitute for it.
- **Fix applied:** the clamp constant and inner `_sleep` were removed; `_run_adapter`
  now passes `sleep` straight through to `enrich_asset` (the parameter was already
  forwarded correctly from `run_identity_preflight`, `pipeline.py:1016`). The
  `bytes`→`str` decode was retained: `GraphQLBatchResponse.body_text` is `str`
  (`collector_graphql.py:478`) and a real HTTP transport may hand over bytes, so it is
  a legitimate boundary adapter, not test scaffolding.
- **Test-side consequence:** three nodes that drive `pf.FailingTransport()` now wait
  out the real backoff. They were bounded **at the call site** with a module-level
  `_no_sleep` helper (the nodes' concern is ordering/status, not backoff), per the
  contract's intent that the caller controls the sleeper.

## Item 5 (reviewer) — the three test-side changes: all CORRECT, none a weakening

1. `test_select_preflight_identities_two_assets_five_categories` expecting
   `A2,A1,B2,B1,…` — **CORRECT.** `sampling.selection_digest` hashes
   `rule_version + NUL + category + NUL + key` (`sampling.py:290-291`) and
   `select_stratum_members` sorts by `(digest, asset_identity_key)`
   (`sampling.py:447-458`); the discovery ordinal is not an input, so declaration
   order cannot change the rank. The old expectation was simply wrong, and a fixture
   swap was proven not to fix it (both `("A1","A2")` and `("A2","A1")` yield A2 first).
2. `test_preflight_persisted_before_gate_returns` asserting the terminal gate-write
   snapshot rather than every intermediate snapshot — **CORRECT.** The requirement
   ("preflight status, summary, and observations are persisted before the gate
   returns", dependency-map line 723) is an ordering guarantee at the return, not an
   incremental-per-upsert guarantee, which is unbatchable. The node still asserts
   `update_run_status` is the last write and that the terminal snapshot equals the
   final read-back.
3. `test_run_identity_preflight_failed_operation_does_not_abort_loop` passing
   `min_categories=5` and asserting requested-identity coverage — **CORRECT.**
   `_run_preflight`'s default `pf.small_policy()` has `min_categories=2` (a fixture
   default), so the selection was legitimately four identities; the implementation's
   `categorised[: policy.min_categories]` matches plan §5.2. The node now passes the
   same policy as its ten-identity siblings, and the coverage assertion (rather than
   an exact call count) is the invariant the test's own docstring names, because
   Chunk 5 owns the retry count.

## Resolved after this note (kept for the record)

- **Signature deviations — FIXED in `ad32328`.** `run_identity_preflight`'s
  non-frozen `transaction` keyword was removed (unconditional
  `with repository.transaction():`, unused `nullcontext` import dropped), and
  `graphql_endpoint_signature` was restored to the frozen two-parameter form with the
  draft-metadata lookup moved into the private `_endpoint_signature_for_draft`. Both
  conformances were confirmed by the round-2 reviewer.
- **Traceability count — RESOLVED by the round-2 reviewer (counted).**
  `validate_traceability`'s "matrix nodes" is `len(traceability.json)`; this worktree
  holds 248 keys (207 pre-6A + 40 preflight nodes + 1 truncation-boundary node). The
  `285` figure came from a bare `python -m` resolving the parent checkout, not from
  this worktree. Cite the `PYTHONPATH=src` number only.
- **Chunk 6B / public-symbol shadowing check** — still not completed by a reviewer.
  The round-2 reviewer confirmed the 6A diff touches only `pipeline.py` and the
  additive `database.py` method, and that no `models.py`/`config.py`/`sampling.py`/
  `validation.py`/`collector_graphql.py` line changed, which limits the risk to
  shadowing *within* `pipeline.py`'s own namespace.

## Open Major from round 1 (history)

- **Major — FIXED in `ef3c228`, boundary test added in `0a9837a`, closed by the
  round-2 `VERDICT: PASS`.** `select_preflight_identities` reported
  `covered_categories`/`selected_category_count`/`asset_shortfall` over all eligible
  categories while selecting identities from `categorised[: policy.min_categories]`.
  The frozen interface §5.2 (lines 74-80) defines `covered_categories` as "the
  selected ones" and §5.5's example shows `selected_category_count: 5` with
  `eligible_category_count: 6`. The fix computes
  `chosen = categorised[: policy.min_categories]`, `covered = chosen`,
  `eligible = categorised`, and `asset_shortfall` against `len(covered)`; the new node
  `test_select_preflight_truncates_covered_but_reports_all_eligible` asserts the
  frozen example's shape.
