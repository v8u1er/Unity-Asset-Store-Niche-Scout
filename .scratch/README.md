# `.scratch/` — agent scratch space

The sanctioned in-repo location for agent throwaway scripts, probes, and
temporary artifacts. Use this instead of `%TEMP%`, `$env:TEMP`, `AppData`,
`C:\Windows\Temp`, or any other path outside this repository.

Everything in this folder except this README is git-ignored (see `.gitignore`)
and may be deleted at any time by a human or by a later agent. Nothing here is
a deliverable.

## Naming

`<task-or-chunk>-<what-it-does>.py`

Examples: `chunk1-extract-markers.py`, `probe-validation-headers.py`.

Do not use generic names (`tmp.py`, `scratch.py`). Never name a file
`test*.py` — pytest would collect it if this folder were ever added to
`pythonpath` or `testpaths`.

## Required header

Every scratch script starts with a module docstring whose first line states
that the file is throwaway, plus the task or chunk it belongs to. Example:

```python
"""Throwaway probe: raw status codes from validation.validate_taxonomy_structure."""
from __future__ import annotations
```

## Running

Run from the repository root with `src` on `PYTHONPATH`:

```powershell
$env:PYTHONPATH = "src"; python .scratch/probe-validation-headers.py
```

Do not add packaging, path shims, or `conftest.py` files for scratch code.

## Expiry

Delete each scratch file in the same task that created it, unless the user
explicitly asks for it to be kept.

## Do not put here

- Product databases or SQLite files (`*.sqlite3`) — those belong under pytest's
  `tmp_path` during tests and `runtime/` for real runs.
- Fixtures referenced by `tests/` or golden vectors.
- Frozen plan, interface, or SRS documents.
- Anything under `src/`, or any file referenced by `src/`, `tests/`, or
  `Documents/`.
