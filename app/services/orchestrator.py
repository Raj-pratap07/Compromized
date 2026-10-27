from __future__ import annotations

import uuid
from typing import Any, Dict

from app.core.errors import RecoveryError
from app.db.repository import SecretRepository
from app.services.akeyless_service import AkeylessService
from app.services.sss_service import SSSService, ShareBundle
from app.storage.base import PutResult, ShareEnvelope, build_share_id
from app.storage.registry import ProviderRegistry


class StorageOrchestrator:
    def __init__(
        self,
        *,
        repository: SecretRepository,
        sss_service: SSSService,
        akeyless_service: AkeylessService,
        provider_registry: ProviderRegistry,
    ):
        self.repository = repository
        self.sss_service = sss_service
        self.akeyless_service = akeyless_service
        self.provider_registry = provider_registry
        self.provider_order = list(provider_registry.provider_ids())
        if (
            len(self.provider_order) != self.sss_service.share_count
            or len(set(self.provider_order)) != len(self.provider_order)
        ):
            raise ValueError("Provider count must match the configured Shamir share count")
        if self.sss_service.threshold > self.sss_service.share_count:
            raise ValueError("Shamir threshold cannot exceed the configured share count")
        if (
            self.repository.share_count != self.sss_service.share_count
            or self.repository.threshold != self.sss_service.threshold
        ):
            raise ValueError("Metadata and Shamir profiles must match")
        if any(
            provider_id not in self.akeyless_service.key_refs
            for provider_id in self.provider_order
        ):
            raise ValueError("Each active provider must have a configured Akeyless key reference")

    def create_record(self, owner_id: str) -> Dict[str, Any]:
        record_id = uuid.uuid4().hex
        version = 1
        share_rows = []
        for share_index, provider_id in enumerate(self.provider_order, start=1):
            share_id = build_share_id(record_id, version, share_index)
            share_rows.append(
                {
                    "share_index": share_index,
                    "provider_id": provider_id,
                    "share_id": share_id,
                    "key_ref": self.akeyless_service.key_refs[provider_id],
                }
            )
        self.repository.create_pending_operation(
            record_id=record_id,
            owner_id=owner_id,
            version=version,
            share_config=share_rows,
            share_count=self.sss_service.share_count,
            threshold=self.sss_service.threshold,
        )
        return {"record_id": record_id, "version": version}

    def store_secret(self, owner_id: str, secret: str) -> Dict[str, Any]:
        record = self.create_record(owner_id)
        record_id = record["record_id"]
        version = record["version"]
        try:
            shares = self.sss_service.split_secret(secret)
            if len(shares) != len(self.provider_order):
                raise RecoveryError("Secret sharing returned an invalid share count")
            for share_index, (share, provider_id) in enumerate(zip(shares, self.provider_order), start=1):
                share_bytes = share.to_bytes()
                key_ref = self.akeyless_service.key_refs[provider_id]
                ciphertext = self.akeyless_service.encrypt_share(
                    share_bytes,
                    record_id=record_id,
                    version=version,
                    share_index=share_index,
                    provider_id=provider_id,
                    key_ref=key_ref,
                )
                share_id = build_share_id(record_id, version, share_index)
                envelope = ShareEnvelope(
                    record_id=record_id,
                    version=version,
                    share_index=share_index,
                    provider_id=provider_id,
                    key_ref=key_ref,
                    format_version=1,
                    ciphertext=ciphertext,
                )
                provider = self.provider_registry.get(provider_id)
                result = provider.put_share(share_id, envelope)
                if not result.success:
                    if result.status == "UNKNOWN":
                        self.repository.update_share_status(
                            record_id=record_id,
                            version=version,
                            share_index=share_index,
                            status="UNKNOWN",
                        )
                        stored = None
                        try:
                            stored = provider.get_share(share_id)
                        except Exception:
                            lookup_succeeded = False
                        else:
                            lookup_succeeded = True
                        if lookup_succeeded and stored == envelope:
                            result = PutResult(provider_id, share_id, "STORED", True)
                        elif lookup_succeeded and stored is None:
                            result = provider.put_share(share_id, envelope)
                            if not result.success and result.status == "UNKNOWN":
                                self.repository.update_share_status(
                                    record_id=record_id,
                                    version=version,
                                    share_index=share_index,
                                    status="UNKNOWN",
                                )
                                try:
                                    stored = provider.get_share(share_id)
                                except Exception:
                                    lookup_succeeded = False
                                else:
                                    lookup_succeeded = True
                                if lookup_succeeded and stored == envelope:
                                    result = PutResult(provider_id, share_id, "STORED", True)
                                elif lookup_succeeded:
                                    result = PutResult(provider_id, share_id, "WRITE_FAILED", False)
                    if not result.success:
                        share_status = "UNKNOWN" if result.status == "UNKNOWN" else "WRITE_FAILED"
                        self.repository.update_share_status(
                            record_id=record_id,
                            version=version,
                            share_index=share_index,
                            status=share_status,
                            last_error_code=share_status,
                        )
                        raise RecoveryError("One or more provider writes failed")
                self.repository.update_share_status(
                    record_id=record_id,
                    version=version,
                    share_index=share_index,
                    status="STORED",
                )
            self.repository.set_record_status(record_id=record_id, status="AVAILABLE")
            return {
                "record_id": record_id,
                "status": "AVAILABLE",
                "share_count": self.sss_service.share_count,
                "threshold": self.sss_service.threshold,
            }
        except Exception:
            self.rollback(record_id)
            raise

    def rollback(self, record_id: str) -> None:
        record = self.repository.get_record(record_id)
        cleanup_complete = True
        for share in self.repository.get_share_records_for_record(record_id, record["version"]):
            try:
                result = self.provider_registry.get(share["provider_id"]).delete_share(share["share_id"])
            except Exception:
                result = None
            if result is not None and (
                result.deleted or result.status == "CONFIRMED_ABSENT"
            ):
                self.repository.update_share_status(
                    record_id=record_id,
                    version=record["version"],
                    share_index=share["share_index"],
                    status="DELETE_CONFIRMED",
                )
            else:
                cleanup_complete = False
                self.repository.update_share_status(
                    record_id=record_id,
                    version=record["version"],
                    share_index=share["share_index"],
                    status="UNKNOWN" if result is None or result.status == "UNKNOWN" else "CLEANUP_REQUIRED",
                    last_error_code="DELETE_UNCONFIRMED",
                )
        self.repository.set_record_status(
            record_id=record_id,
            status="FAILED" if cleanup_complete else "CLEANUP_REQUIRED",
        )

    def recover_secret(self, record_id: str, owner_id: str) -> str:
        record = self.repository.get_record_for_owner(record_id, owner_id)
        if record["status"] != "AVAILABLE":
            raise RecoveryError("Record is not available for recovery")
        valid_shares = []
        for share in self.repository.get_share_records_for_record(record_id, record["version"]):
            if share["status"] != "STORED":
                continue
            provider = self.provider_registry.get(share["provider_id"])
            try:
                envelope = provider.get_share(share["share_id"])
            except Exception:
                continue
            if envelope is None:
                continue
            try:
                self.akeyless_service.validate_key_reference(share["provider_id"], share["key_ref"])
                if (
                    envelope.record_id != record_id
                    or envelope.version != share["version"]
                    or envelope.share_index != share["share_index"]
                    or envelope.provider_id != share["provider_id"]
                    or envelope.key_ref != share["key_ref"]
                    or envelope.format_version != 1
                ):
                    continue
                plaintext = self.akeyless_service.decrypt_share(
                    envelope.ciphertext,
                    record_id=record_id,
                    version=share["version"],
                    share_index=share["share_index"],
                    provider_id=share["provider_id"],
                    key_ref=share["key_ref"],
                )
                share_object = self.sss_service.decode_share(plaintext)
                if isinstance(share_object, ShareBundle):
                    share_index = share_object.index
                    if share_index != share["share_index"]:
                        continue
                    if any(getattr(candidate, "index", None) == share_index for candidate in valid_shares):
                        continue
                    if all(getattr(candidate, "index", None) != share_index for candidate in valid_shares):
                        valid_shares.append(share_object)
                    continue
                share_index = getattr(share_object, "index", None)
                if share_index is None:
                    continue
                if share_index != share["share_index"]:
                    continue
                if all(getattr(candidate, "index", None) != share_index for candidate in valid_shares):
                    valid_shares.append(share_object)
            except Exception:
                continue
        threshold = record["threshold"]
        if len(valid_shares) < threshold:
            raise RecoveryError(
                f"Fewer than {threshold} valid shares were available for recovery"
            )
        secret_bytes = self.sss_service.recover_secret(valid_shares[:threshold])
        try:
            return secret_bytes.decode("utf-8")
        except UnicodeDecodeError:
            raise RecoveryError("Recovered secret encoding is invalid") from None

    def get_status(self, record_id: str, owner_id: str) -> Dict[str, Any]:
        record = self.repository.get_record_for_owner(record_id, owner_id)
        shares = self.repository.get_share_records_for_record(record_id, record["version"])
        confirmed = sum(1 for share in shares if share["status"] == "STORED")
        info = dict(record)
        info["confirmed_shares"] = confirmed
        return info
