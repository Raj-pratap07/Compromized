from __future__ import annotations

import base64
import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Dict

from dotenv import load_dotenv


PROVIDER_PROFILES = {
    "full": ("upstash", "neon", "mongodb", "firebase", "supabase"),
    "three_provider": ("upstash", "neon", "firebase"),
}


def profile_database_path(configured_path: Path, profile: str) -> str:
    if profile != "three_provider":
        return str(configured_path)
    suffix = configured_path.suffix or ".db"
    stem = configured_path.stem
    if not stem.endswith(".three-provider"):
        stem = f"{stem}.three-provider"
    return str(configured_path.with_name(f"{stem}{suffix}"))


@dataclass(frozen=True)
class Settings:
    profile: str = "full"
    environment: str = "development"
    api_token: str = field(default="", repr=False)
    max_secret_bytes: int = 4096
    database_path: str = "./data/firefly.db"
    sqlcipher_key_b64: str = field(default="", repr=False)
    akeyless_api_url: str = "https://api.akeyless.io"
    akeyless_access_id: str = field(default="", repr=False)
    akeyless_access_key: str = field(default="", repr=False)
    akeyless_key_refs: Dict[str, str] = field(
        default_factory=dict,
        repr=False,
    )
    upstash_rest_url: str = field(default="", repr=False)
    upstash_rest_token: str = field(default="", repr=False)
    neon_database_url: str = field(default="", repr=False)
    neon_schema: str = "public"
    neon_table: str = "firefly_shares"
    mongodb_uri: str = field(default="", repr=False)
    mongodb_database: str = "firefly"
    mongodb_collection: str = "shares"
    firebase_project_id: str = ""
    firebase_credentials_path: str = field(default="", repr=False)
    firestore_collection: str = "firefly_shares"
    supabase_database_url: str = field(default="", repr=False)
    supabase_schema: str = "public"
    supabase_table: str = "firefly_shares"
    provider_timeout_seconds: float = 10.0

    def __post_init__(self) -> None:
        if self.profile not in PROVIDER_PROFILES:
            raise ValueError("FIREFLY_PROFILE must be 'full' or 'three_provider'")
        if self.environment.lower() == "production" and self.profile != "full":
            raise ValueError("Production deployments must use the full provider profile")

    @property
    def provider_ids(self) -> tuple[str, ...]:
        return PROVIDER_PROFILES[self.profile]

    @property
    def share_count(self) -> int:
        return len(self.provider_ids)

    @property
    def threshold(self) -> int:
        return 3 if self.profile == "full" else 2

    @property
    def sqlcipher_key(self) -> str:
        if not self.sqlcipher_key_b64:
            raise ValueError("SQLCipher key is not configured")
        try:
            key = base64.b64decode(self.sqlcipher_key_b64, validate=True)
        except ValueError:
            raise ValueError("SQLCipher key configuration is invalid") from None
        if len(key) != 32:
            raise ValueError("SQLCipher key must decode to exactly 32 bytes")
        return key.hex()


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    load_dotenv(Path(__file__).resolve().parents[2] / ".env", override=False)
    profile = os.getenv("FIREFLY_PROFILE", "full").strip().lower()
    configured_db_path = Path(os.getenv("SQLCIPHER_DATABASE_PATH", "./data/firefly.db"))
    db_path = profile_database_path(configured_db_path, profile)
    db_key_b64 = os.getenv("SQLCIPHER_KEY_B64", "")
    return Settings(
        profile=profile,
        environment=os.getenv("FIREFLY_ENV", "development"),
        api_token=os.getenv("FIREFLY_API_TOKEN", ""),
        max_secret_bytes=int(os.getenv("FIREFLY_MAX_SECRET_BYTES", "4096")),
        database_path=db_path,
        sqlcipher_key_b64=db_key_b64,
        akeyless_api_url=os.getenv("AKEYLESS_API_URL", "https://api.akeyless.io"),
        akeyless_access_id=os.getenv("AKEYLESS_ACCESS_ID", ""),
        akeyless_access_key=os.getenv("AKEYLESS_ACCESS_KEY", ""),
        akeyless_key_refs={
            "upstash": os.getenv("AKEYLESS_KEY_UPSTASH", ""),
            "neon": os.getenv("AKEYLESS_KEY_NEON", ""),
            "mongodb": os.getenv("AKEYLESS_KEY_MONGODB", ""),
            "firebase": os.getenv("AKEYLESS_KEY_FIREBASE", ""),
            "supabase": os.getenv("AKEYLESS_KEY_SUPABASE", ""),
        },
        upstash_rest_url=os.getenv("UPSTASH_REDIS_REST_URL", ""),
        upstash_rest_token=os.getenv("UPSTASH_REDIS_REST_TOKEN", ""),
        neon_database_url=os.getenv("NEON_DATABASE_URL", ""),
        neon_schema=os.getenv("NEON_SCHEMA", "public"),
        neon_table=os.getenv("NEON_TABLE", "firefly_shares"),
        mongodb_uri=os.getenv("MONGODB_URI", ""),
        mongodb_database=os.getenv("MONGODB_DATABASE", "firefly"),
        mongodb_collection=os.getenv("MONGODB_COLLECTION", "shares"),
        firebase_project_id=os.getenv("FIREBASE_PROJECT_ID", ""),
        firebase_credentials_path=os.getenv("GOOGLE_APPLICATION_CREDENTIALS", ""),
        firestore_collection=os.getenv("FIRESTORE_COLLECTION", "firefly_shares"),
        supabase_database_url=os.getenv("SUPABASE_DATABASE_URL", ""),
        supabase_schema=os.getenv("SUPABASE_SCHEMA", "public"),
        supabase_table=os.getenv("SUPABASE_TABLE", "firefly_shares"),
        provider_timeout_seconds=float(os.getenv("FIREFLY_PROVIDER_TIMEOUT_SECONDS", "10")),
    )
