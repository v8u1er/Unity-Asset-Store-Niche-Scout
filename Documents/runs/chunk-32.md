# Chunk 32 — run log (dashboard visual design system + progressive disclosure)

New remediation/feature chunk, not in `Documents/requirements-dependency-map.md` §3/§4
(chunk-14 / chunk-30 / chunk-31 precedent: registration = plan + run log + branch). The next
free id is 32 (runs/plans/interfaces stop at 31). Do not edit the dependency map, the SRS,
`AGENTS.md`, or `.kilo/`.

Branch: `chunk-32`, created from `main` @ `0d3e459` (`chunk-31: gate PASSED; run log`).

## Origin

Operator request (2026-10-01, follow-up to chunk 31): `python -m niche_scout dashboard` renders
too much unnecessary text and looks under-designed. Use the `ui-ux-pro-max` skill to critically
audit and then enhance the dashboard: a remove list, an enhance list, a chosen color palette, and
a design language. "Go ahead" to implement, and "make sure your sub-agents [use the ux skill]."

## Preflight

| Check | Result |
|---|---|
| Working tree | only `.kilocode/` and `out.html` untracked; no tracked file modified. Lead will not stage `.kilocode/` or `out.html`. Deviation from a strictly clean tree, accepted and recorded (chunk-31 precedent). |
| Branch | `main` → `chunk-32` |
| Base commit | `0d3e459` (`chunk-31: gate PASSED; run log`) |
| Prerequisite Chunk 11 (report renderer) | `Documents/runs/chunk-11.md` → `GATE: PASSED`; `interfaces/chunk-11.md` `Status: VERIFIED` |
| Prerequisite Chunk 12 (CLI) | `Documents/runs/chunk-12.md` → `GATE: PASSED` |
| Prerequisite Chunk 30/31 (Dash dashboard) | `Documents/runs/chunk-31.md` → `GATE: PASSED`; `interfaces/chunk-11.md` §11 |
| Prior chunk-32 artifacts | none |
| Routing (lead-chosen; rendering/design work) | `chunk-planner` → `impl-fast` (production + tests; tests-first = no, per matrix rows 11/12) → `spec-reviewer` → lead gate |

## Lead critical audit (input to the plan; from reading `report.py` + the ux skill)

The Dash app is **effectively unstyled**: `build_dashboard_app` (`report.py:2074`) passes no
`external_stylesheets` and no `assets/` folder exists; the only CSS in the repo (`_INLINE_CSS`,
`report.py:386`) is used solely by the **static** `render_run_report_html`, not the Dash app.
Every Dash `className` (`dashboard`, `kpi-strip`/`kpi-tile`/`kpi-note`, `chart-grid`/`chart-card`/
`chart-caption`, `primary-table`, `detail-panel`, `formula-panel`, `footnote`, `run-header-block`,
`heuristic`, ...) is orphaned. The five Plotly figures are hard-coded dark
(`_base_layout`, `report.py:1394`: paper/plot `#1b2029`, text `#e6e9ee`) floating on a white page.

Text mass: `HEURISTIC_STATEMENT` (~900 chars, always visible); `_FORMULA_EXPLANATIONS` (11 items,
panel `open=True`); a per-chart "read it as…" caption; a KPI explanation rendered both as a visible
`.kpi-note` and a `title`; a 21-item observed/inferred list repeated in every category detail; a
footnote repeating coverage-vs-sample-fraction already in the formula list.

SRS verdict: the SRS mandates **content** (`LREQ-RPT-020` fields, `LREQ-RPT-030` detail items,
`LREQ-RPT-050` statement + distinctions, Appendix C codes), not always-visible or duplicated
prose. The verbosity is an implementation/plan choice. Fix by progressive disclosure + a real
stylesheet, not by deleting mandated content.

## Hard constraints discovered (lead, read-only)

- **Offline/no-CDN is non-negotiable** (chunk-31 gate): the design MUST NOT reference external
  URLs or Google Fonts. The skill's Fira Sans/Fira Code recommendation is adopted as a
  *structure* (mono for data, sans for labels) via an offline-safe local/system font stack; no
  `@import`/`<link>` to fonts.googleapis.com.
- **`test_report.py:949-950`** forbids `http://`/`https://` in the **static** HTML report; the
  Dash path must independently stay offline.
- **Pinned dashboard tests** (must stay green): `test_build_dashboard_layout_is_deterministic_for_a_fixed_view`,
  `test_build_dashboard_app_layout_matches_the_layout_builder`,
  `test_dashboard_layout_shows_every_primary_table_column_by_default` (all 30 columns),
  `test_dashboard_detail_panel_covers_rpt_030_items_for_a_selected_category`,
  `test_dashboard_layout_keeps_refused_categories_visible_and_off_the_scored_axis`,
  `test_dashboard_layout_includes_the_heuristic_statement` (statement present exactly once),
  `test_dashboard_charts_carry_explanations_and_human_labels` (caption + title present in the tree),
  `test_dashboard_policy_bump_and_kpi_tiles` (KPI explanation text present in the strip),
  `test_dashboard_distinguishes_null_from_explicit_zero`,
  `test_dashboard_score_bar_encodes_ordinal_evidence_grade`,
  `test_dashboard_has_no_confidence_interval_or_error_bars`,
  `test_dashboard_omits_the_coverage_heatmap`,
  `test_end_to_end.py::test_acceptance_rendered_report_contains_required_fields` (heuristic in `app.layout`).
- **Purity**: `report.py` imports no `metrics`/`scoring`/`collector*`/`config`/`pipeline`/`cli`;
  no clock read; layout deterministic for a fixed view.

## Operator-authorized decisions (not re-openable by agents)

- **D-1 — implement now.** The operator authorized implementing the design enhancement.
- **D-2 — skill-mandated.** The lead and every subagent SHALL use the `ui-ux-pro-max` skill
  (`python .kilocode/skills/ui-ux-pro-max/scripts/search.py ...`) and cite its outputs.
- **D-3 — content preserved.** No `LREQ-RPT-020/030/040/050` content or Appendix C code is
  removed from the DOM; verbosity is reduced by progressive disclosure and styling only.
- **D-4 — offline preserved.** No external URL, CDN, or web font.
- **D-5 — new chunk 32**; chunk 30/31 are not edited in place beyond the plan's file list.

## Fixed design selection handed to the planner (lead; from the ux skill)

Style: **Data-Dense Dashboard** (skill `--design-system`). Type structure: mono for numerics,
sans for labels (skill "Dashboard Data"), implemented offline-safe. Palette: one **dark** theme
because the figures and the ordinal evidence scale are already dark-tuned (skill dark-dashboard
palettes + existing figure hues). Tokens (lead-chosen):

`--bg #0B1120`, `--surface #1B2029`, `--surface-2 #222833`, `--border #2C3440`, `--fg #E6E9EE`,
`--muted-fg #9AA6B2`, `--primary #6EA8FE`, `--accent #F2C14E`, `--positive #8FD694`,
`--danger #E06C75`; evidence scale `#c98b8b/#e0a458/#8fb9a8/#8fd694` (existing).

Design language: "data-dense dark analytics console" — 12-col grid, 8px rhythm, semantic tokens,
progressive disclosure, direct labels + text (never color alone), sortable table primary.

## Stage log

| Stage | Status | Notes |
|---|---|---|
| Preflight (lead) | DONE | clean-enough tree; `chunk-32`; this log |
| Plan — `chunk-planner` | DONE | wrote `Documents/plans/chunk-32-dashboard-visual-design.md`; returned BLOCKED on Q1 (heuristic `open` default) and Q2 (planner's `bash` was denied, so it cited the skill's bundled CSVs directly instead of running `search.py`). |
| Skill CLI (lead) | DONE | lead ran the `ui-ux-pro-max` CLI (permitted for the lead); see "Skill CLI evidence" below. |
| Rulings + freeze (lead) | DONE | plan §12 R1–R6; R1 = heuristic `open=False`; R2 = CLI output accepted + corroborates CSV citations; header flipped to `FROZEN`. |
| Plan commit | DONE | `chunk-32: plan` |
| Implement — `impl-fast` | PENDING | |
| Lead verification | PENDING | |
| Review — `spec-reviewer` | PENDING | |
| Gate | PENDING | |

## Skill CLI evidence (lead; `ui-ux-pro-max`)

Commands run by the lead (the planner's own `bash` was denied by the environment rule, Q2):

- `python .kilocode/skills/ui-ux-pro-max/scripts/search.py "internal analytics dashboard data-dense tool dark" --design-system -p "Niche Scout" -f markdown`
  → Style **Data-Dense Dashboard** (light+dark); typography **Fira Code** heading / **Fira Sans**
  body; Analytics Dashboard palette; anti-patterns "Ornate design", "No filtering".
- `--domain color "dashboard analytics tool color palette" -n 3` → Analytics (light), Financial
  Dashboard (dark: bg `#020617`/card `#0E1223`/border `#334155`), Dark tech palettes.
- `--domain style "data dense dashboard KPI cards charts" -n 3` → `data-dense-dashboard`:
  "12-column grid, gap 8px, padding 12px, font-size 12–14px, overflow auto for tables, compact
  card, sticky headers", `--table-row-height:36px`.
- `--domain chart "dashboard ranking comparison distribution funnel" -n 5` → Compare Categories =
  horizontal bar; "categories > 15 → use table"; "never encode category solely by bar color";
  visible sortable data table fallback.
- `--domain typography "monospace numeric data dashboard" -n 3` → "Dashboard Data" (Fira
  Code/Fira Sans), "Code for data, Sans for labels".
- `--domain ux "progressive disclosure long explanatory text" -n 5` → truncation with expand;
  line length 65–75ch; text reflow **Critical**.
- `--domain ux "dashboard information density scanability tooltip" -n 5` → "Don't convey
  information by color alone" (High).
- `--domain ux "dashboard dark mode contrast tokens" -n 5` → text contrast ≥4.5:1 (High); focus
  appearance ≥2 CSS px perimeter with 3:1 state contrast.
- `--domain ux "keyboard focus visible sortable table" -n 5` → visible focus ring on every
  interactive control (High); focus-not-obscured offset.

Decision impact: dark data-dense theme retained (figures already dark), mono-for-data / sans-for-
labels via an **offline system stack** (the skill's Google-Fonts `@import` is rejected under the
offline constraint, D-4), sortable table primary, never colour-alone, focus/reduced-motion rules.
