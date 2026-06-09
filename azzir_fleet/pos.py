# Copyright (c) 2026, Azzir and contributors
# For license information, please see license.txt
"""POS alias-aware item search.

POS uses its own search engine (erpnext ... point_of_sale.get_items), not the
standard Link-field search, so it needs its own single hook. This override
resolves an old code to the current item before the original search runs, and
tags the returned items so the POS client can raise the "old code" toast.
"""

import frappe

from azzir_fleet.alias import resolve_code


@frappe.whitelist()
def get_items(
	start: int,
	page_length: int,
	price_list: str,
	item_group: str,
	pos_profile: str,
	search_term: str = "",
):
	from erpnext.selling.page.point_of_sale.point_of_sale import get_items as _orig_get_items

	old_code = None
	current = None
	if search_term:
		info = resolve_code(search_term)
		if info and info.get("is_alias"):
			old_code = info.get("old_code")
			current = info.get("current_code")
			search_term = current  # search the live code instead

	result = _orig_get_items(
		start,
		page_length,
		price_list,
		item_group,
		pos_profile,
		search_term=search_term,
	)

	# Tag results so the POS client can announce the alias resolution.
	if old_code and isinstance(result, dict) and result.get("items"):
		for item in result["items"]:
			item["azzir_old_code"] = old_code
			item["azzir_current_code"] = current

	return result
