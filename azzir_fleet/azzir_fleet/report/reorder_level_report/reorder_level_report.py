# Copyright (c) 2026, Azzir and contributors
# For license information, please see license.txt
"""Reorder Level Report — items whose physical stock has fallen to/below their
reorder level, with the item's minimum & maximum order quantities and reorder
qty. Once a Purchase Invoice is raised for an item (draft or submitted, within
the "Reordered Within" window) it drops off the report — you've acted on it.

Reorder levels come from each Item's per-warehouse Reorder Levels table
(Item Reorder), so an item can appear once per warehouse that is short."""

import frappe
from frappe import _
from frappe.utils import add_days, flt, today


def execute(filters=None):
	filters = frappe._dict(filters or {})
	return get_columns(), get_rows(filters)


def get_rows(filters):
	# 1) Reorder levels configured per item / warehouse.
	conds = ["ir.warehouse_reorder_level > 0", "b_wh.disabled = 0"]
	vals = {}
	if filters.get("warehouse"):
		conds.append("ir.warehouse = %(warehouse)s")
		vals["warehouse"] = filters.warehouse
	if filters.get("company"):
		conds.append("b_wh.company = %(company)s")
		vals["company"] = filters.company

	reorder = frappe.db.sql(
		"""
		select ir.parent as item_code, ir.warehouse,
		       ir.warehouse_reorder_level as reorder_level,
		       ir.warehouse_reorder_qty as reorder_qty,
		       b_wh.company as company
		from `tabItem Reorder` ir
		join `tabWarehouse` b_wh on b_wh.name = ir.warehouse
		where {conds}
		""".format(conds=" and ".join(conds)),
		vals,
		as_dict=True,
	)
	if not reorder:
		return []

	items = list({r.item_code for r in reorder})

	# 2) Item master figures (min/max order qty, name, disabled).
	meta = {
		i.name: i
		for i in frappe.get_all(
			"Item",
			filters={"name": ["in", items]},
			fields=["name", "item_name", "disabled", "min_order_qty", "max_order_qty"],
		)
	}

	# 3) Current physical stock per (item, warehouse).
	bins = {
		(b.item_code, b.warehouse): flt(b.actual_qty)
		for b in frappe.get_all(
			"Bin",
			filters={"item_code": ["in", items]},
			fields=["item_code", "warehouse", "actual_qty"],
		)
	}

	# 4) Items already reordered — a Purchase Invoice raised for them removes
	#    them from the list. 0 days = any open Purchase Invoice, ever.
	reordered = set()
	if not filters.get("show_reordered"):
		days = int(filters.get("reordered_within_days") or 0)
		pi_conds = ["pi.docstatus in (0, 1)"]
		pi_vals = {"items": items}
		if days > 0:
			pi_conds.append("pi.posting_date >= %(cutoff)s")
			pi_vals["cutoff"] = add_days(today(), -days)
		reordered = {
			r[0]
			for r in frappe.db.sql(
				"""
				select distinct pii.item_code
				from `tabPurchase Invoice Item` pii
				join `tabPurchase Invoice` pi on pi.name = pii.parent
				where pii.item_code in %(items)s and {conds}
				""".format(conds=" and ".join(pi_conds)),
				pi_vals,
			)
		}

	# 5) Economy stock = quantity already on submitted Purchase Orders that has NOT
	#    yet been received (no Purchase Receipt / stock-updating Purchase Invoice)
	#    — i.e. on order / incoming. Per item.
	economy = {}
	for e in frappe.db.sql(
		"""
		select poi.item_code, sum(greatest(0, poi.qty - poi.received_qty)) as on_order
		from `tabPurchase Order Item` poi
		join `tabPurchase Order` po on po.name = poi.parent
		where po.docstatus = 1 and po.status not in ('Closed', 'Completed', 'Delivered')
		  and poi.item_code in %(items)s
		group by poi.item_code
		""",
		{"items": items},
		as_dict=True,
	):
		economy[e.item_code] = flt(e.on_order)

	rows = []
	for r in reorder:
		im = meta.get(r.item_code)
		if not im or im.disabled:
			continue
		if r.item_code in reordered:
			continue
		actual = bins.get((r.item_code, r.warehouse), 0.0)
		if actual > flt(r.reorder_level):
			continue  # not below the reorder point
		rows.append(
			{
				"item_code": r.item_code,
				"item_name": im.item_name,
				"warehouse": r.warehouse,
				"company": r.company,
				"min_order_qty": flt(im.min_order_qty),
				"max_order_qty": flt(im.max_order_qty),
				"reorder_level": flt(r.reorder_level),
				"reorder_qty": flt(r.reorder_qty),
				"actual_qty": actual,
				"economy_stock": economy.get(r.item_code, 0.0),
				"shortage": flt(r.reorder_level) - actual,
			}
		)
	rows.sort(key=lambda x: x["shortage"], reverse=True)
	return rows


def get_columns():
	return [
		{"label": _("Item Code"), "fieldname": "item_code", "fieldtype": "Link", "options": "Item", "width": 180},
		{"label": _("Item Name"), "fieldname": "item_name", "fieldtype": "Data", "width": 200},
		{"label": _("Warehouse"), "fieldname": "warehouse", "fieldtype": "Link", "options": "Warehouse", "width": 160},
		{"label": _("Min Order Qty"), "fieldname": "min_order_qty", "fieldtype": "Float", "width": 110},
		{"label": _("Max Order Qty"), "fieldname": "max_order_qty", "fieldtype": "Float", "width": 110},
		{"label": _("Reorder Level"), "fieldname": "reorder_level", "fieldtype": "Float", "width": 110},
		{"label": _("Reorder Qty"), "fieldname": "reorder_qty", "fieldtype": "Float", "width": 110},
		{"label": _("Actual Qty"), "fieldname": "actual_qty", "fieldtype": "Float", "width": 110},
		{"label": _("Economy Stock"), "fieldname": "economy_stock", "fieldtype": "Float", "width": 120},
		{"label": _("Shortage"), "fieldname": "shortage", "fieldtype": "Float", "width": 110},
	]
