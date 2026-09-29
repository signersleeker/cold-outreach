"""AES-GCM encryption for OAuth tokens at rest.

Ported from kinnatic/apps/backend-core/app/lib/crypto.py.
"""

import base64
import hashlib
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

_NONCE_SIZE = 12


def _derive_key(secret: str) -> bytes:
    return hashlib.sha256(secret.encode("utf-8")).digest()


def encrypt_token(secret: str, plaintext: str) -> str:
    if not secret:
        raise ValueError("token encryption key is required")
    if plaintext == "":
        return ""
    aesgcm = AESGCM(_derive_key(secret))
    nonce = os.urandom(_NONCE_SIZE)
    ciphertext = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
    return base64.b64encode(nonce + ciphertext).decode("ascii")


def decrypt_token(secret: str, encoded: str) -> str:
    if not secret:
        raise ValueError("token encryption key is required")
    if encoded == "":
        return ""
    raw = base64.b64decode(encoded)
    if len(raw) < _NONCE_SIZE:
        raise ValueError("ciphertext too short")
    aesgcm = AESGCM(_derive_key(secret))
    nonce, ciphertext = raw[:_NONCE_SIZE], raw[_NONCE_SIZE:]
    return aesgcm.decrypt(nonce, ciphertext, None).decode("utf-8")
