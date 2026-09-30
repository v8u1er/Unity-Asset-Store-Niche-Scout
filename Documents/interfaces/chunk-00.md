# Chunk 0 — Project skeleton and contracts (public interface)

Status: VERIFIED
Source plan: `Documents/plans/chunk-00-project-skeleton-and-contracts.md`
Verified at: commit working tree state 2026-09-15; gates `pytest tests/test_contracts.py` (22 passed),
`python -m niche_scout.tools.check_import_boundaries` (exit 0),
`python -m niche_scout.tools.validate_traceability` (exit 0).

This file is the **public contract** other chunks build against. It is not the
full source; read the modules for implementation detail. Everything below is
frozen: downstream chunks may consume these names and semantics, and SHALL NOT
redefine them. Chunk 0 deliberately contains **no SQLite execution, no network
code, and no clock reads**.

---

## 1. Module layout and boundary rules

| Module | Kind | Rule |
|---|---|---|
| `src/niche_scout/models.py` | Pure | Typed structures, enums, constants, serialization only |
| `src/niche_scout/config.py` | I/O | Configuration resolution, TOML/JSON/env reads |
| `src/niche_scout/database.py` | I/O | Schema specification + `Repository` protocol (no execution) |
| `src/niche_scout/metrics.py` | **Pure** | Typed metric inputs/results only |
| `src/niche_scout/scoring.py` | **Pure** | Typed scoring inputs/results only |
| `src/niche_scout/tools/check_import_boundaries.py` | Tooling | AST purity enforcement |
| `src/niche_scout/tools/validate_traceability.py` | Tooling | Bidirectional LREQ traceability enforcement |

**Boundary rules (enforced structurally, LREQ-ARCH-010 / LREQ-ARCH-020):**

- `metrics.py` and `scoring.py` SHALL NOT import `collector`, `collector_coveo`,
  `collector_graphql`, `database`, `pipeline`, `report`, `cli`, `config`, or any
  filesystem/process/network module (`os`, `io`, `sys`, `pathlib`, `shutil`,
  `tempfile`, `subprocess`, `socket`, `sqlite3`, `requests`, `urllib`, `http`,
  `httpx`, `aiohttp`, `json`, `csv`, `pickle`) or clock/logging module
  (`time`, `logging`, `platform`).
- `metrics.py` and `scoring.py` SHALL NOT read the system clock. `datetime` is
  permitted **only** for the `datetime`/`timezone` type imports needed to
  validate that a supplied cutoff is timezone-aware UTC.
- `scoring_cutoff_utc` is always an explicit, timezone-aware UTC input.
- Null, zero, invalid, and unavailable are distinct states. Missing, invalid,
  contradictory, or unavailable values remain unavailable (`None`); they SHALL
  NEVER be silently converted to `0` or `0.0`.
- Determinism (LREQ-ARCH-030): identical normalized inputs, policy versions, and
  configuration SHALL produce structurally and numerically equivalent outputs.
  No unseeded randomness, no platform-dependent hashing, no current-time reads.
- All paths use `pathlib.Path` (LREQ-NFR-050); Python 3.11+.

`src/niche_scout/__init__.py` is a package docstring only and deliberately
exports no symbols. The obsolete root-level `tools/` directory was removed in
favor of `src/niche_scout/tools/`.

---

## 2. Enums and status types (`niche_scout.models`)

All are `class X(str, Enum)`. Values are the canonical wire/DB strings.

```python
class RunStatus(str, Enum):                        # running | completed | failed
class DiscoveryStatus(str, Enum):                  # complete | truncated | page_failed | filter_unverified
                                                   # | category_mismatch | identity_incomplete | request_failed
class IdentityResolutionStatus(str, Enum):         # resolved | unresolved | conflict
class OperationStatus(str, Enum):                  # success | error
class PageViewSemanticsStatus(str, Enum):          # unvalidated | validated_cumulative | contradicted
class GraphQLOperationCorrelationMode(str, Enum):  # explicit_key | validated_position
class IdentityPreflightStatus(str, Enum):          # passed | failed | insufficient
class BreadthSource(str, Enum):                    # verified_total_count | distinct_canonical_discovered_count
class BreadthCompletenessStatus(str, Enum):        # complete | incomplete_estimate
class SamplingBasis(str, Enum):                    # census | deterministic_stratified_sample
class ScoreState(str, Enum):                       # available | partial | unavailable
class EvidenceGrade(str, Enum):                    # strong | moderate | weak | insufficient
class RankabilityStatus(str, Enum):                # not_rankable | provisional | rankable
class CategoryStatus(str, Enum):                   # healthy | degraded | failed
class CategoryFilterValidationStatus(str, Enum):   # verified | mismatch | unverified
```

`CategoryStatus` is internal orchestration state; it is never surfaced as a
discovery status, score state, evidence grade, or rankability status.

### `WarningCode` (SRS Appendix C vocabulary)

```python
class WarningCode(str, Enum):
    DISCOVERY_TRUNCATED = "DISCOVERY_TRUNCATED"
    DISCOVERY_INCOMPLETE = "DISCOVERY_INCOMPLETE"   # Chunk 29; SRS App. C
    DISCOVERY_PAGE_FAILED = "DISCOVERY_PAGE_FAILED"
    DISCOVERY_FILTER_UNVERIFIED = "DISCOVERY_FILTER_UNVERIFIED"
    CATEGORY_MISMATCH = "CATEGORY_MISMATCH"
    IDENTITY_UNRESOLVED = "IDENTITY_UNRESOLVED"
    IDENTITY_CONFLICT = "IDENTITY_CONFLICT"
    IDENTITY_PREFLIGHT_FAILED = "IDENTITY_PREFLIGHT_FAILED"
    GRAPHQL_PRODUCT_ERROR = "GRAPHQL_PRODUCT_ERROR"
    GRAPHQL_PAGE_VIEWS_ERROR = "GRAPHQL_PAGE_VIEWS_ERROR"
    GRAPHQL_ID_MAPPING_MISMATCH = "GRAPHQL_ID_MAPPING_MISMATCH"
    STATE_EXCLUDED = "STATE_EXCLUDED"
    INSUFFICIENT_DEMAND_SAMPLE = "INSUFFICIENT_DEMAND_SAMPLE"
    INSUFFICIENT_RECENT_SAMPLE = "INSUFFICIENT_RECENT_SAMPLE"
    INSUFFICIENT_QUALITY_SAMPLE = "INSUFFICIENT_QUALITY_SAMPLE"
    PAGE_VIEW_SEMANTICS_CONTRADICTED = "PAGE_VIEW_SEMANTICS_CONTRADICTED"
    REFERENCE_SET_SMALL = "REFERENCE_SET_SMALL"
    RANKING_SENSITIVITY_HIGH = "RANKING_SENSITIVITY_HIGH"
    SAMPLE_BASED_SIGNAL = "SAMPLE_BASED_SIGNAL"
```

---

## 3. Constants and policy versions (`niche_scout.models`)

`POLICY_VERSIONS` lives in `niche_scout.config` and is exposed to runs through
`NicheScoutConfig.policy_versions()`.

```python
# Version strings (frozen; §3.1 policy versions)
ENDPOINT_CONTRACT_VERSION = "1.0.0"
IDENTITY_MAPPING_RULE_VERSION = "1.0.0"
SAMPLING_RULE_VERSION = "1.0.0"

# Discovery (§7.2)
MAX_DISCOVERY_RESULTS_PER_CATEGORY = 2000
PAGE_SIZE = 96

# Run and reference set
MIN_CATEGORIES_PER_RUN = 8
STRONG_REFERENCE_CATEGORY_COUNT = 21
MAX_TAXONOMY_AGE_DAYS = 30

# Sampling (§5.1) — fixed in lean v1, NOT independently configurable
ENRICHMENT_SAMPLE_SIZE_PER_CATEGORY = 100
SAMPLE_STRATA = 4
SAMPLE_PER_STRATUM = 25
MIN_USABLE_SAMPLES_PER_STRATUM = 5
# Invariant: ENRICHMENT_SAMPLE_SIZE_PER_CATEGORY == SAMPLE_STRATA * SAMPLE_PER_STRATUM

# Evidence and coverage thresholds
MIN_REQUIRED_COMPONENT_COVERAGE = 0.50
STRONG_COMPONENT_COVERAGE = 0.80

# Age and recent window
MIN_AGE_DAYS_FOR_RATE = 30
RECENT_WINDOW_DAYS = 365

# Quality thresholds
QUALITY_MIN_RATING_COUNT = 5
QUALITY_MIN_ELIGIBLE_ASSETS = 5

# Identity preflight defaults (§4.4)
IDENTITY_PREFLIGHT_MIN_CATEGORIES = 5
IDENTITY_PREFLIGHT_ASSETS_PER_CATEGORY = 2
IDENTITY_PREFLIGHT_MAX_CONFLICT_RATE = 0.0
IDENTITY_PREFLIGHT_MIN_SUCCESS_RATE = 0.90

# Composite weights (§9) — fixed in lean v1, NOT independently configurable
W_D = 0.35
W_C = 0.30
W_R = 0.20
W_Q = 0.15

DEMAND_SUBWEIGHT_PER_ASSET = 0.60
DEMAND_SUBWEIGHT_MEDIAN = 0.40
RECENT_SUBWEIGHT_SHARE = 0.70
RECENT_SUBWEIGHT_AGE = 0.30

SENSITIVITY_POLICIES: dict[str, dict[str, float]] = {
    "balanced":          {"D": 0.35, "C": 0.30, "R": 0.20, "Q": 0.15},
    "demand_heavy":      {"D": 0.50, "C": 0.25, "R": 0.15, "Q": 0.10},
    "competition_heavy": {"D": 0.30, "C": 0.45, "R": 0.15, "Q": 0.10},
}
```

---

## 4. Typed row models and JSON serialization (`niche_scout.models`)

All row models are `@dataclass(frozen=True)` and extend a private UTC-validating
base (`_UtcRecord`) that rejects naive datetimes on construction. Fields are the
exact mandatory fields from SRS-lean §6.1–6.5, in declaration order.

### 4.1 Record classes

- `RunRecord` — 18 fields. Includes `run_id`, `run_started_at_utc`,
  `scoring_cutoff_utc`, `completed_at_utc`, `categories_json`,
  `config_snapshot_json`, `config_sha256`, `taxonomy_version`,
  `taxonomy_captured_at_utc`, `taxonomy_sha256`, `endpoint_contract_version`,
  `identity_mapping_rule_version`, `sampling_rule_version`,
  `page_view_semantics_status`, `graphql_operation_correlation_mode`,
  `identity_preflight_status`, `identity_preflight_summary_json`, `status`.
- `RawDiscoveryObservationRecord` — 16 fields. Includes `observation_id`,
  `run_id`, `category`, `discovery_ordinal`, `asset_identity_key`
  (`Optional[str]`), `identity_candidates_json`, `identity_resolution_status`,
  `identity_resolution_reason`, `category_value_json`,
  `category_filter_validation_status`, `stratum_index`, `is_duplicate`,
  `duplicate_of_observation_id`, `request_metadata_json`, `error_summary_json`,
  `retrieved_at_utc`.
- `SampleMemberRecord` — 12 fields. Includes `run_id`, `category`,
  `asset_identity_key`, `stratum_index`, `stratum_start_ordinal`,
  `stratum_end_ordinal`, `sample_rank_within_stratum`, `sample_is_census`,
  `selection_digest`, `overlap_category_count`, `overlap_sample_percentage`,
  `preflight_selected`.
- `EnrichmentObservationRecord` — 19 fields. Includes `run_id`,
  `asset_identity_key`, `product_detail_status`, `page_views_status`,
  `graphql_id`, `product_id`, `rating_average`, `rating_count`, `review_count`,
  `first_published_date_utc`, `publisher_json`, `category_json`, `state`,
  `product_page_views`, `id_mapping_mismatch`,
  `product_detail_error_summary`, `page_views_error_summary`,
  `request_metadata_json`, `retrieved_at_utc`.
- `CategoryScoreRecord` — 50 fields, covering discovery counts, sample/breadth
  provenance, stratum eligibility coverage, raw metric values, score components,
  `market_opportunity_score`, `score_state`, `evidence_grade`,
  `rankability_status`, warning/reference/sensitivity JSON, and
  `computed_at_utc`. Contains **no** duplicate alias columns such as
  `sample_size`, `demand_usable_count`, `recent_supply_usable_count`, or
  `quality_usable_count`.

Status/state fields on records are stored as `str` (the enum `value`), because
the records mirror SQLite columns; use the enums for logic.

### 4.2 JSON serialization contract

```python
def to_json(instance: Any) -> str: ...
def to_json_dict(instance: Any) -> dict[str, Any]: ...
def from_json(payload: str, row_type: type[T]) -> T: ...
def ensure_utc(value: datetime) -> datetime: ...
```

- Datetime fields serialize to ISO-8601 UTC and round-trip through
  `to_json`/`from_json` without precision loss.
- `None` round-trips as `None`; it is never coerced to `0`/`""`.
- `from_json` validates that the payload is an object of the expected record
  type and that UTC fields remain timezone-aware.

---

## 5. Configuration contracts (`niche_scout.config`)

```python
COVEO_TOKEN_ENV = "NICHESCOUT_COVEO_BEARER_TOKEN"
UNITY_CSRF_TOKEN_ENV = "NICHESCOUT_UNITY_CSRF_TOKEN"
DEFAULT_TOML_PATH = Path("config") / "default.toml"
DEFAULT_CATEGORIES_PATH = Path("config") / "categories.json"
DEFAULT_TAXONOMY_PATH = Path("config") / "category_taxonomy.json"
DEFAULT_DB_PATH = Path("runtime") / "niche_scout.sqlite3"

@dataclass(frozen=True)
class Credentials:
    coveo_token: str
    unity_csrf_token: str
    @property
    def coveo_bearer_token(self) -> str: ...
    def require_for_collection(self) -> None: ...   # raises ValueError if either empty

@dataclass(frozen=True)
class NicheScoutConfig:
    categories_path: Path
    taxonomy_path: Path
    db_path: Path
    max_discovery_results_per_category: int
    page_size: int
    min_categories_per_run: int
    strong_reference_category_count: int
    max_taxonomy_age_days: int
    min_usable_samples_per_stratum: int
    min_age_days_for_rate: int
    recent_window_days: int
    quality_min_rating_count: int
    quality_min_eligible_assets: int
    identity_preflight_min_categories: int
    identity_preflight_assets_per_category: int
    identity_preflight_min_success_rate: float
    source: str = "defaults"          # "cli" | "toml" | "defaults"
    def policy_versions(self) -> dict[str, str]: ...

def load_config(
    cli_args: Optional[dict[str, Any]] = None,
    toml_path: Optional[Path] = None,
) -> NicheScoutConfig: ...

def read_categories(categories_path: Path) -> Sequence[str]: ...
def get_credentials(environ: Optional[Mapping[str, str]] = None) -> Credentials: ...
```

**Precedence (LREQ-CLI-030):** `cli_args` > `toml_path` > in-code defaults
(`IN_CODE_DEFAULTS`). `None` values in `cli_args` are treated as absent so an
unset CLI option cannot shadow TOML or defaults. `source` records which level
supplied the winning value and is not itself configurable.

**Guards (LREQ-SMP-030 prohibition):** unknown/unsupported keys raise
`ValueError`, which is how fixed sampling constants (`SAMPLE_STRATA`,
`SAMPLE_PER_STRATUM`) and composite weights (`w_D`…`w_Q`) are kept
non-configurable. `page_size` is validated against the frozen `PAGE_SIZE = 96`.

**TOML shape:** `load_config` accepts either a top-level table or a
`[niche_scout]` section.

**`read_categories`** accepts a bare JSON array or an object with a
`categories` key, returns category paths as `tuple[str, ...]` in declared order.

**`get_credentials`** reads both env vars, strips whitespace, calls
`require_for_collection()`, and raises `ValueError` **without** including any
secret value in the message. `NicheScoutConfig` has no credential fields, so
credentials cannot leak into `config_snapshot_json` by accident.

**Config files:** `config/categories.json` (8 categories),
`config/category_taxonomy.json`, `config/default.toml`.

**Secrets (LREQ-SEC-020):** `.env` and `.env.*` are gitignored
(`!.env.example` re-included); `.env.example` contains only the two variable
names with `<set-locally>` placeholders. Secrets SHALL NOT be written to source
control, logs, SQLite, or error messages.

---

## 6. Persistence contracts (`niche_scout.database`)

**Chunk 0 defines the specification only.** There is no SQLite engine code, no
connection, no DDL/DML execution, and no database file is created.

```python
SCHEMA_VERSION = "1.0.0"

class Repository(Protocol):
    def insert_run(self, run: RunRecord) -> None: ...
    def update_run_status(self, run_id: str, status: str,
                          completed_at_utc: Optional[datetime] = None) -> None: ...
    def insert_raw_discovery_observations(self, observations: Sequence[RawDiscoveryObservationRecord]) -> None: ...
    def insert_sample_members(self, members: Sequence[SampleMemberRecord]) -> None: ...
    def insert_enrichment_observations(self, observations: Sequence[EnrichmentObservationRecord]) -> None: ...
    def insert_category_scores(self, scores: Sequence[CategoryScoreRecord]) -> None: ...
    def get_run(self, run_id: str) -> Optional[RunRecord]: ...
    def iter_raw_discovery_observations(self, run_id: str, category: str) -> Iterator[RawDiscoveryObservationRecord]: ...
    def get_sample_members(self, run_id: str, category: str) -> Sequence[SampleMemberRecord]: ...
    def get_enrichment_observation(self, run_id: str, asset_identity_key: str) -> Optional[EnrichmentObservationRecord]: ...
    def get_category_scores(self, run_id: str) -> Sequence[CategoryScoreRecord]: ...
```

### Schema specification exports

```python
DDL_STATEMENTS: tuple[str, ...]              # 5 CREATE TABLE + 1 CREATE INDEX
CREATE_TABLE_STATEMENTS: dict[str, str]      # table name -> CREATE TABLE string
TABLE_COLUMNS: dict[str, tuple[str, ...]]    # table name -> column names, in order
TABLE_PRIMARY_KEYS: dict[str, tuple[str, ...]]
TABLE_INDEXES: dict[str, str]                # index name -> CREATE INDEX string
```

### Table primary keys (invariants)

| Table | Primary key |
|---|---|
| `runs` | `run_id` |
| `raw_discovery_observations` | `observation_id` |
| `sample_members` | `(run_id, category, asset_identity_key)` |
| `enrichment_observations` | `(run_id, asset_identity_key)` |
| `category_scores` | `(run_id, category)` |

Index: `idx_raw_discovery_observations_run_category_ordinal` on
`raw_discovery_observations (run_id, category, discovery_ordinal)`.

Column types use `TEXT`/`INTEGER`/`REAL`; UTC fields are `TEXT` ISO-8601. The
module validates its own specification at import (`_validate_specification`), so
a drift between DDL text, `TABLE_COLUMNS`, and `TABLE_PRIMARY_KEYS` fails fast.

---

## 7. Pure module stubs

### `niche_scout.metrics`

```python
@dataclass(frozen=True, slots=True)
class MetricInput:
    scoring_cutoff_utc: datetime                       # must be tz-aware UTC, else ValueError
    page_view_semantics_status: PageViewSemanticsStatus = PageViewSemanticsStatus.UNVALIDATED

@dataclass(frozen=True, slots=True)
class MetricResult:
    value: float | None
    usable_sample_count: int
    eligible_population_count: int
    eligibility_coverage: float | None
    unavailable_reason: str | None = None

@dataclass(frozen=True, slots=True)
class RawMetricBundle:
    demand_per_asset_raw: float | None = None
    demand_median_raw: float | None = None
    breadth_raw: float | None = None
    recent_share_raw: float | None = None
    median_age_raw: float | None = None
    quality_raw: float | None = None
```

### `niche_scout.scoring`

```python
@dataclass(frozen=True, slots=True)
class ScoringInput:
    scoring_cutoff_utc: datetime                       # must be tz-aware UTC, else ValueError
    demand: float | None = None
    competition: float | None = None
    recent_supply: float | None = None
    quality: float | None = None

@dataclass(frozen=True, slots=True)
class ScoreResult:
    market_opportunity_score: float | None
    score_state: ScoreState
    component_d: float | None = None
    component_c: float | None = None
    component_r: float | None = None
    component_q: float | None = None
    available_component_count: int = 0
    rankability_status: RankabilityStatus = RankabilityStatus.NOT_RANKABLE
    evidence_grade: EvidenceGrade = EvidenceGrade.INSUFFICIENT

@dataclass(frozen=True, slots=True)
class SensitivityResult:
    top_3_stability: float | None = None
    top_5_stability: float | None = None
    maximum_score_delta: float | None = None
    maximum_rank_displacement: int | None = None
    warning: bool = False
```

`MetricInput` and `ScoringInput` both validate in `__post_init__` that
`scoring_cutoff_utc` is timezone-aware UTC and raise `ValueError` otherwise.
Later chunks add functions over these structures; the structures themselves are
frozen.

---

## 8. Verification tooling

- `python -m niche_scout.tools.check_import_boundaries` → exit 0, prints
  `Import boundaries valid for metrics.py, scoring.py`. Enforces the forbidden
  import set and detects clock-read calls via AST.
- `python -m niche_scout.tools.validate_traceability` → exit 0, prints
  `Traceability valid: 7 Chunk 0 requirements mapped, 22 matrix nodes, 89 defined LREQ IDs`.
  Checks both directions: every referenced LREQ is defined in SRS Appendix B
  ranges, and every Chunk 0 requirement has ≥1 mapped test. Also fails on
  marker/matrix mismatch, marker without matrix entry, and orphan matrix nodes.

**Traceability is bidirectional and fails loudly.** Removing a matrix entry for
a marked test makes the validator exit 1
(`Tests with lreq markers but no matrix entry: ...`). Markers are registered in
`pyproject.toml`:
`"lreq(requirement_id): trace an analytical test to an individual LREQ requirement"`.

`tests/traceability.json` maps fully-qualified pytest node IDs (base node ID for
parameterized tests) to arrays of individual `LREQ-*` strings:

```json
{
  "tests/test_contracts.py::test_models_import": ["LREQ-ARCH-010"],
  "tests/test_contracts.py::test_pure_boundary_no_clock": ["LREQ-ARCH-020"],
  "tests/test_contracts.py::test_determinism_contract": ["LREQ-ARCH-030"],
  "tests/test_contracts.py::test_coveo_endpoint_contract": ["LREQ-EXT-010"],
  "tests/test_contracts.py::test_taxonomy_contract": ["LREQ-EXT-020"],
  "tests/test_contracts.py::test_coveo_retry_contract": ["LREQ-EXT-100"],
  "tests/test_contracts.py::test_graphql_endpoint_contract": ["LREQ-GQL-010"],
  "tests/test_contracts.py::test_credentials_contract": ["LREQ-SEC-010"],
  "tests/test_contracts.py::test_secrets_redaction_contract": ["LREQ-SEC-020"],
  "tests/test_contracts.py::test_preflight_constants_contract": ["LREQ-ID-030"],
  "tests/test_contracts.py::test_sampling_constants_contract": ["LREQ-SMP-030"],
  "tests/test_contracts.py::test_census_model_contract": ["LREQ-SMP-040"],
  "tests/test_contracts.py::test_selection_digest_contract": ["LREQ-SMP-060"],
  "tests/test_contracts.py::test_age_calculation_contract": ["LREQ-MET-020"],
  "tests/test_contracts.py::test_config_precedence_contract": ["LREQ-CLI-030"],
  "tests/test_contracts.py::test_type_hints_and_docstrings": ["LREQ-NFR-040"],
  "tests/test_contracts.py::test_platform_pathlib_contract": ["LREQ-NFR-050"],
  "tests/test_contracts.py::test_quality_workflow_contract": ["LREQ-NFR-060"],
  "tests/test_contracts.py::test_formula_test_conventions": ["LREQ-TST-010"]
}
```

Three additional nodes are also mapped (all marked `LREQ-ARCH-010` / `LREQ-NFR-050`):
`test_status_values_and_mandatory_fields_are_typed`,
`test_repository_protocol_and_schema_specification`,
`test_json_round_trip_for_all_records`.

---

## 9. Fixtures available to downstream chunks

`tests/fixtures/config_fixtures.py` (exported via `tests/fixtures/__init__.py`):

- Default TOML configuration dict
- Custom TOML configuration fixture string
- Mock CLI argument dictionaries overriding specific keys
- Taxonomy JSON fixture with valid headers and a sample category tree
- Mock environment dict containing test credential variables

Per the project rules, analytical tests SHALL use fixtures and golden vectors
only; live network calls are forbidden, and `tests/traceability.json` must stay
in sync with `@pytest.mark.lreq` markers.

---

## 10. What downstream chunks must NOT expect from Chunk 0

- No SQLite implementation, connection, DDL execution, or savepoint/transaction
  behavior — that is Chunk 2.
- No taxonomy/identity validation logic, no exact category-path matching, no
  canonical identity parsing — that is Chunk 1.
- No Coveo/GraphQL HTTP clients, retry loops, or pagination — Chunks 3 and 5.
- No canonical population construction or SHA-256 sample selection — Chunk 4A.
- No metric/scoring function bodies — Chunks 7A/7B, 8, 9A/9B.
- No pipeline orchestration, report rendering, or CLI parsing — Chunks 10, 11, 12.

## 11. Chunk 24 revision — sampling version, stride, and schema (2026-09-28)

Operator-authorized remediation (chunk-24; authoritative delta:
`Documents/interfaces/chunk-24.md`).

- `SAMPLING_RULE_VERSION` is `"2.0.0"` (was `"1.0.0"`); the sampling-rule version is
  an input to the per-category stratum offset.
- `SAMPLE_STRATA` (4) is the systematic ordinal-stratum **stride**, not a count of
  contiguous blocks.
- `SCHEMA_VERSION` is `"1.2.0"` (was `"1.1.0"`); `sample_members` carries
  `stratum_offset`/`stratum_stride` in place of the ordinal interval columns.
