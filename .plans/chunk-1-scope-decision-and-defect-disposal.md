# Chunk 1 scope decision and defect disposal

# Chunk 1 scope decision and defect disposal

## Goal

Dispose of the "Chunk 1 blocked — 13 test failures" claim from the frozen
documents rather than from the brief. Outcome: **do not touch `database.py`;
do not touch `validation.py` as a "defect"; the only source change the evidence
supports is one over-reaching test in `tests/test_validation.py`, and the real
remaining Chunk 1 work is `tests/test_identity.py` plus its 31
`tests/traceability.json` entries.**

Plan Status: informational decision document. No chunk plan is re-opened, no
`Documents/plans/*.md` file is edited.

---

## 1. Independent findings (read from disk, not from the dispatch report)

### 1.1 Authority for what Chunk 1 may touch

- `Documents/plans/chunk-01-...md` §6 "Files touched" authorizes exactly:
  `src/niche_scout/validation.py`, `tests/test_validation.py`,
  `tests/test_identity.py`, `tests/traceability.json`,
  `tests/fixtures/validation_fixtures.py`, conditional
  `tests/fixtures/__init__.py`, conditional `.gitignore`.
- Same file, "Explicitly NOT touched by this chunk" (line 623):
  **"`src/niche_scout/database.py` — Chunk 2 (physical SQLite implementation)."**
- Same file §11 "No frozen-interface edits" (line 822–825): SHALL NOT modify
  "any other chunk's files".
- `src/niche_scout/validation.py` **is** in §6, so a genuine defect in it would
  be in scope — the question is only whether the failures show one.

### 1.2 Does `database.py` contain the root cause of any Chunk 1 test?

No. `tests/test_validation.py` never imports or references `database`; its only
mention of the name is inside the string set at lines 952–975, which asserts the
module does **not** import it. Chunk 1's plan forbids the import in both
directions (plan §11, line 793; §4 line 276–278). Therefore **no Chunk 1 test
can have a root cause in `database.py`**, and chained option A's "fix both
files" half is unsupportable as stated.

`database.py` is Chunk 2's deliverable. `.plans/chunk-2-completion-q3-...md`
Step 1 already records a real, separate `database.py` defect (`computed_at_utc`
incorrectly listed in `_IMPLICIT_NOT_NULL_DEFAULTS["category_scores"]` at
`database.py:502`, with the documented consequence). If that work was not
applied, it is a **Chunk 2** escalation, not Chunk 1 defect work. Either way it
is out of this plan's scope.

### 1.3 Is `import json` in `validation.py` a contract violation? No.

- `src/niche_scout/tools/check_import_boundaries.py:17` —
  `PURE_MODULES = ("metrics.py", "scoring.py")`. `validation.py` is **not** in
  the governed set, so `python -m niche_scout.tools.check_import_boundaries`
  will not report anything for it.
- `Documents/interfaces/chunk-00.md` lines 31–36 — the `json` prohibition is
  scoped to **"`metrics.py` and `scoring.py` SHALL NOT import … `json` …"**.
  `validation.py` is not named in that sentence or in that section's module
  table (line 21–27).
- `json` is genuinely used in `validation.py` at lines 255, 1716, 1727, and
  `summarize_validation_issues` is *required* by plan §9 (line 706) and §5.2
  (line 560–562) to emit "a redacted JSON summary".
- `Documents/SRS-lean.md` §3.1 (line 192) gives `validation` the constraint
  "No network" — not "no stdlib".

**Conclusion:** the `json` import is correct and permitted. The failing
assertion is the test's, not the module's: `tests/test_validation.py:976` calls
`check_module(VALIDATION_PATH)` and asserts `== []`, but `check_module` ignores
`PURE_MODULES` (it checks whatever path it is handed) and `json` **is** in
`FORBIDDEN_MODULES` (line 48). The test therefore asserts a boundary that
neither the tool nor the frozen contract applies to `validation.py`. Verified at
the code level — do not accept or reject this without running the suite (§3.1).

### 1.4 Is the "csrf redaction leak" a real leak? No — it is a defective assertion.

`test_validation.py:855` asserts `"csrf" not in summary.lower()`, and the
summary is built at `validation.py:1711` as `{"code": issue.code, …}` where
`issue.code` comes from `test_validation.py:844`: `f"fixture_{name}"` iterating
`fx.REDACTION_VECTORS`, whose keys include `"csrf_token_value"` and
`"x_csrf_token"` (fixture lines 504, 513). So the summary legitimately contains
the *code* `fixture_csrf_token_value`, and the lowercase substring `"csrf"`
appears — with **no secret value anywhere in the output**.

- The plan's actual redaction requirement (§11 line 819–821, §5 line 581–583) is
  about credential **values**, `Authorization` headers, CSRF **tokens**, cookies,
  and raw response bodies. `fx.FORBIDDEN_REDACTION_SUBSTRINGS` (fixture lines
  517–523) correctly lists token **values** — which `redact_value` does remove.
- `"csrf"` is a substring of the *fixture key name*, not a token. The assertion
  is unsatisfiable by any implementation that also keeps stable machine-readable
  codes, and no plan line requires it.

**Conclusion:** no leak; the assertion is wrong. Note the paired risk: the same
test also asserts `"Authorization" not in summary` (line 851), `"Cookie"` (852),
`"Bearer"` (854), `"access_token"` (856), `"api_key"` (857) — those pass only
because the fixture keeps token values only in *context* (which is redacted) and
the codes use `<name>` spellings that avoid those substrings. The `"csrf"` case
is the only one where the code-name contains the asserted substring, which is why
it fails alone. Any fix must not weaken 851–854/856–857.

### 1.5 A genuine latent defect in the same test (fix while there)

`test_validation.py:843–846`:

```python
issues = tuple(
    v.ValidationIssue(code=f"fixture_{name}", message=value, context=context)
    for name, (value, context) in zip(fx.REDACTION_VECTORS, secret_contexts.items())
)
```

`zip` over a dict iterates its **keys**, so `(value, context)` unpacks the
strings `"authorization_header"`, `"bearer_token_value"`, … — not tuples. This
raises `ValueError: too many values to unpack` from inside the test itself.
`test_validation.py:860` (`vector not in summary`) is therefore also unreachable
as written. This is an unambiguous test bug with no source-side counterpart, and
it is inside plan §6's authorized file list.

### 1.6 The real remaining Chunk 1 work

- `tests/test_identity.py` **does not exist** (`tests/` holds only
  `test_contracts.py`, `test_validation.py`, `traceability.json`, fixtures).
  Plan §9 requires it with 24+ base node IDs across LREQ-EXT-060, EXT-070,
  GQL-010, GQL-060, GQL-070, ID-020, SMP-010, TST-030.
- `tests/traceability.json` has **23 entries, all `tests/test_contracts.py`**
  (verified, lines 2–23). Zero entries for `test_validation.py`'s 24 marked
  tests. This currently violates `tests/AGENTS.md` line 13 and
  `src/niche_scout/tools/validate_traceability.py`'s `missing_nodes` check —
  which is **chunk-agnostic** (computed across all of `tests/`), so
  `python -m niche_scout.tools.validate_traceability` is already failing on
  Chunk 1's marked-but-unmapped nodes, independently of the 13 test failures.

So "13 test failures" understates the position: there is also a hard
traceability failure and an entire missing test module.

---

## 2. Decision

**Option A, with the `database.py` half removed.** The chained answer is:

1. **Do not touch `database.py`.** §1.2. Not as defect work, not as a fix, not as
   an import. It is Chunk 2's file; Chunk 1 cannot have a root cause there.
2. **Do not change `validation.py` for `json` or for csrf.** §1.3, §1.4 — the
   module is correct in both cases.
3. **Do authorize one narrow test-defect fix in `tests/test_validation.py`**, a
   file plan §6 lists as Chunk 1-owned. This is the "use the frozen plan/SRS to
   decide who is wrong" half of option A, applied at the only layer where the
   evidence shows the wrong party is the test.
4. **Do not do this as free-hand repair.** Route Steps 1–3 below through the
   **chunk-implementer** with an explicit scope note, because
   `.cursor/rules/project-rules.md` File discipline forbids touching files
   outside the active plan, and `chunk-implementer.md` lines 24–26 require it to
   stop and report rather than improvise. The note must state that
   `tests/test_validation.py` is authorized by plan §6 and that the fix is a
   *correction of an assertion that contradicts plan §11's own prohibition list*.
   If the reviewer/verifier later classifies the test relaxation as an
   unplanned scope change, that is a human checkpoint — stop, do not reroute.
5. **Then finish the chunk**: `tests/test_identity.py` + the traceability entries.

If you prefer to keep frozen documents absolutely untouched even in the test
layer, the alternative is: leave the two assertions failing, record them as an
**open defect against Chunk 1's §9 test plan**, and hand the plan back for a
`plan-reviewer` amendment — but note that `Documents/plans/chunk-01-...md` is
already `Status: FROZEN` with §12 stating "Section 12 contains no unresolved
human decisions", so that path requires you to re-open a frozen plan. Rejected
as the default because the defect is provably on the test side.

---

## 3. Implementation steps

### Step 0 — Confirm the baseline before editing (no writes)

Run and record real output. **This plan could not run them (Plan mode has no
terminal tool), so every failure attribution in §1 above is a code-level
prediction, not observed output.** If any traceback's deepest frame lands in
`src/niche_scout/validation.py` or `src/niche_scout/database.py`, stop and
re-run this whole analysis with that traceback.

```powershell
python -m pytest tests -q -rf --tb=short
python -m pytest tests -q --collect-only
python -m niche_scout.tools.check_import_boundaries
python -m niche_scout.tools.validate_traceability
python -m pytest tests/test_validation.py -q --tb=long
```

Confirm each of:
- the failure count is 13 and the node IDs are confined to
  `test_validation.py`;
- `validate_traceability` fails on `test_validation.py` markers with no matrix
  entry (`missing_nodes`), quoting its message;
- `check_import_boundaries` reports `Import boundaries valid for metrics.py,
  scoring.py` (i.e. says nothing about `validation.py`).

### Step 1 — Fix the test bug in `tests/test_validation.py`

File: `tests/test_validation.py`. Two anchored edits, nothing else.

**1a — the `zip` unpacking bug** (lines 840–846). Replace the
`secret_contexts`/`zip` construction with a direct iteration over the mapping's
items so `(value, context)` is a real pair:

```python
issues = tuple(
    v.ValidationIssue(code=f"fixture_{name}", message=value, context={"field": value})
    for name, value in fx.REDACTION_VECTORS.items()
)
```

Rationale: keeps the intent (every fixture secret goes into both `message` and a
context value) while removing the key-vs-item confusion that makes the test
error. Preserve the existing `zip`-free behaviour of `secret_contexts` if it is
used elsewhere in the function — check first; if unused after this change,
delete it.

**1b — the over-reaching `"csrf"` assertion** (line 855). Change

```python
assert "csrf" not in summary.lower()
```

to assert the plan's actual requirement — CSRF **token values**, not the
substring:

```python
assert fx.REDACTION_VECTORS["csrf_token_value"] not in summary
assert fx.REDACTION_VECTORS["x_csrf_token"] not in summary
```

Leave lines 849–854, 856–857 untouched. Add a one-line comment stating that
`"csrf"` is a fixture *code-name* substring, not a secret, and citing plan §11
lines 819–821 (values, headers, tokens, cookies — not identifier names). Do not
weaken the `Authorization`/`Cookie`/`Bearer` assertions.

### Step 2 — Fix the over-reaching purity assertion (do **not** touch `validation.py`)

File: `tests/test_validation.py`, line 976. `assert check_module(VALIDATION_PATH)
== []` asserts that `validation.py` satisfies `metrics.py`/`scoring.py`'s purity
set. Replace it with an assertion of the boundary that actually governs
`validation.py`:

```python
assert check_module(VALIDATION_PATH) == [], (
    "validation.py is governed by plan §11: no I/O modules, no clock. "
    "json is forbidden only for metrics.py/scoring.py (check_import_boundaries "
    "PURE_MODULES), so it must not appear here."
)
```

and keep the assertion meaningful by changing the checked set rather than
deleting it: either (a) assert the intersection of
`imported` with `FORBIDDEN_MODULES - {"json"}` is empty, or (b) call
`check_module` only after documenting that `json` is out of scope. Prefer (a) —
it keeps a real boundary assertion (no `sqlite3`, `os`, `pathlib`, `time`,
`requests`, …) while dropping the one member the frozen contract does not apply
to `validation.py`. Import `FORBIDDEN_MODULES` alongside the existing
`check_module, clock_violations` import at line 32.

Do **not** remove the `clock_violations(tree) == []` assertion — that boundary
does apply (§11 line 796–799).

### Step 3 — Re-run and confirm both files are green

```powershell
python -m pytest tests/test_validation.py -q
python -m pytest tests -q
```

`tests/test_validation.py` must be 24/24. `tests` will still fail on
`validate_traceability`'s marker direction until Step 4 lands — that is expected
and is not a regression.

### Step 4 — Complete Chunk 1's actual remaining deliverable

Per plan §9's node-ID tables, author the missing pieces (chunk-implementer
scope, plan §6 authorized):

1. `tests/test_identity.py` (new) — every base node ID in plan §9's two tables
   for `LREQ-EXT-060`, `LREQ-EXT-070`, `LREQ-GQL-060`, `LREQ-GQL-070`,
   `LREQ-TST-030`, plus `LREQ-GQL-010`, `LREQ-ID-020`, `LREQ-SMP-010`. Each test
   carries exactly one `@pytest.mark.lreq(...)` marker matching its row.
2. Extend `tests/fixtures/validation_fixtures.py` only if an identity vector in
   plan §9's golden-vector table is missing; reuse `IDENTITY_RECORDS`,
   `STATE_VECTORS` and the redaction vectors already present.
3. `tests/traceability.json` — add **one entry per new base node ID**, value
   equal to that test's marker set exactly, for `test_identity.py` **and** the 24
   existing `test_validation.py` nodes. Do not reword, reorder, or delete the 23
   existing `test_contracts.py` entries. Expected final count: 23 + 24 + ~25.

### Step 5 — Chunk 1 §10 manual cross-check and gates

Because `validate_traceability.py`'s required-set completeness is still
Chunk-0-scoped (Chunk 1 plan §12 R-3, line 864–873), the gate needs a manual
cross-check: walk plan §3's LREQ table against the actual `@pytest.mark.lreq`
markers in both `tests/test_validation.py` and `tests/test_identity.py`, in both
directions, and report it as a literal checklist. Then run:

```powershell
python -m pytest tests -q
python -m niche_scout.tools.check_import_boundaries
python -m niche_scout.tools.validate_traceability
```

All must exit 0. Only then dispatch the gate-verifier. Per
`.cursor/rules/project-rules.md`, if the gate-verifier reports any §10 bullet as
FAIL, stop and relay it rather than rerouting.

---

## 4. Risks and explicit non-actions

- **Risk: relaxing a test to make it pass.** Mitigated by changing the checked
  *boundary* rather than deleting the assertion (Step 2 option (a)) and by
  scoping the change to assertions that provably contradict plan §11. If you
  disagree with that characterization, treat Steps 1–2 as needing your explicit
  sign-off before the implementer runs — they are the only steps that alter a
  frozen chunk's verification surface.
- **Risk: `database.py` defect hidden by this decision.** §1.2 and the Chunk 2
  completion plan show a real `databases.py`-side defect exists independently.
  It must be routed to **Chunk 2**, and this plan deliberately does not fix it.
  Creating a `Documents/plans/chunk-02-...md`-adjacent fix task is a separate
  human decision.
- **Risk: the 13-failure count is right but my attribution is wrong.** Step 0
  exists solely to falsify that. Do not proceed past Step 0 if a traceback lands
  inside `src/niche_scout/validation.py`.
- **Non-actions, stated so they are not "helpfully" taken:** no edit to
  `src/niche_scout/validation.py`; no edit to `src/niche_scout/database.py`; no
  edit to `src/niche_scout/models.py`; no widening of
  `src/niche_scout/tools/validate_traceability.py` (plan §12 R-3 → Chunk 13); no
  change to `Documents/plans/*` Status lines; no new requirement text.
