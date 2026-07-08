# Copyright (c) 2026, Azzir and contributors
# For license information, please see license.txt
"""Live item-stock helpers for the Quotation grid."""

import frappe
from frappe.utils import flt


@frappe.whitelist()
def get_item_stock(item_code: str, warehouse: str | None = None):
	"""Return the item's stock in `warehouse` (incl. child warehouses if it's a
	group) and its total across all warehouses."""
	if not item_code:
		return {"wh_stock": 0.0, "all_stock": 0.0}

	all_stock = (
		frappe.db.sql(
			"select sum(actual_qty) from `tabBin` where item_code = %s", item_code
		)[0][0]
		or 0
	)

	wh_stock = 0.0
	if warehouse:
		wh_stock = _warehouse_stock(item_code, warehouse)

	return {"wh_stock": flt(wh_stock), "all_stock": flt(all_stock)}


def _warehouse_stock(item_code, warehouse):
	"""Stock in a warehouse — sums child warehouses when it's a group."""
	bounds = frappe.db.get_value("Warehouse", warehouse, ["lft", "rgt"])
	if not bounds or bounds[0] is None:
		return flt(
			frappe.db.get_value("Bin", {"item_code": item_code, "warehouse": warehouse}, "actual_qty")
		)
	lft, rgt = bounds
	qty = frappe.db.sql(
		"""select sum(b.actual_qty) from `tabBin` b
		   join `tabWarehouse` w on w.name = b.warehouse
		   where b.item_code = %s and w.lft >= %s and w.rgt <= %s""",
		(item_code, lft, rgt),
	)[0][0]
	return flt(qty)


@frappe.whitelist()
def get_stock_tree(item_code: str):
	"""Per-warehouse stock for the item, grouped by the warehouse tree.

	Returns a flat list (ordered by tree position) of warehouses that hold stock
	plus their ancestor groups, each with its quantity (a group's quantity is the
	sum of its descendants). The client renders it as a tree.
	"""
	if not item_code:
		return []

	bins = frappe.db.sql(
		"""select warehouse, sum(actual_qty) qty from `tabBin`
		   where item_code = %s and actual_qty != 0 group by warehouse""",
		item_code,
		as_dict=True,
	)
	if not bins:
		return []
	stock = {b.warehouse: flt(b.qty) for b in bins}

	wh_info = {
		w.name: w
		for w in frappe.get_all(
			"Warehouse", fields=["name", "parent_warehouse", "is_group", "lft", "rgt"]
		)
	}

	# Include the ancestor groups of every warehouse that holds stock.
	needed = set(stock)
	for wh in list(stock):
		parent = (wh_info.get(wh) or {}).get("parent_warehouse")
		while parent:
			needed.add(parent)
			parent = (wh_info.get(parent) or {}).get("parent_warehouse")

	rows = []
	for wh in needed:
		info = wh_info.get(wh)
		if not info:
			continue
		if info.is_group:
			qty = sum(
				v
				for lw, v in stock.items()
				if wh_info.get(lw) and wh_info[lw].lft >= info.lft and wh_info[lw].rgt <= info.rgt
			)
		else:
			qty = stock.get(wh, 0)
		rows.append(
			{
				"warehouse": wh,
				"parent": info.parent_warehouse,
				"is_group": info.is_group,
				"qty": flt(qty),
				"lft": info.lft,
				"depth": _depth(wh, wh_info),
			}
		)

	rows.sort(key=lambda r: r["lft"] or 0)
	return rows


def _depth(wh, wh_info):
	"""How many ancestor warehouses `wh` has (for indentation)."""
	d = 0
	parent = (wh_info.get(wh) or {}).get("parent_warehouse")
	while parent:
		d += 1
		parent = (wh_info.get(parent) or {}).get("parent_warehouse")
	return d
