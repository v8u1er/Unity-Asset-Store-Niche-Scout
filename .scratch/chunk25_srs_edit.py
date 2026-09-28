#!/usr/bin/env python
"""Apply chunk-25 SRS edits S1-S5 to Documents/SRS-lean-v2.md.

Bounded, byte-exact replacement: asserts each pattern occurs exactly once,
preserves LF line endings and UTF-8 (no BOM) encoding, and aborts without
writing if any assertion fails. Header block for `.scratch/README.md`.

Usage: python .scratch/chunk25_srs_edit.py
"""

from __future__ import annotations

import hashlib
import pathlib
import sys

SRS = pathlib.Path("Documents/SRS-lean-v2.md")

EDITS: tuple[tuple[str, str], ...] = (
    # S1: §5.1 LREQ-SMP-030 constant block.
    ("MIN_USABLE_SAMPLES_PER_STRATUM = 5\n", "MIN_USABLE_SAMPLES_PER_STRATUM = 1\n"),
    # S2: §14 configuration-reference row.
    (
        "| `MIN_USABLE_SAMPLES_PER_STRATUM` | 5 | Yes | Stratum evidence minimum. |",
        "| `MIN_USABLE_SAMPLES_PER_STRATUM` | 1 | Yes | Stratum evidence minimum. |",
    ),
    # S4a: header version.
    ("| Version | Lean 1.0.2 |", "| Version | Lean 1.0.3 |"),
    # S4b: status line.
    (
        "| Status | Decision-grade lean variant (v2; supersedes `SRS-lean.md`) |",
        "| Status | Decision-grade lean variant (v2; supersedes `SRS-lean.md`) |".replace(
            "v2;", "v2, Lean 1.0.3;"
        ),
    ),
    # S4c: document-status paragraph — extend the rationale to 1.0.3.
    (
        "behavioral change in Lean 1.0.2 is the systematic (interleaved) sampling-stratum\n"
        "geometry and its persistence representation (`LREQ-SMP-050`, `LREQ-SMP-080`, §1.4,\n"
        "§5.1, §6.3, §14); all other Lean 1.0.1 requirement text is carried forward\n"
        "unchanged.",
        "behavioral change in Lean 1.0.2 is the systematic (interleaved) sampling-stratum\n"
        "geometry and its persistence representation (`LREQ-SMP-050`, `LREQ-SMP-080`, §1.4,\n"
        "§5.1, §6.3, §14); all other Lean 1.0.1 requirement text is carried forward\n"
        "unchanged. Lean 1.0.3 supersedes Lean 1.0.2 and changes exactly one default:\n"
        "`MIN_USABLE_SAMPLES_PER_STRATUM` is lowered from 5 to 1 (§5.1, §14), which\n"
        "re-baselines per-stratum usability, the three stratum eligibility coverages, the\n"
        "usable component sample counts, evidence grades, and rankability for runs scored\n"
        "under the default policy. No formula, weight, partition rule, or other constant\n"
        "changes.",
    ),
    # S3: revision-history row appended after the Lean 1.0.2 row.
    (
        "| Lean 1.0.2 | Replaces the four contiguous ordinal strata of `LREQ-SMP-050` "
        "with a systematic (interleaved) partition over the same stable discovery ordinal "
        "(deterministic per-category offset; `stratum_index(i) = (i - 1 + offset) mod "
        "SAMPLE_STRATA`), and changes the persisted stratum geometry from an ordinal "
        "interval to `(offset, stride)`. All other Lean 1.0.1 behavior is unchanged. |\n",
        "| Lean 1.0.2 | Replaces the four contiguous ordinal strata of `LREQ-SMP-050` "
        "with a systematic (interleaved) partition over the same stable discovery ordinal "
        "(deterministic per-category offset; `stratum_index(i) = (i - 1 + offset) mod "
        "SAMPLE_STRATA`), and changes the persisted stratum geometry from an ordinal "
        "interval to `(offset, stride)`. All other Lean 1.0.1 behavior is unchanged. |\n"
        "| Lean 1.0.3 | Lowers the default `MIN_USABLE_SAMPLES_PER_STRATUM` from 5 to 1 "
        "(§5.1, §14), re-baselining per-stratum usability, the three stratum eligibility "
        "coverages, the usable component sample counts, evidence grades, and rankability "
        "for runs scored under the default policy. The constant remains Configurable = Yes "
        "and no formula, weight, partition rule, or other constant changes. |\n",
    ),
    # S5: §5.1 inclusive-floor sentence after the constant block.
    (
        "ENRICHMENT_SAMPLE_SIZE_PER_CATEGORY = SAMPLE_STRATA * SAMPLE_PER_STRATUM\n"
        "```\n",
        "ENRICHMENT_SAMPLE_SIZE_PER_CATEGORY = SAMPLE_STRATA * SAMPLE_PER_STRATUM\n"
        "```\n"
        "\n"
        "The stratum usability minimum is an inclusive floor: a stratum with "
        "`u_h >= MIN_USABLE_SAMPLES_PER_STRATUM` usable observations is usable, while a "
        "stratum with zero usable observations remains unusable and its population weight "
        "is excluded from the stratum eligibility coverages (§7.2, §7.4, §7.5). At the "
        "default of 1 this means a stratum is unusable exactly when it has no usable "
        "observation.\n",
    ),
)


def main() -> int:
    text = SRS.read_text(encoding="utf-8")
    if "\r\n" in text:
        print("ABORT: CRLF line endings detected; refusing to rewrite.")
        return 2
    for index, (old, new) in enumerate(EDITS, start=1):
        count = text.count(old)
        if count != 1:
            print(f"ABORT: edit S{index} pattern count = {count} (expected 1): {old!r}")
            return 1
        text = text.replace(old, new, 1)
    SRS.write_bytes(text.encode("utf-8"))
    payload = SRS.read_bytes()
    print("sha256_after", hashlib.sha256(payload).hexdigest())
    print("len_after", len(payload), "crlf", payload.count(b"\r\n"))
    for token in (
        "MIN_USABLE_SAMPLES_PER_STRATUM = 1",
        "| `MIN_USABLE_SAMPLES_PER_STRATUM` | 1 |",
        "| Lean 1.0.3 |",
        "| Version | Lean 1.0.3 |",
    ):
        print(f"contains {token!r}:", token in text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
