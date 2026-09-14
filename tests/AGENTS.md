# Test Agent Rules

Analytical tests use `@pytest.mark.lreq("LREQ-...")` and fixture or golden-vector data only. Live network calls are forbidden. Parameterized tests are mapped by their base node ID, not generated case IDs.

`tests/traceability.json` is an object keyed by individual `LREQ-*` IDs. Each value is an array of fully qualified pytest node IDs, for example:

```json
{
  "LREQ-SMP-060": ["tests/test_sampling.py::test_digest_changes_with_rule_version"]
}
```

Every individual requirement defined by `Documents/SRS-lean.md` must be present as a key. Once tests exist, every analytical test must have both a marker and a matrix entry, and every requirement must map to at least one required test.

Use this layout for offline data:

- `tests/fixtures/` — mocked request/response and integration fixtures
- `tests/golden_vectors/` — exact analytical inputs and expected outputs
- `tests/test_collector.py`, `test_identity.py`, `test_sampling.py`, `test_scoring.py`, `test_validation.py`, `test_database.py`, and `test_end_to_end.py` — requirement-focused test modules

Keep fixture credentials redacted and do not contact live endpoints.
