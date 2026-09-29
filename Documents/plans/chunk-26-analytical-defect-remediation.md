# Chunk 26 — Analytical defect remediation (page-view semantics, rating missingness, sampling support, report rank)

Status: DRAFT — **not freezeable** until the operator answers §8 OQ-1…OQ-8.
Chunk id: `chunk-26` (remediation/follow-on; no §3/§4 dependency-map row — chunk-14/24/25 precedent).
Run log: `Documents/runs/chunk-26.md`.
Prerequisite: chunk-25, whose run log ends `GATE: PASSED` (`Documents/runs/chunk-25.md:246`); branch `chunk-25`.

Four confirmed defects are scoped here. Three of them (D1, D2, D3) require a
human policy/SRS decision before this plan can be frozen; D4 is a display-only
fix that is freezeable on its own. **Recommended split is in §1.4** — the four
defects do not belong on one branch as-is.

Provenance labels used below: **read** = file opened and quoted; **counted** =
queried by tool with the method stated; **lead-grounded** = supplied in the
dispatch brief from a read-only query of `runtime/niche_scout.sqlite3` and
`runtime/chunk25-run-report.html` and **not re-queried in this session**. Every
code and SRS claim below is **read**; the run figures were **re-verified by
counted read-only queries on 2026-09-29** (run log §"Live-DB verification") and
supersede the brief where they differ — see §2 item 3.

---

## 1. Scope and out of scope

### 1.1 In scope (four defects)

| # | Defect | Severity | LREQ IDs targeted |
|---|---|---|---|
| D1 | `page_view_semantics_status` is never detected (always `unvalidated`); the operator confirms the Unity field is trailing-7-days, so `product_page_views * 7 / age_days_exact` (a cumulative-lifetime numerator) is dimensionally wrong. | Blocker | LREQ-GQL-010, LREQ-GQL-020, LREQ-MET-040, LREQ-SCR-050, LREQ-EVD-020, LREQ-TST-060 |
| D2 | Unity's literal `0` for `rating.average` / `rating.count` on unrated assets is stored as `0.0` / `0`, not `None`; the adapter never produces a "no rating" state. | Blocker | LREQ-GQL-020, LREQ-GQL-050, LREQ-MET-090, LREQ-MET-100 |
| D3 | `SAMPLE_PER_STRATUM = 25` cannot reliably reach `QUALITY_MIN_ELIGIBLE_ASSETS = 5` in low-rating categories; observed quality-eligible rates as low as 2 %. | Major | LREQ-SMP-030, LREQ-SMP-040, LREQ-SMP-050, LREQ-MET-090 |
| D4 | `report._rank_from_sensitivity` returns the position in `ranking_sensitivity_json.ranked_categories` (base-candidate / input order), so the report's `rank` column is not the balanced-score rank and is inverted against the adjacent score column. | Major | LREQ-RPT-020, LREQ-SEN-020 |

### 1.2 Explicitly NOT in this chunk

- No formula, weight, threshold, or partition change **except** where a resolved
  OQ names one. D1's index formula and D3's per-stratum allocation each require a
  new sampling/formula revision; the SRS text change is an operator action (§5).
- No change to `metrics.py` / `scoring.py` purity: no I/O, no clock; rating
  missingness is produced in the I/O adapter (D2), never fabricated in a pure
  module.
- No change to the stored `ranking_sensitivity_json.ranked_categories` order or
  to any LREQ-SCR rule (D4 is display-only).
- No scheduling/history/resume/multi-user/cloud, no extra GraphQL fields, no
  favorites, no bulk enrichment, no confidence intervals, no configurable score
  weights (SRS §15, AGENTS.md "Out of scope").
- No live network in development or tests.

### 1.3 This is one plan for a bundle that is not one freezeable chunk

D1's field semantics were **resolved by the operator on 2026-09-29** (the field
is per-week; see §13) — the remaining D1 blocker is the operator-authorized SRS
formula/token revision, which no agent may apply. D3 changes the frozen §5.1
constants and the census boundary, which per SRS §5.1:463-465 forces a new
`SAMPLING_RULE_VERSION` and an SRS revision. D2 needs the exact rule/boundary
approved. D4 is independent and already fully specified.

### 1.4 Recommended split (operator to accept or override)

| Proposed chunk | Content | Freezeable now? |
|---|---|---|
| `chunk-26` | **D4 + D5** — report rank display fix + corrected formula text + golden re-baseline. No SRS edit, no runtime change. | Yes |
| `chunk-27` | **D2** — rating missingness at the `collector_graphql` mapping layer + downstream re-baseline. | After OQ-3/OQ-4 |
| `chunk-28` | **D1** — page-view semantics: weekly index formula, `validated_windowed_weekly` token, contract-seeded status, report caveats, and the full D/Q/rankability re-baseline + operator-authorized SRS revision. | Ready to plan; SRS edit is the operator checkpoint (§13) |
| `chunk-29` | **D3** — `SAMPLE_PER_STRATUM` + `ENRICHMENT_SAMPLE_SIZE_PER_CATEGORY` + census threshold + `SAMPLING_RULE_VERSION` bump + SRS §5.1/§14 edits + full sampling/coverage re-baseline. **Only if OQ-5 overrides "no change".** | Only after OQ-5/OQ-6/OQ-7 |

If the operator prefers a single branch, land D4 first (it is self-contained),
then D2, then D3, then D1, each at its own gate. **Do not land D3 and D4 in one
commit**: D3 moves every selection digest and sample member; D4 cannot.

### 1.5 Baseline verification (lead-run, 2026-09-29; recorded in the run log)

`python -m pytest -q` → **688 passed in 22.05s**; `validate_traceability` exit 0
(89 IDs, 666 nodes); `check_import_boundaries`, `check_scope_prohibitions`,
`check_secrets` exit 0; `ruff check src` → 80 **pre-existing** errors (not
chunk-26-introduced; the gate is "no new lint"). The live-DB re-verification of
every run figure is in `Documents/runs/chunk-26.md` §"Live-DB verification".

### 1.6 Analysis-only items (answered in §7; not necessarily changed)

- Whether D (demand) is meaningful while D1 and D2 stand (§7.1).
- The environment-vs-humanoids score spread (§7.2).
- Whether D2 alone makes furniture/weapons/land evaluable at 25/stratum (§7.3).

---

## 2. Conflict found with the dispatch brief (surfaced, not silently reconciled)

Two statements in the brief are **refuted by reading the source** and are
corrected here, because the plan must not propagate them. A third is a counted
discrepancy in the run figures:

1. **D4 mechanism.** The brief says `ranked_categories` is "sorted ascending by
   balanced score". It is **not**. `scoring.evaluate_sensitivity` sets
   `ranked_categories = candidates`, and `candidates` is
   `BaseCandidateSet.base_rankable_candidates`, which "follow[s] the caller's
   canonical `all_metrics` order" (`scoring.py:1156-1170, 1452, 1525`;
   docstring `scoring.py:843-845`). `all_metrics` is built in
   `run.categories` order (`pipeline.py:3467-3472`), i.e. the requested
   category order. The observed inversion (run-max `0.854` → rank 21, low
   `0.320` → rank 1) is therefore **input-order position**, which happens to be
   inverse to score in this run — not a score sort. The defect is real; the
   mechanism is different.
2. **D's rating path.** The brief lists "D's rating-midrank path" as a
   downstream consumer of `rating_average` / `rating_count`. **D does not
   consume either.** `demand_per_asset_raw` (`metrics.py:1302-1355`) and
   `demand_median_raw` (`metrics.py:1358+`) use only the age-normalized
   page-view index; LREQ-SCR-010 (`SRS:947-957`) defines
   `D0 = 0.60*P_ref(DemandPerAssetRaw) + 0.40*P_ref(DemandMedianRaw)`. The
   source of the belief is `report.py:112`'s fixed formula text, which says
   "D (demand) consumes the discovered page-view index **and rating
   signals**" — that text is itself inaccurate (recorded as defect candidate
   D5 below, not in §1.1).
3. **Run counts.** The brief reports "18 rankable, 3 provisional". The live DB
   says **17 rankable, 4 provisional, 3 not_rankable** (provisional:
   `2d/textures-materials/floors`, `3d/characters/creatures`, `3d/vehicles/air`,
   `3d/vehicles/space`; not_rankable: `3d/props/furniture`, `3d/props/weapons`,
   `3d/vehicles/land`). The brief's other figures — 1,559 / 289 / 123 / 305 / 416
   rating rows, 2,400 enrichment rows, 20 weak + 3 insufficient + 1 moderate,
   all 24 categories `unvalidated` — were **re-verified and match**. The counted
   values are the operative ones.

---

## 3. D1 — page-view semantics are never detected; the index numerator conflicts with the field's window

> **Superseded in part by §13 (operator ruling, 2026-09-29).** §3.1 (evidence) stands;
> §3.2 (operator decision required) is resolved by §13.2–§13.4. Read §13 before §3.2.

### 3.1 Confirmed evidence (read)

- Enum: `PageViewSemanticsStatus` allows exactly `unvalidated`,
  `validated_cumulative`, `contradicted` (`models.py:126-129`).
- Writers (grep `page_view_semantics_status` over `src/`): only
  `pipeline.py:3339` (run seed → `unvalidated`) and `pipeline.py:999-1007`
  (`persist_preflight`: rewrite `unvalidated` unless the current value is already
  `validated_cumulative` or `contradicted`). grep for `VALIDATED_CUMULATIVE`
  over `src/` returns only `models.py:128` (definition) and `pipeline.py:1001`
  (the read in the non-clobber condition). **No detector anywhere sets
  `validated_cumulative` or `contradicted`.** All 24 categories persisted
  `unvalidated` (report HTML, `page-view semantic status` column).
- Formula: `age_normalized_page_view_index = product_page_views * 7.0 / age`
  (`metrics.py:489`; SRS §7.2 LREQ-MET-040, `SRS:741-750`; definition `SRS:133`).
  The `* 7` presumes the numerator is cumulative lifetime views so that
  `views * 7 / days` is a weekly rate. If the field is already a trailing-7-day
  count, the numerator is windowed and the age division mixes units.
- SRS `SRS:133`: the index "is an unvalidated index, not a validated weekly
  traffic measurement or weekly traffic rate"; `SRS:57-58` and `SRS:1385`
  repeat the disclaimer. So the SRS *already* disclaims validation, but it does
  **not** license a formula whose numerator is windowed while the divisor is
  lifetime.
- Consequence of `contradicted` (SRS §6.3 `SRS:679-680`, §8.2 LREQ-SCR-050
  `SRS:985-987`, §9.1 LREQ-EVD-020 `SRS:1016-1023`): D and Q unavailable for
  **all** categories; `C` and `R` may remain; **no category is final rankable**.

### 3.2 Operator decision required

OQ-1 and OQ-2 in §8. Two SRS-conformant representations exist:

- **(a) `contradicted`.** The endpoint field is windowed, so the cumulative
  interpretation is false; record the run as `contradicted`. Per LREQ-SCR-050
  this makes D and Q unavailable run-wide and every category `not_rankable`.
  This is the literal SRS-conformant encoding of "the cumulative presumption is
  false". It is drastic (the current run would become entirely not-rankable).
- **(b) New validated token + redefined formula.** Add a
  `validated_windowed_7d` status (SRS §6.3 enumeration change) and redefine the
  index for a windowed numerator. This requires an SRS revision and a formula
  revision; no agent may author it.

### 3.3 Validation experiment (required before either representation is trusted)

The experiment needs live data and is therefore an **operator run**, not a dev
task. Design options (for OQ-2):

1. **Two-observation test.** Enrich one stable identity twice with a known
   interval between retrievals (e.g. two runs, or two `ProductPageViews` calls
   in one session). A cumulative counter is non-decreasing and its delta ≈ views
   added; a trailing-7-day counter can fall and is bounded by recent traffic.
2. **External anchor.** Compare the returned scalar to a directly observed
   product-page view figure for the same identity at the same time.
3. Record the capture (redacted) under `.scratch/` or a fixture is **not
   permitted** for a real response (no live capture exists in the repo; the
   identity-mapping rule 1.0.1 is also unverified — AGENTS.md open obligations).

### 3.4 Detector placement (only after OQ-1/OQ-2)

The run-level status is seeded in `pipeline.py` and is `NOT NULL` in
`runs` (`database.py:101`). Any detector must live in the I/O/orchestration
layer (pipeline/collector), never in `metrics.py`/`scoring.py`, because those
consume the status as an explicit parameter and must stay pure
(`metrics.py:796-797`, `scoring.py:520-524`). The comparison basis (what makes a
run "validated_cumulative" vs "contradicted") is exactly what the experiment in
§3.3 must establish; it is not derivable from the current repo.

### 3.5 Files (D1, once decided)

- `src/niche_scout/pipeline.py` — detector + write path (currently
  `999-1007`, `3339`).
- `src/niche_scout/models.py` — only if a new enum token is chosen.
- `src/niche_scout/metrics.py` — only if a new windowed index formula is chosen
  (LREQ-MET-040 rewrite; purity preserved).
- `Documents/SRS-lean-v2.md` — operator-applied revision only (no agent edit).
- Tests/fixtures: contradicted-path and detector-path nodes; the existing
  contradicted tests already exist (`tests/test_end_to_end.py:455-459`).

---

## 4. D2 — Unity's literal rating zeros are stored as real zeros, not "no rating"

### 4.1 Confirmed evidence (read)

- `collector_graphql._usable_number` (`collector_graphql.py:1062-1081`) returns a
  JSON `null` as `None` but passes a literal `0` / `0.0` through unchanged.
  `ProductDetailFields.rating_average: float | None` and
  `rating_count: int | None` are built from it (`:1239-1248, 1304-1313`).
- `metrics._classify_rating_average` (`metrics.py:280-295`) accepts `0.0` because
  `[0, 5]` is inclusive (`metrics.py:293`).
- `metrics._classify_rating_count` (`metrics.py:298-330`) rejects any count
  `< quality_min_rating_count` with `rating_count_below_minimum`.
- Lead-grounded run distribution: `rating_count == 0` → 1,559 rows;
  `rating_count == 1` with `rating_average == 0.0` → 289; `rating_count == 2` →
  123; only 305 rows have `rating_count >= 5`; 416 rows have `rating_count > 0`
  and `rating_average == 0.0`.
- SRS §1.2 (`SRS:92-93`): "Missing, invalid, contradictory, or unavailable
  values SHALL remain unavailable; they SHALL NOT be silently converted to
  zero." §6.4 LREQ-GQL-050 (`SRS:341-343`): failed fields remain null, never
  filled with zero. §6.4 (`SRS:619`) makes the same point for `product_page_views`.

### 4.2 Downstream consumers of `rating_average` / `rating_count` (read)

| Consumer | File:line | Effect of a wrong `0.0` / `0` |
|---|---|---|
| `_classify_rating_average` (eligibility) | `metrics.py:280-295` | `0.0` passes `[0,5]`; a genuine "no rating" is treated as a valid 0. |
| `_classify_rating_count` (eligibility) | `metrics.py:298-330` | `0` fails `< 5` → still ineligible at the default. |
| `quality_observation_eligibility` (order: rating_average then rating_count) | `metrics.py:623-631` | The count check, not the average, is what excludes unrated assets at the default. |
| `quality_raw` numerator `(rating_average/5) * index` | `metrics.py:1565, 1582-1585` | If `quality_min_rating_count` is lowered to ≤ the row's count, a stored `0.0` contributes a metric **zero-quality** observation instead of dropping it. |
| `pipeline.finalize_stratum_counts` → `u_quality_h` | `pipeline.py:1748-1758` | Counts follow the same eligibility. |
| Report display / audit rows | `report.py` rating columns | A `0.0` average is displayed as a real rating. |
| **Demand (`D`)** | `metrics.py:1302+`, LREQ-SCR-010 | **Does not consume ratings** (see §2, item 2). |
| `reference_usable_counts_json` | `scoring.py:141-152` | Counts peers by **field of raw metrics**, not by rating; unaffected by rating values. |
| `reviewCount` | requested/persisted but never consumed by scoring (grep over `src/`: only collector/model/database/pipeline draft) | Out of scope; noted only. |

**Key analytical consequence:** at the shipped default
`QUALITY_MIN_RATING_COUNT = 5`, every literal-zero row is already
quality-ineligible via the rating-count minimum, so D2 changes **no** quality
eligibility at the default. It is nonetheless a §1.2 violation in persisted
audit data, and it becomes a live scoring defect whenever
`quality_min_rating_count` is configured at or below an affected row's count
(chunk-25 recorded a run whose config snapshot had
`quality_min_rating_count = 3`).

### 4.3 Layer and rule (operator decision OQ-3 / OQ-4)

- **Layer:** `collector_graphql` ProductDetail mapping (I/O). Rejected
  alternatives: `metrics.py` (a pure module may not fabricate missingness —
  AGENTS.md Hard rule 1/2) and the database write (the distinction is already
  lost by then).
- **Proposed boundary** (OQ-4 asks the operator to confirm or amend):
  - `rating_count == 0` **and** `rating_average == 0` → both `None` (no-rating
    state; Unity's placeholder zero).
  - `rating_count == 0` **and** `rating_average > 0` → contradictory payload;
    record an issue and persist `None` (operator to confirm).
  - `rating_count > 0` **and** `rating_average == 0.0` → the 416-row case.
    Ratings are 1–5, so a rated asset cannot average 0. Decision needed: same
    no-rating state as row 1, or a **separate contradiction** recorded as an
    issue (OQ-4). If treated as a contradiction it is a different SRS state
    from "no rating" and must not be collapsed.
  - `rating_count > 0` **and** `rating_average` in `(0, 5]` → valid, unchanged.
  - Either `member` absent/`null` → `None` (existing behavior, unchanged).

### 4.4 Test / fixture re-baseline list (D2)

- `tests/test_collector.py` — `test_product_detail_rating_average_*`
  (`:4176-4210` region), the rating-null tests at `:2952-2953, 3007-3008`, and
  any payload asserting `rating_count == 0` round-trips as `0`.
- `tests/test_metrics.py` / `tests/test_validation.py` — the `[0, 5]` inclusive
  boundary test at `tests/test_validation.py:1747-1763` documents
  `rating_average == 0.0` as eligible; if the no-rating rule is adopted, a
  `rating_count == 0, rating_average == 0.0` case must expect the no-rating
  state, and the existing "explicit zero is eligible" case must keep a
  **non-zero** count.
- `tests/fixtures/*` — any observation fixture built with the literal
  `rating_average=0.0, rating_count=0` pair.
- `tests/traceability.json` — only if a new node ID is added.

---

## 5. D3 — `SAMPLE_PER_STRATUM` cannot support the quality gate in low-rating categories

### 5.1 Confirmed evidence (read + lead-grounded)

- Constants: `ENRICHMENT_SAMPLE_SIZE_PER_CATEGORY = 100`, `SAMPLE_STRATA = 4`,
  `SAMPLE_PER_STRATUM = 25` (`models.py:43-45`); the identity
  `ENRICHMENT_SAMPLE_SIZE_PER_CATEGORY = SAMPLE_STRATA * SAMPLE_PER_STRATUM` is
  frozen in SRS §5.1 (`SRS:457-459`). `CENSUS_POPULATION_THRESHOLD` is
  **derived** from `ENRICHMENT_SAMPLE_SIZE_PER_CATEGORY` (`sampling.py:69`), so
  changing either per-stratum constant silently moves the census boundary.
- SRS §5.1 (`SRS:463-465`): changing the sample size, stratum count,
  per-stratum allocation, or the partition rule **requires a new sampling-rule
  version and SRS revision**. §14 (`SRS:1324-1326`) marks
  `ENRICHMENT_SAMPLE_SIZE_PER_CATEGORY`, `SAMPLE_STRATA`, `SAMPLE_PER_STRATUM`
  as "No for v1" (not configurable).
- Gate that fails: quality is unavailable when
  `total_eligible < QUALITY_MIN_ELIGIBLE_ASSETS = 5` (`metrics.py:1591`;
  SRS §7.5 `SRS:853-869`), and `quality_stratum_eligibility_coverage` must reach
  `MIN_REQUIRED_COMPONENT_COVERAGE = 0.50` (`scoring.py:391-393`).
  `MIN_USABLE_SAMPLES_PER_STRATUM = 1` (chunk-25), so a stratum is usable iff it
  has ≥ 1 quality-eligible observation.
- Lead-grounded observed per-stratum `u_quality_h`:
  - `3d/props/weapons` `[0,1,1,0]` coverage 0.50, `usable_quality_count` 2
  - `3d/props/furniture` `[0,0,0,2]` coverage 0.25, count 2
  - `3d/vehicles/land` `[1,0,1,1]` coverage 0.75, count 3
  - All three are the run's `not_rankable` categories with
    `INSUFFICIENT_QUALITY_SAMPLE` (report HTML `detail-21`…`detail-23`, "missing
    components: Q").
- Lead-grounded observed quality-eligible rates (`rating_count >= 5`): min 2.0 %
  (furniture, weapons), max 41.0 % (fullscreen-camera-effects).

### 5.2 Sample-size arithmetic (shown)

Let `p` be the per-asset quality-eligible rate, `n = SAMPLE_PER_STRATUM`, and
`S = SAMPLE_STRATA = 4` strata of approximately equal population weight. With
`MIN_USABLE_SAMPLES_PER_STRATUM = 1` a stratum is usable with ≥ 1 eligible
observation.

Worst observed catalog, `p = 0.02`:

| Quantity | Formula | n=25 (current) | n=63 (min for count) | n=75 (proposed) | n=100 |
|---|---|---:|---:|---:|---:|
| Expected pooled eligible | `S·n·p = 0.08·n` | 2.0 | 5.04 | 6.0 | 8.0 |
| P(stratum usable) | `1-(1-p)^n` | 0.397 | 0.719 | 0.779 | 0.867 |
| Expected stratum coverage | `≈1-(1-p)^n` | 0.397 | 0.719 | 0.779 | 0.867 |

- **Pooled-count constraint (binding):** `S·n·p ≥ QUALITY_MIN_ELIGIBLE_ASSETS`
  → `4·n·0.02 ≥ 5` → `n ≥ 62.5` → **n = 63** is the arithmetic minimum.
- **Coverage constraint:** `1-(1-p)^n ≥ 0.50` → `n ≥ ln 0.5 / ln 0.98 = 34.3`
  → **n = 35**; not binding.
- **Recommendation:** `n = 75` (expected pooled 6.0, coverage 0.779) or
  `n = 100` (expected pooled 8.0, coverage 0.867). The dispatch's "75 → ~1.35"
  and "100 → ~2" are the **per-stratum** expected eligible (`n·p`, using
  `p = 0.018` for 75), i.e. one quarter of the pooled figure; the pooled figure
  is the one compared against `QUALITY_MIN_ELIGIBLE_ASSETS`. Method: closed-form
  expectation over a binomial stratum; no simulation was run.

**Blast radius if `SAMPLE_PER_STRATUM` changes (this is the reason for the
§1.4 split).** `ENRICHMENT_SAMPLE_SIZE_PER_CATEGORY` is a frozen identity
(`SRS:457-459`), so it must change with `SAMPLE_PER_STRATUM`; and because
`CENSUS_POPULATION_THRESHOLD` is derived from it (`sampling.py:69`), the census
boundary moves from 100 to 300 (`n=75`) or 400 (`n=100`). Every category with
`N` in `(100, 300]` / `(100, 400]` flips from "deterministic stratified sample"
to "census", changing `sample_is_census`, sample fraction, coverage, evidence
grade, and every selection digest. `SAMPLING_RULE_VERSION` must bump
(`SRS:463-465`; contrast chunk-25 Q2, where a *configurable policy default* did
not bump — this is a §5.1 sampling-rule change, so it does).

### 5.3 Runtime consequence (lead-recorded rate)

Recorded rate: ≈ 0.5 s per identity (`projected_minimum_enrichment_seconds =
1195.0` for 2,390 pending identities). Linear projection, before unique-identity
de-duplication:

| `n` | sampled/category | total sampled (24 cat.) | projected seconds | projected |
|---:|---:|---:|---:|---:|
| 25 (current) | 100 | 2,400 | 1,200 | 20 min |
| 75 | 300 | 7,200 | 3,600 | 60 min |
| 100 | 400 | 9,600 | 4,800 | 80 min |

These are **projections**, not measurements; `enrichment` is one request per
unique identity, so cross-category overlap can reduce them.

### 5.4 Test / fixture re-baseline list (D3)

- `tests/test_contracts.py::test_sampling_constants_contract` (`:561-569`) — the
  literal `100 / 4 / 25` and the identity assert.
- `tests/fixtures/sampling_fixtures.py` (`:28-30, 134-136, 263-300, 320-322`),
  `tests/fixtures/sampling_persistence_fixtures.py` (`:35-37, 270-338, 481-484`),
  `tests/fixtures/acceptance_fixtures.py` (`:50-52, 549-608`),
  `tests/fixtures/report_fixtures.py` (`:75-77`).
- `tests/test_sampling.py` (`:28-31, 184-192, 369-499`),
  `tests/test_end_to_end.py::…large category…` (`:301-305`),
  `tests/test_sampling.py::test_digest_changes_with_rule_version` (a version
  bump changes every selection digest → most sampling node expectations).
- Any golden vector whose expected selection set, `sample_fraction`,
  `sample_is_census`, coverage, evidence grade, or rankability depends on the
  sample size — this is a full re-capture, chunk-24/25 precedent.
- `tests/traceability.json` — only if new node IDs are added.

---

## 6. D4 — report `rank` column is not the balanced-score rank

### 6.1 Confirmed evidence (read)

- `report._rank_from_sensitivity` (`report.py:541-556`) returns
  `list.index(category) + 1` over
  `ranking_sensitivity_json["ranked_categories"]`.
- `ranking_sensitivity_json` is written by `pipeline._ranking_sensitivity_json`
  (`pipeline.py:2750-2760`): `"ranked_categories": list(sensitivity.ranked_categories)`.
  `SensitivityDiagnostics.ranked_categories` is exactly
  `BaseCandidateSet.base_rankable_candidates` (`scoring.py:1452, 1525`,
  docstring `:1241-1242`), which follows `all_metrics` (requested-category)
  order, **not** score order (`scoring.py:1156-1170`; `pipeline.py:3467-3472`).
  See §2, item 1.
- The real per-category rank is persisted beside it:
  `ranking_sensitivity_json["categories"]` is
  `[asdict(row) for row in sensitivity.categories]` (`pipeline.py:2755`), and
  `CategorySensitivityRank.rank_balanced` is the 1-based rank by **descending**
  balanced score with `(-score, category)` tie-break
  (`scoring.py:1229, 1460-1473, 1502`; `ranked_under_policy` `:1362-1396`).
- Report ordering: `_order_rows` sorts ranked rows by `(-rank, category)`
  (`report.py:530-538`), i.e. **worst rank number first**.
- Report HTML (read): the first data row is
  `<td>vfx/particles/environment</td><td>21</td><td>0.854457</td>…` — the run
  maximum score prints rank 21; `report.py:168-170`'s primary table places
  `rank` immediately before `composite score`. `not_rankable` rows print the
  rank cell as `unavailable` (they are absent from `ranked_categories`), which
  is correct and unchanged.

### 6.2 Fix (display only)

1. `report._rank_from_sensitivity` → read `decoded["categories"]` (a list of
   mappings), find the entry whose `category` matches, and return its integer
   `rank_balanced`. Fall back to `None` when the category is absent or the
   payload is malformed (same contract as today: `rank is None` → the
   `no rank recorded in ranking_sensitivity_json` note, `report.py:704-705`).
2. `report._order_rows` → sort ranked rows by `(rank, category)` **ascending**
   so rank 1 (best balanced score) renders first and the rank column is
   monotone with the score column. (Today's `-rank` only looked "best first"
   because the rank value was inverted; see §2 item 1.) This is a display
   choice, to be confirmed by OQ-8.
3. Do **not** change `scoring.py`'s stored `ranked_categories` order, the
   `rank_balanced` computation, or any LREQ-SCR rule.

### 6.3 Test / fixture re-baseline list (D4)

- `tests/fixtures/report_fixtures.py::ranking_sensitivity_json`
  (`:149-176`) currently emits `"categories": []` and drives rank from
  `ranked_categories` order; it must populate `categories` with
  `{"category": …, "rank_balanced": …}` entries. `scored_rows_for`
  (`:289-305`) builds its payload from it.
- `tests/test_report.py`:
  - `test_load_run_report_view_reads_primary_rows` (`:202-204`)
    `alpha.rank == 1`, `bravo.rank == 2`.
  - `test_load_run_report_view_orders_ranked_then_unranked` (`:244-274`) —
    expected `names == [BRAVO, ALPHA, CHARLIE, ZULU]` and the rank asserts; the
    order flips to `[ALPHA, BRAVO, CHARLIE, ZULU]` under ascending order.
  - `:547-548, :584-585` — `not_rankable` rows keep `rank is None`
    (no change expected).
- The `EMPTY_RANKING_SENSITIVITY_JSON = "{}"` fixture (`:179`) keeps returning
  `None` (no `categories` key).
- Any end-to-end/acceptance golden that asserts report row order or a rank cell.
- `tests/traceability.json` — unchanged unless a new node ID is added.

---

## 7. Analysis (answers to the "ALSO ANALYSE" questions)

### 7.1 Is D meaningful while D1 and D2 stand?

**D2 is irrelevant to D** (D consumes no rating — §2 item 2). **D1** undermines
D's *interpretation* but not its *within-run ordering*: D is built from
midranks `P_ref(DemandPerAssetRaw)` and `P_ref(DemandMedianRaw)` (LREQ-SCR-010),
and the `* 7` multiplier is a positive constant applied to every category, so it
cancels in the midrank. What does **not** cancel is the `1 / age_days_exact`
divisor: with a windowed numerator, windowed-views ÷ lifetime-days is a
spurious age penalty, so an old category with the same weekly traffic is
systematically ranked below a young one. D is therefore an **age-discounted
relative ordering of weekly page views**, not a demand rate, while D1 stands.

Corroborating check (design, not run): compute, for the same run,
`P_ref(weekly_views)` vs `P_ref(weekly_views * 7 / age_days_exact)`; if the two
rankings diverge materially, the age division — not the level — drives D. A
second check is the §3.3 two-observation test to confirm the numerator is
windowed. Until then D is a *directed* proxy only.

### 7.2 Environment `0.854` vs humanoids `0.320` — signal or artefact?

Raw inputs (report HTML, read): environment (`vfx/particles/environment`)
score `0.854457`, `D 0.93913`, `C 1.0`, `R 0.491304`, `Q 0.85`, discovered
population 203, demand-per-asset raw 0.46942, median raw 0.0611652, recent share
0.17064, median age 2113.71 days. Humanoids (`3d/characters/humanoids`) raw
demand-per-asset 0.314771, median 0.0389154, breadth 8276, recent share 0.240032,
median age 747.529 days.

It is **mostly artefact, in two parts**:

1. **Competition is structural.** `C = clamp(1 - P_ref(BreadthRaw), 0, 1)`
   (LREQ-SCR-020): the smallest catalog gets `C = 1.0` by construction, and the
   largest gets `C ≈ 0`. A 203-asset category beating an 8,276-asset category on
   C is definitionally built in, not discovered demand.
2. **Demand is the age-normalized index (D1).** Environment's D `0.939`
   co-exists with a *much older* median age (2113.71 vs 747.529 days); under
   `views * 7 / age` that is only possible because its raw page views are far
   higher. With the field windowed (D1), the 1/age term is spurious, so the D gap
   is inflated by the formula, not validated.

The `LREQ-RPT-050` caveats already say the index is not a weekly traffic rate
and midranks are not percentiles, but the report's *headline ordering* still
invites a demand reading. Conclusion: the spread is a **within-run heuristic
artefact of a small catalog plus an unvalidated index**, not a signal; it should
not be presented as "environment is the best niche".

### 7.3 Would D2 alone make furniture/weapons/land evaluable at 25/stratum?

**No. D3 is also required.** Their persisted `u_quality_h` are
`[0,0,0,2]` (furniture), `[0,1,1,0]` (weapons), `[1,0,1,1]` (land) →
pooled eligible 2 / 2 / 3, all `< QUALITY_MIN_ELIGIBLE_ASSETS = 5`, and
furniture's coverage 0.25 `< 0.50`. D2 converts literal-zero ratings to
`None`; because every affected row has `rating_count < 5`, it is already
quality-ineligible via the rating-count minimum, so D2 can only **remove**
observations (the 416 rows with `rating_count ≥ 5 and rating_average == 0.0`, if
a separate rule applies), never add any. At `n = 25` the expected pooled
eligible in a `p = 0.02` catalog is 2.0 (§5.2), so none of the three clears the
gate; `n ≥ 63` (recommended 75) is required. The three became `not_rankable`
because of sampling support, not because of the rating-zero collapse.

---

## 8. Open questions for the operator (blocking; no agent may resolve)

1. **OQ-1 (D1 representation) — RESOLVED 2026-09-29 (see §13).** Operator
   confirm: the Unity field is a per-week (trailing-7-day) view count; the
   project SHALL stop assuming cumulative lifetime views. Resolution: option
   **(b)** — a validated windowed token + redefined index — and **not**
   `contradicted` (§13.2). The remaining step is the operator-authorized SRS
   revision (§13.4), which no agent may apply.
2. **OQ-2 (D1 validation) — RESOLVED 2026-09-29 (see §13.3).** The semantics are
   operator-confirmed by direct observation; refresh cadence is stable within
   ≤30 min and assumed refreshed at most once per 24 h (daily granularity). A
   two-retrieval probe is optional corroboration, not a prerequisite. The
   identity-mapping rule 1.0.1 capture remains an independent open obligation.
3. **OQ-3 (D2 layer).** Confirm the `collector_graphql` ProductDetail mapping as
   the layer that produces the "no rating" state (so `metrics.py` stays pure).
4. **OQ-4 (D2 rule and the 416 rows).** Confirm the rule in §4.3, and decide
   whether `rating_count == 0 with rating_average > 0`, and the 416 rows with
   `rating_count > 0 and rating_average == 0.0`, are (i) the same no-rating
   state or (ii) a separate contradiction recorded as a validation issue.
5. **OQ-5 (D3 value).** Which `SAMPLE_PER_STRATUM` (arithmetic minimum 63;
   recommendation 75; or 100), and is the target the pooled
   `QUALITY_MIN_ELIGIBLE_ASSETS = 5` gate, the 0.50 coverage gate, or both?
6. **OQ-6 (D3 census boundary).** Accept that
   `ENRICHMENT_SAMPLE_SIZE_PER_CATEGORY` and `CENSUS_POPULATION_THRESHOLD`
   move with it (100 → 300 at n=75, 100 → 400 at n=100), flipping categories
   with `N` in `(100, 300]` / `(100, 400]` to census? If not, a separate
   sampling design is needed and this defect is out of one chunk's scope.
7. **OQ-7 (D3 versioning).** Confirm the required `SAMPLING_RULE_VERSION` bump
   and the SRS §5.1/§14 revision (contrast chunk-25 Q2: a configurable policy
   default did not bump; SRS §5.1:463-465 makes a sampling-rule change bump).
   Also confirm `SAMPLING_RULE_VERSION`'s new value.
8. **OQ-8 (D4 display order).** After the rank is the true `rank_balanced`,
   should the primary table render best-first (rank 1 top; `_order_rows` sorted
   ascending by rank, changing the order test) or worst-first (today's
   `-rank`)? Rank 1 = best is the recommendation.
9. **OQ-9 (split).** Accept the §1.4 split (D4 → D2 → D3 → D1), or one branch?
10. **OQ-10 (D5, side finding).** `report.py:112` states D "consumes … rating
    signals", which contradicts LREQ-SCR-010. Fix the fixed formula text in
    this chunk (trivial string), or leave it for a documentation chunk?

---

## 9. Verification commands (to be run by the lead after implementation; PowerShell)

1. `python -m pytest -q` — full suite; record pass/fail.
2. `python -m niche_scout.tools.validate_traceability` — exit 0 both directions.
3. `python -m niche_scout.tools.check_import_boundaries` — exit 0 (D2's adapter
   change must not move purity; D1 keeps `metrics.py` pure).
4. `python -m niche_scout.tools.check_scope_prohibitions` — exit 0.
5. `python -m niche_scout.tools.check_secrets` — exit 0.
6. `ruff check <changed files>` and `ruff format --check <changed files>`.
7. D4 live check: regenerate the report from `runtime/niche_scout.sqlite3` and
   confirm the run-max score's row prints rank 1 and the rank column is monotone
   with score (read-only; `niche-scout report` must not hit the network).

## 10. Files touched (allowlist per finalized sub-chunk)

| File | D | New/modified | Purpose |
|---|---|---|---|
| `src/niche_scout/collector_graphql.py` | D2 | modified | No-rating state from Unity's literal zeros |
| `src/niche_scout/models.py` | D1/D3 | modified | New semantics token (D1 option b) / sampling constants (D3) |
| `src/niche_scout/sampling.py` | D3 | unchanged (constant derived) | census threshold follows the constant |
| `src/niche_scout/pipeline.py` | D1 | modified | Semantics detector + write path |
| `src/niche_scout/metrics.py` | D1 option b | modified | Windowed index formula only |
| `src/niche_scout/report.py` | D4/D5 | modified | Rank from `rank_balanced`; order ascending; formula text |
| `Documents/SRS-lean-v2.md` | D1/D3 | operator-applied | §6.3 / §7.2 / §5.1 / §14 revisions |
| `tests/**` + `tests/fixtures/**` | all | modified | Re-baseline lists in §4.4/§5.4/§6.3 |
| `tests/traceability.json` | all | modified if new nodes | Matrix entries |
| `Documents/plans/chunk-26-…md`, `Documents/runs/chunk-26.md` | — | new | This plan and its log |

## 11. Gate bullets (from the dependency-map DoD for the affected LREQs; each needs command evidence)

- [ ] D4: report rank equals the persisted `rank_balanced`; the run-max score's
      row prints rank 1; rank column monotone with score; stored
      `ranked_categories` order unchanged; `not_rankable` rows still `None`.
- [ ] D2: a `rating_count == 0, rating_average == 0` payload round-trips as
      `None`/`None`; the 416-row rule matches OQ-4; `metrics.py` still pure
      (`check_import_boundaries` exit 0); no `or 0` / `.get(k, 0)` introduced.
- [ ] D3: `SAMPLE_PER_STRATUM` and `ENRICHMENT_SAMPLE_SIZE_PER_CATEGORY` agree
      with §5.1; `CENSUS_POPULATION_THRESHOLD` follows; `SAMPLING_RULE_VERSION`
      bumped; the three categories' expected pooled eligible meets the gate in
      §5.2 arithmetic.
- [ ] D1: a detector exists and is the only writer of a non-`unvalidated`
      status; `contradicted` makes D/Q unavailable and all categories
      `not_rankable`; `validated_cumulative` requires the OQ-2 evidence;
      `metrics.py`/`scoring.py` still consume the status as a parameter.
- [ ] `pytest` + the four validators exit 0; ruff no new lint.
- [ ] No SRS text edited by any agent; no out-of-scope feature (SRS §15).

---

## 12. Recommended answers (agent proposal — operator decision required)

**Status of this section: proposal only.** Nothing here is frozen, no `Status:` line is
changed, and no agent may act on it without the operator's sign-off. This section was
produced by a read-only verification pass that re-read the source and the cited SRS
sections; it does **not** re-query `runtime/niche_scout.sqlite3` (PowerShell is denied:
`{"permission":"bash","pattern":"*","action":"deny","source":"global"}`), so every
run-distribution figure quoted from the plan is **lead-grounded / unverified here** and
is labelled as such.

### 12.0 Independent verification of the two dispatch corrections (the plan's §2)

Both are **confirmed by reading the source**, and this section agrees with the plan:

1. **D4 mechanism.** `evaluate_sensitivity` sets `ranked_categories = candidates`
   (`scoring.py:1452`) and `ranked_categories=candidates` in the returned diagnostics
   (`scoring.py:1525`); `candidates` is `BaseCandidateSet.base_rankable_candidates`
   (`scoring.py:1167-1170`), appended in the order of `metrics` — i.e. `all_metrics`
   order. `all_metrics` is built by iterating `run.categories` (`pipeline.py:3467-3472`).
   `SensitivityDiagnostics.ranked_categories` is documented as exactly that set "same
   order" (`scoring.py:1241-1242`). The true balanced rank is `rank_balanced`, produced
   by `ranked_under_policy` sorting `(-score, category)` (`scoring.py:1362-1396`), mapped
   to `index + 1` (`scoring.py:1471-1473`) and stored per row (`scoring.py:1502`).
   `report._rank_from_sensitivity` returns `list.index(category) + 1` over
   `ranked_categories` (`report.py:541-556`), so it is the requested-category position,
   not the score rank. **Agree; the correction is right and D4 is a real display defect.**
2. **D does not consume ratings.** `demand_per_asset_raw` (`metrics.py:1302-1355`) and
   `demand_median_raw` (`metrics.py:1358-1402`) consume only page-view indices; LREQ-SCR-010
   (`SRS-lean-v2.md:947-957`) defines `D0 = 0.60*P_ref(DemandPerAssetRaw) +
   0.40*P_ref(DemandMedianRaw)`. The only place ratings enter scoring is `quality_raw`
   (`metrics.py:1565, 1582-1585`). The false statement is the fixed text at `report.py:112`
   ("...and rating signals"). **Agree; the correction is right and D5 is a real report-text
   defect.** `grep` of `tests/` for `rating signals` returns nothing, so D5 is
   test-free and safe to fix.

### 12.1 OQ-1 — D1 representation

Options ranked: **(1) defer: keep `unvalidated`, change nothing yet; (2) add a new
validated windowed token + redefined index; (3) set the run `contradicted`.**

**Recommendation: option 1 now; if OQ-2 later confirms the field is trailing-7-day, adopt
option 2, not option 3.**

- The repo holds **no captured response** (AGENTS "Open obligations"; dependency-map §6.4),
  and the SRS never asserts the field is cumulative — it calls the index "an age-normalized
  index with unvalidated semantics" (§16 item 5, `SRS:1385`; repeated `SRS:57-58`, `SRS:133`).
  `unvalidated` is a truthful, SRS-legal state (§6.3, `SRS:675-676`).
- `contradicted` is a positive claim with run-wide consequences: D and Q unavailable for all
  categories and no category final rankable (LREQ-SCR-050, `SRS:985-987`; §6.3, `SRS:679-680`;
  LREQ-EVD-020, `SRS:1016-1023`). Asserting it from an unrecorded operator recollection,
  with no capture, would itself violate the "do not guess a behavior" rule and the
  missing-not-zero discipline (AGENTS Hard rule 2; §1.2, `SRS:92-93`).
- If the windowed semantics **is** established, a trailing-7-day count is genuine demand
  evidence, so option 2 preserves a real signal while remaining truthful; option 3 discards
  valid signal and makes the whole run unusable. Option 3 is appropriate only if the operator
  decides the product must hard-stop every page-view-dependent score.
- **Caveat (independent finding):** no SRS requirement mandates an automatic page-view
  semantics *detector* in Lean v1. `grep -i semant` over the SRS returns only consumers and
  the enum (§6.3; §7.5; §8.2; §9.1; §9.2; §16), no detection procedure. So "never detected"
  is not by itself an SRS violation; the real exposure is the formula's numerator/divisor
  unit mismatch, which is an SRS defect needing an SRS revision — not an implementation bug
  an agent may fix.
- Blast radius if option 2: `models.py` enum token (`models.py:126-129`); `metrics.py`
  LREQ-MET-040 formula + docstring (`metrics.py:406-490`); a detector in `pipeline.py`
  (seed `pipeline.py:3339`, rewrite `pipeline.py:999-1007`); SRS §6.3/§7.2/§16 revision;
  tests. **No `SAMPLING_RULE_VERSION` bump** (the index is not a sampling-rule input,
  §5.1 `SRS:463-465`); **no `SCHEMA_VERSION` bump** (`database.py:54` — status is a string).
- Reversibility: option 1 trivial; option 2 needs the SRS revision and re-baselines D/Q and
  every rankability golden; option 3 is a one-line status change but destroys run utility.

### 12.2 OQ-2 — D1 validation experiment

Options ranked: **(1) two-observation test; (2) external anchor; (3) both.**

**Recommendation: option 1 as the primary experiment, with option 2 as corroboration if a
page-view figure is directly observable; run by the operator (it needs credentials/network),
never by an agent.**

- Two retrievals of one stable identity separated by a known interval: a cumulative counter
  is non-decreasing and its delta ≈ views added; a trailing-7-day counter can fall and is
  bounded by recent traffic. Record the redacted pair under `.scratch/` (project rules;
  never a real response as a fixture, and never a credential — LREQ-SEC-010/020).
- Fold in the **identity-mapping rule 1.0.1** URI extraction so one capture settles both open
  obligations (dependency-map §6.4; AGENTS "Open obligations"; `IDENTITY_MAPPING_RULE_VERSION`
  `models.py:26`).
- The experiment is **inconclusive if the identity's traffic is flat** (delta 0 fits both
  hypotheses): choose a known-active asset or a long enough interval.
- Output is an operator finding transcribed into the SRS revision; no agent edits the SRS.

### 12.3 OQ-3 — D2 layer

**Recommendation: confirm the `collector_graphql` `ProductDetail` mapping as the layer that
produces the "no rating" state.** `metrics.py`/`scoring.py` are pure and may not fabricate
missingness (AGENTS Hard rule 1/2; project-rules purity); `validation.py` is pure structural
validation and must not either; the database write is too late because the `0.0` is already
stored. The mapping point is `collector_graphql._usable_number`
(`collector_graphql.py:1062-1081`) and the `ProductDetailFields` construction
(`collector_graphql.py:1304-1316`). No version bump, no SRS revision.

### 12.4 OQ-4 — D2 rule and the 416 rows

Options for the contradictory rows ranked: **(1) a separate contradiction, `rating_average`
→ `None`; (2) the same no-rating state; (3) pass the literal `0.0` through.**

**Recommendation: option 1.** Proposed boundary at the mapping layer:

| Payload | Persist | State |
|---|---|---|
| `rating_count == 0` and `rating_average` in `{0, absent, null}` | `None`/`None` | no rating (placeholder zero) |
| `rating_count == 0` and `rating_average > 0` | `rating_average=None`, `rating_count=None` | **contradictory** — record a distinct issue |
| `rating_count > 0` and `rating_average == 0.0` (the 416 rows) | `rating_average=None`, keep the valid integer `rating_count` | **contradictory** — record a distinct issue |
| `rating_count > 0` and `rating_average` in `(0, 5]` | unchanged | valid |
| member absent/null | `None` | existing behavior, unchanged |

Why: §1.2 (`SRS:92-93`) and LREQ-GQL-050 (`SRS:341-343`) require missing/invalid/contradictory
values to remain unavailable, never zero; Unity ratings are 1–5, so a `0.0` average is not a
real value. The four states must stay distinct (AGENTS Hard rule 2), so row 1 (missing) and
row 3 (contradictory) **must not** be collapsed. Ranked rationale: (1) keeps them distinct and
conforms; (2) collapses a contradiction into missing (rejected); (3) is the current §1.2
violation (rejected).
- Analytic consequence: at the shipped default `QUALITY_MIN_RATING_COUNT = 5`
  (`models.py:61`), every literal-zero row is already quality-ineligible via the count minimum
  (`metrics.py:328-329`), so D2 changes **no** eligibility at the default; it corrects persisted
  audit data and matters only when the configurable `quality_min_rating_count` (SRS §14,
  Configurable = Yes) is ≤ an affected row's count.
- `metrics.py`'s inclusive `[0, 5]` check (`metrics.py:293`) is **kept**: LREQ-MET-090
  (`SRS:845-847`) says `rating_average` is finite in `[0, 5]`; the adapter, not the pure layer,
  is what refuses the placeholder.
- Blast radius: `collector_graphql.py` + `tests/test_collector.py` / fixtures only. **No
  `SAMPLING_RULE_VERSION`, no `SCHEMA_VERSION`** (rating columns already nullable). No SRS
  revision strictly required; a §4.2/§6.4 clarification is recommended but is operator text.
- Reversibility: high (adapter mapping). Unknown: the 416-row distribution is lead-grounded
  (not re-queried); the rule is defensive and does not depend on knowing Unity's intent.

### 12.5 OQ-5 — D3 value

Options ranked: **(1) no change, keep `SAMPLE_PER_STRATUM = 25`; (2) `n = 75`; (3) `n = 63`;
(4) `n = 100`.**

**Recommendation: option 1 — do not change `SAMPLE_PER_STRATUM`; record D3 as the SRS's
conservative guard firing, not an implementation defect.** If the operator overrides and
requires low-rating categories to be evaluable, then option 2 (`n = 75`).

- LREQ-MET-090 (`SRS:853-860`) and LREQ-EVD-020 (`SRS:1016-1023`) deliberately make quality
  unavailable below the eligible-count minimum and the category `not_rankable`. The observed
  `INSUFFICIENT_QUALITY_SAMPLE` for the three categories is exactly that guard; it is
  SRS-conformant behavior, and a within-run heuristic is *more* honest, not less, when it
  declines to score a category on 2 observations.
- The SRS freezes `n = 25` in LREQ-SMP-030 (`SRS:446-453`) and LREQ-SMP-050
  (`SRS:470-473`), and §14 marks it "No for v1" (`SRS:1324-1326`).
- Raising `n` has a real analytical **downside**: `CENSUS_POPULATION_THRESHOLD` is derived
  (`sampling.py:69`), so categories with `N` in `(100, 300]` (n=75) or `(100, 400]` (n=100)
  lose their census status and become sampled — degrading accuracy for mid-size categories,
  the opposite of the goal. Runtime also triples (~20 min → ~60 min at n=75; plan §5.3,
  projection only).
- If overridden: option 2 over 3 and 4 — `n = 63` is the bare arithmetic floor
  (`4·63·0.02 = 5.04`) with no margin; `n = 75` gives pooled ≈ 6.0 and coverage ≈ 0.779 at
  3× runtime; `n = 100` doubles runtime again for only ≈ 8.0/0.867. Any of 2–4 forces the
  full §5.1/§14 revision and a `SAMPLING_RULE_VERSION` bump, and re-baselines every selection
  digest, census flag, coverage, evidence grade, and rankability (plan §5.4).
- Non-recommended alternative: lowering the *configurable* `QUALITY_MIN_ELIGIBLE_ASSETS`
  (SRS §14 = Yes) per run weakens the evidence floor and still does not clear the coverage
  gate (furniture coverage 0.25 < 0.50), so it is not a clean fix.

### 12.6 OQ-6 — D3 census boundary

**Recommendation: conditional.** If OQ-5 is option 1 (no change), there is **no boundary
move** and OQ-6 closes with it. If `n` is raised, **accept** the move `100 → 300` (n=75) or
`100 → 400` (n=100); it is unavoidable because the `ENRICHMENT_SAMPLE_SIZE_PER_CATEGORY =
SAMPLE_STRATA * SAMPLE_PER_STRATUM` identity is frozen (`SRS:457-459`) and
`CENSUS_POPULATION_THRESHOLD` derives from it (`sampling.py:69`; LREQ-SMP-040 `SRS:467-468`).
Do **not** decouple the census threshold from the sample size: that breaks the frozen identity
and needs a separate sampling design, out of one chunk's scope. This downside is the main
reason to prefer OQ-5 option 1.

### 12.7 OQ-7 — D3 versioning

**Recommendation: conditional.** If OQ-5 is option 1, **no version bump and no SRS revision**.
If `n` changes, bump `SAMPLING_RULE_VERSION` (`models.py:27`, currently `"2.0.0"`) — recommend
`"3.0.0"` because every selection digest changes — and revise the SRS (§5.1, §14; recommend
Lean `1.0.4`), as SRS §5.1:463-465 explicitly requires ("Changing the sample size, stratum
count, per-stratum allocation, or the stratum partition rule requires a new sampling-rule
version and SRS revision"). This is **not** a `SCHEMA_VERSION` change (`database.py:54`); the
persisted stratum geometry is unchanged. Contrast chunk-25's `MIN_USABLE_SAMPLES_PER_STRATUM`
default change, which is not one of the §5.1 rule inputs and so did not bump
`SAMPLING_RULE_VERSION` (SRS went to Lean 1.0.3).

### 12.8 OQ-8 — D4 display order

Options ranked: **(1) best-first, `_order_rows` sorted ascending by `(rank, category)`;
(2) worst-first (today's `-rank`).**

**Recommendation: option 1.** Rank 1 is the best balanced score by LREQ-SEN-020
(`SRS:1110-1111`: "rank categories by descending composite score", ties by ascending lexical
category), and LREQ-RPT-020 places `rank` immediately before `composite score`
(`SRS:1149-1155`; `report.py:135-139`). Best-first makes the rank column monotone with the
score column. Today's `-rank` sort (`report.py:530-538`) only *appeared* best-first because
the rank value was the inverted input position (plan §2 item 1); once the rank is
`rank_balanced`, worst-first would render the best score last. Blast radius: `report.py`
(`_order_rows`, `_rank_from_sensitivity`), `tests/fixtures/report_fixtures.py::ranking_sensitivity_json`
(`:149-176`, currently emits `"categories": []`), and `tests/test_report.py`
(`:202-204`, `:244-274` — expected order flips to `[ALPHA, BRAVO, CHARLIE, ZULU]`). No
version bump, no SRS revision; fully reversible.

### 12.9 OQ-9 — split

**Recommendation: accept the §1.4 split, amended by the D3 finding.**
`chunk-26` = **D4 + D5** (both display-only, both `report.py`, freezeable now, no SRS edit);
`chunk-27` = **D2** (after OQ-3/OQ-4); **D3** = operator SRS decision first — if OQ-5 is "no
change", close it with a documented rationale and no branch, otherwise a dedicated `chunk-28`
with the full sampling re-baseline; `chunk-29` = **D1** (after OQ-1/OQ-2 and the operator's
live experiment). Rationale: the four defects have different version/SRS implications and
blast radii — D3 moves every digest and the census boundary while D4 moves none, so they must
not share a commit; and D1 cannot be planned at all until the OQ-2 experiment exists, so it
must not block D4/D2. D5 rides with D4 because both edit `report.py` and re-baseline report
fixtures.

### 12.10 OQ-10 — D5 formula text

Options ranked: **(1) fix in this chunk (with D4); (2) leave to a documentation chunk.**

**Recommendation: option 1.** `report.py:112` states D "consumes the discovered page-view
index and rating signals", which contradicts LREQ-SCR-010 (`SRS:947-957`) and the verified
source (`metrics.py:1302-1402`, no rating input). A false formula statement in shipped output
violates LREQ-RPT-030's "formulas or concise explanations" (`SRS:1157-1159`) and the honesty
framing of LREQ-RPT-050 (`SRS:1163-1170`), and conflicts with the AGENTS rule that the tool
must not claim more than it does. Blast radius: one string in `report.py`; no test asserts it;
no version bump, no SRS revision; trivially reversible.

### 12.11 Summary of versioning / reversibility

| Defect | Recommendation | `SAMPLING_RULE_VERSION` | `SCHEMA_VERSION` | SRS revision | Reversibility |
|---|---|---|---|---|---|
| D1 | defer; if confirmed, new windowed token + formula | no | no | yes (if changed) | medium |
| D2 | mapping-layer no-rating + contradiction | no | no | no (clarification recommended) | high |
| D3 | no change (fallback n=75) | only if changed | no | only if changed | low if changed |
| D4 | true `rank_balanced` + best-first | no | no | no | high |
| D5 | fix fixed formula text | no | no | no | high |

### 12.12 Not verified in this session

- All run-distribution figures (the 1,559 / 416 rating rows, per-stratum `u_quality_h`, the
  2 %–41 % eligible rates, the report HTML rank-21 row): **lead-grounded**, not re-queried —
  PowerShell/SQLite denied. The code-level defect *mechanisms* are verified.
- The operator's assertion that the Unity page-view field is trailing-7-day: **no captured
  response exists in the repo**; settled only by the OQ-2 experiment.
- Exact Unity placeholder intent for `rating_count > 0, rating_average == 0.0`: not in any
  capture; the OQ-4 rule is defensive and does not depend on it.

---

## 13. Operator ruling (2026-09-29) — D1 field semantics resolved; the index formula SHALL change

**This section supersedes §3.2 (OQ-1/OQ-2) and the D1 row of §1.4.** It is an operator
ruling on a fact and on the direction of the fix; the exact SRS wording remains the
operator's to authorize (§13.4), because no agent may edit `Documents/SRS-lean-v2.md`.

### 13.1 Recorded operator statements

1. "it is a fact that unity asset store page view are per week. i confirmed it myself."
2. "not sure when the view count changes, but waiting half an hour and refreshing the page,
   does yield the same number, maybe changes every 24 hours. so make the best assumption out
   of what we know, dont keep the broken assumption of the project."

### 13.2 Resolution of OQ-1 — representation

- The field is a **weekly (trailing-7-day) view count**, not cumulative lifetime views.
  The cumulative assumption behind `product_page_views * 7 / age_days_exact`
  (LREQ-MET-040) is **refuted by the operator** and SHALL be dropped.
- Representation: **a new validated token**, `validated_windowed_weekly`, added to the
  SRS §6.3 enumeration alongside `unvalidated`, `validated_cumulative`, `contradicted`.
  **Do not use `contradicted`**: `contradicted` is the encoding for "the endpoint
  contradicts the assumed semantics and page-view-dependent scoring must be disabled"
  (LREQ-SCR-050; §9.1), which would make D and Q unavailable run-wide and every category
  `not_rankable`. Here the semantics are **known and validated**, and a weekly count is a
  genuine demand signal; `contradicted` would discard that signal and make the product
  unusable. `validated_cumulative` is kept only for historical/backward-compatible rows.
- The run-level status is a **declared endpoint-contract value** seeded at run creation,
  not a per-run detector: no single response can distinguish a 7-day window from a
  lifetime counter. `pipeline.py` seeds the status from a module constant (e.g.
  `PAGE_VIEW_SEMANTICS_CONTRACT = PageViewSemanticsStatus.VALIDATED_WINDOWED_WEEKLY`)
  with a comment citing this ruling; the existing non-clobbering write
  (`pipeline.py:999-1007`) is retained. A future capture could flip the constant, but no
  detection logic is fabricated now.

### 13.3 Resolution of OQ-2 — refresh cadence and validation evidence

- Operator observation: the value is stable across a 30-minute refresh; it may change at
  most once per 24 hours.
- **Best assumption (recorded):** the counter is a trailing-7-day window refreshed at
  **daily granularity**. Consequences: the value is stable within a run (no within-run
  drift); a `retrieved_at_utc` already records the observation instant; cross-run
  comparability remains out of scope ("within-run" discipline, SRS §1.4).
- The validation basis is the operator's direct observation. An optional two-retrieval
  probe (same identity 24 h apart) is corroboration only, not a prerequisite. The
  identity-mapping rule 1.0.1 URI capture remains a separate open obligation
  (AGENTS.md; dependency-map §6.4).

### 13.4 Best-assumption formula and the required SRS revision

**Formula (best assumption):**

```text
weekly_page_view_index = product_page_views        # views in the trailing 7-day window
```

- Drop the `* 7 / age_days_exact` factor entirely. Any positive constant scaling (e.g.
  `/ 7` for a daily average) is immaterial to the demand midranks (`P_ref`) and to the
  quality ratio, so the un-scaled weekly count is the simplest faithful representation.
- `MIN_AGE_DAYS_FOR_RATE = 30` is **kept** as an eligibility floor (it is conservative:
  an asset ≥ 30 days old has a full 7-day window plus history). It no longer normalizes a
  rate; the SRS §7.2 sentence tying it to a rate must be reworded.
- Explicit zero views remains usable and yields `0` (a genuine zero weekly count).
- The public symbol name `age_normalized_page_view_index` is now a historical label;
  the plan recommends keeping the symbol to keep the diff bounded and documenting the
  rename in the SRS/docstring. A rename to `weekly_page_view_index` is an operator option
  (§13.6 OQ-11) because it ripples through every LREQ/test/golden reference.

**Proposed SRS edits (operator-authorized; no agent may apply them).** Line numbers are
current pre-edit (`Documents/SRS-lean-v2.md`, Lean 1.0.3).

| # | Section | Edit |
|---|---|---|
| D1-S1 | §1.4 definition (`SRS:133`) | Redefine "Age-normalized page-view index" as the **weekly page-view count** `= product_page_views` (trailing 7 days); state it is a weekly count and not a lifetime average or daily average. |
| D1-S2 | §7.2 **LREQ-MET-040** (`SRS:741-750`) | `age_normalized_page_view_index = product_page_views * 7 / age_days_exact` → `= product_page_views`; update the usable-conditions sentence so `MIN_AGE_DAYS_FOR_RATE` is an eligibility floor, not a rate normalizer. |
| D1-S3 | §6.3 enumeration (`SRS:675`) | Add `validated_windowed_weekly` to the allowed status values and state its meaning (validated trailing-7-day semantics). |
| D1-S4 | §10 **LREQ-RPT-050** (`SRS:1163-1170`) | Replace "the page-view index from a weekly traffic rate" with wording that the index **is** a trailing-7-day view count and is not a lifetime/cumulative or daily-average rate. |
| D1-S5 | §16 limitations item 5 (`SRS:1385`) | Update the "unvalidated semantics … not a validated weekly traffic measurement" wording to the validated weekly semantics. |
| D1-S6 | Appendix A formula block (`SRS:1442`) | `age_normalized_page_view_index = product_page_views`. |
| D1-S7 | Revision history + header (`SRS:10,18-21`) | New row/version (suggest Lean 1.0.4) recording the semantics correction. |

### 13.5 Versioning and blast radius

- `SAMPLING_RULE_VERSION` (`models.py:27`): **no bump** — the page-view semantics is not a
  §5.1 sampling-rule input (`SRS:463-465`).
- `ENDPOINT_CONTRACT_VERSION` (`models.py:25`, `"1.0.0"`): **review** — if it is defined to
  encode the page-view endpoint contract, bump it; the dependency map does not state its
  trigger, so this is flagged, not decided (OQ-12).
- `SCHEMA_VERSION` (`database.py:54`, `"1.2.0"`): the new token extends the
  `page_view_semantics_status` CHECK allow-list (`database.py:399-401`), which is part of
  the frozen schema. **Recommend `1.2.0 → 1.3.0`** unless the operator rules the enum
  allow-list out of schema versioning (OQ-13).
- Blast radius: `metrics.py:406-490` (formula + docstring), the `pipeline.py` seed and
  non-clobber write, `database.py` enum allow-list, `report.py` `HEURISTIC_STATEMENT`
  (`:48-60`) and `_FORMULA_EXPLANATIONS` (`:107-131`), every D/Q/rankability golden vector
  and scenario expectation, `tests/fixtures/*`, and the SRS edits above. A re-run of the
  24-category run moves D, Q, composite scores, evidence grades, and rankability for every
  category.
- Reversibility: medium — the formula and token are simple, but the re-baseline is broad.

### 13.6 New open questions from this ruling

- **OQ-11 (rename).** Rename the public symbol
  `age_normalized_page_view_index` → `weekly_page_view_index` (accurate but a broad
  rename), or keep the symbol and document the historical name (smaller diff)? Recommend
  keep + document.
- **OQ-12 (`ENDPOINT_CONTRACT_VERSION`).** Does the page-view contract change trigger a
  bump of `ENDPOINT_CONTRACT_VERSION` (currently `"1.0.0"`)? If yes, to what value?
- **OQ-13 (`SCHEMA_VERSION`).** Bump `1.2.0 → 1.3.0` for the added enum value, or rule the
  `_ENUM_COLUMNS` allow-list out of schema versioning? Recommend bump.
- **OQ-14 (report caveat text).** `report.py:55` ("the page-view index is not a weekly
  traffic rate") and `report.py:128` ("cumulative page-view signal") become false under
  §13.4 and MUST be reworded. Confirm the replacement wording (the report should say the
  index is a trailing-7-day view count, stable within a run, refreshed at most daily).

### 13.7 Effect on the §1.4 split

- D1 is now **freezeable to plan** (the fact is decided) and moves to `chunk-28`; its only
  human checkpoint is the SRS revision in §13.4 (operator action / operator-directed), plus
  OQ-11…OQ-14.
- `chunk-26` = **D4 + D5** (display + corrected D formula text) remains unchanged and
  independent: D4 relabels the rank; D5 fixes `report.py:112`. Neither depends on D1.
- D2 (`chunk-27`) is unchanged. D3 stays a documented "no change unless overridden"
  decision (`chunk-29` if overridden).

---

## 14. Operator ruling (2026-09-29) — all remaining questions decided

Operator instruction: "for other questions, go with what your sub-agent determined as best
answer." The recommendations in §12 and §13.6 are therefore **adopted**; OQ-1…OQ-14 are
closed. The D1-S1…D1-S7 SRS edits remain the only operator-applied checkpoint (§14.6).

### 14.1 Closed decisions

| OQ | Decision (adopted) |
|---|---|
| OQ-1 | New validated windowed token `validated_windowed_weekly`; index redefined as the weekly count. **Not** `contradicted`. (§13) |
| OQ-2 | Semantics operator-confirmed; daily refresh granularity assumed; optional probe is corroboration only. (§13) |
| OQ-3 | **`collector_graphql` ProductDetail mapping** produces the "no rating" state. |
| OQ-4 | Four states stay distinct: `count==0 & avg==0` → both `None` (no rating); `count==0 & avg>0` → contradiction (avg `None`, issue); `count>0 & avg==0` (the 416 rows) → **separate contradiction** (avg `None`, keep the valid count, issue); `count>0 & avg∈(0,5]` → valid. |
| OQ-5 | **No change: `SAMPLE_PER_STRATUM` stays 25.** D3 closes as SRS-conforming conservative behaviour. |
| OQ-6 | **No census-boundary move** (follows from OQ-5). |
| OQ-7 | **No `SAMPLING_RULE_VERSION` bump** and no §5.1/§14 SRS revision (follows from OQ-5). |
| OQ-8 | **Best-first**, `_order_rows` sorted ascending by `(rank, category)`. |
| OQ-9 | **Accept the amended split**: `chunk-26` = D4 + D5; `chunk-27` = D2; `chunk-28` = D1; D3 closed (no `chunk-29` unless OQ-5 is later overridden). |
| OQ-10 | **Fix `report.py:112`** ("D … and rating signals") in `chunk-26` with D4. |
| OQ-11 | **Keep the symbol** `age_normalized_page_view_index`; document the historical name. No rename. |
| OQ-12 | **Bump `ENDPOINT_CONTRACT_VERSION`** `1.0.0 → 1.1.0` (the page-view contract semantics change). |
| OQ-13 | **Bump `SCHEMA_VERSION`** `1.2.0 → 1.3.0` (the `page_view_semantics_status` CHECK allow-list gains `validated_windowed_weekly`). |
| OQ-14 | **Reword the report caveats** under D1: the index **is** a trailing-7-day view count, stable within a run, refreshed at most daily; not a lifetime/cumulative or daily-average rate. Applies to `report.py:55`, `report.py:128`, and the corresponding D1-S4/D1-S5 SRS wording. |

### 14.2 What this makes true

- `chunk-26` is **freezeable now**: D4 (rank from `rank_balanced`, best-first ordering) +
  D5 (`report.py:112`), both display-only in `report.py`, no SRS edit, no runtime change.
- `chunk-27` (D2) is **unblocked to plan**: OQ-3/OQ-4 fix the layer and the exact rule,
  including the 416-row contradiction.
- `chunk-28` (D1) is **unblocked to plan**: the formula, the token, the version bumps
  (OQ-11…OQ-13), and the report/SRS wording (OQ-14) are decided. Its only human checkpoint
  is applying D1-S1…D1-S7 to `Documents/SRS-lean-v2.md` (§14.6).
- D3 is **closed with no code change**; the three `not_rankable` categories remain a
  documented, SRS-conforming outcome, not a defect.

### 14.3 Corrections that follow from the adopted answers

- §7.3's last sentence ("`n ≥ 63` (recommended 75) is required") is now moot: D3 is not
  being changed. The three categories stay `not_rankable` at 25/stratum; D2 alone cannot
  make them evaluable (pooled eligible 2/2/3 < 5).
- §3.2's option (a) (`contradicted`) is rejected; only option (b) is operative.
- §5.2's arithmetic stands as evidence for the **rejected** option and must not be read as
  a planned change.

### 14.4 OQ-12 blast radius (new, from the adopted answer)

`ENDPOINT_CONTRACT_VERSION` is written to `runs.endpoint_contract_version`
(`pipeline.py:3336`) and is a frozen interface value; a bump re-baselines any fixture or
golden that pins `"1.0.0"`. Locate and update those in `chunk-28` (grep
`ENDPOINT_CONTRACT_VERSION` / `endpoint_contract_version` over `src/`, `tests/`,
`Documents/interfaces/`).

### 14.5 OQ-13 blast radius (new, from the adopted answer)

`SCHEMA_VERSION` (`database.py:54`) is compared against `schema_metadata.schema_version`
on open (`database.py:947-960`), so a bump **rejects an existing DB whose stored version is
older** unless the check is bypassed. The live `runtime/niche_scout.sqlite3` is at 1.2.0;
the D1 chunk must state how the version mismatch is handled for an existing audit DB
(re-run/rebuild, or an operator-approved migration note) — an open implementation detail
for `chunk-28`, recorded here so it is not discovered at gate time.

### 14.6 Remaining human checkpoint

The D1-S1…D1-S7 edits to `Documents/SRS-lean-v2.md` (§13.4). No agent may apply them; the
operator applies them (or directs a bounded, byte-exact script as in chunk-25) before
`chunk-28`'s gate. All other chunk-26/27/28 decisions are now settled.
