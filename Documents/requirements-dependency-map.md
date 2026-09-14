# Requirement dependency map and implementation chunk plan

Source analyzed:

`C:\Users\<redacted-user>\Documents\Python Projects\Unity Asset Store Niche Scout\Documents\SRS-lean.md`

The SRS contains **89 individually defined `LREQ-*` requirements**. The wildcard rows in Appendix B are traceability groupings, not additional requirements.

## Interpretation rules

- Dependencies below are **implementation dependencies inferred from the SRS data flow**. The SRS does not declare an explicit dependency graph.
- `Pure` means the requirement should be implemented in a deterministic function with no network, clock, database, or file access.
- `I/O` identifies network, filesystem, database, process, or orchestration behavior.
- `Test type` follows the SRS traceability matrix and expands it into the likely test mechanism.
- `—` means no direct LREQ prerequisite; foundational project setup may still be required.

---

# 1. Requirement dependency map

## Architecture

| REQ ID | Module | Depends on LREQs | Pure/I/O | Test type | Edge cases |
|---|---|---|---|---|---|
| LREQ-ARCH-010 | `models.py`, `metrics`, `scoring` | — | Pure boundary | Architecture/import test; analytical tests | Typed structures only; no imports from collector/database/report/CLI; no file or network I/O |
| LREQ-ARCH-020 | `metrics`, `scoring` | LREQ-ARCH-010 | Pure | Determinism/unit test | No system-clock reads; timestamps must be supplied |
| LREQ-ARCH-030 | `metrics`, `scoring`, `pipeline` | LREQ-ARCH-010, LREQ-ARCH-020 | Pure plus orchestration | Repeated-input deterministic test; end-to-end test | Same inputs, policy versions, and configuration must produce byte-equivalent logical results |

## Coveo discovery and external collection

| REQ ID | Module | Depends on LREQs | Pure/I/O | Test type | Edge cases |
|---|---|---|---|---|---|
| LREQ-EXT-010 | `collector.py`, `config.py` | LREQ-SEC-010 | Network I/O | HTTP fixture/mock test | Endpoint, headers, taxonomy template, and selected-category facet must match parent SRS |
| LREQ-EXT-020 | `config.py`, `validation.py` | — | File I/O at boundary; pure validation core | Taxonomy fixture/validation test | Missing, malformed, stale taxonomy; requested category absent; invalid hash or metadata |
| LREQ-EXT-030 | `collector.py` | LREQ-EXT-010 | Network I/O | Request-shape fixture test | Reject accidental `q` or `query`; prevent keyword contamination |
| LREQ-EXT-040 | `collector.py`, `validation.py` | LREQ-EXT-010 | Network I/O plus pure response validation | Request/response fixture test | Missing identity fields; forbidden scoring fields accidentally used; extra response fields |
| LREQ-EXT-050 | `collector.py` | LREQ-EXT-010, LREQ-EXT-020, LREQ-EXT-030, LREQ-EXT-040 | Network I/O | Pagination mock/fixture test | Verified `totalCount`, natural terminal page, truncation, failed page, filter uncertainty, category mismatch, zero results |
| LREQ-EXT-060 | `validation.py`, `collector.py` | LREQ-EXT-040, LREQ-EXT-050 | Pure response normalization plus network caller | Identity fixture test | Multiple identity aliases, URI fallback, empty candidates, versioned canonical mapping |
| LREQ-EXT-070 | `validation.py` | LREQ-EXT-060 | Pure | Identity unit test | Conflicting candidates, unresolved candidates, exclusion from denominator and enrichment |
| LREQ-EXT-080 | `validation.py` | LREQ-EXT-020, LREQ-EXT-050, LREQ-EXT-060 | Pure | Taxonomy/category fixture test | Parent versus child path, exact match, scalar category, multi-valued category |
| LREQ-EXT-090 | `collector.py`, `validation.py`, `pipeline.py` | LREQ-EXT-050, LREQ-EXT-070, LREQ-EXT-080 | Orchestration/I/O | Failure-state integration test | Warning generation; competition not fully rankable; failed page must not become zero assets |
| LREQ-EXT-100 | `collector.py` | LREQ-EXT-010, LREQ-SEC-010 | Network I/O | Retry/backoff mock test | Retry `429` and `5xx`; do not endlessly retry authentication, CSRF, malformed-request, or authorization errors |

## GraphQL enrichment

| REQ ID | Module | Depends on LREQs | Pure/I/O | Test type | Edge cases |
|---|---|---|---|---|---|
| LREQ-GQL-010 | `collector.py` | LREQ-EXT-060, LREQ-SEC-010 | Network I/O | GraphQL request fixture | Two operations; same canonical identity; ProductDetail and ProductPageViews; adapter is independently testable with a typed identity fixture |
| LREQ-GQL-020 | `collector.py` | LREQ-GQL-010 | Network I/O | Query-shape fixture test | Required aliases, ratings, dates, state, category, publisher, and page-view scalar |
| LREQ-GQL-030 | `collector.py`, `validation.py` | LREQ-GQL-010 | Network I/O plus pure correlation logic | Correlation fixture test | Reversed response order; operation name or validated correlation key required |
| LREQ-GQL-040 | `collector.py`, `validation.py` | LREQ-GQL-030 | Network I/O | Response-status fixture test | HTTP failures, GraphQL errors, null data, wrong types, missing or ambiguous operation association |
| LREQ-GQL-050 | `collector.py` | LREQ-GQL-040 | Network I/O | Partial-success fixture test | Retain valid ProductDetail when page views fail, and vice versa |
| LREQ-GQL-060 | `validation.py`, `collector.py` | LREQ-GQL-020, LREQ-GQL-040 | Pure validation over I/O result | Eligibility unit/fixture test | Only `published` assets eligible for demand, recent supply, and quality |
| LREQ-GQL-070 | `validation.py` | LREQ-GQL-020, LREQ-GQL-030, LREQ-GQL-040 | Pure | Identity mismatch unit test | Returned aliases disagree with requested identity; mismatch must invalidate affected result |
| LREQ-GQL-080 | `pipeline.py`, `collector.py`, `database.py` | LREQ-GQL-050, LREQ-GQL-070, LREQ-ID-040, LREQ-SMP-080 | Orchestration/I/O | Deduplication integration test | Cross-category overlap; one enrichment per unique identity; successful preflight response reuse; bulk enrichment is blocked until the preflight gate passes |

## Security

| REQ ID | Module | Depends on LREQs | Pure/I/O | Test type | Edge cases |
|---|---|---|---|---|---|
| LREQ-SEC-010 | `config.py`, `collector.py` | — | Environment/process I/O | Configuration and collector fixture test | Missing credentials; credentials required before network activity |
| LREQ-SEC-020 | `config.py`, `collector.py`, `database.py` | LREQ-SEC-010 | File/log/database I/O | Secret-redaction and repository check | No secrets in source control, logs, SQLite, or errors; `.env` ignored |

## Identity preflight

| REQ ID | Module | Depends on LREQs | Pure/I/O | Test type | Edge cases |
|---|---|---|---|---|---|
| LREQ-ID-010 | `pipeline.py`, `sampling.py` | LREQ-SMP-060, LREQ-SMP-080, LREQ-GQL-010 | Orchestration plus network I/O | Identity-preflight fixture test | At least 2 assets from 5 categories where possible; reduced coverage; categories with fewer than 2 assets |
| LREQ-ID-020 | `collector.py`, `validation.py` | LREQ-ID-010, LREQ-GQL-020, LREQ-GQL-030, LREQ-GQL-040, LREQ-GQL-050, LREQ-GQL-070 | Network I/O plus pure validation | Identity-preflight integration test | Request ID rejection, incompatible returned identity, page-view package mismatch, invalid correlation mode, and either-operation partial success |
| LREQ-ID-030 | `config.py`, `pipeline.py` | LREQ-ID-010 | Pure configuration policy | Configuration unit test | Minimum categories/assets, zero conflict rate, 90% minimum success rate |
| LREQ-ID-040 | `pipeline.py`, `database.py` | LREQ-ID-020, LREQ-ID-030 | Orchestration/database I/O | Preflight pass/fail integration test | Zero attempted identities gives `insufficient`, failed preflight blocks bulk enrichment, successful results reused |

## Deterministic sampling

| REQ ID | Module | Depends on LREQs | Pure/I/O | Test type | Edge cases |
|---|---|---|---|---|---|
| LREQ-SMP-010 | `sampling.py` | LREQ-EXT-060, LREQ-EXT-070, LREQ-EXT-080 | Pure | Sampling unit test | Sampling only after canonical identity resolution; conflict/unresolved records excluded |
| LREQ-SMP-020 | `sampling.py` | LREQ-SMP-010 | Pure | Ordering unit test | Canonical population ordered by category and discovery ordinal/rule |
| LREQ-SMP-030 | `sampling.py` | LREQ-SMP-020 | Pure | Configuration/golden test | Default sample size, four strata, threshold at 100, per-stratum size |
| LREQ-SMP-040 | `sampling.py` | LREQ-SMP-030 | Pure | Census unit test | Populations of 0, 1, 99, and 100; all assets selected; zero-population fraction is null |
| LREQ-SMP-050 | `sampling.py` | LREQ-SMP-020, LREQ-SMP-030 | Pure | Four-stratum unit test | Population above 100; contiguous ordinal boundaries; remainder assigned to final stratum |
| LREQ-SMP-060 | `sampling.py` | LREQ-SMP-020, LREQ-SMP-030 | Pure | SHA-256 golden test | NUL-delimited digest; tie-break by identity; no random generator; rule-version changes selection |
| LREQ-SMP-070 | `sampling.py` | LREQ-SMP-050, LREQ-SMP-060 | Pure | Distribution assertion test | Early, middle, and late discovery positions must be represented |
| LREQ-SMP-080 | `sampling.py`, `database.py` | LREQ-SMP-040, LREQ-SMP-050, LREQ-SMP-060, LREQ-SMP-070 | Pure calculation plus disk persistence | Persistence integration test | Census versus sample; overlap counts; per-stratum `N_h`, `n_h`, usable counts; sample fraction distinct from coverage |
| LREQ-SMP-090 | `sampling.py` | LREQ-SMP-050 | Pure | Boundary unit test | Stratum below 25 selects every asset and records reduced count |

## Metrics

| REQ ID | Module | Depends on LREQs | Pure/I/O | Test type | Edge cases |
|---|---|---|---|---|---|
| LREQ-MET-010 | `validation.py`, `scoring.py` | LREQ-GQL-060, LREQ-GQL-070 | Pure | Eligibility unit test | Null, malformed, wrong type, invalid range, future, naive, negative, non-finite, and excluded-state values |
| LREQ-MET-020 | `scoring.py` | LREQ-ARCH-020 | Pure | Date unit/golden test | UTC normalization, naive dates, exact fractional age, future dates |
| LREQ-MET-030 | `scoring.py` | LREQ-MET-010, LREQ-MET-040, LREQ-SMP-080 | Pure | Metric unit/golden test | No usable stratum; zero population; never divide by zero; denominator uses usable-stratum weights |
| LREQ-MET-040 | `scoring.py` | LREQ-MET-010, LREQ-MET-020, LREQ-GQL-050, LREQ-GQL-060, LREQ-GQL-070 | Pure | Index unit/golden test | Zero page views are valid; negative/non-finite values invalid; age threshold; identity/state mismatch; ProductDetail may remain usable when PageViews is unavailable |
| LREQ-MET-050 | `scoring.py` | LREQ-MET-040, LREQ-SMP-080 | Pure | Weighted-median golden test | Parallel to DemandPerAssetRaw; ties, exact half-weight boundary, final-value boundary, empty usable set |
| LREQ-MET-060 | `scoring.py` | LREQ-MET-030, LREQ-SMP-080 | Pure | Coverage unit/golden test | Coverage bounded to `[0,1]`; missing strata; zero population |
| LREQ-MET-070 | `validation.py`, `scoring.py` | LREQ-EXT-050, LREQ-EXT-060, LREQ-EXT-070, LREQ-EXT-080 | Pure over persisted discovery data | Breadth validation test | Verified total, duplicate collapse, unresolved/conflicting identity, incomplete discovery |
| LREQ-MET-080 | `scoring.py` | LREQ-MET-010, LREQ-MET-020, LREQ-GQL-060, LREQ-SMP-080 | Pure | Recent-supply unit/golden test | Inclusive 365-day window; boundary date; missing dates; zero population; weighted median age |
| LREQ-MET-090 | `scoring.py` | LREQ-MET-010, LREQ-GQL-060, LREQ-MET-040 | Pure | Constants and threshold test | Rating count below 5; eligible asset count below 5; contradicted page-view semantics |
| LREQ-MET-100 | `scoring.py` | LREQ-GQL-050, LREQ-GQL-060, LREQ-GQL-070, LREQ-MET-040, LREQ-MET-090, LREQ-SMP-080 | Pure | Quality golden test | ProductDetail/PageViews operation eligibility; identity mismatch; published state; zero visibility denominator; unequal strata; `N_h / n_h` weights; invalid ratings; insufficient coverage |

## Normalization

| REQ ID | Module | Depends on LREQs | Pure/I/O | Test type | Edge cases |
|---|---|---|---|---|---|
| LREQ-NRM-010 | `scoring.py` | LREQ-MET-030, LREQ-MET-050, LREQ-MET-070, LREQ-MET-080, LREQ-MET-100 | Pure | Normalization unit/golden test | Every category is a target; target excluded from its own reference |
| LREQ-NRM-020 | `scoring.py`, `database.py` | LREQ-NRM-010 | Pure plus persistence | Reference-size test | `category_count - 1`; field-specific usable counts; 21 categories means 20 peers |
| LREQ-NRM-030 | `scoring.py` | LREQ-NRM-010, LREQ-NRM-020 | Pure | Midrank golden test | Null target, empty reference, ties, all-equal reference |
| LREQ-NRM-040 | `scoring.py` | LREQ-NRM-030, LREQ-MET-030, LREQ-MET-050, LREQ-MET-070, LREQ-MET-080, LREQ-MET-100 | Pure | Multi-field normalization golden test | Independent normalization; no log transform; null raw fields |

## Score components and composite score

| REQ ID | Module | Depends on LREQs | Pure/I/O | Test type | Edge cases |
|---|---|---|---|---|---|
| LREQ-SCR-010 | `scoring.py` | LREQ-NRM-040, LREQ-MET-030, LREQ-MET-050, LREQ-MET-060 | Pure | Component golden test | Both, one, or neither demand field available; coverage shrinkage; clamping |
| LREQ-SCR-020 | `scoring.py` | LREQ-NRM-040, LREQ-MET-070 | Pure | Component golden test | Unverified or incomplete breadth; null reference; clamping |
| LREQ-SCR-030 | `scoring.py` | LREQ-NRM-040, LREQ-MET-080 | Pure | Component golden test | Both, one, or neither recent-supply field available; coverage shrinkage |
| LREQ-SCR-040 | `scoring.py` | LREQ-NRM-040, LREQ-MET-100 | Pure | Component golden test | Null quality; insufficient quality support; zero denominator |
| LREQ-SCR-050 | `scoring.py` | LREQ-SCR-010, LREQ-SCR-040 | Pure | Semantic-status unit test | Contradicted page views disable D and Q; C and R may remain available; category not rankable |
| LREQ-SCR-060 | `scoring.py` | LREQ-SCR-010, LREQ-SCR-020, LREQ-SCR-030, LREQ-SCR-040, LREQ-SCR-050 | Pure | Composite golden test | Fewer than two components; partial score; available-weight renormalization; fixed primary weights |

## Evidence and rankability

| REQ ID | Module | Depends on LREQs | Pure/I/O | Test type | Edge cases |
|---|---|---|---|---|---|
| LREQ-EVD-010 | `scoring.py` | LREQ-SCR-060 | Pure | State-transition unit test | Only `not_rankable`, `provisional`, and `rankable` states |
| LREQ-EVD-020 | `scoring.py`, `pipeline.py` | LREQ-EXT-090, LREQ-GQL-060, LREQ-GQL-070, LREQ-ID-040, LREQ-MET-070, LREQ-NRM-020, LREQ-SCR-050, LREQ-SCR-060 | Pure decision logic plus orchestration status | Rankability matrix test | Unresolved/conflicting identities, invalid discovery, missing required metrics, preflight failure, contradicted page views, no reference; run failure and category not-rankable status remain distinct |
| LREQ-EVD-030 | `scoring.py` | LREQ-EVD-020, LREQ-SCR-060, LREQ-NRM-020 | Pure | Provisional-state golden test | 8–20 categories; incomplete breadth fallback; weak coverage; high sensitivity |
| LREQ-EVD-040 | `scoring.py` | LREQ-EVD-020, LREQ-EVD-030, LREQ-SEN-030 | Pure | Rankability integration/golden test | Minimum 8 categories; strong reference requirement; sensitivity demotion without changing candidate set or score |
| LREQ-EVD-050 | `scoring.py` | LREQ-EVD-020, LREQ-EVD-030, LREQ-NRM-020, LREQ-SEN-030 | Pure | Evidence-grade golden test | Strong/moderate/weak/insufficient; census alternative; coverage and sensitivity affect grade |

## Ranking sensitivity

| REQ ID | Module | Depends on LREQs | Pure/I/O | Test type | Edge cases |
|---|---|---|---|---|---|
| LREQ-SEN-010 | `scoring.py` | LREQ-SCR-060, LREQ-EVD-020 | Pure | Policy unit test | Balanced, demand-heavy, and competition-heavy weights |
| LREQ-SEN-020 | `scoring.py`, `database.py` | LREQ-SEN-010, LREQ-EVD-020, LREQ-SCR-060 | Pure plus persistence | Sensitivity golden test | Ranks only the fixed `base_rankable_candidates`; top 3/top 5, deterministic tie-breaking, null when too few candidates, rank and score displacement |
| LREQ-SEN-030 | `scoring.py` | LREQ-SEN-020, LREQ-NRM-020 | Pure | Threshold unit/golden test | `top_3_stability < 2/3`; rank displacement greater than `max(3, 25% of reference size)` |
| LREQ-SEN-040 | `scoring.py` | LREQ-SEN-010, LREQ-SEN-020, LREQ-SEN-030 | Pure | Score-preservation test | Sensitivity qualifies the balanced score; it cannot replace or mutate it |

## Reporting

| REQ ID | Module | Depends on LREQs | Pure/I/O | Test type | Edge cases |
|---|---|---|---|---|---|
| LREQ-RPT-010 | `report.py` | LREQ-SCR-060, LREQ-EVD-050, LREQ-SEN-020 | Disk read/render I/O | End-to-end/report smoke test | Local read-only report/dashboard renderer; no direct CLI prerequisite and no network activity |
| LREQ-RPT-020 | `report.py` | LREQ-SMP-080, LREQ-SCR-060, LREQ-EVD-050, LREQ-SEN-020 | Disk read/render I/O | HTML/report fixture test | All required score, coverage, sample, evidence, status, and sensitivity fields |
| LREQ-RPT-030 | `report.py` | LREQ-MET-030, LREQ-SMP-080, LREQ-EVD-050 | Disk read/render I/O | Category-detail snapshot test | Formulas, inputs, strata, warnings, timestamps, observed versus inferred values |
| LREQ-RPT-040 | `report.py` | LREQ-EVD-010, LREQ-EVD-020 | Disk read/render I/O | Visibility test | Non-rankable categories remain visible and explain why |
| LREQ-RPT-050 | `report.py` | LREQ-EVD-050, LREQ-SEN-040, LREQ-SMP-080 | Disk read/render I/O | Warning-vocabulary/report test | Must distinguish heuristic, sample fraction, eligibility coverage, evidence grade, and statistical confidence |

## CLI and orchestration

| REQ ID | Module | Depends on LREQs | Pure/I/O | Test type | Edge cases |
|---|---|---|---|---|---|
| LREQ-CLI-010 | `cli.py`, `pipeline.py` | LREQ-SEC-010, LREQ-EXT-050, LREQ-GQL-080, LREQ-ID-040, LREQ-SCR-060 | Process/orchestration I/O | CLI end-to-end test | Successful run; unrecoverable error exits non-zero; may invoke report generation after pipeline completion |
| LREQ-CLI-020 | `cli.py`, `report.py` | LREQ-RPT-010, LREQ-RPT-020 | Disk/process I/O | Dashboard isolation test | No discovery or enrichment network calls; CLI is only a caller of the report renderer |
| LREQ-CLI-030 | `cli.py`, `config.py` | — | Process/file I/O | Configuration precedence test | CLI overrides TOML; TOML overrides defaults |
| LREQ-CLI-040 | `cli.py`, `pipeline.py` | LREQ-EXT-020, LREQ-NRM-010, LREQ-EVD-020 | Orchestration I/O | End-to-end validation test | Fewer than 8 categories rejected before ranking; completed run retains timestamps and limitations |

## Non-functional requirements

| REQ ID | Module | Depends on LREQs | Pure/I/O | Test type | Edge cases |
|---|---|---|---|---|---|
| LREQ-NFR-010 | `collector.py`, `database.py` | LREQ-EXT-050, LREQ-SMP-080 | Network/database streaming I/O | Streaming/instrumentation test | Large discovery results must not require all responses in memory |
| LREQ-NFR-020 | `pipeline.py`, `collector.py` | LREQ-SMP-080, LREQ-ID-010, LREQ-GQL-080 | Logging/process I/O | Pipeline-log fixture test | Log canonical count, sample count, unique enrichment count, and projected minimum time before enrichment |
| LREQ-NFR-030 | `collector.py`, `pipeline.py` | LREQ-EXT-050, LREQ-GQL-040, LREQ-ID-040 | Orchestration/I/O | Failure-isolation integration test | One page or asset failure must not abort unrelated categories/assets |
| LREQ-NFR-040 | `metrics`, `scoring` | LREQ-ARCH-010, LREQ-ARCH-020 | Pure | Static inspection plus API tests | Type hints and docstrings must describe null and edge behavior |
| LREQ-NFR-050 | Project-wide | — | Runtime/platform | Environment smoke test | Python 3.11+; Windows, macOS, Linux; `pathlib` paths |
| LREQ-NFR-060 | Project-wide | LREQ-NFR-040, LREQ-TST-010 | Tooling/process I/O | Formatting, linting, secret, and analytical checks | Strict whole-project typing, 95% coverage, and CI-on-every-commit are explicitly deferred |

## Testing requirements

These are verification requirements rather than runtime features.

| REQ ID | Module | Depends on LREQs | Pure/I/O | Test type | Edge cases |
|---|---|---|---|---|---|
| LREQ-TST-010 | `tests/` | All formula-producing requirements | Test-only | Unit and golden tests | Normal values, zero, missing, invalid, ties, minimum boundaries |
| LREQ-TST-020 | `tests/test_sampling.py` | LREQ-SMP-010 through LREQ-SMP-090 | Test-only | Sampling unit/golden tests | Census boundaries, four strata, deterministic repeat, reduced final stratum, digest changes, no duplicates |
| LREQ-TST-030 | `tests/test_identity.py` | LREQ-EXT-060, LREQ-EXT-070, LREQ-GQL-070, LREQ-GQL-080 | Test-only | Identity fixture/unit tests | Valid, malformed, unresolved, conflicting, URI parsing, GraphQL mismatch, cross-category duplicates |
| LREQ-TST-040 | `tests/test_collector.py`, `tests/test_identity.py` | LREQ-GQL-010 through LREQ-GQL-080 | Test-only | HTTP/GraphQL fixture tests | Reversed order, missing association, errors, null data, wrong types, invalid page views, partial success, auth/CSRF failure |
| LREQ-TST-050 | `tests/test_scoring.py`, `tests/test_validation.py` | LREQ-MET-010 through LREQ-MET-100 | Test-only | Date/metric unit and golden tests | UTC, naive dates, fractional age, thresholds, future dates, zero views, windows, weighted strata/medians, zero denominator |
| LREQ-TST-060 | `tests/test_scoring.py` | LREQ-NRM-010 through LREQ-SCR-060, LREQ-EVD-010 through LREQ-EVD-040 | Test-only | Scoring golden/integration tests | Ties, all-equal references, missing components, coverage shrinkage, 8 versus 21 categories, fixed candidate set |
| LREQ-TST-070 | `tests/test_scoring.py` | LREQ-SEN-010 through LREQ-SEN-040 | Test-only | Sensitivity golden tests | All policies, displacement, stability, thresholds, score preservation, unchanged candidate set |
| LREQ-TST-080 | `tests/test_end_to_end.py` | All collection, sampling, scoring, persistence, and reporting requirements | Test-only with fixture I/O | End-to-end fixture | Category validation, pagination, duplicates, overlap, sample, one enrichment per identity, partial GraphQL, SQLite, report |
| LREQ-TST-090 | `tests/fixtures/`, `tests/test_scoring.py`, `tests/test_end_to_end.py` | LREQ-TST-010 through LREQ-TST-080 | Test-only | Golden-vector and acceptance suite | Exact tolerance `1e-9`; two-category rejection; 8-category provisional; 21-category strong; zero population; unequal-stratum quality |

---

# 2. Dependency graph

The implementation should follow this high-level directed graph:

```text
Project foundation and status contracts
    ↓
Typed models and configuration
    ↓
Pure taxonomy and identity validation
    ↓
SQLite schema and persistence contracts
    ↓
Coveo request/response adapter
    ↓
Streamed raw discovery persistence
    ↓
Canonical populations and deterministic sampling
    ↓
GraphQL protocol adapter and response correlation
    ↓
Identity preflight and preflight-controlled enrichment
    ↓
Metric eligibility and sample-aware estimators
    ↓
LOO normalization
    ↓
D/C/R/Q components and composite score
    ↓
Evidence/rankability
    ↓
Ranking sensitivity
    ↓
Pipeline orchestration and final SQLite result persistence
    ↓
Report rendering
    ↓
CLI commands and configuration precedence
    ↓
End-to-end and golden acceptance suite
```

Some work can occur in parallel:

```text
Typed models/config/statuses ───┬── pure validation
                                ├── database schema/contracts
                                └── test fixture framework

Coveo request adapter ──────────┬── streamed discovery persistence
                                 └── canonical population construction

GraphQL protocol adapter ───────┬── identity preflight
                                 └── response-validation fixtures

Canonical populations ────────── deterministic sampling ──┐
Database schema/contracts ──────────────────────────────────┤
                                                           ↓
Preflight gate ─────────── unique enrichment and persistence

Pure metrics ─────────────┬── normalization/scoring
Database read model ──────┘
```

---

# 3. Chunked implementation plan

Each chunk should be independently reviewable and should end with a testable gate.

## Chunk 0 — Project skeleton and contracts

**Goal:** Establish the package boundaries before implementing behavior.

Implement:

- `pyproject.toml`
- `src/niche_scout/`
- `tests/`
- `README.md`
- `config/categories.json`
- `config/category_taxonomy.json`
- `config/default.toml`
- `.gitignore`
- `.env.example`
- `models.py`
- `config.py`
- typed result structures for the complete SRS data model
- constants and policy versions
- `RunStatus`: `running`, `completed`, `failed`
- discovery, identity-resolution, operation, score, evidence, and rankability statuses
- warning-code, correlation-mode, and page-view-semantic-status types
- `scoring_cutoff_utc` as an explicit pure-function input
- SQLite logical schema definitions
- test fixture conventions

Requirements primarily covered:

- LREQ-ARCH-010
- LREQ-ARCH-020
- LREQ-ARCH-030
- LREQ-SEC-010
- LREQ-NFR-040
- LREQ-NFR-050
- LREQ-NFR-060

Gate:

- Package imports successfully.
- `metrics` and `scoring` do not import I/O modules.
- Configuration precedence is represented in tests.
- All required status values and mandatory logical row fields are represented by typed structures.
- `.env` is ignored and `.env.example` contains no credentials.
- No network code is required yet.

---

## Chunk 1 — Pure taxonomy, identity, and response validation

**Goal:** Build all deterministic validators before writing network collectors.

Implement:

- taxonomy file schema validation
- taxonomy freshness validation
- exact category-path matching
- canonical identity parsing
- URI identity fallback
- conflict/unresolved status handling
- GraphQL identity alias comparison
- type/range/state/date validation primitives
- redacted error summaries

Requirements:

- LREQ-EXT-020
- LREQ-EXT-060
- LREQ-EXT-070
- LREQ-EXT-080
- LREQ-GQL-060
- LREQ-GQL-070
- LREQ-MET-010

Tests:

- `test_validation.py`
- `test_identity.py`

Gate:

- All identity and taxonomy tests pass without network access.
- Invalid data is represented explicitly, never silently converted to zero or an ordinary asset.
- Validation functions accept typed data and return typed results.

---

## Chunk 2 — SQLite schema and persistence contracts

**Goal:** Define the audit trail and persistence API before runtime discovery or sampling.

Implement tables:

- `runs`
- `raw_discovery_observations`
- `sample_members`
- `enrichment_observations`
- `category_scores`

Implement:

- logical primary and uniqueness rules, including `(run_id, category, asset_identity_key)` for samples and `(run_id, category)` for scores
- nullable page-view fields and run-level preflight/correlation/semantic-status fields
- structured JSON columns and redacted error summaries
- streamed insertion APIs and transaction boundaries
- run/category status transitions that preserve unrelated category failures

Requirements:

- LREQ-SMP-080
- LREQ-GQL-080
- LREQ-NFR-010
- LREQ-SEC-020

Gate:

- Pure sampling and scoring functions do not import or require SQLite.
- Duplicate sample membership is rejected.
- `(run_id, category)` is enforced for category scores.
- Secrets cannot enter persisted records.
- A failed category does not roll back unrelated category observations.

---

## Chunk 3 — Coveo discovery adapter and streamed raw persistence

**Goal:** Discover and persist raw observations without accumulating the complete result set in memory.

Implement:

- Coveo request builder
- required headers and taxonomy facet
- explicit prohibition of free-text query fields
- pagination
- verified `totalCount` handling
- rate limiting
- retry/backoff
- first valid discovery ordinal
- duplicate raw observation and duplicate canonical-record handling
- category-mismatch precedence and `filter_unverified` status
- terminal discovery statuses
- streaming observation emission into the Chunk 2 persistence API
- raw observation metadata and redacted error summaries

Requirements:

- LREQ-EXT-010
- LREQ-EXT-030
- LREQ-EXT-040
- LREQ-EXT-050
- LREQ-EXT-090
- LREQ-EXT-100
- LREQ-NFR-010
- LREQ-NFR-030

Tests:

- `test_collector.py`
- mocked HTTP fixtures
- pagination, duplicate, mismatch, and retry tests

Gate:

- No live endpoint is needed for normal tests.
- Failed pages remain failures and are never interpreted as zero assets.
- Raw observations are persisted before canonical populations or samples are constructed.
- Discovery can process one category without loading the complete result set into memory.

---

## Chunk 4 — Canonical populations and deterministic sampling engine

**Goal:** Produce stable sample membership from validated canonical discovery records.

Implement:

- canonical population construction from persisted discovery observations
- ordinal ordering
- census behavior for `N <= 100`
- four-stratum behavior for `N > 100`
- SHA-256 NUL-delimited selection digest
- reduced final strata
- cross-category overlap metadata after all category samples are selected
- sample fraction and stratum summary structures

Requirements:

- LREQ-SMP-010 through LREQ-SMP-090

Tests:

- `test_sampling.py`
- sampling golden vectors

Gate:

- Repeated selection is identical.
- Changing the sampling-rule version changes the digest/selection.
- Populations 0, 1, 99, 100, and greater than 100 behave exactly as specified.
- Early, middle, and late discovery positions are represented.
- Sample fraction remains distinct from stratum eligibility coverage.

---

## Chunk 5 — GraphQL protocol adapter and response correlation

**Goal:** Build a reusable protocol layer that validates GraphQL operations without deciding whether bulk enrichment is allowed.

Implement:

- ProductDetail query
- ProductPageViews query
- explicit operation correlation
- reversed-order handling
- operation-level status
- partial-success retention
- page-view type/range validation
- state filtering
- identity mismatch handling
- rate limiting and retry policy consistent with the collector

Requirements:

- LREQ-GQL-010 through LREQ-GQL-070
- LREQ-SEC-010
- LREQ-SEC-020
- LREQ-NFR-030

Tests:

- `test_collector.py`
- `test_identity.py`

Gate:

- Reversed GraphQL response order passes.
- Missing or ambiguous operation correlation fails safely.
- Partial ProductDetail/PageViews success is persisted independently.
- The adapter does not perform bulk enrichment or bypass the preflight gate.

---

## Chunk 6 — Identity preflight, enrichment execution, and enrichment persistence

**Goal:** Enforce the SRS sequence: sample identities, run identity preflight, then enrich remaining identities only after the gate passes.

Implement:

- deterministic preflight selection
- minimum category and asset policy
- unique-identity denominator
- success/conflict rate calculations
- preflight persistence
- preflight failure gate
- successful preflight response reuse
- unique sampled-identity union across categories
- one enrichment per unique identity
- bulk enrichment only after successful preflight
- enrichment persistence coordination
- projected minimum enrichment-time calculation and pre-enrichment logging

Requirements:

- LREQ-ID-010
- LREQ-ID-020
- LREQ-ID-030
- LREQ-ID-040
- LREQ-GQL-080
- LREQ-NFR-020

Tests:

- identity-preflight fixtures
- pass/fail threshold tests
- insufficient-preflight test
- overlap denominator test

Gate:

- Failed preflight prevents bulk enrichment.
- Successful preflight responses count toward enrichment exactly once.
- Zero attempted identities produces `insufficient`, not zero success.
- A failed preflight marks the run failed and does not become an informational-only warning.

---

## Chunk 7 — Pure sample-aware metrics

**Goal:** Implement the four raw signal families without database or network dependencies.

Implementation note: choose one explicit module convention before coding. If the lean structure keeps both layers in `scoring.py`, document and test two internal pure layers there: raw metric functions first, then normalization/component/evidence functions. Alternatively, split the raw metric layer into `metrics.py` and retain relative scoring in `scoring.py`; do not leave the architecture ambiguous.

Implement:

- age normalization
- page-view index
- usable-value eligibility
- DemandPerAssetRaw
- weighted DemandMedianRaw
- BreadthRaw
- RecentShareRaw
- weighted MedianAgeRaw
- QualityRaw
- component coverage
- zero-population behavior
- stratum expansion weights

Requirements:

- LREQ-MET-010 through LREQ-MET-100
- LREQ-ARCH-010
- LREQ-ARCH-020
- LREQ-ARCH-030

Tests:

- `test_scoring.py`
- `test_validation.py`
- golden vectors

Gate:

- All metric functions are pure.
- No metric reads the current time.
- Exact fractional age is used.
- Zero is distinguished from null/unavailable.
- Weighted medians use the exact boundary rule.
- Quality uses `N_h / n_h`, not a simple sample average.

---

## Chunk 8 — Normalization and primary scoring

**Goal:** Convert raw metrics to components and a deterministic composite score.

Implement:

- leave-one-out reference construction
- field-specific usable counts
- midrank normalization
- D, C, R, and Q components
- contradicted page-view handling
- fixed Lean v1 weights
- available-component renormalization
- score state

Requirements:

- LREQ-NRM-010 through LREQ-NRM-040
- LREQ-SCR-010 through LREQ-SCR-060

Tests:

- midrank golden vectors
- all-equal reference tests
- missing-component tests
- coverage-shrinkage tests
- 8-category and 21-category tests

Gate:

- A category never appears in its own LOO reference.
- A 21-category run stores reference size 20.
- Fewer than two components produces an unavailable score.
- Balanced primary scoring exactly matches balanced sensitivity weights.
- `score_state` (`unavailable`, `partial`, `available`) is distinct from `rankability_status` (`not_rankable`, `provisional`, `rankable`).

---

## Chunk 9 — Evidence, rankability, and sensitivity

**Goal:** Separate score computation from whether the score is suitable for ranking.

Implement:

- fixed `base_rankable_candidates` constructed before sensitivity
- `not_rankable`, `provisional`, and `rankable`
- evidence grades
- balanced, demand-heavy, and competition-heavy policies
- deterministic rank tie-breaking
- top-3 and top-5 stability
- score/rank displacement
- warning thresholds
- final rankability after sensitivity

Requirements:

- LREQ-EVD-010 through LREQ-EVD-050
- LREQ-SEN-010 through LREQ-SEN-040

Tests:

- scoring golden vectors
- sensitivity golden vectors
- candidate-set immutability tests
- rankability transition tests

Gate:

- Sensitivity never adds or removes candidates.
- Sensitivity never modifies the balanced primary score.
- A sensitivity warning demotes final rankability only as specified.
- Insufficient candidate counts produce null stability values.
- Final rankability and evidence are assigned only after sensitivity is computed.

---

## Chunk 10 — Pipeline orchestration

**Goal:** Connect the pure functions and I/O adapters in the SRS-prescribed order.

Implement this sequence:

1. Load CLI/config/category input.
2. Validate configuration and taxonomy.
3. Create run metadata and policy hashes.
4. Stream Coveo discovery.
5. Persist raw observations.
6. Build canonical populations.
7. Select deterministic samples.
8. Run identity preflight.
9. If preflight passes, compute the unique sampled-identity union, log enrichment projections, and enrich remaining identities while reusing successful preflight responses.
10. Capture `scoring_cutoff_utc`.
11. Compute metrics.
12. Build LOO references.
13. Compute scores and `base_rankable_candidates`.
14. Compute sensitivity only over the fixed candidate set.
15. Compute final evidence and rankability.
16. Persist category scores and run-level status fields.
17. Mark the run `completed` or `failed`.

Requirements:

- LREQ-ARCH-030
- LREQ-ID-040
- LREQ-NFR-020
- LREQ-NFR-030
- LREQ-CLI-010
- LREQ-CLI-040

Gate:

- A failed category does not abort unrelated categories.
- The scoring cutoff is captured once and passed into pure functions.
- A failed preflight prevents enrichment.
- Two-category runs are rejected before ranking.
- Configuration or taxonomy failure causes no network request.
- Preflight failure marks the run failed; category-level `not_rankable` remains separately representable.
- 8–20 category runs may compute provisional scores, but have no rankable candidate set and null sensitivity stability values.

---

## Chunk 11 — Report renderer and read-only dashboard

**Goal:** Expose the completed run without initiating unexpected network activity.

Implement:

- database read model
- `report.py` renderer
- read-only dashboard
- sortable primary table
- category detail panel
- warnings and limitation vocabulary
- display of non-rankable categories

Requirements:

- LREQ-RPT-010 through LREQ-RPT-050

Gate:

- `dashboard` performs database reads only.
- Reports include every mandatory score, sample, coverage, evidence, and sensitivity field.
- Non-rankable categories remain visible.
- Report language does not imply sales forecasting, statistical confidence, or representative marketplace estimation.

---

## Chunk 12 — CLI commands and configuration precedence

**Goal:** Wire the pipeline and report renderer into commands without creating a report/CLI dependency cycle.

Implement:

- `niche-scout run`
- `niche-scout dashboard`
- CLI/TOML/default precedence
- validation and exit-code behavior
- completed-run and failed-run selection for dashboard reads

Requirements:

- LREQ-CLI-010 through LREQ-CLI-040

Gate:

- `run` invokes pipeline orchestration and may call the report renderer only after completion.
- `dashboard` calls the report renderer and performs database reads only.
- Fewer than 8 categories are rejected before ranking.
- Unrecoverable run errors exit non-zero while preserving run status and limitations.

---

## Chunk 13 — Full acceptance suite and quality workflow

**Goal:** Validate the complete decision-grade behavior before release.

Implement:

- end-to-end fixture
- golden vector suite
- mocked Coveo and GraphQL responses
- SQLite persistence verification
- rendered report assertions
- formatting and linting commands
- secret-handling checks
- import-boundary checks
- deterministic repeat-run checks

Requirements:

- LREQ-TST-010 through LREQ-TST-090
- LREQ-NFR-060

Gate:

- Exact golden outputs pass within `1e-9`.
- End-to-end fixture covers all required collection, sampling, enrichment, scoring, persistence, and reporting behaviors.
- 8-category provisional run behaves correctly.
- 21-category strong-reference run behaves correctly.
- Preflight failure produces a failed run and zero bulk-enrichment requests.
- Partial GraphQL operation success and contradicted page-view semantics remain distinguishable.
- Sensitivity is null when the fixed candidate set is empty and never changes that set.
- No stale requirement from the retired SRS is accidentally implemented.

---

# 4. Recommended execution order

The safest implementation order is:

```text
Chunk 0  Foundation
Chunk 1  Pure validation and identity
Chunk 2  SQLite schema and persistence contracts
Chunk 3  Coveo discovery
Chunk 4  Canonical populations and deterministic sampling
Chunk 5  GraphQL protocol adapter
Chunk 6  Identity preflight, enrichment, and enrichment persistence
Chunk 7  Metrics
Chunk 8  Normalization and scoring
Chunk 9  Evidence and sensitivity
Chunk 10 Pipeline
Chunk 11 Report renderer and read-only dashboard
Chunk 12 CLI commands and configuration precedence
Chunk 13 Acceptance and quality gates
```

After Chunk 0, Chunks 1, 2, and the metric fixture interfaces can proceed in parallel. After Chunks 1 and 2, the Coveo adapter and GraphQL protocol adapter can proceed in parallel. Sampling is operationally downstream of persisted discovery; preflight is downstream of sampling; bulk enrichment is downstream of a successful preflight gate. The networked collectors should not be the first implementation target: they depend on canonical identity rules, taxonomy validation, status modeling, persistence contracts, and fixture contracts.

# 5. Important implementation constraints

1. **Do not start with live network integration.** Build request builders and response parsers against fixtures first.
2. **Keep pure scoring isolated.** `metrics` and `scoring` should not know SQLite, HTTP, CLI, report, or system-clock APIs exist.
3. **Treat null, zero, invalid, and unavailable as different states.**
4. **Persist audit information before computing scores.**
5. **Build the base rankable candidate set before sensitivity analysis.**
6. **Do not confuse sample size with discovered population size.**
7. **Do not use category overlap to inflate enrichment counts or preflight rates.**
8. **Use the SRS’s exact weights, thresholds, and boundary conditions.**
9. **Use fixtures and golden vectors to freeze behavior before connecting to live endpoints.**
10. **Map every implementation test back to one or more individual `LREQ-*` IDs.**

## 6. Implementation clarifications from independent review

### 6.1 Run and category status are separate

Preflight failure marks the run as `failed`, while affected categories may also be shown as `not_rankable`. Category failure, preflight failure, run failure, score state, evidence grade, and rankability status must remain distinct fields rather than being collapsed into one status.

### 6.2 Eight-to-twenty-category runs

Runs with 8–20 categories may calculate provisional scores, but they do not produce a rankable candidate set. For those runs, `base_rankable_candidates` is empty and `top_3_stability`, `top_5_stability`, and related sensitivity outputs are `null`. The report must show provisional scores without presenting them as a ranked recommendation set.

### 6.3 Empty sensitivity candidate sets

Sensitivity is evaluated only over the fixed `base_rankable_candidates` set. If that set is empty or too small for a stability statistic, sensitivity values are `null`; sensitivity does not independently create candidates or alter the balanced score.

### 6.4 Runtime invariant

The complete runtime order is:

```text
discover → persist → canonicalize → sample → preflight → enrich → cutoff → score → sensitivity → report
```

The GraphQL protocol adapter may be implemented before preflight, but it must not execute bulk enrichment until the preflight-controlled executor has passed the gate.

This plan exposes the primary hidden dependency: the difficult networked parts are downstream of deterministic taxonomy, identity, sampling, status, and persistence contracts. Implementing those foundational pieces first substantially reduces the risk of building a collector that produces data the scoring layer cannot safely interpret.