# Chunk 33 — dashboard visual redesign: reference palette, minimal nav, truncation fix (run log)

New remediation/feature chunk, not in `Documents/requirements-dependency-map.md` §3/§4
(chunk-14 / chunk-30 / chunk-31 / chunk-32 precedent: registration = plan + run log + branch).
Do not edit the dependency map, the SRS, `AGENTS.md`, or `.kilo/`.

Branch: `chunk-33`, created from `main` @ `3750882` (`chunk-32: gate PASSED; run log`).

## Origin

Operator request (2026-10-01, follow-up to chunk 32), verbatim intent:
- "find all the design issues, i see lots of truncated text, wrong text weights etc for example."
- "heavily use ui-ux-pro-max for designing and improvement of the dashboard."
- "take influence from design language of this screenshot, and confirm that you received the image."
- "i want the color palette of this screenshot be applied to my dashboard."
- Reference image: `c:/Users/<redacted-user>/Downloads/525-bild1-800x.jpg` (800x468 JPEG).
- "the dashboard also needs a minimal navigation system, consult with ui-ux-pro-max skill."
- "use your sub-agents and inform them about ui-ux-pro-max skill and the screenshot and also Kilo Playwright."

## Reference image — RECEIVED and read (lead)

The image was opened and read by the lead. It is a dark **enterprise security-console
dashboard** ("Helios"): a fixed left icon rail, a breadcrumb top bar
(`Protection / Dashboard`) with an `H1` and a primary action, then a bento grid of
rounded cards — a large world-map/health card with a donut, and three equal cards
(`Protection Coverage`, `Compliance`, `Storage`) each with a donut ring, a value, and a
legend list with counts and status dots.

### Palette extracted from the image (method: Pillow, median-cut quantize + HSV filter)

Dominant surfaces (median-cut, 14 colours, `im.quantize(colors=14, method=MEDIANCUT)`):
`#112d3b` (123,463 px), `#0c1d27` (52,080), `#345265` (30,913), `#112d39`, `#1f394e`,
`#102d3c`, `#66908c`, `#0c2432`, `#142d3d`, `#0e1c27`, `#091b27`, `#112d45`, `#12303f`.
Accent scan (HSV: hue 195–245, sat>0.45, val>0.5): `#64bcfb`, `#68bdfd`, `#66bbfb`.
Positive scan (hue 80–175, sat>0.4, val>0.5): `#46b688`, `#47b68c`, `#48b78d`.
Alert scan (hue ~354): `#e27882`.

### Reference palette as applied to the dashboard (lead ruling, R1)

| Token | Old (chunk 32) | New (from image) | Role |
|---|---|---|---|
| `--bg` | `#0B1120` | `#0C1D27` | page canvas |
| `--surface` | `#1B2029` | `#112D3B` | card / panel |
| `--surface-2` | `#222833` | `#0C2432` | inset, table zebra |
| `--border` | `#2C3440` | `#1F394E` | hairline |
| `--fg` | `#E6E9EE` | `#E6F0F4` | primary text |
| `--muted-fg` | `#9AA6B2` | `#8FB0BF` | secondary text |
| `--primary` | `#6EA8FE` | `#64BCFB` | accent / action |
| `--accent` | `#F2C14E` | `#46B688` | secondary accent (image green) |
| `--positive` | `#8FD694` | `#48B78D` | positive |
| `--danger` | `#E06C75` | `#E27882` | alert |

`--accent` becomes the image's teal-green `#46B688` (used for donut/ring style and the
active-nav marker); the amber it previously held is no longer a token. Evidence ordinal
scale is retained and re-tuned to the image family (R2).

## Preflight

| Check | Result |
|---|---|
| Working tree | `.kilocode/` and `out.html` untracked (pre-existing, from chunk 32's report; not staged). No tracked file modified. `cssbase.py` (chunk-32 leftover) is now gone from the tree. Accepted and recorded, chunk-32 precedent. |
| Branch | `main` → `chunk-33` |
| Base commit | `3750882` (`chunk-32: gate PASSED; run log`) |
| Prerequisite Chunk 32 | `Documents/runs/chunk-32.md` → `GATE: PASSED`; plan FROZEN |
| Prerequisite Chunk 11/12/30/31 | chunk-32 run log preflight rows (all PASSED / VERIFIED) |
| Routing | `chunk-planner` → `test-author` (tests-first, `LREQ-RPT-010` styling) → `impl-deep` → lead verify → `spec-reviewer` → gate |

## Live-dashboard audit (lead; Kilo Playwright against the running app)

The lead started `python -m niche_scout dashboard` (loopback 8050, session-lifetime
background process) and inspected the real rendered page with Kilo Playwright. The
service was started once; **no second server was run concurrently** (single-writer rule).

### Measured findings (Kilo Playwright `browser_evaluate`, real DOM)

1. **"Truncated text" — root cause found, and it is not the primary table.** The operator's
   reported truncation is in the **Plotly figures**, not the `DataTable`. The category axis
   of the *Composite score by rank* bar chart and the *Population and sample size* lollipop
   show clipped labels (`...shaders/fullscreen-camera-effects`, `/particles/environment`).
   The Plotly layout reserves a fixed left margin, so long category names are clipped and
   the axis title `category` overlaps the tick labels. **Root cause:** a fixed pixel left
   margin in `_base_layout` (`report.py:1411`) that does not account for the longest label.
2. **The primary table does not truncate its headers, but it reads as truncated.** The
   `.dash-header`/`.dash-cell` `overflow` computes to `hidden auto` and the headers carry
   `text-transform: uppercase` with `letter-spacing: 0.04em`, so the 30 long headers
   (`demand stratum eligibility coverage`, `sample shared with other categories (%)`, …)
   are clipped at the cell edge **visually**, even though the accessible name is complete
   (`column-header-name`, nowrap, `scrollWidth == clientWidth` at the time of sampling).
   `test-report` "Truncation" rule (ux-guidelines, severity Medium) requires an **ellipsis
   plus an expand path**; "Essential Text Truncation" (severity **Critical**) forbids
   clamping distinguishing names.
3. **Wrong text weights (measured).** Rendered leaf-text weight histogram:
   `{400: 1008, 600: 34, 700: 23}`. Only 34 nodes are 600 and 23 are 700 — and the 700s are
   `h1` plus `.kpi-value`; card/section titles (`h2`/`h3`), table headers, and the value
   column are not clearly differentiated from body. There is no defined weight scale.
4. **Font sizes are incoherent (measured).** `{12.48px: 750, 12px: 118, 16px: 85,
   13px: 77, 17px: 11, 14px: 10, 20px: 2, 24px: 4, 9px: 4, 15px: 4}`. The 750 `12.48px`
   nodes come from the Dash `DataTable` default `0.78rem`, not from the stylesheet; `9px`
   appears in the chart legends. The dashboard has no single type ramp.
5. **KPI number is rendered in mono at 24px** (`0.666667`) while `--font-size-base` is
   16px; there is no numeric scale tier between body and KPI. `.kpi-value` and `.kpi-label`
   sit at nearly the same visual weight.
6. **Table header sticky is inert** (chunk-32 MINOR #1, reconfirmed): `.dash-header` computes
   `position: sticky`, but every Dash scroll ancestor sets `overflow-x: auto`, so the
   sticky context never engages.
7. **Page height 4115 px; five 555x360 charts on one page; no in-page navigation.** There is
   no way to jump between the header, the KPI strip, the charts, the primary table, and the
   category detail. The operator asked for a **minimal navigation system**; the reference
   image's left icon rail is the model.
8. **Chart card titles and the Plotly in-figure titles are duplicated** (`H3` "Composite
   score by rank" plus the Plotly title of the same string), doubling the heading mass.

### What was verified vs not

- The live page, its computed styles, weights, sizes, and truncation geometry were
  **measured** with Kilo Playwright against the running app.
- The reference-image palette was **measured** with Pillow (median-cut + HSV scan).
- The chart-label clipping is a **visual read** of the Playwright screenshot; the exact
  Plotly margin number is **read** from `report.py:1411`.
- Whether every one of the 30 `DataTable` headers clips at every viewport is **not** fully
  verified — the sampled header row reported `scrollWidth == clientWidth` at 1280px. The
  fix is therefore specified to be *robust* (ellipsis + expandable full text), not keyed to
  a single measured clip.

## Skill evidence (`ui-ux-pro-max`; lead ran the CLI)

Commands run by the lead (permitted in this environment):

- `search.py "internal analytics dashboard data-dense dark console" --design-system -p "Niche Scout" -f markdown`
  → Style **Data-Dense Dashboard** (Light+Dark); key effects "Hover tooltips, chart zoom on
  click, row highlighting on hover, smooth filter animations, data loading spinners";
  anti-patterns "Ornate design", "No filtering"; accessibility requires
  `contrast-text-4.5`, `keyboard`, `visible-focus`, `reduced-motion`; pre-delivery
  checklist "cursor-pointer on all clickable elements", "Hover states with smooth
  transitions (150-300ms)", "Responsive: 375/768/1024/1440".
- `search.py "minimal sidebar navigation icon rail dashboard" --domain ux -n 6`
  → Navigation **Sticky Navigation** (fixed nav must not obscure content; compensate with
  padding — Medium); Accessibility **Keyboard Navigation** (High); **Heading Hierarchy**
  (sequential h1→h6 — Medium); **Skip Links** ("provide skip to main content" — Medium).
- `search.py "table column header truncation ellipsis wrap" --domain ux -n 6`
  → Content **Truncation** ("truncate with ellipsis and expand option" — Medium);
  **Essential Text Truncation** ("headings, actions, errors, safety text and distinguishing
  names need complete access; wrap, stack, resize, or provide a visible full-detail path" —
  **Critical**); **Compact Label Overflow** ("nowrap with a shrinkable label; expose full
  text to keyboard, pointer and touch users; never a hover-only tooltip" — High).
- `search.py "sidebar navigation dashboard overview table settings icons" --domain icons -n 6`
  → Phosphor outline: `sidebar`, `house`, `list`, `gear`, `list-bullets`, `grid-four`.
  "No emoji as structural icons"; context decides decorative vs meaningful vs interactive.
- `search.py "KPI stat card number label hierarchy dashboard" --domain ux -n 5`
  → **Number Formatting** ("use thousand separators or abbreviations"; Low);
  **Compact Label Overflow** (High).

Decision impact: keep the dark data-dense theme; apply the reference palette; make the
weight/size scale explicit; fix truncation with ellipsis + a keyboard/pointer-operable full
text path (not hover-only); add a minimal icon-rail navigation with skip link, sticky-safe
offset, sequential heading order, and Phosphor-style inline SVG icons (no external font, no
emoji).

## Hard constraints (carried from chunk 31/32)

- **Offline/no-CDN is non-negotiable**: no external URL, CDN, `@import`, or web font. Icons
  are inline SVG; the font stack stays local/system.
- **Content preserved**: no `LREQ-RPT-020/030/040/050` string, no primary-table column, no
  Appendix C code removed from the DOM.
- **Purity**: `report.py` imports no `metrics`/`scoring`/`collector*`/`config`/`pipeline`/`cli`;
  no clock read; the layout is deterministic for a fixed view.
- **No live network / no `niche-scout run`** in development or tests.
- Chunk-32 pinned tests must stay green unless this chunk's plan explicitly supersedes them.

## Operator-authorized decisions

- **E-1 — implement now** (design redesign + nav + truncation fix).
- **E-2 — skill-mandated**: every subagent SHALL consult `ui-ux-pro-max` and cite it.
- **E-3 — reference image is authority for palette and design language** (received and read).
- **E-4 — offline preserved**.
- **E-5 — new chunk 33**.

## Stage log

| Stage | Status | Notes |
|---|---|---|
| Preflight (lead) | DONE | tree clean-enough; `chunk-33` from `3750882`; this log |
| Reference image read + palette extraction (lead) | DONE | Pillow median-cut + HSV scan; table above |
| Live dashboard audit (lead, Kilo Playwright) | DONE | 8 measured findings above; background process `bgp_0f66c4b53001UIFaleLj1nbdMN` |
| Skill CLI (lead) | DONE | five queries above |
| Plan — `chunk-planner` | PENDING | |
| Tests — `test-author` | PENDING | |
| Implement — `impl-deep` | PENDING | |
| Lead verification | PENDING | |
| Review — `spec-reviewer` | PENDING | |
| Gate | PENDING | |

## Open items carried forward

- chunk-32 Minors 1–4 (sticky inert, `scroll-padding-top`, `.missing` 4.2:1, dead
  `details.heuristic > p`) are expected to be resolved by this chunk's styling pass where
  they overlap; anything not resolved is recorded at the gate.
- The three standing obligations (URI extraction, OI-6, `taxonomy_sha256`) remain untouched.