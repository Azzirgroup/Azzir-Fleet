# Copyright (c) 2026, Azzir and contributors
# For license information, please see license.txt
"""Warehouse rules for the sales flow.

Warehouse is mandatory on any line carrying a STOCK item (service / non-stock
lines are exempt). Users pick the actual warehouse directly."""

import frappe
from frappe import _


def require_warehouse_for_stock(doc, method=None):
	"""Warehouse is mandatory on every line carrying a STOCK item. Service /
	non-stock lines are exempt. Hard server-side guard behind the field's
	mandatory_depends_on asterisk."""
	missing = []
	for idx, row in enumerate(doc.get("items") or [], start=1):
		# A 'Buy From Sister Company' line sources from the sister warehouse and gets
		# the landing warehouse in set_landing_warehouse — don't demand a warehouse.
		if row.get("azzir_row_from_sister"):
			continue
		code = row.get("item_code")
		if not code or not frappe.get_cached_value("Item", code, "is_stock_item"):
			continue
		if not row.get("warehouse"):
			missing.append((idx, code))
	if missing:
		lines = "<br>".join(
			_("Row #{0}: Warehouse is required for stock item {1}").format(idx, frappe.bold(code))
			for (idx, code) in missing
		)
		frappe.throw(lines, title=_("Warehouse Required"))
