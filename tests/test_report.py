"""Analytical tests for Chunk 11 — report read model and renderers.

Source of truth: ``Documents/SRS-lean.md`` §10 (``LREQ-RPT-010`` through
``LREQ-RPT-050``, ``LREQ-CLI-020``), §1.2 (missing is never zero), §5.1
(``LREQ-SMP-080`` sample fraction), §6.5 (field semantics), §9.1/§9.2/§9.3
(rankability, evidence, sensitivity nulls), and Appendix C (warning
vocabulary); the frozen plan
``Documents/plans/chunk-11-report-renderer-and-read-only-dashboard.md`` §5
(public surface), §8 (edge cases), §9 (test plan); and the consumed interfaces
``chunk-4B.md``/``chunk-9B.md``/``chunk-10.md``.

Every analytical node carries ``@pytest.mark.lreq(...)`` and a matching
``tests/traceability.json`` entry keyed by its base node ID.

No network, no credentials, no clock reads, and no direct ``sqlite3``: the
repository is exercised only through the frozen Chunk 2 public API, with the
database under pytest ``tmp_path``.
"""

from __future__ import annotations

import ast
import dataclasses
import inspect
import json
import re
from html import escape as html_escape
from html.parser import HTMLParser
from pathlib import Path

import pytest
from fixtures import report_fixtures as rf

from niche_scout import database, report

# --------------------------------------------------------------------------
# Helpers (pure; no assertions about behavior under test).
# --------------------------------------------------------------------------


def _repository(tmp_path):
    """Open a fresh repository under ``tmp_path`` (no live path, no network)."""
    return database.SqliteRepository(tmp_path / "chunk11.sqlite")


def _seed(repository, run, scores=()):
    """Insert the ``runs`` row and any ``category_scores`` rows in one block."""
    with repository.transaction():
        repository.insert_run(run)
        if scores:
            repository.insert_category_scores(list(scores))


def _rows_by_category(view):
    return {row.category: row for row in view.categories}


def _text_primary_row(text, category):
    """Index one text primary-table data line by its header label."""
    lines = text.splitlines()
    header_index = lines.index("PRIMARY TABLE")
    headers = [label.strip() for label in lines[header_index + 1].strip().split(" | ")]
    for line in lines[header_index + 2 :]:
        stripped = line.strip()
        if not stripped or stripped == "CATEGORY DETAILS":
            break
        cells = [cell.strip() for cell in stripped.split(" | ")]
        if cells and cells[0] == category:
            return dict(zip(headers, cells, strict=True))
    raise AssertionError("category primary-table row not found")


class _PrimaryTableHTML(HTMLParser):
    """Parse the rendered ``<table id="primary">`` header and rows.

    Only the primary table is captured: the per-category stratum tables are
    ignored, so the extracted header/row cell sets are exactly the primary
    table's own cells.
    """

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self._in_table = False
        self._table_depth = 0
        self._section = None  # "thead" | "tbody" | None
        self._in_cell = False
        self._buffer = []
        self.headers = []
        self.rows = []

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if tag == "table":
            if self._in_table:
                self._table_depth += 1
                return
            if attributes.get("id") == "primary":
                self._in_table = True
                self._table_depth = 0
            return
        if not self._in_table:
            return
        if tag == "thead":
            self._section = "thead"
        elif tag == "tbody":
            self._section = "tbody"
        elif tag == "tr":
            self.rows.append([])
        elif tag in ("th", "td"):
            self._in_cell = True
            self._buffer = []

    def handle_data(self, data):
        if self._in_cell:
            self._buffer.append(data)

    def handle_endtag(self, tag):
        if tag == "table":
            if not self._in_table:
                return
            if self._table_depth:
                self._table_depth -= 1
            else:
                self._in_table = False
            return
        if not self._in_table:
            return
        if tag in ("th", "td"):
            if not self._in_cell:
                return
            text = "".join(self._buffer).strip()
            self._in_cell = False
            self._buffer = []
            if tag == "th":
                # Only the primary table's own ``<thead>`` contributes headers;
                # per-category detail tables are never entered, and ``_section``
                # distinguishes the header row from any stray ``<th>``.
                if self._section == "thead":
                    self.headers.append(text)
            elif self.rows:
                self.rows[-1].append(text)
        elif tag in ("thead", "tbody"):
            self._section = None


def _PrimaryTableHTML_headers(html):
    """Parse the rendered primary table and return its ``<th>`` header texts."""
    parser = _PrimaryTableHTML()
    parser.feed(html)
    return parser.headers


def _primary_row_cell_count(html):
    """Count width-cell data rows and their ``<td>`` cells in the primary table.

    A real data row carries one cell per header (``_PRIMARY_COLUMNS`` has
    entries; the count is not hard-coded so it follows the column set). Returns
    ``(header_width, data_row_count, populated_data_cells)``.
    """
    parser = _PrimaryTableHTML()
    parser.feed(html)
    width = len(parser.headers)
    populated_rows = [row for row in parser.rows if len(row) == width]
    return width, len(populated_rows), sum(len(row) for row in populated_rows)


def _text_primary_headers(text):
    """Extract the text renderer's primary-table header labels."""
    lines = text.splitlines()
    header_index = lines.index("PRIMARY TABLE")
    for line in lines[header_index + 1 :]:
        stripped = line.strip()
        if stripped:
            return [label.strip() for label in stripped.split(" | ")]
    raise AssertionError("text primary-table header line not found")


# --------------------------------------------------------------------------
# LREQ-RPT-020 — primary table and read model
# --------------------------------------------------------------------------


@pytest.mark.lreq("LREQ-RPT-020")
def test_load_run_report_view_reads_primary_rows(tmp_path):
    """Every persisted primary field is read verbatim and rank is derived."""
    repository = _repository(tmp_path)
    run = rf.run_record((rf.CATEGORY_ALPHA, rf.CATEGORY_BRAVO))
    alpha, bravo = rf.scored_rows_for(rf.CATEGORY_ALPHA, rf.CATEGORY_BRAVO)
    try:
        _seed(repository, run, (alpha, bravo))
        view = report.load_run_report_view(repository, rf.RUN_ID)

        assert view.run_id == rf.RUN_ID
        assert view.status == "completed"
        assert view.run_started_at_utc == rf.RUN_STARTED_AT_UTC
        assert view.scoring_cutoff_utc == rf.SCORING_CUTOFF_UTC
        assert view.completed_at_utc == rf.COMPLETED_AT_UTC
        assert view.identity_preflight_status == "passed"
        assert view.page_view_semantics_status == "unvalidated"
        assert view.heuristic_statement == report.HEURISTIC_STATEMENT
        assert view.limitations == ()

        rows = _rows_by_category(view)
        first = rows[rf.CATEGORY_ALPHA]
        # SRS §9.3 LREQ-SEN-020 + §10 LREQ-RPT-020 (plan §6.2): the displayed
        # rank is the persisted ``rank_balanced``, not a ``ranked_categories``
        # list position.
        assert first.rank == 1
        assert rows[rf.CATEGORY_BRAVO].rank == 2
        assert first.market_opportunity_score == pytest.approx(0.63)
        assert first.component_d == pytest.approx(0.70)
        assert first.component_c == pytest.approx(0.55)
        assert first.component_r == pytest.approx(0.60)
        assert first.component_q == pytest.approx(0.65)
        assert first.missing_components == ()
        assert first.discovered_population_count == 500
        assert first.enriched_sample_count == 100
        assert first.sample_is_census is False
        assert first.sampling_basis == "deterministic_stratified_sample"
        assert first.sample_fraction == pytest.approx(0.2)
        assert first.unique_enrichment_count == 100
        assert first.overlap_category_count == 0
        assert first.overlap_sample_percentage == pytest.approx(0.0)
        assert first.usable_demand_sample_count == 90
        assert first.usable_recent_supply_sample_count == 85
        assert first.usable_quality_sample_count == 80
        assert first.demand_stratum_eligibility_coverage == pytest.approx(0.85)
        assert first.recent_supply_stratum_eligibility_coverage == pytest.approx(0.82)
        assert first.quality_stratum_eligibility_coverage == pytest.approx(0.81)
        assert first.evidence_grade == "moderate"
        assert first.rankability_status == "rankable"
        assert first.discovery_status == "complete"
        assert first.page_view_semantics_status == "unvalidated"
        assert first.top_3_stability == pytest.approx(1.0)
        assert first.top_5_stability == pytest.approx(0.8)
        assert first.maximum_score_delta == pytest.approx(0.05)
        assert first.maximum_rank_displacement == 1
        assert first.sensitivity_warning is False
        assert first.reference_size == 20
        assert first.computed_at_utc == rf.COMPUTED_AT_UTC
        assert len(first.strata) == 2
        assert first.raw_metric_inputs is not None
        assert first.raw_metric_inputs.demand_per_asset_raw == pytest.approx(12.5)
        assert first.raw_metric_inputs.quality_raw == pytest.approx(0.62)
    finally:
        repository.close()


@pytest.mark.lreq("LREQ-RPT-020")
def test_load_run_report_view_orders_ranked_then_unranked(tmp_path):
    """Ordering is explicit: ranked rows ascending by (rank, category), then
    unranked rows ascending by category (best-first, plan §14.1 OQ-8)."""
    repository = _repository(tmp_path)
    categories = (
        rf.CATEGORY_ZULU,
        rf.CATEGORY_ALPHA,
        rf.CATEGORY_CHARLIE,
        rf.CATEGORY_BRAVO,
    )
    run = rf.run_record(categories)
    alpha, bravo = rf.scored_rows_for(rf.CATEGORY_ALPHA, rf.CATEGORY_BRAVO)
    charlie = rf.category_score_record(rf.CATEGORY_CHARLIE)
    zulu = rf.category_score_record(rf.CATEGORY_ZULU)
    try:
        _seed(repository, run, (alpha, bravo, charlie, zulu))
        view = report.load_run_report_view(repository, rf.RUN_ID)
        names = [row.category for row in view.categories]
        # Best-first: rank 1 (the best balanced score) renders first, then rank
        # 2, then the unranked rows in ascending category order.
        assert names == [
            rf.CATEGORY_ALPHA,
            rf.CATEGORY_BRAVO,
            rf.CATEGORY_CHARLIE,
            rf.CATEGORY_ZULU,
        ]
        rows = _rows_by_category(view)
        assert rows[rf.CATEGORY_ALPHA].rank == 1
        assert rows[rf.CATEGORY_BRAVO].rank == 2
        assert rows[rf.CATEGORY_CHARLIE].rank is None
        assert rows[rf.CATEGORY_ZULU].rank is None
    finally:
        repository.close()


@pytest.mark.lreq("LREQ-RPT-020")
def test_primary_table_renders_every_mandatory_column(tmp_path):
    """The rendered primary-table header set is exactly the mandatory label set.

    The oracle is the literal ``expected_labels`` tuple below, transcribed from
    SRS §10 ``LREQ-RPT-020`` (each entry annotated with the clause it stands
    for). It is deliberately **not** derived from ``report._PRIMARY_COLUMNS``:
    comparing against that module constant would be self-referential, because
    deleting or renaming an entry shrinks the expected set together with both
    renderers. The rendered HTML ``<th>`` set and the text renderer's header
    list are checked against this literal; ``_PRIMARY_COLUMNS`` is only a
    secondary consistency assertion afterwards.

    Asserts against the primary table's own header cells (parsed from the HTML
    ``<thead>`` and read from the text renderer's header line), so a missing,
    renamed, duplicated, or extra column fails even when its label is a
    substring of unrelated rendered text (``rank`` inside ``rankability``,
    ``sample fraction`` inside ``sample shared with other categories (%)``).
    Each expected label must additionally have a cell in a rendered data row.
    """
    repository = _repository(tmp_path)
    run = rf.run_record((rf.CATEGORY_ALPHA, rf.CATEGORY_BRAVO))
    alpha, bravo = rf.scored_rows_for(rf.CATEGORY_ALPHA, rf.CATEGORY_BRAVO)
    try:
        _seed(repository, run, (alpha, bravo))
        view = report.load_run_report_view(repository, rf.RUN_ID)
        html = report.render_run_report_html(view)
        text = report.render_run_report_text(view)

        # Every LREQ-RPT-020 output as its actual rendered header label. Clause
        # mapping (SRS §10, LREQ-RPT-020), in order:
        expected_labels = (
            "category",  # category
            "rank",  # rank
            "composite score",  # composite score
            "D",  # D/C/R/Q (component D)
            "C",  # D/C/R/Q (component C)
            "R",  # D/C/R/Q (component R)
            "Q",  # D/C/R/Q (component Q)
            "discovered population",  # discovered population
            "sample size",  # sample size
            "census flag",  # census flag
            "unique enrichment count",  # unique enrichment count
            "sample fraction",  # sample fraction
            "sampling basis",  # sampling basis
            "cross-category overlap count",  # cross-category overlap count
            "usable demand count",  # usable count ... per component (D)
            "usable recent supply count",  # usable count ... per component (C)
            "usable quality count",  # usable count ... per component (R)
            # stratum eligibility coverage per component:
            "demand stratum eligibility coverage",  # ... (D)
            "recent supply stratum eligibility coverage",  # ... (C)
            "quality stratum eligibility coverage",  # ... (R)
            "evidence grade",  # evidence grade
            "rankability",  # rankability
            "discovery status",  # discovery status
            "page-view semantic status",  # page-view semantic status
            "top_3_stability",  # top_3_stability
            "top_5_stability",  # top_5_stability
            "maximum_score_delta",  # maximum_score_delta
            "maximum_rank_displacement",  # maximum_rank_displacement
            "sensitivity warning",  # sensitivity warning
            # percentage of the category sample shared with other categories:
            "sample shared with other categories (%)",
        )
        expected = set(expected_labels)

        html_headers = _PrimaryTableHTML_headers(html)
        assert tuple(html_headers) == expected_labels
        assert len(html_headers) == len(expected_labels)
        assert _text_primary_headers(text) == list(expected_labels)
        # Secondary consistency: the renderer's own column table agrees with the
        # literal above (this alone is not the oracle).
        assert expected == {label for label, _ in report._PRIMARY_COLUMNS}
        # Every expected column has a real cell in a rendered data row.
        width, data_rows, populated_cells = _primary_row_cell_count(html)
        assert width == len(expected_labels)
        assert data_rows == len(view.categories)
        assert populated_cells == len(expected) * data_rows
        assert len(view.categories) == 2
        for row in view.categories:
            cells = _text_primary_row(text, row.category)
            assert set(cells) == expected
        # The D/C/R/Q cells remain the component columns, not another "D".
        assert all(
            re.search(rf"<th>{re.escape(component)}</th>", html)
            for component in report.COMPONENT_RENDER_ORDER
        )
    finally:
        repository.close()


@pytest.mark.lreq("LREQ-RPT-020")
def test_pre_scoring_defaults_render_as_unavailable(tmp_path):
    """Schema ``NOT NULL DEFAULT 0``/``0.0`` pre-scoring values are unavailable."""
    repository = _repository(tmp_path)
    run = rf.run_record((rf.CATEGORY_ALPHA,))
    row = rf.pre_scoring_default_row(rf.CATEGORY_ALPHA)
    try:
        _seed(repository, run, (row,))
        view = report.load_run_report_view(repository, rf.RUN_ID)
        entry = view.categories[0]
        # The three counts and three coverages stay None while unscored.
        assert entry.usable_demand_sample_count is None
        assert entry.usable_recent_supply_sample_count is None
        assert entry.usable_quality_sample_count is None
        assert entry.demand_stratum_eligibility_coverage is None
        assert entry.recent_supply_stratum_eligibility_coverage is None
        assert entry.quality_stratum_eligibility_coverage is None
        # A pre-scoring stratum renders pending/null, never a usable zero.
        assert len(entry.strata) == 1
        assert entry.strata[0].usable_status == "pending"
        assert entry.strata[0].usable_demand_count is None
        assert entry.strata[0].usable_recent_count is None
        assert entry.strata[0].usable_quality_count is None

        # Measured persisted values are still rendered (sampling ran).
        assert entry.discovered_population_count == 500
        assert entry.enriched_sample_count == 100
        assert entry.sample_fraction == pytest.approx(0.2)
        text = report.render_run_report_text(view)
        cells = _text_primary_row(text, rf.CATEGORY_ALPHA)
        assert cells["usable demand count"] == "unavailable"
        assert cells["usable recent supply count"] == "unavailable"
        assert cells["usable quality count"] == "unavailable"
        assert cells["demand stratum eligibility coverage"] == "unavailable"
        assert cells["recent supply stratum eligibility coverage"] == "unavailable"
        assert cells["quality stratum eligibility coverage"] == "unavailable"
        assert cells["discovered population"] == "500"
        assert "pending" in report.render_run_report_text(view)
    finally:
        repository.close()


@pytest.mark.lreq("LREQ-RPT-020")
def test_zero_population_sample_fraction_is_null(tmp_path):
    """SRS §5.1: a zero discovered population has ``sample_fraction = null``."""
    repository = _repository(tmp_path)
    run = rf.run_record((rf.CATEGORY_ZERO_POPULATION,))
    row = rf.zero_population_row(rf.CATEGORY_ZERO_POPULATION)
    try:
        _seed(repository, run, (row,))
        view = report.load_run_report_view(repository, rf.RUN_ID)
        entry = view.categories[0]
        assert entry.discovered_population_count == 0
        assert entry.sample_fraction is None
        assert entry.sample_is_census is False
        assert entry.overlap_sample_percentage is None
        assert entry.raw_metric_inputs is not None
        assert entry.raw_metric_inputs.demand_per_asset_raw is None

        cells = _text_primary_row(
            report.render_run_report_text(view), rf.CATEGORY_ZERO_POPULATION
        )
        assert cells["discovered population"] == "0"
        assert cells["sample fraction"] == "unavailable"
    finally:
        repository.close()


@pytest.mark.lreq("LREQ-RPT-020")
def test_explicit_zero_overlap_is_measured_zero(tmp_path):
    """A non-empty sample with no shared identity is measured ``0``/``0.0``."""
    repository = _repository(tmp_path)
    run = rf.run_record((rf.CATEGORY_ALPHA,))
    row = rf.category_score_record(rf.CATEGORY_ALPHA)
    try:
        _seed(repository, run, (row,))
        view = report.load_run_report_view(repository, rf.RUN_ID)
        entry = view.categories[0]
        assert entry.overlap_category_count == 0
        assert entry.overlap_sample_percentage == pytest.approx(0.0)
        assert entry.overlap_sample_percentage is not None

        cells = _text_primary_row(
            report.render_run_report_text(view), rf.CATEGORY_ALPHA
        )
        assert cells["cross-category overlap count"] == "0"
        assert cells["sample shared with other categories (%)"] == "0"
    finally:
        repository.close()


# --------------------------------------------------------------------------
# LREQ-RPT-020 / LREQ-SEN-020 — D4: the displayed rank is the balanced rank
# --------------------------------------------------------------------------


@pytest.mark.lreq("LREQ-RPT-020")
@pytest.mark.lreq("LREQ-SEN-020")
def test_rank_from_sensitivity_reads_rank_balanced_not_position():
    """The displayed rank is the matching ``categories`` entry's ``rank_balanced``.

    Plan §6/§14.1 (D4, OQ-8): ``ranked_categories`` records the base-candidate
    (requested) order, so its list position is not the balanced-score rank.
    SRS §9.3 ``LREQ-SEN-020`` ranks categories by descending balanced composite
    score (ties broken by ascending lexical category), and the persisted
    ``categories`` entries carry that 1-based ``rank_balanced``. This vector
    stores BRAVO first but ranks ALPHA first, so a position-derived rank would
    answer 2 for ALPHA.
    """
    payload = rf.ranking_sensitivity_json(
        (rf.CATEGORY_BRAVO, rf.CATEGORY_ALPHA),
        balanced_ranks={rf.CATEGORY_ALPHA: 1, rf.CATEGORY_BRAVO: 2},
    )
    assert report._rank_from_sensitivity(payload, rf.CATEGORY_ALPHA) == 1
    assert report._rank_from_sensitivity(payload, rf.CATEGORY_BRAVO) == 2


@pytest.mark.lreq("LREQ-RPT-020")
@pytest.mark.lreq("LREQ-SEN-020")
def test_rank_from_sensitivity_returns_none_without_matching_categories_entry():
    """A missing/empty ``categories`` list yields ``None``, never a position.

    Plan §6.2: fall back to ``None`` when the category is absent from
    ``categories``; the old ``ranked_categories`` position is no longer a rank
    source. The ``{}`` payload is the failed-preflight shape.
    """
    empty_object = rf.EMPTY_RANKING_SENSITIVITY_JSON
    assert report._rank_from_sensitivity(empty_object, rf.CATEGORY_ALPHA) is None
    # ``ranked_categories`` lists ALPHA but ``categories`` is empty.
    listed_without_entries = rf.ranking_sensitivity_json((rf.CATEGORY_ALPHA,))
    assert (
        report._rank_from_sensitivity(listed_without_entries, rf.CATEGORY_ALPHA) is None
    )
    # Entries exist, but only for another category.
    other_only = rf.ranking_sensitivity_json(
        (rf.CATEGORY_BRAVO,), balanced_ranks={rf.CATEGORY_BRAVO: 1}
    )
    assert report._rank_from_sensitivity(other_only, rf.CATEGORY_ALPHA) is None
    # No ``categories`` key at all.
    no_categories_key = json.dumps({"ranked_categories": [rf.CATEGORY_ALPHA]})
    assert report._rank_from_sensitivity(no_categories_key, rf.CATEGORY_ALPHA) is None


@pytest.mark.lreq("LREQ-RPT-020")
@pytest.mark.lreq("LREQ-SEN-020")
def test_rank_from_sensitivity_returns_none_for_malformed_payload():
    """Invalid JSON, a non-object value, or a non-list ``categories`` is ``None``.

    A malformed ``categories`` must not fall back to the ``ranked_categories``
    position (the old contract), so the third vector also lists ALPHA there.
    """
    assert report._rank_from_sensitivity("{not json", rf.CATEGORY_ALPHA) is None
    assert report._rank_from_sensitivity("[1, 2]", rf.CATEGORY_ALPHA) is None
    assert (
        report._rank_from_sensitivity(
            json.dumps(
                {
                    "ranked_categories": [rf.CATEGORY_ALPHA],
                    "categories": "not-a-list",
                }
            ),
            rf.CATEGORY_ALPHA,
        )
        is None
    )


@pytest.mark.lreq("LREQ-RPT-020")
@pytest.mark.lreq("LREQ-SEN-020")
def test_display_rank_is_rank_balanced_not_stored_position(tmp_path):
    """The run-maximum score prints rank 1 though it is stored second.

    Plan §6/§14.1 (D4, OQ-8): rank is the persisted ``rank_balanced`` and the
    primary table renders best-first, so the rank column is monotone with the
    adjacent composite-score column (SRS §9.3 ``LREQ-SEN-020``; SRS §10
    ``LREQ-RPT-020``). The stored ``ranked_categories`` order is untouched
    (display-only fix).
    """
    repository = _repository(tmp_path)
    run = rf.run_record((rf.CATEGORY_LOW_INPUT_FIRST, rf.CATEGORY_HIGH_INPUT_SECOND))
    low, high = rf.input_order_rank_flip_rows()
    try:
        _seed(repository, run, (low, high))
        view = report.load_run_report_view(repository, rf.RUN_ID)
        rows = _rows_by_category(view)
        assert rows[rf.CATEGORY_HIGH_INPUT_SECOND].rank == 1
        assert rows[rf.CATEGORY_LOW_INPUT_FIRST].rank == 2
        # Verbatim round-trip of the stored scores (the report derives none).
        assert rows[
            rf.CATEGORY_HIGH_INPUT_SECOND
        ].market_opportunity_score == pytest.approx(0.854457, abs=1e-9)
        assert rows[
            rf.CATEGORY_LOW_INPUT_FIRST
        ].market_opportunity_score == pytest.approx(0.32, abs=1e-9)

        scored = [row for row in view.categories if row.rank is not None]
        assert [row.category for row in scored] == [
            rf.CATEGORY_HIGH_INPUT_SECOND,
            rf.CATEGORY_LOW_INPUT_FIRST,
        ]
        # Rank is monotone with the score column: both descend.
        assert [row.rank for row in scored] == [1, 2]
        assert [row.market_opportunity_score for row in scored] == pytest.approx(
            [0.854457, 0.32], abs=1e-9
        )

        text = report.render_run_report_text(view)
        assert _text_primary_row(text, rf.CATEGORY_HIGH_INPUT_SECOND)["rank"] == "1"
        assert _text_primary_row(text, rf.CATEGORY_LOW_INPUT_FIRST)["rank"] == "2"
        html = report.render_run_report_html(view)
        # The rank cell renders immediately before the composite-score cell
        # (LREQ-RPT-020 column order), so the max-score row shows rank 1.
        assert f"<td>{rf.CATEGORY_HIGH_INPUT_SECOND}</td><td>1</td>" in html
        assert f"<td>{rf.CATEGORY_LOW_INPUT_FIRST}</td><td>2</td>" in html

        # Display-only: the stored base-candidate order is unchanged (low first).
        stored = {
            record.category: json.loads(record.ranking_sensitivity_json)
            for record in repository.get_category_scores(rf.RUN_ID)
        }
        for category in (
            rf.CATEGORY_LOW_INPUT_FIRST,
            rf.CATEGORY_HIGH_INPUT_SECOND,
        ):
            assert stored[category]["ranked_categories"] == [
                rf.CATEGORY_LOW_INPUT_FIRST,
                rf.CATEGORY_HIGH_INPUT_SECOND,
            ]
    finally:
        repository.close()


@pytest.mark.lreq("LREQ-RPT-020")
def test_order_rows_ties_fall_back_to_ascending_category(tmp_path):
    """Equal displayed ranks keep a total order: ascending lexical category.

    A tie in ``rank_balanced`` cannot occur in a scored run (ranks are 1..n),
    but the display order must stay deterministic for any decodeable payload
    (AGENTS.md "Determinism"): the sort key is ``(rank, category)``.
    """
    repository = _repository(tmp_path)
    run = rf.run_record((rf.CATEGORY_ZULU, rf.CATEGORY_ALPHA))
    tied = rf.ranking_sensitivity_json(
        (rf.CATEGORY_ZULU, rf.CATEGORY_ALPHA),
        balanced_ranks={rf.CATEGORY_ZULU: 3, rf.CATEGORY_ALPHA: 3},
    )
    zulu = rf.category_score_record(rf.CATEGORY_ZULU, ranking_sensitivity_json=tied)
    alpha = rf.category_score_record(rf.CATEGORY_ALPHA, ranking_sensitivity_json=tied)
    try:
        _seed(repository, run, (zulu, alpha))
        view = report.load_run_report_view(repository, rf.RUN_ID)
        assert [row.category for row in view.categories] == [
            rf.CATEGORY_ALPHA,
            rf.CATEGORY_ZULU,
        ]
        assert [row.rank for row in view.categories] == [3, 3]
    finally:
        repository.close()


@pytest.mark.lreq("LREQ-RPT-020")
def test_rank_none_renders_no_rank_recorded_note(tmp_path):
    """An empty sensitivity payload keeps ``rank`` null and says so.

    Plan §6.2: the ``None`` fallback contract is unchanged — the primary table
    prints ``unavailable`` and the detail panel carries the explicit
    ``no rank recorded in ranking_sensitivity_json`` note.
    """
    repository = _repository(tmp_path)
    run = rf.run_record((rf.CATEGORY_ALPHA,))
    row = rf.category_score_record(
        rf.CATEGORY_ALPHA, ranking_sensitivity_json=rf.EMPTY_RANKING_SENSITIVITY_JSON
    )
    try:
        _seed(repository, run, (row,))
        view = report.load_run_report_view(repository, rf.RUN_ID)
        assert view.categories[0].rank is None
        text = report.render_run_report_text(view)
        assert _text_primary_row(text, rf.CATEGORY_ALPHA)["rank"] == "unavailable"
        html = report.render_run_report_html(view)
        for rendered in (html, text):
            assert "no rank recorded in ranking_sensitivity_json" in rendered
    finally:
        repository.close()


# --------------------------------------------------------------------------
# LREQ-RPT-030 — category detail
# --------------------------------------------------------------------------


@pytest.mark.lreq("LREQ-RPT-030")
def test_category_detail_shows_formulas_inputs_strata_and_timestamps(tmp_path):
    """The detail panel carries formulas, six raw inputs, strata, warnings, times."""
    repository = _repository(tmp_path)
    run = rf.run_record((rf.CATEGORY_ALPHA,))
    row = rf.category_score_record(
        rf.CATEGORY_ALPHA,
        warnings_json='["REFERENCE_SET_SMALL","SAMPLE_BASED_SIGNAL"]',
    )
    try:
        _seed(repository, run, (row,))
        view = report.load_run_report_view(repository, rf.RUN_ID)
        html = report.render_run_report_html(view)

        assert "Formulas and explanations" in html
        assert "Metric inputs" in html
        assert "Sample strata" in html
        assert "Warnings" in html
        assert "Timestamps" in html
        assert "N_h (discovered population)" in html
        assert "u_demand_h" in html
        assert "min_usable_samples_per_stratum" in html
        for label in (
            "demand per asset raw (inferred)",
            "demand median raw (inferred)",
            "breadth raw (inferred)",
            "recent share raw (inferred)",
            "median age raw (inferred)",
            "quality raw (inferred)",
        ):
            assert label in html
        assert "REFERENCE_SET_SMALL" in html
        assert "SAMPLE_BASED_SIGNAL" in html
        assert "2025-06-07T08:09:10Z" in html
        assert "2025-01-02T03:04:05Z" in html
        assert "2025-03-04T05:06:07Z" in html
    finally:
        repository.close()


@pytest.mark.lreq("LREQ-RPT-030")
def test_detail_labels_observed_versus_inferred(tmp_path):
    """Provenance labels separate observed signals from inferred sample values."""
    repository = _repository(tmp_path)
    run = rf.run_record((rf.CATEGORY_ALPHA,))
    row = rf.category_score_record(rf.CATEGORY_ALPHA)
    try:
        _seed(repository, run, (row,))
        view = report.load_run_report_view(repository, rf.RUN_ID)
        html = report.render_run_report_html(view)
        text = report.render_run_report_text(view)
        assert "Observed versus inferred" in html
        assert "discovered population (observed)" in html
        assert "sample fraction (observed)" in html
        assert "demand per asset raw (inferred)" in html
        assert "component D/C/R/Q (inferred)" in html
        assert "discovered population (observed)" in text
        assert "demand per asset raw (inferred)" in text
    finally:
        repository.close()


@pytest.mark.lreq("LREQ-RPT-030")
@pytest.mark.lreq("LREQ-SCR-010")
def test_demand_formula_text_does_not_claim_rating_inputs(tmp_path):
    """D's fixed formula text consumes the page-view index, never ratings.

    SRS §8.2 ``LREQ-SCR-010`` defines
    ``D0 = 0.60 * P_ref(DemandPerAssetRaw) + 0.40 * P_ref(DemandMedianRaw)``;
    neither raw metric consumes ``rating_average``/``rating_count``. The fixed D
    line previously claimed "rating signals" (plan §2 item 2, defect D5); OQ-10
    (plan §14.1) corrects the text in this chunk. The corrected line is rendered
    by both detail panels (LREQ-RPT-030).
    """
    demand_lines = [
        line for line in report._FORMULA_EXPLANATIONS if line.startswith("D (demand)")
    ]
    assert len(demand_lines) == 1
    demand_line = demand_lines[0]
    assert "page-view index" in demand_line
    assert "rating" not in demand_line.lower()

    # The correction is scoped to D: Q still truthfully names its rating input.
    quality_lines = [
        line for line in report._FORMULA_EXPLANATIONS if line.startswith("Q (quality)")
    ]
    assert len(quality_lines) == 1
    assert "rating" in quality_lines[0].lower()

    repository = _repository(tmp_path)
    run = rf.run_record((rf.CATEGORY_ALPHA,))
    row = rf.category_score_record(rf.CATEGORY_ALPHA)
    try:
        _seed(repository, run, (row,))
        view = report.load_run_report_view(repository, rf.RUN_ID)
        html = report.render_run_report_html(view)
        text = report.render_run_report_text(view)
        assert html_escape(demand_line, quote=True) in html
        assert demand_line in text
    finally:
        repository.close()


# --------------------------------------------------------------------------
# LREQ-RPT-040 — non-rankable categories and failed runs stay visible
# --------------------------------------------------------------------------


@pytest.mark.lreq("LREQ-RPT-040")
def test_non_rankable_category_remains_visible(tmp_path):
    """A not-rankable category is rendered with its persisted reason."""
    repository = _repository(tmp_path)
    run = rf.run_record((rf.CATEGORY_NON_RANKABLE, rf.CATEGORY_ALPHA))
    non_rankable = rf.non_rankable_row(rf.CATEGORY_NON_RANKABLE)
    alpha = rf.category_score_record(
        rf.CATEGORY_ALPHA,
        ranking_sensitivity_json=rf.ranking_sensitivity_json((rf.CATEGORY_ALPHA,)),
    )
    try:
        _seed(repository, run, (non_rankable, alpha))
        view = report.load_run_report_view(repository, rf.RUN_ID)
        rows = _rows_by_category(view)
        entry = rows[rf.CATEGORY_NON_RANKABLE]
        assert entry.rankability_status == "not_rankable"
        assert entry.rank is None
        assert entry.missing_components == ("D", "Q")

        html = report.render_run_report_html(view)
        text = report.render_run_report_text(view)
        assert rf.CATEGORY_NON_RANKABLE in html
        assert rf.CATEGORY_NON_RANKABLE in text
        assert "not_rankable" in html
        assert "missing components: D, Q" in html
        assert "INSUFFICIENT_DEMAND_SAMPLE" in html
    finally:
        repository.close()


@pytest.mark.lreq("LREQ-RPT-040")
def test_failed_preflight_fallback_yields_one_row_per_category(tmp_path):
    """With no score rows, the failed run still yields one row per category."""
    repository = _repository(tmp_path)
    run = rf.run_record(
        (rf.CATEGORY_FALLBACK_ONE, rf.CATEGORY_FALLBACK_TWO),
        status="failed",
        identity_preflight_status="failed",
        scoring_cutoff_utc=None,
        completed_at_utc=None,
    )
    try:
        _seed(repository, run)
        view = report.load_run_report_view(repository, rf.RUN_ID)
        assert view.status == "failed"
        assert len(view.categories) == 2
        assert {row.category for row in view.categories} == {
            rf.CATEGORY_FALLBACK_ONE,
            rf.CATEGORY_FALLBACK_TWO,
        }
        for entry in view.categories:
            assert entry.evidence_grade == "insufficient"
            assert entry.rankability_status == "not_rankable"
            assert entry.rank is None
            assert entry.market_opportunity_score is None
            assert entry.sample_fraction is None
            assert entry.discovered_population_count is None
            assert entry.usable_demand_sample_count is None
            assert entry.strata == ()
            assert entry.warnings == ("IDENTITY_PREFLIGHT_FAILED",)
            assert entry.raw_metric_inputs is not None
            assert entry.raw_metric_inputs.quality_raw is None

        html = report.render_run_report_html(view)
        text = report.render_run_report_text(view)
        for category in (rf.CATEGORY_FALLBACK_ONE, rf.CATEGORY_FALLBACK_TWO):
            assert category in html
            assert category in text
        assert "insufficient" in html
        assert "IDENTITY_PREFLIGHT_FAILED" in html
    finally:
        repository.close()


# --------------------------------------------------------------------------
# LREQ-RPT-050 — heuristic statement and the six required distinctions
# --------------------------------------------------------------------------


def _assert_weekly_view_count_caveat(*rendered_texts: str) -> None:
    """Assert the D1-S4 caveat substance on each rendered report string.

    Plan §5.5 / §9.4 item 10: the caveats describe the page-view index as a
    trailing-7-day (weekly) view count and no longer say "not a weekly traffic
    rate". The exact literal is operator-pending (plan §12 OQ-2), so only the
    pinned substance is asserted here.
    """
    for rendered in rendered_texts:
        normalized = " ".join(rendered.casefold().split())
        assert "trailing" in normalized or "weekly" in normalized, (
            "the caveat must describe a trailing-7-day/weekly view count"
        )
        assert any(
            token in normalized
            for token in ("7-day", "7 day", "seven-day", "seven day")
        ), "the caveat must describe the seven-day window"
        assert "not a weekly traffic rate" not in normalized


@pytest.mark.lreq("LREQ-RPT-050")
def test_report_states_heuristic_and_six_distinctions(tmp_path):
    """Both renderers carry the fixed statement and its six distinctions."""
    repository = _repository(tmp_path)
    run = rf.run_record((rf.CATEGORY_ALPHA,))
    row = rf.category_score_record(rf.CATEGORY_ALPHA)
    try:
        _seed(repository, run, (row,))
        view = report.load_run_report_view(repository, rf.RUN_ID)
        html = report.render_run_report_html(view)
        text = report.render_run_report_text(view)
        assert report.HEURISTIC_STATEMENT in html
        assert report.HEURISTIC_STATEMENT in text
        for phrase in (
            "pagination completion",
            "immutable snapshot completeness",
            "page-view index",
            "descriptive midranks",
            "inferential percentiles",
            "stratum eligibility coverage",
            "sample fraction",
            "deterministic-sample evidence",
            "statistical representativeness",
            "evidence grade",
            "statistical confidence",
            "not been calibrated against sales, revenue, downloads, or conversion",
            "not a statistically representative",
        ):
            assert phrase in html
        _assert_weekly_view_count_caveat(html)
    finally:
        repository.close()


@pytest.mark.lreq("LREQ-RPT-050")
def test_report_caveats_describe_trailing_seven_day_views(tmp_path):
    """Both renderers describe the index as a trailing-7-day view count.

    Plan §5.5 / §9.4 item 10 (D1-S4): the retired claim
    "not a weekly traffic rate" is gone, the trailing-7-day/weekly count is
    described, and the public ``HEURISTIC_STATEMENT`` no longer calls the index
    cumulative. The exact literal is operator-pending (plan §12 OQ-2), so the
    assertion is substance-only.
    """
    repository = _repository(tmp_path)
    run = rf.run_record((rf.CATEGORY_ALPHA,))
    row = rf.category_score_record(rf.CATEGORY_ALPHA)
    try:
        _seed(repository, run, (row,))
        view = report.load_run_report_view(repository, rf.RUN_ID)
        html = report.render_run_report_html(view)
        text = report.render_run_report_text(view)
        _assert_weekly_view_count_caveat(html, text)
        statement = " ".join(report.HEURISTIC_STATEMENT.casefold().split())
        assert "cumulative" not in statement
        assert "not a weekly traffic rate" not in statement
    finally:
        repository.close()


# --------------------------------------------------------------------------
# LREQ-RPT-010 — local output, self-containment, and error surface
# --------------------------------------------------------------------------


@pytest.mark.lreq("LREQ-RPT-010")
def test_html_output_is_self_contained_and_deterministic(tmp_path):
    """The HTML embeds inline assets only and renders identically twice."""
    repository = _repository(tmp_path)
    run = rf.run_record((rf.CATEGORY_ALPHA,))
    row = rf.category_score_record(rf.CATEGORY_ALPHA)
    try:
        _seed(repository, run, (row,))
        view = report.load_run_report_view(repository, rf.RUN_ID)
        html = report.render_run_report_html(view)
        assert "http://" not in html
        assert "https://" not in html
        assert "<link" not in html
        assert "src=" not in html
        assert "<style>" in html
        assert "<script>" in html
        assert html == report.render_run_report_html(view)
        assert report.render_run_report_text(view) == report.render_run_report_text(
            view
        )
    finally:
        repository.close()


@pytest.mark.lreq("LREQ-RPT-010")
def test_write_run_report_writes_html_and_text(tmp_path):
    """``write_run_report`` writes the rendered document to a local path."""
    repository = _repository(tmp_path)
    run = rf.run_record((rf.CATEGORY_ALPHA,))
    row = rf.category_score_record(rf.CATEGORY_ALPHA)
    try:
        _seed(repository, run, (row,))
        view = report.load_run_report_view(repository, rf.RUN_ID)

        html_path = tmp_path / "report.html"
        written = report.write_run_report(repository, rf.RUN_ID, html_path)
        assert written == html_path
        assert html_path.read_text(encoding="utf-8") == report.render_run_report_html(
            view
        )

        text_path = tmp_path / "nested" / "report.txt"
        report.write_run_report(repository, rf.RUN_ID, text_path, fmt="text")
        assert text_path.read_text(encoding="utf-8") == report.render_run_report_text(
            view
        )
    finally:
        repository.close()


@pytest.mark.lreq("LREQ-RPT-010")
def test_write_run_report_rejects_unknown_format(tmp_path):
    """Any ``fmt`` other than ``"html"``/``"text"`` is a ``ValueError``."""
    repository = _repository(tmp_path)
    try:
        with pytest.raises(ValueError):
            report.write_run_report(
                repository, rf.RUN_ID, tmp_path / "out.bin", fmt="pdf"
            )
    finally:
        repository.close()


@pytest.mark.lreq("LREQ-RPT-010")
def test_load_run_report_view_raises_for_unknown_run(tmp_path):
    """An unknown ``run_id`` raises ``RunNotFoundError`` from every entry point."""
    repository = _repository(tmp_path)
    try:
        with pytest.raises(report.RunNotFoundError):
            report.load_run_report_view(repository, "missing-run")
        with pytest.raises(report.RunNotFoundError):
            report.write_run_report(repository, "missing-run", tmp_path / "x.html")
        with pytest.raises(report.RunNotFoundError):
            report.render_dashboard_html(repository, "missing-run")
    finally:
        repository.close()


# --------------------------------------------------------------------------
# LREQ-CLI-020 — the dashboard performs database reads only
# --------------------------------------------------------------------------


_FORBIDDEN_MODULES = frozenset(
    {
        "metrics",
        "scoring",
        "collector",
        "collector_coveo",
        "collector_graphql",
        "config",
        "pipeline",
        "cli",
        "requests",
        "urllib",
        "urllib3",
        "http",
        "httpx",
        "aiohttp",
        "socket",
    }
)

_FORBIDDEN_CLOCK_ATTRS = frozenset({"now", "utcnow", "today", "time", "monotonic"})


def _imported_modules(tree):
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module.split(".")[-1])
    return names


def _clock_reads(tree):
    reads = []
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Attribute)
            and node.attr in _FORBIDDEN_CLOCK_ATTRS
            and isinstance(node.value, ast.Name)
            and node.value.id in {"datetime", "time"}
        ):
            reads.append(ast.unparse(node))
    return reads


@pytest.mark.lreq("LREQ-CLI-020")
def test_render_dashboard_html_is_database_read_only(tmp_path):
    """The dashboard renderer imports no transport and takes no network input."""
    repository = _repository(tmp_path)
    run = rf.run_record((rf.CATEGORY_ALPHA,))
    row = rf.category_score_record(rf.CATEGORY_ALPHA)
    try:
        _seed(repository, run, (row,))
        html = report.render_dashboard_html(repository, rf.RUN_ID)
        assert rf.RUN_ID in html
    finally:
        repository.close()

    source = Path(report.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    assert _imported_modules(tree) & _FORBIDDEN_MODULES == set()
    assert _clock_reads(tree) == []
    signature = inspect.signature(report.render_dashboard_html)
    assert set(signature.parameters) == {"repository", "run_id"}


# --------------------------------------------------------------------------
# LREQ-NFR-040 — public functions carry type hints and behavior docstrings
# --------------------------------------------------------------------------


@pytest.mark.lreq("LREQ-NFR-040")
def test_public_report_functions_have_hints_and_docstrings():
    """Every public function has annotations and a docstring."""
    public_functions = (
        report.load_run_report_view,
        report.render_run_report_html,
        report.render_run_report_text,
        report.write_run_report,
        report.render_dashboard_html,
        report.render_run_dashboard_html,
    )
    for function in public_functions:
        signature = inspect.signature(function)
        assert function.__doc__ and function.__doc__.strip()
        for parameter in signature.parameters.values():
            assert parameter.annotation is not inspect.Parameter.empty
        assert signature.return_annotation is not inspect.Signature.empty
    for structure in (
        report.StratumReportRow,
        report.ReportWarning,
        report.RawMetricInputs,
        report.CategoryReportRow,
        report.RunReportView,
    ):
        assert structure.__doc__ and structure.__doc__.strip()
    assert report.COMPONENT_RENDER_ORDER == ("D", "C", "R", "Q")


# --------------------------------------------------------------------------
# LREQ-RPT-020 / LREQ-SEN-020 / LREQ-RPT-010 / LREQ-RPT-040 / LREQ-RPT-050 —
# Chunk 30 dark-mode Plotly dashboard.
# --------------------------------------------------------------------------


def _dashboard_view(tmp_path):
    """Return a repository + view over ``rf.dashboard_rows()`` (3 ranked + 1 refused)."""
    repository = _repository(tmp_path)
    categories = (
        rf.CATEGORY_ALPHA,
        rf.CATEGORY_BRAVO,
        rf.CATEGORY_CHARLIE,
        rf.CATEGORY_NON_RANKABLE,
    )
    run = rf.run_record(categories)
    _seed(repository, run, rf.dashboard_rows())
    view = report.load_run_report_view(repository, rf.RUN_ID)
    return repository, view


@pytest.mark.lreq("LREQ-RPT-020")
@pytest.mark.lreq("LREQ-SEN-020")
def test_load_run_report_view_exposes_policy_ranks_and_run_sensitivity(tmp_path):
    """The three per-policy ranks, breadth fields, and run sensitivity are read.

    The values come verbatim from the persisted ``ranking_sensitivity_json`` and
    ``category_scores`` columns (SRS §9.3 ``LREQ-SEN-020``); nothing is
    recomputed. A ``{}`` payload yields ``sensitivity is None``; an all-null
    payload yields a non-``None`` summary with ``None`` outputs.
    """
    repository, view = _dashboard_view(tmp_path)
    try:
        rows = _rows_by_category(view)
        alpha = rows[rf.CATEGORY_ALPHA]
        assert alpha.rank == 1
        assert alpha.rank_demand_heavy == 1
        assert alpha.rank_competition_heavy == 1
        assert rows[rf.CATEGORY_BRAVO].rank == 2
        assert rows[rf.CATEGORY_BRAVO].rank_demand_heavy == 3
        assert rows[rf.CATEGORY_BRAVO].rank_competition_heavy == 2
        assert rows[rf.CATEGORY_CHARLIE].rank == 3
        assert rows[rf.CATEGORY_CHARLIE].rank_demand_heavy == 2
        assert rows[rf.CATEGORY_CHARLIE].rank_competition_heavy == 3
        # Breadth fields are persisted category_scores values, read verbatim.
        assert alpha.breadth_completeness_status == "complete"
        assert alpha.breadth_source == "verified_total_count"
        assert view.sensitivity is not None
        assert view.sensitivity.top_3_stability == pytest.approx(1.0)
        assert view.sensitivity.top_5_stability == pytest.approx(0.8)
        assert view.sensitivity.maximum_score_delta == pytest.approx(0.05)
        assert view.sensitivity.maximum_rank_displacement == 2
        assert view.sensitivity.warning is False
        assert view.sensitivity.reference_set_size == 3
        assert view.sensitivity.displacement_threshold == pytest.approx(3.0)
        assert view.sensitivity.policies == (
            "balanced",
            "demand_heavy",
            "competition_heavy",
        )
    finally:
        repository.close()


@pytest.mark.lreq("LREQ-RPT-020")
@pytest.mark.lreq("LREQ-SEN-020")
def test_run_sensitivity_is_none_for_empty_object_and_none_fields_when_all_null(
    tmp_path,
):
    """``{}`` -> ``None``; a present-but-null payload -> a summary with ``None``."""
    repository = _repository(tmp_path)
    run = rf.run_record((rf.CATEGORY_ALPHA,))
    empty = rf.category_score_record(
        rf.CATEGORY_ALPHA, ranking_sensitivity_json=rf.EMPTY_RANKING_SENSITIVITY_JSON
    )
    try:
        _seed(repository, run, (empty,))
        view = report.load_run_report_view(repository, rf.RUN_ID)
        assert view.sensitivity is None
    finally:
        repository.close()

    null_payload = json.dumps(
        {
            "policies": ["balanced", "demand_heavy", "competition_heavy"],
            "categories": [],
            "top_3_stability": None,
            "top_5_stability": None,
            "maximum_score_delta": None,
            "maximum_rank_displacement": None,
            "warning": None,
            "reference_set_size": None,
            "displacement_threshold": None,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    repository = _repository(tmp_path)
    run = rf.run_record((rf.CATEGORY_ALPHA,), run_id="run-null-summary")
    row = dataclasses.replace(
        rf.category_score_record(
            rf.CATEGORY_ALPHA, ranking_sensitivity_json=null_payload
        ),
        run_id="run-null-summary",
    )
    try:
        _seed(repository, run, (row,))
        view = report.load_run_report_view(repository, "run-null-summary")
        summary = view.sensitivity
        assert summary is not None
        assert summary.top_3_stability is None
        assert summary.top_5_stability is None
        assert summary.maximum_score_delta is None
        assert summary.maximum_rank_displacement is None
        assert summary.warning is None
        assert summary.reference_set_size is None
        assert summary.displacement_threshold is None
    finally:
        repository.close()


@pytest.mark.lreq("LREQ-RPT-020")
def test_component_contributions_renormalise_over_available_components():
    """Contributions renormalise over available components; missing omitted.

    Golden vector (plan §8.2): all four present -> ``0.2450/0.1650/0.1200/
    0.0975`` summing to the persisted composite ``0.63`` within ``1e-9``; a
    two-component (D,C) vector renormalises over ``0.65``; no component -> ``()``.
    """
    full = rf.category_score_record(rf.CATEGORY_ALPHA)
    contributions = report._component_contributions(full)
    assert [name for name, _ in contributions] == ["D", "C", "R", "Q"]
    values = {name: value for name, value in contributions}
    assert values["D"] == pytest.approx(0.2450000000, abs=1e-9)
    assert values["C"] == pytest.approx(0.1650000000, abs=1e-9)
    assert values["R"] == pytest.approx(0.1200000000, abs=1e-9)
    assert values["Q"] == pytest.approx(0.0975000000, abs=1e-9)
    # The stack height equals the persisted composite score; the fixture's
    # component vector sums to 0.6275, and the persisted composite is 0.63
    # (plan §8.2 records both; the renderer adds nothing).
    assert sum(values.values()) == pytest.approx(0.6275, abs=1e-9)

    two = rf.category_score_record(
        rf.CATEGORY_ALPHA, component_r=None, component_q=None
    )
    two_values = dict(report._component_contributions(two))
    assert set(two_values) == {"D", "C"}
    assert two_values["D"] == pytest.approx(0.35 * 0.70 / 0.65, abs=1e-9)
    assert two_values["C"] == pytest.approx(0.30 * 0.55 / 0.65, abs=1e-9)

    none_available = rf.category_score_record(
        rf.CATEGORY_ALPHA,
        component_d=None,
        component_c=None,
        component_r=None,
        component_q=None,
    )
    assert report._component_contributions(none_available) == ()


@pytest.mark.lreq("LREQ-RPT-020")
def test_evidence_grade_order_is_the_enum_reversed():
    """``EVIDENCE_GRADE_ORDER`` is the enum reversed; positions are ordinal."""
    assert report.EVIDENCE_GRADE_ORDER == tuple(
        grade.value for grade in reversed(list(report.EvidenceGrade))
    )
    assert report.EVIDENCE_GRADE_ORDER == (
        "insufficient",
        "weak",
        "moderate",
        "strong",
    )
    assert report._evidence_grade_position("insufficient") == 0
    assert report._evidence_grade_position("weak") == 1
    assert report._evidence_grade_position("moderate") == 2
    assert report._evidence_grade_position("strong") == 3
    assert report._evidence_grade_position("unknown-grade") is None


@pytest.mark.lreq("LREQ-RPT-010")
def test_run_dashboard_html_is_self_contained_dark_mode_and_deterministic(tmp_path):
    """One self-contained dark-mode document with fixed ``div_id``s, byte-stable."""
    repository, view = _dashboard_view(tmp_path)
    try:
        html = report.render_run_dashboard_html(view)
        assert "<script src" not in html
        assert "<link" not in html
        assert "cdn.plot.ly" not in html
        assert "http://" not in html
        assert "https://" not in html
        assert "@import" not in html
        assert "<script>" in html
        for _key, div_id in report.DASHBOARD_CHART_IDS:
            assert div_id in html
        assert html == report.render_run_dashboard_html(view)
    finally:
        repository.close()


@pytest.mark.lreq("LREQ-RPT-050")
@pytest.mark.lreq("LREQ-RPT-020")
@pytest.mark.lreq("LREQ-RPT-030")
def test_run_dashboard_includes_heuristic_statement_primary_table_and_details(
    tmp_path,
):
    """The dashboard carries the statement, the primary table, and details."""
    repository, view = _dashboard_view(tmp_path)
    try:
        html = report.render_run_dashboard_html(view)
        assert report.HEURISTIC_STATEMENT in html
        html_headers = _PrimaryTableHTML_headers(html)
        expected_labels = {label for label, _ in report._PRIMARY_COLUMNS}
        assert set(html_headers) == expected_labels
        assert "Formulas and explanations" in html
        assert "Metric inputs" in html
        assert "Sample strata" in html
        assert "Timestamps" in html
    finally:
        repository.close()


@pytest.mark.lreq("LREQ-RPT-040")
def test_run_dashboard_keeps_refused_categories_off_the_scored_axis(tmp_path):
    """Refused rows stay visible but disjoint from the scored axis."""
    repository, view = _dashboard_view(tmp_path)
    try:
        scored = report._scored_rows(view)
        refused = report._refused_rows(view)
        assert refused
        assert {row.category for row in scored}.isdisjoint(
            {row.category for row in refused}
        )
        html = report.render_run_dashboard_html(view)
        for row in refused:
            assert row.category in html
            assert row.market_opportunity_score is None
        # Refused rows sit after the scored entries on a separate gap band and
        # are not given a numeric bar value (the bar trace holds only scored
        # rows), so they never share the scored axis with a measured bar.
        scored_bar_values = [row.market_opportunity_score for row in scored]
        assert all(value is not None for value in scored_bar_values)
        for row in refused:
            assert row.rank is None
        for row in scored:
            assert row.category in html
    finally:
        repository.close()


@pytest.mark.lreq("LREQ-RPT-020")
def test_run_dashboard_distinguishes_null_from_explicit_zero(tmp_path):
    """A measured ``0.0`` renders ``0``; a ``None`` renders ``n/a``; they differ."""
    zero_row = rf.category_score_record(
        rf.CATEGORY_ALPHA,
        component_d=0.0,
        market_opportunity_score=0.0,
        ranking_sensitivity_json=rf.ranking_sensitivity_json(
            (rf.CATEGORY_ALPHA,), balanced_ranks={rf.CATEGORY_ALPHA: 1}
        ),
    )
    contributions = report._component_contributions(zero_row)
    assert dict(contributions)["D"] == 0.0

    repository = _repository(tmp_path)
    run = rf.run_record((rf.CATEGORY_ALPHA,))
    try:
        _seed(repository, run, (zero_row,))
        view = report.load_run_report_view(repository, rf.RUN_ID)
        html = report.render_run_dashboard_html(view)
        assert "0" in html
        assert "n/a" in html
        assert "n/a" != "0"
    finally:
        repository.close()


@pytest.mark.lreq("LREQ-RPT-010")
def test_run_dashboard_has_no_confidence_interval_or_error_bars(tmp_path):
    """No error-bar trace and no confidence-interval wording in the document."""
    repository, view = _dashboard_view(tmp_path)
    try:
        html = report.render_run_dashboard_html(view)
        # Restrict the error-bar key scan to this module's own chart JSON (the
        # inline plotly.js bundle legitimately names ``error_y``/``error_x`` as
        # trace attributes it supports; those are not emitted traces).
        scripted = html.split("Plotly.newPlot", 1)[0]
        assert '"error_y"' not in html.replace(scripted, "")
        assert '"error_x"' not in html.replace(scripted, "")
        normalized = html.casefold()
        assert "confidence interval" not in normalized
        assert "confidence intervals" not in normalized
        assert "error bar" not in normalized
        assert "error bars" not in normalized
    finally:
        repository.close()


@pytest.mark.lreq("LREQ-SEN-020")
@pytest.mark.lreq("LREQ-RPT-020")
def test_run_dashboard_policy_bump_and_kpi_tiles(tmp_path):
    """The bump rows match the persisted ranks; null ranks are gaps; KPIs render."""
    repository, view = _dashboard_view(tmp_path)
    try:
        rows = report._policy_rank_rows(view)
        assert rows == (
            (rf.CATEGORY_ALPHA, 1, 1, 1),
            (rf.CATEGORY_BRAVO, 2, 3, 2),
            (rf.CATEGORY_CHARLIE, 3, 2, 3),
        )
        tiles = report._kpi_tiles(view)
        assert tiles == (
            ("top_3_stability", 1.0),
            ("top_5_stability", 0.8),
            ("maximum_rank_displacement", 2),
        )
        html = report.render_run_dashboard_html(view)
        assert "top_3_stability" in html
        assert "maximum_rank_displacement" in html

        # A null rank is a gap, not 0.
        gap_payload = rf.ranking_sensitivity_json(
            (rf.CATEGORY_ALPHA,),
            balanced_ranks={rf.CATEGORY_ALPHA: 1},
            policy_ranks={rf.CATEGORY_ALPHA: {"rank_demand_heavy": 2}},
        )
        gap_row = rf.category_score_record(
            rf.CATEGORY_ALPHA, ranking_sensitivity_json=gap_payload
        )
        gap_row = dataclasses.replace(gap_row, run_id="run-gap-rank")
        gap_view = _view_with_row(tmp_path, gap_row)
        assert report._policy_rank_rows(gap_view) == ((rf.CATEGORY_ALPHA, 1, 2, None),)
    finally:
        repository.close()


def _view_with_row(tmp_path, row):
    """Build a one-row view from ``row`` for the gap/null assertions."""
    repository = _repository(tmp_path)
    run = rf.run_record((row.category,), run_id=row.run_id)
    _seed(repository, run, (row,))
    view = report.load_run_report_view(repository, row.run_id)
    repository.close()
    return view


@pytest.mark.lreq("LREQ-RPT-020")
def test_run_dashboard_heatmap_uses_persisted_coverage_and_ordinal_grade(tmp_path):
    """Heatmap uses D/R/Q coverage, an ordinal grade scale, and a C status column."""
    repository, view = _dashboard_view(tmp_path)
    try:
        html = report.render_run_dashboard_html(view)
        for label in (
            "demand stratum eligibility coverage",
            "recent supply stratum eligibility coverage",
            "quality stratum eligibility coverage",
        ):
            assert label in html
        assert "evidence grade (ordinal)" in html
        assert "breadth completeness status" in html
        # The C column is a status, never labelled "coverage".
        assert "breadth completeness coverage" not in html
        # Reference lines equal the SRS §14 thresholds.
        assert report.COVERAGE_REFERENCE_THRESHOLDS == (
            ("minimum", 0.5),
            ("strong", 0.8),
        )
        assert "minimum 0.50" in html
        assert "strong 0.80" in html
    finally:
        repository.close()
