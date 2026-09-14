# Complete Chunk 0 contracts

Goal: Bring Chunk 0 (project skeleton and contracts) into conformance with `Documents/requirements-dependency-map.md:378-441` and the normative contracts in `Documents/SRS-lean.md`.

1. Implement typed domain contracts in `src/niche_scout/models.py`.
   - Add policy/version constants and timezone-aware UTC serialization helpers as required by the SRS.
   - Define enums/literal-backed statuses for `RunStatus`, discovery, identity resolution, category-filter validation, operation, score, evidence, rankability, warning codes, GraphQL correlation mode, page-view semantic status, and related required states.
   - Add typed structures for the mandatory logical rows: `runs`, `raw_discovery_observations`, `sample_members`, `enrichment_observations`, and `category_scores`, preserving nullable/unavailable values instead of using zero sentinels.
   - Add deterministic serialization/deserialization contracts and explicit `scoring_cutoff_utc` fields/inputs where applicable.

2. Implement configuration contracts in `src/niche_scout/config.py`.
   - Define typed configuration structures for category selection, endpoint/pagination/sampling policies, paths, policy versions, and credentials.
   - Define and validate precedence between explicit configuration, environment variables, and defaults without exposing credential values.
   - Require the Coveo and Unity CSRF environment credentials before collection, while keeping pure contract validation independent of network I/O.
   - Use `pathlib` paths and represent missing/invalid values explicitly.

3. Define the persistence/schema protocol in `src/niche_scout/database.py` without implementing SQLite behavior.
   - Add a schema specification containing every mandatory field and logical key from SRS §6, including `(run_id, category, asset_identity_key)` sample uniqueness and `(run_id, category)` score uniqueness.
   - Add typed repository protocols for run/category status, streamed raw observations, sample members, enrichment observations, and category scores.
   - Keep SQLite connections, DDL execution, transactions, and physical persistence out of Chunk 0; those belong to Chunk 2.

4. Strengthen pure-module contracts in `src/niche_scout/metrics.py` and `src/niche_scout/scoring.py`.
   - Replace placeholders with typed public input/output contract structures or frozen interfaces sufficient for later chunks.
   - Ensure `scoring_cutoff_utc` is always an explicit timezone-aware UTC input.
   - Add public type hints and docstrings describing null, invalid, zero, unavailable, and boundary behavior, while leaving actual metric/scoring behavior for later chunks.
   - Preserve the no-I/O/no-clock/no-collector/database/report/CLI dependency boundary.

5. Add required project/configuration artifacts.
   - Create `README.md` documenting the lean sample-based scope without sales/revenue claims and identifying the Chunk 0 contract boundaries.
   - Create `config/default.toml`, `config/categories.json`, and a schema-valid `config/category_taxonomy.json` fixture with required taxonomy metadata fields.
   - Create `.env.example` containing variable names/placeholders only, and `.gitignore` explicitly ignoring `.env` and local runtime/database artifacts.
   - Keep all paths cross-platform and avoid credentials in fixtures or documentation.

6. Correct traceability representation and validation.
   - Update `tests/traceability.json` to the required test-node-keyed format, e.g. `tests/test_x.py::test_y` mapped to arrays of individual `LREQ-*` IDs; do not retain the current inverse LREQ-keyed format.
   - Update `tools/validate_traceability.py` and `src/niche_scout/tools/validate_traceability.py` as needed so validation checks both directions: every referenced LREQ exists, every analytical test has a marker and matrix entry, every required LREQ has at least one mapping, and no retired/unknown requirement is referenced. Parameterized tests must use base node IDs.
   - Add fixture/test conventions under `tests/fixtures/` and contract tests for traceability, package imports, status values, serialization, and configuration precedence. Mark analytical tests with `@pytest.mark.lreq(...)`.

7. Verify the Chunk 0 gates.
   - Run package import checks for `niche_scout` and its contract modules.
   - Run the import-boundary validator and traceability validator.
   - Run formatting/linting and the test suite.
   - Confirm `metrics.py`/`scoring.py` contain no forbidden imports, clock access, or I/O; all mandatory row fields and status values are represented; the repository layer does not require SQLite; `.env` is ignored; `.env.example` has no credentials; and every required Chunk 0 analytical test is bidirectionally traceable.

Risks and notes:
- The current traceability JSON and validator are internally consistent but contradict the documented test-node-keyed contract; convert them together before adding more tests.
- `models.py`, `config.py`, `database.py`, `metrics.py`, and `scoring.py` are placeholders, so later chunks should not be implemented against them until these interfaces are frozen.
- Chunk 0 must not add network behavior, physical SQLite implementation, scheduled execution, resume/checkpoint support, or sales/revenue prediction.
