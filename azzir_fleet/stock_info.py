# Copyright (c) 2026, Azzir and contributors
# For license information, please see license.txt
"""Live item-stock helpers for the Quotation grid."""

import frappe
from frappe.utils import flt


@frappe.whitelist()
def items_with_stock(
	doctype: str,
	txt: str,
	searchfield: str,
	start: int,
	page_len: int,
	filters: dict | str | None = None,
	**kwargs,
):
	"""Link-field query: items that have stock in filters['warehouse'].
	If no warehouse is given, returns all items."""
	if isinstance(filters, str):
		filters = frappe.parse_json(filters)
	warehouse = (filters or {}).get("warehouse")
	like = f"%{txt or ''}%"

	if not warehouse:
		return frappe.db.sql(
			"""select name, item_name from `tabItem`
			   where disabled = 0 and (name like %(t)s or item_name like %(t)s)
			   order by name limit %(s)s, %(p)s""",
			{"t": like, "s": start, "p": page_len},
		)

	return frappe.db.sql(
		"""select distinct it.name, it.item_name from `tabItem` it
		   join `tabBin` b on b.item_code = it.name
		   where b.warehouse = %(wh)s and b.actual_qty > 0 and it.disabled = 0
		     and (it.name like %(t)s or it.item_name like %(t)s)
		   order by it.name limit %(s)s, %(p)s""",
		{"wh": warehouse, "t": like, "s": start, "p": page_len},
	)


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


@frappe.whitelist()
def get_stock_branch(item_code: str, warehouse: str | None = None):
	"""Stock for the item in the picked warehouse and its immediate parent only."""
	if not item_code or not warehouse:
		return []
	info = frappe.db.get_value(
		"Warehouse", warehouse, ["parent_warehouse", "is_group", "lft"], as_dict=True
	)
	if not info:
		return []

	rows = []
	if info.parent_warehouse:
		pinfo = frappe.db.get_value(
			"Warehouse", info.parent_warehouse, ["is_group", "lft"], as_dict=True
		) or {}
		rows.append(
			{
				"warehouse": info.parent_warehouse,
				"is_group": pinfo.get("is_group", 1),
				"qty": _warehouse_stock(item_code, info.parent_warehouse),
				"depth": 0,
			}
		)
	rows.append(
		{
			"warehouse": warehouse,
			"is_group": info.is_group,
			"qty": _warehouse_stock(item_code, warehouse),
			"depth": 1 if info.parent_warehouse else 0,
		}
	)
	return rows


def _depth(wh, wh_info):
	"""How many ancestor warehouses `wh` has (for indentation)."""
	d = 0
	parent = (wh_info.get(wh) or {}).get("parent_warehouse")
	while parent:
		d += 1
		parent = (wh_info.get(parent) or {}).get("parent_warehouse")
	return d
