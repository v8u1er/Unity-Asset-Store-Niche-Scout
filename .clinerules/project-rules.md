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
  (structural/domain validity), sampling.py (deterministic sampling), metrics.py
  (metric eligibility + raw estimators), scoring.py (normalization, score
  components, evidence, sensitivity). I/O and orchestration live only in
  collector.py, config.py, database.py, pipeline.py, report.py, cli.py.
- Pure modules must have no direct or transitive I/O, network, database, CLI,
  filesystem, or system-clock dependencies. Time-dependent pure functions take
  an explicit timezone-aware UTC scoring_cutoff_utc; analytical calculations use
  float64 precision.
- validation.py classifies structural/domain validity; metrics.py decides
  metric-specific eligibility. Null, zero, invalid, and unavailable remain
  distinguishable through typed status/reason data where relevant; never convert
  missing or invalid data to zero.
- Determinism: the same normalized inputs, effective configuration, and policy
  versions produce structurally and numerically equivalent results. No random
  generators or current-time reads in pure code.

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

## Temporary scripts and scratch space
- The ONLY sanctioned location for throwaway scripts, probes, and temporary
  output is `.scratch/` at the repository root. Never write to `%TEMP%`,
  `$env:TEMP`, `AppData`, `C:\Windows\Temp`, or any other path outside this
  repository, and never ask the user for permission to do so — use `.scratch/`.
- Prefer `python -c` or an inline run for a one-liner. If a file is genuinely
  needed, create `.scratch/<task-or-chunk>-<purpose>.py` (see
  `.scratch/README.md` for naming and header conventions).
- Scratch scripts import the package by running from the repository root
  (`python .scratch/<name>.py`) with `src` on `PYTHONPATH` (e.g.
  `$env:PYTHONPATH = "src"; python .scratch/<name>.py`). Do not add new
  packaging or path shims for scratch code.
- `.scratch/*` is git-ignored and is not part of any deliverable. Scratch code
  is never referenced by `src/`, `tests/`, or `Documents/`.
- Delete each scratch file in the same task that created it, unless the user
  explicitly asks for it to be kept.
- Never place product databases, fixtures used by `tests/`, or copies of
  frozen plan/interface/SRS text in `.scratch/`.