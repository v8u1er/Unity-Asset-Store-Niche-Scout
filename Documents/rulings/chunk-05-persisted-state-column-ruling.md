# Ruling — Chunk 5 Q-1: is "state unknown, asset retained" distinguishable from "operation failed" in the persisted `enrichment_observations.state` column?

Status: BINDING (requirement adjudication, not an implementation authorization)
Scope of this document: it decides the **storage contract** question left open at
Q-1 of `Documents/rulings/chunk-05-state-member-ruling.md`. It authorizes no code
edit. No file other than this one was created or modified.
Companion ruling (not modified, not superseded): `Documents/rulings/chunk-05-state-member-ruling.md`.

Everything below is either **quoted** (source opened and read, with a 1-based line
number) or **counted** (query stated verbatim, with the row count it returned).
Anything I did not open or query is labeled **unverified**.

---

## 1. The ruling

**(A) — the distinction is already representable, and it is resolved inside
Chunk 5's own file scope. No cross-chunk change is required.**

Precisely:

1. The persisted column that carries the distinction is **`enrichment_observations.product_detail_status`**
   (the Chunk 2 DDL at `src/niche_scout/database.py:153`, feeding
   `models.EnrichmentObservationRecord.product_detail_status`,
   `src/niche_scout/models.py:428`), read **together with** `state`
   (`models.py:438`). It is the *pair*, and the status column is the
   differentiator; `state = NULL` alone is ambiguous, `state = NULL` **plus**
   `product_detail_status = "success"` is not.
2. For that pairing to work, `product_detail_status` **must** be `"success"` —
   and, critically, `product_detail_error_summary` **must** be `NULL` — on the
   absent/null state paths. Today it is neither: the absent member is classified
   `WRONG_DATA_SHAPE` and the null member `NULL_REQUIRED_DATA`, so both write
   `product_detail_status = "error"` and a non-`NULL` error summary. That is the
   companion ruling's case (a)/(b) defect, and this ruling confirms its
   persistence half needs **no schema change to fix**.
3. The one place a Chunk-5-local change *is* needed is that the
   absent/null distinction required by companion ruling §7 case (b) must be
   carried **in `product_detail_error_summary`**, not in a `state` sentinel and
   not in a new column. See §3.3 — this is the ruling's only correction to the
   companion ruling's §7 case (b) mechanism.
4. **No column, table, enum, dataclass field, or frozen interface changes.** In
   particular `state` SHALL NOT receive a fabricated sentinel such as
   `"unknown"`, and `models.py`, `database.py`, `Documents/interfaces/chunk-02.md`,
   and `Documents/SRS-lean.md` §6.4 are all **not** to be edited.

Naming the exact field and proving it carries the meaning in every case is §3.

---

## 2. The normative text, quoted

### 2.1 `Documents/SRS-lean.md` (normative; opened and read)

**`:575-581` — the `enrichment_observations` required-field list, in full:**

> ```text
> run_id, asset_identity_key, product_detail_status, page_views_status,
> graphql_id, product_id, rating_average, rating_count, review_count,
> first_published_date_utc, publisher_json, category_json, state, product_page_views,
> id_mapping_mismatch,
> product_detail_error_summary, page_views_error_summary, request_metadata_json,
> retrieved_at_utc
> ```

**`:583` — the only nullability sentence attached to that list:**

> `product_page_views` SHALL be nullable and SHALL never use zero as an error sentinel.

Two facts follow, both relied on below. First, the list contains **both**
`product_detail_status` and `state` **and** `product_detail_error_summary` — it is
already a multi-field record, not a single `state` scalar. Second, `state` gets
**no** nullability sentence of its own; the only explicit nullability sentence in
§6.4 is `product_page_views`'s.

**`:318-323` — LREQ-GQL-040 (operation error membership):**

> **LREQ-GQL-040**: Each operation SHALL have an independent status. HTTP failures,
> top-level GraphQL `errors`, HTTP 200 responses with an operation-level `errors`
> member, null required data, wrong data shape, wrong scalar type, boolean/negative/
> non-finite page views, invalid state values, or missing identity SHALL be recorded
> as an operation error. A top-level error SHALL not be treated as a successful
> operation merely because another operation in the same response succeeded.

The words "SHALL be recorded as an operation error" are a **persistence** command:
an operation error is something the record must *show*. That is the SRS text that
makes `product_detail_status` load-bearing.

**`:325-327` — LREQ-GQL-050:**

> **LREQ-GQL-050**: A valid operation's fields MAY be retained when the other operation
> fails. Failed fields SHALL remain null or unavailable; they SHALL NOT be filled with
> zero or another default.

Two states are named here — *valid/retained* and *failed/null* — and nothing in
between.

**`:329-330` — LREQ-GQL-060, in full:**

> **LREQ-GQL-060**: Only `state = "published"` assets are eligible for D, R, and Q.
> State-excluded and state-unknown assets remain part of discovered breadth.

**`:305-312` — LREQ-GQL-030 (the malformed/error precedent for unvalidated structure):**

> Missing, duplicated, unknown, or ambiguous associations SHALL be recorded as malformed
> operation results; the implementation SHALL never guess from response position.
> … If neither mode is validated, both operations
> SHALL be marked malformed and their fields SHALL remain unavailable.

**`:76-77` — §1.2, the project-wide distinctness rule:**

> - Missing, invalid, contradictory, or unavailable values SHALL remain unavailable;
>   they SHALL NOT be silently converted to zero.

**`:33-35` — the endpoint-contract silence bridge, quoted because the companion
ruling rested on it and this ruling must state whether it also reaches persistence:**

> Where this document is silent about an external endpoint contract, the corresponding
> contract in the parent SRS remains applicable. Where this document is explicit, this
> document takes precedence for the lean implementation.

**This is the finding of the section, and it is a narrow one:** `:33-35` is scoped
to "an external endpoint contract". Storage is **not** an external endpoint
contract — it is the lean SRS's own normative domain, which the lean SRS sets out
in its own §6.4 at `:570-581`. The bridge that the companion ruling used to reach
the parent's REQ-GQL-120 **classification** sentence therefore does **not**
authorize importing the parent's **schema** (its `state_exclusion_reason` column)
into the lean design. The lean column list at `:575-581` is explicit, and
`:33-35`'s second sentence makes it take precedence. See §3.4.

**`:653-657` — LREQ-MET-010:**

> **LREQ-MET-010**: A product-level value is usable only when its type, range, state,
> identity, and timestamp conditions for the relevant metric pass. Null, malformed,
> future, naive, negative, non-finite, or state-excluded values SHALL be unavailable.

**`:808-815` — §7.5, quality eligibility (opened because it is the only place a
downstream consumer runs the operation-status question):**

> An asset is quality-eligible only when ProductDetail and ProductPageViews succeeded,
> identity mapping matched, `state = "published"`, `rating_average` is finite in
> `[0, 5]`, `rating_count >= QUALITY_MIN_RATING_COUNT`, the page-view index is usable,
> and page-view semantics are not contradicted. Only quality-eligible observations in
> strata meeting `MIN_USABLE_SAMPLES_PER_STRATUM` contribute to `QualityRaw`; other
> valid observations remain visible in counts but do not create a partially supported
> stratum estimate.

This is the passage that decides whether the distinction is *consumable*. Quality
eligibility is a **conjunction** in which "ProductDetail and ProductPageViews
succeeded" is one conjunct and `state = "published"` is another. Under the
companion ruling's fix, an absent/null-state asset fails the second conjunct
(`state` is `None`, and `None` is not `"published"`) no matter what
`product_detail_status` says. So the metric layer needs the status/state pair to be
*readable*, not *conflated* — and it never needs to ask "was the state member
absent, or null?". See §6.

**`:1113-1119` — LREQ-RPT-020 (the report's required columns):**

> **LREQ-RPT-020**: The primary table SHALL show category, rank, composite score,
> `D/C/R/Q`, discovered population, sample size, census flag, unique enrichment count,
> sample fraction, sampling basis, cross-category overlap count, usable count and
> stratum eligibility coverage per component, evidence grade, rankability, discovery
> status, page-view semantic status, `top_3_stability`,
> `top_5_stability`, `maximum_score_delta`, `maximum_rank_displacement`, sensitivity
> warning, and the percentage of the category sample shared with other categories.

Quoted because it is the *closest* thing in the SRS to a "downstream reader must be
able to tell" requirement, and it does **not** name `state`, `state_unknown`, or
any per-asset observation column. See §5.

**`:1239-1242` — LREQ-TST-040 (the test-observable surface):**

> **LREQ-TST-040**: GraphQL tests SHALL cover success, reversed response ordering,
> missing/ambiguous operation association, operation errors, null data, wrong types,
> negative/non-finite page views, partial success, state filtering, and permanent
> authentication/CSRF failures.

**`:1168-1169` — LREQ-NFR-030:**

> **LREQ-NFR-030**: A failed page or sampled asset SHALL not abort unrelated categories
> or assets; the failure SHALL remain visible in status and evidence fields.

The words "status and evidence fields" are the second SRS text (after LREQ-GQL-040)
that makes a persisted status field load-bearing. Note it requires a *failure* to be
visible; it does not require a *non-failure* to be visible.

### 2.2 `Documents/retired-documents/SRS-revision2.md` ([PARENT]; opened and read)

Reached only for the classification contract, per `SRS-lean.md:123-126` ("source for
unchanged **endpoint details**").

**`:293` — REQ-GQL-120:**

> - **REQ-GQL-120 (DD-4, revised in v2.1.0)**: State eligibility SHALL be explicit: `product.state == "published"` is eligible for D/R/Q; a null or missing state is `state_unknown` and is excluded from D/R/Q; any present value other than `"published"` is `state_excluded` and is excluded from D/R/Q. The asset SHALL remain in `raw_product_details` for audit purposes. State filtering does not remove an asset from discovery breadth or C, because C is a discovery-only metric (REQ-MET-040).

**`:404` — the parent's DDL, quoted for exactly one purpose, to show what the lean
SRS deliberately did *not* carry over:**

>     state_exclusion_reason                                                                                                          TEXT CHECK (state_exclusion_reason IN ('state_excluded','state_unknown')),

**`:395-399` — the parent's own `state` / status columns, quoted because they are
the parent's *counterpart* to the lean pair:**

>     state                                                                                                            TEXT,
>     plus_pro_sale                                                                                                       INTEGER CHECK (plus_pro_sale IN (0,1)),
>     product_page_views                                                                                                     REAL,
>     product_detail_status                                                                                                     TEXT NOT NULL CHECK (product_detail_status IN ('ok','error')),
>     page_views_status                                                                                                            TEXT NOT NULL CHECK (page_views_status IN ('ok','error')),

**`:477` — the parent's data dictionary row for `state`, quoted in full because it
is where the parent states what a `NULL` `state` *means*:**

> | `state` | `raw_product_details` | TEXT | Yes | e.g. `"published"` | `"published"` is eligible for D/R/Q; null or missing is `state_unknown`; other values are `state_excluded`. State does not affect discovery-only C (REQ-GQL-120, DD-4). |

Two observations, and they cut in opposite directions — both are stated because the
ruling depends on holding them together:

- The parent **has** a dedicated column for the distinction
  (`state_exclusion_reason`, `:404`), and its own table is named
  `raw_product_details` (not the lean SRS's `enrichment_observations`).
- The lean SRS's `:575-581` list is **different from the parent's table**: it drops
  `state_exclusion_reason`, drops `plus_pro_sale`, drops `raw_json`, and renames the
  table. That is a deliberate divergence by a document whose `:131-132` declares
  itself "the normative source for sampling, sample-derived metrics, evidence grades,
  rankability, and sensitivity analysis" and whose `:33-35` gives it precedence where
  it is explicit.

So the parent proves the distinction is *coherent and intended in this project*, and
simultaneously proves that the lean SRS **chose a different column set**. Option (i)
of the companion ruling's Q-1 — "add a `state_unknown` boolean/sentinel **column** to
the frozen §6.4 field list" — is therefore a proposal to un-do a deliberate lean
divergence, reached only through a bridge that does not reach storage. §3.4 and §6
develop this.

---

## 3. The exact representable carrier, proven case by case

### 3.1 The carrier

| Layer | Name | file:line |
|---|---|---|
| Column | `enrichment_observations.product_detail_status` | `src/niche_scout/database.py:153` |
| Column | `enrichment_observations.state` | `src/niche_scout/database.py:163` |
| Column | `enrichment_observations.product_detail_error_summary` | `src/niche_scout/database.py:166` |
| Column | `enrichment_observations.id_mapping_mismatch` | `src/niche_scout/database.py:165` |
| Dataclass field | `EnrichmentObservationRecord.product_detail_status: str` | `src/niche_scout/models.py:428` |
| Dataclass field | `EnrichmentObservationRecord.state: str \| None` | `src/niche_scout/models.py:438` |
| Dataclass field | `EnrichmentObservationRecord.product_detail_error_summary: str \| None` | `src/niche_scout/models.py:441` |
| Draft field | `EnrichmentObservationDraft.product_detail_status: str` | `src/niche_scout/collector_graphql.py:1591` |
| Draft field | `EnrichmentObservationDraft.state: str \| None` | `src/niche_scout/collector_graphql.py:1601` |
| Draft field | `EnrichmentObservationDraft.product_detail_error_summary: str \| None` | `src/niche_scout/collector_graphql.py:1604` |

The DDL declaration for the status column, quoted (`database.py:149-173`, the
`CREATE TABLE enrichment_observations` statement):

> ```sql
> CREATE TABLE enrichment_observations (
>     run_id TEXT NOT NULL,
>     asset_identity_key TEXT NOT NULL,
>     product_detail_status TEXT NOT NULL,
>     page_views_status TEXT NOT NULL,
>     …
>     state TEXT,
>     product_page_views INTEGER,
>     id_mapping_mismatch INTEGER NOT NULL,
>     product_detail_error_summary TEXT,
>     page_views_error_summary TEXT,
>     request_metadata_json TEXT NOT NULL,
>     retrieved_at_utc TEXT NOT NULL,
>     PRIMARY KEY (run_id, asset_identity_key),
>     FOREIGN KEY (run_id) REFERENCES runs (run_id)
> )
> ```

Three facts I verified by reading, not assumed:

- `state TEXT` — **nullable**, no `CHECK`, no `NOT NULL`. A `NULL` `state` is a
  permitted, first-class column value.
- `product_detail_status TEXT NOT NULL` — **not nullable** and status-bearing. Its
  allowed values are pinned in code at `database.py:410-412`:
  `("enrichment_observations", "product_detail_status"): tuple(item.value for item in OperationStatus)`.
- `product_detail_error_summary TEXT` — **nullable**, so `NULL` here is itself a
  meaningful value (and is the mechanism §3.3 uses).

I also verified that `database.py` is **not** a module Chunk 5 may import —
`Documents/plans/chunk-05-…md:1177` lists `src/niche_scout/database.py` under
"Deliberately **not** touched", `:1644-1645` forbids `collector_graphql.py` from
importing `database`, and `:1656` forbids it from persisting at all. This matters for
the ruling: **Chunk 5 produces the draft; it does not write the row.** The ruling is
therefore about what the draft must *carry*, which is what Chunk 5 owns.

### 3.2 The case table — every case, with the stored tuple

Derived from companion ruling §7 and its case (c1)/(c2) split, combined with the
current draft-construction code at `collector_graphql.py:1694-1715` and
`:1609-1630`. `d.graphql_id` below is "the draft's `graphql_id` field".

| # | Case | `product_detail_status` | `state` | `product_detail_error_summary` | `id_mapping_mismatch` | Retained in discovered breadth? |
|---|---|---|---|---|---|---|
| 1 | `state = "published"`, everything valid | `"success"` | `"published"` | `NULL` | `False` | yes (eligible for D/R/Q, Chunk 7A) |
| 2 | `state` present, usable, ≠ `"published"` (case c2) | `"success"` | `"deprecated"` | `NULL` | `False` | **yes — state-excluded** |
| 3 | `state` member **absent** (case a) | `"success"` ← *changed by the fix* | `NULL` | `"…[member=state, present:false]…"` ← *the absent/null marker* | `False` | **yes — state-unknown** |
| 4 | `state` present but JSON `null` (case b) | `"success"` ← *changed by the fix* | `NULL` | `"…[member=state, present:true]…"` ← *the absent/null marker* | `False` | **yes — state-unknown** |
| 5 | `state` present, wrong JSON type / empty string (case c1) | `"error"` | `NULL` | non-`NULL`, `invalid_state_value` | `False` | yes (per map `:173`, but the operation **failed**) |
| 6 | `product` absent, or a required identity member absent, or `product` not an object | `"error"` | `NULL` | non-`NULL` | `True` | yes (discovery retains; operation failed) |
| 7 | `product_detail` payload wholly `null` | `"error"` | `NULL` | non-`NULL` | `True` | yes; operation failed |
| 8 | top-level GraphQL error / HTTP failure / transport failure | `"error"` | `NULL` | non-`NULL` | `True` | yes; operation failed |

**The proof, stated as the reader's rule.** A downstream consumer distinguishes the
two collapsed meanings by the pair `(product_detail_status, state)`:

- rows 3–4: `product_detail_status = "success"` **and** `state IS NULL` → **"state
  unknown; the asset was retrieved and is retained."**
- rows 5–8: `product_detail_status = "error"` **and** `state IS NULL` → **"the
  operation failed; nothing was retrieved."**

The two conditions are mutually exclusive because `product_detail_status` is
`NOT NULL` and single-valued, so no row can satisfy both, and exhaustive over the
`state IS NULL` subspace because `OperationStatus` has exactly the values pinned at
`database.py:410-412`. That is what "prove it carries the meaning in every case"
requires, and it holds **without any schema change**.

Restated as the fact that answers Q-1's own framing: the persisted
`enrichment_observations.state` column is *not* the carrier, and never was. The
carrier is `product_detail_status`; `state` is the **payload** whose
missingness is *classified* by that carrier. Q-1's premise ("the persisted
`enrichment_observations.state` column ends up `NULL` — the same stored value a
failed operation writes") is correct about the *column* and was mistaken about the
*row*: a failed operation does not produce the row `("success", NULL)`.

### 3.3 The one correction: the absent/null distinction goes in the error summary, not a new column

Companion ruling §7 case (b) attaches a condition: the persisted record must show
that `state` was *present and null* rather than *absent*, or the fix itself violates
"missing, invalid, and contradictory remain distinct". The companion ruling proposed
carrying that through `ValidationIssue`s. This ruling **confirms the requirement and
fixes the mechanism**, because carrying it in `issues` alone loses it at the
persistence boundary:

- `collector_graphql.py:563-565` builds the summary as
  `return summarize_validation_issues(issues) if issues else None` — i.e. the
  per-operation **error summary is the only place an issue's content is serialized
  onto the record**.
- `collector_graphql.py:1711-1712` copies it verbatim into the draft
  (`product_detail_error_summary=result.product_detail.error_summary`).
- `collector_graphql.py:1604`/`:1613` carry it on the draft; `models.py:441` on the
  record; `database.py:166` in the column.
- Conversely, `EnrichmentObservationDraft` (`collector_graphql.py:1582-1607`) has
  **no** issues field, and `EnrichmentObservationRecord` (`models.py:417-447`) has
  none either. Since Chunk 5 does not persist and Chunks 6A/6B consume the *draft*,
  an issue that is not summarized into `product_detail_error_summary` **does not
  reach the database.**

**Ruling:** on successful cases 3 and 4, `product_detail_error_summary` SHALL be
non-`NULL` and SHALL distinguish the two, by naming the member `state` together with
whether it was **present**. Concretely, `ValidationIssue.code` for case 3 SHALL be a
distinct code from case 4's (the compliant shape is a `state`-scoped pair such as
`response_missing_state_member` / `response_null_state_member`, or one code plus a
`context` member that says `present: true|false`), and the resulting summary string
must be able to name `state` and its presence. The redaction rule at
`Documents/plans/chunk-05-…md:1664-1667` is untouched: `state` is a marketplace
state string, not a credential; only header *values*, tokens, cookies, and full
bodies are forbidden.

**Consequences of this choice, both intended:**

1. Rows 1–2 (`"success"`, `state` non-`NULL`) are unaffected — they carry `NULL`
   summary, so the pre-existing meaning of a `NULL` summary ("success, no
   annotations") is preserved.
2. Rows 5–8 are unaffected and keep their non-`NULL` summaries.
3. So the **only** rows with a non-`NULL` summary *and* `"success"` status are 3–4,
   which is precisely the pair the distinction needs, and it is now a
   three-field tuple (`status`, `state`, `summary`) rather than two. See §8 for the
   residual loss this still leaves.

### 3.4 Why not the sentinel string, and why not a new column

- **`state = "unknown"` (companion ruling Q-1 option iii) is rejected, and the
  companion ruling's own rejection is right.** The column's domain is marketplace
  state strings (`SRS-lean.md:477`-equivalent parent domain, quoted at
  parent `:477`: "e.g. `"published"`"). Writing `"unknown"` into it fabricates a
  marketplace value — it would be indistinguishable from a future real marketplace
  state literally named `unknown`, and it violates `SRS-lean.md:76-77`.
- **A new `state_unknown` column (companion ruling Q-1 option i) is rejected as
  unnecessary, not as incoherent.** It is rejected on the evidence in §3.2: option
  (ii) already carries the meaning in every case, so option (i) would add a schema
  change, a `models.py` field, a `chunk-02.md` contract change, and a
  `SCHEMA_VERSION` decision (`chunk-02.md:62`, `SCHEMA_VERSION = "1.0.0"`, itself
  frozen by Chunk 0), plus `chunk-02.md`'s own statement at `:22-23` that Chunk 2
  "adds **no table, no column, no index, and no constant**, and modifies no frozen
  Chunk 0 name" and at `:182` "No `ALTER TABLE`, no column addition" — **all of it to
  carry a fact the existing pair already carries.**
- The lean SRS's `:575-581` list is the field contract, and `:33-35` bridges only
  *external endpoint contracts*, not storage (§2.1). Adding a column would therefore
  require editing `SRS-lean.md` §6.4 itself, which is a **requirement-text** change,
  not a schema change — a far larger step than the companion ruling's Q-1(i)
  framing suggested.

---

## 4. The dependency map, quoted — who owns what

**Ownership rows** (`Documents/requirements-dependency-map.md`, "Ownership and test
traceability matrix"):

**`:65` — LREQ-GQL-060:**

> | LREQ-GQL-060 | Chunk 7A | Chunk 1, Chunk 5 | Chunk 5, Chunk 7A | LREQ-TST-040, LREQ-TST-050 |

**`:173` — the same LREQ's edge-case row:**

> | LREQ-GQL-060 | `validation.py`, `collector.py` | LREQ-GQL-020, LREQ-GQL-040 | Pure validation over I/O result | Eligibility unit/fixture test | Only `published` assets eligible for D, R, and Q; state-excluded and state-unknown assets remain in discovered breadth and persisted observations |

**`:18` — the module-boundary rule:**

> - The module boundary is fixed: `models.py` contains typed structures; `validation.py` contains structural and semantic validation primitives; `sampling.py` contains deterministic sampling; `metrics.py` contains metric eligibility and raw sample-aware estimators; `scoring.py` contains normalization, score components, evidence, and sensitivity; I/O and orchestration remain in `collector.py`, `database.py`, `pipeline.py`, `report.py`, and `cli.py`.

**`:145` — LREQ-ARCH-010's row, which is the row that makes `models.py` a shared
frozen file:**

> | LREQ-ARCH-010 | `models.py`, `metrics.py`, `scoring.py` | — | Pure boundary | Architecture/import test; analytical tests | Typed structures only; no imports from collector/database/report/CLI; no file or network I/O |

**Chunk 2's section (`:483-518`) — the owner of the physical table:**

> ## Chunk 2 — SQLite implementation and repository behavior
> **Goal:** Implement the audit trail and repository behavior before runtime discovery or sampling. Chunk 0 defines typed domain/schema contracts; this chunk owns the physical SQLite implementation.
> Implement tables:
> - `runs`
> - `raw_discovery_observations`
> - `sample_members`
> - `enrichment_observations`
> - `category_scores`

**Chunk 5's section (`:639-681`) — what Chunk 5 owns and does not:**

> ## Chunk 5 — GraphQL protocol adapter and response correlation
> …
> - state eligibility annotation; excluded and unknown-state assets remain in persisted observations and discovered breadth  (`:652`)
> …
> Supporting adapter behavior:
> - LREQ-GQL-060 and LREQ-GQL-070; their metric-eligibility and metric identity-mismatch completion is owned by Chunk 7A.  (`:664`)
>
> Gate: … (`:674-681`)
> - The metric-eligibility portion of LREQ-GQL-060 and the metric identity-mismatch eligibility portion of LREQ-GQL-070 are not complete until Chunk 7A applies them to metric inputs.  (`:681`)

### What the ownership rows settle

1. **Chunk 5's own "Implement" bullet at `:652` names *persisted observations* as a
   Chunk 5 obligation in express terms** — "excluded and unknown-state assets remain
   in persisted observations and discovered breadth". The companion ruling cited this
   line only for the discovered-breadth half; it has a persistence half too. So
   Chunk 5 does own *the act of producing a draft that a persistence layer can store
   without loss on the unknown-state path*. That is exactly the scope of §3.3, and it
   is why §3.3's change is **inside** Chunk 5's file scope
   (`collector_graphql.py`, `tests/test_collector.py`,
   `tests/fixtures/graphql_fixtures.py` — plan `:1163-1171`).
2. **`models.py` is *not* Chunk 5's.** It carries `LREQ-ARCH-010` (`:145`), plan §11
   `:1711-1713` forbids Chunk 5 touching it, and plan §6 `:1177` lists it under
   "Deliberately **not** touched". Any option that adds a dataclass field is a
   cross-chunk change.
3. **The physical column set is Chunk 2's** (`:487-493`, `:497`), and
   `Documents/interfaces/chunk-02.md` is `Status: VERIFIED` and declares itself
   frozen (`:11-15`): "Everything below is frozen: downstream chunks may consume these
   names and semantics, and SHALL NOT redefine them."
4. **`LREQ-GQL-060`'s primary owner is Chunk 7A, not Chunk 5** (`:65`; `:767-788`
   "metric-eligibility completion for LREQ-GQL-060"). Chunk 5 is the *supporting*
   chunk and the *completion* chunk for the annotation half only. So if the fix
   required a metric-layer change, Chunk 5 could not make it — but §6 shows it does
   not.

**Net:** option (B) would be a three-file cross-chunk change
(`src/niche_scout/models.py`, `Documents/interfaces/chunk-02.md`, and
`src/niche_scout/database.py`'s DDL plus a `SCHEMA_VERSION` decision — owner Chunk 2,
with the `SRS-lean.md` §6.4 list as a fourth). Option (A) needs one Chunk-5-local
change (§3.3).

---

## 5. Does a requirement mandate the distinction? — **No.**

This is the section the task asked to be answered plainly, and the answer is plain.

I searched for every requirement that could plausibly make a *downstream reader's
ability to distinguish* mandatory.

**Query (verbatim, over the lean SRS):**
`Grep pattern="state_unknown|state-unknown|unknown" path=Documents/SRS-lean.md` →
**2 rows**: `:305` ("duplicated, unknown, or ambiguous **associations**" — operation
correlation, LREQ-GQL-030's subject) and `:330` ("State-excluded and
state-unknown assets remain part of discovered breadth").

**Reading of the two rows:** the lean SRS uses the token `state_unknown`
**exactly once** (`:330`), and that occurrence is a *breadth* sentence, not a
*persistence-shape* sentence. It never defines what produces `state_unknown`
(companion ruling §10 Q-3 found this too), and it never says the persisted record
must let a reader identify it.

**Query (verbatim):** `Grep pattern="annotation|annotate|eligib" path=Documents/SRS-lean.md`
→ **53 rows**, triaged: **every** row that is not `stratum eligibility coverage` /
`eligible` in the metric sense is one of `:329` (`state = "published"` assets are
eligible), `:655-657` (`LREQ-MET-010`), `:809-812` (quality eligibility), `:814`,
`:657`. The word **"annotation" does not occur in `SRS-lean.md` at all** — 0 rows
for `annotation`, `0` for `annotate`. The entire annotation vocabulary
(`StateEligibilityAnnotation`, `annotate_state_eligibility`,
`remains_in_discovered_breadth`) is a **project design artifact**, defined in
`validation.py:395-410` and frozen in `Documents/interfaces/chunk-01.md:133-139`,
not an SRS noun.

**Query (verbatim):** `Grep pattern="audit|distinguish|downstream|reader|consumer" path=Documents/SRS-lean.md`
→ **8 rows**: `:89` ("SQLite persistence of audit-critical normalized
observations"), `:111` (discovered population, "retaining them in audit data"),
`:195` (`database` module = "SQLite schema and normalized audit persistence"),
`:210` ("retaining every raw API observation for audit"), `:839` ("Coverage below the
threshold SHALL remain distinguishable" — *coverage*, i.e. stratum eligibility
coverage vs. sample fraction), `:1130` ("distinguish pagination completion from
immutable snapshot completeness"), `:1336`, `:1391`.

Triaged: **`:839` and `:1130` are the only two SRS uses of "distinguish", and both
are about category-level methodological categories** (coverage vs. fraction;
pagination completion vs. snapshot completeness). Neither is about a per-asset
observation's state-vs-failure status. `:89`, `:111`, `:195`, `:210` establish that
audit persistence exists and must retain raw observations — they do **not** specify
*which columns* a reader needs in order to tell two meanings apart.

**Quoted, and this is the closest candidate:** `SRS-lean.md:1113-1119`
(LREQ-RPT-020, §2.1 above) enumerates the primary table's columns exhaustively —
"category, rank, composite score, `D/C/R/Q`, discovered population, sample size,
census flag, unique enrichment count, sample fraction, sampling basis, cross-category
overlap count, usable count and stratum eligibility coverage per component, evidence
grade, rankability, discovery status, page-view semantic status, `top_3_stability`,
`top_5_stability`, `maximum_score_delta`, `maximum_rank_displacement`, sensitivity
warning, and the percentage of the category sample shared with other categories."
**No per-asset column, no `state`, no `state_unknown`, and no operation-error
breakdown appears in it.**

Also checked, and negative: `:637` — "Raw metrics and scores except counts and status
fields SHALL be nullable." This sentence tells us **counts and status fields are
intentionally *not* nullable**, which is a general endorsement of status fields as
load-bearing (§3.1's `product_detail_status NOT NULL` is consistent with it), but it
names no distinguishing requirement.

### The finding

**No requirement in `Documents/SRS-lean.md` mandates that a downstream consumer be
able to distinguish "state unknown, asset retained" from "operation failed, nothing
retrieved."** The nearest normative texts —

- `LREQ-GQL-040` `:318-323` ("SHALL be recorded as an operation error"),
- `LREQ-NFR-030` `:1168-1169` ("the failure SHALL remain visible in status and
  evidence fields"),
- `LREQ-GQL-060` `:329-330` ("remain part of discovered breadth"), and
- the map's `:173` ("remain in discovered breadth and persisted observations"),

— each mandate that **one** of the two states be visible (failure visible; breadth
retained). **None mandates that the two be distinguishable from each other in the
persisted record.** The distinction is therefore **desirable, not required by any
LREQ**. Option (A) satisfies it at zero cross-chunk cost; that is the whole of the
argument for (A) over (B), and it is enough, because (B) is the expensive option.

I did not invent a requirement to reach this conclusion, and I am recording the
absence as the finding.

---

## 6. Does the collapsed representation violate the architecture rule?

**The rule, quoted from `AGENTS.md` (workspace rule, opened and read):**

> Null, zero, invalid, and unavailable are distinct states. Missing, invalid,
> contradictory, or unavailable values SHALL remain unavailable; never fabricate
> zeros.

and its SRS-level counterpart, `SRS-lean.md:76-77` (§2.1).

**Finding: the pairing in §3.2 does not violate this rule, and the reason is
precise.** The rule's verb is *fabricate* and its explicit forbidden outcomes are
"zero or another default" (`LREQ-GQL-050`, `:325-327`) and "silently converted to
zero" (`:76-77`). On cases 3–4 the fix writes `state = NULL` — a first-class
unavailable sentinel, never a fabricated `"published"`, `""`, or `0`. Chunk 2's own
interface file states the module obeys the same line
(`Documents/interfaces/chunk-02.md:50-51`, "**Null, zero, invalid, and unavailable
stay distinct.** No code path converts `None`/missing/invalid to `0`, `0.0`, `""`, or
`False` on write or on read"), and `database.py:12-14` restates it. So the rule is
**satisfied** by the fix.

But the rule has a second clause — the states are "**distinct states**" — and that is
where a real, narrower question lives. Two different meanings sharing one stored cell
is a *distinguishability* concern, not a *fabrication* concern:

- **It is not a violation of this rule**, because the rule governs the *value written*
  and forbids substitution of a default. `NULL` is the correct, non-fabricated value
  for an unavailable `state` in every one of rows 2–8.
- **It is a schema-completeness defect** — and, per §5, a defect no LREQ currently
  names. It becomes a *rule*-level violation only in the one case where the collapse
  is used to **manufacture a value**: if someone later "resolved" the ambiguity by
  writing `"unknown"` into `state`, that would be fabrication and the rule would
  forbid it. §3.4 rejects that path for exactly that reason.
- **Critically, §3.2 means the collapse does not occur**: the pair
  (`product_detail_status`, `state`) distinguishes all eight rows, so on the fixed
  representation there is no shared stored cell carrying two meanings. The
  distinguishability concern that motivated Q-1 is discharged by the fix, not
  papered over.

**And the metric layer needs nothing more, which I checked rather than assumed.**
`SRS-lean.md:809-812` (§2.1) makes quality eligibility the conjunction
"ProductDetail **and** ProductPageViews succeeded, identity mapping matched,
`state = "published"`, …". "Succeeded" is decided by `product_detail_status`;
`state = "published"` is decided by `state`. Under the fix, a case-3/4 asset fails the
`state = "published"` conjunct regardless of its status, and a case-5..8 asset fails
the "succeeded" conjunct. **No metric, count, coverage field, or eligibility
primitive needs to know whether the member was absent or null** — I found no
formula in §§7–9 that consumes that distinction, and `LREQ-MET-010`'s list
(`:655-657`) names "state-excluded" and unusable values, not "state-unknown". The
absent-vs-null granularity is an **audit-trail** property, which is why §3.3 puts it
in an audit field (`product_detail_error_summary`) rather than a metric input.

---

## 7. Consequence of being wrong

### If the project picks (B) — add a column — while §3.2 holds

1. **Frozen-interface churn for no behavioral gain.** `models.py:417-447` gains a
   field, `Documents/interfaces/chunk-02.md` (Status: VERIFIED) must gain it too and
   lose its `:22-23` claim to add "no column"; `database.py:149-173` gains a column;
   `SCHEMA_VERSION` (`chunk-02.md:62`, `"1.0.0"`, frozen by Chunk 0) must be
   reconsidered, and `chunk-02.md:179-182` forbids silent migration — "it never
   migrates silently and never deletes data". Existing databases would need a
   migration path the module currently refuses to provide.
2. **It contradicts the lean SRS's own field list.** `SRS-lean.md:575-581` is
   explicit and exhaustive; a new column means editing §6.4 of the SRS, i.e. making
   a *requirement-text* change to satisfy a requirement nobody has written.
3. **It propagates outward.** `Documents/interfaces/chunk-00.md:199-205` counts
   `EnrichmentObservationRecord` at "19 fields" and lists them; that count and list
   change. `models.MANDATORY_ROW_FIELDS` (`models.py:524-527`) is asserted equal to
   `TABLE_COLUMNS` (`chunk-02.md:77-78`, "asserted by
   `tests/test_contracts.py:921`") — so a `models.py`-only addition without the DDL
   addition **breaks a passing test in a file Chunk 5 is forbidden to touch**
   (plan §11 `:1745-1748`).
4. **Worst case, the project gets a field nothing reads.** §5 found no requirement
   and §6 found no consumer. The likely outcome of (B) is a persisted column whose
   only reader is the test that asserts it exists.

### If the project picks (A) — the pairing — while §3.2 is wrong

1. **A later reader conflates the two states.** If any future code path can write
   `product_detail_status = "success"` **and** `state = NULL` for a *failed*
   operation (or `"error"` for a *retained* one), the reader's rule in §3.2 inverts
   and audit queries silently mis-classify. This is the real risk, and it is
   **bounded and testable**: the invariant is one assertion per case (table §3.2),
   and Chunk 5's existing test surface already has the nodes
   (`test_state_excluded_and_unknown_assets_remain_recorded`,
   `test_failed_operation_fields_are_none_never_zero`,
   `test_partial_success_retains_valid_operation_fields` — plan §9
   `:1479-1483`). Rows 5–8 are already covered; rows 3–4 are what the companion
   ruling's fix makes assertable.
2. **Chunk 7A could be misled.** If §6's claim were wrong and a metric formula did
   need absent-vs-null, Chunk 7A would be consuming a distinction that lives only in
   a human-readable summary string. Mitigation: the summary is a persisted column, so
   the information is not *lost* — it is stored in a field whose primary purpose is
   audit. §8 states this residual honestly.
3. **The far cheaper failure to detect.** If (A) is wrong, the correction is a
   follow-up chunk-02 change made with §3.2's evidence already written down. If (B)
   is wrong, the correction is a schema rollback on a file the project forbids silent
   migration on. (A)'s blast radius is strictly smaller.

---

## 8. Unverified, and the residual loss under (A)

Labeled per the project's counting and verification rules.

- **No code was executed.** I ran no `pytest`, no `python -m
  niche_scout.tools.validate_traceability`, no `python -m
  niche_scout.tools.check_import_boundaries`, and no database probe. Every behavioral
  statement above (in particular that `product_detail_status` is `"success"` on the
  fixed cases 3–4, and that `error_summary` is `None` on rows 1–2) is **derived by
  reading** the cited code paths, not observed. The *schema* facts (`state TEXT`
  nullable, `product_detail_status TEXT NOT NULL`, `product_detail_error_summary
  TEXT` nullable, the `_ENUM_COLUMNS` allow-list) are **quoted** from
  `database.py:149-173` and `:410-412` — those are read, not inferred.
- **Whether a `CHECK` constraint exists in the physical SQLite file is unverified by
  query.** `database.py`'s DDL declares no `CHECK` on `state` (quoted above), and
  `chunk-02.md:50-51` says no code path fabricates a value. I did not open a
  database file to confirm the deployed schema. (Note the parent's DDL *did* carry
  `state_exclusion_reason … CHECK (…)` at parent `:404`, which is a *different*
  column in a *different* table.)
- **`tests/test_collector.py` and `tests/fixtures/graphql_fixtures.py` were not
  opened for this ruling.** The node IDs in §7 come from the plan's §9 rows
  (`:1479-1483`), **not** from reading the test file. Treat any claim about those
  files' current contents as **unverified**; the plan is a document, not the artifact.
- **`Documents/interfaces/chunk-00.md` was read only in part.** I opened its
  `EnrichmentObservationRecord` field list (`:199-205`), its distinctness rule
  (`:41-43`), and its status/enum notes (`:75-79`, `:214-215`). I did **not** open it
  in full; any claim about `chunk-00.md` beyond those ranges is **unverified**.
- **`Documents/interfaces/chunk-03.md` exists and I did not open it.** Counted by
  directory listing: `Documents/interfaces/` contains exactly four files —
  `chunk-00.md`, `chunk-01.md`, `chunk-02.md`, `chunk-03.md`. Unit: **distinct file
  names**, from a directory listing, not a text search. This **contradicts**
  `Documents/plans/chunk-05-…md:140-146`, which asserts "no
  `Documents/interfaces/chunk-03.md` exists yet, so Chunk 5 consumes none of it".
  The plan predates the file's creation, so this is a stale plan statement, **not** a
  defect in this ruling's reasoning and not a defect I was asked to resolve. I did
  not open `chunk-03.md`, so I make no claim about its contents; it is Coveo-side
  and bears on no part of this ruling.
- **The counting statements in §5** are of the form "this grep returned N rows", with
  the query quoted. They are **occurrence counts over a document**, not distinct
  identifiers, and not counts over code. The `annotation`/`annotate` zero-result
  claim is a **0-row grep result on `SRS-lean.md` only** — exhaustive for that file,
  not for the repo.
- **Residual loss under (A), stated plainly because it is a real limitation.** The
  absent-vs-null granularity required by companion ruling §7 case (b) lives in
  `product_detail_error_summary`, which is a **redacted, human-readable summary
  string**, not a typed enum column. A consumer that must *machine-discriminate*
  absent from null would have to parse that string or match an issue code; there is
  no typed field for it anywhere in the frozen record. I judge that acceptable,
  because §5 found no requirement and §6 found no consumer — but if a future
  requirement needs a *typed, queryable* absent/null discriminant, **that** is the
  requirement that would justify option (B), and it would need to arrive as an SRS
  change to §6.4 first, not as a Chunk 5 convenience.
- **The `chunk-03.md` contradiction above is a document-state fact I observed but did
  not investigate.** It is reported, not resolved, and it affects no part of the
  ruling's reasoning.

---

## 9. A recommended sentence for a future SRS revision

**This is a recommendation, not a new requirement, and it creates no obligation.**
It is offered so the question cannot reopen, and it is written to be additive to
`SRS-lean.md` §6.4 (`:583`), where the only existing nullability sentence lives.

> `state` SHALL be nullable. A null `state` SHALL be interpreted together with
> `product_detail_status`: when `product_detail_status` is `success`, a null `state`
> means the asset's marketplace state is unknown or was not returned, and the asset
> remains in persisted observations and discovered breadth; when
> `product_detail_status` is `error`, a null `state` means no state was retrieved.
> `state` SHALL NOT be populated with a placeholder, sentinel, or default value, and
> no separate state-annotation column is required.

Two properties worth noting about this wording, both deliberate: it makes the
**pair** the contract rather than either column alone (which is §3.2's finding), and
it forecloses the sentinel-string path by name (which is §3.4's rejection).
Recommending it is not the same as adopting it; until a human adopts it, this ruling
rests on `SRS-lean.md:575-581`, `:329-330`, `:318-323`, `:76-77`, and the map's
`:173`/`:652`, and I say so rather than presenting a fabricated requirement as SRS
text.

---

## 10. Summary

| Question | Answer |
|---|---|
| (A) representable already, or (B) cross-chunk? | **(A)** — representable, Chunk-5-local. |
| Exact field that carries the distinction | The pair `enrichment_observations.product_detail_status` (`database.py:153`; `models.py:428`; `collector_graphql.py:1591`) + `state` (`database.py:163`; `models.py:438`; `collector_graphql.py:1601`). `"success"` + `NULL` = unknown-but-retained; `"error"` + `NULL` = failed. Proven per case in §3.2. |
| Required change inside Chunk 5 | On successful absent/null state, set `product_detail_status = "success"` **and** carry the absent-vs-null marker in `product_detail_error_summary` via a distinct `state`-scoped issue code or `context` member (§3.3). Files: `collector_graphql.py` (draft/classification), `tests/test_collector.py`, `tests/fixtures/graphql_fixtures.py` — all already in Chunk 5's §6 scope. |
| Files that must **not** change | `models.py`, `database.py`, `Documents/interfaces/chunk-02.md`, `SRS-lean.md` §6.4, `SCHEMA_VERSION`. |
| Does a requirement mandate the distinction? | **No.** No LREQ mandates it; the distinction is **desirable, not required** (§5). The nearest texts (`LREQ-GQL-040` `:318-323`, `LREQ-NFR-030` `:1168-1169`, `LREQ-GQL-060` `:329-330`, map `:173`) each require one *side* to be visible, never that the two be distinguishable from each other. |
| Architecture-rule status | Not a violation of "never fabricate zeros" (the fix writes a first-class `NULL`); it *would* be a violation to write a `"unknown"` sentinel. The distinguishability concern is discharged by the pair, so §3.2 leaves no collapsed cell (§6). |
| Whether this ruling unblocks Chunk 5 | **Partially.** It closes the persistence half of companion ruling Q-1 (case (a)/(b) need no schema change). Companion ruling **Q-2 is untouched and remains open** — the plan's §8 E7 vs §5.8/E10 contradiction is a human decision, and the plan must stay `DRAFT` until it is answered. |
| Frozen interfaces touched | **None.** `chunk-01.md` (`:133-139`, `:204`, `:279-281`) already froze `StateEligibilityAnnotation`, `annotate_state_eligibility`, and the "annotation, not a decision" semantics; this ruling consumes them unchanged. |
