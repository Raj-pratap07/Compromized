# Failure Handling and Idempotency

## 1. State model

Record statuses:

- `PENDING`: storage operation started, not yet fully committed.
- `AVAILABLE`: all five shares are confirmed stored and metadata transition committed.
- `FAILED`: storage did not complete and all writes/copies have been confirmed absent after rollback.
- `CLEANUP_REQUIRED`: at least one write/delete outcome remains uncertain or cleanup failed.
- `RECONCILIATION_REQUIRED`: reserved for a future/explicit recovery pass when persisted state cannot yet be resolved.

Per-share statuses:

- `NOT_STARTED`
- `ENCRYPTED` (ciphertext exists in current process, not necessarily persisted)
- `STORED`
- `UNKNOWN` (timeout or response lost; provider might have acted)
- `WRITE_FAILED` (confirmed failed without a stored object)
- `DELETE_PENDING`
- `DELETE_CONFIRMED`

Do not store plaintext share data or ciphertext copies in SQLite just to make retries easier. If the process dies and the share ciphertext was not stored remotely, the simplest safe policy is to clean up any other successfully stored shares and fail the operation rather than reconstruct or persist plaintext.

## 2. Write order

1. Generate record ID/version; create record and five per-share rows as `PENDING`/`NOT_STARTED` in a short transaction and commit.
2. Split in memory.
3. For each share, build stable context, call Akeyless Encrypt, call provider `put`, and record the result in a new short transaction.
4. On a confirmed write, mark that share `STORED`.
5. On explicit failure, record `WRITE_FAILED` and begin rollback.
6. On timeout/ambiguous result, mark `UNKNOWN`; use the deterministic ID to query the provider before deciding whether to retry or delete.
7. After five `STORED` statuses, commit record `AVAILABLE`.

No cross-provider atomicity is assumed.

## 3. Retry semantics

- Bound retries and include backoff; no infinite loops.
- Do not retry authentication/permission failures blindly.
- Writes should use deterministic object IDs and overwrite/confirm the same logical object safely.
- For unknown writes, read/query by deterministic ID first. If found, validate the envelope metadata and treat as stored; if confirmed absent, retry the same operation; if still uncertain, retain `UNKNOWN`/`CLEANUP_REQUIRED`.
- Deletes should target the deterministic ID. An already-absent object may count as deletion confirmed if provider semantics make that conclusion reliable.
- Do not log ciphertext if not necessary; definitely do not log plaintext or credentials.

## 4. Rollback

On any storage/encryption failure after the pending record is created:

1. Attempt to resolve `UNKNOWN` write outcomes.
2. Delete objects that are confirmed or potentially stored.
3. Persist every result separately.
4. If every expected object is confirmed absent, mark the record `FAILED`.
5. Otherwise mark `CLEANUP_REQUIRED` and retain metadata needed for future reconciliation.

Do not delete the metadata needed to clean up remote objects before cleanup is confirmed.

## 5. Restart behavior (MVP-level)

At startup, list `PENDING`, `UNKNOWN`, and `CLEANUP_REQUIRED` records. Do not automatically promote a record just because five IDs return a value; validate the envelope metadata and Akeyless-decrypt/authentication context before declaring the set complete. If the workflow cannot safely resume, attempt cleanup and preserve the record for manual reconciliation. A full background reconciliation worker is deferred.

## 6. Recovery failure

- Try providers until three distinct, valid shares have been acquired or all candidate providers have been exhausted.
- A provider timeout, invalid envelope, wrong context, wrong key reference, corrupted ciphertext, or duplicate index is not a valid share.
- Fail without reconstructing if fewer than three valid shares are available.
- Clean plaintext buffers on every path as best-effort.

## 7. Public deletion

Public deletion is deferred. Internal adapter delete remains mandatory for rollback. If public deletion is added later, design `DELETING`, `DELETE_INCOMPLETE`, tombstones, backups and provider retention as a separate change.
