"""One-time terms-notice acknowledgement for the ``run`` command.

This module is I/O-only and holds no analytical behavior: it renders the stable
terms notice, hashes it to a versioned digest, remembers a matching digest in a
local marker file, and decides whether a ``run`` may proceed
(``LREQ-CLI-050``, SRS §10). It performs no network access and reads no
credentials.

The marker file stores **only** the digest: no notice text, no version, no
timestamp. A stored acknowledgement is honored only while the digest is
unchanged, so editing :data:`NOTICE_TEXT` invalidates every prior
acknowledgement. Every failure to read or write the marker is non-fatal: a
missing marker means "not acknowledged", and an unwritable marker warns without
blocking a run that the operator has already confirmed.
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import TextIO

#: The notice text version. Changing it (with the text) changes the digest.
NOTICE_VERSION: str = "2"

#: The stable terms notice, versioned by :data:`NOTICE_VERSION`. Not a legal
#: document; it names the independence, the automated access, Unity's terms,
#: account responsibility and indemnity, and the operator's responsibility.
NOTICE_TEXT: str = (
    "Independent project; use at your own risk. Niche Scout is not affiliated "
    "with or endorsed by Unity Technologies. It sends automated requests to "
    "Unity Asset Store endpoints using credentials from your own session. "
    "Unity's Asset Store terms say you agree not to access the Store through "
    "automated means such as scripts or crawlers unless you have a separate "
    "agreement with Unity, and Unity's main terms restrict bots and scrapers "
    "more broadly; breaches may lead to account suspension or other action. "
    "Unity's terms also make you responsible for automated software acting "
    "through your account, and you may be required to indemnify Unity for "
    "breaches. The author provides this software as is, without warranty, and "
    "does not authorize or encourage any use that violates Unity's terms. You "
    "are solely responsible for reading those terms and deciding whether and "
    "how to use this tool."
)

#: The phrase an interactive operator must type, compared case-insensitively
#: after stripping surrounding whitespace.
ACKNOWLEDGEMENT_PHRASE: str = "I understand"

#: The default per-user marker file storing the acknowledged notice digest.
DEFAULT_MARKER_PATH: Path = Path.home() / ".niche_scout" / "terms_acknowledged"


def notice_digest(
    notice_text: str = NOTICE_TEXT, *, notice_version: str = NOTICE_VERSION
) -> str:
    """Return the SHA-256 hex digest of ``notice_version`` followed by the text.

    The version is prepended before hashing, so a version bump alone changes the
    digest even for identical text. Returns a lowercase hex string; it never
    raises for ordinary ``str`` inputs.
    """
    payload = (notice_version + notice_text).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def load_acknowledged_digest(marker_path: Path = DEFAULT_MARKER_PATH) -> str | None:
    """Read the stored acknowledgement digest, or ``None`` when absent/empty.

    Whitespace around the file contents is stripped. A missing file, an
    unreadable file (any ``OSError``), or an empty/whitespace-only file all
    return ``None`` rather than raising.
    """
    try:
        text = Path(marker_path).read_text(encoding="utf-8").strip()
    except OSError:
        return None
    return text or None


def store_acknowledgement(marker_path: Path, digest: str) -> bool:
    """Persist ``digest`` to ``marker_path`` and return whether it succeeded.

    The parent directory is created when missing and the file is written with
    UTF-8 and mode ``0600``. Only the digest is written: no version and no
    timestamp. Any ``OSError`` (for example an unwritable parent) is caught and
    reported as ``False``; this function never raises and never blocks a run.
    """
    path = Path(marker_path)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(digest, encoding="utf-8")
        os.chmod(path, 0o600)
    except OSError:
        return False
    return True


def _stdin_is_interactive(stdin: TextIO) -> bool:
    """Return whether ``stdin`` reports a TTY, defaulting to non-interactive.

    A missing, non-callable, or raising ``isatty`` is treated as
    non-interactive, so a captured stream never blocks on a prompt.
    """
    isatty = getattr(stdin, "isatty", None)
    if not callable(isatty):
        return False
    try:
        return bool(isatty())
    except Exception:
        return False


def ensure_consent(
    *,
    accept_terms: bool,
    stdin: TextIO,
    stderr: TextIO,
    marker_path: Path = DEFAULT_MARKER_PATH,
    notice_text: str = NOTICE_TEXT,
    notice_version: str = NOTICE_VERSION,
) -> bool:
    """Decide whether a ``run`` may proceed under the terms notice.

    Returns ``True`` to proceed and ``False`` to refuse. The notice and every
    message are written to ``stderr``; nothing is written to stdout. Order:

    1. A stored digest matching the current notice proceeds silently.
    2. ``accept_terms`` (the ``--accept-terms`` flag) prints the notice and
       proceeds for this one run without persisting anything.
    3. In an interactive session the notice and the acknowledgement prompt are
       printed, one line is read, and a case-insensitive, whitespace-stripped
       match persists the acknowledgement. A failed persist warns on ``stderr``
       but still proceeds; a non-match refuses.
    4. Non-interactive without the flag prints the notice and a refusal, and
       proceeds no further, so no request is sent.

    Null/edge behavior: a missing or unreadable marker is "not acknowledged";
    an absent or non-callable ``isatty`` is non-interactive.
    """
    digest = notice_digest(notice_text, notice_version=notice_version)
    if load_acknowledged_digest(marker_path) == digest:
        return True

    if accept_terms:
        print(notice_text, file=stderr)
        return True

    if _stdin_is_interactive(stdin):
        print(notice_text, file=stderr)
        print(f'Type "{ACKNOWLEDGEMENT_PHRASE}" to continue:', file=stderr)
        line = stdin.readline()
        if line.strip().lower() == ACKNOWLEDGEMENT_PHRASE.lower():
            if not store_acknowledgement(marker_path, digest):
                print(
                    "warning: could not save the terms acknowledgement; "
                    "continuing for this run",
                    file=stderr,
                )
            return True
        print("error: terms notice not accepted; no requests were sent", file=stderr)
        return False

    print(notice_text, file=stderr)
    print(
        "error: terms notice not acknowledged; no requests were sent. Run "
        "interactively or pass --accept-terms to confirm for one run.",
        file=stderr,
    )
    return False
