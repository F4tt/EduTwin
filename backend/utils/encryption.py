"""
Encryption utilities for PII (Personally Identifiable Information) fields.
Uses AWS KMS for production or Fernet for local development.
"""

import os
from cryptography.fernet import Fernet


# Generate or load encryption key
ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY")

if not ENCRYPTION_KEY:
    # For local development, use a default key (DO NOT use in production)
    ENCRYPTION_KEY = Fernet.generate_key().decode()
    print("[ENCRYPTION] Warning: Using auto-generated encryption key. Set ENCRYPTION_KEY env var for production.")

fernet = Fernet(ENCRYPTION_KEY.encode() if isinstance(ENCRYPTION_KEY, str) else ENCRYPTION_KEY)


def encrypt_field(plaintext: str) -> str:
    """Encrypt a plaintext string."""
    if not plaintext:
        return plaintext
    encrypted_bytes = fernet.encrypt(plaintext.encode())
    return encrypted_bytes.decode()


def decrypt_field(encrypted: str) -> str:
    """Decrypt an encrypted string."""
    if not encrypted:
        return encrypted
    decrypted_bytes = fernet.decrypt(encrypted.encode())
    return decrypted_bytes.decode()
