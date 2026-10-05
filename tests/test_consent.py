"""Analytical tests for the ``run`` terms-consent gate (``LREQ-CLI-050``).

Source of truth: ``Documents/SRS-lean-v2.md`` §10 (``LREQ-CLI-050``), §4.3
(``LREQ-SEC-010``), and §13 (``LREQ-TST-010``). Scope is the bespoke
``consent-gate`` chunk brief; no plan file exists for it.

Every node carries ``@pytest.mark.lreq("LREQ-CLI-050")`` and a matching
``tests/traceability.json`` entry keyed by its base node ID.

Fully offline: the transports are the Chunk 10 in-memory recorders, the clock is
the fixture's fixed clock, the database lives under pytest ``tmp_path``, and the
consent marker is always an explicit path under ``tmp_path`` -- the real
``Path.home()`` marker is never read or written. No network, no credentials, no
``.env``, no clock read.
"""

from __future__ import annotations

import io
from pathlib import Path
from typing import Any

import pytest
from fixtures import cli_fixtures as cf
from fixtures import config_fixtures

from niche_scout import cli, consent


class _InteractiveStdin(io.StringIO):
    """A stdin double that reports itself as an interactive TTY."""

    def isatty(self) -> bool:  # noqa: D102 - deliberate double override
        return True


def _environment() -> dict[str, str]:
    """Return the non-secret fixture credential environment."""
    return dict(config_fixtures.MOCK_ENVIRONMENT)


def _noop_write_report(repository, run_id, output_path, *, fmt="html"):
    """An injected no-op writer, so no report file is produced for a test."""
    _ = repository, run_id, fmt
    return Path(output_path)


def _poison_repository_factory():
    """Return an ``open_repository`` that fails the test if it is ever called."""

    def poison(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("consent gate must decide before the repository opens")

    return poison


def _dummy_run_options(tmp_path: Path, *, accept_terms: bool = False) -> Any:
    """Return run-shaped options pointing at never-read temp paths."""
    return cf.run_options(
        tmp_path / "categories.json",
        tmp_path / "default.toml",
        tmp_path / "run.sqlite3",
        accept_terms=accept_terms,
    )


def _run_command(
    artifacts: cf.ScenarioArtifacts,
    *,
    stdin: Any,
    marker_path: Path,
    accept_terms: bool = True,
    **overrides: Any,
) -> int:
    """Invoke ``cli.run_command`` on the scenario with injected recorders.

    ``stdin`` and ``consent_marker_path`` are always explicit; ``overrides`` may
    replace any other injected seam (for example ``stderr`` or
    ``open_repository``).
    """
    factory = cf.RecordingRepositoryFactory()
    values: dict[str, Any] = {
        "environ": _environment(),
        "clock": artifacts.scenario.clock,
        "sleeper": lambda _seconds: None,
        "coveo_transport": artifacts.scenario.coveo_transport,
        "graphql_transport": artifacts.scenario.graphql_transport,
        "template_path": artifacts.template_path,
        "open_repository": factory,
        "write_report": _noop_write_report,
        "stdout": io.StringIO(),
        "stderr": io.StringIO(),
        "stdin": stdin,
        "consent_marker_path": marker_path,
    }
    options = overrides.pop("options", None)
    values.update(overrides)
    if options is None:
        options = cf.run_options(
            artifacts.categories_path,
            artifacts.config_path,
            artifacts.db_path,
            run_id=artifacts.run_id,
            accept_terms=accept_terms,
        )
    try:
        return cli.run_command(options, **values)
    finally:
        factory.close_all()


# ---------------------------------------------------------------------------
# Refusal and non-interactive behavior.
# ---------------------------------------------------------------------------


@pytest.mark.lreq("LREQ-CLI-050")
def test_non_interactive_without_flag_refuses_with_no_request(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """No stored ack, no flag, no TTY: usage error, no transport, no repository.

    The production Coveo opener and the CLI GraphQL builder are poisoned, and
    ``open_repository`` fails the test if reached, so the refusal provably
    precedes every I/O side effect (``LREQ-CLI-050``).
    """
    from niche_scout import collector_coveo

    def poison(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("refusal must construct no transport")

    monkeypatch.setattr(collector_coveo, "CoveoUrlOpener", poison)
    monkeypatch.setattr(cli, "build_graphql_transport", poison)

    marker = tmp_path / "terms_acknowledged"
    stderr = io.StringIO()
    code = cli.run_command(
        _dummy_run_options(tmp_path, accept_terms=False),
        environ=_environment(),
        stdin=io.StringIO(),
        stderr=stderr,
        consent_marker_path=marker,
        open_repository=_poison_repository_factory(),
    )

    assert code == cli.EXIT_USAGE_ERROR
    assert not marker.exists()
    assert consent.NOTICE_TEXT in stderr.getvalue()


@pytest.mark.lreq("LREQ-CLI-050")
def test_accept_terms_allows_one_run_and_persists_nothing(tmp_path: Path) -> None:
    """``--accept-terms`` completes the run and writes no marker file."""
    artifacts = cf.scenario_artifacts(tmp_path, run_id="run-consent-accept")
    marker = tmp_path / "terms_acknowledged"
    code = _run_command(
        artifacts,
        stdin=io.StringIO(),
        marker_path=marker,
        accept_terms=True,
    )

    assert code == cli.EXIT_OK
    assert not marker.exists()


@pytest.mark.lreq("LREQ-CLI-050")
def test_interactive_phrase_persists_and_second_run_is_silent(
    tmp_path: Path,
) -> None:
    """The correct phrase persists; an acknowledged run prints no notice."""
    marker = tmp_path / "terms_acknowledged"
    first_dir = tmp_path / "first"
    first_dir.mkdir()
    first = cf.scenario_artifacts(first_dir, run_id="run-consent-first")
    first_stderr = io.StringIO()
    first_code = _run_command(
        first,
        stdin=_InteractiveStdin(consent.ACKNOWLEDGEMENT_PHRASE + "\n"),
        marker_path=marker,
        accept_terms=False,
        stderr=first_stderr,
    )

    assert first_code == cli.EXIT_OK
    assert marker.is_file()
    assert consent.load_acknowledged_digest(marker) == consent.notice_digest()

    second_dir = tmp_path / "second"
    second_dir.mkdir()
    second = cf.scenario_artifacts(second_dir, run_id="run-consent-second")
    second_stderr = io.StringIO()
    second_code = _run_command(
        second,
        stdin=io.StringIO(),
        marker_path=marker,
        accept_terms=False,
        stderr=second_stderr,
    )

    assert second_code == cli.EXIT_OK
    assert consent.NOTICE_TEXT not in second_stderr.getvalue()


@pytest.mark.lreq("LREQ-CLI-050")
def test_interactive_wrong_phrase_refuses(tmp_path: Path) -> None:
    """An interactive non-matching phrase returns the usage error and stores nothing."""
    marker = tmp_path / "terms_acknowledged"
    code = cli.run_command(
        _dummy_run_options(tmp_path, accept_terms=False),
        environ=_environment(),
        stdin=_InteractiveStdin("no thanks\n"),
        stderr=io.StringIO(),
        consent_marker_path=marker,
        open_repository=_poison_repository_factory(),
    )

    assert code == cli.EXIT_USAGE_ERROR
    assert not marker.exists()


# ---------------------------------------------------------------------------
# Digest stability and persistence failure.
# ---------------------------------------------------------------------------


@pytest.mark.lreq("LREQ-CLI-050")
def test_changed_notice_invalidates_a_stored_acknowledgement(tmp_path: Path) -> None:
    """A stored digest is honored only while the notice text is unchanged."""
    marker = tmp_path / "terms_acknowledged"
    assert consent.store_acknowledgement(marker, consent.notice_digest()) is True

    assert (
        consent.ensure_consent(
            accept_terms=False,
            stdin=io.StringIO(),
            stderr=io.StringIO(),
            marker_path=marker,
        )
        is True
    )

    edited_stderr = io.StringIO()
    assert (
        consent.ensure_consent(
            accept_terms=False,
            stdin=io.StringIO(),
            stderr=edited_stderr,
            marker_path=marker,
            notice_text=consent.NOTICE_TEXT + " (edited)",
        )
        is False
    )
    assert consent.NOTICE_TEXT in edited_stderr.getvalue()


@pytest.mark.lreq("LREQ-CLI-050")
def test_unwritable_marker_warns_but_does_not_block(tmp_path: Path) -> None:
    """A persist failure warns on stderr and the confirmed run still completes."""
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    artifacts = cf.scenario_artifacts(run_dir, run_id="run-consent-unwritable")
    blocker = tmp_path / "blocker"
    blocker.write_text("a regular file, not a directory", encoding="utf-8")
    marker = blocker / "terms_acknowledged"
    stderr = io.StringIO()
    code = _run_command(
        artifacts,
        stdin=_InteractiveStdin(consent.ACKNOWLEDGEMENT_PHRASE + "\n"),
        marker_path=marker,
        accept_terms=False,
        stderr=stderr,
    )

    assert code == cli.EXIT_OK
    assert "warning" in stderr.getvalue().lower()
    assert not marker.exists()


# ---------------------------------------------------------------------------
# Ordering: consent precedes the credential read.
# ---------------------------------------------------------------------------


@pytest.mark.lreq("LREQ-CLI-050")
def test_refusal_precedes_credential_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The refusal returns usage error before ``get_credentials`` is called."""
    calls: list[Any] = []

    def poison_credentials(*args: Any, **kwargs: Any) -> Any:
        calls.append((args, kwargs))
        raise AssertionError("credentials must not be read on refusal")

    monkeypatch.setattr(cli.config, "get_credentials", poison_credentials)

    marker = tmp_path / "terms_acknowledged"
    code = cli.run_command(
        _dummy_run_options(tmp_path, accept_terms=False),
        environ=_environment(),
        stdin=io.StringIO(),
        stderr=io.StringIO(),
        consent_marker_path=marker,
        open_repository=_poison_repository_factory(),
    )

    assert code == cli.EXIT_USAGE_ERROR
    assert calls == []
    assert not marker.exists()
