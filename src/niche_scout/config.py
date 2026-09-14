"""Configuration contracts and precedence rules.

Configuration is pure data. Collection code is responsible for consuming the
validated credentials and performing network access.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

DEFAULTS = {
    "max_discovery_results_per_category": 2000,
    "page_size": 96,
    "enrichment_sample_size_per_category": 100,
    "min_usable_samples_per_stratum": 5,
    "min_age_days_for_rate": 30,
}
ENV_NAMES = {
    "coveo_bearer_token": "NICHESCOUT_COVEO_BEARER_TOKEN",
    "unity_csrf_token": "NICHESCOUT_UNITY_CSRF_TOKEN",
}


@dataclass(frozen=True, slots=True)
class PolicyVersions:
    endpoint_contract_version: str = "parent-srs-2.3.0"
    identity_mapping_rule_version: str = "identity-map-1"
    sampling_rule_version: str = "lean-stratified-v1"


@dataclass(frozen=True, slots=True)
class Credentials:
    coveo_bearer_token: str | None = None
    unity_csrf_token: str | None = None

    def missing(self) -> tuple[str, ...]:
        return tuple(name for field, name in ENV_NAMES.items() if not getattr(self, field))

    def require_for_collection(self) -> None:
        missing = self.missing()
        if missing:
            raise ValueError(f"Missing required credentials: {', '.join(missing)}")


@dataclass(frozen=True, slots=True)
class PathsConfig:
    taxonomy_file: Path = Path("config/category_taxonomy.json")
    categories_file: Path = Path("config/categories.json")
    database_file: Path = Path("runtime/niche_scout.sqlite3")


@dataclass(frozen=True, slots=True)
class ScoutConfig:
    categories: tuple[str, ...]
    max_discovery_results_per_category: int = DEFAULTS["max_discovery_results_per_category"]
    page_size: int = DEFAULTS["page_size"]
    enrichment_sample_size_per_category: int = DEFAULTS["enrichment_sample_size_per_category"]
    min_usable_samples_per_stratum: int = DEFAULTS["min_usable_samples_per_stratum"]
    min_age_days_for_rate: int = DEFAULTS["min_age_days_for_rate"]
    paths: PathsConfig = PathsConfig()
    policy_versions: PolicyVersions = PolicyVersions()
    credentials: Credentials = Credentials()

    def validate(self) -> None:
        if not self.categories or any(not category.strip() for category in self.categories):
            raise ValueError("at least one non-empty category is required")
        for name in (
            "max_discovery_results_per_category",
            "page_size",
            "enrichment_sample_size_per_category",
            "min_usable_samples_per_stratum",
            "min_age_days_for_rate",
        ):
            if getattr(self, name) <= 0:
                raise ValueError(f"{name} must be positive")
        if self.page_size != 96:
            raise ValueError("page_size is fixed by the endpoint protocol")
        for name in ("endpoint_contract_version", "identity_mapping_rule_version", "sampling_rule_version"):
            if not getattr(self.policy_versions, name).strip():
                raise ValueError(f"{name} must be non-empty")


def _int_value(value: object, name: str) -> int:
    try:
        parsed = int(str(value))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be an integer") from exc
    return parsed


def load_config(
    explicit: Mapping[str, object] | None = None,
    environ: Mapping[str, str] | None = None,
) -> ScoutConfig:
    """Build config using explicit values, then environment, then defaults."""
    explicit = explicit or {}
    environ = os.environ if environ is None else environ

    def value(name: str) -> object:
        if name in explicit:
            return explicit[name]
        env_name = "NICHE_SCOUT_" + name.upper()
        return environ.get(env_name, DEFAULTS[name])

    categories_raw = explicit.get("categories", environ.get("NICHE_SCOUT_CATEGORIES", ""))
    categories = tuple(
        item.strip() for item in (categories_raw if isinstance(categories_raw, (list, tuple)) else str(categories_raw).split(",")) if item.strip()
    )
    def credential(name: str) -> str | None:
        raw = explicit[name] if name in explicit else environ.get(ENV_NAMES[name], "")
        if raw is None:
            return None
        if not isinstance(raw, str):
            raise ValueError(f"{name} must be a string")
        return raw or None

    credentials = Credentials(
        coveo_bearer_token=credential("coveo_bearer_token"),
        unity_csrf_token=credential("unity_csrf_token"),
    )
    default_paths = PathsConfig()
    paths = PathsConfig(
        taxonomy_file=Path(str(explicit.get("taxonomy_file", environ.get("NICHE_SCOUT_TAXONOMY_FILE", default_paths.taxonomy_file)))),
        categories_file=Path(str(explicit.get("categories_file", environ.get("NICHE_SCOUT_CATEGORIES_FILE", default_paths.categories_file)))),
        database_file=Path(str(explicit.get("database_file", environ.get("NICHE_SCOUT_DATABASE_FILE", default_paths.database_file)))),
    )
    config = ScoutConfig(
        categories=categories,
        max_discovery_results_per_category=_int_value(value("max_discovery_results_per_category"), "max_discovery_results_per_category"),
        page_size=_int_value(value("page_size"), "page_size"),
        enrichment_sample_size_per_category=_int_value(value("enrichment_sample_size_per_category"), "enrichment_sample_size_per_category"),
        min_usable_samples_per_stratum=_int_value(value("min_usable_samples_per_stratum"), "min_usable_samples_per_stratum"),
        min_age_days_for_rate=_int_value(value("min_age_days_for_rate"), "min_age_days_for_rate"),
        paths=paths,
        policy_versions=PolicyVersions(
            endpoint_contract_version=str(explicit.get("endpoint_contract_version", environ.get("NICHE_SCOUT_ENDPOINT_CONTRACT_VERSION", PolicyVersions().endpoint_contract_version))),
            identity_mapping_rule_version=str(explicit.get("identity_mapping_rule_version", environ.get("NICHE_SCOUT_IDENTITY_MAPPING_RULE_VERSION", PolicyVersions().identity_mapping_rule_version))),
            sampling_rule_version=str(explicit.get("sampling_rule_version", environ.get("NICHE_SCOUT_SAMPLING_RULE_VERSION", PolicyVersions().sampling_rule_version))),
        ),
        credentials=credentials,
    )
    config.validate()
    return config
