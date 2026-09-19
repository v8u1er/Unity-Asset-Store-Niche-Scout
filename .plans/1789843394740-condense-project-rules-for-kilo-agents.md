# Plan — Condense `.kilo/project-rules.md` for the current Kilo agent setup

Status: READY FOR REVIEW
Owner: human / primary agent with `.kilo/**` edit permission (see "Who can implement")

## 1. Goal

Rewrite `.kilo/project-rules.md` (currently 343 lines) into a short, normative,
deduplicated ruleset that:
- keeps only rules not already stated in `AGENTS.md`, `tests/AGENTS.md`,
  `.kilo/agents/*.md`, or `.scratch/README.md` (those become one-line
  cross-references);
- uses the role names that actually exist in `.kilo/agents/`;
- moves the incident/rationale narrative to a separate, non-auto-loaded file.

No configuration change. The file keeps its path; `kilo.jsonc`, `AGENTS.md`,
agent files, `Documents/**`, `src/`, and `tests/` are not touched.

## 2. Constraints and decisions (already settled)

| Decision | Value |
|---|---|
| Scope | Rewrite `.kilo/project-rules.md` in place; add `.kilo/project-rules-rationale.md` |
| Kilo wiring | None. Do not edit `.kilo/kilo.jsonc` (user decision) |
| Rationale | One-line "Why" per rule inline; full incident record moves to the rationale file |
| Dedup target | `AGENTS.md`, `tests/AGENTS.md`, the six `.kilo/agents/*.md`, `.scratch/README.md` are the canonical homes; project-rules.md cross-references them |
| Section headings | Keep all 11 existing headings verbatim — frozen plans and rulings cite several by name (e.g. `§"Plan review and audit"`, `§"File discipline"`, `§"Temporary scripts and scratch space"`, `§"File size and concern boundaries"`) |
| Role names | Replace retired `plan-writer` / `plan-reviewer` / `chunk-implementer` / `gate-verifier` with current `chunk-planner` / `test-author` / `impl-fast` / `impl-deep` / `spec-reviewer` / `chunk-lead` |
| Frontmatter | Keep `description`; keep `alwaysApply: true`; drop the empty `globs:` key |
| Out of scope | `.kilo/windows.md` content, `AGENTS.md`, agent prompts, `kilo.jsonc`, the traceability.json shape conflict in `tests/AGENTS.md` |

## 3. Step 0 — snapshot the untracked single-copy files (blocking)

`.kilo/project-rules.md` (343 lines) and `.kilo/windows.md` (12 lines) are
**untracked**; the old `.cursor/rules/*` copies show as deleted. They exist in
one copy only, which the rules file itself forbids editing.

Before any rewrite, a committing role runs:

```powershell
git add -A .cursor .kilo
git commit -m "chore: move cursor rules into .kilo (WIP snapshot)"
```

Expected: the two `.cursor/rules/*` deletions and the two `.kilo/*` additions
are the only changes. Do not proceed to Step 1 until this commit exists.

## 4. Step 1 — create `.kilo/project-rules-rationale.md`

New file, clearly marked non-normative and not auto-loaded. Contents moved out of
the rules file:

- Intro line: "Rationale and incident record for `.kilo/project-rules.md`. Not
  normative; not loaded by any agent by default."
- Migration note: historical documents cite this file as
  `.cursor/rules/project-rules.md`; it now lives at `.kilo/project-rules.md`, and
  the section headings are unchanged.
- The retired-pipeline history (plan-writer → plan-reviewer → chunk-implementer →
  gate-verifier) explaining why the rules say what they say.
- Incident narratives currently inline, verbatim: the `Move-Item -Force` probe
  that destroyed a plan file; the six lost uncommitted hunks; the ~369-line vs
  75-line reporting error; the five "inferred from tooling" incidents; the
  measured lossy extraction (118,618 → 121,865 bytes); the mis-derived count that
  propagated into a plan, interface, and dispatch brief; the 2026-09-19 adoption
  date of the snapshot rule.

Add one pointer line at the top of the rewritten rules file:
`Rationale and incident record: .kilo/project-rules-rationale.md`.

## 5. Step 2 — rewrite `.kilo/project-rules.md`

Target: roughly 100–140 lines. Line count is a result, not a gate; no normative
rule may be dropped to hit a number.

Disposition per existing section:

| Current section | Action |
|---|---|
| Source-of-truth precedence | Keep the 4-item precedence ladder and the "chat turns / dispatch briefs are not sources" rule. Drop restatement of `AGENTS.md` file list. |
| Architecture rules | Keep the module-boundary list (pure: `models`, `validation`, `sampling`, `metrics`, `scoring`; I/O: `collector`, `collector_coveo`, `collector_graphql`, `database`, `pipeline`, `report`, `cli`) — this is not in `AGENTS.md`. Replace the purity/null/time/precision bodies with a cross-reference to `AGENTS.md` "Hard rules" 1–4. |
| Test traceability | Content duplicated by `AGENTS.md` "Tests and quality" + `tests/AGENTS.md`. Reduce to 2 lines: cross-reference those files; keep only "counts must be re-queried" as a pointer to Plan review and audit. |
| Scope discipline | Keep: frozen plan is the only scope authority; do not implement another chunk's behavior; an open question blocks freeze and only a human clears it. |
| File discipline | Keep: only touch files in plan §6 "Files touched"; growth inside an authorized file is in scope; boundary crossing is a report item, not a mid-task split; cross-reference to File size section. |
| File size and concern boundaries | Condense ~35 lines to ~8. Keep: the 800–1,000-line test trigger; split along requirement clusters; fixtures are data in `tests/fixtures/*.py`; source files have no line-count rule (check structure, not length); exempt list. Replace `chunk-implementer` with "the implementer (`impl-fast`/`impl-deep`)". |
| Temporary scripts and scratch space | Reduce to 3 bullets: use `.scratch/` (see `.scratch/README.md` for naming/header/cleanup); the probe-path rule (a probe never names a real plan/interface/source/test/fixture path as input or target); the single-copy snapshot rule. |
| Chunk pipeline auto-chaining | Retarget to the real pipeline. Keep "chain on the happy path; stop and relay to the user" and the stop triggers, with current role names: planner returns `BLOCKED`/`QUESTIONS`; implementer reports a file outside the plan or an unresolved ambiguity; reviewer returns Blocker/Major after the fix-round limit. |
| Plan review and audit | Condense ~60 lines to ~12. Keep: query the artifact for any count; state unit and method; anchored enumeration for counts written into frozen docs; agreement ≠ verification; dispatch briefs propagate → ground and label claims (read / counted / unverified); a recorded refutation is the operative entry; correct the full forward transmission path of a false citation. |
| Verification of existence, change, and content | Condense to ~5 bullets: read before claiming exists/changed/contains; no match ≠ absence; metadata ≠ content; label unverified; tool output is not self-authenticating → require a second, differently-shaped query. |
| Extracting git objects for comparison | Condense to ~6 bullets: byte-exact extraction required; forbidden lossy methods (`git show > file`, `Out-File`, `Set-Content`, `>`); name the two endpoints of any delta; state which extraction method was used; a phantom diff is not evidence. |

Style rules for the rewrite:
- Imperative `SHALL`/`MUST NOT` statements; no second-person narration, no
  restating the same rule twice under two headings.
- One "Why:" clause per non-obvious rule, maximum one line.
- Cite files by path; cite LREQ IDs where the original did.
- Do not introduce new rules, thresholds, or formulas.

## 6. Step 3 — validation

1. Record before/after counts with the exact query, e.g.
   `(Get-Content .kilo/project-rules.md).Count` and the same for the rationale
   file. State that this is a line count of each file.
2. Produce a disposition enumeration in the report: every existing heading and
   every original bullet assigned to exactly one of *kept*, *moved to rationale*,
   or *removed as duplicate of <file>*. Show the addition
   (`kept + moved + removed = original bullets`). Per the rules file, a count
   without its enumeration is not audited.
3. Grep the rewritten file for retired role names and confirm zero matches:
   `rg "plan-writer|plan-reviewer|chunk-implementer|gate-verifier" .kilo/project-rules.md`.
4. Confirm every referenced path exists: `.scratch/README.md`, `AGENTS.md`,
   `tests/AGENTS.md`, `tests/traceability.json`, `Documents/plans/`,
   `Documents/interfaces/`. Do not invent new paths.
5. Confirm no other file changed:
   `git status` and `git diff --stat` show only `.kilo/project-rules.md`
   (modified) and `.kilo/project-rules-rationale.md` (new).
6. Confirm the 11 headings still exist verbatim (anchor compatibility).

## 7. Step 4 — commit

`git add .kilo/project-rules.md .kilo/project-rules-rationale.md` then
`git commit -m "docs: condense project rules for Kilo agents"`.

## 8. Who can implement

The global config denies `edit` on `.kilo/**` for the chunk agents and for
`chunk-lead`. This rewrite must be done by the user or by a primary agent session
with `.kilo/**` edit permission. Do not dispatch it to `impl-fast`/`impl-deep`
(they will be denied and will report BLOCKED).

## 9. Open items (record, do not resolve)

- **Kilo loading is unverified.** `.kilo/project-rules.md` is not referenced by
  `kilo.jsonc` or `AGENTS.md`, and Kilo's documented instruction sources are
  `AGENTS.md`, `CLAUDE.md`, `CONTEXT.md`, plus the `instructions` config field.
  It may currently be inert in Kilo. The user chose not to wire it, so no config
  change is made; the rewrite is still correct if and when it is wired.
- `.kilo/windows.md` is also untracked and partly duplicates the Windows line in
  `AGENTS.md`. Out of scope here; Step 0 commits it.
- `tests/AGENTS.md` documents the inverse `tests/traceability.json` shape
  (LREQ-keyed) from the actual file (node-ID-keyed). Not this file; note only.
