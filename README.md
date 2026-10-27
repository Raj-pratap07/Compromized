# Firefly

Firefly is a synchronous FastAPI MVP. Its default `full` profile splits a
secret into five Shamir shares (threshold three), encrypts each share with its
configured Akeyless key, and stores one ciphertext per provider. SQLCipher
protects local metadata.

See [Implemented architecture and workflow](./docs/firefly-docs-pack/docs/IMPLEMENTED_ARCHITECTURE.md)
for diagrams based on the code currently wired into the application.

For temporary integration testing while MongoDB Atlas and Supabase are
unavailable, set `FIREFLY_PROFILE=three_provider` in `.env`. This profile uses
Upstash, Neon, and Firestore with three shares and a threshold of two. It is
for synthetic test data only and does not replace the default 5/3 design.
Firefly automatically uses a separate SQLCipher metadata file for this profile;
switching back to `FIREFLY_PROFILE=full` restores the full profile and its
existing records without a migration. Records are not shared across profiles.

## Local setup

1. Use Python 3.11 or newer and create/activate a virtual environment.
2. Install dependencies:

   ```powershell
   python -m pip install -r requirements.txt
   ```

3. Copy `.env.example` to `.env` and set the local API token, a Base64-encoded
   32-byte SQLCipher key, Akeyless credentials/key references, and provider
   connection settings. Do not paste credentials into chat or commit `.env`.
4. In the default `full` profile, provision the Neon and Supabase tables and
   the MongoDB collection before running Firefly. The `three_provider` profile
   does not require the MongoDB or Supabase configuration. See
   [Provider setup](./docs/firefly-docs-pack/docs/PROVIDER_SETUP.md) for the
   required schema and credential boundaries.
5. Start the API:

   ```powershell
   python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
   ```

The API uses the configured bearer token for the local demo. Keep it on
localhost and use HTTPS when deployed. The recovery endpoint returns the
plaintext secret and must only be used by an authorized caller.

## Tests

```powershell
python -m pytest -q tests
```

The unit tests use fake service clients and do not contact cloud providers.
Live store/recover tests write external ciphertext records; use dedicated test
projects and a synthetic secret, then verify cleanup. Never use production
credentials for integration tests.