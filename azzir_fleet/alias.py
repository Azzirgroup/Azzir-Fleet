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


def get_item_previous_code(item_code):
	"""The single most recent old code of an item (the one it was renamed from) —
	for print formats that want only the last previous part number, not the whole
	alias history."""
	if not item_code:
		return ""
	return (
		frappe.db.get_value(
			CHILD_DT,
			{"parent": item_code, "parenttype": "Item", "is_primary": 0},
			"code",
			order_by="changed_on desc",
		)
		or ""
	)


def description_for_print(item_code, description, hide_alt=0):
	"""Description text for print formats. When hide_alt is set, the item's
	alternative (old) part numbers are stripped out of the text — they're often
	typed into the description itself (e.g. "TIP LONG ... 3G8354 ADAPTER J350"),
	so hiding the separate "(old code)" line alone isn't enough."""
	text = description or ""
	if not hide_alt or not item_code:
		return text

	codes = set()
	prev = get_item_previous_code(item_code)
	if prev:
		codes.add(prev)
	for c in (get_item_old_codes(item_code) or "").split(","):
		c = c.strip()
		if c:
			codes.add(c)

	# Longest first so a code that is a substring of another is handled correctly.
	for c in sorted(codes, key=len, reverse=True):
		alnum = re.sub(r"[^A-Za-z0-9]", "", c)
		if not alnum:
			continue
		# Match the code separator-insensitively (azzir codes ignore separators):
		# "100-3402", "100 3402" and "1003402" all match old code "1003402".
		pattern = (
			r"(?<![A-Za-z0-9])"
			+ r"[^A-Za-z0-9]*".join(re.escape(ch) for ch in alnum)
			+ r"(?![A-Za-z0-9])"
		)
		text = re.sub(pattern, "", text, flags=re.IGNORECASE)

	# Tidy leftovers: empty brackets, doubled spaces, stray separators.
	text = re.sub(r"\(\s*\)", "", text)
	text = re.sub(r"\s{2,}", " ", text)
	return text.strip(" -,·/")


@frappe.whitelist()
def item_search_for_spa(txt: str | None = None) -> list:
	"""Items matching by code, name, OR alternative part number — for the sales
	frontend (/sales) item picker, which otherwise only searches code/name.
	Returns [{name, item_name, alt}] where `alt` is the matched old code, if any."""
	txt = (txt or "").strip()
	seen: dict = {}
	if txt:
		like = "%%%s%%" % txt
		for r in frappe.db.sql(
			"select name, item_name from `tabItem` where disabled = 0 "
			"and (name like %(t)s or item_name like %(t)s) order by name limit 15",
			{"t": like},
			as_dict=True,
		):
			seen[r.name] = {"name": r.name, "item_name": r.item_name, "alt": None}
	# alternative part numbers (old codes)
	for m in fuzzy_item_matches(txt, limit=15):
		if m["item"] not in seen:
			seen[m["item"]] = {
				"name": m["item"],
				"item_name": frappe.db.get_value("Item", m["item"], "item_name") or m["item"],
				"alt": m.get("old_code"),
			}
	return list(seen.values())[:25]


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
