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
