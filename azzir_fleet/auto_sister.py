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


def _sister_candidates_in_branch(item, branch, exclude_company):
	"""EVERY sister LEAF of `item` (not just the best) under any OPTED-IN sister
	company's GROUP warehouse sharing `branch` — the group carries the branch tag, not
	necessarily its leaves. Ordered by stock, most first, so a short line can be covered
	by combining more than one sister warehouse. Returns a list of rows with
	warehouse/company/qty."""
	# The CANDIDATE (supplying) company only needs azzir_sister_supply_enabled — a
	# separate flag from azzir_auto_purchase_from_sister (the buyer flag checked in
	# auto_source_from_sister below) so a company can supply sisters WITHOUT itself
	# becoming able to auto-buy from anyone. One-directional on purpose.
	candidates = []
	for sg in frappe.db.sql(
		"""select w.name, w.lft, w.rgt, w.company
		   from `tabWarehouse` w
		   join `tabCompany` c on c.name = w.company
		   where w.azzir_branch = %(branch)s and w.is_group = 1 and w.disabled = 0
		     and w.company != %(co)s and c.azzir_sister_supply_enabled = 1""",
		{"branch": branch, "co": exclude_company}, as_dict=True,
	):
		for leaf in frappe.db.sql(
			"""select b.warehouse, sum(b.actual_qty) qty
			   from `tabBin` b join `tabWarehouse` w on w.name = b.warehouse
			   where b.item_code = %(item)s and w.is_group = 0 and w.disabled = 0
			     and w.lft >= %(lft)s and w.rgt <= %(rgt)s
			   group by b.warehouse having qty > 0""",
			{"item": item, "lft": sg.lft, "rgt": sg.rgt}, as_dict=True,
		):
			candidates.append(frappe._dict(warehouse=leaf.warehouse, company=sg.company, qty=flt(leaf.qty)))
	candidates.sort(key=lambda c: -c.qty)
	return candidates


def _best_sister_in_branch(item, branch, exclude_company):
	"""Best (most stock) single LEAF — kept for any other caller that only wants one."""
	cands = _sister_candidates_in_branch(item, branch, exclude_company)
	return cands[0] if cands else None


_ROW_COPY_SKIP = {
	"name", "idx", "owner", "creation", "modified", "modified_by", "docstatus",
	"parent", "parentfield", "parenttype", "doctype",
}


def _split_row_copy(doc, row, qty, conv):
	"""A new child row cloned from `row` (same item/rate/description/etc.) carrying
	only `qty` of the original line — used when one sister warehouse can't cover the
	whole line and the remainder is split onto a second (or third...) sister source."""
	new_row = doc.append("items", {})
	for fieldname, value in row.as_dict().items():
		if fieldname in _ROW_COPY_SKIP:
			continue
		new_row.set(fieldname, value)
	new_row.qty = (qty / conv) if conv else qty
	new_row.stock_qty = qty
	new_row.amount = flt(new_row.qty) * flt(new_row.rate)
	new_row.net_amount = new_row.amount
	return new_row


def auto_source_from_sister(doc, method=None):
	# Only at submit — leave draft saves alone.
	if doc.docstatus != 1:
		return
	company = doc.get("company")
	if not company or not frappe.db.get_value("Company", company, "azzir_auto_purchase_from_sister"):
		return

	notes = []
	split_happened = False
	# How much of each (item, sister warehouse) earlier ROWS in THIS SAME document have
	# already claimed. Without this, two rows needing the same item from the same sister
	# warehouse are each checked against the FULL stock independently and silently
	# over-commit more than the sister actually has — the real shortfall then surfaces
	# later, confusingly, during the actual transfer instead of here, clearly.
	claimed = {}
	# Iterate a SNAPSHOT — rows added for a split go onto doc.items directly and must not
	# themselves be re-processed by this same loop.
	for row in list(doc.get("items") or []):
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

		# Every sister LEAF sharing this branch, most stock first — a short line is
		# covered by ONE warehouse when possible, or SPLIT across several in turn when
		# the biggest alone isn't enough.
		candidates = _sister_candidates_in_branch(item, branch, company)
		if not candidates:
			frappe.throw(_(
				"Auto-purchase: warehouse <b>{0}</b> is short of <b>{1}</b> (has {2}, need {3}), "
				"and no sister company sharing branch <b>{4}</b> has any stock of it. "
				"Add stock to {0} or to a sister warehouse on that branch."
			).format(wh, item, w_avail, needed, branch), title=_("Not enough stock"))

		remaining = needed
		allocations = []  # [(candidate, qty_taken), ...]
		for cand in candidates:
			if remaining <= 1e-9:
				break
			key = (item, cand.warehouse)
			free = flt(cand.qty) - flt(claimed.get(key, 0))
			if free <= 1e-9:
				continue
			take = min(free, remaining)
			allocations.append((cand, take))
			claimed[key] = flt(claimed.get(key, 0)) + take
			remaining -= take

		if remaining > 1e-9:
			# Not enough even combining EVERY matching sister warehouse. Undo the
			# partial claims this line made so a later line isn't wrongly blocked by them.
			for cand, taken in allocations:
				claimed[(item, cand.warehouse)] -= taken
			covered = needed - remaining
			frappe.throw(_(
				"We noted warehouse <b>{0}</b> did not have enough <b>{1}</b> (has {2}, need {3}). "
				"Combining every sister warehouse on branch <b>{4}</b> only covers "
				"<b>{5}</b> — still short by <b>{6}</b>. Reduce the quantity, or add more stock."
			).format(wh, item, w_avail, needed, branch, covered, remaining),
				title=_("Sister stock also short"))

		# Covered — by one warehouse, or split across several. The FIRST (biggest)
		# allocation updates the ORIGINAL row; any further allocations become NEW rows.
		conv = flt(row.get("conversion_factor") or 1)
		first_cand, first_qty = allocations[0]
		row.azzir_row_from_sister = 1
		row.azzir_supply_company = first_cand.company
		row.azzir_supply_warehouse = first_cand.warehouse
		if len(allocations) > 1:
			split_happened = True
			row.qty = (first_qty / conv) if conv else first_qty
			notes.append(_("{0}: {1} from sister {2} ({3})").format(
				item, first_qty, first_cand.company, first_cand.warehouse))
			for cand, qty_taken in allocations[1:]:
				new_row = _split_row_copy(doc, row, qty_taken, conv)
				new_row.azzir_row_from_sister = 1
				new_row.azzir_supply_company = cand.company
				new_row.azzir_supply_warehouse = cand.warehouse
				notes.append(_("{0}: {1} from sister {2} ({3})").format(
					item, qty_taken, cand.company, cand.warehouse))
		else:
			notes.append(_("{0}: bought from sister {1} ({2})").format(
				item, first_cand.company, first_cand.warehouse))

	if split_happened:
		doc.calculate_taxes_and_totals()

	if notes:
		frappe.msgprint(
			_("Your warehouse was short, so we initiated purchase from a sister company:<br>{0}")
			.format("<br>".join(notes)),
			title=_("Auto purchase from sister"), indicator="blue",
		)
