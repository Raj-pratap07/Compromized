# Implementation Plan — Firefly

Build in vertical slices, from highest-risk dependencies to end-to-end behavior. Do not ask an AI coding agent to implement the entire project in one pass.

## Milestone 0 — Repository and toolchain audit

Tasks:
- Inspect existing repo, branch, uncommitted work and current files.
- Create/activate venv and establish supported Python version.
- Confirm SQLCipher driver installs and reports SQLCipher.
- Confirm Akeyless account has five usable AES-256-GCM keys and enough API operations.
- Verify credentials are not tracked.

Done when: environment checks are documented and a minimal test can open an encrypted SQLCipher DB.

## Milestone 1 — Contracts and configuration

Tasks:
- Add typed settings for app auth token, SQLCipher key, five provider connections, Akeyless auth and key references.
- Fail at startup if required config is missing or malformed (except optional test mode).
- Define `ProviderId`, `ShareEnvelope`, `PutOutcome`, `DeleteOutcome`, record/share statuses.
- Define API request/response schemas.

Done when: unit tests cover valid/invalid config and models; no real secrets required.

## Milestone 2 — SQLCipher repository

Tasks:
- Implement explicit DB initialization and open existing DB.
- Add `secret_records` and `share_operations` schema, constraints/indexes.
- Implement short methods to create pending record, update a share outcome, mark available/failed/cleanup required, fetch owner/status, list incomplete records.
- Add transaction rollback on exceptions.

Done when: correct key opens DB; wrong key fails; no plaintext secret fields exist; statuses persist across process restart; integration tests run.

## Milestone 3 — SSS service spike

Tasks:
- Evaluate candidate maintained SSS libraries; do not invent arithmetic.
- Choose based on review, API, supported payload size, secure randomness, license and tests.
- Implement thin wrapper with fixed 5/3 settings and clear validation.

Done when: 5 shares created; all 10 three-share combinations recover exact bytes; fewer-than-three requests are rejected by wrapper; duplicate/malformed share test cases rejected where supported.

## Milestone 4 — Akeyless service spike

Tasks:
- Configure one test key and exercise Encrypt/Decrypt end to end.
- Verify Base64 representation for bytes and context match behavior.
- Then map five distinct keys to five providers.
- Normalize errors/timeouts; never log secret or token.

Done when: binary test vectors round-trip exactly; wrong context/ciphertext fails; configured key mapping is enforced. If Akeyless plan doesn't support five keys, stop and bring the issue to the human rather than silently switching design.

## Milestone 5 — One storage adapter

Recommended first adapter: the easiest provider the team can provision reliably. Create one storage contract and implement one adapter.

Done when: put → get equals stored opaque envelope; repeated put is idempotent; delete works; unavailable provider and timeout are represented as distinct outcomes; logs are redacted.

## Milestone 6 — Remaining four adapters

Implement Upstash, Neon, MongoDB Atlas, Firestore and Supabase one at a time against the same interface. Avoid building all five before testing the contract.

Done when: adapter-specific integration tests pass with isolated credentials and all writes use deterministic IDs with no TTL.

## Milestone 7 — Store orchestrator

Implement pending record → split → per-share Akeyless Encrypt → adapter put → persist status → confirm five stored → AVAILABLE. On failure, reconcile unknown write, rollback stored objects and persist FAILED/CLEANUP_REQUIRED.

Done when: fault-injection tests cover failure at each provider index, Akeyless failure and timeout.

## Milestone 8 — Recovery orchestrator

Implement owner authorization, record lookup, provider selection, share validation, Akeyless Decrypt, threshold collection, SSS rebuild and safe response.

Done when: recover with all 10 share combinations; survive any two provider outages after successful storage; fail safely with fewer than three valid shares; no secret is logged/cached.

## Milestone 9 — FastAPI integration

Implement endpoints described in `API_CONTRACT.md`, safe exception mapping and dependency injection.

Done when: TestClient tests exercise happy/error paths without live providers, and integration test exercises end-to-end path with test backends.

## Milestone 10 — Failure and demo rehearsal

Test write failure, uncertain timeout, rollback, restart with pending record, SQLCipher wrong-key/tamper, Akeyless context failure, logs/redaction, provider outages.

Done when: acceptance criteria in PRD pass and known limitations are documented.

## Scope control

Deferred: async rewrite, generic plugin system, queues, automatic background reconciliation, public deletion endpoint, custom metadata MAC, Rust, client-side encryption, multi-instance deployment. A human must approve any scope change.
