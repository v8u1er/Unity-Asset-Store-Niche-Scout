# Security Policy

Niche Scout handles two live credentials copied from a Unity Asset Store browser
session, writes a local SQLite database, and produces local reports. Its security goal is
narrow but firm: your tokens never leave your machine except to Unity's own endpoints, and
they never reach source control, logs, the database, reports, or error messages.

## Supported versions

Only the latest release on `main` is supported with security fixes. Niche Scout is
pre-1.0; there are no long-term support branches.

## Reporting a vulnerability

Please report suspected vulnerabilities **privately**, using GitHub's private
vulnerability reporting:

<https://github.com/v8u1er/unity-asset-store-niche-scout/security/advisories/new>

Do not open a public issue for a security problem. Include:

- a description of the issue and its impact,
- the version or commit you tested,
- steps to reproduce, ideally against fixtures rather than live endpoints,
- any suggested fix.

Never paste a real token value into an issue, a pull request, a chat, or a report. If a
credential is already exposed, treat it as compromised: log out of the Asset Store (or
wait for it to expire) and capture a fresh one.

## In scope

- Credential exposure: a token value reaching source, tests, fixtures, logs, SQLite,
  reports, error messages, or a URL that is not Unity's.
- Network-boundary failures: credentials sent anywhere other than Unity's Asset Store
  endpoints.
- Purity-boundary failures: `metrics.py` or `scoring.py` importing I/O, the database,
  collectors, the report or CLI, or reading the clock.
- Injection or path issues in SQLite persistence, report rendering, or file handling.
- Redaction failures in validation issues or request metadata.
- A malicious or malformed API response that causes code execution, not merely an
  incorrect score.

## Out of scope

- Unity Asset Store terms of service, rate limiting, or account consequences. Niche Scout
  is unofficial; using it is your responsibility. See the terms notice in the README.
- The accuracy, calibration, or business interpretation of the score. It is a
  deterministic, sample-based, within-run heuristic and makes no sales or demand claim.
- Denial of service against your own local run, or resource use from a large scan.
- Vulnerabilities in Unity's services or in third-party dependencies with no reachable
  path in this project (report those upstream, though a note is welcome).

## What to expect

This is a small project maintained on a best-effort basis. We aim to acknowledge a report
within a few days and to agree on a disclosure timeline with you before any public
write-up. Fixes for confirmed credential-exposure issues take priority over everything
else.