# Test Plan — Firefly

## 1. Unit tests (no network)

### SSS
- Fixed test secret splits into five unique shares.
- Every one of the 10 combinations of three shares recovers identical original bytes.
- The application wrapper rejects fewer than three shares before reconstruction.
- Duplicate indices and cross-record/cross-version share mixing are rejected.
- Invalid/malformed share input fails safely.

### Akeyless service (mock at unit level; live integration separately)
- Correct key + context + ciphertext round-trips expected bytes in live integration tests.
- Context includes record ID, version, index, provider and format version.
- Wrong context/ciphertext/key response is rejected.
- Base64 conversion handles binary values with zero bytes and non-UTF-8 content.
- Exceptions/log fields contain no plaintext or credentials.

### Metadata repository
- Create pending record and exactly five share-operation rows.
- Per-share state transitions persist.
- AVAILABLE cannot be committed when one share is not STORED.
- Transactions rollback on exception.
- Existing DB with wrong key does not get replaced.
- Unknown states are rejected; timestamps UTC; owner is checked.

### Orchestrator with fake adapters
- Happy store calls SSS once, Akeyless five times, and each adapter's put once.
- Failure at each share/provider index triggers rollback of stored/possible copies.
- A timeout produces UNKNOWN and queries deterministic ID before blind retry.
- Cleanup failure produces CLEANUP_REQUIRED.
- No secret/share/key is present in log records.
- Recovery collects only distinct valid shares from the same record/version.
- Fewer than three valid shares fails without invoking rebuild.
- Recovery cleanup path runs on success and errors.

## 2. Provider adapter integration tests (use test credentials only)

For each provider:
- put deterministic share ID and retrieve same ciphertext/envelope.
- repeated put does not create duplicate logical records.
- delete works; repeated delete is handled safely.
- data is durable across client reconnect/process restart.
- no expiration/TTL is configured for shares.
- credentials are restricted to the Firefly collection/table/keyspace where possible.
- timeout/error classifications are normalized.

Provider set:
1. Upstash Redis
2. Neon PostgreSQL
3. MongoDB Atlas
4. Firebase Firestore
5. Supabase PostgreSQL

## 3. End-to-end tests

- Store secret -> all 5 encrypted shares stored -> status AVAILABLE -> recover exact secret.
- Exercise all 10 share combinations.
- Simulate any two providers unavailable; recover from the remaining three.
- Simulate three unavailable; recovery fails without returning partial plaintext.
- Alter ciphertext, key reference, record ID, version, provider ID or share index; recovery rejects the invalid candidate.
- Akeyless outage fails recovery safely and does not return any partial result.
- SQLCipher key/integrity failure prevents sensitive operations.

## 4. Fault injection

Inject failure after each stage:
- pending metadata created;
- SSS split complete;
- each Akeyless Encrypt call;
- each provider write before/after server-side commit;
- metadata per-share status commit;
- final AVAILABLE commit;
- every rollback delete.

Expected: no false AVAILABLE, no untracked cleanup requirement, no plaintext persistence. For uncertain outcomes, assert the system checks the deterministic ID.

## 5. Security checks

- Search log output and test artifacts for a unique synthetic canary secret.
- Confirm `.env`, service account JSON, database file and real credentials are gitignored/not committed.
- Confirm recovery responses send `Cache-Control: no-store`.
- Confirm status/health responses reveal no sensitive provider/key configuration.
- Confirm standard `sqlite3` is not accidentally used for production metadata.
- Confirm SQLCipher `cipher_version` and integrity check in the test environment.

## 6. Test commands

The implementation agent must establish the actual test command after setting up pyproject/requirements. Prefer pytest. Report the exact commands and whether external integration tests were skipped due to absent credentials. Never mark a live-service test as passed if it was only mocked.
