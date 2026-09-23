# Chunk 16 — Coveo discovery record-shape remediation (labeled post-completion remediation)

Status: FROZEN
Depends on (frozen interfaces required before this plan can be trusted):
  - `Documents/interfaces/chunk-03.md` §3 (the `CoveoPageResponse` typed result and
    its `records`/`issues`/`is_structural_failure` contract), §4
    (`resolve_observation_identity(record)`), §5 (`CoveoObservationSink.write_page`)
    and §6 ("Discovery-time field population" — the response `ec_category` verbatim
    and the identity candidates). Signatures unchanged.
  - `Documents/interfaces/chunk-01.md` §4 (`collect_identity_candidates`,
    `resolve_canonical_identity`, `match_exact_category`, `taxonomy_path_set`) and
    §4.1 (identity mapping rule `1.0.1`) — consumed unchanged; no signature and no
    extraction-rule change.
  - `Documents/interfaces/chunk-02.md` §3 (the page sink
    `insert_raw_discovery_observations(page_observations)`) — consumed unchanged.
  - `Documents/interfaces/chunk-00.md` §2/§5 (`COVEO_DISCOVERY_FIELD_SET`'s five
    names; `MAX_DISCOVERY_RESULTS_PER_CATEGORY`; config paths) — consumed unchanged.
Blocks (chunks whose plan/implementation needs this chunk's interface):
  - None. This is a labeled post-Chunk-15 remediation (same pattern as Chunks 14 and
    15): it has **no `Documents/requirements-dependency-map.md` §3/§4 row**, it
    introduces no new interface file, and no downstream chunk starts on it. The plan
    states its own gate in §10.

## 1. Goal

Two live `niche-scout run` executions failed discovery for **all eight** categories
with `DISCOVERY_PAGE_FAILED`, each reporting **96** `response_missing_required_member`
issues (96 = `PAGE_SIZE`). The persisted cause is unavailable offline (Chunks 14/15
recorded it as an unverifiable-offline suspect), and the human supplied a live,
redacted response capture this session that resolves it: the Coveo Search API v2
nests the five requested discovery fields under a per-record **`raw`** object, while
the adapter reads each record **flat**. Every record therefore looks identity-less
and category-less, the required-member check fires per record, and the whole page is
discarded as a structural failure — never read as zero assets (correct failure
semantics, wrong parse).

Live record shape (human-supplied live capture, redacted to the discovery fields;
this is the operative evidence for the plan, not a guess):

- top level: `"uri": "assetstore://product/379642"`,
  `"clickUri": "https://assetstore.unity.com/packages/package/379642"`,
  `"uniqueId": "42.20568$assetstore://product/379642"`, plus `title`/`excerpt`/`score`.
- nested: `"raw": {"permanentid": "379642", "ec_product_id": ["379642"],
  "ec_name": "...", "ec_category": ["3d", " 3d > characters"],
  "publisher_name": "..."}`.
- `ec_product_id` and `ec_category` are **lists**; `permanentid` is a **string**.
  `clickUri`/`uri` are top-level (not under `raw`).

This chunk fixes the read boundary so the required-member check, identity resolution,
category matching, and the persisted `category_value_json` all see the **live**
shape, with **no** change to `validation.py` semantics, no signature change, and no
behavior change for flat synthetic fixtures. One normalization step lifts only the
five discovery-set members out of `raw`; everything downstream is the existing
machinery.

Where it fails (each verified by reading the working tree this session; the dispatch's
line anchors were confirmed and are cited below as anchors, not contents):

- `src/niche_scout/collector_coveo.py:1091-1093` — the required-member check walks
  `_RESPONSE_FIELD_SET_MEMBERS` (`("permanentid", "ec_product_id", "ec_category")`,
  defined at `:238-242`) against the **top-level** `item`; `:1131` `records.append(item)`.
- `src/niche_scout/collector_coveo.py:1341-1343` —
  `resolve_observation_identity(record)` and
  `match_exact_category(record.get("ec_category"), taxonomy_paths)`.
- `src/niche_scout/collector_coveo.py:1721-1723` —
  `category_value_json=json.dumps(record.get("ec_category"), ...)`.
- `src/niche_scout/validation.py:1348-1379` — `collect_identity_candidates` reads
  `record.get(source_field)` for `ec_product_id`/`permanentid`/`clickUri`/`uri` and
  drops any non-string through `_usable_candidate` (`:1246-1257`); `clickUri`/`uri`
  are **not** in `_IDENTITY_SOURCE_FIELDS` in a way that tolerates non-strings.
- `src/niche_scout/collector_coveo.py:394-400` `is_structural_failure` +
  `:1927-1930` the `PAGE_FAILED` break: one required-member issue makes the whole
  page a structural failure and it is discarded (never zero assets) — the correct
  outcome for a genuinely malformed page, and the reason a parse mismatch is fatal
  rather than partial.

## 2. Scope

### In scope

- **R1 — one record normalization step in `_read_page`.** Add a private helper
  (name/typing in §7.1) that returns, for one raw response record, a mapping in
  which each of the five `COVEO_DISCOVERY_FIELD_SET` members is exposed **at the top
  level** using the record's own value when present, else the value found under
  `raw` when `raw` is a mapping that carries it. Call it once per record **before**
  the required-member check (`:1091`), the forbidden-member check (`:1132`), and
  `records.append(item)` (`:1131`). (LREQ-EXT-040, LREQ-EXT-060, LREQ-EXT-080)
- **R2 — field-set-restricted lift.** Only the five discovery-set member names may be
  read out of `raw`. No other `raw` member (e.g. `sysurihash`/`urihash`) is lifted,
  copied, or renamed into the record. The forbidden-member check keeps reading the
  top-level keys of the normalized mapping. (LREQ-EXT-040)
- **R3 — precedence and backward compatibility.** A member present at the top level
  wins; `raw` is a **fallback** only. A record with no `raw`, with a non-mapping
  `raw`, or with a `raw` mapping missing a member keeps exactly today's behavior:
  flat synthetic fixtures (all existing tests) are byte-for-byte unaffected.
  (LREQ-EXT-040, LREQ-ARCH-030)
- **R4 — `raw` is never itself a structural failure.** An absent or non-mapping
  `raw` adds no issue and changes no issue code. A record with neither a top-level
  nor a `raw`-nested required member still produces the existing
  `response_missing_required_member` per record and the existing `page_failed`.
  (LREQ-EXT-040, LREQ-EXT-050)
- **R5 — no new lifting of the top-level response fields.** `clickUri`/`uri` stay
  top-level-only sources (the capture shows them top-level); this chunk does **not**
  begin reading a `raw.clickUri`/`raw.uri` and does not add them to any lifted set.
  (LREQ-EXT-060)
- **R6 — tests and traceability first.** The test-author writes the failing nodes
  and their `tests/traceability.json` entries (§9) before `impl-deep` implements R1.

### Explicitly out of scope (and who owns it instead)

- **`validation.py` semantics and every Chunk 1 primitive signature.** No edit to
  `validation.py`. The fix is at the adapter's record-reading boundary by design; the
  primitives keep receiving a flat mapping. (Owner: Chunk 1 / none.)
- **`ec_product_id` list shape.** With this fix `ec_product_id` stays a
  non-string (a one-element list), so `_usable_candidate` still drops it as a
  candidate and identity resolves through the string `permanentid`. That is recorded
  as an explicit assumption/limitation in §12, **not** silently handled. Adding list
  unwrapping is a separate decision with its own LREQ basis and test (§12 Q1); this
  plan does not include it. (Owner: none yet.)
- **URI trailing-identifier extraction (identity mapping rule `1.0.1`).** Still
  **inferred and UNVERIFIED**; the live capture now in hand is *not* a verified
  redacted Coveo response committed to the repository, so this chunk adds **no**
  claim that the extraction rule was verified and does not touch it.
  (`interfaces/chunk-01.md` §4.1; dependency-map §6.4.)
- **GraphQL, OI-6 (CSRF/session sufficiency).** Untouched
  (`interfaces/chunk-01.md` §4.1; dependency-map §7).
- **Schema, `pipeline.py`, `cli.py`, `report.py`, scoring, sampling, metrics.** No
  formula, weight, threshold, output, warning, or persisted-column change.
- **Live network.** No live call in development or tests; the human's capture is the
  only live evidence and is quoted here, not re-fetched.
- **A committed live-response fixture.** This plan does **not** commit the raw
  capture as a file; the live-shape fixture is a hand-derived literal (§9). Whether a
  committed captured response should replace it is an open question (§12 Q4).

## 3. Requirements this chunk must satisfy

Chunk 16 is a labeled post-completion remediation and has **no
`Documents/requirements-dependency-map.md` §3 section** (the map's chunked plan ends
at Chunk 13; Chunks 14/15 are the same kind of remediation and are likewise absent).
No dependency-map section is created and no interface file is edited.

| LREQ ID | Ownership role here | Normative text (from `SRS-lean.md`, quoted/derived) | SRS section |
|---|---|---|---|
| LREQ-EXT-040 | Primary (this remediation) | "Discovery SHALL use the parent SRS discovery-only field set: `permanentid`, `ec_product_id`, `ec_name`, `ec_category`, and `publisher_name`. Product rating, page views, publication date, and price SHALL NOT be sourced from Coveo for scoring." The five names are the **only** members this chunk may lift from `raw`; the response-side allow-list complement (a top-level member outside the five is recorded as forbidden presence, by count and index only) is unchanged. | §4.1 (line 254) |
| LREQ-EXT-050 | Supporting (Chunk 3 remains primary; no behavior change) | "…the discovery status SHALL be one of `complete`, `truncated`, `page_failed`, `filter_unverified`, `category_mismatch`, `identity_incomplete`, or `request_failed`; a failed or truncated page SHALL never be interpreted as zero assets." The fix converts a **false** `page_failed` into the true status by making the record readable; a genuinely missing member still fails the page and is still never read as zero assets. | §4.1 (line 259) |
| LREQ-EXT-060 | Primary (this remediation) | "Each discovery record SHALL retain all non-empty identity candidates from `ec_product_id`, `permanentid`, response-level `clickUri`, and response-level `uri`. Candidates SHALL be canonicalized under one versioned mapping rule." "Response-level" is read as **record-level in the response**, which the live capture shows split between top level (`clickUri`/`uri`) and `raw` (`permanentid`/`ec_product_id`); after R1 the record exposes all four at the top level and the existing `collect_identity_candidates` retains them unchanged. `raw`-membership is the fix; the extraction rule itself is untouched (§2 out of scope). | §4.1 (line 265) |
| LREQ-EXT-080 | Primary (this remediation) | "Exact category membership SHALL be checked against the canonical taxonomy. Parent paths SHALL NOT match child paths merely by prefix. Scalar and multi-valued category response shapes SHALL be handled explicitly." The live multi-valued `["3d", " 3d > characters"]` shape is handled by the existing primitive once `ec_category` is exposed at the top level; construction is per-field so a non-category member does not invalidate the category. | §4.1 (line 275) |
| LREQ-EXT-090 | Supporting (Chunks 3/10/12 remain primary) | "A failed page, unverified filter, category mismatch, or material identity incompleteness SHALL generate a warning and SHALL prevent a fully rankable competition result for that category." The fix removes the **false** `page_failed` warning source; a genuinely absent value still yields the existing condition set and warning path, which this chunk does not change. | §4.1 (line 279) |
| LREQ-ARCH-030 | Supporting (Chunk 10 remains primary) | "The same normalized input data, policy versions, and configuration SHALL produce the same metric, score, evidence, and sensitivity outputs." The normalization is a deterministic, order-free function of its input record (fixed per-field order; no set/dict-iteration dependence, no clock, no RNG); repeated calls are equivalent. | §3 |

`AGENTS.md` "Hard rules" 2 is the **supporting invariant** for R1's construction rule:
"Missing is not zero. Null, explicit valid zero, invalid, and unavailable are four
different states." A member is copied only when genuinely **present**; presence is
tested with an explicit `in`/`is not None`, never with a truthiness fallback. No
`or`-default, `.get(k, 0)`, or fill-from-nothing is introduced. No new LREQ is
invented and no formula, weight, or threshold is asserted.

## 4. Interface contracts consumed

Copied from the frozen interface files (not re-derived from source):

- `interfaces/chunk-03.md` §3: `CoveoPageResponse(page_index, first_result,
  total_count, records: tuple[Mapping[str, object], ...], request_metadata, issues,
  filtered_count, forbidden_field_presence)`, with
  `is_structural_failure` true when an issue code is
  `response_wrong_container_kind` or `response_missing_required_member`.
- `interfaces/chunk-03.md` §4: `resolve_observation_identity(record:
  Mapping[str, object]) -> IdentityResolutionResult` — signature unchanged; it reads
  the four identity fields **flat** through the Chunk 1 primitive.
- `interfaces/chunk-03.md` §5: `CoveoObservationSink.write_page(page, *,
  ordinal_start, taxonomy_paths, seen_identities, limit=None) ->
  CategoryPageOutcome` — unchanged.
- `interfaces/chunk-03.md` §6: "Every raw observation carries: all non-empty identity
  candidates (`identity_candidates_json`)…, the response `ec_category` verbatim, the
  category-filter status… No value is fabricated for a missing field."
- `interfaces/chunk-01.md` §4:
  `collect_identity_candidates(record: Mapping[str, object]) -> tuple[IdentityCandidate, ...]`
  (reads `ec_product_id`, `permanentid`, `clickUri`, `uri`; non-string and
  whitespace-only dropped by `_usable_candidate`, `validation.py:1246-1257`);
  `match_exact_category(category_value: object, taxonomy_paths: Container[str]) ->
  CategoryMatchResult` (a `list`/`tuple` contributes every string entry; absent /
  wrong-typed ⇒ `unverified`; usable-but-no-match ⇒ `mismatch`);
  `taxonomy_path_set(payload: object) -> frozenset[str]`.
  §4.1 identity mapping rule `1.0.1`: `ec_product_id`/`permanentid` are canonical
  as-supplied; URI-derived identifiers require the trailing `-<digits>` pattern.
- `interfaces/chunk-02.md` §3: `insert_raw_discovery_observations(page_observations)`
  page-sink contract — unchanged.
- `interfaces/chunk-00.md` §2/§5: the five-name `COVEO_DISCOVERY_FIELD_SET`
  (identical to the adapter's own
  `collector_coveo.COVEO_DISCOVERY_FIELD_SET`, `:86-87`, read this session).

**Signature-freeze facts (verified by reading, this session).**

- `collector_coveo._RESPONSE_FIELD_SET_MEMBERS` is exactly
  `("permanentid", "ec_product_id", "ec_category")` (`:238-242`). The required-member
  check is therefore a **subset** test, not a five-name test: `ec_name` and
  `publisher_name` are deliberately not structural.
- `tests/test_collector.py::test_extra_response_fields_are_ignored_and_missing_identity_fields_stay_missing`
  (`:579-625`) asserts `page_failed` for a record that is only
  `{"ec_name": "Nameless"}` — a record with no `raw` and no required member. R1 and
  R4 keep that node passing unchanged.
- `tests/test_collector.py::test_response_carrying_a_novel_member_records_forbidden_presence`
  (`:628-663`) asserts `forbidden_field_presence == [{"record_index": 0,
  "extra_member_count": 1}]` for a flat record with one novel member. The
  normalization must not add top-level keys beyond the five discovery members, or
  this node changes.
- `tests/test_collector.py::test_request_body_builder_signature_is_stable` (`:357`)
  and `tests/test_collector.py::test_module_imports_without_side_effects` (`:325`)
  are the two non-analytical collector nodes (no marker, no matrix entry). This chunk
  adds no non-analytical node.
- `tests/fixtures/coveo_discovery.py::record` (`:347-376`) builds **flat** records
  (`permanentid`/`ec_product_id`/`ec_name`/`ec_category`/`publisher_name` at the top
  level). Every existing discovery test is a flat-record test; R3 must leave them
  unchanged.
- `tests/fixtures/pipeline_fixtures.py::coveo_record` (`:614-627`) likewise builds
  flat records; `coveo_page` (`:630-641`) is the only page builder for the e2e
  scenario, and `scenario_artifacts` (`fixtures/cli_fixtures.py:476-510`) reuses it.
  A live-shape e2e assertion requires a **new** fixture helper, not an edit to
  `coveo_page` (which would perturb the frozen scenario).
- `pyproject.toml` has no logging configuration relevant here;
  `[tool.ruff] line-length = 88`, `select = ["E", "F", "I"]` (carried from
  `Documents/runs/chunk-15.md` §4 and the Chunk 15 plan §4, itself verified by
  reading; not re-read this session).
- `tests/traceability.json` is committed **node-ID → array of LREQ IDs**;
  `python -m niche_scout.tools.validate_traceability` enforces that orientation
  (carried from the Chunk 15 plan §4, verified there; not re-read this session;
  `tests/AGENTS.md` lines 5–13 describe the opposite, stale orientation — the
  committed file and the validator govern).

## 5. Interface contract this chunk produces

**None.** This is a labeled post-completion remediation, not a dependency-map chunk.
No `Documents/interfaces/chunk-16.md` is created (Chunks 14 and 15 created none) and
no downstream chunk consumes a new surface from it. Every public signature in §4 is
unchanged.

One behavioral record replaces interface-document state without rewriting the frozen
interface files:

- `CoveoPageResponse.records` now carries records whose five discovery fields may
  have been **lifted from a per-record `raw` mapping** (the live Coveo Search v2
  shape). This changes neither the type (`tuple[Mapping[str, object], ...]`) nor the
  sink contract; it changes which record members the required-member check, the
  identity step, the category matcher, and `category_value_json` observe.
  `interfaces/chunk-03.md` §6's "the response `ec_category` verbatim" is preserved:
  the verbatim value is the one the endpoint supplied, at whichever level it supplied
  it. `interfaces/chunk-03.md` is **not** edited by this chunk; the divergence is
  recorded here and in the run log.

## 6. Files touched

| File | New/modified | Purpose |
|---|---|---|
| `src/niche_scout/collector_coveo.py` | modified | R1/R2/R3/R4/R5: add one private record-normalization helper and call it once per record in `_read_page` before the required-member check. No public signature changes; no constant and no vocabulary changes. |
| `tests/test_collector.py` | modified | New analytical nodes (§9) for the live nested shape, precedence, fallback, no-lift, and `raw`-absent behavior. Existing nodes unchanged. |
| `tests/test_end_to_end.py` | modified | New Node 11 live-shape acceptance node (§9); existing Chunk 13 acceptance nodes unchanged. |
| `tests/fixtures/coveo_discovery.py` | modified | New live-shape record/page helpers (§9); existing helpers and every existing literal unchanged. |
| `tests/traceability.json` | modified | New node → LREQ-array entries (§9). |

**Not touched:** `validation.py`, `pipeline.py`, `cli.py`, `database.py`,
`report.py`, `metrics.py`, `scoring.py`, `sampling.py`, `models.py`, `config.py`,
`collector.py`, `collector_graphql.py`, `src/niche_scout/tools/**`, `pyproject.toml`,
`config/**`, `tests/fixtures/pipeline_fixtures.py`,
`tests/fixtures/cli_fixtures.py`, `tests/fixtures/config_fixtures.py`,
`tests/test_pipeline.py`, `tests/test_cli.py`,
`Documents/SRS-lean.md`, `Documents/requirements-dependency-map.md`, `AGENTS.md`,
`kilo.json(c)`, `.kilo/`, and every `Documents/interfaces/*` file.

**Why no fixture file beyond `coveo_discovery.py`:** the live-shape e2e assertion is
built **inline** from the public `pipeline_fixtures` builders plus the new
`coveo_discovery` helper, so `pipeline_fixtures.py` and `cli_fixtures.py` stay
byte-identical and the frozen Chunk 10/13 scenario is not perturbed.

## 7. Exact edits

Line anchors below are the working-tree state read this session; they are **anchors,
not contents**. The plan's task list cites the same anchors.

### 7.1 `src/niche_scout/collector_coveo.py` — the normalization step

Add one private helper. Placement: immediately above `_read_page` (current line
1013), next to `_usable_total_count`/`_api_reported_count`, so it is a record-reading
concern with no other caller.

```python
#: The one member whose presence may be lifted from a record's nested ``raw``
#: mapping (the live Coveo Search v2 shape). It is ``COVEO_DISCOVERY_FIELD_SET``
#: and nothing else: no other ``raw`` member is read, copied, or renamed
#: (LREQ-EXT-040).
_RAW_FALLBACK_FIELD_SET: tuple[str, ...] = tuple(COVEO_DISCOVERY_FIELD_SET)


def _normalize_discovery_record(
    record: Mapping[str, object],
) -> Mapping[str, object]:
    """Return ``record`` with the five discovery fields exposed at the top level.

    The live Coveo Search v2 response nests the requested discovery fields under a
    per-record ``raw`` object, while the adapter's required-member check, identity
    step, category matcher, and ``category_value_json`` all read the record flat.
    This is the single place that bridges the two: for each member of
    :data:`COVEO_DISCOVERY_FIELD_SET` in that fixed order, the top-level value wins
    when the key is present (even as ``None``), else the value found under ``raw``
    when ``raw`` is a mapping that carries the key.

    Backward compatible: a record with no ``raw``, a non-mapping ``raw``, or a
    ``raw`` mapping missing a member is returned **unchanged** (the identical
    object), so flat synthetic fixtures keep exactly today's behavior. ``raw``
    itself is never removed, never validated, and never treated as a structural
    failure — an absent or non-mapping ``raw`` adds no issue.

    Only the five discovery-set names are lifted. A member that is present but
    unusable (for example the live one-element list ``ec_product_id``) is copied
    **as supplied** and stays unusable downstream; nothing is coerced, and a
    missing member is never replaced by a zero or an empty value (AGENTS.md hard
    rule 2). The result is a deterministic function of ``record``: the copy order
    is the fixed field-set order and no set/dict iteration order is observed
    (``LREQ-ARCH-030``).

    The copy is a shallow ``dict`` per field, constructed only when a field
    actually needs lifting; a record that needs none is returned as the same
    mapping object, so the forbidden-member check below still sees exactly the
    record's own (top-level) keys and a lifted field cannot create a terminator.
    """
    raw = record.get("raw")
    if not isinstance(raw, Mapping):
        return record
    lifted: dict[str, object] | None = None
    for member in _RAW_FALLBACK_FIELD_SET:
        if member in record:
            continue
        if member in raw:
            if lifted is None:
                lifted = dict(record)
            lifted[member] = raw[member]
    if lifted is None:
        return record
    return lifted
```

Then, in `_read_page`'s record loop, change exactly one line region:

- Current (`:1091-1093`):

  ```python
  missing_members = [
      member for member in _RESPONSE_FIELD_SET_MEMBERS if member not in item
  ]
  ```

- New — normalize first, then test the normalized record:

  ```python
  item = _normalize_discovery_record(item)
  missing_members = [
      member for member in _RESPONSE_FIELD_SET_MEMBERS if member not in item
  ]
  ```

Everything after that is unchanged: `structural_missing` (`:1104-1111`),
`_issue("response_missing_required_member", ...)` (`:1119-1129`), `records.append(item)`
(`:1131`) — which now appends the **normalized** mapping — and the
forbidden-member check (`:1132-1139`), which now reads the normalized record's
top-level keys.

No other edit in this file. `resolve_observation_identity`,
`_build_observation`, `CoveoObservationSink.write_page`,
`_RESPONSE_FIELD_SET_MEMBERS`, `_DISCOVERY_RESPONSE_FIELD_SET`,
`COVEO_DISCOVERY_FIELD_SET`, and every public signature stay as they are.

## 8. Edge cases and invariants

- **Top-level wins, `raw` is fallback.** A member present at the top level is never
  overwritten from `raw`, **including an explicit `None` or `""`** (presence, not
  truthiness). A record carrying both a top-level `ec_category` and a `raw.ec_category`
  is classified from the top-level value.
- **No `raw`, non-mapping `raw`, `raw` without the member.** The helper returns the
  same mapping object; nothing is added, removed, or marked. `raw: null`,
  `raw: "text"`, `raw: [1, 2]`, and `raw: {}` are all inert.
- **`raw` is never a structural failure.** `CoveoPageResponse.issues` gains no code
  and loses none because of `raw`; the only structural codes remain
  `response_wrong_container_kind` and `response_missing_required_member`.
- **A record with neither level's required member** still yields the existing
  per-record `response_missing_required_member` and the existing `page_failed`
  (`test_extra_response_fields_are_ignored_and_missing_identity_fields_stay_missing`,
  `:614-625`).
- **No member outside the five is lifted.** `raw.sysurihash`, `raw.urihash`,
  `raw.uniqueId`, and any other `raw` member stay under `raw`; they are neither
  copied to the top level nor recounted. `raw` itself stays a top-level key, so a
  live record still records **one** forbidden member (`raw`) exactly as it does
  today.
- **Forbidden-member accounting is unchanged in kind.** The check at `:1132` still
  emits one `{"record_index", "extra_member_count": 1}` per record carrying any key
  outside the five-name set. Because R1 adds only the five names, it can never turn a
  1 into a 2; the `test_response_carrying_a_novel_member_records_forbidden_presence`
  assertion (`:657-659`) is preserved.
- **`ec_product_id` list shape.** `["379642"]` is copied as a list and dropped by
  `_usable_candidate` (`validation.py:1246-1257`); it is **not** unwrapped (§12 Q1).
- **Identity resolves through the string `permanentid`.** With the live record, the
  candidates are `permanentid` (string) and `clickUri`/`uri` (top level) only;
  `ec_product_id` contributes nothing. Under mapping rule `1.0.1` the live pair
  resolves iff the URI trailing identifier **equals** `permanentid`. For the capture,
  `permanentid = "379642"` and `clickUri`/`uri` end in `/379642` with no
  `-<digits>` suffix, so the URI fields contribute **nothing** (no candidate); the
  record resolves to `"379642"` through `permanentid` alone. A URI form with a
  `-<digits>` suffix that differs from `permanentid` would be a `conflict` under the
  existing rule — unchanged by this chunk.
- **`category_value_json` carries the verbatim live value.** For the live
  `["3d", " 3d > characters"]` shape, the persisted JSON is that list verbatim
  (`:1721-1723`), and `match_exact_category` normalizes each entry with the existing
  `" > "` separator handling (`validation.py:1075`). A record whose `ec_category` is
  a `str` or `list[str]` is unchanged in behavior.
- **A `raw`-nested `ec_category` that is a scalar string** is lifted and matched the
  same way a top-level scalar is.
- **Encoding/serialization unchanged.** The normalized mapping is plain JSON-shaped
  data (the `raw` sub-values are `str`/`list`/`dict`); no new serialization default,
  no `default=str` behavior change, no non-JSON object introduced.
- **Determinism.** The helper's output depends only on the record; copy order is the
  fixed field-set order. No clock, RNG, set/dict-ordering dependence.
- **Purity boundary untouched.** `collector_coveo.py` is an I/O module; no clock is
  read outside the injected one and no new import is added.

## 9. Test plan

- **Files:** the new analytical nodes go in `tests/test_collector.py` (the Chunk 3
  requirement home); the live-shape record/page helpers go in
  `tests/fixtures/coveo_discovery.py`. No new test module and no new fixture module.
- **Fixtures:** add **only** live-shape helpers to `coveo_discovery.py`; every
  existing helper and literal stays byte-identical (the flat `record`, `records`,
  `record_without_identity`, `conflicting_record`, make_page`, `page_response` path
  in `test_collector.py`, and all `LIVE_FORM_*` literals). The e2e node builds its
  run inline from `pipeline_fixtures` (which is **not** edited).
- **Red state required.** After `test-author` writes the nodes, the suite must fail
  as **missing-implementation** (the live-shape nodes fail; no collection or syntax
  error). `impl-deep` implements R1 afterwards.
- **Exact markers and traceability entries** (each node must carry exactly these
  marker arguments and exactly matching `tests/traceability.json` values; the file's
  orientation is node-ID → array of LREQ IDs, §4):

| pytest node ID | `@pytest.mark.lreq(...)` marker args | `tests/traceability.json` value |
|---|---|---|
| `tests/test_collector.py::test_raw_nested_discovery_fields_are_read_from_the_live_record_shape` | `LREQ-EXT-040`, `LREQ-EXT-060` | `["LREQ-EXT-040", "LREQ-EXT-060"]` |
| `tests/test_collector.py::test_live_nested_record_resolves_identity_and_category_from_normalized_shape` | `LREQ-EXT-060`, `LREQ-EXT-080` | `["LREQ-EXT-060", "LREQ-EXT-080"]` |
| `tests/test_collector.py::test_top_level_member_wins_over_raw_fallback` | `LREQ-EXT-040` | `["LREQ-EXT-040"]` |
| `tests/test_collector.py::test_flat_record_without_raw_is_normalized_unchanged` | `LREQ-EXT-040` | `["LREQ-EXT-040"]` |
| `tests/test_collector.py::test_non_mapping_raw_is_inert_and_not_a_structural_failure` | `LREQ-EXT-040`, `LREQ-EXT-050` | `["LREQ-EXT-040", "LREQ-EXT-050"]` |
| `tests/test_collector.py::test_live_raw_is_not_lifted_and_forbidden_metadata_is_unchanged` | `LREQ-EXT-040` | `["LREQ-EXT-040"]` |
| `tests/test_collector.py::test_live_multivalued_category_is_matched_verbatim_after_normalization` | `LREQ-EXT-080` | `["LREQ-EXT-080"]` |
| `tests/test_collector.py::test_live_nested_record_yields_complete_status_and_no_page_failed` | `LREQ-EXT-050`, `LREQ-EXT-090` | `["LREQ-EXT-050", "LREQ-EXT-090"]` |
| `tests/test_collector.py::test_live_nested_record_populates_identity_candidates_without_ec_product_id` | `LREQ-EXT-060` | `["LREQ-EXT-060"]` |
| `tests/test_collector.py::test_normalization_is_deterministic_for_equal_live_records` | `LREQ-ARCH-030` | `["LREQ-ARCH-030"]` |
| `tests/test_end_to_end.py::test_acceptance_run_reads_live_shaped_raw_records` | `LREQ-EXT-060`, `LREQ-EXT-050`, `LREQ-TST-080` | `["LREQ-EXT-060", "LREQ-EXT-050", "LREQ-TST-080"]` |

- **New fixture helpers** (add to `tests/fixtures/coveo_discovery.py`, append after
  the response-side section, §"Live-form vocabulary" region; every name must be added
  to `__all__`):

  - `LIVE_RAW_RECORD_FIELDS: dict[str, object]` — the human-supplied live `raw`
    member set, hand-derived from the capture in §1:
    `{"permanentid": "379642", "ec_product_id": ["379642"], "ec_name": "Fixture Live Asset", "ec_category": ["3d", " 3d > characters"], "publisher_name": "Fixture Publisher"}`.
  - `def live_raw_record(index: int = 0, *, category: object = None) -> dict[str, Any]`
    — return one record with the live **nesting**: top-level `uri`, `clickUri`,
    `uniqueId`, `title`, `excerpt`, `score`, and a `raw` mapping carrying the five
    discovery fields. Default identity `f"{379642 + index}"` for `permanentid`, with
    `ec_product_id` the one-element list of the same value, and `uri`/`clickUri` the
    live forms without a `-<digits>` suffix
    (`"assetstore://product/379642"`,
    `"https://assetstore.unity.com/packages/package/379642"`). Keep the helper
    **derived-but-explicit**: a module docstring line states it is hand-derived from
    the supplied live capture and is not a committed capture file.
  - `def live_raw_page(page_records, *, total_count, filtered_count=None) -> dict[str, Any]`
    — the same page envelope `make_page` uses (`results`, `totalCount`,
    `totalCountFiltered`), so the existing `page_response` harness can serve it.
  - `def live_raw_summary_record(*, identity: str, category: str) -> dict[str, Any]`
    — one live-nested record for a synthetic e2e category: `permanentid` = the
    scenario identity, `ec_product_id` = `[identity]`, `ec_category` = the category,
    with top-level `uri`/`clickUri` carrying no usable trailing identifier so the
    identity resolves through `permanentid` alone.

  None of these helpers may read `config/`, a clock, or the network; they are inert
  literals in the spirit of `coveo_discovery.py`'s docstring.

- **Node-by-node expected values (hand-derived; test-author asserts these without
  reading the implementation).**

  - **Node 1
    `test_raw_nested_discovery_fields_are_read_from_the_live_record_shape`.** Build a
    one-record page from `fx.live_raw_page([fx.live_raw_record(0)], total_count=1)`
    and run `discover(repository, opener)` (the module's existing harness). Expected:
    `result.discovery_status is DiscoveryStatus.COMPLETE`; exactly one row; the row's
    `category_value_json` loads to `["3d", " 3d > characters"]`; the row's
    `identity_candidates_json` source fields are `["permanentid"]` at a minimum (no
    `ec_product_id`), and `asset_identity_key == "379642"`.
  - **Node 2
    `test_live_nested_record_resolves_identity_and_category_from_normalized_shape`.**
    Same page; assert `result.canonical_identity_count == 1`,
    `result.unresolved_identity_count == 0`, `result.conflict_identity_count == 0`,
    `result.filter_status is CategoryFilterValidationStatus.VERIFIED`, and
    `result.conditions == ()`. The category match is verified against the fixture
    taxonomy's live-form inventory (`fx.LIVE_FORM_INVENTORY_CANONICAL` contains
    `3d/characters`), so pass `taxonomy=fx.live_form_taxonomy_payload()` to
    `discover`.
  - **Node 3 `test_top_level_member_wins_over_raw_fallback`.** A record whose
    top-level `ec_category` is `CATEGORY` (the fixture's canonical 3-segment path)
    but whose `raw.ec_category` is `["vfx", " vfx > particles"]`. Assert the row's
    `category_value_json` loads to `CATEGORY` (top level), **not** the `raw` list,
    and the persisted `category_filter_validation_status` is `verified`.
  - **Node 4 `test_flat_record_without_raw_is_normalized_unchanged`.** Two flat
    `fx.record`s with no `raw`; assert both rows and statuses equal the outcome of
    the pre-change flat behavior (`COMPLETE`, identities resolved, categories
    verified). This is the backward-compatibility pin; it must pass **pre-change**
    and post-change.
  - **Node 5 `test_non_mapping_raw_is_inert_and_not_a_structural_failure`.** Three
    records: `raw: None`, `raw: "text"`, `raw: {"permanentid": "1"}` where the last
    has a top-level `ec_category` but a required-member gap (no top-level or raw
    `ec_product_id`). Assert the first two records are read as flat (same as node 4),
    the page's issue codes contain no `response_missing_required_member` for them,
    and the page is **not** a structural failure. For the third record, assert the
    **existing** per-record required-member behavior (a `page_failed` for the whole
    page and `response_missing_required_member` present) so R4 is pinned both ways.
    Optionally split into two `discover` calls in one node.
  - **Node 6 `test_live_raw_is_not_lifted_and_forbidden_metadata_is_unchanged`.**
    Serve one `fx.live_raw_record(0)` plus one extra `raw` member
    (`"sysurihash": "fixture-hash"`). Assert the persisted
    `request_metadata_json`'s `forbidden_field_presence == [{"record_index": 0,
    "extra_member_count": 1}]` (only `raw`), that `"sysurihash"` and
    `"fixture-hash"` appear in **no** persisted column, and that the normalized
    record carries no new top-level key. (The helper must be invoked through the
    real adapter path; the negative assertions are on `identity_candidates_json`,
    `request_metadata_json`, `error_summary_json`, `category_value_json`.)
  - **Node 7 `test_live_multivalued_category_is_matched_verbatim_after_normalization`.**
    Serve the live record whose `raw.ec_category` is
    `["3d", " 3d > characters"]` against `fx.live_form_taxonomy_payload()`; assert
    `result.filter_status is CategoryFilterValidationStatus.VERIFIED`,
    `result.conditions == ()`, and the persisted `category_value_json` is the
    verbatim list. Then serve a variant whose `raw.ec_category` is
    `["2d", " 2d > textures-materials > lava"]`; assert
    `DiscoveryStatus.CATEGORY_MISMATCH in result.conditions` and
    `result.filter_status is CategoryFilterValidationStatus.MISMATCH` — the existing
    LREQ-EXT-080 semantics, unchanged by the fix.
  - **Node 8 `test_live_nested_record_yields_complete_status_and_no_page_failed`.**
    Serve `PAGE_SIZE` live-nested **distinct** records as one page with
    `total_count=PAGE_SIZE`, `filtered_count=PAGE_SIZE`; assert
    `DiscoveryStatus.PAGE_FAILED not in result.conditions`,
    `result.discovery_status is DiscoveryStatus.COMPLETE`, and
    `result.observations_emitted == PAGE_SIZE`. This is the direct regression pin for
    the live "96 × `response_missing_required_member`" failure mode.
  - **Node 9
    `test_live_nested_record_populates_identity_candidates_without_ec_product_id`.**
    Serve one live record; assert `ec_product_id` is the one-element list
    `["379642"]` and the candidate JSON contains **no** `ec_product_id` entry (a
    non-string is dropped by `_usable_candidate`, not coerced), while
    `identity_resolution_status == RESOLVED` and `asset_identity_key == "379642"`.
    This pins the §2 limitation explicitly rather than silently.
  - **Node 10 `test_normalization_is_deterministic_for_equal_live_records`.** Run the
    same live-nested page through two fresh `discover` calls (two repositories) and
    assert the persisted `category_value_json`, `identity_candidates_json`,
    `identity_resolution_status`, and `category_filter_validation_status` are equal
    row-for-row. No set/dict-ordering dependence is observable.
  - **Node 11
    `tests/test_end_to_end.py::test_acceptance_run_reads_live_shaped_raw_records`.**
    Build the run **inline**: `template_path = pf.write_run_local_template(tmp_path,
    pf.END_TO_END_CATEGORIES)`; a `RecordingCoveoTransport` mapping **every**
    `pf.END_TO_END_CATEGORIES` entry to a `coveo_page` built from
    `pf.live_raw_summary_record(identity=<the scenario identity>, category=<category>)`
    for the identities `pf.END_TO_END_CATEGORIES`' designed populations use
    (`900`/`901`/`902` shared rows and `A1..E2`), with `total_count`/`filtered_count`
    set as the existing scenario does; run through
    `cf.scenario_artifacts`-style options but with `coveo_transport=` the live-shaped
    one and `identity_preflight_min_success_rate=0.0` (so preflight cannot block the
    completed-run assertion). Expected, hand-derived: the run completes
    (`RunStatus` completed or the suite's documented completed value), every
    transport-fed category's persisted discovery status excludes `page_failed`, and
    `repository.count_raw_discovery_observations(...)` equals the number of live
    records served. The node may reuse `cf.scenario_artifacts`'s artifacts and
    **replace only** `scenario.coveo_transport` with a live-shaped transport, so no
    fixture module changes.
    (If the half-converted scenario proves to change pinned preflight/sampling counts,
    the test-author restricts the live-shaped transport to **one** category and
    serves flat pages for the rest, keeping the assertions about that category only;
    the node ID, markers, and matrix values do not change.)

- **Golden vectors / expected values.** All values above are hand-derived from the
  live capture in §1, the frozen mapping rule `1.0.1`, and `match_exact_category`'s
  documented behavior. No golden-vector file is added.

- **Existing nodes that must keep passing unchanged (verified by reading, this
  session):**
  `tests/test_collector.py::test_extra_response_fields_are_ignored_and_missing_identity_fields_stay_missing`
  (`:579-625`; flat + `page_failed` path),
  `tests/test_collector.py::test_response_carrying_a_novel_member_records_forbidden_presence`
  (`:628-663`; the `extra_member_count: 1` assertion),
  `tests/test_collector.py::test_response_reader_never_sources_forbidden_scoring_fields`
  (`:534-576`),
  every `LREQ-EXT-060`/`LREQ-EXT-070`/`LREQ-EXT-080` node (`:794-993`),
  `tests/test_collector.py::test_failed_page_never_becomes_zero_assets` (`:734`),
  `tests/test_collector.py::test_request_body_builder_signature_is_stable` (`:357`),
  `tests/test_collector.py::test_module_imports_without_side_effects` (`:325`),
  and the Chunk 13 acceptance nodes in `tests/test_end_to_end.py`
  (`test_acceptance_run_persists_and_renders`, etc.).

- **Contradiction handling.** If any existing test contradicts the SRS or this plan
  after these changes, the test-author leaves it and reports
  `DISPUTE: <test id> — SRS §x says ...`; it is not silently edited.

## 10. Definition of done (gate)

Chunk 16 has **no `requirements-dependency-map.md` §3 gate**. The gate below is the
dispatch's Definition of Done plus the in-scope Chunk 3 gate bullets this remediation
touches (dependency-map §3 Chunk 3 bullets: structural validation before any record is
read; a failed page is never zero assets; the discovery-only field set is the
allow-list; identity candidates retained from the four fields).

Copied from the dispatch:

- **Full suite green, with a real, countable bullet.**
  `python -m pytest -q` reports `passed, 0 failed` with the real counts written into
  the run log; the count SHALL be stated as the pre-change baseline plus the number of
  new nodes, and the exact command and its verbatim output recorded. If an unrelated
  pre-existing failure exists, it is reported verbatim rather than claimed green.
- **All four validators valid:**
  `python -m niche_scout.tools.validate_traceability`,
  `python -m niche_scout.tools.check_import_boundaries`,
  `python -m niche_scout.tools.check_scope_prohibitions`,
  `python -m niche_scout.tools.check_secrets`.
- **`ruff` clean on changed files** (`ruff format` and `ruff check`), using the
  configuration in `pyproject.toml` (`line-length = 88`, `select = ["E", "F", "I"]`);
  any pre-existing deviation is reported as PARTIAL with the unchanged lines named,
  not silently reformatted.
- **Live-shape discovery succeeds offline.** A page of live-nested records
  (`raw` carrying `permanentid`/`ec_product_id`/`ec_name`/`ec_category`/
  `publisher_name`) is read as assets: `response_missing_required_member` is **absent**
  and the category is **not** `page_failed`.
- **Flat behavior unchanged.** Every flat synthetic fixture and every existing
  collector/acceptance node behaves exactly as before.
- **Only the five discovery members are lifted.** No non-discovery `raw` member is
  copied; the forbidden-member accounting is unchanged in kind (`raw` still counts as
  one extra member).
- **`ec_product_id`'s list shape is recorded, not silently handled.** A node pins
  that it is dropped as a candidate and identity resolves through `permanentid`.
- **No interface file, schema, `validation.py`, `pipeline.py`, `cli.py`, `report.py`,
  metric, or scoring change.**
- Tests were written **before** implementation and failed as missing-implementation
  (no collection/syntax error); the red state is recorded.
- Plan, run log, new node→LREQ entries, and the live-capture provenance are recorded.

## 11. Explicit prohibitions

- **Live network in development or tests.** No test calls the real endpoint; the
  capture in §1 is the only live evidence and is quoted, not re-fetched.
- **No `validation.py` edit and no Chunk 1 signature change.** The fix lives at the
  adapter's record-reading boundary; `collect_identity_candidates`,
  `resolve_canonical_identity`, `match_exact_category`, `normalize_category_path`, and
  every other primitive keep their signatures and semantics.
- **No lift of any `raw` member outside the five-name discovery set.** No
  `sysurihash`/`urihash`/`uniqueId`/`score`/`title`/`excerpt`, and no
  `raw.clickUri`/`raw.uri` handling.
- **No list handling for `ec_product_id`** in this chunk; do not unwrap, join, or
  index the list, and do not coerce it to a string. If a human wants it, it is a
  separate decision with its own LREQ basis and test (§12 Q1).
- **No truthiness fallback for presence.** Never `record.get(k) or raw.get(k)`;
  presence is `in`/`is not None`. No `or 0`, `.get(k, 0)`, or default-value
  substitution (AGENTS.md hard rule 2).
- **No new structural issue code, no change to `is_structural_failure`, no change to
  `_RESPONSE_FIELD_SET_MEMBERS` or `_DISCOVERY_RESPONSE_FIELD_SET`.**
- **No edits to `pipeline.py`, `cli.py`, `database.py`, `report.py`, `metrics.py`,
  `scoring.py`, `sampling.py`, `models.py`, `config.py`, `collector.py`,
  `collector_graphql.py`, `src/niche_scout/tools/**`, `pyproject.toml`, `config/**`,
  `tests/fixtures/pipeline_fixtures.py`, `tests/fixtures/cli_fixtures.py`,
  `tests/fixtures/config_fixtures.py`, or any `Documents/interfaces/*` file.**
- **No schema change and no new persisted column.**
- **No change to the URI trailing-identifier extraction rule (`1.0.1`)** and no claim
  that it is verified. The live capture in hand is **not** a committed redacted
  response; the rule stays inferred and UNVERIFIED.
- **No re-opening of OI-6** (CSRF/session sufficiency); it stays unassigned.
- **No new CLI flag, no new environment variable, no new dependency.**
- **No rename or deletion of an existing pytest node ID or its
  `tests/traceability.json` entry.**
- **Do not edit** `Documents/SRS-lean.md`,
  `Documents/requirements-dependency-map.md`, `AGENTS.md`, `kilo.json(c)`, or
  `.kilo/`.
- **Secrets never appear in source, tests, fixtures, config, or logs.**
- **Do not claim the live run now completes end to end.** This chunk fixes the
  discovery record shape; identity preflight (OI-6) and GraphQL remain the next
  live-path unknowns.

## 12. Open questions and assumptions

### Assumptions (recorded, not silently resolved)

- **A1 — Live capture is quote-fidelity evidence, not a committed artifact.**
  The §1 record shape is human-supplied and redacted; this plan trusts it as the
  operative live shape but does **not** add the response to the repository. Whether a
  committed captured response should exist is **Q4**.
- **A2 — "response-level `clickUri`/`uri`" means record-level (top level).**
  `interfaces/chunk-03.md` §6 and `collect_identity_candidates` read them at the
  top level, matching the live capture. This chunk does not extend them into `raw`.
- **A3 — `raw`'s extra members are not recounted.** Because R1 lifts only the five
  discovery names, `raw` remains the single forbidden member a live record records,
  preserving the `extra_member_count: 1` assertion. If a human later wants `raw`
  treated as an envelope that is not a forbidden member at all, that is a separate
  interface-adjacent decision (it would change `interfaces/chunk-03.md` §6's
  allow-list complement).
- **A4 — `page_index`/`first_result` derive from `numberOfResults`.** `fetch_category_page`
  computes `page_index = first_result // page_size` from the request body
  (`:926-928`); `CoveoPageResponse.page_index` is therefore always `0` in production
  pagination. This is pre-existing and out of scope; it is noted because it makes
  `page_index` unsuitable as a fixture differentiator.

### Open questions (not resolved by this plan; human decision required before relying
on the affected behavior)

1. **`ec_product_id` as a one-element list — unwrap or keep dropping?** The live
   capture shows `ec_product_id: ["379642"]`; `_usable_candidate` drops non-strings,
   so the field contributes no candidate and identity resolves through `permanentid`.
   Options: (a) keep dropping (this plan; no behavior change to the Chunk 1
   primitive, but `ec_product_id` is never a candidate for live records — it is
   retained verbatim in the record for audit); (b) add explicit list handling at the
   adapter's normalization step, with an LREQ basis (candidates are the *values* of
   the field, so a one-element list is arguably the same candidate) and its own test.
   **This plan does neither (b) silently nor without an LREQ basis; it records (a)
   and asks.** SRS §4.1 `LREQ-EXT-060` names the fields, not their response
   container shape.
2. **Does `raw` itself belong in `forbidden_field_presence`?** A live record's five
   lifted fields are the discovery set, but the record also carries a `raw` envelope
   (plus `title`/`excerpt`/`score`/`uniqueId`). Today each such record records
   `extra_member_count: 1`. If a human rules `raw` an envelope rather than a
   forbidden scoring field, the check would need an exemption — an
   `interfaces/chunk-03.md` §6-adjacent change this plan does not make.
3. **Should the live response shape become a committed fixture?** No captured
   response exists in the repository (dependency-map §6.4). The live-shape fixture
   here is a hand-derived literal from the human's capture. If a redacted captured
   response should be committed (and the URI extraction rule verified against it),
   that is a new obligation with an owner.
4. **One live run per category still needs the real taxonomy/facet + OI-6.** This
   chunk's offline gate cannot prove the live end-to-end path; the next live run is
   the human's check, and it may still fail at the identity preflight (OI-6).

## 13. Task breakdown

- [ ] T1 — `test-author`: add the live-shape helpers to
  `tests/fixtures/coveo_discovery.py` (§9), the eleven nodes to
  `tests/test_collector.py`/`tests/test_end_to_end.py`, and the eleven
  `tests/traceability.json` entries. Allow `_read_page` to be a chokepoint
  candidate. (LREQ-EXT-040/050/060/080/090, LREQ-ARCH-030, LREQ-TST-080)
- [ ] T2 — `test-author`: run the suite and record the red state (the live-shape
  nodes fail as missing-implementation; no collection/syntax error). (all)
- [ ] T3 — `impl-deep`: add `_RAW_FALLBACK_FIELD_SET` and
  `_normalize_discovery_record` to `collector_coveo.py` (§7.1) and insert the one
  normalization call in `_read_page`'s record loop before the required-member check.
  (LREQ-EXT-040/060/080)
- [ ] T4 — `impl-deep`: run the suite, the four validators, and `ruff` on the changed
  files; report real counts and output. (all)
- [ ] T5 — lead/reviewer: record the plan, the run log, and the live-capture
  provenance; verify no file outside §6 changed. (all)

## 14. Freeze record

This plan is **Status: FROZEN**. The §9 pytest node IDs are frozen with the plan and
SHALL NOT be renamed by a later change. The chunk creates no interface file and edits
no documented authority file except this plan. The carried-forward obligations from
Chunks 14/15 (OI-6, the URI trailing-identifier extraction rule, the missing persisted
discovery cause, the live end-to-end path) are recorded, not resolved, and are not
claimed here.