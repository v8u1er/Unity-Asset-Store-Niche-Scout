# Niche Scout — Evidence-Based Technical Analysis Report

**Repository:** `Unity Asset Store Niche Scout` · **HEAD:** `eff5768` ("archify: niche-scout architecture diagram + gate receipts") · **Working tree:** clean at time of analysis · **Analyzed:** 2026-10-03

**Verification performed by this analysis (real command output):**

| Command | Result |
|---|---|
| `python -m niche_scout.tools.validate_traceability` | `Traceability valid: 89 required/defined LREQ IDs mapped, 745 matrix nodes, 0 unmarked analytical tests outside exemption (3 exempted non-analytical nodes)` |
| `python -m niche_scout.tools.check_import_boundaries` | `Import boundaries valid for metrics.py, scoring.py` |
| `python -m niche_scout.tools.check_scope_prohibitions` | `Scope prohibitions valid: no retired token found ... (6 tokens checked)` |
| `python -m niche_scout.tools.check_secrets` | `Secret check valid: no literal credential found ...; .gitignore ignores .env and no tracked .env exists` |
| `python -m pytest -q -p no:cacheprovider` | `766 passed, 37 warnings in 30.72s` |

Labels used throughout: **[observed]** = read directly in source/tests; **[counted]** = produced by a query, method named; **[inferred]** = my interpretation; **[unverified]** = not checked.

---

## 1. Executive Summary

**What it is.** Niche Scout is a local, single-user Python CLI that ranks a small, user-selected set of Unity Asset Store categories by a fixed, transparent, sample-based heuristic. Its advertised output is "a sample-based, deterministic, within-run market-opportunity heuristic", explicitly **not** a sales/revenue/download/demand predictor (`README.md:3-6`; `Documents/SRS-lean-v2.md:60-65`; `cli.py:209-214`).

**User.** A Unity Asset Store publisher/artist shortlisting categories for further investigation — not a quantitative analyst (`SRS-lean-v2.md:87-88`).

**Inputs.** A JSON list of category paths (`config/categories.json`, 24 paths committed), a TOML config (`config/default.toml`), a captured Coveo taxonomy (`config/category_taxonomy.json`), a captured Coveo request template (`config/coveo_search_template.json`), and two environment credentials (`NICHESCOUT_COVEO_BEARER_TOKEN`, `NICHESCOUT_UNITY_CSRF_TOKEN`).

**Stages (all [observed]):** CLI parse → config resolution → credential read → taxonomy validation → Coveo discovery (paginated, streamed to SQLite) → canonical-population construction → deterministic 4-stratum sampling (census ≤100) → identity preflight gate → unique-identity GraphQL enrichment → scoring cutoff capture → pure metric estimators → leave-one-out normalization → D/C/R/Q components → composite score → base-rankable candidate freeze → 3-policy sensitivity → final evidence/rankability → SQLite persistence → HTML/text report and/or a read-only Dash/Plotly dashboard.

**Key architectural idea.** A hard *purity boundary*: `metrics.py` and `scoring.py` are pure (no I/O, no clock, no network, no DB) and consume plain typed inputs; all network/disk/orchestration live in `collector_coveo.py`, `collector_graphql.py`, `database.py`, `pipeline.py`, `report.py`, `cli.py`. The boundary is machine-enforced by `tools/check_import_boundaries.py` (an AST checker) and by `tools/check_scope_prohibitions.py`; I re-ran both and they pass.

**Deliberately not predicted:** sales, revenue, downloads, conversion, causal demand, traffic, customer intent, publisher margin, future category growth (`SRS-lean-v2.md:169-176`, §15, §16; `report.py:305-320`).

---

## 2. What the Project Does

**Product behavior [observed]:**
- `niche-scout run` discovers each requested category through the Unity Coveo search endpoint, streams every raw observation to SQLite, samples deterministically, enriches unique sampled assets through the Unity GraphQL batch endpoint, computes fixed metrics and a composite score, runs a ranking-sensitivity diagnostic, and persists one result row per category (`cli.py:371-478`, `pipeline.py:3253-3576`).
- `niche-scout dashboard [--run-id]` opens the SQLite DB, loads one run's report view, and serves a read-only Dash app on loopback `127.0.0.1:8050` (`cli.py:481-568`, `report.py:2662-2690`).
- `run --report PATH --report-format html|text` writes a self-contained HTML or plain-text report (`report.py:2803-2828`).

**Scope limits [observed in SRS §1.3 and enforced by code]:**
- A run with **fewer than 8 requested categories is rejected before ranking** (`pipeline.py:3284-3290`, constant `MIN_CATEGORIES_PER_RUN = 8` at `models.py:35`).
- Runs of **8–20 categories are provisional** and can never be labeled `rankable`; **21 categories** is the "strong reference" boundary (`SRS-lean-v2.md:1030-1067`; `scoring.py:1032-1033`, `1608`).
- Out of scope: scheduling, resume/checkpoint, historical trends, cross-run comparison, full-category enrichment, alternative collection strategies, configurable weights, favorite-count, extra GraphQL fields, multi-user/cloud, automated credential acquisition, sales calibration (`SRS-lean-v2.md:118-128, 1365-1389`).

**Corrections to the prompt's framing:**
1. The prompt says discovery "pulls category listings". The code does *facet-filtered product discovery*: it POSTs to Coveo search with an `ec_category` facet whose `currentValue` equals the requested category, and it **explicitly forbids free-text `q`/`query`** at any nesting depth (`collector_coveo.py:630-779`). So it is category-scoped asset listing, not category-listing retrieval.
2. The prompt lists "freshness" as a metric. There is no metric named "freshness"; the recency signal is `RecentShareRaw`/`MedianAgeRaw` inside the **Recent supply (`R`)** component (`metrics.py:1423-1514`).
3. The prompt calls the dashboard invocation `niche-scout dashboard --run-id`. That is accurate, but `--run-id` is **optional** and defaults to the most recent run (`cli.py:243-249`, `546-554`).
4. The prompt says the tool "uses credentials-only access". Verified: both credentials are read only from environment variables (`config.py:280-292`) and required before collection (`config.py:109-115`).

---

## 3. Repository & Architecture Map

**Top-level layout [observed]:** `pyproject.toml`, `README.md`, `config/`, `src/niche_scout/`, `tests/`, `Documents/` (SRS, plans, interfaces, runs), `.archify/` (generated diagram), `runtime/` (SQLite DBs and report outputs), `.env.example`.

**Package modules and responsibilities [observed]:**

| Module | Role | Purity |
|---|---|---|
| `models.py` | Typed domain records (5 SRS tables), enums, frozen constants, policy versions, JSON serialization | Pure |
| `config.py` | Config precedence CLI > TOML > defaults; category file read; env credential read | I/O at boundary |
| `validation.py` | Taxonomy, identity canonicalization, response shape, state annotation, redaction | Pure primitives |
| `sampling.py` | Canonical population, systematic strata, SHA-256 selection, overlap | Pure |
| `metrics.py` | Metric eligibility primitives + six sample-aware raw estimators | Pure |
| `scoring.py` | LOO reference, midrank normalization, D/C/R/Q, composite, evidence, sensitivity | Pure |
| `collector_coveo.py` | Coveo request build, HTTP fetch/retry/rate-limit, streamed persistence, terminal status | Network + disk |
| `collector_graphql.py` | Two-operation GraphQL batch build, correlation, validation, retry, draft records | Network |
| `collector.py` | Re-exporting facade over the two collectors (`collector.py:1-54`) | Facade |
| `database.py` | SQLite DDL, `SqliteRepository`, transactions/savepoints, read surface | Disk |
| `pipeline.py` | Run orchestration: preflight, enrichment union, finalization, scoring wiring | Orchestration |
| `report.py` | Read model + HTML/text renderers + Dash app | Disk read + render |
| `cli.py` | argparse, dispatch, exit codes, transports | Process I/O |
| `tools/` | Traceability, import-boundary, scope-prohibition, secret checks, quality workflow | Tooling |

**Dependency direction [observed]:** `cli → {config, database, pipeline, report}`; `pipeline → {collector_coveo, collector_graphql, config, database, metrics, models, sampling, validation, scoring}`; `database → {models, sampling}`; `report → {database, models}`; `metrics → {models, validation}`; `scoring → {metrics, models}`. The pure modules (`metrics`, `scoring`) import only `models` and `validation`; `validation` imports only `models`. This is enforced, not merely intended: `check_import_boundaries.py:20-56` forbids `metrics.py`/`scoring.py` from importing `collector*`, `database`, `pipeline`, `report`, `cli`, `config`, `os`, `io`, `sys`, `pathlib`, `sqlite3`, `urllib`, `json`, `time`, `logging`, etc.

**Data flow [observed]:** persisted discovery → canonical population → sample → preflight → unique enrichment → cutoff → metrics → normalize → score → base candidates → sensitivity → final evidence → persist → render. This matches the SRS runtime order (`SRS-lean-v2.md:357-361`) and is implemented sequentially in `run_pipeline` (`pipeline.py:3355-3553`).

**Purity/side-effect boundaries [observed]:** the only clock reads are in I/O modules via injected seams (`cli._utcnow` at `cli.py:366-368`, `collector_coveo._default_clock` at `collector_coveo.py:1547`, and default `time.sleep`); the pipeline takes `clock`, `coveo_transport`, `graphql_transport`, and `sleeper` as parameters (`pipeline.py:3253-3272`).

**Architecture caveat [observed]:** `pipeline.py` is 3,576 lines and imports from `collector_coveo` (including a private `_failure_cause_json`), `collector_graphql`, `database`, `metrics`, `scoring`, `sampling`, and `validation`. It is a monolith. The architecture rule file lists it as an orchestration-only module, and it *is* the sole orchestration module — but it concentrates several chunks' worth of logic (preflight, union, finalization, warning assembly, row building, run loop) in one file. No line-count rule is violated (`.kilo/project-rules.md` "File size and concern boundaries" says no line count is a violation), but this is a real structural signal.

---

## 4. Archify Architecture vs. Implemented Architecture

**Archify artifact location [observed]:** `.archify/architecture-niche-scout-20261003-091932/` containing `candidate.json` (the spec), `niche-scout.html` (the rendered diagram, 793,354 bytes), and gate receipts. The `delivery.json` records `status: current`, artifact sha256 `f13835…ebd53`; the `finalize-summary.json` records all four gates (`validate`, `deliver`, `check`, `browser-check`) as `pass` with `diagnosticSummary.total = 0`. The `candidate.json` meta records repository revision `603c429481f4dd3ad8d47ca4d10282a0c119f4cc` — which is **one commit behind HEAD** (`eff5768`), so the diagram was generated from the working tree before the commit that added it.

**Correct relationships [observed in `candidate.json`]:**
- Components `cli`, `config`, `credentials`, `pipeline`, `coveo` (`collector_coveo.py`), `graphql` (`collector_graphql.py`), `validation`, `sampling`, `database`, `metrics`, `scoring`, `report`, plus external `coveo_api`, `graphql_api`, `html_report`, `dashboard`.
- Edges that match the source: `cli→config` (`load_config`), `cli→pipeline` (`run_pipeline()` once), `pipeline→coveo` (`discover_category`), `coveo→database` (discovery rows), `pipeline→sampling` (`select_run_sample`), `sampling→database` (`persist_run_sampling`), `pipeline→graphql` (preflight + enrichment), `pipeline→metrics` (`CategoryMetricInput`), `metrics→scoring` (raw metrics), `validation→metrics` (`annotate_state_eligibility`), `scoring→pipeline` (ranked score rows), `pipeline→database`, `cli→report`, `database→report`, `report→html_report`, `report→dashboard`. All verified against the import graph.
- Source citations in `candidate.json` point to real line ranges (e.g. `pipeline.py:3253-3576`, `collector_coveo.py:928-1098`, `scoring.py:636-696`, `report.py:681-724`).

**Simplifications / omissions [observed]:**
- `collector.py` (the facade) is **absent** from the diagram. That is defensible (it is a re-export shim) but it means the diagram omits one real module boundary.
- The diagram's security-group boundary wraps only `coveo` and `graphql`; it does not represent the credential flow into `build_coveo_headers`/`build_graphql_headers` or the redaction guarantees.
- The diagram does not show the `tools/` quality gates, the `models.py` frozen constants, or the fixture layer, though the "Reporting & gates" card mentions `tools/`.
- The card text "Deterministic parallelism-by-stride strata selection" is slightly imprecise: the strata are **sequential** interleaved ordinal partitions (`stratum_index(i) = (i-1+offset) mod stride`), not parallel execution (`sampling.py:393-499`).

**Correctness verdict:** the Archify map is **materially accurate** at component-and-edge level; its simplifications are editorial, not factual. The one factual drift I found is the "parallelism" wording. The revision-pin drift (one commit) is recorded above.

---

## 5. End-to-End Execution Flow

Trace of `niche-scout run` [observed, `cli.run_command` → `pipeline.run_pipeline`]:

1. **Command parsing** — `cli.build_parser()` defines `run` and `dashboard` subparsers; `--categories`, `--config`, `--report`, `--report-format`, and one override flag per SRS-configurable setting (`cli.py:198-251`).
2. **Config resolution** — `config.load_config(cli_args, toml_path)` merges with precedence CLI > TOML > in-code defaults, rejects unknown keys, and pins `page_size` to 96 (`config.py:194-256`).
3. **Category read + credential read** — `config.read_categories` and `config.get_credentials(environ)` run before any transport (`cli.py:410-416`). Missing credentials → `EXIT_USAGE_ERROR`.
4. **Run-row creation** — `run_pipeline` validates ≥8 categories, validates taxonomy freshness, computes `taxonomy_sha256`, inserts a `runs` row with `status=running`, policy versions, and a seeded preflight summary (`pipeline.py:3284-3359`).
5. **Discovery** — `_discover_all` loops categories, each in its own `category_transaction`; `discover_category` validates taxonomy and credentials before the first request, loads and hash-checks the template, paginates, and streams each page to `CoveoObservationSink.write_page` (`pipeline.py:2901-2966`, `collector_coveo.py:1895-2207`).
6. **Canonical population** — persisted observations are projected to `DiscoveryPopulationRecord`s and `select_run_sample` builds ordered, deduplicated populations and selects members (`pipeline.py:3376-3390`, `sampling.py:307-658`).
7. **Sampling persistence** — `persist_run_sampling` writes `sample_members` and per-category summaries with pending usable-count placeholders (`database.py:2195-2272`).
8. **Identity preflight** — `run_identity_preflight` selects a deterministic set, issues one `enrich_asset` call per unique identity, computes unique-identity rates, evaluates the gate, and persists status/summary/observations **before returning** (`pipeline.py:1088-1209`).
9. **Gate** — if not `passed`, the run is marked `failed` and null-score limitation rows are written; no bulk enrichment (`pipeline.py:3407-3429`).
10. **Bulk enrichment** — `compute_enrichment_union` excludes preflight-reused identities; `enrich_unique_identities` issues exactly one request per pending identity inside one transaction, never aborting on a single failure (`pipeline.py:3431-3461`, `1498-1585`).
11. **Cutoff** — `capture_scoring_cutoff_utc(clock())` captures one post-enrichment UTC timestamp and writes it to the run (`pipeline.py:3463-3464`).
12. **Finalization** — `finalize_enrichment` recomputes per-stratum `u_demand_h`/`u_recent_h`/`u_quality_h` from persisted observations and checks consistency (`pipeline.py:3466-3476`).
13. **Metrics** — per category, `compute_category_raw_metrics` returns the six raw values, three coverages, three usable counts, and breadth provenance (`pipeline.py:3478-3503`).
14. **Scoring** — `score_category` builds the LOO reference, normalizes, computes components and composite; `build_base_rankable_candidates` freezes candidates; `evaluate_sensitivity` ranks them under three policies (`pipeline.py:3504-3534`).
15. **Final rows + status** — `_build_scored_rows` writes every score/evidence/rankability/sensitivity column; the run is marked `completed` (or preserved `failed`) (`pipeline.py:3536-3575`).
16. **Report** — the renderer runs only after a successful pipeline return and only when `--report` is given (`cli.py:451-458`).

`niche-scout dashboard` [observed]: `dashboard_command` opens the repository, resolves the run id (given or latest), loads the view once, builds the Dash app, and serves loopback — **no transport is constructed and no discovery/enrichment occurs** (`cli.py:505-568`, docstring `cli.py:12-14`).

**Network-bound stages:** 5 (Coveo) and 8/10 (GraphQL). **Deterministic/pure stages:** 6, 13, 14, and the gate arithmetic in 8. **Disk-bound:** 4, 7, 9, 11, 12, 15, 16.

---

## 6. External API & Data Acquisition

### 6.1 Coveo discovery [observed]
- **Endpoint:** `https://unitytechnologiesproductionmkahteav.org.coveo.com/rest/search/v2?organizationId=unitytechnologiesproductionmkahteav` (`collector_coveo.py:128-131, 592-594`).
- **Headers:** `Content-Type`, `Accept`, `Referer: https://assetstore.unity.com/`, plus `Authorization: Bearer <token>`; a leading `"Bearer "` in the stored credential is normalized out so exactly one scheme is sent (`collector_coveo.py:144-148, 597-627`).
- **Request body:** replayed from the captured template (`config/coveo_search_template.json`) for `locale`, `tab`, `referrer`, `timezone`, `context`, `dictionaryFieldContext`, `searchHub`, `sortCriteria`, `numberOfResults`, `facetOptions`; the `facets` block is replaced by the single `ec_category` facet; `actionsHistory` emptied, analytics dropped, `firstResult = page_index * page_size`, `visitorId` fixed to `niche-scout-lean-v1` (`collector_coveo.py:665-779`).
- **Field set:** exactly `permanentid`, `ec_product_id`, `ec_name`, `ec_category`, `publisher_name` (`collector_coveo.py:163-169`). The template's `fieldsToInclude` is deliberately overridden to this five-field set; the module records this as the single deliberate divergence from the capture and flags the capture's 23-entry list as an open discrepancy (`collector_coveo.py:155-169, 832-836`).
- **No free-text query:** `find_forbidden_query_field` recursively rejects any `q`/`query` member at any depth (`collector_coveo.py:630-662`).
- **Pagination:** `PAGE_SIZE = 96` (fixed, protocol limit — `config.py:240-241`); stops when the verified `totalCount` is reached, the page is terminal, or `max_discovery_results_per_category` (default 9000 in code; 9000 in `default.toml`) is hit (`collector_coveo.py:2210-2234`).
- **Retry/backoff:** transient statuses `{408,425,429,5xx}` and transport `URLError`/`OSError` are retried up to `COVEO_MAX_RETRIES = 5` with exponential backoff base 2.0s, honoring numeric `Retry-After`; permanent statuses are not retried (`collector_coveo.py:151-153, 928-1089`).
- **Rate limiting:** `COVEO_MIN_REQUEST_INTERVAL_SECONDS = 1.0`, enforced across the whole run through one shared `CoveoRateLimiter` using the injected `sleeper` (`collector_coveo.py:151, 336-374, 1007-1010`).
- **Response validation:** shape-validated via `validate_response_shape`; a structurally failed 200 page is never read as records and never becomes zero assets (`collector_coveo.py:1147-1301, 2079-2091`).
- **Streaming:** one page is written to the sink before the next request exists; no per-category record list is built (`collector_coveo.py:24-26, 2016-2114`).

### 6.2 GraphQL enrichment [observed]
- **Endpoint:** `https://assetstore.unity.com/api/graphql/batch` (`collector_graphql.py:141`).
- **Operations:** exactly two per request — `ProductDetail(id: ID!)` requesting `id`, `productId`, `rating.average`, `rating.count`, `reviewCount`, `firstPublishedDate`, `state`, `category{id,name}`, `publisher{id,name}`; and `ProductPageViews(packageId: String!)` (`collector_graphql.py:316-373`). Both use the same canonical identity.
- **Headers:** constant set plus `X-CSRF-Token: <token>` and `cookie: _csrf=<token>` from the same operator-supplied credential (`collector_graphql.py:152-161, 397-413`).
- **Correlation:** `operationName` is the explicit key; response position is never trusted unless the preflight validates a fixed two-operation ordering. The persisted mode is `explicit_key` or `validated_position` (`collector_graphql.py:622-899, 1640-1699`).
- **Independent operation status:** each operation has its own status; a top-level error is not treated as success just because the sibling succeeded; partial success retains the valid operation's fields (`collector_graphql.py:515-553, 1937-1977`).
- **Retry:** `max_attempts = 4` (1 + 3), backoff base 0.5s ×2 capped at 8s, retryable classes `HTTP_TRANSIENT` and `TRANSPORT_FAILURE` only; auth/CSRF/malformed/authorization are never retried (`collector_graphql.py:163-173, 216-231, 2181-2191, 2767-2842`).
- **Coupling to undocumented upstream behavior [observed and acknowledged in-code]:** the page-view field is undocumented and its semantics were previously mis-assumed. Lean 1.0.4 corrects it to "validated trailing-7-day (weekly) view count" and the index is `= product_page_views` (`SRS-lean-v2.md:22, 140, 752-764`; `metrics.py:406-495`). The endpoint, organization id, header set, and template are all derived from a *captured* response, and the URI trailing-identifier extraction rule is explicitly inferred rather than verified (`AGENTS.md` "Open obligations"; `collector_coveo.py:249-276`).

**Why both sources:** Coveo is authoritative for category-scoped discovery breadth, membership, and pagination metadata; GraphQL is authoritative for rating, review count, publication date, page views, publisher, category, state, and identity confirmation (`SRS-lean-v2.md:365-369`). Neither duplicates a scoring field.

**Secrets:** never logged, persisted, or echoed. Redaction helpers (`validation.redact_value`) and secret-free error builders are used throughout; `request_metadata_json` and `error_summary_json` carry names/statuses/hashes only (`collector_coveo.py:27-29, 782-842`; `collector_graphql.py:18-21, 1761-1928`). I re-ran the secret checker: clean.

---

## 7. Sampling Model

**What a sample is [observed].** After canonical identity resolution, a category's discovered population is ordered by retained discovery ordinal (`sampling.py:307-358`). If the population is ≤100, it is a **census** (all assets selected). If >100, it is divided into **4 systematic (interleaved) ordinal strata** and 25 assets are selected per stratum → target sample 100 (`sampling.py:426-499`, `models.py:43-46`).

**Strata geometry [observed].** A per-category deterministic offset is derived from `sha256(sampling_rule_version + NUL + category)`'s first 8 bytes mod 4; ordinal `i` belongs to stratum `(i - 1 + offset) mod stride` (`sampling.py:366-423`). This interleaving is why early, middle, and late discovery positions are all represented structurally (`SRS-lean.v2:510-515`).

**Within-stratum selection [observed].** Each candidate is digested by `sha256(sampling_rule_version + NUL + category + NUL + asset_identity_key)`; candidates are sorted by `(digest, asset_identity_key)` and the first `min(25, stratum_size)` are selected (`sampling.py:282-299, 507-556`). **No RNG is used anywhere in sampling** — verified by reading the module (only `hashlib` and stdlib containers) and by the import-boundary test `tests/test_sampling.py::test_sampling_module_imports_are_pure`.

**Reproducibility [observed].** Selection is a pure function of `(sampling_rule_version, category, identity keys, discovery ordinals)`. Same inputs → same digest → same members. Changing the rule version changes the digest and selection (asserted by `tests/test_sampling.py::test_digest_changes_with_rule_version`, a traced node).

**What "deterministic, sample-based, within-run heuristic" means in code [observed]:**
- *Deterministic*: no RNG, no clock, no platform hash; explicit tie-breaks; same inputs give the same outputs (`LREQ-ARCH-030`, `scoring.py` docstrings, sampling digest).
- *Sample-based*: for large categories, product-level attributes are estimated from ≤100 assets, while competition uses discovered breadth (not sample size) (`SRS-lean-v2.md:194-204`).
- *Within-run*: normalization is leave-one-out against the *other categories in the same run*, so scores are not comparable across runs with different category sets (`SRS-lean-v2.md:144, 1399`).

**What may vary between runs [observed, inferred]:** live upstream catalog changes, page-ordering changes, and endpoint behavior changes all change the discovered population, hence the sample. The code makes no claim of cross-run identity; the SRS explicitly defers cross-run comparability (`SRS-lean-v2.md:1376`).

**Edge handling [observed]:** populations of 0/1/99/100 are covered by tests; a stratum below 25 selects all and records a reduced count (`LREQ-SMP-090`); a zero population yields `sample_fraction = None`, never `0.0` (`sampling.py:606-610`); duplicate membership is prevented by the `(run_id, category, asset_identity_key)` primary key (`database.py:147`).

**Cross-category overlap [observed].** `compute_overlap` counts other categories sharing at least one sampled identity and the percentage of this category's sample shared elsewhere; a zero-member category yields `None`, a non-empty no-overlap category yields a measured `0.0` (`sampling.py:696-748`). Overlap never inflates enrichment or preflight counts.

---

## 8. Analytics & Heuristics

All formulas below are transcribed from `metrics.py` (7A/7B) and `scoring.py` (8/9A/9B) and match SRS Appendix A (`SRS-lean-v2.md:1453-1486`).

**Common eligibility [observed].** A product-level value is usable only if its type, range, state, identity, and timestamp conditions pass; null/malformed/wrong-type/future/naive/negative/non-finite/state-excluded values are *classified unavailable with a distinct reason* and never raised away and never converted to zero (`metrics.py:88-122, 338-495`). `age_days_exact = (scoring_cutoff_utc - first_published_date_utc).total_seconds() / 86400` (`metrics.py:371-403`).

### Metric dictionary

| Metric | Inputs | Formula / Logic | Direction | Normalization | Interpretation | Caveats |
|---|---|---|---|---|---|---|
| `age_days_exact` | `first_published_date_utc`, cutoff | `(cutoff - date).total_seconds()/86400` | — | none | exact fractional age | naive/future → unavailable |
| `age_normalized_page_view_index` | `product_page_views`, date, state, identity | `= product_page_views` (weekly count) | higher = more views | none | trailing-7-day views | historical name; not age-normalized; 0 is valid; needs age ≥ `MIN_AGE_DAYS_FOR_RATE` |
| `DemandPerAssetRaw` | usable per-stratum view means | `Σ(w_h·mean_h)/Σ(w_h)`, `w_h=N_h/N` | higher = more demand | none | population-weighted mean weekly views | null if no usable stratum; `N=0` → null |
| `DemandMedianRaw` | usable view indices | weighted median, weight `N_h/n_h` | higher = more demand | none | robust central views | exact-half → mean of boundary pair |
| `BreadthRaw` | verified `totalCount` or distinct canonical count | verified total, else distinct count | higher = broader | none | catalog breadth | fallback marks `incomplete_estimate`; failed page ≠ 0 |
| `RecentShareRaw` | usable dated assets | `Σ(w_h·share_h)/Σ(w_h)`, `share_h = count(0≤age≤365)/u_recent_h` | higher = more recent supply | none | recent catalog composition | not sales velocity |
| `MedianAgeRaw` | usable ages | weighted median, weight `N_h/n_h` | higher = older catalog | none | median asset age | |
| `QualityRaw` | rating-average, view index | `Σ(N_h/n_h·Σ((rating/5)·index)) / Σ(N_h/n_h·Σ(index))` | higher = better-rated | none | visibility-weighted rating strength | needs rating_count ≥5 and eligible ≥5; not satisfaction |
| `demand_stratum_eligibility_coverage` | stratum weights | `Σ(N_h/N)` over demand-usable strata, clamped `[0,1]` | higher = better support | clamp | population share in usable strata | not sample fraction |
| `recent_supply_stratum_eligibility_coverage` | stratum weights | same over recent-usable strata | higher = better support | clamp | — | — |
| `quality_stratum_eligibility_coverage` | stratum weights | same over quality-usable strata | higher = better support | clamp | — | — |
| `P_ref(x)` | target, peer values | `(L + 0.5E)/m` | higher = higher rank | midrank `[0,1]` | descriptive relative position | not an inferential percentile |
| `D0` | two demand midranks | `0.60·P_ref(per_asset)+0.40·P_ref(median)`; single available value if one | higher = better | — | demand component pre-shrink | unavailable if neither |
| `D` | `D0`, demand coverage | `clamp(0.5 + coverage·(D0-0.5),0,1)` | higher = better | clamp | demand component | unavailable if coverage < 0.50 |
| `C` | breadth midrank | `clamp(1 - P_ref(BreadthRaw),0,1)` | higher = less crowded | clamp | competition component | only with verified complete breadth; no shrinkage |
| `Rpressure0` | recent/age midranks | `0.70·P_ref(share)+0.30·(1-P_ref(age))`; single value if one | higher = more pressure | — | — | — |
| `R` | `R0=1-Rpressure0`, coverage | `clamp(0.5 + coverage·(R0-0.5),0,1)` | higher = better | clamp | recent-supply component | unavailable if coverage < 0.50 |
| `Q` | quality midrank, coverage | `clamp(0.5 + coverage·(1-P_ref(QualityRaw)-0.5),0,1)` | higher = better | clamp | quality component | contradicted page views → unavailable |
| `market_opportunity_score` | available components | `W_A=Σw_x`; `S=Σ(w_x·x)/W_A`; `clamp(0.5+W_A·(S-0.5),0,1)` | higher = better | clamp | composite | null if <2 components available |

**Constants [observed, `models.py`]:** `MAX_DISCOVERY_RESULTS_PER_CATEGORY=9000`; `PAGE_SIZE=96`; `MIN_CATEGORIES_PER_RUN=8`; `STRONG_REFERENCE_CATEGORY_COUNT=21`; `MAX_TAXONOMY_AGE_DAYS=30`; `ENRICHMENT_SAMPLE_SIZE_PER_CATEGORY=100`; `SAMPLE_STRATA=4`; `SAMPLE_PER_STRATUM=25`; `MIN_USABLE_SAMPLES_PER_STRATUM=1`; `MIN_REQUIRED_COMPONENT_COVERAGE=0.50`; `STRONG_COMPONENT_COVERAGE=0.80`; `MIN_AGE_DAYS_FOR_RATE=30`; `RECENT_WINDOW_DAYS=365`; `QUALITY_MIN_RATING_COUNT=5`; `QUALITY_MIN_ELIGIBLE_ASSETS=5`; `W_D/W_C/W_R/W_Q=0.35/0.30/0.20/0.15`; demand subweights `0.60/0.40`; recent subweights `0.70/0.30`; three sensitivity policies.

**Note on a constant drift [observed]:** the SRS §14 table says `MAX_DISCOVERY_RESULTS_PER_CATEGORY` default `2000`, but `models.py:33` sets **9000** and `config/default.toml:16` sets `9000`. The SRS also labels it "Configurable = Yes", so this is a documented default that was changed in code/config without an SRS revision entry. This is a documentation/code drift worth reporting.

**Objective vs. heuristic [inferred]:** the raw values (views, ratings, dates, counts) are observed; the stratum expansion weights, the coverage shrinkage toward 0.5, the subweights, the component weights, and the LOO midrank are **heuristic policy choices**, all fixed and documented but not calibrated against any outcome dataset.

---

## 9. Ranking Model

**Pipeline [observed]:**
1. Raw metric values per category (`metrics.compute_category_raw_metrics`).
2. Leave-one-out reference: each target normalized against all *other* categories in the run (`scoring.py:300-347`); `reference_size = category_count - 1` (`scoring.py:340`).
3. Midrank normalization of six fields independently (`scoring.py:273-371`).
4. Components `D/C/R/Q` with coverage shrinkage (`scoring.py:374-558`).
5. Composite via available-weight renormalization (`scoring.py:561-633`).
6. **Base-rankable candidate set frozen before sensitivity** — requires ≥21 categories, all four components available, every coverage ≥0.50, positive reference, and field-support passes (`scoring.py:1015-1054, 1115-1173`).
7. Sensitivity: the frozen candidate set is ranked under `balanced`, `demand_heavy`, `competition_heavy`; ties broken by ascending lexical category path (`scoring.py:1362-1534`).
8. Final evidence grade and final rankability, which sensitivity may demote to `provisional` but never to `not_rankable` and never changes the balanced score (`scoring.py:1537-1656`).

**Interpretation [observed]:** a high rank means "highest score under this fixed within-run heuristic given the available evidence", **not** commercial success. The SRS is explicit: the output is "not a sales forecast, revenue prediction, causal demand estimate, statistically representative estimate … or validated weekly traffic measurement" (`SRS-lean-v2.md:60-65`), and the report statement repeats it (`report.py:305-320`).

**Tie handling, sorting, missing data [observed]:** sorting is by `(-score, category)` (`scoring.py:1395`); an unavailable component is excluded from the weight sum, never zeroed; fewer than two components → `unavailable` and no score; coverage below 0.50 removes the component and, if required, the category's rankability (`scoring.py:596-604`, `metrics.py:1614-1620`).

---

## 10. Reproducibility & Purity Boundary

**Pure functions [observed]:** all of `sampling.py`, the metric estimators in `metrics.py`, and the normalization/scoring/evidence/sensitivity functions in `scoring.py`. They accept typed inputs and return typed results; they perform no I/O and read no clock. `scoring_cutoff_utc` is always an explicit parameter.

**Side-effectful / boundary functions [observed]:** `collector_coveo.fetch_category_page`/`discover_category`, `collector_graphql.enrich_asset`/`execute_graphql_batch`, `database.SqliteRepository`, `pipeline.run_pipeline`, `report.write_run_report`/`build_dashboard_app`, `cli.main`.

**Enforcement [observed, re-run by me]:** `tools/check_import_boundaries.py` is an AST checker that fails if `metrics.py`/`scoring.py` import any forbidden module or read a clock attribute. It printed "Import boundaries valid". This is a maintained guard, not a proof (its docstring says so), but it is a real automated check.

**What reproducibility means here, precisely [observed]:**
- *Deterministic calculation given the same input dataset*: **yes** — pure functions, explicit tie-breaks, no RNG, `float64`.
- *Deterministic sampling*: **yes** — SHA-256 over frozen strings with a fixed rule version.
- *Identical results across separate live runs*: **no guarantee** — upstream catalog, ordering, and page composition can change between runs.
- *Reproducibility after upstream API changes*: **not claimed**; the endpoint contract version is recorded per run (`runs.endpoint_contract_version`) but there is no replay-from-capture path.

**Replay/re-analysis of saved runs [observed]:** the dashboard and `--report` re-render **persisted** results and recompute nothing (`report.py:1-27`, `681-724`). A saved run cannot be re-scored with new policy without re-running the pipeline, because scoring consumes persisted enrichment observations, not raw responses (full raw-response archival is deferred — `SRS-lean-v2.md:1380`).

**Intentional purity violations [observed]:** `pipeline.py` imports a private helper `_failure_cause_json` from `collector_coveo`; `report.py` computes `_rank_from_sensitivity`-style ordering from persisted JSON; `database.py` imports `sampling` to compute overlap at persist time. These are pragmatic couplings, not violations of the metrics/scoring boundary.

---

## 11. Testing Strategy

**Suite size [counted]:** `pytest -q` → **766 passed, 37 warnings in 30.72s** (the warnings are Dash deprecation notices, not failures). `tests/traceability.json` holds **745 node IDs [counted]**, distributed across 19 test modules; the largest are `test_collector.py` (102), `test_validation.py` (63), `test_report.py` (60), `test_identity_preflight.py` (46), `test_metrics.py` (44).

**Traceability [observed, re-run]:** the validator printed `89 required/defined LREQ IDs mapped, 745 matrix nodes, 0 unmarked analytical tests outside exemption`. Three non-analytical nodes are explicitly exempted (`validate_traceability.py:48-54`). Every analytical test carries `@pytest.mark.lreq` and a matching matrix entry; parameterized tests map by base node ID.

**Network isolation [observed, verified two ways]:**
- `tests/test_pipeline.py:1172-1194` installs a sentinel that makes a real `socket.connect` raise `AssertionError("the pipeline must not open a socket")`, then runs an end-to-end pipeline.
- `tests/test_cli.py:569-596` replaces `collector_coveo.CoveoUrlOpener` with a poison transport and asserts no live call occurs.
- `tests/test_live_endpoint_compatibility.py:1-15` states the module is offline and deterministic and contacts no endpoint.
- Grep for `socket|urlopen|requests\.|http.client` in `tests/` found only these isolation seams and docstring mentions, not live calls.

**Fixture strategy [observed]:** `tests/fixtures/*.py` holds 16 inert data modules (golden vectors, captured-response literals, scenario builders), totaling ~12k lines. Fixture credentials are non-secret literals (`MOCK_ENVIRONMENT`).

**What tests protect [observed]:** the purity boundary (import test + socket sentinel), formula correctness (golden vectors, `1e-9` tolerance per SRS §13), edge cases (zero population, ties, boundaries, partial GraphQL success, reversed order), persistence round-trips, CLI exit codes, and report rendering. **What they do not protect:** live upstream contract drift (the "live compatibility" module uses encoded literals, not a captured response), and the unverified URI trailing-identifier extraction rule.

**Gaps I can substantiate [observed]:** (a) `tests/golden_vectors/` is referenced in `tests/AGENTS.md` but does not exist on disk — golden data lives in `tests/fixtures/`; (b) there is no coverage gate or CI config in the repo (deliberately deferred per `LREQ-NFR-060`); (c) strict whole-project typing is deferred, so mypy/pyright are not configured in `pyproject.toml`.

---

## 12. CLI & User Experience

**Commands and options [observed, `cli.py:198-251`]:**

```
niche-scout run [--categories PATH] [--config PATH] [--report PATH]
                [--report-format html|text] [config overrides...]
niche-scout dashboard [--categories PATH] [--config PATH] [--run-id ID] [config overrides...]
```

Config override flags exist only for the SRS-configurable settings: `--max-discovery-results-per-category`, `--max-taxonomy-age-days`, `--min-usable-samples-per-stratum`, `--min-age-days-for-rate`, `--recent-window-days`, `--quality-min-rating-count`, `--quality-min-eligible-assets`, `--identity-preflight-min-categories`, `--identity-preflight-assets-per-category`, `--identity-preflight-min-success-rate` (`cli.py:109-123`). `--page-size`, `--min-categories-per-run`, and `--strong-reference-category-count` are deliberately **not** exposed (`cli.py:106-108`).

**Exit codes [observed]:** `0` success (including provisional 8–20 runs), `1` runtime failure (including preflight-failed runs), `2` usage/config error (`cli.py:48-55, 581-610`).

**Outputs [observed]:** stdout is reserved; limitations and errors go to stderr; logs use `LEVEL logger: message` at INFO (`cli.py:75-95, 449-458`). `--report` writes HTML or text to the given path.

**Fresh install → completed analysis [observed]:** install the package (`pyproject.toml` `[project.scripts] niche-scout = "niche_scout.cli:main"`), set the two env credentials, edit `config/categories.json` to 8–21 category paths, then `niche-scout run --report runtime/report.html`, then `niche-scout dashboard`. No command is invented here; all four come from the parser and README/SRS.

**UX caveat [observed]:** `niche-scout` with no subcommand prints an error and returns 2; `--help` returns 0. `dashboard` binds only loopback and never opens a browser (`cli.py:488-502`).

---

## 13. Reporting & Dashboard

**Text/HTML report [observed, `report.py`]:** `load_run_report_view` reads persisted rows only and builds a `RunReportView`; the HTML renderer emits a self-contained document with inline CSS and a client-side sortable table; the text renderer emits the same fields as plain text. `HEURISTIC_STATEMENT` (`report.py:305-320`) is fixed text stating the score is a within-run heuristic not calibrated against sales/revenue/downloads/conversion, and distinguishing pagination completion from snapshot completeness, the weekly page-view index from lifetime/daily-average, descriptive midranks from inferential percentiles, coverage from sample fraction, deterministic-sample evidence from statistical representativeness, and evidence grade from confidence.

**Dashboard [observed, `report.py:2583-2690`]:** a Dash app built by `build_dashboard_layout`/`build_dashboard_app`, served locally (`serve_locally=True`, no CDN). It renders a run header, KPI strip, six Plotly charts (`score_bar`, `contribution_stack`, `policy_bump`, `population_lollipop`, `score_quality_scatter`, `demand_competition_scatter` — fixed `div_id`s in `DASHBOARD_CHART_IDS`), a primary table covering every `LREQ-RPT-020` field, a category-detail panel, a shared formula panel, and a footnote.

**Transparency mechanisms [observed]:** progressive disclosure via `<details>` elements (`_disclosure`, `_heuristic_banner`, `_shared_formula_panel`); plain-language label vocabulary `_DASHBOARD_LABELS`; per-chart captions `_DASHBOARD_CHART_CAPTIONS`; a column guide mapping every column to a one-line meaning; "n/a" is an explicit unavailable marker distinct from a measured 0 (`report.py:129-131, 2540-2550`).

**Read-only [observed]:** `build_dashboard_app` constructs the app and one callback (`_render_selected_detail`) that reads the already-loaded view; no repository access inside the callback, no writes, no network. `dashboard_command` never constructs a transport.

**Does it re-compute? [observed]:** No. The module docstring states it "recomputes no metric, component, normalized value, composite score, evidence grade, rankability, or sensitivity statistic: every displayed value is a persisted value rendered verbatim (display rounding only)" (`report.py:6-9`).

---

## 14. Data Provenance & Auditability

**Persisted tables [observed, `database.py:86-234`]:** `runs`, `raw_discovery_observations`, `sample_members`, `enrichment_observations`, `category_scores`, plus a `schema_metadata` table holding `SCHEMA_VERSION = "1.3.0"`.

**Provenance chain [observed]:**
- `runs` stores `run_id`, timestamps, `categories_json`, `config_snapshot_json`, `config_sha256`, taxonomy version/capture/hash, three policy versions, page-view semantics status, correlation mode, preflight status/summary, and status.
- `raw_discovery_observations` stores the ordinal, all identity candidates, resolution status/reason, category value and filter validation status, duplicate linkage, redacted request metadata, redacted error summary, and retrieval time.
- `sample_members` stores the stratum geometry, rank, census flag, selection digest, overlap, and preflight flag.
- `enrichment_observations` stores per-operation status, all enriched fields (nullable), identity mismatch, redacted per-operation error summaries, redacted request metadata (operation names, correlation keys/mode, HTTP status, response sha256, retry metadata), and retrieval time.
- `category_scores` stores the raw values, coverages, usable counts, stratum statistics, components, composite, evidence grade, rankability, missing components, warnings, reference size/usable counts, sensitivity fields, and computation time.

**Can a user trace `category → sample → asset data → metric → normalized value → aggregate score`? [observed]:** **Yes, within a run.** `category_scores` → `sample_members` (by run_id+category) → `enrichment_observations` (by run_id+identity) → `raw_discovery_observations` (by run_id+category) gives the full chain. The report and dashboard expose it: category details show raw metric inputs, strata with `N_h`/`n_h`/`u_*_h`, warnings, timestamps, and observed-vs-inferred labels; the primary table carries reference size and usable counts.

**Where the chain is incomplete [observed]:** raw response bodies are not archived (`SRS-lean-v2.md:1380`; scope guard forbids `raw_product_details`). So a value can be traced to the *persisted normalized observation* and the request metadata (including a response sha256), but not re-derived from the original HTTP body. The dashboard omits advanced provenance navigation by design (`LREQ-RPT-050`).

---

## 15. Error Handling & Failure Modes

**Behavior by failure class [observed]:**

| Failure | Behavior |
|---|---|
| Missing credentials | `get_credentials` raises; CLI returns 2 before any transport (`config.py:109-115`, `cli.py:413-416`) |
| Stale/malformed/incomplete taxonomy | `TaxonomyInvalidError`; run aborts before network (`pipeline.py:3306-3316`) |
| Coveo page 429/5xx/transport error | Retried with backoff up to 5; terminal `CoveoRequestFailed` records category `request_failed` with redacted cause (`collector_coveo.py:1029-1089, 2043-2063`) |
| Coveo structural page failure | Category marked `page_failed`; page contributes no records; never zero assets (`collector_coveo.py:2079-2091`) |
| Coveo unreconciled total | Category marked `truncated` with a recorded `DISCOVERY_INCOMPLETE` shortfall (`collector_coveo.py:2151-2178`) |
| Category identity conflict/unresolved | Record marked and excluded from denominator/enrichment; category `identity_incomplete` (`validation.py:1445-1489`, `collector_coveo.py:2185-2186`) |
| Unexpected per-category adapter exception | Caught, isolated, recorded `request_failed` for that category only (`pipeline.py:2944-2963`) |
| GraphQL operation error / null / wrong type | Per-operation `error` status; fields remain `None`; partial success retained (`collector_graphql.py:515-553, 2585-2640`) |
| GraphQL auth/CSRF/malformed | Permanent, never retried (`collector_graphql.py:221-231`) |
| Preflight below success rate or above conflict rate | Run marked `failed`; bulk enrichment blocked; limitation rows persisted (`pipeline.py:3407-3429`) |
| Zero preflight identities | Status `insufficient`; no observations written; run failed (`pipeline.py:476-485`, `942-1016`) |
| Empty category | `discovered_population_count=0`, `sample_fraction=None`, demand metrics null, coverage 0 (`sampling.py:606-610`, `metrics.py:1321-1325`) |
| Insufficient sample | Component unavailable; category `not_rankable` or coverage-shrunk (`metrics.py:1596-1620`) |
| Missing persisted observation for a sampled member | `PipelineError` naming category only — never substituted with a zero (`pipeline.py:2811-2817`) |
| Filesystem/DB failure | `DatabaseError`/`OSError` → exit 1; secrets never in messages (`cli.py:468-470`) |
| Unknown run id on dashboard | `RunNotFoundError` → exit 1; empty DB → error to stderr (`cli.py:546-561`) |

**Pattern [observed]:** the system generally **fails fast** on configuration/taxonomy/credential problems and **continues partially with recorded status** on per-category/per-asset problems. It never substitutes a default for a missing measurement; it marks a distinct status instead.

---

## 16. Performance & Scale Assumptions

**Scale assumptions [observed]:** the SRS states "at least 8 categories per run" and treats 21 as the strong-reference boundary (`SRS-lean-v2.md:107-116, 932-936`); the prompt's "roughly 8–20 categories" matches the provisional band. The committed `config/categories.json` lists 24 categories.

**Is 8–20 a hard limit? [observed]:** No. `MIN_CATEGORIES_PER_RUN=8` is a hard **lower** bound enforced before ranking (`pipeline.py:3285-3290`). There is no upper bound; runs with ≥21 categories can reach `rankable`. The 8–20 band is a *documented policy* that yields `provisional` (`SRS-lean-v2.md:1058`), not a technical limit.

**Request amplification [observed, inferred]:**
- Discovery: `ceil(min(N, 9000)/96)` requests per category, spaced ≥1.0s apart.
- Preflight: up to `min_categories × assets_per_category` unique identities (default 5×2=10, deduped).
- Enrichment: one batch request per unique sampled identity not reused from preflight (≤ `4×25=100` per large category, deduped across categories).
- So a 24-category run with large categories could issue on the order of a few thousand GraphQL requests, each with `min_request_interval_seconds=0.5` and up to 4 attempts. `build_enrichment_projection` logs a projected minimum time before enrichment (`pipeline.py:1393-1458`).

**Concurrency [observed]:** **none.** Discovery, preflight, and enrichment are all sequential `for` loops. No async, threads, or process pool.

**Caching [observed]:** none across runs; within a run, preflight responses are reused as enrichment observations and each unique identity is enriched at most once (`pipeline.py:3431-3461`).

**Memory [observed]:** discovery is streamed one page at a time (`LREQ-NFR-010`); enrichment holds only the union of pending identity keys. The largest in-memory structures are the per-run metric/score tuples, which scale with category count, not catalog size.

**Computational complexity [inferred]:** metric/score work is linear in categories and sampled assets; normalization is O(categories²) in the worst case (each target scans all peers). At the intended 8–24 category scale this is trivial. At hundreds of categories the LOO normalization and the per-category GraphQL request count would dominate.

**Dashboard load [observed]:** one DB read per run; charts are built in-process from the view; no pagination or lazy loading.

---

## 17. Security & Credential Handling

**Credential sources [observed]:** only `NICHESCOUT_COVEO_BEARER_TOKEN` and `NICHESCOUT_UNITY_CSRF_TOKEN` from the environment (`config.py:39-40, 280-292`). `.env` is git-ignored; `.env.example` contains no credentials. The checker confirms no tracked `.env` and no literal credential in `src/`, `tests/`, `config/`, or `pyproject.toml`.

**Implemented properties [observed]:**
- Credentials are required before any transport call (`config.py:109-115`; `pipeline.py:3291-3294`; `collector_graphql.py:376-394`).
- No credential, header value, cookie, or response body reaches logs, errors, SQLite, or `request_metadata_json`. `build_request_metadata_json`'s signature accepts no credential/header/body parameter at all (`collector_graphql.py:1841-1928`). Error builders name only table/column or failure class (`database.py:16`, `collector_coveo.py:430-449`).
- Redaction helper `validation.redact_value` (`validation.py:183-200`); the secret checker is a maintained guard (self-described as a guard, not a proof).

**Local-server behavior [observed]:** the dashboard binds `127.0.0.1` only and never opens a browser (`cli.py:481-502`). There is no authentication on the loopback server; any local process could read the served data. This is a user-maintained assumption, not an implemented control.

**Network boundaries [observed]:** outbound only to the Coveo organization endpoint and the Unity GraphQL batch endpoint, both HTTPS. No telemetry, analytics block dropped from the Coveo body (`collector_coveo.py:678-681`).

**Not implemented [observed]:** no credential encryption at rest, no OS keychain integration, no per-run credential scoping, no rotation support. Secrets in process environment are visible to the same user's other processes — a standard assumption.

---

## 18. Design Decisions Worth Explaining

For each: what, where, problem, trade-off, and whether the motivation is documented or inferred.

1. **Isolate API acquisition from pure analytics.** `metrics.py`/`scoring.py` never import I/O; the pipeline passes plain typed inputs. *Evidence:* `check_import_boundaries.py`, module docstrings, SRS §3.3. *Solves:* testability, determinism, auditability. *Trade-off:* the pipeline must marshal every value explicitly, adding boilerplate. *Motivation:* documented (`LREQ-ARCH-010/020`).

2. **Represent runs as reproducible artifacts.** Five tables persist raw observations, samples, enrichment, scores, and run metadata. *Evidence:* `database.py:86-234`. *Solves:* "where did this number come from?" *Trade-off:* storage and schema evolution burden; raw bodies not archived. *Motivation:* documented (`SRS-lean-v2.md:565-694`).

3. **Heuristics as explicit formulas, not opaque scores.** Every component is a documented expression with a formula panel in the report. *Evidence:* `report.py:366-391`, SRS Appendix A. *Trade-off:* exposes the heuristic's arbitrariness. *Motivation:* documented.

4. **Sample-based signals instead of pretending to have demand data.** Large categories are estimated from a deterministic stratified sample; competition uses breadth. *Evidence:* `sampling.py`, SRS §2.3. *Trade-off:* sample bias and reduced precision; explicitly disclaimed. *Motivation:* documented.

5. **Identity preflight as a hard gate.** Bulk enrichment cannot start until an endpoint-and-mapping smoke test passes. *Evidence:* `pipeline.py:1088-1209, 3407-3429`. *Solves:* prevents burning thousands of requests on a broken identity mapping. *Trade-off:* a failed preflight fails the whole run. *Motivation:* documented (`LREQ-ID-040`).

6. **Read-only dashboard.** No writes, no network, no recomputation. *Evidence:* `report.py:6-9, 2662-2690`. *Solves:* the UI cannot silently change results. *Trade-off:* no interactive re-weighting. *Motivation:* documented (`LREQ-CLI-020`, `LREQ-RPT-010`).

7. **Network-independent tests.** A socket sentinel and poisoned transports make live calls fail the suite. *Evidence:* `tests/test_pipeline.py:1172-1194`, `tests/test_cli.py:569-596`. *Trade-off:* live contract drift is not caught by tests. *Motivation:* documented in `AGENTS.md`.

8. **Progressive disclosure.** Complexity is behind `<details>` and plain-language labels. *Evidence:* `report.py:2472-2527`. *Trade-off:* the most important caveats are collapsed by default. *Motivation:* documented (`LREQ-RPT-030/050`); the specific `<details>` choice is an implementation decision.

---

## 19. What Niche Scout Does Not Know

This section is explicit about model boundaries. **The system has no information about:**

- **Sales, revenue, downloads, conversion rate** — not collected, not estimated, not calibrated (`SRS-lean-v2.md:60-65, 1388`; `report.py:305-320`).
- **Traffic beyond the page-view field** — the only view signal is an undocumented weekly page-view count whose semantics were corrected in Lean 1.0.4 (`metrics.py:406-495`).
- **Demand in the causal sense** — `DemandPerAssetRaw` is a population-weighted mean of weekly page views, a marketplace observation, not buyer intent.
- **Customer intent** — no behavioral or survey data.
- **Publisher margins or marketing spend** — no cost or spend data.
- **Quality beyond observable metadata** — `QualityRaw` is visibility-weighted rating strength, not objective quality; ratings are "marketplace observations, not objective product-quality measurements" (`SRS-lean-v2.md:1401`).
- **Future category growth** — no forecasting; scores are within-run relative positions.
- **Causal effects** — no experimental design, no treatment/control.
- **Statistical representativeness** — the sample is a deterministic stratified sample of *discovery order*, not a probability sample of buyers, sales, or marketplace activity (`SRS-lean-v2.md:555-561, 1397`).

**The critical distinction, preserved verbatim from the code and SRS:**

> "This category scores well according to the implemented heuristic" **≠** "this category will be commercially successful."

A high `market_opportunity_score` means: under this fixed within-run weighting, given the available evidence and the sampled observations, this category ranks highly on the observed combination of weekly views, limited verified breadth, recent catalog composition, and apparent rating gap. It is a **ranking aid**, not a prediction. The report states this (`report.py:305-320`), the CLI description states this (`cli.py:209-214`), and the SRS states this repeatedly (`SRS-lean-v2.md:60-65, 169-176`).

---

## 20. Strengths, Trade-offs, and Risks

### Strengths (implementation-supported)
- **Enforced purity boundary** with an automated AST guard that I re-ran and that passes (`check_import_boundaries.py`).
- **Bidirectional requirement traceability**: 89 requirements, 745 matrix nodes, validator passes (`validate_traceability.py`).
- **Missing-not-zero discipline** is pervasive and testable: distinct unavailable reasons, nullable columns, explicit `n/a` markers.
- **Deterministic sampling** with no RNG and a versioned rule string.
- **Network-independent test suite** with an active socket sentinel.
- **Streamed discovery** with a per-page memory invariant.
- **Secret redaction** verified by a maintained static checker.

### Trade-offs (deliberate or consequential)
- **Sequential execution only** — no concurrency, so a large run is slow; `build_enrichment_projection` logs a projected minimum time.
- **`pipeline.py` monolith** (3,576 lines) concentrating orchestration, preflight, union, finalization, warning assembly, and row building.
- **Raw responses not archived** — provenance stops at normalized observations plus a response hash.
- **No cross-run comparability** — scores are explicitly within-run.
- **Fixed weights** — the balanced score cannot be tuned without a new SRS revision.

### Risks (grounded in the repository)
- **Upstream API instability**: the Coveo endpoint, organization id, header set, template, and GraphQL endpoint are all derived from a *capture*; the page-view field is undocumented. A capture is a snapshot, not a contract.
- **Unverified identity rule**: URI trailing-identifier extraction is inferred, not verified against a real response (`AGENTS.md` open obligations; `collector_coveo.py:249-276`).
- **Sample bias**: the sample follows discovery order, which "may reflect marketplace ranking or retrieval behavior" (`SRS-lean-v2.md:1398`).
- **Metadata bias**: ratings and page views are marketplace observations with unknown collection methodology.
- **Sensitivity to weighting**: three policies are evaluated precisely because ranking can shift; `RANKING_SENSITIVITY_HIGH` warns when top-3 stability < 2/3.
- **Sensitivity to sample composition**: coverage shrinkage pulls weak-support components toward neutral, which can move ranks.
- **Hidden normalization assumptions**: the LOO reference excludes the target, so a category is scored relative to the *selected* peers; a category set change changes every score.
- **Coupling to current Asset Store behavior**: the adapter replays a captured request body and a captured taxonomy; both can go stale (taxonomy freshness is checked at 30 days).

### Documented-vs-implemented drifts found [observed]
1. **`MAX_DISCOVERY_RESULTS_PER_CATEGORY`**: SRS §14 says default `2000`; `models.py:33` and `config/default.toml:16` say `9000`. No SRS revision entry documents the change.
2. **SRS path drift**: `AGENTS.md` and `validate_traceability.py` point at `Documents/SRS-lean-v2.md`, but `.kilo/project-rules.md:9` still names `Documents/SRS-lean.md`, and ten source docstrings cite `Documents/SRS-lean.md` line numbers that no longer correspond to the normative file (the line offsets differ because Lean 1.0.4 added text). The *IDs* remain valid; the *line citations* are stale.
3. **README is stale**: `README.md` describes "Chunk 0 contracts" only and lists a narrower module set than exists; it does not describe the dashboard, preflight, or sensitivity features that are implemented.
4. **`tests/golden_vectors/`** is named in `tests/AGENTS.md` but does not exist; golden data lives in `tests/fixtures/`.
5. **`.kilo/project-rules.md` vs `AGENTS.md`**: both exist as project instruction files with overlapping but non-identical content; the precedence rules in `.kilo/project-rules.md` point at the retired SRS path.

---

## 21. Suggested Technical Storylines for a Future Medium Article

These are **candidate angles, not rankings**.

**Storyline A — "The Purity Boundary: Making an Analytics Pipeline Auditable by Construction"**
- *Thesis:* Determinism and auditability are architectural properties you enforce with a machine, not conventions you hope reviewers follow.
- *Evidence:* `metrics.py`/`scoring.py` purity; `check_import_boundaries.py` (AST enforcement); the explicit `scoring_cutoff_utc` parameter; the missing-not-zero taxonomy.
- *Sections to explain:* 3 (architecture map), 10 (purity boundary), 11 (tests).
- *Lesson:* a small, checkable rule ("pure modules may not import I/O or read the clock") buys testability and reproducibility cheaply.
- *Caveat:* the guard is syntactic — it cannot prove semantic purity, and the pipeline still concentrates orchestration in one large file.

**Storyline B — "Sampling Without Randomness: Deterministic Stratified Selection with SHA-256"**
- *Thesis:* You can get a reproducible, distributed sample without an RNG by hashing versioned strings and interleaving ordinal strata.
- *Evidence:* `sampling.py:282-556`; the digest formula; the `(offset, stride)` geometry; census ≤100.
- *Sections to explain:* 7 (sampling model), 8 (estimators), 9 (ranking).
- *Lesson:* determinism and distribution are not in tension; the version string is the reproducibility handle.
- *Caveat:* deterministic sampling is not a probability sample and does not bound error; the SRS says so explicitly.

**Storyline C — "A Gate Before the Firehose: Identity Preflight for a Fragile API"**
- *Thesis:* When an undocumented API's identity mapping can silently disagree, test the endpoint and mapping on a tiny deterministic set before spending thousands of requests.
- *Evidence:* `pipeline.py:1088-1209`; success/conflict rates over unique identities; the failed-run transition; preflight reuse.
- *Sections to explain:* 5 (execution flow), 6 (API acquisition), 15 (failure modes).
- *Lesson:* a cheap smoke test is an architectural safeguard, not just a test.
- *Caveat:* a failed preflight fails the whole run, and the preflight is "not a statistically representative validation" (`SRS-lean-v2.md:399-400`).

**Storyline D — "Saying 'I Don't Know' in Data: Missing-Not-Zero as a Design Principle"**
- *Thesis:* Treating missing, invalid, and unavailable as first-class distinct states prevents fabricated zeros from silently becoming evidence.
- *Evidence:* the reason vocabulary in `metrics.py:88-122`; nullable columns; `sample_fraction=None` for zero population; the `n/a` marker; coverage shrinkage toward neutral.
- *Sections to explain:* 8 (metrics), 13 (reporting), 14 (provenance), 19 (limits).
- *Lesson:* explicit unavailability is more useful than an imputed zero.
- *Caveat:* it makes schemas and reports more verbose, and the distinction must be maintained across every layer.

**Storyline E — "Heuristics You Can Argue With: Shipping a Transparent Ranking Instead of a Black Box"**
- *Thesis:* A ranking model whose formulas, weights, coverage shrinkage, and sensitivity are all visible is more honest and more useful than an opaque score.
- *Evidence:* `scoring.py` components and composite; the formula panel; the three-policy sensitivity; the evidence grades; the fixed weights.
- *Sections to explain:* 8 (heuristics), 9 (ranking), 13 (reporting), 20 (trade-offs).
- *Lesson:* transparency about heuristic choices is a feature, not an admission of weakness.
- *Caveat:* transparency does not create validity; the score is uncalibrated and within-run.

---

## 22. Evidence Index

| Claim | Evidence | Confidence | Notes |
|---|---|---|---|
| Tool is a sample-based within-run heuristic, not a predictor | `README.md:3-6`; `SRS-lean-v2.md:60-65`; `report.py:305-320`; `cli.py:209-214` | High | Stated in code, report text, CLI description, SRS |
| ≥8 categories required before ranking | `pipeline.py:3285-3290`; `models.py:35` | High | Enforced at runtime |
| 8–20 categories provisional; 21 strong reference | `SRS-lean-v2.md:1053-1067`; `scoring.py:1032-1033, 1608` | High | Policy + code |
| `metrics.py`/`scoring.py` are pure | `metrics.py:7-13`; `scoring.py:1-15`; `check_import_boundaries.py` run output | High | Re-ran the checker |
| No clock reads in pure code | `check_import_boundaries.py:100-112`; explicit `scoring_cutoff_utc` params | High | AST check passes |
| Deterministic sampling, no RNG | `sampling.py:282-299, 507-556` | High | Only `hashlib` used |
| Census ≤100, 4 strata >100, 25/stratum | `sampling.py:426-499`; `models.py:43-46` | High | |
| Systematic `(offset, stride)` strata | `sampling.py:366-423`; `SRS-lean-v2.md:479-502` | High | Lean 1.0.2 change |
| Coveo endpoint + org id | `collector_coveo.py:128-131` | High | Captured |
| Free-text `q`/`query` forbidden | `collector_coveo.py:630-662, 772-778` | High | Recursive check |
| Five-field discovery set | `collector_coveo.py:163-169` | High | |
| Coveo retry/backoff/rate limit | `collector_coveo.py:151-153, 928-1089` | High | |
| Streamed discovery, one page in memory | `collector_coveo.py:24-26, 2016-2114` | High | |
| Failed page never zero assets | `collector_coveo.py:2079-2091, 1276-1290` | High | |
| GraphQL two operations | `collector_graphql.py:316-373` | High | |
| `operationName` correlation; position only if validated | `collector_graphql.py:622-899, 1640-1699` | High | |
| Per-operation independent status | `collector_graphql.py:515-553` | High | |
| Preflight gate blocks bulk enrichment | `pipeline.py:1088-1209, 3407-3429` | High | |
| One enrichment per unique identity | `pipeline.py:1269-1363, 1498-1585`; `database.py:73` | High | PK enforces |
| Composite weights 0.35/0.30/0.20/0.15 | `models.py:77-80`; `scoring.py:620-633` | High | |
| Coverage shrinkage toward 0.5 | `scoring.py:263-265`; `metrics.py:1614-1620` | High | |
| LOO midrank normalization | `scoring.py:273-347` | High | |
| Sensitivity over frozen candidate set | `scoring.py:1115-1173, 1399-1534` | High | |
| Sensitivity cannot change balanced score | `scoring.py:1627-1656`; `SRS-lean-v2.md:1148-1149` | High | |
| Page-view index = weekly view count | `metrics.py:406-495`; `SRS-lean-v2.md:752-764` | High | Lean 1.0.4 correction |
| Missing ≠ zero discipline | `metrics.py:88-122`; `models.py:3-4`; `database.py:12-16` | High | |
| Credentials from env only | `config.py:39-40, 280-292` | High | |
| Secrets never persisted/logged | `collector_graphql.py:1841-1928`; `check_secrets.py` run output | High | |
| Dashboard read-only, loopback | `cli.py:481-568`; `report.py:2662-2690` | High | |
| Report recomputes nothing | `report.py:6-9, 681-724` | High | |
| Tests use no live network | `tests/test_pipeline.py:1172-1194`; `tests/test_cli.py:569-596`; grep result | High | |
| 766 tests pass | `pytest -q` output | High | Ran |
| 89 requirements / 745 nodes traceable | validator output | High | Ran |
| Archify diagram matches source | `candidate.json` vs imports | High | One wording drift ("parallelism") |
| Archify revision is one commit behind HEAD | `candidate.json:11` (`603c429…`) vs `git log` (`eff5768`) | High | |
| `MAX_DISCOVERY_RESULTS_PER_CATEGORY` SRS says 2000, code says 9000 | `SRS-lean-v2.md:1334` vs `models.py:33`, `config/default.toml:16` | High | Documentation drift |
| Source docstrings cite retired `SRS-lean.md` line numbers | grep of 10 occurrences in `collector_coveo.py`/`collector_graphql.py` | High | Stale citations; IDs still valid |
| README describes only Chunk 0 | `README.md:1-18` | High | Stale |
| `tests/golden_vectors/` absent | glob of `tests/` | High | Named in `tests/AGENTS.md` only |
| URI trailing-identifier rule unverified | `AGENTS.md` open obligations; `collector_coveo.py:249-276` | High | Acknowledged in repo |
| No CI/coverage/strict typing | `pyproject.toml:24-40` | High | Deliberately deferred (`LREQ-NFR-060`) |
| Pipeline is 3,576 lines and imports private collector helper | file read; `pipeline.py:34-42` | High | Structural signal |
| No concurrency anywhere | read of `pipeline.py`, `collector_*.py` loops | High | Sequential |

---

### Final quality checks performed

- **Accuracy:** every formula was read from `metrics.py`/`scoring.py`, not paraphrased; the SRS was read directly and line-cited; contradictions (README staleness, constant drift, SRS-path drift, Archify revision) are reported rather than smoothed.
- **Analytical transparency:** the metric dictionary separates observed inputs from heuristic weights; heuristics are labeled as such.
- **Reproducibility:** the report distinguishes deterministic calculation, deterministic sampling, live-run identity, and post-upstream-change reproducibility — none is conflated.
- **Architecture:** module boundaries and dependency direction were verified against imports and the AST checker; the Archify map was validated against source.
- **Limitations:** §19 is explicit that sales/revenue/downloads/demand/conversion are not known and that "scores well" ≠ "will succeed".
- **Testing:** the no-live-network claim is supported by a socket sentinel and poisoned transports, and the suite was actually run.
- **Article readiness:** every non-trivial claim carries a file/function/line reference or an explicit uncertainty label; a second LLM can write from this without inventing behavior.

**Unverified in this report:** live upstream behavior (no network was used), the Archify HTML's visual quality (only the JSON spec and gate receipts were inspected), and the exact content of the `runtime/*.sqlite3` databases (schema was read from DDL, not from the binary files).
