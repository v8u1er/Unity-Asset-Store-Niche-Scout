"""Shared fixtures for the niche-scout analytical test suite.

Fixture modules are imported by name (``import fixtures.config_fixtures``), which
keeps each chunk's fixtures in its own module. The imports below re-export the
existing modules for convenience only; they add no symbols of their own.
"""

from __future__ import annotations

from fixtures import (
    acceptance_fixtures,
    config_fixtures,
    coveo_discovery,
    date_eligibility_fixtures,
    graphql_fixtures,
    metric_estimator_fixtures,
    pipeline_fixtures,
    sampling_fixtures,
    sampling_persistence_fixtures,
    scoring_evidence_fixtures,
    scoring_fixtures,
    sensitivity_fixtures,
    validation_fixtures,
)

__all__ = [
    "acceptance_fixtures",
    "config_fixtures",
    "coveo_discovery",
    "date_eligibility_fixtures",
    "graphql_fixtures",
    "metric_estimator_fixtures",
    "pipeline_fixtures",
    "sampling_fixtures",
    "sampling_persistence_fixtures",
    "scoring_evidence_fixtures",
    "scoring_fixtures",
    "sensitivity_fixtures",
    "validation_fixtures",
]
