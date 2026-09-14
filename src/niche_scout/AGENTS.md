# Package Agent Rules

The package follows `Documents/SRS-lean.md` Appendix B and the dependency map module ownership. `models.py` owns typed structures; `validation.py` owns structural and semantic validation; `sampling.py` owns deterministic sampling; `metrics.py` owns metric eligibility and raw estimators; and `scoring.py` owns normalization, components, evidence, and sensitivity. I/O and orchestration belong only in `collector.py`, `collector_coveo.py`, `collector_graphql.py`, `config.py`, `database.py`, `pipeline.py`, `report.py`, and `cli.py`.

`collector.py` is a re-exporting facade over the independent Coveo and GraphQL collector modules. The split preserves the purity boundary and allows their chunks to work in parallel.

`metrics.py` and `scoring.py` never import collectors, database, pipeline, report, or CLI modules; never perform I/O; and never read the clock. Pure functions receive an explicit timezone-aware UTC `scoring_cutoff_utc`. Calculations use `float64` precision. Null, zero, invalid, contradictory, and unavailable remain distinct; unavailable values are never fabricated as zero.

Use the SRS's exact frozen weights, thresholds, and boundary rules. Analytical tests require an explicit `@pytest.mark.lreq("LREQ-...")` marker and a `tests/traceability.json` entry. Tests never make live network calls.
