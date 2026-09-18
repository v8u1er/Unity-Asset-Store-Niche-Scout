# Ruling — Chunk 5: absent / null / unusable `state` on a GraphQL `ProductDetail`

Status: BINDING (requirement adjudication, not an implementation authorization)
Scope: `src/niche_scout/collector_graphql.py`, `tests/test_collector.py`,
`tests/fixtures/graphql_fixtures.py`, and this plan's §5.8 / §8 E7 / §8 E10 text.
No file other than this one was created.

Everything below is either **quoted** (source opened and read, with line number) or
**counted** (query stated verbatim, with result). Anything else is labeled
**unverified**.

---

## 1. The question

`tests/test_collector.py:2236` (`test_state_excluded_and_unknown_assets_remain_recorded`,
`LREQ-GQL-060`) deletes the `state` member from a `ProductDetail` payload
(`tests/test_collector.py:2216-2218`) and asserts `assert unknown.product_detail.is_success`
(line 2236). The adapter instead returns `WRONG_DATA_SHAPE`. Both readings were
argued to be defensible from `SRS-lean.md:329-330` and `SRS-lean.md:318-323`. This
ruling decides which governs, separately for three cases.

---

## 2. The normative text, quoted

Queried: `Documents/SRS-lean.md`, read directly.

**`SRS-lean.md:318-323` (LREQ-GQL-040, in full):**

> `**LREQ-GQL-040**: Each operation SHALL have an independent status. HTTP failures,`
> `top-level GraphQL `errors`, HTTP 200 responses with an operation-level `errors``
> `member, null required data, wrong data shape, wrong scalar type, boolean/negative/`
> `non-finite page views, invalid state values, or missing identity SHALL be recorded`
> `as an operation error. A top-level error SHALL not be treated as a successful`
> `operation merely because another operation in the same response succeeded.`

**`SRS-lean.md:329-330` (LREQ-GQL-060, in full):**

> `**LREQ-GQL-060**: Only `state = "published"` assets are eligible for D, R, and Q.`
> `State-excluded and state-unknown assets remain part of discovered breadth.`

**`SRS-lean.md:294-298` (LREQ-GQL-020, the operation's declared field set):**

> `**LREQ-GQL-020**: The `ProductDetail` operation SHALL request product identity`
> `aliases, `rating.average`, `rating.count`, `reviewCount`, `firstPublishedDate`,`
> `state`, `category`, and `publisher`. The separate `ProductPageViews` operation`
> `SHALL request its page-view scalar. Fields not required by scoring MAY be omitted`
> `from the lean implementation.`

**`SRS-lean.md:325-327` (LREQ-GQL-050):**

> `**LREQ-GQL-050**: A valid operation's fields MAY be retained when the other operation`
> `fails. Failed fields SHALL remain null or unavailable; they SHALL NOT be filled with`
> `zero or another default.`

**`SRS-lean.md:76-77` (§1.2 Normative language, the project-wide distinctness rule):**

> `- Missing, invalid, contradictory, or unavailable values SHALL remain unavailable;`
> `  they SHALL NOT be silently converted to zero.`

**`SRS-lean.md:33-35` (the endpoint-contract silence bridge — decisive):**

> `Where this document is silent about an external endpoint contract, the corresponding`
> `contract in the parent SRS remains applicable. Where this document is explicit, this`
> `document takes precedence for the lean implementation.`

**`SRS-lean.md:134` and `SRS-lean.md:123-126` (source references):**

> `### 1.5 Source references`
> `- **[PARENT]** — `SRS-revision2.md`, the full-MVP SRS and source for unchanged`
> `  endpoint details.`

**`SRS-lean.md:570-583` (§6.4, the persisted `enrichment_observations` contract):**

> `- `state`, product_page_views,`
> `id_mapping_mismatch,`
> … paragraph: ``product_page_views` SHALL be nullable and SHALL never use zero as an error sentinel.`

**`SRS-lean.md:655-657` (LREQ-MET-010, Chunk 7A's requirement):**

> `**LREQ-MET-010**: A product-level value is usable only when its type, range, state,`
> `identity, and timestamp conditions for the relevant metric pass. Null, malformed,`
> `future, naive, negative, non-finite, or state-excluded values SHALL be unavailable.`

**`SRS-lean.md:570-583` note on `state`'s nullability:** the `state` field is listed
among the required *fields* of the row; only `product_page_views` gets an explicit
"SHALL be nullable and SHALL never use zero as an error sentinel" clause. The
`state` member therefore has **no** explicit nullability sentence of its own. That
silence is bridged by `SRS-lean.md:33-35` to the parent, below.

### 2.1 The parent SRS — an operative definition of the same three cases

`Documents/retired-documents/SRS-revision2.md` is **[PARENT]** per `SRS-lean.md:125`.
Opened and read directly; query
`rg -n "state" Documents/retired-documents/SRS-revision2.md` (row-quoted results
include line 293, quoted here in full):

> `- **REQ-GQL-120 (DD-4, revised in v2.1.0)**: State eligibility SHALL be explicit: `product.state == "published"` is eligible for D/R/Q; a null or missing state is `state_unknown` and is excluded from D/R/Q; any present value other than `"published"` is `state_excluded` and is excluded from D/R/Q. The asset SHALL remain in `raw_product_details` for audit purposes. State filtering does not remove an asset from discovery breadth or C, because C is a discovery-only metric (REQ-MET-040).`

This is the single most decisive passage in the ruling. It:

1. names **exactly the three cases** (null **or missing** / other present string),
2. assigns **both** `null` and `missing` the same classification, `state_unknown`,
3. from which it follows that neither is a *malformed* payload — the requirement
   presupposes that the operation succeeded and produced an observation to
   classify and retain.

`SRS-lean.md:33-35` makes this applicable: the lean SRS is silent about what a
missing `state` member means for the endpoint contract, so the parent's contract
"remains applicable", and the lean SRS has not taken precedence on this point
(it is explicit about `state` only at `:329-330`, which names `state-unknown` as a
**retained** class and never as an error).

---

## 3. The dependency map, quoted

**`Documents/requirements-dependency-map.md:173` (LREQ-GQL-060 row of the same
table whose line 65 the plan cites as "Matrix row, line 65"):**

> `| LREQ-GQL-060 | `validation.py`, `collector.py` | LREQ-GQL-020, LREQ-GQL-040 | Pure validation over I/O result | Eligibility unit/fixture test | Only `published` assets eligible for D, R, and Q; state-excluded and state-unknown assets remain in discovered breadth and persisted observations |`

**`requirements-dependency-map.md:652` (Chunk 5's "Implement" list):**

> `- state eligibility annotation; excluded and unknown-state assets remain in persisted observations and discovered breadth`

**`requirements-dependency-map.md:171` (LREQ-GQL-040 row):**

> `| LREQ-GQL-040 | `collector.py`, `validation.py` | LREQ-GQL-030 | Network I/O | Response-status fixture test | HTTP failures, GraphQL errors, null data, wrong types, missing or ambiguous operation association |`

Two things follow. First, the map's LREQ-GQL-040 edge-case column is a closed list
of seven items, and "a missing field" / "absent member" is **not** one of them.
Second, the "missing" in that column belongs to "missing or ambiguous operation
association", which is LREQ-GQL-030's subject (unmatched **operations**), not a
missing **member**.

Additional map text bearing on case (b): `requirements-dependency-map.md:657`
quotes LREQ-MET-010's list including "state-excluded values" as the metric-level
unavailability class, and `:173` assigns the metric half to Chunk 7A
(`:65`: primary owner Chunk 7A). No map passage classifies an absent `state`
member as an operation error.

**Conflict noted, deliberately not resolved here:** `requirements-dependency-map.md:478`
(Chunk 1's row) says of Chunk 1: "This chunk owns structural validity only; metric
eligibility rules such as published-state, UTC/date, future-date, finite/non-negative,
age, and page-view eligibility are owned by Chunk 7A." That sentence is about
**metric eligibility**, not about required-member structure, and this ruling does
not rest on it. See §7, item 3.

---

## 4. The plan, quoted — what it actually decided

`Documents/plans/chunk-05-graphql-protocol-adapter-and-response-correlation.md`,
`Status: FROZEN` (line 3).

**Plan §5.8, line 913-922:**

> `State annotation is the Chunk 1 call `annotate_state_eligibility(state_value)`; the`
> `adapter stores the returned `StateEligibilityAnnotation` unchanged, keeps the raw`
> `state` string in `ProductDetailFields.state` (verbatim, including a `None` for a`
> `missing state), and adds `WarningCode.STATE_EXCLUDED` to the operation's issue`
> `context when `state_excluded` is true. `state_unknown` and `state_excluded` are`
> `recorded as such, and `remains_in_discovered_breadth` is always `True`, so this`
> `chunk satisfies the dependency map's "state-excluded and state-unknown assets remain`
> `in persisted observations and discovered breadth" (line 652) by construction.`

This is the plan's **only** positive statement about a missing `state`: it
contemplates "a `None` for a missing state" reaching `ProductDetailFields.state`.
That is reachable only if the operation **succeeds** with `state` absent.

**Plan §8 E7, lines 1309-1313 — this is the internal contradiction:**

> `- **E7 — Wrong data shape and invalid state (LREQ-GQL-040).** `product` present but`
> `  not an object, a required member missing, and `state` present but not a string are`
> `  each an operation error for `ProductDetail`; a present non-`"published"` state is`
> `  **not** an operation error — it is `state_excluded`, annotated, and retains the`
> `  asset in discovered breadth (LREQ-GQL-060 annotation half).`

E7 makes "a required member missing" an operation error; `state` is in
`PRODUCT_DETAIL_REQUIRED_MEMBERS` (`collector_graphql.py:876-885`), so E7 makes an
absent `state` an error.

**Proposed resolution of that contradiction for planning purposes (flagged as a
question for the human, not decided here):** E7's phrase "a required member
missing" is scoped by its own parenthetical to the identity members, which is how
the adapter's implementation comment reads it (`collector_graphql.py:1149-1151`,
quoted in §5). Under that reading of E7, §5.8 and E7 agree and no plan edit is
needed; under the literal reading, they conflict and one of the two must be
edited. This ruling does not pick between them; see §8.

**Plan §8 E10, lines 1326-1330:**

> `- **E10 — State eligibility annotation (LREQ-GQL-060).** Only `published` is annotated`
> `  published; a present non-`published` value is `state_excluded`; a missing, null, or`
> `  wrong-typed value is `state_unknown`. In both non-published cases the asset remains`
> `  in persisted observations and discovered breadth`
> `  (`remains_in_discovered_breadth is True`), and no D/R/Q verdict is produced.`

E10 collapses all three cases into `state_unknown`. It is **consistent with E7**
only on the proposition that no *state* reading makes the operation fail; to be
consistent with a literal E7 it would have to carve out wrong-typed from
"third and fourth cases" and make it a failure, which it does not do.

**Plan §9 rows, lines 1481-1483 — the two test nodes this ruling is about:**

> `| tests/test_collector.py | `test_state_annotation_covers_published_excluded_and_unknown` | LREQ-GQL-060 |`
> `| tests/test_collector.py | `test_state_excluded_and_unknown_assets_remain_recorded` | LREQ-GQL-060 |`
> `| tests/test_collector.py | `test_adapter_declares_no_metric_eligibility_verdict` | LREQ-GQL-060 |`

---

## 5. What the artifacts actually do now (opened and read)

**`src/niche_scout/collector_graphql.py:876-885` — `state` is declared required:**

> `PRODUCT_DETAIL_REQUIRED_MEMBERS: tuple[str, ...] = (`
> `    "id", "productId", "rating", "reviewCount", "firstPublishedDate", "state", "category", "publisher",`
> `)`

**`collector_graphql.py:1050-1055` — the structural call:**

`validate_response_shape(payload, expected_shape="mapping", required_members=PRODUCT_DETAIL_REQUIRED_MEMBERS, field_types=PRODUCT_DETAIL_NUMERIC_MEMBER_TYPES)`

**`src/niche_scout/validation.py:1760-1768` — the check that fires for an absent member:**

> `    for member in required_members:`
> `        if member not in payload:`
> `            issues.append(`
> `                ValidationIssue(`
> `                    code="response_missing_required_member",`

A member absent from the mapping takes exactly this branch: it is in
`required_members` and `not in payload`.

**`collector_graphql.py:1137-1158` — where state is annotated, and the intended carve-out:**

> `    state_value = payload.get("state")`
> `    state_annotation = annotate_state_eligibility(state_value)`
> `    if state_annotation.state_excluded:`
> `        ... "state_excluded" ...`
> `    elif state_annotation.state_unknown and state_value is not None:`
> `        # A present but unusable state value is an invalid state value`
> `        # (LREQ-GQL-040's "invalid state values" clause). A missing or null state`
> `        # is state-unknown only (LREQ-GQL-060's annotation half).`
> `        issues.append(_issue("invalid_state_value", ...))`

**`collector_graphql.py:1196-1209` — the classification order:**

> `    codes = {issue.code for issue in issues}`
> `    if missing_identity or "response_missing_identity" in codes: return MISSING_IDENTITY`
> `    if "invalid_state_value" in codes: return INVALID_STATE_VALUE`
> `    if "response_wrong_container_kind" in codes: return WRONG_DATA_SHAPE`
> `    if "response_missing_required_member" in codes: return WRONG_DATA_SHAPE`
> `    if "response_null_required_member" in codes: return NULL_REQUIRED_DATA`
> `    if "response_wrong_scalar_type" in codes: return WRONG_SCALAR_TYPE`
> `    return NONE`

**Ordering, stated precisely (the dispatch's question 5):** `MISSING_IDENTITY` fires
first, `INVALID_STATE_VALUE` second, `WRONG_DATA_SHAPE` third. For an **absent**
`state` member none of the first three conditions is true: the identity path is
unaffected, and `invalid_state_value` is never appended because the guard at line
1148 requires `state_value is not None` and `payload.get("state")` yields `None`.
So the **fourth** check fires, and the operation is `WRONG_DATA_SHAPE`.

**The internal contradiction inside the adapter, quoted:** the code comment at
lines 1149-1151 states the intent that "A missing or null state is state-unknown
only (LREQ-GQL-060's annotation half)". That intent is **_dead code_**. For a
missing member the operation is destroyed earlier, at lines 1197-1204, and
`product_detail` is set to `None` at line 1186. The annotation is computed at line
1138 but the object carrying it is discarded. The `elif` at 1148 can therefore only
ever fire for a **present, non-`None`, non-string** value (e.g. `17`), or the empty
string. A `state` present as JSON `null` is caught even earlier, by the
`response_null_required_member` branch at `validation.py:1769-1779`, and classified
`NULL_REQUIRED_DATA`.

Summarized as behavior:

| Case | Current adapter outcome | `ProductDetailFields` |
|---|---|---|
| (a) member absent | operation **ERROR** `WRONG_DATA_SHAPE` | `None` (line 1186) |
| (b) present `null` | operation **ERROR** `NULL_REQUIRED_DATA` | `None` |
| (c) present, unusable (int, empty string) | operation **ERROR** `INVALID_STATE_VALUE` | `None` |

**One implementation trap, called out because it constrains the fix.**
`collector_graphql.py:1186` sets `product_detail=fields if valid else None`, and
`collector_graphql.py:1739-1743` (`_product_detail_fields_from_payload`) returns
`None` for any payload that fails re-validation. The retry loop re-validates the
retained payload (line 2020 retains the raw payload including a now-absent
`state`; line 2357 builds the draft). Therefore **any code-path change that only
relaxes the missing-member classification without also removing `state` from the
required-member list will be reverted on the retry pass, and the draft will carry
`state = None`, `graphql_id = None`, and `id_mapping_mismatch = True`** — i.e. the
test would still fail, and would fail in a way that falsely reads as an identity
mismatch. This is **verified by reading**, not by execution: no test was run.

**Fixtures, `tests/fixtures/graphql_fixtures.py` (opened):**

- `product_detail_payload` (lines 296-321) builds every member in
  `PRODUCT_DETAIL_REQUIRED_MEMBERS`, with `state: object = "published"` (line 302)
  and returns `{"id", "productId", "rating", "reviewCount", "firstPublishedDate",
  "state", "category", "publisher"}`.
- `state_excluded_body` (742-753): "a body whose `state` is present but not
  `published`", via `product_detail_payload(state="deprecated")`.
- `invalid_state_body` (756-767): "a body whose `state` value is present but not a
  usable string", via `product_detail_payload(state=17)` — case (c).
- `missing_identity_member_body` (770-780) deletes `id`; its docstring at 784-789
  states the mechanism explicitly: "Both aliases are present as required members
  but carry JSON `null` … an absent alias fails the required-member check first."
- `missing_identity_body` (783-799) sets `id = None; productId = None`.

**Counted, per the project's anchored-enumeration rule.** Query:
`rg -n "response_missing_required_member|response_null_required_member|response_wrong_scalar_type|response_missing_identity" src/niche_scout/collector_graphql.py`
Rows returned: 37 for the union of member-related symbols; the four
`error_classes` keys are at `collector_graphql.py:1058-1063` (4 matches, all 1-based
line numbers, one per line, no line carrying two). Unit: **occurrences**, not
distinct identifiers. The `PRODUCT_DETAIL_REQUIRED_MEMBERS` tuple literal spans
**8 member names**, of which **2** are identity aliases (`"id"`, `"productId"`).
Counted by reading lines 876-885; the 8 names are listed verbatim in the quote
above and 2 + 6 = 8 reconciles.

---

## 6. The architecture rule, applied to each case

`AGENTS.md` and `.cursor/rules/project-rules.md` both carry: "Null, zero, invalid,
and unavailable are distinct states. Missing, invalid, contradictory, or
unavailable values SHALL remain unavailable; never fabricate zeros." The SRS
equivalent is `SRS-lean.md:76-77`, quoted in §2 — the **SRS-level** rule, which is
the binding one.

Applied:

- **(a) absent** is the rule's **"missing"** state. The rule's command for it is
  "SHALL remain unavailable" — a *retention* command. The rule never says a
  missing value invalidates its container; it says the value stays unavailable. The
  forbidden outcome is fabrication (`"published"`, `""`, `0`), not continued
  existence of the operation.
- **(b) `null`** is both the rule's "missing" and its "null". Same command:
  remains unavailable. Again no container-invalidating command.
- **(c) present but unusable** is the rule's **"invalid"** state, and here a second
  requirement applies independently: `SRS-lean.md:318-323` names "invalid state
  values" *and* "wrong data shape" as operation errors. The rule and LREQ-GQL-040
  agree. An untouched LREQ-GQL-040 item — a present, typed member whose value is
  outside the domain — must not be nulled out by this ruling.

The rule therefore **forbids a fabricated `state`** and **permits, but does not by
itself compel, retention**. What compels retention is `SRS-lean.md:33-35` bridged
to the parent's REQ-GQL-120, plus the map's `:652` ("excluded and unknown-state
assets remain in persisted observations") and the plan's own §5.8/E10.

**Where the map's "remain in persisted observations" becomes decisive:** under the
adapter's current behavior, for case (a) there is **no observation row at all** —
`product_detail=fields if valid else None` (line 1186) discards every field,
including `graphql_id`, `rating_average`, and `first_published_date_utc`, which are
the fields LREQ-MET-010's eligibility and LREQ-MET-060's recent-supply estimator
consume. The map's own LREQ-MET-040 row (`requirements-dependency-map.md:214`)
states the intended shape: "ProductDetail may remain usable when PageViews is
unavailable". Classifying a *valid* ProductDetail invalid because one member is
absent makes the reverse true, on a payload that is otherwise complete.

**No silent fabrication:** the retained value must be a first-class unavailable
sentinel, not a string. Note the collision that makes this concrete — the existing
`StateEligibilityAnnotation.state_unknown: bool` (`validation.py:409`,
`Documents/interfaces/chunk-01.md:138`) and the *payload-ish* name
`state_enrichment` are not the same thing: **(checked)** `rg -n "state_enrichment"`
over `src/niche_scout/collector_graphql.py` returns **1 row, at line 1144**, and it
is prose inside a message string ("state-excluded and remains in discovered
breadth") — there is **no** symbol, field, function, or module named
`state_enrichment` in the adapter. Nothing named `state_enrichment` is affected by
this ruling. Unit: occurrences against real code, excluding prose; the single match
is prose and is therefore excluded, giving **0 real-code matches**.

---

## 7. The ruling

### Case (a) — the `state` member is **absent** entirely

**Operation succeeds. The asset is state-unknown and is retained.**

- `product_detail.status = SUCCESS`; no failure class.
- `state` value: **`None`** (`ProductDetailFields.state = None`).
- Unavailable sentinel: `StateEligibilityAnnotation(state_value=None,
  is_published=False, state_excluded=False, state_unknown=True,
  remains_in_discovered_breadth=True)`.
  **A usable sentinel already exists; no new type is needed.**
- **Must be recorded in `ProductDetailFields`/`EnrichmentObservationDraft` as a
  distinct field** — see the condition in §7.4.
- No `STATE_EXCLUDED` warning; no `invalid_state_value` issue; no D/R/Q verdict
  (`LREQ-MET-010`, Chunk 7A).

### Case (b) — `state` is present but `null`

**Operation succeeds. Same treatment as (a), with one audit difference the
implementer must be told explicitly, because the two cases are NOT currently
distinguishable once both are relaxed.**

- `state = None`; `state_annotation.state_unknown = True`; retained.
- **Conditional, and it must not be skipped:** the observation must record that the
  member was *present and null* rather than *absent*, or "missing, invalid, and
  contradictory remain distinct" is violated by the fix itself. The issue/annotation
  carries this: issue code `response_null_required_member` with `context.member ==
  "state"` for (b), and no such issue for (a). Preserving that issue on a
  **successful** operation is a permitted use of `issues` — the field is already a
  general issue channel (`collector_graphql.py` appends `state_excluded` and
  `graphql_id_mapping_mismatch` to successful results at lines 1139-1147 and
  2011-2018).

### Case (c) — `state` is present with the wrong type or an unrecognized value

**Split. This is the case the earlier analysis collapsed, and the split is the
ruling's most important consequence.**

- **(c1) present, wrong JSON _type_ (an integer, a boolean, an object, a list, or
  the empty string — anything `annotate_state_eligibility` classifies as
  `state_unknown` while the value is not `None`): ERROR,
  `failure_class = INVALID_STATE_VALUE`.** Unchanged from current behavior.
  `SRS-lean.md:321` names "invalid state values" as an operation error, and the
  adapter's `elif` at line 1148 is the correct implementation of it. `invalid_state_body`
  (type `17`) stays an error; `test_invalid_state_value_and_missing_identity_are_operation_errors`
  (lines 1956-1966) **must keep passing**.
- **(c2) present, a usable string outside the known set (`"deprecated"`,
  `"disabled"`, anything else): SUCCESS, `state_excluded`.** Unchanged from current
  behavior; this is `SRS-lean.md:330`'s "state-excluded", not an error. Note this
  is not really "unrecognized value" in the current design:
  `annotate_state_eligibility` (`validation.py:1645-1661`) **compares only against
  `"published"`** — any other usable non-empty string is `state_excluded`
  (quoted: "Any other usable non-empty string yields `state_excluded = True`",
  `validation.py:1635`). There is no enumerated known-set test in the primitive, so
  the phrase "an unrecognized value" in the dispatch has **no implementation** and
  no error path; do not invent one.

### 7.4 Condition attached to the ruling for (a) and (b)

Relaxing the two classifications is **necessary but not sufficient**. The required
change is three-part, and the third part is the one most likely to be missed:

1. `state` **must leave `PRODUCT_DETAIL_REQUIRED_MEMBERS`**
   (`collector_graphql.py:876-885`), so `validate_response_shape` stops emitting
   `response_missing_required_member` and stops setting
   `StructuralValidationResult.is_valid = False`.
2. `state`, when present but `null`, must not be emitted as
   `response_null_required_member` **for the `state` member only**. The other seven
   members keep this behavior in full. Two ways exist (a `state`-specific
   pre-check, or a superset of `required_members` distinct from the "usable
   members" set); **this ruling fixes the behavior, not the mechanism** — the
   implementer owns the choice.
3. `EnrichmentObservationDraft` / the persistence contract **must gain a
   `state_unknown`-bearing field** (or equivalent), and a test must assert it. **This
   is where my reading collides with a frozen interface.** `EnrichmentObservationRecord`
   (`src/niche_scout/models.py:418-447`) has `state: str | None` (line 438) and
   **no** `state_annotation`/`state_unknown` field, and its column list mirrors
   `SRS-lean.md:575-580` exactly, which lists `state` but no annotation column; the
   plan's mapping table states the same (`plan:1009`, `plan:1043`:
   "`state` | the corresponding `ProductDetailFields` member, else `None`"). So
   under (a) and (b) the pre-record row for `state` is `NULL` — **identical to the
   row produced for a failed operation** — and the persisted row cannot by itself
   distinguish "state unknown/absent" from "ProductDetail failed". That distinction
   currently lives only in `StateEligibilityAnnotation` inside the discarded
   `ProductDetailFields`. **How (or whether) to persist it touches a frozen
   contract and a frozen interface file and must not be decided inside Chunk 5.**
   See §8.

---

## 8. Which side is wrong

**Case (a), specifically: the implementation is wrong, and it is wrong on its own
stated intent — but the test's assertion cannot be green either until the
persistence question in §7.4 item 3 is answered.**

- The **adapter** is the primary defect for classification. `collector_graphql.py:876-885`
  list `state` as a required member, contradicting the adapter's own comment at
  lines 1149-1151 ("A missing or null state is state-unknown only"), plan §5.8 lines
  913-922 ("verbatim, including a `None` for a missing state"), plan §8 E10 lines
  1326-1330, map line 173, and map line 652.
- **Files that must change to satisfy case (a):**
  `src/niche_scout/collector_graphql.py:876-885` (remove `state` from the required
  tuple), `src/niche_scout/collector_graphql.py:1148` (the guard that currently
  suppresses the annotation path is now correct; the `invalid_state_value` append
  must remain for non-`None` unusable values), and
  `src/niche_scout/collector_graphql.py:1739-1743` (the re-validation path that
  discards the draft's `state` on the retry pass — see the trap in §5).
  **The specific line that must change is `collector_graphql.py:876-885`; without
  it, no other change takes effect.**
- The **test** is wrong at `tests/test_collector.py:2216-2218`:
  `payload = gqlfx.product_detail_payload(); del payload["state"]` combined with
  the in-line comment at 2216 ("A missing `state` member is state-unknown, not an
  exclusion string") is precisely what plan §8 E10 and the plan's own §8 fixture
  list describe: a **case (a)** payload. That fixture belongs in
  `tests/fixtures/graphql_fixtures.py` alongside `state_excluded_body` and
  `invalid_state_body` as, e.g., `missing_state_body()`, not inline in a test body;
  the file's own convention (lines 742-799) is one named factory per payload shape.
- **The plan file itself contains a contradiction** between §8 E7 (line 1309-1311,
  "a required member missing … [is] an operation error") and §5.8 (line 915,
  "including a `None` for a missing state") plus §8 E10 (line 1327). The plan is
  `Status: FROZEN` (line 3). **I do not edit it.** One of those two passages needs
  an edit and only a human may choose which; see §10.

**Case (b): the adapter is wrong.** `NULL_REQUIRED_DATA` for a `null` `state`.
`SRS-lean.md:33-35` + parent REQ-GQL-120 ("a null or missing state is
`state_unknown`") govern. Same three-part fix as (a).

**Case (c1): the adapter is right and the test is right.** No change. `SRS-lean.md:321`
("invalid state values") is untouched by this ruling.

**Case (c2): the adapter is right.** No change.

**`page_views`: unaffected.** No part of this ruling touches
`validate_page_view_scalar` (`collector_graphql.py:1212`), the `ProductPageViews`
correlation, or the `product_page_views` column. `SRS-lean.md:320`'s
"wrong scalar type" and the "boolean/negative/non-finite page views" clause keep
their current force, and `SRS-lean.md:583` ("`product_page_views` SHALL be nullable
and SHALL never use zero as an error sentinel") remains the governing sentence for
that field. Note only the *consistency* consequence: if `state` stops being a
required member on the "the requirement names it, therefore absent = malformed"
argument, that argument is equally unavailable for page views — and it already was,
since `LREQ-GQL-020` makes the scalar a separate operation whose absence is
`NULL_REQUIRED_DATA` by the *scalar's own* rule, not by a member-presence rule.

### 8.1 Every test node whose expectation this ruling changes

Counted by reading the file; all line numbers are 1-based. Query used:
`rg -n "state_unknown|state_excluded|state is None|\.state\b|WRONG_DATA_SHAPE|NULL_REQUIRED_DATA" tests/test_collector.py`
(15 rows), each triaged against the seven nodes named in plan §9 lines 1481-1483
and the `LREQ-GQL-040` node at line 1477.

| Node | Plan §9 | Expectation under this ruling |
|---|---|---|
| `test_state_excluded_and_unknown_assets_remain_recorded` (`tests/test_collector.py:2236-2239`) | line 1482, `LREQ-GQL-060` | **CHANGES — the node that must be made green.** Lines 2236 and 2237-2238 become correct once §7.4 items 1-3 are applied. Its `state_excluded` half (2207-2214) is already correct. |
| `test_state_annotation_covers_published_excluded_and_unknown` (`tests/test_collector.py:2187-2201`) | line 1481, `LREQ-GQL-060` | **Expectation unchanged** — despite its name it exercises only published (2189-2193) and excluded (2195-2201). It does **not** currently cover the "unknown" third of its own name; that is a test-naming defect worth a follow-up, not a change caused by this ruling. |
| `test_invalid_state_value_and_missing_identity_are_operation_errors` (`tests/test_collector.py:1956-1983`) | line 1477, `LREQ-GQL-040` | **Unchanged, and must stay green.** Its `invalid_state_body` half (1958-1966) is case (c1) — still `INVALID_STATE_VALUE`. Its identity half (1968-1983) is unaffected: `id`/`productId` remain required members, so `missing_identity_member_body` is still `MISSING_IDENTITY` by the mechanism its own docstring describes. |
| `test_failed_operation_fields_are_none_never_zero` (`tests/test_collector.py:2133-2178`) | line 1480, `LREQ-GQL-050` | **Expectation unchanged**; its `draft.state is None` assertion (2114, 2155, 2168) still holds — but see §7.4 item 3: it is about a **failed** operation, and conflating it with (a)/(b) is exactly the ambiguity the sentinel field exists to remove. |
| `test_partial_success_retains_valid_operation_fields` (`tests/test_collector.py:2100-2129`) | line 1479, `LREQ-GQL-050` | **No change required.** |
| `test_null_required_data_and_wrong_data_shape_are_operation_errors` | line 1476, `LREQ-GQL-040` | **No change required** — it exercises whole-payload `null`/wrong-shape (lines 1921-1951), not the `state` member. |
| `test_adapter_declares_no_metric_eligibility_verdict` (`tests/test_collector.py:2243-2276`) | line 1483, `LREQ-GQL-060` | **No change required**, with a caveat: if §7.4 item 3 is implemented by adding a field whose **name** contains no "eligib"/"score"/"d"/"r"/"q"/"rankability" substring, this node's `dataclasses.fields` sweep (2252-2254) still passes. A field named e.g. `state_eligibility` **would break it**. Name the new field `state_unknown` (or `state_annotation_state`), never `state_eligibility`. |

**No other node in `tests/test_collector.py` or `tests/test_identity.py` names
`state` in a way this ruling reaches.** `rg -n "state" tests/test_identity.py`
returned no row that asserts a GraphQL `state` member's presence classification
(**unverified**: I did not open `test_identity.py` in full; the query result was
empty for the member-classification pattern).

---

## 9. Counter-argument, addressed

**The strongest case for the reading I rejected (absent = operation error):**

1. `SRS-lean.md:294-298` (LREQ-GQL-020) is a **SHALL** and names `state` among the
   members the `ProductDetail` operation "SHALL request". A response omitting a
   member the operation was required to request is, on its face, a response of the
   wrong shape.
2. `SRS-lean.md:318-323` (LREQ-GQL-040) lists "wrong data shape" and "null required
   data" as operation errors, and `state` is, by argument (1), required.
3. The project rule (SRS `:76-77`, `AGENTS.md`) says missing values "SHALL remain
   unavailable". Invalidating the operation certainly makes `state` unavailable —
   the strongest possible form of compliance.
4. `SRS-lean.md:305-312` (LREQ-GQL-030) establishes the house style that an
   unvalidated or ambiguous GraphQL structure is "malformed" and its fields
   "remain unavailable" — i.e. this SRS prefers failing closed on response
   structure.

**Why it loses:**

- Argument (1) is about the **request**, not the response. LREQ-GQL-020's second
  sentence draws the line itself: "Fields not required by scoring MAY be omitted
  from the lean implementation" — the requirement governs what is *asked for*.
  Nothing in it says a response missing a requested member is malformed.
- Argument (2) begs the question. "Null required data" (`:320`) and "missing
  identity" (`:321`) are the only two member-level failure items LREQ-GQL-040
  names; it never says "missing required member". The adapter **invented** the
  `response_missing_required_member` → `WRONG_DATA_SHAPE` mapping. The map's own
  LREQ-GQL-040 edge-case column (`requirements-dependency-map.md:171`) enumerates a
  different, closed set — "HTTP failures, GraphQL errors, null data, wrong types,
  missing or ambiguous operation association" — in which "missing" attaches to
  *operation association* (LREQ-GQL-030), not to a member.
- Argument (3) is defeated by `SRS-lean.md:33-35`. The lean SRS is silent on what a
  missing `state` member means; the parent contract therefore remains applicable;
  and the parent, at `SRS-revision2.md:293` (REQ-GQL-120), says in terms that "a
  null **or missing** state is `state_unknown`" and that the asset "SHALL remain"
  for audit. A bridge that resolves silence in favor of the parent's explicit
  sentence cannot be overridden by "fail closed" as a preference.
- Argument (3) is independently defeated by its own consequence: it makes `state`
  *unavailable* by making **every other field unavailable too**. At
  `collector_graphql.py:1186` the whole `ProductDetailFields` is dropped — the
  retained-breadth guarantee of `SRS-lean.md:330` and map `:652` becomes
  unobservable, and `LREQ-MET-060`'s recent-supply population loses an asset that
  has a usable publication date. That is not a conservative reading; it is the
  loss of discoverable data the SRS requires to be kept.
- Argument (4) is real but narrow: LREQ-GQL-030's "malformed" attaches to
  **correlation** ambiguity ("the implementation SHALL never guess from response
  position"), not to payload member presence. It does not reach case (a).
- Finally, on the reading's own terms it is **incoherent about case (c2)**: if
  `state` is required because LREQ-GQL-020 names it, then a present `"deprecated"`
  must *also* be an operation error — yet LREQ-GQL-060's "state-excluded" and plan
  §8 E7 both say it is a retained, successful, annotated asset. So the "required
  because named" premise does not hold even in the plan's own text; it cannot be
  the ground for treating its absence as an error.

---

## 10. Open questions — for a human, not for an agent

Per the project rule, an open question blocks a plan's freeze and no agent may
clear one on its own. This ruling deliberately decides **behavior** and leaves
these three items open. They are the reason this document is a ruling rather than
an authorization to edit code.

**Q-1 (blocking; persistence, frozen interface).** §7.4 item 3. Under (a) and (b),
the persisted `enrichment_observations.state` is `NULL` — the same row as a failed
operation, because `EnrichmentObservationRecord` (`src/niche_scout/models.py:438`)
has no annotation field and `SRS-lean.md:575-580` lists no annotation column.
Three options, none of which Chunk 5 may choose alone:
  (i) add a `state_unknown` boolean/sentinel **column** to the frozen §6.4 field
      list (`SRS-lean.md:570-583`) and to `models.py` / `chunk-02.md` — touches a
      frozen interface and a frozen SRS field contract;
  (ii) keep the schema unchanged and accept that a row with
      `product_detail_status = "success"` and `state = NULL` means "unknown", while
      `product_detail_status = "error"` means "failed" — this works **only** because
      `product_detail_status` is `SUCCESS` for (a)/(b), and it makes
      `chunk-02.md`'s `state` column semantics load-bearing;
  (iii) persist a sentinel string such as `"unknown"` in `state` — **rejected on
      sight by project rule** ("Missing, invalid, contradictory, or unavailable
      values SHALL remain unavailable; never fabricate zeros"): a sentinel string
      is a fabricated value in a column whose domain is marketplace states.
  This question must be answered before the fix is implemented, because option (ii)
  is a one-line classification fix and option (i) is a cross-chunk change.

**Q-2 (blocking; frozen plan contradiction).** Plan §8 E7 (lines 1309-1311) vs plan
§5.8 (line 915) and §8 E10 (line 1327). One of them must be edited, and the plan is
`Status: FROZEN` (line 3). Options: (i) scope E7's "a required member missing" to
non-`state` members, or to identity members only, by explicit edit; (ii) scope
§5.8/E10 to the case where `state` is not a required member, and then decide
whether it is. I do not choose.

**Q-3 (defect in the SRS, recorded not invented).** `SRS-lean.md` is **genuinely
silent** on whether an absent `state` member is an operation error. It says so
nowhere. `SRS-lean.md:329-330` names "state-unknown" as a retained class but never
defines the conditions that produce it; `SRS-lean.md:318-323` names "invalid state
values" but not "absent state member". The definition exists only in three places
the SRS does not incorporate as normative text: the parent's REQ-GQL-120
(`SRS-revision2.md:293`, reached via the `:33-35` bridge), the map's `:652`, and
this project's own `chunk-01.md:134-139` contract. **Recommendation for a later
SRS revision, not a requirement I am creating:** give `state` one sentence — "A
missing or null `state` is `state_unknown`; a present non-`published` value is
`state_excluded`; a present non-string value is an operation error" — so that the
lean SRS is explicit where `SRS-lean.md:33-35` currently forces a bridge. Until
that sentence exists or a human rules otherwise, this ruling rests on the bridge
and on the parent text, and I say so plainly rather than presenting a fabricated
requirement as SRS text.

---

## 11. Unverified claims

Labeled per the project's counting and verification rules.

- **No test was executed.** I did not run `pytest`, `python -m
  niche_scout.tools.validate_traceability`, or any other command. Every statement
  above about runtime behavior is **derived by reading** the code paths cited, not
  observed. In particular, the claim that
  `test_state_excluded_and_unknown_assets_remain_recorded` currently fails with
  `WRONG_DATA_SHAPE` is **unverified by execution**; the *classification* claim
  (an absent `state` yields `WRONG_DATA_SHAPE` at
  `collector_graphql.py:1203-1204`) is verified by reading the code path from
  `876-885` through `validation.py:1760-1768` to `1196-1204`.
- **The §5 "retry trap" is a reading, not a measurement.** I traced it through
  `1739-1743` → `2020` → `2357`. I did not execute the adapter to confirm that the
  draft's `state` reverts. It should be re-derived by whoever implements the fix,
  with a probe in `.scratch/` per the workspace rule.
- **`tests/test_identity.py` was not opened.** The claim that no node there is
  affected is supported only by a grep that returned no member-classification rows;
  treat it as **unverified**.
- **`Documents/interfaces/chunk-02.md` was not opened.** The claim about that file's
  `state` column semantics in Q-1(ii) is inferred from `models.py:438` and
  `SRS-lean.md:575-580`, not read from the interface file. **Unverified.**
- **I read lines 630-689 of `requirements-dependency-map.md` and did not open
  `Documents/interfaces/chunk-03.md`, `chunk-00.md` (beyond grepping for
  `PRODUCT_DETAIL_REQUIRED_MEMBERS`, which returned no match), the retired
  `SRS-revision2.md` §4.4 region in full, or any plan other than chunk-05.** Claims
  about those files would be unverified; I have made none that depend on them.
- **`SRS-lean.md` line 906** (cited in earlier session work as the only
  `monoton|A-3|Assumption` hit) was not re-opened for this ruling; it is not relied
  on here.

---

## 12. Summary

| Case | Ruling | Current behavior | Must change |
|---|---|---|---|
| (a) member absent | **SUCCESS**, `state_unknown`, `state = None`, retained | ERROR `WRONG_DATA_SHAPE` | yes — `collector_graphql.py:876-885` (primary), `1148`, `1739-1743`; test fixture `tests/test_collector.py:2216-2218` → `tests/fixtures/graphql_fixtures.py` |
| (b) present `null` | **SUCCESS**, `state_unknown`, `state = None`, retained; distinct from (a) in the audit trail | ERROR `NULL_REQUIRED_DATA` | yes — same change |
| (c) present, wrong JSON type | **ERROR** `INVALID_STATE_VALUE` | ERROR `INVALID_STATE_VALUE` | no |
| (c) present, usable string ≠ `"published"` | **SUCCESS**, `state_excluded` | SUCCESS, `state_excluded` | no |

Side at fault for case (a): **the adapter** — and it contradicts its own code
comment at `collector_graphql.py:1149-1151`, its own plan §5.8/E10, and map `:652`
while doing so. The test's assertion becomes correct once the three-part fix is
applied, but the fix is **not authorized by this document alone**: Q-1 (persistence
of the unknown/absent distinction, which touches the frozen `models.py` /
`SRS-lean.md` §6.4 field list) and Q-2 (the frozen plan's internal contradiction
between §8 E7 and §5.8/E10) are open, and both are human decisions.
