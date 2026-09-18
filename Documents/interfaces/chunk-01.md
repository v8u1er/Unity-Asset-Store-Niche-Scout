# Chunk 1 — Pure taxonomy, identity, and response validation (public interface)

Status: VERIFIED
Source plan: `Documents/plans/chunk-01-pure-taxonomy-identity-and-response-validation.md`
Verified at: working tree state 2026-09-16; gates `python -m pytest tests/test_validation.py -q`
(22 passed, exit 0), `python -m pytest tests/test_identity.py -q` (25 passed, exit 0),
`python -m niche_scout.tools.check_import_boundaries` (exit 0),
`python -m pytest tests -q --collect-only` (75 tests, exit 0).

This file is the **public contract** other chunks build against. It is not the
full source; read `src/niche_scout/validation.py` for implementation detail.
Everything below is frozen: downstream chunks may consume these names and
semantics, and SHALL NOT redefine them. Chunk 1 is **pure**: no filesystem,
database, network, process, CLI, or system-clock access, and no import of any
I/O module of this package.

**This contract is structural only.** None of these functions decides whether a
value is *usable for a metric*; published-state eligibility applied to metric
inputs, UTC/date normalization for metrics, future-date rejection,
finite/non-negative checks, age thresholds, and page-view eligibility ranges are
metric-eligibility semantics owned by **Chunk 7A**. Adapter integration of these
primitives (real Coveo and GraphQL responses) is completed by **Chunks 3 and 5**.

---

## 1. Module and boundary rules

| Module | Kind | Rule |
|---|---|---|
| `src/niche_scout/validation.py` | **Pure** | Taxonomy, identity, category-matching, response-structure, and redaction primitives only |

- `validation.py` SHALL NOT import `collector`, `collector_coveo`,
  `collector_graphql`, `database`, `pipeline`, `report`, `cli`, `config`,
  `metrics`, or `scoring`, and SHALL NOT import any filesystem, process, network,
  or clock module. Verified structurally by
  `tests/test_validation.py::test_structural_validation_does_not_decide_metric_eligibility`
  (lines 989–1040), which asserts the intersection with the forbidden set is
  empty and that `check_import_boundaries.clock_violations(tree) == []`.
- `json` **is** imported by `validation.py` and this is correct: the `json`
  prohibition is scoped to `metrics.py`/`scoring.py`
  (`check_import_boundaries.PURE_MODULES`; `interfaces/chunk-00.md` §1), and
  `summarize_validation_issues` is required to emit a redacted JSON summary.
  `python -m niche_scout.tools.check_import_boundaries` reports only
  `Import boundaries valid for metrics.py, scoring.py`.
- Determinism: identical inputs plus an identical `mapping_rule_version` produce
  structurally equivalent outputs. Candidate order is input order and issue order
  is deterministic (member name, then code precedence).
- Null, zero, invalid, and unavailable stay distinct in every result. A
  missing/malformed/wrong-typed/unparseable value yields `None` plus an issue —
  never `0`, `0.0`, `""`, `[]`, or `False` as a sentinel.
- `models.py` was **not** modified. `IdentityResolutionStatus`,
  `CategoryFilterValidationStatus`, `OperationStatus`,
  `GraphQLOperationCorrelationMode`, `DISCOVERY`/`WarningCode` enums,
  `IDENTITY_MAPPING_RULE_VERSION`, `MAX_TAXONOMY_AGE_DAYS`, `ensure_utc`,
  `to_json_dict`, and `to_json` are all consumed from Chunk 0 as frozen.

---

## 2. Constants and vocabularies (`niche_scout.validation`)

```python
TAXONOMY_REQUIRED_HEADER_FIELDS: tuple[str, ...] = (
    "schema_version", "captured_at_utc", "source_url", "template_sha256",
)
TAXONOMY_INVENTORY_FIELDS: tuple[str, ...] = ("canonical_category_paths", "canonical_paths")
TAXONOMY_ENTRY_PATH_FIELDS: tuple[str, ...] = ("path", "canonical_path", "category_path")
RESPONSE_CONTAINER_KINDS: tuple[str, ...] = ("mapping", "list", "identity", "str", "int", "float", ...)
SECONDS_PER_DAY = 86400.0
```

`__all__` exports exactly the names in sections 3–5 below plus these constants.

---

## 3. Typed result and issue structures

All are `@dataclass(frozen=True, slots=True)`.

```python
@dataclass(frozen=True, slots=True)
class ValidationIssue:
    code: str                      # stable machine-readable code, e.g. "taxonomy_missing_header"
    message: str                   # redacted, secret-free, no raw response bodies
    context: dict[str, Any]        # JSON-safe, redacted (field name, counts, path)
    def to_json(self) -> str: ...  # deterministic ordering via models.to_json_dict

@dataclass(frozen=True, slots=True)
class TaxonomyValidationResult:
    is_valid: bool
    is_fresh: bool | None          # None when freshness is undeterminable (never False-by-default)
    status: str                    # "valid" | "missing_headers" | "malformed" | "stale"
                                   # | "missing_categories" | "invalid_capture_timestamp"
    missing_header_fields: tuple[str, ...]
    missing_requested_categories: tuple[str, ...]
    age_days_exact: float | None   # None when captured_at_utc is unusable
    payload: object                # the validated object (carried for stage reporting)
    issues: tuple[ValidationIssue, ...]

@dataclass(frozen=True, slots=True)
class IdentityCandidate:
    source_field: str              # "ec_product_id" | "permanentid" | "clickUri" | "uri"
    raw_value: str                 # non-empty, retained verbatim
    canonical_value: str | None    # None when the candidate is unparseable
    parse_failure_reason: str | None

@dataclass(frozen=True, slots=True)
class IdentityResolutionResult:
    canonical_identity_key: str | None
    status: IdentityResolutionStatus           # resolved | unresolved | conflict
    reason: str | None                         # redacted; non-None for unresolved/conflict
    candidates: tuple[IdentityCandidate, ...]  # every non-empty candidate, in input order
    included_in_canonical_denominator: bool
    included_in_enrichment_set: bool
    mapping_rule_version: str
    issues: tuple[ValidationIssue, ...]

@dataclass(frozen=True, slots=True)
class CategoryMatchResult:
    matched_path: str | None
    status: CategoryFilterValidationStatus     # verified | mismatch | unverified
    matched_value_count: int
    unmatched_values: tuple[str, ...]
    issues: tuple[ValidationIssue, ...]

@dataclass(frozen=True, slots=True)
class GraphQLIdentityComparisonResult:
    matches_requested_identity: bool
    id_mapping_mismatch: bool
    reason: str | None
    compared_aliases: tuple[tuple[str, str], ...]
    issues: tuple[ValidationIssue, ...]

@dataclass(frozen=True, slots=True)
class StateEligibilityAnnotation:
    state_value: str | None
    is_published: bool
    state_excluded: bool                       # present but not "published"
    state_unknown: bool                        # missing/null/unparsable
    remains_in_discovered_breadth: bool        # always True (annotation only)

@dataclass(frozen=True, slots=True)
class StructuralValidationResult:
    is_valid: bool
    expected_shape: str
    actual_shape: str | None
    issues: tuple[ValidationIssue, ...] = ()
```

`IdentityCandidate.canonical_value` is `None` for an unparseable candidate, which
then never contributes a guessed value. For `IdentityResolutionResult`,
`canonical_identity_key` is non-`None` **only** for `resolved`; a `conflict` or
`unresolved` record always carries a non-`None` `reason`, is excluded from both
the canonical denominator and the enrichment set, and is never returned as an
ordinary asset.

`StructuralValidationResult` reports a failed member through `issues`; no value
is fabricated in its place.

---

## 4. Public functions

```python
def redact_value(value: object) -> str: ...
def summarize_validation_issues(
    issues: Sequence[ValidationIssue], *, max_context_chars: int = 256
) -> str: ...            # returns a redacted JSON summary for error_summary_json

def validate_taxonomy_structure(payload: object) -> TaxonomyValidationResult: ...
def validate_taxonomy_freshness(
    payload: object, *, reference_utc: datetime,
    max_taxonomy_age_days: int = MAX_TAXONOMY_AGE_DAYS,
) -> TaxonomyValidationResult: ...
def validate_requested_categories(
    payload: object, requested_categories: Sequence[str]
) -> TaxonomyValidationResult: ...
def validate_taxonomy(
    payload: object, *, requested_categories: Sequence[str], reference_utc: datetime,
    max_taxonomy_age_days: int = MAX_TAXONOMY_AGE_DAYS,
) -> TaxonomyValidationResult: ...

def normalize_category_path(value: str) -> str: ...
def taxonomy_path_set(payload: object) -> frozenset[str]: ...
def match_exact_category(
    category_value: object, taxonomy_paths: Container[str]
) -> CategoryMatchResult: ...
def discovery_status_for_category_status(
    status: CategoryFilterValidationStatus
) -> DiscoveryStatus | None: ...

def collect_identity_candidates(record: Mapping[str, object]) -> tuple[IdentityCandidate, ...]: ...
def canonicalize_identity_candidate(
    raw_value: str, *, mapping_rule_version: str = IDENTITY_MAPPING_RULE_VERSION
) -> str | None: ...
def resolve_canonical_identity(
    record: Mapping[str, object], *,
    mapping_rule_version: str = IDENTITY_MAPPING_RULE_VERSION,
) -> IdentityResolutionResult: ...

def compare_graphql_identity_aliases(
    requested_identity: str, aliases: Mapping[str, object], *,
    mapping_rule_version: str = IDENTITY_MAPPING_RULE_VERSION,
) -> GraphQLIdentityComparisonResult: ...
def annotate_state_eligibility(state_value: object) -> StateEligibilityAnnotation: ...

def validate_response_shape(
    payload: object, *, expected_shape: str,
    required_members: Sequence[str] = (),
    field_types: Mapping[str, type | tuple[type, ...]] | None = None,
) -> StructuralValidationResult: ...
```

### 4.1 Identity mapping rule `1.0.1` (normative for LREQ-EXT-060 canonicalization)

- `ec_product_id` and `permanentid`, if non-empty: trim whitespace, then compare
  directly — numerically when both parse as integers, else as strings. Both are
  treated as **already canonical**; no further transformation is applied.
- `clickUri` / `uri`, if non-empty: the trailing numeric identifier after the
  final `-` in the URL's last path segment (query string and fragment ignored).
  A value that does not fit that pattern contributes **nothing** — never a
  guessed or partial identifier.
- `resolve_canonical_identity` compares all successfully-derived candidates: all
  equal → `resolved` with that value as `asset_identity_key`; any disagreement →
  `conflict`; nothing derivable → `unresolved`.

**Caveat Chunk 3 must verify (plan RN-1, not a defect in this chunk).** The URI
trailing-numeric-segment rule is *inferred* from the retired parent-SRS fragment
plus general Unity Asset Store URL conventions. It is **NOT** verified against a
real captured Coveo response. Chunk 3 (the `LREQ-EXT-060` integration completion
chunk) SHALL sanity-check this rule against real redacted fixtures before
treating it as final; `IDENTITY_MAPPING_RULE_VERSION = "1.0.1"` exists precisely
so a correction is cheap. Consumers SHALL branch on
`IdentityResolutionResult.mapping_rule_version` rather than assuming `1.0.0`
semantics silently.

**Satisfaction condition of the caveat above — explicitly RELAXED by human
ruling (supersedes the unconditional "SHALL sanity-check … before treating it as
final" obligation as written above).** That obligation was previously
unconditional and is now discharged by **scope declaration**: the rule remains
*unverified* and the verification is **deferred to a future capture**, rather
than performed. Accepting deferral as discharge means "before treating it as
final" is read as a bar on **asserting the rule is verified**, not as a bar on
publishing it as an explicitly-unverified inference — the sentence names no
verifying artifact and sets no deadline. The consequence is recorded precisely:
the extraction half of rule `1.0.1` is **UNVERIFIED**, and no artifact in this
repository — this contract, an adapter interface, a plan, a docstring, a
`mapping_rule_version` stamp, or a test name — may state or imply that it was
verified against a real Coveo response.

**The exposure deferral leaves open.** "Before treating it as final" protects
against an inferred extraction pattern silently producing wrong
`asset_identity_key` values for every record. Deferral does **not** remove that
exposure — it accepts it for the present rule version. A wrong pattern is
currently surfaced only by whatever causes *disagreement* among the candidate
sources: an extraction that yields a plausible but incorrect identifier
agreeing across the URI fields while the explicit `ec_product_id`/`permanentid`
agree with each other only *rescues* the record into `resolved` under
`LREQ-EXT-070`'s all-equal branch, and is not detected. This exposure remains
open until the deferred verification is performed; the relaxation does not
assert it away.

**What `1.0.1` is.** Its only substantive change from `1.0.0` is the removal of
an adapter-side suffix-tolerant comparison that was never part of this contract
at any version: a URI-derived identifier was once accepted whenever it was a
*suffix* of (or otherwise loosely matched) the explicit anchor. Under `1.0.1`
such a case is a **`conflict`**, not an agreement. The extraction rule itself is
**unchanged** by `1.0.1` — not strengthened, not weakened, and **not verified**.
Consumers SHALL branch on `IdentityResolutionResult.mapping_rule_version` rather
than assume the older tolerant comparison. Nothing above blesses the inferred
extraction rule.

### 4.2 Structural issue codes emitted

`taxonomy_missing_header`, `taxonomy_missing_path_inventory`,
`taxonomy_invalid_path_entry`, `taxonomy_invalid_categories_shape`,
`taxonomy_duplicate_path`, `taxonomy_invalid_capture_timestamp`,
`taxonomy_stale_capture`, `taxonomy_future_capture`,
`taxonomy_missing_requested_category`, `category_unverified`,
`category_mismatch`, `identity_conflict`, `identity_unresolved`,
`identity_candidate_unparseable`, `response_missing_required_member`,
`response_null_required_member`, `response_wrong_scalar_type`,
`response_wrong_container_kind`, `response_missing_identity`.

Issue order is deterministic: primary key is the reported member/field, secondary
key is the code's position in the module's shape precedence, ties keep insertion
order.

---

## 5. Behavioral contracts downstream chunks may rely on

- **Structural only** — every function classifies structure (shape, type,
  presence, alias agreement, path equality, candidate canonicalizability). None
  decides metric usability; that is Chunk 7A.
- **Purity** — no I/O, no clock, no randomness. `reference_utc` is always an
  explicit timezone-aware UTC argument and is normalized through
  `models.ensure_utc`. Which concrete timestamp an orchestration-layer caller
  passes is a Chunk 10/12 decision, deliberately not fixed by this chunk (§3.2
  step 2 runs before step 3 creates `run_started_at_utc`).
- **Taxonomy freshness boundary is inclusive**: `age_days_exact <=
  max_taxonomy_age_days` (30) is fresh; `age > 30` or a future capture is stale.
  `age_days_exact == (reference_utc - captured_at_utc).total_seconds() / 86400`.
  A naive or unparsable `captured_at_utc` is `"invalid_capture_timestamp"` with
  `is_fresh = None`, never treated as fresh.
- **Exact category matching is full-segment equality**, case-insensitive in
  comparison and case-preserving in the reported `matched_path`. `Parent` never
  matches `Parent/Child` and vice versa. A multi-valued value with one exact
  match is `verified`; usable values with no match are `mismatch`; no usable
  value (`null`, absent, wrong-typed) is `unverified`.
- **`discovery_status_for_category_status`** maps `unverified` →
  `DiscoveryStatus.FILTER_UNVERIFIED` and `mismatch` →
  `DiscoveryStatus.CATEGORY_MISMATCH`; `verified` maps to `None` (a verified
  filter is not a failure). Producing the warning and preventing a rankable
  result is Chunks 10/12.
- **`annotate_state_eligibility`** is an annotation, not a decision:
  `remains_in_discovered_breadth` is always `True` and the result exposes no
  D/R/Q eligibility attribute.
- **Redaction** — `ValidationIssue.message`/`context`, `redact_value`, and
  `summarize_validation_issues` never include credential values,
  `Authorization` headers, CSRF tokens, cookies, or full response bodies.
- **No fabricated zeros or defaults** — in particular a `conflict`/`unresolved`
  identity never becomes an ordinary asset, and a missing category never becomes
  an empty category.

---

## 6. What downstream chunks must NOT expect from Chunk 1

- No network collection, HTTP client, request construction, pagination, retry, or
  rate limiting — Chunks 3 and 5.
- No persisted `identity_resolution_status`, denominator/enrichment-set
  enforcement at runtime, or duplicate marking — Chunks 3, 4B, 6B.
- No canonical population construction, ordinal ordering, strata, or sampling —
  Chunk 4A.
- No SQLite persistence or transactions — Chunk 2.
- No metric eligibility semantics (published-state eligibility for D/R/Q,
  UTC/date normalization for metrics, future-date rejection, finite/non-negative
  checks, age thresholds, page-view eligibility) — **Chunk 7A**.
- No run rejection, exit-code behavior, or report retention — Chunks 10 and 12.
- No `LREQ-EXT-100` behavior: its matrix row names supporting chunk `Chunk 0`
  only, so it is outside this chunk's scope and appears nowhere in Chunk 1.
- **Traceability-validator widening is NOT done** — `tools/validate_traceability.py`
  remains Chunk 0-scoped and deliberately untouched by Chunk 1 (plan R-3); its
  required-set widening is **Chunk 13** (`LREQ-NFR-060`). Until Chunk 13 lands,
  gate-verifier must manually cross-check the plan's LREQ table against the
  actual `@pytest.mark.lreq` markers.

---

## 7. Requirement ownership roles recorded by this chunk

Primary owner: `LREQ-EXT-020`, `LREQ-EXT-070`. Supporting contract chunk:
`LREQ-EXT-010`, `LREQ-EXT-030`, `LREQ-EXT-040`, `LREQ-EXT-050`,
`LREQ-EXT-060`, `LREQ-EXT-080`, `LREQ-EXT-090`, `LREQ-GQL-010`,
`LREQ-GQL-020`, `LREQ-GQL-030`, `LREQ-GQL-040`, `LREQ-GQL-050`,
`LREQ-GQL-060`, `LREQ-GQL-070`, `LREQ-ID-020`, `LREQ-SMP-010`,
`LREQ-MET-010`, `LREQ-CLI-040`, `LREQ-TST-030`.

Chunk 1 authors tests for every matrix row above **except** `LREQ-GQL-020`,
`LREQ-GQL-030` (pure protocol/query-construction and response-correlation
concerns owned by Chunk 5), and `LREQ-EXT-010`, `LREQ-EXT-030`, `LREQ-EXT-040`,
`LREQ-CLI-040` (their required tests belong to Chunks 3 and 12). This is resolved
decision R-1 and was verified two-directionally at the gate.

Test modules: `tests/test_validation.py` (22 marked tests), `tests/test_identity.py`
(26 marked tests), fixtures in `tests/fixtures/validation_fixtures.py`
(`tests/fixtures/__init__.py` re-exports it). All 48 base node IDs have exactly
matching `tests/traceability.json` entries.

> **Dated correction (2026-09-18).** The figures in this paragraph were
> `test_identity.py` **25** and the pair total **47**. Both were measured and
> found wrong; they are superseded by **26** and **48** above. Nothing is
> deleted — the superseded figures are retained here in this note.
>
> Method. `python -m pytest tests/test_identity.py tests/test_validation.py
> --collect-only -q` returns **48 collected node lines**; python `-m pytest
> --collect-only` (via `subprocess`, `-p no:cacheprovider`) plus AST parsing of
> the two modules yields **26** distinct base node IDs in `tests/test_identity.py`
> and **22** in `tests/test_validation.py`; `48 = 26 + 22`. `tests/traceability.json`
> has a matching entry for all 48 (0 missing).
>
> Unit discipline — three different units live in this module and the original
> figures did not distinguish them. In `tests/test_identity.py`: **26** marker
> decorator lines, **26** distinct base node IDs, **26** `test_` functions, plus
> **1** further occurrence of the literal string `@pytest.mark.lreq` inside the
> module docstring at line 3 (which is not a marker and is excluded from the
> count above). In `tests/test_validation.py`: **23** marker decorator lines,
> **22** distinct base node IDs, **22** `test_` functions, plus **1** further
> docstring occurrence at line 3, and additionally lines 1187–1188 form a
> two-marker stack on a single `test_` function, which is the sole cause of the
> 23-vs-22 gap. The `22` already written in this file refers to distinct base
> node IDs and remains correct.

> **Dated correction (2026-09-18), provenance note.** The `test_identity.py`
> marker counted at `tests/test_identity.py:354`
> (`test_uri_derived_proper_suffix_of_anchor_is_conflict`, `LREQ-EXT-070`) is the
> boundary-case test added when the suffix-tolerance branch in
> `collector_coveo.py::_identity_candidates_agree` was removed and
> `identity_mapping_rule_version` advanced to `1.0.1`. It is the delta that
> carried `test_identity.py` from 25 to 26 and the pair total from 47 to 48; it
> asserts the strict-equality reading of `LREQ-EXT-070` that this file's
> identity-mapping-rule section states at lines 222–224.
