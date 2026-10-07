"""Auth/identity contract schemas (V1A-1). Passwords are SecretStr so their
values never appear in repr/str/logs/errors."""

from datetime import datetime

from pydantic import BaseModel, SecretStr


class LoginRequest(BaseModel):
    tenant_slug: str
    email: str
    password: SecretStr


class UserCreateRequest(BaseModel):
    email: str
    display_name: str
    password: SecretStr
    role: str


class UserOut(BaseModel):
    id: str
    email: str
    display_name: str
    role: str
    status: str
    tenant_id: str


class TenantOut(BaseModel):
    id: str
    slug: str
    name: str
    status: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_at: datetime
    user: UserOut
    tenant: TenantOut


class LogoutResponse(BaseModel):
    status: str = "revoked"


class SessionOut(BaseModel):
    id: str
    user_id: str
    created_at: datetime
    expires_at: datetime
    revoked: bool


class MeResponse(BaseModel):
    user: UserOut
    tenant: TenantOut
    session_id: str
    session_expires_at: datetime
    permissions: dict[str, list[str]]
