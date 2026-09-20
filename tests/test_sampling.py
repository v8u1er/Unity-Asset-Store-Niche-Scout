"""Analytical tests for chunk 4A — canonical populations and deterministic sampling.

Source of truth: ``Documents/SRS-lean.md`` §5.1 (sampling policy) and the frozen
plan ``Documents/plans/chunk-4A-canonical-populations-and-deterministic-sampling.md``
(§5 interface contract, §9 test plan). Expected values are derived from the SRS
formulas and stated with their derivation; the SRS-pinned digest literal in
Fixture F is the implementation's cross-check.

Every analytical test carries ``@pytest.mark.lreq`` and has a
``tests/traceability.json`` entry. ``test_sampling_module_imports_are_pure`` is
the local AST purity gate required by the plan's Q-8 ruling and is deliberately
unmarked and untraced (plan §9.3).
"""

from __future__ import annotations

import ast
import inspect
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

from fixtures import sampling_fixtures as fx

from niche_scout.models import (
    ENRICHMENT_SAMPLE_SIZE_PER_CATEGORY,
    SAMPLE_PER_STRATUM,
    SAMPLE_STRATA,
    SAMPLING_RULE_VERSION,
    SamplingBasis,
)

import niche_scout.sampling as sampling

REPO_ROOT = Path(__file__).resolve().parents[1]
SAMPLING_SOURCE = REPO_ROOT / "src" / "niche_scout" / "sampling.py"

#: Forbidden top-level imports for a pure module. Mirrors
#: ``check_import_boundaries.FORBIDDEN_MODULES`` plus the sampling-specific
#: prohibitions in plan §5.0/§11; it is re-stated locally because the Q-8 ruling
#: removed the ``PURE_MODULES`` registration edit.
FORBIDDEN_IMPORTS = frozenset(
    {
        # Package I/O and orchestration modules (plan §5.0/§11).
        "collector",
        "collector_coveo",
        "collector_graphql",
        "database",
        "pipeline",
        "report",
        "cli",
        "config",
        "metrics",
        "scoring",
        # Filesystem, process, network, database, serialization.
        "os",
        "io",
        "sys",
        "pathlib",
        "shutil",
        "tempfile",
        "subprocess",
        "socket",
        "sqlite3",
        "sqlite",
        "requests",
        "urllib",
        "urllib3",
        "http",
        "httpx",
        "aiohttp",
        "json",
        "csv",
        "pickle",
        # Clock, logging, randomness.
        "time",
        "logging",
        "platform",
        "random",
        "secrets",
        "uuid",
    }
)

CLOCK_ATTRIBUTES = frozenset(
    {"now", "utcnow", "today", "time", "time_ns", "monotonic", "perf_counter", "localtime", "gmtime", "sleep"}
)


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------


def build_records(mappings):
    """Project inert mappings into ``DiscoveryPopulationRecord`` instances.

    Kept behind a helper so a missing/stale input structure fails a single test
    with a clear AttributeError rather than every test with a TypeError.
    """
    return tuple(sampling.DiscoveryPopulationRecord(**item) for item in mappings)


def sampled_summary(result):
    """Return a deterministic digest of the selected members for repeat checks."""
    return tuple(
        (m.stratum_index, m.asset_identity_key, m.selection_digest) for m in result.members
    )


# --------------------------------------------------------------------------
# Digest (LREQ-SMP-060)
# --------------------------------------------------------------------------


@pytest.mark.lreq("LREQ-SMP-060")
def test_digest_matches_nul_delimited_sha256_literal():
    """Fixture F: the digest is the SHA-256 of the NUL-delimited UTF-8 triple.

    SRS §5.1 LREQ-SMP-060. Hash input bytes, exactly:
        b"1.0.0" + b"\\x00" + b"3D/Characters" + b"\\x00" + b"12345"
    The 64-char lowercase-hex literal was computed once by the test author over
    those bytes with ``hashlib.sha256``; ``DIGEST_F_BYTES`` is the same byte
    string, so hashing it here re-derives the expected value independently of
    the implementation.
    """
    import hashlib

    expected = hashlib.sha256(fx.DIGEST_F_BYTES).hexdigest()
    # 25-byte input: 5 (rule) + 1 (NUL) + 13 (category) + 1 (NUL) + 5 (key).
    assert len(fx.DIGEST_F_BYTES) == 25
    assert len(expected) == 64 and expected == expected.lower()
    assert fx.DIGEST_F_HEX == expected, "frozen Fixture F literal drifted from its bytes"

    actual = sampling.selection_digest(
        fx.DIGEST_FIXTURE_CATEGORY,
        fx.DIGEST_FIXTURE_KEY,
        sampling_rule_version=fx.DIGEST_FIXTURE_RULE_VERSION,
    )
    assert actual == fx.DIGEST_F_HEX


@pytest.mark.lreq("LREQ-SMP-060")
def test_digest_changes_with_rule_version():
    """Fixture E: a different rule version changes every member digest.

    SRS §5.1 LREQ-SMP-060: the rule version is a digest input, so the same
    ``(category, key)`` pair must digest differently under "1.0.0" and "1.0.1"
    (a test-local string; the second version is not a policy constant).
    """
    category = fx.CATEGORY
    records = build_records(fx.large_101_records())

    result_a = sampling.select_category_sample(
        records, category=category, sampling_rule_version="1.0.0"
    )
    result_b = sampling.select_category_sample(
        records, category=category, sampling_rule_version="1.0.1"
    )

    result_digests = {
        m.asset_identity_key: m.selection_digest for m in result_a.members
    }
    result_b_digests = {
        m.asset_identity_key: m.selection_digest for m in result_b.members
    }

    # At least one stratum's selected identity set differs.
    a_selection: dict[int, set[str]] = {h: set() for h in range(SAMPLE_STRATA)}
    b_selection: dict[int, set[str]] = {h: set() for h in range(SAMPLE_STRATA)}
    for member in result_a.members:
        a_selection[member.stratum_index].add(member.asset_identity_key)
    for member in result_b.members:
        b_selection[member.stratum_index].add(member.asset_identity_key)
    assert any(a_selection[h] != b_selection[h] for h in range(SAMPLE_STRATA))

    # Every shared selected identity must carry a different digest under each
    # rule version, because (rule_version, category, key) is the digest input.
    shared_keys = set(result_digests) & set(result_b_digests)
    assert shared_keys
    for key in shared_keys:
        assert result_digests[key] != result_b_digests[key]

    # Standalone digest function agrees with the member digests.
    assert sampling.selection_digest(
        category, "asset-0000", sampling_rule_version="1.0.0"
    ) != sampling.selection_digest(
        category, "asset-0000", sampling_rule_version="1.0.1"
    )


@pytest.mark.lreq("LREQ-SMP-060", "LREQ-SMP-050")
def test_repeated_selection_is_identical():
    """Determinism: identical inputs and rule version -> identical result.

    SRS §5.1 LREQ-SMP-060 (no unseeded RNG, no platform-dependent hash) and
    LREQ-SMP-050 (the selection is a pure function of the population). Two
    independent calls are compared field by field, not by object identity.
    """
    records = build_records(fx.large_200_records())
    first = sampling.select_category_sample(records, category=fx.LARGE_CATEGORY)
    second = sampling.select_category_sample(records, category=fx.LARGE_CATEGORY)

    assert sampled_summary(first) == sampled_summary(second)
    assert first.strata == second.strata
    assert first.population == second.population
    assert first.sample_fraction == second.sample_fraction
    assert first.enriched_sample_count == second.enriched_sample_count
    assert first.sampling_basis == second.sampling_basis

    # And the digest helper itself is a pure function.
    assert sampling.selection_digest(fx.LARGE_CATEGORY, "asset-0000") == sampling.selection_digest(
        fx.LARGE_CATEGORY, "asset-0000"
    )


@pytest.mark.lreq("LREQ-SMP-060", "LREQ-ARCH-020")
def test_no_randomness_module_used():
    """AST check: ``sampling.py`` imports no RNG/clock and calls no clock read.

    SRS §5.1 LREQ-SMP-060 forbids an unseeded random generator; SRS §3.3
    LREQ-ARCH-020 forbids clock reads in pure code. This is the analytical half
    of the purity check; the import-boundary half is the unmarked AST test
    ``test_sampling_module_imports_are_pure``.
    """
    tree = ast.parse(SAMPLING_SOURCE.read_text(encoding="utf-8"), filename=str(SAMPLING_SOURCE))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[-1])

    assert not (imported & {"random", "secrets", "uuid", "time"}), (
        f"sampling.py must not import an RNG or clock module: {imported & {'random', 'secrets', 'uuid', 'time'}}"
    )

    clock_calls = [
        ast.unparse(node)
        for node in ast.walk(tree)
        if isinstance(node, ast.Attribute)
        and node.attr in CLOCK_ATTRIBUTES
        and isinstance(node.value, ast.Name)
        and node.value.id in {"datetime", "date", "time", "dt"}
    ]
    assert clock_calls == []


# --------------------------------------------------------------------------
# Census (LREQ-SMP-040)
# --------------------------------------------------------------------------


@pytest.mark.lreq("LREQ-SMP-040")
@pytest.mark.parametrize("n", [0, 1, 99, 100])
def test_census_population_sizes_zero_one_99_100(n):
    """Fixture A: populations of 0, 1, 99, 100 are census (SRS §5.1 LREQ-SMP-040).

    At most 100 canonical assets is fully enriched and ``sample_is_census`` is
    true. For N in {1, 99, 100} every canonical asset is a member; N == 0 is the
    empty case with ``sample_fraction is None`` (never 0.0).
    """
    records = build_records(fx.population_records(n))
    result = sampling.select_category_sample(records, category=fx.CATEGORY)

    assert result.sample_is_census is True
    assert result.sampling_basis == SamplingBasis.CENSUS
    assert result.sampling_basis == "census"
    assert result.discovered_population_count == n
    assert result.population.size == n
    assert result.enriched_sample_count == n
    assert len(result.members) == n
    assert len(result.strata) == (0 if n == 0 else 1)
    if n == 0:
        assert result.sample_fraction is None
    else:
        assert result.sample_fraction == pytest.approx(1.0, abs=1e-9)


@pytest.mark.lreq("LREQ-SMP-040")
def test_census_selects_all_assets():
    """Fixture A: every canonical identity is selected, once, in census."""
    for records in (fx.census_one_records(), fx.census_99_records(), fx.census_100_records()):
        result = sampling.select_category_sample(build_records(records), category=fx.CATEGORY)
        expected_keys = {item["asset_identity_key"] for item in records}
        assert {m.asset_identity_key for m in result.members} == expected_keys
        assert len(result.members) == len(expected_keys)


@pytest.mark.lreq("LREQ-SMP-040")
def test_zero_population_fraction_is_null_not_zero():
    """Empty category: ``sample_fraction is None``, never ``0.0``.

    SRS §5.1 LREQ-SMP-080 (null when the discovered population is zero) and
    SRS §1.2 missing-is-not-zero; plan §5.3.
    """
    result = sampling.select_category_sample((), category=fx.CATEGORY)
    assert result.discovered_population_count == 0
    assert result.population.size == 0
    assert result.sample_fraction is None
    assert result.sample_fraction != 0.0
    assert result.members == ()
    assert result.strata == ()
    assert result.enriched_sample_count == 0


@pytest.mark.lreq("LREQ-SMP-040")
def test_census_sample_fraction_is_exactly_one():
    """Non-empty census: ``sample_fraction == 1.0`` exactly (SRS §5.1 LREQ-SMP-080)."""
    for n in (1, 99, 100):
        result = sampling.select_category_sample(
            build_records(fx.population_records(n)), category=fx.CATEGORY
        )
        assert result.sample_fraction == pytest.approx(1.0, abs=1e-9)
        # 1.0 exactly, not merely close.
        assert result.sample_fraction == 1.0


# --------------------------------------------------------------------------
# Stratum geometry (LREQ-SMP-050)
# --------------------------------------------------------------------------


@pytest.mark.lreq("LREQ-SMP-050")
def test_four_strata_boundaries_at_101():
    """Fixture B: N = 101 divides into 1..25, 26..50, 51..75, 76..101.

    Derivation (SRS §5.1 LREQ-SMP-050, ``start = floor(h*N/4)+1``,
    ``end = floor((h+1)*N/4)``, final stratum takes the remainder):
        h=0: floor(0/4)+1 = 1      .. floor(101/4)   = 25 (25.25 -> 25)
        h=1: floor(101/4)+1 = 26   .. floor(202/4)   = 50 (50.5 -> 50)
        h=2: floor(202/4)+1 = 51   .. floor(303/4)   = 75 (75.75 -> 75)
        h=3: floor(303/4)+1 = 76   .. floor(404/4)   = 101
    Each non-reduced stratum selects 25; the final stratum has 26 assets, so 100
    of 101 are selected: ``sample_fraction == 100/101``, which is < 1.0.
    """
    assert fx.expected_stratum_boundaries(101) == ((1, 25), (26, 50), (51, 75), (76, 101))

    result = sampling.select_category_sample(
        build_records(fx.large_101_records()), category=fx.LARGE_CATEGORY
    )
    assert result.sample_is_census is False
    assert result.sampling_basis == SamplingBasis.DETERMINISTIC_STRATIFIED_SAMPLE
    assert result.sampling_basis == "deterministic_stratified_sample"

    observed = tuple(
        (s.stratum_index, s.start_ordinal, s.end_ordinal, s.population_count)
        for s in result.strata
    )
    assert observed == (
        (0, 1, 25, 25),
        (1, 26, 50, 25),
        (2, 51, 75, 25),
        (3, 76, 101, 26),
    )

    assert len(result.members) == 100
    assert result.enriched_sample_count == 100
    assert result.discovered_population_count == 101
    assert result.sample_fraction == pytest.approx(100 / 101, abs=1e-9)
    assert result.sample_fraction < 1.0


@pytest.mark.lreq("LREQ-SMP-050")
def test_four_strata_boundaries_at_200():
    """Fixture C: N = 200 gives four equal 50-asset strata; each selects 25.

    Derivation: h=0..3 -> start in {1, 51, 101, 151}, end in {50, 100, 150, 200};
    no remainder. ``sample_fraction == 100/200 == 0.5``.
    """
    result = sampling.select_category_sample(
        build_records(fx.large_200_records()), category=fx.LARGE_CATEGORY
    )
    observed = tuple(
        (s.stratum_index, s.start_ordinal, s.end_ordinal, s.population_count, s.selected_count)
        for s in result.strata
    )
    assert observed == (
        (0, 1, 50, 50, 25),
        (1, 51, 100, 50, 25),
        (2, 101, 150, 50, 25),
        (3, 151, 200, 50, 25),
    )
    assert len(result.members) == 100
    assert result.sample_fraction == pytest.approx(0.5, abs=1e-9)


@pytest.mark.lreq("LREQ-SMP-050")
@pytest.mark.parametrize("n", [101, 105, 200, 1000])
def test_strata_are_contiguous_and_cover_population(n):
    """Strata have no gap and no overlap and their union is exactly ``1..N``.

    SRS §5.1 LREQ-SMP-050 "contiguous ordinal strata"; the union check is
    boundary-rule independent and holds for the census single stratum too.
    """
    result = sampling.select_category_sample(
        build_records(fx.population_records(n)), category=fx.LARGE_CATEGORY
    )
    strata = result.strata
    assert strata, "a non-empty population must produce at least one stratum"
    assert strata[0].start_ordinal == 1
    assert strata[-1].end_ordinal == n
    for previous, current in zip(strata, strata[1:]):
        assert current.start_ordinal == previous.end_ordinal + 1
    covered = [ordinal for s in strata for ordinal in range(s.start_ordinal, s.end_ordinal + 1)]
    assert covered == list(range(1, n + 1))


@pytest.mark.lreq("LREQ-SMP-050")
def test_large_category_targets_25_per_stratum():
    """Every non-reduced stratum selects exactly ``SAMPLE_PER_STRATUM`` (25)."""
    for n in (101, 105, 200, 1000):
        result = sampling.select_category_sample(
            build_records(fx.population_records(n)), category=fx.LARGE_CATEGORY
        )
        for stratum in result.strata:
            assert stratum.is_reduced is False
            assert stratum.target_count == SAMPLE_PER_STRATUM == 25
            assert stratum.selected_count == SAMPLE_PER_STRATUM == 25
        assert len(result.members) == SAMPLE_STRATA * SAMPLE_PER_STRATUM == 100


# --------------------------------------------------------------------------
# Canonical population construction (LREQ-SMP-020, LREQ-SMP-010)
# --------------------------------------------------------------------------


@pytest.mark.lreq("LREQ-SMP-020")
def test_population_ordered_by_discovery_ordinal():
    """The population is ordered by retained discovery ordinal, ties by key.

    SRS §5.1 LREQ-SMP-020. Input is deliberately shuffled; output must be
    ascending by ordinal and carry the ordinals in the same order as the keys.
    Also exercises the identity-key tie-break: two records share an ordinal and
    must order by their keys.
    """
    records = build_records(
        (
            fx.record(9, "zeta"),
            fx.record(3, "beta"),
            fx.record(0, "alpha"),
            fx.record(7, "eta"),
            fx.record(1, "gamma"),
        )
    )
    population = sampling.build_canonical_population(records, category=fx.CATEGORY)
    assert population.identity_keys == ("alpha", "gamma", "beta", "eta", "zeta")
    assert population.retained_ordinals == (0, 1, 3, 7, 9)
    assert population.size == 5

    # Same ordinal -> identity-key tie-break.
    tied = build_records((fx.record(4, "b"), fx.record(4, "a")))
    tied_population = sampling.build_canonical_population(tied, category=fx.CATEGORY)
    assert tied_population.identity_keys == ("a", "b")
    assert tied_population.retained_ordinals == (4, 4)


@pytest.mark.lreq("LREQ-SMP-020")
def test_first_valid_ordinal_retained_for_repeat():
    """A repeated identity keeps its first (lowest) valid ordinal.

    SRS §5.1 LREQ-SMP-020; Fixture H and the shuffled repeat fixture. Input
    order is high-ordinal first, so preserving input order fails the assertion.
    """
    records = build_records(fx.repeated_identity_lowest_ordinal_records())
    population = sampling.build_canonical_population(records, category=fx.CATEGORY)
    assert population.identity_keys == ("repeat-key",)
    assert population.retained_ordinals == (2,)
    assert population.collapsed_repeat_count == 1
    assert population.size == 1

    fixture_h = sampling.build_canonical_population(
        build_records(fx.exclusion_records()), category=fx.CATEGORY
    )
    assert fixture_h.identity_keys == ("keep-0", "keep-1", "keep-2")
    assert fixture_h.retained_ordinals == (0, 1, 5)
    assert fixture_h.collapsed_repeat_count == 1
    assert fixture_h.size == 3


@pytest.mark.lreq("LREQ-SMP-010")
def test_unresolved_and_conflict_excluded():
    """A null identity key (unresolved or conflict) is never in the population.

    SRS §5.1 LREQ-SMP-010 (sampling after identity resolution); SRS §4.1
    LREQ-EXT-070 (conflict/unresolved excluded); plan §5.2 and the Q-2 ruling
    (one ``excluded_unresolved_count`` field covering both).
    """
    records = build_records(
        (
            fx.record(0, "resolved-a"),
            fx.record(1, None),
            fx.record(2, None),
            fx.record(3, "resolved-b"),
        )
    )
    population = sampling.build_canonical_population(records, category=fx.CATEGORY)
    assert population.identity_keys == ("resolved-a", "resolved-b")
    assert population.retained_ordinals == (0, 3)
    assert population.excluded_unresolved_count == 2
    assert population.excluded_duplicate_count == 0
    assert population.collapsed_repeat_count == 0
    assert population.size == 2
    assert None not in population.identity_keys


@pytest.mark.lreq("LREQ-SMP-010")
def test_duplicate_row_excluded_and_counted():
    """``is_duplicate=True`` rows are excluded and counted, key or no key.

    Fixture H hand derivation (plan §5.2, §9.2): ordinal 3 is a duplicate with
    a non-null key (``excluded_duplicate_count``); ordinal 4 is a duplicate with
    a null key, where the null key dominates and it counts as unresolved.
    """
    population = sampling.build_canonical_population(
        build_records(fx.exclusion_records()), category=fx.CATEGORY
    )
    assert population.excluded_duplicate_count == 1
    assert population.excluded_unresolved_count == 2
    assert "keep-0" in population.identity_keys
    # The duplicate ordinal 3 is not retained; the lowest ordinal is 0.
    assert population.retained_ordinals[population.identity_keys.index("keep-0")] == 0


# --------------------------------------------------------------------------
# Reduced strata (LREQ-SMP-090)
# --------------------------------------------------------------------------


@pytest.mark.lreq("LREQ-SMP-090")
def test_reduced_stratum_selects_all_and_reports_reduced_count():
    """Fixture D: a stratum below 25 selects all and reports the reduced count.

    SRS §5.1 LREQ-SMP-090; the Q-3 ruling places the reachable case on a census
    population with N < 25. N = 24 -> one stratum, target 24, reduced; N = 25 ->
    target 25, not reduced; N = 1 -> target 1, reduced. N = 105 companion keeps
    every stratum non-reduced at 25.
    """
    reduced_24 = sampling.select_category_sample(
        build_records(fx.census_24_records()), category=fx.CATEGORY
    )
    assert len(reduced_24.strata) == 1
    stratum = reduced_24.strata[0]
    assert (stratum.stratum_index, stratum.start_ordinal, stratum.end_ordinal) == (0, 1, 24)
    assert stratum.population_count == 24
    assert stratum.target_count == 24
    assert stratum.selected_count == 24
    assert stratum.is_reduced is True
    assert len(reduced_24.members) == 24
    assert reduced_24.sample_fraction == pytest.approx(1.0, abs=1e-9)
    assert reduced_24.sample_is_census is True

    exact_25 = sampling.select_category_sample(
        build_records(fx.census_25_records()), category=fx.CATEGORY
    )
    assert exact_25.strata[0].target_count == 25
    assert exact_25.strata[0].selected_count == 25
    assert exact_25.strata[0].is_reduced is False

    single = sampling.select_category_sample(
        build_records(fx.census_one_records()), category=fx.CATEGORY
    )
    assert single.strata[0].target_count == 1
    assert single.strata[0].is_reduced is True

    large_105 = sampling.select_category_sample(
        build_records(fx.large_105_records()), category=fx.LARGE_CATEGORY
    )
    assert tuple((s.start_ordinal, s.end_ordinal) for s in large_105.strata) == (
        (1, 26),
        (27, 52),
        (53, 78),
        (79, 105),
    )
    for large_stratum in large_105.strata:
        assert large_stratum.is_reduced is False
        assert large_stratum.selected_count == 25


# --------------------------------------------------------------------------
# Position coverage (LREQ-SMP-070)
# --------------------------------------------------------------------------


@pytest.mark.lreq("LREQ-SMP-070")
def test_early_middle_late_positions_represented():
    """Fixture I: the N = 101 sample draws from all four ordinal ranges.

    SRS §5.1 LREQ-SMP-070. One selected key per stratum suffices; each member
    carries its own stratum boundaries, so position is read off the member.
    """
    result = sampling.select_category_sample(
        build_records(fx.large_101_records()), category=fx.LARGE_CATEGORY
    )
    ordinals_by_key = {
        item["asset_identity_key"]: i + 1 for i, item in enumerate(fx.large_101_records())
    }
    ranges = ((1, 25), (26, 50), (51, 75), (76, 101))
    for low, high in ranges:
        positions = [
            ordinals_by_key[m.asset_identity_key]
            for m in result.members
            if low <= ordinals_by_key[m.asset_identity_key] <= high
        ]
        assert positions, f"no selected asset in ordinal range {low}..{high}"


@pytest.mark.lreq("LREQ-SMP-070")
def test_sample_is_not_first_page_prefix():
    """The selection is not the first 100 (or first ``PAGE_SIZE``) results.

    SRS §5.1 LREQ-SMP-070: selecting only the first page or first 100 results is
    non-conforming. The selected ordinal set must contain at least one ordinal
    beyond 100.
    """
    records = fx.large_101_records()
    ordinals_by_key = {
        item["asset_identity_key"]: i + 1 for i, item in enumerate(records)
    }
    result = sampling.select_category_sample(
        build_records(records), category=fx.LARGE_CATEGORY
    )
    selected_ordinals = {ordinals_by_key[m.asset_identity_key] for m in result.members}
    assert len(selected_ordinals) == 100
    assert max(selected_ordinals) > 100


# --------------------------------------------------------------------------
# Basis / census flag and non-configurability (LREQ-SMP-030, LREQ-SMP-040)
# --------------------------------------------------------------------------


@pytest.mark.lreq("LREQ-SMP-030", "LREQ-SMP-040")
def test_sampling_basis_and_census_flag():
    """``census`` at/under 100; ``deterministic_stratified_sample`` above.

    SRS §5.1 LREQ-SMP-040 and LREQ-SMP-080 (``sampling_basis`` vocabulary).
    """
    census = sampling.select_category_sample(
        build_records(fx.census_100_records()), category=fx.CATEGORY
    )
    assert census.sampling_basis == SamplingBasis.CENSUS
    assert census.sampling_basis == "census"
    assert census.sample_is_census is True

    large = sampling.select_category_sample(
        build_records(fx.large_101_records()), category=fx.LARGE_CATEGORY
    )
    assert large.sampling_basis == SamplingBasis.DETERMINISTIC_STRATIFIED_SAMPLE
    assert large.sampling_basis == "deterministic_stratified_sample"
    assert large.sample_is_census is False


@pytest.mark.lreq("LREQ-SMP-030")
def test_default_constants_are_not_configurable():
    """The fixed sampling constants come from ``models`` and are not parameters.

    SRS §5.1 LREQ-SMP-030: the values are fixed and SHALL not be exposed as
    independently configurable. The test also pins that the census threshold is
    the frozen ``ENRICHMENT_SAMPLE_SIZE_PER_CATEGORY`` and that the invariant
    ``100 == 4 * 25`` holds.
    """
    import niche_scout.models as models

    assert models.ENRICHMENT_SAMPLE_SIZE_PER_CATEGORY == 100
    assert models.SAMPLE_STRATA == 4
    assert models.SAMPLE_PER_STRATUM == 25
    assert models.ENRICHMENT_SAMPLE_SIZE_PER_CATEGORY == models.SAMPLE_STRATA * models.SAMPLE_PER_STRATUM

    # The sampling module re-exports the same frozen values.
    assert sampling.ENRICHMENT_SAMPLE_SIZE_PER_CATEGORY == ENRICHMENT_SAMPLE_SIZE_PER_CATEGORY
    assert sampling.SAMPLE_STRATA == SAMPLE_STRATA
    assert sampling.SAMPLE_PER_STRATUM == SAMPLE_PER_STRATUM
    assert sampling.SAMPLING_RULE_VERSION == SAMPLING_RULE_VERSION == "1.0.0"
    assert sampling.CENSUS_POPULATION_THRESHOLD == ENRICHMENT_SAMPLE_SIZE_PER_CATEGORY == 100
    assert sampling.NUL_DELIMITER == "\x00"

    # Production entry point exposes no stratum/allocation override.
    for name in ("select_category_sample", "select_run_sample"):
        parameters = inspect.signature(getattr(sampling, name)).parameters
        for forbidden in (
            "sample_strata",
            "per_stratum_target",
            "census_threshold",
            "enrichment_sample_size_per_category",
            "sample_size",
        ):
            assert forbidden not in parameters, f"{name} exposes {forbidden}"

    # The public defaults bound the fixed constants; the analytical
    # ``build_strata`` overrides are keyword-only and default to those values.
    build_strata_parameters = inspect.signature(sampling.build_strata).parameters
    assert build_strata_parameters["sample_strata"].default == SAMPLE_STRATA
    assert build_strata_parameters["per_stratum_target"].default == SAMPLE_PER_STRATUM
    assert build_strata_parameters["census_threshold"].default == ENRICHMENT_SAMPLE_SIZE_PER_CATEGORY


# --------------------------------------------------------------------------
# Malformed input (LREQ-SMP-010)
# --------------------------------------------------------------------------


@pytest.mark.lreq("LREQ-SMP-010")
def test_malformed_population_input_raises_value_error():
    """Fixture J: malformed input raises ``ValueError``, never a substituted value.

    Plan §5.2/§5.4: empty/whitespace category; negative, boolean, or non-int
    ordinal; empty/whitespace identity key. A bool is rejected because it is an
    ``int`` subclass and is never an ordinal.
    """
    good_record = fx.record(0, "asset-0000", False)

    for bad_category in fx.malformed_category_values():
        with pytest.raises(ValueError):
            sampling.selection_digest(bad_category, "asset-0000")
        with pytest.raises(ValueError):
            sampling.build_canonical_population(
                build_records((good_record,)), category=bad_category
            )
        with pytest.raises(ValueError):
            sampling.select_category_sample(
                build_records((good_record,)), category=bad_category
            )

    for bad_ordinal in fx.malformed_ordinal_values():
        with pytest.raises(ValueError):
            sampling.build_canonical_population(
                build_records((fx.record(bad_ordinal, "asset-0000", False),)),
                category=fx.CATEGORY,
            )

    for bad_key in fx.malformed_identity_values():
        with pytest.raises(ValueError):
            sampling.build_canonical_population(
                build_records((fx.record(0, bad_key, False),)), category=fx.CATEGORY
            )


# --------------------------------------------------------------------------
# Membership and run-wide behaviour (LREQ-SMP-010)
# --------------------------------------------------------------------------


@pytest.mark.lreq("LREQ-SMP-010")
def test_no_duplicate_membership_within_category():
    """Members within one category are identity-unique.

    SRS §5.1 LREQ-SMP-010/020: the population is identity-unique and selection
    draws from it once.
    """
    for records in (fx.census_100_records(), fx.large_101_records(), fx.exclusion_records()):
        result = sampling.select_category_sample(build_records(records), category=fx.CATEGORY)
        keys = [m.asset_identity_key for m in result.members]
        assert len(keys) == len(set(keys))
        assert len(result.population.identity_keys) == len(set(result.population.identity_keys))


@pytest.mark.lreq("LREQ-SMP-010")
def test_run_sample_preserves_category_order():
    """``select_run_sample`` preserves the caller mapping's insertion order (Q-7).

    Plan §5.4 Q-7 ruling: categories are emitted in insertion order and never
    sorted, so a non-lexical order such as B before A stays B before A.
    """
    mapping = fx.run_categories_mapping()
    result = sampling.select_run_sample(mapping, run_id="run-0001")

    assert result.run_id == "run-0001"
    assert [category.category for category in result.categories] == [
        fx.SHARED_CATEGORY_B,
        fx.SHARED_CATEGORY_A,
    ]
    assert list(result.by_category) == [fx.SHARED_CATEGORY_B, fx.SHARED_CATEGORY_A]
    assert result.sampling_rule_version == SAMPLING_RULE_VERSION

    empty = sampling.select_run_sample({}, run_id="run-empty")
    assert empty.categories == ()
    assert dict(empty.by_category) == {}


@pytest.mark.lreq("LREQ-SMP-010")
def test_shared_identity_appears_in_both_categories():
    """Fixture G: a shared identity may appear in both category samples; the
    enrichment union lists it once and no overlap count is produced.

    SRS §5.1 LREQ-SMP-010 and LREQ-SMP-080 (enrichment set is the union; each
    unique identity enriched once); plan §5.3 and §9.2 Fixture G.
    """
    result = sampling.select_run_sample(fx.run_categories_mapping(), run_id="run-0001")
    by_category = result.by_category

    category_b = by_category[fx.SHARED_CATEGORY_B]
    category_a = by_category[fx.SHARED_CATEGORY_A]
    assert fx.SHARED_IDENTITY_KEY in {m.asset_identity_key for m in category_b.members}
    assert fx.SHARED_IDENTITY_KEY in {m.asset_identity_key for m in category_a.members}

    enrichment_keys = result.enrichment_identity_keys
    assert enrichment_keys.count(fx.SHARED_IDENTITY_KEY) == 1
    expected_first_seen = []
    for category_result in result.categories:
        for member in category_result.members:
            if member.asset_identity_key not in expected_first_seen:
                expected_first_seen.append(member.asset_identity_key)
    assert tuple(expected_first_seen) == tuple(enrichment_keys)

    # No overlap metric is emitted by this chunk.
    assert not hasattr(result, "overlap_category_count")
    assert not hasattr(category_b, "overlap_sample_percentage")


# --------------------------------------------------------------------------
# Persistence-facing separation (LREQ-SMP-080)
# --------------------------------------------------------------------------


@pytest.mark.lreq("LREQ-SMP-080")
def test_sample_fraction_distinct_from_stratum_aggregates():
    """``sample_fraction`` is its own field; no stratum coverage or usable count is emitted.

    SRS §5.1 LREQ-SMP-080 (``sample_fraction`` is distinct from stratum
    eligibility coverage) and plan §2/§5.3 (no ``u_*`` counts, no overlap).
    """
    result = sampling.select_category_sample(
        build_records(fx.large_101_records()), category=fx.LARGE_CATEGORY
    )
    assert result.sample_fraction == pytest.approx(100 / 101, abs=1e-9)
    assert result.sample_fraction != 1.0
    assert result.discovered_population_count == 101
    assert result.enriched_sample_count == 100

    for name in (
        "stratum_eligibility_coverage",
        "u_demand_h",
        "u_recent_h",
        "u_quality_h",
        "usable_demand_sample_count",
        "overlap_sample_percentage",
    ):
        assert not hasattr(result, name), f"Chunk 4A must not emit {name}"

    # Every persistence column value must be carried for Chunk 4B to write.
    for name in (
        "sampling_basis",
        "sample_fraction",
        "sample_is_census",
        "discovered_population_count",
        "enriched_sample_count",
        "sampling_rule_version",
    ):
        assert hasattr(result, name)
    for member in result.members:
        for name in (
            "category",
            "asset_identity_key",
            "stratum_index",
            "stratum_start_ordinal",
            "stratum_end_ordinal",
            "sample_rank_within_stratum",
            "sample_is_census",
            "selection_digest",
        ):
            assert hasattr(member, name), f"member missing persistence field {name}"


# --------------------------------------------------------------------------
# Census member ranking and digest (Q-5, Q-6 rulings)
# --------------------------------------------------------------------------


@pytest.mark.lreq("LREQ-SMP-060")
def test_census_member_ranks_follow_digest_order():
    """Census ``sample_rank_within_stratum`` is 1-based in ``(digest, key)`` order.

    Plan §5.3 Q-6 ruling: census ranks follow the digest sort exactly as sampled
    ranks do, not the original discovery order.
    """
    result = sampling.select_category_sample(
        build_records(fx.census_100_records()), category=fx.CATEGORY
    )
    for stratum in result.strata:
        members = [m for m in result.members if m.stratum_index == stratum.stratum_index]
        assert [m.sample_rank_within_stratum for m in members] == list(
            range(1, len(members) + 1)
        )
        ordered = sorted(
            members, key=lambda m: (m.selection_digest, m.asset_identity_key)
        )
        assert [m.asset_identity_key for m in members] == [m.asset_identity_key for m in ordered]
        assert all(
            (members[i].selection_digest, members[i].asset_identity_key)
            < (members[i + 1].selection_digest, members[i + 1].asset_identity_key)
            for i in range(len(members) - 1)
        )
    assert all(m.sample_is_census is True for m in result.members)


@pytest.mark.lreq("LREQ-SMP-060")
def test_census_member_digest_is_standard_nul_digest():
    """Every census member carries the standard NUL digest; no sentinel (Q-5).

    Plan §5.3 Q-5 ruling: ``selection_digest`` is always
    ``selection_digest(rule_version, category, key)``, for census members too.
    """
    category = fx.CATEGORY
    result = sampling.select_category_sample(
        build_records(fx.census_100_records()), category=category
    )
    for member in result.members:
        assert member.selection_digest == sampling.selection_digest(
            category, member.asset_identity_key, sampling_rule_version=SAMPLING_RULE_VERSION
        )
        assert len(member.selection_digest) == 64
        assert member.selection_digest == member.selection_digest.lower()


# --------------------------------------------------------------------------
# Purity boundary (plan §5.0 / §11; Q-8 ruling). NOT an analytical test:
# deliberately no ``@pytest.mark.lreq`` and no traceability entry.
# --------------------------------------------------------------------------


def test_sampling_module_imports_are_pure():
    """AST purity gate for ``sampling.py`` (Q-8 ruling; plan §5.0).

    Asserts the module imports no forbidden package/IO/network/clock/randomness
    module and performs no clock read. This replaces the ``PURE_MODULES``
    registration edit that the Q-8 ruling removed.
    """
    tree = ast.parse(SAMPLING_SOURCE.read_text(encoding="utf-8"), filename=str(SAMPLING_SOURCE))

    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imported.add(node.module.split(".")[-1])
            else:
                imported.update(alias.name.split(".")[0] for alias in node.names)

    violations = sorted(imported & FORBIDDEN_IMPORTS)
    assert violations == [], f"sampling.py imports forbidden modules: {violations}"

    clock_reads = [
        ast.unparse(node)
        for node in ast.walk(tree)
        if isinstance(node, ast.Attribute)
        and node.attr in CLOCK_ATTRIBUTES
        and (
            (isinstance(node.value, ast.Name) and node.value.id in {"datetime", "date", "time", "dt"})
            or (
                isinstance(node.value, ast.Attribute)
                and isinstance(node.value.value, ast.Name)
                and node.value.value.id in {"datetime", "date", "time", "dt"}
            )
        )
    ]
    assert clock_reads == [], f"sampling.py reads the clock: {clock_reads}"

    # Sanity: the parser was pointed at the real module file.
    assert SAMPLING_SOURCE.is_file()
