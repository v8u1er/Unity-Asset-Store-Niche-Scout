# Chunk 2 test_database.py first slice (repository/schema group)

# Chunk 2 — `tests/test_database.py`, first slice (repository/schema group)

Goal: create `tests/test_database.py` with exactly the six repository/schema-group
tests from the frozen plan's §9.4 table, plus the autouse `tmp_path` guard and the
`run_record` fixture only. Nothing else.

## Blocking finding (must be reported)

`Documents/plans/chunk-02-...md` §9.4 assigns markers to all 23 planned nodes, and
`tests/traceability.json` cannot be modified in this dispatch. Therefore every one of
the six new tests WILL trip `validate_traceability`'s "markers but no matrix entry"
check. The dispatch message pre-authorises this ("expected to be red on
`missing_nodes`"). Two additional pre-existing red items in the working tree are NOT
ours and must be reported, not fixed:

- `tests/test_contracts.py::test_repository_protocol_and_schema_specification` fails at
  line 938 (`assert "sqlite3" not in database.py`). That artifact was already invalidated
  by the earlier Chunk 2 implementer pass, and `test_contracts.py` is on the do-not-touch
  list for this dispatch (it is also on the Chunk 1 file list, not Chunk 2's).
- 11 `tests/test_validation.py` / `tests/test_identity.py` failures (Chunk 1 territory).

## Files

- `tests/test_database.py` — new (the only file touched).
- `tests/traceability.json` — deliberately NOT touched (next dispatch).

## Steps

1. Create `tests/test_database.py` with:
   - module docstring; `from __future__ import annotations`
   - imports: `ast`, `datetime`, `Path`, `pytest`, `fixtures.config_fixtures as
     fixtures`, `sqlite3`, and the `niche_scout.database` names
     (`CREATE_TABLE_STATEMENTS`, `DDL_STATEMENTS`, `SCHEMA_VERSION`, `TABLE_COLUMNS`,
     `TABLE_PRIMARY_KEYS`, `SqliteRepository`, plus the enum sources from
     `niche_scout.models` used for the allowed-value assertions)
   - module constants `ROOT`, `PACKAGE`, `DATABASE_PATH`, and a `_TABLE_ENUM_COLUMNS`
     mapping derived from `models` enums so the enum test asserts observed allow-lists
   - `_iso(hour)` helper and the `run_record` fixture (ported from
     `tests/test_contracts.py::_run_record`)
   - the autouse guard fixture `_database_paths_stay_under_pytest_temp_base` that
     (a) asserts the pytest temp base exists and is not under the repo root,
     (b) asserts a plain `Path(tmp_path)` really does resolve under it,
     (c) monkeypatches `SqliteRepository.__init__` so EVERY construction call is
     captured and must resolve under the temp base.
   - six test functions, exact names and exact markers per §9.4:
     | node | marker(s) |
     |---|---|
     | `test_schema_initialization_is_versioned_and_idempotent` | `LREQ-SEC-020` |
     | `test_no_alias_columns_and_no_import_time_ddl` | `LREQ-TST-080` |
     | `test_foreign_key_and_pragma_contracts_are_enforced` | `LREQ-SEC-020`, `LREQ-GQL-080` |
     | `test_insert_versus_upsert_semantics_per_table` | `LREQ-SMP-080`, `LREQ-GQL-080`, `LREQ-SEC-020` |
     | `test_enum_backed_columns_reject_unknown_values` | `LREQ-SEC-020`, `LREQ-ID-040` |
     | `test_json_and_utc_round_trip_for_all_record_types` | `LREQ-TST-080` |
2. Assert only against observed `database.py` behavior (repository opened at
   `tmp_path / "niche_scout.sqlite3"`; DDL applied through `_idempotent`;
   `schema_metadata` metastore; pragmas `foreign_keys=1`, `journal_mode=wal`,
   `busy_timeout=5000`, `synchronous=NORMAL`; `NO` row-factory, so rows are tuples and
   index access is required).
3. Run `python -m pytest tests/test_database.py -q` and
   `python -m pytest tests/test_database.py -q --collect-only`, and `git status --short`.
4. Do not run `validate_traceability`.

## Risks / notes

- The `sqlite3` import in the test module is what makes the import-time-DDL probe
  possible (`sqlite3.connect` monkeypatch). It does not touch a production module.
- The round-trip test is written to read back EVERY `TABLE_COLUMNS["runs"]` column and
  compare against the inserted `RunRecord`, which already exercises §8.2's
  "UTC datetime TEXT round-trip" for both the NULL and non-NULL timestamp columns. It
  deliberately does not assert equality of the four non-`RunRecord` row types, because
  `_project_row` reconstructs only a subset of columns there
  (`category_scores.ranking_sensitivity_json` / `computed_at_utc` are excluded) — that
  gap is reported, not papered over.
