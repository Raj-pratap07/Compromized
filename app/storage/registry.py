from __future__ import annotations

from typing import Dict, Iterable

from psycopg.conninfo import make_conninfo
from pymongo.uri_parser import parse_uri

from app.core.config import Settings, get_settings
from app.core.errors import ConfigurationError
from app.storage.base import BaseStorageAdapter
from app.storage.firebase import FirebaseAdapter
from app.storage.mongodb import MongoDBAdapter
from app.storage.neon import NeonAdapter
from app.storage.supabase import SupabaseAdapter
from app.storage.upstash import UpstashAdapter


class ProviderRegistry:
    def __init__(self, adapters: Iterable[BaseStorageAdapter]):
        self._adapters: Dict[str, BaseStorageAdapter] = {
            adapter.provider_id: adapter for adapter in adapters
        }

    def get(self, provider_id: str) -> BaseStorageAdapter:
        if provider_id not in self._adapters:
            raise KeyError(f"Unknown provider: {provider_id}")
        return self._adapters[provider_id]

    def all(self) -> Iterable[BaseStorageAdapter]:
        return list(self._adapters.values())

    def provider_ids(self) -> list[str]:
        return list(self._adapters.keys())

    def __contains__(self, provider_id: str) -> bool:
        return provider_id in self._adapters


def create_provider_registry(settings: Settings | None = None) -> ProviderRegistry:
    config = settings or get_settings()
    timeout = config.provider_timeout_seconds
    provider_configuration = {
        "upstash": (config.upstash_rest_url, config.upstash_rest_token),
        "neon": (config.neon_database_url,),
        "mongodb": (config.mongodb_uri, config.mongodb_database, config.mongodb_collection),
        "firebase": (config.firebase_project_id, config.firestore_collection),
        "supabase": (
            config.supabase_database_url,
            config.supabase_schema,
            config.supabase_table,
        ),
    }
    configured_values = [
        config.akeyless_access_id,
        config.akeyless_access_key,
        *(value for provider_id in config.provider_ids for value in provider_configuration[provider_id]),
        *(config.akeyless_key_refs.get(provider_id, "") for provider_id in config.provider_ids),
    ]
    placeholder_markers = ("replace_me", "replace_with", "your_", "changeme", "<", ">")
    if timeout <= 0 or any(
        not value or any(marker in value.lower() for marker in placeholder_markers)
        for value in configured_values
    ):
        raise ConfigurationError("Required provider configuration is missing or invalid")
    try:
        if "neon" in config.provider_ids:
            make_conninfo(config.neon_database_url)
        if "supabase" in config.provider_ids:
            make_conninfo(config.supabase_database_url)
        if "mongodb" in config.provider_ids:
            parse_uri(config.mongodb_uri)
    except Exception:
        raise ConfigurationError("A provider connection configuration is invalid") from None

    adapters = []
    if "upstash" in config.provider_ids:
        adapters.append(
            UpstashAdapter(
                rest_url=config.upstash_rest_url,
                rest_token=config.upstash_rest_token,
                timeout_seconds=timeout,
            )
        )
    if "neon" in config.provider_ids:
        adapters.append(
            NeonAdapter(
                database_url=config.neon_database_url,
                schema=config.neon_schema,
                table=config.neon_table,
                timeout_seconds=timeout,
            )
        )
    if "mongodb" in config.provider_ids:
        adapters.append(
            MongoDBAdapter(
                uri=config.mongodb_uri,
                database=config.mongodb_database,
                collection=config.mongodb_collection,
                timeout_seconds=timeout,
            )
        )
    if "firebase" in config.provider_ids:
        adapters.append(
            FirebaseAdapter(
                project_id=config.firebase_project_id,
                collection=config.firestore_collection,
                credentials_path=config.firebase_credentials_path,
                timeout_seconds=timeout,
            )
        )
    if "supabase" in config.provider_ids:
        adapters.append(
            SupabaseAdapter(
                database_url=config.supabase_database_url,
                schema=config.supabase_schema,
                table=config.supabase_table,
                timeout_seconds=timeout,
            )
        )
    return ProviderRegistry(adapters)
