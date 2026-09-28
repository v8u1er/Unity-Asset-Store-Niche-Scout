"""Inert fixtures and hand-derived golden vectors for chunk 4A sampling tests.

Data and factory functions only: this module contains no assertions and no
logic under test, so a defect in it cannot mask a sampling defect.

Sources:
- SRS-lean.md §5.1 (LREQ-SMP-010/020/030/040/050/060/070/080/090).
- Documents/plans/chunk-4A-canonical-populations-and-deterministic-sampling.md
  §5 (interface contract), §5.2 (input contract), §9.2 (golden vectors),
  §9.5 (fixture inventory).
- Documents/plans/chunk-24-systematic-strata.md §2 (systematic partition and
  A3 offset), §6 (typed pure contract), §8.2 (offset capture and membership
  vectors). The contiguous-boundary vectors of chunk 4A are retired; the
  membership vectors below are the chunk-24 golden vectors.

No credentials, no network, no clock reads, no file I/O.
"""

from __future__ import annotations

import hashlib

# --------------------------------------------------------------------------
# SRS-pinned constants (SRS §5.1, LREQ-SMP-030). Mirrored as literals only to
# size fixtures; the tests compare against ``models`` for the live values.
# --------------------------------------------------------------------------

SAMPLE_STRATA = 4
SAMPLE_PER_STRATUM = 25
CENSUS_POPULATION_THRESHOLD = 100

CATEGORY = "3D/Characters"
LARGE_CATEGORY = "Textures/Materials"

#: Fixture F pins this category/key/rule-version triple to a frozen digest.
DIGEST_FIXTURE_CATEGORY = "3D/Characters"
DIGEST_FIXTURE_KEY = "12345"
DIGEST_FIXTURE_RULE_VERSION = "1.0.0"

# --------------------------------------------------------------------------
# Fixture F — the digest literal (SRS §5.1 LREQ-SMP-060)
# --------------------------------------------------------------------------
#
# Hand derivation from the SRS formula
#     s = f"{rule_version}\0{category}\0{asset_identity_key}".encode("utf-8")
#     digest = hashlib.sha256(s).hexdigest()
#
# The exact byte string hashed is the 25-byte ASCII sequence:
#     b"1.0.0" + b"\x00" + b"3D/Characters" + b"\x00" + b"12345"
# (5 + 1 + 13 + 1 + 5 = 25 bytes; ASCII, so UTF-8 is the identity encoding).
#
# The frozen 64-char lowercase-hex literal was computed by the test author with
# ``hashlib.sha256`` over exactly the bytes in ``DIGEST_F_BYTES``; the
# implementation must reproduce it character-for-character. This pins the NUL
# delimiter and the UTF-8 encoding and nothing else.
DIGEST_F_BYTES: bytes = b"1.0.0\x003D/Characters\x0012345"
#: Cross-check snapshot computed at test-authoring time over DIGEST_F_BYTES,
#: via ``hashlib.sha256`` on the 25 bytes. This literal is the frozen expected
#: value the implementation must reproduce character-for-character.
DIGEST_F_HEX: str = "20c3b87100bb44ce9c198328ef98b894e0773afb4f03ff99ed3f7cc1439feebb"

# --------------------------------------------------------------------------
# Fixture G — shared identity across two categories (LREQ-SMP-010; plan §9.2)
# --------------------------------------------------------------------------

SHARED_IDENTITY_KEY = "shared-asset-1"
SHARED_CATEGORY_A = "Overlap/A"
SHARED_CATEGORY_B = "Overlap/B"


def record(discovery_ordinal, asset_identity_key, is_duplicate=False) -> dict:
    """Return one inert observation mapping for ``DiscoveryPopulationRecord``.

    The tests convert these mappings with a single ``DiscoveryPopulationRecord(
    **mapping)`` call, exactly as the production caller projects a persisted row.
    """
    return {
        "discovery_ordinal": discovery_ordinal,
        "asset_identity_key": asset_identity_key,
        "is_duplicate": is_duplicate,
    }


def population_records(
    n: int,
    *,
    prefix: str = "asset",
    first_ordinal: int = 0,
    key_width: int = 4,
) -> tuple:
    """Return ``n`` distinct canonical records with ordinals ``first_ordinal..``.

    Ordinals are 0-based and ascending, one per record, as Chunk 3 assigns them
    (SRS §5.1 LREQ-SMP-020; interfaces/chunk-03.md §6). Keys are
    ``f"{prefix}-{i:0{key_width}d}"`` for ``i`` in ``0..n-1``. No record is a
    duplicate and every record carries a non-None identity key.
    """
    return tuple(
        record(first_ordinal + i, f"{prefix}-{i:0{key_width}d}", False)
        for i in range(n)
    )


def census_zero_records() -> tuple:
    """Fixture A: ``N == 0`` — no observations at all."""
    return ()


def census_one_records() -> tuple:
    """Fixture A: ``N == 1`` — ordinals ``0..0``."""
    return population_records(1)


def census_99_records() -> tuple:
    """Fixture A: ``N == 99`` — ordinals ``0..98``."""
    return population_records(99)


def census_100_records() -> tuple:
    """Fixture A: ``N == 100`` — the last census population, ordinals ``0..99``."""
    return population_records(100)


def large_101_records() -> tuple:
    """Fixture B: ``N == 101``, first four-stratum population (ordinals 0..100)."""
    return population_records(101)


def large_200_records() -> tuple:
    """Fixture C: ``N == 200``, equal 50-asset strata (ordinals 0..199)."""
    return population_records(200)


def census_24_records() -> tuple:
    """Fixture D: ``N == 24`` census below ``SAMPLE_PER_STRATUM`` (reduced)."""
    return population_records(24)


def census_25_records() -> tuple:
    """Fixture D companion: ``N == 25`` — exactly one target, not reduced."""
    return population_records(25)


def large_105_records() -> tuple:
    """Fixture D companion: ``N == 105``; boundaries 1..26/27..52/53..78/79..105."""
    return population_records(105)


def exclusion_records() -> tuple:
    """Fixture H — exclusions and collapse (SRS §5.1 LREQ-SMP-020; plan §5.2).

    Records in persisted discovery order (ordinals 0..6):

    - ordinal 0: ``keep-0`` — canonical, retained.
    - ordinal 1: ``keep-1`` — canonical, retained.
    - ordinal 2: ``asset_identity_key is None`` — unresolved *or* conflict; both
      are persisted with a null key and are excluded (LREQ-SMP-010; Q-2 ruling:
      one ``excluded_unresolved_count`` field).
    - ordinal 3: ``keep-0`` flagged ``is_duplicate=True`` — excluded and counted
      in ``excluded_duplicate_count``.
    - ordinal 4: null key *and* ``is_duplicate=True`` — the null key dominates;
      counted in ``excluded_unresolved_count`` (plan §5.2 exclusion order).
    - ordinal 5: ``keep-2`` — new identity, retained.
    - ordinal 6: ``keep-0`` again with ``is_duplicate=False`` — a repeated
      identity whose first valid ordinal (0) is retained; counted in
      ``collapsed_repeat_count``.

    Hand-derived expected population: keys ``("keep-0", "keep-1", "keep-2")``,
    retained ordinals ``(0, 1, 5)``, ``size == 3``,
    ``excluded_unresolved_count == 2``, ``excluded_duplicate_count == 1``,
    ``collapsed_repeat_count == 1``.
    """
    return (
        record(0, "keep-0", False),
        record(1, "keep-1", False),
        record(2, None, False),
        record(3, "keep-0", True),
        record(4, None, True),
        record(5, "keep-2", False),
        record(6, "keep-0", False),
    )


def repeated_identity_lowest_ordinal_records() -> tuple:
    """A repeat with no duplicate flag keeps the lowest ordinal (LREQ-SMP-020).

    Input order is deliberately high-ordinal first, so an implementation that
    merely preserves input order fails: the retained ordinal must be 2, not 7,
    and the output must be ordered by retained ordinal.
    """
    return (
        record(7, "repeat-key", False),
        record(2, "repeat-key", False),
    )


def overlap_category_a_records() -> tuple:
    """Fixture G category A: the shared identity plus one distinct identity."""
    return (
        record(0, SHARED_IDENTITY_KEY, False),
        record(1, "a-only-1", False),
    )


def overlap_category_b_records() -> tuple:
    """Fixture G category B: the same shared identity plus two distinct ones."""
    return (
        record(0, "b-only-1", False),
        record(1, SHARED_IDENTITY_KEY, False),
        record(2, "b-only-2", False),
    )


def run_categories_mapping() -> dict:
    """Fixture G input: category -> records, in caller order B then A.

    Insertion order is deliberately *not* lexical (``Overlap/B`` before
    ``Overlap/A``) so ``select_run_sample``'s order preservation is observable
    (Q-7 ruling; plan §5.4).
    """
    return {
        SHARED_CATEGORY_B: overlap_category_b_records(),
        SHARED_CATEGORY_A: overlap_category_a_records(),
    }


# --------------------------------------------------------------------------
# Fixture J — malformed inputs (plan §5.2 / §9.2)
# --------------------------------------------------------------------------


def malformed_category_values() -> tuple:
    """Empty and whitespace-only category strings (never a shared bucket)."""
    return ("", " ", "\t", "\n", "   \t  ")


def malformed_ordinal_values() -> tuple:
    """Negative, boolean, and non-int ordinals (must raise ``ValueError``)."""
    return (-1, -100, True, False, 1.0, "3", None)


def malformed_identity_values() -> tuple:
    """Empty and whitespace-only identity keys (never silently kept or dropped)."""
    return ("", " ", "\t", "\n", "   ")


# --------------------------------------------------------------------------
# Systematic-partition helpers and golden membership vectors
# (plan chunk-24 §2 and §8.2; supersedes the chunk-4A contiguous boundaries).
#
# The helpers restate the plan chunk-24 §2 formulas independently of
# ``niche_scout.sampling``; a defect in the module under test cannot hide
# behind them. The frozen tuples below are hand-derived from the formula and
# are the assertions' source of truth.
# --------------------------------------------------------------------------

#: The ``SAMPLING_RULE_VERSION`` value frozen by chunk-24 (plan §3.1, OQ-2).
#: It is an input to the offset digest, so every offset depends on it.
OFFSET_RULE_VERSION = "2.0.0"

#: Independent A3 capture command (plan §8.2) for the concrete
#: ``(sampling_rule_version, category)`` pair below. Run it from the
#: repository root; ``chr(0)`` is the NUL delimiter and the digest's first
#: eight bytes are read big-endian, then reduced mod SAMPLE_STRATA.
#: The one-line form (copy verbatim):
#: python -c "import hashlib; v='2.0.0'; c='Textures/Materials'; print(int.from_bytes(hashlib.sha256((v+chr(0)+c).encode('utf-8')).digest()[:8], 'big') % 4)"
STRATUM_OFFSET_CAPTURE_COMMAND: str = (
    "python -c \"import hashlib; v='2.0.0'; c='Textures/Materials'; "
    "print(int.from_bytes(hashlib.sha256((v+chr(0)+c).encode('utf-8')).digest()[:8], 'big') % 4)\""
)

#: Frozen A3 offset literals captured by the LEAD with the exact command above
#: (same payload, ``c`` = the category shown). Recorded from the independent
#: one-liner, never from the module under test:
#:   Textures/Materials   -> 0   (STRATUM_OFFSET_CAPTURE_COMMAND)
#:   3D/Characters        -> 2
#:   2d/gui/icons         -> 1
#:   vfx/particles/spells -> 0
FROZEN_OFFSET_LITERALS: tuple[tuple[str, int], ...] = (
    ("Textures/Materials", 0),
    ("3D/Characters", 2),
    ("2d/gui/icons", 1),
    ("vfx/particles/spells", 0),
)

#: The captured offset for the large fixture category (plan §8.2 concrete
#: value), asserted as a literal by the tests, not recomputed by the module.
EXPECTED_OFFSET_LARGE_CATEGORY = 0


def expected_stratum_offset(sampling_rule_version: str, category: str) -> int:
    """Restate the plan chunk-24 §2.2 (A3) offset independently.

    ``offset = int.from_bytes(sha256(utf8(version + NUL + category)).digest()
    [:8], "big") % SAMPLE_STRATA`` -- hashlib only; ``niche_scout.sampling`` is
    never imported here. The payload is exactly two values (version, category);
    the category bytes are used verbatim as UTF-8 with no casing step.
    """
    payload = (sampling_rule_version + "\x00" + category).encode("utf-8")
    return int.from_bytes(hashlib.sha256(payload).digest()[:8], "big") % SAMPLE_STRATA


#: Categories used to prove that distinct categories can land in different
#: strata: the four captured-literal categories plus 24 generated names, so
#: distinct categories are known to differ (see FROZEN_OFFSET_LITERALS:
#: 0/2/1/0 are not all equal).
OFFSET_VARIATION_CATEGORIES: tuple[str, ...] = (
    CATEGORY,
    LARGE_CATEGORY,
    "2d/gui/icons",
    "vfx/particles/spells",
    *(f"Offset/Variation-{index:02d}" for index in range(24)),
)


def expected_stratum_member_ordinals(
    population_size: int,
    stratum_index: int,
    *,
    offset: int,
    stride: int = SAMPLE_STRATA,
) -> tuple[int, ...]:
    """Restate plan chunk-24 §2.1: ascending ``i`` in 1..N with
    ``(i - 1 + offset) % stride == stratum_index`` (the census encoding is
    ``stride == 1``)."""
    return tuple(
        ordinal
        for ordinal in range(1, population_size + 1)
        if (ordinal - 1 + offset) % stride == stratum_index
    )


#: N = 101, offset = 0, stride = 4. Hand derivation (plan §2.1): stratum h
#: holds i with (i - 1) % 4 == h, i.e. i % 4 == h + 1:
#:   h=0: 1,5,...,101 -> ((101 - 1) / 4) + 1 = 26 members
#:   h=1: 2,6,...,98  -> 25
#:   h=2: 3,7,...,99  -> 25
#:   h=3: 4,8,...,100 -> 25
#: Total 26 + 25 + 25 + 25 = 101: a disjoint cover of 1..101.
EXPECTED_MEMBER_ORDINALS_N101_OFFSET0: tuple[tuple[int, ...], ...] = (
    tuple(range(1, 102, 4)),
    tuple(range(2, 99, 4)),
    tuple(range(3, 100, 4)),
    tuple(range(4, 101, 4)),
)

#: N = 104, offset = 0, stride = 4. Hand derivation: 104 = 4 * 26 exactly, so
#: each residue class i % 4 holds 26 ordinals:
#: 1,5,...,101; 2,6,...,102; 3,7,...,103; 4,8,...,104.
EXPECTED_MEMBER_ORDINALS_N104_OFFSET0: tuple[tuple[int, ...], ...] = (
    tuple(range(1, 105, 4)),
    tuple(range(2, 106, 4)),
    tuple(range(3, 107, 4)),
    tuple(range(4, 108, 4)),
)

#: N = 101, offset = 1, stride = 4. Hand derivation: stratum h holds i with
#: (i - 1 + 1) % 4 == h, i.e. i % 4 == h for h in 1..3 and i % 4 == 0 for h=0:
#:   h=0: 4,8,...,100 -> 25;  h=1: 1,5,...,101 -> 26;
#:   h=2: 2,6,...,98  -> 25;  h=3: 3,7,...,99  -> 25.
EXPECTED_MEMBER_ORDINALS_N101_OFFSET1: tuple[tuple[int, ...], ...] = (
    tuple(range(4, 101, 4)),
    tuple(range(1, 102, 4)),
    tuple(range(2, 99, 4)),
    tuple(range(3, 100, 4)),
)


def expected_digest(rule_version: str, category: str, asset_identity_key: str) -> str:
    """Restate the SRS §5.1 LREQ-SMP-060 digest formula independently."""
    raw = f"{rule_version}\x00{category}\x00{asset_identity_key}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
