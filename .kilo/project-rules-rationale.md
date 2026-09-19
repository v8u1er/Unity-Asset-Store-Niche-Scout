# Rationale and incident record

Not normative and not loaded by any agent by default. This file preserves the
evidence behind `.kilo/project-rules.md`; the rules file states the rules, this
file states why they exist. A rule is changed in `.kilo/project-rules.md`, not
here.

Migration note: historical documents cite this rules file as
`.cursor/rules/project-rules.md`. It now lives at `.kilo/project-rules.md`. The
section headings are unchanged, so earlier by-name citations still resolve.

## Retired chunk pipeline

The "Chunk pipeline auto-chaining" rule was written for a Cursor-era pipeline of
`plan-writer → plan-reviewer → chunk-implementer → gate-verifier`. Those roles no
longer exist as agents; their definitions survive only under
`Documents/retired-documents/agents/`. The current setup is a `chunk-lead`
primary agent dispatching `chunk-planner`, `test-author`, `impl-fast`,
`impl-deep`, and `spec-reviewer` (see `.kilo/agents/` and the `agent` block in
the global `kilo.jsonc`). The rule was retargeted to the current roles; the
human-checkpoint intent is unchanged.

## File size and splits

The file-size section is a review trigger, not a gate. Splitting a test file
changes frozen `Documents/plans/*.md` "Files touched" tables, pytest node IDs,
and `tests/traceability.json`; that is a chunk-shaped change needing its own plan
and gate, so no agent performs it mid-task. As of the trigger's adoption,
`tests/test_collector.py` and `tests/test_database.py` were already over the
threshold and deliberately left unsplit.

## Scratch space and the destructive probe

The probe-path rule exists because a probe that tested `Move-Item -Force`
semantics against a real plan file destroyed that file. The probe succeeded —
`-Force` was not refused — and the artifact was the casualty. A probe's value
never justifies pointing it at something not reproducible: a real plan,
interface, source, test, or fixture path is never the probe's input, target, or
output.

The single-copy snapshot rule was adopted 2026-09-19 after six working-tree hunks
(part of a 68-line/6-line delta) existed in no other form and could not be
restored from anywhere. `git diff` output is a description of what changed, not a
copy of the changed content, and cannot restore a deleted hunk. Completeness is
not a precondition for a snapshot commit; a document that self-declares DRAFT
makes the snapshot an accurate record of its actual state.

## Counting and auditing

The counting rules exist because six errors of one kind occurred in one chunk: a
countable property asserted rather than re-derived (a marker count; a node
composition; a per-file entry count; a node total; a cross-file docstring
contamination; a claimed tool capability). Every one was caught by re-running a
query against the artifact, and none by re-reading a report. A number that
arrives without its anchored enumeration has not been audited, however it was
labeled.

A single mis-derived count propagated into a plan, an interface file, and a
dispatch brief before anyone followed it forward. The origin was fixed first and
the inherited copies kept circulating, which is why the fix scope is the full
forward transmission path rather than the origin point.

A record is not neutral history: a completed-but-wrong item sitting unflagged
next to its own correction re-enters circulation, because an agent reading the
list sees a completed item as decided. The check was performed and recorded, and
the record was not then consulted.

## Inferring content from tooling

The "Verification of existence, change, and content" section addresses one
failure shape: inferring an artifact's content or existence from a tool's
metadata instead of opening and reading the region in question. Five observed
instances, compressed:

1. A search for a specific line missed the word "Caveat" in that line, and the
   miss was recorded as "no such caveat exists" — the caveat paragraph was
   present and bolded in the file.
2. A subagent inferred a "Dated correction block" from a `git diff` hunk header
   and reported it as file content; no such block existed.
3. A directory listing run from the wrong working directory returned empty, and
   the emptiness was recorded as "that directory was not pulled into the repo" —
   the directory existed with two files in it.
4. A section header was quoted from memory instead of read, the actual file said
   something different, and the remembered header was stated as the REASON for a
   placement decision that happened to be correct anyway.
5. A `git status` listing and a `git diff --numstat` listing were compared, a
   discrepancy was recorded between them and labeled as counted, and a
   programmatic set comparison later proved the two lists one-to-one identical.
   The disagreement did not exist; it had been inferred from the shape of the two
   outputs, and it propagated into a later report because it sat in a dispatch
   brief.

## Lossy git extraction and phantom diffs

Text-mode redirection of git output in PowerShell — `git show ... > file`,
`Out-File -Encoding utf8`, `Set-Content`, and any `| Out-File` pipeline — rewrites
LF line endings to CRLF and prepends a UTF-8 BOM. MEASURED on this repository: a
118,618-byte blob became 121,865 bytes under `Out-File -Encoding utf8`, and the
transformation MANUFACTURED a non-empty diff between HEAD and the working tree
where the two were in fact identical. PowerShell's `>` redirection operator, in
some configurations, defaults to UTF-16 and mangles non-ASCII content outright.

A phantom diff of this shape is worse than no comparison, because it arrives as a
finding and is then cited as one. A stale index entry that produced the appearance
of a three-way document disagreement and a lossy extraction that produced a
phantom diff are the same defect: a tooling artifact masquerading as a content
finding.

The "name the two endpoints" rule was added after a ~369-line figure was reported
as an uncommitted single-copy exposure when the measured uncommitted delta was 75
lines across 3 files; the difference was a HEAD-to-worktree line-count delta being
reported as a pending-change delta. The rule fired correctly — a snapshot was
warranted — but the exposure was overstated roughly 5x. The same conflation
appeared earlier as a clean HEAD being repeated as a clean working tree.
