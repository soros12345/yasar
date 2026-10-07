"""Casbin enforcer factory + RevenueOS policy content.

V1A-1 authorization rules (domain = tenant id):

  TENANT_ADMIN  user:read/write, tenant:read, session:read  (obj "*" / act "*")
  OPERATOR      user:read, tenant:read, session:read
  VIEWER        user:read, tenant:read

The enforcer is built per decision (correctness first): policies are loaded
from PostgreSQL through the RevenueOS adapter. Policy-cache performance
work belongs to a later packet with explicit invalidation.
"""

from importlib import resources

from casbin import Enforcer

from revenueos_authorization.adapter import SQLAlchemyAdapter

# Objects and actions known to V1A-1 (extend per phase packet, never silently)
OBJECTS = ("tenant", "user", "session")
ACTIONS = ("read", "write")

DEFAULT_ROLE_POLICIES: tuple[tuple[str, str, str, str], ...] = (
    ("TENANT_ADMIN", "*", "*", "*"),      # (role, domain-placeholder, obj, act) — domain filled at provision
    ("OPERATOR", "*", "user", "read"),
    ("OPERATOR", "*", "tenant", "read"),
    ("OPERATOR", "*", "session", "read"),
    ("VIEWER", "*", "user", "read"),
    ("VIEWER", "*", "tenant", "read"),
)


def _model_path() -> str:
    return str(resources.files("revenueos_authorization").joinpath("model.conf"))


def _resolve_session_factory(session_factory):
    """Accept: None (use shared factory), lru-cached getter, or a sessionmaker."""
    if session_factory is None:
        from revenueos_shared.db import get_session_factory

        return get_session_factory()
    if hasattr(session_factory, "cache_clear"):  # lru_cache-wrapped getter
        return session_factory()
    return session_factory


def make_enforcer(session_factory=None) -> Enforcer:
    factory = _resolve_session_factory(session_factory)
    adapter = SQLAlchemyAdapter(factory)
    return Enforcer(_model_path(), adapter)


def can(user_id: str, tenant_id: str, obj: str, act: str) -> bool:
    """One authorization decision. Domain (tenant) is always explicit."""
    enforcer = make_enforcer()
    return bool(enforcer.enforce(user_id, tenant_id, obj, act))


def ensure_default_policies(tenant_id: str, session_factory=None) -> None:
    """Idempotently seed role policies for a tenant (persisted via adapter)."""
    enforcer = make_enforcer(session_factory)
    for role, _placeholder, obj, act in DEFAULT_ROLE_POLICIES:
        rule = (role, tenant_id, obj, act)
        if not enforcer.has_policy(*rule):
            enforcer.add_policy(*rule)


def bind_role(user_id: str, role: str, tenant_id: str, session_factory=None) -> None:
    """Bind a user to a role inside a tenant domain (g rule, persisted)."""
    enforcer = make_enforcer(session_factory)
    roles = enforcer.get_roles_for_user_in_domain(user_id, tenant_id) or []
    if role not in roles:
        enforcer.add_role_for_user_in_domain(user_id, role, tenant_id)


def permissions_matrix(user_id: str, tenant_id: str, session_factory=None) -> dict[str, list[str]]:
    """Explicit allow-matrix for display on /auth/me."""
    enforcer = make_enforcer(session_factory)
    matrix: dict[str, list[str]] = {}
    for obj in OBJECTS:
        allowed = [act for act in ACTIONS if enforcer.enforce(user_id, tenant_id, obj, act)]
        if allowed:
            matrix[obj] = allowed
    return matrix
