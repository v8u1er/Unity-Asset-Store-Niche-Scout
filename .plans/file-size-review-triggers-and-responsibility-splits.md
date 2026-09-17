# File size review triggers and responsibility splits

# Plan — File-size review triggers and concern-boundary splits

## Goal

Add a small, non-gating rule that keeps long files and multi-concern files visible to agents before they grow worse, using the split boundaries the project already defines (module boundary, requirement clusters, fixtures-as-data) rather than an arbitrary line count. No new mechanism, no new tooling, no code changes.

Two rule surfaces are touched:

- `.cursor/rules/project-rules.md` — the always-applied rule that agents read on every turn. Add a new `## File size and concern boundaries` section and one cross-reference line in `## File discipline`.
- `Documents/agents/chunk-implementer.md` — the only pipeline member that grows files during implementation, and the only one whose report is the natural place to surface the observation.

Deliberately **not** touched: `AGENTS.md` (a condensed mirror; adding a third copy of the same rule would create three places to keep in sync), `plan-reviewer.md`, `plan-writer.md`, `gate-verifier.md` (a review trigger is not a gate, and the plan/interface files are not test or source files), and any file under `src/` or `tests/`. No file is split by this plan.

## Verified starting state

These counts were **queried** (Grep with `output_mode: "count"`), not read from prose. Unit note: Grep's count is matching lines, and every counted line here is a non-blank line matched by the pattern `.` (a literal full stop does not match a blank line), so the unit is "non-blank lines", which for these files equals total lines read by `Read`'s `total_lines` within ±1 for a trailing-newline difference.

Query 1 — `Grep(pattern=".", glob="*.py", path="tests", output_mode="count")`:

| File | Non-blank lines |
|---|---|
| `tests/fixtures/validation_fixtures.py` | 437 |
| `tests/fixtures/coveo_discovery.py` | 376 |
| `tests/fixtures/graphql_fixtures.py` | 939 |
| `tests/fixtures/config_fixtures.py` | 139 |
| `tests/test_collector.py` | 2113 |
| `tests/test_database.py` | 1953 |
| `tests/test_validation.py` | 1048 |
| `tests/test_contracts.py` | 966 |
| `tests/test_identity.py` | 778 |

Query 2 — `Grep(pattern=".", glob="*.py", path="src", output_mode="count")`:

| File | Non-blank lines |
|---|---|
| `src/niche_scout/collector_graphql.py` | 2069 |
| `src/niche_scout/collector_coveo.py` | 1956 |
| `src/niche_scout/validation.py` | 1675 |
| `src/niche_scout/database.py` | 1581 |
| `src/niche_scout/models.py` | 418 |
| `src/niche_scout/config.py` | 244 |
| `src/niche_scout/tools/validate_traceability.py` | 158 |
| `src/niche_scout/tools/check_import_boundaries.py` | 132 |
| `src/niche_scout/collector.py` | 53 |
| `src/niche_scout/scoring.py` | 41 |
| `src/niche_scout/metrics.py` | 37 |

Facts that shape the rule's wording:

1. Two test files already exceed the proposed test trigger and one is close: `test_collector.py` (2113), `test_database.py` (1953), `test_validation.py` (1048).
2. Three source files already exceed any "few hundred lines" reading: `collector_graphql.py` (2069), `collector_coveo.py` (1956), `validation.py` (1675), `database.py` (1581). All four are single *concern* modules by the project's own boundary (`collector_coveo.py`/`collector_graphql.py` are explicitly sanctioned adapters; `validation.py` and `database.py` are named responsibilities). This is the evidence for making the source-side trigger structural rather than numeric, and for not inventing a source-side line threshold that every sanctioned module already violates.
3. Fixtures are already separated from test logic under `tests/fixtures/` (`config_fixtures.py`, `coveo_discovery.py`, `graphql_fixtures.py`, `validation_fixtures.py`, re-exported by `tests/fixtures/__init__.py`). The rule's "separate data from logic" guidance restates an existing convention; it does not introduce one. `graphql_fixtures.py` at 939 lines is a live example of a data module that is legitimately long.
4. `tests/test_contracts.py::test_repository_protocol_and_schema_specification` and the `LREQ-TST-030` suite node show the project already tolerates one non-requirement "suite" node per file alongside requirement-cluster nodes. A split proposal should preserve that shape rather than forbid it.

## Steps

### Step 1 — `tests/identity-cluster-map.json` and other traceability inputs: do not authorize a split as part of this change

No edit. This step is a constraint recorded so the executing agent does not go further than the plan says:

- `tests/traceability.json` keys analytical tests by pytest node ID. A split that renames or moves node IDs invalidates entries; a split that *copies* node IDs into two files creates duplicate node IDs and is worse.
- Because every LREQ cluster boundary in a test file is already visible in `tests/traceability.json` and in each frozen plan's `## 9. Test plan`, a proposed split boundary is derivable without new tooling. The rule must therefore say "propose a split along LREQ/requirement-cluster boundaries" and **must not** mandate a line counter, a script, or a gate.

### Step 2 — `.cursor/rules/project-rules.md`: add `## File size and concern boundaries`

Insert a new section immediately after `## File discipline` (i.e. between the current line 58 and the blank line before `## Temporary scripts and scratch space` at line 60). Verbatim content to insert:

```markdown
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
```

### Step 3 — `.cursor/rules/project-rules.md`: cross-reference from `## File discipline`

The file-size trigger is inert unless a reader of `## File discipline` knows it exists. Append two lines to the existing `## File discipline` bullet list (after current line 58, which ends `editing it.`):

```markdown
- Growth inside a file you are already authorized to touch is in scope, but a file
  crossing the thresholds in "File size and concern boundaries" is a report item,
  not a silent continuation and not a mid-task split.
```

Use `-` bullets and hard-wrapped prose consistent with the rest of the file (the file wraps at roughly 78 columns and uses `SHALL`/`SHALL NOT` for normative statements). Do not reflow or reformat any existing line in the file — the edit is purely additive.

### Step 4 — `Documents/agents/chunk-implementer.md`: make the report line mandatory

In the `As you go:` bullet list (current lines 20–29), insert one bullet after the existing "If you find yourself wanting to touch a file not listed in section 6..." bullet (current lines 24–26):

```markdown
- If a file you touched crosses the thresholds in the project rule's "File size
  and concern boundaries" section, say so in your closing report and propose a
  split along that section's stated boundaries. Do not perform the split: it is a
  change to the plan's "Files touched" list and therefore a scope decision, not a
  step you may add to section 7.
```

Then, in the closing paragraph (current lines 31–33), change the final sentence shape so the report has a fixed place for it. Replace:

```markdown
When the task breakdown is complete, run the test suite for the files you own
and return pass/fail. Do not change the plan's Status — that happens in
gate-verifier next.
```

with:

```markdown
When the task breakdown is complete, run the test suite for the files you own
and return pass/fail, plus any file-size/split observation from the project
rule's "File size and concern boundaries" section (state "none" explicitly if
there is none — an omitted observation is indistinguishable from an unchecked
one). Do not change the plan's Status — that happens in gate-verifier next.
```

The `state "none" explicitly` clause matters because of the project's own audit rule: an agent's silence about a countable property is not evidence that it checked.

### Step 5 — Verification (read-only; no test suite run required)

1. Re-read the edited `## File discipline` and `## File size and concern boundaries` sections and confirm the additions are additive only: `git --no-pager diff --stat .cursor/rules/project-rules.md Documents/agents/chunk-implementer.md` should show only added lines plus the one replaced closing sentence in `chunk-implementer.md`.
2. Confirm no `src/`, `tests/`, `Documents/plans/`, `Documents/interfaces/`, or `AGENTS.md` file appears in `git --no-pager status --porcelain`. `AGENTS.md` is intentionally left alone; a human can decide later whether to mirror the section there.
3. Confirm the new section does not contradict an existing rule by checking each claim against the file: the "no new gate" framing against `## Plan review and audit` (which governs *counts*, not file lengths) and the "no mid-task split" framing against `## File discipline` (which restricts the agent to the plan's `Files touched` list). Both are consistent; no existing sentence needs rewording.
4. Confirm `pytest` is unaffected: no `.py` file changes, so no node ID, marker, or `tests/traceability.json` entry can change. Do not run `validate_traceability` for this change; its inputs are untouched.

## Risks and non-goals

- **Risk: threshold creep into a gate.** The section is deliberately headed "review triggers, not gates" and every bullet says what the trigger does *not* authorize. If a later pipeline member starts failing a chunk on it, that is a rule violation, not an interpretation.
- **Risk: a split performed for the counter.** Mitigated by requiring the split boundary be stated in terms of LREQ clusters and by forbidding any split that renames or duplicates a node ID.
- **Non-goal: splitting any existing file.** `test_collector.py` (2113) and `test_database.py` (1953) are over the trigger today. This plan does not split them and does not authorize an agent to. Doing so would touch frozen plans' `## 6. Files touched` tables, `tests/traceability.json`, and possibly `Documents/interfaces/`; that is a chunk-shaped change needing its own plan and its own gate.
- **Non-goal: a line-count script or pre-commit hook.** Explicitly excluded; see Step 1.
- **Non-goal: editing `AGENTS.md`.** It is a condensed mirror of `project-rules.md`; a third copy of the same section is more sync burden than signal. Flagged here as a possible follow-up for a human, not done.

## Open questions

None. Every threshold in the new section (800–1,000 lines for tests; "a few hundred lines" as an explicitly non-binding signal for source files; exemption for fixture data modules and frozen documents) is a judgment call the user's own framing already made, and the user's instruction was to put it in the rule rather than to enforce it.
