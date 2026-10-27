# ADR-011: SQLCipher Python driver selection

**Status:** Pending compatibility spike

## Context
Metadata must be encrypted at rest. Python's standard `sqlite3` is not sufficient for the production metadata connection; the driver must link to SQLCipher.

## Evaluation checklist
- Installable on the team's actual OS/Python version.
- Reports a real SQLCipher version via supported PRAGMA.
- Correct database key opens a database; incorrect key cannot read it.
- `cipher_integrity_check` supported and tested in the installed build/version.
- Can use parameterized SQL and transactions safely.
- Maintenance status and license checked.
- Build/install instructions documented for the team's operating system.

## Decision
Do not assume a package works based on its PyPI description. Test it in a clean virtual environment. Record package name/version and the verified key initialization sequence before implementing the metadata repository.

## Consequences
Do not silently fall back to standard sqlite3 if SQLCipher fails to install or verify. Stop and ask for a decision rather than degrading to unencrypted metadata.
