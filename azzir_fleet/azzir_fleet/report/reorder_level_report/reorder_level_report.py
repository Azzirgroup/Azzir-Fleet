# Copyright (c) 2026, Azzir and contributors
# For license information, please see license.txt
"""Reorder Level Report — items whose stock is OUT OF BAND: below the item's
Minimum Order Qty (understocked → reorder) or above its Maximum Order Qty
(overstocked). Driven by the item's Min/Max Order Qty (no per-warehouse reorder
level needed). Shows Economy Stock (already on order, not yet received) and the
reorder level for reference. A Below-Minimum item drops off once a Purchase
Invoice is raised for it (within the Reordered-Within window)."""

import frappe
from frappe import _
from frappe.utils import add_days, flt, today


def execute(filters=None):
	filters = frappe._dict(filters or {})
	return get_columns(), get_rows(filters)


def get_rows(filters):
	# 1) Items that have a Minimum or Maximum Order Qty configured.
	items = frappe.get_all(
		"Item",
		filters={"disabled": 0, "is_stock_item": 1},
		or_filters={"min_order_qty": [">", 0], "max_order_qty": [">", 0]},
		fields=["name", "item_name", "min_order_qty", "max_order_qty"],
	)
	if not items:
		return []
	codes = [i.name for i in items]

	# 2) Stock per item, scoped to the chosen warehouse (else the company, else all).
	conds = ["b.item_code in %(codes)s"]
	vals = {"codes": tuple(codes)}
	wh_join = ""
	if filters.get("warehouse"):
		conds.append("b.warehouse = %(wh)s")
		vals["wh"] = filters.warehouse
	elif filters.get("company"):
		wh_join = "join `tabWarehouse` w on w.name = b.warehouse"
		conds.append("w.company = %(co)s")
		vals["co"] = filters.company
	stock = {}
	for r in frappe.db.sql(
		"select b.item_code, sum(b.actual_qty) q from `tabBin` b {j} where {c} group by b.item_code".format(
			j=wh_join, c=" and ".join(conds)
		),
		vals,
		as_dict=True,
	):
		stock[r.item_code] = flt(r.q)

	# 3) Economy stock = quantity on submitted Purchase Orders not yet received.
	economy = {}
	for e in frappe.db.sql(
		"""
		select poi.item_code, sum(greatest(0, poi.qty - poi.received_qty)) as on_order
		from `tabPurchase Order Item` poi
		join `tabPurchase Order` po on po.name = poi.parent
		where po.docstatus = 1 and po.status not in ('Closed', 'Completed', 'Delivered')
		  and poi.item_code in %(codes)s
		group by poi.item_code
		""",
		{"codes": tuple(codes)},
		as_dict=True,
	):
		economy[e.item_code] = flt(e.on_order)

	# 4) Reorder level (reference only) — highest configured across the item's warehouses.
	reorder_level = {}
	for r in frappe.db.sql(
		"""select parent as item_code, max(warehouse_reorder_level) lvl
		   from `tabItem Reorder` where parent in %(codes)s group by parent""",
		{"codes": tuple(codes)},
		as_dict=True,
	):
		reorder_level[r.item_code] = flt(r.lvl)

	# 5) Below-Minimum items drop off once a Purchase Invoice has been raised for
	#    them (they've been reordered). 0 days = any open Purchase Invoice, ever.
	reordered = set()
	if not filters.get("show_reordered"):
		days = int(filters.get("reordered_within_days") or 0)
		pi_conds = ["pi.docstatus in (0, 1)"]
		pi_vals = {"codes": tuple(codes)}
		if days > 0:
			pi_conds.append("pi.posting_date >= %(cutoff)s")
			pi_vals["cutoff"] = add_days(today(), -days)
		reordered = {
			r[0]
			for r in frappe.db.sql(
				"""select distinct pii.item_code from `tabPurchase Invoice Item` pii
				   join `tabPurchase Invoice` pi on pi.name = pii.parent
				   where pii.item_code in %(codes)s and {c}""".format(c=" and ".join(pi_conds)),
				pi_vals,
			)
		}

	wh_label = filters.get("warehouse") or (_("All — {0}").format(filters.company) if filters.get("company") else _("All Warehouses"))
	rows = []
	for im in items:
		mn, mx = flt(im.min_order_qty), flt(im.max_order_qty)
		actual = flt(stock.get(im.name, 0.0))
		below = mn > 0 and actual < mn
		above = mx > 0 and actual > mx
		if not (below or above):
			continue  # within the [min, max] band — fine
		if below and not above and im.name in reordered:
			continue  # already reordered
		rows.append(
			{
				"item_code": im.name,
				"item_name": im.item_name,
				"warehouse": wh_label,
				"min_order_qty": mn,
				"max_order_qty": mx,
				"reorder_level": reorder_level.get(im.name, 0.0),
				"actual_qty": actual,
				"economy_stock": economy.get(im.name, 0.0),
				"status": _("Below Minimum") if below else _("Above Maximum"),
				"variance": (mn - actual) if below else (actual - mx),
			}
		)
	# Below-minimum (understocked) first, biggest gap on top.
	rows.sort(key=lambda x: (x["status"] != _("Below Minimum"), -x["variance"]))
	return rows


def get_columns():
	return [
		{"label": _("Item Code"), "fieldname": "item_code", "fieldtype": "Link", "options": "Item", "width": 180},
		{"label": _("Item Name"), "fieldname": "item_name", "fieldtype": "Data", "width": 200},
		{"label": _("Warehouse"), "fieldname": "warehouse", "fieldtype": "Data", "width": 150},
		{"label": _("Min Order Qty"), "fieldname": "min_order_qty", "fieldtype": "Float", "width": 110},
		{"label": _("Max Order Qty"), "fieldname": "max_order_qty", "fieldtype": "Float", "width": 110},
		{"label": _("Reorder Level"), "fieldname": "reorder_level", "fieldtype": "Float", "width": 110},
		{"label": _("Actual Qty"), "fieldname": "actual_qty", "fieldtype": "Float", "width": 110},
		{"label": _("Economy Stock"), "fieldname": "economy_stock", "fieldtype": "Float", "width": 120},
		{"label": _("Status"), "fieldname": "status", "fieldtype": "Data", "width": 130},
		{"label": _("Variance"), "fieldname": "variance", "fieldtype": "Float", "width": 100},
	]
