# Copyright (c) 2026, Azzir and contributors
# For license information, please see license.txt
"""Override ERPNext's get_item_details so Quotation / Sales Invoice never auto-fill
an item's default warehouse. Those documents are region-only: the user picks a
GROUP warehouse deliberately, and the field must otherwise stay empty. A warehouse
the row already has (a region the user chose, or an inherited Set Warehouse) is
left untouched."""

import frappe
from erpnext.stock.get_item_details import get_item_details as _erpnext_get_item_details

_REGION_ONLY = ("Quotation", "Sales Invoice")


@frappe.whitelist()
def get_item_details(
	ctx: dict | str | None = None,
	doc: dict | str | None = None,
	for_validate: bool = False,
	overwrite_warehouse: bool = True,
) -> dict:
	out = _erpnext_get_item_details(
		ctx, doc=doc, for_validate=for_validate, overwrite_warehouse=overwrite_warehouse
	)

	c = frappe.parse_json(ctx) if isinstance(ctx, str) else (ctx or {})
	doctype = c.get("doctype") if isinstance(c, dict) else None
	incoming_warehouse = c.get("warehouse") if isinstance(c, dict) else None

	# Region-only docs: the warehouse is whatever the row already had (the region
	# the user picked, or an inherited Set Warehouse) — never the item's default
	# bin. So force it back to the incoming value, or empty.
	if doctype in _REGION_ONLY and isinstance(out, dict):
		out["warehouse"] = incoming_warehouse or None

	return out
