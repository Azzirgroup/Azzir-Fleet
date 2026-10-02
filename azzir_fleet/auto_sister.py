# Copyright (c) 2026, Azzir and contributors
# For license information, please see license.txt
"""Automatic buy-from-sister on a Sales Invoice.

When the buying company opts in ("Is Auto Purchase From Sister Company") and a line's
warehouse is short of the item AT SUBMIT TIME, we automatically fill the per-row
buy-from-sister fields — instead of the seller manually ticking "From sister" and
picking a company + warehouse. The sister is chosen by BRANCH: a sister company that
is also opted in, whose leaf warehouse shares the same Branch as the buying warehouse
and holds the item (most stock wins). The existing intercompany machinery
(set_landing_warehouse -> process_sister_purchase) then does the transfer.

Runs only when the document is actually being submitted (docstatus == 1), so drafts
save freely. If no sister can cover the shortfall it blocks the submit with a clear
message (what your warehouse has, what the sister has — reduce the qty or add stock).
Being server-side, it behaves identically on the desk and on the /sales portal.
"""

import frappe
from frappe import _
from frappe.utils import flt


def _needed_qty(row):
	"""Line qty in STOCK uom (Bin.actual_qty is in stock uom)."""
	if flt(row.get("stock_qty")):
		return flt(row.get("stock_qty"))
	return flt(row.get("qty")) * flt(row.get("conversion_factor") or 1)


def _effective_branch(warehouse):
	"""The warehouse's own azzir_branch if set, else its nearest ancestor GROUP's —
	walking up parent_warehouse. Branch lives on the GROUP; a leaf doesn't need its own
	branch tagged as long as the group it sits under has one. Mirrors
	warehouse_cc.resolve_warehouse_cost_center's walk-up for cost centres."""
	seen = set()
	wh = warehouse
	while wh and wh not in seen:
		seen.add(wh)
		branch, parent = frappe.db.get_value(
			"Warehouse", wh, ["azzir_branch", "parent_warehouse"]
		) or (None, None)
		if branch:
			return branch
		wh = parent
	return None


def _best_sister_in_branch(item, branch, exclude_company):
	"""Best (most stock) LEAF of `item` under any OPTED-IN sister company's GROUP
	warehouse sharing `branch` — the group carries the branch tag, not necessarily its
	leaves. Reuses intercompany_sale's leaf-under-bounds search (_best_leaf_with_stock)
	so this and the manual 'All Warehouses' resolver share one implementation for
	"find stock under a group" instead of two copies of the same SQL. Returns a row
	with warehouse/company/qty, or None."""
	from azzir_fleet.intercompany_sale import _best_leaf_with_stock

	best = None
	for sg in frappe.db.sql(
		"""select w.name, w.lft, w.rgt, w.company
		   from `tabWarehouse` w
		   join `tabCompany` c on c.name = w.company
		   where w.azzir_branch = %(branch)s and w.is_group = 1 and w.disabled = 0
		     and w.company != %(co)s and c.azzir_auto_purchase_from_sister = 1""",
		{"branch": branch, "co": exclude_company}, as_dict=True,
	):
		cand = _best_leaf_with_stock(item, lft=sg.lft, rgt=sg.rgt, exclude_company=exclude_company)
		if cand and (best is None or flt(cand.qty) > flt(best.qty)):
			best = cand
	return best


def auto_source_from_sister(doc, method=None):
	# Only at submit — leave draft saves alone.
	if doc.docstatus != 1:
		return
	company = doc.get("company")
	if not company or not frappe.db.get_value("Company", company, "azzir_auto_purchase_from_sister"):
		return

	notes = []
	for row in doc.get("items") or []:
		if row.get("azzir_row_from_sister"):
			continue  # seller already chose a sister source for this line
		item = row.get("item_code")
		wh = row.get("warehouse")
		if not item or not wh:
			continue
		if not frappe.db.get_value("Item", item, "is_stock_item"):
			continue
		needed = _needed_qty(row)
		if needed <= 0:
			continue

		w_avail = flt(frappe.db.get_value("Bin", {"item_code": item, "warehouse": wh}, "actual_qty"))
		if w_avail >= needed:
			continue  # this warehouse has enough — nothing to do

		branch = _effective_branch(wh)
		if not branch:
			# No branch (on this warehouse or any ancestor group) to match a sister on —
			# let normal stock validation handle it.
			continue

		# Best sister LEAF, found by matching the GROUP warehouse branch (not the leaf's
		# own) and drilling into that group's children for stock — most stock first.
		best = _best_sister_in_branch(item, branch, company)

		if not best:
			frappe.throw(_(
				"Auto-purchase: warehouse <b>{0}</b> is short of <b>{1}</b> (has {2}, need {3}), "
				"and no sister company sharing branch <b>{4}</b> has any stock of it. "
				"Add stock to {0} or to a sister warehouse on that branch."
			).format(wh, item, w_avail, needed, branch), title=_("Not enough stock"))

		ws_avail = flt(best.qty)
		if ws_avail < needed:
			frappe.throw(_(
				"We noted warehouse <b>{0}</b> did not have enough <b>{1}</b> (has {2}, need {3}) "
				"and looked to buy from sister <b>{4}</b> (warehouse {5}) — but it only has "
				"<b>{6}</b>. Consider reducing the quantity to {6}, or add more stock "
				"(to {0} or {5})."
			).format(wh, item, w_avail, needed, best.company, best.warehouse, ws_avail),
				title=_("Sister stock also short"))

		# Sister can cover — auto-fill the buy-from-sister fields for this line.
		row.azzir_row_from_sister = 1
		row.azzir_supply_company = best.company
		row.azzir_supply_warehouse = best.warehouse
		notes.append(_("{0}: bought from sister {1} ({2})").format(item, best.company, best.warehouse))

	if notes:
		frappe.msgprint(
			_("Your warehouse was short, so we initiated purchase from a sister company:<br>{0}")
			.format("<br>".join(notes)),
			title=_("Auto purchase from sister"), indicator="blue",
		)
