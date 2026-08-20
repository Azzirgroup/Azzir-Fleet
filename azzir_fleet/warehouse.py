# Copyright (c) 2026, Azzir and contributors
# For license information, please see license.txt
"""Warehouse pickers for the group-warehouse sales flow.

Sales documents (Quotation, Sales Invoice) — which do NOT move stock — only let
you pick a GROUP (parent) warehouse, so sales people see a region/branch, never
the actual bin. The Delivery Note (which DOES move stock) then restricts each
line to the LEAF warehouses under the group that was chosen on the Sales Invoice.
"""

import frappe
from frappe import _


@frappe.whitelist()
def group_warehouses(
	doctype: str,
	txt: str,
	searchfield: str,
	start: int,
	page_len: int,
	filters: dict,
) -> list:
	"""Only group (parent) warehouses — for Quotation / Sales Invoice pickers."""
	filters = filters or {}
	like = "%%%s%%" % (txt or "")
	conds = "is_group = 1 and disabled = 0 and (name like %(t)s or warehouse_name like %(t)s)"
	vals = {"t": like, "s": start, "p": page_len}
	if filters.get("company"):
		conds += " and company = %(c)s"
		vals["c"] = filters["company"]
	return frappe.db.sql(
		"select name, warehouse_name from `tabWarehouse` where "
		+ conds
		+ " order by name limit %(s)s, %(p)s",
		vals,
	)


def _group_of(filters):
	"""Resolve the group warehouse from an explicit `group`, or from the source
	Sales Invoice line (`si_item`)."""
	group = filters.get("group")
	if not group and filters.get("si_item"):
		group = frappe.db.get_value("Sales Invoice Item", filters["si_item"], "warehouse")
	return group


@frappe.whitelist()
def leaves_under(
	doctype: str,
	txt: str,
	searchfield: str,
	start: int,
	page_len: int,
	filters: dict,
) -> list:
	"""Leaf (non-group) warehouses under a group — for the Delivery Note. With no
	group in context, returns all leaves (a plain, non-sourced delivery note)."""
	filters = filters or {}
	group = _group_of(filters)
	like = "%%%s%%" % (txt or "")
	conds = "w.is_group = 0 and w.disabled = 0 and (w.name like %(t)s or w.warehouse_name like %(t)s)"
	vals = {"t": like, "s": start, "p": page_len}
	if filters.get("company"):
		conds += " and w.company = %(c)s"
		vals["c"] = filters["company"]
	if group:
		bounds = frappe.db.get_value("Warehouse", group, ["lft", "rgt", "is_group"])
		if bounds and bounds[2]:  # a real group -> its descendant leaves
			conds += " and w.lft > %(lft)s and w.rgt < %(rgt)s"
			vals["lft"], vals["rgt"] = bounds[0], bounds[1]
		elif bounds:  # someone stored a leaf on the SI -> just that leaf
			conds += " and w.name = %(g)s"
			vals["g"] = group
	return frappe.db.sql(
		"select w.name, w.warehouse_name from `tabWarehouse` w where "
		+ conds
		+ " order by w.name limit %(s)s, %(p)s",
		vals,
	)


def leaves_of(group):
	"""List of leaf warehouse names under a group (empty if it isn't a group)."""
	bounds = frappe.db.get_value("Warehouse", group, ["lft", "rgt", "is_group"], as_dict=True)
	if not bounds or not bounds.is_group:
		return []
	return frappe.get_all(
		"Warehouse",
		filters={"is_group": 0, "disabled": 0, "lft": [">", bounds.lft], "rgt": ["<", bounds.rgt]},
		pluck="name",
		order_by="name",
	)


@frappe.whitelist()
def resolve_delivery_warehouses(names: list | str) -> dict:
	"""For the given warehouse names, return {group: replacement} — a group with a
	single leaf maps to that leaf (auto-fill), any other group maps to "" (the user
	must pick a bin). Leaf warehouses are omitted (left untouched). Used by the
	Delivery Note form to drop the region carried over from a Sales Invoice."""
	if isinstance(names, str):
		names = frappe.parse_json(names)
	result = {}
	for wh in set(names or []):
		if not wh or not frappe.db.get_value("Warehouse", wh, "is_group"):
			continue
		leaves = leaves_of(wh)
		result[wh] = leaves[0] if len(leaves) == 1 else ""
	return result


def enforce_group_warehouse(doc, method=None):
	"""Quotation / Sales Invoice are region-only: drop any leaf (bin) warehouse —
	including ERPNext's auto-filled item default — so only a chosen group (region)
	is ever stored. The field stays empty until the user picks a region."""
	for row in doc.get("items") or []:
		wh = row.get("warehouse")
		if wh and not frappe.db.get_value("Warehouse", wh, "is_group"):
			row.warehouse = None
	if doc.get("set_warehouse") and not frappe.db.get_value("Warehouse", doc.set_warehouse, "is_group"):
		doc.set_warehouse = None


def resolve_child_warehouse(doc, method=None):
	"""Delivery Note before_validate: a warehouse copied from a Sales Invoice may be
	a GROUP (sales picks the region). Group warehouses hold no stock, so each line
	must drop to a leaf — auto-filled when the group has exactly one leaf, otherwise
	the user is asked to pick the specific bin (the field's picker already lists
	only leaves under that region)."""
	pending = []
	for idx, row in enumerate(doc.get("items") or [], start=1):
		wh = row.get("warehouse")
		if not wh or not frappe.db.get_value("Warehouse", wh, "is_group"):
			continue
		leaves = leaves_of(wh)
		if len(leaves) == 1:
			row.warehouse = leaves[0]
		else:
			pending.append((idx, row.get("item_code"), wh))

	# Parent convenience field, if it points at a group.
	if doc.get("set_warehouse") and frappe.db.get_value("Warehouse", doc.set_warehouse, "is_group"):
		doc.set_warehouse = None

	if pending:
		lines = "<br>".join(
			_("Row #{0}: choose a bin under region {1} for item {2}").format(
				idx, frappe.bold(wh), frappe.bold(code or "")
			)
			for (idx, code, wh) in pending
		)
		frappe.throw(lines, title=_("Choose a Delivery Bin"))
