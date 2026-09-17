# Finish Chunk 5 — traceability, plan corrections, gate

# Finish Chunk 5 (GraphQL adapter): traceability, plan corrections, gate

## Goal

Take Chunk 5 from "all 25 test nodes written but unexecuted" to a completed, gate-verified chunk with a published interface contract — by first proving the tests actually run, then closing the traceability gap, then correcting the frozen plan's three residual defects, then gating.

## Verified starting state (anchored enumeration, not carry-forward)

| Item | Value | How it was established |
|---|---|---|
| `tests/test_collector.py` | ~2448 lines | Read `total_lines` |
| Chunk 5 marked nodes | **25 of 25 — none missing** | anchored `^@pytest\.mark\.lreq\(` grep, split at banner line 1322 |
| Chunk 3 marked nodes | 25 (file total 50 markers) | same query |
| `def test_` total | 52 = 27 Chunk 3 + 25 Chunk 5 | anchored `^def test_` grep |
| Chunk 3 unmarked nodes | 2 (`test_module_imports_without_side_effects`:309, `test_request_body_builder_signature_is_stable`:341) | declared non-analytical at :305 |
| Traceability entries for Chunk 5 nodes | **0 of 25** | `Grep "test_collector\.py" tests/traceability.json` → 25 rows, all Chunk 3, JSON lines 94–118 |
| `ProductDetailFieldsProtocol` | 0 repo-wide matches | full-repo grep — deletion landed |
| `test_page_view_scalar_type_and_range_acceptance` | 1 marker: `LREQ-GQL-040` (line 1986) | direct read of 1986–1987 |
| Tests executed against Chunk 5 code | **zero** | no member has run pytest |

**Known blocker for this plan:** no agent in this workspace has a command-execution tool. `AwaitShell` only waits/observes an existing job; there is no `Shell` tool. The human must run the four commands in Step 1 and paste output. One member proved `Rg` is broken (`ripgrep is not available on this machine`); use `Grep`.

## Ordered steps

### Step 1 — Human runs the verification commands (BLOCKING)

The human runs and pastes:

```powershell
python -m pytest tests/test_collector.py -q
python -m pytest tests/ -q
python -m pytest tests/test_collector.py --collect-only -q -m lreq
git diff --numstat -- tests/test_collector.py
python -m niche_scout.tools.validate_traceability
```

Interpretation rules, decided in advance so the next step is mechanical:

- **Collection error ≠ test failures.** An import error invalidates any "tests pass" claim and must be reported as a distinct outcome, not folded in with failures.
- `--collect-only -m lreq` must report **50** marked nodes (25 Chunk 3 + 25 Chunk 5). Anything else means a node failed to collect.
- `git diff --numstat` **deleted column MUST be 0** on `tests/test_collector.py`. Non-zero means the append disturbed Chunk 3's frozen file; every removed line must be listed verbatim.
- `validate_traceability` is **expected to FAIL** with 25 `missing_nodes` until Step 2 lands. That is the validator working, not a surprise.

Do not proceed to Step 3 if Step 1 shows a collection error or a non-zero deleted count — those are human checkpoints per the project rule.

### Step 2 — Append 25 traceability entries to `tests/traceability.json`

File: `tests/traceability.json` (currently 120 lines / 119 entries).

- **Generate the entries from the written file, not from the plan's §9 table.** The file's node ordering does not match plan order, so plan-derived keys risk 25 orphans + 25 missing_nodes simultaneously.
- Schema to mirror character-for-character (2-space indent, `"tests/<file>.py::<node>"`, value is an array, comma on every entry except the final one): follow the existing Chunk 3 precedent at JSON line 110.
- Append after the current last entry (line 118); the old final entry gains a trailing comma; the closing `}` moves down.
- Expected keys and IDs — **verify each against the file before writing**, do not trust this list:

  | Node | LREQ |
  |---|---|
  | `test_batch_request_has_exactly_two_operations_with_one_identity` | GQL-010 |
  | `test_adapter_cannot_bulk_enrich_or_consult_preflight_state` | GQL-010 |
  | `test_product_detail_query_requests_only_required_fields` | GQL-020 |
  | `test_page_views_operation_requests_its_scalar` | GQL-020 |
  | `test_request_construction_requires_graphql_credential` | SEC-010 |
  | `test_reversed_response_order_correlates_by_explicit_key` | GQL-030 |
  | `test_missing_correlation_key_is_malformed_not_positional` | GQL-030 |
  | `test_duplicated_unknown_and_ambiguous_correlation_fail_safely` | GQL-030 |
  | `test_explicit_key_mode_never_falls_back_to_response_position` | GQL-030 |
  | `test_validated_position_mode_is_accepted_not_validated_here` | GQL-030 |
  | `test_http_failure_is_an_operation_error` | GQL-040 |
  | `test_top_level_errors_are_not_masked_by_sibling_success` | GQL-040 |
  | `test_operation_level_errors_on_http_200_are_operation_errors` | GQL-040 |
  | `test_null_required_data_and_wrong_data_shape_are_operation_errors` | GQL-040 |
  | `test_invalid_state_value_and_missing_identity_are_operation_errors` | GQL-040 |
  | `test_page_view_scalar_type_and_range_acceptance` | GQL-040 **(single-element — confirmed one marker)** |
  | `test_retry_backoff_on_transient_and_no_indefinite_retry` | GQL-040 |
  | `test_partial_success_retains_valid_operation_fields` | GQL-050 |
  | `test_failed_operation_fields_are_none_never_zero` | GQL-050 |
  | `test_state_annotation_covers_published_excluded_and_unknown` | GQL-060 |
  | `test_state_excluded_and_unknown_assets_remain_recorded` | GQL-060 |
  | `test_adapter_declares_no_metric_eligibility_verdict` | GQL-060 |
  | `test_transport_failure_does_not_escape_as_an_exception` | NFR-030 |
  | `test_request_metadata_json_carries_required_fields_without_secrets` | SEC-020 |
  | `test_error_summaries_and_metadata_are_redacted` | SEC-020 |

  Arithmetic: 2+2+1+5+7+2+3+1+2 = **25**.

- **Corruption guards (must all hold):** no existing entry modified, extended, reused, reordered, or deleted; `marker_mismatch` = 0 (each entry's array equals its node's actual marker set — **read the decorator, don't copy this table**); `orphan_nodes` = 0; `missing_nodes` = 0 after the write.
- Re-run `python -m niche_scout.tools.validate_traceability` (human) — it must now pass.
- **Do not add entries for the 3 `test_identity.py` nodes** in this step. See Step 4.

### Step 3 — Correct the three plan defects

File: `Documents/plans/chunk-05-graphql-protocol-adapter-and-response-correlation.md` (FROZEN, ~2365 lines). `Status: FROZEN` line is untouched; no box is ticked.

**Defect 1 — box 16 carries a retracted claim.** Lines 1262–1266 instruct recording a "known Chunk 0 `test_contracts.py::test_repository_protocol_and_schema_specification` failure... as pre-existing." §12.2 item 7(d) (lines 2116–2125) and item 8 (2145–2152) record that this was a **fabricated observation** — the node passes (`1 passed`). §6 and §11 were already corrected; box 16 is the last surviving copy. Rewrite box 16's clause to state the node **passes** (marker verified at `tests/test_contracts.py:881`, decorator immediately above `def` at 882) and that `test_contracts.py` is outside Chunk 5's file scope.

Note: the `938 → 881` citation correction is **already landed** in §6 (1183–1188) and §11 (1745–1748); there is no literal string `Box 16` in the plan — it is the 16th `- [ ]` item.

**Defect 2 — four `1310` occurrences.** Plan lines 98, 1167, 1384, 2045. All four use 1310 as "the file as Chunk 3 froze it, **before** Chunk 5 appends." Treatment: **keep the figure, label it explicitly as the pre-append / Chunk-3-frozen baseline, and drop any implication it is the file's present size.** Do **not** re-measure to the current 2448 — that would describe Chunk 5's own output as external pre-existing state (the same category error as the earlier "13 distinct nodes" bug recorded at plan 2126–2129).

**Defect 3 — `additional_correlation_keys` has no §9 node.** §9's matrix is 28 table rows; none scopes it. The SRS does not name it (`SRS-lean.md` grep: 0 rows); its parent is `LREQ-GQL-030`'s permissive "**or another validated correlation key**" clause (SRS-lean.md:300–306). But `tests/test_collector.py:2348–2350` **already asserts it**. This is a human decision (Step 5) — **do not invent a 29th node.** If the ruling is "needs a node," the "exactly 28 entries" clause must be made consistent in the same pass.

### Step 4 — Decide the 3 `test_identity.py` nodes (HUMAN)

Plan §9 rows 26–28 assign three `LREQ-GQL-070` nodes to `tests/test_identity.py`:

- `test_correlated_product_detail_reports_alias_mismatch`
- `test_missing_returned_identity_is_not_an_implicit_match`
- `test_adapter_mismatch_is_a_flag_not_a_metric_exclusion`

They are **not written**. They were deliberately relocated out of `test_identity.py` because that file is now a **verification artifact** — its 25-markers/25-nodes bijection is the evidence cited in §12.2 items 7 and 8, and adding nodes there changes the count those records depend on.

Options: (a) write them into `test_collector.py` with the other 25; (b) write them into `test_identity.py` as the plan's §9 table specifies, and add a note that the file's count is now 28; (c) defer them as an open item.

**If (b) is chosen, §12.2 items 7 and 8 must be re-verified in the same pass** — their citations depend on `test_identity.py` holding exactly 25 markers over 8 distinct LREQ IDs (6+6+5+4+1+1+1+1 = 25).

### Step 5 — Human rulings on the two open items

1. **`additional_correlation_keys`:** does it require a marked §9 node, or is surfacing it in `request_metadata_json` an uncontracted implementation detail? (Currently the code tests something the frozen plan does not authorize — the behavior is implemented and asserted but not contracted.)
2. **Scope of the traceability requirement:** `validate_traceability.py:131` calls `chunk_requirements(text)` with **no chunk argument**, and the signature at `:54` defaults `chunk: str = "0"` (docstring `:3`, message `:180–181`). So `missing_required` can **never** fire for Chunk 5 — **the requirement→test direction is unvalidated.** `missing_nodes` / `marker_mismatch` / `orphan_nodes` (`:144–153`) *are* suite-wide and do bind. The plan's manual two-directional cross-check (§9, ~1568) is therefore the **only** coverage check for this chunk, and it must be performed with its enumeration pasted, not asserted.

### Step 6 — Gate

Run the `gate-verifier` against the frozen plan and publish `Documents/interfaces/chunk-05.md`.

The gate report MUST include:
- the Step 1 pytest output (full-file pass/fail, marked-node count, collection-error check);
- `git diff --numstat` for `tests/test_collector.py` with the deleted-line verdict;
- the `validate_traceability` result;
- **the manual two-directional LREQ cross-check, with its anchored enumeration pasted** — §3's LREQ table against the actual markers, both directions;
- an explicit reading on `collector.py` lacking `__all__` (plan §11 mentions "import statements and `__all__`"; QC flagged the absence);
- the `collector_graphql.__all__` arity — **49 or 50** is still unreconciled against the plan/summary's 50;
- explicit statement of whether any Definition of Done bullet is FAIL (a FAIL is a human checkpoint per the project rule).

## Risks and open items carried forward

| Item | Status |
|---|---|
| No command-execution tool in this workspace | **Blocks Steps 1 and 6** until the human runs the commands |
| 25 Chunk 5 nodes have markers but no entries | Step 2; validator will fail until fixed |
| `additional_correlation_keys` contracted? | Step 5, human |
| 3 `test_identity.py` nodes unwritten | Step 4, human |
| `collector.py` has no `__all__` | Gate must read explicitly |
| `collector_graphql.__all__` = 49 vs plan's 50 | Reconcile at gate |
| Chunk 6A run-start init (SRS-revision2.md:196) | Human ruling required; not a Chunk 5 item |
| Chunk 7B `LREQ-MET-090` detection rule | Open; not a Chunk 5 item |
| `LREQ-TST-040` two-plan collision, zero marked nodes | Chunk 13's marker pass |
| OI-6 ownership: no chunk owns it | Record in map §7 with four sub-questions verbatim; Chunk 5 neither resolves nor absorbs |
| Chunk 5 supplementary sourcing (C3) | Add to §12.1 Q5 "Chunk 5 sets nothing" bullet: map Chunk 5 gate line 681 + SRS-lean.md:642 |
| `.scratch/` holds pre-existing agent artifacts | Not yet cleaned |

## Verification

Chunk 5 is done when, and only when:

1. `python -m pytest tests/test_collector.py -q` passes with **no collection error**, and Chunk 3's 25 nodes still pass.
2. `git diff --numstat -- tests/test_collector.py` shows **deleted = 0**.
3. `python -m pytest tests/test_collector.py --collect-only -q -m lreq` reports **50** marked nodes.
4. `python -m niche_scout.tools.validate_traceability` passes.
5. The manual two-directional LREQ cross-check is performed and pasted.
6. The gate report is published with no Definition of Done bullet FAIL, and `Documents/interfaces/chunk-05.md` exists.

## Process note

Six errors of one kind occurred during this chunk: a countable property asserted rather than re-derived (a marker count; a node composition; a per-file entry count; a node total; a cross-file docstring contamination; a claimed tool capability). Every one was caught by re-running a query against the artifact, and none by re-reading a report. The rule now in `.cursor/rules/project-rules.md` ("Plan review and audit") requires any count written into a frozen document to ship with its anchored enumeration. **It applies to dispatch messages and to the project lead.** No count in this plan was carried forward; each is attributed to the query that produced it.
