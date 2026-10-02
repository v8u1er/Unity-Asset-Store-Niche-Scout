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

- preflight: DONE — branch `chunk-35`; operator colour hunk carried.
- audit: DONE — evidence above.
- plan: pending.
- tests: pending.
- implement: pending.
- verify: pending.
- review: pending.
- gate: pending.