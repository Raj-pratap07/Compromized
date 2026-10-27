# Operations and Local Development

## 1. Local setup principles

- Use a project virtual environment and a supported Python version selected during Milestone 0.
- Copy `.env.example` to `.env`; fill only local test credentials.
- `.env` must be ignored by Git. Never paste real secrets into issue trackers, agent prompts, README, or screenshots.
- Use separate test credentials/projects for Firefly; do not use production database accounts.
- Keep the SQLCipher database in a persistent local path excluded from Git.
- If using Docker, ensure the metadata directory is mounted to persistent storage; deleting a container must not silently destroy the only metadata database.

## 2. Configuration categories

Required categories (exact names are in `.env.example`):
- application auth token and environment;
- SQLCipher DB path and stable encoded key;
- Akeyless endpoint/auth and five key references;
- Upstash connection URL/token;
- Neon connection string;
- MongoDB URI/database/collection;
- Firebase credentials path or supported application-default credentials;
- Supabase PostgreSQL connection string/table/schema.

The `.env.example` contains placeholders only. Validate the shape of every required value on startup. Do not print values on validation error.

## 3. Akeyless account readiness

Before coding all adapters:
- verify the active account can create/use five AES-256-GCM keys;
- verify Encrypt/Decrypt operation limits;
- verify the authentication method and least-privilege access to those keys;
- test binary input/output via Base64 with a record/index/provider/version context;
- confirm context mismatch fails decryption.

API-key authentication is acceptable for the short hackathon proof of concept, but Akeyless does not recommend it for production. Revisit workload identity/cloud IAM if the project is deployed beyond the demo.

## 4. SQLCipher readiness

- Install selected SQLCipher-backed Python driver on the actual OS before implementation proceeds.
- Verify runtime reports SQLCipher version.
- Confirm DB key is applied before first database read.
- Confirm correct key opens and incorrect key fails.
- Confirm `cipher_integrity_check` behavior in the selected build/version.
- Never recreate an existing DB after key/integrity failure.
- Use encrypted, access-controlled backups and test restoration.

## 5. Provider retention

- Do not set TTL/expiration for share objects.
- Ensure Upstash eviction settings cannot evict shares.
- Verify each provider's free-tier limit, storage behavior, connection method and persistence configuration. Free-tier plans can change; do not encode pricing assumptions into application logic.
- Ensure each provider account/database/collection/table has the correct deterministic ID and credential boundary.

## 6. Demo safety

Use synthetic test secrets only. Rotate any test credential pasted into a chat, agent prompt, screenshot, log or public repository. The public demo must not show real connection strings or secret values except a clearly synthetic example.
