"""Deterministic, local-only configuration fixtures for the contract suite.

These fixtures never touch the network and never contain real credentials. They
supply the TOML bodies, CLI override dictionaries, taxonomy payloads, and mock
environment dictionaries needed to exercise the Chunk 0 configuration and
taxonomy contracts.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

# Requirements the taxonomy fixture must satisfy (LREQ-EXT-020).
REQUIRED_TAXONOMY_FIELDS: tuple[str, ...] = (
    "schema_version",
    "captured_at_utc",
    "source_url",
    "template_sha256",
)

# The eight live Q4 categories (chunk-14 plan appendix B) as canonical
# '/'-form paths: the same eight strings `config/categories.json` and the
# committed template facet must each carry.
#
# The order here is ascending lexical, a fixture-local choice: the two
# committed files' own order is fixed by the impl-side regeneration (and the
# `test_committed_categories_match_template_facet_byte_for_byte` node compares
# those two files to each other, never to this fixture). Lexical order keeps
# fixture-derived ordering assertions valid, e.g. `get_category_scores`
# returning rows lexically by category for `DEFAULT_CATEGORIES[0]` then `[1]`.
DEFAULT_CATEGORIES: tuple[str, ...] = (
    "2d/gui/icons",
    "2d/textures-materials/stone",
    "3d/characters/animals/mammals",
    "3d/characters/humanoids",
    "3d/vegetation/trees",
    "3d/vehicles/land",
    "audio/music/orchestral",
    "vfx/particles/fire-explosions",
)

DEFAULT_TOML_BODY: str = """
categories_path = "config/categories.json"
taxonomy_path = "config/category_taxonomy.json"
db_path = "runtime/niche_scout.sqlite3"

max_discovery_results_per_category = 2000
page_size = 96
min_categories_per_run = 8
strong_reference_category_count = 21
max_taxonomy_age_days = 30

min_usable_samples_per_stratum = 5
min_age_days_for_rate = 30
recent_window_days = 365
quality_min_rating_count = 5
quality_min_eligible_assets = 5

identity_preflight_min_categories = 5
identity_preflight_assets_per_category = 2
identity_preflight_min_success_rate = 0.90
""".strip()

# Overrides max_taxonomy_age_days, quality thresholds, recent window, and paths.
CUSTOM_TOML_BODY: str = """
categories_path = "config/categories.json"
taxonomy_path = "runtime/custom_taxonomy.json"
db_path = "runtime/custom.sqlite3"

max_discovery_results_per_category = 1500
page_size = 96
min_categories_per_run = 10
strong_reference_category_count = 21
max_taxonomy_age_days = 14

min_usable_samples_per_stratum = 4
min_age_days_for_rate = 45
recent_window_days = 180
quality_min_rating_count = 10
quality_min_eligible_assets = 7

identity_preflight_min_categories = 6
identity_preflight_assets_per_category = 3
identity_preflight_min_success_rate = 0.95
""".strip()

# A TOML body wearing the optional [niche_scout] section form.
SECTIONED_TOML_BODY: str = """
[niche_scout]
page_size = 96
max_taxonomy_age_days = 21
min_age_days_for_rate = 60
""".strip()

DEFAULT_TOML_VALUES: dict[str, Any] = {
    "max_discovery_results_per_category": 2000,
    "page_size": 96,
    "min_categories_per_run": 8,
    "strong_reference_category_count": 21,
    "max_taxonomy_age_days": 30,
    "min_usable_samples_per_stratum": 5,
    "min_age_days_for_rate": 30,
    "recent_window_days": 365,
    "quality_min_rating_count": 5,
    "quality_min_eligible_assets": 5,
    "identity_preflight_min_categories": 5,
    "identity_preflight_assets_per_category": 2,
    "identity_preflight_min_success_rate": 0.90,
}

CUSTOM_TOML_VALUES: dict[str, Any] = {
    "taxonomy_path": Path("runtime/custom_taxonomy.json"),
    "db_path": Path("runtime/custom.sqlite3"),
    "max_discovery_results_per_category": 1500,
    "min_categories_per_run": 10,
    "max_taxonomy_age_days": 14,
    "min_usable_samples_per_stratum": 4,
    "min_age_days_for_rate": 45,
    "recent_window_days": 180,
    "quality_min_rating_count": 10,
    "quality_min_eligible_assets": 7,
    "identity_preflight_min_categories": 6,
    "identity_preflight_assets_per_category": 3,
    "identity_preflight_min_success_rate": 0.95,
}

# CLI dictionaries that partially override the TOML body above.
CLI_OVERRIDE_ARGS: dict[str, Any] = {
    "max_discovery_results_per_category": 500,
    "min_age_days_for_rate": 90,
    "quality_min_eligible_assets": 12,
}

# CLI dictionaries whose keys must be ignored because the value is absent.
CLI_NONE_ARGS: dict[str, Any] = {
    "max_discovery_results_per_category": None,
    "recent_window_days": None,
}

MOCK_ENVIRONMENT: Mapping[str, str] = {
    "NICHESCOUT_COVEO_BEARER_TOKEN": "fixture-coveo-token",
    "NICHESCOUT_UNITY_CSRF_TOKEN": "fixture-csrf-token",
}

MOCK_ENVIRONMENT_PARTIAL: Mapping[str, str] = {
    "NICHESCOUT_UNITY_CSRF_TOKEN": "fixture-csrf-token",
}

TAXONOMY_FIXTURE: dict[str, Any] = {
    "schema_version": "1.0.0",
    "captured_at_utc": "2026-01-05T00:00:00Z",
    "source_url": "https://assetstore.unity.com/categories",
    "template_sha256": "0" * 64,
    "canonical_category_paths": list(DEFAULT_CATEGORIES),
    "categories": [
        {
            "path": path,
            "label": path.rsplit("/", 1)[-1],
            "parent": path.rsplit("/", 1)[0] if "/" in path else "",
        }
        for path in DEFAULT_CATEGORIES
    ],
}


def write_toml(directory: Path, body: str, name: str = "fixture.toml") -> Path:
    """Write a TOML fixture body into ``directory`` and return its path."""
    path = directory / name
    path.write_text(body + "\n", encoding="utf-8")
    return path
