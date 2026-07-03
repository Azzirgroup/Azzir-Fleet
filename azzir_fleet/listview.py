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
	# Must never break a report — fall through to the original on any problem.
	try:
		_do_expand()
	except Exception:
		pass


def _do_expand():
	fd = frappe.form_dict
	doctype = fd.get("doctype")
	if not doctype:
		return

	parsed = _parse_json(fd.get("filters"))
	if not isinstance(parsed, list) or not parsed:
		return

	has_existing_or = bool(fd.get("or_filters"))
	kept = []
	extra_or = []
	changed_or = False
	changed_inplace = False

	for f in parsed:
		field, op, value = _parse_filter(f)
		if not field or op not in ("like", "=") or not value:
			kept.append(f)
			continue
		if not _is_item_field(doctype, field):
			kept.append(f)
			continue

		currents = _resolve_currents(value, op)
		if not currents:
			kept.append(f)
			continue

		if has_existing_or:
			# Don't touch or_filters semantics — just point an exact filter at the
			# current code in place. (Partial/like is left alone in this case.)
			if op == "=":
				kept.append(_set_filter_value(f, list(currents)[0]))
				changed_inplace = True
			else:
				kept.append(f)
		else:
			extra_or.append([doctype, field, op, value])
			for c in currents:
				extra_or.append([doctype, field, "=", c])
			changed_or = True

	if changed_or:
		fd["filters"] = json.dumps(kept)
		fd["or_filters"] = json.dumps(extra_or)
	elif changed_inplace:
		fd["filters"] = json.dumps(kept)


def _is_item_field(doctype, field):
	"""True if `field` identifies an Item: the Item doctype's own name, or a
	Link-to-Item field on any other doctype."""
	if doctype == "Item":
		return field == "name"
	try:
		df = frappe.get_meta(doctype).get_field(field)
	except Exception:
		return False
	return bool(df) and df.fieldtype == "Link" and df.options == "Item"


def _parse_json(value):
	if not value:
		return None
	if isinstance(value, str):
		try:
			return json.loads(value)
		except Exception:
			return None
	return value


def _set_filter_value(f, new_value):
	f = list(f)
	f[-1] = new_value
	return f


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
	"""Current items whose code — current OR old — matches the typed value,
	ignoring separators so '1003402' resolves '100-3402'."""
	inner = str(value).strip("%")
	if not inner:
		return []
	from azzir_fleet.alias import fuzzy_item_matches

	return list({m["item"] for m in fuzzy_item_matches(inner) if m.get("item")})
