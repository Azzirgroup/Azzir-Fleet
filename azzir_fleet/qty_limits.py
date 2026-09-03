# Copyright (c) 2026, Azzir and contributors
# For license information, please see license.txt
"""Enforce per-row Maximum Order Qty (buying) and Maximum Sales Qty (selling)."""

import frappe
from frappe import _
from frappe.utils import flt

OVERRIDE_ROLE = "Azzir Stock Override"


def _can_override():
	"""Senior users with the override role bypass the min/max/stock limits."""
	return OVERRIDE_ROLE in frappe.get_roles()


def validate_buying(doc, method=None):
	# Purchasing is intentionally UNRESTRICTED: users may order any quantity — below
	# the Minimum Order Qty or above the Maximum Order Qty. Min/Max Order Qty now only
	# drive the Reorder Level Report, they are not a purchase floor/ceiling. (Re-enable
	# the ceiling by restoring the _enforce call below.)
	return
	_enforce(doc, "max_order_qty", _("ordered or requested"))  # noqa: unreachable


def validate_selling(doc, method=None):
	if _can_override():
		return
	_enforce(doc, "max_sale_qty", _("sold"))


def validate_sales_stock(doc, method=None):
	"""Block billing more of an item than is in stock (Bin actual_qty) for the
	row's warehouse. Skipped when the invoice updates stock (ERPNext handles it).
	"""
	if doc.get("update_stock") or _can_override():
		return

	# Sum this invoice's qty per (item, warehouse) — covers the same item on
	# multiple rows.
	sister_doc = doc.get("azzir_buy_from_sister")
	needed = {}
	for row in doc.get("items") or []:
		# A 'From Sister' line receives its stock via the intercompany transfer at
		# submit — the draft check would wrongly see the landing warehouse as empty.
		if sister_doc and row.get("azzir_row_from_sister"):
			continue
		code, wh = row.get("item_code"), row.get("warehouse")
		if not code or not wh:
			continue
		if not frappe.get_cached_value("Item", code, "is_stock_item"):
			continue
		needed[(code, wh)] = needed.get((code, wh), 0) + flt(row.qty)

	for (code, wh), this_qty in needed.items():
		available = flt(
			frappe.db.get_value("Bin", {"item_code": code, "warehouse": wh}, "actual_qty")
		)
		if this_qty > available:
			frappe.throw(
				_(
					"Item {0} in {1}: only {2} in stock, but this invoice bills {3}. "
					"You cannot bill more than the available stock."
				).format(frappe.bold(code), wh, available, this_qty),
				title=_("Insufficient Stock"),
			)


def _enforce(doc, field, action):
	limits = {}
	sister_doc = doc.get("azzir_buy_from_sister")
	for row in doc.get("items") or []:
		if sister_doc and row.get("azzir_row_from_sister"):
			continue  # sister line — sourced from another company, not our sales cap
		code = row.get("item_code")
		if not code:
			continue
		if code not in limits:
			limits[code] = flt(frappe.get_cached_value("Item", code, field))
		limit = limits[code]
		if limit and flt(row.get("qty")) > limit:
			frappe.throw(
				_("Row #{0}: Item {1} cannot be {2} in quantity {3} — the maximum allowed is {4}.").format(
					row.idx, frappe.bold(code), action, flt(row.get("qty")), limit
				)
			)
