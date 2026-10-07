#!/usr/bin/env python3
"""Provision a tenant with its TENANT_ADMIN user (V1A-1).

Password source (in order): env CREATE_TENANT_ADMIN_PASSWORD, then stdin.
The password is NEVER accepted as an argument and NEVER printed.

Usage:
  CREATE_TENANT_ADMIN_PASSWORD=... scripts/create-tenant.py \
      --slug acme --name "Acme Corp" --email admin@acme.example --display-name "Acme Admin"
  scripts/create-tenant.py --repair --slug acme --email admin@acme.example
"""

import argparse
import os
import sys

from revenueos_authorization.enforcer import bind_role, ensure_default_policies
from revenueos_identity.models import ROLE_TENANT_ADMIN, Tenant, User
from revenueos_identity.services import IdentityError, create_tenant, create_user
from revenueos_shared.db import session_scope
from sqlalchemy import select


def _read_password() -> str:
    password = os.environ.get("CREATE_TENANT_ADMIN_PASSWORD")
    if not password:
        if sys.stdin.isatty():
            import getpass

            password = getpass.getpass("Tenant admin password (never echoed): ")
        else:
            password = sys.stdin.readline().rstrip("\n")
    if not password:
        raise SystemExit("ERROR: no password provided (env CREATE_TENANT_ADMIN_PASSWORD or stdin)")
    return password


def main() -> int:
    parser = argparse.ArgumentParser(description="Provision a RevenueOS tenant + admin")
    parser.add_argument("--slug", required=True)
    parser.add_argument("--name", default="")
    parser.add_argument("--email", default="")
    parser.add_argument("--display-name", default="")
    parser.add_argument("--repair", action="store_true",
                        help="existing tenant: re-ensure policies and admin binding only")
    args = parser.parse_args()

    if args.repair:
        with session_scope() as db:
            tenant = db.execute(select(Tenant).where(Tenant.slug == args.slug.strip().lower())).scalar_one_or_none()
            if tenant is None:
                print(f"ERROR: tenant '{args.slug}' not found")
                return 1
            admin = db.execute(
                select(User).where(User.tenant_id == tenant.id, User.email == args.email.strip().lower())
            ).scalar_one_or_none()
            if admin is None:
                print(f"ERROR: admin user '{args.email}' not found in tenant")
                return 1
            tenant_id, admin_id, admin_email = tenant.id, admin.id, admin.email
        ensure_default_policies(tenant_id)
        bind_role(admin_id, ROLE_TENANT_ADMIN, tenant_id)
        print(f"repaired tenant={args.slug} tenant_id={tenant_id} admin_user_id={admin_id} admin_email={admin_email}")
        return 0

    if not args.email:
        print("ERROR: --email required (unless --repair)")
        return 2
    password = _read_password()

    with session_scope() as db:
        try:
            tenant = create_tenant(db, args.slug, args.name or args.slug)
            user = create_user(
                db,
                tenant_id=tenant.id,
                email=args.email,
                display_name=args.display_name or args.email,
                password=password,
                role=ROLE_TENANT_ADMIN,
            )
        except IdentityError as exc:
            print(f"ERROR: {exc}")
            return 1
        tenant_id, admin_id, admin_email = tenant.id, user.id, user.email

    # Policies/bindings commit after the identity transaction succeeded
    # (idempotent; safe to re-run with --repair on partial failure).
    ensure_default_policies(tenant_id)
    bind_role(admin_id, ROLE_TENANT_ADMIN, tenant_id)

    print(
        f"created tenant={args.slug} tenant_id={tenant_id} "
        f"admin_user_id={admin_id} admin_email={admin_email}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
