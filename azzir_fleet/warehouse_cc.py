# Copyright (c) 2026, Azzir and contributors
# For license information, please see license.txt
"""Cost-center scoping for warehouse SELECTION.

Each Warehouse carries a cost center (`azzir_cost_center`). Each user is assigned
one or more cost centers via User Permission ("Cost Center"). A user may SEE every
warehouse's stock, but may only SELECT a warehouse whose cost center is one they
are assigned to. Nothing is hardcoded — it is driven entirely by the data.
"""

import frappe

COST_CENTER = "Cost Center"


def allowed_cost_centers(user: str | None = None) -> set | None:
	"""Cost centers the user is allowed to transact in, from their User Permissions.

	Returns None = NO restriction (Administrator, System Manager, or a user with no
	Cost Center user permission) -> may select any warehouse. A set = only those.
	"""
	user = user or frappe.session.user
	if user == "Administrator" or "System Manager" in frappe.get_roles(user):
		return None
	ccs = frappe.get_all(
		"User Permission",
		filters={"user": user, "allow": COST_CENTER},
		pluck="for_value",
	)
	return set(ccs) if ccs else None


def is_selectable(warehouse_cost_center: str | None, allowed: set | None) -> bool:
	"""Whether a warehouse (by its cost center) may be selected by the user."""
	if allowed is None:
		return True
	return bool(warehouse_cost_center) and warehouse_cost_center in allowed


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def warehouse_query(
	doctype: str, txt: str, searchfield: str, start: int, page_len: int, filters: dict | str | None
) -> list:
	"""Link-field query for warehouse fields: shows only warehouses the user is
	allowed to SELECT (attached to a cost center they're assigned; all if the user
	is unrestricted). Honours an incoming company / is_group filter."""
	allowed = allowed_cost_centers()
	filters = frappe.parse_json(filters) if isinstance(filters, str) else (filters or {})

	conds = ["w.disabled = 0", "(w.name like %(txt)s or w.warehouse_name like %(txt)s)"]
	vals = {"txt": "%%%s%%" % (txt or ""), "start": start, "page_len": page_len}
	if filters.get("company"):
		conds.append("w.company = %(company)s")
		vals["company"] = filters["company"]
	if filters.get("is_group") is not None:
		conds.append("w.is_group = %(is_group)s")
		vals["is_group"] = frappe.utils.cint(filters.get("is_group"))
	if allowed is not None:
		if not allowed:
			return []
		conds.append("w.azzir_cost_center in %(allowed)s")
		vals["allowed"] = tuple(allowed)

	return frappe.db.sql(
		"select w.name from `tabWarehouse` w where "
		+ " and ".join(conds)
		+ " order by w.name limit %(start)s, %(page_len)s",
		vals,
	)
