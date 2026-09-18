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

## Verification of existence, change, and content
- Any claim about whether something EXISTS, was CHANGED, or CONTAINS specific
  text SHALL be backed by an actual read of that content. A search result, a
  search tool's return value, or the absence of a match is not a read and SHALL
  NOT be offered as evidence of existence, of change, or of content.
- The absence of a match is not evidence of absence. A search that returns
  nothing supports no claim beyond the search having returned nothing; an agent
  SHALL NOT record such a result as a finding that a file, section, line, or
  symbol does not exist.
- Metadata is not content. A diff hunk header, a filename, a path, a directory
  listing, a cross-reference, a commit subject, and a citation in another
  document each state something about an artifact without stating what the
  artifact says. None of them SHALL be reported as the artifact's contents, and
  none SHALL be quoted as if it had been read.
- Where a claim is checkable by opening or querying the artifact, an agent that
  did not do so SHALL label the claim unverified. An unverified claim is not
  verified by being repeated from an earlier document, an earlier dispatch, or
  an earlier agent's report.
- Tool output is not self-authenticating. A search tool can return a value that
  does not mean what it appears to mean — a `-SimpleMatch`-style flag silently
  ignored, a result column printing a different field than the one queried, a
  count of raw substring matches that includes prose, docstrings, comments, or
  headers. When a tool's output is the sole basis for a claim, the agent SHALL
  state which tool produced it, SHALL state what the returned value actually
  measures, and SHALL NOT treat a zero or a total as conclusive without a
  second, differently-shaped query that would fail if the first result were
  wrong. Where the tool's own semantics are the uncertainty, the second query
  SHALL NOT be the same tool with the same flags.
- A claim asserted in a dispatch brief propagates. A subagent cannot see the
  conversation that produced its brief, so a false premise in that brief will be
  returned in the subagent's report as though the brief were a source. A lead
  that asserts a fact in a brief SHALL ground that assertion the same way it
  requires of the report receiving it, and SHALL state in the brief which claims
  are read, which are counted, and which are unverified.
- The failure these rules address has one shape: inferring an artifact's content
  or existence from a tool's metadata instead of opening and reading the region
  in question. Five observed instances, compressed:
  1. A search for a specific line missed the word "Caveat" in that line, and the
     miss was recorded as "no such caveat exists" — the caveat paragraph was
     present and bolded in the file.
  2. A subagent inferred a "Dated correction block" from a `git diff` hunk
     header and reported it as file content; no such block existed.
  3. A directory listing run from the wrong working directory returned empty,
     and the emptiness was recorded as "that directory was not pulled into the
     repo" — the directory existed with two files in it.
  4. A section header was quoted from memory instead of read, the actual file
     said something different, and the remembered header was stated as the
     REASON for a placement decision that happened to be correct anyway.
  5. A `git status` listing and a `git diff --numstat` listing were compared, a
     discrepancy was recorded between them and labeled as counted, and a
     programmatic set comparison later proved the two lists one-to-one
     identical. The disagreement did not exist; it had been inferred from the
     shape of the two outputs, and it propagated into a later report because it
     sat in a dispatch brief.

## Extracting git objects for comparison
- Any extraction of a git object — a blob, a tree, or a file revision — for the
  purpose of comparing it against a working-tree file SHALL use a byte-exact
  method. An extractor that is not byte-exact does not produce a copy of the
  artifact; it produces a new document that differs from the artifact in ways
  that have nothing to do with the question being asked.
- Forbidden extraction methods. Each is forbidden because it rewrites the
  bytes, not because it is merely unfashionable:
  - Text-mode redirection of git output in PowerShell — `git show ... > file`,
    `Out-File -Encoding utf8`, `Set-Content`, and any `| Out-File` pipeline —
    is FORBIDDEN. It is LOSSY: it rewrites LF line endings to CRLF and
    prepends a UTF-8 BOM. MEASURED on this repository: a 118,618-byte blob
    became 121,865 bytes under `Out-File -Encoding utf8`, and the
    transformation MANUFACTURED a non-empty diff between HEAD and the working
    tree where the two were in fact identical.
  - PowerShell's `>` redirection operator, which in some configurations
    defaults to UTF-16, mangles non-ASCII content outright rather than merely
    changing its line endings.
- Consequence. A diff produced from a lossily-extracted copy is not evidence
  about the artifact, because part of the diff is an artifact of the extractor.
  A phantom diff of this shape can invent a divergence between two copies of a
  document that does not exist — the same failure the section above prohibits:
  recording a discrepancy that was inferred from tooling rather than read from
  the artifact. A phantom diff is worse than no comparison, because it arrives
  as a finding and is then cited as one.
- Required discipline. Use a byte-exact extraction: `git hash-object` for an
  identity comparison, `git diff --no-index` between two real paths, or a
  byte-exact write. Where identity is the actual question, compare object IDs
  or hashes rather than file text — a hash answers the identity question
  directly and cannot be perturbed by encoding, line-ending, or BOM drift.
- Declaring the extraction method. Any dispatch brief that asks a member to
  diff a git object against a working-tree file SHALL state which extraction
  method is to be used, and the resulting report SHALL state which method was
  actually used. This puts a phantom-diff cause in the report, where it can be
  seen, instead of leaving it to surface as an unexplained disagreement between
  two numbers.
- Same class as the isolated-index defect. A stale index entry that produced
  the appearance of a three-way document disagreement and a lossy extraction
  that produced a phantom diff are the same defect: a tooling artifact
  masquerading as a content finding. Both were fixed permanently rather than
  by a remembered caution, and this section is the permanent fix for the
  second.
