"""Unsigned JWTs issued and validated by the local faker."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import threading
import time
from typing import Any

TOKEN_LIFETIME_SECONDS = 3600
TOKEN_ISSUER = "sector-api-faker"
_ISSUED_TOKEN_IDS: dict[str, tuple[int, bytes]] = {}
_TOKEN_LOCK = threading.Lock()


def credentials_match(user_id: str, password: str) -> bool:
    configured_user = os.environ.get("SECTOR_API_USER", "")
    configured_password = os.environ.get("SECTOR_API_PASSWORD", "")
    if not configured_user or not configured_password:
        return False
    return hmac.compare_digest(
        user_id.encode("utf-8"), configured_user.encode("utf-8")
    ) and hmac.compare_digest(
        password.encode("utf-8"), configured_password.encode("utf-8")
    )


def issue_token(user_id: str, panel_id: str) -> str:
    now = int(time.time())
    expires_at = now + TOKEN_LIFETIME_SECONDS
    token_id = secrets.token_urlsafe(32)
    header = {"alg": "none", "typ": "JWT"}
    payload = {
        "sub": user_id,
        "iss": TOKEN_ISSUER,
        "panelId": panel_id,
        "iat": now,
        "exp": expires_at,
        "jti": token_id,
    }

    def encode(part: dict[str, Any]) -> str:
        return base64.urlsafe_b64encode(
            json.dumps(part, separators=(",", ":")).encode("utf-8")
        ).decode("ascii").rstrip("=")

    token = f"{encode(header)}.{encode(payload)}."
    token_digest = hashlib.sha256(token.encode("ascii")).digest()
    with _TOKEN_LOCK:
        expired_ids = [
            issued_id
            for issued_id, (expiration, _) in _ISSUED_TOKEN_IDS.items()
            if expiration <= now
        ]
        for issued_id in expired_ids:
            del _ISSUED_TOKEN_IDS[issued_id]
        _ISSUED_TOKEN_IDS[token_id] = (expires_at, token_digest)
    return token


def is_valid_token(token: str) -> bool:
    parts = token.split(".")
    if len(parts) != 3 or parts[2]:
        return False

    try:
        header_part = parts[0] + "=" * (-len(parts[0]) % 4)
        payload_part = parts[1] + "=" * (-len(parts[1]) % 4)
        header = json.loads(base64.urlsafe_b64decode(header_part))
        payload = json.loads(base64.urlsafe_b64decode(payload_part))
        token_digest = hashlib.sha256(token.encode("ascii")).digest()
    except (UnicodeError, ValueError, TypeError):
        return False

    if (
        not isinstance(header, dict)
        or header.get("alg") != "none"
        or header.get("typ") != "JWT"
        or not isinstance(payload, dict)
        or payload.get("iss") != TOKEN_ISSUER
        or not isinstance(payload.get("sub"), str)
        or not payload["sub"]
        or not isinstance(payload.get("panelId"), str)
        or not payload["panelId"]
        or not isinstance(payload.get("jti"), str)
        or not payload["jti"]
        or type(payload.get("iat")) is not int
        or type(payload.get("exp")) is not int
    ):
        return False

    now = time.time()
    issued_at = payload["iat"]
    expires_at = payload["exp"]
    if issued_at > now or expires_at <= now or expires_at <= issued_at:
        return False

    with _TOKEN_LOCK:
        issued_token = _ISSUED_TOKEN_IDS.get(payload["jti"])
        if issued_token is None:
            return False
        if issued_token[0] <= now:
            del _ISSUED_TOKEN_IDS[payload["jti"]]
            return False
        return issued_token[0] == expires_at and hmac.compare_digest(
            issued_token[1], token_digest
        )
