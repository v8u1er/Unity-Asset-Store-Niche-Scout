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
- A requirement may have an early **supporting contract** or pure primitive and a later **integration completion**. A chunk that defines a contract does not thereby claim to complete the runtime behavior of every requirement using that contract.
- Chunk ownership is described separately from the dependency table using these labels: **primary implementation chunk**, **supporting contract chunk**, and **integration completion chunk**. This prevents early validation and persistence work from being mistaken for complete adapter or orchestration behavior.
- The dependency graph is a DAG. The runtime path is shown separately from parallelizable protocol, fixture, persistence, and pure-function work.

For the early ownership cases that otherwise look contradictory in the table:

- Chunk 1 is the supporting contract chunk for identity, taxonomy, and value validation; Chunks 3 and 5 are the integration completion chunks for Coveo and GraphQL responses.
- Chunk 2 is the supporting contract chunk for sampling summaries, unique enrichment persistence, streaming, and redaction; Chunks 3, 4B, 6A, and 6B are the integration completion chunks.
- Chunk 6A is the primary implementation chunk for preflight planning and gating; Chunk 6B completes unique enrichment and reuse behavior.
- Chunk 7A supplies structural validation and metric-eligibility primitives; Chunk 7B completes the raw estimators. Chunk 9A produces pre-sensitivity evidence state and freezes base candidates; Chunk 9B completes sensitivity, final evidence, and final rankability.

---

## Ownership and test traceability matrix

The dependency tables above describe logical prerequisites. The following
machine-actionable matrix assigns every individual requirement a primary owner,
supporting chunks, an integration/completion chunk, and the required test
references. Ranges are intentionally not used in this matrix so that tooling
can validate coverage one `LREQ-*` at a time.

| REQ ID | Primary owner | Supporting chunks | Completion chunk | Required tests |
|---|---|---|---|---|
| LREQ-ARCH-010 | Chunk 0 | — | Chunk 0 | LREQ-TST-010, LREQ-NFR-040 |
| LREQ-ARCH-020 | Chunk 0 | — | Chunk 0 | LREQ-TST-010, LREQ-NFR-040 |
| LREQ-ARCH-030 | Chunk 10 | Chunk 0 | Chunk 10 | LREQ-TST-080, LREQ-TST-090 |
| LREQ-EXT-010 | Chunk 3 | Chunk 0, Chunk 1 | Chunk 3 | LREQ-TST-040, LREQ-TST-080 |
| LREQ-EXT-020 | Chunk 1 | Chunk 0 | Chunk 3 | LREQ-TST-080 |
| LREQ-EXT-030 | Chunk 3 | Chunk 1 | Chunk 3 | LREQ-TST-040, LREQ-TST-080 |
| LREQ-EXT-040 | Chunk 3 | Chunk 1 | Chunk 3 | LREQ-TST-040, LREQ-TST-080 |
| LREQ-EXT-050 | Chunk 3 | Chunk 1, Chunk 2 | Chunk 3 | LREQ-TST-040, LREQ-TST-080 |
| LREQ-EXT-060 | Chunk 3 | Chunk 1 | Chunk 3 | LREQ-TST-030, LREQ-TST-080 |
| LREQ-EXT-070 | Chunk 1 | Chunk 2 | Chunk 3 | LREQ-TST-030, LREQ-TST-080 |
| LREQ-EXT-080 | Chunk 3 | Chunk 1 | Chunk 3 | LREQ-TST-080 |
| LREQ-EXT-090 | Chunk 3 | Chunk 1, Chunk 2 | Chunk 10 | LREQ-TST-080 |
| LREQ-EXT-100 | Chunk 3 | Chunk 0 | Chunk 3 | LREQ-TST-040, LREQ-TST-080 |
| LREQ-GQL-010 | Chunk 5 | Chunk 0, Chunk 1 | Chunk 5 | LREQ-TST-040, LREQ-TST-080 |
| LREQ-GQL-020 | Chunk 5 | Chunk 1 | Chunk 5 | LREQ-TST-040, LREQ-TST-080 |
| LREQ-GQL-030 | Chunk 5 | Chunk 1 | Chunk 5 | LREQ-TST-040, LREQ-TST-080 |
| LREQ-GQL-040 | Chunk 5 | Chunk 1 | Chunk 5 | LREQ-TST-040, LREQ-TST-080 |
| LREQ-GQL-050 | Chunk 5 | Chunk 1, Chunk 2 | Chunk 5 | LREQ-TST-040, LREQ-TST-080 |
| LREQ-GQL-060 | Chunk 7A | Chunk 1, Chunk 5 | Chunk 7A | LREQ-TST-040, LREQ-TST-050 |
| LREQ-GQL-070 | Chunk 5 | Chunk 1 | Chunk 5 | LREQ-TST-030, LREQ-TST-040 |
| LREQ-GQL-080 | Chunk 6B | Chunk 2, Chunk 5, Chunk 6A | Chunk 6B | LREQ-TST-030, LREQ-TST-040, LREQ-TST-080 |
| LREQ-SEC-010 | Chunk 0 | Chunk 3, Chunk 5, Chunk 12 | Chunk 3, Chunk 5, Chunk 12 | LREQ-TST-080 |
| LREQ-SEC-020 | Chunk 2 | Chunk 0, Chunk 3, Chunk 5 | Chunk 13 | LREQ-TST-080, LREQ-NFR-060 |
| LREQ-ID-010 | Chunk 6A | Chunk 2, Chunk 4B, Chunk 5 | Chunk 6A | LREQ-TST-080 |
| LREQ-ID-020 | Chunk 6A | Chunk 1, Chunk 2, Chunk 5 | Chunk 6A | LREQ-TST-040, LREQ-TST-080 |
| LREQ-ID-030 | Chunk 6A | Chunk 0 | Chunk 6A | LREQ-TST-080 |
| LREQ-ID-040 | Chunk 6A | Chunk 2, Chunk 5 | Chunk 10 | LREQ-TST-080 |
| LREQ-SMP-010 | Chunk 4A | Chunk 1, Chunk 2, Chunk 3 | Chunk 4A | LREQ-TST-020, LREQ-TST-080 |
| LREQ-SMP-020 | Chunk 4A | Chunk 3 | Chunk 4A | LREQ-TST-020 |
| LREQ-SMP-030 | Chunk 4A | Chunk 0 | Chunk 4A | LREQ-TST-020 |
| LREQ-SMP-040 | Chunk 4A | Chunk 0 | Chunk 4A | LREQ-TST-020 |
| LREQ-SMP-050 | Chunk 4A | Chunk 4A | Chunk 4A | LREQ-TST-020 |
| LREQ-SMP-060 | Chunk 4A | Chunk 0 | Chunk 4A | LREQ-TST-020 |
| LREQ-SMP-070 | Chunk 4A | Chunk 4A | Chunk 4A | LREQ-TST-020 |
| LREQ-SMP-080 | Chunk 4B | Chunk 2, Chunk 4A | Chunk 4B | LREQ-TST-020, LREQ-TST-080 |
| LREQ-SMP-090 | Chunk 4A | Chunk 4A | Chunk 4A | LREQ-TST-020 |
| LREQ-MET-010 | Chunk 7A | Chunk 1, Chunk 5 | Chunk 7A | LREQ-TST-010, LREQ-TST-050 |
| LREQ-MET-020 | Chunk 7A | Chunk 0 | Chunk 7A | LREQ-TST-010, LREQ-TST-050 |
| LREQ-MET-030 | Chunk 7B | Chunk 4B, Chunk 7A | Chunk 7B | LREQ-TST-050 |
| LREQ-MET-040 | Chunk 7B | Chunk 5, Chunk 7A | Chunk 7B | LREQ-TST-050 |
| LREQ-MET-050 | Chunk 7B | Chunk 4B, Chunk 7A | Chunk 7B | LREQ-TST-050 |
| LREQ-MET-060 | Chunk 7B | Chunk 4B, Chunk 7A | Chunk 7B | LREQ-TST-050 |
| LREQ-MET-070 | Chunk 7B | Chunk 3, Chunk 4A, Chunk 7A | Chunk 7B | LREQ-TST-050 |
| LREQ-MET-080 | Chunk 7B | Chunk 5, Chunk 7A | Chunk 7B | LREQ-TST-050 |
| LREQ-MET-090 | Chunk 7B | Chunk 5, Chunk 7A | Chunk 7B | LREQ-TST-050 |
| LREQ-MET-100 | Chunk 7B | Chunk 5, Chunk 4B, Chunk 7A | Chunk 7B | LREQ-TST-050 |
| LREQ-NRM-010 | Chunk 8 | Chunk 7B | Chunk 8 | LREQ-TST-060 |
| LREQ-NRM-020 | Chunk 8 | Chunk 2 | Chunk 10 | LREQ-TST-060 |
| LREQ-NRM-030 | Chunk 8 | Chunk 8 | Chunk 8 | LREQ-TST-060 |
| LREQ-NRM-040 | Chunk 8 | Chunk 8 | Chunk 8 | LREQ-TST-060 |
| LREQ-SCR-010 | Chunk 8 | Chunk 7B | Chunk 8 | LREQ-TST-060 |
| LREQ-SCR-020 | Chunk 8 | Chunk 7B | Chunk 8 | LREQ-TST-060 |
| LREQ-SCR-030 | Chunk 8 | Chunk 7B | Chunk 8 | LREQ-TST-060 |
| LREQ-SCR-040 | Chunk 8 | Chunk 7B | Chunk 8 | LREQ-TST-060 |
| LREQ-SCR-050 | Chunk 8 | Chunk 5, Chunk 7B | Chunk 8 | LREQ-TST-060 |
| LREQ-SCR-060 | Chunk 8 | Chunk 8 | Chunk 8 | LREQ-TST-060, LREQ-TST-090 |
| LREQ-EVD-010 | Chunk 9A | Chunk 8 | Chunk 9A | LREQ-TST-060 |
| LREQ-EVD-020 | Chunk 9A | Chunk 3, Chunk 5, Chunk 6A, Chunk 7B, Chunk 8 | Chunk 10 | LREQ-TST-060, LREQ-TST-080 |
| LREQ-EVD-030 | Chunk 9A | Chunk 8, Chunk 9B | Chunk 9B | LREQ-TST-060, LREQ-TST-090 |
| LREQ-EVD-040 | Chunk 9B | Chunk 9A, Chunk 8 | Chunk 9B | LREQ-TST-060, LREQ-TST-070 |
| LREQ-EVD-050 | Chunk 9B | Chunk 9A, Chunk 8 | Chunk 9B | LREQ-TST-060, LREQ-TST-070 |
| LREQ-SEN-010 | Chunk 9B | Chunk 8, Chunk 9A | Chunk 9B | LREQ-TST-070 |
| LREQ-SEN-020 | Chunk 9B | Chunk 8, Chunk 9A | Chunk 10 | LREQ-TST-070 |
| LREQ-SEN-030 | Chunk 9B | Chunk 9A | Chunk 9B | LREQ-TST-070 |
| LREQ-SEN-040 | Chunk 9B | Chunk 8, Chunk 9A | Chunk 9B | LREQ-TST-070 |
| LREQ-RPT-010 | Chunk 11 | Chunk 8, Chunk 9B, Chunk 10 | Chunk 12 | LREQ-TST-080 |
| LREQ-RPT-020 | Chunk 11 | Chunk 4B, Chunk 8, Chunk 9B, Chunk 10 | Chunk 11 | LREQ-TST-080 |
| LREQ-RPT-030 | Chunk 11 | Chunk 4B, Chunk 7B, Chunk 9B, Chunk 10 | Chunk 11 | LREQ-TST-080 |
| LREQ-RPT-040 | Chunk 11 | Chunk 9A, Chunk 10 | Chunk 11 | LREQ-TST-080 |
| LREQ-RPT-050 | Chunk 11 | Chunk 4B, Chunk 9B, Chunk 10 | Chunk 11 | LREQ-TST-080 |
| LREQ-CLI-010 | Chunk 12 | Chunk 6A, Chunk 6B, Chunk 8, Chunk 10, Chunk 11 | Chunk 12 | LREQ-TST-080 |
| LREQ-CLI-020 | Chunk 12 | Chunk 11 | Chunk 12 | LREQ-TST-080 |
| LREQ-CLI-030 | Chunk 12 | Chunk 0 | Chunk 12 | LREQ-TST-080 |
| LREQ-CLI-040 | Chunk 12 | Chunk 1, Chunk 8, Chunk 9A, Chunk 10 | Chunk 12 | LREQ-TST-080 |
| LREQ-NFR-010 | Chunk 3 | Chunk 2 | Chunk 3 | LREQ-TST-080 |
| LREQ-NFR-020 | Chunk 6B | Chunk 2, Chunk 6A | Chunk 10 | LREQ-TST-080 |
| LREQ-NFR-030 | Chunk 10 | Chunk 3, Chunk 5, Chunk 6A, Chunk 6B | Chunk 10 | LREQ-TST-080 |
| LREQ-NFR-040 | Chunk 0 | Chunk 7A, Chunk 8 | Chunk 13 | LREQ-TST-010, LREQ-NFR-060 |
| LREQ-NFR-050 | Chunk 0 | — | Chunk 13 | LREQ-NFR-060 |
| LREQ-NFR-060 | Chunk 13 | Chunk 0 | Chunk 13 | LREQ-NFR-060 |
| LREQ-TST-010 | Chunk 13 | Chunk 0, Chunk 7A, Chunk 7B, Chunk 8 | Chunk 13 | LREQ-TST-010 |
| LREQ-TST-020 | Chunk 13 | Chunk 4A, Chunk 4B | Chunk 13 | LREQ-TST-020 |
| LREQ-TST-030 | Chunk 13 | Chunk 1, Chunk 5, Chunk 6B | Chunk 13 | LREQ-TST-030 |
| LREQ-TST-040 | Chunk 13 | Chunk 3, Chunk 5, Chunk 6A | Chunk 13 | LREQ-TST-040 |
| LREQ-TST-050 | Chunk 13 | Chunk 7A, Chunk 7B | Chunk 13 | LREQ-TST-050 |
| LREQ-TST-060 | Chunk 13 | Chunk 8, Chunk 9A, Chunk 9B | Chunk 13 | LREQ-TST-060 |
| LREQ-TST-070 | Chunk 13 | Chunk 9B | Chunk 13 | LREQ-TST-070 |
| LREQ-TST-080 | Chunk 13 | All runtime chunks | Chunk 13 | LREQ-TST-080 |
| LREQ-TST-090 | Chunk 13 | All analytical chunks | Chunk 13 | LREQ-TST-090 |

---

# 1. Requirement dependency map

## Architecture

| REQ ID | Module | Depends on LREQs | Pure/I/O | Test type | Edge cases |
|---|---|---|---|---|---|
| LREQ-ARCH-010 | `models.py`, `metrics`, `scoring` | — | Pure boundary | Architecture/import test; analytical tests | Typed structures only; no imports from collector/database/report/CLI; no file or network I/O |
| LREQ-ARCH-020 | `metrics`, `scoring` | LREQ-ARCH-010 | Pure | Determinism/unit test | No system-clock reads; timestamps must be supplied |
| LREQ-ARCH-030 | `metrics`, `scoring`, `pipeline` | LREQ-ARCH-010, LREQ-ARCH-020 | Pure plus orchestration | Repeated-input deterministic test; end-to-end test | Same inputs, policy versions, and configuration must produce structurally and numerically equivalent logical results; byte identity requires a separately defined canonical serialization |

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
| LREQ-GQL-060 | `validation.py`, `collector.py` | LREQ-GQL-020, LREQ-GQL-040 | Pure validation over I/O result | Eligibility unit/fixture test | Only `published` assets eligible for D, R, and Q; state-excluded and state-unknown assets remain in discovered breadth and persisted observations |
| LREQ-GQL-070 | `validation.py` | LREQ-GQL-020, LREQ-GQL-030, LREQ-GQL-040 | Pure | Identity mismatch unit test | Returned aliases disagree with requested identity; mismatch must invalidate affected result |
| LREQ-GQL-080 | `pipeline.py`, `collector.py`, `database.py` | LREQ-GQL-050, LREQ-GQL-070, LREQ-ID-040, LREQ-SMP-080 | Orchestration/I/O | Deduplication integration test | Cross-category overlap; at most one enrichment execution per unique identity per run, including successful preflight reuse; bulk enrichment is blocked until the preflight gate passes |

## Security

| REQ ID | Module | Depends on LREQs | Pure/I/O | Test type | Edge cases |
|---|---|---|---|---|---|
| LREQ-SEC-010 | `config.py`, `collector.py` | — | Environment/process I/O | Configuration and collector fixture test | Missing credentials; credentials required before network activity |
| LREQ-SEC-020 | `config.py`, `collector.py`, `database.py` | LREQ-SEC-010 | File/log/database I/O | Secret-redaction and repository check | No secrets in source control, logs, SQLite, or errors; `.env` ignored |

## Identity preflight

| REQ ID | Module | Depends on LREQs | Pure/I/O | Test type | Edge cases |
|---|---|---|---|---|---|
| LREQ-ID-010 | `pipeline.py`, `sampling.py` | LREQ-SMP-060, LREQ-SMP-080, LREQ-GQL-010 | Orchestration plus network I/O | Identity-preflight fixture test | At least 2 assets from 5 categories where possible; reduced coverage; categories with fewer than 2 assets |
| LREQ-ID-020 | `collector.py`, `validation.py`, `pipeline.py` | LREQ-ID-010, LREQ-GQL-010, LREQ-GQL-020, LREQ-GQL-030, LREQ-GQL-040, LREQ-GQL-050, LREQ-GQL-070 | Network I/O plus pure validation | Identity-preflight integration test | Chunk 6A invokes the Chunk 5 adapter for every preflight identity and validates both operations; request ID rejection, incompatible returned identity, page-view package mismatch, invalid correlation mode, and either-operation partial success |
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
| LREQ-SMP-080 | `sampling.py`, `database.py` | LREQ-SMP-040, LREQ-SMP-050, LREQ-SMP-060, LREQ-SMP-070 | Pure calculation plus disk persistence | Persistence integration test | Chunk 4B materializes `sample_members`, summaries, per-stratum `N_h`, `n_h`, and usable-count fields/placeholders; census versus sample; overlap counts; sample fraction distinct from coverage |
| LREQ-SMP-090 | `sampling.py` | LREQ-SMP-050 | Pure | Boundary unit test | Stratum below 25 selects every asset and records reduced count |

## Metrics

| REQ ID | Module | Depends on LREQs | Pure/I/O | Test type | Edge cases |
|---|---|---|---|---|---|
| LREQ-MET-010 | `validation.py`, `scoring.py` | LREQ-GQL-060, LREQ-GQL-070 | Pure | Eligibility unit test | Structural validation is supplied by Chunk 1; Chunk 7A owns metric eligibility semantics: null, malformed, wrong type, invalid range, future, naive, negative, non-finite, and excluded-state values |
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
| LREQ-EVD-030 | `scoring.py` | LREQ-EVD-020, LREQ-SCR-060, LREQ-NRM-020, LREQ-SEN-030 | Pure | Provisional-state golden test | Pre-sensitivity provisional decision plus sensitivity-driven provisional demotion; 8–20 categories; incomplete breadth fallback; weak coverage; high sensitivity |
| LREQ-EVD-040 | `scoring.py` | LREQ-EVD-020, LREQ-EVD-030, LREQ-SEN-030 | Pure | Rankability integration/golden test | Minimum 8 categories; strong reference requirement; sensitivity demotion without changing candidate set or score |
| LREQ-EVD-050 | `scoring.py` | LREQ-EVD-020, LREQ-EVD-030, LREQ-NRM-020, LREQ-SEN-030 | Pure | Evidence-grade golden test | Final grade is assigned after sensitivity; strong/moderate/weak/insufficient; census alternative; coverage and sensitivity affect grade |

## Ranking sensitivity

| REQ ID | Module | Depends on LREQs | Pure/I/O | Test type | Edge cases |
|---|---|---|---|---|---|
| LREQ-SEN-010 | `scoring.py` | LREQ-SCR-060, LREQ-EVD-020 | Pure | Policy unit test | Balanced, demand-heavy, and competition-heavy weights |
| LREQ-SEN-020 | `scoring.py`, `database.py` | LREQ-SEN-010, LREQ-EVD-020, LREQ-SCR-060 | Pure plus persistence | Sensitivity golden test | Chunk 9B returns a complete typed diagnostic; Chunk 10 persists it; ranks only the fixed `base_rankable_candidates`; top 3/top 5, deterministic tie-breaking, null when too few candidates, rank and score displacement |
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

The implementation is a directed acyclic graph rather than a single mostly
linear pipeline. The runtime path remains ordered, but protocol adapters,
validation primitives, persistence contracts, and fixture work can proceed in
parallel after their foundations exist.

```text
Foundation: typed models, constants, statuses, configuration contracts
    ├── pure taxonomy, identity, and value-validation primitives
    ├── SQLite schema, transaction, redaction, and persistence contracts
    ├── Coveo request/response protocol adapter
    ├── GraphQL protocol adapter and response correlation
    └── metric/scoring fixture contracts

Coveo adapter + persistence contracts
    ↓
Streamed raw discovery observations
    ↓
Canonical populations
    ↓
Deterministic sampling
    ├── sampling summaries and overlap metadata
    └── fixed sampled-identity set

GraphQL adapter + identity primitives + sampled identities
    ↓
Identity preflight planner and gate
    ├── failed → failed run; no bulk enrichment
    └── passed → unique enrichment executor and persistence

Persisted observations + scoring cutoff
    ↓
Eligibility/date/page-view primitives
    ↓
Sample-aware raw estimators
    ↓
LOO normalization → D/C/R/Q scoring
    ↓
Evidence and fixed base-rankable candidate set
    ↓
Sensitivity diagnostics → final evidence/rankability
    ↓
Pipeline result persistence → report read model → CLI/dashboard
```

The runtime order is therefore:

```text
discover → persist → canonicalize → sample → preflight → enrich → cutoff
→ metrics → normalize → score → base candidates → sensitivity
→ final evidence/rankability → persist results → report
```

The Coveo and GraphQL adapters may be developed in parallel after the
foundational contracts. Sampling is operationally downstream of persisted
discovery; preflight is downstream of sampling and the GraphQL adapter; bulk
enrichment is downstream of a successful preflight gate. Pure metric/scoring
Pure metric/scoring work and the report template, view-model contract, and
fixture renderer may proceed against frozen fixtures. Database-backed report
integration begins only after the final score, sensitivity, and failed-run read
models are frozen.
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
- typed domain/result structures, enums, statuses, and serialization contracts for the complete SRS data model
- constants and policy versions
- `RunStatus`: `running`, `completed`, `failed`
- discovery, identity-resolution, operation, score, evidence, and rankability statuses
- warning-code, correlation-mode, and page-view-semantic-status types
- `scoring_cutoff_utc` as an explicit pure-function input
- SQLite schema specification and repository protocol only; no SQLite implementation
- test fixture conventions
- pytest `lreq` marker registration and the machine-readable test-to-requirement matrix format

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
- Configuration precedence has a typed contract and fixture cases; behavioral CLI precedence tests are completed in Chunk 12.
- All required status values and mandatory logical row fields are represented by typed structures.
- The repository protocol and schema specification are defined without requiring SQLite behavior in this chunk.
- Every analytical test fixture has a traceability marker or matrix entry; missing markers fail the local test command.
- `.env` is ignored and `.env.example` contains no credentials.
- No network code is required yet.

---

## Chunk 1 — Pure taxonomy, identity, and response validation

**Goal:** Build pure validation primitives before writing network collectors; adapter-specific integration is completed in Chunks 3 and 5.

Implement:

- taxonomy file schema validation
- taxonomy freshness validation
- exact category-path matching
- canonical identity parsing
- URI identity fallback
- conflict/unresolved status handling
- GraphQL identity alias comparison
- structural validation primitives: malformed shape, wrong type, identity candidates, aliases, taxonomy shape, and redacted errors
- redacted error summaries

Requirements:

- LREQ-EXT-020
- supporting contracts for LREQ-EXT-060, LREQ-EXT-070, and LREQ-EXT-080
- supporting contracts for LREQ-GQL-060 and LREQ-GQL-070
- LREQ-MET-010

Tests:

- `test_validation.py`
- `test_identity.py`

Gate:

- All structural identity and taxonomy tests pass without network access.
- Invalid data is represented explicitly, never silently converted to zero or an ordinary asset.
- Validation functions accept typed data and return typed results.
- This chunk owns structural validity only; metric eligibility rules such as published-state, UTC/date, future-date, finite/non-negative, age, and page-view eligibility are owned by Chunk 7A.
- This chunk does not claim complete Coveo or GraphQL requirement behavior; those validators are applied to external responses in Chunks 3 and 5.

---

## Chunk 2 — SQLite implementation and repository behavior

**Goal:** Implement the audit trail and repository behavior before runtime discovery or sampling. Chunk 0 defines typed domain/schema contracts; this chunk owns the physical SQLite implementation.

Implement tables:

- `runs`
- `raw_discovery_observations`
- `sample_members`
- `enrichment_observations`
- `category_scores`

Implement:

- SQLite DDL, constraints, indexes, and logical primary/uniqueness rules, including `(run_id, category, asset_identity_key)` for samples and `(run_id, category)` for scores
- nullable page-view fields and run-level preflight/correlation/semantic-status fields
- structured JSON columns and redacted error summaries
- repository implementation, streamed insertion APIs, transactions/savepoints, and category-isolated transaction boundaries
- run/category status transitions that preserve unrelated category failures

Supporting contracts:

- persistence support for LREQ-SMP-080; physical sampling materialization is completed by Chunk 4B
- persistence support for LREQ-GQL-080
- persistence support for LREQ-NFR-010
- persistence support for LREQ-SEC-020

Gate:

- Pure sampling and scoring functions do not import or require SQLite.
- Duplicate sample membership is rejected.
- `(run_id, category)` is enforced for category scores.
- Secrets cannot enter persisted records.
- A failed category does not roll back unrelated category observations.
- Streaming insertion APIs and category-isolated transactions/savepoints are available to Chunks 3, 4B, 6A, and 6B.
- Behavioral verification of sampling summaries, unique enrichment, streamed discovery, and collector/error redaction remains in Chunks 3, 4B, 6A, and 6B.

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
- nullable/update lifecycle for post-discovery fields: `asset_identity_key` and `stratum_index` may be null during raw persistence; canonical identity, duplicate linkage, and stratum assignment are updated after canonicalization/sampling

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
- During discovery, persist every identity candidate, nullable canonical identity, identity-resolution status, nullable stratum index, and raw error metadata; after canonicalization/sampling, update canonical identity, duplicate linkage, and stratum index before inserting sample memberships.
- Discovery can process one category without loading the complete result set into memory.
- This chunk completes the Coveo-side integration of the validation primitives from Chunk 1; the primitive contracts alone do not satisfy LREQ-EXT-060 or LREQ-EXT-080.

---

## Chunk 4A — Canonical populations and deterministic sampling engine

**Goal:** Produce stable sample membership from validated canonical discovery records as a pure, deterministic result.

Implement:

- canonical population construction from persisted discovery observations
- ordinal ordering
- census behavior for `N <= 100`
- four-stratum behavior for `N > 100`
- SHA-256 NUL-delimited selection digest
- reduced final strata
- sample fraction and stratum summary structures

Requirements:

- LREQ-SMP-010 through LREQ-SMP-070 and LREQ-SMP-090

Tests:

- `test_sampling.py`
- sampling golden vectors

Gate:

- Repeated selection is identical.
- Changing the sampling-rule version changes the digest/selection.
- Populations 0, 1, 99, 100, and greater than 100 behave exactly as specified.
- Early, middle, and late discovery positions are represented.
- Sample fraction remains distinct from stratum eligibility coverage.
- The pure result includes all values required for later persistence, but this chunk does not claim physical SQLite materialization.

---

## Chunk 4B — Sample persistence, overlap, and sampling summaries

**Goal:** Materialize the pure sampling result into the audit trail and verify
that persisted values match the deterministic calculation.

Implement:

- `sample_members` materialization with selected identity keys or selection digest
- per-category sampling summaries and census status
- per-stratum `N_h`, `n_h`, `u_demand_h`, `u_recent_h`, and `u_quality_h` values or explicit placeholders until enrichment eligibility is known
- stratum boundaries, selected counts, sample fraction, and rule version persistence
- cross-category overlap counts and percentages after all category samples are selected
- persisted-value verification against the Chunk 4A pure sampling result

Requirements:

- primary implementation/completion for LREQ-SMP-080

Tests:

- `test_sampling_persistence.py`
- SQLite round-trip and overlap fixtures

Gate:

- Every selected sample has a persisted membership or reproducible digest.
- Per-category and per-stratum summaries survive a database round trip.
- Overlap is calculated from unique canonical identities after all samples are selected.
- Persisted sample fraction is distinct from per-stratum eligibility coverage.
- A pure sampling test cannot pass this gate without a corresponding persistence verification.

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
- state eligibility annotation; excluded and unknown-state assets remain in persisted observations and discovered breadth
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
- This chunk completes GraphQL response validation and correlation using the primitives from Chunk 1; it does not decide metric eligibility or bulk enrichment. Bulk identity/enrichment behavior remains in Chunks 6A and 6B.

---

## Chunk 6A — Identity preflight planner and gate

**Goal:** Select and validate a deterministic preflight set, persist its observations, and prevent bulk enrichment unless the gate passes.

Implement:

- deterministic preflight selection
- minimum category and asset policy
- unique-identity denominator
- invoke the Chunk 5 GraphQL adapter for the deterministic preflight set
- validate both ProductDetail and ProductPageViews operations for every preflight identity
- persist independent operation outcomes, selected correlation mode, and endpoint signature
- success/conflict rate calculations
- preflight persistence
- preflight failure gate

Requirements:

- LREQ-ID-010
- LREQ-ID-020
- LREQ-ID-030
- primary implementation for LREQ-ID-040

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
- Preflight rates use unique identities, not category references.
- Preflight executes the normal GraphQL request through the reusable Chunk 5 adapter; Chunk 5 supplies protocol behavior, while Chunk 6A supplies controlled execution and gate policy.
- Preflight status, summary, and observations are persisted before the gate returns.

---

## Chunk 6B — Unique enrichment executor and persistence

**Goal:** Enrich the unique sampled-identity union only after a successful preflight, reusing successful preflight responses and isolating asset failures.

Implement:

- successful preflight response reuse
- unique sampled-identity union across categories
- at most one enrichment execution per unique identity per run; a successful preflight observation counts as that identity's enrichment
- bulk enrichment only after successful preflight
- enrichment persistence coordination
- projected minimum enrichment-time calculation and pre-enrichment logging

Requirements:

- integration completion for LREQ-GQL-080
- LREQ-NFR-020
- LREQ-NFR-030

Tests:

- overlapping category samples
- response-reuse tests
- one-request-per-identity tests
- failed-asset isolation tests

Gate:

- Overlapping category samples cause at most one enrichment execution per unique identity.
- Successful preflight observations are not requested again.
- A failed asset does not abort unrelated assets.
- No bulk-enrichment request is issued when the preflight gate is failed or `insufficient`.

---

## Chunk 7A — Metric eligibility, date, and page-view primitives

**Goal:** Freeze the pure eligibility and time semantics used by every estimator.

Implement the metric-eligibility layer over Chunk 1's structural validation primitives:

- UTC normalization
- exact fractional age calculation
- page-view index
- published-state, identity, date, age, finite/non-negative, and range eligibility
- zero versus null versus invalid/unavailable behavior
- component-eligibility and zero-population rules

Requirements:

- LREQ-MET-010
- LREQ-MET-020
- supporting primitives for LREQ-MET-030, LREQ-MET-040, LREQ-MET-080, and LREQ-MET-090
- LREQ-ARCH-010
- LREQ-ARCH-020

Tests:

- `test_validation.py`
- date and eligibility golden vectors

Gate:

- All primitives are pure and receive `scoring_cutoff_utc` explicitly.
- No metric reads the current time.
- Exact fractional age is used.
- Zero is distinguished from null, invalid, and unavailable.
- Invalid values are excluded rather than converted to zero.
- Structural malformed-shape/type/alias checks remain owned by Chunk 1; this chunk owns the semantic decision about whether a value contributes to a metric.

---

## Chunk 7B — Sample-aware raw estimators

**Goal:** Implement the four raw signal families over frozen eligibility fixtures without database or network dependencies.

Implementation note: choose one explicit module convention before coding. If the lean structure keeps both layers in `scoring.py`, document and test two internal pure layers there: raw metric functions first, then normalization/component/evidence functions. Alternatively, split the raw metric layer into `metrics.py` and retain relative scoring in `scoring.py`; do not leave the architecture ambiguous.

Implement:

- DemandPerAssetRaw
- weighted DemandMedianRaw
- BreadthRaw
- RecentShareRaw
- weighted MedianAgeRaw
- QualityRaw
- component coverage
- stratum expansion weights
- exact weighted-median boundary behavior
- zero-population behavior

Requirements:

- LREQ-MET-030 through LREQ-MET-100
- integration completion for the LREQ-MET primitives supported by Chunk 7A
- LREQ-ARCH-030

Tests:

- `test_scoring.py`
- metric golden vectors
- zero-population and unequal-stratum fixtures

Gate:

- All estimators are pure and use the Chunk 7A eligibility results.
- Weighted medians use the exact boundary rule.
- Quality uses `N_h / n_h`, not a simple sample average.
- Zero-population metrics are null where specified and coverage is zero where specified.
- Sample fraction remains distinct from stratum eligibility coverage.

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

## Chunk 9A — Pre-sensitivity evidence checks and immutable base candidates

**Goal:** Validate pre-sensitivity evidence, construct the immutable candidate set,
and produce an internal preliminary decision object before sensitivity is evaluated.

Implement:

- score-state versus rankability-state handling
- evidence input validation and pre-sensitivity evidence eligibility
- field-specific support checks
- fixed `base_rankable_candidates`
- preliminary `not_rankable` and `provisional` decisions
- `pre_sensitivity_evidence_state` and preliminary rankability state; these are not silently treated as final persisted evidence fields
- the rule that sensitivity cannot create candidates or mutate the balanced score

Requirements:

- LREQ-EVD-010 through LREQ-EVD-030 as pre-sensitivity decision work
- supporting contract for LREQ-SEN-030

Tests:

- evidence/rankability matrices
- candidate-set construction tests
- provisional/not-rankable golden vectors

Gate:

- The base candidate set is frozen before any alternate policy is ranked.
- Score state, pre-sensitivity evidence state, and preliminary rankability status remain distinct.
- Categories with insufficient support are excluded from the base candidate set without changing their stored score fields.
- No final evidence grade is persisted by this chunk when sensitivity is an input to the final grade.

---

## Chunk 9B — Sensitivity, final evidence, and final rankability

**Goal:** Evaluate alternate policies only over the fixed base candidate set, then
assign final evidence and rankability states.

Implement:

- balanced, demand-heavy, and competition-heavy policies
- deterministic rank tie-breaking
- top-3 and top-5 stability
- score/rank displacement
- warning thresholds
- final `evidence_grade` using coverage, integrity, reference size, semantics, and sensitivity
- final rankability after sensitivity

Requirements:

- LREQ-SEN-010 through LREQ-SEN-040
- integration completion for LREQ-EVD-030, LREQ-EVD-040, and LREQ-EVD-050

Tests:

- sensitivity golden vectors
- candidate-set immutability tests
- rankability transition tests

Gate:

- Sensitivity never adds or removes candidates.
- Sensitivity never modifies the balanced primary score.
- A sensitivity warning demotes final rankability only as specified.
- Insufficient candidate counts produce the explicitly defined null outputs.
- `final_evidence_grade` and `final_rankability_status` are assigned here after sensitivity; Chunk 10 persists the complete result.
- Final rankability is assigned only after sensitivity is computed.

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
15. Compute final evidence and rankability from the sensitivity result.
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
- Runs with fewer than `MIN_CATEGORIES_PER_RUN` categories (configured as 8) are rejected before ranking.
- Configuration or taxonomy failure causes no network request.
- If identity preflight fails: persist `run.status = failed`, retain discovery/sample/preflight observations, issue no bulk-enrichment requests, skip metric/score/ranking computation, persist category limitations where possible, produce no rankable scores, allow the dashboard to display the failed run as an audit/diagnostic report, and return a non-zero CLI exit code.
- Category-level failure is represented internally by a typed `CategoryStatus` (`healthy`, `degraded`, `failed`) and mapped to `discovery_status`, warnings, `evidence_grade`, and `rankability_status`; it is not a separate persisted enum unless the schema explicitly adds that field.
- On preflight failure, the report read model uses one null-score `category_scores` row per requested category with persisted discovery/sample fields, `evidence_grade = insufficient`, `rankability_status = not_rankable`, and explicit preflight warnings. If implementation instead omits those rows, Chunk 11 must join runs, discovery, samples, and preflight observations to provide the same one-row-per-category view.
- 8–20 category runs may compute provisional scores, but have no rankable candidate set and null sensitivity stability values.

---

## Chunk 11 — Report renderer and read-only dashboard

**Goal:** Expose completed and failed runs as read-only audit/diagnostic views without initiating unexpected network activity.

Implement:

- database read model
- `report.py` renderer
- read-only dashboard
- sortable primary table
- category detail panel
- warnings and limitation vocabulary
- display of non-rankable categories
- failed-run read model: prefer one null-score row per requested category with discovery/sample fields, `insufficient` evidence, `not_rankable` status, and explicit preflight warnings; if rows are absent, provide an equivalent join over `runs`, discovery, sample, and preflight observations

Requirements:

- LREQ-RPT-010 through LREQ-RPT-050

Gate:

- `dashboard` performs database reads only.
- Reports include every mandatory score, sample, coverage, evidence, and sensitivity field.
- Non-rankable categories remain visible.
- Failed preflight runs remain visible as audit/diagnostic reports even when no metric or score rows were computed.
- Report fixtures assert the required distinctions between pagination completion and immutable snapshot completeness, page-view index and weekly traffic rate, midranks and inferential percentiles, sample fraction and stratum eligibility coverage, deterministic evidence and statistical confidence, and heuristic output versus sales/revenue/conversion/traffic-rate claims.
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
- Every analytical test contains an explicit LREQ marker, missing markers fail local test execution, and a machine-checkable bidirectional traceability check verifies that every required test maps to valid individual `LREQ-*` IDs and every individual `LREQ-*` has at least one required test reference.
- No stale requirement from the retired SRS is accidentally implemented.

---

# 4. Recommended execution order

The safest implementation order is:

```text
Chunk 0  Foundation
Chunk 1  Pure validation and identity
Chunk 2  SQLite schema and persistence contracts
Chunk 3  Coveo discovery
Chunk 4A Canonical populations and deterministic sampling
Chunk 4B Sample persistence and overlap
Chunk 5  GraphQL protocol adapter
Chunk 6A Identity preflight planner and gate
Chunk 6B Unique enrichment executor and persistence
Chunk 7A Eligibility, date, and page-view primitives
Chunk 7B Sample-aware raw estimators
Chunk 8  Normalization and scoring
Chunk 9A Pre-sensitivity evidence and base candidates
Chunk 9B Sensitivity, final evidence, and final rankability
Chunk 10 Pipeline
Chunk 11 Report renderer and read-only dashboard
Chunk 12 CLI commands and configuration precedence
Chunk 13 Acceptance and quality gates
```

After Chunk 0, Chunks 1, 2, 5, and the metric fixture interfaces can proceed in parallel. After Chunks 1 and 2, the Coveo adapter and GraphQL protocol adapter can proceed in parallel. Sampling is operationally downstream of persisted discovery: 4A computes the pure result and 4B materializes it; preflight is downstream of 4B and the GraphQL adapter; bulk enrichment is downstream of a successful preflight gate. Chunks 7A and 7B may proceed against frozen fixtures while collection adapters are built. The networked collectors should not be the first implementation target: they depend on canonical identity rules, taxonomy validation, status modeling, persistence contracts, and fixture contracts.

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
10. **Map every implementation test back to one or more individual `LREQ-*` IDs and enforce the mapping mechanically.**
11. **Use structurally and numerically equivalent logical results for determinism; require byte equivalence only if a canonical serialization format is separately specified.**

## 6. Implementation clarifications from independent review

### 6.1 Run and category status are separate

Preflight failure marks the run as `failed`, while affected categories may also be shown as `not_rankable`. Category failure, preflight failure, run failure, score state, evidence grade, and rankability status must remain distinct fields rather than being collapsed into one status.

### 6.2 Eight-to-twenty-category runs

Runs with 8–20 categories may calculate provisional scores, but they do not produce a rankable candidate set. For those runs, `base_rankable_candidates` is empty and `top_3_stability`, `top_5_stability`, and related sensitivity outputs are `null`. The report must show provisional scores without presenting them as a ranked recommendation set.

### 6.3 Empty sensitivity candidate sets

Sensitivity is evaluated only over the fixed `base_rankable_candidates` set. If that set is empty or too small for a stability statistic, sensitivity does not independently create candidates or alter the balanced score. The null contract is explicit:

- `top_3_stability = null` when fewer than 3 base candidates exist.
- `top_5_stability = null` when fewer than 5 base candidates exist.
- `maximum_score_delta = null` and `maximum_rank_displacement = null` when there are no base candidates or no comparable policy ranks.
- `sensitivity_warning = null` when the required sensitivity statistic cannot be computed; it is not `false` or zero.
- `ranking_sensitivity_json` retains an explicit empty-candidate or insufficient-candidate status rather than becoming an empty, ambiguous object.

### 6.4 Runtime invariant

The complete runtime order is:

```text
discover → persist → canonicalize → sample → preflight → enrich → cutoff → score → sensitivity → report
```

The GraphQL protocol adapter may be implemented before preflight, but it must not execute bulk enrichment until the preflight-controlled executor has passed the gate.

### 6.5 Category failure representation

Category-level failure is represented through `discovery_status`, warnings,
`evidence_grade`, and `rankability_status`; run-level `status` remains separate.
If implementation needs a standalone category state, it must add and document a
typed `category_status` field rather than overloading discovery or rankability.

### 6.6 Test traceability contract

Every analytical test must contain an explicit individual `LREQ-*` marker, for
example `@pytest.mark.lreq("LREQ-SMP-060")`, or be listed in a machine-readable
test-to-requirement matrix. Chunk 13 must verify both directions: every required
test has at least one valid LREQ marker, and every individual LREQ has at least
one required test reference.

This plan exposes the primary hidden dependency: the difficult networked parts are downstream of deterministic taxonomy, identity, sampling, status, and persistence contracts. Implementing those foundational pieces first substantially reduces the risk of building a collector that produces data the scoring layer cannot safely interpret.