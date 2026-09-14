# Chunk {ID} — {TITLE}

Status: DRAFT | REVIEWED | FROZEN | IMPLEMENTED | VERIFIED
Depends on (frozen interfaces required before this plan can be trusted):
  {list of interfaces/chunk-XX.md, or "none"}
Blocks (chunks whose plan/implementation needs this chunk's interface):
  {list}

## 1. Goal
One paragraph. What this chunk makes true that wasn't true before.

## 2. Scope
### In scope
- ...
### Explicitly out of scope (and who owns it instead)
- Use the dependency map's own language: "supporting contract chunk" vs
  "primary implementation chunk" vs "integration completion chunk." Name the
  chunk that completes anything this chunk only partially satisfies.

## 3. Requirements this chunk must satisfy
For every LREQ ID this chunk owns (primary, supporting, or completion),
in a table:

| LREQ ID | Ownership role here | Normative text (from SRS-lean.md, quoted/derived) | SRS section |
|---|---|---|---|

Pull the actual text from SRS-lean.md. Do not summarize from the dependency
map alone — the dependency map records ownership and edge cases, not the
requirement's exact SHALL/SHOULD wording.

## 4. Interface contracts consumed
For each dependency listed above, the exact function signatures, types, enums,
or schema fragments this chunk is allowed to assume exist. Copied from
interfaces/chunk-XX.md, not re-derived from reading that chunk's source code.
If a needed interface file doesn't exist yet, this is a blocking open question
— do not guess the contract.

## 5. Interface contract this chunk produces
The public surface downstream chunks may depend on: function signatures,
types, enums, DB tables/columns, status values. This becomes
interfaces/chunk-{ID}.md verbatim once frozen (Prompt D).

## 6. Files touched
| File | New/modified | Purpose |
|---|---|---|

## 7. Task breakdown
Ordered checklist, each item tagged with the LREQ ID(s) it implements.
- [ ] ... (LREQ-...)

## 8. Edge cases and invariants
Pulled from the dependency map's "Edge cases" column for every LREQ this
chunk owns, plus any invariant stated in the chunk's own gate/description
(e.g. "failed page never becomes zero assets").

## 9. Test plan
- Test file(s) to create/extend.
- Golden vectors / fixtures needed, with source (SRS example, hand-derived).
- Exact pytest lreq markers required, mapped 1:1 to section 3's LREQ IDs.
- traceability.json entries to add.

## 10. Definition of done (gate)
Copied **verbatim** from the dependency map's Gate section for this chunk.
Do not reword, soften, or summarize. Add nothing that isn't testable.

## 11. Explicit prohibitions
Concrete "must not" statements specific to this chunk (e.g. "must not read
system clock," "must not import sqlite3," "must not issue a bulk-enrichment
request before the preflight gate passes").

## 12. Open questions / assumptions
Anything ambiguous in the source documents. Leave unresolved rather than
guessing; flag for human decision before Prompt B freezes the plan.