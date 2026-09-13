# Software Requirements Specification

## Unity Asset Store Niche Scout — Lean Decision-Grade Variant

| Field | Value |
|---|---|
| Document type | Software Requirements Specification (SRS) |
| Parent specification | `SRS-revision2.md`, effective revision 2.3.0 |
| Variant | Lean, sample-based, decision-grade MVP |
| Version | Lean 1.0.0 |
| Status | Draft — decision-grade lean variant |
| Target release | v0.1.0-lean |

## Revision history

| Version | Change |
|---|---|
| Lean 1.0.0 | New standalone lean variant derived from `SRS-revision2.md`. Reduces enrichment, persistence, dashboard, and operational scope while retaining identity integrity, response validation, exact time handling, missing-data safeguards, deterministic scoring, evidence reporting, and ranking-sensitivity diagnostics. |

## Document status and relationship to the parent SRS

This document is a separate implementation target. It does not modify or replace
`SRS-revision2.md`. The parent remains the full-MVP specification; this document
defines a smaller product with deliberately different collection and evidence
policies.

Derived from SRS-revision2.md, including all requirements and corrections identified as version 2.3.0.
The parent header still says `2.2.0`, but its revision history and requirements
explicitly include the effective `2.3.0` corrections; that outdated header is not
authoritative for this lean variant.

Where this document is silent about an external endpoint contract, the corresponding
contract in the parent SRS remains applicable. Where this document is explicit, this
document takes precedence for the lean implementation.

The lean implementation SHALL NOT claim that its scores predict sales, revenue,
downloads, conversion, or causal buyer demand. Its output is a **sample-based, deterministic, within-run market-opportunity heuristic**.

It is not a sales forecast, revenue prediction, causal demand estimate, statistically
representative estimate of the entire Unity Asset Store, or validated weekly traffic
measurement.

---

## 1. Introduction

### 1.1 Purpose

This SRS specifies a locally run tool that:

1. accepts a selected set of Unity Asset Store categories;
2. discovers category breadth and product identities through the Coveo storefront
   search endpoint;
3. selects a deterministic, distributed sample of discovered products for larger
   categories;
4. enriches the union of sampled products through the Unity Asset Store GraphQL
   storefront endpoint;
5. computes demand, competition, recent-supply, and quality-gap signals;
6. normalizes those signals within the same run;
7. reports scores together with sample sizes, coverage, evidence grade, warnings,
   and ranking sensitivity.

The system is intended to help an artist shortlist categories for further
investigation. It is not a sales-forecasting system.

### 1.2 Normative language

- **SHALL** means mandatory for conformance.
- **SHOULD** means recommended; deviation requires a documented reason.
- **MAY** means optional.
- Requirements use the `LREQ-<AREA>-<NNN>` namespace.
- All timestamps used in calculations SHALL be timezone-aware UTC timestamps.
- All formulas operate internally at `float64` precision. Display rounding is not
  part of the calculation.
- Missing, invalid, contradictory, or unavailable values SHALL remain unavailable;
  they SHALL NOT be silently converted to zero.

### 1.3 Product scope

In scope:

- one manually initiated run at a time;
- 8–50 categories per run;
- category taxonomy validation;
- bounded, paginated Coveo discovery;
- deterministic stratified GraphQL enrichment sampling;
- one GraphQL enrichment request per unique sampled asset per run;
- SQLite persistence of audit-critical normalized observations;
- four transparent score components: `D`, `C`, `R`, and `Q`;
- a local sortable report or dashboard;
- deterministic ranking-sensitivity analysis;
- unit, fixture, and one end-to-end test suite.

Out of scope:

- sales or revenue prediction;
- historical trend dashboards;
- scheduled execution;
- resume/checkpoint execution;
- full enrichment of every discovered asset in large categories;
- automated credential acquisition;
- multi-user or cloud deployment;
- a formal population-level statistical confidence interval;
- calibration against downloads, sales, revenue, or an external outcome.

### 1.4 Definitions

| Term | Meaning |
|---|---|
| Discovered population | Distinct canonical asset identities returned by verified category discovery, excluding unresolved/conflicting identities from the canonical denominator but retaining them in audit data. |
| Enrichment sample | Assets selected from a category for GraphQL enrichment. It is a census for small categories and a distributed stratified sample for larger categories. |
| Stratum | One ordinal segment of a category's canonical discovery population. |
| Usable observation | An observation satisfying the component-specific type, range, state, identity, date, and operation-status rules. |
| Coverage | The proportion of the relevant discovered population represented by usable evidence, including stratum population weights where sampling is used. |
| Age-normalized page-view index | `product_page_views * 7 / age_days_exact`, using an undocumented page-view field. It is an unvalidated index, not a validated weekly traffic measurement or weekly traffic rate. |
| Midrank relative position | `(L + 0.5E) / m`, where `L` is the number of usable reference values below the target, `E` is the number equal to it, and `m` is the number of usable reference values. It is descriptive, not inferential. |
| Rankable | Evidence state indicating that a category may be used in the primary ranking under the policies in §9. |
| Within-run | Relative to the category set and collection policy used in one run. Scores are not expected to be comparable across arbitrary runs. |

### 1.5 Source references

- **[PARENT]** — `SRS-revision2.md`, the full-MVP SRS and source for unchanged
  endpoint details.
- **[API]** — `Unity_Data_Extraction_API.md`, as cited by the parent SRS.
- **[MATH]** — `V3_MATHEMATICAL_REFERENCE.md`, as cited by the parent SRS.
- **[AUDIT]** — `V3_MATHEMATICAL_AUDIT_REPORT.md`, as cited by the parent SRS.

The lean SRS is the normative source for sampling, sample-aware estimators,
evidence grades, rankability, and sensitivity analysis.

---

## 2. Scientific and methodological position

### 2.1 Interpretation of the output

The primary output answers:

> Among the categories selected for this run, which categories show the strongest
> observed combination of demand proxy, limited catalog breadth, recent catalog
> activity, and apparent quality gap, given the available evidence?

It does not answer:

- how many units an asset will sell;
- how much revenue a category will generate;
- whether a category causes higher sales;
- whether the selected categories represent the entire marketplace;
- whether the ranking will remain unchanged when the category set changes.

### 2.2 Safeguards that SHALL NOT be removed

The following are analytical safeguards, not optional infrastructure:

1. deterministic category comparison rules;
2. canonical identity resolution and conflict detection;
3. operation-level GraphQL response validation;
4. exact UTC timestamp normalization and a shared scoring cutoff;
5. explicit component-specific eligibility;
6. separate discovered-population and sampled-population counts;
7. coverage-aware shrinkage toward the neutral score `0.5`;
8. no fabricated values for missing data;
9. warnings for incomplete or contradictory data;
10. deterministic score formulas;
11. ranking sensitivity diagnostics;
12. visible evidence grade and rankability state.

### 2.3 Explicit lean trade-off

For categories larger than the configured enrichment sample, product-level
attributes are estimated from a deterministic distributed sample rather than
collected for every discovered asset. Competition remains a breadth measure from
discovery and does not use the enriched sample count as a substitute for catalog
size.

The report SHALL use the phrase **sample-based market signal** for results affected
by sampling.

---

## 3. Architecture and data flow

### 3.1 Components

| Component | Responsibility | Network/file I/O |
|---|---|---|
| `collector` | Coveo discovery, GraphQL enrichment, retries, response validation | Network |
| `sampling` | Canonical population construction, strata, deterministic sample selection | No network |
| `validation` | Taxonomy, identity, type, date, state, and semantic checks | No network |
| `metrics` | Sample-aware demand, competition, recent-supply, and quality metrics | Pure |
| `scoring` | LOO normalization, components, composite score, evidence, sensitivity | Pure |
| `database` | SQLite schema and normalized audit persistence | Disk |
| `pipeline` | Run orchestration and status handling | Coordinates |
| `report` | Sortable local report/dashboard | Disk read |
| `cli` | Configuration and commands | Process I/O |

### 3.2 One-run data flow

1. Load category input, configuration, Coveo credential, and Unity CSRF credential.
2. Validate configuration and the cached category taxonomy before network requests.
3. Create `run_id`, `run_started_at_utc`, policy versions, and a configuration hash.
4. Run the identity preflight described in §4.4 before bulk enrichment.
5. Discover each category with the same endpoint, filter, sort order, page size,
   and pagination rules.
6. Persist each raw discovery observation, including unresolved and conflicting
   identity records.
7. Deduplicate canonical identities within each category for metric purposes while
   retaining every raw API observation for audit.
8. Build ordinal strata and select a deterministic enrichment sample per category.
9. Enrich the union of sampled canonical identities once each.
10. Capture `scoring_cutoff_utc` immediately before metric computation.
11. Compute sample-aware raw metrics and their coverage values.
12. Construct a leave-one-out reference for every category.
13. Compute primary scores, evidence state, warnings, and sensitivity diagnostics.
14. Persist one result row per category and mark the run completed.
15. Render the report without initiating new network requests.

### 3.3 Purity boundary

**LREQ-ARCH-010**: `metrics` and `scoring` SHALL accept plain typed data and SHALL
not import or call `collector`, `database`, `report`, or `cli` code.

**LREQ-ARCH-020**: Pure metric and scoring functions SHALL NOT read the system
clock. All timestamps SHALL be supplied by the orchestration layer.

**LREQ-ARCH-030**: The same normalized input data, policy versions, and configuration
SHALL produce the same metric, score, evidence, and sensitivity outputs.

---

## 4. External interfaces and collection

### 4.1 Coveo discovery

**LREQ-EXT-010**: Discovery SHALL use the parent SRS Coveo endpoint, required
headers, captured taxonomy template, and selected-category facet mechanism.

**LREQ-EXT-020**: The cached taxonomy file SHALL include `schema_version`,
`captured_at_utc`, `source_url`, `template_sha256`, and a canonical category-path
inventory. The system SHALL abort before collection if the file is missing,
malformed, stale, or does not contain every requested category.

**LREQ-EXT-030**: The Coveo request SHALL contain no free-text `q` or `query` field
that could contaminate category filtering with keyword relevance.

**LREQ-EXT-040**: Discovery SHALL use the parent SRS discovery-only field set:
`permanentid`, `ec_product_id`, `ec_name`, `ec_category`, and `publisher_name`.
Product rating, page views, publication date, and price SHALL NOT be sourced from
Coveo for scoring.

**LREQ-EXT-050**: For every requested category, discovery SHALL retrieve all
available pages using the same endpoint, filters, sort order, page size, pagination
rules, and category predicate. It SHALL stop when the verified `totalCount` is
reached, the endpoint returns a natural terminal page, or
`MAX_DISCOVERY_RESULTS_PER_CATEGORY` is reached. The discovery status SHALL be one of `complete`, `truncated`, `page_failed`, `filter_unverified`, `category_mismatch`, `identity_incomplete`, or `request_failed`; a failed or truncated page SHALL never be interpreted as zero assets.

**LREQ-EXT-060**: Each discovery record SHALL retain all non-empty identity
candidates from `ec_product_id`, `permanentid`, response-level `clickUri`, and
response-level `uri`. Candidates SHALL be canonicalized under one versioned mapping
rule.

**LREQ-EXT-070**: If canonical candidates disagree, the record SHALL be marked
`conflict` and excluded from the canonical denominator and enrichment set. If no
candidate can be canonicalized, it SHALL be marked `unresolved`. Neither case may
be silently treated as an ordinary asset.

**LREQ-EXT-080**: Exact category membership SHALL be checked against the canonical
taxonomy. Parent paths SHALL NOT match child paths merely by prefix. Scalar and
multi-valued category response shapes SHALL be handled explicitly.

**LREQ-EXT-090**: A failed page, unverified filter, category mismatch, or material
identity incompleteness SHALL generate a warning and SHALL prevent a fully rankable
competition result for that category.

**LREQ-EXT-100**: Requests SHALL be rate-limited and retry transient `429` and `5xx`
responses with exponential backoff. Permanent authentication, CSRF, malformed
request, or authorization failures SHALL not be retried indefinitely.

### 4.2 GraphQL enrichment

**LREQ-GQL-010**: Enrichment SHALL use the parent SRS GraphQL batch endpoint and
the two required operations: `ProductDetail(id: ID!)` and
`ProductPageViews(packageId: String!)`. Both operations SHALL use the same
canonical `asset_identity_key`.

**LREQ-GQL-020**: The `ProductDetail` operation SHALL request product identity
aliases, `rating.average`, `rating.count`, `reviewCount`, `firstPublishedDate`,
`state`, `category`, and `publisher`. The separate `ProductPageViews` operation
SHALL request its page-view scalar. Fields not required by scoring MAY be omitted
from the lean implementation.

**LREQ-GQL-030**: GraphQL response items SHALL be associated by explicit operation
name or another validated correlation key. Response position alone SHALL NOT be
trusted unless separately validated as an endpoint guarantee.

Reversed operation order SHALL be handled through that correlation key. Missing,
duplicated, unknown, or ambiguous associations SHALL be recorded as malformed
operation results; the implementation SHALL never guess from response position.

**LREQ-GQL-040**: Each operation SHALL have an independent status. HTTP 200 with an
operation-level `errors` member, null required data, wrong data shape, wrong scalar
type, negative page views, non-finite page views, or missing identity SHALL be
recorded as an operation error.

**LREQ-GQL-050**: A valid operation's fields MAY be retained when the other operation
fails. Failed fields SHALL remain null or unavailable; they SHALL NOT be filled with
zero or another default.

**LREQ-GQL-060**: Only `state = "published"` assets are eligible for D, R, and Q.
State-excluded and state-unknown assets remain part of discovered breadth.

**LREQ-GQL-070**: If returned GraphQL identity aliases do not agree with the
requested canonical identity, the asset SHALL be marked `id_mapping_mismatch` and
excluded from D, R, and Q.

**LREQ-GQL-080**: A unique sampled identity SHALL be enriched at most once per run,
regardless of how many category samples reference it. The result SHALL be joined to
every referencing category.

The source separation is mandatory: Coveo is authoritative for category-scoped
discovery, category membership, canonical discovered breadth, and pagination metadata;
GraphQL is authoritative for rating, rating count, review count, first publication
date, page views, publisher, category, state, and product identity confirmation.
Neither source SHALL provide duplicate scoring fields for the same metric.

### 4.3 Credentials and security

**LREQ-SEC-010**: Coveo and Unity CSRF credentials SHALL be read from environment
variables and SHALL be required before network collection.

**LREQ-SEC-020**: Secrets SHALL NOT be written to source control, logs, SQLite, or
error messages. The `.env` pattern SHALL be ignored by version control.

### 4.4 Identity preflight

The formal reusable identity-validation study in the parent SRS is replaced by a
per-run deterministic preflight.

**LREQ-ID-010**: Before bulk enrichment, select at least two canonical assets from
each of at least five categories when five categories are available. If fewer than
five categories are in the run, use every category and record the reduced preflight
coverage.

**LREQ-ID-020**: The preflight SHALL perform the normal GraphQL request and verify:
the request identifier is accepted by both operations; returned product identifiers
are compatible with the requested identity; page-view package identity is
compatible; and no unexplained response-shape or operation-association error
occurred.

**LREQ-ID-030**: Default preflight policy is:

```text
IDENTITY_PREFLIGHT_MIN_CATEGORIES = 5
IDENTITY_PREFLIGHT_ASSETS_PER_CATEGORY = 2
IDENTITY_PREFLIGHT_MAX_CONFLICT_RATE = 0
IDENTITY_PREFLIGHT_MIN_SUCCESS_RATE = 0.90
```

**LREQ-ID-040**: A preflight below the minimum success rate or above the maximum
conflict rate SHALL stop bulk enrichment and mark the run failed. The failure SHALL
include sampled counts, mismatch counts, endpoint signature, mapping-rule version,
and a redacted diagnostic summary.

---

## 5. Deterministic sampling

### 5.1 Sampling policy

**LREQ-SMP-010**: Sampling SHALL occur only after canonical discovery identities
have been resolved and duplicates have been marked.

**LREQ-SMP-020**: The canonical population for a category SHALL be ordered by the
stable discovery ordinal assigned during collection. If the endpoint repeats or
reorders a record, the first valid ordinal is retained and the duplicate is recorded
separately.

**LREQ-SMP-030**: Default sampling constants SHALL be:

```text
ENRICHMENT_SAMPLE_SIZE_PER_CATEGORY = 100
SAMPLE_STRATA = 4
SAMPLE_PER_STRATUM = 25
MIN_USABLE_SAMPLES_PER_STRATUM = 5
```

**LREQ-SMP-040**: A category with at most 100 canonical discovered assets SHALL be
fully enriched. Its `sample_is_census` flag SHALL be true.

**LREQ-SMP-050**: A category with more than 100 canonical discovered assets SHALL
be divided into four contiguous ordinal strata of approximately equal population
size. The implementation SHALL select 25 assets from each stratum.

**LREQ-SMP-060**: Selection within each stratum SHALL be deterministic using a
stable hash of `sampling_rule_version + category + asset_identity_key`. The
implementation SHALL NOT use an unseeded random generator.

**LREQ-SMP-070**: A large-category sample SHALL include assets from early, middle,
and late discovery positions. Selecting only the first page or first 100 results is
non-conforming.

**LREQ-SMP-080**: Every category SHALL persist discovered population size, sample
size, usable sample size by component, stratum boundaries, stratum sizes and
selected counts, selected identity keys or a reproducible selection digest,
sampling-rule version, census flag, and duplicate/cross-category overlap counts.

The run SHALL also persist `discovered_population_count`, `enriched_sample_count`,
`usable_demand_sample_count`,
`usable_recent_supply_sample_count`, and `usable_quality_sample_count` as distinct
values. `enriched_sample_count` SHALL never replace the discovered population
The enrichment set SHALL be the union of all category samples, and each unique
identity SHALL be enriched once only.

**LREQ-SMP-090**: If a stratum contains fewer than 25 assets, all assets in that
stratum SHALL be eligible for selection and the reduced count SHALL be reported.

### 5.2 Sampling limitation

The sample is distributed across the observed discovery ordering, not a probability
sample of buyers, sales, or all marketplace activity. The report SHALL state that
sample-based metrics estimate observed catalog signals under the selected policy.

---

## 6. Data model

SQLite SHALL be used for one local database. The exact Python persistence library is
implementation-defined, but the logical fields below are mandatory.

### 6.1 `runs`

Required fields:

```text
run_id, run_started_at_utc, scoring_cutoff_utc, completed_at_utc,
categories_json, config_snapshot_json, config_sha256,
taxonomy_captured_at_utc, taxonomy_sha256,
endpoint_contract_version, identity_mapping_rule_version, sampling_rule_version,
page_view_semantics_status, status
```

`status` SHALL be `running`, `completed`, or `failed`.

### 6.2 `raw_discovery_observations`

Required fields:

```text
observation_id, run_id, category, discovery_ordinal, asset_identity_key,
identity_candidates_json, identity_resolution_status, identity_resolution_reason,
category_value_json, category_filter_validation_status, stratum_index,
is_duplicate, duplicate_of_observation_id, retrieved_at_utc
```

Raw response bodies MAY be omitted, but a structured redacted error summary SHALL
be retained when a page or observation fails validation.

### 6.3 `sample_members`

Required fields:

```text
run_id, category, asset_identity_key, stratum_index,
stratum_start_ordinal, stratum_end_ordinal, sample_rank_within_stratum,
sample_is_census, selection_digest, overlap_category_count,
overlap_sample_percentage
```

The primary key SHALL prevent duplicate membership for a run, category, and
identity.

### 6.4 `enrichment_observations`

Required fields:

```text
run_id, asset_identity_key, product_detail_status, page_views_status,
graphql_id, product_id, rating_average, rating_count, review_count,
first_published_date_utc, publisher_json, category_json, state, product_page_views,
id_mapping_mismatch,
product_detail_error_summary, page_views_error_summary, retrieved_at_utc
```

`product_page_views` SHALL be nullable and SHALL never use zero as an error sentinel.

### 6.5 `category_scores`

Required fields:

```text
discovered_population_count, discovery_returned_count, enriched_sample_count,
usable_demand_sample_count, usable_recent_supply_sample_count,
usable_quality_sample_count,
discovery_status, discovery_filter_verified, discovery_unresolved_identity_count,
discovery_conflict_count, discovery_duplicate_count, sample_size,
sample_is_census, unique_enrichment_count, demand_usable_count,
demand_coverage, recent_supply_usable_count, recent_supply_coverage,
quality_usable_count, quality_coverage, demand_per_asset_raw,
demand_median_raw, breadth_raw, recent_share_raw, median_age_raw, quality_raw,
component_d, component_c, component_r, component_q,
market_opportunity_score, score_state, evidence_grade, rankability_status,
missing_components_json, warnings_json, reference_size,
reference_usable_counts_json, ranking_sensitivity_json, computed_at_utc
```

Raw metrics and scores except counts and status fields SHALL be nullable.

---

## 7. Metrics and sample-aware estimators

### 7.1 Common eligibility

**LREQ-MET-010**: A product-level value is usable only when its type, range, state,
identity, and timestamp conditions for the relevant metric pass. Null, malformed,
future, naive, negative, non-finite, or state-excluded values SHALL be unavailable.

**LREQ-MET-020**: All age calculations SHALL use:

```text
age_days_exact =
    (scoring_cutoff_utc - first_published_date_utc).total_seconds() / 86400
```

The floor of age may be used for display only.

### 7.2 Demand

For category `c`, let `N_h` be the discovered canonical population in stratum `h`,
`N` the total discovered canonical population, and `n_h` the number of sampled
assets in that stratum with a usable age-normalized page-view index.

For each usable stratum:

```text
stratum_view_mean_h = mean(age_normalized_page_view_index_h)
stratum_weight_h = N_h / N
```

**LREQ-MET-030**: The demand-per-asset estimate SHALL be:

```text
DemandPerAssetRaw =
    sum(stratum_weight_h * stratum_view_mean_h for usable strata)
    /
    sum(stratum_weight_h for usable strata)
```

It is null when no stratum has at least `MIN_USABLE_SAMPLES_PER_STRATUM` usable
observations.

`N_h` is the discovered canonical population in stratum `h`, `n_h` is the sampled
population in that stratum, and `u_h` is its usable demand count. A stratum is
usable for the mean only when `u_h >= MIN_USABLE_SAMPLES_PER_STRATUM`. The
denominator is the sum of population weights for usable strata, not `N` alone.

**LREQ-MET-040**: The page-view index SHALL be:

```text
age_normalized_page_view_index = product_page_views * 7 / age_days_exact
```

It is usable only for a finite non-negative page-view value, a valid UTC date no
later than cutoff, `age_days_exact >= MIN_AGE_DAYS_FOR_RATE`, and a matched,
published identity. An explicit valid page-view value of zero is usable and yields
an index of zero.

**LREQ-MET-050**: `DemandMedianRaw` SHALL be a stratum-expanded weighted median of
usable product indices. Each usable observation in stratum `h` receives weight
`N_h / n_h`. The weighted median is the first sorted value whose cumulative weight
is at least half the total weight. If cumulative weight equals exactly half at a
value boundary, use the arithmetic mean of that value and the next sorted value;
when the boundary value is the final sorted value, use that final value. It is null
when the usable weighted sample is empty.

For a weighted-median input, sort finite usable values ascending, retain ties as
separate observations, compute cumulative weights in that order, and compare with
exactly half the total weight. Missing, invalid, or unusable values contribute no
weight. The same algorithm and boundary rule SHALL be used for `MedianAgeRaw`.

**LREQ-MET-060**: Demand coverage SHALL be:

```text
demand_coverage = sum(stratum_weight_h for strata meeting the usable minimum)
```

bounded to `[0, 1]`.

### 7.3 Competition / catalog breadth

**LREQ-MET-070**: `BreadthRaw` SHALL be the verified discovered canonical
population count, not the enrichment sample size. A verified, reconciled
`totalCount` MAY be used; otherwise use distinct canonical discovered identities and
record the limitation.

Competition is unavailable when filtering is unverified, a material page failed,
or identity incompleteness makes breadth an unbounded lower bound.

### 7.4 Recent supply

For each stratum with usable published first-publication dates:

```text
stratum_recent_share_h =
    count(0 <= age_days_exact <= RECENT_WINDOW_DAYS)
    / dated_asset_count_h
```

**LREQ-MET-080**: `RecentShareRaw` SHALL be the stratum-population-weighted mean
of usable `stratum_recent_share_h` values, renormalized over usable strata.
`MedianAgeRaw` SHALL be the corresponding stratum-expanded weighted median of exact
ages. `recent_supply_coverage` SHALL be the represented population weight.

For each stratum, `N_h` is its discovered population, `n_h` is its sampled dated
population, and `u_h` is the usable dated count. A missing or unusable stratum SHALL
reduce coverage and SHALL NOT contribute zero to the recent-share numerator.

`RECENT_WINDOW_DAYS` defaults to `365`, inclusive. Recent supply measures catalog
composition, not sales flow or publication velocity.

### 7.5 Quality gap

An asset is quality-eligible only when ProductDetail and ProductPageViews succeeded,
identity mapping matched, `state = "published"`, `rating_average` is finite in
`[0, 5]`, `rating_count >= QUALITY_MIN_RATING_COUNT`, the page-view index is usable,
and page-view semantics are not contradicted.

**LREQ-MET-090**: Default quality constants SHALL be:

```text
QUALITY_MIN_RATING_COUNT = 5
QUALITY_MIN_ELIGIBLE_ASSETS = 5
```

Quality is unavailable below the minimum eligible count.

Quality SHALL also be unavailable when weighted usable coverage is insufficient under
the configured evidence policy, when page-view semantics are contradicted, or when
the visibility-weighted denominator is zero. `rating_count` is a reliability
minimum only and SHALL NOT weight the quality formula.

**LREQ-MET-100**: Quality raw value SHALL be:

```text
QualityRaw =
    sum((rating_average / 5) * age_normalized_page_view_index)
    / sum(age_normalized_page_view_index)
```

It is null when the eligible set is too small or the denominator is zero.
`quality_coverage` SHALL be the eligible weighted sample coverage. Quality gap is
an apparent opportunity signal, not a causal measure of dissatisfaction.

---

## 8. Normalization, components, and composite score

### 8.1 Leave-one-out reference

**LREQ-NRM-010**: Every category SHALL be scored as a target. For target `c_i`,
the reference contains all other categories in the same run.

**LREQ-NRM-020**: `reference_size = category_count - 1`. Field-specific usable
reference counts SHALL be stored separately.

**LREQ-NRM-030**: For target `x` and usable reference values `r_1..r_m`:

```text
L = count(r_k < x)
E = count(r_k = x)
P_ref(x) = (L + 0.5 * E) / m
```

If `m = 0` or `x` is null, the normalized value is null. Ties receive the same
midrank. These are descriptive relative positions, not inferential percentiles.

**LREQ-NRM-040**: Normalize independently:

```text
DemandPerAssetRaw, DemandMedianRaw, BreadthRaw,
RecentShareRaw, MedianAgeRaw, QualityRaw
```

No log transform is required because strictly monotone transforms do not change
midrank ordering.

### 8.2 Components

**LREQ-SCR-010**: Demand SHALL be:

```text
D0 = weighted available mean of:
       0.60 * P_ref(DemandPerAssetRaw)
       0.40 * P_ref(DemandMedianRaw)
D = clamp(0.5 + demand_coverage * (D0 - 0.5), 0, 1)
```

`D` is unavailable when no demand raw value is usable.

**LREQ-SCR-020**: Competition SHALL be:

```text
C = clamp(1 - P_ref(BreadthRaw), 0, 1)
```

It is available only with verified and sufficiently complete discovery.

**LREQ-SCR-030**: Recent supply SHALL be:

```text
Rpressure0 = weighted available mean of:
    0.70 * P_ref(RecentShareRaw)
    0.30 * (1 - P_ref(MedianAgeRaw))
R0 = 1 - Rpressure0
R = clamp(0.5 + recent_supply_coverage * (R0 - 0.5), 0, 1)
```

**LREQ-SCR-040**: Quality gap SHALL be:

```text
Q0 = 1 - P_ref(QualityRaw)
Q = clamp(0.5 + quality_coverage * (Q0 - 0.5), 0, 1)
```

**LREQ-SCR-050**: If `page_view_semantics_status = "contradicted"`, `D` and `Q`
SHALL be unavailable. `C` and `R` MAY remain available, but the category SHALL not
be rankable.

### 8.3 Composite score

Default weights are `w_D=0.35`, `w_C=0.30`, `w_R=0.20`, and `w_Q=0.15`.

**LREQ-SCR-060**: Use available-component renormalization:

```text
W_A = sum(weights of available components)
S_available = sum(weight_x * x for available x) / W_A
market_opportunity_score = clamp(0.5 + W_A * (S_available - 0.5), 0, 1)
```

The composite MAY be persisted as `partial`, but it SHALL not be a rankable
recommendation when required evidence policies fail.

---

## 9. Evidence, rankability, and sensitivity

### 9.1 Rankability states

**LREQ-EVD-010**: Use `not_rankable`, `provisional`, and `rankable` states.

**LREQ-EVD-020**: A category is `not_rankable` when any of the following applies:
discovery filtering is unverified; identity conflicts remain unresolved at a material
rate; required demand data is unavailable; recent-supply minimum evidence is not met;
quality is unavailable under the configured required-component policy; page-view
semantics are contradicted for a page-view-dependent score; no valid leave-one-out
reference exists; identity preflight fails; or an unrecoverable data-integrity error
occurs. Material discovery failure or unbounded breadth also makes competition
non-rankable.

**LREQ-EVD-030**: A score SHALL be `provisional` when computable and required
conditions pass, but the run has 8–20 categories, the reference has fewer than 21
categories, discovery is bounded by a verified total rather than fully complete,
sample coverage is acceptable but below the strong policy, or sensitivity is high.

**LREQ-EVD-040**: A category may be `rankable` only when the run contains at least
8 categories, discovery and identity checks pass, required component evidence
policies pass, sample and field coverage meet configured thresholds, no critical
contradiction exists, sensitivity is within limits, and the reference contains at
least 21 categories. A run with 8–20 categories SHALL never be labeled `rankable`;
it may be `provisional`.

```text
MIN_CATEGORIES_PER_RUN = 8
STRONG_REFERENCE_CATEGORY_COUNT = 21
```

### 9.2 Evidence grade

**LREQ-EVD-050**: Evidence grade SHALL consider sample size, census status,
component coverage, discovery integrity, reference size, page-view semantics, and
sensitivity. Sample count alone SHALL not determine it.

| Grade | Default policy |
|---|---|
| `strong` | At least 80 usable sampled assets, or a census of at least 50; required coverage at least 80%; verified discovery; no identity conflict; at least 21 reference categories; no critical contradiction; acceptable sensitivity. |
| `moderate` | At least 40 usable sampled assets, or a census of at least 20; required coverage at least 50%; at least 8 reference categories; no critical identity failure. |
| `weak` | Computable but below moderate policy in sample, coverage, reference, discovery, or sensitivity. |
| `insufficient` | Required evidence is invalid, unavailable, or contradictory; category is not rankable. |

These are operational evidence grades, not confidence intervals or probabilities.

### 9.3 Ranking sensitivity

**LREQ-SEN-010**: Recompute rankings under these policies:

```text
balanced:          D=0.35, C=0.30, R=0.20, Q=0.15
demand_heavy:      D=0.50, C=0.25, R=0.15, Q=0.10
competition_heavy: D=0.30, C=0.45, R=0.15, Q=0.10
```

**LREQ-SEN-020**: Report top-three membership stability, top-five membership
stability, each category's rank under each policy, maximum rank displacement, and
maximum score displacement. The persisted field names SHALL include
`top_3_stability`, `top_5_stability`, and `maximum_score_delta`.

**LREQ-SEN-030**: Warn when `top_3_stability < 2 / 3`, or when a category's rank
changes by more than `max(3 positions, 25% of reference-set size)`. The warning
threshold SHALL be interpreted using the configured reference-set size and SHALL
not silently alter the primary balanced score.

**LREQ-SEN-040**: Sensitivity diagnostics SHALL qualify the balanced score and SHALL
not silently replace it.

---

## 10. Reporting and CLI

**LREQ-RPT-010**: Provide a local read-only HTML report or dashboard launched by
one command. The required interface SHALL retain:

```text
niche-scout run --categories config/categories.json --config config/default.toml
niche-scout dashboard
```

**LREQ-RPT-020**: The primary table SHALL show category, rank, composite score,
`D/C/R/Q`, discovered population, sample size, census flag, usable count and
coverage per component, evidence grade, rankability, discovery status, page-view
semantic status, `top_3_stability`, sensitivity warning, and the percentage of the
category sample shared with other categories.

**LREQ-RPT-030**: Category details SHALL show formulas or concise explanations,
metric inputs, sample strata, warnings, timestamps, and observed-versus-inferred
sample-based values.

**LREQ-RPT-040**: Non-rankable categories SHALL remain visible.

**LREQ-RPT-050**: The report SHALL state that the score is a deterministic,
within-run heuristic based on marketplace signals and, for larger categories, a
stratified sample; it has not been calibrated against sales, revenue, downloads, or
conversion. It SHALL distinguish pagination completion from immutable snapshot
completeness, the page-view index from a weekly traffic rate, descriptive midranks
from inferential percentiles, and evidence grade from statistical confidence.

The lean dashboard SHALL omit historical run comparison, scheduled-run controls,
complex trend displays, run-resume controls, and advanced provenance navigation. A
sortable table and category detail panel are sufficient.

**LREQ-CLI-010**: The primary command SHALL be equivalent to:

```text
niche-scout run --categories config/categories.json --config config/default.toml
```

It SHALL run one pipeline and exit non-zero on unrecoverable errors.

**LREQ-CLI-020**: A report command SHALL read the database and SHALL not initiate
discovery or enrichment.

**LREQ-CLI-030**: CLI options SHALL override TOML configuration, which SHALL
override documented in-code defaults.

**LREQ-CLI-040**: The pipeline SHALL reject a run with fewer than
`MIN_CATEGORIES_PER_RUN` requested categories before producing a ranking. It SHALL
retain a completed run's collection timestamp and explicit limitations in the report.

---

## 11. Non-functional requirements

**LREQ-NFR-010**: Discovery persistence SHALL be streamed and SHALL not require all
responses in memory.

**LREQ-NFR-020**: Before bulk enrichment, log discovered canonical assets, sampled
assets, unique enrichment identities, and projected minimum enrichment time.

**LREQ-NFR-030**: A failed page or sampled asset SHALL not abort unrelated categories
or assets; the failure SHALL remain visible in status and evidence fields.

**LREQ-NFR-040**: Public metric and scoring functions SHALL have type hints and
docstrings describing null and edge-case behavior.

**LREQ-NFR-050**: The system SHALL run on Python 3.11+ on Windows, macOS, and Linux
using `pathlib` for paths.

**LREQ-NFR-060**: Formatting, linting, secret handling, and analytical tests SHALL
be part of the normal workflow. Strict project-wide typing, 95% whole-package
coverage, and CI-on-every-commit are deferred quality improvements, not lean MVP
blockers.

---

## 12. Project structure and conventions

The lean implementation SHOULD use:

```text
niche-scout/
├── README.md
├── pyproject.toml
├── config/
│   ├── categories.json
│   ├── category_taxonomy.json
│   └── default.toml
├── src/niche_scout/
│   ├── cli.py
│   ├── config.py
│   ├── models.py
│   ├── collector.py
│   ├── validation.py
│   ├── sampling.py
│   ├── scoring.py
│   ├── database.py
│   ├── pipeline.py
│   └── report.py
└── tests/
    ├── fixtures/
    ├── test_collector.py
    ├── test_identity.py
    ├── test_sampling.py
    ├── test_scoring.py
    ├── test_validation.py
    └── test_end_to_end.py
```

The exact module decomposition MAY differ, but the purity boundary in §3.3 SHALL
remain. Use `snake_case` files/functions, `PascalCase` classes, `UPPER_SNAKE_CASE`
constants, UTC suffixes for timestamps, and `LREQ-*` references in analytical tests.

---

## 13. Testing requirements

**LREQ-TST-010**: Every formula SHALL have tests for normal values, explicit valid
zero where applicable, missing values, invalid values, ties, and minimum boundaries.

**LREQ-TST-020**: Sampling tests SHALL verify census behavior at 0, 1, 99, and 100
assets; four-stratum selection above 100; deterministic repeated selection; early,
middle, and late strata; reduced final strata; changed selection digest for a changed
rule version; and no duplicate membership.

**LREQ-TST-030**: Identity tests SHALL cover valid canonical candidates, malformed
fallback, unresolved identity, conflicting candidates, URI parsing, GraphQL mismatch,
and duplicate cross-category identities.

**LREQ-TST-040**: GraphQL tests SHALL cover success, reversed response ordering,
missing/ambiguous operation association, operation errors, null data, wrong types,
negative/non-finite page views, partial success, state filtering, and permanent
authentication/CSRF failures.

**LREQ-TST-050**: Date and metric tests SHALL cover UTC normalization, naive dates,
exact fractional age, rate-threshold boundaries, future dates, zero page views,
recent-window boundaries, weighted strata, missing strata, weighted medians, and
zero-denominator quality.

**LREQ-TST-060**: Scoring tests SHALL cover midrank ties, all-equal references,
missing-component renormalization, coverage shrinkage, contradicted page views,
8-category provisional runs, 21-category strong-reference runs, and non-rankability.

**LREQ-TST-070**: Sensitivity tests SHALL verify all three policies, rank displacement,
top-three/top-five stability, warning thresholds, and preservation of the balanced
primary score.

**LREQ-TST-080**: An end-to-end fixture SHALL exercise category validation,
pagination, duplicate/overlapping identities, four-stratum sampling, one enrichment
per unique sampled identity, partial GraphQL failure, metrics, scoring, evidence,
sensitivity, SQLite persistence, and report rendering.

**LREQ-TST-090**: Golden vectors SHALL assert exact results within `1e-9` for
sample-aware metrics, normalization, components, composite score, coverage, evidence,
and sensitivity outputs.

Formatting, linting, secret handling, and analytical tests remain mandatory. The lean
variant may defer package-wide strict typing, architecture import-linter enforcement,
and exhaustive tests of non-scoring infrastructure.

---

## 14. Configuration reference

| Constant | Default | Configurable? | Purpose |
|---|---:|---|---|
| `MAX_DISCOVERY_RESULTS_PER_CATEGORY` | 2000 | Yes | Discovery bound. |
| `PAGE_SIZE` | 96 | No, protocol limit | Coveo page size. |
| `MIN_CATEGORIES_PER_RUN` | 8 | No | Minimum comparison set. |
| `STRONG_REFERENCE_CATEGORY_COUNT` | 21 | No | Strong reference boundary. |
| `MAX_TAXONOMY_AGE_DAYS` | 30 | Yes | Taxonomy freshness. |
| `ENRICHMENT_SAMPLE_SIZE_PER_CATEGORY` | 100 | Yes, bounded | Large-category sample target. |
| `SAMPLE_STRATA` | 4 | No for v1 | Ordinal strata count. |
| `SAMPLE_PER_STRATUM` | 25 | No for v1 | Per-stratum sample target. |
| `MIN_USABLE_SAMPLES_PER_STRATUM` | 5 | Yes | Stratum evidence minimum. |
| `MIN_AGE_DAYS_FOR_RATE` | 30 | Yes | Index age threshold. |
| `RECENT_WINDOW_DAYS` | 365 | Yes | Recent window. |
| `QUALITY_MIN_RATING_COUNT` | 5 | Yes | Rating evidence minimum. |
| `QUALITY_MIN_ELIGIBLE_ASSETS` | 5 | Yes | Quality sample minimum. |
| `IDENTITY_PREFLIGHT_MIN_CATEGORIES` | 5 | Yes | Preflight breadth. |
| `IDENTITY_PREFLIGHT_ASSETS_PER_CATEGORY` | 2 | Yes | Preflight sample. |
| `IDENTITY_PREFLIGHT_MAX_CONFLICT_RATE` | 0 | No for v1 | Permitted conflict rate. |
| `IDENTITY_PREFLIGHT_MIN_SUCCESS_RATE` | 0.90 | Yes | Preflight success threshold. |
| `w_D,w_C,w_R,w_Q` | 0.35,0.30,0.20,0.15 | Yes, sum 1 | Balanced weights. |
| `DEMAND_SUBWEIGHTS` | 0.60,0.40 | No for v1 | Demand subcomponents. |
| `RECENT_SUBWEIGHTS` | 0.70,0.30 | No for v1 | Recent subcomponents. |
| `NICHESCOUT_COVEO_BEARER_TOKEN` | operator-supplied | Environment | Coveo credential. |
| `NICHESCOUT_UNITY_CSRF_TOKEN` | operator-supplied | Environment | GraphQL credential. |

The three sensitivity policies in §9.3 are fixed diagnostics in v1 and SHALL not
be disabled in the report.

---

## 15. Deferred scope and rationale

The following items are intentionally removed from the lean implementation. Each
entry states the primary affected dimension so that operational simplification is
not confused with harmlessness to analytical validity.

| Deferred item | Reason for deferral | Primary impact dimension | Effect or safeguard |
|---|---|---|---|
| Full formal identity-validation study | Replaced by automated fixtures and per-run preflight | Operational reliability | Identity conflict detection and preflight blocking remain mandatory. |
| Enrichment of every discovered asset | Replaced by deterministic four-stratum sampling | Analytical validity | Population denominators, coverage, and sample limitations remain explicit. |
| Historical trend analysis | Not needed for a within-run decision | User experience | No historical claims are supported. |
| Cross-run ranking compatibility checks | Scores are explicitly within-run | Analytical validity | Cross-run comparability is not claimed. |
| Checkpoint/resume support | Reduces state-management complexity | Operational reliability | Interrupted runs restart from the beginning. |
| Scheduled execution | Manual ideation is the target workflow | Operational reliability | No recurring measurement is implied. |
| Historical dashboard views | Keeps the dashboard decision-focused | User experience | Only the selected run is shown. |
| Full raw API-response archival | Reduces storage and secret-retention risk | Operational reliability | Required normalized fields, request metadata, and redacted error summaries remain. |
| Extensive provenance UI | Reduces dashboard complexity | User experience | Audit-critical provenance remains in SQLite and category details. |
| Strict project-wide static typing | Engineering overhead exceeds lean scope | Maintainability | Analytical public functions remain typed and tested. |
| 95% coverage requirement for all analytical packages | Defer package-wide threshold enforcement | Maintainability | Required analytical vectors and end-to-end tests remain mandatory. |
| Architecture import-linter enforcement | Tooling overhead | Maintainability | The collection/persistence-to-scoring purity boundary remains normative. |
| Support for more than one live collection strategy | One Coveo plus GraphQL strategy is sufficient | Future scalability | Alternative strategies require a future SRS revision. |
| Favorite-count enrichment | Unvalidated and unused signal | Analytical validity | It is not part of the score or required GraphQL fields. |
| Additional unused GraphQL fields | Avoids schema and persistence scope | Maintainability | Only fields required for identity, metrics, and audit are requested. |
| Population-level sales or revenue calibration | No reliable outcome dataset is supplied | Analytical validity | Output remains a heuristic and explicitly not a sales or revenue estimate. |

---

## 16. Known limitations and warnings

The implementation and report SHALL document that:

1. larger categories use a deterministic sample rather than a census;
2. the sample is stratified by discovery order, not a probability sample from all possible buyers or sales;
3. discovery order may reflect marketplace ranking or retrieval behavior;
4. rankings are relative to the selected categories in the same run;
5. the page-view field is an age-normalized index with unvalidated semantics, not a validated weekly traffic measurement;
6. ratings are marketplace observations, not objective product-quality measurements;
7. recent share measures catalog composition, not sales or publication velocity;
8. categories with incomplete discovery are lower-confidence or non-rankable;
9. overlapping assets make category observations dependent;
10. missing data may make a category non-rankable or shrink it toward neutral;
11. a strong evidence grade is not a probability of correctness;
12. ranking stability depends on selected categories and weights;
13. sensitivity warnings indicate instability, not an objectively correct weighting;
14. discovery completion does not guarantee an immutable marketplace snapshot;
15. the result is not calibrated against downloads, sales, revenue, or conversion.

---

## 17. Acceptance criteria

The implementation is acceptable only when:

1. at least eight categories are required for a normal run;
2. taxonomy and filter validation occur before scoring;
3. identity conflicts and unresolved identities are retained and visible;
4. identity preflight blocks bulk enrichment when thresholds fail;
5. large-category sampling is deterministic, four-stratum, and not first-page-only;
6. small categories are enriched as a census;
7. shared sampled assets are enriched once and joined to all relevant categories;
8. competition uses discovered breadth, not sample size;
9. sample-aware coverage is used for demand, recent supply, and quality;
10. missing values are not converted to zero;
11. quality has rating-count and eligible-sample minimums;
12. exact UTC age and one scoring cutoff are used;
13. contradicted page-view semantics disable D/Q and rankability;
14. reference size and field-specific usable counts are stored;
15. 8-category results are provisional and 21-category results can qualify as strong;
16. three weight policies are evaluated and sensitivity is reported;
17. non-rankable categories remain visible;
18. the report labels the score as a within-run heuristic, not a sales estimate;
19. golden vectors and the end-to-end fixture pass;
20. no stale requirement assumes every large-category asset is enriched;
21. all retained formulas have their inputs defined in the data model;
22. every sample-derived metric distinguishes population size, sample size, usable sample size, and coverage;
23. sample selection includes late-result strata and shared assets are enriched once;
24. identity conflicts prevent rankable output and contradicted page-view semantics disable affected components;
25. the traceability matrix maps every lean requirement area to a module and test;
26. the SRS contains no unresolved references to removed historical, scheduling, resume, or full-enrichment requirements;
27. no unsupported claim of statistical precision, sales prediction, revenue prediction, or representative marketplace estimation remains.

---

## Appendix A — Formula summary

```text
age_days_exact = (scoring_cutoff_utc - first_published_date_utc).total_seconds() / 86400
age_normalized_page_view_index = product_page_views * 7 / age_days_exact
stratum_weight_h = N_h / N
DemandPerAssetRaw = sum(stratum_weight_h * stratum_view_mean_h for usable strata)
                    / sum(stratum_weight_h for usable strata)
P_ref(x) = (L + 0.5 * E) / m
D0 = weighted available mean of 0.60*P_ref(DemandPerAssetRaw),
     0.40*P_ref(DemandMedianRaw)
D = clamp(0.5 + demand_coverage*(D0 - 0.5), 0, 1)
C = clamp(1 - P_ref(BreadthRaw), 0, 1)
Rpressure0 = weighted available mean of 0.70*P_ref(RecentShareRaw),
             0.30*(1 - P_ref(MedianAgeRaw))
R0 = 1 - Rpressure0
R = clamp(0.5 + recent_supply_coverage*(R0 - 0.5), 0, 1)
QualityRaw = sum((rating_average / 5) * age_normalized_page_view_index)
             / sum(age_normalized_page_view_index)
Q0 = 1 - P_ref(QualityRaw)
Q = clamp(0.5 + quality_coverage*(Q0 - 0.5), 0, 1)
W_A = sum(weight_x for available components)
S_available = sum(weight_x*x for available x) / W_A
market_opportunity_score = clamp(0.5 + W_A*(S_available - 0.5), 0, 1)
```

---

## Appendix B — Traceability matrix

| Requirement area | Primary module | Required tests |
|---|---|---|
| `LREQ-EXT-*` | `collector.py`, `validation.py` | `test_collector.py` |
| `LREQ-GQL-*` | `collector.py`, `validation.py` | `test_collector.py`, `test_identity.py` |
| `LREQ-ID-*` | `validation.py`, `pipeline.py` | `test_identity.py`, `test_end_to_end.py` |
| `LREQ-SMP-*` | `sampling.py` | `test_sampling.py` |
| `LREQ-MET-*` | `scoring.py` | `test_scoring.py`, `test_validation.py` |
| `LREQ-NRM-*`, `LREQ-SCR-*` | `scoring.py` | `test_scoring.py` |
| `LREQ-EVD-*` | `scoring.py`, `report.py` | `test_scoring.py` |
| `LREQ-SEN-*` | `scoring.py` | `test_scoring.py` |
| `LREQ-RPT-*` | `report.py`, `cli.py` | `test_end_to_end.py` |
| `LREQ-CLI-*` | `cli.py` | `test_end_to_end.py` |
| `LREQ-ARCH-*` | `pipeline.py`, `scoring.py` | `test_end_to_end.py`, analytical tests |
| `LREQ-SEC-*` | `config.py`, `collector.py`, `database.py` | `test_collector.py`, `test_end_to_end.py` |
| `LREQ-NFR-*` | cross-cutting | project checks and end-to-end tests |
| `LREQ-TST-*` | `tests/` | all test modules |

---

## Appendix C — Required report warning vocabulary

The implementation SHOULD use these stable warning codes:

```text
DISCOVERY_TRUNCATED
DISCOVERY_PAGE_FAILED
DISCOVERY_FILTER_UNVERIFIED
CATEGORY_MISMATCH
IDENTITY_UNRESOLVED
IDENTITY_CONFLICT
IDENTITY_PREFLIGHT_FAILED
GRAPHQL_PRODUCT_ERROR
GRAPHQL_PAGE_VIEWS_ERROR
GRAPHQL_ID_MAPPING_MISMATCH
STATE_EXCLUDED
INSUFFICIENT_DEMAND_SAMPLE
INSUFFICIENT_RECENT_SAMPLE
INSUFFICIENT_QUALITY_SAMPLE
PAGE_VIEW_SEMANTICS_CONTRADICTED
REFERENCE_SET_SMALL
RANKING_SENSITIVITY_HIGH
SAMPLE_BASED_SIGNAL
```

Warnings SHALL identify the affected category or asset count where applicable and
shall not expose credentials or unredacted response secrets.