---
description: Niche Scout project rules — architecture, traceability, and scope discipline for all agents and subagents
globs:
alwaysApply: true
---

## Source-of-truth precedence
1. Documents/SRS-lean.md — normative requirement text. Never paraphrase a
   requirement from memory; open the file and quote/derive it.
2. Documents/requirements-dependency-map.md — chunk ownership, gates, edge cases.
3. Documents/plans/chunk-*.md — the frozen scope contract for one chunk.
4. Documents/interfaces/chunk-*.md — frozen public contracts from completed chunks.
Never treat prior chat turns as a source of truth for requirement text,
interface dependencies, or gate criteria if they conflict with the files
above — that includes an LREQ list or interface list typed into a dispatch
message. A chunk identifier is a pointer; the files above are what actually
define its scope.

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
- Traceability counts (markers, distinct node IDs, matrix entries) are countable
  claims about existing artifacts; verify them per the counting rule under "Plan
  review and audit."

## Scope discipline
- A chunk's frozen plans/chunk-XX.md is the only scope authority for that
  chunk's implementation. Do not implement behavior that the plan explicitly
  marks as owned by a different chunk, even if it would be convenient to do
  so now.
- If something looks missing or ambiguous, write it to the plan's "Open
  questions" section (planning tasks) or stop and ask (implementation tasks).
  Never invent a resolution silently. An open question blocks that plan's
  freeze until a human resolves it — no team member may clear it on its own.

## File discipline
- Only touch files listed in the active chunk's plan under "Files touched."
  If you believe another file must change, stop and flag it instead of
  editing it.
- Growth inside a file you are already authorized to touch is in scope, but a file
  crossing the thresholds in "File size and concern boundaries" is a report item,
  not a silent continuation and not a mid-task split.

## File size and concern boundaries

These are review triggers, not gates. Crossing a threshold never blocks a
chunk, never fails a Definition of Done bullet, and never justifies a split
that changes a frozen interface, a pytest node ID, or a `tests/traceability.json`
entry. The trigger's only output is a note in the implementing agent's report
plus a proposed split boundary. A split is a scope decision for a human or a
plan, not something an agent performs mid-task to satisfy a counter.

- Test files: when a test file crosses roughly 800–1,000 lines, chunk-implementer
  notes it in its report and proposes a split along **requirement-cluster
  boundaries** — the clusters the LREQ ownership matrix and the file's own
  `@pytest.mark.lreq` markers already distinguish — never a mechanical "file A /
  file B" cut. Existing examples of the shape a split should take:
  `tests/test_identity.py` separates candidate collection/canonicalization
  (`LREQ-EXT-060`) from agreement/conflict/unresolved resolution (`LREQ-EXT-070`).
  A split SHALL NOT duplicate or rename a pytest node ID; existing
  `tests/traceability.json` entries SHALL stay byte-identical for every node whose
  behavior is unchanged, and any node that moves keeps its ID and gains a
  traceability path update in the same change.
- Fixtures are data, not logic. Golden vectors, parametrized tables, and captured
  response bodies belong in `tests/fixtures/*.py` (the existing convention:
  `config_fixtures`, `coveo_discovery`, `graphql_fixtures`, `validation_fixtures`,
  re-exported by `tests/fixtures/__init__.py`). Moving them there shrinks the file
  an agent must reason about without touching test logic, and a largely inert data
  module is allowed to be long — length alone is not a reason to split one.
- Source files: no line count is a violation. This project's module-boundary rule
  already states the real boundary, so a source file that grows far beyond its
  peers is a signal to check *structure*, not length: does it import something the
  boundary forbids, is it performing two named modules' jobs, or has a function
  accreted unrelated responsibilities? A structural boundary violation is caught
  by the module-boundary and import-boundary rules and is reported as such; it
  SHALL NOT be reported as "the file is too long."
- This section does not apply to files the rule is not about: frozen plans,
  interface files, the SRS, `tests/traceability.json`, and
  `tests/fixtures/*.py` data modules are exempt. A long frozen document is a
  documentation-shape question, not a code-responsibility one.

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

## Chunk pipeline auto-chaining
When Project mode runs a chunk's pipeline (plan-writer → plan-reviewer →
chunk-implementer → gate-verifier) as one wave, chain automatically between
members — don't pause for confirmation on the happy path. But if any
member's report contains one of the following, stop the chain immediately,
do not attempt to resolve it yourself or reroute it to a different member,
and relay the member's report to the user in full:
- plan-reviewer leaving Status as DRAFT, for any reason (a failed audit
  check or an unresolved open question).
- chunk-implementer reporting a file outside the plan's "Files touched," or
  a requirement whose behavior is ambiguous even after reading the cited
  SRS text.
- gate-verifier reporting any Definition of Done bullet as FAIL.
These are deliberate human checkpoints, not implementation gaps.

## Plan review and audit
- Counting is part of auditing. Any statement in a plan or an audit report that
  asserts a countable property of an existing artifact — node, marker, line,
  entry, table-row, or symbol count — SHALL be verified by querying that
  artifact, never by cross-reading the plan or any other document. A count
  asserted in a document is not evidence about the artifact.
- The audit report SHALL state how it counted, not merely that it counted. It
  SHALL distinguish at minimum: distinct identifiers (node IDs, LREQ IDs) from
  occurrences (marker lines, matches); table rows from line numbers; 1-based
  line numbers from newline or trailing-newline counts; and matches against real
  code from matches against prose, docstrings, comments, or test-file headers.
- The report SHALL label every factual claim as quoted from a source (opened and
  read) or counted in a source (queried, method named), and SHALL label a claim
  that is neither as unverified. An unverified claim SHALL NOT be certified
  correct because an earlier pass agreed with it.
- Agreement between passes is not verification. Repetition of a number from an
  earlier document is not evidence for it; only a count of the artifact is.
- This section applies to any task that authors or audits a countable claim,
  including in-flight dispatches.
- Any count that is written into a frozen document — a plan, an interface file,
  or a rule file — SHALL be accompanied, in the report the document is drawn
  from, by the anchored enumeration that produced it: the exact query, quoted
  so it can be re-run verbatim; the row or match count that query returned; the
  matched lines themselves, or for a long list the full list of line numbers
  plus enough verbatim text to identify each; the arithmetic reconciliation
  when the total is composed of parts, every matched line assigned to exactly
  one category with the addition shown; and an explicit statement of which unit
  each number is — distinct identifiers from occurrences; table rows from line
  numbers; decorator lines from substring matches; real code from prose,
  docstrings, comments, or headers. A number that arrives without its
  enumeration has not been audited, however it was labeled.
- A number is not verified by being agreed with. A second reviewer that has not
  re-run the query has not verified the count and SHALL NOT present agreement
  as confirmation. Where a claim about an artifact is checkable by opening or
  querying that artifact, a reviewer that did not do so SHALL label the claim
  unverified rather than pass it.