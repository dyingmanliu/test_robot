from __future__ import annotations

import hashlib
import os
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
from jose import JWTError, jwt


def _sha256_hex_for_bcrypt(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()

SECRET_KEY = os.getenv("JWT_SECRET", "change-me-in-production-use-long-random-string")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", "10080"))


def hash_password(password: str) -> str:
    secret = _sha256_hex_for_bcrypt(password).encode("ascii")
    return bcrypt.hashpw(secret, bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    h = hashed.encode("utf-8")
    plain_b = plain.encode("utf-8")
    if len(plain_b) <= 72:
        try:
            if bcrypt.checkpw(plain_b, h):
                return True
        except ValueError:
            pass
    try:
        return bcrypt.checkpw(_sha256_hex_for_bcrypt(plain).encode("ascii"), h)
    except ValueError:
        return False


def create_access_token(user_id: int, role: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {"sub": str(user_id), "role": role, "exp": expire}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token_payload(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        return None


def decode_token(token: str) -> Optional[int]:
    payload = decode_access_token_payload(token)
    if payload is None:
        return None
    sub = payload.get("sub")
    if sub is None:
        return None
    try:
        return int(sub)
    except (TypeError, ValueError):
        return None
