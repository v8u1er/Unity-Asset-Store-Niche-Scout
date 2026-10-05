# Contributing

Thanks for taking a look at Niche Scout. This is a small, opinionated project with an
unusually strict set of rules around analytical validity, because its output is a
heuristic that people may act on. Please read this file and
[`AGENTS.md`](AGENTS.md) before opening a pull request.

By participating you agree to follow the [Code of Conduct](CODE_OF_CONDUCT.md).

## Source of truth

These files are normative, in this order:

1. `Documents/SRS-lean-v2.md` — the requirements (`LREQ-<AREA>-<NNN>`).
2. `Documents/requirements-dependency-map.md` — chunk ownership and gates.
3. `Documents/plans/chunk-*.md` — the frozen scope contract for one chunk.
4. `Documents/interfaces/chunk-*.md` — frozen public contracts from finished chunks.

If the SRS is ambiguous or silent, do not invent a formula, threshold, weight, field
name, or behavior. Open a discussion or an issue and stop. Constants live in SRS §14;
do not hard-code magic numbers.

## Development setup

Niche Scout targets Python 3.11 or newer. The project is developed on Windows
(PowerShell) and also runs on macOS and Linux.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
```

On macOS or Linux, use `python3 -m venv .venv` and `source .venv/bin/activate`.
If PowerShell refuses to run the activation script, allow it for this window only:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

`.[dev]` adds the test and formatting tools. `.[test]` is the lighter, tests-only extra.

## Running the quality gate

`src/niche_scout/tools/quality_workflow.py` runs the maintained gate in a fixed order and
stops at the first failure:

```powershell
python -m niche_scout.tools.quality_workflow
```

The steps are: `validate_traceability`, `check_import_boundaries`,
`check_scope_prohibitions`, `check_secrets`, `ruff check`, `ruff format --check`, and
`pytest -q`. Run it before you push; CI (`.github/workflows/ci.yml`) runs exactly this
command on Windows and Linux across Python 3.11 and 3.12, and also builds the package.

You can also run the individual steps:

```powershell
python -m pytest -q
python -m ruff check .
python -m ruff format .
```

Tests are offline. **Never** make a live network call in a test, and never run
`niche-scout run`. All network behavior is exercised through injected fakes and captured
fixtures.

## Tests and traceability

Niche Scout's tests are part of its validity argument, not just its CI.

- Every analytical test carries `@pytest.mark.lreq("LREQ-...")`.
- Every marked test has an entry in `tests/traceability.json` keyed by its full pytest
  node ID (for parameterized tests, the base node ID).
- Formula tests cover the normal case plus explicit zero, missing, invalid, ties, and
  minimum boundaries; golden vectors assert within `1e-9`.
- Do not rename or move a test without updating its `tests/traceability.json` entry in the
  same change. A pytest node ID is a stable identifier.
- `python -m niche_scout.tools.validate_traceability` must pass.

See `tests/AGENTS.md` for the test layout and fixture rules.

## Code style

- `snake_case` functions and files, `PascalCase` classes, `UPPER_SNAKE_CASE` constants.
- Type hints on public functions, with docstrings that state null and edge-case behavior.
- `ruff format` and `ruff check` are authoritative; the configuration is in
  `pyproject.toml`. Run both before pushing.
- `metrics.py` and `scoring.py` are pure: no imports of collectors, database, report, or
  CLI modules; no file or network I/O; no clock reads. `scoring_cutoff_utc` is always a
  parameter. Missing, explicit zero, invalid, and unavailable are four distinct states;
  never default a missing value to zero.
- Use `pathlib`, never hard-coded path separators.

## Secrets

Credentials come only from the environment variables
`NICHESCOUT_COVEO_BEARER_TOKEN` and `NICHESCOUT_UNITY_CSRF_TOKEN`. Never write a token
value into source, tests, fixtures, logs, SQLite, error messages, or a commit — and never
open `.env`. Fixture credentials must be obvious placeholders. `check_secrets` scans the
tracked source, tests, config, and `pyproject.toml`; a finding fails the gate.

If you ever expose a token by accident, treat it like a leaked password: log out of the
Asset Store (or wait for it to expire) and capture a fresh one.

## Scope discipline

The project deliberately excludes scheduling, resume/checkpoint, historical trends and
run comparison, enriching every discovered asset, favorite-count, extra GraphQL fields,
alternative collection strategies, configurable score weights, confidence intervals,
sales calibration, automated credential acquisition, and multi-user or cloud features.
Do not add them. Use the warning vocabulary in SRS Appendix C in any user-facing text.

## Pull requests

1. Keep the change small and focused on one concern.
2. Touch only the files the relevant plan or issue allows.
3. Run `python -m niche_scout.tools.quality_workflow` and paste the real result.
4. Describe the change, the requirement it serves, and anything you could not verify.
5. Do not commit generated data, `runtime/`, or anything under `.scratch/`.

A maintainer reviews and merges. If a change touches a frozen interface or a test node
ID, call that out explicitly.

## Reporting bugs and security issues

Open a GitHub issue for ordinary bugs, using a minimal reproduction and the exact command
and output. For anything that could expose credentials or weaken the security or purity
boundaries, follow [SECURITY.md](SECURITY.md) instead of opening a public issue.
