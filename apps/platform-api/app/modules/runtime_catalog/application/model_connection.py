"""Short-lived, opaque references for Runtime model connections."""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
import secrets
import time
from typing import Any


class ModelReferenceError(ValueError):
    pass


def _encode(value: dict[str, Any]) -> str:
    raw = json.dumps(value, ensure_ascii=True, separators=(",", ":"), sort_keys=True).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _decode(value: str) -> dict[str, Any]:
    try:
        padded = value + "=" * (-len(value) % 4)
        decoded = base64.urlsafe_b64decode(padded.encode())
        payload = json.loads(decoded)
    except (ValueError, TypeError, UnicodeDecodeError, json.JSONDecodeError, binascii.Error) as exc:
        raise ModelReferenceError("invalid model reference") from exc
    if not isinstance(payload, dict):
        raise ModelReferenceError("invalid model reference")
    return payload


def _signature(payload: str, secret: str) -> str:
    if not secret:
        raise ModelReferenceError("model reference secret is not configured")
    return hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()


def create_model_reference(
    *,
    project_id: str,
    model_id: str,
    secret: str,
    ttl_seconds: int = 60,
) -> str:
    payload = _encode(
        {
            "v": 1,
            "project_id": project_id,
            "model_id": model_id,
            "exp": int(time.time()) + max(10, min(ttl_seconds, 300)),
            "nonce": secrets.token_urlsafe(12),
        }
    )
    return f"v1.{payload}.{_signature(payload, secret)}"


def parse_model_reference(reference: str, *, secret: str) -> dict[str, Any]:
    if not isinstance(reference, str):
        raise ModelReferenceError("invalid model reference")
    try:
        version, payload, signature = reference.split(".", 2)
    except ValueError as exc:
        raise ModelReferenceError("invalid model reference") from exc
    if version != "v1" or not hmac.compare_digest(signature, _signature(payload, secret)):
        raise ModelReferenceError("invalid model reference")
    values = _decode(payload)
    if values.get("v") != 1 or not isinstance(values.get("project_id"), str) or not isinstance(values.get("model_id"), str):
        raise ModelReferenceError("invalid model reference")
    if not isinstance(values.get("exp"), int) or values["exp"] < int(time.time()):
        raise ModelReferenceError("expired model reference")
    if not isinstance(values.get("nonce"), str) or not values["nonce"]:
        raise ModelReferenceError("invalid model reference")
    return values


__all__ = ["ModelReferenceError", "create_model_reference", "parse_model_reference"]
