from __future__ import annotations

from cryptography.fernet import Fernet, InvalidToken


class ModelCredentialError(ValueError):
    pass


def _fernet(master_key: str | None) -> Fernet:
    if not master_key:
        raise ModelCredentialError("model_config_master_key is not configured")
    try:
        return Fernet(master_key.encode("ascii"))
    except (ValueError, TypeError, UnicodeEncodeError) as exc:
        raise ModelCredentialError("model_config_master_key is invalid") from exc


def encrypt_api_key(api_key: str, *, master_key: str | None) -> str:
    if not api_key:
        raise ModelCredentialError("api_key is required")
    return _fernet(master_key).encrypt(api_key.encode("utf-8")).decode("ascii")


def decrypt_api_key(ciphertext: str | None, *, master_key: str | None) -> str:
    if not ciphertext:
        raise ModelCredentialError("model api key is not configured")
    try:
        return _fernet(master_key).decrypt(ciphertext.encode("ascii")).decode("utf-8")
    except (InvalidToken, UnicodeDecodeError, UnicodeEncodeError, ValueError) as exc:
        raise ModelCredentialError("model api key cannot be decrypted") from exc
