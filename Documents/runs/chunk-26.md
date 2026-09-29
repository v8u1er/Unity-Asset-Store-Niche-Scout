# Chunk 26 — run log (Analytical defect remediation: semantics, ratings, sampling support, report rank)

Started 2026-09-29. Registration: next free id after chunk-25 (highest run log /
plan id; chunk-14/24/25 remediation precedent — **no §3/§4 dependency-map row**).
Planned branch: `chunk-26` — **not created yet** (no implementation stage has
started; branch creation is the lead's step at preflight, per the procedure).

Prerequisite: chunk-25 — run log ends `GATE: PASSED`
(`Documents/runs/chunk-25.md:246`); branch `chunk-25`; SRS live file
`Documents/SRS-lean-v2.md` (Lean 1.0.3).

## Scope status

Plan: `Documents/plans/chunk-26-analytical-defect-remediation.md`.
**Status: DRAFT — not freezeable** pending operator answers OQ-1…OQ-10
(plan §8). Four defects scoped (D1 page-view semantics, D2 rating missingness,
D3 sample support, D4 report rank). Recommended split in plan §1.4:
`chunk-26` = D4; `chunk-27` = D2; `chunk-28` = D3; `chunk-29` = D1.

## Preflight

| Check | Result |
|---|---|
| Working tree | **not clean, by design** — `git status --porcelain --branch` → `## main`; `?? Documents/plans/chunk-26-analytical-defect-remediation.md`; `?? Documents/runs/chunk-26.md`. Only this chunk's own two artifacts are untracked; no tracked file modified. They will be committed as part of the first `chunk-26` stage (planning commit) once the branch exists. |
| Prior gate | Chunk 25 `GATE: PASSED` (`Documents/runs/chunk-25.md:246`) — read |
| Next free id | `chunk-26` — `Documents/runs/` and `Documents/plans/` highest is `chunk-25`; no `chunk-26*` artifact exists (glob returned none) |
| Branch | `chunk-26` intended; **not created** — no implementation stage has started; the branch is created at the first writing stage's preflight |
| Routing (proposed) | `chunk-planner` → (tests-first) `test-author` → `impl-deep` → `spec-reviewer` → lead gate, per sub-chunk in §1.4 |

## Baseline (lead-run, 2026-09-29; real output)

| Command | Real result |
|---|---|
| `python -m pytest -q` | **688 passed in 22.05s** — clean tree, no failures |
| `python -m niche_scout.tools.validate_traceability` | exit 0 — 89 required/defined LREQ IDs mapped, 666 matrix nodes, 0 unmarked analytical tests outside exemption (3 exempted non-analytical nodes) |
| `python -m niche_scout.tools.check_import_boundaries` | exit 0 — valid for `metrics.py`, `scoring.py` |
| `python -m niche_scout.tools.check_scope_prohibitions` | exit 0 — no retired token in `src/niche_scout/*.py` (6 tokens checked) |
| `python -m niche_scout.tools.check_secrets` | exit 0 — no literal credential; `.gitignore` ignores `.env`, no tracked `.env` |
| `ruff check src` | **80 pre-existing errors** in `collector_coveo.py`, `database.py`, `validation.py` (E501 ×~70, I001 ×1, F401 ×2, F821 ×1, F841 ×1). **Not chunk-26-introduced**; recorded so the gate uses "no new lint". |

### Live-DB verification (lead, read-only `file:runtime/niche_scout.sqlite3?mode=ro`)

Latest run `run-2026-09-29T05:33:21.664034+00:00`; `sampling_rule_version 2.0.0`;
config snapshot `min_usable_samples_per_stratum=1`, `quality_min_rating_count=5`,
`min_age_days_for_rate=30`. All figures below are **counted** from the DB
(earlier "lead-grounded" labels are now replaced by these real reads).

- Enrichment: `2400` rows, `2400` distinct `asset_identity_key` — confirmed.
- Ratings: `rating_count==0` → **1559** (all with `rating_average==0`); `rc==1` → **289** (all avg 0); `rc==2` → **123** (all avg 0); `rc>=5` → **305**; `rc>0 & avg==0` → **416** — all confirmed exactly.
- Rankability: `{not_rankable: 3, provisional: 4, rankable: 17}` — **17 rankable, not the brief's 18** (see "Corrections to the dispatch", item 3).
- Evidence: `{insufficient: 3, moderate: 1, weak: 20}` — confirmed (20 weak, not the brief's 20+).
- Provisional categories: `2d/textures-materials/floors`, `3d/characters/creatures`, `3d/vehicles/air`, `3d/vehicles/space` (4, not the brief's 3).
- Not-rankable: `3d/props/furniture`, `3d/props/weapons`, `3d/vehicles/land` — confirmed; per-stratum `u_quality_h` `[0,0,0,2]`, `[0,1,1,0]`, `[1,0,1,1]` — confirmed exactly.
- Run-level `page_view_semantics_status = 'unvalidated'` — confirmed; no category row carries a semantics column (it is run-level, consistent with `category_scores` field list).
- D4: `vfx/particles/environment`, score `0.8544565…`, appears at index 21 of `ranked_categories` (rank 21) but its persisted `rank_balanced` is **1** — confirmed.

## Stage log

| Stage | Status | Evidence |
|---|---|---|
| Plan — `chunk-planner` | DONE (DRAFT) | `Documents/plans/chunk-26-analytical-defect-remediation.md`. Read-only artifact confirmation only; no `python`/`git` (bash denied). |
| Analysis pass — `chunk-planner` (recommendations) | DONE | session `ses_f13d6f784ffel1rmLvxHtlShHB`. Independently re-verified D1–D4 and both §2 corrections (both confirmed); appended plan §12 with ranked recommendations for OQ-1…OQ-10. Shell unavailable in that session (`{"permission":"bash","pattern":"*","action":"deny","source":"global"}`); all runtime figures remain lead-grounded. Lead read plan §12 (lines 587-836) and confirmed it. |
| Operator ruling — D1 semantics | DONE (2026-09-29) | Operator confirmed the Unity page-view field is per-week (trailing 7 days), refresh stable ≤30 min / assumed ≤ daily. Plan §13 records the ruling, the best-assumption formula, the required SRS edits D1-S1…D1-S7, and new OQ-11…OQ-14. §3.2/OQ-1/OQ-2 marked RESOLVED; §1.3/§1.4 split updated. |
| Operator ruling — all remaining OQ | DONE (2026-09-29) | Operator: "go with what your sub-agent determined as best answer." Plan §14 records the adopted answers for OQ-3…OQ-14 (OQ-1/OQ-2 already resolved in §13): D2 at the collector mapping with four distinct states incl. the 416-row contradiction; **D3 no change** (no census move, no version bump); D4 best-first from `rank_balanced`; D5 fix `report.py:112`; keep the symbol (OQ-11); bump `ENDPOINT_CONTRACT_VERSION` 1.0.0→1.1.0 (OQ-12) and `SCHEMA_VERSION` 1.2.0→1.3.0 (OQ-13); reword report caveats (OQ-14); split accepted (`chunk-26`=D4+D5, `chunk-27`=D2, `chunk-28`=D1). |
| Plan Q&A — operator | **DONE** | OQ-1…OQ-14 all resolved (plan §13, §14). Only the D1-S1…D1-S7 SRS edit remains a human checkpoint for `chunk-28`. |
| Tests / Implement / Review / Gate | NOT STARTED | `chunk-26` (D4+D5) is now freezeable; next step is branch + tests-first. |

## Preflight executed (2026-09-29)

| Check | Result |
|---|---|
| `git status --porcelain --branch` | `## main`; only the two chunk-26 docs untracked |
| Branch | `git switch -c chunk-26` → "Switched to a new branch 'chunk-26'" |
| Plan commit | `git commit` → `[chunk-26 3a1b2a5] chunk-26: plan (D4+D5 scoped; OQ-1..OQ-14 resolved)` — 2 files, 1213 insertions |

## Operator ruling 2026-09-29 (D1 — page-view semantics)

Operator statements (verbatim intent): (1) the Unity Asset Store page view count is
per week, operator-confirmed directly; (2) the count is stable across a 30-minute
refresh and may change at most every 24 hours. Instruction: make the best assumption
and stop keeping the project's broken cumulative assumption.

Decision recorded in plan §13:
- Best assumption: **trailing-7-day view count with daily refresh granularity**; stable
  within a run, so `retrieved_at_utc` suffices and no within-run drift model is needed.
- Formula: **`weekly_page_view_index = product_page_views`** (drop `* 7 / age_days_exact`).
  `MIN_AGE_DAYS_FOR_RATE = 30` stays as a conservative eligibility floor.
- Representation: **new token `validated_windowed_weekly`**, seeded as an endpoint-contract
  constant (no runtime detector); **not** `contradicted` (which would disable D/Q and make
  all categories `not_rankable`).
- SRS edits D1-S1…D1-S7 enumerated (operator-authorized; no agent may apply).
- Versioning: no `SAMPLING_RULE_VERSION` bump; `SCHEMA_VERSION` 1.2.0→1.3.0 recommended for
  the enum allow-list (OQ-13); `ENDPOINT_CONTRACT_VERSION` flagged (OQ-12).
- New OQ-11…OQ-14 (rename; endpoint-contract version; schema version; report caveat text).
- Split update: `chunk-26`=D4+D5; `chunk-27`=D2; **`chunk-28`=D1**; `chunk-29`=D3 only if
  OQ-5 overrides "no change".

## Agent recommendations (proposal — operator sign-off required; full text in plan §12)

- **OQ-1 D1:** defer — keep `unvalidated`; if OQ-2 confirms windowed semantics, add a windowed token + redefined index (not `contradicted`). `contradicted` is a positive unproven claim with run-wide D/Q loss and total `not_rankable`. Also: no SRS requirement mandates an automatic detector.
- **OQ-2:** two-observation test, operator-run; fold in the identity-mapping rule 1.0.1 capture.
- **OQ-3:** `collector_graphql` ProductDetail mapping (purity rules out metrics/validation; DB too late).
- **OQ-4:** keep four states distinct; `count==0 & avg==0` → both `None` (no rating); the 416 rows `count>0 & avg==0` → **separate contradiction**, avg `None`, keep valid count. No eligibility change at the default count minimum.
- **OQ-5 D3:** **no change (keep 25)** — `INSUFFICIENT_QUALITY_SAMPLE` is the SRS's conservative guard; raising `n` degrades mid-size categories (census boundary) and triples runtime. Fallback if overridden: `n = 75`.
- **OQ-6/OQ-7:** conditional on OQ-5 — no boundary move / no bump if 25 stays; if raised, accept `100→300` and bump `SAMPLING_RULE_VERSION` 2.0.0→3.0.0 + SRS Lean 1.0.4.
- **OQ-8 D4:** best-first, sort ascending `(rank, category)`.
- **OQ-9 split:** accept, amended — `chunk-26` = **D4 + D5**; `chunk-27` = D2; D3 = operator decision then a dedicated chunk if changed; `chunk-29` = D1.
- **OQ-10 D5:** fix `report.py:112` text with D4.

## Confirmation method (all read-only)

- D1: read `models.py:126-129`, `pipeline.py:999-1007`, `pipeline.py:3339`,
  `metrics.py:406-490`; grep `VALIDATED_CUMULATIVE` / `page_view_semantics_status`
  over `src/` → no non-`unvalidated` writer exists.
- D2: read `collector_graphql.py:1062-1081, 1237-1316`, `metrics.py:280-330,
  623-631, 1565-1585, 1591`; grep `rating_average|rating_count` over `src/` and
  `tests/`; **DB counts re-verified** (Baseline above).
- D3: read `models.py:43-45`, `sampling.py:69, 429-432, 587-591`,
  `metrics.py:1591`, SRS §5.1/§7.5/§14; **per-stratum `u_quality_h` re-verified**
  from `runtime/niche_scout.sqlite3` (Baseline above). The eligible-rate range
  (2 %–41 %) remains **unverified** (would need a per-category rating-count
  computation; not required by any decision here).
- D4: read `report.py:530-556`, `scoring.py:1156-1170, 1241-1242, 1362-1396,
  1452-1525`, `pipeline.py:2750-2760`; read the report HTML row for
  `vfx/particles/environment` (rank 21, score 0.854457) and the primary-table
  ordering; **DB re-verified** `ranked_categories` index 21 vs `rank_balanced` 1.

## Corrections to the dispatch (surfaced, per project rule "surface the refutation")

1. `ranked_categories` is **not** sorted by balanced score; it is
   base-candidate = requested-category order. D4's defect is real; the mechanism
   is input-order position (plan §2 item 1).
2. D does **not** consume `rating_average`/`rating_count`
   (LREQ-SCR-010; `metrics.py:1302+`). The claim's source is the inaccurate
   fixed text at `report.py:112` (recorded as side finding D5, OQ-10).
3. **Run counts.** The brief's "18 rankable, 3 provisional" does not match the
   DB: it is **17 rankable, 4 provisional, 3 not_rankable** (the 4th provisional
   is `3d/characters/creatures`, named by the brief as provisional). The brief's
   "20 weak" matches; its evidence summary is otherwise correct. Corrected
   counts are the operative ones.

## Open questions (verbatim from plan §8)

**All closed.** OQ-1/OQ-2 resolved by the 2026-09-29 D1 ruling (§13); OQ-3…OQ-14
adopted from the agent recommendations by the operator instruction "go with what
your sub-agent determined as best answer" (§14).

## Adopted decisions (2026-09-29, plan §14)

- OQ-3/OQ-4 (D2): `collector_graphql` ProductDetail mapping; four distinct states;
  `count==0 & avg==0` → `None`/`None`; `count==0 & avg>0` → contradiction; the 416
  rows `count>0 & avg==0` → separate contradiction (avg `None`, keep count).
- OQ-5/OQ-6/OQ-7 (D3): **no change** — keep `SAMPLE_PER_STRATUM = 25`; no census move;
  no `SAMPLING_RULE_VERSION` bump; no §5.1/§14 SRS revision. D3 closes as
  SRS-conforming conservative behaviour.
- OQ-8 (D4): best-first, ascending `(rank, category)`; rank read from `rank_balanced`.
- OQ-9: split accepted — `chunk-26`=D4+D5, `chunk-27`=D2, `chunk-28`=D1; no `chunk-29`.
- OQ-10 (D5): fix `report.py:112` with D4.
- OQ-11: keep the symbol `age_normalized_page_view_index`; document the historical name.
- OQ-12: bump `ENDPOINT_CONTRACT_VERSION` 1.0.0 → 1.1.0.
- OQ-13: bump `SCHEMA_VERSION` 1.2.0 → 1.3.0 (enum allow-list gains the new token);
  existing-DB mismatch handling is a `chunk-28` implementation detail (plan §14.5).
- OQ-14: reword the report caveats for the weekly index (`report.py:55`, `:128`).

Remaining human checkpoint: the D1-S1…D1-S7 SRS edits (plan §13.4, §14.6).

No gate attempted.
