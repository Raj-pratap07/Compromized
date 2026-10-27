from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.core.errors import ConfigurationError, RecordNotFoundError
from app.db.sqlcipher import check_sqlcipher_integrity, initialize_sqlcipher_schema, open_sqlcipher_database


class SecretRepository:
    def __init__(
        self,
        database_path: str,
        sqlcipher_key: str,
        *,
        share_count: int = 5,
        threshold: int = 3,
    ):
        self.database_path = database_path
        self.sqlcipher_key = sqlcipher_key
        if share_count < threshold or threshold < 1:
            raise ValueError("Invalid Shamir share configuration")
        self.share_count = share_count
        self.threshold = threshold
        self._ensure_db_ready()

    def _connect(self):
        return open_sqlcipher_database(self.database_path, self.sqlcipher_key)

    def _ensure_db_ready(self) -> None:
        connection = self._connect()
        try:
            initialize_sqlcipher_schema(
                connection,
                share_count=self.share_count,
                threshold=self.threshold,
            )
            if not check_sqlcipher_integrity(connection):
                raise ConfigurationError("SQLCipher integrity check failed")
        finally:
            connection.close()

    @staticmethod
    def _utc_now_iso() -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    def create_record(
        self,
        *,
        record_id: str,
        owner_id: str,
        status: str = "PENDING",
        operation_id: Optional[str] = None,
        share_count: int = 5,
        threshold: int = 3,
        version: int = 1,
    ) -> Dict[str, Any]:
        now = self._utc_now_iso()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO secret_records (
                    record_id, owner_id, version, share_count, threshold, status,
                    created_at, updated_at, operation_id, last_error_code
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, NULL)
                """,
                (record_id, owner_id, version, share_count, threshold, status, now, now, operation_id),
            )
            connection.commit()
        return self.get_record(record_id)

    def create_pending_operation(
        self,
        *,
        record_id: str,
        owner_id: str,
        version: int,
        share_config: List[Dict[str, Any]],
        share_count: int = 5,
        threshold: int = 3,
    ) -> Dict[str, Any]:
        if len(share_config) != share_count or share_count < threshold:
            raise ConfigurationError("Storage configuration has an invalid share count")
        if share_count != self.share_count or threshold != self.threshold:
            raise ConfigurationError("Storage configuration does not match the metadata database")
        now = self._utc_now_iso()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO secret_records (
                    record_id, owner_id, version, share_count, threshold, status,
                    created_at, updated_at, operation_id, last_error_code
                ) VALUES (?, ?, ?, ?, ?, 'PENDING', ?, ?, NULL, NULL)
                """,
                (record_id, owner_id, version, share_count, threshold, now, now),
            )
            for row in share_config:
                connection.execute(
                    """
                    INSERT INTO share_operations (
                        record_id, version, share_index, provider_id, share_id, key_ref,
                        status, attempt_count, last_attempt_at, last_error_code
                    ) VALUES (?, ?, ?, ?, ?, ?, 'NOT_STARTED', 0, NULL, NULL)
                    """,
                    (
                        record_id,
                        version,
                        row["share_index"],
                        row["provider_id"],
                        row["share_id"],
                        row["key_ref"],
                    ),
                )
            connection.commit()
        return self.get_record(record_id)

    def create_share_rows(
        self,
        *,
        record_id: str,
        version: int,
        share_config: List[Dict[str, Any]],
    ) -> None:
        with self._connect() as connection:
            for row in share_config:
                connection.execute(
                    """
                    INSERT INTO share_operations (
                        record_id, version, share_index, provider_id, share_id, key_ref,
                        status, attempt_count, last_attempt_at, last_error_code
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, 0, NULL, NULL)
                    """,
                    (
                        record_id,
                        version,
                        row["share_index"],
                        row["provider_id"],
                        row["share_id"],
                        row["key_ref"],
                        "NOT_STARTED",
                    ),
                )
            connection.commit()

    def get_record(self, record_id: str) -> Dict[str, Any]:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM secret_records WHERE record_id = ?",
                (record_id,),
            ).fetchone()
        if row is None:
            raise RecordNotFoundError(f"Record {record_id} not found")
        keys = [
            "record_id",
            "owner_id",
            "version",
            "share_count",
            "threshold",
            "status",
            "created_at",
            "updated_at",
            "operation_id",
            "last_error_code",
        ]
        return dict(zip(keys, row))

    def get_record_for_owner(self, record_id: str, owner_id: str) -> Dict[str, Any]:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM secret_records WHERE record_id = ? AND owner_id = ?",
                (record_id, owner_id),
            ).fetchone()
        if row is None:
            raise RecordNotFoundError(f"Record {record_id} for owner {owner_id} not found")
        keys = [
            "record_id",
            "owner_id",
            "version",
            "share_count",
            "threshold",
            "status",
            "created_at",
            "updated_at",
            "operation_id",
            "last_error_code",
        ]
        return dict(zip(keys, row))

    def get_share_records_for_record(self, record_id: str, version: int = 1) -> List[Dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT record_id, version, share_index, provider_id, share_id, key_ref, status,
                       attempt_count, last_attempt_at, last_error_code
                FROM share_operations
                WHERE record_id = ? AND version = ?
                ORDER BY share_index ASC
                """,
                (record_id, version),
            ).fetchall()
        keys = [
            "record_id",
            "version",
            "share_index",
            "provider_id",
            "share_id",
            "key_ref",
            "status",
            "attempt_count",
            "last_attempt_at",
            "last_error_code",
        ]
        return [dict(zip(keys, row)) for row in rows]

    def update_share_status(
        self,
        *,
        record_id: str,
        version: int,
        share_index: int,
        status: str,
        last_error_code: Optional[str] = None,
    ) -> Dict[str, Any]:
        now = self._utc_now_iso()
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE share_operations
                SET status = ?, last_attempt_at = ?, last_error_code = ?, attempt_count = attempt_count + 1
                WHERE record_id = ? AND version = ? AND share_index = ?
                """,
                (status, now, last_error_code, record_id, version, share_index),
            )
            connection.execute(
                "UPDATE secret_records SET updated_at = ? WHERE record_id = ?",
                (now, record_id),
            )
            connection.commit()
        return self.get_share_record(record_id, version, share_index)

    def get_share_record(self, record_id: str, version: int, share_index: int) -> Dict[str, Any]:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT record_id, version, share_index, provider_id, share_id, key_ref, status,
                       attempt_count, last_attempt_at, last_error_code
                FROM share_operations
                WHERE record_id = ? AND version = ? AND share_index = ?
                """,
                (record_id, version, share_index),
            ).fetchone()
        if row is None:
            raise RecordNotFoundError(f"Share {share_index} for record {record_id} not found")
        keys = [
            "record_id",
            "version",
            "share_index",
            "provider_id",
            "share_id",
            "key_ref",
            "status",
            "attempt_count",
            "last_attempt_at",
            "last_error_code",
        ]
        return dict(zip(keys, row))

    def set_record_status(
        self,
        *,
        record_id: str,
        status: str,
        last_error_code: Optional[str] = None,
    ) -> Dict[str, Any]:
        now = self._utc_now_iso()
        with self._connect() as connection:
            if status == "AVAILABLE":
                record = connection.execute(
                    "SELECT share_count, version FROM secret_records WHERE record_id = ?",
                    (record_id,),
                ).fetchone()
                if record is None:
                    raise RecordNotFoundError(f"Record {record_id} not found")
                stored_count = connection.execute(
                    """
                    SELECT COUNT(*) FROM share_operations
                    WHERE record_id = ? AND version = ? AND status = 'STORED'
                    """,
                    (record_id, record[1]),
                ).fetchone()[0]
                if stored_count != record[0]:
                    raise ConfigurationError(
                        "A record is AVAILABLE only after all configured writes are confirmed"
                    )
            connection.execute(
                "UPDATE secret_records SET status = ?, updated_at = ?, last_error_code = ? WHERE record_id = ?",
                (status, now, last_error_code, record_id),
            )
            connection.commit()
        return self.get_record(record_id)

    def get_status(self, record_id: str) -> Dict[str, Any]:
        return self.get_record(record_id)

    def list_pending_records(self) -> List[Dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM secret_records WHERE status IN ('PENDING', 'UNKNOWN', 'CLEANUP_REQUIRED') ORDER BY created_at DESC"
            ).fetchall()
        keys = [
            "record_id",
            "owner_id",
            "version",
            "share_count",
            "threshold",
            "status",
            "created_at",
            "updated_at",
            "operation_id",
            "last_error_code",
        ]
        return [dict(zip(keys, row)) for row in rows]
