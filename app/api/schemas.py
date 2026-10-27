from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class SecretCreateRequest(BaseModel):
    secret: str = Field(..., min_length=1, max_length=4096)

    @field_validator("secret")
    @classmethod
    def validate_secret(cls, value: str) -> str:
        if len(value.encode("utf-8")) == 0:
            raise ValueError("Secret must not be empty")
        return value


class SecretCreateResponse(BaseModel):
    record_id: str
    status: str
    share_count: int = 5
    threshold: int = 3
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class SecretRecoverResponse(BaseModel):
    record_id: str
    secret: str


class SecretStatusResponse(BaseModel):
    record_id: str
    owner_id: str
    version: int
    status: str
    threshold: int
    share_count: int
    confirmed_shares: int
    created_at: str
    updated_at: str
    operation_id: Optional[str] = None
