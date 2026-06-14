# Copyright (c) 2026, Azzir and contributors
# For license information, please see license.txt
"""Enforce per-row Maximum Order Qty (buying) and Maximum Sales Qty (selling)."""

import frappe
from frappe import _
from frappe.utils import flt


def validate_buying(doc, method=None):
	_enforce(doc, "max_order_qty", _("ordered or requested"))


def validate_selling(doc, method=None):
	_enforce(doc, "max_sale_qty", _("sold"))


def _enforce(doc, field, action):
	limits = {}
	for row in doc.get("items") or []:
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
