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

	# Tree bounds of the selected warehouse: a LEAF's (lft, rgt) covers only itself,
	# a GROUP's covers all its child warehouses — so "stock in this warehouse" also
	# means "stock in any leaf under it" when a group is chosen.
	bounds = frappe.db.get_value("Warehouse", warehouse, ["lft", "rgt"]) if warehouse else None

	if not warehouse or not bounds or bounds[0] is None:
		rows = frappe.db.sql(
			"""select name, item_name, '' from `tabItem`
			   where disabled = 0 and (name like %(t)s or item_name like %(t)s)
			   order by name limit %(s)s, %(p)s""",
			{"t": like, "s": start, "p": page_len},
		)
		bounds = None
	else:
		rows = frappe.db.sql(
			"""select distinct it.name, it.item_name, '' from `tabItem` it
			   join `tabBin` b on b.item_code = it.name
			   join `tabWarehouse` bw on bw.name = b.warehouse
			   where bw.lft >= %(lft)s and bw.rgt <= %(rgt)s and b.actual_qty > 0
			     and it.disabled = 0 and (it.name like %(t)s or it.item_name like %(t)s)
			   order by it.name limit %(s)s, %(p)s""",
			{"lft": bounds[0], "rgt": bounds[1], "t": like, "s": start, "p": page_len},
		)

	# Resolve OLD codes too (separator-insensitive), so typing a retired part number
	# finds the current item — same as every other item field. Keep the in-stock rule:
	# an aliased item is only offered if it has stock in the source warehouse (or any
	# leaf under it, if a group was chosen).
	if txt:
		from azzir_fleet.alias import fuzzy_item_matches

		rows = [list(r) for r in rows]
		existing = {r[0] for r in rows}
		for m in fuzzy_item_matches(txt, limit=15):
			item = m.get("item")
			if not item or item in existing:
				continue
			if bounds is not None:
				in_stock = frappe.db.sql(
					"""select 1 from `tabBin` b join `tabWarehouse` bw on bw.name = b.warehouse
					   where b.item_code = %(it)s and b.actual_qty > 0
					     and bw.lft >= %(lft)s and bw.rgt <= %(rgt)s limit 1""",
					{"it": item, "lft": bounds[0], "rgt": bounds[1]},
				)
				if not in_stock:
					continue
			existing.add(item)
			note = "↺ old code: %s" % m["old_code"] if m.get("old_code") else ""
			rows.insert(0, [item, frappe.db.get_value("Item", item, "item_name") or item, note])
	return rows


@frappe.whitelist()
def warehouses_with_stock(
	doctype: str,
	txt: str,
	searchfield: str,
	start: int,
	page_len: int,
	filters: dict | str | None = None,
	**kwargs,
):
	"""Link-field query: warehouses that hold stock of filters['item_code'] (so the
	user picks a source warehouse straight from those with qty). No item -> all
	non-group warehouses."""
	if isinstance(filters, str):
		filters = frappe.parse_json(filters)
	filters = filters or {}
	item_code = filters.get("item_code")
	company = filters.get("company")
	like = f"%{txt or ''}%"

	if not item_code:
		conds = "is_group = 0 and disabled = 0 and (name like %(t)s or warehouse_name like %(t)s)"
		vals = {"t": like, "s": start, "p": page_len}
		if company:
			conds += " and company = %(c)s"
			vals["c"] = company
		return frappe.db.sql(
			f"""select name, warehouse_name from `tabWarehouse`
			   where {conds} order by name limit %(s)s, %(p)s""",
			vals,
		)

	conds = "w.is_group = 0 and w.disabled = 0 and b.item_code = %(it)s and b.actual_qty > 0"
	vals = {"it": item_code, "t": like, "s": start, "p": page_len}
	if company:
		conds += " and w.company = %(c)s"
		vals["c"] = company
	return frappe.db.sql(
		f"""select distinct w.name, w.warehouse_name
		   from `tabWarehouse` w join `tabBin` b on b.warehouse = w.name
		   where {conds} and (w.name like %(t)s or w.warehouse_name like %(t)s)
		   order by b.actual_qty desc, w.name limit %(s)s, %(p)s""",
		vals,
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
def get_stock_tree(
	item_code: str, exclude_invoice: str | None = None, groups_only: int | str | None = None
):
	"""Per-warehouse stock for the item, grouped by the warehouse tree.

	Returns a flat list (ordered by tree position) of warehouses that hold stock
	plus their ancestor groups, each with its quantity (a group's quantity is the
	sum of its descendants). The client renders it as a tree.

	When `exclude_invoice` is provided (the dialog passes the current invoice), the
	quantities are AVAILABLE stock = physical minus what other open invoices have
	reserved. Reservations recorded against a group (region) are subtracted from
	that group's rolled-up total; leaf reservations from the leaf.

	When `groups_only` is set, only GROUP warehouses are returned (the sales view —
	sales people pick a region, never a bin).
	"""
	if not item_code:
		return []

	groups_only = frappe.utils.cint(groups_only)

	bins = frappe.db.sql(
		"""select warehouse, sum(actual_qty) qty, sum(ordered_qty) ordered from `tabBin`
		   where item_code = %s and (actual_qty != 0 or ordered_qty != 0) group by warehouse""",
		item_code,
		as_dict=True,
	)
	if not bins:
		return []
	stock = {b.warehouse: flt(b.qty) for b in bins}
	# Incoming (economy) stock per warehouse = quantity on order (Purchase Orders
	# not yet received into that warehouse).
	ordered = {b.warehouse: flt(b.ordered) for b in bins}

	reserved = {}
	if exclude_invoice is not None:
		from azzir_fleet.stock_reservation import reserved_by_warehouse

		reserved = {w: flt(r) for w, r in reserved_by_warehouse(item_code, exclude_invoice).items()}

	# Cost-center scoping: the user may SEE every warehouse, but may only SELECT
	# ones attached to a cost center they are assigned to (None = no restriction).
	# Guarded so it degrades gracefully if the field hasn't been migrated yet.
	from azzir_fleet.warehouse_cc import _effective_bounds, _within_bounds

	has_cc = frappe.get_meta("Warehouse").has_field("azzir_cost_center")
	wh_fields = ["name", "parent_warehouse", "is_group", "lft", "rgt", "company"]
	if has_cc:
		wh_fields.append("azzir_cost_center")
	wh_info = {w.name: w for w in frappe.get_all("Warehouse", fields=wh_fields)}

	# Warehouses the user may SELECT (Warehouse permission wins over cost centre;
	# None = unrestricted). Used only to flag rows selectable — everything they may SEE
	# is still shown.
	eff = _effective_bounds()

	# Company scope: holders of "Azzir Group Stock" (or Administrator) see ALL
	# companies' stock; everyone else sees the companies they are permitted for (their
	# Company user permissions), falling back to their default company.
	if not ("Azzir Group Stock" in frappe.get_roles() or frappe.session.user == "Administrator"):
		companies = frappe.get_all(
			"User Permission", {"user": frappe.session.user, "allow": "Company"}, pluck="for_value"
		)
		if not companies:
			dc = frappe.defaults.get_user_default("Company")
			companies = [dc] if dc else []
		if companies:
			stock = {wh: q for wh, q in stock.items() if (wh_info.get(wh) or {}).get("company") in companies}
			ordered = {wh: q for wh, q in ordered.items() if (wh_info.get(wh) or {}).get("company") in companies}
			if not stock:
				return []

	# Include the ancestor groups of every warehouse that holds stock.
	needed = set(stock)
	for wh in list(stock):
		parent = (wh_info.get(wh) or {}).get("parent_warehouse")
		while parent:
			needed.add(parent)
			parent = (wh_info.get(parent) or {}).get("parent_warehouse")

	def _under(node, info):
		"""Is warehouse `node` inside group `info`'s subtree?"""
		ni = wh_info.get(node)
		return bool(ni) and ni.lft >= info.lft and ni.rgt <= info.rgt

	rows = []
	for wh in needed:
		info = wh_info.get(wh)
		if not info:
			continue
		if info.is_group:
			physical = sum(v for lw, v in stock.items() if _under(lw, info))
			held = sum(r for rw, r in reserved.items() if _under(rw, info))
			qty = max(0.0, physical - held)
			incoming = sum(o for lw, o in ordered.items() if _under(lw, info))
		else:
			qty = max(0.0, flt(stock.get(wh, 0)) - flt(reserved.get(wh, 0)))
			incoming = flt(ordered.get(wh, 0))
		rows.append(
			{
				"warehouse": wh,
				"parent": info.parent_warehouse,
				"is_group": info.is_group,
				"qty": flt(qty),
				"incoming": flt(incoming),
				"lft": info.lft,
				"depth": _depth(wh, wh_info),
				"company": info.company,
				"cost_center": info.get("azzir_cost_center"),
				# Groups are never picked; a leaf is selectable when the user is
				# unrestricted, or it falls within their effective warehouse grant.
				"selectable": True
				if info.is_group
				else (eff is None or _within_bounds(info.lft, info.rgt, eff)),
			}
		)

	if groups_only:
		rows = [r for r in rows if r["is_group"]]

	rows.sort(key=lambda r: (r.get("company") or "", r["lft"] or 0))
	return rows


@frappe.whitelist()
def best_warehouse_in_group(item_code: str | None = None, warehouse: str | None = None):
	"""The leaf warehouse UNDER `warehouse` (a group, or a leaf) that holds the MOST
	stock of the item — used to auto-fill a Stock Entry row's Source Warehouse from the
	chosen Default Group Source Warehouse. Nested groups included. None if none hold it."""
	if not item_code or not warehouse:
		return None
	bounds = frappe.db.get_value("Warehouse", warehouse, ["lft", "rgt"])
	if not bounds or bounds[0] is None:
		return None
	row = frappe.db.sql(
		"""select b.warehouse, sum(b.actual_qty) qty
		   from `tabBin` b join `tabWarehouse` w on w.name = b.warehouse
		   where b.item_code = %(it)s and b.actual_qty > 0 and w.is_group = 0 and w.disabled = 0
		     and w.lft >= %(lft)s and w.rgt <= %(rgt)s
		   group by b.warehouse having qty > 0 order by qty desc limit 1""",
		{"it": item_code, "lft": bounds[0], "rgt": bounds[1]},
		as_dict=True,
	)
	return row[0].warehouse if row else None


@frappe.whitelist()
def target_warehouse_in_group(item_code: str | None = None, warehouse: str | None = None):
	"""Leaf under `warehouse` to auto-fill a Stock Entry row's TARGET Warehouse from the
	chosen Default Group Target Warehouse: the leaf holding the MOST of the item, or — when
	none holds it (e.g. a receipt into an empty group) — the first (alphabetical) enabled
	leaf in the group, so the target always lands somewhere sensible. None if the group has
	no usable leaf."""
	if not warehouse:
		return None
	best = best_warehouse_in_group(item_code, warehouse) if item_code else None
	if best:
		return best
	b = frappe.db.get_value("Warehouse", warehouse, ["lft", "rgt"])
	if not b or b[0] is None:
		return None
	row = frappe.db.sql(
		"""select w.name from `tabWarehouse` w
		   where w.is_group = 0 and w.disabled = 0
		     and w.lft >= %(lft)s and w.rgt <= %(rgt)s
		   order by w.name limit 1""",
		{"lft": b[0], "rgt": b[1]},
		as_dict=True,
	)
	return row[0].name if row else None


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def leaves_in_group(doctype, txt, searchfield, start, page_len, filters):
	"""Link-field query: leaf warehouses that sit UNDER filters['group'] (a group
	warehouse) — for a Stock Entry row's Target Warehouse once a Default Group Target
	Warehouse is chosen. No group given -> all leaf warehouses."""
	if isinstance(filters, str):
		filters = frappe.parse_json(filters)
	filters = filters or {}
	group = filters.get("group")
	like = "%%%s%%" % (txt or "")
	conds = ["w.disabled = 0", "w.is_group = 0", "(w.name like %(t)s or w.warehouse_name like %(t)s)"]
	vals = {"t": like, "s": start, "p": page_len}
	if group:
		b = frappe.db.get_value("Warehouse", group, ["lft", "rgt"])
		if b and b[0] is not None:
			conds.append("w.lft >= %(lft)s and w.rgt <= %(rgt)s")
			vals["lft"], vals["rgt"] = b[0], b[1]
	return frappe.db.sql(
		"select w.name, w.warehouse_name from `tabWarehouse` w where "
		+ " and ".join(conds) + " order by w.name limit %(s)s, %(p)s",
		vals,
	)


@frappe.whitelist()
def last_warehouse(item_code: str, company: str | None = None) -> str:
	"""The warehouse this item was most recently stored in (last stock ledger
	entry), even if that warehouse is now empty. For auto-filling receipts."""
	if not item_code:
		return ""
	filters = {"item_code": item_code, "is_cancelled": 0}
	if company:
		filters["company"] = company
	return (
		frappe.db.get_value(
			"Stock Ledger Entry", filters, "warehouse", order_by="posting_datetime desc, creation desc"
		)
		or ""
	)


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
