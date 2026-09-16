"""Configuration contracts, precedence hierarchy, and credential reading.

Configuration is pure data. Collection code is responsible for consuming the
validated credentials and performing network access; nothing in this module
performs I/O beyond reading an explicitly supplied TOML file path.

Precedence contract (LREQ-CLI-030): ``cli_args`` > ``toml_path`` > in-code
defaults. Policy versions and fixed SRS constants are imported from
:mod:`niche_scout.models` rather than restated here.
"""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence

from .models import (
    ENDPOINT_CONTRACT_VERSION,
    IDENTITY_MAPPING_RULE_VERSION,
    IDENTITY_PREFLIGHT_ASSETS_PER_CATEGORY,
    IDENTITY_PREFLIGHT_MIN_CATEGORIES,
    IDENTITY_PREFLIGHT_MIN_SUCCESS_RATE,
    MAX_DISCOVERY_RESULTS_PER_CATEGORY,
    MAX_TAXONOMY_AGE_DAYS,
    MIN_AGE_DAYS_FOR_RATE,
    MIN_CATEGORIES_PER_RUN,
    MIN_USABLE_SAMPLES_PER_STRATUM,
    PAGE_SIZE,
    QUALITY_MIN_ELIGIBLE_ASSETS,
    QUALITY_MIN_RATING_COUNT,
    RECENT_WINDOW_DAYS,
    SAMPLING_RULE_VERSION,
    STRONG_REFERENCE_CATEGORY_COUNT,
)

COVEO_TOKEN_ENV = "NICHESCOUT_COVEO_BEARER_TOKEN"
UNITY_CSRF_TOKEN_ENV = "NICHESCOUT_UNITY_CSRF_TOKEN"

DEFAULT_TOML_PATH = Path("config") / "default.toml"
DEFAULT_CATEGORIES_PATH = Path("config") / "categories.json"
DEFAULT_TAXONOMY_PATH = Path("config") / "category_taxonomy.json"
DEFAULT_DB_PATH = Path("runtime") / "niche_scout.sqlite3"

# Documented in-code defaults, consumed by every downstream chunk. Fixed
# sampling constants and composite scoring weights are intentionally absent:
# they are policy constants, not user-configurable settings.
IN_CODE_DEFAULTS: dict[str, Any] = {
    "categories_path": DEFAULT_CATEGORIES_PATH,
    "taxonomy_path": DEFAULT_TAXONOMY_PATH,
    "db_path": DEFAULT_DB_PATH,
    "max_discovery_results_per_category": MAX_DISCOVERY_RESULTS_PER_CATEGORY,
    "page_size": PAGE_SIZE,
    "min_categories_per_run": MIN_CATEGORIES_PER_RUN,
    "strong_reference_category_count": STRONG_REFERENCE_CATEGORY_COUNT,
    "max_taxonomy_age_days": MAX_TAXONOMY_AGE_DAYS,
    "min_usable_samples_per_stratum": MIN_USABLE_SAMPLES_PER_STRATUM,
    "min_age_days_for_rate": MIN_AGE_DAYS_FOR_RATE,
    "recent_window_days": RECENT_WINDOW_DAYS,
    "quality_min_rating_count": QUALITY_MIN_RATING_COUNT,
    "quality_min_eligible_assets": QUALITY_MIN_ELIGIBLE_ASSETS,
    "identity_preflight_min_categories": IDENTITY_PREFLIGHT_MIN_CATEGORIES,
    "identity_preflight_assets_per_category": IDENTITY_PREFLIGHT_ASSETS_PER_CATEGORY,
    "identity_preflight_min_success_rate": IDENTITY_PREFLIGHT_MIN_SUCCESS_RATE,
}

_INT_FIELDS: tuple[str, ...] = (
    "max_discovery_results_per_category",
    "page_size",
    "min_categories_per_run",
    "strong_reference_category_count",
    "max_taxonomy_age_days",
    "min_usable_samples_per_stratum",
    "min_age_days_for_rate",
    "recent_window_days",
    "quality_min_rating_count",
    "quality_min_eligible_assets",
    "identity_preflight_min_categories",
    "identity_preflight_assets_per_category",
)

_FLOAT_FIELDS: tuple[str, ...] = ("identity_preflight_min_success_rate",)

_PATH_FIELDS: tuple[str, ...] = ("categories_path", "taxonomy_path", "db_path")

# Policy versions are frozen constants; they are reported but never overridden
# by user configuration.
POLICY_VERSIONS: dict[str, str] = {
    "endpoint_contract_version": ENDPOINT_CONTRACT_VERSION,
    "identity_mapping_rule_version": IDENTITY_MAPPING_RULE_VERSION,
    "sampling_rule_version": SAMPLING_RULE_VERSION,
}


@dataclass(frozen=True)
class Credentials:
    """Environment-sourced credentials. Both values are required before collection."""

    coveo_token: str
    unity_csrf_token: str

    @property
    def coveo_bearer_token(self) -> str:
        """Alias for :attr:`coveo_token` used by HTTP header construction code."""
        return self.coveo_token

    def require_for_collection(self) -> None:
        """Raise :class:`ValueError` when either credential is empty."""
        if not self.coveo_token or not self.unity_csrf_token:
            raise ValueError(
                f"Missing required credentials: {COVEO_TOKEN_ENV} and "
                f"{UNITY_CSRF_TOKEN_ENV} must both be set before network collection"
            )


@dataclass(frozen=True)
class NicheScoutConfig:
    """Typed run configuration resolved through the CLI > TOML > defaults hierarchy."""

    categories_path: Path
    taxonomy_path: Path
    db_path: Path
    max_discovery_results_per_category: int
    page_size: int
    min_categories_per_run: int
    strong_reference_category_count: int
    max_taxonomy_age_days: int
    min_usable_samples_per_stratum: int
    min_age_days_for_rate: int
    recent_window_days: int
    quality_min_rating_count: int
    quality_min_eligible_assets: int
    identity_preflight_min_categories: int
    identity_preflight_assets_per_category: int
    identity_preflight_min_success_rate: float
    source: str = "defaults"

    def policy_versions(self) -> dict[str, str]:
        """Return the frozen policy version strings recorded on each run."""
        return dict(POLICY_VERSIONS)


def _as_int(value: Any, name: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{name} must be an integer")
    if isinstance(value, int):
        return value
    try:
        return int(str(value))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be an integer") from exc


def _as_float(value: Any, name: str) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{name} must be a number")
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be a number") from exc


def _as_path(value: Any, name: str) -> Path:
    if isinstance(value, Path):
        return value
    if isinstance(value, str):
        return Path(value)
    raise ValueError(f"{name} must be a filesystem path")


def _load_toml(toml_path: Optional[Path]) -> dict[str, Any]:
    if toml_path is None:
        return {}
    path = Path(toml_path)
    if not path.is_file():
        return {}
    with path.open("rb") as handle:
        parsed = tomllib.load(handle)
    if not isinstance(parsed, dict):
        raise ValueError(f"{path} must contain a TOML table")
    # Accept either a top-level table or a [niche_scout] section.
    section = parsed.get("niche_scout")
    if isinstance(section, dict):
        merged = {key: value for key, value in parsed.items() if key != "niche_scout"}
        merged.update(section)
        return merged
    return parsed


def load_config(
    cli_args: Optional[dict[str, Any]] = None,
    toml_path: Optional[Path] = None,
) -> NicheScoutConfig:
    """Resolve configuration using the documented precedence.

    ``cli_args`` > ``toml_path`` > in-code defaults.

    ``cli_args`` values that are ``None`` are treated as absent so that a parsed
    CLI namespace with unset options cannot shadow TOML or default values.
    Keys outside the documented field set are rejected so that fixed sampling
    constants and composite scoring weights cannot be made configurable.
    """
    overrides = {
        key: value for key, value in (cli_args or {}).items() if value is not None
    }
    toml_values = {
        key: value for key, value in _load_toml(toml_path).items() if value is not None
    }

    unknown = sorted((set(overrides) | set(toml_values)) - set(IN_CODE_DEFAULTS))
    if unknown:
        raise ValueError(f"unsupported configuration keys: {', '.join(unknown)}")

    if "source" in overrides or "source" in toml_values:
        raise ValueError("'source' is reported by load_config and is not configurable")

    resolved: dict[str, Any] = {}
    explicit: set[str] = set()

    def resolve(name: str) -> Any:
        if name in overrides:
            explicit.add(name)
            return overrides[name]
        if name in toml_values:
            explicit.add(name)
            return toml_values[name]
        return IN_CODE_DEFAULTS[name]

    for name in _PATH_FIELDS:
        resolved[name] = _as_path(resolve(name), name)
    for name in _INT_FIELDS:
        resolved[name] = _as_int(resolve(name), name)
    for name in _FLOAT_FIELDS:
        resolved[name] = _as_float(resolve(name), name)

    if resolved["page_size"] != PAGE_SIZE:
        raise ValueError(f"page_size is fixed at {PAGE_SIZE} by the endpoint contract")
    if resolved["max_discovery_results_per_category"] <= 0:
        raise ValueError("max_discovery_results_per_category must be positive")
    if resolved["min_categories_per_run"] <= 0:
        raise ValueError("min_categories_per_run must be positive")
    if not 0.0 <= resolved["identity_preflight_min_success_rate"] <= 1.0:
        raise ValueError("identity_preflight_min_success_rate must lie within [0, 1]")

    if explicit & set(overrides):
        source = "cli"
    elif explicit & set(toml_values):
        source = "toml"
    else:
        source = "defaults"

    return NicheScoutConfig(source=source, **resolved)


def read_categories(categories_path: Path) -> Sequence[str]:
    """Read the requested category list from a JSON selection file.

    Accepts either a bare JSON array or the documented object form with a
    ``categories`` key. Returns category paths in declared order.
    """
    import json

    path = Path(categories_path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        categories = payload.get("categories", [])
    else:
        categories = payload
    if not isinstance(categories, list) or any(
        not isinstance(item, str) for item in categories
    ):
        raise ValueError(f"{path} must contain a list of category path strings")
    return tuple(item for item in categories if item)


def get_credentials(environ: Optional[Mapping[str, str]] = None) -> Credentials:
    """Read credentials from the environment, raising :class:`ValueError` if missing.

    Secret values are never included in the raised message.
    """
    env = os.environ if environ is None else environ
    coveo_token = (env.get(COVEO_TOKEN_ENV) or "").strip()
    unity_csrf_token = (env.get(UNITY_CSRF_TOKEN_ENV) or "").strip()
    credentials = Credentials(
        coveo_token=coveo_token, unity_csrf_token=unity_csrf_token
    )
    credentials.require_for_collection()
    return credentials
