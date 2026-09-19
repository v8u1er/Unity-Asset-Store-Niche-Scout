# Agent Rules

These rules are grounded in `Documents/requirements-dependency-map.md` §A.1 and cross-checked against `Documents/SRS-lean.md` §§1.2–1.3 and Appendix B.

## Module boundaries

The module boundary is fixed by the SRS traceability matrix. `models.py` contains typed structures; `validation.py` contains structural and semantic validation primitives; `sampling.py` contains deterministic sampling; `metrics.py` contains metric eligibility and raw sample-aware estimators; `scoring.py` contains normalization, score components, evidence, and sensitivity. I/O and orchestration remain in `collector.py`, `collector_coveo.py`, `collector_graphql.py`, `database.py`, `pipeline.py`, `report.py`, and `cli.py`. `collector.py` is a facade re-exporting both collector adapters so Coveo and GraphQL work can proceed independently.

`metrics.py` and `scoring.py` are pure. They SHALL accept typed inputs and return typed outputs, SHALL never import I/O modules, SHALL never read the system clock, and SHALL perform no network, file, database, process, or CLI I/O. `scoring_cutoff_utc` is always an explicit timezone-aware UTC input. Formulas operate internally at `float64` precision.

Null, zero, invalid, and unavailable are distinct states. Missing, invalid, contradictory, or unavailable values SHALL remain unavailable; never fabricate zeros.

## Requirements and tests

Use the SRS's exact weights, thresholds, and boundary rules from Appendix A. Do not modify frozen interfaces without a separate coordination task.

Every analytical test carries `@pytest.mark.lreq("LREQ-...")` and has a corresponding entry in `tests/traceability.json`. Parameterized tests are represented by their base node ID. Tests use fixtures and golden vectors only; live network calls are forbidden.

## Scope prohibitions

The following items from `Documents/SRS-lean.md` §1.3 are explicitly forbidden: sales or revenue prediction, scheduled execution, resume/checkpoint execution, full enrichment of every discovered asset in large categories, automated credential acquisition, and multi-user or cloud deployment. No agent may implement them even if asked.

## Source of truth

Read `Documents/SRS-lean.md` and `Documents/requirements-dependency-map.md` directly before making requirement-driven changes. Do not paraphrase either document into new requirements documentation.

## Scratch space

Throwaway scripts and probes belong in the repo-root `.scratch/` directory. Never request access to a temporary path outside this repository. See `.scratch/README.md` for naming, header, and cleanup conventions.
