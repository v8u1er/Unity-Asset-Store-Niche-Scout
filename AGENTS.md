# Niche Scout — agent instructions

Local Python 3.11+ tool that scores Unity Asset Store categories from Coveo discovery
plus sampled GraphQL enrichment. The output is a **sample-based, deterministic,
within-run heuristic**. It is NOT a sales, revenue, download, or demand predictor and
NOT a statistically representative estimate. Never write code, comments, report text,
or docs that claim otherwise.

## Source of truth (read on demand, never whole)

- `Documents/SRS-lean-v2.md` — requirements, `LREQ-<AREA>-<NNN>`. Each file is ~18k tokens;
  do not read it end to end. `grep` for the LREQ ID or section number, then read that
  section only.
- `Documents/requirements-dependency-map.md` — chunk plan (Chunks 0–13), ownership and
  test-traceability matrix, clarifications (§6), open items (§7).
- If the SRS is ambiguous or silent, STOP and ask. Never invent formulas, thresholds,
  weights, or field names. Constants come from SRS §14; do not hard-code magic numbers.
- Spec index: architecture §3 · Coveo §4.1 · GraphQL §4.2 · credentials §4.3 · identity
  preflight §4.4 · sampling §5 · data model §6 · metrics §7 · normalization/composite §8 ·
  evidence/rankability/sensitivity §9 · report/CLI §10 · NFR §11 · layout §12 · tests §13 ·
  config §14 · out of scope §15 · limitations §16 · acceptance §17 · formulas App. A ·
  warning vocabulary App. C.

## Workflow

- Work on ONE chunk at a time, in the order in dependency-map §4. Each chunk ends at a
  gate; do not start the next chunk until the gate passes.
- State the chunk and the LREQ IDs you are targeting before editing.
- Fixtures and golden vectors first; no live network in development or tests. Never run
  `niche-scout run` or anything that needs the real credentials.
- Small diffs, one concern each. Run tests after every change and report the real
  output. Never claim "tests pass" without running them.
- Dev machine is Windows (PowerShell). Chain commands with `;`, not `&&`; use
  `python -m ...`; avoid bash-only tools. Use `pathlib`, never hard-coded separators.

## Hard rules (analytical validity)

1. **Purity boundary.** `metrics.py` and `scoring.py` take plain typed inputs and return
   typed results. They must not import `collector`, `database`, `report`, `cli`, HTTP,
   `sqlite3`, or do file I/O, and must not read the clock (`datetime.now`, `utcnow`,
   `time.time`). `scoring_cutoff_utc` is always a parameter. (LREQ-ARCH-010/020)
2. **Missing is not zero.** Null, explicit valid zero, invalid, and unavailable are four
   different states. No `or 0`, `.get(k, 0)`, `fillna(0)`, or default-0 parameters on
   metric inputs. (SRS §1.2)
3. **Time.** All calculation timestamps are timezone-aware UTC; naive datetimes are
   invalid. Age is exact fractional days. Timestamp names end in `_utc`.
4. **Precision.** `float64` throughout; round only for display.
5. **Sample vs population.** Competition uses discovered breadth, not sample size.
   `sample_fraction` is not stratum eligibility coverage. Overlap must never inflate
   enrichment counts or preflight rates.
6. **Ordering.** Persist audit data before scoring. Freeze `base_rankable_candidates`
   before sensitivity. Sensitivity never adds candidates or changes the balanced score.
7. **Separate status fields.** Run status, discovery status, score state, evidence grade,
   and rankability are distinct fields; never collapse them into one.
8. **Enrichment.** One GraphQL enrichment request per unique sampled asset per run.
   No bulk enrichment until the identity preflight gate passes.
9. **Determinism.** Same inputs + policy versions + config give the same outputs: no
   unseeded randomness, no dependence on set/dict ordering, explicit tie-breaks.
10. **Runs of 8–20 categories** are provisional with an empty candidate set and `null`
    stability outputs; fewer than 8 is rejected before ranking.
11. **Report wording** uses the warning vocabulary in SRS Appendix C.

## Out of scope — do not add

Scheduling, resume/checkpoint, historical trends or run comparison, enriching every
discovered asset, favorite-count, extra GraphQL fields, alternative collection
strategies, configurable score weights (fixed in Lean v1), confidence intervals, sales
calibration, automated credential acquisition, multi-user/cloud. Chunk 13 statically
checks for these.

## Secrets

Credentials come only from `NICHESCOUT_COVEO_BEARER_TOKEN` and
`NICHESCOUT_UNITY_CSRF_TOKEN`. Never in source, logs, SQLite, error messages, or
fixtures. Never open `.env`. Redact before logging. (LREQ-SEC-010/020)

## Tests and quality

- pytest. Every analytical test carries `@pytest.mark.lreq("LREQ-...")` and an entry in
  `tests/traceability.json` (key = test node ID, value = list of LREQ IDs).
- Validator: `python -m niche_scout.tools.validate_traceability`.
- Formula tests cover: normal, explicit zero, missing, invalid, ties, minimum boundaries
  (LREQ-TST-010). Golden vectors assert within `1e-9`.
- Public metric/scoring functions: type hints plus docstrings that state null and
  edge-case behavior (LREQ-NFR-040).
- Run the formatter and linter configured in `pyproject.toml` (check it; do not assume).
- Naming: `snake_case` functions/files, `PascalCase` classes, `UPPER_SNAKE_CASE` constants.

## Open obligations (record, do not silently resolve)

- URI trailing-identifier extraction (identity mapping rule 1.0.1) is inferred, not
  verified against a real Coveo response. No captured response exists in the repo.
- OI-6: CSRF/session sufficiency has no owning chunk.
- `runs.taxonomy_sha256` must reject empty hashes; owner is Chunk 10.

## Multi-agent contract

Chunks are run by `chunk-lead`, which dispatches subagents one at a time (they share one
working directory, so never run two writers concurrently). Roles: `chunk-planner`,
`test-author`, `impl-fast`, `impl-deep`, `spec-reviewer`. Run logs live in
`Documents/runs/chunk-<id>.md`; plans in `Documents/plans/`.

If you are a subagent:

- You are non-interactive. You cannot ask the user anything. When you hit an SRS gap,
  ambiguity, missing plan, or conflict, STOP that part and report it under `QUESTIONS`.
  Never pick a behavior to keep going.
- Only the lead commits. Do not run `git add`, `git commit`, or switch branches.
- Do not edit `Documents/`, `AGENTS.md`, `kilo.jsonc`, or `.kilo/` unless your role says so.
- Do not modify tests written by `test-author`. If a test contradicts the SRS, leave it
  and report `DISPUTE: <test id> — SRS §x says ...` instead.
- Do not paste large spec or plan text into your result; cite section numbers and LREQ IDs.
- If a provider/API error stops you, report the error text verbatim and stop.

End every run with exactly this block (reviewers use `VERDICT` instead of `STATUS`):

```text
STATUS: DONE | BLOCKED | INCOMPLETE
CHUNK: <id>
SUMMARY: <2-5 lines>
FILES: <created/modified paths>
COMMANDS: <each command you ran and its real result, e.g. "pytest: 41 passed, 0 failed">
QUESTIONS: <numbered, each with SRS reference and the options you see; or "none">
DISPUTES: <or "none">
UNVERIFIED: <anything you could not check; or "none">
```
