# Software Requirements Specification

## Unity Asset Store Niche Scout (MVP) — "niche-scout"

| Field | Value |
|---|---|
| Document type | Software Requirements Specification (SRS) |
| Format basis | ISO/IEC/IEEE 29148:2018 structure, adapted |
| Version | 2.2.0 |
| Status | Draft — pending resolution of open items in §2.6 |
| Target release | v0.1.0 (MVP) |

### Revision history

| Version | Change |
|---|---|
| 1.0.0 | Initial SRS. Derived from `V3_MATHEMATICAL_REFERENCE.md`, `V3_MATHEMATICAL_AUDIT_REPORT.md`, and `Unity_Data_Extraction_API.md`, with corrections for two identified defects (see §2.1) and an intentional architecture change (leave-one-out reference, see DD-1 in §6.5). |
| 2.0.0 | Incorporates the Unity Asset Store GraphQL storefront API section added to `Unity_Data_Extraction_API.md`. Replaces the single-source, Coveo-only field model with a two-stage **discovery (Coveo) + enrichment (GraphQL)** extraction architecture: Coveo is retained only for what it uniquely provides (which assets exist in a category), and every other per-asset attribute (rating, review count, first-publication date, page views, price, publisher, category, state) is now sourced from GraphQL. This closes **OI-1** (views field) and **OI-2** (publish-date field) from v1.0.0, updates **OI-4** (asset identity) to require cross-system ID mapping validation, adds a new non-blocking **OI-5** (favorite count, deferred), and introduces **DD-3** (weekly-views approximation from an undocumented, apparently-cumulative view counter) and **DD-4** (asset-state exclusion rule). Per operator instruction, this SRS — not `Unity_Data_Extraction_API.md` — is the single source of truth for every field name, formula, and requirement from this point forward; a future change to either live endpoint requires a revision to this document, not a silent code change. |
| 2.1.0 | Resolves the mathematical, data-quality, and scraping ambiguities identified in the second-opinion review: discovery completeness and taxonomy validation, canonical asset identity handling, explicit state semantics, GraphQL response-shape validation, exact category matching, corrected midrank wording, field-specific reference evidence, rankability boundaries, timestamp provenance, and clarification that the score is a deterministic within-run heuristic rather than an inferential statistical estimate. |
| 2.2.0 | Corrects fractional-age rate bias by using exact UTC age; renames the unvalidated page-view derivative as an age-normalized index; makes aggregate missing-data treatment explicit; strengthens rankability with field-specific reference support; treats unresolved discovery identities as incomplete breadth; replaces restrictive category regex validation with taxonomy membership; distinguishes pagination completion from snapshot consistency; defines filter verification, identity conflicts, GraphQL null/malformed responses, metric populations, and timestamp normalization. |

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

This document specifies the requirements for **niche-scout**, a minimal, single-operator, locally-run system that (a) discovers publicly visible Unity Asset Store assets per category through the documented Coveo search endpoint, (b) enriches each uniquely discovered asset with per-product detail and page-view data through the Unity Asset Store's GraphQL storefront endpoint, (c) computes a deterministic, observed-data comparative score for every category the operator specifies, and (d) presents the results in a minimal local dashboard.

This SRS is written so that a single competent implementer (human or AI coding agent) can build the system without needing to make an undocumented judgment call on any formula, data type, boundary condition, file name, or module boundary. Where the source material was ambiguous or incomplete, this document makes an explicit decision and labels it as such (see **Design Decision (DD-n)** and **Open Item (OI-n)** markers).

### 1.2 Document conventions

- **SHALL** — mandatory. A conforming implementation MUST satisfy this.
- **SHOULD** — strongly recommended; deviation requires a documented reason.
- **MAY** — optional, implementer's discretion.
- Requirement IDs use the form `REQ-<AREA>-<NNN>`, numbered in increments of 10 within each area to allow future insertion without renumbering; where v2.0.0 inserts a requirement between two v1.0.0 numbers, a mid-value (e.g., `REQ-GEN-015`, `REQ-MET-005`) is used rather than renumbering existing requirements.
- Every formula is given in a fenced code block using plain arithmetic notation. `ln` denotes the natural logarithm. `clamp(v, lo, hi) = min(max(v, lo), hi)`. All formulas operate on `float64` unless stated otherwise.
- **Design Decision (DD-n)**: a point where the source material was silent or ambiguous and this SRS makes a binding choice.
- **Open Item (OI-n)**: a dependency that cannot be resolved from the supplied source material alone and SHALL be confirmed against the live system before the affected code is written, or (if marked RESOLVED) a v1.0.0 item this revision closes.

### 1.3 Project scope

In scope for the MVP:

1. A Coveo API client that retrieves category-scoped asset **discovery** data (identity and category membership only) for an operator-supplied set of category paths.
2. A GraphQL API client that **enriches** every uniquely discovered asset, once per run, with product detail (rating, review count, first-publication date, price, category, publisher, state) and page-view data.
3. Local persistence of raw observations (both discovery and enrichment) and computed results in a single SQLite file.
4. A pure scoring engine that computes four bounded components (Demand `D`, Competition `C`, Recent-Supply `R`, Quality-Gap `Q`) and a composite `market_opportunity_score` for **every** category in the operator-supplied set, using a leave-one-out reference (see §6.5, DD-1).
5. A minimal local, read-only dashboard for inspecting and sorting results.
6. A command-line entry point that runs discovery, enrichment, scoring, and persistence in one invocation.

Out of scope for the MVP: see §10.

### 1.4 Definitions, acronyms, abbreviations

| Term | Meaning |
|---|---|
| Asset | A single product listing on the Unity Asset Store. |
| Category | A Coveo `ec_category` facet value, e.g. `"3d > props > exterior"`. |
| Package ID | The Unity Asset Store package identifier appearing in an asset's public URL (e.g. `69717` in `.../horror-assets-69717`); the identifier accepted by GraphQL's `product(id)` and `productPageViews(packageId)` queries. Assumed equal to the asset's Coveo `ec_product_id`/`permanentid` value (see OI-4). |
| Discovery | The per-category Coveo lookup that establishes which assets exist in a category and how many (§6.2). |
| Enrichment | The per-asset GraphQL lookup (`ProductDetail` + `ProductPageViews`), performed at most once per unique asset per run, after discovery (§6.1, §6.3, §6.4). |
| CSRF session | The `_csrf` cookie / `X-CSRF-Token` header pair required for anonymous access to the GraphQL storefront endpoint. |
| Run | One execution of the pipeline against an operator-supplied category set, sharing one UTC cutoff. |
| Target category | Any category in the operator-supplied set, when being scored. |
| Reference set (for a target) | All *other* categories in the same run's operator-supplied set (see DD-1). Every category is a target in its own right and a reference member for every other category in the same run. |
| Midrank percentile | Nonparametric rank-based normalization, defined in §6.5. |
| Component | One of `D`, `C`, `R`, `Q`. |
| Evidence-count proxy | A coverage-adjusted evidence heuristic used by confidence; it is not an effective sample size or an inferential statistic (§6.7). |
| Discovered population | All distinct canonical assets returned for a category by verified discovery, including assets that later fail enrichment or are not published. |
| Published-eligible population | Discovered assets with successful, identity-matched enrichment and `state = "published"`; D, R, and Q use subsets of this population. |
| Age-normalized page-view index | `product_page_views * 7 / age_days_exact`, calculated from an undocumented page-view field. It SHALL NOT be called a weekly traffic rate unless Assumption A-3 is validated. |
| MVP | Minimum viable product. |
| LOO | Leave-one-out. |

### 1.5 Source references

This SRS is derived from three operator-supplied documents, referred to throughout by short name:

- **[REF-MATH]** — `V3_MATHEMATICAL_REFERENCE.md`: the prior system's formula reference.
- **[REF-AUDIT]** — `V3_MATHEMATICAL_AUDIT_REPORT.md`: the prior system's mathematical audit.
- **[REF-API]** — `Unity_Data_Extraction_API.md`: documents two distinct, undocumented-by-Unity endpoints captured from browser network traffic — (a) the Coveo category-search endpoint (`rest/search/v2`), used in this SRS for **discovery only**, and (b) the Unity Asset Store GraphQL storefront endpoint (`/api/graphql/batch`), used in this SRS for **per-asset enrichment**. Where the two sections of `[REF-API]` both expose a value for the same real-world quantity (e.g., a rating), the GraphQL section's field is authoritative for scoring as of v2.0.0 (§2.1, item 4).

Where this SRS departs from `[REF-MATH]` or from a literal reading of `[REF-API]`, the departure and its reason are stated explicitly (see §2.1 and §2.6). This SRS is the single source of truth for the resulting system: `[REF-API]` is retained only as a citation for *why* a given field, header, or constraint was chosen, and a future change to either live endpoint requires a revision to this document, not a silent code change.

---

## 2. Overall Description

### 2.1 Product perspective — what changed from the reviewed V3 design, and why

This is a clean MVP rebuild, not a port. Four changes are made relative to `[REF-MATH]`/v1.0.0 of this SRS, each tied to a specific finding:

1. **The natural-log transform on `DemandPerAssetRaw`, `DemandMedianRaw`, `BreadthRaw`, and `MedianAgeRaw` is removed.** Midrank percentile normalization (§6.5) depends only on order relations between values. Any strictly monotonic transform, including `ln(1+x)`, preserves every `<`, `>`, and `=` relation exactly, so it cannot change the resulting percentile. Since these four raw fields are used only as percentile-normalization inputs, the log step has no effect on any score and is deleted for code simplicity. **REQ-MET-030** below is normative on this point.
2. **The reference cohort is replaced with a leave-one-out (LOO) reference constructed from the operator's own category set**, per the explicit MVP requirement that every specified category SHALL be scored and none SHALL be excluded as reference-only. This is **DD-1**, detailed in §6.5, and it changes what a score *means*: it is a within-run relative comparison, not a comparison against a fixed, cross-time external benchmark.
3. **The override/provisional workflow, cross-run provenance-compatibility gates, and the stability module (nested-prefix / independent-policy analysis) are cut from the MVP.** They existed in `[REF-MATH]` to protect a *frozen, cross-run* reference cohort from drift and contamination. The MVP reference is reconstructed fresh from the current run's data, so target and reference category rows share the same run and collection policy. However, LOO does **not** eliminate underlying asset, publisher, or taxonomy overlap: an asset discovered in multiple categories contributes to multiple category aggregates, so the resulting scores are descriptive relative comparisons rather than independent statistical estimates. See §10 and §11 for the remaining non-goals and limitation.
4. **(New in v2.0.0) Per-asset data collection is split into a two-stage discovery-then-enrichment pipeline, with GraphQL as the primary source of per-asset attributes.** The Coveo endpoint is retained only for what it uniquely provides — the set of assets visible under a given category facet, which is the raw input to the Competition (`C`) component and to `observed_asset_count` (§6.2). Every other per-asset attribute needed for scoring — rating, review count, first-publication date, and page views — is now sourced from the Unity Asset Store's GraphQL storefront endpoint (`[REF-API]`, GraphQL section), queried once per uniquely discovered asset per run (REQ-GQL-055). This resolves **OI-1** and **OI-2** from v1.0.0 (neither Coveo field existed; both GraphQL fields do — see §2.6) and introduces a new operational dependency: an anonymous storefront CSRF session, alongside the existing Coveo bearer token.

   **This change is not free of new limitations, and they are treated as first-class design decisions, not oversights.** GraphQL's `productPageViews` field is an undocumented counter with no declared refresh cadence or time window (`[REF-API]`'s own caveat). It cannot be substituted directly for the `views_count` / `views_window_days` pair envisioned for Coveo in v1.0.0. §6.1 (**REQ-MET-010**, **DD-3**) defines an age-normalized page-view index in its place. The index SHALL NOT be described as a lifetime-average weekly rate until Assumption A-3 has been validated; §11 records the resulting methodological limitation (**L-6**). Enrichment cost also now scales with the number of *unique assets discovered*, not the number of categories or pages — a materially different performance profile from v1.0.0 (§7, **REQ-NFR-015**; §11, **L-7**).

Everything else in `[REF-MATH]` that was assessed as sound — missing-vs-zero handling, coverage-based shrinkage toward 0.5, confidence as a completeness heuristic kept separate from the score, and the general midrank/component/composite structure — is retained and made normative below.

### 2.2 Product functions (summary)

- `F1` — Accept an operator-supplied list of Unity Asset Store category paths.
- `F2` — Discover assets in each category via the Coveo endpoint, with pagination, retry, and rate-limit handling.
- `F3` — Deduplicate discovered assets across categories and enrich each unique asset once via the GraphQL storefront endpoint (product detail + page views), with batching, retry, and rate-limit handling.
- `F4` — Persist raw discovery and enrichment observations and run metadata.
- `F5` — Compute per-category metrics (demand, breadth, recent-supply, quality) from the joined discovery + enrichment data.
- `F6` — Normalize each category's metrics against an LOO reference built from the other categories in the same run.
- `F7` — Compute components `D`, `C`, `R`, `Q` and the composite score for every category.
- `F8` — Compute confidence, coverage status, and rankability for every category.
- `F9` — Persist results.
- `F10` — Display results in a local dashboard.

### 2.3 User characteristics

Single local operator (e.g., a 3D artist or analyst) running the tool on their own machine. Technical enough to set an environment variable and run a CLI command. No multi-user, no remote access, no role-based permissions.

### 2.4 Operating environment

- Python 3.11 or later, single OS process, single machine (Windows, macOS, or Linux).
- Local filesystem for SQLite storage; outbound HTTPS to the Coveo endpoint and to the Unity Asset Store GraphQL storefront endpoint (`assetstore.unity.com`) only.
- No required cloud services, no required paid third-party services.

### 2.5 Design and implementation constraints

- **REQ-GEN-010**: The system SHALL implement the Coveo discovery request contract exactly as specified in `[REF-API]` (endpoint, headers, minimal request shape, category facet mechanics, pagination) unless explicitly overridden below.
- **REQ-GEN-015 (NEW)**: The system SHALL implement the GraphQL batch request contract exactly as specified in `[REF-API]`'s GraphQL section (endpoint, batch array shape, headers, CSRF cookie/header pairing) unless explicitly overridden below (§4.2).
- **REQ-GEN-020**: The system SHALL NOT persist, log, or transmit the Coveo bearer token in any form other than passing it in the `Authorization` header of the outbound request for which it is needed.
- **REQ-GEN-025 (NEW)**: The system SHALL NOT persist, log, or transmit the Unity storefront CSRF token/cookie in any form other than the `_csrf` cookie and `X-CSRF-Token` header of the outbound GraphQL request for which it is needed.
- **REQ-GEN-030 (revised in v2.2.0)**: The scoring engine (metrics + normalization + components + composite + confidence heuristic) SHALL be implemented as pure functions: given the same inputs, they SHALL return the same outputs, and SHALL NOT perform network I/O, file I/O, or read the system clock. `run_started_at_utc` SHALL be captured at orchestration start; `scoring_cutoff_utc` SHALL be captured once immediately before metrics/scoring after enrichment and passed explicitly to the pure functions. All timestamp arithmetic SHALL use timezone-aware UTC values.
- **REQ-GEN-035 (NEW)**: All GraphQL timestamps used by scoring SHALL be timezone-aware ISO 8601 values. The client SHALL convert them to UTC before persistence and reject malformed or timezone-naive timestamps. Date-only values SHALL be rejected unless a future SRS revision explicitly defines their timezone and midnight interpretation. A timestamp after `scoring_cutoff_utc` MAY be retained for audit but SHALL be unavailable to scoring.

### 2.6 Assumptions, dependencies, and open data gaps

**OI-1 (field availability resolved in v2.0.0; semantics remain conditional).** Originally: `[REF-API]`'s Coveo `fieldsToInclude` list carried no field for a view or popularity count. **Resolution:** the GraphQL storefront endpoint exposes `productPageViews(packageId: String!)`, confirmed against a live tested response in `[REF-API]`. This field is now the system's sole page-view signal (REQ-GQL-050). It is **not** a drop-in replacement for the `views_count` / `views_window_days` pair envisioned in `[REF-MATH]` and v1.0.0 of this SRS: it carries no declared time window, and its update cadence is undocumented. §6.1 (REQ-MET-010, **DD-3**) defines a lifetime-average page-view proxy, and this proxy — not a literal weekly count — is what `DemandPerAssetRaw` and `DemandMedianRaw` are computed from going forward. Whether the field is a cumulative lifetime total remains Assumption A-3 and SHALL be validated against live observations before interpreting the result as a lifetime-average proxy. The v1.0.0 configuration keys `VIEWS_COUNT_FIELD` and `VIEWS_WINDOW_DAYS_FIELD` (Appendix C) are removed: there is nothing left to configure, since the field name and its (lack of) windowing are endpoint observations, not runtime configuration.

**OI-2 (RESOLVED in v2.0.0).** Originally: no confirmed response field for an asset's publication date. **Resolution:** `product.firstPublishedDate` on the GraphQL `ProductDetail` query, confirmed against a live tested response in `[REF-API]`. This is a first-publication timestamp, not a last-updated timestamp — `product.currentVersion.publishedDate` is a separate field the system persists (for possible future use, §10 ND-10) but does **not** use for the Recent-Supply component. The v1.0.0 configuration key `PUBLISH_DATE_FIELD` (Appendix C) is removed for the same reason as OI-1.

**OI-3 (unchanged, still open): The full category taxonomy (all "idle" `ec_category` facet values) is not supplied.** `[REF-API]` requires preserving the complete facet structure, including idle category values, for faithful browser replay of the Coveo **discovery** request. **The operator SHALL capture one real browser request once and save its full facet block as a static asset** `config/category_taxonomy.json` (see REQ-EXT-020). This SRS specifies the mechanism, not the data. This item is unaffected by the GraphQL addition, since GraphQL is not involved in category discovery.

**OI-4 (updated in v2.1.0, still open): Asset identity now spans two independently-identified systems and SHALL be validated before bulk collection.** Discovery resolves a raw identity candidate per REQ-EXT-060, then canonicalizes it into an accepted GraphQL/package identifier. `ec_product_id` and `permanentid` are preferred; URI fallbacks SHALL be parsed and SHALL NOT be passed as complete URLs unless the live API contract explicitly confirms that behavior. GraphQL is queried only with the canonical identifier. `ProductDetail`'s response separately returns `productId` and `itemId`, which `[REF-API]` explicitly warns are *different* identifiers from the one the query accepts as `id`. **Before bulk collection, the operator SHALL run the pipeline against a small (≥ 5 category) sample and confirm that the returned `product.id` matches the requested canonical identifier for every successfully enriched asset.** A mismatch is retained for audit but is an enrichment identity failure for scoring, not merely an informational warning: the asset remains available to discovery breadth but is excluded from D/R/Q.

**OI-5 (new in v2.0.0, non-blocking): Favorite count is not collected in the MVP.** `[REF-API]` shows a page-visible favorite count and an embedded `packageInListHotness` field that matched it for one tested product, but explicitly states this mapping is undocumented, unvalidated across products, not returned by the `ProductDetail`/`ProductPageViews` batch used in REQ-GQL-050, and only obtainable (if at all) by parsing a separate, unstable storefront page-hydration payload. This SRS makes an explicit non-goal of it (§10, ND-9) rather than leaving it open-ended; it MAY be revisited in a future revision if a stable collection path is confirmed.

- **Assumption A-1**: `timezone` in the Coveo discovery request body does not affect `ec_category` filtering correctness and MAY default to `"UTC"` rather than the session-specific `"Asia/Tehran"` value shown as an example in `[REF-API]`. If this assumption is found false during OI-3 verification, it SHALL be revised.
- **Assumption A-2**: The operator holds a currently valid Coveo bearer token and is responsible for refreshing it; token acquisition/automation is out of scope (§10).
- **Assumption A-3 (revised in v2.2.0)**: `productPageViews` is assumed to be a cumulative, monotonically-non-decreasing lifetime total, not a rolling or periodic figure, per `[REF-API]`'s own framing ("confirm whether the value is cumulative... before using changes... as a time-series measure"). This assumption is not resolved merely by field availability. Until validated, the derived value SHALL be named and presented only as an **age-normalized page-view index**, not as a lifetime-average weekly traffic rate. Validation SHALL select at least 10 assets spanning ages and categories, collect each asset on at least three dates, test monotonicity, compare changes with elapsed time, inspect newly published assets for plausible starting values, and record the validation status, date, asset count, and contradictions. A later observation showing a lower value for the same asset SHALL be treated as a data-quality signal and set the semantic status to `contradicted`, not silently accepted (§10, ND-11).
- **Assumption A-4 (new in v2.0.0)**: The operator holds a currently valid Unity Asset Store storefront CSRF token/session (the `_csrf` cookie value) and is responsible for refreshing it if a run fails with a CSRF or auth error; automated acquisition is out of scope (§10, ND-8).
- **Dependency**: Outbound network access to `unitytechnologiesproductionmkahteav.org.coveo.com` (Coveo discovery) and to `assetstore.unity.com` (GraphQL enrichment), both on port 443.

---

## 3. System Architecture

### 3.1 Modules and responsibilities

| Module | Responsibility | I/O? |
|---|---|---|
| `extraction` | Build and send Coveo **discovery** requests (paginate, validate category application, retry/backoff) and GraphQL **enrichment** requests (batch per unique asset, retry/backoff); deduplicate asset identities across categories before enrichment | Yes (network) |
| `persistence` | SQLite schema, read/write of runs, raw discovery observations, raw enrichment observations, and results | Yes (disk) |
| `metrics` | Per-category metric computation from raw discovery + enrichment observations, joined by `asset_identity_key`, plus cutoff | No (pure) |
| `scoring` | Normalization, components, composite, confidence, coverage, rankability | No (pure) |
| `pipeline` | Orchestrates discovery → dedup → enrichment → persistence → metrics → scoring → persistence of results | Yes (coordinates the above) |
| `dashboard` | Read-only local UI over persisted results | Yes (disk read only) |
| `cli` | Entry point, argument parsing, config loading | Yes |

### 3.2 Data flow (one run)

```text
 1. CLI loads operator category list + config + Coveo bearer token + Unity storefront CSRF token/cookie.
  2. pipeline generates run_id (UUID4) and `run_started_at_utc = now(UTC)`, validates and records the taxonomy metadata, initializes `page_view_semantics_status` from the latest operator validation (`unvalidated` unless validated or contradicted), sets `discovery_pagination_mode = "offset_best_effort"`, then writes the `runs` row (status=running). `scoring_cutoff_utc` is initially unset in orchestration state and is captured after enrichment in step 8.
3. For each category: extraction.coveo_client.fetch_category(category, run_started_at_utc)
    -> raw discovery records (paginated, retried).
  4. persistence stores each raw discovery record as a row in `raw_observations`, tagged with run_id + category, including all identity candidates, canonicalization status, source, and resolution reason.
 5. pipeline computes the deduplicated set of every asset_identity_key discovered across all
    categories in the run (REQ-GQL-055).
 6. For each unique asset_identity_key: extraction.graphql_client.fetch_product(asset_identity_key)
    -> one ProductDetail + ProductPageViews batch (retried, rate-limited).
 7. persistence stores each enrichment result as one row in `raw_product_details`, tagged with
    run_id + asset_identity_key (independent of category).
  8. Capture `scoring_cutoff_utc = now(UTC)` immediately before metrics computation. For each category: metrics.compute(
        raw_observations_for[category] JOIN raw_product_details ON asset_identity_key,
        scoring_cutoff_utc
    ) -> per-category metric bundle.
 9. scoring.build_reference(all_metric_bundles, exclude=target_category) -> LOO reference for
    that target (per REQ-NRM-010).
 10. scoring.score_category(target_bundle, loo_reference) -> D, C, R, Q, composite, confidence_heuristic,
    coverage_status, rankable. Repeated for every category in the run (REQ-SCR-010).
11. persistence writes one row per category into `category_scores`.
 12. pipeline records `completed_at_utc` and marks `runs.status = completed`.
13. dashboard reads `category_scores` (optionally filtered by run_id) for display.
```

### 3.3 Purity boundary

**REQ-GEN-040**: The `metrics` and `scoring` modules SHALL NOT import or call anything in `extraction`, `persistence`, or `dashboard`. They SHALL accept plain Python data structures (dataclasses / typed dicts) and return plain data structures. This boundary SHALL be enforced by a dedicated import-linter test (§9), unaffected by the extraction module now containing two clients instead of one.

---

## 4. External Interface Requirements

### 4.1 Coveo Search API — discovery only (source of truth: `[REF-API]`, Coveo section)

- **REQ-EXT-010**: Endpoint SHALL be exactly `POST https://unitytechnologiesproductionmkahteav.org.coveo.com/rest/search/v2?organizationId=unitytechnologiesproductionmkahteav`.
- **REQ-EXT-020 (revised in v2.1.0)**: The request body SHALL be built from a static base template stored at `config/category_taxonomy.json` (OI-3) containing the full facet block (all idle `ec_category` values) captured from a real browser session, with only the `currentValues` entry for the target category set to `"state": "selected"` and all others set to `"state": "idle"`, per `[REF-API]`. The taxonomy file SHALL include `schema_version`, `captured_at_utc`, `source_url`, `template_sha256`, and the canonical category-path inventory. At startup, the system SHALL verify the file schema, verify that every operator category exists in the inventory, record the capture timestamp and SHA-256 in `runs`, and abort before network collection if the file is missing, malformed, stale beyond `MAX_TAXONOMY_AGE_DAYS`, or does not contain an operator category. All non-`fieldsToInclude` parts of the captured template (`facets`, `context`, `dictionaryFieldContext`, `searchHub`, `analytics`, `actionsHistory`) SHALL be replayed as captured, even where a field (e.g. `ec_price` in `dictionaryFieldContext`) is no longer requested under REQ-EXT-040.
- **REQ-EXT-030**: Headers SHALL be exactly: `Authorization: Bearer <token>`, `Content-Type: application/json`, `Accept: application/json`, `Origin: https://assetstore.unity.com`, `Referer: https://assetstore.unity.com/`. The token SHALL be read from the environment variable `NICHESCOUT_COVEO_BEARER_TOKEN` at process start; if absent or empty, the process SHALL exit with a non-zero status and an error message that does not echo any partial token value.
- **REQ-EXT-040 (revised in v2.0.0)**: `fieldsToInclude` SHALL contain exactly: `permanentid`, `ec_product_id`, `ec_name`, `ec_category`, `publisher_name`. This is a **discovery-only** field set (§2.1, item 4): rating, price, and popularity are no longer sourced from Coveo as of v2.0.0. Fields present in v1.0.0 that are superseded by GraphQL equivalents (`ec_price`, `ec_rating`, `ec_rating_count`, `ec_thumbnails`, `ec_tags`, `min_unity_version`) SHALL NOT be requested, to reduce payload size and avoid two systems disagreeing about the same fact. This list SHALL override whatever `fieldsToInclude` value is present in the captured base template (REQ-EXT-020).
- **REQ-EXT-050 (revised in v2.0.0)**: At startup, the system SHALL validate that both the Coveo bearer token (REQ-EXT-030) and the Unity storefront CSRF token (REQ-GQL-040) are configured (non-empty). If either is unset, the system SHALL abort before making any network request, with an error identifying which credential is missing. (v1.0.0's OI-1/OI-2 field-mapping validation at this requirement is removed: those fields are now fixed GraphQL field names confirmed in `[REF-API]`, not runtime configuration — see §2.6.)
- **REQ-EXT-060 (revised in v2.2.0)**: For each discovery record, the system SHALL collect every non-empty candidate from `ec_product_id`, `permanentid`, response-level `clickUri`, and response-level `uri`, then canonicalize every parseable candidate. If at least one candidate canonicalizes and all canonicalized candidates agree, the agreed value SHALL be stored as `asset_identity_key` and the source candidate SHALL be stored as `identity_source`. If a higher-priority candidate is malformed but a lower-priority candidate canonicalizes, the valid lower-priority candidate MAY be used and the malformed candidate SHALL be retained for audit. If canonicalized candidates conflict, the record SHALL be marked `identity_resolution_status = 'conflict'`, excluded from enrichment, and counted as an unresolved identity. If no candidate canonicalizes, the record SHALL be marked `identity_resolution_status = 'unresolved'`, excluded from enrichment, and logged with a reason. URI candidates SHALL be parsed; a complete URL SHALL NOT be passed directly as the GraphQL key unless live API validation explicitly confirms that behavior. Only a canonical, non-empty value SHALL be passed to GraphQL (REQ-GQL-055, REQ-GQL-060).
- **REQ-EXT-070 (revised in v2.2.0)**: `numberOfResults` SHALL be `96` per page (the documented maximum). `firstResult` SHALL increment by `96` each page. `pagination_complete` means that all required requests succeeded, the filter was verified, and pagination terminated through a short page or reconciled `totalCount`. This is best-effort offset traversal, not proof of an immutable catalog snapshot; assets may be inserted, removed, reordered, duplicated, or skipped while pages are fetched. The system SHALL persist `snapshot_completeness_status = 'not_guaranteed'` for every run; no category may claim an immutable snapshot. A category is `discovery_status = 'complete'` only when pagination is complete, filter verification succeeds, and no unresolved or conflicting identities were returned. If accumulated results reach `MAX_RESULTS_PER_CATEGORY` before completion, the category SHALL be marked `truncated`; the observed breadth is a lower bound and SHALL NOT be treated as complete evidence.
- **REQ-EXT-080**: No free-text `q` or `query` field SHALL be present in any request body (per `[REF-API]`'s explicit warning that this contaminates category filtering with keyword relevance).
- **REQ-EXT-090 (revised in v2.2.0)**: After discovery, the system SHALL validate category application using exact normalized category-path membership, not substring containment. Normalization SHALL apply `.strip().casefold()` to each complete path. The MVP policy SHALL be `category_match_policy = 'exact'`; descendant matching is not enabled unless separately configured and persisted. `discovery_filter_verified = 1` SHALL be recorded only when: (a) the request contains exactly one selected canonical target category; (b) no free-text query is present; (c) any returned `advancedExpression` contains a category predicate agreeing with the target, when present; (d) every returned category path exactly equals the normalized target path under the exact policy; and (e) the response has the expected structural fields. A mismatch, failed page, unresolved/conflicting identity, or unverified filter SHALL prevent C and rankability from being complete. A `totalCount` of zero is valid zero-breadth evidence only when the request predicate and response structure are independently verified; otherwise the category SHALL be marked `filter_unverified`.
- **REQ-EXT-100**: Between consecutive Coveo requests (across all categories/pages in a run), the system SHALL wait at least `COVEO_MIN_REQUEST_INTERVAL_SECONDS` (default `1.0`s, configurable; renamed from `MIN_REQUEST_INTERVAL_SECONDS` in v1.0.0 for symmetry with the new GraphQL client, §4.2). On HTTP `429` or `5xx`, the system SHALL retry with exponential backoff (base `2.0`s, up to `MAX_RETRIES` = `5`), honoring a `Retry-After` response header when present, before giving up and marking that page as failed (failure removes that page's records from the category's `observed_*` counts; it SHALL NOT be treated as zero evidence).

### 4.2 Unity Asset Store GraphQL Storefront API — enrichment only (NEW; source of truth: `[REF-API]`, GraphQL section)

- **REQ-GQL-010**: Endpoint SHALL be exactly `POST https://assetstore.unity.com/api/graphql/batch`.
- **REQ-GQL-020 (revised in v2.1.0)**: Each request body SHALL be a JSON array of exactly two operation objects, each of the shape `{"query": ..., "variables": {...}, "operationName": ...}`: `ProductDetail` (variable `id: ID!`) and `ProductPageViews` (variable `packageId: String!`), both set to the same canonical `asset_identity_key` value (REQ-GQL-060). The response SHALL be a JSON array of exactly two items. Each item SHALL be validated by operation identity when supplied and by its expected data shape (`product` for `ProductDetail`, scalar page-view data for `ProductPageViews`); array position alone SHALL NOT be sufficient when identity or shape is ambiguous. Any response that is not a valid, unambiguous two-operation response SHALL be treated as a failed enrichment for that asset (REQ-GQL-070).
- **REQ-GQL-030**: Headers SHALL be exactly: `Accept: application/json`, `Content-Type: application/json;charset=UTF-8`, `operations: ProductDetail,ProductPageViews`, `X-Requested-With: XMLHttpRequest`, `X-Source: storefront`, `X-CSRF-Token: <token>`, `Origin: https://assetstore.unity.com`, `Referer: https://assetstore.unity.com/`. The `Cookie` header SHALL include `_csrf=<token>` using the identical value as `X-CSRF-Token`.
- **REQ-GQL-040**: The CSRF token SHALL be read from the environment variable `NICHESCOUT_UNITY_CSRF_TOKEN` at process start; if absent or empty, the process SHALL exit with a non-zero status and an error message that does not echo any partial token value (mirrors REQ-EXT-030).
- **REQ-GQL-050**: The `ProductDetail` query SHALL request exactly the field set given in `[REF-API]`'s complete/production Python example, reproduced here verbatim as the normative contract:
  ```graphql
  query ProductDetail($id: ID!) {
    product(id: $id) {
      id
      productId
      itemId
      slug
      name
      description
      rating { average count }
      reviewCount
      currentVersion { id name publishedDate }
      downloadSize
      assetCount
      publisher { id name url supportUrl supportEmail }
      originalPrice {
        itemId originalPrice finalPrice isFree currency entitlementType
        discount { save percentage type saleType }
      }
      category { id name slug longName }
      firstPublishedDate
      publishNotes
      supportedUnityVersions
      state
      plusProSale
    }
  }
  ```
  ```graphql
  query ProductPageViews($packageId: String!) {
    productPageViews(packageId: $packageId)
  }
  ```
  The exploratory-only fields `elevatorPitch`, `keyFeatures`, `compatibilityInfo`, `overlay`, `overlayText`, `licenseText` seen elsewhere in `[REF-API]` are NOT required for MVP scoring and SHALL NOT be added without a corresponding SRS revision (schema stability).
- **REQ-GQL-055**: Before enrichment, the system SHALL compute the union of `asset_identity_key` values across every category discovered in the run and SHALL query GraphQL **at most once per unique key per run**, regardless of how many categories reference it. The resulting `raw_product_details` row SHALL be joined back to every `raw_observations` row sharing that key during metrics computation (§3.2, step 8).
- **REQ-GQL-060**: The same string value SHALL be passed as `ProductDetail`'s `id` variable and `ProductPageViews`'s `packageId` variable for a given asset (OI-4).
- **REQ-GQL-070 (revised in v2.2.0)**: For each batch item, the system SHALL check the response item's `errors` member independently of the overall HTTP status. An HTTP `200` response containing `errors` for the `ProductDetail` item SHALL be recorded as `product_detail_status = 'error'`; likewise, `page_views_status = 'error'` for a `ProductPageViews` item with `errors`. An HTTP `200` response with a missing required object, `product = null`, `productPageViews = null`, a wrong response type, a boolean/non-finite/negative page-view scalar, or any missing required identity field SHALL also be recorded as an operation error. The two statuses SHALL be tracked independently. A field sourced from a failed or malformed operation SHALL be persisted as null, never coerced to a default or zero value.
- **REQ-GQL-080 (revised in v2.2.0)**: Between consecutive GraphQL requests, the system SHALL wait at least `GRAPHQL_MIN_REQUEST_INTERVAL_SECONDS` (default `0.5`s, configurable, Appendix C). On HTTP `429` or `5xx`, it SHALL retry with the same exponential-backoff policy as REQ-EXT-100. On HTTP `400` with a body indicating `csrf token mismatch`, or HTTP `401`/`403`, it SHALL NOT retry and SHALL abort the run with an error identifying the CSRF/session dependency. Other `4xx` responses, including `404`, `409`, and `422`, SHALL NOT be retried and SHALL be recorded as permanent operation errors. Malformed JSON, timeout, connection-reset, and DNS failures SHALL be classified explicitly as transient or permanent by the client; transient failures follow the retry policy and permanent failures produce an error status without coercion.
- **REQ-GQL-090**: The system SHALL NOT attempt to collect `favorite_count` / `packageInListHotness` in the MVP (§2.6, OI-5; §10, ND-9).
- **REQ-GQL-100**: The system SHALL NOT include any GraphQL operation other than `ProductDetail` and `ProductPageViews` in a batch — specifically excluding `CurrentUser`, `ShoppingCartQuery`, `ServerTime`, `ProductRatingStar`, `Publisher`, `BigQueryCachedPackages`, `ProductTags`, and `ProductMLRecommendation`, all of which `[REF-API]` documents as observed in browser traffic but unneeded for a single-product collector.
- **REQ-GQL-110 (revised in v2.2.0)**: For every enriched asset, the system SHALL compare the requested canonical `asset_identity_key` against the `id` field of the returned `product` object. A mismatch SHALL be logged, persisted as `id_mapping_mismatch = 1` and `enrichment_identity_status = 'mismatch'`, and treated as an enrichment identity failure for scoring: the asset remains available to the discovered population but is excluded from D/R/Q. A match SHALL set `enrichment_identity_status = 'matched'`. A missing or malformed returned product identity SHALL set `enrichment_identity_status = 'unresolved'` and exclude the asset from D/R/Q.
- **REQ-GQL-120 (DD-4, revised in v2.1.0)**: State eligibility SHALL be explicit: `product.state == "published"` is eligible for D/R/Q; a null or missing state is `state_unknown` and is excluded from D/R/Q; any present value other than `"published"` is `state_excluded` and is excluded from D/R/Q. The asset SHALL remain in `raw_product_details` for audit purposes. State filtering does not remove an asset from discovery breadth or C, because C is a discovery-only metric (REQ-MET-040).

### 4.3 Category input interface

- **REQ-CAT-010**: The operator SHALL supply categories via a JSON file, default path `config/categories.json`, containing a JSON array of strings, e.g. `["3d > props > exterior", "3d > props > interior"]`.
- **REQ-CAT-020 (revised in v2.2.0)**: Each category input SHALL be a string and SHALL be normalized with `normalize_category_path(value) = value.strip().casefold()`. The normalized value SHALL be matched against the normalized canonical category-path inventory in `config/category_taxonomy.json`; the taxonomy inventory, not an ad hoc ASCII regex, is authoritative. If no taxonomy match exists, the run SHALL abort before network collection and name the offending value. The canonical taxonomy spelling SHALL be used in requests and persisted as the operative category value.
- **REQ-CAT-030 (revised in v2.2.0)**: Duplicate category inputs after `casefold()` normalization SHALL be deduplicated with a warning; the deduplicated, order-preserved canonical taxonomy list is the operative category set. The original operator input and canonical value SHOULD both be retained in run metadata.
- **REQ-CAT-040 (revised in v2.1.0)**: The operative category set SHALL contain at least `MIN_CATEGORIES_PER_RUN` = `2` entries (the mathematical minimum for any LOO reference to exist). If fewer, the run SHALL abort with an explanatory error. A run with fewer than `MIN_CATEGORIES_FOR_RANKABILITY` = `21` categories MAY compute provisional scores, but no category in that run SHALL be rankable because its LOO reference is too small for the MVP rankability threshold. The operator's categories SHALL also be checked against the captured taxonomy; a missing category SHALL abort before network collection.

### 4.4 Dashboard interface (see also §6.9)

- **REQ-DSH-010**: The dashboard SHALL be launched by a single command and SHALL open a local web page with no authentication step, reflecting single-operator, local-only use.

---

## 5. Data Model

### 5.1 SQLite schema (authoritative DDL)

```sql
CREATE TABLE runs (
    run_id                TEXT PRIMARY KEY,
    created_at_utc        TEXT NOT NULL,
    run_started_at_utc    TEXT NOT NULL,
    scoring_cutoff_utc    TEXT,
    completed_at_utc      TEXT,
    taxonomy_captured_at_utc TEXT NOT NULL,
    taxonomy_sha256       TEXT NOT NULL,
    page_view_semantics_status TEXT NOT NULL CHECK (page_view_semantics_status IN ('unvalidated','validated_cumulative','contradicted')),
    discovery_pagination_mode TEXT NOT NULL CHECK (discovery_pagination_mode IN ('offset_best_effort')),
    categories_json          TEXT NOT NULL,
    config_snapshot_json       TEXT NOT NULL,
    status                       TEXT NOT NULL CHECK (status IN ('running','completed','failed'))
);

-- Coveo discovery rows: identity + category membership only, per v2.0.0 (REQ-EXT-040).
CREATE TABLE raw_observations (
    observation_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id                 TEXT NOT NULL REFERENCES runs(run_id),
    category                  TEXT NOT NULL,
    asset_identity_key           TEXT,
    discovery_identity_raw       TEXT,
    identity_candidates_json     TEXT NOT NULL,
    ec_product_id                   TEXT,
    permanentid                        TEXT,
    source_url                            TEXT,
    identity_resolution_status            TEXT NOT NULL CHECK (identity_resolution_status IN ('canonical','unresolved','conflict')),
    identity_source                         TEXT,
    identity_resolution_reason              TEXT,
    ec_name                                  TEXT,
    publisher_name                              TEXT,
    ec_category_raw_json                           TEXT NOT NULL,
    raw_json                                          TEXT NOT NULL,
    retrieved_at_utc                                     TEXT NOT NULL,
    UNIQUE (run_id, category, asset_identity_key)
);

-- GraphQL enrichment rows: one per unique asset per run, independent of category (REQ-GQL-055).
CREATE TABLE raw_product_details (
    run_id                              TEXT NOT NULL REFERENCES runs(run_id),
    asset_identity_key                     TEXT NOT NULL,
    graphql_id                                TEXT,
    product_id                                   TEXT,
    item_id                                         TEXT,
    slug                                                TEXT,
    name                                                   TEXT,
    rating_average                                            REAL,
    rating_count                                                 INTEGER,
    review_count                                                    INTEGER,
    current_version_name                                               TEXT,
    current_version_published_date_utc                                    TEXT,
    download_size                                                            TEXT,
    asset_count                                                                 INTEGER,
    publisher_id                                                                   TEXT,
    publisher_name                                                                    TEXT,
    original_price                                                                       REAL,
    final_price                                                                             REAL,
    is_free                                                                                    INTEGER CHECK (is_free IN (0,1)),
    currency                                                                                       TEXT,
    discount_percentage                                                                               REAL,
    category_id                                                                                          TEXT,
    category_name                                                                                           TEXT,
    category_long_name                                                                                         TEXT,
    first_published_date_utc                                                                                      TEXT,
    state                                                                                                            TEXT,
    plus_pro_sale                                                                                                       INTEGER CHECK (plus_pro_sale IN (0,1)),
    product_page_views                                                                                                     REAL,
    product_detail_status                                                                                                     TEXT NOT NULL CHECK (product_detail_status IN ('ok','error')),
    page_views_status                                                                                                            TEXT NOT NULL CHECK (page_views_status IN ('ok','error')),
    id_mapping_mismatch                                                                                                             INTEGER NOT NULL CHECK (id_mapping_mismatch IN (0,1)),
    state_exclusion_reason                                                                                                          TEXT CHECK (state_exclusion_reason IN ('state_excluded','state_unknown')),
    enrichment_identity_status                                                                                                      TEXT NOT NULL CHECK (enrichment_identity_status IN ('matched','mismatch','unresolved')),
    raw_json                                                                                                                           TEXT NOT NULL,
    fetched_at_utc                                                                                                                        TEXT NOT NULL,
    PRIMARY KEY (run_id, asset_identity_key)
);

CREATE TABLE category_scores (
    run_id                          TEXT NOT NULL REFERENCES runs(run_id),
    category                          TEXT NOT NULL,
    observed_asset_count                INTEGER NOT NULL,
    usable_view_count                      INTEGER,
    usable_view_coverage                      REAL,
    median_age_normalized_page_view_index       REAL,
    page_view_index_per_observed_asset           REAL,
    observed_discovery_breadth                         INTEGER NOT NULL,
    discovery_status                                    TEXT NOT NULL CHECK (discovery_status IN ('complete','truncated','page_failed','filter_unverified','category_mismatch','identity_incomplete','request_failed')),
    pagination_complete                                  INTEGER NOT NULL CHECK (pagination_complete IN (0,1)),
    snapshot_completeness_status                         TEXT NOT NULL CHECK (snapshot_completeness_status IN ('not_guaranteed','not_assessed')),
    discovery_total_count                              INTEGER,
    discovery_returned_count                           INTEGER NOT NULL,
    discovery_failed_page_count                        INTEGER NOT NULL,
    discovery_termination_reason                       TEXT NOT NULL,
    discovery_filter_verified                          INTEGER NOT NULL CHECK (discovery_filter_verified IN (0,1)),
    discovery_category_mismatch_count                 INTEGER NOT NULL,
    discovery_unresolved_identity_count               INTEGER NOT NULL,
    discovery_duplicate_count                        INTEGER NOT NULL,
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
    evidence_count_proxy                                                                          REAL,
    reference_usable_counts_json                                                                   TEXT NOT NULL,
    confidence_heuristic                                                                               REAL,
    coverage_status                                                                                      TEXT NOT NULL CHECK (coverage_status IN ('insufficient_data','partial','full')),
    rankable                                                                                                INTEGER NOT NULL CHECK (rankable IN (0,1)),
    reference_size                                                                                            INTEGER NOT NULL,
    computed_at_utc                                                                                              TEXT NOT NULL,
    PRIMARY KEY (run_id, category)
);
```

### 5.2 Data dictionary (selected non-obvious fields)

| Field | Table | Type | Nullable | Domain | Notes |
| `asset_identity_key` | `raw_observations`, `raw_product_details` | TEXT | Yes in `raw_observations`; No in `raw_product_details` | canonical, non-empty when present | Canonical GraphQL/package identifier resolved per REQ-EXT-060. An unresolved or conflicting discovery record is retained with a null key and excluded from enrichment; the original candidates and resolution reason are retained separately. |
| `identity_resolution_status` | `raw_observations` | TEXT | No | `canonical`, `unresolved`, `conflict` | Identity resolution outcome per REQ-EXT-060. Unresolved/conflicting records are retained for audit but excluded from enrichment and complete breadth. |
| `identity_candidates_json` | `raw_observations` | TEXT | No | JSON array | All non-empty identity candidates considered during canonicalization, retained to make fallback and conflict decisions auditable. |
| `product_page_views` | `raw_product_details` | REAL | Yes | ≥ 0, finite | Raw value from GraphQL `productPageViews`. Its cumulative/window semantics are unvalidated under A-3. Null = unavailable, error, malformed response, or state-excluded — never coerced to 0. |
| `median_age_normalized_page_view_index` | `category_scores` | REAL | Yes | ≥ 0, finite | Median of usable age-normalized page-view indices; it is not a literal rolling-week count. |
| `first_published_date_utc` | `raw_product_details` | TEXT | Yes | normalized, timezone-aware ISO 8601 UTC | From GraphQL `product.firstPublishedDate`. A future value MAY be stored for audit but is unavailable to metrics when after `scoring_cutoff_utc`. |
| `current_version_published_date_utc` | `raw_product_details` | TEXT | Yes | ISO 8601 UTC | Persisted for possible future use; NOT used for age/recency in the MVP (§10, ND-10) — do not confuse with `first_published_date_utc`. |
| `rating_average` | `raw_product_details` | REAL | Yes | `[0, 5]` | From GraphQL `product.rating.average`. Replaces Coveo's `ec_rating` as of v2.0.0. |
| `rating_count` | `raw_product_details` | INTEGER | Yes | ≥ 0 | From GraphQL `product.rating.count`. Not an eligibility condition or weight (§11, L-4). |
| `review_count` | `raw_product_details` | INTEGER | Yes | ≥ 0 | From GraphQL `product.reviewCount`. May differ from `rating_count`; not used in scoring. |
| `product_detail_status` / `page_views_status` | `raw_product_details` | TEXT | No | `'ok'`, `'error'` | Tracked independently per REQ-GQL-070; drives which fields `metrics` treats as usable. |
| `id_mapping_mismatch` | `raw_product_details` | INTEGER | No | `0`, `1` | Set when GraphQL's returned `id` differs from the requested `asset_identity_key` (REQ-GQL-110). A data-quality flag per OI-4, not itself a hard error. |
 | `state` | `raw_product_details` | TEXT | Yes | e.g. `"published"` | `"published"` is eligible for D/R/Q; null or missing is `state_unknown`; other values are `state_excluded`. State does not affect discovery-only C (REQ-GQL-120, DD-4). |
| `market_opportunity_score` | `category_scores` | REAL | Yes | `[0,1]` when non-null | Null iff `score_state = 'unavailable'`. |
| `missing_components_json` | `category_scores` | TEXT | No | JSON array, e.g. `[]`, `["Q"]`, `["D","R"]` | Replaces the enumerated fallback-state approach of `[REF-MATH]` with a direct list, per DD-2 (§6.6). |
 | `reference_size` | `category_scores` | INTEGER | No | ≥ 1 | Number of *other* categories in this run in this row's LOO reference (= N − 1), regardless of field-level missingness. Field-specific usable counts are stored in `reference_usable_counts_json`. |
| `rankable` | `category_scores` | INTEGER | No | 0 or 1 | See REQ-CNF-040. A rankable row still represents an offset-pagination collection for which point-in-time snapshot completeness is not guaranteed. |

---

## 6. Functional Requirements

### 6.1 Demand metric

- **REQ-MET-005 (NEW, revised in v2.2.0)**: An enrichment record is usable *for demand purposes* only if `product_detail_status = 'ok'`, `page_views_status = 'ok'`, `enrichment_identity_status = 'matched'`, and `state = "published"`. A null/missing state (`state_unknown`), every non-published state (`state_excluded`), and enrichment identity/operation failures are excluded from D/R/Q. State and enrichment-operation exclusions do not remove the asset from the discovered population or C; unresolved/conflicting discovery identities are not countable breadth and make C unavailable under REQ-MET-040.
- **REQ-MET-010 (revised in v2.2.0 — DD-3, age-normalized page-view index)**: For each asset satisfying REQ-MET-005, with a finite `product_page_views ≥ 0` and a usable timezone-aware `first_published_date_utc` normalized to UTC (non-null, parseable ISO 8601, ≤ `scoring_cutoff_utc`):
  ```text
  age_days_exact = (scoring_cutoff_utc - first_published_date_utc).total_seconds() / 86400
  age_days_floor = floor(age_days_exact)       [display/bucketing only]
  age_normalized_page_view_index = product_page_views * 7 / age_days_exact
                                     only if age_days_exact >= MIN_AGE_DAYS_FOR_RATE
  ```
  An asset with `age_days_exact < MIN_AGE_DAYS_FOR_RATE` (default `30`, Appendix C) SHALL be excluded before division — not coerced to 0 or to the raw count — because a very short age produces a noisy index. An asset with `product_page_views` or `first_published_date_utc` missing, non-finite, boolean, wrong-typed, `product_page_views < 0`, a naive timestamp, or a date after `scoring_cutoff_utc` SHALL likewise be excluded. An explicit `product_page_views = 0` with a usable, sufficiently-old publish date IS usable and yields an index of `0`. `age_days_exact = 0` SHALL never be used as a denominator.

  **DD-3 note (non-normative)**: this is an age-normalized index, not a genuine recent/rolling-window rate or validated lifetime average, because `[REF-API]`'s `productPageViews` field carries no documented window and Assumption A-3 remains subject to live validation. It may understate current interest for an asset whose traffic is growing and overstate it for one whose traffic has decayed since a past spike. This is recorded as **L-6** in §11.
- **REQ-MET-020**: Per category:
  ```text
  observed_asset_count      = count of distinct asset_identity_key observed in this category after dedup
   usable_view_count         = count of those with a usable age_normalized_page_view_index (REQ-MET-010)
  usable_view_coverage      = usable_view_count / observed_asset_count   (0 if observed_asset_count = 0)
   median_age_normalized_page_view_index = median(age_normalized_page_view_index over usable records; null if usable_view_count = 0)
   sum_page_view_indices_usable  = sum(age_normalized_page_view_index over usable records; 0 if usable_view_count = 0)
   page_view_index_per_observed_asset = sum_page_view_indices_usable / observed_asset_count   (0 if observed_asset_count = 0)
  ```
  `page_view_index_per_observed_asset` is deliberately defined over the full discovered population, not just the usable subset. An unavailable index contributes zero to the numerator while remaining in `observed_asset_count`; this is an aggregate zero-contribution policy, not persistence of a raw zero. `usable_view_coverage` separately expresses how much of the aggregate is backed by usable evidence, so the full denominator and subsequent coverage shrinkage intentionally impose a compounded conservative treatment on immature or incompletely enriched categories (DD-5, L-9).
- **REQ-MET-030**: Raw fields for normalization (no log transform, per §2.1 finding 1):
  ```text
   DemandPerAssetRaw = page_view_index_per_observed_asset
    DemandMedianRaw   = median_age_normalized_page_view_index
  ```

### 6.2 Competition (breadth) metric

This metric is unaffected by the v2.0.0 GraphQL enrichment stage: breadth is a discovery-only concept, computed purely from `raw_observations` (§2.1, item 4).

- **REQ-MET-040 (revised in v2.2.0)**: `observed_discovery_breadth` = count of distinct canonical `asset_identity_key` values returned for the category after dedup. A zero-result category (`totalCount = 0`, REQ-EXT-090) SHALL yield `observed_discovery_breadth = 0` only when the discovery filter is verified. State-excluded, state-unknown, and enrichment-failed assets remain part of the discovered population because C measures catalog breadth. Records with unresolved or conflicting identities are retained for audit but are not counted in breadth; any such record makes breadth a lower bound, sets `discovery_status = 'identity_incomplete'`, makes C unavailable, and makes the category non-rankable.
- **REQ-MET-050**: `BreadthRaw = observed_discovery_breadth` (no log transform).

### 6.3 Recent-supply metric

- **REQ-MET-060 (revised in v2.2.0)**: For each distinct asset in the published-eligible population — `product_detail_status = 'ok'`, `enrichment_identity_status = 'matched'`, `state = "published"` — with a usable timezone-aware `first_published_date_utc` normalized to UTC (non-null, parseable ISO 8601, ≤ `scoring_cutoff_utc`):
  ```text
   age_days_exact = (scoring_cutoff_utc - first_published_date_utc).total_seconds() / 86400
  ```
  A `first_published_date_utc` strictly after `scoring_cutoff_utc` SHALL be treated as unavailable and SHALL count toward `missing_date_coverage`, not toward `dated_asset_count`. This is the same underlying `first_published_date_utc` field used by REQ-MET-010; an implementation MAY compute `age_days_exact` once per asset and share it between the Demand and Recent-Supply metrics.
- **REQ-MET-070**:
  ```text
  dated_asset_count     = count of distinct assets with a usable first_published_date_utc
  dated_coverage        = dated_asset_count / observed_asset_count           (0 if observed_asset_count = 0)
   recent_share_365      = count(dated assets with 0 <= age_days_exact <= RECENT_WINDOW_DAYS) / dated_asset_count   (null if dated_asset_count = 0)
   median_age_days       = median(age_days_exact over dated assets)                                      (null if dated_asset_count = 0)
  RecentShareRaw        = recent_share_365
  MedianAgeRaw           = median_age_days      (no log transform)
  ```
  `RECENT_WINDOW_DAYS = 365` is inclusive and measured as an exact UTC duration (`age_days_exact <= 365` counts as recent).

### 6.4 Quality metric

- **REQ-MET-080 (revised in v2.2.0)**: An asset is *quality-eligible* iff it is in the published-eligible population, has a finite `rating_average` in `[0, 5]`, and has a usable age-normalized page-view index (REQ-MET-010). `rating_count` and `review_count` are NOT eligibility conditions and are NOT weights, per `[REF-MATH]`. (This is retained as a known inherited limitation — see §11, L-4.)
- **REQ-MET-090**:
  ```text
   quality_adjusted_visibility = sum((rating_average / 5) * age_normalized_page_view_index over eligible assets)
                                 / sum(age_normalized_page_view_index over eligible assets)
  ```
   Unavailable (null) if the eligible set is empty or the denominator is exactly 0 (i.e., all eligible assets have a zero index — no unweighted-rating fallback is used).
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
  A null target value SHALL yield a null percentile regardless of `m`. Ties SHALL receive the same midpoint value. If all usable reference values are equal and the target equals that common value, `P_ref(x) = 0.5`; a target below the common value receives `0`, and a target above it receives `1`.
- **REQ-NRM-035**: Field-specific reference counts SHALL be treated as distinct from `reference_size`. With small `m`, the midrank percentile is necessarily coarse; for example, `m = 1` permits only `0`, `0.5`, or `1`. The system SHALL describe these values as descriptive rank positions, not inferential percentiles or estimates.
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
- **REQ-SCR-020 (revised in v2.1.0)**: Using `b = P_ref(BreadthRaw)`:
  ```text
  C = clamp(1 - b, 0, 1)     if b is defined AND discovery_status = "complete" AND discovery_filter_verified = 1
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
 - **REQ-SCR-060 (DD-2)**: `missing_components_json` SHALL be the JSON array of component names (subset of `["D","C","R","Q"]`) not in `A`, replacing the enumerated fallback-state names of `[REF-MATH]` (`missing_demand`, etc.) with a direct, always-accurate list. This is a simplification, not a behavior change. Omitting unavailable components and renormalizing the available weights is an explicit design convention, not a mathematically unique treatment of missing components.

### 6.7 Confidence, coverage, and rankability

- **REQ-CNF-010 (revised in v2.1.0)**:
  ```text
  source_coverage(D) = usable_view_coverage
  source_coverage(C) = 1.0
  source_coverage(R) = dated_coverage
  source_coverage(Q) = quality_observation_coverage
  evidence_count_proxy = observed_asset_count * min(source_coverage(x) for x in A)   (0 if A is empty)
  ```
- **REQ-CNF-020 (revised in v2.1.0)**:
  ```text
  sample_factor      = clamp(evidence_count_proxy / 60, 0, 1)
  component_coverage = W_A                                        (sum of available top-level weights, REQ-SCR-050)
  M_D = min(m_DemandPerAssetRaw, m_DemandMedianRaw) when both demand subfields are used; otherwise the usable count of the one demand subfield used
  M_C = m_BreadthRaw
  M_R = min(m_RecentShareRaw, m_MedianAgeRaw) when both recent subfields are used; otherwise the usable count of the one recent subfield used
  M_Q = m_QualityRaw
  reference_factor = min(clamp(M_x / REFERENCE_FACTOR_DENOMINATOR, 0, 1) for each available component x)
  confidence_heuristic = clamp(0.50*sample_factor + 0.30*component_coverage + 0.20*reference_factor, 0, 1)
  ```
  `m_<field>` is the count of usable, non-null reference values for that normalized field and SHALL be persisted in `reference_usable_counts_json`. `reference_size` remains the total number of other categories and SHALL NOT substitute for these field-specific counts. `confidence_heuristic` is an evidence-completeness heuristic, not a probability, confidence interval, standard error, or estimate of score correctness. **REQ-CNF-025**: it SHALL NOT be multiplied into `market_opportunity_score` at any point.
- **REQ-CNF-030**:
  ```text
  coverage_status = "insufficient_data"   if score_state = "unavailable" OR observed_asset_count < 10
                   = "partial"             elif score_state = "partial" OR evidence_count_proxy < 60
                   = "full"                 otherwise
  ```
- **REQ-CNF-040 (revised in v2.2.0)**: `rankable = 1` iff ALL of: `score_state = "available"`; `coverage_status = "full"`; `reference_size >= MIN_CATEGORIES_FOR_RANKABILITY - 1`; for every available component `x`, its field-specific support count `M_x >= REFERENCE_FACTOR_DENOMINATOR`; `discovery_status = "complete"`; `discovery_filter_verified = 1`; `discovery_failed_page_count = 0`; `discovery_category_mismatch_count = 0`; and `discovery_unresolved_identity_count = 0`. Otherwise `rankable = 0`. Numeric scores may still be computed for smaller or incomplete runs, but they are provisional/non-rankable. `confidence_heuristic` remains continuous evidence information and does not replace this gate.

### 6.8 Persistence of results

- **REQ-PER-010**: The pipeline SHALL write exactly one `category_scores` row per category per run, using `INSERT` (never `UPDATE`) — a re-run SHALL use a new `run_id`, preserving prior runs for comparison.
- **REQ-PER-020**: All raw discovery and raw enrichment rows for a run SHALL be retained (not deleted) after scoring, to allow re-scoring from persisted raw data without re-extraction.

### 6.9 Dashboard

- **REQ-DSH-020**: The dashboard SHALL present a sortable, filterable table with one row per category (default: most recent `run_id`), showing at minimum: `category`, `market_opportunity_score`, `component_d`, `component_c`, `component_r`, `component_q`, `confidence_heuristic`, `coverage_status`, `rankable`, `observed_asset_count`, and `discovery_status`.
- **REQ-DSH-030**: Numeric display values SHALL be rounded to 3 decimal places for display only; underlying stored precision is unaffected (REQ-NRM-050).
- **REQ-DSH-040**: The dashboard SHALL provide a bar chart of `market_opportunity_score` across all categories in the selected run, and, on selecting a single category, a small chart of its four component values.
- **REQ-DSH-050**: A run selector SHALL allow choosing among previously completed runs (by `run_id`/`created_at_utc`). The dashboard SHALL NOT allow editing persisted data.
- **REQ-DSH-060**: Non-rankable rows (`rankable = 0`) SHALL be visually distinguished (e.g., a badge or muted row style) rather than hidden, so the operator can still see their score/coverage context.
- **REQ-DSH-070 (NEW)**: The dashboard SHALL label `market_opportunity_score` as a deterministic within-run heuristic. It SHALL state that component weights have not been calibrated against sales, downloads, revenue, or another external outcome, and SHALL distinguish the age-normalized page-view index from a validated weekly traffic rate.

### 6.10 CLI / orchestration

- **REQ-CLI-010**: `niche-scout run --categories config/categories.json --config config/default.toml` SHALL execute the full pipeline (§3.2) in one process and exit non-zero on any unrecoverable error.
- **REQ-CLI-020**: `niche-scout dashboard` SHALL launch the dashboard against the existing SQLite database without re-running discovery or enrichment.
- **REQ-CLI-030**: All constants marked configurable in Appendix C SHALL be overridable via `config/default.toml`, with CLI flags taking precedence over the TOML file, which takes precedence over hard-coded defaults. Constants marked non-configurable SHALL remain fixed.

---

## 7. Non-Functional Requirements

- **REQ-NFR-010 (Performance)**: The system SHALL handle at least 50 categories with up to 2,000 assets each in a single run on a typical consumer laptop without exceeding available memory, by streaming persistence (writing raw discovery observations as pages arrive rather than buffering an entire run in memory).
- **REQ-NFR-015 (NEW — Performance/Feasibility)**: Because enrichment requires one GraphQL batch request per uniquely discovered asset (REQ-GQL-055), total run time scales with the number of *unique assets discovered*, not the number of categories or pages — a materially different cost profile from discovery-only v1.0.0. Before beginning enrichment, the system SHALL log the count of unique assets to enrich and a projected minimum completion time computed from `GRAPHQL_MIN_REQUEST_INTERVAL_SECONDS`, so the operator is not surprised by a run that runs far longer than discovery alone would suggest (§11, L-7).
- **REQ-NFR-020 (Reliability)**: A network failure on any single category's discovery, or any single asset's enrichment, SHALL NOT abort the run for other categories or assets; the failed item SHALL be marked and reported, and scoring SHALL proceed for all successfully processed categories using whatever enrichment data is available (REQ-MET-005).
- **REQ-NFR-030 (Maintainability)**: All public functions in `metrics` and `scoring` SHALL have type hints and a docstring stating inputs, outputs, and null/edge-case behavior. See §8.3 for enforced tooling.
- **REQ-NFR-040 (Security)**: No secret (Coveo bearer token, Unity storefront CSRF token/cookie) SHALL appear in source control, logs, or the SQLite database. `.env` files SHALL be listed in `.gitignore`.
- **REQ-NFR-050 (Portability)**: The system SHALL run unmodified on Windows, macOS, and Linux under Python 3.11+, using only cross-platform-safe file path handling (`pathlib`).
- **REQ-NFR-060 (Usability)**: A first-time operator SHALL be able to go from a cloned repository to a rendered dashboard using only the steps documented in `README.md`, with no undocumented manual step, including obtaining and setting both required credentials (Coveo bearer token, Unity storefront CSRF token).

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
│       │   ├── coveo_client.py         # discovery
│       │   ├── graphql_client.py       # enrichment (NEW in v2.0.0)
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
│   │   ├── test_confidence.py
│   │   ├── test_dedup.py               # NEW in v2.0.0
│   │   └── test_graphql_client.py      # NEW in v2.0.0
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
| Python modules/files | `snake_case.py` | `graphql_client.py` |
| Classes | `PascalCase` | `CategoryMetricBundle` |
| Functions/variables | `snake_case` | `compute_demand_component` |
| Constants | `UPPER_SNAKE_CASE` | `MIN_CATEGORIES_PER_RUN` |
| Test files | `test_<module>.py` | `test_demand.py` |
| Test functions | `test_<behavior>__<condition>` | `test_demand_component__zero_views_is_valid` |
| SQLite tables | plural `snake_case` | `category_scores`, `raw_product_details` |
| SQLite columns | `snake_case`, `_utc` suffix for timestamps, `_id` suffix for identifiers | `created_at_utc`, `run_id` |
| Environment variables | `NICHESCOUT_UPPER_SNAKE_CASE` | `NICHESCOUT_COVEO_BEARER_TOKEN`, `NICHESCOUT_UNITY_CSRF_TOKEN` |
| Config (TOML) keys | `snake_case` | `min_request_interval_seconds` |
| Git branches | `type/short-description` | `feat/graphql-enrichment` |
| Commit messages | Conventional Commits | `feat(extraction): add graphql enrichment client` |

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
- **REQ-TST-020 (revised in v2.2.0)**: A golden-vector test suite (`tests/golden/test_golden_vectors.py`) SHALL fix a synthetic reference set and target values, hand-compute the expected `D`, `C`, `R`, `Q`, composite score, evidence-count proxy, field-specific reference factor, confidence heuristic, and rankability decision, and assert exact (within float tolerance `1e-9`) agreement — mirroring the worked-example discipline of `[REF-AUDIT]`. It SHALL include all-equal reference values with target below, equal to, and above the common value, plus a partial missing-component vector that documents the chosen renormalization behavior.
- **REQ-TST-030**: `tests/architecture/test_purity_boundary.py` SHALL statically assert that `niche_scout.metrics` and `niche_scout.scoring` import nothing from `niche_scout.extraction`, `niche_scout.persistence`, or `niche_scout.dashboard` (REQ-GEN-040).
- **REQ-TST-040**: Minimum line coverage for `metrics` and `scoring` packages SHALL be 95%, enforced in CI.
- **REQ-TST-050 (NEW)**: `tests/unit/test_dedup.py` SHALL verify that when the same `asset_identity_key` is discovered under two or more categories in one run, exactly one GraphQL enrichment call is made for it (REQ-GQL-055), and that the resulting `raw_product_details` row is correctly joined to every referencing category during metrics computation.
- **REQ-TST-060 (revised in v2.2.0)**: `tests/unit/test_graphql_client.py` SHALL cover: a batch response with both operations succeeding; reversed or ambiguous response ordering; wrong operation/data shape; `product = null`; `productPageViews = null`; wrong scalar types; negative/non-finite page views; a response where exactly one operation's item contains `errors`; canonical URI identity extraction; malformed high-priority candidate with valid fallback; conflicting canonical candidates; an `id_mapping_mismatch` case that excludes the asset from D/R/Q; `product.state = "published"`, a non-published state, null/missing state, and state exclusion from D/R/Q but not C; HTTP 404/409/422 permanent-error handling; and the `400 csrf token mismatch` / `401` / `403` non-retry-abort path.
- **REQ-TST-070 (revised in v2.2.0)**: `tests/unit/test_demand.py` SHALL include: exact-age calculation without floor bias; age 29 days 23 hours excluded; exactly `MIN_AGE_DAYS_FOR_RATE` included; age 30 days and 1 second using the fractional denominator; an asset younger than one day excluded without division by zero; explicit zero page views; future and naive timestamps excluded; exact recent-window boundaries at 365 days and 365 days plus one second; and scoring against `scoring_cutoff_utc` rather than run start.
- **REQ-TST-080 (revised in v2.2.0)**: Discovery tests SHALL cover natural pagination completion, `totalCount` reconciliation, offset-pagination best-effort metadata, duplicate observations, maximum-result truncation, a failed middle page, exact category-path matching, parent/child path non-matching, verified and unverified zero-result responses, taxonomy category absence, malformed fallback identities, conflicting identities, unresolved identity counts, and the requirement that incomplete discovery makes C unavailable and rankable false.
- **REQ-TST-090 (revised in v2.2.0)**: Confidence tests SHALL cover a large `reference_size` with only two usable reference values, field-specific usable reference counts, required-component support below and at `REFERENCE_FACTOR_DENOMINATOR`, two-category runs, 20-category runs, and the 21-category rankability boundary.
- **REQ-TST-100 (NEW)**: Overlap tests SHALL verify that an asset discovered under multiple categories is enriched once, joined to each referencing category, and documented as creating category-level dependence rather than independent observations.
- **REQ-TST-110 (NEW)**: Date and taxonomy tests SHALL verify timezone-aware UTC normalization, rejection of naive timestamps, Unicode `casefold()` normalization, taxonomy-membership validation for punctuation/non-ASCII category names, and preservation of canonical taxonomy spelling.

---

## 10. MVP Non-Goals (Explicitly Deferred)

- **ND-1**: Stability analysis (nested-prefix / independent-policy sensitivity testing) is not implemented. Not needed for MVP correctness; may be added post-MVP as an optional report.
- **ND-2**: No override/provisional workflow. A category either has enough evidence to compute components or it does not; there is no mechanism to force a numeric score past a failed eligibility check.
- **ND-3**: No cross-run provenance-compatibility gates (policy version, collection-mode matching, sort verification) are implemented. Same-run collection policy and timestamps are recorded, but LOO does not eliminate shared-asset or other category-level dependence (§2.1, L-8).
- **ND-4**: No automated Coveo bearer token acquisition/refresh; operator-supplied only.
- **ND-5**: No authentication, multi-user support, or remote/cloud deployment for the dashboard.
- **ND-6**: No multi-run historical trend view in the dashboard beyond selecting a single prior run (REQ-DSH-050).
- **ND-7**: No automatic re-scoring on a schedule; the CLI is invoked manually.
- **ND-8 (NEW)**: No automated acquisition or refresh of the Unity storefront CSRF token/session; operator-supplied only (mirrors ND-4).
- **ND-9 (NEW)**: No collection of `favorite_count` / `packageInListHotness` (§2.6, OI-5); the field is undocumented, unvalidated across products, and not returned by the required `ProductDetail`/`ProductPageViews` batch.
- **ND-10 (NEW)**: `currentVersion.*`, `description`, `publishNotes`, `supportedUnityVersions`, `downloadSize`, `assetCount`, `publisher.url`/`supportUrl`/`supportEmail`, `originalPrice.*`, and `category.*` (GraphQL) are persisted (REQ-GQL-050, §5.1) for possible future dashboard display or analysis, but are NOT used by any scoring formula in the MVP.
- **ND-11 (NEW)**: The MVP does not automatically compare `product_page_views` across ordinary runs. The separate A-3 validation study may mark the run-level semantic status `contradicted` when its controlled repeated observations show a decrease; no general historical alerting or repair workflow is implemented.
- **ND-12 (NEW)**: No resume/checkpoint CLI mechanism for an interrupted enrichment stage (§11, L-7); a new run always starts enrichment from zero, even though a prior run's completed `raw_product_details` rows are retained (REQ-PER-020).

---

## 11. Known Inherited Limitations (Not Fixed in MVP)

These were identified as real methodological concerns in the prior review, or introduced by the v2.0.0 GraphQL-enrichment redesign, but are consciously **not** further redesigned in this MVP, to keep it minimal. They are documented so they are not mistaken for oversights.

- **L-1 (compensatory aggregation)**: The composite score is a weighted sum, so a very strong component can offset a very weak one. A category with excellent demand but saturated competition can score similarly to a mediocre, balanced category. No interaction/multiplicative term is implemented.
- **L-2 (fixed, non-empirical weights)**: All weights (`0.35/0.30/0.20/0.15`, `0.60/0.40`, `0.70/0.30`, `0.50/0.30/0.20`) are carried over as fixed constants with no empirical derivation or sensitivity analysis in the MVP.
- **L-3 (per-run reference, not cross-time)**: DD-1 resolves "no category excluded" but means scores are only comparable within one run's category set; comparing a score from one run to a score from a differently-scoped run is not meaningful.
- **L-8 (NEW — category overlap and dependence)**: Categories may share assets, publishers, or taxonomy ancestry. LOO excludes the target category's aggregate row from its reference set but does not produce independent observations. Scores are descriptive within-run relative comparisons, not inferential estimates based on independent samples.
- **L-4 (rating reliability not modeled)**: `quality_adjusted_visibility` weights `rating_average` (from GraphQL as of v2.0.0) by traffic, not by the number of reviews behind the rating; a high-traffic asset with one review counts as strongly as one with a thousand.
- **L-5 (outlier concentration)**: `page_view_index_per_observed_asset` and `quality_adjusted_visibility` are both susceptible to domination by a single high-traffic asset within a category; no winsorization or cap is applied.
- **L-6 (NEW — undocumented page-view semantics)**: `age_normalized_page_view_index` (§6.1, DD-3) is derived from an undocumented `product_page_views` field divided by exact asset age. The cumulative interpretation remains Assumption A-3 and requires live validation. If the counter is rolling, reset, delayed, or begins after publication, the index does not represent a lifetime-average weekly rate. Even if cumulative, it may understate current interest for growing assets and overstate it for assets whose traffic has decayed since a past spike. No windowed or decayed alternative is implemented in the MVP.
- **L-9 (NEW — conservative treatment of immature assets)**: Categories with many assets younger than `MIN_AGE_DAYS_FOR_RATE` receive both a lower full-population demand mean because those assets remain in the denominator and coverage-based shrinkage of D toward 0.5. This compounded conservative treatment is deliberate in the MVP and may disadvantage categories with rapidly growing catalogs.
- **L-10 (NEW — recent share is composition, not flow)**: `RecentShareRaw` measures the proportion of the dated catalog published within the recent window. It is not an asset-arrival rate, sales rate, or catalog-growth velocity; categories with different catalog sizes can have the same recent share.
- **L-11 (NEW — collection-window snapshot)**: Discovery and enrichment occur at different times. The run is an approximate collection-window snapshot, not a perfect point-in-time snapshot; `run_started_at_utc`, per-record retrieval timestamps, and `scoring_cutoff_utc` are retained for provenance.
- **L-7 (NEW — enrichment cost scales with unique assets, not categories)**: Unlike the Coveo-only design in v1.0.0, every additional uniquely discovered asset costs one additional GraphQL round trip (REQ-GQL-055). A broad, high-volume category set can make a single run take hours (REQ-NFR-015). No resume/checkpoint mechanism is implemented (ND-12); a failed or interrupted run's completed `raw_product_details` rows remain in the database (REQ-PER-020), but there is no CLI-level way to resume a specific `run_id` — a new run starts enrichment from zero. Operators running large category sets SHOULD start with a conservative `MAX_RESULTS_PER_CATEGORY` (Appendix C) to bound the unique-asset count.

---
```text
age_days_exact = (scoring_cutoff_utc - first_published_date_utc).total_seconds() / 86400
age_days_floor = floor(age_days_exact)                 [display/bucketing only]
age_normalized_page_view_index = product_page_views * 7 / age_days_exact
                                 [only if age_days_exact >= MIN_AGE_DAYS_FOR_RATE]
DemandPerAssetRaw         = page_view_index_per_observed_asset
DemandMedianRaw           = median_age_normalized_page_view_index
BreadthRaw                = observed_discovery_breadth
RecentShareRaw             = recent_share_365
MedianAgeRaw              = median_age_days
QualityRaw                = quality_adjusted_visibility

P_ref(x) = (L + 0.5*E) / m         [midrank percentile vs. LOO reference, REQ-NRM-030]

D0 = weighted-available-mean(P_ref(DemandPerAssetRaw)*0.60, P_ref(DemandMedianRaw)*0.40)
D  = clamp(0.5 + usable_view_coverage*(D0-0.5), 0, 1)

C  = clamp(1 - P_ref(BreadthRaw), 0, 1)
     [only if discovery_status = "complete" and discovery_filter_verified = 1
      and discovery_unresolved_identity_count = 0]

Rpressure0 = weighted-available-mean(P_ref(RecentShareRaw)*0.70, (1-P_ref(MedianAgeRaw))*0.30)
R0 = 1 - Rpressure0
R  = clamp(0.5 + dated_coverage*(R0-0.5), 0, 1)

Q0 = 1 - P_ref(QualityRaw)
Q  = clamp(0.5 + quality_observation_coverage*(Q0-0.5), 0, 1)

S_available = sum(w_x * x for x in available) / W_A
market_opportunity_score = clamp(0.5 + W_A*(S_available-0.5), 0, 1)

evidence_count_proxy = observed_asset_count * min(source_coverage(x) for x in available)
reference_factor = min(clamp(M_x / REFERENCE_FACTOR_DENOMINATOR, 0, 1) for each available component x)
confidence_heuristic = clamp(0.50*clamp(evidence_count_proxy/60,0,1) + 0.30*W_A + 0.20*reference_factor, 0, 1)
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
| `COVEO_MIN_REQUEST_INTERVAL_SECONDS` | 1.0 | Yes | REQ-EXT-100 |
| `MAX_RETRIES` | 5 | Yes | REQ-EXT-100, REQ-GQL-080 (shared) |
| `RETRY_BACKOFF_BASE_SECONDS` | 2.0 | Yes | REQ-EXT-100, REQ-GQL-080 (shared) |
| `MIN_CATEGORIES_PER_RUN` | 2 | No | REQ-CAT-040 |
| `MIN_CATEGORIES_FOR_RANKABILITY` | 21 | No | REQ-CAT-040, REQ-CNF-040 |
| `MAX_TAXONOMY_AGE_DAYS` | 30 | Yes | REQ-EXT-020 |
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
| `CURRENCY` | EUR | Yes | §4.1 (Coveo `dictionaryFieldContext` replay fidelity only; not used in scoring as of v2.0.0, since `ec_price` is no longer requested — REQ-EXT-040) |
| `LOCALE` | en-US | Yes | §4.1 |
| `TIMEZONE` | UTC (A-1) | Yes | §4.1 |
| `GRAPHQL_ENDPOINT_URL` | fixed, §4.2 | No | REQ-GQL-010 |
| `GRAPHQL_MIN_REQUEST_INTERVAL_SECONDS` | 0.5 | Yes | REQ-GQL-080 |
| `MIN_AGE_DAYS_FOR_RATE` | 30 | Yes | REQ-MET-010 |
| `NICHESCOUT_COVEO_BEARER_TOKEN` (env var) | operator-supplied | — | REQ-EXT-030 |
| `NICHESCOUT_UNITY_CSRF_TOKEN` (env var) | operator-supplied | — | REQ-GQL-040 |

---

## Appendix D — Requirements Traceability Matrix

| Requirement range | Module |
|---|---|
| `REQ-EXT-010–100` | `extraction/coveo_client.py`, `extraction/validation.py`; pagination and snapshot metadata are persisted by `pipeline.py` / `persistence/db.py` |
| REQ-GQL-010–120 | `extraction/graphql_client.py`, `extraction/validation.py`; dedup orchestration (REQ-GQL-055) lives in `pipeline.py` |
| REQ-CAT-010–040 | `cli.py`, `config.py` |
| `REQ-MET-005–090` | `metrics/demand.py`, `metrics/competition.py`, `metrics/recent_supply.py`, `metrics/quality.py`; exact UTC timestamp normalization is enforced in `extraction/validation.py` |
| `REQ-NRM-010–050` | `scoring/normalization.py` |
| REQ-SCR-010–060 | `scoring/components.py`, `scoring/composite.py` |
| `REQ-CNF-010–040` | `scoring/confidence.py` |
| `REQ-PER-010–020` | `persistence/db.py` |
| `REQ-DSH-010–070` | `dashboard/app.py` |
| REQ-CLI-010–030 | `cli.py`, `pipeline.py` |
| `REQ-NFR-010–100` | cross-cutting; enforced via CI config + `pyproject.toml` |
| `REQ-TST-010–110` | `tests/` |
