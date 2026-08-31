# Copyright (c) 2026, Azzir and contributors
# For license information, please see license.txt
"""Cost-center scoping for warehouse SELECTION.

Each Warehouse carries a cost center (`azzir_cost_center`). Each user is assigned
one or more cost centers via User Permission ("Cost Center"). A user may SEE every
warehouse's stock, but may only SELECT a warehouse whose cost center is one they
are assigned to. Nothing is hardcoded — it is driven entirely by the data.
"""

import frappe
from frappe.utils import flt

COST_CENTER = "Cost Center"


def _field_ready() -> bool:
	"""The azzir_cost_center field exists on Warehouse (migrate has run). Until then
	the feature is simply inactive so nothing errors."""
	try:
		return frappe.get_meta("Warehouse").has_field("azzir_cost_center")
	except Exception:
		return False


def allowed_cost_centers(user: str | None = None) -> set | None:
	"""Cost centers the user is allowed to transact in, from their User Permissions.

	Returns None = NO restriction (Administrator, System Manager, a user with no
	Cost Center user permission, or before the field is migrated) -> may select any
	warehouse. A set = only those.
	"""
	if not _field_ready():
		return None
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
def user_warehouse_for_item(item_code: str | None = None, company: str | None = None) -> str | None:
	"""A warehouse the user is allowed to select (attached to one of their assigned
	cost centers), used to auto-fill the row warehouse instead of the item's default.
	Prefers a warehouse that actually holds this item; else any of the user's. Returns
	None if the user is unrestricted (keep ERPNext's own default) or has none."""
	allowed = allowed_cost_centers()
	if not allowed:  # None (unrestricted) or empty -> don't override
		return None
	conds = ["w.disabled = 0", "w.is_group = 0", "w.azzir_cost_center in %(cc)s"]
	vals = {"cc": tuple(allowed)}
	if company:
		conds.append("w.company = %(co)s")
		vals["co"] = company
	warehouses = frappe.db.sql_list(
		"select w.name from `tabWarehouse` w where " + " and ".join(conds) + " order by w.name", vals
	)
	if not warehouses:
		return None
	if item_code:
		for w in warehouses:
			if flt(frappe.db.get_value("Bin", {"item_code": item_code, "warehouse": w}, "actual_qty")) > 0:
				return w
	return warehouses[0]


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
