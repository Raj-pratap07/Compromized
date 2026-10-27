from __future__ import annotations

from app.storage.postgres import PostgresStorageAdapter


class SupabaseAdapter(PostgresStorageAdapter):
    provider_id = "supabase"
