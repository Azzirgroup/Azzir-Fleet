# Copyright (c) 2026, Azzir and contributors
# For license information, please see license.txt
"""Owner-scoping for procurement documents on the desk.

A procurement user only sees the documents they created (list views, reports,
and opening a doc by URL). Give a user the 'Azzir Procurement Overseer' role
(or Purchase Manager / System Manager) and they see everyone's."""

import frappe

# Doctypes scoped to their creator for ordinary procurement users.
PROCUREMENT_DOCTYPES = (
	"Material Request",
	"Request for Quotation",
	"Supplier Quotation",
	"Purchase Order",
	"Purchase Receipt",
	"Purchase Invoice",
)

SEE_ALL_ROLES = {"Azzir Procurement Overseer", "Purchase Manager", "System Manager"}


def _can_see_all() -> bool:
	return bool(set(frappe.get_roles()) & SEE_ALL_ROLES)


def get_permission_query_conditions(user: str | None = None) -> str:
	"""Restrict list views / reports to the current user's own records, unless
	they hold an overseer role. Returned as a raw SQL condition string."""
	if _can_see_all():
		return ""
	user = user or frappe.session.user
	return "`owner` = {user}".format(user=frappe.db.escape(user))


def has_permission(doc, ptype: str | None = None, user: str | None = None) -> bool:
	"""Block opening someone else's procurement document by URL. Overseers pass;
	otherwise only the creator may read it. Returning True defers other perm
	checks to Frappe's standard role permissions."""
	if _can_see_all():
		return True
	user = user or frappe.session.user
	return (doc.owner == user) if getattr(doc, "owner", None) else True
