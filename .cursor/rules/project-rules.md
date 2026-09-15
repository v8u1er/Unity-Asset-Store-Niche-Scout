---
description: Niche Scout project rules — architecture, traceability, and scope discipline for all agents and subagents
globs:
alwaysApply: true
---

# Niche Scout — project rules for all agent tasks

## Source-of-truth precedence
1. `Documents/SRS-lean.md` — normative requirement text. Never paraphrase a
   requirement from memory; open the file and quote or derive it.
2. `Documents/requirements-dependency-map.md` — chunk ownership, gates, and
   edge cases.
3. `Documents/plans/chunk-*.md` — the frozen scope contract for one chunk.
4. `Documents/interfaces/chunk-*.md` — frozen public contracts from completed
   chunks.

Never treat prior chat turns as a source of truth for requirement text or gate
criteria if they conflict with these files. Read the SRS and dependency map
directly before making requirement-driven changes.

## Architecture rules (non-negotiable, all chunks)
- The module boundary is fixed. `models.py` contains typed structures;
  `validation.py` contains structural and semantic validation primitives;
  `sampling.py` contains deterministic sampling; `metrics.py` contains metric
  eligibility and raw sample-aware estimators; and `scoring.py` contains
  normalization, score components, evidence, and sensitivity.
- I/O and orchestration remain in `collector.py`, `collector_coveo.py`,
  `collector_graphql.py`, `config.py`, `database.py`, `pipeline.py`,
  `report.py`, and `cli.py`. `collector.py` is a facade re-exporting both
  collector adapters so Coveo and GraphQL work can proceed independently.
- `metrics.py` and `scoring.py` are pure. They SHALL accept typed inputs and
  return typed outputs, SHALL never import I/O modules, and SHALL perform no
  network, file, database, process, or CLI I/O or system-clock reads.
- Time-dependent pure functions take an explicit timezone-aware UTC
  `scoring_cutoff_utc` argument. Analytical formulas operate internally at
  `float64` precision.
- `validation.py` classifies structural and domain validity; `metrics.py`
  decides metric-specific eligibility. Null, zero, invalid, and unavailable
  remain distinguishable through typed status or reason data where relevant.
  Missing, invalid, contradictory, or unavailable values SHALL remain
  unavailable; never fabricate or silently convert them to zero.
- Determinism is required: the same normalized inputs, effective configuration,
  and policy versions produce structurally and numerically equivalent results.
  Pure code SHALL NOT use random generators or current-time reads.

## Requirements and tests
- Use the SRS's exact weights, thresholds, and boundary rules from Appendix A.
- Do not modify frozen interfaces without a separate coordination task.
- Every analytical test has an explicit `@pytest.mark.lreq("LREQ-....")`
  marker and a matching entry in `tests/traceability.json`.
- Parameterized tests are mapped by their base pytest node ID, not each case.
- Tests use fixtures and golden vectors only; live network calls are forbidden.
- Run `python -m niche_scout.tools.validate_traceability` before declaring any
  chunk done.

## Scope discipline
- A chunk's frozen `Documents/plans/chunk-XX.md` is the only scope authority
  for that chunk's implementation task. Do not implement behavior that the
  plan explicitly marks as owned by a different chunk, even if it would be
  convenient to do so now.
- If something looks missing or ambiguous, write it to the plan's `Open
  questions` section during planning, or stop and ask during implementation.
  Never invent a resolution silently.

## File discipline
- Only touch files listed in the active chunk's plan under `Files touched`.
  If another file appears necessary, stop and flag it instead of editing it.

## Scope prohibitions
The following items from `Documents/SRS-lean.md` §1.3 are explicitly
forbidden: sales or revenue prediction, scheduled execution, resume/checkpoint
execution, full enrichment of every discovered asset in large categories,
automated credential acquisition, and multi-user or cloud deployment. No agent
may implement them even if asked.