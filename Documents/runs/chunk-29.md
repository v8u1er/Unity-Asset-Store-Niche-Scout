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
| Plan | IN_PROGRESS | chunk-planner dispatched |
