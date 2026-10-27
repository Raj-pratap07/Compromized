from __future__ import annotations

import os

import sqlcipher3

from app.core.errors import ConfigurationError


def _escape_sqlcipher_key(value: str) -> str:
    return value.replace("'", "''")


def open_sqlcipher_database(database_path: str, key: str):
    os.makedirs(os.path.dirname(database_path) or ".", exist_ok=True)
    connection = sqlcipher3.connect(database_path)
    connection.execute(f"PRAGMA key = '{_escape_sqlcipher_key(key)}';")
    try:
        connection.execute("SELECT count(*) FROM sqlite_master;")
        connection.execute("PRAGMA cipher_version;")
    except Exception as exc:  # pragma: no cover - defensive guard for invalid key
        connection.close()
        raise ConfigurationError(f"SQLCipher database is not usable: {exc}") from exc
    return connection


def initialize_sqlcipher_schema(
    connection,
    *,
    share_count: int = 5,
    threshold: int = 3,
) -> None:
    if share_count < threshold or threshold < 1:
        raise ValueError("Invalid Shamir share configuration")
    connection.execute(
        f"""
        CREATE TABLE IF NOT EXISTS secret_records (
            record_id TEXT PRIMARY KEY,
            owner_id TEXT NOT NULL,
            version INTEGER NOT NULL DEFAULT 1,
            share_count INTEGER NOT NULL CHECK (share_count = {share_count}),
            threshold INTEGER NOT NULL CHECK (threshold = {threshold}),
            status TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            operation_id TEXT,
            last_error_code TEXT
        );
        """
    )
    connection.execute(
        f"""
        CREATE TABLE IF NOT EXISTS share_operations (
            record_id TEXT NOT NULL,
            version INTEGER NOT NULL,
            share_index INTEGER NOT NULL CHECK (share_index BETWEEN 1 AND {share_count}),
            provider_id TEXT NOT NULL,
            share_id TEXT NOT NULL,
            key_ref TEXT NOT NULL,
            status TEXT NOT NULL,
            attempt_count INTEGER NOT NULL DEFAULT 0,
            last_attempt_at TEXT,
            last_error_code TEXT,
            PRIMARY KEY (record_id, version, share_index),
            UNIQUE (share_id),
            FOREIGN KEY (record_id) REFERENCES secret_records(record_id)
        );
        """
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_secret_records_owner_status ON secret_records(owner_id, status);"
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_share_operations_record_status ON share_operations(record_id, status);"
    )
    connection.commit()


def check_sqlcipher_integrity(connection) -> bool:
    try:
        result = connection.execute("PRAGMA cipher_integrity_check;").fetchone()
    except Exception:
        return False
    if result is None:
        return True
    value = result[0]
    if value is None:
        return True
    return isinstance(value, str) and ("ok" in value.lower() or "pass" in value.lower() or value.lower() == "")
