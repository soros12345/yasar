"""Auth schema unit tests: credentials must never leak via repr/str/JSON."""

import pytest
from pydantic import ValidationError

from revenueos_schemas.auth import LoginRequest, UserCreateRequest

pytestmark = pytest.mark.unit

SECRET = "TopSecretPassword123!"


def test_login_request_hides_password_in_repr_and_json():
    req = LoginRequest(tenant_slug="acme", email="a@b.c", password=SECRET)
    assert SECRET not in repr(req)
    assert SECRET not in str(req)
    assert SECRET not in req.model_dump_json()
    assert req.password.get_secret_value() == SECRET


def test_user_create_request_hides_password():
    req = UserCreateRequest(
        email="a@b.c", display_name="A", password=SECRET, role="VIEWER"
    )
    assert SECRET not in repr(req)
    assert SECRET not in req.model_dump_json()


def test_login_request_requires_all_fields():
    with pytest.raises(ValidationError):
        LoginRequest(tenant_slug="acme", email="a@b.c")  # type: ignore[call-arg]
