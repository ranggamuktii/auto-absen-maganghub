"""AES-256 Symmetric encryption for credentials at rest."""

import base64
import hashlib
import os

from cryptography.fernet import Fernet


def _get_fernet() -> Fernet:
    """Derive a Fernet key from CRON_SECRET or ENCRYPTION_SECRET."""
    secret = (
        os.environ.get("ENCRYPTION_SECRET")
        or os.environ.get("CRON_SECRET")
        or os.environ.get("POSTGRES_PASSWORD")
        or "maganghub-default-fallback-salt-2026"
    )
    # Derive 32-byte key using SHA-256
    key = base64.urlsafe_b64encode(hashlib.sha256(secret.encode("utf-8")).digest())
    return Fernet(key)


def encrypt_password(raw_password: str) -> str:
    """Encrypt password for secure database storage."""
    if not raw_password:
        return ""
    if raw_password.startswith("enc:"):
        return raw_password  # already encrypted

    try:
        f = _get_fernet()
        ciphertext = f.encrypt(raw_password.encode("utf-8")).decode("utf-8")
        return f"enc:{ciphertext}"
    except Exception as e:
        print(f"[CRYPTO] Encryption warning: {e}")
        return raw_password


def decrypt_password(stored_password: str) -> str:
    """Decrypt password stored in database. Supports legacy plaintext."""
    if not stored_password:
        return ""
    if not stored_password.startswith("enc:"):
        return stored_password  # legacy unencrypted password

    try:
        f = _get_fernet()
        token = stored_password[len("enc:"):]
        return f.decrypt(token.encode("utf-8")).decode("utf-8")
    except Exception as e:
        print(f"[CRYPTO] Decryption warning: {e}")
        return stored_password

