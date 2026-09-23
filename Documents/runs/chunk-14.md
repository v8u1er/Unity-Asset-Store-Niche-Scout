# Chunk 14 — run log (Live endpoint compatibility, post-Chunk-13 remediation)

Started 2026-09-23. Working tree off `main` at `cd51923` (`chunk-13: gate passed; run log`).
Chunk 14 is a labeled post-completion remediation requested by the human after a live probe
against the real Coveo endpoint showed the committed configuration cannot complete a run.
Plan: `Documents/plans/chunk-14-live-endpoint-compatibility.md` (`Status: FROZEN`).
No new interface file; no dependency-map gate row (the dispatch DoD is the gate).

## Preflight

| Check | Result |
|---|---|
| Working tree | clean at start (`git status` → nothing to commit) |
| Branch | `main` (no branch created; human instructed lead to own process) |
| Python / pytest | 3.12.2 / pytest 9.1.1 |
| Prior gate | Chunk 13 `GATE: PASSED`, `596 passed` (`cd51923`) |
| Routing | reconnaissance → `chunk-planner` → `test-author` → `impl-deep` → `spec-reviewer` → lead gate |

## Grounded findings (labels: read / counted / live / unverified)

| # | Finding | Evidence |
|---|---|---|
| F1 | Replayed `sortCriteria` is live-invalid; hash must be recomputed after any body edit | read `collector_coveo.py:184-195,463-522,616-721`, `config/coveo_search_template.json:25`; live `InvalidSortField` for `@score` then `@ec_popularity` (human-supplied) |
| F2 | Inbound `" > "`-separated, leading-space, lowercase vocabulary cannot match the `/`-only normalizer | read `validation.py:660-685,1048-1203,1082-1109`; call site `collector_coveo.py:1334,1853`; live facet/record shapes (human-supplied) |
| F3 | Server-side filtering accepts canonical `/` form | live: `3d/characters/humanoids` → `totalCountFiltered 8254` (human-supplied); generalization unverified |
| F4 | Committed taxonomy was stale and structurally malformed | read+counted: `captured_at_utc 2026-01-05`, single-segment entries fail `_is_canonical_path_shape`, all-zero `template_sha256`; `validate_taxonomy_structure` returns `malformed` on any such entry (`validation.py:744-751`) |
| F5 | 596 tests passed because none encoded the live vocabulary or sort rejection | read: tests are offline and the hash self-check hashes the committed body |

## Decisions recorded (plan §2/§12)

- **Q1 separator.** `normalize_category_path` maps the exact `" > "` sequence to `/` (segments trimmed,
  empties dropped, case preserved); `_canonical_path_shape_preserved` tokenizes both separators without
  dropping empties. The SRS defines no separator or casing rule; this is a new, documented convention.
- **Q2 sortCriteria.** Removed from the committed body; `_COVEO_REPLAYED_TEMPLATE_FIELDS` still names it so
  a future valid capture replays it. Human states the Unity default is relevance; removing the invalid
  explicit sort yields the engine default and preserves LREQ-EXT-050's "same sort order" across categories.
  **Pagination stability is not verified** and is recorded as a limitation.
- **Q3 coupling.** Config-only: `categories.json` == template facet `currentValues` byte-for-byte; no
  in-code injection. Guard added in `build_coveo_request_body` (raise when `matched_selected == 0`).
- **Q4 categories (ADJUSTED).** The dispatch's recommended set was infeasible: `tests/test_contracts.py::test_taxonomy_contract`
  requires each requested category's immediate parent in `canonical_category_paths`, and single-segment
  entries are rejected as malformed, so a 2-segment category (`tools/utilities`, `audio/ambient`) cannot be
  requested while excluding the 7 top-level values. The requested set is 8 three-segment live paths:
  `2d/gui/icons`, `2d/textures-materials/stone`, `3d/characters/animals/mammals`, `3d/characters/humanoids`,
  `3d/vegetation/trees`, `3d/vehicles/land`, `audio/music/orchestral`, `vfx/particles/fire-explosions`.
  No live `tools/*` category is 3-segment, so `tools` is not represented.
- **Q5** exclude the 7 single-segment tops. **Q6** real recomputed template hash. **Q7** manual capture
  recorded as an open obligation, no tooling. **Q8** no optional `categories` records.
- **Q9 capture instant.** `config/category_taxonomy.json` and `config/categories.json` carry
  `captured_at_utc = 2026-09-23T07:21:37Z`, the instant the human's live facet capture was delivered
  (human stated the taxonomy was never captured and supplied the live response directly). It is a
  delivery instant, not a separately verified probe instant; a later-known probe instant supersedes it
  without changing any structural decision. The template keeps its own request-capture instant
  `2026-09-17T04:28:28.915Z`. **Q10** no `pipeline.py`/`cli.py` changes.

## Stage log

| Stage | Status | Session / evidence |
|---|---|---|
| Reconnaissance (lead) | DONE | Read F1–F5 sites, SRS §4.1 lines 243–285, `pyproject.toml`, config files, validators baseline. Resolved Q9/Q2 with the human; derived the Q4 feasibility constraint from `validation.py:744-751` + `test_contracts.py:459-461`. |
| Plan — `chunk-planner` | DONE | `ses_f32ca0a02ffeWn3SlSP0br7rzc`. First attempt hit the step cap before writing; resumed and wrote the 402-line FROZEN plan. Appendix A verified by count: 121 entries, comma-split, no single-segment entry (lead, counted). |
| Tests — `test-author` | DONE | `ses_f32ae16c9ffebechHwxDMBw70r`. 14 new nodes + fixtures; `pytest -q` → 11 failed, 599 passed (expected red); traceability 89/596/0/3. |
| Implement — `impl-deep` | DONE | `ses_f328f6bedffeDLqnEo39Enc3Fz`. Source + config regenerated; `pytest -q` → 610 passed; all four validators valid. |
| Review — `spec-reviewer` | VERDICT: PASS | `ses_f3274aef8ffeWNy746FPS8Tk1g`. No Blocker/Major; Minors recorded below. |

## Implementation

- `src/niche_scout/validation.py`: `normalize_category_path` replaces the exact `" > "` before splitting;
  `_canonical_path_shape_preserved` tokenizes both separators. Module stays pure; no new imports.
- `src/niche_scout/collector_coveo.py`: guard `if matched_selected == 0: raise ValueError(...)` after the
  `currentValues` loop, before the body is assembled; public signature unchanged.
- `config/coveo_search_template.json`: `sortCriteria` deleted; facet `currentValues` = the 8 categories;
  `template_sha256 = a6bf5a2a…1229` recomputed and verified.
- `config/categories.json`, `config/category_taxonomy.json`: regenerated; 121-entry inventory; no
  `categories` records; trailing newline restored to match repo style.

## Deviations and review findings (recorded, not silently resolved)

1. **`tests/fixtures/pipeline_fixtures.py` modified although the plan §6 row said "expected unmodified."**
   The new guard made the two un-templated synthetic-category calls impossible, degrading 25 nodes. Minimal
   fix: `graphql_seeded_transport` skips the documented non-join-key fingerprint map when
   `template_path is None`; `EndToEndScenario` gained `template_path`. Lead verified by reading
   `RecordingGraphQLTransport` (`tests/fixtures/pipeline_fixtures.py:712-766`): `_by_identity` is the
   primary lookup and `_by_fingerprint` is only a fallback, and every directory identity is also registered
   by identity (`:824-825`), so skipping the fingerprint map cannot change resolution; no test asserts on
   `_by_fingerprint` (grep). No node ID, marker, or traceability entry changed. Plan §6 note is superseded by
   this entry.
2. **`tests/fixtures/validation_fixtures.py` + `tests/test_validation.py`.** `ONE_ABSENT_CATEGORY` re-pointed
   from `Audio/Music/Orchestral` (casefold-colliding with new `audio/music/orchestral`) to `audio/music/dnb`;
   the two expected-value literals updated. Semantics preserved (one absent requested category →
   `missing_categories`); node IDs unchanged.
3. **Doc/orientation mismatch (pre-existing).** `tests/AGENTS.md` says `tests/traceability.json` is keyed
   LREQ → nodes; the committed file and the validator use node → `[LREQ ids]`. The 14 new entries follow the
   real file; `tests/AGENTS.md` is outside this chunk's file set.
4. **Guard exact-equality note.** The guard compares `value == category` exactly; a future live-form
   capture would fail loudly rather than silently normalize. Matches plan Q3 (config-only coupling).

## Post-fix verification (lead, real output)

| Command | Real result |
|---|---|
| `python -m pytest -q` | `610 passed in 19.32s` (post trailing-newline fix) |
| `python -m niche_scout.tools.validate_traceability` | `Traceability valid: 89 required/defined LREQ IDs mapped, 596 matrix nodes, 0 unmarked analytical tests outside exemption (3 exempted non-analytical nodes)` |
| `python -m niche_scout.tools.check_import_boundaries` | `Import boundaries valid for metrics.py, scoring.py` |
| `python -m niche_scout.tools.check_scope_prohibitions` | valid, 6 tokens checked |
| `python -m niche_scout.tools.check_secrets` | valid |
| config consistency (`python -c`, lead) | template hash match `True`; inventory `121` unique `121`, no single-segment; `taxo_template_sha256 == template hash` `True`; `categories == facet currentValues` `True`; every requested parent present |
| `load_coveo_search_template` | no raise (hash verified); `validate_taxonomy(committed, 8 requested, 2026-09-23T08:00:00Z, 30)` → `valid`, `is_fresh True`, age ≈ 0.027 d (impl run) |
| ruff on changed files | `ruff 0.16.7`: worktree 118 errors vs HEAD byte-exact copies 120 (114 E501 + 2 I001 + 2 F401 + 1 F821 + 1 F841 at HEAD). No new lint; the `F821`/`F401`/`F841`/`I001` are pre-existing. |

**Ruff DoD caveat.** The dispatch DoD says "ruff on changed files clean." The changed source/fixture files
carry a pre-existing E501/F401/F821/F841/I001 backlog (the same repo-wide debt Chunk 13 recorded as
out-of-scope R10). This chunk introduces no new ruff error (worktree 118 < HEAD 120, byte-exact HEAD
extraction via `git show` + `write_bytes`); fixing the backlog would be unreviewable churn in files whose
changed lines are ≤88. This is the one DoD bullet not green on its face; the substantive requirement
(no new lint) holds.

**Human live run.** The DoD bullet "a human-run `niche-scout run` completes (exit 0) or fails only at the
identity preflight" is by design reserved for the human after this gate (the dispatch forbids the agent from
running `niche-scout run`). Pending human execution; the failure mode to expect is the OI-6 identity
preflight limitation, not a discovery abort.

## Open obligations (record, do not silently close)

- **OI-6** (CSRF/session sufficiency, dependency-map §7) remains unowned; live GraphQL auth unverified.
- **Pagination stability** after removing `sortCriteria` is unverified (Q2).
- **Manual taxonomy capture/refresh** procedure (Q7) is an obligation with no owner/tooling; Q9 provenance
  is a delivery instant.
- **URI trailing-identifier extraction** (identity mapping rule 1.0.1) remains unverified; unchanged here.

## Gate

| DoD bullet | Evidence | Status |
|---|---|---|
| Full suite green with real counts | `610 passed` | PASS |
| Four validators valid | outputs above | PASS |
| Ruff on changed files clean | no new lint; pre-existing backlog (caveat above) | PARTIAL (pre-existing) |
| Human live run completes or fails only at preflight | reserved for human post-gate | PENDING HUMAN |
| Config/template mutually consistent; hash matches body | lead `python -c` checks above | PASS |
| Plan, run log, tests, traceability, new convention recorded | plan FROZEN; this log; 14 nodes; 596 matrix entries | PASS |

**GATE: PASSED** on every agent-verifiable bullet (`610 passed`; four validators valid; config and template
consistent; hash verified). Two caveats recorded, not silently resolved: the ruff bullet is met only as
"no new lint" because of pre-existing repo-wide debt, and the human live-run bullet is reserved for the
human per the dispatch.

## Commit

Lead-only commit of the chunk-14 delta (`chunk-14: live-endpoint compatibility remediation`). No push.