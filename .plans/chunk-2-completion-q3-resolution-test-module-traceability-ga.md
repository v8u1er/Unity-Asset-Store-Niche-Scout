# Chunk 2 completion: Q3 resolution, test module, traceability, gates

# Chunk 2 completion: Q3 resolution, test module, traceability, gates

## Goal

Finish Chunk 2 without re-opening its frozen plan: resolve the one internal
contradiction in `database.py` (`computed_at_utc`), write the missing
`tests/test_database.py`, append the planned traceability entries, run the four
verification commands, and only then let the gate-verifier start.

## Verified starting state (read from disk, not from the dispatch reports)

- `Documents/plans/chunk-02-...md` line 3 = `Status: FROZEN`; §12 closed (Q1–Q7);
  §12.1 records the two deleted false citations.
- §10's seven bullets match `Documents/requirements-dependency-map.md` lines
  **512–518** word-for-word. The plan's citation "lines 510–518" is off by two
  (510 = `Gate:`, 511 blank); bullets are exact. Cosmetic only.
- §6 authorizes exactly three files: `src/niche_scout/database.py`,
  `tests/test_database.py`, `tests/traceability.json`.
- `src/niche_scout/database.py` = 1,260 lines: exception hierarchy (325–349),
  codecs, `SqliteRepository` (693) with all five frozen protocol methods plus
  the additive surface (`transaction`, `savepoint`, `category_transaction`,
  `append_raw_discovery_observations`, `stream_raw_discovery_observations`,
  `update_run_preflight`, `set_category_status`, `update_raw_discovery_identity`,
  5× `count_*`, `upsert_*`). Streamed sink has the raise-outside-category guard
  (1031–1035) and per-batch savepoints (1055+).
- `tests/` has `test_contracts.py`, `test_validation.py`, `traceability.json`.
  **No `test_database.py`.** `traceability.json` has zero `test_database` matches.
- `tests/traceability.json` is **node-keyed**
  (`"tests/test_contracts.py::test_models_import": ["LREQ-ARCH-010"]`), per
  `tests/AGENTS.md` lines 5–10. 23 existing entries.

## Two corrections to the dispatch framing

1. Traceability self-validates without a new manual step. In
   `src/niche_scout/tools/validate_traceability.py`, `missing_nodes`,
   `marker_mismatch`, and `orphan_nodes` (lines 144–151) are computed across
   **all** of `tests/`; only `missing_required` is scoped to
   `chunk_requirements(text, chunk="0")` (line 131). So markers-without-entries
   and entries-without-nodes both fail immediately. The §10 manual cross-check
   remains necessary only for the *completeness* direction (every §3 LREQ has at
   least one entry).
2. The split "test module" / "traceability + gates" is a false split: the first
   dispatch would leave the validator red on 23 marked-but-unmapped nodes, and
   the second cannot produce markers on its own. Order must be
   test module → traceability → gates.

## Step 1 — Resolve Q3 inside `database.py` (implementer)

The defect, confirmed by reading both files:

- `models.py:509` — `CategoryScoreRecord.computed_at_utc: datetime` is
  **non-optional**; `__post_init__` (511–512) calls `_validate_utc_fields()`, so a
  `None` is unrepresentable in the frozen record.
- `database.py:436-449` — `_NULLABLE_COLUMNS` is derived by scanning each DDL
  line for the literal `NOT NULL`. `computed_at_utc` has no `NOT NULL`, so it is
  treated as nullable.
- `database.py:502` — `"computed_at_utc": _IMPLICIT_NULLABLE` is placed inside
  `_IMPLICIT_NOT_NULL_DEFAULTS["category_scores"]`, a mapping documented as
  "columns whose value is not yet knowable but that are declared `NOT NULL`".
  The inversion also makes `_validate_required_columns` (557–563) skip the column
  entirely (`if value is None: continue`).
- `database.py:962-994` — `set_category_status` therefore inserts
  `computed_at_utc = NULL` and is returned by `get_category_scores`, whose
  reconstruction cannot build the frozen record.

Required change (the only permitted shape, because §11 forbids new columns,
`ALTER TABLE`, and schema invention):

- Remove `computed_at_utc` from `_IMPLICIT_NOT_NULL_DEFAULTS["category_scores"]`
  in `src/niche_scout/database.py` so it becomes a bindable column.
- In `set_category_status(run_id, category, discovery_status)`, bind an explicit
  value for `computed_at_utc` instead of NULL. Preferred: add a keyword-only
  `computed_at_utc: datetime | None = None` parameter and, when it is `None`,
  derive nothing from the clock — the repository must not read the system clock
  (§11: `*_at_utc` values come from the caller). If a concrete value is required
  for a discovery-only row, take it from the caller; otherwise the argument is
  required and `set_category_status` raises `InvalidRecordValueError` when it
  would have to invent one.
- Whichever branch is chosen, the `ON CONFLICT (run_id, category) DO UPDATE`
  branch must **not** overwrite an already-scored row's `computed_at_utc` with
  `NULL`. Exclude `computed_at_utc` from `assignments` when the supplied value is
  `None`, so a finalization write by Chunks 8/9/10 is preserved.
- Record the decision in the plan's §12 Q3 entry as a *clarification of an
  existing closed decision* (the frozen record's non-optional field), not as a
  new open question. Do not contradict §12's "not to be re-opened" language and
  do not introduce a new `category_status` column or enum (Q2 stands).

Files: `src/niche_scout/database.py` only.
Risk: this is the one place where a wrong call propagates into Chunks 4B, 6A, 6B,
and 10, all of which write discovery-phase `category_scores` rows.

## Step 2 — Write `tests/test_database.py` (implementer)

Follow `Documents/plans/chunk-02-...md` §9.1–§9.4 literally; do not invent tests
or markers beyond the table.

- One `tmp_path` database per test, plus the recommended autouse guard asserting
  the path is under the pytest temp base. No repo-relative `runtime/*.sqlite3`.
- Fixtures, exactly the §9.3 set, defined inside `tests/test_database.py`
  (no new fixture module): `run_record`, `raw_observation_factory`,
  `sample_member_factory`, `enrichment_factory`, `category_score_factory`,
  `two_categories` (reuse `tests/fixtures/config_fixtures.py::DEFAULT_CATEGORIES`),
  `credential_shaped_text`.
- The 23 base node IDs and their marker sets exactly as listed in §9.4, including
  the two non-obvious mappings the plan justifies in its notes:
  `test_repository_never_persists_or_leaks_secrets` carries
  `LREQ-SEC-020, LREQ-NFR-060`, and
  `test_at_most_one_enrichment_row_per_run_and_identity` carries
  `LREQ-GQL-080, LREQ-TST-030`. Do **not** attach `LREQ-TST-040` or
  `LREQ-TST-020` anywhere — §12 Q6 forbids those fabricated mappings.
- Assertion content must map to the §10 gate bullets: duplicate sample membership
  rejected (by the primary key, not by a pre-`SELECT`), `(run_id, category)`
  enforced, secrets absent from every TEXT column and from every exception
  message, and a failed category leaving sibling categories' committed rows
  intact.
- Add one assertion pinning Step 1's resolution: a discovery-only
  `set_category_status` row either carries the caller-supplied `computed_at_utc`
  or raises, and reading it back never yields a record with a `None` timestamp.
- `test_no_alias_columns_and_no_import_time_ddl`: assert the persisted
  `category_scores` column set equals `TABLE_COLUMNS["category_scores"]` exactly,
  and that importing `niche_scout.database` opens no file and executes no SQL.

Files: `tests/test_database.py` (new) only. Do not touch `traceability.json` in
this step.

## Step 3 — Append traceability entries (implementer)

- Add 23 node→LREQ keys to `tests/traceability.json`, values equal to the marker
  sets exactly (the validator fails on any mismatch).
- Do not reword, reorder, or delete the 23 existing `test_contracts.py` entries.
- Every value array must contain only `LREQ-*` strings inside SRS Appendix B
  ranges.

Files: `tests/traceability.json` only.

## Step 4 — Run the gates and quote real output (implementer)

Run all four and paste the actual output, not a summary:

- `python -m pytest tests/test_database.py`
- `python -m pytest`
- `python -m niche_scout.tools.check_import_boundaries`
- `python -m niche_scout.tools.validate_traceability`

All must exit 0. `validate_traceability` also catches the marker/entry mismatch
direction for free (Step 2's "correction 1"); quote its `Traceability valid:`
line.

## Step 5 — §10 manual cross-check (implementer)

Walk §3's LREQ table (17 IDs) against the actual `@pytest.mark.lreq` markers in
`tests/test_database.py` and the new `tests/traceability.json` keys. Report the
result as a literal checklist — every §3 LREQ ID with at least one mapped marker
and one entry — because the validator's completeness check still covers Chunk 0
only (§12 Q3(c)). This is the deliverable that closes the gate, not the exit code.

## Step 6 — Hand off to the gate-verifier

Dispatch the gate-verifier only after Steps 1–5 report complete, with the quoted
command output and the §10 cross-check table as evidence. Per the auto-chaining
rule, stop immediately if the verifier reports any §10 bullet as FAIL.

## Dispatch shape (budget)

Three implementer dispatches, not two:

- **A** = Step 1 (small, self-contained; keeps the Q3 reasoning visible instead of
  burying it in a test-writing dispatch).
- **B** = Step 2 (the 23-node module is at the upper end of one dispatch's
  envelope; §9.3 alone specifies seven fixtures).
- **C** = Steps 3–5 (23 JSON keys, four command runs, one manual cross-check).

Collapsing B and C re-creates the step-limit failures already observed three
times. Collapsing A into B hides the one genuine scope judgment.

## Explicitly out of scope

- Widening `src/niche_scout/tools/validate_traceability.py` (deferred to Chunk 13
  by §12 Q3(b); the tool is not in §6).
- Any change to `models.py`, `config.py`, `pyproject.toml`, the DDL constants,
  `SCHEMA_VERSION`, the `Repository` protocol, or the five record dataclasses.
- Any new table, column, `ALTER TABLE`, index, or enum (Q2 and §11).
- Any chunk-crossing behavior: sampling materialization (4B), preflight gating
  (6A), enrichment dedup/reuse (6B), orchestration policy (10), report rendering
  (11), collector streaming/redaction (3).
- Publishing `Documents/interfaces/chunk-02.md` — that is the gate-verifier's
  output, not the implementer's.

## Verification / definition of done

- `database.py` no longer contains `computed_at_utc` in
  `_IMPLICIT_NOT_NULL_DEFAULTS`, and no `category_scores` read path can produce a
  record with a `None` timestamp.
- `tests/test_database.py` exists with exactly the 23 §9.4 node IDs and their
  exact marker sets.
- `tests/traceability.json` has 46 entries, the original 23 untouched.
- All four gate commands exit 0 with quoted output.
- The §10 manual cross-check table shows every §3 LREQ mapped.
- Gate-verifier dispatched only after the above, and the chain halts on any FAIL.
