# Copyright (c) 2026, Azzir and contributors
# For license information, please see license.txt
"""POS alias-aware item search.

POS uses its own search engine, so it needs its own hook. This override runs the
normal POS search, then augments it with any items whose OLD codes match the
search term (exact OR partial), tagging them so the POS client can announce the
"old code" resolution.
"""

import frappe

CHILD_DT = "Item Code Entry"


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

	result = _orig_get_items(
		start, page_length, price_list, item_group, pos_profile, search_term=search_term
	)
	if not search_term:
		return result

	if not isinstance(result, dict):
		result = {"items": list(result or [])}
	items = result.get("items") or []
	present = {i.get("item_code"): i for i in items}

	# Old codes / separator-insensitive codes matching the term.
	from azzir_fleet.alias import fuzzy_item_matches, _norm

	term_n = _norm(search_term)
	resolved = {}  # current_code -> (old_code, is_exact_match)
	for m in fuzzy_item_matches(search_term, limit=20):
		current = m.get("item")
		old = m.get("old_code") or current
		# exact when the normalized old/current code equals the normalized term
		exact = _norm(old) == term_n or _norm(current) == term_n
		if current not in resolved or exact:
			resolved[current] = (m.get("old_code"), exact)

	for current, (old, exact) in resolved.items():
		# Only tag (-> client toast) on a COMPLETE old code. Partial typing still
		# surfaces the item, but without the "old code" announcement.
		if current in present:
			if exact:
				present[current]["azzir_old_code"] = old
				present[current]["azzir_current_code"] = current
			continue
		# Look the live item up by its current code (uses the normal SQL path).
		sub = _orig_get_items(
			start, page_length, price_list, item_group, pos_profile, search_term=current
		)
		for it in sub.get("items", []) if isinstance(sub, dict) else []:
			if it.get("item_code") == current and current not in present:
				if exact:
					it["azzir_old_code"] = old
					it["azzir_current_code"] = current
				items.append(it)
				present[current] = it

	result["items"] = items
	return result
