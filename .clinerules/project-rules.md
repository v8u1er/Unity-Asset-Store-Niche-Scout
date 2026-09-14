# Niche Scout — project rules for all agent tasks

## Source-of-truth precedence
1. Documents/SRS-lean.md — normative requirement text. Never paraphrase a
   requirement from memory; open the file and quote/derive it.
2. Documents/requirements-dependency-map.md — chunk ownership, gates, edge cases.
3. Documents/plans/chunk-*.md — the frozen scope contract for one chunk.
4. Documents/interfaces/chunk-*.md — frozen public contracts from completed chunks.
Never treat prior chat turns as a source of truth for requirement text or gate
criteria if they conflict with the files above.

## Architecture rules (non-negotiable, all chunks)
- Module boundary is fixed: models.py (typed structures), validation.py
  (structural/semantic validation primitives), sampling.py (deterministic
  sampling), metrics.py (eligibility + raw estimators), scoring.py
  (normalization, score components, evidence, sensitivity). I/O and
  orchestration live only in collector.py, database.py, pipeline.py,
  report.py, cli.py.
- metrics.py and scoring.py must never import sqlite3, network, filesystem,
  CLI, or system-clock APIs. All time-dependent pure functions take
  scoring_cutoff_utc as an explicit argument.
- Null, zero, invalid, and unavailable are distinct states. Never silently
  convert missing/invalid data to zero.
- Determinism: same inputs + same policy versions → structurally and
  numerically equivalent results. No random generators in sampling; no
  current-time reads in pure code.

## Test traceability (non-negotiable, all chunks)
- Every analytical test has an explicit `@pytest.mark.lreq("LREQ-....")`
  marker and a matching entry in tests/traceability.json.
- Parameterized tests are mapped by their base pytest node ID, not each case.
- Run `python -m niche_scout.tools.validate_traceability` before declaring any
  chunk done.

## Scope discipline
- A chunk's frozen plans/chunk-XX.md is the only scope authority for that
  chunk's implementation task. Do not implement behavior that the plan
  explicitly marks as owned by a different chunk, even if it would be
  convenient to do so now.
- If something looks missing or ambiguous, write it to the plan's "Open
  questions" section (planning tasks) or stop and ask (implementation tasks).
  Never invent a resolution silently.

## File discipline
- Only touch files listed in the active chunk's plan under "Files touched."
  If you believe another file must change, stop and flag it instead of
  editing it.