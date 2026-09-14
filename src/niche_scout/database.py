"""Persistence-neutral schema and repository protocols.

Chunk 0 defines contracts only. SQLite connections, DDL, transactions, and
physical persistence belong to the persistence implementation chunk.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from typing import Protocol

from .models import (
    CategoryScore,
    EnrichmentObservation,
    RawDiscoveryObservation,
    RunRow,
    SampleMember,
    MANDATORY_ROW_FIELDS,
)

SCHEMA_VERSION = "lean-schema-1"
PRIMARY_KEYS = {
    "runs": ("run_id",),
    "raw_discovery_observations": ("observation_id",),
    "sample_members": ("run_id", "category", "asset_identity_key"),
    "enrichment_observations": ("run_id", "asset_identity_key"),
    "category_scores": ("run_id", "category"),
}


class Repository(Protocol):
    """Storage adapter required by orchestration; no backend is implied."""

    def create_run(self, row: RunRow) -> None: ...
    def update_run(self, row: RunRow) -> None: ...
    def append_discovery(self, rows: Iterable[RawDiscoveryObservation]) -> None: ...
    def write_sample_members(self, rows: Iterable[SampleMember]) -> None: ...
    def write_enrichment(self, rows: Iterable[EnrichmentObservation]) -> None: ...
    def write_category_scores(self, rows: Iterable[CategoryScore]) -> None: ...
    def iter_discovery(self, run_id: str, category: str) -> Iterator[RawDiscoveryObservation]: ...
    def iter_samples(self, run_id: str, category: str) -> Iterator[SampleMember]: ...
    def get_scores(self, run_id: str) -> tuple[CategoryScore, ...]: ...


class RunRepository(Protocol):
    def create_run(self, row: RunRow) -> None: ...
    def update_run(self, row: RunRow) -> None: ...


class DiscoveryRepository(Protocol):
    def append_discovery(self, rows: Iterable[RawDiscoveryObservation]) -> None: ...
    def iter_discovery(self, run_id: str, category: str) -> Iterator[RawDiscoveryObservation]: ...


class SampleRepository(Protocol):
    def write_sample_members(self, rows: Iterable[SampleMember]) -> None: ...
    def iter_samples(self, run_id: str, category: str) -> Iterator[SampleMember]: ...


class EnrichmentRepository(Protocol):
    def write_enrichment(self, rows: Iterable[EnrichmentObservation]) -> None: ...


class ScoreRepository(Protocol):
    def write_category_scores(self, rows: Iterable[CategoryScore]) -> None: ...
    def get_scores(self, run_id: str) -> tuple[CategoryScore, ...]: ...


SCHEMA_SPEC: dict[str, dict[str, object]] = {
    table: {"primary_key": PRIMARY_KEYS[table], "fields": fields}
    for table, fields in MANDATORY_ROW_FIELDS.items()
}

for _table, _key in PRIMARY_KEYS.items():
    if not set(_key).issubset(SCHEMA_SPEC[_table]["fields"]):
        raise RuntimeError(f"schema key is not a declared field: {_table}")
