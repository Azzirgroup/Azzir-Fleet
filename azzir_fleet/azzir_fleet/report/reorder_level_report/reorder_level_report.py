# Copyright (c) 2026, Azzir and contributors
# For license information, please see license.txt
"""Reorder Level Report — items whose stock is OUT OF BAND: below the item's
Minimum Order Qty (understocked → reorder) or above its Maximum Order Qty
(overstocked). Driven by the item's Min/Max Order Qty (no per-warehouse reorder
level needed). Shows Economy Stock (already on order, not yet received) and the
reorder level for reference.

Presented as a TREE grouped per warehouse: each warehouse is a parent node and
the out-of-band items it holds are its children (so you never see a single
lumped "All Warehouses" row). A Below-Minimum item drops off once a Purchase
Invoice is raised for it (within the Reordered-Within window).

The Item filter is alias-aware: type a current OR an alternative (old) part
number and it resolves to the live item (via azzir_fleet.alias)."""

import frappe
from frappe import _
from frappe.utils import add_days, flt, today


def execute(filters=None):
	filters = frappe._dict(filters or {})
	return get_columns(), get_rows(filters)


def _item_filter(filters):
	"""The chosen items (alias-aware): each picked value is already a live Item
	code, but we also resolve anything that is an old/alternative code, just in
	case."""
	raw = filters.get("items")
	if isinstance(raw, str):
		raw = frappe.parse_json(raw) if raw.strip().startswith("[") else [raw]
	codes = []
	from azzir_fleet.alias import resolve_code

	for c in raw or []:
		if not c:
			continue
		hit = resolve_code(c)
		codes.append(hit["item"] if hit else c)
	return list(dict.fromkeys(codes))


def get_rows(filters):
	# 1) Items with a Minimum or Maximum Order Qty configured (optionally the ones
	#    picked in the Item filter).
	item_conds = {"disabled": 0, "is_stock_item": 1}
	picked = _item_filter(filters)
	if picked:
		item_conds["name"] = ["in", picked]
	items = frappe.get_all(
		"Item",
		filters=item_conds,
		or_filters={"min_order_qty": [">", 0], "max_order_qty": [">", 0]},
		fields=["name", "item_name", "min_order_qty", "max_order_qty"],
	)
	if not items:
		return []
	meta = {i.name: i for i in items}
	codes = list(meta)

	# 2) Stock per (item, warehouse), scoped by the company / warehouse filters.
	conds = ["b.item_code in %(codes)s", "w.is_group = 0", "w.disabled = 0"]
	vals = {"codes": tuple(codes)}
	if filters.get("warehouse"):
		conds.append("b.warehouse = %(wh)s")
		vals["wh"] = filters.warehouse
	if filters.get("company"):
		conds.append("w.company = %(co)s")
		vals["co"] = filters.company
	bins = frappe.db.sql(
		"""select b.item_code, b.warehouse, w.company, sum(b.actual_qty) q
		   from `tabBin` b join `tabWarehouse` w on w.name = b.warehouse
		   where {c} group by b.item_code, b.warehouse""".format(c=" and ".join(conds)),
		vals,
		as_dict=True,
	)

	# 3) Economy stock per (item, warehouse) = on submitted, not-yet-received POs.
	economy = {}
	for e in frappe.db.sql(
		"""select poi.item_code, poi.warehouse,
		          sum(greatest(0, poi.qty - poi.received_qty)) as on_order
		   from `tabPurchase Order Item` poi
		   join `tabPurchase Order` po on po.name = poi.parent
		   where po.docstatus = 1 and po.status not in ('Closed', 'Completed', 'Delivered')
		     and poi.item_code in %(codes)s
		   group by poi.item_code, poi.warehouse""",
		{"codes": tuple(codes)},
		as_dict=True,
	):
		economy[(e.item_code, e.warehouse)] = flt(e.on_order)

	# 4) Reorder level per (item, warehouse) — reference only.
	reorder_level = {}
	for r in frappe.db.sql(
		"""select parent as item_code, warehouse, max(warehouse_reorder_level) lvl
		   from `tabItem Reorder` where parent in %(codes)s group by parent, warehouse""",
		{"codes": tuple(codes)},
		as_dict=True,
	):
		reorder_level[(r.item_code, r.warehouse)] = flt(r.lvl)

	# 5) Below-Minimum items drop off once a Purchase Invoice has been raised for
	#    them. 0 days = any open Purchase Invoice, ever.
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

	below_label, above_label = _("Below Minimum"), _("Above Maximum")

	# 6) Build the qualifying children, grouped by warehouse.
	by_wh = {}
	for b in bins:
		im = meta[b.item_code]
		mn, mx = flt(im.min_order_qty), flt(im.max_order_qty)
		actual = flt(b.q)
		below = mn > 0 and actual < mn
		above = mx > 0 and actual > mx
		if not (below or above):
			continue  # within the [min, max] band — fine
		if below and not above and b.item_code in reordered:
			continue  # already reordered
		grp = by_wh.setdefault(b.warehouse, {"company": b.company, "kids": []})
		grp["kids"].append(
			{
				"item_code": b.item_code,
				"label": b.item_code,
				"item_name": im.item_name,
				"min_order_qty": mn,
				"max_order_qty": mx,
				"reorder_level": reorder_level.get((b.item_code, b.warehouse), 0.0),
				"actual_qty": actual,
				"economy_stock": economy.get((b.item_code, b.warehouse), 0.0),
				"status": below_label if below else above_label,
				"variance": (mn - actual) if below else (actual - mx),
				"indent": 1,
			}
		)

	# 7) Emit warehouse parents (indent 0) then their item children (indent 1).
	#    Warehouses holding the most below-minimum items float to the top.
	def wh_sort_key(wh):
		kids = by_wh[wh]["kids"]
		below_ct = sum(1 for k in kids if k["status"] == below_label)
		return (-below_ct, wh)

	rows = []
	for wh in sorted(by_wh, key=wh_sort_key):
		grp = by_wh[wh]
		kids = grp["kids"]
		kids.sort(key=lambda x: (x["status"] != below_label, -x["variance"]))
		below_ct = sum(1 for k in kids if k["status"] == below_label)
		rows.append(
			{
				"label": wh,
				"warehouse": wh,
				"item_name": grp["company"],
				"actual_qty": sum(k["actual_qty"] for k in kids),
				"economy_stock": sum(k["economy_stock"] for k in kids),
				"status": _("{0} below · {1} item(s)").format(below_ct, len(kids)),
				"is_group": 1,
				"indent": 0,
			}
		)
		rows.extend(kids)
	return rows


def get_columns():
	return [
		{"label": _("Warehouse / Item"), "fieldname": "label", "fieldtype": "Data", "width": 260},
		{"label": _("Item Name / Company"), "fieldname": "item_name", "fieldtype": "Data", "width": 220},
		{"label": _("Min Order Qty"), "fieldname": "min_order_qty", "fieldtype": "Float", "width": 110},
		{"label": _("Max Order Qty"), "fieldname": "max_order_qty", "fieldtype": "Float", "width": 110},
		{"label": _("Reorder Level"), "fieldname": "reorder_level", "fieldtype": "Float", "width": 110},
		{"label": _("Actual Qty"), "fieldname": "actual_qty", "fieldtype": "Float", "width": 110},
		{"label": _("Economy Stock"), "fieldname": "economy_stock", "fieldtype": "Float", "width": 120},
		{"label": _("Status"), "fieldname": "status", "fieldtype": "Data", "width": 150},
		{"label": _("Variance"), "fieldname": "variance", "fieldtype": "Float", "width": 100},
	]
