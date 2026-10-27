# Firefly: Implemented Architecture and Workflow

This document describes the behavior wired into the current Python code, not
the broader product plan.

## What runs with the current local configuration

The application reads `FIREFLY_PROFILE` from the repository-root `.env`. If it
is missing, the code defaults to `full`. The current local settings resolve to:

- Profile: `full`
- Shamir: 5 shares, threshold 3
- Providers: Upstash, Neon, MongoDB Atlas, Firestore, and Supabase

The code also supports `FIREFLY_PROFILE=three_provider`:

- Shamir: 3 shares, threshold 2
- Providers: Upstash, Neon, and Firestore
- MongoDB and Supabase settings are not required for this profile
- SQLCipher metadata uses a separate filename with `.three-provider` added

The three-provider live tests used a temporary process-level profile override;
they did not change `.env`. To make a normal local app launch use the reduced
profile, set `FIREFLY_PROFILE=three_provider` in `.env` and restart the app.
The reduced profile is intended for synthetic hackathon demos and is rejected
when `FIREFLY_ENV=production`.

## Component and data-flow diagram

```mermaid
flowchart LR
    Client["Demo client"]
    API["FastAPI routes<br/>Authorization header check<br/>fixed owner: demo-owner"]
    Config["Settings and provider registry<br/>FIREFLY_PROFILE selects active providers"]
    Orchestrator["StorageOrchestrator<br/>sequential store / recover"]
    SSS["SSSService<br/>shamirs library<br/>share bundles"]
    Akeyless["Akeyless REST<br/>AES-256-GCM encrypt / decrypt"]
    Metadata[("SQLCipher SQLite<br/>secret_records<br/>share_operations")]
    Upstash[("Upstash Redis")]
    Neon[("Neon PostgreSQL<br/>public.firefly_shares by default")]
    Mongo[("MongoDB Atlas")]
    Firestore[("Firebase Firestore")]
    Supabase[("Supabase PostgreSQL<br/>public.firefly_shares by default")]

    Client --> API
    API --> Config
    Config --> Orchestrator
    API --> Orchestrator
    Orchestrator <--> Metadata
    Orchestrator <--> SSS
    Orchestrator <--> Akeyless
    Orchestrator --> Upstash
    Orchestrator --> Neon
    Orchestrator --> Mongo
    Orchestrator --> Firestore
    Orchestrator --> Supabase
    Upstash --> Orchestrator
    Neon --> Orchestrator
    Mongo --> Orchestrator
    Firestore --> Orchestrator
    Supabase --> Orchestrator
    Orchestrator --> API

```

In the `three_provider` profile, MongoDB and Supabase are not instantiated or
contacted. In `full`, all five providers are active. Provider index/key mapping
is assigned in the active profile's order:

| Profile | Share 1 | Share 2 | Share 3 | Share 4 | Share 5 |
|---|---|---|---|---|---|
| `full` (default) | Upstash | Neon | MongoDB | Firestore | Supabase |
| `three_provider` | Upstash | Neon | Firestore | — | — |

Each active provider uses its matching configured Akeyless key reference.

## Store workflow as implemented

```mermaid
flowchart TD
    Start["POST /secrets"] --> Auth{"Authorization accepted?"}
    Auth -- No --> Reject401["401"]
    Auth -- Yes --> Validate["Validate non-empty secret<br/>and configured UTF-8 byte limit"]
    Validate --> Registry["Build active provider registry<br/>validate active settings"]
    Registry --> Pending["Generate UUID record ID<br/>commit PENDING record and one NOT_STARTED row per provider"]
    Pending --> Split["SSSService splits the secret in memory<br/>15-byte chunks, wrapped as indexed ShareBundles"]
    Split --> Loop["For each active provider in order"]
    Loop --> Encrypt["Akeyless /auth as needed<br/>then /encrypt with Base64 input"]
    Encrypt --> Context["Context binds record ID, version,<br/>share index, provider ID, format version"]
    Context --> Put["Write opaque ciphertext<br/>using deterministic share ID"]
    Put --> Outcome{"Provider confirms write?"}
    Outcome -- Yes --> Stored["Commit share status STORED"]
    Stored --> More{"More active providers?"}
    More -- Yes --> Loop
    More -- No --> AllStored["Repository verifies all profile<br/>share rows are STORED"]
    AllStored --> Available["Commit record AVAILABLE"]
    Available --> Response["201: record ID, status,<br/>share count and threshold"]
    Outcome -- "UNKNOWN / timeout" --> Reconcile["Mark UNKNOWN; lookup deterministic ID"]
    Reconcile --> Decision{"Exact envelope found?"}
    Decision -- Yes --> Stored
    Decision -- "Confirmed absent" --> Retry["Retry same deterministic write;<br/>reconcile a second UNKNOWN"]
    Retry --> Outcome
    Decision -- "Lookup failed / mismatch" --> Rollback
    Outcome -- "Confirmed failure" --> Rollback["Rollback: issue delete for each configured share ID"]
    Encrypt -- "Encryption error" --> Rollback
    Rollback --> Cleanup{"All deletes confirmed<br/>or objects absent?"}
    Cleanup -- Yes --> Failed["Record FAILED"]
    Cleanup -- No --> CleanupRequired["Record CLEANUP_REQUIRED;<br/>retain metadata"]
```

Implementation details represented in the diagram:

- The pending metadata record and its share rows are committed before external
  encryption or provider writes. Network calls are not made inside that
  metadata transaction.
- Provider writes happen sequentially, not in parallel. There is no
  cross-provider transaction.
- `AVAILABLE` means all providers in the selected profile have confirmed
  writes and the metadata transition has committed.
- Share IDs are deterministic from the random record ID, version, and share
  index. Akeyless ciphertext is stored as an opaque value with routing metadata.
- On store failure, the orchestrator attempts deletes across the configured
  share rows. It records confirmed cleanup or `CLEANUP_REQUIRED`; cleanup is
  not guaranteed just because the request failed.

## Recovery workflow as implemented

```mermaid
flowchart TD
    Start["POST /secrets/{record_id}/recover"] --> Auth{"Authorization accepted?"}
    Auth -- No --> Reject401["401"]
    Auth -- Yes --> Owner["Load metadata for fixed demo owner"]
    Owner --> Available{"Record status AVAILABLE?"}
    Available -- No --> Reject["Safe recovery error"]
    Available -- Yes --> Rows["Read share rows for record version"]
    Rows --> Iterate["Visit each STORED share row in order"]
    Iterate --> Fetch["Provider GET by deterministic share ID"]
    Fetch --> Envelope{"Envelope fields match<br/>metadata and profile key mapping?"}
    Envelope -- No / absent / error --> Next["Skip candidate"]
    Envelope -- Yes --> Decrypt["Akeyless /decrypt<br/>same key reference and context"]
    Decrypt --> Decode["Decode indexed ShareBundle"]
    Decode --> Valid{"Valid new share index?"}
    Valid -- No / error --> Next
    Valid -- Yes --> Collect["Collect distinct valid share"]
    Collect --> Next
    Next --> More{"More stored rows?"}
    More -- Yes --> Iterate
    More -- No --> Threshold{"Collected at least<br/>profile threshold?"}
    Threshold -- No --> Fail["Recovery unavailable"]
    Threshold -- Yes --> Rebuild["SSSService reconstructs using<br/>the first threshold shares"]
    Rebuild --> UTF8{"Valid UTF-8 secret?"}
    UTF8 -- No --> Fail
    UTF8 -- Yes --> Response["200 response with secret<br/>Cache-Control: no-store"]
```

The current recovery loop visits all stored candidates before checking the
threshold; it does not stop provider queries immediately when the threshold is
reached. It only supplies the first threshold number of distinct decoded
shares to reconstruction. A candidate is skipped if its envelope metadata
doesn't match, its provider read fails, Akeyless rejects decryption, or share
decoding/validation fails.

For `three_provider`, one valid share is insufficient and two distinct valid
shares are required. The negative live test retrieved/decrypted one synthetic
share, observed reconstruction rejection, and confirmed remote test share
cleanup.

## Metadata, providers, and API boundaries

### SQLCipher metadata

The encrypted local database contains two tables:

- `secret_records`: owner, version, profile share count/threshold, status, and
  timestamps.
- `share_operations`: share index, provider ID, deterministic share ID,
  Akeyless key reference, status, attempt count, and normalized error code.

The original secret, plaintext Shamir shares, and Akeyless key material are
not repository fields. Each profile gets a compatible schema check constraint;
the three-provider profile's database path is separate from the full
profile's path. The current repository initializes tables with
`CREATE TABLE IF NOT EXISTS`.

### Provider adapters

All adapters implement `put_share`, `get_share`, `delete_share`, and
`health_check`:

- Upstash uses REST `SET`/`GET`/`DEL`/`PING`; share writes set no TTL.
- Neon and Supabase use the shared psycopg adapter over TLS and configured
  schema/table identifiers.
- MongoDB uses deterministic document `_id` values.
- Firestore uses deterministic document IDs in the configured collection.

### API routes currently present

- `GET /health`: returns `{"status":"ok"}` without probing provider readiness.
- `POST /secrets`: authenticated store request.
- `POST /secrets/{record_id}/recover`: authenticated recovery; the returned
  secret response uses `Cache-Control: no-store` and `Pragma: no-cache`.
- `GET /secrets/{record_id}/status`: authenticated metadata status.

The demo auth dependency maps any valid configured bearer token to the single
hard-coded owner `demo-owner`; this is not multi-user identity management.
There is no public delete endpoint or automatic background reconciliation
worker. Delete operations are used internally for rollback.

## Demo-relevant boundaries

- Akeyless authentication/encrypt/decrypt and all provider operations are live
  network calls with configured timeouts.
- A timeout can leave the outcome unknown; the write path reconciles by the
  deterministic share ID before retrying.
- SQLCipher and provider test results are environment-specific. The
  three-provider end-to-end live test passed with a synthetic secret and
  verified remote deletion; the normal local profile currently resolves to
  `full`, so select `three_provider` in `.env` before launching a three-provider
  demo.
- Python memory cleanup is best-effort; complete zeroization is not claimed.
