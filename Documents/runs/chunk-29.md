# Chunk 29 run log — Coveo retrieval-window coverage remediation

Branch: `chunk-29` (created from `main`; originally created as `chunk-14`, renamed to `chunk-29` — 14–28 are already used).

## Origin

`breadth_raw` for `3d/characters/humanoids` was 8,291 while only 4,948 distinct assets were
discovered. User-confirmed facts:

- Store page and live Coveo response: `totalCount = totalCountFiltered = 8294` (real catalog size).
- Storefront caps at page 53 × 96 = 5,088; every stored run stops at exactly 4,992 rows.
- The tool reports `complete` / `bounded=1` / `rankable` with no warning.
- Cause: `_has_read_enough` (collector_coveo.py:2194) and `_endpoint_may_hold_more`
  (collector_coveo.py:2219-2220) treat an empty page as exhaustion without reconciling
  the read cover against the verified `totalCount`.

## Operator rulings

1. Authorized two SRS edits (Lean 1.0.5): `LREQ-EXT-050` exhaustion/reconciliation addendum, and
   `DISCOVERY_INCOMPLETE` added to Appendix C warning vocabulary.
2. Operator delegated the `_endpoint_may_hold_more` / `_breadth_verified_total` consistency
   contradiction fix to lead discretion.
3. New chunk (29); dispatch subagents.

## Stages

| Stage | Status | Notes |
|---|---|---|
| Preflight | DONE | `git status` clean on `main`; SRS pre-edit sha256 `6903b8da128e…f55b` |
| SRS edits (operator-authorized) | DONE | post-edit sha256 `2d81d8d0618b…c878`; §4.1 addendum + Appendix C `DISCOVERY_INCOMPLETE` |
| Branch | DONE | `chunk-29` |
| Plan | DONE | `Documents/plans/chunk-29-discovery-window-coverage-remediation.md`; committed `4354d48` |
| Plan questions resolved | DONE | Operator chose Q1-(a) new field `unreconciled_total_shortfall` (amends frozen `interfaces/chunk-03.md`, additive/defaulted) and Q2-(a) strict `persisted < verified_totalCount` |
| Tests first | DONE | test-author; committed `8455539`. Lead ran suite: `5 failed, 712 passed`; all 5 failures are missing-implementation only (AttributeError on `unreconciled_total_shortfall` / `WarningCode.DISCOVERY_INCOMPLETE`), no syntax/collection errors. The 2 metric/scoring fallback tests already pass (existing chain). `validate_traceability`: 696 matrix nodes, valid. |
| Implement | DONE | impl-deep; committed `81bcd1b`. Added `_verified_total_shortfall`, post-loop reconciliation (empty/short terminal page with unreconciled verified total → `TRUNCATED` + shortfall), `CategoryDiscoveryResult.unreconciled_total_shortfall`, `WarningCode.DISCOVERY_INCOMPLETE`, `pipeline._warning_codes` emission. |
| Interfaces + plan freeze | DONE | committed `e097961`; `chunk-00.md` (WarningCode), `chunk-03.md` (field + note), `chunk-10.md` (§6 note); plan frozen Q1a/Q2a. |
| Tests (remaining vectors + pipeline) | DONE | committed `2da5763`; 6 nodes + default-preserving fixture variant. |
| Lead verification | DONE | `python -m pytest -q` → **723 passed, 0 failed**; `validate_traceability` → 702 matrix nodes, valid; `check_import_boundaries` → valid; `ruff --select F,E9,I` → no new findings from chunk-29 (all remaining are pre-existing at HEAD: `collector_coveo.py` I001/F401/F821, `validation.py` F841, test-file I001/F401/F841). Added lines all ≤88 chars (no new E501). Replay of the stored humanoids run: `_verified_total_shortfall(verified_total=8294, persisted=4992, max_results=9000, terminal_page_short=True) == 3302`; `_has_read_enough(empty)=True`; `_endpoint_may_hold_more(empty)=False` → the new post-loop check is what classifies it `truncated`. |
| Review | DONE | round 1: `FAIL` (test coverage). round 2: `VERDICT: PASS` — reviewer confirmed the short-page branch is now discriminable, all Minors closed, no test weakened (`git diff 8455539 e89e3ac` additions-only), production untouched by the fix round. |
| Step 4 cap-consistency audit | DONE | Already consistent: the cap path appends `TRUNCATED` (collector_coveo.py:2122) and `_endpoint_may_hold_more` is True for the cap (2217-2218); `_ordered_conditions` dedups; `_breadth_verified_total` returns `None` for terminal `TRUNCATED`, so breadth falls back and `C` is unavailable. The new shortfall path appends the same `TRUNCATED` condition and inherits the same chain. No fix required. **Recorded observation (out of scope):** `_breadth_verified_total` does not exclude a terminal `PAGE_FAILED`/`REQUEST_FAILED` with a `VERIFIED` filter; a separate scope decision with its own LREQ-MET-070/EXT-090 evidence. |
| Gate | IN_PROGRESS | walking plan §10 bullets |

## Gate walk (plan §10)

| Bullet | Evidence | Result |
|---|---|---|
| `python -m pytest -q` all pass | `726 passed, 0 failed` | PASS |
| `validate_traceability` exit 0, new nodes mapped | `705 matrix nodes, 0 unmarked`; 11 chunk-29 nodes each have a marker + entry | PASS |
| `check_import_boundaries` exit 0 | `Import boundaries valid for metrics.py, scoring.py` | PASS |
| Detection: vectors A–F correct, unchanged semantics | 8 collector nodes pass, incl. short-page Major-close | PASS |
| Warning: `DISCOVERY_INCOMPLETE` only on recorded shortfall; JSON shape unchanged | `test_unreconciled_total_emits_...`, `test_cap_truncated_..._excludes_discovery_incomplete` | PASS |
| Interfaces amended and consistent | `chunk-00.md:86`, `chunk-03.md:153,211`, `chunk-10.md` §6 note; reviewer confirmed vs code | PASS |
| `LREQ-MET-070` without new metric/scoring code | `metrics.py`/`scoring.py` untouched; fallback→`C` None→not-rankable node passes; reporter confirmed via hash | PASS |
| Regression (vi): enum pin updated, node name unchanged | `test_contracts.py` enum pin includes `DISCOVERY_INCOMPLETE` (node name unchanged) | PASS |
| Formatter/linter (`pyproject.toml`: `ruff`, line-length 88, select E,F,I) | no NEW findings from chunk-29; all remaining F/E9/I failures pre-exist at HEAD; every added line ≤88 chars | PASS |
| No file outside §1.4 changed | changed set = 3 authorized src + 3 interfaces + plan/run-log; 2 extra test files (`test_metrics.py`, `test_scoring.py`) additive only — recorded below | PASS (with note) |
| Run log records Step 4 audit | recorded above | PASS |

**GATE: PASSED**

Deviations from plan §1.4 (additive only, recorded): `tests/test_metrics.py` and `tests/test_scoring.py` also gained chunk-29 nodes; `tests/fixtures/pipeline_fixtures.py` gained a default-preserving `unreconciled_terminal` variant. No production file outside the authorized three.

## Review findings that were Minor only (recorded, no loop)

- Plan §6.1 node `test_cap_truncation_records_no_unreconciled_shortfall` shipped as `test_cap_truncation_preserves_existing_truncated_behavior`; an extra node `test_exhausted_category_with_consistent_total_is_complete` duplicates vector C. Traceability keys match the actual nodes; the plan's node names are stale.
- Plan §6.3 said "no new node ID"; a new node `test_discovery_incomplete_warning_is_distinct_from_discovery_truncated` was added (additive).
- Plan §1.4 authorized `test_collector.py`/`test_pipeline.py`/`test_contracts.py`/`traceability.json`; two more test files changed additively (`test_metrics.py`, `test_scoring.py`). No production impact.
