# Chunk 5 — run log (GraphQL protocol adapter and response correlation)

Resumed 2026-09-19. Branch: `main` (no `chunk-5` branch exists on this tree; the
operator ruled to stay on `main` — see D6). HEAD at resume: `9b9485d`.

## Preflight (resume)

| Check | Result |
|---|---|
| Working tree | clean (`git status` → "nothing to commit, working tree clean") |
| Branch | `main` only; `git show-ref --heads` → one ref (`refs/heads/main`) |
| Run logs | `Documents/runs/` did not exist on this tree — created by this run. Expected, not a blocker. |
| Prerequisite chunks | Chunk 5's prerequisites are Chunk 0/1/2/3, satisfied by the VERIFIED interface files `chunk-00/01/02/03.md`. Recorded as a deliberate exception to the usual `GATE: PASSED` run-log check: those run logs do not exist on this tree. Not blocked. |
| Frozen plan | `Documents/plans/chunk-05-graphql-protocol-adapter-and-response-correlation.md` — `Status: FROZEN`. Not re-planned (routing: no planner dispatch for a frozen plan). |

## Decisions recorded before any writer dispatch (operator-ruled 2026-09-19)

D1. **Node count.** `tests/test_collector.py` carries **51** marked nodes =
**25 original Chunk 3 + 1 added by `9bbef14` + 25 Chunk 5**. The brief's DoD 3
target of "50 (25+25)" is stale. `51 = 26 + 25` verified on the artifact.

D2. **DoD 2 baseline — option B1.** DoD 2 is restated as: `git diff --numstat
4135e6e HEAD -- tests/test_collector.py` = **+55 / −11**, and all 11 deletions
belong to Chunk 5's own three commits `df0de45` (14/0), `f100732` (38/9),
`137562c` (3/2); no Chunk 3 node, marker, fixture import, or
`tests/traceability.json` entry is deleted by Chunk 5's window.
`9bbef14` deletes 13 lines of Chunk 3 material (`tests/test_collector.py` 98/13,
`test_identity.py` +46/0, `tests/traceability.json` 28/1) **before** the
baseline `4135e6e` (`9bbef14` is `main~25`, an ancestor of `4135e6e` and of
HEAD). That is a **pre-existing cross-workstream fact**; Chunk 5 neither owns
nor fixes it, and no follow-up on it is pre-authorized or foreclosed here.

D3. **Three `LREQ-GQL-070` nodes — option (b).** Write
`test_correlated_product_detail_reports_alias_mismatch`,
`test_missing_returned_identity_is_not_an_implicit_match`, and
`test_adapter_mismatch_is_a_flag_not_a_metric_exclusion` into
`tests/test_identity.py`, as frozen plan §9 (`:1558-1560`) assigns them, and
re-verify the file's counts in the same pass (26 → 29) per §12.2 item 9's
mechanism. Do not relocate them to `tests/test_collector.py` (that would be an
unruled plan edit).

D4. **Metadata two-renderer split — in scope.** §12.6 item 3 / §5.10 require
real operation names **and** correlation keys in `request_metadata_json`.
Operation names pass through today; `correlation_keys` and
`additional_correlation_keys` values still go through `_metadata_text →
redact_value`. Completing the split is in the impl-deep dispatch scope; the
naming/shape of the two renderers is the implementer's and the reviewer's call
(§12.5 item 2).

D5. **`__all__` arity — 49/50, no code change.** `collector_graphql.__all__`
holds 50 names; `collector.py` re-exports 49. The omitted name is
`CORRELATION_KEY_MEMBERS`, which plan §5 does not list. Recorded explicitly in
`Documents/interfaces/chunk-05.md` as a deliberate state; not added.

D6. **Branch — stay on `main`.** Branching to `chunk-5` from HEAD does not clean
the numstat and buys isolation at the cost of complexity without solving the
problem (D2 restatement is what solves it). All commits land on `main`.

D7. **Ruling A correction — approved.** Correct `chunk-05-…md` §6/§9's
"51 … all of them Chunk 3's … none an `LREQ-GQL-*`" to the measured
decomposition 25 original Chunk 3 + 1 from `9bbef14` + 25 Chunk 5, as a dated
correction (correct the figures, mark the correction, do not silently
substitute). Cite `9bbef14` as the actual source of the +1.

## Stage log

| Stage | Status | Evidence / notes |
|---|---|---|
| Resume + preflight | DONE | See table above. |
| Baseline verification | DONE | `git log 4135e6e..HEAD` = 20 commits; `git diff --numstat 4135e6e HEAD -- tests/test_collector.py` = `55 11`. |