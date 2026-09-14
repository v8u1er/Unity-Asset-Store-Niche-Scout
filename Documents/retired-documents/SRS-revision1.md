# Software Requirements Specification

## Unity Asset Store Niche Scout (MVP) — "niche-scout"

| Field | Value |
|---|---|
| Document type | Software Requirements Specification (SRS) |
| Format basis | ISO/IEC/IEEE 29148:2018 structure, adapted |
| Version | 1.0.0 |
| Status | Draft — pending resolution of open items in §2.6 |
| Target release | v0.1.0 (MVP) |

### Revision history

| Version | Change |
|---|---|
| 1.0.0 | Initial SRS. Derived from `V3_MATHEMATICAL_REFERENCE.md`, `V3_MATHEMATICAL_AUDIT_REPORT.md`, and `Unity_Data_Extraction_API.md`, with corrections for two identified defects (see §2.1) and an intentional architecture change (leave-one-out reference, see DD-1 in §6.5). |

### Table of contents

1. [Introduction](#1-introduction)
2. [Overall Description](#2-overall-description)
3. [System Architecture](#3-system-architecture)
4. [External Interface Requirements](#4-external-interface-requirements)
5. [Data Model](#5-data-model)
6. [Functional Requirements](#6-functional-requirements)
7. [Non-Functional Requirements](#7-non-functional-requirements)
8. [Project Structure and Coding Conventions](#8-project-structure-and-coding-conventions)
9. [Testing Requirements](#9-testing-requirements)
10. [MVP Non-Goals (Explicitly Deferred)](#10-mvp-non-goals-explicitly-deferred)
11. [Known Inherited Limitations (Not Fixed in MVP)](#11-known-inherited-limitations-not-fixed-in-mvp)
12. [Appendix A — Consolidated Formula Reference](#appendix-a--consolidated-formula-reference)
13. [Appendix B — Glossary](#appendix-b--glossary)
14. [Appendix C — Configuration Constants Reference](#appendix-c--configuration-constants-reference)
15. [Appendix D — Requirements Traceability Matrix](#appendix-d--requirements-traceability-matrix)

---

## 1. Introduction

### 1.1 Purpose

This document specifies the requirements for **niche-scout**, a minimal, single-operator, locally-run system that (a) extracts publicly visible Unity Asset Store category data through the documented Coveo search endpoint, (b) computes a deterministic, observed-data comparative score for every category the operator specifies, and (c) presents the results in a minimal local dashboard.

This SRS is written so that a single competent implementer (human or AI coding agent) can build the system without needing to make an undocumented judgment call on any formula, data type, boundary condition, file name, or module boundary. Where the source material was ambiguous or incomplete, this document makes an explicit decision and labels it as such (see **Design Decision (DD-n)** and **Open Item (OI-n)** markers).

### 1.2 Document conventions

- **SHALL** — mandatory. A conforming implementation MUST satisfy this.
- **SHOULD** — strongly recommended; deviation requires a documented reason.
- **MAY** — optional, implementer's discretion.
- Requirement IDs use the form `REQ-<AREA>-<NNN>`, numbered in increments of 10 within each area to allow future insertion without renumbering.
- Every formula is given in a fenced code block using plain arithmetic notation. `ln` denotes the natural logarithm. `clamp(v, lo, hi) = min(max(v, lo), hi)`. All formulas operate on `float64` unless stated otherwise.
- **Design Decision (DD-n)**: a point where the source material was silent or ambiguous and this SRS makes a binding choice.
- **Open Item (OI-n)**: a dependency that cannot be resolved from the supplied source material alone and SHALL be confirmed against the live system before the affected code is written.

### 1.3 Project scope

In scope for the MVP:

1. A Coveo API client that retrieves category-scoped asset listing data for an operator-supplied set of category paths.
2. Local persistence of raw observations and computed results in a single SQLite file.
3. A pure scoring engine that computes four bounded components (Demand `D`, Competition `C`, Recent-Supply `R`, Quality-Gap `Q`) and a composite `market_opportunity_score` for **every** category in the operator-supplied set, using a leave-one-out reference (see §6.5, DD-1).
4. A minimal local, read-only dashboard for inspecting and sorting results.
5. A command-line entry point that runs extraction, scoring, and persistence in one invocation.

Out of scope for the MVP: see §10.

### 1.4 Definitions, acronyms, abbreviations

| Term | Meaning |
|---|---|
| Asset | A single product listing on the Unity Asset Store. |
| Category | A Coveo `ec_category` facet value, e.g. `"3d > props > exterior"`. |
| Run | One execution of the pipeline against an operator-supplied category set, sharing one UTC cutoff. |
| Target category | Any category in the operator-supplied set, when being scored. |
| Reference set (for a target) | All *other* categories in the same run's operator-supplied set (see DD-1). Every category is a target in its own right and a reference member for every other category in the same run. |
| Midrank percentile | Nonparametric rank-based normalization, defined in §6.5. |
| Component | One of `D`, `C`, `R`, `Q`. |
| ESS | Effective sample size, §6.7. |
| MVP | Minimum viable product. |
| LOO | Leave-one-out. |

### 1.5 Source references

This SRS is derived from three operator-supplied documents, referred to throughout by short name:

- **[REF-MATH]** — `V3_MATHEMATICAL_REFERENCE.md`: the prior system's formula reference.
- **[REF-AUDIT]** — `V3_MATHEMATICAL_AUDIT_REPORT.md`: the prior system's mathematical audit.
- **[REF-API]** — `Unity_Data_Extraction_API.md`: the Coveo endpoint contract.

Where this SRS departs from `[REF-MATH]`, the departure and its reason are stated explicitly (see §2.1).

---

## 2. Overall Description

### 2.1 Product perspective — what changed from the reviewed V3 design, and why

This is a clean MVP rebuild, not a port. Three changes are made relative to `[REF-MATH]`, each tied to a specific finding:

1. **The natural-log transform on `DemandPerAssetRaw`, `DemandMedianRaw`, `BreadthRaw`, and `MedianAgeRaw` is removed.** Midrank percentile normalization (§6.5) depends only on order relations between values. Any strictly monotonic transform, including `ln(1+x)`, preserves every `<`, `>`, and `=` relation exactly, so it cannot change the resulting percentile. Since these four raw fields are used only as percentile-normalization inputs, the log step has no effect on any score and is deleted for code simplicity. **REQ-MET-010** below is normative on this point.
2. **The reference cohort is replaced with a leave-one-out (LOO) reference constructed from the operator's own category set**, per the explicit MVP requirement that every specified category SHALL be scored and none SHALL be excluded as reference-only. This is **DD-1**, detailed in §6.5, and it changes what a score *means*: it is a within-run relative comparison, not a comparison against a fixed, cross-time external benchmark.
3. **The override/provisional workflow, cross-run provenance-compatibility gates, and the stability module (nested-prefix / independent-policy analysis) are cut from the MVP.** They existed in `[REF-MATH]` to protect a *frozen, cross-run* reference cohort from drift and contamination. Because the MVP reference is reconstructed fresh from the current run's own data (DD-1), the specific failure modes those mechanisms guarded against (stale reference, target/reference overlap, mismatched collection provenance) cannot occur by construction — target and reference rows always share the same run, same cutoff, same collection method. See §10 for the full non-goals list.

Everything else in `[REF-MATH]` that was assessed as sound — missing-vs-zero handling, coverage-based shrinkage toward 0.5, confidence as a completeness heuristic kept separate from the score, and the general midrank/component/composite structure — is retained and made normative below.

### 2.2 Product functions (summary)

- `F1` — Accept an operator-supplied list of Unity Asset Store category paths.
- `F2` — Extract listing data for each category via the Coveo endpoint, with pagination, retry, and rate-limit handling.
- `F3` — Persist raw observations and run metadata.
- `F4` — Compute per-category metrics (demand, breadth, recent-supply, quality).
- `F5` — Normalize each category's metrics against an LOO reference built from the other categories in the same run.
- `F6` — Compute components `D`, `C`, `R`, `Q` and the composite score for every category.
- `F7` — Compute confidence, coverage status, and rankability for every category.
- `F8` — Persist results.
- `F9` — Display results in a local dashboard.

### 2.3 User characteristics

Single local operator (e.g., a 3D artist or analyst) running the tool on their own machine. Technical enough to set an environment variable and run a CLI command. No multi-user, no remote access, no role-based permissions.

### 2.4 Operating environment

- Python 3.11 or later, single OS process, single machine (Windows, macOS, or Linux).
- Local filesystem for SQLite storage; outbound HTTPS to the Coveo endpoint only.
- No required cloud services, no required paid third-party services.

### 2.5 Design and implementation constraints

- **REQ-GEN-010**: The system SHALL implement the Coveo request contract exactly as specified in `[REF-API]` (endpoint, headers, minimal request shape, category facet mechanics, pagination) unless explicitly overridden below.
- **REQ-GEN-020**: The system SHALL NOT persist, log, or transmit the Coveo bearer token in any form other than passing it in the `Authorization` header of the outbound request for which it is needed.
- **REQ-GEN-030**: The scoring engine (metrics + normalization + components + composite + confidence) SHALL be implemented as pure functions: given the same inputs, they SHALL return the same outputs, and SHALL NOT perform network I/O, file I/O, or read the system clock. The single UTC cutoff SHALL be an explicit parameter, captured once by the orchestration layer at run start.

### 2.6 Assumptions, dependencies, and open data gaps

**OI-1 (blocking): Views/popularity field mapping is unconfirmed.** `[REF-API]`'s `fieldsToInclude` list (`permanentid`, `ec_name`, `ec_category`, `publisher_name`, `ec_product_id`, `ec_price`, `ec_rating`, `ec_rating_count`, `ec_thumbnails`, `ec_tags`, `min_unity_version`) does not include any field carrying a view count or popularity signal, yet the Demand (`D`) and Quality (`Q`) components both require `weekly_views_equivalent`, which needs a view count and a time window. **Before REQ-MET-010 or REQ-EXT-040 can be implemented, the operator SHALL inspect a live Coveo response for this index and identify the actual field name(s)** carrying a view/popularity count and its associated time window (if the index exposes a rolling fixed-window popularity figure instead of a raw count, the metric definition in §6.4 SHALL be adapted accordingly and this SRS SHALL be revised). Until resolved, the configuration keys `VIEWS_COUNT_FIELD` and `VIEWS_WINDOW_DAYS_FIELD` (Appendix C) SHALL remain unset, and **REQ-EXT-050** requires the system to fail fast rather than silently proceed without demand data.

**OI-2 (blocking): Publication-date field mapping is unconfirmed.** `[REF-API]` mentions `first_published_at` only in the list of fields to preserve for faithful *request*-body replay; it is not confirmed as a *response* field name. The Recent-Supply (`R`) component requires each asset's publication date. **The operator SHALL confirm the actual response field name** and set `PUBLISH_DATE_FIELD` (Appendix C) before `R` can be computed. Same fail-fast requirement as OI-1.

**OI-3: The full category taxonomy (all "idle" `ec_category` facet values) is not supplied.** `[REF-API]` requires preserving the complete facet structure, including idle category values, for faithful browser replay. **The operator SHALL capture one real browser request once and save its full facet block as a static asset** `config/category_taxonomy.json` (see REQ-EXT-020). This SRS specifies the mechanism, not the data.

**OI-4: Asset identity field names are inferred, not confirmed.** `[REF-API]` and `[REF-MATH]` describe asset identity generically as "the first non-empty value of `asset_id`, `source_url`, or `url`." This SRS maps that to concrete Coveo fields in REQ-EXT-060 as a best-effort default (`ec_product_id` → `permanentid` → response-level `clickUri`/`uri`); the operator SHOULD confirm these are the correct field names against a live response before relying on deduplication behavior.

- **Assumption A-1**: `timezone` in the Coveo request body does not affect `ec_category` filtering correctness and MAY default to `"UTC"` rather than the session-specific `"Asia/Tehran"` value shown as an example in `[REF-API]`. If this assumption is found false during OI-1–OI-3 verification, it SHALL be revised.
- **Assumption A-2**: The operator holds a currently valid Coveo bearer token and is responsible for refreshing it; token acquisition/automation is out of scope (§10).
- **Dependency**: Outbound network access to `unitytechnologiesproductionmkahteav.org.coveo.com` on port 443.

---

## 3. System Architecture

### 3.1 Modules and responsibilities

| Module | Responsibility | I/O? |
|---|---|---|
| `extraction` | Build and send Coveo requests, paginate, validate category application, retry/backoff | Yes (network) |
| `persistence` | SQLite schema, read/write of runs, raw observations, results | Yes (disk) |
| `metrics` | Per-category metric computation from raw observations + cutoff | No (pure) |
| `scoring` | Normalization, components, composite, confidence, coverage, rankability | No (pure) |
| `pipeline` | Orchestrates extraction → persistence → metrics → scoring → persistence of results | Yes (coordinates the above) |
| `dashboard` | Read-only local UI over persisted results | Yes (disk read only) |
| `cli` | Entry point, argument parsing, config loading | Yes |

### 3.2 Data flow (one run)

```text
1. CLI loads operator category list + config + env token.
2. pipeline generates run_id (UUID4) and cutoff_utc = now(UTC), writes `runs` row (status=running).
3. For each category: extraction.fetch_category(category, cutoff) -> raw records (paginated, retried).
4. persistence stores each raw record as a row in `raw_observations`, tagged with run_id + category.
5. For each category: metrics.compute(raw_observations_for[category], cutoff_utc) -> per-category metric bundle.
6. scoring.build_reference(all_metric_bundles, exclude=target_category) -> LOO reference for that target (per REQ-NRM-010).
7. scoring.score_category(target_bundle, loo_reference) -> D, C, R, Q, composite, confidence, coverage_status, rankable.
   Repeated for every category in the run (REQ-SCR-010).
8. persistence writes one row per category into `category_scores`.
9. pipeline marks `runs.status = completed`.
10. dashboard reads `category_scores` (optionally filtered by run_id) for display.
```

### 3.3 Purity boundary

**REQ-GEN-040**: The `metrics` and `scoring` modules SHALL NOT import or call anything in `extraction`, `persistence`, or `dashboard`. They SHALL accept plain Python data structures (dataclasses / typed dicts) and return plain data structures. This boundary SHALL be enforced by a dedicated import-linter test (§9).

---

## 4. External Interface Requirements

### 4.1 Coveo Search API (source of truth: `[REF-API]`)

- **REQ-EXT-010**: Endpoint SHALL be exactly `POST https://unitytechnologiesproductionmkahteav.org.coveo.com/rest/search/v2?organizationId=unitytechnologiesproductionmkahteav`.
- **REQ-EXT-020**: The request body SHALL be built from a static base template stored at `config/category_taxonomy.json` (OI-3) containing the full facet block (all idle `ec_category` values) captured from a real browser session, with only the `currentValues` entry for the target category set to `"state": "selected"` and all others set to `"state": "idle"`, per `[REF-API]`.
- **REQ-EXT-030**: Headers SHALL be exactly: `Authorization: Bearer <token>`, `Content-Type: application/json`, `Accept: application/json`, `Origin: https://assetstore.unity.com`, `Referer: https://assetstore.unity.com/`. The token SHALL be read from the environment variable `NICHESCOUT_COVEO_BEARER_TOKEN` at process start; if absent or empty, the process SHALL exit with a non-zero status and an error message that does not echo any partial token value.
- **REQ-EXT-040**: `fieldsToInclude` SHALL contain at minimum: `permanentid`, `ec_name`, `ec_category`, `publisher_name`, `ec_product_id`, `ec_price`, `ec_rating`, `ec_rating_count`, `ec_thumbnails`, `ec_tags`, `min_unity_version`, plus the fields resolved under OI-1 and OI-2 once confirmed.
- **REQ-EXT-050**: At startup, the system SHALL validate that `VIEWS_COUNT_FIELD`, `VIEWS_WINDOW_DAYS_FIELD` (or a documented fixed-window equivalent), and `PUBLISH_DATE_FIELD` are configured (non-empty). If any is unset, the system SHALL abort before making any network request, with an error identifying OI-1/OI-2 by name.
- **REQ-EXT-060**: Per-asset identity SHALL be resolved as the first non-empty value, in this priority order: `ec_product_id`, `permanentid`, response-level `clickUri`, response-level `uri` (OI-4). A record with no non-empty value in any of these fields SHALL be dropped and logged as a warning, not silently included.
- **REQ-EXT-070**: `numberOfResults` SHALL be `96` per page (the documented maximum). `firstResult` SHALL increment by `96` each page. Pagination SHALL stop when a page returns fewer than `96` results, or when accumulated results for the category reach `MAX_RESULTS_PER_CATEGORY` (Appendix C, default `2000`), whichever comes first.
- **REQ-EXT-080**: No free-text `q` or `query` field SHALL be present in any request body (per `[REF-API]`'s explicit warning that this contaminates category filtering with keyword relevance).
- **REQ-EXT-090**: After each category's extraction completes, the system SHALL validate category application by checking, in order: (a) `advancedExpression` in the response, if present, contains the requested category string; (b) for each returned result, the normalized (`.strip().casefold()`) `ec_category` field contains the normalized requested category string. A category whose returned results fail (b) for more than 0% of records SHALL be flagged with a `category_mismatch` warning in the run log but SHALL NOT halt the run. A `totalCount` of zero SHALL NOT be treated as an error — it is valid evidence of zero discovery breadth (**REQ-MET-030**).
- **REQ-EXT-100**: Between consecutive Coveo requests (across all categories/pages in a run), the system SHALL wait at least `MIN_REQUEST_INTERVAL_SECONDS` (default `1.0`s, configurable). On HTTP `429` or `5xx`, the system SHALL retry with exponential backoff (base `2.0`s, up to `MAX_RETRIES` = `5`), honoring a `Retry-After` response header when present, before giving up and marking that page as failed (failure removes that page's records from the category's `observed_*` counts; it SHALL NOT be treated as zero evidence).

### 4.2 Category input interface

- **REQ-CAT-010**: The operator SHALL supply categories via a JSON file, default path `config/categories.json`, containing a JSON array of strings, e.g. `["3d > props > exterior", "3d > props > interior"]`.
- **REQ-CAT-020**: Each category string SHALL be validated against the pattern `^[a-z0-9]+( > [a-z0-9\- ]+)*$` (lowercase segments separated by `" > "`). Any entry that does not match after `.strip().lower()` normalization SHALL cause the run to abort with the offending entry named in the error.
- **REQ-CAT-030**: Duplicate category strings (after normalization) SHALL be deduplicated with a warning; the deduplicated, order-preserved list is the operative category set for the run.
- **REQ-CAT-040**: The operative category set SHALL contain at least `MIN_CATEGORIES_PER_RUN` = `2` entries (the mathematical minimum for any LOO reference to exist). If fewer, the run SHALL abort with an explanatory error. A count below `RECOMMENDED_MIN_CATEGORIES_PER_RUN` = `21` SHALL NOT block the run — it SHALL run and simply produce a lower `reference_factor` (§6.7), consistent with the requirement that no specified category is ever excluded from scoring.

### 4.3 Dashboard interface (see also §6.9)

- **REQ-DSH-010**: The dashboard SHALL be launched by a single command and SHALL open a local web page with no authentication step, reflecting single-operator, local-only use.

---

## 5. Data Model

### 5.1 SQLite schema (authoritative DDL)

```sql
CREATE TABLE runs (
    run_id                TEXT PRIMARY KEY,
    created_at_utc        TEXT NOT NULL,
    cutoff_utc             TEXT NOT NULL,
    categories_json          TEXT NOT NULL,
    config_snapshot_json       TEXT NOT NULL,
    status                       TEXT NOT NULL CHECK (status IN ('running','completed','failed'))
);

CREATE TABLE raw_observations (
    observation_id         INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id                   TEXT NOT NULL REFERENCES runs(run_id),
    category                   TEXT NOT NULL,
    asset_identity_key           TEXT NOT NULL,
    ec_product_id                  TEXT,
    permanentid                       TEXT,
    source_url                          TEXT,
    ec_name                                TEXT,
    publisher_name                            TEXT,
    ec_price                                     REAL,
    ec_rating                                      REAL,
    ec_rating_count                                  INTEGER,
    views_count                                        REAL,
    views_window_days                                    REAL,
    publish_date_utc                                       TEXT,
    raw_json                                                 TEXT NOT NULL,
    retrieved_at_utc                                           TEXT NOT NULL,
    UNIQUE (run_id, category, asset_identity_key)
);

CREATE TABLE category_scores (
    run_id                          TEXT NOT NULL REFERENCES runs(run_id),
    category                          TEXT NOT NULL,
    observed_asset_count                INTEGER NOT NULL,
    usable_view_count                      INTEGER,
    usable_view_coverage                      REAL,
    median_weekly_views                          REAL,
    views_per_observed_asset                        REAL,
    observed_discovery_breadth                         INTEGER NOT NULL,
    dated_asset_count                                     INTEGER,
    dated_coverage                                           REAL,
    recent_share_365                                            REAL,
    median_age_days                                                REAL,
    quality_eligible_count                                            INTEGER,
    quality_observation_coverage                                         REAL,
    quality_adjusted_visibility                                             REAL,
    component_d                                                                REAL,
    component_c                                                                   REAL,
    component_r                                                                      REAL,
    component_q                                                                         REAL,
    market_opportunity_score                                                               REAL,
    score_state                                                                               TEXT NOT NULL CHECK (score_state IN ('available','partial','unavailable')),
    missing_components_json                                                                     TEXT NOT NULL,
    effective_sample_size                                                                          REAL,
    confidence                                                                                        REAL,
    coverage_status                                                                                      TEXT NOT NULL CHECK (coverage_status IN ('insufficient_data','partial','full')),
    rankable                                                                                                INTEGER NOT NULL CHECK (rankable IN (0,1)),
    reference_size                                                                                            INTEGER NOT NULL,
    computed_at_utc                                                                                              TEXT NOT NULL,
    PRIMARY KEY (run_id, category)
);
```

### 5.2 Data dictionary (selected non-obvious fields)

| Field | Type | Nullable | Domain | Notes |
|---|---|---|---|---|
| `asset_identity_key` | TEXT | No | non-empty | Resolved per REQ-EXT-060 |
| `views_count` | REAL | Yes | ≥ 0, finite | Null = unavailable, never coerced to 0 |
| `views_window_days` | REAL | Yes | > 0, finite | Null = unavailable |
| `publish_date_utc` | TEXT | Yes | ISO 8601 UTC, ≤ `cutoff_utc` | A value after `cutoff_utc` SHALL be stored as-is but treated as unavailable by `metrics` (REQ-MET-050) |
| `market_opportunity_score` | REAL | Yes | `[0,1]` when non-null | Null iff `score_state = 'unavailable'` |
| `missing_components_json` | TEXT | No | JSON array, e.g. `[]`, `["Q"]`, `["D","R"]` | Replaces the enumerated fallback-state approach of `[REF-MATH]` with a direct list, per DD-2 (§6.6) |
| `reference_size` | INTEGER | No | ≥ 1 | Number of *other* categories in this run used as this row's LOO reference (= N − 1) |
| `rankable` | INTEGER | No | 0 or 1 | See REQ-CNF-040 |

---

## 6. Functional Requirements

### 6.1 Demand metric

- **REQ-MET-010**: For each raw observation with finite `views_count ≥ 0` and finite `views_window_days > 0`:
  ```text
  weekly_views_equivalent = views_count * 7 / views_window_days
  ```
  A record with `views_count`, `views_window_days` missing, non-finite, boolean, wrong-typed, or `views_window_days ≤ 0` SHALL be excluded from the *usable* view population for that category (not coerced to 0). An explicit `views_count = 0` with a valid window IS usable and yields `weekly_views_equivalent = 0`.
- **REQ-MET-020**: Per category:
  ```text
  observed_asset_count      = count of distinct asset_identity_key observed in this category after dedup
  usable_view_count         = count of those with a usable weekly_views_equivalent
  usable_view_coverage      = usable_view_count / observed_asset_count   (0 if observed_asset_count = 0)
  median_weekly_views       = median(weekly_views_equivalent over usable records)
  sum_weekly_views_usable   = sum(weekly_views_equivalent over usable records)
  views_per_observed_asset  = sum_weekly_views_usable / observed_asset_count   (0 if observed_asset_count = 0)
  ```
  `views_per_observed_asset` is defined over the full observed population (not just the usable subset) so that categories with many unusable/missing view records are not inflated; `usable_view_coverage` separately expresses how much of that mean is backed by usable evidence.
- **REQ-MET-030**: Raw fields for normalization (no log transform, per §2.1 finding 1):
  ```text
  DemandPerAssetRaw = views_per_observed_asset
  DemandMedianRaw   = median_weekly_views
  ```

### 6.2 Competition (breadth) metric

- **REQ-MET-040**: `observed_discovery_breadth` = count of distinct `asset_identity_key` returned for the category after dedup. A zero-result category (`totalCount = 0`, REQ-EXT-090) SHALL yield `observed_discovery_breadth = 0`, which is valid evidence, not missing data.
- **REQ-MET-050**: `BreadthRaw = observed_discovery_breadth` (no log transform).

### 6.3 Recent-supply metric

- **REQ-MET-060**: For each distinct asset with a usable `publish_date_utc` (non-null, parseable ISO 8601, ≤ `cutoff_utc`):
  ```text
  age_days = (cutoff_utc - publish_date_utc).days
  ```
  A `publish_date_utc` strictly after `cutoff_utc` SHALL be treated as unavailable and SHALL count toward `missing_date_coverage`, not toward `dated_asset_count`.
- **REQ-MET-070**:
  ```text
  dated_asset_count     = count of distinct assets with a usable publish_date_utc
  dated_coverage        = dated_asset_count / observed_asset_count           (0 if observed_asset_count = 0)
  recent_share_365      = count(dated assets with age_days <= 365) / dated_asset_count   (null if dated_asset_count = 0)
  median_age_days       = median(age_days over dated assets)                              (null if dated_asset_count = 0)
  RecentShareRaw        = recent_share_365
  MedianAgeRaw           = median_age_days      (no log transform)
  ```
  `RECENT_WINDOW_DAYS = 365` is inclusive (`age_days <= 365` counts as recent).

### 6.4 Quality metric

- **REQ-MET-080**: An asset is *quality-eligible* iff it has a finite `ec_rating` in `[0, 5]` AND a usable `weekly_views_equivalent` (REQ-MET-010). Review count (`ec_rating_count`) is NOT an eligibility condition and is NOT a weight, per `[REF-MATH]`. (This is retained as a known inherited limitation — see §11, item L-4.)
- **REQ-MET-090**:
  ```text
  quality_adjusted_visibility = sum((ec_rating / 5) * weekly_views_equivalent over eligible assets)
                               / sum(weekly_views_equivalent over eligible assets)
  ```
  Unavailable (null) if the eligible set is empty or the denominator is exactly 0 (i.e., all eligible assets have zero weekly views — no unweighted-rating fallback is used).
  ```text
  quality_eligible_count        = count of distinct quality-eligible assets
  quality_observation_coverage  = quality_eligible_count / observed_asset_count   (0 if observed_asset_count = 0)
  QualityRaw                    = quality_adjusted_visibility
  ```

### 6.5 Reference construction and normalization

**DD-1 (binding design decision — leave-one-out reference).** For a run with operative category set `S = {c_1, ..., c_N}` (`N ≥ 2`, REQ-CAT-040), and for each target category `c_i`, the reference set is:
```text
Reference(c_i) = { raw-field values of c_j for all j != i, j in 1..N }
```
- **REQ-NRM-010**: Every category in `S` SHALL be scored as a target exactly once per run. No category in `S` SHALL be withheld from scoring to serve only as a reference, satisfying the explicit MVP requirement that no specified category is excluded.
- **REQ-NRM-020**: `reference_size` for `c_i` SHALL equal `N - 1` and SHALL be stored per row (§5.1).
- **Consequence (non-normative, stated for clarity)**: a score is a statement about how `c_i` compares to the *other categories the operator chose to include in the same run*, not an absolute, cross-time benchmark. Re-running with a different category set, or a different `N`, will generally change every score, including for categories present in both runs. This replaces the frozen, cross-run-comparable reference of `[REF-MATH]`.

- **REQ-NRM-030**: Midrank percentile of target value `x` against reference set `r_1..r_m` (only usable, non-null reference values counted; `m` = count of usable reference values):
  ```text
  L = count of usable r_k < x
  E = count of usable r_k = x
  P_ref(x) = (L + 0.5*E) / m        (undefined if m = 0)
  ```
  A null target value SHALL yield a null percentile regardless of `m`. Ties SHALL receive the same midpoint value. An all-equal usable reference set SHALL yield `P_ref(x) = 0.5` for any usable `x`.
- **REQ-NRM-040**: All six normalized fields (`DemandPerAssetRaw`, `DemandMedianRaw`, `BreadthRaw`, `RecentShareRaw`, `MedianAgeRaw`, `QualityRaw`) SHALL be normalized independently via REQ-NRM-030, each against the corresponding raw field's values across `Reference(c_i)`.
- **REQ-NRM-050**: Formulas SHALL be evaluated at full `float64` precision internally. Persisted values SHALL NOT be pre-rounded; display-only rounding (3 decimal places) is a dashboard concern only (REQ-DSH-030).

### 6.6 Components and composite score

- **REQ-SCR-010**: For target category `c_i`, using `p = P_ref(DemandPerAssetRaw)`, `m = P_ref(DemandMedianRaw)`:
  ```text
  D0 = 0.60*p + 0.40*m                         if both p and m are usable
     = the single usable value                  if exactly one is usable
     = undefined                                 if neither is usable
  D  = clamp(0.5 + usable_view_coverage * (D0 - 0.5), 0, 1)     if D0 is defined AND usable_view_count >= 1
     = unavailable                                                otherwise
  ```
- **REQ-SCR-020**: Using `b = P_ref(BreadthRaw)`:
  ```text
  C = clamp(1 - b, 0, 1)     if b is defined
    = unavailable             otherwise
  ```
- **REQ-SCR-030**: Using `s = P_ref(RecentShareRaw)`, `a = P_ref(MedianAgeRaw)`:
  ```text
  Rpressure0 = 0.70*s + 0.30*(1 - a)            if both s and a are usable
             = the single usable subcomponent     if exactly one is usable (s, or 1-a)
             = undefined                            if neither is usable
  R0 = 1 - Rpressure0                              if Rpressure0 is defined
  R  = clamp(0.5 + dated_coverage * (R0 - 0.5), 0, 1)
       if R0 is defined AND dated_asset_count >= 2 AND at least one of (s, a) is usable
     = unavailable      otherwise
  ```
- **REQ-SCR-040**: Using `q = P_ref(QualityRaw)`:
  ```text
  Q0 = 1 - q                                      if q is defined
  Q  = clamp(0.5 + quality_observation_coverage * (Q0 - 0.5), 0, 1)
       if Q0 is defined AND quality_eligible_count >= 2 AND quality_observation_coverage > 0
     = unavailable      otherwise
  ```
- **REQ-SCR-050**: Fixed top-level weights: `w_D = 0.35`, `w_C = 0.30`, `w_R = 0.20`, `w_Q = 0.15` (sum to 1.0; not empirically re-derived in the MVP — see §11, item L-2). Let `A` = the set of available components for `c_i`, `W_A = sum(w_x for x in A)`:
  ```text
  if |A| < 2:
      market_opportunity_score = null
      score_state = "unavailable"
  else:
      S_available = sum(w_x * value_x for x in A) / W_A
      market_opportunity_score = clamp(0.5 + W_A * (S_available - 0.5), 0, 1)
      score_state = "available" if |A| = 4 else "partial"
  ```
- **REQ-SCR-060 (DD-2)**: `missing_components_json` SHALL be the JSON array of component names (subset of `["D","C","R","Q"]`) not in `A`, replacing the enumerated fallback-state names of `[REF-MATH]` (`missing_demand`, etc.) with a direct, always-accurate list. This is a simplification, not a behavior change.

### 6.7 Confidence, coverage, and rankability

- **REQ-CNF-010**:
  ```text
  source_coverage(D) = usable_view_coverage
  source_coverage(C) = 1.0
  source_coverage(R) = dated_coverage
  source_coverage(Q) = quality_observation_coverage
  effective_sample_size = observed_asset_count * min(source_coverage(x) for x in A)   (0 if A is empty)
  ```
- **REQ-CNF-020**:
  ```text
  sample_factor      = clamp(effective_sample_size / 60, 0, 1)
  component_coverage = W_A                                        (sum of available top-level weights, REQ-SCR-050)
  reference_factor    = clamp(reference_size / 20, 0, 1)            (reference_size per REQ-NRM-020; denominator chosen so N=21 total categories, i.e. reference_size=20, yields reference_factor=1, preserving the numeric intent of [REF-AUDIT]'s 21-member threshold under the new LOO design)
  confidence           = clamp(0.50*sample_factor + 0.30*component_coverage + 0.20*reference_factor, 0, 1)
  ```
  Confidence is an evidence-completeness heuristic. **REQ-CNF-025**: it SHALL NOT be multiplied into `market_opportunity_score` at any point.
- **REQ-CNF-030**:
  ```text
  coverage_status = "insufficient_data"   if score_state = "unavailable" OR observed_asset_count < 10
                   = "partial"             elif score_state = "partial" OR effective_sample_size < 60
                   = "full"                 otherwise
  ```
- **REQ-CNF-040**: `rankable = 1` iff ALL of: `score_state = "available"`; `coverage_status = "full"`; `observed_discovery_breadth` and all other inputs came from a category whose extraction produced no unresolved `category_mismatch` warning (REQ-EXT-090). Otherwise `rankable = 0`. (This is a deliberate simplification of `[REF-MATH]`'s multi-field rankability predicate — see §10 item ND-3.)

### 6.8 Persistence of results

- **REQ-PER-010**: The pipeline SHALL write exactly one `category_scores` row per category per run, using `INSERT` (never `UPDATE`) — a re-run SHALL use a new `run_id`, preserving prior runs for comparison.
- **REQ-PER-020**: All raw observation rows for a run SHALL be retained (not deleted) after scoring, to allow re-scoring from persisted raw data without re-extraction.

### 6.9 Dashboard

- **REQ-DSH-020**: The dashboard SHALL present a sortable, filterable table with one row per category (default: most recent `run_id`), showing at minimum: `category`, `market_opportunity_score`, `component_d`, `component_c`, `component_r`, `component_q`, `confidence`, `coverage_status`, `rankable`, `observed_asset_count`.
- **REQ-DSH-030**: Numeric display values SHALL be rounded to 3 decimal places for display only; underlying stored precision is unaffected (REQ-NRM-050).
- **REQ-DSH-040**: The dashboard SHALL provide a bar chart of `market_opportunity_score` across all categories in the selected run, and, on selecting a single category, a small chart of its four component values.
- **REQ-DSH-050**: A run selector SHALL allow choosing among previously completed runs (by `run_id`/`created_at_utc`). The dashboard SHALL NOT allow editing persisted data.
- **REQ-DSH-060**: Non-rankable rows (`rankable = 0`) SHALL be visually distinguished (e.g., a badge or muted row style) rather than hidden, so the operator can still see their score/coverage context.

### 6.10 CLI / orchestration

- **REQ-CLI-010**: `niche-scout run --categories config/categories.json --config config/default.toml` SHALL execute the full pipeline (§3.2) in one process and exit non-zero on any unrecoverable error.
- **REQ-CLI-020**: `niche-scout dashboard` SHALL launch the dashboard against the existing SQLite database without re-running extraction.
- **REQ-CLI-030**: All configuration constants in Appendix C SHALL be overridable via `config/default.toml`, with CLI flags taking precedence over the TOML file, which takes precedence over hard-coded defaults.

---

## 7. Non-Functional Requirements

- **REQ-NFR-010 (Performance)**: The system SHALL handle at least 50 categories with up to 2,000 assets each in a single run on a typical consumer laptop without exceeding available memory, by streaming persistence (writing raw observations as pages arrive rather than buffering an entire run in memory).
- **REQ-NFR-020 (Reliability)**: A network failure on any single category's extraction SHALL NOT abort the run for other categories; the failed category SHALL be marked and reported, and scoring SHALL proceed for all successfully extracted categories.
- **REQ-NFR-030 (Maintainability)**: All public functions in `metrics` and `scoring` SHALL have type hints and a docstring stating inputs, outputs, and null/edge-case behavior. See §8.3 for enforced tooling.
- **REQ-NFR-040 (Security)**: No secret (bearer token) SHALL appear in source control, logs, or the SQLite database. `.env` files SHALL be listed in `.gitignore`.
- **REQ-NFR-050 (Portability)**: The system SHALL run unmodified on Windows, macOS, and Linux under Python 3.11+, using only cross-platform-safe file path handling (`pathlib`).
- **REQ-NFR-060 (Usability)**: A first-time operator SHALL be able to go from a cloned repository to a rendered dashboard using only the steps documented in `README.md`, with no undocumented manual step.

---

## 8. Project Structure and Coding Conventions

### 8.1 Directory layout

```text
niche-scout/
├── README.md
├── pyproject.toml
├── .env.example
├── .gitignore
├── config/
│   ├── default.toml
│   ├── categories.json
│   └── category_taxonomy.json        # OI-3: captured once from a live browser session
├── src/
│   └── niche_scout/
│       ├── __init__.py
│       ├── config.py
│       ├── cli.py
│       ├── pipeline.py
│       ├── extraction/
│       │   ├── __init__.py
│       │   ├── coveo_client.py
│       │   └── validation.py
│       ├── persistence/
│       │   ├── __init__.py
│       │   ├── schema.sql
│       │   └── db.py
│       ├── metrics/
│       │   ├── __init__.py
│       │   ├── demand.py
│       │   ├── competition.py
│       │   ├── recent_supply.py
│       │   └── quality.py
│       ├── scoring/
│       │   ├── __init__.py
│       │   ├── normalization.py
│       │   ├── components.py
│       │   ├── composite.py
│       │   └── confidence.py
│       └── dashboard/
│           ├── __init__.py
│           └── app.py
├── tests/
│   ├── conftest.py
│   ├── unit/
│   │   ├── test_normalization.py
│   │   ├── test_demand.py
│   │   ├── test_competition.py
│   │   ├── test_recent_supply.py
│   │   ├── test_quality.py
│   │   ├── test_components.py
│   │   ├── test_composite.py
│   │   └── test_confidence.py
│   ├── golden/
│   │   └── test_golden_vectors.py
│   └── architecture/
│       └── test_purity_boundary.py
└── docs/
    └── SRS.md
```

### 8.2 Naming conventions

| Category | Convention | Example |
|---|---|---|
| Python modules/files | `snake_case.py` | `recent_supply.py` |
| Classes | `PascalCase` | `CategoryMetricBundle` |
| Functions/variables | `snake_case` | `compute_demand_component` |
| Constants | `UPPER_SNAKE_CASE` | `MIN_CATEGORIES_PER_RUN` |
| Test files | `test_<module>.py` | `test_demand.py` |
| Test functions | `test_<behavior>__<condition>` | `test_demand_component__zero_views_is_valid` |
| SQLite tables | plural `snake_case` | `category_scores` |
| SQLite columns | `snake_case`, `_utc` suffix for timestamps, `_id` suffix for identifiers | `created_at_utc`, `run_id` |
| Environment variables | `NICHESCOUT_UPPER_SNAKE_CASE` | `NICHESCOUT_COVEO_BEARER_TOKEN` |
| Config (TOML) keys | `snake_case` | `min_request_interval_seconds` |
| Git branches | `type/short-description` | `feat/loo-reference` |
| Commit messages | Conventional Commits | `fix(scoring): remove inert log transform` |

### 8.3 Code quality standards

- **REQ-NFR-070**: Formatting SHALL be enforced with `black` (line length 100); linting with `ruff`; both SHALL run in CI on every commit.
- **REQ-NFR-080**: `mypy --strict` SHALL pass on `src/niche_scout/metrics` and `src/niche_scout/scoring`.
- **REQ-NFR-090**: No bare `except:`; no mutable default arguments; no wildcard imports.
- **REQ-NFR-100**: Docstrings SHALL use Google style and SHALL document null/edge-case behavior for any function implementing a requirement in §6.

### 8.4 Configuration management

- **REQ-CFG-010**: Precedence, highest to lowest: CLI flag > `config/default.toml` > in-code default (Appendix C).
- **REQ-CFG-020**: `config/default.toml` and `config/categories.json` SHALL be the only operator-editable configuration surfaces; constants not exposed in Appendix C are implementation details, not configuration.

---

## 9. Testing Requirements

- **REQ-TST-010**: Every formula in §6.1–§6.7 SHALL have at least one unit test covering: the normal case, the "explicit zero is valid" case where applicable, the "missing/invalid input" case, and the minimum-count boundary (e.g., exactly 1 vs. exactly 2 dated assets for `R`).
- **REQ-TST-020**: A golden-vector test suite (`tests/golden/test_golden_vectors.py`) SHALL fix a synthetic reference set and target values, hand-compute the expected `D`, `C`, `R`, `Q`, composite score, ESS, and confidence, and assert exact (within float tolerance `1e-9`) agreement — mirroring the worked-example discipline of `[REF-AUDIT]`.
- **REQ-TST-030**: `tests/architecture/test_purity_boundary.py` SHALL statically assert that `niche_scout.metrics` and `niche_scout.scoring` import nothing from `niche_scout.extraction`, `niche_scout.persistence`, or `niche_scout.dashboard` (REQ-GEN-040).
- **REQ-TST-040**: Minimum line coverage for `metrics` and `scoring` packages SHALL be 95%, enforced in CI.

---

## 10. MVP Non-Goals (Explicitly Deferred)

- **ND-1**: Stability analysis (nested-prefix / independent-policy sensitivity testing) is not implemented. Not needed for MVP correctness; may be added post-MVP as an optional report.
- **ND-2**: No override/provisional workflow. A category either has enough evidence to compute components or it does not; there is no mechanism to force a numeric score past a failed eligibility check.
- **ND-3**: No cross-run provenance-compatibility gates (policy version, collection-mode matching, sort verification). Moot by construction under the single-run LOO design (§2.1).
- **ND-4**: No automated Coveo bearer token acquisition/refresh; operator-supplied only.
- **ND-5**: No authentication, multi-user support, or remote/cloud deployment for the dashboard.
- **ND-6**: No multi-run historical trend view in the dashboard beyond selecting a single prior run (REQ-DSH-050).
- **ND-7**: No automatic re-scoring on a schedule; the CLI is invoked manually.

---

## 11. Known Inherited Limitations (Not Fixed in MVP)

These were identified as real methodological concerns in the prior review but are consciously **not** redesigned in this MVP, to keep it minimal. They are documented so they are not mistaken for oversights.

- **L-1 (compensatory aggregation)**: The composite score is a weighted sum, so a very strong component can offset a very weak one. A category with excellent demand but saturated competition can score similarly to a mediocre, balanced category. No interaction/multiplicative term is implemented.
- **L-2 (fixed, non-empirical weights)**: All weights (`0.35/0.30/0.20/0.15`, `0.60/0.40`, `0.70/0.30`, `0.50/0.30/0.20`) are carried over as fixed constants with no empirical derivation or sensitivity analysis in the MVP.
- **L-3 (per-run reference, not cross-time)**: DD-1 resolves "no category excluded" but means scores are only comparable within one run's category set; comparing a score from one run to a score from a differently-scoped run is not meaningful.
- **L-4 (rating reliability not modeled)**: `quality_adjusted_visibility` weights ratings by traffic, not by the number of reviews behind the rating; a high-traffic asset with one review counts as strongly as one with a thousand.
- **L-5 (outlier concentration)**: `views_per_observed_asset` and `quality_adjusted_visibility` are both susceptible to domination by a single high-traffic asset within a category; no winsorization or cap is applied.

---

## Appendix A — Consolidated Formula Reference

```text
weekly_views_equivalent   = views_count * 7 / views_window_days
DemandPerAssetRaw         = views_per_observed_asset
DemandMedianRaw           = median_weekly_views
BreadthRaw                = observed_discovery_breadth
RecentShareRaw             = recent_share_365
MedianAgeRaw                = median_age_days
QualityRaw                   = quality_adjusted_visibility

P_ref(x) = (L + 0.5*E) / m         [midrank percentile vs. LOO reference, REQ-NRM-030]

D0 = weighted-available-mean(P_ref(DemandPerAssetRaw)*0.60, P_ref(DemandMedianRaw)*0.40)
D  = clamp(0.5 + usable_view_coverage*(D0-0.5), 0, 1)

C  = clamp(1 - P_ref(BreadthRaw), 0, 1)

Rpressure0 = weighted-available-mean(P_ref(RecentShareRaw)*0.70, (1-P_ref(MedianAgeRaw))*0.30)
R0 = 1 - Rpressure0
R  = clamp(0.5 + dated_coverage*(R0-0.5), 0, 1)

Q0 = 1 - P_ref(QualityRaw)
Q  = clamp(0.5 + quality_observation_coverage*(Q0-0.5), 0, 1)

S_available = sum(w_x * x for x in available) / W_A
market_opportunity_score = clamp(0.5 + W_A*(S_available-0.5), 0, 1)

ESS = observed_asset_count * min(source_coverage(x) for x in available)
confidence = clamp(0.50*clamp(ESS/60,0,1) + 0.30*W_A + 0.20*clamp(reference_size/20,0,1), 0, 1)
```

---

## Appendix B — Glossary

See §1.4. No additional terms.

---

## Appendix C — Configuration Constants Reference

| Constant | Default | Configurable? | Requirement |
|---|---|---|---|
| `COVEO_ENDPOINT_URL` | fixed, §4.1 | No | REQ-EXT-010 |
| `PAGE_SIZE` | 96 | No (protocol max) | REQ-EXT-070 |
| `MAX_RESULTS_PER_CATEGORY` | 2000 | Yes | REQ-EXT-070 |
| `MIN_REQUEST_INTERVAL_SECONDS` | 1.0 | Yes | REQ-EXT-100 |
| `MAX_RETRIES` | 5 | Yes | REQ-EXT-100 |
| `RETRY_BACKOFF_BASE_SECONDS` | 2.0 | Yes | REQ-EXT-100 |
| `MIN_CATEGORIES_PER_RUN` | 2 | No | REQ-CAT-040 |
| `RECOMMENDED_MIN_CATEGORIES_PER_RUN` | 21 | Yes (informational) | REQ-CAT-040 |
| `REFERENCE_FACTOR_DENOMINATOR` | 20 | Yes | REQ-CNF-020 |
| `SAMPLE_FACTOR_DENOMINATOR` | 60 | Yes | REQ-CNF-020 |
| `INSUFFICIENT_DATA_MIN_OBSERVED_ASSETS` | 10 | Yes | REQ-CNF-030 |
| `RECENT_WINDOW_DAYS` | 365 | Yes | REQ-MET-070 |
| `QUALITY_MIN_ELIGIBLE_ASSETS` | 2 | No | REQ-SCR-040 |
| `RECENT_MIN_DATED_ASSETS` | 2 | No | REQ-SCR-030 |
| `w_D, w_C, w_R, w_Q` | 0.35, 0.30, 0.20, 0.15 | Yes (must sum to 1.0) | REQ-SCR-050 |
| `DEMAND_SUBWEIGHTS` | 0.60, 0.40 | Yes | REQ-SCR-010 |
| `RECENT_SUBWEIGHTS` | 0.70, 0.30 | Yes | REQ-SCR-030 |
| `CONFIDENCE_WEIGHTS` | 0.50, 0.30, 0.20 | Yes | REQ-CNF-020 |
| `CURRENCY` | EUR | Yes | §4.1 |
| `LOCALE` | en-US | Yes | §4.1 |
| `TIMEZONE` | UTC (A-1) | Yes | §4.1 |
| `VIEWS_COUNT_FIELD` | **unset (OI-1)** | Yes, required before run | REQ-EXT-050 |
| `VIEWS_WINDOW_DAYS_FIELD` | **unset (OI-1)** | Yes, required before run | REQ-EXT-050 |
| `PUBLISH_DATE_FIELD` | **unset (OI-2)** | Yes, required before run | REQ-EXT-050 |

---

## Appendix D — Requirements Traceability Matrix

| Requirement range | Module |
|---|---|
| REQ-EXT-010–100 | `extraction/coveo_client.py`, `extraction/validation.py` |
| REQ-CAT-010–040 | `cli.py`, `config.py` |
| REQ-MET-010–090 | `metrics/demand.py`, `metrics/competition.py`, `metrics/recent_supply.py`, `metrics/quality.py` |
| REQ-NRM-010–050 | `scoring/normalization.py` |
| REQ-SCR-010–060 | `scoring/components.py`, `scoring/composite.py` |
| REQ-CNF-010–040 | `scoring/confidence.py` |
| REQ-PER-010–020 | `persistence/db.py` |
| REQ-DSH-010–060 | `dashboard/app.py` |
| REQ-CLI-010–030 | `cli.py`, `pipeline.py` |
| REQ-NFR-010–100 | cross-cutting; enforced via CI config + `pyproject.toml` |
| REQ-TST-010–040 | `tests/` |