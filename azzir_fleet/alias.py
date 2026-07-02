# Copyright (c) 2026, Azzir and contributors
# For license information, please see license.txt
"""Alias-aware search middleware (single source of truth = Item.azzir_alias_codes).

Old codes live as non-primary rows in the Item Code Entry child table. This
makes every Link-to-Item field (Sales Order, Invoice, Delivery Note, Purchase
docs, Item list, ...) resolve those old codes to the current item and tell the
user the live code.
"""

import re

import frappe

CHILD_DT = "Item Code Entry"

# Characters ignored when matching codes ("100-3402" == "1003402" == "100 3402").
_NORM_RE = re.compile(r"[^a-z0-9]")


def _norm(value):
	return _NORM_RE.sub("", (value or "").lower())


def _norm_sql(col):
	"""SQL expression that strips separators and lowercases a column."""
	expr = f"lower({col})"
	for ch in ("-", " ", ".", "/", "_"):
		expr = f"replace({expr}, '{ch}', '')"
	return expr


def fuzzy_item_matches(txt, limit=10):
	"""Items whose current code OR an old code matches txt ignoring separators.
	Returns list of {'item': current_code, 'old_code': old code or None}."""
	n = _norm(txt)
	if not n:
		return []
	like = f"%{n}%"
	current = frappe.db.sql(
		f"select name as item from `tabItem` where {_norm_sql('name')} like %(n)s limit {int(limit)}",
		{"n": like},
		as_dict=True,
	)
	aliases = frappe.db.sql(
		f"""select parent as item, code as old_code from `tab{CHILD_DT}`
		    where parenttype='Item' and is_primary=0 and {_norm_sql('code')} like %(n)s
		    limit {int(limit)}""",
		{"n": like},
		as_dict=True,
	)
	out = [{"item": r["item"], "old_code": None} for r in current]
	out += [{"item": r["item"], "old_code": r["old_code"]} for r in aliases]
	return out


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
	"""Add/flag results so old codes (and separator-insensitive codes) resolve to
	the current item. '100-3402' is found when the user types '1003402'."""
	existing_values = {r.get("value") for r in results}

	for m in fuzzy_item_matches(txt):
		current = m.get("item")
		if not current:
			continue
		note = f'↺ old code: {m["old_code"]}' if m.get("old_code") else None
		if current in existing_values:
			if note:
				for r in results:
					if r.get("value") == current:
						desc = r.get("description") or ""
						if "↺ old code:" not in desc:
							r["description"] = f"{note} · {desc}".strip(" ·")
						break
		else:
			results.insert(0, {"value": current, "description": note or "", "label": current})
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

	for m in fuzzy_item_matches(txt):
		current = m.get("item")
		if not current or current in existing:
			continue
		existing.add(current)
		note = f"↺ old code: {m['old_code']}" if m.get("old_code") else ""
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

	# Separator-insensitive fallback: '1003402' -> '100-3402'.
	cur = _resolve_normalized(code)
	if cur:
		return {"item": cur, "current_code": cur, "is_alias": True, "old_code": code}
	return None


def _resolve_normalized(code):
	"""Exact match ignoring separators, against item names and old codes."""
	n = _norm(code)
	if not n:
		return None
	row = frappe.db.sql(
		f"select name from `tabItem` where {_norm_sql('name')} = %(n)s limit 1", {"n": n}
	)
	if row:
		return row[0][0]
	row = frappe.db.sql(
		f"""select parent from `tab{CHILD_DT}`
		    where parenttype='Item' and is_primary=0 and {_norm_sql('code')} = %(n)s limit 1""",
		{"n": n},
	)
	return row[0][0] if row else None
