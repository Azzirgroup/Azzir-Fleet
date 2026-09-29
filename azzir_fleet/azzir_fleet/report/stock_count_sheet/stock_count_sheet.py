# Copyright (c) 2026, Azzir and contributors
# For license information, please see license.txt
"""Stock Count Sheet — a printable physical-count sheet.

Lists each item held in a warehouse with its Part Number, Description, Warehouse and the
system Balance, plus a BLANK 'Actual Quantity' column for the person to write in what they
physically count. Print it from the report view (the Actual Quantity column prints empty).

Scoped by Company / Warehouse / Item Group. By default only lines with stock are shown;
tick 'Include Zero Balance' to list everything (to catch stock that should be zero)."""

import frappe
from frappe import _
from frappe.utils import flt, strip_html


def execute(filters=None):
	filters = frappe._dict(filters or {})
	return get_columns(), get_rows(filters)


def get_columns():
	return [
		{"label": _("Part Number"), "fieldname": "part_number", "fieldtype": "Data", "width": 150},
		{"label": _("Description"), "fieldname": "description", "fieldtype": "Data", "width": 320},
		{"label": _("Warehouse"), "fieldname": "warehouse", "fieldtype": "Link", "options": "Warehouse", "width": 180},
		{"label": _("Balance (System)"), "fieldname": "balance_qty", "fieldtype": "Float", "width": 130},
		# Blank on purpose — the physical count is written here on the printout.
		{"label": _("Actual Quantity"), "fieldname": "actual_quantity", "fieldtype": "Data", "width": 140},
	]


def get_rows(filters):
	conds = ["w.is_group = 0", "w.disabled = 0", "i.is_stock_item = 1"]
	vals = {}
	if filters.get("company"):
		conds.append("w.company = %(company)s"); vals["company"] = filters.company
	if filters.get("warehouse"):
		conds.append("b.warehouse = %(warehouse)s"); vals["warehouse"] = filters.warehouse
	if filters.get("item_group"):
		conds.append("i.item_group = %(item_group)s"); vals["item_group"] = filters.item_group
	if not filters.get("include_zero"):
		conds.append("b.actual_qty != 0")

	rows = frappe.db.sql(
		"""select b.item_code, b.warehouse, b.actual_qty, i.item_name, i.description
		   from `tabBin` b
		   join `tabWarehouse` w on w.name = b.warehouse
		   join `tabItem` i on i.name = b.item_code
		   where {c}
		   order by b.warehouse, b.item_code""".format(c=" and ".join(conds)),
		vals,
		as_dict=True,
	)
	return [
		{
			"part_number": r.item_code,
			"description": (strip_html(r.description or "").strip() or r.item_name or ""),
			"warehouse": r.warehouse,
			"balance_qty": flt(r.actual_qty),
			"actual_quantity": "",  # blank for the physical count
		}
		for r in rows
	]
