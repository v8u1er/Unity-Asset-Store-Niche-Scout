# Software Requirements Specification

## Unity Asset Store Niche Scout — Lean Decision-Grade Variant

| Field | Value |
|---|---|
| Document type | Software Requirements Specification (SRS) |
| Parent specification | `SRS-revision2.md`, effective revision 2.3.0 |
| Variant | Lean, sample-based, decision-grade MVP |
| Version | Lean 1.0.4 |
| Status | Decision-grade lean variant (v2, Lean 1.0.4; supersedes `SRS-lean.md`) |
| Target release | v0.1.0-lean |

## Revision history

| Version | Change |
|---|---|
| Lean 1.0.0 | New standalone lean variant derived from `SRS-revision2.md`. Reduces enrichment, persistence, dashboard, and operational scope while retaining identity integrity, response validation, exact time handling, missing-data safeguards, deterministic scoring, evidence reporting, and ranking-sensitivity diagnostics. |
| Lean 1.0.1 | Clarifies deterministic-sample interpretation, makes quality stratum-expanded, removes sensitivity/rankability circularity, completes result persistence keys, freezes Lean v1 scoring weights, and specifies zero-population and GraphQL-correlation behavior. |
| Lean 1.0.2 | Replaces the four contiguous ordinal strata of `LREQ-SMP-050` with a systematic (interleaved) partition over the same stable discovery ordinal (deterministic per-category offset; `stratum_index(i) = (i - 1 + offset) mod SAMPLE_STRATA`), and changes the persisted stratum geometry from an ordinal interval to `(offset, stride)`. All other Lean 1.0.1 behavior is unchanged. |
| Lean 1.0.3 | Lowers the default `MIN_USABLE_SAMPLES_PER_STRATUM` from 5 to 1 (§5.1, §14), re-baselining per-stratum usability, the three stratum eligibility coverages, the usable component sample counts, evidence grades, and rankability for runs scored under the default policy. The constant remains Configurable = Yes and no formula, weight, partition rule, or other constant changes. |
| Lean 1.0.4 | Corrects the page-view semantics (§1.4, §7.2 `LREQ-MET-040`, §6.3, §10 `LREQ-RPT-050`, §16, Appendix A): the field is a validated trailing-7-day (weekly) view count (`age_normalized_page_view_index = product_page_views`), replacing the refuted age-normalized cumulative-rate assumption; adds the `validated_windowed_weekly` run status; `MIN_AGE_DAYS_FOR_RATE` becomes an eligibility floor only. No other formula, weight, partition rule, or constant changes. |

## Document status and relationship to the parent SRS

**Lean v2 (this file) supersedes `SRS-lean.md` (Lean 1.0.1).** The prior file is
retired to `Documents/retired-documents/` and retained for history only; where this
file and the retired `SRS-lean.md` differ, this file is normative. The Lean 1.0.2
behavioral change is the systematic (interleaved) sampling-stratum geometry and its
persistence representation (`LREQ-SMP-050`, `LREQ-SMP-080`, §1.4, §5.1, §6.3, §14);
all other Lean 1.0.1 requirement text is carried forward unchanged. Lean 1.0.3
supersedes Lean 1.0.2 and changes exactly one default:
`MIN_USABLE_SAMPLES_PER_STRATUM` is lowered from 5 to 1 (§5.1, §14), which
re-baselines per-stratum usability, the three stratum eligibility coverages, the
usable component sample counts, evidence grades, and rankability for runs scored
under the default policy. No formula, weight, partition rule, or other constant
changes. Lean 1.0.4 supersedes Lean 1.0.3 and corrects the page-view field
semantics (§1.4, §7.2 `LREQ-MET-040`, §6.3, §10 `LREQ-RPT-050`, §16, Appendix A):
the field is a validated trailing-7-day (weekly) view count and
`age_normalized_page_view_index = product_page_views`; the `validated_windowed_weekly`
run status is added and `MIN_AGE_DAYS_FOR_RATE` becomes an eligibility floor only.
No other formula, weight, partition rule, or constant changes.
Tooling that reads the SRS by path (`src/niche_scout/tools/`,
`AGENTS.md`) must be re-pointed to this file when the prior file is retired.

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
- at least 8 categories per run;
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
| Stratum | One systematic (interleaved) set of a category's canonical discovery ordinals at a fixed stride and a per-category offset (see `LREQ-SMP-050`). |
| Usable observation | An observation satisfying the component-specific type, range, state, identity, date, and operation-status rules. |
| Sample fraction | The proportion of a category's canonical discovered population included in its enrichment sample. It is `1.0` for a census category and is not a measure of statistical representativeness. |
| Stratum eligibility coverage | The proportion of discovered population weight belonging to strata that meet a component's minimum usable-observation rule. It is a data-support measure, not a probability-sampling coverage estimate or confidence measure. |
| Age-normalized page-view index | The **weekly (trailing-7-day) page-view count**, `product_page_views`, using an undocumented page-view field. It is a weekly view count, not a lifetime-average count and not a daily-average rate; it is stable within a run and refreshed at most daily. |
| Midrank relative position | `(L + 0.5E) / m`, where `L` is the number of usable reference values below the target, `E` is the number equal to it, and `m` is the number of usable reference values. It is descriptive, not inferential. |
| Base-rankable candidate | A category that satisfies every rankability requirement except the final sensitivity thresholds. Sensitivity is evaluated over the fixed set of these candidates before final rankability is assigned. |
| Rankable | Evidence state indicating that a category may be used in the primary ranking under the policies in §9. |
| Within-run | Relative to the category set and collection policy used in one run. Scores are not expected to be comparable across arbitrary runs. |

### 1.5 Source references

- **[PARENT]** — `SRS-revision2.md`, the full-MVP SRS and source for unchanged
  endpoint details.
- **[API]** — `Unity_Data_Extraction_API.md`, as cited by the parent SRS.
- **[MATH]** — `V3_MATHEMATICAL_REFERENCE.md`, as cited by the parent SRS.
- **[AUDIT]** — `V3_MATHEMATICAL_AUDIT_REPORT.md`, as cited by the parent SRS.

The lean SRS is the normative source for sampling, sample-derived metrics,
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
4. Discover each category with the same endpoint, filter, sort order, page size,
   and pagination rules.
5. Persist each raw discovery observation, including unresolved and conflicting
   identity records.
6. Deduplicate canonical identities within each category for metric purposes while
   retaining every raw API observation for audit.
7. Build ordinal strata and select a deterministic enrichment sample per category.
8. Select the deterministic identity-preflight set from the sampled identities and
   run the preflight described in §4.4. Cache successful preflight responses as
   enrichment observations.
9. Enrich the union of sampled canonical identities once each, excluding identities
   already completed by the preflight.
10. Capture `scoring_cutoff_utc` immediately before metric computation.
11. Compute sample-aware raw metrics, sample fractions, and stratum eligibility coverage values.
12. Construct a leave-one-out reference for every category.
13. Compute primary scores and base-rankable candidates, then compute sensitivity over that
    fixed candidate set and assign final evidence states and rankability.
14. Persist one result row per category and mark the run completed.
15. Render the report without initiating new network requests.

### 3.3 Purity boundary

**LREQ-ARCH-010**: `metrics` and `scoring` SHALL accept plain typed input structures
and return typed result structures. They SHALL not import or call `collector`,
`database`, `report`, or `cli` code, and SHALL perform no network or file I/O.

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
If the live response provides no explicit operation name or correlation key, the
implementation MAY use response position only after the identity preflight validates
the fixed two-operation ordering and expected operation-specific response shapes across
the selected preflight identities. The persisted correlation mode SHALL be either
`explicit_key` or `validated_position`. If neither mode is validated, both operations
SHALL be marked malformed and their fields SHALL remain unavailable.

For a scalar `ProductPageViews` response, request-scoped identity validation through
the associated `ProductPageViews(packageId: ...)` operation is sufficient; the scalar
response is not required to repeat the package identifier.

**LREQ-GQL-040**: Each operation SHALL have an independent status. HTTP failures,
top-level GraphQL `errors`, HTTP 200 responses with an operation-level `errors`
member, null required data, wrong data shape, wrong scalar type, boolean/negative/
non-finite page views, invalid state values, or missing identity SHALL be recorded
as an operation error. A top-level error SHALL not be treated as a successful
operation merely because another operation in the same response succeeded.

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

**LREQ-ID-010**: After deterministic sampling and before bulk enrichment, select at
least two sampled canonical assets from each of at least five categories when five
categories with two sampled assets are available. If fewer than five eligible
categories are available, use every category with at least two sampled assets and
record the reduced preflight coverage and asset shortfall. The preflight selection
SHALL use the same stable sampling order and SHALL be persisted. A category with
fewer than two sampled assets SHALL not be represented as satisfying the two-asset
per-category minimum.

**LREQ-ID-020**: The preflight SHALL perform the normal GraphQL request and verify:
the request identifier is accepted by both operations; returned product identifiers
are compatible with the requested identity; the page-view operation is associated
with the requested package identifier; the operation-correlation mode is valid; and
no unexplained response-shape or operation-association error occurred.

The preflight is an operational endpoint-and-mapping smoke test. It is not a
statistically representative validation of all marketplace identity forms.

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
and a redacted diagnostic summary. Successful preflight responses SHALL be reused
as the corresponding enrichment observations and SHALL count toward the one-
enrichment-per-unique-identity limit.

Preflight rates SHALL use unique sampled identities as the denominator, so category
overlap SHALL not inflate the counts:

```text
preflight_success_rate =
    unique identities for which both operations and identity checks succeed
    /
    unique preflight identities attempted

preflight_conflict_rate =
    unique identities with an identity mismatch or incompatible returned identity
    /
    unique preflight identities attempted
```

When `unique preflight identities attempted = 0`, both rates SHALL be null, the
preflight SHALL be `insufficient`, and bulk enrichment SHALL not start. This is a
preflight evidence shortfall, not a zero-success result.

The persisted `identity_preflight_summary_json` SHALL include attempted, successful,
conflicting, and other failed unique-identity counts, together with the selected
`graphql_operation_correlation_mode`.

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
MIN_USABLE_SAMPLES_PER_STRATUM = 1
```

For lean v1, these sampling constants are fixed and SHALL satisfy:

```text
ENRICHMENT_SAMPLE_SIZE_PER_CATEGORY = SAMPLE_STRATA * SAMPLE_PER_STRATUM
```

The stratum usability minimum is an inclusive floor: a stratum with `u_h >= MIN_USABLE_SAMPLES_PER_STRATUM` usable observations is usable, while a stratum with zero usable observations remains unusable and its population weight is excluded from the stratum eligibility coverages (§7.2, §7.4, §7.5). At the default of 1 this means a stratum is unusable exactly when it has no usable observation.

Changing the sample size, stratum count, per-stratum allocation, or the stratum
partition rule requires a new sampling-rule version and SRS revision; an
implementation SHALL not expose one of these values as independently configurable.

**LREQ-SMP-040**: A category with at most 100 canonical discovered assets SHALL be
fully enriched. Its `sample_is_census` flag SHALL be true.

**LREQ-SMP-050**: A category with more than 100 canonical discovered assets SHALL
be divided into `SAMPLE_STRATA` systematic (interleaved) ordinal strata of
approximately equal population size. The implementation SHALL select 25 assets from
each stratum.

For a large category with canonical population size `N`, let `offset` be the
category's deterministic partition offset (`0 <= offset < SAMPLE_STRATA`), computed
from the same `sampling_rule_version` string used for selection (`LREQ-SMP-060`)
as:

```text
offset = int.from_bytes(
    sha256(utf8(sampling_rule_version + NUL + category)).digest()[:8], "big"
) mod SAMPLE_STRATA
```

The category's stratum `stride` SHALL be `SAMPLE_STRATA`. For 1-based population
ordinal `i`, `stratum_index(i) = (i - 1 + offset) mod SAMPLE_STRATA`. Stratum `h`
(zero-based) SHALL contain the ordinals `i` in `1..N` with
`(i - 1 + offset) mod SAMPLE_STRATA == h`; the strata are a disjoint cover of
`1..N`, their sizes differ by at most one, and every stratum spans the whole ordinal
axis. The `offset` SHALL be deterministic and SHALL be persisted as part of the
stratum geometry. A census category SHALL use one stratum encoded as
`stratum_offset = 0`, `stratum_stride = 1`, containing ordinals `1..N`.

**LREQ-SMP-060**: Selection within each stratum SHALL compute a SHA-256 digest of
the UTF-8 encoding of the three values joined by a NUL delimiter:
`sampling_rule_version + NUL + category + NUL + asset_identity_key`. Assets SHALL
be sorted by `(digest, asset_identity_key)` and the first `SAMPLE_PER_STRATUM`
assets SHALL be selected. The implementation SHALL NOT use an unseeded random
generator or platform-dependent hash function.

**LREQ-SMP-070**: A large-category sample SHALL include assets from early, middle,
and late discovery positions. Selecting only the first page or first 100 results is
non-conforming. A systematic (interleaved) partition satisfies this requirement
structurally, because every stratum spans the whole ordinal axis; this clause adds
no relaxation of the prohibition.

**LREQ-SMP-080**: Every category SHALL persist discovered population size, sample
enrichment sample size, usable sample size by component, stratum geometry (offset and stride), stratum sizes and
selected counts, selected identity keys or a reproducible selection digest,
sampling-rule version, census flag, and duplicate/cross-category overlap counts.
For every stratum, the persisted summary SHALL include `N_h` (discovered
population), `n_h` (sampled population), `u_demand_h`, `u_recent_h`, and
`u_quality_h`, together with the eligibility rule used for each usable count.
For a census category, all discovered canonical assets SHALL be selected and
`sample_is_census` SHALL be true; its stratum summaries SHALL retain the same
`N_h`, `n_h`, and usable-count fields used by the sampled estimator.

The following SHALL be persisted as distinct values:
`discovered_population_count`, `enriched_sample_count`,
`usable_demand_sample_count`,
`usable_recent_supply_sample_count`, and `usable_quality_sample_count` as distinct
values. `enriched_sample_count` SHALL never replace the discovered population.
The enrichment set SHALL be the union of all category samples, and each unique
identity SHALL be enriched once only.

Each category SHALL also persist:

```text
sampling_basis = "census" | "deterministic_stratified_sample"
sample_fraction = enriched_sample_count / discovered_population_count
```

`sample_fraction` SHALL be `1.0` for a non-empty census category and `null` when the
discovered population is zero. For a large category it is normally below `1.0`.
Neither `sample_fraction` nor stratum eligibility coverage SHALL be described as a
measure of statistical representativeness.

The selected identity keys SHALL be joined back to every category sample that
contains them. Preflight-selected identities are members of the ordinary sample;
they are not an additional enrichment population.

**LREQ-SMP-090**: If a stratum contains fewer than 25 assets, all assets in that
stratum SHALL be eligible for selection and the reduced count SHALL be reported.

### 5.2 Sampling limitation

The sample is distributed across the observed discovery ordering, not a probability
sample of buyers, sales, or all marketplace activity. The report SHALL state that
sample-based metrics are stratum-expanded descriptive catalog signals under the
selected policy; they are not statistically representative estimates of the discovered
population or marketplace activity.

---

## 6. Data model

SQLite SHALL be used for one local database. The exact Python persistence library is
implementation-defined, but the logical fields below are mandatory.

### 6.1 `runs`

Required fields:

```text
run_id, run_started_at_utc, scoring_cutoff_utc, completed_at_utc,
categories_json, config_snapshot_json, config_sha256,
taxonomy_version, taxonomy_captured_at_utc, taxonomy_sha256,
endpoint_contract_version, identity_mapping_rule_version, sampling_rule_version,
page_view_semantics_status, graphql_operation_correlation_mode,
identity_preflight_status,
identity_preflight_summary_json, status
```

`status` SHALL be `running`, `completed`, or `failed`.

### 6.2 `raw_discovery_observations`

Required fields:

```text
observation_id, run_id, category, discovery_ordinal, asset_identity_key,
identity_candidates_json, identity_resolution_status, identity_resolution_reason,
category_value_json, category_filter_validation_status, stratum_index,
is_duplicate, duplicate_of_observation_id, request_metadata_json,
error_summary_json, retrieved_at_utc
```

Raw response bodies MAY be omitted, but a structured redacted error summary SHALL
be retained when a page or observation fails validation.

### 6.3 `sample_members`

Required fields:

```text
run_id, category, asset_identity_key, stratum_index,
stratum_offset, stratum_stride, sample_rank_within_stratum,
sample_is_census, selection_digest, overlap_category_count,
overlap_sample_percentage, preflight_selected
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
product_detail_error_summary, page_views_error_summary, request_metadata_json,
retrieved_at_utc
```

`product_page_views` SHALL be nullable and SHALL never use zero as an error sentinel.

### 6.5 `category_scores`
Required fields:

```text
run_id, category,
discovery_status, discovery_filter_verified, discovery_unresolved_identity_count,
discovery_conflict_count, discovery_duplicate_count,
discovered_population_count, enriched_sample_count, sample_is_census,
sampling_basis, sample_fraction, unique_enrichment_count,
overlap_category_count, overlap_sample_percentage,
usable_demand_sample_count, usable_recent_supply_sample_count,
usable_quality_sample_count,
breadth_source, breadth_completeness_status, discovery_bounded_by_verified_total,
demand_stratum_eligibility_coverage, recent_supply_stratum_eligibility_coverage,
quality_stratum_eligibility_coverage,
demand_per_asset_raw,
demand_median_raw, breadth_raw, recent_share_raw, median_age_raw, quality_raw,
stratum_statistics_json,
component_d, component_c, component_r, component_q,
market_opportunity_score, score_state, evidence_grade, rankability_status,
missing_components_json, warnings_json, reference_size,
reference_usable_counts_json, top_3_stability, top_5_stability,
maximum_score_delta, maximum_rank_displacement, sensitivity_warning,
ranking_sensitivity_json, computed_at_utc
```

The logical primary key SHALL be `(run_id, category)`. `enriched_sample_count` is
the distinct sampled canonical-identity count selected for the category, regardless
of whether its later GraphQL operation succeeds; it is not a replacement for
`discovered_population_count`. `unique_enrichment_count` is the
distinct sampled-identity count enriched once across the entire run and MAY be
repeated on each category row for reporting convenience.

The three `usable_*_sample_count` fields SHALL count distinct sampled observations
that contribute to strata satisfying the applicable minimum usable-observation rule.
The stratum summary remains authoritative for the per-stratum counts. No duplicate
aliases such as `sample_size`, `demand_usable_count`, `recent_supply_usable_count`,
or `quality_usable_count` SHALL be required in the lean schema.

`overlap_category_count` and `overlap_sample_percentage` SHALL also be persisted in
`category_scores` or its joined sample summary. `overlap_category_count` is the number
of other categories sharing at least one sampled identity with this category, and:

```text
overlap_sample_percentage =
    100 * count(sampled identities in this category appearing in another category)
    / enriched_sample_count
```

It is null when `enriched_sample_count = 0`. These are descriptive dependency
indicators, not formal corrections for dependence.

Raw metrics and scores except counts and status fields SHALL be nullable.

`page_view_semantics_status` SHALL use only `unvalidated`, `validated_cumulative`,
`contradicted`, or `validated_windowed_weekly`. `validated_windowed_weekly` records
that the page-view field is validated as a trailing-7-day (weekly) view count. The
run-level value describes the endpoint semantic-validation state. An individual
malformed or failed page-view operation is an asset-level
`page_views_status = "error"` and SHALL not by itself contradict the endpoint.
When the run-level status is `contradicted`, D and Q are unavailable for all
categories, while C and R MAY remain available; no category is final rankable.
`request_metadata_json` SHALL contain concise operation names, correlation keys,
the correlation mode, HTTP status, response hash when available, and retry/error
metadata, but no credentials or full response bodies.

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
`N` the total discovered canonical population, `n_h` the number of sampled
assets in that stratum, and `u_h` the number of sampled assets with a usable
age-normalized page-view index. The persisted stratum summary is the authoritative
source for these values; formulas SHALL not reconstruct population denominators
from the enrichment sample.

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

When `N = 0`, `DemandPerAssetRaw`, `DemandMedianRaw`, and all demand stratum
eligibility coverage values SHALL be null or zero as specified in this section;
the implementation SHALL never evaluate `N_h / N`.

`N_h` is the discovered canonical population in stratum `h`, `n_h` is the sampled
population in that stratum, and `u_h` is its usable demand count. A stratum is
usable for the mean only when `u_h >= MIN_USABLE_SAMPLES_PER_STRATUM`. The
denominator is the sum of population weights for usable strata, not `N` alone.

**LREQ-MET-040**: The page-view index SHALL be:

```text
age_normalized_page_view_index = product_page_views
```

The symbol name `age_normalized_page_view_index` is a historical label: the value
is the weekly (trailing-7-day) page-view count, and it no longer depends on
`age_days_exact`. It is usable only for a finite non-negative page-view value, a
valid UTC date no later than cutoff, `age_days_exact >= MIN_AGE_DAYS_FOR_RATE`, and
a matched, published identity. `MIN_AGE_DAYS_FOR_RATE` is an eligibility floor
only, not a rate normalizer. An explicit valid page-view value of zero is usable
and yields an index of zero.

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

**LREQ-MET-060**: Demand stratum eligibility coverage SHALL be:

```text
demand_stratum_eligibility_coverage =
    sum(stratum_weight_h for strata meeting the usable minimum)
```

bounded to `[0, 1]`.

This value measures the proportion of discovered population weight belonging to
strata that meet the minimum usable-observation rule. It is not the percentage of
assets directly observed, a probability-sampling coverage estimate, or a confidence
measure. The persisted name is `demand_stratum_eligibility_coverage`; it SHALL not
be confused with `sample_fraction`.

For a verified category with `N = 0`, demand stratum eligibility coverage SHALL be
`0` and demand raw metrics SHALL be null.

### 7.3 Competition / catalog breadth

**LREQ-MET-070**: `BreadthRaw` SHALL be the verified discovered canonical
population count, not the enrichment sample size. When the endpoint provides a
structurally verified, category-filter-consistent `totalCount`, `breadth_source`
SHALL be `verified_total_count` and `BreadthRaw` SHALL equal that count. Otherwise,
`breadth_source` SHALL be `distinct_canonical_discovered_count`, `BreadthRaw` SHALL
equal the distinct canonical discovered count, and
`breadth_completeness_status` SHALL be `incomplete_estimate`.

The fallback estimate SHALL be treated as potentially materially different from the
true breadth for lean v1. Therefore, a category using the fallback breadth SHALL not
be `rankable`; it MAY be `provisional` only when all other required evidence passes.
This is a conservative operational interpretation of the plan's materiality rule and
prevents an unverified denominator from supporting a fully rankable competition
comparison.

Competition is unavailable when filtering is unverified, a material page failed,
identity incompleteness makes breadth an unbounded lower bound, or the fallback
breadth cannot be bounded. A failed or truncated discovery page SHALL never be
interpreted as zero assets.

For a verified zero-result category, `discovered_population_count` and `BreadthRaw`
SHALL be `0`, `sample_fraction` SHALL be null, and all sample-derived raw metrics
and stratum eligibility coverage values SHALL be null or `0` as defined in their
sections. Competition MAY retain `BreadthRaw = 0` as a descriptive value when its
leave-one-out reference is valid, but the category SHALL not be rankable because the
required sample-derived components are unavailable.

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
ages. A stratum SHALL be usable for Recent Supply only when its dated usable count
meets `MIN_USABLE_SAMPLES_PER_STRATUM`; `recent_supply_stratum_eligibility_coverage`
SHALL be the represented population weight of those usable strata.
`usable_recent_supply_sample_count` SHALL be the sum of usable dated observations in
those strata.

For each stratum, `N_h` is its discovered population, `n_h` is its total sampled
population, and `u_recent_h` is its usable dated count. Each usable dated
observation receives expansion weight `N_h / n_h` for `MedianAgeRaw`; missing or
unusable dates SHALL reduce coverage and SHALL NOT contribute zero to the
recent-share numerator. A stratum is usable for Recent Supply only when
`u_recent_h >= MIN_USABLE_SAMPLES_PER_STRATUM`.

`RECENT_WINDOW_DAYS` defaults to `365`, inclusive. Recent supply measures catalog
composition, not sales flow or publication velocity.

When `N = 0`, RecentShareRaw and MedianAgeRaw SHALL be null and
`recent_supply_stratum_eligibility_coverage` SHALL be `0`.

### 7.5 Quality gap
An asset is quality-eligible only when ProductDetail and ProductPageViews succeeded,
identity mapping matched, `state = "published"`, `rating_average` is finite in
[0, 5], `rating_count >= QUALITY_MIN_RATING_COUNT`, the page-view index is usable,
and page-view semantics are not contradicted. Only quality-eligible observations in
strata meeting `MIN_USABLE_SAMPLES_PER_STRATUM` contribute to `QualityRaw`; other
valid observations remain visible in counts but do not create a partially supported
stratum estimate.

**LREQ-MET-090**: Default quality constants SHALL be:

```text
QUALITY_MIN_RATING_COUNT = 5
QUALITY_MIN_ELIGIBLE_ASSETS = 5
```

Quality is unavailable below the minimum eligible count.
`quality_stratum_eligibility_coverage` SHALL be the sum of `N_h / N` for strata with
at least `MIN_USABLE_SAMPLES_PER_STRATUM` quality-eligible observations; it is not a
count fraction and is not renormalized to the sampled assets. It is a stratum support
measure, not a probability-sampling coverage estimate or confidence measure.

Quality SHALL also be unavailable when weighted usable coverage is below
`MIN_REQUIRED_COMPONENT_COVERAGE`, when page-view semantics are contradicted, or
when the visibility-weighted denominator is zero. `rating_count` is a reliability
minimum only and SHALL NOT weight the quality formula.

The same `MIN_REQUIRED_COMPONENT_COVERAGE` policy applies to Demand and Recent
Supply: if `demand_stratum_eligibility_coverage` or
`recent_supply_stratum_eligibility_coverage` is below the
threshold, the affected component SHALL be unavailable for rankability and SHALL not
receive composite weight. Coverage below the threshold SHALL remain distinguishable
from a valid metric value of zero.

**LREQ-MET-100**: Quality raw value SHALL be:

For each quality-usable stratum `h`, define `quality_weight_h = N_h / n_h` and:

```text
quality_numerator_h =
    quality_weight_h *
    sum((rating_average_i / 5) * age_normalized_page_view_index_i
        for quality-eligible i in stratum h)

quality_denominator_h =
    quality_weight_h *
    sum(age_normalized_page_view_index_i
        for quality-eligible i in stratum h)

QualityRaw =
    sum(quality_numerator_h for quality-usable strata)
    /
    sum(quality_denominator_h for quality-usable strata)
```

It is null when the eligible set is too small, no stratum is quality-usable, or the
expanded visibility-weighted denominator is zero. Quality gap is an apparent
opportunity signal, not a causal measure of dissatisfaction. The result is a
stratum-expanded descriptive signal under a deterministic sample, not a statistically
representative or unbiased population estimate.

When `N = 0`, QualityRaw SHALL be null and
`quality_stratum_eligibility_coverage` SHALL be `0`.

---

## 8. Normalization, components, and composite score

### 8.1 Leave-one-out reference

**LREQ-NRM-010**: Every category SHALL be scored as a target. For target `c_i`,
the reference contains all other categories in the same run.

**LREQ-NRM-020**: `reference_size = category_count - 1`. Field-specific usable
reference counts SHALL be stored separately. `STRONG_REFERENCE_CATEGORY_COUNT = 21`
is an operational run-size threshold: a run with 21 categories qualifies for the
strong-reference policy and has 20 leave-one-out peers for each target. The stored
`reference_size` remains 20 for that run; the threshold SHALL not be misreported as
21 peers.

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
D0 = 0.60 * P_ref(DemandPerAssetRaw) + 0.40 * P_ref(DemandMedianRaw)
       when both normalized values are available;
     the one available normalized value when exactly one is available;
     unavailable when neither is available;
 D = clamp(0.5 + demand_stratum_eligibility_coverage * (D0 - 0.5), 0, 1)
```

`D` is unavailable when no demand raw value is usable.

**LREQ-SCR-020**: Competition SHALL be:

```text
C = clamp(1 - P_ref(BreadthRaw), 0, 1)
```

It is available only with verified and sufficiently complete discovery.

**LREQ-SCR-030**: Recent supply SHALL be:

```text
Rpressure0 = 0.70 * P_ref(RecentShareRaw) + 0.30 * (1 - P_ref(MedianAgeRaw))
    when both normalized values are available;
    the one available normalized value when exactly one is available;
    unavailable when neither is available;
R0 = 1 - Rpressure0
R = clamp(0.5 + recent_supply_stratum_eligibility_coverage * (R0 - 0.5), 0, 1)
```

**LREQ-SCR-040**: Quality gap SHALL be:

```text
Q0 = 1 - P_ref(QualityRaw)
Q = clamp(0.5 + quality_stratum_eligibility_coverage * (Q0 - 0.5), 0, 1)
```

**LREQ-SCR-050**: If `page_view_semantics_status = "contradicted"`, `D` and `Q`
SHALL be unavailable. `C` and `R` MAY remain available, but the category SHALL not
be rankable.

### 8.3 Composite score

Lean v1 fixes the primary weights at `w_D=0.35`, `w_C=0.30`, `w_R=0.20`, and
`w_Q=0.15`. They are not configurable in Lean v1, so the primary balanced score
is exactly the `balanced` sensitivity policy.

**LREQ-SCR-060**: Use available-component renormalization:

```text
W_A = sum(weights of available components)
S_available = sum(weight_x * x for available x) / W_A
market_opportunity_score = null, score_state = "unavailable", when fewer than
    two components are available;
market_opportunity_score = clamp(0.5 + W_A * (S_available - 0.5), 0, 1),
    score_state = "available" when all four components are available, otherwise
    "partial", when at least two components are available.
```

The composite MAY be persisted as `partial`, but it SHALL not be a rankable
recommendation when required evidence policies fail.

---

### 9.1 Rankability states

**LREQ-EVD-010**: Use `not_rankable`, `provisional`, and `rankable` states.

**LREQ-EVD-020**: A category is `not_rankable` when any of the following applies:
discovery filtering is unverified; any unresolved or conflicting discovery identity
remains in the category; required demand data is unavailable; recent-supply minimum
evidence is not met; quality is unavailable under the required-component policy;
page-view semantics are contradicted for a page-view-dependent score; no valid
leave-one-out reference exists; identity preflight fails; or an unrecoverable
data-integrity error occurs. Material discovery failure or unbounded breadth also
makes competition non-rankable.

The implementation SHALL first construct a fixed `base_rankable_candidates` set.
A category is a base-rankable candidate only when the requirements above pass, the
run contains at least `STRONG_REFERENCE_CATEGORY_COUNT` categories, all four
components are available, every required stratum eligibility coverage meets
`MIN_REQUIRED_COMPONENT_COVERAGE`, and field-specific reference support passes.
Sensitivity SHALL not be used to construct this set.

**LREQ-EVD-030**: A score SHALL be `provisional` when computable and required
conditions pass, but the run has 8–20 categories, the run has fewer than
`STRONG_REFERENCE_CATEGORY_COUNT` categories, breadth uses the incomplete fallback
estimate, stratum eligibility coverage is acceptable but below the strong policy, or
sensitivity is high. Discovery bounded by a verified total is sufficient for
rankability and SHALL not by itself force a provisional status.

**LREQ-EVD-040**: A category may be `rankable` only when the run contains at least
8 categories, discovery and identity checks pass, required component evidence
conditions pass, sample and field coverage meet configured thresholds, breadth is
verified or bounded by a verified total, no critical contradiction exists, the
category is in `base_rankable_candidates`, and the final sensitivity thresholds pass.
A run with 8–20 categories SHALL never be labeled `rankable`; it may be provisional.
Sensitivity failure changes final rankability to `provisional` but does not change
the fixed candidate set or the balanced primary score.

```text
MIN_CATEGORIES_PER_RUN = 8
STRONG_REFERENCE_CATEGORY_COUNT = 21
MIN_REQUIRED_COMPONENT_COVERAGE = 0.50
STRONG_COMPONENT_COVERAGE = 0.80
```

`MIN_REQUIRED_COMPONENT_COVERAGE` is the minimum stratum eligibility coverage for
each required sample-derived component. A component below this threshold is
unavailable for rankability and receives no composite weight. A category cannot be
rankable when any required component is below this threshold. The
`STRONG_COMPONENT_COVERAGE` threshold is used by the strong evidence grade; it does
not create a statistical confidence interval or guarantee estimate accuracy.

### 9.2 Evidence grade

**LREQ-EVD-050**: Evidence grade SHALL consider sample size, census status,
component coverage, discovery integrity, reference size, page-view semantics, and
sensitivity. Sample count alone SHALL not determine it.

For evidence grading, define:

```text
minimum_component_sample_count =
    min(
        usable_demand_sample_count,
        usable_recent_supply_sample_count,
        usable_quality_sample_count
    )
```

This is the conservative count used when a combined grade must summarize all three
sample-derived components. For a census category, the census alternative in the
table below uses `discovered_population_count`.

| Grade | Default policy |
|---|---|
| `strong` | `minimum_component_sample_count >= 80`, or a census of at least 50; every required stratum eligibility coverage is at least `STRONG_COMPONENT_COVERAGE`; verified discovery; no identity conflict; a run containing at least `STRONG_REFERENCE_CATEGORY_COUNT` categories (20 leave-one-out peers per target); no critical contradiction; acceptable sensitivity. |
| `moderate` | `minimum_component_sample_count >= 40`, or a census of at least 20; every required stratum eligibility coverage is at least `MIN_REQUIRED_COMPONENT_COVERAGE`; at least 8 categories; no critical identity failure. |
| `weak` | Computable but below moderate policy in sample, coverage, reference, discovery, or sensitivity. |
| `insufficient` | Required evidence is invalid, unavailable, or contradictory; category is not rankable. |

These are operational within-run evidence grades, not confidence intervals,
probabilities, or measures of deterministic-sample representativeness. A strong
sample-based grade SHALL still be labeled `sample-based` in the report.

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
`top_3_stability`, `top_5_stability`, `maximum_score_delta`,
`maximum_rank_displacement`, and `sensitivity_warning`.

For each policy, rank categories by descending composite score. Ties SHALL be broken
deterministically by canonical category path in ascending lexical order. Let `T_k,p`
be the resulting top-`k` category set under policy `p`; categories that are not
in `base_rankable_candidates` SHALL remain visible but SHALL be excluded from the
ranked set. The candidate set SHALL be fixed before any sensitivity policy is
evaluated; sensitivity SHALL not remove or add candidates. Define:

```text
top_k_stability =
    |T_k,balanced ∩ T_k,demand_heavy ∩ T_k,competition_heavy| / k
```

for `k = 3` and `k = 5`. If fewer than `k` rankable categories exist, the value is
null rather than padded with unavailable categories. For each category,
`maximum_score_delta` is the maximum absolute difference between its score under a
non-balanced policy and its balanced score, and `maximum_rank_displacement` is the
maximum absolute rank difference across policies. The same diagnostics SHALL be
stored in `ranking_sensitivity_json` with each policy's scores and ranks.

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
`D/C/R/Q`, discovered population, sample size, census flag, unique enrichment count,
sample fraction, sampling basis, cross-category overlap count, usable count and
stratum eligibility coverage per component, evidence grade, rankability, discovery
status, page-view semantic status, `top_3_stability`,
`top_5_stability`, `maximum_score_delta`, `maximum_rank_displacement`, sensitivity
warning, and the percentage of the category sample shared with other categories.

**LREQ-RPT-030**: Category details SHALL show formulas or concise explanations,
metric inputs, sample strata, warnings, timestamps, and observed-versus-inferred
sample-based values.

**LREQ-RPT-040**: Non-rankable categories SHALL remain visible.

**LREQ-RPT-050**: The report SHALL state that the score is a deterministic,
within-run heuristic based on marketplace signals and, for larger categories, a
stratified sample; it has not been calibrated against sales, revenue, downloads, or
conversion. It SHALL distinguish pagination completion from immutable snapshot
completeness, the page-view index (a validated trailing-7-day view count) from a
lifetime or cumulative count and from a daily-average rate, descriptive midranks
from inferential percentiles, stratum eligibility coverage from sample fraction,
deterministic-sample evidence from statistical representativeness, and evidence grade
from statistical confidence.

The lean dashboard SHALL omit historical run comparison, scheduled-run controls,
complex trend displays, run-resume controls, and advanced provenance navigation. A
sortable table and category detail panel are sufficient.

**LREQ-CLI-010**: The primary command SHALL be equivalent to:

```text
niche-scout run --categories config/categories.json --config config/default.toml
```

It SHALL run one pipeline and exit non-zero on unrecoverable errors.

**LREQ-CLI-020**: The `niche-scout dashboard` command SHALL read the database and
SHALL not initiate discovery or enrichment.

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
rule version; no duplicate membership; `sampling_basis`; `sample_fraction = 1.0` for
non-empty census categories; null sample fraction for zero-population categories; and
sample fraction distinct from stratum eligibility coverage.

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
zero-denominator quality; zero-population categories; and unequal-stratum quality
where `QualityRaw` uses `N_h / n_h` expansion weights.

**LREQ-TST-060**: Scoring tests SHALL cover midrank ties, all-equal references,
missing-component renormalization, coverage shrinkage, contradicted page views,
8-category provisional runs, 21-category strong-reference runs, fixed
`base_rankable_candidates` constructed before sensitivity, sensitivity-driven final
provisional status, and non-rankability.

**LREQ-TST-070**: Sensitivity tests SHALL verify all three policies, rank displacement,
top-three/top-five stability, warning thresholds, and preservation of the balanced
primary score; the sensitivity candidate set SHALL remain unchanged when a warning is
raised; and the balanced policy SHALL equal the primary score weights.

**LREQ-TST-080**: An end-to-end fixture SHALL exercise category validation,
pagination, duplicate/overlapping identities, four-stratum sampling, one enrichment
per unique sampled identity, partial GraphQL failure, metrics, scoring, evidence,
sensitivity, SQLite persistence, and report rendering.

**LREQ-TST-090**: Golden vectors SHALL assert exact results within `1e-9` for
sample-aware metrics, normalization, components, composite score, coverage, evidence,
and sensitivity outputs. The vectors SHALL include a two-category input rejected
before ranking, an 8-category provisional run, and a 21-category strong-reference
run, zero-population behavior, unequal-stratum QualityRaw, sample fraction versus
stratum eligibility coverage, and sensitivity after base-candidate construction.

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
| `ENRICHMENT_SAMPLE_SIZE_PER_CATEGORY` | 100 | No for v1 | Large-category sample target. |
| `SAMPLE_STRATA` | 4 | No for v1 | Systematic ordinal-stratum stride (count). |
| `SAMPLE_PER_STRATUM` | 25 | No for v1 | Per-stratum sample target. |
| `MIN_USABLE_SAMPLES_PER_STRATUM` | 1 | Yes | Stratum evidence minimum. |
| `MIN_REQUIRED_COMPONENT_COVERAGE` | 0.50 | No for v1 | Minimum required stratum eligibility coverage. |
| `STRONG_COMPONENT_COVERAGE` | 0.80 | No for v1 | Strong evidence stratum eligibility coverage threshold. |
| `MIN_AGE_DAYS_FOR_RATE` | 30 | Yes | Index age threshold. |
| `RECENT_WINDOW_DAYS` | 365 | Yes | Recent window. |
| `QUALITY_MIN_RATING_COUNT` | 5 | Yes | Rating evidence minimum. |
| `QUALITY_MIN_ELIGIBLE_ASSETS` | 5 | Yes | Quality sample minimum. |
| `IDENTITY_PREFLIGHT_MIN_CATEGORIES` | 5 | Yes | Preflight breadth. |
| `IDENTITY_PREFLIGHT_ASSETS_PER_CATEGORY` | 2 | Yes | Preflight sample. |
| `IDENTITY_PREFLIGHT_MAX_CONFLICT_RATE` | 0 | No for v1 | Permitted conflict rate. |
| `IDENTITY_PREFLIGHT_MIN_SUCCESS_RATE` | 0.90 | Yes | Preflight success threshold. |
| `w_D,w_C,w_R,w_Q` | 0.35,0.30,0.20,0.15 | No for Lean v1 | Fixed balanced primary weights; identical to the balanced sensitivity policy. |
| `DEMAND_SUBWEIGHTS` | 0.60,0.40 | No for v1 | Demand subcomponents. |
| `RECENT_SUBWEIGHTS` | 0.70,0.30 | No for v1 | Recent subcomponents. |
| `NICHESCOUT_COVEO_BEARER_TOKEN` | operator-supplied | Environment | Coveo credential. |
| `NICHESCOUT_UNITY_CSRF_TOKEN` | operator-supplied | Environment | GraphQL credential. |

The three sensitivity policies in §9.3 are fixed diagnostics in v1 and SHALL not
be disabled in the report. Scoring weights are intentionally not configurable in
Lean v1 so that the primary balanced score and sensitivity baseline cannot diverge.

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
5. the page-view field is a validated trailing-7-day (weekly) view count, stable within a run and refreshed at most daily, not a lifetime or cumulative count and not a daily-average rate;
6. ratings are marketplace observations, not objective product-quality measurements;
7. recent share measures catalog composition, not sales or publication velocity;
8. categories with incomplete discovery are lower-confidence or non-rankable;
9. overlapping assets make category observations dependent;
10. missing data may make a category non-rankable or shrink it toward neutral;
11. sample fraction and stratum eligibility coverage measure different properties;
12. deterministic stratified samples are not statistically representative probability samples;
13. ranking stability depends on selected categories and fixed diagnostic weights;
14. sensitivity warnings indicate instability, not an objectively correct weighting;
15. discovery completion does not guarantee an immutable marketplace snapshot;
16. the result is not calibrated against downloads, sales, revenue, or conversion.
15. the result is not calibrated against downloads, sales, revenue, or conversion.

---

## 17. Acceptance criteria

The implementation is acceptable only when:

1. at least eight categories are required for a normal run, and a run with fewer
   than 21 categories is visibly provisional rather than reliable/rankable;
2. taxonomy and filter validation occur before scoring;
3. identity conflicts and unresolved identities are retained and visible;
4. identity preflight blocks bulk enrichment when thresholds fail;
5. large-category sampling is deterministic, four-stratum, and not first-page-only;
6. small categories are enriched as a census;
7. shared sampled assets are enriched once and joined to all relevant categories;
8. competition uses discovered breadth, not sample size;
9. stratum-expanded metrics use stratum eligibility coverage for demand, recent supply, and quality;
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
22. every sample-derived metric distinguishes population size, sample size, usable sample size, sample fraction, and stratum eligibility coverage;
23. sample selection includes late-result strata and shared assets are enriched once;
24. identity conflicts prevent rankable output and contradicted page-view semantics disable affected components;
25. the traceability matrix maps every individual `LREQ-*` requirement ID (grouped
only by explicitly exhaustive wildcard range) to a primary module and required test;
26. the SRS contains no unresolved references to removed historical, scheduling, resume, or full-enrichment requirements;
27. no unsupported claim of statistical precision, sales prediction, revenue prediction, or representative marketplace estimation remains;
28. QualityRaw uses stratum expansion weights, sensitivity is evaluated after fixed base-candidate construction, and category scores are keyed by `(run_id, category)`.

---

## Appendix A — Formula summary

```text
age_days_exact = (scoring_cutoff_utc - first_published_date_utc).total_seconds() / 86400
age_normalized_page_view_index = product_page_views
stratum_weight_h = N_h / N
DemandPerAssetRaw = sum(stratum_weight_h * stratum_view_mean_h for usable strata)
                    / sum(stratum_weight_h for usable strata)
DemandMedianRaw = weighted median of usable indices with weight N_h / n_h
RecentShareRaw = sum(stratum_weight_h * stratum_recent_share_h for usable strata)
                 / sum(stratum_weight_h for usable strata)
MedianAgeRaw = weighted median of usable ages with weight N_h / n_h
QualityRaw =
    sum((N_h / n_h) * sum((rating_average_i / 5) * age_normalized_page_view_index_i
        for quality-eligible i in stratum h) for quality-usable strata)
    /
    sum((N_h / n_h) * sum(age_normalized_page_view_index_i
        for quality-eligible i in stratum h) for quality-usable strata)
P_ref(x) = (L + 0.5 * E) / m
D0 = 0.60*P_ref(DemandPerAssetRaw) + 0.40*P_ref(DemandMedianRaw)
     when both are available, otherwise the one available value
D = clamp(0.5 + demand_stratum_eligibility_coverage*(D0 - 0.5), 0, 1)
C = clamp(1 - P_ref(BreadthRaw), 0, 1)
Rpressure0 = 0.70*P_ref(RecentShareRaw) + 0.30*(1-P_ref(MedianAgeRaw))
             when both are available, otherwise the one available value
R0 = 1 - Rpressure0
R = clamp(0.5 + recent_supply_stratum_eligibility_coverage*(R0 - 0.5), 0, 1)
Q0 = 1 - P_ref(QualityRaw)
Q = clamp(0.5 + quality_stratum_eligibility_coverage*(Q0 - 0.5), 0, 1)
W_A = sum(weight_x for available components)
S_available = sum(weight_x*x for available x) / W_A
market_opportunity_score = null when fewer than two components are available;
otherwise clamp(0.5 + W_A*(S_available - 0.5), 0, 1)
```

---

## Appendix B — Traceability matrix

| Exhaustive requirement ID range | Primary module | Required tests |
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

Every `LREQ-*` identifier defined in this SRS SHALL belong to exactly one row in this
matrix. A wildcard row denotes the complete set of IDs in that area, not an optional
or approximate grouping. The implementation review SHALL verify that no requirement
ID is omitted, duplicated across rows, or mapped without at least one required test.

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