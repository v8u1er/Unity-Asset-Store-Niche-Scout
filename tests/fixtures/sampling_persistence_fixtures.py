"""Inert fixtures and hand-derived vectors for chunk 4B sampling persistence.

Data and factory functions only: this module contains no assertions and no
logic under test, so a defect in it cannot mask a persistence or overlap defect.

Sources:
- ``Documents/SRS-lean.md`` §6.5 (per-category overlap; stratum summary).
- ``Documents/plans/chunk-4B-sample-persistence-overlap-and-sampling-summaries.md``
  §5 (interface contract), §9.2 (fixtures O1-O10).

No credentials, no network, no clock reads, no file I/O, no ``sqlite3``.
Datetimes are fixed aware-UTC literals, never ``now()``.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone

from niche_scout.models import (
    DiscoveryStatus,
    RunRecord,
    SamplingBasis,
)

# --------------------------------------------------------------------------
# SRS-pinned constants (SRS §5.1, LREQ-SMP-030). Mirrored as literals only to
# size fixtures; the persistence tests compare against ``models`` for the live
# values where the live value matters.
# --------------------------------------------------------------------------

SAMPLE_STRATA = 4
SAMPLE_PER_STRATUM = 25
CENSUS_POPULATION_THRESHOLD = 100
SAMPLING_RULE_VERSION = "1.0.0"

# --------------------------------------------------------------------------
# Category names and identity keys used by every overlap fixture.
# --------------------------------------------------------------------------

CATEGORY_A = "Overlap/A"
CATEGORY_B = "Overlap/B"
CATEGORY_C = "Overlap/C"

SHARED_IDENTITY_KEY = "s1"
A_ONLY_1 = "a1"
A_ONLY_2 = "a2"
B_ONLY_1 = "b1"
B_ONLY_2 = "b2"
C_ONLY_1 = "c1"

#: Fixture O6 categories.
CENSUS_CATEGORY = "Census/Cat"
LARGE_CATEGORY = "Large/Cat"
ZERO_CATEGORY = "Empty/Cat"

#: Fixture O6 census population size (census: ``N <= 100``).
CENSUS_N = 3
#: Fixture O6 large population size (four strata).
LARGE_N = 101

#: Fixed aware-UTC timestamps. No clock is ever read (LREQ-ARCH-020).
RUN_STARTED_AT_UTC = datetime(2025, 1, 2, 3, 4, 5, tzinfo=timezone.utc)
SCORING_CUTOFF_UTC = datetime(2025, 3, 4, 5, 6, 7, tzinfo=timezone.utc)
TAXONOMY_CAPTURED_AT_UTC = datetime(2025, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
COMPUTED_AT_UTC = datetime(2025, 6, 7, 8, 9, 10, tzinfo=timezone.utc)

#: A digest-bearing category whose members are three identities.
DIGEST_VECTOR_CATEGORY = CATEGORY_A


# --------------------------------------------------------------------------
# Inert observation factories. The keys are the same shape chunk 4A consumes
# (``DiscoveryPopulationRecord`` fields), so the persistence tests can build a
# pure ``RunSamplingResult`` through the live 4A engine.
# --------------------------------------------------------------------------


def observation(discovery_ordinal: int, asset_identity_key: str) -> dict:
    """Return one inert 4A population-record mapping (no duplicates)."""
    return {
        "discovery_ordinal": discovery_ordinal,
        "asset_identity_key": asset_identity_key,
        "is_duplicate": False,
    }


def records_for(keys: tuple[str, ...], *, first_ordinal: int = 0) -> tuple[dict, ...]:
    """Return ``keys`` as ascending-ordinal 4A records (one canonical each)."""
    return tuple(
        observation(first_ordinal + index, key) for index, key in enumerate(keys)
    )


def sequential_keys(prefix: str, n: int, *, width: int = 4) -> tuple[str, ...]:
    """Return ``n`` distinct identity keys ``f"{prefix}-{i:0{width}d}"``."""
    return tuple(f"{prefix}-{index:0{width}d}" for index in range(n))


# --------------------------------------------------------------------------
# Fixtures O1-O5: overlap populations and behaviorally derived expectations.
#
# The expectation tables below are derived from the SRS §6.5 definition:
#   overlap_category_count      = |{other categories sharing >= 1 identity}|
#   overlap_sample_percentage   = 100 * (this category's sampled identities that
#                                 appear in >= 1 other category) / sample size
# and are stated per category as (category, count, percentage).
# --------------------------------------------------------------------------

#: O1 - shared ``s1``; every category has 3 members.
O1_CATEGORY_A_KEYS: tuple[str, ...] = (A_ONLY_1, A_ONLY_2, SHARED_IDENTITY_KEY)
O1_CATEGORY_B_KEYS: tuple[str, ...] = (B_ONLY_1, B_ONLY_2, SHARED_IDENTITY_KEY)
#: Shared count 1 of 3 sampled -> exactly 100 * 1 / 3, stored unrounded.
O1_SHARED_COUNT = 1
O1_SAMPLE_SIZE = 3
O1_EXPECTED_PERCENTAGE = 100.0 * O1_SHARED_COUNT / O1_SAMPLE_SIZE


def o1_categories() -> dict[str, tuple[dict, ...]]:
    """Fixture O1 input: two 3-member categories sharing one identity."""
    return {
        CATEGORY_A: records_for(O1_CATEGORY_A_KEYS),
        CATEGORY_B: records_for(O1_CATEGORY_B_KEYS),
    }


def o1_expected() -> dict[str, tuple[int, float]]:
    """Fixture O1 expected per category: count 1, percentage ``100 * 1/3``."""
    return {
        CATEGORY_A: (1, O1_EXPECTED_PERCENTAGE),
        CATEGORY_B: (1, O1_EXPECTED_PERCENTAGE),
    }


def o2_categories() -> dict[str, tuple[dict, ...]]:
    """Fixture O2 input: two disjoint 2-member categories."""
    return {
        CATEGORY_A: records_for((A_ONLY_1, A_ONLY_2)),
        CATEGORY_B: records_for((B_ONLY_1, B_ONLY_2)),
    }


def o2_expected() -> dict[str, tuple[int, float]]:
    """Fixture O2 expected: measured zero overlap for both categories."""
    return {
        CATEGORY_A: (0, 0.0),
        CATEGORY_B: (0, 0.0),
    }


def o3_categories() -> dict[str, tuple[dict, ...]]:
    """Fixture O3 input: one non-empty category only."""
    return {CATEGORY_A: records_for((A_ONLY_1, A_ONLY_2))}


def o3_expected() -> dict[str, tuple[int, float]]:
    """Fixture O3 expected: no other category -> measured zero."""
    return {CATEGORY_A: (0, 0.0)}


def o4_categories() -> dict[str, tuple[dict, ...]]:
    """Fixture O4 input: one non-empty category plus one empty category."""
    return {
        CATEGORY_A: records_for((A_ONLY_1, A_ONLY_2)),
        ZERO_CATEGORY: (),
    }


def o4_expected() -> dict[str, tuple[int, float | None]]:
    """Fixture O4 expected: empty category is ``None``, never ``0.0``."""
    return {
        CATEGORY_A: (0, 0.0),
        ZERO_CATEGORY: (0, None),
    }


#: O5 - one identity shared by three 1-member categories.
O5_CATEGORY_A_KEYS: tuple[str, ...] = (SHARED_IDENTITY_KEY,)
O5_CATEGORY_B_KEYS: tuple[str, ...] = (SHARED_IDENTITY_KEY,)
O5_CATEGORY_C_KEYS: tuple[str, ...] = (SHARED_IDENTITY_KEY,)
O5_EXPECTED_PERCENTAGE = 100.0


def o5_categories() -> dict[str, tuple[dict, ...]]:
    """Fixture O5 input: ``s1`` in A, B and C, one member each."""
    return {
        CATEGORY_A: records_for(O5_CATEGORY_A_KEYS),
        CATEGORY_B: records_for(O5_CATEGORY_B_KEYS),
        CATEGORY_C: records_for(O5_CATEGORY_C_KEYS),
    }


def o5_expected() -> dict[str, tuple[int, float]]:
    """Fixture O5 expected: the other two categories count, percentage 100."""
    return {
        CATEGORY_A: (2, O5_EXPECTED_PERCENTAGE),
        CATEGORY_B: (2, O5_EXPECTED_PERCENTAGE),
        CATEGORY_C: (2, O5_EXPECTED_PERCENTAGE),
    }


def o5_union_identity_keys() -> tuple[str, ...]:
    """Fixture O5 union: exactly one distinct identity."""
    return (SHARED_IDENTITY_KEY,)


# --------------------------------------------------------------------------
# Fixture O6: a round-trip run -- one census category and one large category.
# --------------------------------------------------------------------------


def run_record(run_id: str) -> RunRecord:
    """Return the fixed O6 ``RunRecord`` (aware UTC, ``status="running"``)."""
    return RunRecord(
        run_id=run_id,
        run_started_at_utc=RUN_STARTED_AT_UTC,
        scoring_cutoff_utc=SCORING_CUTOFF_UTC,
        completed_at_utc=None,
        categories_json='["Census/Cat","Large/Cat"]',
        config_snapshot_json="{}",
        config_sha256="0" * 64,
        taxonomy_version="2025.1",
        taxonomy_captured_at_utc=TAXONOMY_CAPTURED_AT_UTC,
        taxonomy_sha256="1" * 64,
        endpoint_contract_version="1.0.0",
        identity_mapping_rule_version="1.0.1",
        sampling_rule_version=SAMPLING_RULE_VERSION,
        page_view_semantics_status="unvalidated",
        graphql_operation_correlation_mode="explicit_key",
        identity_preflight_status="passed",
        identity_preflight_summary_json="{}",
        status="running",
    )


def census_category_keys() -> tuple[str, ...]:
    """Fixture O6 census population: ``N == 3``."""
    return sequential_keys("census", CENSUS_N)


def large_category_keys() -> tuple[str, ...]:
    """Fixture O6 large population: ``N == 101`` (four strata)."""
    return sequential_keys("large", LARGE_N)


def o6_categories() -> dict[str, tuple[dict, ...]]:
    """Fixture O6 sampling input, in declared category order."""
    return {
        CENSUS_CATEGORY: records_for(census_category_keys()),
        LARGE_CATEGORY: records_for(large_category_keys()),
    }


def census_report_discovery_status() -> str:
    """Discovery status passed to ``set_category_status`` for the O6 rows."""
    return DiscoveryStatus.COMPLETE.value


def o6_expected_sample_fractions() -> dict[str, float]:
    """Fixture O6 hand-derived sample fractions.

    Census ``N == 3``: every asset is selected, so the SRS §5.1 census rule
    gives exactly ``1.0``.
    Large ``N == 101``: ``SAMPLE_PER_STRATUM == 25`` and the four strata
    (``1..25``, ``26..50``, ``51..75``, ``76..101``) hold 25/25/25/26 assets. The
    last stratum holds 26 but is not reduced (26 >= 25, LREQ-SMP-090) and
    contributes 25, so ``enriched_sample_count == 25 + 25 + 25 + 25 == 100`` and
    the fraction is exactly ``100 / 101``.

    Lead correction 2026-09-20 by human ruling (a): the pre-ruling text said the
    last stratum "is reduced and contributes all 26" and then wrote the total as
    ``25 + 25 + 25 + 26 == 100``, which is arithmetically self-contradictory
    (that sum is 101). The returned values below were already correct.
    """
    return {
        CENSUS_CATEGORY: 1.0,
        LARGE_CATEGORY: 100.0 / 101.0,
    }


def o6_expected_selected_counts() -> dict[str, int]:
    """Fixture O6 expected ``len(members)`` per category."""
    return {CENSUS_CATEGORY: CENSUS_N, LARGE_CATEGORY: 100}


def o6_expected_basis() -> dict[str, str]:
    """Fixture O6 expected ``sampling_basis`` per category."""
    return {
        CENSUS_CATEGORY: SamplingBasis.CENSUS.value,
        LARGE_CATEGORY: SamplingBasis.DETERMINISTIC_STRATIFIED_SAMPLE.value,
    }


# --------------------------------------------------------------------------
# Fixture O7: a zero-population category.
# --------------------------------------------------------------------------


def o7_categories() -> dict[str, tuple[dict, ...]]:
    """Fixture O7 input: one category with no records at all."""
    return {ZERO_CATEGORY: ()}


# --------------------------------------------------------------------------
# Fixture O8: per-stratum ``N_h``/``n_h`` and boundaries at ``N == 101``.
#
# Derived from SRS §5.1 LREQ-SMP-050: ``start = floor(h*N/4) + 1``,
# ``end = floor((h+1)*N/4)``, final stratum takes the boundary remainder.
# LREQ-SMP-090 thresholds the reduced case at "fewer than 25 assets", so the
# 26-asset final stratum is NOT reduced (26 >= SAMPLE_PER_STRATUM) and selects 25
# (LREQ-SMP-050 "select 25 assets from each stratum"):
#   h=0: floor(101/4)=25  -> 1..25   (N_h 25, n_h 25)
#   h=1: floor(202/4)=50  -> 26..50  (N_h 25, n_h 25)
#   h=2: floor(303/4)=75  -> 51..75  (N_h 25, n_h 25)
#   h=3: floor(404/4)=101 -> 76..101 (N_h 26, n_h 25, not reduced)
#
# Lead correction 2026-09-20 by human ruling (a) on the 4B fixture dispute:
# the previous h=3 line read "(N_h 26, n_h 26, reduced)" and the table entry was
# (3, 76, 101, 26, 26). That contradicted LREQ-SMP-050, LREQ-SMP-090's numeric
# threshold, the frozen 4A interface and engine, the 4A tests, and this module's
# own o6_expected_selected_counts() == 100. The 4A engine and 4B persistence are
# correct; only this fixture literal was wrong. No source change.
# --------------------------------------------------------------------------

#: ``(stratum_index, start, end, N_h, n_h)`` for ``N == 101``.
O8_EXPECTED_STRATA_N101: tuple[tuple[int, int, int, int, int], ...] = (
    (0, 1, 25, 25, 25),
    (1, 26, 50, 25, 25),
    (2, 51, 75, 25, 25),
    (3, 76, 101, 26, 25),
)


# --------------------------------------------------------------------------
# Fixture O9: the exact serialized ``stratum_statistics_json`` for a census
# category of size 1. Byte-exact literal per plan §9.2 (keys sorted by
# ``json.dumps(..., sort_keys=True, separators=(",", ":"))``).
# --------------------------------------------------------------------------

CENSUS_ONE_KEYS: tuple[str, ...] = sequential_keys("one", 1)

O9_STRATUM_STATISTICS_JSON: str = (
    '[{"N_h":1,"eligibility_rule":null,"n_h":1,'
    '"stratum_end_ordinal":1,"stratum_index":0,"stratum_start_ordinal":1,'
    '"u_demand_h":null,"u_quality_h":null,"u_recent_h":null,'
    '"usable_status":"pending"}]'
)

#: The frozen ten-key per-stratum object schema, in ``sort_keys`` order.
O9_STRATUM_KEYS: tuple[str, ...] = (
    "N_h",
    "eligibility_rule",
    "n_h",
    "stratum_end_ordinal",
    "stratum_index",
    "stratum_start_ordinal",
    "u_demand_h",
    "u_quality_h",
    "u_recent_h",
    "usable_status",
)

#: The four-token ``usable_status`` vocabulary frozen by chunk 4B (Q-4).
USABLE_STATUS_VOCABULARY: tuple[str, ...] = (
    "pending",
    "usable",
    "unavailable",
    "invalid",
)

#: The token chunk 4B writes while enrichment eligibility is unknown.
PENDING_USABLE_STATUS = "pending"

#: An empty population serializes to an empty JSON array.
EMPTY_STRATUM_STATISTICS_JSON = "[]"


def census_one_categories() -> dict[str, tuple[dict, ...]]:
    """Fixture O9 input: a single-member census category."""
    return {DIGEST_VECTOR_CATEGORY: records_for(CENSUS_ONE_KEYS)}


# --------------------------------------------------------------------------
# Fixture O10: the category-level placeholder vector.
#
# ``set_category_status`` creates the row with the module's pre-scoring
# defaults; chunk 4B must leave these four columns exactly as it found them.
# --------------------------------------------------------------------------

#: ``unique_enrichment_count`` plus the three usable counts (Q-1/Q-1(b)).
O10_PLACEHOLDER_COLUMNS: tuple[str, ...] = (
    "unique_enrichment_count",
    "usable_demand_sample_count",
    "usable_recent_supply_sample_count",
    "usable_quality_sample_count",
)

#: The eight sampling-phase columns ``upsert_sampling_summary`` owns (Q-2).
O10_SAMPLING_PHASE_COLUMNS: tuple[str, ...] = (
    "discovered_population_count",
    "enriched_sample_count",
    "sample_is_census",
    "sampling_basis",
    "sample_fraction",
    "overlap_category_count",
    "overlap_sample_percentage",
    "stratum_statistics_json",
)

#: The pre-scoring zero placeholders created by ``set_category_status``.
O10_EXPECTED_PLACEHOLDERS: dict[str, int] = {
    "unique_enrichment_count": 0,
    "usable_demand_sample_count": 0,
    "usable_recent_supply_sample_count": 0,
    "usable_quality_sample_count": 0,
}


def o10_categories() -> dict[str, tuple[dict, ...]]:
    """Fixture O10 input: one census category and one zero-population one."""
    return {
        CENSUS_CATEGORY: records_for(sequential_keys("ph", 3)),
        ZERO_CATEGORY: (),
    }


# --------------------------------------------------------------------------
# Digest vectors: an independent transcription of the SRS §5.1 LREQ-SMP-060
# digest formula, used to prove a persisted digest is reproducible rather than
# merely copied out of the pure result.
# --------------------------------------------------------------------------


def expected_digest(
    category: str,
    asset_identity_key: str,
    *,
    sampling_rule_version: str = SAMPLING_RULE_VERSION,
) -> str:
    """Restate the SRS §5.1 LREQ-SMP-060 NUL-delimited SHA-256 digest formula."""
    raw = f"{sampling_rule_version}\x00{category}\x00{asset_identity_key}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


__all__ = [
    "A_ONLY_1",
    "A_ONLY_2",
    "B_ONLY_1",
    "B_ONLY_2",
    "CENSUS_CATEGORY",
    "CENSUS_N",
    "CENSUS_ONE_KEYS",
    "CENSUS_POPULATION_THRESHOLD",
    "CATEGORY_A",
    "CATEGORY_B",
    "CATEGORY_C",
    "COMPUTED_AT_UTC",
    "C_ONLY_1",
    "DIGEST_VECTOR_CATEGORY",
    "EMPTY_STRATUM_STATISTICS_JSON",
    "LARGE_CATEGORY",
    "LARGE_N",
    "O10_EXPECTED_PLACEHOLDERS",
    "O10_PLACEHOLDER_COLUMNS",
    "O10_SAMPLING_PHASE_COLUMNS",
    "O1_EXPECTED_PERCENTAGE",
    "O1_SAMPLE_SIZE",
    "O1_SHARED_COUNT",
    "O8_EXPECTED_STRATA_N101",
    "O9_STRATUM_KEYS",
    "O9_STRATUM_STATISTICS_JSON",
    "PENDING_USABLE_STATUS",
    "RUN_STARTED_AT_UTC",
    "SAMPLE_PER_STRATUM",
    "SAMPLE_STRATA",
    "SAMPLING_RULE_VERSION",
    "SCORING_CUTOFF_UTC",
    "SHARED_IDENTITY_KEY",
    "TAXONOMY_CAPTURED_AT_UTC",
    "USABLE_STATUS_VOCABULARY",
    "ZERO_CATEGORY",
    "census_category_keys",
    "census_one_categories",
    "census_report_discovery_status",
    "expected_digest",
    "large_category_keys",
    "o10_categories",
    "o1_categories",
    "o1_expected",
    "o2_categories",
    "o2_expected",
    "o3_categories",
    "o3_expected",
    "o4_categories",
    "o4_expected",
    "o5_categories",
    "o5_expected",
    "o5_union_identity_keys",
    "o6_categories",
    "o6_expected_basis",
    "o6_expected_sample_fractions",
    "o6_expected_selected_counts",
    "o7_categories",
    "run_record",
    "sequential_keys",
]
