# Copyright (c) 2026, Azzir and contributors
# For license information, please see license.txt
"""Make the Item list view resolve old codes.

When you type an old code in the Item list's ID filter, the standard query
(`name LIKE '%old%'`) finds nothing because the item's name is the new code now.
These overrides expand such a filter to also include the resolved current item,
so the list shows the item under its new code.
"""

import json

import frappe

CHILD_DT = "Item Code Entry"


@frappe.whitelist()
@frappe.read_only()
def get():
	_expand_item_alias_filters()
	from frappe.desk.reportview import get as _orig

	return _orig()


@frappe.whitelist()
@frappe.read_only()
def get_list():
	_expand_item_alias_filters()
	from frappe.desk.reportview import get_list as _orig

	return _orig()


@frappe.whitelist()
@frappe.read_only()
def get_count():
	_expand_item_alias_filters()
	from frappe.desk.reportview import get_count as _orig

	return _orig()


def _expand_item_alias_filters():
	fd = frappe.form_dict
	if fd.get("doctype") != "Item":
		return

	filters = fd.get("filters")
	if not filters:
		return
	try:
		parsed = json.loads(filters) if isinstance(filters, str) else filters
	except Exception:
		return
	if not isinstance(parsed, list):
		return

	kept = []
	extra_or = []
	changed = False

	for f in parsed:
		field, op, value = _parse_filter(f)
		if field == "name" and op in ("like", "=") and value:
			currents = _resolve_currents(value, op)
			if currents:
				# keep the original name match, OR-ed with the resolved item(s)
				extra_or.append(["Item", "name", op, value])
				for c in currents:
					extra_or.append(["Item", "name", "=", c])
				changed = True
				continue
		kept.append(f)

	if not changed:
		return

	fd["filters"] = json.dumps(kept)
	existing_or = fd.get("or_filters")
	try:
		or_parsed = json.loads(existing_or) if isinstance(existing_or, str) else (existing_or or [])
	except Exception:
		or_parsed = []
	or_parsed.extend(extra_or)
	fd["or_filters"] = json.dumps(or_parsed)


def _parse_filter(f):
	"""Return (field, op, value) from a filter that may be [dt, field, op, val] or [field, op, val]."""
	if not isinstance(f, (list, tuple)):
		return None, None, None
	if len(f) == 4:
		return f[1], f[2], f[3]
	if len(f) == 3:
		return f[0], f[1], f[2]
	return None, None, None


def _resolve_currents(value, op):
	"""Current item codes whose OLD codes match the typed value (partial or exact)."""
	inner = str(value).strip("%")
	if not inner:
		return []
	code_filter = ["like", f"%{inner}%"] if op == "like" else inner
	rows = frappe.get_all(
		CHILD_DT,
		filters={"code": code_filter, "is_primary": 0, "parenttype": "Item"},
		fields=["parent"],
		limit=20,
	)
	return list({r["parent"] for r in rows})
