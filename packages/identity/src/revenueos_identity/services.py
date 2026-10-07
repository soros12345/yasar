"""Identity provisioning services (used by API + operator CLI)."""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from revenueos_identity.models import (
    ROLES,
    TENANT_ACTIVE,
    USER_ACTIVE,
    Tenant,
    User,
)
from revenueos_identity.passwords import hash_password, password_strength_error


class IdentityError(ValueError):
    """Domain-level input error (never contains secrets)."""


def create_tenant(db: DbSession, slug: str, name: str) -> Tenant:
    slug = slug.strip().lower()
    if not slug or len(slug) > 63:
        raise IdentityError("invalid tenant slug")
    exists = db.execute(select(Tenant).where(Tenant.slug == slug)).scalar_one_or_none()
    if exists is not None:
        raise IdentityError("tenant slug already exists")
    tenant = Tenant(id=str(uuid.uuid4()), slug=slug, name=name.strip() or slug, status=TENANT_ACTIVE)
    db.add(tenant)
    db.flush()
    return tenant


def create_user(
    db: DbSession,
    tenant_id: str,
    email: str,
    display_name: str,
    password: str,
    role: str,
) -> User:
    email = email.strip().lower()
    if "@" not in email or len(email) > 254:
        raise IdentityError("invalid email")
    if role not in ROLES:
        raise IdentityError(f"role must be one of {ROLES}")
    strength = password_strength_error(password)
    if strength:
        raise IdentityError(strength)
    exists = db.execute(
        select(User).where(User.tenant_id == tenant_id, User.email == email)
    ).scalar_one_or_none()
    if exists is not None:
        raise IdentityError("user email already exists in tenant")
    user = User(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        email=email,
        display_name=display_name.strip() or email,
        password_hash=hash_password(password),
        role=role,
        status=USER_ACTIVE,
    )
    db.add(user)
    db.flush()
    return user


def get_user_by_email(db: DbSession, tenant_id: str, email: str) -> User | None:
    return db.execute(
        select(User).where(User.tenant_id == tenant_id, User.email == email.strip().lower())
    ).scalar_one_or_none()


def list_users(db: DbSession, tenant_id: str) -> list[User]:
    return list(
        db.execute(
            select(User).where(User.tenant_id == tenant_id).order_by(User.created_at)
        ).scalars()
    )


def get_tenant(db: DbSession, tenant_id: str) -> Tenant | None:
    return db.execute(select(Tenant).where(Tenant.id == tenant_id)).scalar_one_or_none()
