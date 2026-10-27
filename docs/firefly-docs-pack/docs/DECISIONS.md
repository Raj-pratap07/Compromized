# Architecture Decision Records — Firefly

This file is the source of truth for locked decisions. Ask a human before changing any accepted decision.

## ADR-001 — Trusted backend threat model

**Status:** Accepted  
**Decision:** The API server/orchestrator is trusted to handle plaintext secret and plaintext SSS shares during storage/recovery.  
**Reason:** This is the agreed hackathon scope.  
**Consequences:** No client-side encryption, DEK reconstruction on client, independent share-holder services, MPC/FHE/TEE, or claims that a compromised backend cannot read the secret. We still protect against isolated provider data theft and offline metadata-file theft.

## ADR-002 — SSS configuration

**Status:** Accepted  
**Decision:** Split one original secret directly into 5 shares with threshold 3.  
**Reason:** Simple MVP for one secret credential; no separate DEK/payload envelope.  
**Consequences:** Any 3 valid shares recover; fewer than 3 reveal no information under a correct SSS implementation. A successful creation requires all five writes confirmed, while later recovery tolerates up to two unavailable providers.

## ADR-003 — Share encryption

**Status:** Accepted  
**Decision:** Akeyless AES-256-GCM Encrypt/Decrypt operations; five provider-specific key references, one per provider.  
**Reason:** Keep key material managed outside share stores and simplify backend key handling.  
**Consequences:** The backend needs Akeyless authentication and permission to use the five configured keys. Akeyless availability/authorization is required for recovery. Exact same encryption context must be supplied at decrypt. Verify account plan/quotas before depending on this design.

## ADR-004 — Storage providers

**Status:** Accepted  
**Decision:** Upstash Redis, Neon PostgreSQL, MongoDB Atlas, Firebase Firestore, Supabase PostgreSQL.  
**Reason:** Five separately configured cloud provider/project boundaries for the demo.  
**Consequences:** Each provider gets exactly one share index and its own credentials. Share writes/deletes are separate remote operations; there is no cross-provider atomic transaction.

## ADR-005 — Metadata database

**Status:** Accepted  
**Decision:** SQLCipher-encrypted SQLite.  
**Reason:** Small single-instance MVP; metadata remains local and lightweight.  
**Consequences:** Keep a stable DB key outside the DB; verify the driver actually uses SQLCipher; use persistent local storage; short transactions; no multi-instance/shared network filesystem support in MVP. Application-level metadata HMAC is deferred.

## ADR-006 — Language/runtime

**Status:** Accepted  
**Decision:** Python only, using synchronous requests/adapters for MVP.  
**Reason:** Time constraints and lower integration complexity.  
**Consequences:** No Rust zeroization subsystem. Best-effort cleanup only; avoid blocking async handlers by using sync route handlers with sync dependencies.

## ADR-007 — Distributed write semantics

**Status:** Accepted  
**Decision:** All five writes must be confirmed before marking a new record `AVAILABLE`.  
**Reason:** Clear conservative create semantics.  
**Consequences:** Create may fail if a provider is down even though 3-of-5 would theoretically allow recovery later. Use stable IDs, per-share statuses, `UNKNOWN` for ambiguous timeouts, rollback and `CLEANUP_REQUIRED`.

## ADR-008 — Public deletion endpoint

**Status:** Deferred  
**Decision:** No user-facing permanent deletion endpoint in initial MVP. Adapter `delete` is mandatory for rollback.  
**Reason:** Focus the hackathon on secure storage and recovery first.  
**Consequences:** Do not remove delete from adapter interface. Add public delete later only with a full state/retention policy.

## ADR-009 — Application-level metadata MAC

**Status:** Deferred  
**Decision:** Do not add custom record-level HMAC in initial MVP.  
**Reason:** Avoid duplicating integrity logic within 24 hours. SQLCipher page-level integrity is retained.  
**Consequences:** Do not claim that SQLCipher detects every logical metadata edit through a valid DB connection. Revisit if the threat model requires that.

## ADR-010 — SSS library selection

**Status:** Pending implementation spike  
**Decision:** Use a maintained, reviewed SSS library; do not implement polynomial/field arithmetic manually.  
**Required evaluation:** Supports byte payloads of our allowed size, 5 shares/threshold 3, cryptographically secure randomness, clean reconstruction validation, supported Python version, license, current maintenance, and adequate tests. Add selected package/version and reasoning as an ADR before using it in production paths.

## ADR-011 — SQLCipher Python driver selection

**Status:** Pending compatibility spike  
**Decision:** Select a SQLCipher-linked Python driver only after verifying installability on the team's OS. Standard `sqlite3` is not sufficient.  
**Required proof:** `PRAGMA cipher_version` reports SQLCipher; wrong key fails to open existing DB; correct key opens it; tampered copy fails an integrity check where supported. Document driver package/version and key application syntax.
