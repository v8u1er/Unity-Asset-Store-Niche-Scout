# Chunk 27 — run log (D2 — rating missingness at the collector mapping layer)

Started 2026-09-29. Remediation/follow-on chunk: **no dependency-map §3/§4 row**
(chunk-14/24/25/26 precedent). Registration = plan + run log + branch.

Scope (operator-fixed): **D2 only** — Unity returns a literal `0` for
`rating.average` / `rating.count` on unrated assets; the adapter stores `0.0` / `0`,
violating SRS §1.2 ("missing is not zero") and §6.4 LREQ-GQL-050. Fix at the I/O
adapter (`collector_graphql` ProductDetail mapping), never in the pure layer.

Governing defect plan: `Documents/plans/chunk-26-analytical-defect-remediation.md`
§4 (D2 evidence, consumers, layer/rule) and §14.1 (operator-adopted OQ-3/OQ-4);
§2 item 2.

## Preflight

| Check | Result |
|---|---|
| Prior gate | chunk-26 `GATE: PASSED` — `Documents/runs/chunk-26.md:98`; merged to `main` at `7fdf92e` (log line 104; brief says d4baac7 — see note) |
| Working tree | clean — `git status --porcelain --branch` → `## main` only |
| Branch | `git switch -c chunk-27` → "Switched to a new branch 'chunk-27'" |
| Routing (plan) | `chunk-planner` → `test-author` (tests first) → `impl-deep` → `spec-reviewer` → lead gate |
| Next free id | `chunk-27` per operator-fixed scope; no `chunk-27*` artifact previously existed |

Note on the merge SHA: the run log records `Updating 44fe283..7fdf92e` for the
`chunk-26` fast-forward (chunk-26.md:102-104). The dispatch brief cites `d4baac7`.
The run log is the operative artifact; `d4baac7` is not yet confirmed against git.

## Baseline (lead-run, 2026-09-29; real output)

| Command | Real result |
|---|---|
| `python -m pytest -q` | **695 passed in 22.93s** — clean tree, no failures |

### Live-DB re-verification (lead, read-only `file:runtime/niche_scout.sqlite3?mode=ro`)

Latest run `run-2026-09-29T05:33:21.664034+00:00`. Counted from
`enrichment_observations` by `.scratch/chunk27_db_check.py`:

- rows / distinct `asset_identity_key`: **2400 / 2400** — confirmed.
- `rating_count==0` → **1559** (all `rating_average==0.0`) — confirmed.
- `rc==1` → **289** (all avg `0.0`); `rc==2` → **123** (all avg `0.0`) — confirmed.
- `rc>=5` → **305** — confirmed.
- `rc>0 & avg==0` → **416** (= 289+123+2+1+1) — confirmed.
- `rc>0 & avg>0` → **425**; `rc>0 & avg in (0,5]` → **425** — consistent.
- `avg IS NULL` → **0**; `cnt IS NULL` → **0** — no nulls persisted today (all literal zeros).
- Partition check: 1559+289+123+2+1+1+425 = **2400** ✓.
- Distinct `(count, avg)` pairs show the contradictions: `(3,0.0)×2`, `(9,0.0)×1`,
  `(18,0.0)×1`, plus 289+123 zero-avg rows below 3.

## Stage log

| Stage | Status | Evidence |
|---|---|---|
| Preflight (lead) | DONE | branch `chunk-27`; clean tree; chunk-26 GATE PASSED; baseline 695 passed; DB re-verified above. |
| Plan — `chunk-planner` | PENDING | target `Documents/plans/chunk-27-rating-missingness-remediation.md` |
| Tests — `test-author` | PENDING | |
| Implement — `impl-deep` | PENDING | |
| Verify (lead) | PENDING | |
| Review — `spec-reviewer` | PENDING | |
| Gate (lead) | PENDING | |

## Gate bullets (the plan must adopt these)

1. `rating_count==0, rating_average==0` round-trips as `None`/`None`.
2. The 416-row case persists `rating_average=None` with the integer count retained and a
   distinct, deterministic validation issue.
3. `count>0, avg in (0,5]` unchanged.
4. `metrics.py` / `scoring.py` unchanged; `check_import_boundaries` exit 0; no `or 0` /
   `.get(k, 0)` added.
5. pytest + four validators exit 0; ruff no new lint.
6. No SRS edit; no version bump; no out-of-scope file changed.

## Allowlist (chunk-planner confirms against its own §6)

- `src/niche_scout/collector_graphql.py`
- `tests/test_collector.py` and collector fixtures; any test pinning rating null-ness
  (`grep -rn "rating_average\|rating_count" tests/`)
- `tests/traceability.json` only if a new node ID is added
- `Documents/plans/chunk-27-*.md`, `Documents/runs/chunk-27.md`

NOT: `metrics.py`, `scoring.py`, `pipeline.py`, `database.py`, `report.py`, config, SRS,
sampling constants. A needed change outside this list is a STOP-and-flag, not an edit.

## Open questions

(none yet)

## Gate

(not attempted)