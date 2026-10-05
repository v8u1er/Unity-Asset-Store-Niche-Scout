"""Analytical tests for chunk 4A — canonical populations and deterministic sampling.

Source of truth: ``Documents/SRS-lean.md`` §5.1 (sampling policy), the frozen
plan ``Documents/plans/chunk-4A-canonical-populations-and-deterministic-sampling.md``
(§5 interface contract, §9 test plan), and the frozen remediation plan
``Documents/plans/chunk-24-systematic-strata.md`` (§2 systematic partition and
A3 offset, §6 typed pure contract, §7 affected nodes, §8 golden vectors).
Expected values are derived from the SRS/plan formulas and stated with their
derivation; the SRS-pinned digest literal in Fixture F is the implementation's
cross-check.

Every analytical test carries ``@pytest.mark.lreq`` and has a
``tests/traceability.json`` entry. ``test_sampling_module_imports_are_pure`` is
the local AST purity gate required by the plan's Q-8 ruling and is deliberately
unmarked and untraced (plan §9.3).
"""

from __future__ import annotations

import ast
import inspect
from pathlib import Path

import pytest
from fixtures import sampling_fixtures as fx

import niche_scout.sampling as sampling
from niche_scout.models import (
    ENRICHMENT_SAMPLE_SIZE_PER_CATEGORY,
    SAMPLE_PER_STRATUM,
    SAMPLE_STRATA,
    SAMPLING_RULE_VERSION,
    SamplingBasis,
)

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
    {
        "now",
        "utcnow",
        "today",
        "time",
        "time_ns",
        "monotonic",
        "perf_counter",
        "localtime",
        "gmtime",
        "sleep",
    }
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
        (m.stratum_index, m.asset_identity_key, m.selection_digest)
        for m in result.members
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
    assert fx.DIGEST_F_HEX == expected, (
        "frozen Fixture F literal drifted from its bytes"
    )

    actual = sampling.selection_digest(
        fx.DIGEST_FIXTURE_CATEGORY,
        fx.DIGEST_FIXTURE_KEY,
        sampling_rule_version=fx.DIGEST_FIXTURE_RULE_VERSION,
    )
    assert actual == fx.DIGEST_F_HEX


@pytest.mark.lreq("LREQ-SMP-060")
@pytest.mark.lreq("LREQ-TST-020")
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
    assert sampling.selection_digest(
        fx.LARGE_CATEGORY, "asset-0000"
    ) == sampling.selection_digest(fx.LARGE_CATEGORY, "asset-0000")


@pytest.mark.lreq("LREQ-SMP-060", "LREQ-ARCH-020")
def test_no_randomness_module_used():
    """AST check: ``sampling.py`` imports no RNG/clock and calls no clock read.

    SRS §5.1 LREQ-SMP-060 forbids an unseeded random generator; SRS §3.3
    LREQ-ARCH-020 forbids clock reads in pure code. This is the analytical half
    of the purity check; the import-boundary half is the unmarked AST test
    ``test_sampling_module_imports_are_pure``.
    """
    tree = ast.parse(
        SAMPLING_SOURCE.read_text(encoding="utf-8"), filename=str(SAMPLING_SOURCE)
    )
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[-1])

    forbidden_present = imported & {"random", "secrets", "uuid", "time"}
    assert not forbidden_present, (
        f"sampling.py must not import an RNG or clock module: {forbidden_present}"
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
@pytest.mark.lreq("LREQ-TST-020")
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
    for records in (
        fx.census_one_records(),
        fx.census_99_records(),
        fx.census_100_records(),
    ):
        result = sampling.select_category_sample(
            build_records(records), category=fx.CATEGORY
        )
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


@pytest.mark.lreq("LREQ-SMP-040")
@pytest.mark.lreq("LREQ-TST-020")
def test_census_geometry_is_offset_zero_stride_one():
    """Census: one stratum, index 0, offset 0, stride 1, ordinals ``1..N``.

    Plan chunk-24 §2.3/OQ-1 freezes the census encoding
    ``(stratum_offset, stratum_stride) = (0, 1)`` -- the only stride under
    ``(i - 1 + 0) mod stride == 0`` that reproduces all ordinals. Hand checks:
    N = 0 -> no stratum at all; N = 1 -> the single ordinal 1; N = 99 ->
    1..99; N = 100 -> the last census population, 1..100.
    """
    assert sampling.select_category_sample((), category=fx.CATEGORY).strata == ()

    for n in (1, 99, 100):
        result = sampling.select_category_sample(
            build_records(fx.population_records(n)), category=fx.CATEGORY
        )
        assert len(result.strata) == 1
        stratum = result.strata[0]
        assert (
            stratum.stratum_index,
            stratum.stratum_offset,
            stratum.stratum_stride,
        ) == (0, 0, 1)
        assert stratum.population_count == stratum.selected_count == n
        assert stratum.is_reduced is (n < SAMPLE_PER_STRATUM)
        assert sampling.stratum_member_ordinals(stratum, n) == tuple(range(1, n + 1))
        for member in result.members:
            assert member.stratum_offset == 0
            assert member.stratum_stride == 1


# --------------------------------------------------------------------------
# Systematic (interleaved) partition geometry (LREQ-SMP-050; chunk-24 §2)
# --------------------------------------------------------------------------


@pytest.mark.lreq("LREQ-SMP-050")
@pytest.mark.lreq("LREQ-TST-020")
def test_stratum_member_ordinals_systematic_vector_at_101_offset_zero():
    """Fixture K: N = 101, offset 0 -> interleaved sets 26/25/25/25.

    Derivation (plan chunk-24 §2.1): stratum h holds the ascending i in 1..101
    with ``(i - 1 + offset) % stride == h``; at offset 0 that is
    ``i % 4 == h + 1``:
        h=0: 1,5,...,101 -> ((101 - 1) / 4) + 1 = 26 members
        h=1: 2,6,...,98  -> 25
        h=2: 3,7,...,99  -> 25
        h=3: 4,8,...,100 -> 25
    Total 26 + 25 + 25 + 25 = 101: a disjoint cover of 1..101, never four
    contiguous bands.
    """
    expected = fx.EXPECTED_MEMBER_ORDINALS_N101_OFFSET0
    # Frozen-literal sanity checks: hand-derived counts and endpoints.
    assert (len(expected[0]), expected[0][0], expected[0][-1]) == (26, 1, 101)
    assert (len(expected[1]), expected[1][0], expected[1][-1]) == (25, 2, 98)
    assert (len(expected[2]), expected[2][0], expected[2][-1]) == (25, 3, 99)
    assert (len(expected[3]), expected[3][0], expected[3][-1]) == (25, 4, 100)
    assert fx.expected_stratum_member_ordinals(101, 0, offset=0) == expected[0]

    rebuilt: list[int] = []
    for stratum_index, wanted in enumerate(expected):
        stratum = sampling.SamplingStratum(
            stratum_index=stratum_index,
            stratum_offset=0,
            stratum_stride=SAMPLE_STRATA,
            population_count=len(wanted),
            selected_count=min(SAMPLE_PER_STRATUM, len(wanted)),
            target_count=SAMPLE_PER_STRATUM,
            is_reduced=len(wanted) < SAMPLE_PER_STRATUM,
        )
        ordinals = sampling.stratum_member_ordinals(stratum, 101)
        assert ordinals == wanted
        rebuilt.extend(ordinals)
    assert sorted(rebuilt) == list(range(1, 102))


@pytest.mark.lreq("LREQ-SMP-050")
@pytest.mark.lreq("LREQ-TST-020")
def test_stratum_member_ordinals_systematic_vector_at_104_offset_zero():
    """N = 104, offset 0 -> four 26-member strata (plan §8 hand vector).

    Derivation: 104 = 4 * 26 exactly, so each residue class ``i % 4`` holds 26
    ordinals: 1,5,..,101; 2,6,..,102; 3,7,..,103; 4,8,..,104.
    """
    expected = fx.EXPECTED_MEMBER_ORDINALS_N104_OFFSET0
    assert tuple(len(group) for group in expected) == (26, 26, 26, 26)
    for stratum_index, wanted in enumerate(expected):
        stratum = sampling.SamplingStratum(
            stratum_index=stratum_index,
            stratum_offset=0,
            stratum_stride=SAMPLE_STRATA,
            population_count=26,
            selected_count=SAMPLE_PER_STRATUM,
            target_count=SAMPLE_PER_STRATUM,
            is_reduced=False,
        )
        assert sampling.stratum_member_ordinals(stratum, 104) == wanted
    assert fx.expected_stratum_member_ordinals(104, 0, offset=0) == expected[0]


@pytest.mark.lreq("LREQ-SMP-050")
def test_stratum_member_ordinals_shifted_offset_at_101():
    """N = 101, offset 1: the remainder moves to the stratum holding ordinal 1.

    Hand derivation (plan §2.1): stratum h holds i with
    ``(i - 1 + 1) % 4 == h``, i.e. ``i % 4 == h`` for h in 1..3 and
    ``i % 4 == 0`` for h = 0:
        h=0: 4,8,...,100 -> 25;  h=1: 1,5,...,101 -> 26;
        h=2: 2,6,...,98  -> 25;  h=3: 3,7,...,99  -> 25.
    The offset shifts membership; it never reorders the ordinals.
    """
    expected = fx.EXPECTED_MEMBER_ORDINALS_N101_OFFSET1
    assert tuple(len(group) for group in expected) == (25, 26, 25, 25)
    for stratum_index, wanted in enumerate(expected):
        stratum = sampling.SamplingStratum(
            stratum_index=stratum_index,
            stratum_offset=1,
            stratum_stride=SAMPLE_STRATA,
            population_count=len(wanted),
            selected_count=min(SAMPLE_PER_STRATUM, len(wanted)),
            target_count=SAMPLE_PER_STRATUM,
            is_reduced=len(wanted) < SAMPLE_PER_STRATUM,
        )
        assert sampling.stratum_member_ordinals(stratum, 101) == wanted


@pytest.mark.lreq("LREQ-SMP-050")
@pytest.mark.lreq("LREQ-TST-010")
def test_stratum_member_ordinals_zero_population_and_negative_size():
    """Zero population -> (); a negative population size raises ``ValueError``.

    Plan §6 contract: ``population_size == 0 -> ()`` and
    ``population_size < 0 -> ValueError``. Missing input is the empty tuple, an
    invalid one raises; neither is silently coerced.
    """
    census = sampling.SamplingStratum(
        stratum_index=0,
        stratum_offset=0,
        stratum_stride=1,
        population_count=0,
        selected_count=0,
        target_count=0,
        is_reduced=True,
    )
    assert sampling.stratum_member_ordinals(census, 0) == ()

    large = sampling.SamplingStratum(
        stratum_index=0,
        stratum_offset=0,
        stratum_stride=SAMPLE_STRATA,
        population_count=0,
        selected_count=0,
        target_count=SAMPLE_PER_STRATUM,
        is_reduced=True,
    )
    assert sampling.stratum_member_ordinals(large, 0) == ()
    with pytest.raises(ValueError):
        sampling.stratum_member_ordinals(large, -1)


@pytest.mark.lreq("LREQ-SMP-050")
@pytest.mark.lreq("LREQ-TST-020")
def test_systematic_partition_with_live_category_offset_at_101():
    """The N = 101 fixture partitions by the live category offset (A3).

    Plan §2.1/§2.2: ``stratum_index(i) = (i - 1 + offset) mod 4`` with the
    offset from the independently transcribed digest. Hand derivation:
    101 = 4 * 25 + 1, so the stratum holding ordinals 1 and 101 has 26 members
    and the other three have 25; every stratum selects min(25, N_h) = 25, so
    100 of 101 assets are selected and ``sample_fraction == 100/101``.
    """
    offset = fx.expected_stratum_offset(fx.OFFSET_RULE_VERSION, fx.LARGE_CATEGORY)
    result = sampling.select_category_sample(
        build_records(fx.large_101_records()), category=fx.LARGE_CATEGORY
    )
    assert result.sample_is_census is False
    assert result.sampling_basis == SamplingBasis.DETERMINISTIC_STRATIFIED_SAMPLE
    assert result.sampling_basis == "deterministic_stratified_sample"

    observed = tuple(
        (
            stratum.stratum_index,
            stratum.stratum_offset,
            stratum.stratum_stride,
            stratum.population_count,
            stratum.selected_count,
            stratum.is_reduced,
        )
        for stratum in result.strata
    )
    expected = tuple(
        (
            h,
            offset,
            SAMPLE_STRATA,
            26 if h == offset else 25,
            SAMPLE_PER_STRATUM,
            False,
        )
        for h in range(SAMPLE_STRATA)
    )
    assert observed == expected

    # Every member carries its stratum's (offset, stride) geometry unchanged.
    for member in result.members:
        assert member.stratum_offset == offset
        assert member.stratum_stride == SAMPLE_STRATA
    assert len(result.members) == 100
    assert result.enriched_sample_count == 100
    assert result.discovered_population_count == 101
    assert result.sample_fraction == pytest.approx(100 / 101, abs=1e-9)
    assert result.sample_fraction < 1.0


@pytest.mark.lreq("LREQ-SMP-050")
@pytest.mark.lreq("LREQ-TST-020")
@pytest.mark.parametrize("n", [101, 104, 105, 200, 1000])
def test_strata_are_a_disjoint_cover_of_the_ordinal_axis(n):
    """Every ordinal maps to exactly one stratum; the union is ``1..N``.

    Plan §2.1: "Every ``i`` maps to exactly one ``h``; the partition is a
    disjoint cover of ``1..N``." Size distribution is the quotient/remainder
    distribution of N over ``SAMPLE_STRATA``; because N >= 101 every stratum has
    at least 25 members, so ``is_reduced`` is False for every stratum and
    LREQ-SMP-090 reduction is unreachable on this branch. Hand-checked sizes:
        N = 101 -> {25, 26}   N = 104 -> {26}   N = 105 -> {26, 27}
        N = 200 -> {50}       N = 1000 -> {250}
    """
    result = sampling.select_category_sample(
        build_records(fx.population_records(n)), category=fx.LARGE_CATEGORY
    )
    offset = fx.expected_stratum_offset(fx.OFFSET_RULE_VERSION, fx.LARGE_CATEGORY)
    assert len(result.strata) == SAMPLE_STRATA
    union: list[int] = []
    for stratum in result.strata:
        ordinals = sampling.stratum_member_ordinals(stratum, n)
        assert list(ordinals) == sorted(ordinals)
        assert len(set(ordinals)) == len(ordinals)
        assert all(
            (i - 1 + offset) % SAMPLE_STRATA == stratum.stratum_index for i in ordinals
        )
        assert (stratum.stratum_offset, stratum.stratum_stride) == (
            offset,
            SAMPLE_STRATA,
        )
        assert stratum.population_count == len(ordinals)
        assert stratum.is_reduced is False
        assert stratum.target_count == SAMPLE_PER_STRATUM
        assert stratum.selected_count == SAMPLE_PER_STRATUM
        union.extend(ordinals)
    assert sorted(union) == list(range(1, n + 1))
    sizes = {
        len(sampling.stratum_member_ordinals(stratum, n)) for stratum in result.strata
    }
    assert sizes == {n // SAMPLE_STRATA, -(-n // SAMPLE_STRATA)}
    assert len(result.members) == SAMPLE_STRATA * SAMPLE_PER_STRATUM == 100


@pytest.mark.lreq("LREQ-SMP-050")
def test_large_category_targets_25_per_stratum():
    """Every non-reduced stratum selects exactly ``SAMPLE_PER_STRATUM`` (25).

    Plan §2.1: for N >= 101 every stratum has at least 25 members, so
    ``is_reduced`` is False for every large-category stratum and each selects
    the fixed 25.
    """
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
# Offset derivation (LREQ-SMP-050; plan §2.2, OQ-2/OQ-3)
# --------------------------------------------------------------------------


@pytest.mark.lreq("LREQ-SMP-050")
@pytest.mark.lreq("LREQ-TST-010")
def test_category_stratum_offset_matches_independent_formula_and_range():
    """A3: offset = int.from_bytes(sha256(utf8(v + NUL + category))[:8]) % 4.

    Plan §2.2/§8.2. Expected values come from the independent transcription in
    ``fixtures.sampling_fixtures.expected_stratum_offset`` (hashlib only; the
    module under test is not imported there). The capture command the plan
    requires for the concrete literals is recorded verbatim in the fixture:

        fx.STRATUM_OFFSET_CAPTURE_COMMAND

    Hand-checkable properties asserted here: every value is in 0..3 (the
    SAMPLE_STRATA range), repeated calls are identical, the default version is
    the live models constant, and distinct categories do not all collapse to a
    single bucket. The lead-captured literals in ``FROZEN_OFFSET_LITERALS``
    (Textures/Materials -> 0, 3D/Characters -> 2, 2d/gui/icons -> 1,
    vfx/particles/spells -> 0) are asserted directly against the module.
    """
    for category in fx.OFFSET_VARIATION_CATEGORIES:
        actual = sampling.category_stratum_offset(
            category, sampling_rule_version=fx.OFFSET_RULE_VERSION
        )
        assert 0 <= actual < SAMPLE_STRATA
        assert actual == fx.expected_stratum_offset(fx.OFFSET_RULE_VERSION, category)
        assert actual == sampling.category_stratum_offset(
            category, sampling_rule_version=fx.OFFSET_RULE_VERSION
        )

    assert fx.OFFSET_RULE_VERSION == SAMPLING_RULE_VERSION == "2.0.0"

    # Frozen literals captured by the lead with the recorded independent
    # one-liner (plan §8.2); each is asserted directly, not only via the
    # transcription.
    for category, captured in fx.FROZEN_OFFSET_LITERALS:
        assert captured == fx.expected_stratum_offset(fx.OFFSET_RULE_VERSION, category)
        assert (
            sampling.category_stratum_offset(
                category, sampling_rule_version=fx.OFFSET_RULE_VERSION
            )
            == captured
        )
    assert (
        sampling.category_stratum_offset(fx.LARGE_CATEGORY)
        == fx.EXPECTED_OFFSET_LARGE_CATEGORY
        == 0
    )

    observed = {
        sampling.category_stratum_offset(
            category, sampling_rule_version=fx.OFFSET_RULE_VERSION
        )
        for category in fx.OFFSET_VARIATION_CATEGORIES
    }
    assert len(observed) >= 2, (
        "distinct categories must be able to land in different strata"
    )


@pytest.mark.lreq("LREQ-SMP-050")
@pytest.mark.lreq("LREQ-TST-010")
def test_category_stratum_offset_rejects_malformed_category():
    """A non-str or empty/whitespace-only category raises ``ValueError``.

    Plan §6: the offset "Raises ValueError for a non-str or empty/whitespace-only
    category"; an empty category is never a shared offset bucket.
    """
    for bad_category in (*fx.malformed_category_values(), None, 3, b"bytes", ["x"]):
        with pytest.raises(ValueError):
            sampling.category_stratum_offset(bad_category)


@pytest.mark.lreq("LREQ-SMP-050")
@pytest.mark.lreq("LREQ-SMP-030")
def test_build_strata_offset_is_always_reduced_mod_sample_strata():
    """A non-default ``sample_strata`` changes the stride, not the offset modulus.

    Plan §6 (OQ-3): the offset is always reduced ``mod SAMPLE_STRATA``; a
    non-default ``sample_strata`` is a test-only override and never a production
    path.
    """
    population = sampling.build_canonical_population(
        build_records(fx.large_200_records()), category=fx.LARGE_CATEGORY
    )
    expected_offset = fx.expected_stratum_offset(
        fx.OFFSET_RULE_VERSION, fx.LARGE_CATEGORY
    )
    strata = sampling.build_strata(
        population,
        sample_strata=2,
        sampling_rule_version=fx.OFFSET_RULE_VERSION,
    )
    assert len(strata) == 2
    union: list[int] = []
    for stratum in strata:
        assert stratum.stratum_stride == 2
        assert stratum.stratum_offset == expected_offset
        union.extend(sampling.stratum_member_ordinals(stratum, 200))
    assert sorted(union) == list(range(1, 201))


@pytest.mark.lreq("LREQ-SMP-050")
@pytest.mark.lreq("LREQ-TST-010")
def test_build_strata_rejects_non_positive_parameters():
    """``sample_strata < 1`` or ``per_stratum_target < 1`` raises ``ValueError``.

    Plan §6 contract; the same test covers the empty population's valid zero
    result (``build_strata(empty) == ()``).
    """
    population = sampling.build_canonical_population(
        build_records(fx.large_101_records()), category=fx.LARGE_CATEGORY
    )
    for overrides in (
        {"sample_strata": 0},
        {"sample_strata": -1},
        {"per_stratum_target": 0},
        {"per_stratum_target": -1},
    ):
        with pytest.raises(ValueError):
            sampling.build_strata(population, **overrides)

    empty = sampling.build_canonical_population((), category=fx.CATEGORY)
    assert sampling.build_strata(empty) == ()


# --------------------------------------------------------------------------
# Public surface contract (LREQ-NFR-040; plan §6)
# --------------------------------------------------------------------------


@pytest.mark.lreq("LREQ-NFR-040")
def test_sampling_systematic_surface_has_docstrings_and_frozen_fields():
    """The plan §6 typed contract: docstrings and exact public field lists.

    LREQ-NFR-040 requires type hints plus docstrings; the chunk-24 pure surface
    must expose exactly the fields of plan §6 -- the interval fields are gone.
    """
    import dataclasses
    import inspect

    for function in (
        sampling.category_stratum_offset,
        sampling.stratum_member_ordinals,
        sampling.build_strata,
        sampling.select_stratum_members,
    ):
        assert function.__doc__, f"{function.__name__} must have a docstring"
        assert function.__annotations__, f"{function.__name__} must be annotated"

    offset_parameters = inspect.signature(sampling.category_stratum_offset).parameters
    assert list(offset_parameters) == ["category", "sampling_rule_version"]

    membership_parameters = inspect.signature(
        sampling.stratum_member_ordinals
    ).parameters
    assert list(membership_parameters) == ["stratum", "population_size"]

    build_parameters = inspect.signature(sampling.build_strata).parameters
    assert list(build_parameters) == [
        "population",
        "sample_strata",
        "per_stratum_target",
        "census_threshold",
        "sampling_rule_version",
    ]

    select_parameters = inspect.signature(sampling.select_stratum_members).parameters
    assert list(select_parameters) == [
        "population",
        "stratum",
        "sample_is_census",
        "sampling_rule_version",
    ]

    stratum_fields = [
        field.name for field in dataclasses.fields(sampling.SamplingStratum)
    ]
    assert stratum_fields == [
        "stratum_index",
        "stratum_offset",
        "stratum_stride",
        "population_count",
        "selected_count",
        "target_count",
        "is_reduced",
    ]
    member_fields = [field.name for field in dataclasses.fields(sampling.SampledMember)]
    assert member_fields == [
        "category",
        "asset_identity_key",
        "stratum_index",
        "stratum_offset",
        "stratum_stride",
        "sample_rank_within_stratum",
        "sample_is_census",
        "selection_digest",
    ]


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
@pytest.mark.lreq("LREQ-TST-020")
def test_reduced_stratum_selects_all_and_reports_reduced_count():
    """Fixture D: a stratum below 25 selects all and reports the reduced count.

    SRS §5.1 LREQ-SMP-090; plan chunk-24 §2.3 keeps the reduced rule and makes
    it reachable only through the census branch (every large-category stratum
    has at least 25 members because N >= 101). Census geometry is
    ``(stratum_offset, stratum_stride) = (0, 1)``, so its member ordinals are
    1..N. N = 24 -> one stratum, target 24, reduced; N = 25 -> target 25, not
    reduced; N = 1 -> target 1, reduced. N = 105 companion: 105 = 4 * 26 + 1,
    so the stratum holding ordinal 1 has 27 members and the other three 26;
    all are >= 25, so none is reduced and each selects 25.
    """
    reduced_24 = sampling.select_category_sample(
        build_records(fx.census_24_records()), category=fx.CATEGORY
    )
    assert len(reduced_24.strata) == 1
    stratum = reduced_24.strata[0]
    assert (
        stratum.stratum_index,
        stratum.stratum_offset,
        stratum.stratum_stride,
    ) == (0, 0, 1)
    assert stratum.population_count == 24
    assert stratum.target_count == 24
    assert stratum.selected_count == 24
    assert stratum.is_reduced is True
    assert sampling.stratum_member_ordinals(stratum, 24) == tuple(range(1, 25))
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
    assert (single.strata[0].stratum_offset, single.strata[0].stratum_stride) == (0, 1)
    assert single.strata[0].target_count == 1
    assert single.strata[0].is_reduced is True

    large_105 = sampling.select_category_sample(
        build_records(fx.large_105_records()), category=fx.LARGE_CATEGORY
    )
    offset = fx.expected_stratum_offset(fx.OFFSET_RULE_VERSION, fx.LARGE_CATEGORY)
    sizes = [large_stratum.population_count for large_stratum in large_105.strata]
    assert sorted(sizes) == [26, 26, 26, 27]
    # Ordinals 1 and 105 share residue 1 -> they sit in stratum ``offset``.
    assert sizes[offset] == 27
    for large_stratum in large_105.strata:
        assert (
            large_stratum.stratum_offset,
            large_stratum.stratum_stride,
        ) == (offset, SAMPLE_STRATA)
        assert large_stratum.population_count == len(
            sampling.stratum_member_ordinals(large_stratum, 105)
        )
        assert large_stratum.is_reduced is False
        assert large_stratum.selected_count == 25


# --------------------------------------------------------------------------
# Position coverage (LREQ-SMP-070; plan chunk-24 §7.5 structural assertion)
# --------------------------------------------------------------------------


@pytest.mark.lreq("LREQ-SMP-070")
@pytest.mark.lreq("LREQ-TST-020")
@pytest.mark.parametrize("n", [101, 104, 200])
def test_early_middle_late_positions_represented(n):
    """Every stratum's membership intersects the early, middle, and late ranges.

    SRS §5.1 LREQ-SMP-070 requires early/middle/late discovery positions; plan
    chunk-24 §7.5/OQ-6 freezes the assertion as STRUCTURAL: for each stratum,
    its member ordinals must intersect the first, middle, and last third of the
    1..N ordinal axis. No minimum span and no quantitative threshold is
    asserted -- only intersection.

    Derivation: contiguous members of a systematic stratum are exactly stride 4
    apart, and each third spans at least 33 ordinals at these N, so every
    stratum intersects every third regardless of the category offset. An
    interleaved set cannot be confined to one contiguous band.
    """
    third = n // 3
    windows = (
        ("early", range(1, third + 1)),
        ("middle", range(third + 1, 2 * third + 1)),
        ("late", range(2 * third + 1, n + 1)),
    )
    result = sampling.select_category_sample(
        build_records(fx.population_records(n)), category=fx.LARGE_CATEGORY
    )
    for stratum in result.strata:
        ordinals = set(sampling.stratum_member_ordinals(stratum, n))
        for label, window in windows:
            assert ordinals & set(window), (
                f"stratum {stratum.stratum_index} misses the {label} range at N={n}"
            )


@pytest.mark.lreq("LREQ-SMP-070")
def test_sample_is_not_first_page_prefix():
    """The N = 101 selection is not confined to a first-results prefix.

    SRS §5.1 LREQ-SMP-070: selecting only the first page or the first 100
    results is non-conforming. Hand derivation from the partition (plan §2.1):
    with N = 101 the strata hold 26/25/25/25 and every stratum selects
    min(25, N_h); the three 25-member strata select ALL their members. Ordinals
    2, 3 and 4 have residues distinct from the offset residue, so they sit in
    those full strata and are always selected -> min <= 4. Ordinals 98, 99 and
    100 likewise sit in the three full strata -> max >= 100. The first page is
    96 results and the selection has 100 members, so it cannot be first-page
    only either.
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
    assert min(selected_ordinals) <= 4
    assert max(selected_ordinals) >= 100


# --------------------------------------------------------------------------
# Basis / census flag and non-configurability (LREQ-SMP-030, LREQ-SMP-040)
# --------------------------------------------------------------------------


@pytest.mark.lreq("LREQ-SMP-030", "LREQ-SMP-040")
@pytest.mark.lreq("LREQ-TST-020")
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
    assert (
        models.ENRICHMENT_SAMPLE_SIZE_PER_CATEGORY
        == models.SAMPLE_STRATA * models.SAMPLE_PER_STRATUM
    )

    # The sampling module re-exports the same frozen values.
    assert (
        sampling.ENRICHMENT_SAMPLE_SIZE_PER_CATEGORY
        == ENRICHMENT_SAMPLE_SIZE_PER_CATEGORY
    )
    assert sampling.SAMPLE_STRATA == SAMPLE_STRATA
    assert sampling.SAMPLE_PER_STRATUM == SAMPLE_PER_STRATUM
    assert sampling.SAMPLING_RULE_VERSION == SAMPLING_RULE_VERSION == "2.0.0"
    assert (
        sampling.CENSUS_POPULATION_THRESHOLD
        == ENRICHMENT_SAMPLE_SIZE_PER_CATEGORY
        == 100
    )
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
    assert (
        build_strata_parameters["census_threshold"].default
        == ENRICHMENT_SAMPLE_SIZE_PER_CATEGORY
    )


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
@pytest.mark.lreq("LREQ-TST-020")
def test_no_duplicate_membership_within_category():
    """Members within one category are identity-unique.

    SRS §5.1 LREQ-SMP-010/020: the population is identity-unique and selection
    draws from it once.
    """
    for records in (
        fx.census_100_records(),
        fx.large_101_records(),
        fx.exclusion_records(),
    ):
        result = sampling.select_category_sample(
            build_records(records), category=fx.CATEGORY
        )
        keys = [m.asset_identity_key for m in result.members]
        assert len(keys) == len(set(keys))
        assert len(result.population.identity_keys) == len(
            set(result.population.identity_keys)
        )


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
@pytest.mark.lreq("LREQ-TST-020")
def test_sample_fraction_distinct_from_stratum_aggregates():
    """``sample_fraction`` is its own field; no coverage or usable count emitted.

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
            "stratum_offset",
            "stratum_stride",
            "sample_rank_within_stratum",
            "sample_is_census",
            "selection_digest",
        ):
            assert hasattr(member, name), f"member missing persistence field {name}"


# --------------------------------------------------------------------------
# Census member ranking and digest (Q-5, Q-6 rulings)
# --------------------------------------------------------------------------


@pytest.mark.lreq("LREQ-SMP-060")
@pytest.mark.lreq("LREQ-TST-020")
def test_census_member_ranks_follow_digest_order():
    """Census ``sample_rank_within_stratum`` is 1-based in ``(digest, key)`` order.

    Plan §5.3 Q-6 ruling: census ranks follow the digest sort exactly as sampled
    ranks do, not the original discovery order.
    """
    result = sampling.select_category_sample(
        build_records(fx.census_100_records()), category=fx.CATEGORY
    )
    for stratum in result.strata:
        members = [
            m for m in result.members if m.stratum_index == stratum.stratum_index
        ]
        assert [m.sample_rank_within_stratum for m in members] == list(
            range(1, len(members) + 1)
        )
        ordered = sorted(
            members, key=lambda m: (m.selection_digest, m.asset_identity_key)
        )
        assert [m.asset_identity_key for m in members] == [
            m.asset_identity_key for m in ordered
        ]
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
            category,
            member.asset_identity_key,
            sampling_rule_version=SAMPLING_RULE_VERSION,
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

    NOT an analytical test: deliberately no ``@pytest.mark.lreq`` and no
    ``tests/traceability.json`` entry (plan §9.3).
    """
    tree = ast.parse(
        SAMPLING_SOURCE.read_text(encoding="utf-8"), filename=str(SAMPLING_SOURCE)
    )

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
            (
                isinstance(node.value, ast.Name)
                and node.value.id in {"datetime", "date", "time", "dt"}
            )
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
