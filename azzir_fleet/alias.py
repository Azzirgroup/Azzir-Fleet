# Copyright (c) 2026, Azzir and contributors
# For license information, please see license.txt
"""Alias capture + alias-aware search middleware.

Every time an Item is renamed (manually OR via the Item Code Change Tool),
`capture_alias_after_rename` records the old code as a permanent alias that
resolves to the current item. `search_link` then makes every Link-to-Item
field (Sales Order, Invoice, Delivery Note, Purchase docs, Item list, ...)
resolve those old codes and tell the user the current code.
"""

import frappe
from frappe.utils import now_datetime


# --------------------------------------------------------------------------- #
# Alias capture (fired by hooks.doc_events Item.after_rename)
# --------------------------------------------------------------------------- #
def capture_alias_after_rename(doc, method=None, old=None, new=None, merge=False):
	if not old or not new or old == new:
		return

	_upsert_alias(old_code=old, item=new, source="Manual Rename")

	# Frappe's rename engine has already re-pointed every Link-to-Item
	# (including older Item Code Alias rows) from `old` to `new`.
	# Refresh their denormalised current_code so the whole chain shows the
	# latest code -- no matter how many times this item was renamed before.
	frappe.db.sql(
		"update `tabItem Code Alias` set current_code=%s where item=%s",
		(new, new),
	)


def _upsert_alias(old_code, item, source="Manual Rename", change_tool=None):
	if frappe.db.exists("Item Code Alias", old_code):
		alias = frappe.get_doc("Item Code Alias", old_code)
		alias.item = item
		alias.current_code = item
	else:
		alias = frappe.new_doc("Item Code Alias")
		alias.old_code = old_code
		alias.item = item
		alias.current_code = item

	alias.source = source
	alias.renamed_on = now_datetime()
	alias.renamed_by = frappe.session.user
	if change_tool:
		alias.change_tool = change_tool
	alias.flags.ignore_permissions = True
	alias.save()


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
	"""Append/flag results so old codes resolve to the current item."""
	existing_values = {r.get("value") for r in results}

	aliases = frappe.get_all(
		"Item Code Alias",
		filters={"old_code": ["like", f"%{txt}%"]},
		fields=["old_code", "item", "current_code"],
		limit=10,
	)

	for a in aliases:
		current = a.get("current_code") or a.get("item")
		if not current:
			continue
		# Keep the marker short so it doesn't overflow narrow grid cells.
		# The "↺ old code:" prefix is also the signal the client JS uses to
		# raise the "this is an old code" toast on selection.
		note = f'↺ old code: {a["old_code"]}'
		if current in existing_values:
			for r in results:
				if r.get("value") == current:
					desc = r.get("description") or ""
					if "↺ old code:" not in desc:
						r["description"] = f"{note} · {desc}".strip(" ·")
					break
		else:
			results.insert(
				0,
				{
					"value": current,
					"description": note,
					"label": current,
				},
			)
			existing_values.add(current)

	return results


# --------------------------------------------------------------------------- #
# Helper API (used by client JS / POS / anywhere)
# --------------------------------------------------------------------------- #
@frappe.whitelist()
def resolve_code(code: str):
	"""Return the current item for any code (current or old). None if unknown."""
	if not code:
		return None
	if frappe.db.exists("Item", code):
		return {"item": code, "current_code": code, "is_alias": False, "old_code": None}

	alias = frappe.db.get_value(
		"Item Code Alias",
		code,
		["item", "current_code", "old_code"],
		as_dict=True,
	)
	if alias:
		return {
			"item": alias.item,
			"current_code": alias.current_code or alias.item,
			"is_alias": True,
			"old_code": alias.old_code,
		}
	return None
