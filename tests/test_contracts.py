from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from niche_scout.config import load_config
from niche_scout.models import (
    CategoryScore,
    DiscoveryStatus,
    EvidenceGrade,
    RankabilityStatus,
    RunRow,
    RunStatus,
    ScoreState,
    to_json,
)


@pytest.mark.lreq("LREQ-ARCH-010")
def test_contract_modules_import_and_status_values() -> None:
    assert RunStatus.RUNNING.value == "running"
    assert ScoreState.UNAVAILABLE.value == "unavailable"
    assert EvidenceGrade.INSUFFICIENT.value == "insufficient"
    assert RankabilityStatus.NOT_RANKABLE.value == "not_rankable"


@pytest.mark.lreq("LREQ-ARCH-020")
def test_serialization_normalizes_aware_timestamp_to_utc() -> None:
    row = RunRow(
        run_id="run-1",
        run_started_at_utc=datetime(2026, 1, 1, 1, tzinfo=timezone.utc),
        scoring_cutoff_utc=datetime(2026, 1, 1, 2, tzinfo=timezone.utc),
        status=RunStatus.RUNNING,
    )
    assert '"scoring_cutoff_utc":"2026-01-01T02:00:00Z"' in to_json(row)


@pytest.mark.lreq("LREQ-ARCH-030")
def test_unavailable_score_is_not_a_zero_sentinel() -> None:
    score = CategoryScore(
        run_id="run-1",
        category="tools",
        discovery_status=DiscoveryStatus.COMPLETE,
        discovery_filter_verified=False,
        discovery_unresolved_identity_count=0,
        discovery_conflict_count=0,
        discovery_duplicate_count=0,
        discovered_population_count=0,
        enriched_sample_count=0,
        sample_is_census=False,
        sampling_basis="sample",
    )
    assert score.market_opportunity_score is None
    assert score.score_state is ScoreState.UNAVAILABLE


@pytest.mark.lreq("LREQ-ARCH-010")
def test_schema_spec_covers_typed_row_fields() -> None:
    from dataclasses import fields
    from niche_scout.database import SCHEMA_SPEC
    from niche_scout.models import CategoryScore, EnrichmentObservation, RawDiscoveryObservation, RunRow, SampleMember

    expected = {
        "runs": RunRow,
        "raw_discovery_observations": RawDiscoveryObservation,
        "sample_members": SampleMember,
        "enrichment_observations": EnrichmentObservation,
        "category_scores": CategoryScore,
    }
    for table, row_type in expected.items():
        assert SCHEMA_SPEC[table]["fields"] == tuple(field.name for field in fields(row_type))


@pytest.mark.lreq("LREQ-SEC-010")
def test_configuration_precedence_and_credential_requirement() -> None:
    config = load_config(
        explicit={"categories": ["explicit"], "page_size": 96},
        environ={
            "NICHE_SCOUT_CATEGORIES": "environment",
            "NICHESCOUT_COVEO_BEARER_TOKEN": "redacted",
            "NICHESCOUT_UNITY_CSRF_TOKEN": "redacted",
        },
    )
    assert config.categories == ("explicit",)
    config.credentials.require_for_collection()


@pytest.mark.lreq("LREQ-NFR-040")
def test_scoring_cutoff_requires_timezone_awareness() -> None:
    with pytest.raises(ValueError):
        RunRow(
            run_id="run-1",
            run_started_at_utc=datetime(2026, 1, 1, tzinfo=timezone.utc),
            scoring_cutoff_utc=datetime(2026, 1, 1),
            status=RunStatus.RUNNING,
        )
    with pytest.raises(ValueError):
        RunRow(
            run_id="run-1",
            run_started_at_utc=datetime(2026, 1, 1, tzinfo=timezone.utc),
            scoring_cutoff_utc=datetime(2026, 1, 1, tzinfo=timezone(timedelta(hours=2))),
            status=RunStatus.RUNNING,
        )


@pytest.mark.lreq("LREQ-NFR-050")
def test_configuration_uses_pathlib_paths() -> None:
    config = load_config(
        {"categories": ["tools"]},
        {
            "NICHESCOUT_COVEO_BEARER_TOKEN": "x",
            "NICHESCOUT_UNITY_CSRF_TOKEN": "y",
        },
    )
    assert isinstance(config.paths.database_file, Path)


@pytest.mark.lreq("LREQ-NFR-060")
def test_project_quality_artifacts_are_present_and_secret_free() -> None:
    root = Path(__file__).resolve().parents[1]
    env_example = (root / ".env.example").read_text(encoding="utf-8")
    assert "NICHESCOUT_COVEO_BEARER_TOKEN=" in env_example
    assert "NICHESCOUT_UNITY_CSRF_TOKEN=" in env_example
    assert "redacted" not in env_example.lower()
    assert ".env" in (root / ".gitignore").read_text(encoding="utf-8")
    assert (root / "config" / "default.toml").is_file()
