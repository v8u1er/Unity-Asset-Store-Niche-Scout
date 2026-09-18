# Add in-repo agent scratch folder

# Add an in-repo scratch folder for agent temporary scripts

**Goal:** Give every agent a single, sanctioned place for throwaway scripts and temporary artifacts *inside* this repo, so no agent ever needs permission to touch `%TEMP%`, `AppData`, or any other path outside the workspace.

---

## Decisions already made (rationale)

- **Folder name/placement:** `.scratch/` at the repo root, alongside the existing dot-directories (`.plans/`, `.cursor/`). It reads as agent-only tooling space, it is not a Python package (no `__init__.py`), and it is not collected by pytest or built by setuptools.
- **Why not `runtime/`:** `runtime/` is already git-ignored for the *product*, and `tests/test_database.py` contains an autouse guard (`database_paths_stay_under_pytest_temp_base`, lines 132–176) plus module docstrings that assert product databases live under pytest `tmp_path` and never inside the tree. Putting scratch artifacts in `runtime/` would blur that boundary and invite confusion with the product data path. A distinct `.scratch/` keeps the agent artifact store separate from product output.
- **Git:** ignored, so scratch scripts never enter history, never trip `ruff`/pytest collection on commit, and never get mistaken for deliverables.
- **Boundary compliance:** the rule text lives in `.cursor/rules/`, which is an agent-instruction file, not one of the modules named in the project's fixed module boundary (`models.py`, `validation.py`, `sampling.py`, `metrics.py`, `scoring.py`, and the I/O/orchestration modules). No analytical code, no requirement text, and no frozen interface changes. `src/niche_scout/tools/check_import_boundaries.py` is untouched: `metrics.py`/`scoring.py` still never import `tempfile`, `pathlib`, etc. The scratch folder is a *convention*, not a runtime dependency of any module.
- **Cleanup:** two-sided. A `README.md` in the folder states ownership/expiry rules, and the rule file instructs agents to delete their own scripts when done.

---

## Steps

### 1. Create `.scratch/` with a self-describing README

Create `.scratch/README.md` (the only tracked file in the folder) containing:

- One-line purpose: sanctioned in-repo location for agent throwaway scripts and temporary artifacts.
- Note that everything else in this folder is git-ignored and may be deleted at any time by a human or a later agent.
- Naming convention for scratch scripts: `<task-or-chunk>-<what-it-does>.py`, e.g. `chunk1-extract-markers.py`, `probe-validation-headers.py`. No generic `tmp.py`/`test.py` names (a `test*.py` name would be picked up by pytest collection if the folder were ever added to `pythonpath`/`testpaths`).
- Required header in each scratch script (Python): a module docstring whose first line states it is throwaway, plus the task/chunk it belongs to.
- Expiry rule: delete the script in the same task that created it, unless the user explicitly asks to keep it.
- Explicit "do not put here" list: product databases (`*.sqlite3`), fixtures referenced by `tests/`, frozen plan/interface documents, anything under `src/`.

### 2. Ignore the folder's contents, keep the README

Append to `.gitignore` (after the existing `*.egg-info/` line):

```
.scratch/*
!.scratch/README.md
```

This keeps `.scratch/` discoverable in a fresh clone (the README is tracked) while every scratch artifact stays out of git.

### 3. Add the rule to `.cursor/rules/project-rules.md`

Insert a new `## Temporary scripts and scratch space` section between `## File discipline` (ends line 55) and `## Chunk pipeline auto-chaining` (line 57). Exact rule content:

```markdown
## Temporary scripts and scratch space
- The ONLY sanctioned location for throwaway scripts, probes, and temporary
  output is `.scratch/` at the repository root. Never write to `%TEMP%`,
  `$env:TEMP`, `AppData`, `C:\Windows\Temp`, or any other path outside this
  repository, and never ask the user for permission to do so — use `.scratch/`.
- Prefer `python -c` or an inline run for a one-liner. If a file is genuinely
  needed, create `.scratch/<task-or-chunk>-<purpose>.py` (see
  `.scratch/README.md` for naming and header conventions).
- Scratch scripts import the package by running from the repository root
  (`python .scratch/<name>.py`) with `src` on `PYTHONPATH` (e.g.
  `$env:PYTHONPATH = "src"; python .scratch/<name>.py`). Do not add new
  packaging or path shims for scratch code.
- `.scratch/*` is git-ignored and is not part of any deliverable. Scratch code
  is never referenced by `src/`, `tests/`, or `Documents/`.
- Delete each scratch file in the same task that created it, unless the user
  explicitly asks for it to be kept.
- Never place product databases, fixtures used by `tests/`, or copies of
  frozen plan/interface/SRS text in `.scratch/`.
```

This also softens the interaction with `## File discipline` above it: `.scratch/` files are explicitly exempt from the "only touch files listed in the plan" rule, which is why the exemption must be stated here explicitly.

### 4. Add the same section to the second rule source — SUPERSEDED

> **Correction, 2026-09-18:** this step is superseded and must not be performed.
> The `.clinerules/` directory no longer exists — `.clinerules/project-rules.md`
> and `.clinerules/windows.md` were deleted in commit `36da5f7`, and Cline is no
> longer used on this project. `.cursor/rules/project-rules.md` is now the single
> authority for project rules. Do not create `.clinerules/`, do not restore
> anything into it from git history, and do not mirror rule text into it.

> **Correction, 2026-09-18:** the paragraph below describes the former
> `.clinerules` mirror as a live second rule source. It is retained as a record
> of the original plan, but it no longer describes this repository: the mirror
> no longer exists and this step is not to be performed.
>
> ~~The `.clinerules` copy is a near-identical mirror (49 lines, same section headings, differing only in wording of the architecture bullets). Append the same `## Temporary scripts and scratch space` section after `## File discipline` (end of file, line 49) with identical text so both rule sources agree. Do not restructure or "sync" the rest of the mirror — that is out of scope.~~

### 5. Point `AGENTS.md` at the rule

Append a short subsection to `AGENTS.md` after the existing `## Requirements and tests` section (or at end of file):

```markdown
## Scratch space

Throwaway scripts and probes belong in the repo-root `.scratch/` directory.
Never request access to a temporary path outside this repository. See
`.scratch/README.md` for naming, header, and cleanup conventions.
```

### 6. Remove the two existing off-convention artifacts

- Delete `_probe_tmp.py` from the repo root (its content is a scratch probe of `niche_scout.validation._missing_header_fields`; it is not referenced by any test or module — verify with a grep for `_probe_tmp` before deleting).
- Delete the two stray scratch scripts sitting in `.plans/`: `_chunk1_check.py` and `_chunk1_extract_markers.py`. They are planning-time throwaway checkers, not plan documents, and `.plans/` is the plan-artifact location, not a code location.
- Do not delete or move anything else in `.plans/` or `Documents/`.
- If the user wants to keep any of these three, move it to `.scratch/` with a descriptive name instead of deleting (ask at execution time only if a grep shows a live reference; otherwise delete).

### 7. (Optional, confirm with user) Exclude `.scratch/` from editor/agent noise

No change needed to `pyproject.toml`: setuptools `packages.find where = ["src"]` already excludes it, and pytest has no `testpaths` entry, so `.scratch/` is never collected. Leave `.vscode/settings.json` (currently `{}`) alone unless the user wants file-exclude entries. Listed here only to record that this step was considered and deliberately skipped.

---

## Risks / notes

- The rule explicitly contradicts a common agent habit ("write to `%TEMP%`"), so it must be stated as a hard prohibition, not a preference — hence the "never ask the user for permission" clause in step 3.
- `.scratch/` is a new top-level dot-directory; a future `globais`/tooling file that enumerates repo dirs (e.g. a docs index) may need a one-line addition. No such file exists today.
- There is only one rule source to keep in sync: `.cursor/rules/project-rules.md`. The second copy named in the original plan was removed (see the correction on step 4), so no cross-file drift check applies.
- `Documents/requirements-dependency-map.md` §A.1 and `Documents/SRS-lean.md` are untouched: this change introduces no requirement, no LREQ, and no test, so no traceability entry is needed.

## Verification

1. `git status --short` → should show `.scratch/README.md`, `.gitignore`, `.cursor/rules/project-rules.md`, `AGENTS.md`, and the deletions. (The former plan also listed `.clinerules/project-rules.md` here; that file was later removed and is not part of the expected output.)
2. `git check-ignore -v .scratch/foo.py` → confirms the ignore rule matches.
3. `New-Item .scratch/smoke.py; git status --short` → `smoke.py` must NOT appear; `Remove-Item .scratch/smoke.py` afterwards.
4. `python -m pytest -q` → unchanged pass/fail set (no collection of `.scratch/`).
5. `python -m niche_scout.tools.check_import_boundaries` → still "Import boundaries valid for metrics.py, scoring.py".
6. `python -m niche_scout.tools.validate_traceability` → unchanged.
7. Grep the repo for `_probe_tmp`, `_chunk1_check`, `_chunk1_extract_markers` → zero live references after step 6.
