"""Permission catalogue and the roles every installation starts with."""

PERMISSIONS: dict[str, tuple[str, str]] = {
    # key: (resource, description)
    "users:read": ("users", "View customer and provider accounts"),
    "users:ban": ("users", "Ban and unban accounts"),
    "admins:manage": ("users", "Create and deactivate admin users"),
    "disputes:read": ("disputes", "View disputes and their messages"),
    "disputes:resolve": ("disputes", "Review, escalate and resolve disputes"),
    "finance:read": ("finance", "View settlements and revenue reports"),
    "audit:read": ("audit", "View the audit log"),
    "monitoring:read": ("monitoring", "View service health and metrics"),
    "config:write": ("config", "Change system configuration"),
    "roles:manage": ("access", "Create roles and change their permissions"),
}

# name -> (description, permissions). The admin role always has every permission.
DEFAULT_ROLES: dict[str, tuple[str, list[str]]] = {
    "admin": ("Full access to the admin dashboard", sorted(PERMISSIONS)),
    "support": (
        "Customer support: accounts and disputes",
        ["users:read", "users:ban", "disputes:read", "disputes:resolve", "audit:read"],
    ),
    "finance": ("Finance team: payouts and revenue", ["finance:read", "disputes:read", "audit:read"]),
    "viewer": (
        "Read-only access",
        ["users:read", "disputes:read", "finance:read", "audit:read", "monitoring:read"],
    ),
}

PROTECTED_ROLES = frozenset({"admin"})
