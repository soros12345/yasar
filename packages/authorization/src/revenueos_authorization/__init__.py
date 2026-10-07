"""RevenueOS authorization package (V1A-1).

Casbin is the authorization engine; RevenueOS owns the model, the policy
content, and the persistence adapter. Keycloak (V1C) will own authentication
identity — Casbin never replaces identity, and identity never replaces
RevenueOS business authorization.
"""

__version__ = "0.1.0"
