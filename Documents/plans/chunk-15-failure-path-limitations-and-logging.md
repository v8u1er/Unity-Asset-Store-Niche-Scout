# Chunk 15 — Failure-path limitations and logging (labeled post-completion remediation)

Status: FROZEN
Depends on (frozen interfaces required before this plan can be trusted):
  - `Documents/interfaces/chunk-02.md` §2.7/§2.8 (the `set_category_status`
    upsert-creates-row contract, `get_category_scores`, `upsert_category_scores`)
    — consumed unchanged. §4 ("No logging of any kind", "No `category_status`
    column") is honoured.
  - `Documents/interfaces/chunk-03.md` §3 (the `CategoryDiscoveryResult` typed
    result, including `issues: tuple[ValidationIssue, ...]`) and §4
    (`discover_category`, `CoveoTransport`) — consumed unchanged.
  - `Documents/interfaces/chunk-10.md` §4 (the `PipelineResult.limitations`
    redaction invariant: "a tuple of redacted strings naming a category and a
    field only") and §5 (`category_status_for` signature and roll-up rule).
  - `Documents/interfaces/chunk-11.md` §4 (line 120/127–129:
    `RunReportView.limitations` is `()`; per-category warnings carry the
    limitations) — consumes `PipelineResult`, never redefined here.
  - `Documents/interfaces/chunk-12.md` §5/§6 (`run_command` prints redacted
    `limitations` to `stderr`; the renderer runs only after a successful return)
    and the chunk-12 plan §5 Ruling 5 / §11 (no render on the failure path).
  - `Documents/plans/chunk-10-pipeline-orchestration.md` §5.3 (the `limitations`
    invariant) and §5.6 (`warnings_json` / `missing_components_json` shapes).
Blocks (chunks whose plan/implementation needs this chunk's interface):
  - None. This is a labeled post-completion remediation after Chunk 13 and the
    Chunk 14 live-endpoint remediation. It introduces no new interface file and
    no downstream contract. No chunk starts on it.

## 1. Goal

Two defects remain on the preflight-failure path and in production observability,
and one of them is what makes the other hard to diagnose:

1. `_persist_failure_limitation_rows` appends the **same** limitation string
   `category <repr>: identity_preflight_status` for **every** requested category,
   even when a category's own discovery failed. It also fabricates
   `DiscoveryStatus.REQUEST_FAILED` when a `category_scores` row is missing
   instead of reading the adapter's actual status. That misreports a discovery
   failure as a preflight failure and defeats the audit purpose of the failure
   row (LREQ-EVD-020, LREQ-NFR-030).
2. No production code configures `logging`, so the one LREQ-NFR-020 INFO record
   (and any diagnostics) are discarded by Python's default `lastResort` handler
   (WARNING+). There is no progress logging and no per-category discovery
   outcome, so a live failure cannot be located from the terminal.

This chunk fixes both with SRS-anchored changes only: the limitation string is
chosen from the category's own final fields (R1), the fabricated status is
replaced by the adapter's actual status or a redacted `PipelineError` (R2), and
an idempotent `cli._configure_logging` plus bounded, redaction-safe
progress/diagnostic lines in `pipeline.py` make the failure path observable (R3).
`collector_coveo.py`, `collector_graphql.py`, `database.py`, `report.py`, every
schema, and the live Coveo root cause stay out of scope (R4); the new logging is
the diagnostic hook for the live failure, not a fix for it.

## 2. Scope

### In scope

- **R1 — limitation content.** In `_persist_failure_limitation_rows`, per
  requested category, compute
  `roll_up = category_status_for(base.discovery_status, warnings=<codes>,
  evidence_grade=EvidenceGrade.INSUFFICIENT.value,
  rankability_status=RankabilityStatus.NOT_RANKABLE.value)`. If
  `roll_up is not CategoryStatus.HEALTHY` append
  `f"category {category!r}: discovery_status"`; **elif** the preflight status is
  not `passed` append `f"category {category!r}: identity_preflight_status"`. No
  run-level or category-less limitation line is emitted; the run-level preflight
  fact is logged instead (R3). `interfaces/chunk-10.md` §4/§6 and the
  `category <repr>: <field>` format are unchanged. (LREQ-EVD-020, LREQ-NFR-030)
- **R2 — no fabricated status.** When `base is None`, create the row with the
  adapter's actual status `discovery_by_category[category].discovery_status.value`;
  when the discovery result is also absent, raise `PipelineError` whose message
  names only the `category_scores` table (never a value). (LREQ-NFR-030,
  LREQ-SEC-020)
- **R3 — logging.** (a) an idempotent `cli._configure_logging(stream=...)`
  attaching exactly one INFO `StreamHandler` to the `niche_scout` logger, called
  from `main()` only; (b) bounded progress/diagnostic lines in `pipeline.py`
  (per-category discovery outcome; a WARNING in `_discover_all`'s `except` arm;
  one run-level identity-preflight outcome line; one run completion/failure
  line); (c) an optional finer DEBUG level inside `pipeline.py` only. No new CLI
  flag and no new environment variable. (LREQ-NFR-020, LREQ-NFR-030, LREQ-ID-040,
  LREQ-CLI-040 supporting)

### Explicitly out of scope (and who owns it instead)

- **`collector_coveo.py` (R4).** No change to request construction, pagination,
  retry, terminal statuses, or `CategoryDiscoveryResult`; the per-category
  `issues` are read (as issue codes) by `pipeline.py`, never mutated. Owner:
  Chunk 3.
- **`collector_graphql.py` (R4).** No change. Owner: Chunk 5 / 6A.
- **`database.py`, any schema change, and any new persisted discovery-error
  column (R4).** The discovery root cause still persists no cause; that is a
  recorded limitation, not a defect fixed here. Owner: none (a future chunk or a
  human ruling).
- **`report.py` and `run --report` on a failed run (R4).** Chunk-12 plan §5
  Ruling 5 and §11 deliberately make it a no-op; `tests/test_cli.py:151-192`
  pins it. Owner: Chunk 11 / 12.
- **The live Coveo root cause (R4).** Not diagnosed or fixed here. The R3
  logging is the diagnostic hook for it.
- **New CLI flags, a `--verbose`/`--quiet` flag, or a new environment variable
  (R3c).** SRS §10 names none; none may be invented. Owner: n/a.
- **Re-opening OI-6 (CSRF/session sufficiency) or URI trailing-identifier
  extraction (identity mapping rule 1.0.1).** Both stay open and unassigned
  (dependency-map §6.4/§7).
- **Rewriting the limitation format.** It stays `category <repr>: <field>`
  (`interfaces/chunk-10.md` §4). No `interfaces/chunk-10.md` edit.

## 3. Requirements this chunk must satisfy

Chunk 15 is a labeled post-completion remediation and has **no
`Documents/requirements-dependency-map.md` §3 section** (the map's chunked plan
ends at Chunk 13; Chunk 14 is the same kind of remediation and is likewise
absent). Its ownership rows are therefore read from the §"Ownership and test
traceability matrix" (map §1, lines 69/73/104/122/123/278/285/286). No new
dependency-map section is created and no interface file is edited.

| LREQ ID | Ownership role here | Normative text (from `SRS-lean.md`, quoted/derived) | SRS section |
|---|---|---|---|
| LREQ-EVD-020 | Integration completion (matrix line 104: primary Chunk 9A; supporting 3/5/6A/7B/8; completion Chunk 10) | "A category is `not_rankable` when any of the following applies: discovery filtering is unverified; any unresolved or conflicting discovery identity remains in the category; ... identity preflight fails; ... The implementation SHALL first construct a fixed `base_rankable_candidates` set. ... Sensitivity SHALL not be used to construct this set." The failure-path limitation must name the *actual* not-rankable reason's field, so a discovery-failed category is not mislabelled as preflight-failed. | §9.1 (lines 980–994) |
| LREQ-ID-040 | Integration completion (matrix line 73: primary Chunk 6A; supporting 2/5; completion 6A and 10) | "A preflight below the minimum success rate or above the maximum conflict rate SHALL stop bulk enrichment and mark the run failed. The failure SHALL include sampled counts, mismatch counts, endpoint signature, mapping-rule version, and a redacted diagnostic summary." Plus: "When `unique preflight identities attempted = 0`, both rates SHALL be null, the preflight SHALL be `insufficient`, and bulk enrichment SHALL not start." The run-level log line carries status + integer counts only (R3b-3). | §4.4 (lines 386–391, 408–410) |
| LREQ-NFR-020 | Integration completion (matrix line 122: primary Chunk 6B; supporting 2/6A; completion Chunk 10) | "Before bulk enrichment, log discovered canonical assets, sampled assets, unique enrichment identities, and projected minimum enrichment time." This chunk only makes existing/future records reachable by configuring a handler; it does **not** add a second projection line and does **not** change `log_enrichment_projection`. | §11 (lines 1165–1166) |
| LREQ-NFR-030 | Primary (matrix line 123: primary Chunk 10; supporting 3/5/6A/6B; completion Chunk 10) | "A failed page or sampled asset SHALL not abort unrelated categories or assets; the failure SHALL remain visible in status and evidence fields." The per-category limitation field must carry the discovery failure, and a per-category discovery outcome log makes it visible at run time. | §11 (lines 1168–1169) |
| LREQ-CLI-040 | Supporting orchestration (matrix line 120: primary Chunk 12; supporting 1/8/9A/10; completion Chunk 12) | "The pipeline SHALL reject a run with fewer than `MIN_CATEGORIES_PER_RUN` requested categories before producing a ranking. It SHALL retain a completed run's collection timestamp and explicit limitations in the report." Unchanged here; the corrected limitation strings are what Chunk 12 prints to `stderr`. | §10 (lines 1154–1156) |
| LREQ-SEC-020 | Supporting redaction (matrix line 69: primary Chunk 2; supporting 0/3/5; completion Chunk 13) | "Secrets SHALL NOT be written to source control, logs, SQLite, or error messages." Bound on every new log line and on the R2 `PipelineError` message. | §4.3 (lines 351–352) |

Derived behavior this chunk implements without a new LREQ (from the dependency
map Chunk 10 gate and reconciliation, recorded here so tests can name a source):

- Dependency-map §3 Chunk 10 gate (line 1003): "If identity preflight fails:
  persist `run.status = failed`, retain discovery/sample/preflight observations,
  issue no bulk-enrichment requests, skip metric/score/ranking computation,
  **persist category limitations where possible**, produce no rankable scores,
  ...". R1 makes "where possible" accurate per category.
- Dependency-map §3 Chunk 10 gate (line 1005): "Category-level failure is
  represented internally by a typed `CategoryStatus` (`healthy`, `degraded`,
  `failed`) and mapped to `discovery_status`, warnings, `evidence_grade`, and
  `rankability_status`; it is not a separate persisted enum". R1 uses the mapping
  to choose the limitation field; it adds no column.
- Dependency-map §6.5 (line 1176): category failure is carried by
  `discovery_status`, warnings, `evidence_grade`, and `rankability_status`.
- Chunk-10 plan §5.3: `limitations` "is a tuple of redacted strings naming a
  category and a field only".
- `interfaces/chunk-11.md` §4 (lines 127–129): `RunReportView.limitations` is
  `()`; there is no run-level limitation column — hence R1's prohibition on a
  run-level limitation line.

## 4. Interface contracts consumed

Copied from the frozen interface files (not re-derived from source):

- `interfaces/chunk-10.md` §5:
  `category_status_for(discovery_status: str, *, warnings: Sequence[str],
  evidence_grade: str, rankability_status: str) -> CategoryStatus`.
  Roll-up rule: `page_failed`/`request_failed` → `FAILED`; `truncated`/
  `filter_unverified`/`category_mismatch`/`identity_incomplete` → `DEGRADED`;
  otherwise `HEALTHY`. The rule reads **only** `discovery_status`; the other
  three arguments are carried and derive nothing.
- `interfaces/chunk-10.md` §2/§4: `PipelineResult(run_id, status,
  scoring_cutoff_utc, categories, identity_preflight_status,
  category_scores_written, limitations)`; `limitations` names a category and a
  field only.
- `interfaces/chunk-03.md` §3: `CategoryDiscoveryResult` carries
  `discovery_status: DiscoveryStatus`, `conditions: tuple[DiscoveryStatus, ...]`,
  `issues: tuple[ValidationIssue, ...]` (line 440 of `collector_coveo.py`).
  `ValidationIssue` (`validation.py:279-292`) has `code: str`, `message: str`,
  `context: dict[str, Any]`; `code` is a stable machine-readable identifier.
- `interfaces/chunk-02.md` §2.7: `set_category_status(run_id, category,
  discovery_status, *, computed_at_utc)` "creates the row on first write if it
  does not exist yet"; §2.8 `get_category_scores(run_id)` returns rows ordered by
  `category` ASC.
- `interfaces/chunk-12.md` §5/§6: `cli.run_command` prints redacted
  `limitations` to `stderr`; `cli.main(argv) -> int` "never calls `sys.exit`
  itself".

**Signature-freeze facts (verified by reading, this session).**

- `tests/test_pipeline.py:55-70` resolves pipeline symbols through
  `_pipeline_symbol`; new pipeline tests must keep that discipline so an
  unwritten symbol fails only its own node.
- `tests/fixtures/pipeline_fixtures.py:884` records the pipeline logger name as
  `niche_scout.pipeline`; `:855-879` `LogCapture.assert_projection_logged` treats
  **any** message containing `"enrichment"` (case-insensitive) as the projection
  line, and `:207-208` `_projection_messages` filters on the same substring in
  `tests/test_pipeline.py`. Every new discovery log line **MUST NOT** contain
  `"enrichment"`.
- `tests/test_enrichment.py:219-239` asserts `len(messages) == 1` for a **direct**
  call to `pipeline.log_enrichment_projection`; it does not run the pipeline, so
  new pipeline log lines cannot reach it.
- `pyproject.toml:21-37` has **no** logging configuration; `[tool.ruff]
  line-length = 88`; `[tool.ruff.lint] select = ["E", "F", "I"]`.
- `tests/traceability.json` is committed **node-ID → array of LREQ IDs**
  (lines 1–40) and `validate_traceability.py:163-177, 204-212` enforces that
  orientation (`missing_nodes`, `marker_mismatch`, `orphan_nodes`).
  `tests/AGENTS.md` lines 5–13 describe the opposite orientation and are **stale**
  (chunk-13 plan §2 R3 records the same finding). The committed file and the
  validator govern.

## 5. Interface contract this chunk produces

**None.** This is a labeled post-Chunk-13 remediation, not a dependency-map
chunk. No new `interfaces/chunk-15.md` is created; no downstream chunk consumes a
new surface from it.

Three behavioral records replace interface-document state without rewriting the
frozen interface files:

1. The failure-path `limitations` content is per category and conditioned on the
   category's own roll-up (R1); the string format is unchanged.
2. `_persist_failure_limitation_rows` no longer fabricates a discovery status
   (R2); the `base is None` branch reads the adapter's actual status.
3. `cli._configure_logging` and the `pipeline.py` log templates in §7 become
   frozen process diagnostics (R3). `interfaces/chunk-10.md` §5 (the LREQ-NFR-020
   projection line) and `interfaces/chunk-12.md` §5 are **not** edited.

## 6. Files touched

| File | New/modified | Purpose |
|---|---|---|
| `src/niche_scout/pipeline.py` | modified | R1 limitation content; R2 real status; R3b progress/diagnostic logging (`_log_discovery_outcome`, `_log_preflight_outcome`, except-arm warning, run-status line). `_LOGGER` (line 164) is reused; `logging` is already imported. |
| `src/niche_scout/cli.py` | modified | R3a: add `import logging`; add `_configure_logging` and its constants; call it from `main()` only. |
| `tests/test_pipeline.py` | modified | Six new analytical nodes (§9). Existing nodes unchanged. |
| `tests/test_cli.py` | modified | Two new analytical nodes (§9). Existing nodes unchanged. |
| `tests/traceability.json` | modified | Eight new node → LREQ-array entries (§9). |
| `tests/fixtures/pipeline_fixtures.py` | audited, expected unmodified | The all-complete run in §9 is built inline from the public builders (`RecordingCoveoTransport`, `coveo_page`, `coveo_record`, `end_to_end_scenario`, `write_run_local_template`, `fixture_config`, `ErrorCoveoTransport`). Change only if a real assertion breaks; a break is reported, not silently patched. |
| `tests/fixtures/cli_fixtures.py` | audited, expected unmodified | `_configure_logging` nodes need no fixture: they call the helper directly and monkeypatch it for the `main` node. |

**Not touched:** `collector_coveo.py`, `collector_graphql.py`, `database.py`,
`report.py`, `metrics.py`, `scoring.py`, `models.py`, `config.py`,
`src/niche_scout/tools/**`, `pyproject.toml`, `Documents/SRS-lean.md`,
`Documents/requirements-dependency-map.md`, `AGENTS.md`, `kilo.json(c)`,
`.kilo/`, and every `Documents/interfaces/*` file.

## 7. Exact edits per file

Line anchors below are the working-tree state read this session; they are
anchors, not contents. The plan's task list cites the same anchors.

### 7.1 `src/niche_scout/pipeline.py`

**E1 — `_discover_all` `except` arm (current lines 2812–2820): log a redacted
warning (R3b-2).**

Current:

```python
        except Exception:
            with repository.transaction():
                repository.set_category_status(
                    run_id,
                    category,
                    DiscoveryStatus.REQUEST_FAILED.value,
                    computed_at_utc=clock(),
                )
            result = _failed_discovery_result(category)
```

Replace with:

```python
        except Exception as exc:
            _LOGGER.warning(
                "category %s: discovery request failed (%s)",
                category,
                type(exc).__name__,
            )
            with repository.transaction():
                repository.set_category_status(
                    run_id,
                    category,
                    DiscoveryStatus.REQUEST_FAILED.value,
                    computed_at_utc=clock(),
                )
            result = _failed_discovery_result(category)
```

`str(exc)` is **never** logged (it can carry a URL, response body, or provider
message). Only the category and the exception class name are logged.

**E2 — per-category discovery outcome (R3b-1).**

After the loop body's `results[category] = result` (current line 2821), add
`_log_discovery_outcome(result)` inside the `for` loop. Then add the new private
helper immediately after `_discover_all` returns (before
`_persist_failure_limitation_rows`, current line 2825):

```python
def _log_discovery_outcome(discovery: CategoryDiscoveryResult) -> None:
    """Emit one bounded per-category discovery outcome line (LREQ-NFR-030).

    INFO when the category roll-up is ``CategoryStatus.HEALTHY``, WARNING
    otherwise. The message carries the category, the terminal discovery status,
    the ordered condition codes, and the issue codes only: never an identity
    string, credential, header value, cookie, or response body
    (LREQ-SEC-010/020). ``warnings``/``evidence_grade``/``rankability_status``
    are the values :func:`category_status_for` carries but derives nothing from;
    the roll-up reads ``discovery_status`` alone. The message never contains the
    substring ``"enrichment"`` (case-insensitive) so the LREQ-NFR-020 projection
    filter and its redaction nodes keep their scope.
    """
    roll_up = category_status_for(
        discovery.discovery_status.value,
        warnings=(),
        evidence_grade=EvidenceGrade.INSUFFICIENT.value,
        rankability_status=RankabilityStatus.NOT_RANKABLE.value,
    )
    conditions = ",".join(condition.value for condition in discovery.conditions)
    issues = ",".join(issue.code for issue in discovery.issues)
    message = "category %s: discovery %s conditions=[%s] issues=[%s]"
    arguments = (
        discovery.category,
        discovery.discovery_status.value,
        conditions,
        issues,
    )
    if roll_up is CategoryStatus.HEALTHY:
        _LOGGER.info(message, *arguments)
    else:
        _LOGGER.warning(message, *arguments)
```

Edge contract: an empty `conditions`/`issues` tuple renders as `[]` (the join
of nothing is `""`). Category paths are not secrets and are already named by the
limitation strings; identity strings and exception messages are not logged.

**E3 — `_persist_failure_limitation_rows`: read the real status (R2); current
lines 2847–2873.**

Current loop head:

```python
    for category in categories:
        base = persisted.get(category)
        if base is None:
            repository.set_category_status(
                run_id,
                category,
                DiscoveryStatus.REQUEST_FAILED.value,
                computed_at_utc=clock(),
            )
            base = next(
                (
                    row
                    for row in repository.get_category_scores(run_id)
                    if row.category == category
                ),
                None,
            )
            if base is None:
                raise PipelineError(f"category {category!r}: category_scores")
        discovery = discovery_by_category.get(category)
        codes = _warning_codes(
```

Replace with (note `discovery` moves up; the later duplicate lookup is removed):

```python
    for category in categories:
        discovery = discovery_by_category.get(category)
        base = persisted.get(category)
        if base is None:
            if discovery is None:
                raise PipelineError(f"category {category!r}: category_scores")
            repository.set_category_status(
                run_id,
                category,
                discovery.discovery_status.value,
                computed_at_utc=clock(),
            )
            base = next(
                (
                    row
                    for row in repository.get_category_scores(run_id)
                    if row.category == category
                ),
                None,
            )
            if base is None:
                raise PipelineError(f"category {category!r}: category_scores")
        codes = _warning_codes(
```

Edge contract: `discovery_by_category` is keyed by the same `categories` the
caller passes (its only caller, `run_pipeline`, builds it from `requested` and
passes `requested`), so `discovery is None` is unreachable for a category that
went through `_discover_all`; the branch exists so a caller-supplied mismatch
fails closed with a redacted message. The `PipelineError` message keeps the
existing `category <repr>: category_scores` shape (line 2865 and the sibling at
`_build_scored_rows` line 2945) and carries no value.

**E4 — `_persist_failure_limitation_rows`: choose the limitation field (R1);
current line 2896.**

Current:

```python
        limitations.append(f"category {category!r}: identity_preflight_status")
```

Replace with (inserted after the `rows.append(replace(...))` block, before the
persistence `with` block):

```python
        roll_up = category_status_for(
            base.discovery_status,
            warnings=codes,
            evidence_grade=EvidenceGrade.INSUFFICIENT.value,
            rankability_status=RankabilityStatus.NOT_RANKABLE.value,
        )
        if roll_up is not CategoryStatus.HEALTHY:
            limitations.append(f"category {category!r}: discovery_status")
        elif preflight_status != IdentityPreflightStatus.PASSED.value:
            limitations.append(f"category {category!r}: identity_preflight_status")
```

The `roll_up` arguments match the persisted row exactly
(`evidence_grade=EvidenceGrade.INSUFFICIENT.value`,
`rankability_status=RankabilityStatus.NOT_RANKABLE.value` in the `replace`
call above), so the limitation and the row agree.

**E5 — run-level preflight outcome line (R3b-3).**

In `run_pipeline`, immediately after
`page_view_status = _page_view_status(repository, resolved_run_id)`
(current line 3209), add `_log_preflight_outcome(preflight_outcome)`. Add the
helper next to the other run-level helpers (a placement near `_page_view_status`
is sufficient; before `_warning_codes` at line 2542):

```python
def _log_preflight_outcome(outcome: IdentityPreflightOutcome) -> None:
    """Emit one bounded run-level identity-preflight outcome line (LREQ-ID-040).

    ``WARNING`` when the status is not ``passed``, ``INFO`` otherwise. The
    message carries the status and the four integer unique-identity counts only:
    never an identity string, endpoint URL, header value, correlation payload,
    or diagnostic summary. The message never contains the substring
    ``"enrichment"`` (case-insensitive).
    """
    summary = outcome.summary
    message = (
        "identity preflight: status=%s attempted=%d successful=%d "
        "conflicting=%d other_failed=%d"
    )
    arguments = (
        outcome.status.value,
        summary.attempted_unique_identities,
        summary.successful_unique_identities,
        summary.conflicting_unique_identities,
        summary.other_failed_unique_identities,
    )
    if outcome.status is IdentityPreflightStatus.PASSED:
        _LOGGER.info(message, *arguments)
    else:
        _LOGGER.warning(message, *arguments)
```

**E6 — run completion/failure line (R3b-4).**

- Failure path: immediately before the `return PipelineResult(...)` at current
  line 3224, add
  `_LOGGER.info("run %s: %s", resolved_run_id, RunStatus.FAILED.value)`.
- Completed path: immediately before the final `return PipelineResult(...)` at
  current line 3365, add
  `_LOGGER.info("run %s: %s", resolved_run_id, final_status)`.

Exactly one run-status line is emitted per run. The run id is not a secret.

**E7 — optional.** A finer `_LOGGER.debug(...)` level may be added inside
`pipeline.py` only. It is optional, adds no requirement, and must obey the same
redaction and `"enrichment"`-substring constraints.

### 7.2 `src/niche_scout/cli.py`

**E8 — `_configure_logging` and its call (R3a).**

Add `import logging` to the stdlib import block (current lines 29–38; between
`import argparse` and `import sys` to keep ruff's `I` ordering). Add the
constants and helper near the other module constants (after
`_DEFAULT_GRAPHQL_TIMEOUT_SECONDS`, current line 53):

```python
#: The logger root every package module nests under (``niche_scout.pipeline``
#: is ``logging.getLogger("niche_scout.pipeline")``).
_LOGGER_ROOT: str = "niche_scout"

#: Concise, single-line production format: level, logger, message.
_LOG_FORMAT: str = "%(levelname)s %(name)s: %(message)s"

#: Marker attribute set on the handler this helper installs, so a repeated call
#: can recognize and replace its own handler instead of duplicating it.
_HANDLER_MARKER: str = "_niche_scout_logging_handler"


def _configure_logging(stream: TextIO | None = None) -> None:
    """Attach exactly one INFO ``StreamHandler`` to the ``niche_scout`` logger.

    ``stream`` defaults to the *current* ``sys.stderr``, resolved at call time so
    a caller's captured buffer is honoured. Idempotent: any handler this function
    previously installed is removed before the new one is added, so repeated calls
    leave exactly one marked handler. Called from :func:`main` only — never from
    :func:`run_command` or :func:`dashboard_command` — so direct-call test seams
    stay silent. Reads no environment variable and defines no verbosity flag
    (SRS §10 names none).
    """
    logger = logging.getLogger(_LOGGER_ROOT)
    logger.setLevel(logging.INFO)
    for handler in list(logger.handlers):
        if getattr(handler, _HANDLER_MARKER, False):
            logger.removeHandler(handler)
    handler = logging.StreamHandler(sys.stderr if stream is None else stream)
    handler.setLevel(logging.INFO)
    handler.setFormatter(logging.Formatter(_LOG_FORMAT))
    setattr(handler, _HANDLER_MARKER, True)
    logger.addHandler(handler)
```

In `main()` (current line 489), add `_configure_logging()` as the first
statement, before `parser = build_parser()`.

Edge contract: the helper never touches the root logger and never disables
propagation; it adds at most one handler to `niche_scout`. Calling it twice
leaves exactly one handler (the first, unmarked, is not this helper's). A test
that calls `cli.main` should monkeypatch `cli._configure_logging` so no handler
is installed for the rest of the session (see §9 node 8).

## 8. Edge cases and invariants

- **Roll-up reads only `discovery_status`.** `category_status_for` derives
  nothing from `warnings`/`evidence_grade`/`rankability_status`
  (`interfaces/chunk-10.md` §5). A `complete` category → `HEALTHY` →
  `identity_preflight_status`; `page_failed`/`request_failed` → `FAILED`;
  `truncated`/`filter_unverified`/`category_mismatch`/`identity_incomplete` →
  `DEGRADED`; both non-HEALTHY cases → `discovery_status`.
- **The failure path always has a non-`passed` preflight.** `_persist_failure_limitation_rows`
  is called only from the `if preflight_status is not IdentityPreflightStatus.PASSED`
  branch (`pipeline.py:3211-3223`), so the `elif` in E4 always fires when the
  roll-up is healthy. It is written as an `elif` so the R1 rule is expressed
  literally and cannot silently emit both lines.
- **No run-level limitation line.** Every appended string names a requested
  category; the module never appends a category-less string. The run-level
  preflight fact is the R3b-3 log line instead.
- **Exactly one limitation per requested category.** The loop appends at most one
  string per iteration, so `len(result.limitations) == len(requested)` on the
  failure path and the returned tuple is in declared-category order.
- **Existing limitation format preserved.** `category <repr>: <field>` with
  `<field>` in `{discovery_status, identity_preflight_status}`; no new field name
  is introduced.
- **`base is None` never fabricates a status.** The status written is
  `discovery_by_category[category].discovery_status.value`. `None` for the
  discovery result is an orchestration error, not a status: it raises
  `PipelineError` naming `category_scores`, never a value.
- **Discovery log lines contain no `"enrichment"`.** The three templates in §7
  (per-category discovery outcome, failed discovery request, run status) and the
  preflight outcome template contain none. This keeps
  `tests/fixtures/pipeline_fixtures.py::LogCapture.assert_projection_logged` and
  `tests/test_pipeline.py::_projection_messages` scoped to the LREQ-NFR-020 line.
- **No identity string in any new log line.** `_log_discovery_outcome` logs the
  category path, status enum values, condition codes, and `ValidationIssue.code`
  tokens only. `_log_preflight_outcome` logs the status and integer counts.
  `_discover_all` logs the exception class name only.
- **Redaction is not weakened.** Category paths already appear in the
  `limitations` strings Chunk 12 prints to `stderr`; the log lines add no
  credential, header value, cookie, response body, token, or identity.
- **Idempotence.** `_configure_logging` results in exactly one marked handler on
  the `niche_scout` logger regardless of how many times it is called.
- **Purity preserved.** `pipeline.py` is an I/O/orchestration module; no clock is
  read except through the injected `clock`, and `metrics.py`/`scoring.py` are
  untouched. Logging is side-effect I/O already owned by `pipeline.py`.
- **Determinism of the limitation tuple.** The tuple depends only on declared
  category order and persisted fields; no set/dict iteration order, no clock, no
  RNG.
- **Pre-existing failing-preflight nodes keep passing.**
  `tests/test_pipeline.py::test_failed_preflight_persists_per_category_limitations`
  asserts only that the rows exist, carry warnings, and that no sentinel appears
  in `result.limitations`; the per-category strings change from uniform to
  conditioned, so it still passes. `tests/test_pipeline.py:473-476` also still
  passes because the new strings still name only a category and a field.

## 9. Test plan

- **Files:** the six pipeline nodes go in `tests/test_pipeline.py`; the two CLI
  nodes go in `tests/test_cli.py`. No new test module (not authorized) and no new
  fixture module.
- **Fixtures:** expected unmodified. The all-complete run is built inline from
  `tests/fixtures/pipeline_fixtures.py` public builders.
- **Traceability keying (verified this session):** the committed matrix is
  **node-ID → array of LREQ IDs**; `validate_traceability.py` enforces that
  orientation. Add entries in that orientation. Key order in the JSON file does
  not affect the validator; matching the file's existing sorted placement keeps
  the diff small.
- **Exact markers and matrix values** (each node must carry exactly these marker
  arguments and exactly matching `tests/traceability.json` values):

| pytest node ID | `@pytest.mark.lreq(...)` marker args | `tests/traceability.json` value |
|---|---|---|
| `tests/test_pipeline.py::test_failure_path_limitations_use_discovery_status_when_rollup_is_failed` | `LREQ-NFR-030`, `LREQ-EVD-020` | `["LREQ-NFR-030", "LREQ-EVD-020"]` |
| `tests/test_pipeline.py::test_failure_path_limitations_use_identity_preflight_status_when_discovery_healthy` | `LREQ-NFR-030`, `LREQ-ID-040` | `["LREQ-NFR-030", "LREQ-ID-040"]` |
| `tests/test_pipeline.py::test_failure_path_limitation_strings_name_category_and_field_only` | `LREQ-NFR-030`, `LREQ-SEC-020` | `["LREQ-NFR-030", "LREQ-SEC-020"]` |
| `tests/test_pipeline.py::test_discovery_outcome_log_line_is_emitted_on_pipeline_logger` | `LREQ-NFR-030` | `["LREQ-NFR-030"]` |
| `tests/test_pipeline.py::test_discovery_failure_log_omits_exception_message_and_sentinels` | `LREQ-NFR-030`, `LREQ-SEC-020` | `["LREQ-NFR-030", "LREQ-SEC-020"]` |
| `tests/test_pipeline.py::test_run_level_preflight_and_run_status_lines_are_logged` | `LREQ-ID-040`, `LREQ-NFR-030` | `["LREQ-ID-040", "LREQ-NFR-030"]` |
| `tests/test_cli.py::test_configure_logging_attaches_exactly_one_handler_and_is_idempotent` | `LREQ-NFR-020` | `["LREQ-NFR-020"]` |
| `tests/test_cli.py::test_main_invokes_configure_logging` | `LREQ-NFR-020` | `["LREQ-NFR-020"]` |

- **Node 1 —
  `test_failure_path_limitations_use_discovery_status_when_rollup_is_failed`.**
  Run: the eight `fx.END_TO_END_CATEGORIES` with a run-local template
  (`fx.write_run_local_template`), `coveo_transport=fx.ErrorCoveoTransport()`,
  `identity_preflight_assets_per_category=3`, `identity_preflight_min_success_rate=1.0`,
  `min_categories_per_run=SCENARIO_CATEGORY_COUNT`,
  `max_discovery_results_per_category=fx.SCENARIO_DISCOVERY_CAP`, taxonomy from
  `fx.taxonomy_payload(fx.END_TO_END_CATEGORIES)` (mirroring
  `test_insufficient_preflight_leaves_run_non_completed` and
  `test_failed_page_is_not_zero_assets`). Precondition assertions:
  `result.status == RunStatus.FAILED.value` and
  `result.identity_preflight_status == IdentityPreflightStatus.INSUFFICIENT.value`.
  Golden (hand-derived from `category_status_for(request_failed, ...) is FAILED`):

  ```python
  assert result.limitations == tuple(
      f"category {category!r}: discovery_status"
      for category in fx.END_TO_END_CATEGORIES
  )
  for limitation in result.limitations:
      assert "identity_preflight_status" not in limitation
  ```

- **Node 2 —
  `test_failure_path_limitations_use_identity_preflight_status_when_discovery_healthy`.**
  Build `template_path = fx.write_run_local_template(tmp_path, fx.END_TO_END_CATEGORIES)`,
  `scenario = fx.end_to_end_scenario(template_path=template_path)`, then an inline
  all-complete Coveo transport over every declared category:

  ```python
  complete = fx.RecordingCoveoTransport(
      {
          category: (
              fx.coveo_page(
                  [
                      fx.coveo_record(0, f"k{index}-a", category),
                      fx.coveo_record(1, f"k{index}-b", category),
                  ],
                  total_count=2,
                  filtered_count=2,
              ),
          )
          for index, category in enumerate(fx.END_TO_END_CATEGORIES)
      }
  )
  ```

  Config: `min_categories_per_run=SCENARIO_CATEGORY_COUNT`,
  `max_discovery_results_per_category=fx.SCENARIO_DISCOVERY_CAP`,
  `identity_preflight_assets_per_category=3`,
  `identity_preflight_min_success_rate=1.0`. Pass `coveo_transport=complete` and
  the scenario's `graphql_transport` (never called). Preconditions:
  `result.status == RunStatus.FAILED.value`,
  `result.identity_preflight_status == IdentityPreflightStatus.INSUFFICIENT.value`,
  and every persisted row has `discovery_status == DiscoveryStatus.COMPLETE.value`
  (so the roll-up is `HEALTHY`). Golden:

  ```python
  assert result.limitations == tuple(
      f"category {category!r}: identity_preflight_status"
      for category in fx.END_TO_END_CATEGORIES
  )
  ```

- **Node 3 —
  `test_failure_path_limitation_strings_name_category_and_field_only`.**
  Reuse node 1's run (or node 2's). Assert every limitation matches
  `re.fullmatch(r"category .+: (discovery_status|identity_preflight_status)", limitation)`,
  that each limitation contains the `repr` of a requested category, and that no
  string in `fx.RECORDED_SENTINELS` and no fixture identity (`k0-a`, `900`,
  `901`, `902`) appears in any limitation. This pins the format and the
  redaction invariant without changing `interfaces/chunk-10.md`.

- **Node 4 —
  `test_discovery_outcome_log_line_is_emitted_on_pipeline_logger`.**
  Run node 1's scenario inside
  `with caplog.at_level(logging.INFO, logger="niche_scout.pipeline"):`. Collect
  `[record.getMessage() for record in caplog.records]` and the records
  themselves. Assert:
  - there is at least one record whose message starts with
    `f"category {fx.END_TO_END_CATEGORIES[0]}: discovery "` and contains
    `"conditions=["` and `"issues=["`;
  - that record's `levelno == logging.WARNING` (discovery failed → roll-up not
    `HEALTHY`);
  - no message contains `"enrichment"` (case-insensitive);
  - no message contains a string in `fx.RECORDED_SENTINELS`.
  The condition/issue token lists are discovery-internal, so they are asserted as
  present (`conditions=[...]`, `issues=[...]`), not by exact value.

- **Node 5 —
  `test_discovery_failure_log_omits_exception_message_and_sentinels`.**
  Define a test-local transport in `tests/test_pipeline.py`:

  ```python
  class _ExplodingCoveoTransport:
      """A transport whose send() raises with a sentinel-bearing message."""

      def __init__(self, message: str) -> None:
          self._message = message

      def send(self, url: str, headers: Mapping[str, str], payload: bytes) -> Any:
          raise RuntimeError(self._message)
  ```

  Run the eight categories with `_ExplodingCoveoTransport(fx.RECORDED_SENTINELS[4])`
  and the node 1 config, inside caplog at `logger="niche_scout.pipeline"`.
  Hand-derived assertion: for every category,
  `f"category {category}: discovery request failed (RuntimeError)"` is in the
  messages. Assert no message contains `fx.RECORDED_SENTINELS[4]` and that the
  run still returns `status == RunStatus.FAILED.value` (failure isolation,
  LREQ-NFR-030).

- **Node 6 — `test_run_level_preflight_and_run_status_lines_are_logged`.**
  Run node 2's all-complete scenario with an explicit `run_id`, inside caplog at
  `logger="niche_scout.pipeline"`. Hand-derived exact assertions:
  `"identity preflight: status=insufficient attempted=0 successful=0 conflicting=0 other_failed=0"`
  is in the messages, and `f"run {run_id}: failed"` is in the messages. Assert no
  message contains any fixture identity (`k0-a`, `k1-a`) or any
  `fx.RECORDED_SENTINELS` string.

- **Node 7 —
  `test_configure_logging_attaches_exactly_one_handler_and_is_idempotent`.**
  In `tests/test_cli.py`:

  ```python
  logger = logging.getLogger("niche_scout")
  before_handlers = list(logger.handlers)
  before_level = logger.level
  try:
      cli._configure_logging(io.StringIO())
      cli._configure_logging(io.StringIO())
      marked = [
          handler
          for handler in logger.handlers
          if getattr(handler, cli._HANDLER_MARKER, False)
      ]
      assert len(marked) == 1
      assert marked[0].level == logging.INFO
      assert marked[0].formatter is not None
      assert marked[0].formatter._fmt == cli._LOG_FORMAT
  finally:
      for handler in list(logger.handlers):
          if handler not in before_handlers:
              logger.removeHandler(handler)
      logger.setLevel(before_level)
  ```

  Do not assert on `logger.handlers` length overall (other tooling may have
  added handlers); assert on the marked set.

- **Node 8 — `test_main_invokes_configure_logging`.** Monkeypatch
  `cli._configure_logging` with a recorder and call `cli.main([])`; assert the
  recorder was called exactly once and `cli.main([]) == cli.EXIT_USAGE_ERROR`.
  Monkeypatching prevents a real handler from leaking into the rest of the
  session.

- **Golden vectors / expected values.** All expected values above are
  hand-derived: the limitation strings from `category_status_for`'s documented
  rule, the preflight-log counts from SRS §4.4 ("`attempted = 0` ⇒ both rates
  null, status `insufficient`"), and the exact log templates frozen in §7. No
  golden-vector file is added.

- **Existing nodes that must keep passing unchanged:**
  `tests/test_pipeline.py::test_failed_preflight_persists_per_category_limitations`
  (now sees conditioned strings; its assertions are satisfied),
  `tests/test_pipeline.py::test_enrichment_projection_is_logged_before_first_request`,
  `tests/test_pipeline.py::test_projection_contains_required_counts_and_minimum_time`,
  `tests/test_pipeline.py::test_projection_log_contains_no_secret_or_identity`
  (the `"enrichment"` substring filter excludes the new lines),
  `tests/test_enrichment.py::test_projection_log_line_contains_no_credential_or_identity`
  (direct call to `log_enrichment_projection`; unaffected),
  `tests/test_cli.py::test_run_command_does_not_render_on_failure_path` (lines
  151–192; failure-path rendering stays a no-op).

- **Contradiction handling.** If any existing test contradicts the SRS or this
  plan after these changes, the test-author leaves it and reports
  `DISPUTE: <test id> — SRS §x says ...`; it is not silently edited.

## 10. Definition of done (gate)

Chunk 15 has no `requirements-dependency-map.md` §3 gate. The gate below carries
the dispatch's Definition of Done and the in-scope Chunk 10 gate bullets
(dependency-map §3 lines 996–1007) this remediation touches.

Copied from dependency-map §3 Chunk 10 gate (in-scope bullets):

- "A failed category does not abort unrelated categories."
- "A failed preflight prevents enrichment."
- "If identity preflight fails: persist `run.status = failed`, retain
  discovery/sample/preflight observations, issue no bulk-enrichment requests,
  skip metric/score/ranking computation, **persist category limitations where
  possible**, produce no rankable scores, allow the dashboard to display the
  failed run as an audit/diagnostic report, and return a non-zero CLI exit code."
- "Category-level failure is represented internally by a typed `CategoryStatus`
  (`healthy`, `degraded`, `failed`) and mapped to `discovery_status`, warnings,
  `evidence_grade`, and `rankability_status`; it is not a separate persisted enum
  unless the schema explicitly adds that field."
- "On preflight failure, the report read model uses one null-score
  `category_scores` row per requested category with persisted discovery/sample
  fields, `evidence_grade = insufficient`, `rankability_status = not_rankable`,
  and explicit preflight warnings."

Dispatch Definition of Done:

- Full suite green (`python -m pytest -q`) with the real counts reported; if an
  unrelated pre-existing failure exists, report it verbatim rather than claiming
  green.
- All validators valid: `python -m niche_scout.tools.validate_traceability`,
  `python -m niche_scout.tools.check_import_boundaries`,
  `python -m niche_scout.tools.check_scope_prohibitions`,
  `python -m niche_scout.tools.check_secrets`.
- `ruff format` and `ruff check` clean on the changed files (`pyproject.toml`:
  `line-length = 88`, `select = ["E", "F", "I"]`).
- Failure-path limitations are per category and match
  `category <repr>: (discovery_status|identity_preflight_status)`; a
  discovery-failed category never reports `identity_preflight_status`.
- No fabricated discovery status on the `base is None` path; no new persisted
  column, no schema change.
- `_configure_logging` is idempotent, attaches exactly one handler to the
  `niche_scout` logger, and is invoked by `cli.main`.
- Progress/diagnostic logging is emitted on the `niche_scout.pipeline` logger,
  carries no sentinel/identity/credential/header/body, and no new discovery log
  line contains `"enrichment"`.
- No new CLI flag and no new environment variable were added.

## 11. Explicit prohibitions

- No live network in development or tests; tests never call the real endpoint.
- No edits to `collector_coveo.py`, `collector_graphql.py`, `database.py`,
  `report.py`, `metrics.py`, `scoring.py`, `models.py`, `config.py`, or any
  `Documents/interfaces/*` file (R4).
- No schema change, no new persisted column, no new discovery-error column.
- No change to the limitation string format or to `interfaces/chunk-10.md`.
- No run-level or category-less limitation line.
- No new CLI flag (including `--verbose`/`--quiet`) and no new environment
  variable (R3c; SRS §10 names none).
- Do not log `str(exc)`, a response body, a header value, a cookie, a token, an
  identity string, or an endpoint URL. `_discover_all` logs the exception class
  name only.
- Do not make any new discovery log line contain the substring `"enrichment"`
  (case-insensitive); the LREQ-NFR-020 projection filter and its redaction nodes
  keep their scope.
- Do not add a second projection line or change `log_enrichment_projection`; the
  handler this chunk installs makes the existing one reachable (LREQ-NFR-020).
- Do not call `_configure_logging` from `run_command`/`dashboard_command`; it is
  `main()`'s responsibility so direct-call test seams stay silent.
- Do not re-open OI-6 or the URI trailing-identifier extraction; neither is
  resolved, absorbed, or claimed verified here.
- Do not rename or delete an existing pytest node ID or its
  `tests/traceability.json` entry.
- Do not edit `Documents/SRS-lean.md`,
  `Documents/requirements-dependency-map.md`, `AGENTS.md`, `kilo.json(c)`,
  `.kilo/`, or `pyproject.toml`.
- Do not claim the live Coveo failure is fixed or diagnosed; the logging is the
  diagnostic hook only.

## 12. Resolved decisions (lead rulings) and carried-forward obligations

The four rulings below were fixed by the lead before this plan and are adopted,
not recommended. They are not open questions.

1. **R1 — limitation content (adopted).** Covered by §2 "In scope", §7.1 E4. The
   format `category <repr>: <field>` and `interfaces/chunk-10.md` are unchanged.
2. **R2 — no fabricated status (adopted).** Covered by §7.1 E3. The adapter's
   actual `discovery_status.value` is written; an absent discovery result raises
   a redacted `PipelineError`.
3. **R3 — logging (adopted).** Covered by §7.1 E1/E2/E5/E6 and §7.2 E8. No new
   CLI flag, no new environment variable; discovery lines contain no
   `"enrichment"`.
4. **R4 — out of scope (adopted).** Covered by §2 "Explicitly out of scope". The
   live Coveo root cause, the collectors, `database.py`, `report.py`, schemas,
   and failed-run rendering are untouched.

**Carried-forward obligations (recorded, not resolved, and not owned by this
chunk):**

- **Discovery-page failure has no persisted cause.** `category_scores` has no
  issue/error column (`database.py` `CREATE TABLE category_scores`), a failed
  page writes no raw observation, and the in-memory `CategoryDiscoveryResult.issues`
  are still dropped by the pipeline after this chunk (only their codes are
  logged). A durable discovery-cause column is a schema change owned by no chunk.
  Owner: none.
- **OI-6 (CSRF/session sufficiency).** Unassigned (dependency-map §7). Chunk 15
  neither resolves nor absorbs it.
- **URI trailing-identifier extraction (identity mapping rule 1.0.1).**
  UNVERIFIED; no captured Coveo response exists in the repository. Chunk 15 makes
  no claim about it.
- **Live Coveo failure.** Not diagnosed or fixed (R4). The R3 logging is the
  diagnostic hook a later human or chunk uses.

**Freeze record.** This plan is **Status: FROZEN**. The four rulings are adopted
as written; the §9 pytest node IDs are frozen with the plan and SHALL NOT be
renamed by a later change. The carried-forward obligations are recorded, not
resolved. This chunk creates no interface file and edits no documented authority
file except this plan.

### Non-blocking assumptions recorded while freezing

- **A1 — `PipelineError` message shape.** R2 says the message "names only
  `category_scores` (never a value)". The existing raise at `pipeline.py:2865`
  (and the sibling at `:2945`) is `f"category {category!r}: category_scores"`,
  which names a category and the table and carries no value. The plan keeps that
  message byte-identical so the redaction and the established format are
  preserved; "names only `category_scores`" is read as "names the table, not the
  status value or any identity". A human who intended a bare `"category_scores"`
  message can say so without changing any other decision.
- **A2 — LREQ mapping for the two `_configure_logging` nodes.**
  `LREQ-NFR-020` is the SRS's only logging requirement, so the wiring nodes map
  to it. They assert handler wiring and `main()` invocation only; they do **not**
  assert NFR-020's four named quantities (those stay with the existing
  projection nodes). If a human prefers `LREQ-CLI-010` or `LREQ-CLI-040` for the
  wiring nodes, only the marker/matrix values change, not the test behavior.
- **A3 — inert `category_status_for` arguments in `_log_discovery_outcome`.**
  The function requires `warnings`/`evidence_grade`/`rankability_status`; the
  discovery-time call passes `warnings=()`,
  `evidence_grade=EvidenceGrade.INSUFFICIENT.value`,
  `rankability_status=RankabilityStatus.NOT_RANKABLE.value`. The documented rule
  derives nothing from them, so the disposition is well-defined; the values are
  placeholders matching the failure-path row, not a claim about discovery-time
  evidence.
- **A4 — `_configure_logging` default parameter.** R3 names
  `_configure_logging(stream=sys.stderr)`. The plan uses
  `stream: TextIO | None = None` and resolves `None` to the current `sys.stderr`
  at call time, so a test's captured buffer is honoured and no stale
  import-time buffer is retained. The default behavior is unchanged.
- **A5 — `tests/AGENTS.md` keying is stale.** Lines 5–13 describe
  `tests/traceability.json` as LREQ-ID → node arrays; the committed file and
  `validate_traceability.py` use node-ID → LREQ arrays, confirmed by chunk-13
  plan §2 R3. The committed artifact governs; the stale rule file is not edited
  by this chunk.
