# Chunk 14 — Live endpoint compatibility (post-Chunk-13 remediation)

Status: FROZEN
Depends on (frozen interfaces required before this plan can be trusted):
  - `Documents/interfaces/chunk-01.md` §2–§4 (taxonomy validation primitives,
    `normalize_category_path`, `taxonomy_path_set`, `match_exact_category`,
    `TaxonomyValidationResult`, `CategoryMatchResult`) — signatures unchanged.
  - `Documents/interfaces/chunk-03.md` §4/§6 (Coveo template capture,
    `load_coveo_search_template`, `build_coveo_request_body`) — signature
    unchanged; §6 "Request construction" gains one documented divergence (this plan).
  - `Documents/interfaces/chunk-00.md` §5/§9 (config paths, `DEFAULT_CATEGORIES`
    fixture contract cited by `tests/fixtures/validation_fixtures.py`).
  - `Documents/interfaces/chunk-02.md` §3 (page sink) — consumed unchanged.
Blocks (chunks whose plan/implementation needs this chunk's interface):
  - None. This is a remediation after Chunk 13; it introduces no new interface
    file and no downstream contract. No chunk starts on it.

## 1. Goal

Make the committed configuration and the pure category-membership logic agree
with the **live** Unity/Coveo contract, so that a human `niche-scout run` against
the real endpoint can traverse discovery and reach the identity preflight instead
of aborting on taxonomy validation or resolving every record to
`category_mismatch`. A live probe against the real endpoint (human-run, this
session) showed three independent blockers: an invalid replayed `sortCriteria`,
a taxonomy file that fails structure/freshness/requested-presence validation,
and an inbound `" > "`-separated, leading-space, lowercase facet/record
vocabulary that the `/`-only normalizer cannot match. This chunk fixes those
three with SRS-anchored changes only, adds a request-body guard so an unfiltered
request can never silently run, and freezes the new separator/casing convention
in tests and fixtures.

## 2. Scope

### In scope
- `normalize_category_path` accepts the live `" > "` separator and normalizes it
  to the canonical `/` form; `_canonical_path_shape_preserved` tokenizes both
  `" > "` and `/` so a live-form inventory entry is not misreported as repaired.
  (LREQ-EXT-080, LREQ-EXT-020)
- Regenerate `config/coveo_search_template.json`: drop the invalid `sortCriteria`
  member; set the `ec_category` facet `currentValues` to the 8 committed
  categories (idle, `numberOfValues: 150`); recompute `template_sha256` over the
  edited body. (LREQ-EXT-010, LREQ-EXT-050)
- Regenerate `config/categories.json` and `config/category_taxonomy.json` so the
  cached taxonomy carries every required header, is fresh, contains the full live
  multi-segment inventory, and includes every requested category and its parent.
  (LREQ-EXT-020)
- Add a `build_coveo_request_body` guard: raise `ValueError` when no template
  `currentValue` equals the requested `category`, so a filter/config mismatch can
  never silently issue an unfiltered request. Public signature unchanged.
  (LREQ-EXT-010)
- Preferver the live vocabulary in fixtures/tests: lowercase slugs, `" > "`
  separator, leading-space child record values, slash-form round-trip; update
  `tests/traceability.json`. (LREQ-EXT-060, LREQ-EXT-080, LREQ-EXT-090,
  LREQ-ARCH-030)
- Record the new separator/casing convention and the sortCriteria removal,
  including the pagination-stability tradeoff, in this plan and the run log.

### Explicitly out of scope (and who owns it instead)
- **Identity preflight/session (OI-6).** No GraphQL, CSRF, cookie, or session
  changes. A run that fails only at the identity preflight is the documented
  OI-6 limitation, not a new defect. Owner: unassigned (dependency-map §7).
- **Capture tooling.** No automated taxonomy/facet capture is built; the manual
  capture procedure is recorded as an open item (Q7). Owner: human operator.
- **Pipeline/CLI behavior.** No edits to `pipeline.py` or `cli.py` (Q10). The
  freshness window and abort logic already exist; this chunk only makes the
  committed data valid for them.
- **Scoring, sampling, metrics, report.** No formula, weight, threshold, or
  output changes. This chunk is a collection/validation-integration remediation;
  LREQ-ARCH-030 is a supporting determinism guard only, not a scoring change.
- **Real function/field-name conventions not evidenced by the live probe.**
  The SRS defines neither a path separator nor a casing rule; the conventions
  here are new and are documented and traceable, not asserted as SRS-defined.

## 3. Requirements this chunk must satisfy

| LREQ ID | Ownership role here | Normative text (from SRS-lean.md, quoted/derived) | SRS section |
|---|---|---|---|
| LREQ-EXT-010 | Supporting contract (Chunk 3 remains primary) | "Discovery SHALL use the parent SRS Coveo endpoint, required headers, captured taxonomy template, and selected-category facet mechanism." The committed template must be a replayable capture and the facet mechanism must select exactly the requested category; the guard enforces the facet-selection half. | §4.1 (line 243) |
| LREQ-EXT-020 | Primary (this remediation) | "The cached taxonomy file SHALL include `schema_version`, `captured_at_utc`, `source_url`, `template_sha256`, and a canonical category-path inventory. The system SHALL abort before collection if the file is missing, malformed, stale, or does not contain every requested category." | §4.1 (line 246) |
| LREQ-EXT-050 | Supporting/integration (Chunk 3 remains primary) | "For every requested category, discovery SHALL retrieve all available pages using the same endpoint, filters, sort order, page size, pagination rules, and category predicate. It SHALL stop when the verified `totalCount` is reached, the endpoint returns a natural terminal page, or `MAX_DISCOVERY_RESULTS_PER_CATEGORY` is reached. The discovery status SHALL be one of `complete`, `truncated`, `page_failed`, `filter_unverified`, `category_mismatch`, `identity_incomplete`, or `request_failed`; a failed or truncated page SHALL never be interpreted as zero assets." Removing the rejected explicit sort leaves one engine-default sort order shared by every category; pagination stability is not claimed verified. | §4.1 (line 259) |
| LREQ-EXT-060 | Supporting contract (no behavior change) | "Each discovery record SHALL retain all non-empty identity candidates from `ec_product_id`, `permanentid`, response-level `clickUri`, and response-level `uri`. Candidates SHALL be canonicalized under one versioned mapping rule." Category normalization must not disturb identity candidates; the live multi-valued `ec_category` shape must not be read as identity. Extraction-half verification stays deferred (open obligation). | §4.1 (line 265) |
| LREQ-EXT-080 | Primary (this remediation) | "Exact category membership SHALL be checked against the canonical taxonomy. Parent paths SHALL NOT match child paths merely by prefix. Scalar and multi-valued category response shapes SHALL be handled explicitly." The `" > "` separator and leading-space multi-valued record values are the live shapes that must be handled explicitly. | §4.1 (line 275) |
| LREQ-EXT-090 | Supporting (Chunk 3/10 remain primary) | "A failed page, unverified filter, category mismatch, or material identity incompleteness SHALL generate a warning and SHALL prevent a fully rankable competition result for that category." The fix prevents a false `category_mismatch`; a genuinely absent value must still yield `category_mismatch` and its warning. | §4.1 (line 279) |
| LREQ-ARCH-030 | Supporting (Chunk 10 remains primary) | "The same normalized input data, policy versions, and configuration SHALL produce the same metric, score, evidence, and sensitivity outputs." Normalization/matching is a pure deterministic function of its inputs; repeated calls must be equivalent, with no ordering dependence. | §3 (line 234) |

## 4. Interface contracts consumed

Copied from the frozen interface files (not re-derived from source):

- `interfaces/chunk-01.md` §4: `normalize_category_path(value: str) -> str`,
  `taxonomy_path_set(payload: object) -> frozenset[str]`,
  `match_exact_category(category_value: object, taxonomy_paths: Container[str]) -> CategoryMatchResult`.
- `interfaces/chunk-01.md` §3: `CategoryMatchResult.matched_path: str | None`,
  `.status: CategoryFilterValidationStatus`, `.matched_value_count: int`,
  `.unmatched_values: tuple[str, ...]`, `.issues: tuple[ValidationIssue, ...]`;
  `TaxonomyValidationResult.status` vocabulary
  `"valid" | "missing_headers" | "malformed" | "stale" | "missing_categories" | "invalid_capture_timestamp"`.
- `interfaces/chunk-03.md` §4: `build_coveo_request_body(template: Mapping[str, object], category: str, *, page_index: int, page_size: int = PAGE_SIZE) -> dict[str, object]`;
  `load_coveo_search_template(template_path: "Path | str" = COVEO_TEMPLATE_PATH) -> Mapping[str, object]`.
- `interfaces/chunk-02.md` §3: `insert_raw_discovery_observations(page_observations)` page-sink contract (unchanged).
- `interfaces/chunk-00.md` §5/§9: `DEFAULT_CATEGORIES_PATH`, `DEFAULT_TAXONOMY_PATH`
  and the fixture contract that `tests/fixtures/config_fixtures.py` /
  `validation_fixtures.py` consume `DEFAULT_CATEGORIES` and `TAXONOMY_FIXTURE`
  read-only.

**Signature-freeze facts (verified by reading, this session).**
- `tests/test_collector.py:357-366` asserts `inspect.signature(build_coveo_request_body)`
  parameters are exactly `["template", "category", "page_index", "page_size"]`,
  with `page_index` keyword-only and `page_size` defaulting to `PAGE_SIZE`. The
  Q3 guard MUST NOT change this signature.
- `tests/test_collector.py:418` asserts the request facet's `numberOfValues == 150`.
- `tests/test_collector.py:419-425` asserts the facet `currentValues` order equals
  `CAPTURED_STATE_BY_CATEGORY` (derived from the template) and that exactly the
  requested `CATEGORY` is `"selected"`.

## 5. Interface contract this chunk produces

**None.** This is a labeled post-Chunk-13 remediation, not a dependency-map chunk.
No new `interfaces/chunk-14.md` is created; no downstream chunk consumes a new
surface from it. The public signatures in §4 are unchanged.

Two behavioral records replace interface-document state without rewriting the
frozen interface files:
- `build_coveo_request_body` raises `ValueError` when the template carries no
  `currentValue` equal to `category` (new failure mode; same signature).
- The committed capture's body no longer carries `sortCriteria`; the replay list
  `_COVEO_REPLAYED_TEMPLATE_FIELDS` still names `"sortCriteria"` so a future
  capture carrying a valid sort replays it. This is recorded here and in the run
  log; `interfaces/chunk-03.md` §6 is not edited by this chunk.

## 6. Files touched

| File | New/modified | Purpose |
|---|---|---|
| `src/niche_scout/validation.py` | modified | Q1: `normalize_category_path` maps `" > "` → `/`; `_canonical_path_shape_preserved` tokenizes `" > "` and `/`. No other function changes; module stays pure (no clock/I/O/network). |
| `src/niche_scout/collector_coveo.py` | modified | Q3: `matched_selected == 0` guard in `build_coveo_request_body`; signature unchanged. `_COVEO_REPLAYED_TEMPLATE_FIELDS` unchanged (keeps `"sortCriteria"`). |
| `config/coveo_search_template.json` | modified | Regenerate: drop `sortCriteria`; facet `currentValues` = 8 Q4 categories (idle, `numberOfValues: 150`); recompute `template_sha256`. |
| `config/categories.json` | modified | Regenerate: `schema_version`, Q9 `captured_at_utc`, `source_url`, the 8 Q4 categories byte-for-byte. |
| `config/category_taxonomy.json` | modified | Regenerate: `schema_version`, Q9 `captured_at_utc`, `source_url`, Q6 `template_sha256`, 121-entry `canonical_category_paths`, no `categories` records. |
| `tests/fixtures/config_fixtures.py` | modified | `DEFAULT_CATEGORIES` = the 8 Q4 categories (matches `config/categories.json`). `TAXONOMY_FIXTURE` derives from it (existing shape). |
| `tests/fixtures/coveo_discovery.py` | modified | `COVEO_FIXTURE_CATEGORY` / `COVEO_FIXTURE_CATEGORY_OTHER` become two of the 8 Q4 categories; add live-form vocabulary helpers. |
| `tests/fixtures/validation_fixtures.py` | modified | Re-point `ONE_ABSENT_CATEGORY`'s appended path to a no-casefold-match sentinel (`audio/music/dnb`), per the dispatch precaution. |
| `tests/test_validation.py` | modified | Update the two literal assertions (lines 342 and 344) to the new absent sentinel. Node IDs unchanged. |
| `tests/test_live_endpoint_compatibility.py` | new | New LREQ-marked analytical tests for normalization/membership/guard/config consistency (see §9). |
| `tests/traceability.json` | modified | Add node→`[LREQ ids]` entries for every new test node. |
| `tests/fixtures/pipeline_fixtures.py` | audited, expected unmodified | Synthetic category sets run through `write_run_local_template` + `request_body_for_category(..., template_path=...)`; `EXPECTED_TAXONOMY_SHA256` is derived from `compliant_category_paths()`. Change only if a real assertion breaks; a break is reported, not silently patched. |
| `tests/fixtures/identity_preflight_vectors.py` | audited, expected unmodified | Config paths are inert ("never opened"); category literals are GraphQL-side values, not Coveo template values. |
| `tests/fixtures/graphql_fixtures.py` | audited, expected unmodified | `"Tools/Level Design/Tilemap"` is a GraphQL category literal, not a Coveo template value. |

**Not touched:** `pipeline.py`, `cli.py`, `database.py`, `report.py`, `metrics.py`,
`scoring.py`, `models.py`, `Documents/SRS-lean.md`, `AGENTS.md`, `kilo.json(c)`,
`.kilo/`, any `Documents/interfaces/*` file.

## 7. Task breakdown

- [ ] Q1a — In `validation.py`, change `normalize_category_path` to replace the
  live `" > "` separator with `/` before splitting, then trim segments and drop
  empties; output remains canonical `/`, case preserved; non-string still raises
  `TypeError`. (LREQ-EXT-080)
- [ ] Q1b — In `validation.py`, change `_canonical_path_shape_preserved` to
  tokenize raw input on both `" > "` and `/` (without dropping empties) before
  comparing segment counts against the normalized form. (LREQ-EXT-020, LREQ-EXT-080)
- [ ] Q1c — Verify no other sibling assumes `/`-only input: the only candidates
  are `validation.py:671` (Q1b) and `:1062-1063` (Q1a); lines 1278/1328/1626 are
  URI handling and out of scope. (LREQ-EXT-080)
- [ ] Q2 — Regenerate `config/coveo_search_template.json`: remove `sortCriteria`;
  facet `currentValues` = the 8 Q4 categories, each `state: "idle"`,
  `numberOfValues: 150`; recompute `template_sha256` (Q6) over
  `json.dumps(request_body, sort_keys=True, separators=(",",":"), ensure_ascii=False)`.
  (LREQ-EXT-010, LREQ-EXT-050)
- [ ] Q3 — Add the guard in `build_coveo_request_body`: when
  `matched_selected == 0`, raise `ValueError`; keep the public signature. (LREQ-EXT-010)
- [ ] Q4/Q5 — Regenerate `config/categories.json` with the 8 Q4 categories. (LREQ-EXT-020)
- [ ] Q6/Q8/Q9 — Regenerate `config/category_taxonomy.json`: headers, Q9 capture
  instant, Q6 hash, 121-entry inventory, no `categories` records. (LREQ-EXT-020)
- [ ] Q1 fixture — Update `config_fixtures.DEFAULT_CATEGORIES` to the 8 Q4
  categories (byte-equal to `config/categories.json`). (LREQ-EXT-020)
- [ ] Q1 fixture — Update `coveo_discovery.COVEO_FIXTURE_CATEGORY` and
  `COVEO_FIXTURE_CATEGORY_OTHER` to two of the 8 Q4 categories; recompute
  `CAPTURED_STATE_BY_CATEGORY`/`CAPTURE_BODY` (already derived). (LREQ-EXT-010)
- [ ] Q1 fixture — Re-point `validation_fixtures.ONE_ABSENT_CATEGORY` to a
  no-casefold-match sentinel and update the two literals in `test_validation.py`. (LREQ-EXT-020)
- [ ] Q6 tests — Add the new tests in `tests/test_live_endpoint_compatibility.py`
  and their `tests/traceability.json` entries (§9). (LREQ-EXT-080, LREQ-EXT-020,
  LREQ-EXT-010, LREQ-EXT-050, LREQ-EXT-060, LREQ-EXT-090, LREQ-ARCH-030)
- [ ] Q7 note — Record the manual capture procedure as an open item in §12; build
  no tooling. (LREQ-EXT-020)
- [ ] Run all four validators and the suite; report real counts. (all)

## 8. Edge cases and invariants

- **Live `" > "` separator.** `"2d > textures-materials > stone"` normalizes to
  `"2d/textures-materials/stone"`. Only the exact space-greater-space sequence is
  a separator; `"A>B"` (no spaces) is not split and remains one segment.
- **Leading-space child record values.** A multi-valued record
  `["3d", " 3d > characters", " 3d > characters > humanoids"]` normalizes each
  entry with whitespace trimmed per segment; all three become canonical paths.
- **`/`-only raw input unchanged.** `"A/B"`, `" Tools / Utilities / "`, and
  `"A//B"` normalize exactly as before (`"A/B"`, `"Tools/Utilities"`, `"A/B"`).
- **Empty/whitespace segments.** Empty segments are dropped from output; a
  whitespace-only value normalizes to `""`, which `_is_canonical_path_shape`
  rejects. `""` as a supplied category value is still `mismatch`, not
  `unverified` (existing LREQ-EXT-080 semantics).
- **Repair detection preserved.** `/Leading/Slash` and `Tools/` remain malformed
  inventory entries: `_canonical_path_shape_preserved` counts raw segments
  including empties, so normalization must not be able to "repair" them.
- **Case preserved vs casefold comparison.** `normalize_category_path` preserves
  case (output is canonical, case-preserving). `match_exact_category` compares
  `casefold`ed. `validate_requested_categories` compares **case-sensitively**
  (`normalized not in known`); this asymmetry is existing behavior and is pinned
  by a new test.
- **Parent-not-prefix.** `3d/characters` never matches `3d/characters/humanoids`
  and vice versa; parent paths are not prefix matches. Live multi-segment
  inventory excludes the 7 single-segment tops (Q5), so a top-level value can
  never satisfy a requested category.
- **Guard fires on no match.** A requested category absent from the template
  raises `ValueError` before the body is built. Duplicate equal currentValues do
  not trip the guard (`matched_selected >= 1`). The guard does not change
  `build_coveo_request_body`'s signature.
- **`numberOfValues: 150`.** The committed facet keeps `numberOfValues: 150` (the
  live capture's value, with `moreValuesAvailable: false` at 128 values returned)
  even though the requested `currentValues` are the 8 selected categories;
  `tests/test_collector.py:418` pins this.
- **8-category provisional run.** The 8 requested categories still satisfy
  `MIN_CATEGORIES_PER_RUN = 8`; a completed run with 8 categories remains
  provisional (empty `base_rankable_candidates`, null stability) per dependency-map
  §6.2. Unchanged by this chunk.
- **Determinism.** Normalization and matching depend only on their inputs; no
  clock, RNG, set/dict-ordering dependence. `config/category_taxonomy.json`
  freshness is judged by the caller's clock; the committed Q9 instant is fresh
  only within `max_taxonomy_age_days = 30` of the run, which is a documented
  limitation.

## 9. Test plan

- **New test module:** `tests/test_live_endpoint_compatibility.py`.
- **Fixtures:** `tests/fixtures/coveo_discovery.py` (live vocabulary helpers:
  `" > "`-joined, leading-space child values, slash round-trip),
  `tests/fixtures/config_fixtures.py` (8 Q4 `DEFAULT_CATEGORIES`),
  `tests/fixtures/validation_fixtures.py` (absent sentinel). No golden-vector
  file is needed; all expected values are hand-derived strings/sets and the
  recomputed template hash.
- **Exact markers and traceability entries** (each node must carry exactly these
  marker arguments and exactly matching `tests/traceability.json` values):

| pytest node ID | `@pytest.mark.lreq(...)` marker args | `tests/traceability.json` value |
|---|---|---|
| `tests/test_live_endpoint_compatibility.py::test_normalize_category_path_accepts_live_double_gt_separator` | `LREQ-EXT-080` | `["LREQ-EXT-080"]` |
| `tests/test_live_endpoint_compatibility.py::test_normalize_category_path_leaves_slash_form_unchanged` | `LREQ-EXT-080` | `["LREQ-EXT-080"]` |
| `tests/test_live_endpoint_compatibility.py::test_live_form_taxonomy_inventory_entry_is_well_formed` | `LREQ-EXT-020` | `["LREQ-EXT-020"]` |
| `tests/test_live_endpoint_compatibility.py::test_live_form_multi_valued_record_values_match_canonical_inventory` | `LREQ-EXT-080` | `["LREQ-EXT-080"]` |
| `tests/test_live_endpoint_compatibility.py::test_live_form_record_category_match_is_verified_not_mismatch` | `LREQ-EXT-090` | `["LREQ-EXT-090"]` |
| `tests/test_live_endpoint_compatibility.py::test_absent_category_value_still_maps_to_category_mismatch` | `LREQ-EXT-090` | `["LREQ-EXT-090"]` |
| `tests/test_live_endpoint_compatibility.py::test_request_body_guard_rejects_category_absent_from_template` | `LREQ-EXT-010` | `["LREQ-EXT-010"]` |
| `tests/test_live_endpoint_compatibility.py::test_request_body_guard_selects_exactly_one_committed_category` | `LREQ-EXT-010` | `["LREQ-EXT-010"]` |
| `tests/test_live_endpoint_compatibility.py::test_committed_categories_match_template_facet_byte_for_byte` | `LREQ-EXT-020`, `LREQ-EXT-010` | `["LREQ-EXT-020", "LREQ-EXT-010"]` |
| `tests/test_live_endpoint_compatibility.py::test_committed_taxonomy_covers_requested_categories_and_parents` | `LREQ-EXT-020` | `["LREQ-EXT-020"]` |
| `tests/test_live_endpoint_compatibility.py::test_committed_taxonomy_excludes_single_segment_entries` | `LREQ-EXT-020` | `["LREQ-EXT-020"]` |
| `tests/test_live_endpoint_compatibility.py::test_committed_template_omits_sort_criteria` | `LREQ-EXT-050` | `["LREQ-EXT-050"]` |
| `tests/test_live_endpoint_compatibility.py::test_live_form_normalization_is_deterministic` | `LREQ-ARCH-030` | `["LREQ-ARCH-030"]` |
| `tests/test_live_endpoint_compatibility.py::test_live_form_record_identity_candidates_unchanged` | `LREQ-EXT-060` | `["LREQ-EXT-060"]` |

- **`validation_fixtures.ONE_ABSENT_CATEGORY` casefold collision.** Verified by
  reading `validation.py` this session: `validate_requested_categories` compares
  `normalized not in known` where `known` is the case-preserving output of
  `taxonomy_path_set`, so presence is **case-sensitive** and
  `"Audio/Music/Orchestral"` remains genuinely absent beside
  `"audio/music/orchestral"`. The collision is therefore latent, not active. Per
  the dispatch and to keep a guaranteed-absent sentinel if that comparison is ever
  made case-insensitive, re-point the appended path to `audio/music/dnb` (no
  casefold match in the 121-entry inventory) and update the two literal
  assertions in `tests/test_validation.py` (lines 342 and 344) to match. Existing
  node IDs are unchanged; no node is renamed or weakened.
- **Fixture-category update.** `tests/fixtures/coveo_discovery.py`:
  `COVEO_FIXTURE_CATEGORY = "3d/characters/humanoids"` and
  `COVEO_FIXTURE_CATEGORY_OTHER = "vfx/particles/fire-explosions"` (both in the
  Q4 set, both template `currentValues`, both in
  `config_fixtures.DEFAULT_CATEGORIES`), or the Q3 guard raises in many existing
  `test_collector.py` nodes.
- **Existing nodes that must keep passing unchanged:** `tests/test_contracts.py::test_taxonomy_contract`
  (LREQ-EXT-020: requested ⊆ inventory, each parent in inventory),
  `tests/test_collector.py::test_coveo_endpoint_headers_and_facet_selection_match_captured_template`
  (`numberOfValues == 150`, one selected),
  `tests/test_collector.py::test_request_body_builder_signature_is_stable`,
  and all `tests/test_validation.py` LREQ-EXT-080 nodes.
- **Contradiction handling.** If any existing test contradicts the SRS after these
  changes (e.g. an assertion that `sortCriteria` must be replayed, if one is
  found), the test-author leaves it and reports
  `DISPUTE: <test id> — SRS §x says ...`; it is not silently edited.

## 10. Definition of done (gate)

Copied verbatim from the dispatch:

- Full suite green (`python -m pytest -q`) with the real counts reported; all four validators valid (`python -m niche_scout.tools.validate_traceability`, `...check_import_boundaries`, `...check_scope_prohibitions`, `...check_secrets`); ruff on changed files clean (config in `pyproject.toml`: `ruff` format + `check`/`lint`).
- A human-run `niche-scout run` against the live endpoint completes (exit 0), or fails only at the identity preflight — documented as the OI-6 limitation, not a new defect.
- Config and template are mutually consistent (string equality between `categories.json` and the template facet), and `template_sha256` matches the edited body.
- Plan, run log, tests, traceability, and the new separator/casing convention recorded.

## 11. Explicit prohibitions

- No live network in development or tests; tests never call the real endpoint.
- No edits to `pipeline.py` or `cli.py` (Q10).
- No GraphQL/session/CSRF/cookie fixes (OI-6), no capture tooling, no new GraphQL
  fields, no scoring/weight/threshold changes, no scheduling, no new dependencies,
  no new features.
- Never set `normalize_category_path` or any validation primitive to read a clock,
  open a file, or perform I/O; `validation.py` stays pure (LREQ-ARCH-010/020).
- Do not inject the requested category into the template in code (Q3 is
  config-only); the coupling is byte equality between `config/categories.json`
  and the template `currentValues`.
- Do not change the public signature of `build_coveo_request_body` or any function
  in §4; do not rename or delete existing pytest node IDs or their traceability
  entries.
- Do not modify `Documents/SRS-lean.md`, `AGENTS.md`, `kilo.json(c)`, `.kilo/`, or
  any frozen `Documents/interfaces/*` file.
- Secrets never appear in source, tests, fixtures, config, or logs.
- Do not claim pagination/ranking stability was verified; the sortCriteria removal
  leaves the engine default sort and an unverified stability tradeoff.

## 12. Open questions / assumptions

Assumptions (recorded, not silently resolved):

- **Q9 capture-instant provenance.** `config/category_taxonomy.json` and
  `config/categories.json` carry `captured_at_utc = 2026-09-23T07:21:37Z`,
  labeled **human-supplied**: it is the instant the human's live facet capture
  was delivered (the environment message time), because the human stated the
  taxonomy was never captured and supplied the live facet response directly. It
  is the delivery instant, not a separately verified probe instant. If a
  different probe instant is later known, it supersedes this value without
  changing any structural decision.
- **Fixture clock.** `tests/fixtures/config_fixtures.py` `TAXONOMY_FIXTURE`'s
  fixture-local capture instant stays `2026-01-05T00:00:00Z`, so
  `coveo_discovery.TAXONOMY_CAPTURED_AT_UTC`, `CAPTURE_CLOCK_OFFSET`, and
  `REFERENCE_UTC` remain valid and no freshness node ripples. The fixture is
  independent of the committed config; it is not re-derived from Q9. If a human
  later requires the fixture to mirror Q9, the three discovery constants and the
  `validation_fixtures` freshness fixtures must be re-derived together (a
  separate change).
- **Request-capture instant.** `config/coveo_search_template.json`'s
  `captured_at_utc` stays the request-capture instant
  (`2026-09-17T04:28:28.915Z`); Q9 applies only to the taxonomy/categories files.
- **Q4 feasibility deviation.** The dispatch's originally recommended requested
  set is infeasible: `tests/test_contracts.py::test_taxonomy_contract` (existing
  node, not edited) asserts `parent = path.rsplit("/",1)[0]` is in
  `canonical_category_paths` for every requested category. Including top-level
  values would make `validate_taxonomy_structure` return `malformed`
  (single-segment entries fail `_is_canonical_path_shape`) and would also make
  every record match trivially on its top-level element (record `ec_category`
  includes `"3d"`), so a 2-segment requested category such as `tools/utilities`
  (whose parent `tools` is single-segment) cannot be requested. No live
  `tools/*` category is 3-segment, so tools cannot appear in the requested set.
  The requested set is therefore exactly the 8 three-segment Q4 categories.
- **Tools limitation.** Because the taxonomy inventory must exclude the 7
  single-segment tops (Q5) to pass the parent-in-inventory contract, and no
  `tools/*` category is 3-segment, the `tools` domain is not represented in the 8
  requested categories.

Open questions (not resolved by this plan; human decision required before relying
on the affected behavior):

1. **Q7 manual capture procedure.** How the taxonomy file is to be captured and
   refreshed manually (source, cadence, redaction) is documented as an obligation
   but no tooling is built. If a formal procedure is required, it needs an owner
   and a future chunk.
2. **Pagination stability after sortCriteria removal.** Removing the invalid
   explicit sort yields the engine default (human states relevance). Whether
   page-to-page ordering is stable enough for the existing duplicate/ordinal
   handling is **not verified**; this is a documented limitation, not a proven
   property. LREQ-EXT-050's "same sort order" is satisfied only in the sense that
   all categories share the same default.
3. **OI-6 (CSRF/session sufficiency).** Out of scope and unowned (dependency-map
   §7). A run failing only at the identity preflight is the OI-6 limitation.
4. **URI trailing-identifier extraction (identity mapping rule 1.0.1).**
   Unverified (no captured response in the repo); this chunk does not change it
   and adds no claim that it was verified.

## Appendix A — `config/category_taxonomy.json` `canonical_category_paths` (121 entries, canonical `/` form)

`2d/characters, 2d/environments, 2d/fonts, 2d/gui, 2d/gui/icons, 2d/textures-materials, 2d/textures-materials/abstract, 2d/textures-materials/brick, 2d/textures-materials/building, 2d/textures-materials/concrete, 2d/textures-materials/fabric, 2d/textures-materials/floors, 2d/textures-materials/food, 2d/textures-materials/metals, 2d/textures-materials/nature, 2d/textures-materials/roads, 2d/textures-materials/roofing, 2d/textures-materials/sky, 2d/textures-materials/stone, 2d/textures-materials/tiles, 2d/textures-materials/water, 2d/textures-materials/wood, 3d/animations, 3d/characters, 3d/characters/animals, 3d/characters/animals/birds, 3d/characters/animals/fish, 3d/characters/animals/insects, 3d/characters/animals/mammals, 3d/characters/animals/reptiles, 3d/characters/creatures, 3d/characters/humanoids, 3d/characters/humanoids/fantasy, 3d/characters/humanoids/humans, 3d/characters/humanoids/sci-fi, 3d/characters/robots, 3d/environments, 3d/environments/dungeons, 3d/environments/fantasy, 3d/environments/historic, 3d/environments/industrial, 3d/environments/landscapes, 3d/environments/roadways, 3d/environments/sci-fi, 3d/environments/urban, 3d/gui, 3d/props, 3d/props/clothing, 3d/props/clothing/accessories, 3d/props/clothing/armor, 3d/props/electronics, 3d/props/exterior, 3d/props/food, 3d/props/furniture, 3d/props/guns, 3d/props/industrial, 3d/props/interior, 3d/props/tools, 3d/props/weapons, 3d/vegetation, 3d/vegetation/flowers, 3d/vegetation/plants, 3d/vegetation/trees, 3d/vehicles, 3d/vehicles/air, 3d/vehicles/land, 3d/vehicles/sea, 3d/vehicles/space, audio/ambient, audio/ambient/fantasy, audio/ambient/nature, audio/ambient/noise, audio/ambient/sci-fi, audio/ambient/urban, audio/music, audio/music/electronic, audio/music/orchestral, audio/music/pop, audio/music/rock, audio/music/world, audio/sound-fx, audio/sound-fx/animals, audio/sound-fx/creatures, audio/sound-fx/foley, audio/sound-fx/transportation, audio/sound-fx/voices, audio/sound-fx/weapons, templates/packs, templates/systems, templates/tutorials, tools/ai-ml-integration, tools/animation, tools/audio, tools/behavior-ai, tools/camera, tools/game-toolkits, tools/generative-ai, tools/gui, tools/input-management, tools/integration, tools/level-design, tools/localization, tools/modeling, tools/network, tools/painting, tools/particles-effects, tools/physics, tools/sprite-management, tools/terrain, tools/utilities, tools/version-control, tools/video, tools/visual-scripting, vfx/particles, vfx/particles/environment, vfx/particles/fire-explosions, vfx/particles/spells, vfx/shaders, vfx/shaders/directx-11, vfx/shaders/fullscreen-camera-effects, vfx/shaders/substances.`

Excluded single-segment tops (Q5): `2d, 3d, add-ons, audio, templates, tools, vfx`
(total 128 = 121 + 7).

## Appendix B — Requested categories and facet values (Q4, all 3-segment, all live)

| # | Canonical path | Live `totalCountFiltered` |
|---|---|---|
| 1 | `3d/characters/humanoids` | 8254 |
| 2 | `2d/gui/icons` | 3366 |
| 3 | `3d/vehicles/land` | 3174 |
| 4 | `audio/music/orchestral` | 1383 |
| 5 | `3d/characters/animals/mammals` | 1053 |
| 6 | `3d/vegetation/trees` | 752 |
| 7 | `vfx/particles/fire-explosions` | 440 |
| 8 | `2d/textures-materials/stone` | 194 |

All eight are `state: "idle"` in the committed template; the builder marks exactly
the requested one `"selected"`. `config/categories.json` and the template facet
must be byte-for-byte equal on these eight strings.