from __future__ import annotations

import hashlib
import random
import string


def generate_password_hash(plaintext: str) -> str:
    """Generate a gnuworld-compatible password hash.

    Format: <8-char-salt><32-char-md5-hex>
    Algorithm: MD5(salt + plaintext)
    """
    salt_chars = string.ascii_letters + string.digits
    salt = "".join(random.choice(salt_chars) for _ in range(8))
    md5_hash = hashlib.md5((salt + plaintext).encode()).hexdigest()
    return salt + md5_hash


def verify_password(plaintext: str, stored_hash: str) -> bool:
    """Verify a plaintext password against a stored gnuworld hash."""
    salt = stored_hash[:8]
    expected = hashlib.md5((salt + plaintext).encode()).hexdigest()
    return stored_hash[8:] == expected
