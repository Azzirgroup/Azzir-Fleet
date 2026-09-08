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

		branch = frappe.db.get_value("Warehouse", wh, "azzir_branch")
		if not branch:
			# No branch to match a sister on — let normal stock validation handle it.
			continue

		# Best sister warehouse: same branch, another opted-in company, leaf, enabled,
		# holding the item — most stock first.
		cand = frappe.db.sql(
			"""select b.warehouse, w.company, sum(b.actual_qty) qty
			   from `tabBin` b
			   join `tabWarehouse` w on w.name = b.warehouse
			   join `tabCompany` c on c.name = w.company
			   where b.item_code = %(item)s and w.azzir_branch = %(branch)s
			     and w.company != %(co)s and w.is_group = 0 and w.disabled = 0
			     and c.azzir_auto_purchase_from_sister = 1
			   group by b.warehouse having qty > 0 order by qty desc limit 1""",
			{"item": item, "branch": branch, "co": company},
			as_dict=True,
		)

		if not cand:
			frappe.throw(_(
				"Auto-purchase: warehouse <b>{0}</b> is short of <b>{1}</b> (has {2}, need {3}), "
				"and no sister company sharing branch <b>{4}</b> has any stock of it. "
				"Add stock to {0} or to a sister warehouse on that branch."
			).format(wh, item, w_avail, needed, branch), title=_("Not enough stock"))

		best = cand[0]
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
