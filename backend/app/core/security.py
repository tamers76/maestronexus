"""Security primitives: password hashing (bcrypt) and JWT tokens.

Kept dependency-light on purpose so the auth surface is easy to audit (docs/14).
Feature modules should depend on the dependencies in ``app/core/deps.py`` rather
than calling these functions directly.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

import bcrypt
import jwt

from app.core.config import settings

TokenType = Literal["access", "refresh"]

# bcrypt has a hard 72-byte input limit; longer passwords are truncated by the
# algorithm. We encode to bytes explicitly to control that boundary.
_BCRYPT_MAX_BYTES = 72


def hash_password(password: str) -> str:
    pw = password.encode("utf-8")[:_BCRYPT_MAX_BYTES]
    return bcrypt.hashpw(pw, bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str | None) -> bool:
    if not password_hash:
        return False
    pw = password.encode("utf-8")[:_BCRYPT_MAX_BYTES]
    try:
        return bcrypt.checkpw(pw, password_hash.encode("utf-8"))
    except ValueError:
        return False


def _create_token(
    subject: uuid.UUID | str,
    tenant_id: uuid.UUID | str,
    token_type: TokenType,
    expires_delta: timedelta,
    extra_claims: dict[str, Any] | None = None,
) -> str:
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": str(subject),
        "tid": str(tenant_id),
        "type": token_type,
        "iat": now,
        "exp": now + expires_delta,
    }
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def create_access_token(
    subject: uuid.UUID | str,
    tenant_id: uuid.UUID | str,
    extra_claims: dict[str, Any] | None = None,
) -> str:
    return _create_token(
        subject,
        tenant_id,
        "access",
        timedelta(minutes=settings.access_token_expire_minutes),
        extra_claims,
    )


def create_refresh_token(subject: uuid.UUID | str, tenant_id: uuid.UUID | str) -> str:
    return _create_token(
        subject,
        tenant_id,
        "refresh",
        timedelta(days=settings.refresh_token_expire_days),
    )


def decode_token(token: str) -> dict[str, Any]:
    """Decode and verify a JWT. Raises ``jwt.PyJWTError`` on any problem."""

    return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
