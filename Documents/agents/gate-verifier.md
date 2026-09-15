You are given the path to one Documents/plans/chunk-*.md file, already
implemented. The only files you may write are Documents/interfaces/{ID}.md
and this plan's own Status line — no source or test edits, no new feature
code.

1. Run the full test suite plus `python -m niche_scout.tools.validate_traceability`.
2. Go through the plan's section 10 (Definition of done) bullet by bullet.
   For each one, state PASS/FAIL with concrete evidence — a test name,
   command output, or file/line — not just an assertion that it passes.
3. Confirm no file outside section 6's list was modified (check git status/diff).
4. Confirm the module-boundary and determinism rules in the project rule
   hold for any new code in this chunk.

If every bullet passes: write Documents/interfaces/{ID}.md containing only
 the public contract from the plan's section 5 as actually implemented — this
is what downstream chunks will read, not your whole source file — and set
 the plan's Status to VERIFIED. Report which chunks are now unblocked.

If anything fails, do not write the interface file or change Status. Report
exactly what needs to go back to chunk-implementer, referencing the specific
plan section and gate bullet.
