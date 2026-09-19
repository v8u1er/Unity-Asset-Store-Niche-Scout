---
description: Niche Scout project rules — normative constraints for all agents and subagents; deduplicated against AGENTS.md
alwaysApply: true
---

Rationale and incident record: `.kilo/project-rules-rationale.md`.

## Source-of-truth precedence
1. `Documents/SRS-lean.md` — normative requirement text. Never paraphrase from
   memory; open the file and quote or derive it.
2. `Documents/requirements-dependency-map.md` — chunk ownership, gates, edge cases.
3. `Documents/plans/chunk-*.md` — the frozen scope contract for one chunk.
4. `Documents/interfaces/chunk-*.md` — frozen public contracts from completed chunks.

Chat turns, dispatch briefs, and this file are never a source of requirement text,
interface dependencies, or gate criteria when they conflict with the files above. A
chunk identifier is a pointer; the files define its scope.

## Architecture rules (non-negotiable, all chunks)
- Module boundary is fixed. Pure: `models.py` (typed structures), `validation.py`
  (structural/semantic validation primitives), `sampling.py` (deterministic
  sampling), `metrics.py` (eligibility + raw estimators), `scoring.py`
  (normalization, score components, evidence, sensitivity). I/O and orchestration
  only: `collector.py`, `collector_coveo.py`, `collector_graphql.py`,
  `database.py`, `pipeline.py`, `report.py`, `cli.py`.
- `metrics.py` and `scoring.py` never import `sqlite3`, network, filesystem, or CLI
  APIs and never read the clock; `scoring_cutoff_utc` is always an explicit
  parameter. Purity, missing-not-zero, time, and precision: see `AGENTS.md`
  "Hard rules" 1–4.
- Determinism: same inputs + policy versions → equivalent results. No RNG in
  sampling; no clock reads in pure code.

## Test traceability (non-negotiable, all chunks)
Every analytical test carries `@pytest.mark.lreq("LREQ-....")` and a matching
`tests/traceability.json` entry; parameterized tests map by base pytest node ID; run
`python -m niche_scout.tools.validate_traceability` before declaring a chunk done.
Details: `AGENTS.md` "Tests and quality" and `tests/AGENTS.md`. Traceability counts
are countable claims — verify per "Plan review and audit".

## Scope discipline
- A chunk's frozen `Documents/plans/chunk-XX.md` is the only scope authority for
  that chunk. Do not implement behavior the plan assigns to another chunk.
- Missing or ambiguous behavior: write it to the plan's "Open questions" (planning
  tasks) or stop and ask (implementation tasks). An open question blocks the plan's
  freeze until a human resolves it; no agent clears it alone.

## File discipline
- Touch only files in the active chunk's plan §6 "Files touched." If another file
  must change, stop and flag it instead of editing it.
- Growth inside an authorized file is in scope; crossing a threshold in "File size
  and concern boundaries" is a report item, not a silent continuation and not a
  mid-task split.

## File size and concern boundaries

Review triggers, not gates. Crossing a threshold never blocks a chunk, never fails a
Definition of Done bullet, and never justifies a split that changes a frozen
interface, a pytest node ID, or a `tests/traceability.json` entry. Output: a note
plus a proposed split boundary in the implementer's (`impl-fast`/`impl-deep`)
report; a split is a scope decision for a human or a plan.

- Test files at roughly 800–1,000 lines: propose a split along requirement-cluster
  boundaries (the clusters the LREQ ownership matrix and the file's own
  `@pytest.mark.lreq` markers distinguish), never a mechanical "file A / file B"
  cut. A split SHALL NOT duplicate or rename a pytest node ID; unchanged nodes keep
  byte-identical `tests/traceability.json` entries, and a moved node keeps its ID
  and gains a traceability path update in the same change.
- Fixtures are data, not logic: golden vectors, parametrized tables, and captured
  response bodies belong in `tests/fixtures/*.py`; an inert data module may be long.
- Source files: no line count is a violation. A file far larger than its peers is a
  signal to check structure (forbidden imports, two named modules' jobs, accreted
  responsibilities), reported as a boundary violation, never as "too long."
- Exempt: frozen plans, interface files, the SRS, `tests/traceability.json`, and
  `tests/fixtures/*.py`.

## Temporary scripts and scratch space
- Throwaway scripts, probes, and temporary output go only in `.scratch/` at the
  repository root; never write outside the repository. Naming, header, running, and
  cleanup: `.scratch/README.md`.
- No probe SHALL name a real artifact path as its source or destination. Use a
  scratch source and a scratch destination under `.scratch/`; a real plan,
  interface, source, test, or fixture path is never a probe's input, target, or
  output, whatever the probe's purpose.
- A single-copy uncommitted delta above roughly a few hundred lines SHALL be
  committed as a DRAFT/WIP snapshot as soon as noticed, finished or not. Commit a
  file before any write against it: `git diff` describes a change but cannot restore
  a deleted hunk.

## Chunk pipeline auto-chaining
Chain automatically between stages when `chunk-lead` dispatches `chunk-planner`,
`test-author`, `impl-fast`/`impl-deep`, `spec-reviewer`; do not pause on the happy
path. Stop immediately, do not reroute, and relay the member's report to the user in
full when:
- `chunk-planner` returns `QUESTIONS`/`BLOCKED` or leaves a plan at DRAFT (failed
  audit check or unresolved open question);
- `impl-fast`/`impl-deep` reports a file outside the plan's "Files touched," or a
  requirement ambiguous even after reading the cited SRS text;
- `spec-reviewer` reports a Blocker or Major surviving the allowed fix rounds.

These are deliberate human checkpoints, not implementation gaps.

## Plan review and audit
- A statement asserting a countable property of an existing artifact — node,
  marker, line, entry, table-row, or symbol count — SHALL be verified by querying
  that artifact, never by cross-reading the plan or another document.
- State how you counted, and distinguish: distinct identifiers from occurrences;
  table rows from line numbers; 1-based line numbers from newline counts; matches in
  real code from matches in prose, docstrings, comments, or headers.
- Label every factual claim quoted (opened and read), counted (queried, method
  named), or unverified. Agreement between passes is not verification; a reviewer
  that did not re-run the query labels the count unverified rather than passing it.
- A count written into a frozen document (plan, interface, or rule file) SHALL ship,
  in the report it is drawn from, with its anchored enumeration: the exact query
  quoted so it can be re-run verbatim; the row or match count it returned; the
  matched lines, or the full list of line numbers plus identifying text; the
  arithmetic reconciliation when the total is composed of parts, every matched line
  in exactly one category with the addition shown; and the unit of each number.
- Dispatch briefs propagate. A lead asserting a fact in a brief SHALL ground it the
  same way it requires of the report it receives, and SHALL state which claims are
  read, counted, or unverified.
- A record is not neutral history: where a claim and a prior refutation coexist,
  surface the refutation where the claim is next dispatched or acted on; it is the
  operative entry, and a completed-but-wrong item SHALL NOT be read as settled.
- The fix scope for a propagated citation is the full forward transmission path, not
  the origin: trace forward to every place that cited or relied on a wrong locant,
  name, or claim and correct each one.
- Applies to any task that authors or audits a countable claim, including in-flight
  dispatches.

## Verification of existence, change, and content
- A claim that something exists, was changed, or contains specific text SHALL be
  backed by an actual read. A search result, a tool's return value, or the absence
  of a match is not a read.
- The absence of a match is not evidence of absence; a search returning nothing
  supports only that the search returned nothing.
- Metadata is not content: a diff hunk header, filename, path, directory listing,
  cross-reference, commit subject, or citation states something about an artifact,
  not what the artifact says. None SHALL be reported or quoted as its contents.
- Where a claim is checkable by opening or querying the artifact, an agent that did
  not do so SHALL label it unverified; repetition from an earlier document,
  dispatch, or report does not verify it.
- Tool output is not self-authenticating: state which tool produced a value and what
  it measures, and treat a zero or a total as inconclusive without a second,
  differently-shaped query that would fail if the first were wrong. Where the tool's
  own semantics are the uncertainty, do not repeat the same tool with the same flags.

## Extracting git objects for comparison
- Extraction of a git object (blob, tree, or file revision) for comparison against a
  working-tree file SHALL be byte-exact; a non-byte-exact extractor yields a new
  document, not a copy.
- Forbidden, because each rewrites the bytes: text-mode redirection of git output in
  PowerShell (`git show ... > file`, `Out-File -Encoding utf8`, `Set-Content`, any
  `| Out-File`) — lossy; it rewrites LF to CRLF and prepends a UTF-8 BOM — and
  PowerShell's `>` operator, which can default to UTF-16 and mangle non-ASCII
  content.
- A diff from a lossily-extracted copy is not evidence; part of it is an artifact of
  the extractor. A phantom diff is worse than none, because it arrives as a finding
  and is then cited as one.
- Required methods: `git hash-object` for identity, `git diff --no-index` between
  two real paths, or a byte-exact write. Where identity is the question, compare
  hashes, not file text.
- A dispatch brief asking for a git-object diff SHALL name the extraction method; the
  report SHALL state which method was used.
- Any line-count or content delta SHALL name the two revisions or states compared. A
  HEAD-to-worktree line-count delta SHALL NOT be reported as "committed vs
  uncommitted," a pending-change size, or a dirty working tree.
