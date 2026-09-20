"""Shared fixtures for the niche-scout analytical test suite.

Fixture modules are imported by name (``import fixtures.config_fixtures``), which
keeps each chunk's fixtures in its own module. The imports below re-export the
existing modules for convenience only; they add no symbols of their own.
"""

from __future__ import annotations

from fixtures import (
    config_fixtures,
    coveo_discovery,
    graphql_fixtures,
    sampling_fixtures,
    validation_fixtures,
)

__all__ = [
    "config_fixtures",
    "coveo_discovery",
    "graphql_fixtures",
    "sampling_fixtures",
    "validation_fixtures",
]
