"""Auth primitives: password hashing, session cookies, and Skills pull keys.

No third-party crypto dependency: we use PBKDF2-HMAC-SHA256 from the standard
library (well-understood, tunable, no wheels to trust). Session tokens and pull
keys are random and stored only as hashes, so a database leak does not hand out
live credentials.
"""
from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import time

PBKDF2_ROUNDS = 240_000
SESSION_TTL_SECONDS = 14 * 24 * 3600


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, PBKDF2_ROUNDS)
    return f"pbkdf2${PBKDF2_ROUNDS}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, rounds, salt_hex, digest_hex = stored.split("$")
        if scheme != "pbkdf2":
            return False
        digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt_hex), int(rounds))
        return hmac.compare_digest(digest.hex(), digest_hex)
    except (ValueError, TypeError):
        return False


def new_session_token() -> str:
    return secrets.token_urlsafe(32)


def token_hash(token: str) -> str:
    """Stable hash for storage. Not salted: tokens are high-entropy random, and
    we must be able to look them up by value."""
    return hashlib.sha256(token.encode()).hexdigest()


def new_pull_key() -> str:
    """A pull key is shown to the user once, then stored only as a hash.

    Prefix is a hint so a leaked key is recognizable in logs / secret scanners:
    `aiops-sk-...`.
    """
    return "aiops-sk-" + secrets.token_urlsafe(32)


def now() -> float:
    return time.time()
