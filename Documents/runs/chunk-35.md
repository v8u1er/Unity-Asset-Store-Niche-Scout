# Chunk 35 — Dashboard refinement: labels, chart repairs, new chart, nav icons, wide layout

Branch: `chunk-35` (created from `main`).
Prerequisite: Chunk 34 `GATE: PASSED` (`Documents/runs/chunk-34.md`); Chunks 11/12
interfaces `VERIFIED`. No later chunk is a prerequisite for this dashboard-only work.

## Preflight

- `git status` was **not** clean on entry: `src/niche_scout/report.py` carried one
  operator-authored uncommitted hunk (the `_RAMP_HEXES` values changed to
  `#73adf0 / #59e082 / #d0df4d / #e68d52`). The user states this colour change is
  theirs and intended ("i changed colors in the .py file to my liking"), and item 5
  makes `report.py` the single colour source of truth. Decision: carry the operator
  hunk onto `chunk-35` and commit it as the chunk baseline (no rewrite, no loss).
- Pre-existing untracked `.kilocode/` (the ui-ux-pro-max skill), `cssbase.py`,
  `out.html`: accepted and recorded, never staged (`.kilocode/` is skill config;
  the two files are scratch). `.scratch/` is git-ignored.
- Deviation from the standing procedure: the tree was dirty on entry. Recorded here
  rather than stopping, because the dirty hunk is operator-authored content that is
  itself in scope for item 5. No other file was dirty.

## Live audit (Playwright, `python -m niche_scout dashboard`, run-2026-09-30T12:49:08)

- Desktop 1920×1080: `.dashboard` box x=96, width 1664 (max-inline-size 1600 +
  padding), right edge 1760 → 160px dead space right.
- Ultrawide 2560×1080: same box right edge 1760 → **800px dead space right** (item 8).
- 5 chart cards; at ≥1440 each `grid-column: span 4` → rows of 3, so the 5th card
  leaves an empty 6th slot (item 7).
- Score bar / contribution / population / scatter y-axis labels are single-line
  leaf-only (`environment` for `vfx/particles/environment`); collision rows get
  `leaf · parent` (item 1).
- Contribution chart legend is vertically scrolled (4 entries do not fit the plot
  box at 360px; Demand is clipped) (item 2).
- Policy bump: 18+ crossing lines with per-line text at the left endpoint **and** a
  legend repeating the same names (items 3).
- Population lollipop: green `sample size` markers all at x=100 (all categories have
  enriched_sample_count = 100) → a vertical column of identical dots with no signal
  (item 4).
- Nav rail icons (Phosphor-style): Run=house, KPIs=4 squares, Charts=bar, Table=list-
  bullets, Detail=3 lines. The house icon for "Run" is the specific dislike (item 6).
- CSS `--ramp-1..4` and `--evidence-*` tokens duplicate the `_RAMP_HEXES` literals
  and are not referenced by any rule → misleading second source (item 5).

## Data probe (read-only, `.scratch/audit/probe_*.py`)

- `category_scores` in `runtime/niche_scout.sqlite3` run-2026-09-30T12:49:08:
  24 rows. `discovered_population_count` 203..4934; `enriched_sample_count` = 100
  for every row; `component_d` 0.31..0.92; `component_c` 0.09..1.00;
  `component_r` 0.00..0.99; `component_q` 0.06..1.00; `overlap_*` = 0 for all;
  `maximum_rank_displacement` = 5 for all; `quality_stratum_eligibility_coverage`
  0.25..1.00 (varies); `reference_usable_counts_json` identical across rows.
- Implication for item 7: a Demand-vs-Competition opportunity quadrant is the
  strongest new chart — both components vary, and high-demand / low-competition is
  the project's core question. Charts built on sample size or overlap would be flat.

## Stages

- preflight: DONE — branch `chunk-35`; operator colour hunk carried (`bc7e273`).
- audit: DONE — evidence above.
- plan: DONE — `Documents/plans/chunk-35-dashboard-refinement.md`, FROZEN; six lead CLI
  `ui-ux-pro-max` returns recorded in plan §2.1a (`89db690`). One blocking question
  (sixth-chart split) answered by the operator: option (a) D/C scatter with **no**
  threshold. Icon set refined by the lead to the skill's Phosphor-only outline catalog
  (item 6 needed a metaphor fix, not a family swap).
- tests: DONE — six nodes amended in place, seven added; adjudicated after a
  fixture-partition error (`24c39b5`, `0fcd545`). Red state 11 failing; traceability
  747 nodes valid.
- implement: DONE — D35-1..D35-8 in `report.py` + `dashboard.css` (`c8c6681`); one
  follow-up to bound the policy-bump series at 10 with an omitted-row disclosure
  (`132bc75`). All 768 tests pass.
- verify (lead): DONE — `pytest -q` 768 passed; traceability/imports/scope exit 0;
  ruff clean. Playwright at 1920×1080 and 2560×1080 and 375 (below): 6 chart cards in a
  3×2 grid; `.dashboard` right edge 1905/2360 → dead space 15px/200px (was 160/800);
  policy chart 10 traces, legend off, stable/omitted note present; population chart 2
  traces (no constant sample series); sixth chart renders 18 markers with both axes
  titled; nav shows play-circle/gauge/chart-bar/table/file-text and the old house icon
  is gone; all y-axis labels wrap to two lines (`environment` over `particles`).
- review: DONE — `spec-reviewer`: `VERDICT: PASS` with Minors only.
- gate: DONE — all bullets evidenced; `GATE: PASSED` (below).

## Verification evidence (lead)

- `python -m pytest -q` → `768 passed` (42 warnings, Dash DataTable deprecation).
- `python -m niche_scout.tools.validate_traceability` → 89 LREQ IDs, 747 nodes, 0 unmarked.
- `python -m niche_scout.tools.check_import_boundaries` → valid for `metrics.py`, `scoring.py`.
- `python -m niche_scout.tools.check_scope_prohibitions` → no retired token (6 checked).
- `python -m ruff format --check` / `ruff check` `report.py` → clean.
- Playwright, served `python -m niche_scout dashboard` (loopback 8050), run
  `run-2026-09-30T12:49:08.901818+00:00`:
  - 1920×1080: `.dashboard` x=96 width 1809 right 1905 → **15px** right dead space
    (was 160px); 6 `.chart-card`, all width 576, positions (128,521) (712,521)
    (1297,521) (128,1028) (712,1028) (1297,1028).
  - 2560×1080: `.dashboard` width 2264 right 2360 → **200px** right dead space (was
    800px); 6 cards, all width 728.
  - Chart read-backs: score bar `showlegend=false`; contribution 4 named bars,
    `showlegend=true`, horizontal legend, `xTitle="category (leaf, then parent)"`;
    policy 10 traces, `showlegend=false`, annotation
    `"Stable across policies: sci-fi…"` + `"Not shown (beyond top 10): …"`;
    population 2 traces (`discovered population`, `measured zero`), no `sample size`;
    score-vs-quality 1 trace, no legend; demand-vs-competition 1 trace of 18 markers,
    `shapes=0`, `annotations=[]`, axis titles `Demand (higher = more demand)` /
    `Competition (higher = less crowded)`.
  - Nav: `play-circle`, `gauge`, `chart-bar`, `table`, `file-text`; no `house`.
  - Close-ups: `.scratch/audit/c35-demand-comp.png`, `c35-policy-bump2.png`,
    `c35-contribution.png`, `c35-population.png`, `c35-nav-rail.png`,
    `c35-2560-full.png`.

## Items → outcome

1. Wrapped two-line category labels on every chart category axis — done.
2. Contribution legend fits horizontally below the plot — done (4 entries, no scroll).
3. Policy chart de-spaghettied: legend dropped, only changing rows drawn, capped at 10
   with the omitted rows and stable rows disclosed in one in-card note — done.
4. Constant `sample size` series removed from the population chart — done.
5. Non-functional `--ramp-*`/`--evidence-*` CSS colour tokens removed; `_RAMP_HEXES`
   is the single source — done.
6. Nav icons replaced (Phosphor outline; house-for-Run gone) — done.
7. Sixth chart added: Demand vs competition scatter (persisted components only, no
   invented threshold) — done; 2×3 grid.
8. Content area fills the ultrawide screen (cap 2200px) — done.

## Deviations / notes

- The plan's D35-1 initially named Google Material Symbols; the lead refined it in
  flight to the skill's Phosphor-only outline catalog (the skill carries no Material
  family) — a metaphor fix, same contract shape. Recorded in plan §2.1a.
- One extra implementation round was required: the first chunk-35 render still drew 17
  policy-bump traces in the live run (fixture tests only exercise ≤5), so the merge gate
  audit added a `_POLICY_BUMP_MAX_SERIES = 10` cap with an omitted-row note.
- Standing obligations untouched: URI trailing-identifier extraction, OI-6 CSRF
  sufficiency, `runs.taxonomy_sha256` empty-hash rejection. No SRS gap was resolved
  silently; the only SRS-shaped question (sixth-chart threshold) was answered by the
  operator with "no threshold".

GATE: PASSED