"""Role -> permission map. Server-side checks use these; the frontend mirrors them cosmetically."""

ALL = "*"

ACCOUNTANT = {
    "masters.read",
    "masters.write",
    "purchase.create",
    "purchase.update",
    "challan.create",
    "challan.update",
    "rental.create",
    "rental.update",
    "payment.create",
    "payment.update",
    "expense.create",
    "expense.update",
    "attendance.write",
    "wages.settle",
    "stock.view",
    "stock.count",
    "invoice.create",
    "dashboard.view",
    "report.khata",
    "report.cashbook",
    "report.daybook",
    "report.stock",
    "report.labour_khata",
}

ROLE_PERMISSIONS: dict[str, set[str]] = {
    "admin": {ALL},
    "accountant": ACCOUNTANT,
    # Phase 3 roles exist from day 1 so they can be switched on without a redesign.
    "driver": {"trip.create_own", "diesel.create_own", "statement.view_own"},
    "customer": {"khata.view_own", "bill.view_own"},
}

ROLES = tuple(ROLE_PERMISSIONS)
# Roles that may sign in to the portal in phase 1.
ACTIVE_PORTAL_ROLES = {"admin", "accountant"}


def permissions_for(role: str) -> set[str]:
    return ROLE_PERMISSIONS.get(role, set())


def has_permission(role: str, perm: str) -> bool:
    perms = permissions_for(role)
    return ALL in perms or perm in perms
