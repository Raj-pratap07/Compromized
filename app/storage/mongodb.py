from __future__ import annotations

from typing import Any

from pymongo import MongoClient
from pymongo.errors import AutoReconnect, ConnectionFailure, PyMongoError

from app.storage.base import BaseStorageAdapter, DeleteResult, HealthResult, PutResult, ShareEnvelope


class MongoDBAdapter(BaseStorageAdapter):
    provider_id = "mongodb"

    def __init__(
        self,
        *,
        uri: str,
        database: str,
        collection: str,
        timeout_seconds: float = 10.0,
        client: Any | None = None,
    ):
        if not uri or not database or not collection:
            raise ValueError("MongoDB connection and collection configuration are required")
        self.client = client or MongoClient(
            uri,
            serverSelectionTimeoutMS=int(timeout_seconds * 1000),
            connectTimeoutMS=int(timeout_seconds * 1000),
            socketTimeoutMS=int(timeout_seconds * 1000),
            retryWrites=True,
        )
        self._collection = self.client[database][collection]
        self._database_name = database
        self._collection_name = collection

    @staticmethod
    def _to_document(share_id: str, envelope: ShareEnvelope) -> dict[str, Any]:
        return {
            "_id": share_id,
            "record_id": envelope.record_id,
            "version": envelope.version,
            "share_index": envelope.share_index,
            "provider_id": envelope.provider_id,
            "key_ref": envelope.key_ref,
            "format_version": envelope.format_version,
            "ciphertext": envelope.ciphertext,
        }

    @staticmethod
    def _from_document(document: dict[str, Any]) -> ShareEnvelope:
        return ShareEnvelope(
            record_id=document["record_id"],
            version=int(document["version"]),
            share_index=int(document["share_index"]),
            provider_id=document["provider_id"],
            key_ref=document["key_ref"],
            format_version=int(document["format_version"]),
            ciphertext=document["ciphertext"],
        )

    def _ensure_collection_exists(self) -> None:
        if self._collection_name not in self.client[self._database_name].list_collection_names(
            filter={"name": self._collection_name}
        ):
            raise RuntimeError("Configured MongoDB collection is not provisioned")

    def put_share(self, share_id: str, envelope: ShareEnvelope) -> PutResult:
        try:
            self._ensure_collection_exists()
            self._collection.replace_one(
                {"_id": share_id},
                self._to_document(share_id, envelope),
                upsert=True,
            )
            return PutResult(self.provider_id, share_id, "STORED", True)
        except (AutoReconnect, ConnectionFailure):
            return PutResult(self.provider_id, share_id, "UNKNOWN", False)
        except PyMongoError:
            return PutResult(self.provider_id, share_id, "WRITE_FAILED", False)

    def get_share(self, share_id: str) -> ShareEnvelope | None:
        try:
            self._ensure_collection_exists()
            document = self._collection.find_one({"_id": share_id})
            return self._from_document(document) if document is not None else None
        except (PyMongoError, KeyError, TypeError, ValueError):
            raise RuntimeError("MongoDB share lookup failed") from None

    def delete_share(self, share_id: str) -> DeleteResult:
        try:
            self._ensure_collection_exists()
            result = self._collection.delete_one({"_id": share_id})
            existed = result.deleted_count > 0
            return DeleteResult(
                self.provider_id,
                share_id,
                "DELETE_CONFIRMED" if existed else "CONFIRMED_ABSENT",
                deleted=existed,
                existed=existed,
            )
        except (AutoReconnect, ConnectionFailure):
            return DeleteResult(self.provider_id, share_id, "UNKNOWN", False, False)
        except PyMongoError:
            return DeleteResult(self.provider_id, share_id, "DELETE_FAILED", False, False)

    def health_check(self) -> HealthResult:
        try:
            self.client.admin.command("ping")
            self._ensure_collection_exists()
            return HealthResult(self.provider_id, "ok", True)
        except PyMongoError:
            return HealthResult(self.provider_id, "unavailable", False)
        except RuntimeError:
            return HealthResult(self.provider_id, "unavailable", False)
