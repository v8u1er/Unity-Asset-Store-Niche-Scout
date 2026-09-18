# Tooling P0-2 — Traceability validator blind spot: declared-but-never-written nodes

Status: DRAFT
Depends on (frozen interfaces required before this plan can be trusted):
  none — this plan produces no runtime interface and consumes none. It changes
  `src/niche_scout/tools/validate_traceability.py`, a developer tool that is
  outside the SRS module boundary (SRS-lean.md §12 lists `cli.py`, `config.py`,
  `models.py`, `collector.py`, `validation.py`, `sampling.py`, `scoring.py`,
  `database.py`, `pipeline.py`, `report.py` and `tests/`; the tools package is
  not in it) and outside every frozen `Documents/interfaces/chunk-XX.md`.
Amendment 2026-09-18 (count-unit constraint, §5.7): the new check compares **distinct
marked node IDs** to `tests/traceability.json` **keys** (143 vs 143 today, exact); a
**marker-occurrence** count (152 today) is never an error signal, because stacked
distinct `@pytest.mark.lreq` decorators on one node are legitimate here
(`tests/test_database.py` 31/23/23, `tests/test_validation.py` 23/22/22). One §9
regression node was added and §11 gained Q-U, Q-V, Q-W. `Status` remains DRAFT.
Correction 2026-09-18 (mechanical): §11's Q-U / Q-V / Q-W had been claimed here before
they existed; they are now written, re-run against the tree, and their figures replace
the two wrong raw-substring numbers §5.7 carried (`153` / `154`; measured `158` / `152`).
Blocks (chunks whose plan/implementation needs this chunk's interface):
  none by interface. Behaviourally it blocks every chunk whose gate runs
  `python -m niche_scout.tools.validate_traceability`, in the sense that the
  new check decides whether that run is green: Chunk 1's plan §4.7 (its lines
  387–399), Chunk 5's plan §11 (its lines 1749–1750), and the dependency map's
  Chunk 13 gate bullet (`Documents/requirements-dependency-map.md` line 1098).
  The known pending user is the stalled Chunk 5 implementation: three nodes its
  frozen plan declares are exactly the defect this plan closes (§1, §4).

## 1. Goal

`src/niche_scout/tools/validate_traceability.py` is currently blind to an entire
class of traceability defect, and today's run demonstrates it. The tool exits **0**
with `Traceability valid: 7 Chunk 0 requirements mapped, 143 matrix nodes, 89 defined
LREQ IDs` (re-run for this plan: §11 query Q-M) while `tests/test_identity.py` is
missing all three test nodes that
`Documents/plans/chunk-05-graphql-protocol-adapter-and-response-correlation.md` §9
declares for it (its lines 1489–1491). This plan makes the tool able to see that class
of defect, at the one seam where it is visible without parsing a plan file: an LREQ ID
that the dependency map's ownership matrix gives a complete primary-owner chunk whose
completion chunks are also complete, and that the SRS Appendix B matrix assigns to a
test module, **has no `@pytest.mark.lreq` marker anywhere in `tests/`**.
After this plan the tool's exit code is a statement about declaration-and-delivery on
both axes it can actually observe — declared LREQ IDs versus marked LREQ IDs, and
declared matrix rows versus existing pytest nodes — rather than about whichever axis
happens to be non-empty on both sides.

## 2. Scope

### In scope

- A new **requirement-axis** check in `src/niche_scout/tools/validate_traceability.py`:
  every LREQ ID the SRS defines is classified into an explicit **status** (table in
  §5.1), and one status — `pending_setup_phase` — is a defect that makes `main`
  return 1. The defect set is derived from two repo artifacts and no plan file
  (§5.2).
- An explicit, per-ID documentation list for every ID excluded from the defect set
  on an "owned elsewhere / delivered by a different mechanism" argument, with the
  SRS anchor for each (§5.3). The excluded IDs are enumerated, not derived.
- Two distinct **counting units**, both named in the message: LREQ IDs (distinct
  identifiers) and pytest node IDs (distinct identifiers). The existing
  `len(matrix)` figure is replaced by a row count with its unit stated and its
  non-node rows reported separately (§5.4).
- Non-recursive test collection: the glob is replaced by a non-recursive module-path
  walk over `tests/` (§5.4).
- A **name-equality check as advisory warning only**: node names declared in plan
  documents under `Documents/plans/` that do not exist in `tests/`. It must be
  structurally incapable of affecting the exit code (§5.5).
- A new analytical test module for the tool, with `@pytest.mark.lreq` markers that
  must resolve to an existing SRS LREQ ID, plus its `tests/traceability.json`
  entries (§9). This is a Chunk 0 gate obligation, not decoration: Chunk 0's gate
  bullet (dependency map line 438) requires **every** analytical test to carry a
  marker and a matrix entry, and the tool's own `missing_nodes` check enforces it.
- A **reported baseline disclosure**: the repository's current suite is `6 failed,
  139 passed` (`python -m pytest tests -q`, run for this plan). That fact is
  recorded in this plan and must be repeated in the implementing agent's report
  (§4, §8.6, §12.1) so neither this plan's own verification nor a later gate can read
  a validator exit code as a statement about the suite being green.
- A **counting rule for marker data**, stated normatively in §5.7: the check compares
  **distinct marked node IDs** against `tests/traceability.json` **keys**, and a
  **marker-occurrence** count SHALL NOT be an error signal, because stacked distinct
  `@pytest.mark.lreq` decorators on one node are legitimate in this repository
  (`tests/test_database.py`: 31 decorator occurrences / 23 distinct marked node IDs /
  23 matrix rows; `tests/test_validation.py`: 23 / 22 / 22).

### Explicitly out of scope (and who owns it instead)

- **Widening the `missing_required` direction beyond Chunk 0's seven requirements.**
  Fixed by resolved decision **R-3** in `Documents/plans/chunk-01-pure-taxonomy-identity-and-response-validation.md`
  §12 (`Chunk 1 does **not** touch the tool`; its lines 396–399) and restated by
  Chunk 5's plan §11 (`Chunk 5 SHALL NOT widen tools/validate_traceability.py; its
  required-set widening is Chunk 13`, its lines 1749–1750). **`Chunk 13` owns it**
  and is its completion chunk (dependency map lines 126, 124, and 1097–1098). This
  plan changes no `chunk` parameter, no `Requirements primarily covered:` parsing,
  and no required-set membership.
- **Making Chunk 0's required-set block reflect other chunks.** `Chunk 13` owns it,
  for the reason above.
- **Re-running the current-looking figures in `Documents/plans/chunk-03-...md`
  (its line 5, `119 passed`) and `Documents/plans/chunk-05-...md` (its line 1264's
  `known Chunk 0 ... failure`).** Neither is an accurate description of the tree
  today (§12.1), but both are *planned* edits owned by the user's standing P0-3 item
  ("Fix the `119 passed` figures last, once Step D and Step E produce the real
  number"). The P0-3 chore owns both and this plan does not absorb a third document
  edit into a tooling plan.
- **Authoring the three missing Chunk 5 nodes in `tests/test_identity.py`.** They are
  implementation work owned by the **`Chunk 5` implementer**, and the user has
  already ruled them blocked behind the unresolved Q-2 contradiction in Chunk 5's
  own ruling document. The user's earlier ruling explicitly re-scoped the Chunk 5
  bookkeeping dispatch to exclude `marker-and-entry both absent` cases such as these
  three: *"3 of the 25 are marker-and-entry both absent (tests never written) — those
  are implementation work, blocked behind Q-2."* This plan's job is to make the
  validator capable of reporting them, not to write them.
- **A machine-readable manifest that tests/plans declare their node IDs into.**
  Considered and rejected on artifact evidence (§5.2, §12.2): no such file exists,
  the artifact that would host it (`tests/traceability.json`) is already the thing
  whose completeness is in question, and the hard-wired Chunk 0 scope (§12.1) is the
  real cause of the blind spot. The `Chunk 0` sub-gate owner would own creating one.
- **Chunk 0 gate re-verification.** The `Chunk 0` gate-verifier (or `Chunk 13`) owns
  re-running Chunk 0's bullets. This plan reports the effect on Chunk 0's tooling
  bullet as evidence (§8.6) and does not re-open Chunk 0's Status.
- **`src/niche_scout/tools/check_import_boundaries.py`.** Out of scope; it is a
  different tool with a different rule (`metrics.py` / `scoring.py` purity). If this
  plan turns out to need a change there, that is a stop-and-flag event (§11, §12.4).

## 3. Requirements this chunk must satisfy

This plan owns **no primary LREQ**. It is a tooling change on the shared
requirement-and-test management surface. The table below records the LREQ IDs whose
text the change must stay inside, with ownership role named in the dependency map's
own vocabulary.

| LREQ ID | Ownership role here | Normative text (from SRS-lean.md, quoted/derived) | SRS section |
|---|---|---|---|
| LREQ-NFR-060 | Not this plan's. Primary owner is **Chunk 13**; Chunk 0 is a supporting contract chunk; this plan is an in-flight edit to an artifact Chunk 0 produced, with no ownership claim. Dependency map line 126: `\| LREQ-NFR-060 \| Chunk 13 \| Chunk 0 \| Chunk 13 \| LREQ-NFR-060 \|` | "Formatting, linting, secret handling, and analytical tests SHALL be part of the normal workflow. Strict project-wide typing, 95% whole-package coverage, and CI-on-every-commit are deferred quality improvements, not lean MVP blockers." (lines 1177–1180) | §11 |
| LREQ-TST-010 | Not this plan's; **Chunk 13** is primary and completion, Chunk 0 a supporting chunk (dependency map line 127). Cited only because this plan adds analytical tests, and "Every formula SHALL have tests for normal values, explicit valid zero where applicable, missing values, invalid values, ties, and minimum boundaries" (lines 1225–1226) is the nearest normative statement of the project's analytical-test convention. It does not enumerate this tool's cases; the cases in §9 are derived from the tool's own observable outputs (§9). | §13 |
| LREQ-ARCH-010 | Not this plan's; **Chunk 0** is primary and completion (dependency map line 47). Cited for one boundary the change must not cross: the tool lives outside `metrics.py` / `scoring.py` and must not become an import-boundary subject. The relevant text is the purity boundary in SRS §3.3 (lines 225–238) read together with the matrix row. | §3.3 |
| LREQ-TST-030 | Not this plan's. **Chunk 13** is primary; supporting chunks are **Chunk 1, Chunk 5, Chunk 6B** — this plan is not among them (dependency map line 129). Named here only to record that the node set whose absence this plan detects (`tests/test_identity.py`) is Chunk 1's and Chunk 5's test surface, never this plan's. | §13 |

**There is no LREQ that requires this check to exist, and this plan does not claim one.**
The nearest text is Chunk 0's gate bullet (`Documents/requirements-dependency-map.md`
line 439): "The traceability validator passes in both directions: every referenced LREQ
exists and every individual LREQ has at least one mapped test." That bullet has been
satisfied since Chunk 0 by the tool's **matrix-referenced** axis, and this plan does not
reinterpret it ([INV-4], §8). The justification for the check is the observed defect
(§4), the dependency map's Chunk 13 gate bullet (line 1097: "a machine-checkable
bidirectional traceability check verifies that every required test maps to valid
individual `LREQ-*` IDs and **every individual `LREQ-*` has at least one required test
reference**"), and the user's own authorization of this work as its own plan. A reviewer
who concludes no check may exist without an LREQ should record that as an objection in
§12.2, where the reading that the Chunk 13 bullet is normative for the final state but
**deferred to Chunk 13** already lives.

## 4. Interface contracts consumed

None. This plan consumes no `Documents/interfaces/chunk-XX.md` and none is required:
the artifacts it reads are `Documents/SRS-lean.md`, `Documents/requirements-dependency-map.md`,
`tests/traceability.json`, `tests/*.py`, and (for advisory warnings only)
`Documents/plans/*.md` — all of which exist.

The **observed defect this plan closes** — quoted from the artifacts, each claim
labelled by how it was established:

- `src/niche_scout/tools/validate_traceability.py` reads no plan file. **Quoted**
  (read in full, 188 lines): its only path constants are `SRS_PATH`,
  `DEPENDENCY_MAP_PATH`, `TESTS_DIR`, and `TRACEABILITY_PATH` (lines 25–29).
- `main` narrows the "required" set to Chunk 0's seven requirements by calling
  `chunk_requirements(...)` with its default `chunk="0"` (line 131). **Quoted.**
- The dependency map declares each chunk's requirements under a heading that is
  **not** `Requirements primarily covered:` for later chunks — Chunk 13 uses
  `Requirements:` (line 1083). **Quoted** (dependency map lines 1083–1086).
  Consequence: `chunk_requirements` raises `ValueError` for any chunk except Chunk 0
  (`validate_traceability.py` lines 67–70). This is the same hard-wiring Chunk 1's
  plan recorded at its lines 601–606 and Chunk 5's plan at its lines 1558–1561.
- A **declared-but-never-written** node is therefore invisible: **counted** (§11
  query Q-A). The three node names `test_correlated_product_detail_reports_alias_mismatch`,
  `test_missing_returned_identity_is_not_an_implicit_match`, and
  `test_adapter_mismatch_is_a_flag_not_a_metric_exclusion` each occur **0** times in
  `tests/` (marker: 0, matrix entry: 0) and once each in
  `Documents/plans/chunk-05-graphql-protocol-adapter-and-response-correlation.md`
  (its lines 1489, 1490, 1491). Chunk 5's plan declares them twice — in its §9 node
  table (lines 1489–1491) and in its §6 files-touched row for `tests/test_identity.py`
  (its line 1168). Its §7 task box at its line 1251 instructs the implementer to add
  them.
- `/tmp/cov-30probe.txt` does not exist on this machine, so Chunk 3's report flag is
  **not** evidence that Chunk 3's three nodes were ever written. **Re-verified
  (filesystem probe)**; recorded because the P0-2 authorization cites those three
  nodes as the motivating precedent.
- The suite's real state today is **counted** (§11 query Q-M):
  `python -m pytest tests -q` → `6 failed, 139 passed`, all six in
  `tests/test_collector.py` and all six **marked** nodes
  (`test_adapter_cannot_bulk_enrich_or_consult_preflight_state`,
  `test_null_required_data_and_wrong_data_shape_are_operation_errors`,
  `test_invalid_state_value_and_missing_identity_are_operation_errors`,
  `test_failed_operation_fields_are_none_never_zero`,
  `test_state_excluded_and_unknown_assets_remain_recorded`,
  `test_request_metadata_json_carries_required_fields_without_secrets`).
  `tests/test_contracts.py::test_repository_protocol_and_schema_specification`
  **passes** — Chunk 5's plan already corrected that claim (its item 7(d), line 2116).
  This is reported, not fixed; **Chunk 5's implementer** owns the six.

## 5. Interface contract this chunk produces

There is no runtime interface. The observable public surface of the change is the
tool's **status vocabulary**, its **message text**, and its **exit code**. That is
what this section freezes; it is what a later gate or a downstream chunk may rely on.

### 5.1 LREQ status vocabulary

Every LREQ ID returned by `defined_ids` is placed in exactly one of these statuses.
The statuses are disjoint and total over `defined_ids`.

| Status | Meaning | Defect? |
|---|---|---|
| `marked` | At least one collected test node carries this ID in its marker set. | No |
| `owned_not_yet_implemented` | No marker, and the ID's primary-owner chunk is not complete. Derived live, never from a listing (§5.2). | No |
| `plan_owned_disclosed` | No marker, and its primary owner **is** complete. Covers exactly the two IDs enumerated in §5.3 item 1. | No |
| `tooling` | `LREQ-NFR-060` — delivered by this validator's own existence and the workflow rules, not by a test node. Enumerated in §5.3 item 2. | No |
| `delivered_elsewhere` | `LREQ-SEC-010` and `LREQ-NFR-050` — SRS Appendix B assigns them a non-`tests/` primary owner / required test. Enumerated in §5.3 item 3. | No |
| `pending_setup_phase` | No marker, primary owner complete, not enumerated above. **Requires a marker, a matrix entry, or one more §5.3 entry — all three are cheap.** | **Yes → exit 1** |

Invariants:

- **[INV-1] The defect set is derived from two repo artifacts and no plan file.**
  Input `req` is a defect iff, and only iff, all three hold:
  (a) `req in defined_ids(srs_text)`;
  (b) `req not in actual_marked`;
  (c) the dependency map's ownership matrix names at least one chunk that is complete,
  obtained by calling `chunk_requirements(dep_map_text, chunk)` for every `chunk` whose
  `"## Chunk {chunk} "` section exists, catching the `ValueError` a missing or
  differently-worded section raises, and testing the intersection with
  `{req}`.

  The **complete-chunk set** is an explicit literal in the module —
  `COMPLETE_CHUNKS: tuple[str, ...] = ("0",)` today — every entry a chunk whose plan's
  `Status:` line reads `IMPLEMENTED` or `VERIFIED`. It is **not** inferred from plan
  prose and **not** parsed from a traceability table, so no table-shape problem can
  reach the check. Chunk 0 is the only entry today: its plan's line 3 reads
  `Status: VERIFIED`; Chunk 1's line 3 reads `Status: FROZEN`; Chunk 3's line 3 reads
  `Status: VERIFIED` (see [INV-3]). **[INV-1] is the deliverable that makes the check
  real, not the enumeration in §5.3** — a listing of IDs would itself be a new hole
  the moment a future chunk finishes.
- **[INV-2] `COMPLETE_CHUNKS` is a maintenance obligation with a stated failure mode.**
  Adding an entry whose chunk is not actually complete turns the check into a
  false-positive generator for that chunk's whole requirement set. Every entry SHALL be
  accompanied by the plan file and the `Status:` line it was read from, in the same
  commit. It is deliberately **not** auto-derived: doing so would mean parsing plan
  files, which this design forbids.
- **[INV-3] Applying `("0",)` today does not put Chunk 3's IDs into the defect set.**
  Chunk 3 is `Status: VERIFIED`, so its IDs belong there if it were listed — but
  Chunk 3's IDs are protected by a second independent mechanism: all ten of its
  primary-owner IDs are in `actual_marked` today, so clause (b) already excludes them.
  Adding `"3"` to `COMPLETE_CHUNKS` is therefore expected to be a no-op **and is the
  plan's own first verification step** (§7 step 6) precisely because that expectation
  is a claim about artifacts, not a proof.
- **[INV-4] No reinterpretation.** The check does not redefine, widen, narrow, or
  replace the meaning of `missing_required` (Chunk 0's seven requirements) or of
  `marker_mismatch`, `orphan_nodes`, or `missing_nodes`. Those four comparisons keep
  their current definitions and their current exit contribution.
- **[INV-5] Every exclusion is enumerated, not computed.** Each ID in
  `plan_owned_disclosed`, `tooling`, and `delivered_elsewhere` has its own literal
  entry with an SRS anchor (§5.3). Without that entry its owner's completion would
  escalate it to `pending_setup_phase` automatically — the failure mode is safe
  (over-reporting a real gap), never silent.

### 5.2 Source-of-truth boundaries

Read API, replacing the current private helpers' role in the new check:

```python
COMPLETE_CHUNKS: tuple[str, ...] = ("0",)

LREQ_STATUS_MARKED = "marked"
LREQ_STATUS_OWNED_NOT_YET_IMPLEMENTED = "owned_not_yet_implemented"
LREQ_STATUS_PLAN_OWNED_DISCLOSED = "plan_owned_disclosed"
LREQ_STATUS_TOOLING = "tooling"
LREQ_STATUS_DELIVERED_ELSEWHERE = "delivered_elsewhere"
LREQ_STATUS_PENDING_SETUP_PHASE = "pending_setup_phase"

STATUS_EXCLUSIONS: Mapping[str, Mapping[str, str]]   # status -> {LREQ ID: anchor}

def marked_requirement_ids(tests: Mapping[str, set[str]]) -> set[str]
def mapped_chunk_requirements(dep_map_text: str) -> dict[str, set[str]]
def complete_chunk_requirements(dep_map_text: str) -> set[str]
def classify_requirements(
    defined: set[str],
    actual_marked: set[str],
    complete_owned: set[str],
) -> dict[str, str]
def pending_setup_phase_requirements(statuses: Mapping[str, str]) -> list[str]
def declared_plan_node_names(plans_dir: Path) -> set[str]
def advisory_name_mismatches(declared: set[str], tests: Mapping[str, set[str]]) -> list[str]
```

`classify_requirements` is the only place a status is assigned. It is used by `main`
and by the test module, so the test module tests the real classification rather than a
re-implementation. `marked_requirement_ids` is shared with `main`'s existing
`referenced` computation for `unknown`; it returns `set()`, never `None`, for an empty
or all-unmarked suite.

### 5.3 The enumerated exclusions

Each item states the ID, the repository artifact that discharges it, and the
requirement text that makes the discharge the *right* discharge. These are the plan's
scripture; "discharged by prose" is not accepted for any other ID.

1. **`plan_owned_disclosed` — `LREQ-NFR-040` and `LREQ-NFR-050`.** Both are defined
   (SRS lines 1171–1172 and 1174–1175), both have no marker anywhere in `tests/`
   (**counted**, §11 query Q-B: 42 of 89 defined IDs are unmarked, and these two are
   in that set), and both have a complete primary owner (**Chunk 0**, dependency map
   lines 124 and 125). Their required tests are `LREQ-TST-010` and `LREQ-NFR-060`,
   not nodes of their own. The `missing_required` message that names that direction is
   computed as `sorted(required - referenced)` over the matrix's own value arrays
   (`validate_traceability.py` lines 140–143), so it is not produced by their marker
   absence, and whether it lists either ID today is **unverified** (that run was not
   repeated for this plan). Discharging them as `plan_owned_disclosed` is nevertheless
   the *honest* status: `marked_requirement_ids` over the current suite returns 47
   distinct IDs and neither ID is among them (Q-B), so both are marker-less by the new
   check's own input; the gap is disclosed, owned by a complete chunk, and not this
   plan's to close.
2. **`tooling` — `LREQ-NFR-060`.** Dependency map line 289 gives its `Module` as
   `Project-wide`, its `Pure/I/O` as `Tooling/process I/O`, and its `Required tests`
   as `LREQ-NFR-060` (itself). Its normative text (SRS lines 1177–1180) is satisfied
   by "analytical tests SHALL be part of the normal workflow" — i.e. by this tool, the
   `lreq` marker registration in `pyproject.toml` (its lines 20–22), and the workflow
   rules — not by a test node.
3. **`delivered_elsewhere` — `LREQ-SEC-010` and `LREQ-NFR-050`.** SRS-lean's Appendix
   B assigns `LREQ-SEC-*` the primary modules `config.py`, `collector.py`,
   `database.py` with required tests `test_collector.py`, `test_end_to_end.py`
   (its line 1454), and assigns `LREQ-NFR-*` the primary owner `cross-cutting` with
   "project checks and end-to-end tests" (its line 1455). `LREQ-SEC-010`'s own
   dependency-map row (line 68) names Chunk 3 / Chunk 5 / Chunk 12 as completion
   chunks with required test `LREQ-TST-080` — a full end-to-end fixture — not a
   marked unit node. **`LREQ-NFR-050` is deliberately listed in both items 1 and 3:**
   it has a complete primary owner (item 1's test) *and* an Appendix B owner outside
   `tests/` (item 3's test). Exactly one status must be chosen; **this plan chooses
   item 1** and records item 3's anchor as corroboration. §12.5 flags the choice.
4. **Everything else that is unmarked and has no complete owner is
   `owned_not_yet_implemented` and is not a defect.** This covers the bulk of the 42
   (**counted**, query Q-B): `LREQ-EVD-*`, `LREQ-MET-03x`–`LREQ-MET-100`,
   `LREQ-NRM-*`, `LREQ-RPT-*`, `LREQ-SCR-*`, `LREQ-SEN-*`, `LREQ-SMP-020/050/070/090`,
   `LREQ-CLI-010/020/040`, and `LREQ-TST-020`–`LREQ-TST-090`, whose primary owners
   (Chunks 4A, 4B, 7A, 7B, 8, 9A, 9B, 11, 12, 13) are all `FROZEN` or unplanned, not
   complete.

### 5.4 Message format, units, and exit codes

`main`'s output contract. Every count names its unit.

```text
Traceability valid: {n_required} Chunk 0 requirements mapped, {n_marked_nodes} marked
test nodes, {n_lreq_marked} of {n_defined} LREQ IDs carry a marker
(marked units: distinct IDs), {n_matrix_rows} matrix rows
({n_matrix_node_rows} node rows, {n_matrix_alias_rows} plan-declared node IDs not present in tests/)
```

- `{n_required}` replaces the current `len(required)` and is the same number (7).
- `{n_marked_nodes}` is a count of **distinct pytest node IDs with at least one
  marker** (143 today), replacing the ambiguous `{len(matrix)}`.
- `{n_lreq_marked} of {n_defined}` is a count of **distinct LREQ IDs** (47 of 89
  today). This is the number that makes the blind spot visible in the *green* output.
- `{n_matrix_rows}` distinguishes **matrix rows** from node IDs. `{n_matrix_alias_rows}`
  is the subset of `tests/traceability.json` keys that are not pytest node IDs
  (0 today, 1 while Chunk 5's plan alias stands — §12.3).
- Defect output, in the existing `print`-then-`return 1` shape:

```text
LREQ IDs required by a complete chunk with no test marker, no matrix only-entry, and
no enumeration in STATUS_EXCLUSIONS: {ids}
```

`main` returns 1 when the `pending_setup_phase` list is non-empty, in addition to the
four existing conditions. It continues to print the `unmarked_tests` note before the
summary line, and continues to return 0 with a green summary when no defect is found.

Number-unit rule for this line: `{n_marked_nodes}` and `{n_matrix_rows}` are counts of
the **same 143 distinct identifiers** under two different queries (marked pytest node
IDs; `tests/traceability.json` top-level keys), not occurrence counts of the marker text
(152 today). The message SHALL NOT print `n_marked_nodes + n_matrix_rows`, a sum, a
difference, or a "total markers" figure of any kind, because every way of combining the
two 143s invites reading them as 286 objects; each count is printed once, adjacent to its
own unit. The marker-occurrence count (152) and the per-module occurrence-versus-node
skew (§5.7) SHALL NOT appear in this message and SHALL NOT be computed by `main`; they
are inputs to the §9 regression test, which passes its own literals.

### 5.5 Advisory name-equality check

`declared_plan_node_names` extracts from each `Documents/plans/*.md` file every
backtick-quoted or `::`-qualified token of the form `test_<identifier>`, cheaply and
without table parsing. `advisory_name_mismatches` returns the declared names that do
not occur as a node name in the collected suite; they are printed as one
`Note: ...` line, in the same shape as the existing `unmarked_tests` note.

Hard constraints:

- Its return value **must not** be reachable from any `return 1` path. The
  `problems` boolean is computed before it is called, or the note is printed after
  the early `return 0`/`return 1` decision, so no code path can promote it.
  A test asserts this by construction: `main` is exercised with a tree containing an
  alias-only name and the exit code is still 0 (§9).
- It is advisory because the rejected defect is that **name equality is not a
  contract**: `test_parent_path_does_not_match_child_path` is a real marked node in
  `tests/test_validation.py` and is named in Chunk 1's plan **and** Chunk 3's plan
  (**counted**, §11 query Q-D: 7 of the 143 marker-carrying node IDs are cited by two
  plan files; **not** "7 of 143 marked nodes", because Chunk 1's and Chunk 5's §9 tables
  declare the node name `test_parent_path_does_not_match_child_path` under
  `tests/test_collector.py` as well, which is a `def`-less alias). Any `chunk` claim
  inferred from plan prose would be wrong for both readings.
- Today the check yields a **non-empty** advisory list, and that is correct behaviour,
  not a defect: the set includes the three Chunk 5 node names plus at least one
  retained-but-deleted node name (§12.3). It exits 0 regardless.

### 5.6 Non-recursive test collection

Replace `collect_tests`'s `TESTS_DIR.glob("test_*.py")` with collection that resolves
to `tests/<module>.py` module paths without recursing: a non-recursive
`Iterable` over the `tests/` directory's own entries, filtered to `*.py` files whose
name starts with `test_` (and `test_*.py` under `tests/` only), mirrored in the `pytest`
configuration in the same way the current walk is mirrored.

**Verified current behaviour:** `collect_tests` uses `Path.glob("test_*.py")`, which
is **non-recursive already** (`**/` is what recurses). **Quoted** (line 104) and
**counted**: the five modules it finds are `test_collector.py`, `test_contracts.py`,
`test_database.py`, `test_identity.py`, `test_validation.py` (§11 query Q-G′). So this
item changes the *mechanism* (defensive) and must change **no** collected node. A test
asserts the collected count is unchanged across the two mechanisms (§9).

### 5.7 Marker-count units: a node may carry several markers

This section is normative for every count the new check performs, and it exists because
the check's own correctness depends on which unit it counts. It is stated as its own
subsection so a reviewer can reject it independently of §5.1's status vocabulary.

**Normative statements.**

- The new check **SHALL** compare a count of **distinct marked pytest node IDs** to a
  count of `tests/traceability.json` **keys**, and SHALL treat a mismatch between those
  two distinct-identifier counts as the violation. (Unit: distinct identifiers on both
  sides, not occurrences.)
- The new check **SHALL NOT** treat a count of `@pytest.mark.lreq` **occurrences** as an
  error signal, and `main` SHALL NOT compute one. An occurrence count is a property of
  the *source text*; the contract is a property of the *node*.
- A node carrying **multiple** `@pytest.mark.lreq` decorators is **valid** and is the
  expected shape when one test node is the required test for several LREQ IDs. Its
  `tests/traceability.json` value is a **multi-element JSON array**, one element per
  distinct marked ID, in the marker's own order, per the existing `marker_mismatch`
  comparison (`validate_traceability.py` lines 147–151, which compares
  `set(matrix.get(node, ()))` to the node's full marker set — set equality, so it is
  already multi-marker correct and is unchanged by this plan).
- Consequence for the alias-row and `missing_nodes` classes: both are keyed by node ID,
  so both are already counted in the distinct-identifier unit and neither may be
  re-derived from an occurrence count.

**Worked examples — the two modules where occurrence count and distinct-node count
legitimately differ.** Each number's unit is named; the three columns are three
different units and are not interchangeable. Query Q-U in §11 is the exact query; it was
re-run for this correction pass and reproduced all three columns. **(Re-run 2026-09-18;
the failure of that claim is recorded in §11 Q-M″ and is the same defect class §8.6
names: the earlier pass asserted a re-run it had not performed, and the two figures it
gave were wrong. The Q-U entry in §11 below was written by this correction pass, which
is the first pass that actually ran it.)**

| Module | `@pytest.mark.lreq(` **occurrences** (decorator lines) | **distinct marked node IDs** | `tests/traceability.json` **keys** for the module |
|---|---|---|---|
| `tests/test_database.py` | 31 | 23 | 23 |
| `tests/test_validation.py` | 23 | 22 | 22 |

The gap is **stacked distinct decorators on one node**, not a defect. Quoted from
`tests/test_database.py` lines 595–600 (one node, three markers):

```python
@pytest.mark.lreq("LREQ-SMP-080")
@pytest.mark.lreq("LREQ-GQL-080")
@pytest.mark.lreq("LREQ-SEC-020")
def test_insert_versus_upsert_semantics_per_table(
```

and its matching row `"tests/test_database.py::test_insert_versus_upsert_semantics_per_table":
["LREQ-SMP-080", "LREQ-GQL-080", "LREQ-SEC-020"]` — one key, three IDs. Same shape once
in `tests/test_validation.py` lines 1187–1189 (`LREQ-EXT-050` + `LREQ-EXT-090`,
`test_category_mismatch_and_unverified_map_to_discovery_status_vocabulary`).
`tests/test_database.py` holds **seven** such nodes and `tests/test_validation.py`
**one**, which is the whole 9-occurrence gap in the table: 23 + 7 = 31 and 22 + 1 = 23.

**The repository-wide reconciliation** (query Q-U, all five modules, decorator-occurrence
unit, distinct-node-ID unit, matrix-row unit, and collected-node-ID unit):

| Module | occurrences | distinct marked node IDs | matrix keys | collected nodes |
|---|---|---|---|---|
| `tests/test_collector.py` | 51 | 51 | 51 | 53 |
| `tests/test_contracts.py` | 22 | 22 | 22 | 22 |
| `tests/test_database.py` | 31 | 23 | 23 | 23 |
| `tests/test_identity.py` | 25 | 25 | 25 | 25 |
| `tests/test_validation.py` | 23 | 22 | 22 | 22 |
| **TOTAL** | **152** | **143** | **143** | **145** |

Arithmetic reconciliation, addition shown: `145` collected node IDs − `2` unmarked nodes
= `143` marked distinct node IDs = `143` matrix keys; `152` occurrence-count matches −
`143` distinct node IDs = `9` additional decorator occurrences (7 + 1 = 8 stacked *extra*
decorators on 7 + 1 nodes, plus **1** occurrence of the marker text inside
`tests/test_identity.py`'s own module docstring — Q-U's pattern `@pytest\.mark\.lreq\(`
counts **decorator occurrences** and excludes docstring prose only for the escaped form,
so any count derived by raw substring search over file text is a **different unit again**.
**Measured for this correction (query Q-U, paren-anchored and no-paren variants):** the
paren-anchored pattern `@pytest\.mark\.lreq\(` returns **152** matches, exactly equal to
the AST decorator-child *occurrence* count in the table above; the no-paren pattern
`@pytest\.mark\.lreq` returns **158**, i.e. **152 + 6**. The distinguishing lines are the
**six module docstrings** that name the marker in prose without a trailing `(` — one per
module: `tests/test_collector.py` line 3 and line **1417** (an interior comment block, so
this module contributes **2**), `tests/test_contracts.py` line 3, `tests/test_database.py`
line 3, `tests/test_identity.py` line 3, `tests/test_validation.py` line 3. **All six are
prose lines** (a module docstring or a comment), not decorator lines, which is the whole
of the 6-match gap. **Raw-substring counts SHALL NOT be used anywhere in this change**;
note that the 158 figure is itself a raw-substring count of the *no-paren* pattern and is
quoted only to name the gap, never as a count of the property under assertion.) The pattern of the relation matters more than any total:
**`occurrences ≥ distinct node IDs` is expected here; `matrix keys == distinct marked
node IDs` holds exactly.** This plan's check counts the right-hand pair.

**What this forbids, concretely.** A check that reported the difference between the
occurrence column and the node column as a violation would fail `tests/test_database.py`
and `tests/test_validation.py`, **both of which are correct** — the two modules whose
occurrence count exceeds their distinct-node count. It would also report `→ 9` on a green
tree and would push the suite's own multi-marker nodes into a defect list, which is the
`119 passed` presentation failure (§8.6) in a new costume: a real, defensible-looking
number that means something other than what the reader takes it to mean. The rule is
therefore a **SHALL NOT on the occurrence unit**, not a footnote.

**Where the unit already matters elsewhere, quoted so this plan is not read as claiming
it is first.** Chunk 5's plan records the identical class of error twice: its §12 item 7
(the `tests/test_collector.py` "25 markers over 13 nodes") and its item 8, whose own
lesson is that a substring count of the marker text "is not a count of the property being
asserted" — the shape it cites is a **one-to-one** multi-node case (25 occurrences over
25 nodes), which is the *other* shape from this section's (31 occurrences over 23 nodes).
Both shapes are legal here; only the unit differs. Neither the one-to-one 25/25 case nor
the stacked 31/23 case may be compressed into a single number by the new check.

## 6. Files touched

| File | New/modified | Purpose |
|---|---|---|
| `src/niche_scout/tools/validate_traceability.py` | modified | Add the requirement-axis classification, `COMPLETE_CHUNKS`, `STATUS_EXCLUSIONS`, the named-unit summary, the advisory name-applicability note, and non-recursive collection. |
| `tests/test_validate_traceability.py` | new | Analytical tests for the tool's classification, sensitivity, exit code, message units, the marker-count-unit constraint (§5.7), and advisory boundary (§9). Carries `@pytest.mark.lreq("LREQ-NFR-060")` on each analytical node. |
| `tests/traceability.json` | modified | Add one entry per new base node ID; no existing entry edited, removed, or reordered. |

Supporting evidence only, not code: `.scratch/p0-2-*.py` scratch files are already used
and deleted inside this planning task (§11 cleanup); nothing from them is referenced by
`src/` or `tests/`.

## 7. Task breakdown

- [ ] [INV-1] Introduce `COMPLETE_CHUNKS = ("0",)` with a module comment naming the plan
      file and `Status:` line each entry was read from. (LREQ-NFR-060 mechanism)
- [ ] Add `marked_requirement_ids`, `mapped_chunk_requirements`, and
      `complete_chunk_requirements`; confirm `chunk_requirements(text, chunk)` raises
      `ValueError` rather than returning an empty set for a section that exists but uses
      a different requirements heading. (LREQ-NFR-060 mechanism)
- [ ] Add the status constants, `STATUS_EXCLUSIONS` with the §5.3 entries and their SRS
      anchors, `classify_requirements`, and `pending_setup_phase_requirements`.
      (LREQ-NFR-060 mechanism)
- [ ] Add the defect message and make `main` return 1 on a non-empty
      `pending_setup_phase` list; leave the four existing conditions untouched. (LREQ-NFR-060)
- [ ] Replace the `{len(matrix)} matrix nodes` figure with the §5.4 summary line, every
      count carrying its unit; keep the `unmarked_tests` note. (LREQ-NFR-060)
- [ ] **Verify [INV-3] before trusting it:** add each exit-status-plausible chunk ID to
      `COMPLETE_CHUNKS` **one at a time** — **`"3"` first** — removing it again before the
      next is tried, and record the resulting defect set for each. If any attempt yields a
      non-empty defect set, **stop and report** rather than adding that chunk's IDs to
      `STATUS_EXCLUSIONS`. Do **not** add Chunk 2, Chunk 12, or Chunk 13 to the literal as
      a batch: §11's own prohibition forbids deriving `COMPLETE_CHUNKS` from plan prose or
      from any status guess. **Note the citation that was wrong here (corrected
      2026-09-18):** this box previously justified that prohibition with a **counted**
      claim about the `Status:` line of
      `chunk-13-coveo-graphql-endpoint-verification-and-cross-cutting-validation.md`. That
      file **does not exist on this tree** — `Glob` for `Documents/plans/*.md` returns
      **7** paths, and the only numbered plans present are `chunk-00`, `chunk-01`,
      `chunk-02`, `chunk-03`, `chunk-05`, plus `_TEMPLATE.md` and this file (unit: distinct
      files) — so that read could not have been performed and the `DRAFT` value is
      **withdrawn as unverified** (§11 Q-M″(c)). The prohibition itself stands on §11's
      rule, not on the withdrawn value: `<Status:>` values that are cited as fact SHALL be
      read, and a value that cannot be read SHALL NOT be asserted. A
      partial-over-approximation instrument changes what
      the check tests, so §5.1's `owned_not_yet_implemented` claim must be re-measured
      rather than assumed. (LREQ-NFR-060)
- [ ] Add `declared_plan_node_names` and `advisory_name_mismatches`; print the note;
      assert by construction that no `return 1` path can reach them. (LREQ-NFR-060)
- [ ] Replace the collection glob with non-recursive module-path collection; assert the
      collected count is unchanged. (LREQ-NFR-060)
- [ ] Write `tests/test_validate_traceability.py` with the §9 nodes, each carrying
      `@pytest.mark.lreq("LREQ-NFR-060")`. (LREQ-TST-010 convention, LREQ-NFR-060)
- [ ] Add the matching `tests/traceability.json` entries, one per base node ID, arrays
      equal to the marker sets. (LREQ-NFR-060)
- [ ] Run `python -m pytest tests -q`, `python -m niche_scout.tools.validate_traceability`,
      and `python -m niche_scout.tools.check_import_boundaries`; record the **real**
      pass/fail figures and the pre-existing `tests/test_collector.py` failures
      verbatim. (LREQ-NFR-060)
- [ ] Run the §11 anchored queries against the new tool and record every count with its
      unit in the chunk report. (LREQ-NFR-060)

## 8. Edge cases and invariants

- **8.1 Empty or unmarked suite.** `marked_requirement_ids` returns `set()` for an
  empty suite. The defect set must then be *all* non-excluded defined IDs, not an
  exception and not `None`. Assert it directly.
- **8.2 `traceability.json` missing, unreadable, or not an object.** Unchanged: the
  existing `except (OSError, ValueError, json.JSONDecodeError)` path prints
  `Unable to read traceability matrix: {exc}` and returns 1 (lines 135–137). The new
  check runs after that guard, so it never sees a malformed matrix.
- **8.3 Section exists, heading differs.** `chunk_requirements` raises `ValueError`
  when the section lacks `Requirements primarily covered:`. `complete_chunk_requirements`
  catches it and skips the chunk. Assert that a chunk with `Requirements:` (Chunk 13's
  wording) is skipped, not silently treated as having no requirements *and* not raising
  out of `main`.
- **8.4 Backwards compatibility of existing exit codes.** A tree in which only an
  existing condition holds (unknown ID, missing Chunk 0 requirement, marker without
  entry, mismatch, orphan) must still exit 1 with the same message; a tree in which
  only the new condition holds must exit 1 with the new message. Assert both.
- **8.5 `LREQ-TST-090` carries no marker anywhere** (**counted**, query Q-B) while its
  primary owner is Chunk 13 (`Status:` unplanned) — so it must be
  `owned_not_yet_implemented`, not a defect. Assert its specific status, because it is
  the ID a reader is most likely to expect at the top of a defect list.
- **8.6 The reported baseline disclosure is part of the invariant set.** The
  validator's exit code is **not** a statement that the suite passes, and today's
  suite does not (`6 failed, 139 passed`, all six in `tests/test_collector.py`, all
  six marked). Every report of a validator run written under this plan SHALL state the
  pytest figure alongside it. A green validator over a red suite is exactly the
  `119 passed` class of presentation the user has already ruled against; the tool
  cannot detect it (`t = set(matrix) == A` is satisfied for failing nodes, because
  those nodes exist and are marked) and this plan does not claim to close it
  (§12.1).
- **8.7 Total and disjoint statuses.** `classify_requirements(defined, marked, owned)`
  shall return exactly one key per element of `defined` — no missing key, no extra
  key. Assert `set(statuses) == defined` and that no ID matches two predicate sets.
- **8.8 Alias-only matrix row.** A `tests/traceability.json` row whose node ID has no
  `def` (Chunk 5's §9 alias row, or `chunk-05-...md`'s line 1495 node) is currently an
  `orphan_nodes` exit-1 failure. This plan does **not** classify it as a distinct
  status and does **not** exempt it, because exempting rows that no `def` backs would
  be a new exit-code weakening. It is counted into `{n_matrix_alias_rows}` for
  visibility and otherwise behaves exactly as today (§12.3).
- **8.9 Naming and documentation.** `classify_requirements`' docstring states the
  `MUST NOT` that makes the check safe.

## 9. Test plan

- **Test file:** `tests/test_validate_traceability.py` (new).
- **Fixture source:** repository fixtures only — no new fixture module. Inputs are
  built from small in-memory literals (a mini SRS text, a mini dependency-map text, a
  mini matrix dict, a mini node map), never from the repository's real paths, except
  for tests whose subject *is* the real repository (marked below). No clock, no
  network, no filesystem writes outside pytest's `tmp_path`.
- **Mechanism:** every analytical node calls the real public functions introduced in
  §5.2 — selection tests call `classify_requirements` and `main` with repository
  paths. Tests of `main`'s exit code invoke `main([])` and assert its return value
  (never `sys.exit`), which keeps the test deterministic and lets the four existing
  branches be exercised without monkeypatching.
- **Exact pytest lreq markers required.** All ten nodes carry
  `@pytest.mark.lreq("LREQ-NFR-060")` — the tooling requirement. `LREQ-NFR-060` is a
  **defined** SRS ID (SRS line 1177), so the marker both satisfies `unknown` and clears
  the new `pending_setup_phase` clause for the ID **while the new check is red**; the
  order of work is therefore: write the tool, then the tests, then re-run, and the
  defect the tests describe is one the tool must report and the test set must not hide
  (§8.6). §12.6 flags the sequencing consequence.

| Base pytest node ID | Subject | Marker |
|---|---|---|
| `test_unmarked_defined_id_with_complete_owner_is_a_defect` | Selection: an unmarked ID with a complete owner is `pending_setup_phase`. | LREQ-NFR-060 |
| `test_unmarked_defined_id_with_incomplete_owner_is_not_a_defect` | Sensitivity: the same input with an incomplete owner is `owned_not_yet_implemented`. | LREQ-NFR-060 |
| `test_enumerated_exclusions_are_not_defects` | All six IDs enumerated in §5.3 keep their stated status under a complete owner. | LREQ-NFR-060 |
| `test_statuses_are_total_and_disjoint_over_defined_ids` | [INV-5] / §8.7. | LREQ-NFR-060 |
| `test_empty_suite_makes_every_unexcluded_id_a_defect` | §8.1. | LREQ-NFR-060 |
| `test_chunk_section_with_different_requirements_heading_is_skipped` | §8.3. | LREQ-NFR-060 |
| `test_advisory_name_mismatch_cannot_change_the_exit_code` | §5.5 / §8.4: an alias-only declared name is reported and the exit code stays 0. | LREQ-NFR-060 |
| `test_existing_defect_classes_still_exit_nonzero` | §8.4 backwards compatibility, one parametrized node over the four existing conditions (base node ID only). | LREQ-NFR-060 |
| `test_repository_state_is_reported_with_named_units` | Runs the tool once against the repository and asserts the summary line names both units, without asserting the defect list is empty. | LREQ-NFR-060 |
| `test_marker_occurrence_count_exceeding_distinct_node_count_is_not_a_violation` | §5.7: a node carrying stacked distinct `lreq` markers is accepted, its multi-element matrix array is valid, and an occurrence count above the distinct-node count raises no violation and cannot reach any `return 1` path. Brings §9 to ten nodes; see §5.7 for the literals and the unit of each. | LREQ-NFR-060 |

- **`tests/traceability.json` entries to add:** one entry per base node ID above,
  each array equal to that node's marker set (ten entries, each `["LREQ-NFR-060"]`).
  No existing entry is edited.
- **Non-analytical tests:** none. This module has no helper-only tests; every
  `test_*` node is analytical and carries the marker. The module docstring SHALL NOT
  contain the literal marker text `@pytest.mark.lreq`, so a naive substring count of
  the file does not over-count (this is exactly the unit error recorded in Chunk 5's
  plan items 6–8). Because of that rule the literal here is written with an escaped dot
  (`@pytest\.mark\.lreq` in prose only, never as the unescaped decorator text), and the
  new node is the sharpest test of the rule: its own module SHALL NOT create the
  stacked-marker or occurrence-skew shape §5.7 describes (one decorator per node, no
  multi-ID matrix array in this file) **except** that the node's own marker is present
  exactly once. That assertion runs against **literals passed by the test**, never
  against this test file, because a test that read its own module would be asserting
  its own text rather than the artifact under test.

## 10. Definition of done (gate)

There is no dependency-map Gate section for this plan, because the dependency map has
no chunk for it; P0-2 was authorized by the user as its own plan. Each bullet below is
**derived from this plan's own §5 contract**, with the §12 open questions that can
block it named. A bullet is satisfied only by a test in §9 or by a command whose exit
code is recorded — never by reading the plan back.

- Every defined LREQ ID receives exactly one status from §5.1, and the statuses are
  total and disjoint over `defined_ids`. (§9, `test_statuses_are_total_and_disjoint_over_defined_ids`)
- The defect set contains the three node-less IDs of §5.5 and `LREQ-TST-090`, and
  contains **no** ID enumerated in §5.3. (§9,
  `test_unmarked_defined_id_with_complete_owner_is_a_defect`,
  `test_enumerated_exclusions_are_not_defects`)
- The defect set is derived from `SRS-lean.md`, `requirements-dependency-map.md`,
  `tests/traceability.json`, and `tests/` only, and no status depends on any table
  shape or heading wording inside a plan file. (§9,
  `test_chunk_section_with_different_requirements_heading_is_skipped`)
- The four existing failure classes still exit 1 with their existing messages, and the
  green path still exits 0. (§9, `test_existing_defect_classes_still_exit_nonzero`)
- The advisory name-applicability note cannot make `main` return non-zero. (§9,
  `test_advisory_name_mismatch_cannot_change_the_exit_code`)
- Collection over `tests/` is non-recursive and collects the same module set as the
  current `glob("test_*.py")`. (§9; §7's collection task)
- The summary line names each count's unit, and reports marked LREQ IDs separately
  from marked pytest node IDs and from matrix rows. (§9,
  `test_repository_state_is_reported_with_named_units`)
- **The existing green run stays green.** `python -m niche_scout.tools.validate_traceability`
  exits **0** and its summary line still contains `7 Chunk 0 requirements mapped`, on
  the tree as it exists at implementation time. (§11 Q-M′ is the recorded
  pre-implementation baseline: exit 0, `7 Chunk 0 requirements mapped, 143 matrix nodes,
  89 defined LREQ IDs`.) If the implementing agent's run exits 1, the correct action is
  to **stop and report the defect set** (§12.6), never to widen `STATUS_EXCLUSIONS`.
- No file outside §6 is modified, verified by `git status`.
- `python -m niche_scout.tools.validate_traceability` and
  `python -m niche_scout.tools.check_import_boundaries` are run and their exit codes
  recorded, **together with** `python -m pytest tests -q`'s pass/fail figures, so no
  green validator run is presented as a green suite (§8.6).
- Every count written into the implementing agent's report carries its anchored
  enumeration (query, count, matched lines), per the project rule.

## 11. Explicit prohibitions

- `validate_traceability.py` SHALL NOT read, parse, split, or pattern-match any file
  under `Documents/plans/` for violation purposes. The only permitted plan-file access
  is the advisory node-name scan of §5.5, whose result SHALL NOT be reachable from any
  `return 1` path.
- `validate_traceability.py` SHALL NOT derive chunk completeness, ownership, gates, or
  the complete-chunk set from plan prose. `COMPLETE_CHUNKS` is a literal with a
  documented `Status:`-line provenance per entry.
- `validate_traceability.py` SHALL NOT invent a requirement ID, a test node, or a
  matrix entry, and SHALL NOT write, create, or mutate any file. It is a read-only
  reporting tool.
- `validate_traceability.py` SHALL NOT change the exit code of any condition it
  already detects, SHALL NOT remove or rename an existing message, and SHALL NOT widen
  Chunk 0's required set.
- `validate_traceability.py` SHALL NOT import a new third-party dependency, and SHALL
  NOT read the system clock; it stays standard-library-only (`ast`, `json`, `re`,
  `sys`, `pathlib`).
- This plan SHALL NOT implement, stub, xfail, or skip any node of
  `tests/test_identity.py`. The three missing nodes are Chunk 5's; their existence in
  a test file is what makes the validator's existing `missing_nodes` check fire.
- This plan SHALL NOT remove or edit any existing `tests/traceability.json` entry,
  including the alias-only row discussed in §8.8.
- This plan SHALL NOT touch `tests/test_collector.py`, and SHALL NOT repair, xfail, or
  skip its six failing nodes. They are Chunk 5's.
- This plan SHALL NOT edit `src/niche_scout/tools/check_import_boundaries.py`,
  `src/niche_scout/models.py`, any `src/niche_scout/*.py` outside the tools package,
  or any file under `Documents/` — including the figures that need correcting. Those
  are the P0-3 chore's. **Stated precisely, because two §5.2/§7 obligations reference
  `Documents/` without editing it:** the `COMPLETE_CHUNKS` provenance requirement
  ([INV-2] / §7's first box) is satisfied by *reading* `Documents/plans/chunk-00-...md`'s
  `Status:` line and copying it into a **source comment inside
  `validate_traceability.py`** — permitted and in scope — never by editing the plan
  file; and the tool is forbidden to read `Documents/plans/` at runtime (§11, first
  bullet) except for §5.5's advisory scan. §7's box should be read that way.
- This plan SHALL NOT mark a test `@pytest.mark.lreq` with an ID that is not defined
  in `SRS-lean.md`'s Appendix B ranges; an undefined ID would make the tool exit 1 on
  `unknown` and would be a fabricated requirement.

**Anchored enumerations for every count in this plan.** Every number above is
reproducible by running the query as written; the query text is the anchored
enumeration. Where the plan-writer's own run was not repeated for a figure, the query
is still stated so it can be re-run verbatim, and the figure is **not** thereby audited.

**Counts established by re-running the queries for this plan** (queries quoted, then the
number each returned, then the unit):

- `python -m pytest tests -q --collect-only` → `145 tests collected`. Unit: distinct
  collected pytest node IDs (one line per node ID; the summary line's "tests"). This is
  a count of *collected node IDs*, not of test functions in source.
- `python -m pytest tests -q` → `6 failed, 139 passed`. Unit: test outcomes
  (**occurrences**, 145 of them, not distinct identifiers). 6 + 139 = 145 reconciles with
  the collected count above; the six failing node IDs are listed in Q-N.
- `$env:PYTHONPATH="src"; python -m niche_scout.tools.validate_traceability` → exit **0**,
  `Traceability valid: 7 Chunk 0 requirements mapped, 143 matrix nodes, 89 defined LREQ IDs`,
  preceded by `Note: 2 test(s) carry no lreq marker: …`. Units: requirements (distinct
  IDs), **matrix rows** (JSON keys — see the reconciliation below), defined LREQ IDs
  (distinct IDs), unmarked tests (distinct node IDs).
- In-process query (Q-B′ form, extended):
  `python -c "import sys; sys.path.insert(0,'src'); from niche_scout.tools import validate_traceability as v; srs=v.SRS_PATH.read_text(encoding='utf-8'); d=v.defined_ids(srs); m=v.collect_tests(); a=set().union(*m.values()); print(len(d), len(a), len(d-a), len(m), len([n for n,s in m.items() if s]), len([n for n,s in m.items() if not s]), len(v.load_matrix()))"`
  → `89 47 42 145 143 2 143`. Units: **distinct LREQ IDs** (89 defined, 47 marked, 42
  unmarked), **distinct pytest node IDs** (145 collected, 143 marker-carrying, 2 unmarked),
  **JSON object keys** (143 matrix rows). Reconciliation: 145 = 143 + 2, and 143 matrix
  rows = 143 marker-carrying node IDs *today only because* `missing_nodes` and
  `orphan_nodes` both return 0; `missing_nodes` (marker without entry) = `[]` and
  `orphan_nodes` (entry without node) = `[]`, counted by the same query's remaining two
  terms. The validator's own `143 matrix nodes` figure is therefore a **row count that
  happens to equal** a node-ID count today — which is exactly the conflation §5.4 ends.
- Marker **occurrences** in decorator position, `ast` walk over
  `tests/test_*.py`, counting `ast.FunctionDef`/`AsyncFunctionDef` nodes named `test_*`
  with a `pytest.mark.lreq` decorator: 51 (`test_collector.py`) + 22
  (`test_contracts.py`) + 23 (`test_database.py`) + 25 (`test_identity.py`) + 22
  (`test_validation.py`) = **143**. Unit: **distinct marked node IDs** here, because each
  of the 143 carries exactly one marker; the same walk counting decorator occurrences
  rather than nodes returns 152 (per §5.7's per-module table), and the difference is the
  unit, not a discrepancy.
- `tests/test_identity.py` marker-carrying nodes: `python -m pytest
  tests/test_identity.py --collect-only -q -m lreq` → `25 tests collected`. Unit:
  distinct collected node IDs, none of which is among the three declared-but-unwritten
  Chunk 5 names (Q-A).
- Recursive test-file listing: `Get-ChildItem tests -Recurse -Filter "test_*.py"` → 5
  files, all direct children of `tests/`; `tests/fixtures/` and `tests/__pycache__/` are
  the only subdirectories, and `tests/fixtures/test_*.py` does not exist. Unit:
  distinct file paths. This is what makes a recursive glob and the current non-recursive
  glob return the same 5 **today**.
- Completion-chunk column of the ownership matrix (quoted table rows, lines 47–135):
  chunk `0` is the sole completion chunk for exactly **2** rows (`LREQ-ARCH-010`,
  `LREQ-ARCH-020`, lines 47–48); chunk `1` and chunk `2` appear in the completion column
  of **0** rows (they appear as supporting chunks). Unit: **table rows**. Consequence
  for §5.3: the plan's `COMPLETE_CHUNKS` clause (c) is a *refinement* of the dependency
  map's notion, not a transcription of the `Completion chunk(s)` column — "primary owner
  complete AND every completion chunk complete" — and it is a **refinement toward
  over-reporting**, never toward silence: the plan's own claimed defect set is therefore
  empty on the current tree, and today's live effect is the message change (§12.6).

- **Q-A — declared-but-never-written nodes.** `Grep` for
  `correlated_product_detail|missing_returned_identity|adapter_mismatch_is_a_flag`
  over `tests/` (**Python files**) → 0 rows; the same pattern over
  `Documents/plans/chunk-05-graphql-protocol-adapter-and-response-correlation.md` →
  3 rows, at its lines 1489, 1490, 1491 (node names only, in the §9 table). Reported
  as: 0 occurrences in `tests/`, 3 distinct node names declared, one declaration
  file. Units named: occurrences vs distinct node names.
- **Q-B — defined vs marked.** `[i for i in validate_traceability.defined_ids(SRS)
  if i not in actual_marked]` where `actual_marked = set().union(*marked_nodes
  .values())` → 42 rows, listed in full in the probe output; `len(defined) = 89` and
  `len(actual_marked) = 47`. Units named: distinct LREQ IDs. Re-verified for this plan
  by the same in-process query (§11, Q-B′), which returned the same 89 / 47 / 42.
  **Q-B′ — re-verification query, run for this plan** (read-only, no file written):
  `python -c "import pathlib,sys; sys.path.insert(0,'src'); from niche_scout.tools import
  validate_traceability as v; srs=v.SRS_PATH.read_text(encoding='utf-8');
  d=v.defined_ids(srs); m=v.collect_tests(); a=set().union(*m.values());
  print(len(d), len(a), len(d-a))"` → `89 47 42`. Units named: distinct LREQ IDs
  (`89` defined, `47` marked, `42` unmarked).
- **Q-D — nodes cited by more than one plan.** Query: for each of the 143 marker-carrying
  node IDs (`validate_traceability.collect_tests()`, markers non-empty), count the files
  `Documents/plans/*.md` whose text contains both the node name and at least one of that
  node's marker IDs. **Query re-run for this plan, with the file being written excluded**
  (`tooling-p0-2-…md`, whose own §9 and §11 cite the names it discusses; the first run
  counted it and returned 8) → **132** of 143 node IDs are cited by exactly one plan file
  and **7** by two: `test_parent_path_does_not_match_child_path` (two *files*:
  `tests/test_collector.py` and `tests/test_validation.py` — cited by the §9 marker tables
  at `chunk-01-...md` lines 714–735 and `chunk-03-...md` lines 602–622, and by Chunk 1's
  plan §3 at its lines 164–168),
  `test_repository_protocol_and_schema_specification`, `test_taxonomy_contract`,
  `test_type_hints_and_docstrings`,
  `test_identity_suite_covers_valid_malformed_unresolved_conflict_uri_and_mismatch`,
  `test_requested_identity_compatibility_comparison`. Units named: distinct node IDs vs
  plan files per node ID. Whole-directory variant, for reproducibility: 8 node IDs are
  cited by two or more plan files once this plan's own file is included, which is why the
  query states its exclusion.
- **Q-G — collection set.** `sorted((tests).glob("test_*.py"))` → 5 modules, named in
  §5.6. Units named: distinct module paths.
- **Q-M — suite state.** `python -m pytest tests -q` → `6 failed, 139 passed`;
  `python -m pytest tests -q --collect-only` → `145 tests collected`;
  `python -m pytest tests/test_identity.py --collect-only -q -m lreq` → `25 tests
  collected`. Units named: test outcomes (occurrences) vs collected node IDs.
  Re-run for this plan; the collected total moved from the earlier pass's `144/143` to
  `145` because Chunk 5's implementation has since added nodes, and the validator's
  `143 matrix nodes` figure (a **row count**, not a node count) did **not** move with
  it — which is itself a second, independent display of the same class of blindness.
  **Reconciliation:** `145` collected node IDs = `143` matrix rows + `2` unmarked nodes
  (`tests/test_collector.py::test_module_imports_without_side_effects`,
  `tests/test_collector.py::test_request_body_builder_signature_is_stable`, both named
  in the validator's own `Note:` line, §11 Q-M′). The two numbers agree only because
  every marked node has a matrix entry today; they are different units and the plan's
  §5.4 message stops conflating them.
- **Q-M′ — validator baseline output, re-run for this plan.**
  `$env:PYTHONPATH="src"; python -m niche_scout.tools.validate_traceability` → two
  lines, exit **0**:
  `Note: 2 test(s) carry no lreq marker: tests/test_collector.py::test_module_imports_without_side_effects, tests/test_collector.py::test_request_body_builder_signature_is_stable`
  `Traceability valid: 7 Chunk 0 requirements mapped, 143 matrix nodes, 89 defined LREQ IDs`
  Units named: requirements (distinct IDs), matrix nodes (**rows**), defined LREQ IDs
  (distinct IDs), unmarked tests (distinct node IDs).
- **Q-N — the six failing nodes.** `$env:PYTHONPATH="src"; python -m pytest tests -q
  --tb=no -rf` → `6 failed, 139 passed`, matching `6 FAILED` lines:
  `tests/test_collector.py::test_adapter_cannot_bulk_enrich_or_consult_preflight_state`,
  `tests/test_collector.py::test_null_required_data_and_wrong_data_shape_are_operation_errors`,
  `tests/test_collector.py::test_invalid_state_value_and_missing_identity_are_operation_errors`,
  `tests/test_collector.py::test_failed_operation_fields_are_none_never_zero`,
  `tests/test_collector.py::test_state_excluded_and_unknown_assets_remain_recorded`,
  `tests/test_collector.py::test_request_metadata_json_carries_required_fields_without_secrets`.
  All six are in `tests/test_collector.py`; `tests/test_contracts.py::test_repository_protocol_and_schema_specification`
  **passes**, contradicting Chunk 5's plan line 1264–1266 (its own item 7(d) at line
  2116 already corrected that claim). Units named: distinct pytest node IDs.
- **Q-G′ — non-recursion of the current glob, and the module set.**
  `sorted(p.name for p in pathlib.Path("tests").glob("test_*.py"))` → 5 names
  (`test_collector.py`, `test_contracts.py`, `test_database.py`, `test_identity.py`,
  `test_validation.py`). `glob("test_*.py")` does not recurse (`**/` is the recursive
  form), so the current collection is **already non-recursive** and the §5.6 change is
  defensive only. Units named: distinct module paths. No file exists under
  `tests/` in a subdirectory matching the pattern, so a recursive glob would return the
  same 5 today; the plan's §9 test asserts the equality rather than assuming it.
- **Existing validator messages.** `python -m niche_scout.tools.validate_traceability`
  → `Note: 2 test(s) carry no lreq marker: ...`, then `Traceability valid: 7 Chunk 0
  requirements mapped, 143 matrix nodes, 89 defined LREQ IDs`, exit 0. Units named:
  requirements (distinct IDs), matrix nodes (rows), defined IDs (distinct IDs).

**Q-U, Q-V, Q-W — the §5.7 marker-unit queries, written 2026-09-18.** §5.7's table cites
"Query Q-U" three times and header line 16 claimed §11 "gained Q-U, Q-V, Q-W", but no
such entry existed in this section: the identifier was a cross-reference with no
definition, so §5.7's 152 / 143 / 143 / 145 columns were **unaudited** under the project
counting rule ("a number that arrives without its enumeration has not been audited,
however it was labeled"). All three entries below were written by this correction pass,
and every number in them was produced by running the quoted query against the tree on
2026-09-18. Where a number differs from what §5.7 previously asserted, the difference is
named in the entry. One scratch file was used —
`.scratch/p0-2-defect12-recount.py`, deleted in the same pass (listed once here and not
re-declared below) — and it wrote nothing outside `.scratch/`.

- **Q-U — the marker-unit count, per module and repository-wide.** Anchored `Regex` over
  the five module file texts (`\A`-free, count of *matches*, no `ast` involvement) versus
  an `ast` walk:
  `python -c "import ast,json,pathlib,re; P=re.compile(r'@pytest\.mark\.lreq\('); N=re.compile(r'@pytest\.mark\.lreq'); K=json.loads(pathlib.Path('tests/traceability.json').read_text(encoding='utf-8')); [print(m.name, len(P.findall(t:=m.read_text(encoding='utf-8'))), len(N.findall(t)), len({n.name for n in ast.walk(ast.parse(t)) if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) and any(re.findall(r'lreq\(',ast.unparse(d)) for d in n.decorator_list)}), len([k for k in K if k.split('::')[0]=='tests/'+m.name])) for m in sorted(pathlib.Path('tests').glob('test_*.py'))]"`
  → per module, columns in the order `paren_matches`, `noparen_matches`,
  `distinct_marked_node_IDs`, `matrix_keys_for_module`:

  | Module | `@pytest\.mark\.lreq\(` matches | `@pytest\.mark\.lreq` matches | distinct marked node IDs | `traceability.json` keys |
  |---|---|---|---|---|
  | `tests/test_collector.py` | 51 | 53 | 51 | 51 |
  | `tests/test_contracts.py` | 22 | 23 | 22 | 22 |
  | `tests/test_database.py` | 31 | 32 | 23 | 23 |
  | `tests/test_identity.py` | 25 | 26 | 25 | 25 |
  | `tests/test_validation.py` | 23 | 24 | 22 | 22 |
  | **TOTAL** | **152** | **158** | **143** | **143** |

  **Unit named per column:** column 2 and column 3 are **occurrences** (matches in source
  text / decorator children of a `test_*` node); column 4 is **distinct marked node IDs**;
  column 5 is **JSON object keys** (matrix rows). Columns 2 and 3 are not interchangeable
  and neither is a node count. **Reproduction:** columns 2, 4, and 5 reproduce §5.7's
  table exactly (152 / 143 / 143 and every per-module 51 / 22 / 31 / 25 / 23 and 51 / 22 /
  23 / 25 / 22). **Column 3 did not reproduce** §5.7's asserted `154`: the measured
  no-paren total is **158**, not 154 (§5.7's separate `153` and `154` figures were both
  wrong; see Q-V). One scratch file was used for the regex-independent cross-check —
  `.scratch/p0-2-defect12-recount.py`, deleted in the same pass.
- **Q-V — the raw-substring reconciliation, and the exact lines that distinguish the two
  regexes.** The same run as Q-U, reporting only the lines that match the **no-paren**
  pattern and **not** the paren-anchored one — i.e. the difference between column 3 and
  column 2 above. Query: for each line of each of the five files,
  `N.search(line) and not P.search(line)`:

  | Module | line | what the line is | text (verbatim, truncated at the prose) |
  |---|---|---|---|
  | `tests/test_collector.py` | 3 | module docstring | ``Every test here carries exactly the ``@pytest.mark.lreq`` marker that`` |
  | `tests/test_collector.py` | 1417 | interior comment block | ``# section 9. Each node carries exactly the one ``@pytest.mark.lreq`` marker that`` |
  | `tests/test_contracts.py` | 3 | module docstring | ``Every test in this module carries an explicit ``@pytest.mark.lreq`` marker and a`` |
  | `tests/test_database.py` | 3 | module docstring | ``Every test here carries exactly the ``@pytest.mark.lreq`` marker set that`` |
  | `tests/test_identity.py` | 3 | module docstring | ``Every test here carries an explicit ``@pytest.mark.lreq`` marker and a matching`` |
  | `tests/test_validation.py` | 3 | module docstring | ``Every test here carries exactly one explicit ``@pytest.mark.lreq`` marker and a`` |

  **6 rows**, all **prose** (5 module docstrings + 1 comment), which is exactly
  `158 − 152 = 6`. **Unit:** matched lines (a line count, 1 per row) versus matches; each
  of these lines contains exactly one such match. **Reproduction of §5.7's claim, failed:**
  §5.7 asserted `153` decorator-shaped and `154` total, attributing the excess to a
  **single** line, `tests/test_identity.py` line 3. Measured, the paren-anchored count is
  **152** — identical to the AST decorator count, not 153 — the no-paren count is **158**,
  and the excess is **6** lines, not 1. The plan's `152 + 1` arithmetic therefore produced
  neither 153 nor 154, and its named cause accounted for one sixth of the real gap. The
  **whole tree** matches the paren-anchored pattern with **zero** prose hits: in all five
  files every `@pytest\.mark\.lreq\(` occurrence is a real decorator, and the two counts
  agree *because* that is true, not by coincidence.
- **Q-W — the stacked-decorator nodes, so the per-module gaps attribute to named nodes.**
  Query: for each of the five files, `ast`-walk `FunctionDef` / `AsyncFunctionDef` nodes,
  extract every `lreq(...)` first-argument literal from `decorator_list`, and keep the
  nodes whose list has more than one element:
  `python -c "import ast,pathlib,re; [print(m.name, n.name, re.findall(r'lreq\(\s*[\x27\"]([^\x27\"]+)', ' '.join(ast.unparse(d) for d in n.decorator_list))) for m in sorted(pathlib.Path('tests').glob('test_*.py')) for n in ast.walk(ast.parse(m.read_text(encoding='utf-8'))) if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) and len(re.findall(r'lreq\(', ' '.join(ast.unparse(d) for d in n.decorator_list)))>1]"`
  → **8 rows**: **7** in `tests/test_database.py` and **1** in
  `tests/test_validation.py`, namely

  | Module | node ID | marker set (marker's own order) |
  |---|---|---|
  | `tests/test_database.py` | `test_foreign_key_and_pragma_contracts_are_enforced` | `LREQ-SEC-020`, `LREQ-GQL-080` |
  | `tests/test_database.py` | `test_insert_versus_upsert_semantics_per_table` | `LREQ-SMP-080`, `LREQ-GQL-080`, `LREQ-SEC-020` |
  | `tests/test_database.py` | `test_enum_backed_columns_reject_unknown_values` | `LREQ-SEC-020`, `LREQ-ID-040` |
  | `tests/test_database.py` | `test_repository_never_persists_or_leaks_secrets` | `LREQ-SEC-020`, `LREQ-NFR-060` |
  | `tests/test_database.py` | `test_at_most_one_enrichment_row_per_run_and_identity` | `LREQ-GQL-080`, `LREQ-TST-030` |
  | `tests/test_database.py` | `test_discovery_terminal_states_round_trip_without_zero_substitution` | `LREQ-EXT-050`, `LREQ-EXT-090` |
  | `tests/test_database.py` | `test_category_isolation_preserves_unrelated_observations` | `LREQ-SMP-080`, `LREQ-EXT-090` |
  | `tests/test_validation.py` | `test_category_mismatch_and_unverified_map_to_discovery_status_vocabulary` | `LREQ-EXT-050`, `LREQ-EXT-090` |

  **Unit:** distinct pytest node IDs (8), one row each, versus occurrences (13 decorator
  matches across those 8 nodes). **Reproduction of §5.7's attribution, succeeded:** the
  plan asserted 7 such nodes in `tests/test_database.py` and 1 in
  `tests/test_validation.py`, and each node's matrix array holds its full marker set as a
  multi-element array. **Arithmetic reconciliation, addition shown:** `31 − 23 = 8`
  additional occurrences in `tests/test_database.py` = 7 nodes × 1 extra decorator + **1**
  three-marker node (`8 = 7 + 1`); `23 − 22 = 1` in `tests/test_validation.py` = 1 node ×
  1 extra decorator; so `8 + 1 = 9 = 152 − 143`, and the repository-wide figure is
  **9 additional decorator occurrences over 8 stacked nodes**, with every matched line
  assigned to exactly one category. §5.7's decomposition is therefore **correct as
  written**; only its raw-substring illustration (the `153` / `154` sentence) was wrong.
  Note the third marker set in this table is `["LREQ-EXT-050", "LREQ-EXT-090"]` in
  `tests/test_validation.py` while Chunk 5's plan line 1385 describes the pre-Chunk-5
  `tests/test_collector.py` at "25 markers over 13 distinct nodes"; both are legal shapes
  and neither is a defect (§5.7's own point).
- **Q-M″ — the three findings this correction pass could not fix inside this file.**
  Recorded as queries so each is reproducible; none may be edited by this pass (§11
  forbids editing anything under `Documents/`). **Unit: occurrences / quoted text /
  distinct identifiers, as named per item.**
  - **(a) A false premise that has propagated into a second plan.** `Grep` for
    `25 markers over 13 distinct nodes` over `Documents/plans/` returns **3 rows**, all in
    `Documents/plans/chunk-05-graphql-protocol-adapter-and-response-correlation.md`, at
    its lines **98**, **1167**, and **1386**. **Measured on the artifact now:**
    `tests/test_collector.py` does not have 13 distinct marked nodes — it has **51**
    (`tests/traceability.json` holds **51** entries keyed to that module, and the `ast`
    walk finds **51** marked nodes, Q-U). **The "13" is a pre-Chunk-3 figure, not a
    current one:** an actual **regression** has since occurred in that file, and it is
    **not** covered by Chunk 5's plan line 1385 ("its fixtures, its module-level …") nor
    by this plan's §10 ("non-recursive and collects the same module set" speaks to the
    module *set*, not to node count). `tests/traceability.json` carries **51** entries for
    `tests/test_collector.py` — the same **51** as its distinct marked node IDs and **2
    fewer** than its **53** collected node IDs (§5.6, Q-U) — so the matrix agrees with the
    artifact and disagrees with all three prose sites. This is the **second** instance of
    the same stale-count class across two consecutive plans — the **third** once
    **(b)** below is counted — and it is the defect class this plan exists to make
    visible; this plan does not absorb the fix. Its most recent measured projection is
    **error, error**, where Chunk 3's plan recorded **pass** (Chunk 3's plan line 1607).
  - **(b) A second false figure inside the same frozen plan.** Chunk 5's plan line 2044
    states `tests/test_collector.py` is **`1310 lines`**, with the parenthetical "(not
    1313 / 26 / 21)". **Measured:** the file is **2533 lines** (1-based line count of
    `tests/test_collector.py`, unit: lines; the file ends with a newline, so its newline
    count is one less). **Measured, the line-2046 figures are not about the file they are
    attached to:** that sentence's "**25** marked test nodes carrying **25** …
    occurrences over **8** distinct LREQ IDs, **0** unmarked" are all still correct for
    **`tests/test_identity.py`** — but `0 unmarked` is wrong if the sentence is read as
    being about `tests/test_collector.py`, which has **2** unmarked nodes
    (`test_module_imports_without_side_effects`,
    `test_request_body_builder_signature_is_stable`, both inside the
    `# Non-analytical tests (no marker, no traceability entry)` banner at its line 321) and
    **51** marked ones, not 25. Both counts-only regressions are Chunk 5's to correct
    under the same counts-only exception its own item 7 claims.
  - **(c) A file this plan cites in six sections does not exist, and the plan file set is
    a different set from the one this plan describes.** `Glob` for `Documents/plans/*.md`
    returns **7** paths; **unit: distinct files**. The five numbered plans present are
    `chunk-00-…md` (806 lines), `chunk-01-…md` (920), `chunk-02-…md` (1454),
    `chunk-03-…md` (1110), `chunk-05-…md` (2365), plus `_TEMPLATE.md` (73) and this file
    (`tooling-p0-2-…md`). **`chunk-13-coveo-graphql-endpoint-verification-and-cross-cutting-validation.md`
    is absent**, and so are `chunk-04A`, `chunk-05a`, `chunk-05b`, `chunk-05-c3-…`,
    `chunk-06A`, `chunk-06B`, `chunk-07B`, `chunk-09A`, `chunk-10`, `chunk-12`, and
    `tooling-p0-1-…` — every one of which this plan or its prerequisites name as though it
    were readable. This pass's own verification step for [INV-3] reads the `Status:` line
    of `chunk-13-…md`; **that read is not possible on this tree**, so the `DRAFT` status
    previously asserted in this item is **withdrawn as unverified** — it was not read, and
    the file is not on disk. **The distinction that matters, so the blocker is sized
    correctly:** Chunk 13 itself is **not** missing — `Documents/requirements-dependency-map.md`
    line 1066 defines it (`## Chunk 13 — Full acceptance suite and quality workflow`), its
    gate bullet is quoted at this plan's line 25 and line 144, and `LREQ-NFR-060`'s
    ownership row is quoted at line 133. What is absent is the **plan file** for Chunk 13,
    which this plan cites by filename for a `Status:` read it cannot perform. **This is a
    blocking open question, not a finding to resolve here:** either the repository state
    this plan was authored against is not the state on disk, or `chunk-13`'s plan was never
    written. **Nothing in this plan requires a `chunk-13` plan file at *implementation*
    time** — `COMPLETE_CHUNKS` is calibrated to Chunk 0 only, and adding any other chunk to
    it is a defect per §11 — so the blocker is on calibration and review, not on the code.

**`.scratch` discipline:** this planning task wrote four files —
`.scratch/p0-2-enumeration.py`, `.scratch/p0-2-provenance.py`,
`.scratch/p0-2-vanish-repro.py`, `.scratch/p0-2-index-safety.py` — and deletes all four
in the same task, per the standing `.scratch`-per-dispatch rule. **Re-listed after
deletion to verify the final state**, per `.scratch/README.md`'s "Cleanup" section:
the directory is back to its prior content — `.scratch/README.md`,
`.scratch/chunk05-c3-ids-baseline.txt`, `.scratch/chunk05-ids-baseline.txt` — none of
which this task created, and none of which this task may delete (they belong to other
tasks and are cross-task evidence this plan must not destroy).

## 12. Open questions / assumptions

Thirteen items (corrected 2026-09-18: this sentence previously read "Fourteen
items"; the file carries thirteen `### 12.x` subsections, one per item, and no
unheaded fourteenth item — COUNTED: `python` read of every line beginning
`### 12.` over this file reports 13, at lines 1086, 1109, 1132, 1152, 1168,
1179, 1195, 1202, 1210, 1222, 1237, 1247, 1268, the same 13 lines the audit's
`###`-anchored query returned, so the two differ in unit only — heading lines
vs. distinct subsection numbers — and not in number; the prior wording is
quoted here rather than deleted, per the dated-correction convention);
**§12.1, §12.3, §12.5, §12.6, §12.10, §12.12, and §12.13 are flagged for
a human ruling before this plan is treated as a settled scope contract.** §12.10 is
listed as needing a ruling though it is not marked "Needs a human ruling" in its heading:
it ends in "**A human should confirm…**". §§12.2 and 12.4 are recorded resolutions or
disclosed assumptions that need no ruling. §§12.12 and 12.13 were added by the plan audit
and **do not change the plan's design or scope** — §12.12 is a wording question about
`COMPLETE_CHUNKS`'s membership rule, §12.13 is a question about a rule file this plan may
not touch.

### 12.1 Blocking: the baseline figures this plan's gate depends on

`python -m pytest tests -q` currently reports **`6 failed, 139 passed`**, not the
`119 passed` recorded in `Documents/plans/chunk-03-coveo-discovery-adapter-and-streamed-raw-persistence.md`
(its line 5) and not the figure either frozen plan's verification text implies. All six
failures are in `tests/test_collector.py`, all six are **marked** nodes, and none is
predicted by `Documents/plans/chunk-05-...md`'s "known Chunk 0
`test_repository_protocol_and_schema_specification` failure" note (its line 1264) —
that node **passes** today, which Chunk 5's own item 7(d) already corrected (its line
2116).

Consequences, each of which a human should confirm rather than have this plan assume:

1. The implementing agent cannot claim a green suite; it can only claim *its own*
   changes introduced no new failure. The gate bullet in §10 is worded for that.
2. `tests/test_collector.py` is inside the set of files this plan may not touch, but it
   is also the file whose six failures are the most likely to be mistaken for this
   change's regressions.
3. The six failing nodes are Chunk 5's. This plan assumes but **cannot verify** that
   they are the *known open* work of the stalled Chunk 5 dispatch rather than a new
   regression; if they are a regression, an earlier dispatch's report is wrong.
   **A human should say which before the implementer runs its baseline.**

### 12.2 Recorded resolution: no manifest, and why

`tests/AGENTS.md` (§ "Test Agent Rules", its lines 5–13) **mentions** a second JSON
layout — "`tests/traceability.json` is an object keyed by individual `LREQ-*` IDs.
Each value is an array of fully qualified pytest node IDs" — which is the **transpose**
of the layout that actually exists: `tests/traceability.json` is keyed by node ID
(lines 2–14 quoted for this plan), and `tests/traceability.json`'s real key set is
node IDs.

- **It does not block this plan and it is not a second convention.** `validate_traceability.py`
  is unambiguous and authoritative on the layout; `tests/AGENTS.md` line 13's own
  sentence ("Every individual requirement defined by `Documents/SRS-lean.md` must be
  present as a key" and "every analytical test must have both a marker and a matrix
  entry") describes this plan's *goal* state, not the file's shape. The likely
  history is that the rule file describes the intended layout and the file grew the
  other way. **The tool is the tie-breaker; no file's `Status` changes.**
- This is also why the **manifest** design option was rejected. A manifest of declared
  node IDs would live in `tests/` (a new file, outside this plan's §6), would have to
  be kept in sync by every future chunk with no enforcement mechanism (the same
  "trust the plan file" problem), and would duplicate a layout that `tests/AGENTS.md`
  already describes inconsistently. The requirement-axis approach needs no new file,
  no new maintenance surface, and no new convention.

### 12.3 Disclosed and not fixed: the Chunk 5 plan alias and the deleted capture node

`Documents/plans/chunk-05-...md` §9 (its lines 1489–1491) declares the three node
names, and its own text at its line 1494 says "The former 29th node,
`test_duplicate_operation_names_correlate_by_operation_name_in_captured_batches`
(`LREQ-GQL-030`), is **removed from the frozen set along with its `tests/traceability.json`
entry**." An earlier artifact state therefore probably held an entry for a node name
that no `def` ever backed, which the tool reports as `orphan_nodes` today (**counted**:
`orphan_nodes = 0` on the current tree).

This plan does **not**:
- classify a plan-declared node name as a distinct status,
- exempt an alias-only matrix row from `orphan_nodes`,
- author a capture, a fixture, or an entry for that node.

It only **reports** alias-only rows in the summary line's `{n_matrix_alias_rows}` so the
condition is visible without being silently tolerated. If a human wants the alias row
to be tolerated rather than fatal, that is a separate ruling on `main`'s exit-code
contract and belongs to **Chunk 13**, which owns the tool's widening.

### 12.4 Disclosed coverage gap: the check cannot detect a deleted node

The requirement-axis check detects an LREQ ID with no marker anywhere. It does **not**
detect the strictly harder case: a plan declares node `N` for requirement `R`, `N` was
written and then deleted, and some **other** node still marks `R`. That is a real gap
in what this plan claims to close, and it is closed by the existing `orphan_nodes`
check only if the matrix entry survives — which is exactly what Chunk 5's line 1494
says was removed along with the node.

Closing it properly requires a **frozen declaration surface** (a machine-readable list
of node ID → LREQ written at plan-freeze time and updated only by an explicit
coordination task). That is the manifest design this plan rejected in §12.2 for
*this* chunk, and it is a larger change with a scope question of its own: who updates
the declaration when a node is legitimately removed. **Recommended owner: Chunk 13**,
as part of the traceability work its gate bullet already requires.

### 12.5 Needs a human ruling: `LREQ-NFR-050` appears in two exclusion categories

§5.3 lists `LREQ-NFR-050` under both `plan_owned_disclosed` (item 1: complete primary
owner Chunk 0) and `delivered_elsewhere` (item 3: SRS Appendix B assigns `LREQ-NFR-*`
a `cross-cutting` owner with "project checks and end-to-end tests"). Exactly one status
is required by [INV-5]. This plan chooses `plan_owned_disclosed` and records the other
anchor as corroboration. A reviewer who prefers `delivered_elsewhere` changes which
line of `STATUS_EXCLUSIONS` the ID sits on and nothing else; a reviewer who wants
`LREQ-NFR-050` to remain a defect should say so, because the consequence is a
permanently-red validator until someone writes a platform smoke test.

### 12.6 Needs a human ruling: the check goes red on the current tree

Because `LREQ-NFR-040` and `LREQ-NFR-050` are *already* enumerated as
`plan_owned_disclosed` (not defects) and the remaining complete-owner IDs are marked,
the tool is expected to stay **green** on the current tree. The plan cannot prove that
before implementation, and two outcomes are possible:

- **Green** (expected): the check's only live effect today is the richer summary line
  and the advisory note. §7 step 6 is the instrument that converts this expectation
  into evidence.
- **Red**: some ID is `pending_setup_phase` that this plan did not predict. That is a
  *finding*, not a failure of this plan, and it must be reported rather than silenced
  by adding an exclusion — an exclusion added to turn the check green is the
  `119 passed` failure mode in a new costume. **The implementing agent SHALL stop and
  report a red result instead of adjusting `STATUS_EXCLUSIONS` to clear it.**

### 12.7 Disclosed assumption: `COMPLETE_CHUNKS` maintenance is a process, not a test

[INV-2] is enforceable only by review. No test can decide whether a chunk's `Status:`
line was read correctly. Recorded so the next reviewer does not treat the literal as
self-maintaining. A candidate mechanical guard (compare each entry's `Status:` line to
a policy constant) is a **Chunk 13**-scope idea, not this plan's.

### 12.8 Disclosed assumption: `Source analyzed:` is not validated

`requirements-dependency-map.md` line 5 names a `Source analyzed:` path under the
authoring machine's user profile. `validate_traceability.py` reads `Documents/SRS-lean.md`
by relative path (its line 26) and never consults that string. This plan keeps that
behaviour; validating the pointer is not this plan's job and the string is stale-looking
only because it is absolute.

### 12.9 Disclosed assumption: the advisory scan's cheapness is asserted, not proved

`declared_plan_node_names` is specified as a token scan (backticked or `::`-qualified
`test_<identifier>` tokens), not a table parse, because the plans' traceability tables
have at least three mutually incompatible shapes (**quoted**: the §9 marker tables in
`chunk-01-...md` (its lines 714–735), `chunk-03-...md` (semicolon-prose rows), and
`chunk-05-...md` (its lines 1489–1491) do not share a header, and `chunk-00-...md` has
no such table). The scan's **precision** is therefore unknown and unasserted; the plan
accepts a false-positive-prone advisory list because §5.5 makes the list
non-normative. If the list proves noisy enough to be ignored, that is an argument for
deleting the advisory check, and the deletion is a one-function change.

### 12.10 Needs a human ruling: the new test module's requirement attribution

Chunk 5's plan §11 forbids it from widening this tool; Chunk 1's plan R-3 defers the
widening to Chunk 13. **No frozen plan names this plan or authorizes a new test module
under `tests/`.** The module is required anyway: Chunk 0's gate bullet (dependency map
line 438) makes a marker-plus-matrix-entry pair mandatory for *every analytical test*,
so a test for the changed tool cannot be written without one, and without such a test
this plan's own §10 gate bullets are untestable. The marker chosen is
`LREQ-NFR-060` — the tooling requirement, primary owner Chunk 13, Chunk 0 a supporting
chunk. **A human should confirm that this is not read as an unauthorized ownership
claim by Chunk 13.** §12.6 explains why this choice also has a sequencing consequence:
adding the marker for `LREQ-NFR-060` while writing the tests is what keeps that ID out
of `pending_setup_phase`, and doing so is the plan's own answer to its own check —
which is honest only if the marker is on real tests and not a placeholder.

### 12.11 Out of scope, disclosed: the six failing `test_collector.py` nodes

Recorded here so a later reader does not discover them as a surprise: six marked
analytical nodes in `tests/test_collector.py` fail today, all
`LREQ-GQL-*`/`LREQ-SEC-020`-marked, all owned by the stalled **Chunk 5**
implementation. This plan neither fixes nor reclassifies them. If a future
`validate_traceability` enhancement is asked to catch this class, the honest answer is
that the tool cannot see it (§8.6) and that the catching mechanism is
`python -m pytest`, not traceability.

### 12.12 Needs a human ruling: `COMPLETE_CHUNKS`'s membership rule has no stated cross-chunk condition

Added by the plan audit. [INV-1] clause (c) reads: *"the dependency map's ownership matrix
names at least one chunk that is complete"*. On `LREQ-SEC-010` (dependency map line 68:
primary owner **Chunk 0** — complete — with completion chunks Chunk 3, Chunk 5, Chunk 12)
that literal rule is satisfied and the ID is unmarked (Q-B), so clause (c) puts it in the
defect set unless §5.3 item 3 excludes it as `delivered_elsewhere`. The plan's *intent*
(§5.1's `owned_not_yet_implemented` wording, §5.2's `complete_chunk_requirements`) is the
stricter "primary owner complete **and** every completion chunk complete", which returns
**2** matrix rows today (`LREQ-ARCH-010`, `LREQ-ARCH-020`) and leaves the defect set
empty. The two readings differ by exactly one ID today, and by four (`LREQ-SEC-010` plus
`LREQ-NFR-040`, `LREQ-NFR-050`, `LREQ-NFR-060`) if §5.3 were dropped.

**The question a human must answer:** does an ID whose primary owner is complete but whose
completion chunks are not (Chunk 3's and Chunk 5's `LREQ-SEC-010` work) belong in
`pending_setup_phase` or in `owned_not_yet_implemented`? §5.3 already excludes
`LREQ-SEC-010` either way, so nothing in the current tree changes; the choice is binding
for the *next* chunk that completes. It also decides whether §5.3 item 3
(`delivered_elsewhere`) is load-bearing or decorative, and whether clause (c) should be
restated as the conjunction.

### 12.13 Needs a human ruling: whether later plans must cite a marker's LREQ ID

Added by the plan audit. The plan's advisory check is scoped to a **node name** (§5.5),
and §5.3's exclusion test does not depend on plan prose. Neither surface, and no rule
file, states an obligation that a later chunk's plan cite a node it intends to rely on
**together with one of that node's LREQ IDs**. Chunk 5's plan relies on 23 existing
marked nodes — including the two the validator reported as failing tests, which trigger
its own gate — while naming their LREQ IDs nowhere: only one of those 23 marker sets
(`LREQ-ARCH-010`, line 1744) has any of its IDs written in that plan. So on the plan
audit's own Q-D query, 23 of 143 marker-carrying nodes would be **invisible** to any
plan-side check built on the name-plus-ID shape the plan-writer's own Q-D query relies on.

This plan does not absorb the question. §5.5's advisory check is name-equality only and
must not be widened here, and adding a citation obligation to a rule file is outside this
plan's §6 file set.

**The question a human must answer:** is "a plan that relies on an existing marked node
must cite that node **and** one of its LREQ IDs" a rule anywhere, and if not, should it
be — or is name-only citation the deliberate convention? Its answer decides whether Q-D's
"cited by" figures mean *cited for that requirement* or merely *mentioned*; §5.5's
argument that "name equality is not a contract" survives either way.
