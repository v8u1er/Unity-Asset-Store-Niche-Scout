# Chunk 22 — run log

Labeled post-completion remediation (Chunks 14–21 pattern) that was initially
BLOCKED on human input. The operator supplied an authorized live Coveo Search v2
`ec_category` facet capture and the ruling set in §0 of the dispatch, which
clears the four Stage 1 open questions recorded in the original blocked log.
Scope: raise the discovery cap off 2000, expand the comparison set to the 24
operator-named categories, regenerate the three `config/` files from the new
capture, and record the run policy. `chunk-22` is a labeled remediation: no
`requirements-dependency-map.md` §3/§4 gate row and no downstream chunk.

## Stage 0 — Preflight (resolved)

- Working tree at `f687a84` ("chunk-21: gate passed") on `main`; `Documents/runs/chunk-22.md`
  was the only untracked file.
- Original environmental blocker (lead `bash` denied) no longer applies: the lead
  ran `git status`, `git log`, `git rev-parse`, `python -m pytest`,
  the four `niche_scout.tools` validators, and `ruff` this run.
- Work performed on branch `chunk-22`.

## Stage 1 — Capture validation (report; abort on failure)

Capture artifact: `.scratch/chunk22-ec_category-capture.json` (operator-run,
authorized; the response body supplied with the dispatch). Validation query:
`python .scratch/chunk22-build-config.py` read the file, asserted the facet
structure, and enumerated `facets[0].values`.

- Exactly one facet, `facetId == "ec_category"`, `field == "ec_category"`. ✔
- `moreValuesAvailable == false`. ✔
- Every entry carries exactly `{value, state, numberOfResults}`. ✔
- Counts (enumerated by the script, printed to stdout): **total = 128**,
  **single-segment = 7**, **multi-segment = 121**. Matches the committed baseline
  (7 single-segment tops + 121 multi-segment). No stop condition triggered.
- Single-segment tops confirmed as the exact set
  `{2d, 3d, add-ons, audio, templates, tools, vfx}`. ✔

## Stage 2 — Canonical inventory and requested categories

- `config/category_taxonomy.json`: `canonical_category_paths` =
  `sorted({normalize_category_path(v) for v in multi-segment values})`, using the
  imported `niche_scout.validation.normalize_category_path` (not reimplemented).
  121 entries, deduplicated, ascending, canonical `/` form, no single-segment
  entry.
- `config/categories.json`: the exact 24-path ordered list of dispatch §3.3
  (16 3d character/environment/prop/vehicle paths, 4 2d, 4 vfx; audio excluded).
  Every path has ≥3 segments, is in the inventory, and its immediate parent is in
  the inventory. Count = 24 (≥ the Chunk 22 target of ≥21).

## Stage 3 — Config regeneration and hash

All three files carry `captured_at_utc = 2026-09-27T06:43:41Z`, `schema_version
"1.0.0"`. `source_url` is `https://assetstore.unity.com/categories` for
`categories.json`/`category_taxonomy.json` and `https://assetstore.unity.com/`
(kept from the committed file) for the template. `organization_id` =
`unitytechnologiesproductionmkahteav`; `endpoint` =
`https://unitytechnologiesproductionmkahteav.org.coveo.com/rest/search/v2`.

- `config/coveo_search_template.json`: committed `request_body` shape replayed
  with only the `ec_category` facet changed. `currentValues` = the 24 §3.3 paths
  in order, each `{"value": <path>, "state": "idle"}`. `numberOfValues` kept at
  150; `fieldsToInclude` = the 5-field discovery set; no `sortCriteria`; no
  `q`/`query`. Capture `values` → template `currentValues`, keeping `value` and
  `state` only (`numberOfResults` dropped from the template; counts retained only
  in this record).
- `template_sha256 = 9dee9a6cd88cd679fff342a4978661dfc59da91fa6435dab95afa1c187c641ed`
  (SHA-256 over `json.dumps(request_body, sort_keys=True, separators=(",", ":"),
  ensure_ascii=False)`), set in both the template header and
  `category_taxonomy.json`.

## Stage 4 — Cap change and ripple

- `config/default.toml`: `max_discovery_results_per_category = 9000`.
- `src/niche_scout/models.py`: `MAX_DISCOVERY_RESULTS_PER_CATEGORY = 9000`.
- `tests/test_contracts.py`: SRS-defaults map `MAX_DISCOVERY_RESULTS_PER_CATEGORY`
  2000 → 9000; the `test_coveo_endpoint_contract` literal 2000 → 9000.
- `tests/fixtures/config_fixtures.py`: `DEFAULT_CATEGORIES` → the 24 committed
  categories in ascending lexical order (fixture-local order preserved so the
  `get_category_scores` lexical-order assertion in `test_database.py` holds);
  `DEFAULT_TOML_BODY` and `DEFAULT_TOML_VALUES` cap 2000 → 9000.
- `tests/fixtures/coveo_discovery.py`: `COVEO_FIXTURE_CATEGORY` stays
  `3d/characters/humanoids`; `COVEO_FIXTURE_CATEGORY_OTHER` stays
  `vfx/particles/fire-explosions` (both are members of the 24);
  `CAPTURED_STATE_BY_CATEGORY` auto-derives from the regenerated template.
- Stale-prose updates in `tests/fixtures/cli_fixtures.py`, `tests/fixtures/pipeline_fixtures.py`,
  and `tests/test_cli.py` describing the former `2000` default / "eight" category set.
- `tests/traceability.json` unchanged (no pytest node IDs changed).
- No `Documents/`, `AGENTS.md`, `kilo.json(c)`, `.kilo/`, or frozen interface file
  was edited.

### Ruling — SRS §14 default revision: `MAX_DISCOVERY_RESULTS_PER_CATEGORY`

Old default **2000** → new default **9000** (SRS §14 row
`MAX_DISCOVERY_RESULTS_PER_CATEGORY`, Configurable `Yes`). Grounded
justification: the largest selected category, `3d/characters/humanoids`, carries
**8272** assets in the authorized capture (`numberOfResults` 8272), which
truncates under the old 2000 cap. 9000 exceeds every selected category's captured
population.

### Ruling — `QUALITY_MIN_ELIGIBLE_ASSETS`

Left at **5** (no constant/default change): `src/niche_scout/models.py:62` and
`config/default.toml:26` stay at 5. The dispatch's §0 ruling is "leave at 5".

## Stage 5 — Verification (real output)

| Command | Result |
|---|---|
| `python -m pytest -q` | **664 passed, 0 failed** in 22.79s |
| `python -m niche_scout.tools.validate_traceability` | valid: 89 required/defined LREQ IDs mapped, 645 matrix nodes, 0 unmarked analytical tests outside exemption (3 exempted) |
| `python -m niche_scout.tools.check_import_boundaries` | valid for `metrics.py`, `scoring.py` |
| `python -m niche_scout.tools.check_scope_prohibitions` | valid: no retired token (6 tokens checked) |
| `python -m niche_scout.tools.check_secrets` | valid: no literal credential under src/tests/config/pyproject; no tracked `.env` |
| `python .scratch/chunk22-verify-config.py` | all independent checks passed (see below) |

Independent checks (reported explicitly):

- Recompute the hash from the written `request_body` and compare: written
  `9dee9a6…c641ed` == recomputed. ✔
- `config/categories.json` list == template facet `currentValues` values, order
  and strings, byte-for-byte (both equal the §3.3 list). ✔
- Inventory 121 long, deduplicated, sorted, canonical `/` form, and contains no
  single-segment entry. ✔
- Every one of the 24 requested paths and its immediate parent
  (`path.rsplit("/", 1)[0]`) is in the inventory. ✔
- `load_coveo_search_template()` on the written template did not raise. ✔
- Capture instant `2026-09-27T06:43:41Z` age at verification
  `0.028014` days ≤ `MAX_TAXONOMY_AGE_DAYS` (30). ✔

### Ruff

`ruff format --check` and `ruff check` are not clean repo-wide at baseline
(pre-existing debt, carried by every chunk since Chunk 8). Changed-file
comparison against byte-exact `git show HEAD:` copies in `.scratch/head/`:
worktree **12** `check` errors vs HEAD **13** (all 11 remaining `E501`s are in
`test_contracts.py` lines untouched by this chunk; the single `I001` is the
pre-existing blank-line import grouping). Format: **3** changed files would be
reformatted at both HEAD and worktree — unchanged. No new lint or format debt
introduced; no unrelated reflow performed.

## Open questions

All four original Stage 1 questions are resolved by the dispatch §0 rulings and
the supplied capture. None remain.

## Deviations

- The SRS §14 default for `MAX_DISCOVERY_RESULTS_PER_CATEGORY` is revised in
  `config/default.toml` and `src/niche_scout/models.py` per the operator ruling;
  the frozen SRS text itself was not edited.
- `COVEO_FIXTURE_CATEGORY_OTHER` remained `vfx/particles/fire-explosions`, which
  is already a member of the 24-path set; only its comment was updated.