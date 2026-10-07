"""Password hashing unit tests (V1A-1)."""

import pytest

from revenueos_identity.passwords import (
    ALGORITHM,
    MIN_PASSWORD_LENGTH,
    hash_password,
    password_strength_error,
    verify_password,
)

pytestmark = pytest.mark.unit


def test_hash_and_verify_roundtrip():
    encoded = hash_password("correct horse battery staple 7", iterations=10_000)
    assert encoded.startswith(f"{ALGORITHM}$10000$")
    assert verify_password("correct horse battery staple 7", encoded) is True


def test_wrong_password_rejected():
    encoded = hash_password("correct horse battery staple 7", iterations=10_000)
    assert verify_password("correct horse battery staple 8", encoded) is False
    assert verify_password("", encoded) is False


def test_short_password_rejected_by_policy():
    with pytest.raises(ValueError):
        hash_password("short", iterations=10_000)
    assert password_strength_error("short") is not None
    assert password_strength_error("long-enough-password") is None


def test_malformed_encoded_value_fails_closed():
    assert verify_password("anything", "not-a-valid-hash") is False
    assert verify_password("anything", "md5$1$ab$cd") is False
    assert verify_password("anything", "") is False


def test_salts_are_unique():
    a = hash_password("same password here!!", iterations=10_000)
    b = hash_password("same password here!!", iterations=10_000)
    assert a != b, "salt must randomize the hash"
