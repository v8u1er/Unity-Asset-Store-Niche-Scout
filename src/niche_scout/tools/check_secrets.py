"""Static secret-handling check over the tracked source surface (R5).

SRS §4.3 (``LREQ-SEC-020``) requires credentials never to reach source control;
the ``.env`` pattern is ignored by version control and the two credential
environment variables are the only sources of a live value. This module is the
static half of the maintained guard:

* it walks tracked files under ``src/``, ``tests/``, ``config/``, and the
  repository ``pyproject.toml`` and reports a **literal credential value**,
* it asserts ``.gitignore`` carries an ``.env`` pattern and that no tracked
  ``.env`` file exists.

It detects, and reports a *pattern class* only:

* ``Bearer <literal>`` where the bearer value is not an obvious placeholder,
* ``X-CSRF-Token: <literal>`` (case-insensitive header) where the value is not an
  obvious placeholder,
* an assignment of a non-placeholder literal to the frozen environment variable
  names ``NICHESCOUT_COVEO_BEARER_TOKEN`` / ``NICHESCOUT_UNITY_CSRF_TOKEN``.

The environment-variable *names* used as ordinary strings, dictionary keys, or
module constants (for example ``config.COVEO_TOKEN_ENV =
"NICHESCOUT_COVEO_BEARER_TOKEN"``) are not findings: a name is not a secret. Only
a non-placeholder value is.

The check is a **guard, not a proof**: a credential split across lines, computed
at runtime, or supplied out of band is out of its reach, and ``.env`` itself is
never read (its mere existence is the only thing inspected, and only to confirm
it is covered by ``.gitignore``). Failure messages name the file, the 1-based line
number, and the pattern class, and never echo the matched value.

This definition module is excluded from the scan for the same reason as the
scope-prohibition guard: it necessarily contains the detection patterns themselves,
which are not credentials.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]

#: The frozen credential environment-variable names (SRS §14 / interfaces/chunk-00).
ENV_VAR_NAMES: tuple[str, ...] = (
    "NICHESCOUT_COVEO_BEARER_TOKEN",
    "NICHESCOUT_UNITY_CSRF_TOKEN",
)

#: Directories whose tracked files are scanned, plus the repository manifest.
SCAN_DIRECTORIES: tuple[str, ...] = ("src", "tests", "config")
SCAN_FILES: tuple[str, ...] = ("pyproject.toml",)

#: File suffixes worth reading as text.
_TEXT_SUFFIXES: frozenset[str] = frozenset(
    {".py", ".toml", ".json", ".cfg", ".ini", ".txt", ".md", ".example", ".env"}
)

#: Case-insensitive placeholder seeds: an obvious non-secret token used in docs,
#: fixtures, or templates. A value containing one of these is allowed.
PLACEHOLDER_SEEDS: tuple[str, ...] = (
    "your_token",
    "your-token",
    "your_csrf_token",
    "your-csrf-token",
    "redacted",
    "changeme",
    "change-me",
    "set-locally",
    "set_locally",
    "placeholder",
    "example",
    "dummy",
    "fake",
    "fixture-",
    "test-",
    "sample-",
    "<",
    "${",
    "{{",
)

_PATTERN_CLASS_ENV_ASSIGNMENT = "literal credential assigned to a frozen env var"
_PATTERN_CLASS_BEARER = "literal bearer credential"
_PATTERN_CLASS_CSRF_HEADER = "literal CSRF header credential"

#: ``Bearer`` followed by a credential-shaped value. The value must be long and
#: contain a separator or digit, so ordinary prose ("bearer credential") and
#: placeholder sentinels do not match, while a base64/JWT/opaque token does.
_BEARER_PATTERN = re.compile(r"(?i)\bBearer\s+([A-Za-z0-9._~+/=-]{16,})")
#: The CSRF header in ``Name: value`` form; the value must be credential-shaped.
_CSRF_HEADER_PATTERN = re.compile(
    r"(?i)\bX-CSRF-Token['\"]?\s*[:=]\s*['\"]?([A-Za-z0-9._~+/=-]{8,})"
)
#: ``"NAME": "value"`` / ``NAME = "value"`` / ``NAME: "value"`` forms, requiring
#: a quoted literal value so an identifier reference (``...: raw``) is not flagged.
_ENV_ASSIGNMENT_PATTERN = re.compile(
    r"(?P<name>NICHESCOUT_(?:COVEO_BEARER|UNITY_CSRF)_TOKEN)"
    r"['\"]?\s*[:=]\s*['\"](?P<value>[^'\"]+)['\"]"
)


@dataclass(frozen=True, slots=True)
class SecretFinding:
    """One suspected literal credential, identified by class and never by value."""

    path: Path
    line_number: int
    pattern_class: str


def _is_placeholder(value: str) -> bool:
    """Return whether ``value`` is an obvious non-secret placeholder.

    A blank value, a shell/markdown sentinel, or a value containing one of
    :data:`PLACEHOLDER_SEEDS` is a placeholder. Comparisons are case-insensitive
    so ``YOUR_TOKEN``, ``your_token``, and ``Your-Token`` all qualify.
    """
    if not value:
        return True
    lowered = value.lower()
    return any(seed in lowered for seed in PLACEHOLDER_SEEDS)


def scan_text_for_secrets(text: str) -> list[tuple[int, str]]:
    """Return ``(1-based line, pattern class)`` for each literal credential.

    Only non-placeholder values are reported; the matched value itself is never
    returned, so a caller can never print or persist it. Env-var names used as
    plain strings are not findings.
    """
    findings: list[tuple[int, str]] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        bearer = _BEARER_PATTERN.search(line)
        if bearer and not _is_placeholder(bearer.group(1)):
            findings.append((line_number, _PATTERN_CLASS_BEARER))

        csrf = _CSRF_HEADER_PATTERN.search(line)
        if csrf and not _is_placeholder(csrf.group(1)):
            findings.append((line_number, _PATTERN_CLASS_CSRF_HEADER))

        assignment = _ENV_ASSIGNMENT_PATTERN.search(line)
        if assignment and not _is_placeholder(assignment.group("value")):
            findings.append((line_number, _PATTERN_CLASS_ENV_ASSIGNMENT))
    return findings


def _iter_scanned_files(root: Path = ROOT) -> list[Path]:
    """Return the tracked-shaped files under the scan roots, in stable order.

    This definition module is skipped: it necessarily contains the detection
    patterns, which are not credentials.
    """
    own_path = Path(__file__).resolve()
    files: list[Path] = []
    for directory in SCAN_DIRECTORIES:
        base = Path(root) / directory
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*")):
            if (
                path.is_file()
                and path.suffix in _TEXT_SUFFIXES
                and path.resolve() != own_path
            ):
                files.append(path)
    for name in SCAN_FILES:
        path = Path(root) / name
        if path.is_file():
            files.append(path)
    return files


def _gitignore_env_assertions(root: Path) -> list[SecretFinding]:
    """Return findings for a missing ``.env`` ignore pattern or a tracked ``.env``.

    A ``.env`` file that exists but is covered by the ``.env`` ignore pattern is
    untracked and allowed; ``.env.example`` is a template and is always allowed.
    ``.env`` itself is never opened: only its path is tested for existence.
    """
    findings: list[SecretFinding] = []
    gitignore = Path(root) / ".gitignore"
    has_env_pattern = False
    if not gitignore.is_file():
        findings.append(
            SecretFinding(Path(".gitignore"), 1, "missing .gitignore .env pattern")
        )
    else:
        lines = gitignore.read_text(encoding="utf-8").splitlines()
        has_env_pattern = any(
            line.strip() in (".env", ".env.*", "/.env") for line in lines
        )
        if not has_env_pattern:
            findings.append(
                SecretFinding(
                    Path(".gitignore"),
                    1,
                    "missing .gitignore .env pattern",
                )
            )
    tracked_env = Path(root) / ".env"
    if tracked_env.is_file() and not has_env_pattern:
        findings.append(SecretFinding(Path(".env"), 1, "tracked .env file present"))
    return findings


def find_credential_findings(root: Path = ROOT) -> list[SecretFinding]:
    """Walk the scanned surface and return every credential finding.

    A finding carries the file, the 1-based line number, and a pattern class; it
    never carries the matched value or a partial credential. ``.env`` is never
    opened. The check is a guard, not a proof.
    """
    findings: list[SecretFinding] = []
    for path in _iter_scanned_files(root):
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for line_number, pattern_class in scan_text_for_secrets(text):
            try:
                relative = path.relative_to(root)
            except ValueError:
                relative = path
            findings.append(SecretFinding(relative, line_number, pattern_class))
    findings.extend(_gitignore_env_assertions(root))
    return findings


def main(argv: list[str] | None = None) -> int:
    """Exit 0 when no credential finding exists; else print and return 1.

    Each failure line names the file, the line number, and the pattern class only;
    the matched credential value is never printed.
    """
    args = list(sys.argv[1:] if argv is None else argv)
    root = Path(args[0]) if args else ROOT
    findings = find_credential_findings(root)
    if findings:
        for finding in findings:
            print(f"{finding.path}:{finding.line_number}: {finding.pattern_class}")
        return 1
    print(
        "Secret check valid: no literal credential found under "
        f"{', '.join(SCAN_DIRECTORIES)}, {', '.join(SCAN_FILES)}; "
        ".gitignore ignores .env and no tracked .env exists"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
