"""Deterministic, canonical sampling engine for one run and category.

This module implements SRS-lean §5.1 (``LREQ-SMP-010`` … ``LREQ-SMP-090``): it
builds the ordered canonical population from already-persisted discovery
observations, applies census behaviour at ``N <= 100`` and four contiguous
ordinal strata above that, and selects within each stratum by a SHA-256 digest
over ``sampling_rule_version + NUL + category + NUL + asset_identity_key``.

The module is pure. It performs no I/O, opens no database, reads no clock, and
uses no random or platform-dependent hash. It imports no collector, database,
pipeline, report, CLI, config, metrics, or scoring module. Missing, zero, and
unavailable stay distinct: an empty category yields ``sample_fraction is None``,
never ``0.0``. Nothing here persists a row or claims physical materialization.

Plan: ``Documents/plans/chunk-4A-canonical-populations-and-deterministic-sampling.md``
§5 (interface contract) and §11 (prohibitions).
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from niche_scout.models import (
    ENRICHMENT_SAMPLE_SIZE_PER_CATEGORY,
    SAMPLE_PER_STRATUM,
    SAMPLE_STRATA,
    SAMPLING_RULE_VERSION,
    SamplingBasis,
)

__all__ = [
    "CENSUS_POPULATION_THRESHOLD",
    "NUL_DELIMITER",
    "CanonicalPopulation",
    "CategoryOverlap",
    "CategorySamplingResult",
    "DiscoveryPopulationRecord",
    "RunOverlapResult",
    "RunSamplingResult",
    "SampledMember",
    "SamplingStratum",
    "build_canonical_population",
    "build_strata",
    "compute_overlap",
    "select_category_sample",
    "select_run_sample",
    "select_stratum_members",
    "selection_digest",
]

# --------------------------------------------------------------------------
# Constants and vocabularies (LREQ-SMP-030)
# --------------------------------------------------------------------------
# Re-exported from ``models`` for downstream convenience; the values are never
# re-declared and are never exposed as independently configurable parameters.

#: NUL delimiter joining the three digest inputs (LREQ-SMP-060).
NUL_DELIMITER: str = "\x00"

#: Census boundary derived from the frozen sample size, so the two can never
#: drift apart (LREQ-SMP-030/040).
CENSUS_POPULATION_THRESHOLD: int = ENRICHMENT_SAMPLE_SIZE_PER_CATEGORY


# --------------------------------------------------------------------------
# Typed input structure (plan §5.2)
# --------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class DiscoveryPopulationRecord:
    """One persisted raw discovery observation, projected for sampling.

    ``discovery_ordinal`` is the stable 0-based ordinal assigned during
    collection by Chunk 3. ``asset_identity_key`` is non-``None`` only for a
    ``resolved`` identity (LREQ-EXT-060/EXT-070). ``is_duplicate`` is ``True``
    for a repeated canonical record whose first occurrence carries the retained
    ordinal (LREQ-SMP-020).

    Null/edge contract: a ``None`` identity key is excluded and counted as
    unresolved; a ``True`` duplicate is excluded and counted as duplicate even
    when its key is non-``None``; a repeated identity without the flag collapses
    to the lowest retained ordinal.
    """

    discovery_ordinal: int
    asset_identity_key: str | None
    is_duplicate: bool = False


# --------------------------------------------------------------------------
# Typed result structures (plan §5.3)
# --------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class CanonicalPopulation:
    """The ordered canonical population for one ``(run_id, category)``.

    The ordering is LREQ-SMP-020's: ascending retained discovery ordinal, ties
    broken by ``(ordinal, asset_identity_key)``. ``identity_keys`` and
    ``retained_ordinals`` are positionally aligned; position ``i`` has the
    1-based population ordinal ``i + 1``, the ordinal space LREQ-SMP-050's
    stratum boundaries are expressed in.
    """

    category: str
    identity_keys: tuple[str, ...]
    retained_ordinals: tuple[int, ...]
    excluded_unresolved_count: int
    excluded_duplicate_count: int
    collapsed_repeat_count: int

    @property
    def size(self) -> int:
        """Canonical population size (``len(identity_keys)``); never fabricated."""
        return len(self.identity_keys)


@dataclass(frozen=True, slots=True)
class SamplingStratum:
    """One ordinal stratum.

    ``stratum_index`` is 0-based. ``start_ordinal``/``end_ordinal`` are 1-based
    inclusive positions in the canonical population (LREQ-SMP-050:
    ``floor(h*N/4)+1 .. floor((h+1)*N/4)``; census: ``1..N``). A stratum is always
    non-empty: ``end_ordinal >= start_ordinal``.

    ``is_reduced`` is ``True`` exactly when ``population_count`` is below
    ``SAMPLE_PER_STRATUM`` (LREQ-SMP-090); ``selected_count`` never exceeds
    ``population_count``.
    """

    stratum_index: int
    start_ordinal: int
    end_ordinal: int
    population_count: int
    selected_count: int
    target_count: int
    is_reduced: bool


@dataclass(frozen=True, slots=True)
class SampledMember:
    """One selected sample member, 1:1 with a future ``sample_members`` row."""

    category: str
    asset_identity_key: str
    stratum_index: int
    stratum_start_ordinal: int
    stratum_end_ordinal: int
    sample_rank_within_stratum: int
    sample_is_census: bool
    selection_digest: str


@dataclass(frozen=True, slots=True)
class CategorySamplingResult:
    """The complete pure sampling outcome for one category.

    ``sample_fraction`` is ``None`` iff ``discovered_population_count == 0``; it
    is ``1.0`` for a non-empty census and ``enriched_sample_count /
    discovered_population_count`` otherwise. ``members`` holds no duplicate
    identity and ``strata`` is empty exactly when the population is empty.
    """

    category: str
    population: CanonicalPopulation
    strata: tuple[SamplingStratum, ...]
    members: tuple[SampledMember, ...]
    sampling_basis: SamplingBasis
    sample_is_census: bool
    discovered_population_count: int
    enriched_sample_count: int
    sample_fraction: float | None
    sampling_rule_version: str


@dataclass(frozen=True, slots=True)
class RunSamplingResult:
    """All category sampling results for one run, in caller-declared order.

    ``categories`` preserves the input mapping's insertion order and ``run_id``
    is echoed only for correlation; nothing is persisted here.
    """

    run_id: str
    sampling_rule_version: str
    categories: tuple[CategorySamplingResult, ...]

    @property
    def by_category(self) -> Mapping[str, CategorySamplingResult]:
        """Map each category to its result in caller-declared order."""
        return {result.category: result for result in self.categories}

    @property
    def enrichment_identity_keys(self) -> tuple[str, ...]:
        """Distinct selected identities across all categories, first-seen order.

        This is the union Chunk 6B enriches once. It is a convenience view and
        carries no overlap counts or percentages.
        """
        seen: set[str] = set()
        ordered: list[str] = []
        for result in self.categories:
            for member in result.members:
                if member.asset_identity_key not in seen:
                    seen.add(member.asset_identity_key)
                    ordered.append(member.asset_identity_key)
        return tuple(ordered)


# --------------------------------------------------------------------------
# Validation helpers (plan §5.2 / §5.4)
# --------------------------------------------------------------------------


def _require_nonempty_category(category: str) -> None:
    """Raise ``ValueError`` for a non-string or empty/whitespace-only category."""
    if not isinstance(category, str) or not category.strip():
        raise ValueError("category must be a non-empty, non-whitespace string")


def _validate_record(record: DiscoveryPopulationRecord) -> None:
    """Raise ``ValueError`` for a malformed ordinal or identity key (plan §5.2)."""
    ordinal = record.discovery_ordinal
    if isinstance(ordinal, bool) or not isinstance(ordinal, int):
        raise ValueError(f"discovery_ordinal must be an int, got {ordinal!r}")
    if ordinal < 0:
        raise ValueError(f"discovery_ordinal must be non-negative, got {ordinal!r}")
    key = record.asset_identity_key
    if key is not None and (not isinstance(key, str) or not key.strip()):
        raise ValueError(
            "asset_identity_key must be None or a non-empty, non-whitespace string"
        )


def _record_sort_key(record: DiscoveryPopulationRecord) -> tuple[int, bool, str]:
    """Total order over records: ordinal, then identity key, nulls last."""
    key = record.asset_identity_key
    return (record.discovery_ordinal, key is None, key if key is not None else "")


def _project_records(
    records: Sequence[DiscoveryPopulationRecord | Mapping[str, object]],
) -> tuple[DiscoveryPopulationRecord, ...]:
    """Coerce a sequence of records or inert mappings to typed records.

    ``select_run_sample`` accepts caller-supplied per-category sequences that
    may be raw observation projections; this keeps the digest/selection path
    typed without a caller-side conversion. A ``DiscoveryPopulationRecord`` is
    passed through unchanged.
    """
    projected: list[DiscoveryPopulationRecord] = []
    for record in records:
        if isinstance(record, DiscoveryPopulationRecord):
            projected.append(record)
        elif isinstance(record, Mapping):
            projected.append(DiscoveryPopulationRecord(**record))
        else:
            raise ValueError(
                "each record must be a DiscoveryPopulationRecord or a mapping"
            )
    return tuple(projected)


# --------------------------------------------------------------------------
# Digest (LREQ-SMP-060)
# --------------------------------------------------------------------------


def selection_digest(
    category: str,
    asset_identity_key: str,
    *,
    sampling_rule_version: str = SAMPLING_RULE_VERSION,
) -> str:
    """Return the lowercase hex SHA-256 selection digest (LREQ-SMP-060).

    The hashed bytes are the UTF-8 encoding of
    ``sampling_rule_version + NUL + category + NUL + asset_identity_key``. The
    function is pure and uses no platform-dependent hash.

    Raises ``ValueError`` when ``category`` is empty or whitespace-only; an empty
    category is never a silently shared digest bucket.
    """
    _require_nonempty_category(category)
    payload = NUL_DELIMITER.join((sampling_rule_version, category, asset_identity_key))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


# --------------------------------------------------------------------------
# Canonical population (LREQ-SMP-010/020)
# --------------------------------------------------------------------------


def build_canonical_population(
    records: Sequence[DiscoveryPopulationRecord],
    *,
    category: str,
) -> CanonicalPopulation:
    """Order and deduplicate canonical identities (LREQ-SMP-010/020).

    Retains the lowest discovery ordinal per identity. ``records`` need not be
    sorted; the output is ordered by ``(retained_ordinal, asset_identity_key)``.
    A record with a ``None`` key is excluded and counted unresolved (conflict and
    unresolved both persist a null key); a record flagged ``is_duplicate`` is
    excluded and counted a duplicate even when keyed; a repeated identity whose
    first valid ordinal was already retained is counted as a collapsed repeat.

    An empty ``records`` yields an empty population with all counts ``0``.
    Raises ``ValueError`` for a malformed record: a negative, boolean, or non-int
    ordinal, or an empty/whitespace-only identity key.
    """
    _require_nonempty_category(category)
    ordered_records = list(records)
    for record in ordered_records:
        _validate_record(record)
    ordered_records.sort(key=_record_sort_key)

    seen: dict[str, int] = {}
    identity_keys: list[str] = []
    retained_ordinals: list[int] = []
    excluded_unresolved_count = 0
    excluded_duplicate_count = 0
    collapsed_repeat_count = 0

    for record in ordered_records:
        key = record.asset_identity_key
        if key is None:
            excluded_unresolved_count += 1
        elif record.is_duplicate:
            excluded_duplicate_count += 1
        elif key in seen:
            collapsed_repeat_count += 1
        else:
            seen[key] = record.discovery_ordinal
            identity_keys.append(key)
            retained_ordinals.append(record.discovery_ordinal)

    return CanonicalPopulation(
        category=category,
        identity_keys=tuple(identity_keys),
        retained_ordinals=tuple(retained_ordinals),
        excluded_unresolved_count=excluded_unresolved_count,
        excluded_duplicate_count=excluded_duplicate_count,
        collapsed_repeat_count=collapsed_repeat_count,
    )


# --------------------------------------------------------------------------
# Strata (LREQ-SMP-040/050/090)
# --------------------------------------------------------------------------


def build_strata(
    population: CanonicalPopulation,
    *,
    sample_strata: int = SAMPLE_STRATA,
    per_stratum_target: int = SAMPLE_PER_STRATUM,
    census_threshold: int = CENSUS_POPULATION_THRESHOLD,
) -> tuple[SamplingStratum, ...]:
    """Return the ordinal strata for a population (LREQ-SMP-040/050/090).

    Census (``size <= census_threshold``): one stratum over ordinals ``1..N``
    whose target is the full population, because every canonical asset is
    selected (LREQ-SMP-040 `fully enriched`). Large: ``sample_strata`` contiguous
    strata with ``start = floor(h*N/sample_strata)+1`` and
    ``end = floor((h+1)*N/sample_strata)``; the final stratum receives any
    remainder. An empty population yields ``()``.

    ``is_reduced`` is ``True`` exactly when a stratum holds fewer than
    ``SAMPLE_PER_STRATUM`` assets (LREQ-SMP-090). Raises ``ValueError`` when
    ``sample_strata < 1`` or ``per_stratum_target < 1``; production callers use
    the frozen defaults and never pass these parameters (LREQ-SMP-030).
    """
    if sample_strata < 1:
        raise ValueError("sample_strata must be >= 1")
    if per_stratum_target < 1:
        raise ValueError("per_stratum_target must be >= 1")

    size = population.size
    if size == 0:
        return ()

    if size <= census_threshold:
        return (
            SamplingStratum(
                stratum_index=0,
                start_ordinal=1,
                end_ordinal=size,
                population_count=size,
                selected_count=size,
                target_count=size,
                is_reduced=size < per_stratum_target,
            ),
        )

    strata: list[SamplingStratum] = []
    for stratum_index in range(sample_strata):
        start_ordinal = (stratum_index * size) // sample_strata + 1
        end_ordinal = ((stratum_index + 1) * size) // sample_strata
        population_count = end_ordinal - start_ordinal + 1
        strata.append(
            SamplingStratum(
                stratum_index=stratum_index,
                start_ordinal=start_ordinal,
                end_ordinal=end_ordinal,
                population_count=population_count,
                selected_count=min(per_stratum_target, population_count),
                target_count=per_stratum_target,
                is_reduced=population_count < per_stratum_target,
            )
        )
    return tuple(strata)


# --------------------------------------------------------------------------
# Selection (LREQ-SMP-060/090)
# --------------------------------------------------------------------------


def select_stratum_members(
    population: CanonicalPopulation,
    stratum: SamplingStratum,
    *,
    sample_is_census: bool,
    sampling_rule_version: str = SAMPLING_RULE_VERSION,
) -> tuple[SampledMember, ...]:
    """Select up to ``stratum.target_count`` members from ``stratum``.

    Candidates are the population identities at 1-based ordinals
    ``start_ordinal..end_ordinal``. Each is digested by :func:`selection_digest`;
    candidates are sorted by ``(digest, asset_identity_key)`` and the first
    ``min(target_count, population_count)`` are selected, ranked 1-based in that
    order (LREQ-SMP-060, LREQ-SMP-090). For a census population the target is the
    full stratum, so every canonical asset is selected (LREQ-SMP-040).

    Deterministic; no RNG and no clock. An empty stratum returns ``()``. The
    returned members carry ``sample_is_census`` unchanged and never exceed
    ``stratum.target_count``.
    """
    start_index = stratum.start_ordinal - 1
    candidates = population.identity_keys[start_index : stratum.end_ordinal]
    ranked = [
        (
            selection_digest(
                population.category,
                key,
                sampling_rule_version=sampling_rule_version,
            ),
            key,
        )
        for key in candidates
    ]
    ranked.sort(key=lambda item: (item[0], item[1]))
    limit = min(stratum.target_count, len(ranked))

    return tuple(
        SampledMember(
            category=population.category,
            asset_identity_key=key,
            stratum_index=stratum.stratum_index,
            stratum_start_ordinal=stratum.start_ordinal,
            stratum_end_ordinal=stratum.end_ordinal,
            sample_rank_within_stratum=rank,
            sample_is_census=sample_is_census,
            selection_digest=digest,
        )
        for rank, (digest, key) in enumerate(ranked[:limit], start=1)
    )


# --------------------------------------------------------------------------
# Category and run pipelines (LREQ-SMP-030/040/050/070/080)
# --------------------------------------------------------------------------


def select_category_sample(
    records: Sequence[DiscoveryPopulationRecord],
    *,
    category: str,
    run_id: str | None = None,
    sampling_rule_version: str = SAMPLING_RULE_VERSION,
) -> CategorySamplingResult:
    """Full sampling pipeline for one category (LREQ-SMP-010 … SMP-070, SMP-090).

    Builds the canonical population, decides census versus four-stratum, selects
    members, and computes ``sampling_basis``, ``sample_is_census``,
    ``discovered_population_count``, ``enriched_sample_count``, and
    ``sample_fraction``. ``run_id`` is accepted for correlation only and is not
    echoed into the category result.

    Empty input yields ``discovered_population_count == 0`` with
    ``sample_fraction is None`` (never ``0.0``), a census flag of ``True``, an
    empty stratum tuple, and no members. Pure: no usable counts, no overlap
    fields, and no warnings are emitted. Raises ``ValueError`` when ``category``
    is empty or whitespace-only.
    """
    _require_nonempty_category(category)
    del run_id  # correlation only; the category result carries no run id.
    population = build_canonical_population(records, category=category)
    discovered_population_count = population.size
    sample_is_census = discovered_population_count <= CENSUS_POPULATION_THRESHOLD
    strata = build_strata(population)

    members: list[SampledMember] = []
    for stratum in strata:
        members.extend(
            select_stratum_members(
                population,
                stratum,
                sample_is_census=sample_is_census,
                sampling_rule_version=sampling_rule_version,
            )
        )

    enriched_sample_count = len(members)
    sample_fraction: float | None
    if discovered_population_count == 0:
        sample_fraction = None
    else:
        sample_fraction = enriched_sample_count / discovered_population_count

    return CategorySamplingResult(
        category=category,
        population=population,
        strata=strata,
        members=tuple(members),
        sampling_basis=(
            SamplingBasis.CENSUS
            if sample_is_census
            else SamplingBasis.DETERMINISTIC_STRATIFIED_SAMPLE
        ),
        sample_is_census=sample_is_census,
        discovered_population_count=discovered_population_count,
        enriched_sample_count=enriched_sample_count,
        sample_fraction=sample_fraction,
        sampling_rule_version=sampling_rule_version,
    )


def select_run_sample(
    categories: Mapping[
        str, Sequence[DiscoveryPopulationRecord | Mapping[str, object]]
    ],
    *,
    run_id: str,
    sampling_rule_version: str = SAMPLING_RULE_VERSION,
) -> RunSamplingResult:
    """Run-wide sampling over already-declared categories, preserving input order.

    Each category is sampled independently with :func:`select_category_sample`.
    ``run_id`` is echoed only for correlation; no persistence occurs. Categories
    are emitted in the caller mapping's insertion order and are never sorted (the
    caller decides the declared order). An empty mapping yields
    ``categories == ()``; the same ``run_id`` is not required to exist.
    """
    return RunSamplingResult(
        run_id=run_id,
        sampling_rule_version=sampling_rule_version,
        categories=tuple(
            select_category_sample(
                _project_records(records),
                category=category,
                run_id=run_id,
                sampling_rule_version=sampling_rule_version,
            )
            for category, records in categories.items()
        ),
    )


# --------------------------------------------------------------------------
# Cross-category overlap (LREQ-SMP-080, SRS §6.5)
# --------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class CategoryOverlap:
    """Overlap of one category's sample with all other categories' samples.

    Per SRS §6.5. ``overlap_category_count`` counts OTHER categories sharing at
    least one sampled canonical identity; ``overlap_sample_percentage`` is
    ``100 * (<this category's sampled identities that appear in at least one
    other category>) / enriched_sample_count``. It is ``None`` iff
    ``enriched_sample_count == 0``; a non-empty sample with no shared identity is
    ``0.0`` (a measured zero), never ``None``. The value is stored unrounded.
    """

    category: str
    overlap_category_count: int
    overlap_sample_percentage: float | None


@dataclass(frozen=True, slots=True)
class RunOverlapResult:
    """Overlap for every category, in the ``RunSamplingResult`` category order."""

    run_id: str
    categories: tuple[CategoryOverlap, ...]

    @property
    def by_category(self) -> Mapping[str, CategoryOverlap]:
        """Map each category to its overlap in ``RunSamplingResult`` order."""
        return {entry.category: entry for entry in self.categories}


def compute_overlap(run: RunSamplingResult) -> RunOverlapResult:
    """Per-category cross-category overlap (SRS §6.5).

    Input is the completed ``RunSamplingResult``; overlap is computed from unique
    canonical identities after all samples are selected. A category's members
    are already identity-unique (4A), so a shared identity is counted once per
    category regardless of how many categories contain it. Category order is
    preserved; an empty run yields ``categories == ()``. Pure: no RNG, no clock,
    no I/O, no mutation. ``overlap_sample_percentage`` is unrounded ``float64``
    (Q-7): rounding is a display concern only.

    ``overlap_category_count`` is the number of OTHER categories whose sample
    contains at least one identity in this category's sample. The percentage
    numerator counts this category's sampled identities that appear in at least
    one other category; the denominator is this category's
    ``enriched_sample_count``. A zero-member category yields count ``0`` and
    percentage ``None`` (never ``0.0``); a non-empty category with no shared
    identity yields a measured ``0.0``. This function never increases an
    enrichment or preflight count; the input is not modified.
    """
    identities_by_category: dict[str, frozenset[str]] = {}
    for result in run.categories:
        identities_by_category[result.category] = frozenset(
            member.asset_identity_key for member in result.members
        )

    categories: list[CategoryOverlap] = []
    for result in run.categories:
        own_identities = identities_by_category[result.category]
        shared_identities: set[str] = set()
        overlap_category_count = 0
        for other in run.categories:
            if other.category == result.category:
                continue
            shared = own_identities & identities_by_category[other.category]
            if shared:
                overlap_category_count += 1
                shared_identities.update(shared)

        if result.enriched_sample_count == 0:
            percentage: float | None = None
        else:
            percentage = 100.0 * len(shared_identities) / result.enriched_sample_count

        categories.append(
            CategoryOverlap(
                category=result.category,
                overlap_category_count=overlap_category_count,
                overlap_sample_percentage=percentage,
            )
        )

    return RunOverlapResult(run_id=run.run_id, categories=tuple(categories))
