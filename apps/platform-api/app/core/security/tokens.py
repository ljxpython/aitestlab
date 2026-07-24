from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt

from app.core.config import Settings


class InvalidTokenError(Exception):
    pass


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _encode(payload: dict[str, Any], *, secret: str, kid: str, settings: Settings) -> str:
    return jwt.encode(
        payload,
        secret,
        algorithm=settings.jwt_algorithm,
        headers={"kid": kid, "typ": "JWT"},
    )


def _decode(
    token: str,
    *,
    expected_type: str,
    active_kid: str,
    active_secret: str,
    verification_keys: dict[str, str],
    settings: Settings,
) -> dict[str, Any]:
    try:
        header = jwt.get_unverified_header(token)
        kid = header.get("kid")
        if not isinstance(kid, str) or not kid:
            raise InvalidTokenError("missing token kid")
        keys = {**verification_keys, active_kid: active_secret}
        secret = keys.get(kid)
        if not secret:
            raise InvalidTokenError("unknown token kid")
        payload = jwt.decode(
            token,
            secret,
            algorithms=[settings.jwt_algorithm],
            issuer=settings.jwt_issuer,
            audience=settings.jwt_audience,
            options={"require": ["exp", "nbf", "sub", "jti", "type"]},
        )
    except InvalidTokenError:
        raise
    except jwt.PyJWTError as exc:
        raise InvalidTokenError("token validation failed") from exc
    if payload.get("type") != expected_type:
        raise InvalidTokenError(f"invalid {expected_type} token type")
    if not isinstance(payload.get("sub"), str) or not payload["sub"]:
        raise InvalidTokenError("invalid token subject")
    if not isinstance(payload.get("jti"), str) or not payload["jti"]:
        raise InvalidTokenError("invalid token id")
    return payload


def create_access_token(*, user_id: str, username: str, settings: Settings) -> str:
    now = _now()
    payload: dict[str, Any] = {
        "sub": user_id,
        "username": username,
        "type": "access",
        "jti": uuid.uuid4().hex,
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
        "iat": int(now.timestamp()),
        "nbf": int(now.timestamp()),
        "exp": int(
            (now + timedelta(seconds=settings.jwt_access_ttl_seconds)).timestamp()
        ),
    }
    return _encode(
        payload,
        secret=settings.jwt_access_secret,
        kid=settings.jwt_access_kid,
        settings=settings,
    )


def create_refresh_token(
    *,
    user_id: str,
    username: str,
    settings: Settings,
) -> tuple[str, str]:
    now = _now()
    token_id = uuid.uuid4().hex
    payload: dict[str, Any] = {
        "sub": user_id,
        "username": username,
        "type": "refresh",
        "jti": token_id,
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
        "iat": int(now.timestamp()),
        "nbf": int(now.timestamp()),
        "exp": int(
            (now + timedelta(seconds=settings.jwt_refresh_ttl_seconds)).timestamp()
        ),
    }
    return (
        _encode(
            payload,
            secret=settings.jwt_refresh_secret,
            kid=settings.jwt_refresh_kid,
            settings=settings,
        ),
        token_id,
    )


def decode_access_token(token: str, settings: Settings) -> dict[str, Any]:
    return _decode(
        token,
        expected_type="access",
        active_kid=settings.jwt_access_kid,
        active_secret=settings.jwt_access_secret,
        verification_keys=settings.jwt_access_verification_keys,
        settings=settings,
    )


def decode_refresh_token(token: str, settings: Settings) -> dict[str, Any]:
    return _decode(
        token,
        expected_type="refresh",
        active_kid=settings.jwt_refresh_kid,
        active_secret=settings.jwt_refresh_secret,
        verification_keys=settings.jwt_refresh_verification_keys,
        settings=settings,
    )
