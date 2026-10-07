"""Password hashing — stdlib PBKDF2-HMAC-SHA256 (no third-party crypto dep).

Format: pbkdf2_sha256$<iterations>$<salt_hex>$<hash_hex>
Upgrade path to Argon2id requires an ADR + dependency vetting; the format
string keeps the algorithm explicit and migratable.
"""

import hashlib
import hmac
import secrets

from revenueos_shared.config import get_settings

ALGORITHM = "pbkdf2_sha256"
DEFAULT_ITERATIONS = 600_000  # OWASP recommendation for PBKDF2-HMAC-SHA256
SALT_BYTES = 16
MIN_PASSWORD_LENGTH = 12


def _iterations() -> int:
    try:
        value = get_settings().pbkdf2_iterations
        return int(value) if value else DEFAULT_ITERATIONS
    except Exception:
        return DEFAULT_ITERATIONS


def hash_password(password: str, iterations: int | None = None) -> str:
    if len(password) < MIN_PASSWORD_LENGTH:
        raise ValueError(f"password must be at least {MIN_PASSWORD_LENGTH} characters")
    iters = iterations if iterations is not None else _iterations()
    salt = secrets.token_bytes(SALT_BYTES)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iters)
    return f"{ALGORITHM}${iters}${salt.hex()}${digest.hex()}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, iters_s, salt_hex, expected_hex = encoded.split("$", 3)
        if algorithm != ALGORITHM:
            return False
        iters = int(iters_s)
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(expected_hex)
    except (ValueError, AttributeError):
        return False
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iters)
    return hmac.compare_digest(digest, expected)


def password_strength_error(password: str) -> str | None:
    if len(password) < MIN_PASSWORD_LENGTH:
        return f"password must be at least {MIN_PASSWORD_LENGTH} characters"
    return None
