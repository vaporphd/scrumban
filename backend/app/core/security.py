"""Password hashing, JWT issuance/decoding, and refresh-token primitives.

See ADR-0005 for the refresh-token design. Passwords go through argon2;
refresh tokens are 32 bytes of `secrets.token_urlsafe` hashed with
SHA-256 before storage. Access tokens are HS256 JWTs with `sub`, `iat`,
and `exp`.
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime, timedelta

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from jose import JWTError, jwt

from app.core.config import get_settings

_password_hasher = PasswordHasher()


def hash_password(plaintext: str) -> str:
    return _password_hasher.hash(plaintext)


def verify_password(plaintext: str, hashed: str) -> bool:
    try:
        return _password_hasher.verify(hashed, plaintext)
    except VerifyMismatchError:
        return False
    except Exception:
        # Malformed stored hash, etc. Treat as invalid credentials; do not
        # leak the distinction to callers.
        return False


def issue_access_token(user_id: int, now: datetime | None = None) -> str:
    settings = get_settings()
    issued_at = now or datetime.now(tz=UTC)
    expires_at = issued_at + timedelta(minutes=settings.jwt.access_ttl_minutes)
    payload = {
        "sub": str(user_id),
        "iat": int(issued_at.timestamp()),
        "exp": int(expires_at.timestamp()),
    }
    return jwt.encode(payload, settings.jwt.secret, algorithm=settings.jwt.algorithm)


def decode_access_token(token: str) -> int | None:
    """Return the user_id encoded in a valid access token, or None.

    Any decode failure — bad signature, expired, malformed — collapses to
    None so callers can uniformly 401.
    """
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.jwt.secret, algorithms=[settings.jwt.algorithm])
    except JWTError:
        return None
    sub = payload.get("sub")
    if not isinstance(sub, str):
        return None
    try:
        return int(sub)
    except ValueError:
        return None


def generate_refresh_token() -> str:
    """Opaque 32-byte url-safe token. Returned to the client, never stored."""
    return secrets.token_urlsafe(32)


def hash_refresh_token(plaintext: str) -> str:
    """Hex SHA-256. 256 bits of input entropy — no KDF needed (ADR-0005)."""
    return hashlib.sha256(plaintext.encode("utf-8")).hexdigest()
