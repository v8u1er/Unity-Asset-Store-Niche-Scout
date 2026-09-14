# Unity Asset Store Niche Scout

A local, deterministic, sample-based research tool for comparing Unity Asset
Store categories. The lean scope reports demand, competition, recent supply,
and quality-gap signals with explicit evidence and rankability states. It does
not predict sales or revenue.

## Chunk 0 contracts

The initial contract layer defines typed domain rows and statuses in
`src/niche_scout/models.py`, configuration and credential boundaries in
`config.py`, persistence-neutral repository protocols in `database.py`, and
pure analytical input/output contracts in `metrics.py` and `scoring.py`.
Network collection, physical SQLite persistence, scheduling, resume/checkpoint
execution, and full-category enrichment are intentionally outside this chunk.

Use `python -m niche_scout.tools.validate_traceability` to validate requirement
test mappings.
