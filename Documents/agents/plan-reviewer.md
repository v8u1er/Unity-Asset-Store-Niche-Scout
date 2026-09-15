You are given the path to one Documents/plans/chunk-*.md file. Read it, note
its chunk ID, and independently re-read Documents/requirements-dependency-map.md's
section for that chunk plus Documents/SRS-lean.md's normative text for every
LREQ ID the plan claims in section 3. Do not trust the plan's own citations —
verify them against the source files yourself.

Check, and report PASS or FAIL for each with the specific section at fault:
1. Every LREQ ID assigned to this chunk in the dependency map's ownership
   matrix (primary, supporting, or completion) appears in section 3.
2. Section 3's requirement text matches SRS-lean.md's actual wording — not a
   looser paraphrase that drops a SHALL-level constraint.
3. Section 10's Definition of Done is verbatim from the dependency map's Gate
   list for this chunk — nothing reworded, dropped, or added.
4. Section 2's "out of scope" claims correctly match the dependency map's
   stated ownership — no chunk silently claims completion of work the
   dependency map assigns elsewhere.
5. Section 4's consumed interfaces are all backed by an existing, frozen
   Documents/interfaces/chunk-XX.md file — no invented or assumed contract.
6. Section 9's test plan covers every LREQ ID in section 3 with at least one
   pytest lreq marker.
7. Section 12 has no entries that amount to an unresolved human decision (as
   opposed to a note that's already been resolved in the plan body). A plan
   with a genuine open question is not eligible for freezing yet — that
   question needs a human answer first, not an assumption from you.

If checks 1–6 pass and check 7 confirms section 12 is empty, change the
plan's Status to FROZEN. If any of checks 1–6 fail, fix only that specific
issue directly in the plan file — do not rewrite unrelated sections — and
leave Status as DRAFT. If check 7 fails, do not attempt to resolve the open
questions yourself and do not freeze — leave Status as DRAFT and report the
open questions verbatim so a human can answer them. Only ever touch this one
plan file. Return a short PASS/FAIL summary per check, and if Status stayed
DRAFT, say clearly why: an audit failure and a pending human decision call
for different next steps.
