# Copyright (c) 2026, Azzir and contributors
# For license information, please see license.txt
"""Alias-aware search middleware (single source of truth = Item.azzir_alias_codes).

Old codes live as non-primary rows in the Item Code Entry child table. This
makes every Link-to-Item field (Sales Order, Invoice, Delivery Note, Purchase
docs, Item list, ...) resolve those old codes to the current item and tell the
user the live code.
"""

import frappe

CHILD_DT = "Item Code Entry"


# --------------------------------------------------------------------------- #
# Search middleware (overrides frappe.desk.search.search_link via hooks)
# --------------------------------------------------------------------------- #
@frappe.whitelist()
def search_link(
	doctype: str,
	txt: str,
	query: str | None = None,
	filters: str | dict | list | None = None,
	page_length: int = 10,
	searchfield: str | None = None,
	reference_doctype: str | None = None,
	ignore_user_permissions: bool = False,
	*,
	link_fieldname: str | None = None,
):
	from frappe.desk.search import search_link as _orig_search_link

	results = _orig_search_link(
		doctype,
		txt,
		query=query,
		filters=filters,
		page_length=page_length,
		searchfield=searchfield,
		reference_doctype=reference_doctype,
		ignore_user_permissions=ignore_user_permissions,
		link_fieldname=link_fieldname,
	)

	if doctype == "Item" and txt:
		results = _inject_item_aliases(results, txt)

	return results


def _inject_item_aliases(results, txt):
	"""Add/flag results so old codes resolve to the current item (partial match)."""
	existing_values = {r.get("value") for r in results}

	aliases = frappe.get_all(
		CHILD_DT,
		filters={"code": ["like", f"%{txt}%"], "is_primary": 0, "parenttype": "Item"},
		fields=["code as old_code", "parent as item"],
		limit=10,
	)

	for a in aliases:
		current = a.get("item")
		if not current:
			continue
		note = f'↺ old code: {a["old_code"]}'
		if current in existing_values:
			for r in results:
				if r.get("value") == current:
					desc = r.get("description") or ""
					if "↺ old code:" not in desc:
						r["description"] = f"{note} · {desc}".strip(" ·")
					break
		else:
			results.insert(0, {"value": current, "description": note, "label": current})
			existing_values.add(current)

	return results


# --------------------------------------------------------------------------- #
# item_query override — makes report MultiSelectList item filters (Stock Ledger,
# Stock Balance, etc.) and any direct item_query caller show old codes too.
# (Link fields call item_query server-side via search_link, so they're untouched
# and never double-injected.)
# --------------------------------------------------------------------------- #
@frappe.whitelist()
def item_query(
	doctype: str,
	txt: str,
	searchfield: str,
	start: int,
	page_len: int,
	filters: str | dict | list | None = None,
	as_dict: bool = False,
):
	from erpnext.controllers.queries import item_query as _orig

	results = _orig(doctype, txt, searchfield, start, page_len, filters, as_dict=as_dict)
	if not txt:
		return results

	results = list(results or [])
	existing = set()
	for r in results:
		key = r.get("name") if isinstance(r, dict) else (r[0] if r else None)
		if key:
			existing.add(key)

	aliases = frappe.get_all(
		CHILD_DT,
		filters={"code": ["like", f"%{txt}%"], "is_primary": 0, "parenttype": "Item"},
		fields=["code as old_code", "parent as item"],
		limit=10,
	)
	for a in aliases:
		current = a.get("item")
		if not current or current in existing:
			continue
		existing.add(current)
		note = f"↺ old code: {a['old_code']}"
		if as_dict:
			results.insert(0, {"name": current, "item_name": note})
		else:
			results.insert(0, (current, note))

	return results


# --------------------------------------------------------------------------- #
# Helper API (used by POS / client JS / anywhere)
# --------------------------------------------------------------------------- #
def get_item_old_codes(item_code):
	"""Comma-joined alternative (old) codes of an item — for print formats."""
	if not item_code:
		return ""
	codes = frappe.get_all(
		CHILD_DT,
		filters={"parent": item_code, "parenttype": "Item", "is_primary": 0},
		pluck="code",
		order_by="changed_on desc",
	)
	return ", ".join(codes)


@frappe.whitelist()
def resolve_code(code: str):
	"""Return the current item for any code (current or old). None if unknown."""
	if not code:
		return None
	if frappe.db.exists("Item", code):
		return {"item": code, "current_code": code, "is_alias": False, "old_code": None}

	parent = frappe.db.get_value(
		CHILD_DT, {"code": code, "is_primary": 0, "parenttype": "Item"}, "parent"
	)
	if parent:
		return {"item": parent, "current_code": parent, "is_alias": True, "old_code": code}
	return None
