# Copyright (c) 2026, Azzir and contributors
# For license information, please see license.txt
"""Product Bundle helpers.

get_bundle_components powers the client-side explosion so a bundle's components
appear in the Packed Items table the moment the bundle item is selected — before
save. The server keeps them consistent on save via azzir_fleet.overrides.
"""

import json

import frappe


@frappe.whitelist()
def get_bundle_components(item_codes: str, company: str | None = None) -> dict:
	"""Map of {bundle_item_code: [components]} for the given item codes.
	Non-bundle codes are omitted. Component qty is per ONE bundle."""
	if isinstance(item_codes, str):
		item_codes = json.loads(item_codes or "[]")

	from erpnext.stock.doctype.packed_item.packed_item import (
		get_product_bundle_items,
		is_product_bundle,
	)

	out = {}
	for code in item_codes or []:
		if not code or not is_product_bundle(code):
			continue
		comps = []
		for b in get_product_bundle_items(code):
			comps.append(
				{
					"item_code": b.item_code,
					"item_name": frappe.get_cached_value("Item", b.item_code, "item_name"),
					"description": b.description
					or frappe.get_cached_value("Item", b.item_code, "description"),
					"qty": b.qty,
					"uom": b.uom or frappe.get_cached_value("Item", b.item_code, "stock_uom"),
				}
			)
		out[code] = comps
	return out
