# Copyright (c) 2026, Azzir and contributors
# For license information, please see license.txt
"""Cost-center scoping for warehouse SELECTION.

Each Warehouse carries a cost center (`azzir_cost_center`). Each user is assigned
one or more cost centers via User Permission ("Cost Center"). A user may SEE every
warehouse's stock, but may only SELECT a warehouse whose cost center is one they
are assigned to. Nothing is hardcoded — it is driven entirely by the data.
"""

import frappe
from frappe.utils import flt

COST_CENTER = "Cost Center"


def _field_ready() -> bool:
	"""The azzir_cost_center field exists on Warehouse (migrate has run). Until then
	the feature is simply inactive so nothing errors."""
	try:
		return frappe.get_meta("Warehouse").has_field("azzir_cost_center")
	except Exception:
		return False


def allowed_cost_centers(user: str | None = None) -> set | None:
	"""Cost centers the user is allowed to transact in, from their User Permissions.

	Returns None = NO restriction (Administrator, System Manager, a user with no
	Cost Center user permission, or before the field is migrated) -> may select any
	warehouse. A set = only those.
	"""
	if not _field_ready():
		return None
	user = user or frappe.session.user
	if user == "Administrator" or "System Manager" in frappe.get_roles(user):
		return None
	ccs = frappe.get_all(
		"User Permission",
		filters={"user": user, "allow": COST_CENTER},
		pluck="for_value",
	)
	return set(ccs) if ccs else None


def warehouse_permission_bounds(user: str | None = None) -> list | None:
	"""(lft, rgt) ranges of the warehouses the user holds a Warehouse User Permission
	for. Because warehouses are a tree, a permission on a GROUP warehouse thus covers
	every child warehouse beneath it.

	Returns None = this dimension does NOT restrict (Administrator, System Manager, or
	a user with no Warehouse user permission). A list = only warehouses inside those
	ranges may be selected.
	"""
	user = user or frappe.session.user
	if user == "Administrator" or "System Manager" in frappe.get_roles(user):
		return None
	names = frappe.get_all(
		"User Permission", filters={"user": user, "allow": "Warehouse"}, pluck="for_value"
	)
	if not names:
		return None
	bounds = []
	for w in names:
		b = frappe.db.get_value("Warehouse", w, ["lft", "rgt"])
		if b and b[0] is not None:
			bounds.append((b[0], b[1]))
	return bounds or None


def cost_center_bounds(allowed: set | None) -> list | None:
	"""(lft, rgt) ranges of the warehouses tagged with one of the user's cost centres.
	Because warehouses are a tree, a cost centre set on a GROUP warehouse thus covers
	every child warehouse beneath it — just like a Warehouse User Permission on a group.

	Returns None when the cost-centre dimension does NOT restrict (user is unrestricted);
	[] when the user HAS cost centres but none are tagged on any warehouse (grants
	nothing); else the list of ranges.
	"""
	if allowed is None:
		return None
	rows = frappe.get_all(
		"Warehouse", filters={"azzir_cost_center": ["in", list(allowed)]}, fields=["lft", "rgt"]
	)
	return [(r.lft, r.rgt) for r in rows if r.lft is not None]


def _within_bounds(lft, rgt, bounds) -> bool:
	if not bounds or lft is None:
		return False
	return any(lft >= lo and rgt <= hi for lo, hi in bounds)


def _bounds_sql(bounds, vals: dict, prefix: str) -> str | None:
	"""SQL OR-fragment: warehouse `w` lies inside one of these ancestor-or-self tree
	ranges. Empty/None bounds -> None (contributes nothing). Fills `vals`."""
	if not bounds:
		return None
	ors = []
	for i, (lo, hi) in enumerate(bounds):
		ors.append("(w.lft >= %({p}lo{i})s and w.rgt <= %({p}hi{i})s)".format(p=prefix, i=i))
		vals["%slo%d" % (prefix, i)] = lo
		vals["%shi%d" % (prefix, i)] = hi
	return "(" + " or ".join(ors) + ")"


def warehouse_selectable(
	cost_center: str | None, lft, rgt, cc_allowed: set | None, wh_bounds: list | None
) -> bool:
	"""Whether a (leaf) warehouse may be SELECTED, across BOTH granting dimensions:

	* a Cost Center the user is assigned (cc_allowed), and/or
	* a Warehouse User Permission covering this warehouse — directly, or via one of
	  its ancestor GROUP warehouses (wh_bounds).

	Both dimensions None = the user is unrestricted. Otherwise the warehouse is
	selectable if it satisfies AT LEAST ONE dimension the user actually has (union),
	so granting either a cost center or a group warehouse opens it up.
	"""
	if cc_allowed is None and wh_bounds is None:
		return True
	if cc_allowed is not None and cost_center and cost_center in cc_allowed:
		return True
	return _within_bounds(lft, rgt, wh_bounds)


def is_selectable(warehouse_cost_center: str | None, allowed: set | None) -> bool:
	"""Back-compat: cost-center-only selectability. Prefer warehouse_selectable()."""
	if allowed is None:
		return True
	return bool(warehouse_cost_center) and warehouse_cost_center in allowed


@frappe.whitelist()
def user_warehouse_for_item(item_code: str | None = None, company: str | None = None) -> str | None:
	"""A warehouse the user is allowed to select (attached to one of their assigned
	cost centers), used to auto-fill the row warehouse instead of the item's default.
	When an item is given, returns one that actually HOLDS it (in stock); if none of
	the user's warehouses have stock, returns None so the row is left blank for a
	manual pick. Returns None too if the user is unrestricted (keep ERPNext's own
	default) or has no cost-centre warehouses."""
	# Warehouses the user may select (Warehouse permission wins over cost centre).
	bounds = _effective_bounds()
	if not bounds:  # None (unrestricted -> keep ERPNext default) or [] (nothing)
		return None
	frag = _bounds_sql(bounds, (vals := {}), "g")
	if not frag:
		return None
	conds = ["w.disabled = 0", "w.is_group = 0", frag]
	if company:
		conds.append("w.company = %(co)s")
		vals["co"] = company
	warehouses = frappe.db.sql_list(
		"select w.name from `tabWarehouse` w where " + " and ".join(conds) + " order by w.name", vals
	)
	if not warehouses:
		return None
	if item_code:
		# Only auto-fill a warehouse that actually HOLDS this item. If none of the
		# user's warehouses have stock, return None so the row is left blank and the
		# user consciously picks one from the dropdown (which still lists every
		# allowed warehouse, zero-stock included).
		for w in warehouses:
			if flt(frappe.db.get_value("Bin", {"item_code": item_code, "warehouse": w}, "actual_qty")) > 0:
				return w
		return None
	return warehouses[0]


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def warehouse_query(
	doctype: str, txt: str, searchfield: str, start: int, page_len: int, filters: dict | str | None
) -> list:
	"""Link-field query for warehouse fields: shows only warehouses the user is
	allowed to SELECT (attached to a cost center they're assigned; all if the user
	is unrestricted). Honours an incoming company / is_group filter."""
	filters = frappe.parse_json(filters) if isinstance(filters, str) else (filters or {})

	conds = ["w.disabled = 0", "(w.name like %(txt)s or w.warehouse_name like %(txt)s)"]
	vals = {"txt": "%%%s%%" % (txt or ""), "start": start, "page_len": page_len}
	if filters.get("company"):
		conds.append("w.company = %(company)s")
		vals["company"] = filters["company"]
	if filters.get("is_group") is not None:
		conds.append("w.is_group = %(is_group)s")
		vals["is_group"] = frappe.utils.cint(filters.get("is_group"))
	# Selection is granted by a Cost Center and/or a Warehouse user permission — either
	# one set on a GROUP warehouse cascades to its children via lft/rgt tree bounds.
	grant = _grant_conditions(vals)
	if grant:
		conds.append(grant)

	return frappe.db.sql(
		"select w.name from `tabWarehouse` w where "
		+ " and ".join(conds)
		+ " order by w.name limit %(start)s, %(page_len)s",
		vals,
	)


def _effective_bounds() -> list | None:
	"""Warehouse tree ranges the current user may SELECT, or None when unrestricted.

	Priority: an explicit Warehouse User Permission WINS. When the user holds one,
	ONLY those ranges apply — so the /sales picker matches the desk, which also honours
	the Warehouse permission and ignores the cost centre. A user with NO Warehouse
	permission falls back to their cost-centre ranges (a cost centre on a group still
	cascades to its children). Either dimension set on a GROUP warehouse covers every
	child beneath it (lft/rgt)."""
	wh_bounds = warehouse_permission_bounds()  # None = no Warehouse user permission
	if wh_bounds is not None:
		return wh_bounds  # explicit warehouse permission -> use it alone
	return cost_center_bounds(allowed_cost_centers())  # None / [] / [ranges]


def _grant_conditions(vals: dict) -> str | None:
	"""SQL fragment for 'this warehouse is selectable by the current user', or None
	when the user is unrestricted (so callers add no condition). Fills `vals`."""
	bounds = _effective_bounds()
	if bounds is None:
		return None  # unrestricted
	frag = _bounds_sql(bounds, vals, "g")
	return frag if frag else "1=0"  # [] -> nothing is selectable


@frappe.whitelist()
def warehouse_search(txt: str | None = None, company: str | None = None) -> list:
	"""Portal (/sales) warehouse picker: only leaf warehouses the current user may
	SELECT (cost-center / warehouse-permission scoped; all if unrestricted)."""
	conds = ["w.disabled = 0", "w.is_group = 0", "(w.name like %(t)s or w.warehouse_name like %(t)s)"]
	vals = {"t": "%%%s%%" % (txt or "")}
	if company:
		conds.append("w.company = %(co)s")
		vals["co"] = company
	grant = _grant_conditions(vals)
	if grant:
		conds.append(grant)
	return frappe.db.sql(
		"select w.name, w.warehouse_name from `tabWarehouse` w where "
		+ " and ".join(conds) + " order by w.name limit 25",
		vals, as_dict=True,
	)


@frappe.whitelist()
def my_allowed_warehouses(company: str | None = None) -> list | None:
	"""Leaf warehouse names the current user may SELECT (cost-center / warehouse scoped),
	or None when the user is unrestricted (may pick any). Used by the /sales portal to
	scope its warehouse pickers."""
	vals: dict = {}
	grant = _grant_conditions(vals)
	if grant is None:
		return None  # unrestricted — pick any
	conds = ["w.disabled = 0", "w.is_group = 0", grant]
	if company:
		conds.append("w.company = %(co)s")
		vals["co"] = company
	return frappe.db.sql_list("select w.name from `tabWarehouse` w where " + " and ".join(conds), vals)


def enforce_warehouse_selection(doc, method=None):
	"""Server-side guarantee (desk, portal AND API): reject any row whose warehouse the
	user is not allowed to SELECT. Unrestricted users (Admin/System Manager, or no cost
	center / warehouse permission) pass. Sister-sourced rows are skipped (their warehouse
	is system-managed). Only leaf warehouses are policed.

	Quotations post no stock and often inherit an item's default warehouse the user can't
	use — so they are not policed here; enforcement applies where stock actually moves
	(Sales Invoice / Delivery Note / Stock Entry / Purchase Receipt)."""
	if getattr(doc, "doctype", None) == "Quotation":
		return
	if not _field_ready():
		return
	all_bounds = _effective_bounds()  # Warehouse permission wins over cost centre
	if all_bounds is None:
		return  # unrestricted user — nothing to enforce

	checked = {}

	def ok(wh):
		if not wh:
			return True
		if wh in checked:
			return checked[wh]
		info = frappe.db.get_value(
			"Warehouse", wh, ["lft", "rgt", "is_group"], as_dict=True
		)
		# unknown or group node -> don't police (stock posts to leaves)
		res = True if (not info or info.is_group) else _within_bounds(info.lft, info.rgt, all_bounds)
		checked[wh] = res
		return res

	bad = set()
	for row in doc.get("items") or []:
		if row.get("azzir_row_from_sister"):
			continue  # sister/landing warehouse is system-managed
		for f in ("warehouse", "s_warehouse", "t_warehouse"):
			wh = row.get(f)
			if wh and not ok(wh):
				bad.add(wh)
	for f in ("set_warehouse", "from_warehouse", "to_warehouse"):
		wh = doc.get(f)
		if wh and not ok(wh):
			bad.add(wh)

	if bad:
		frappe.throw(
			frappe._("You are not allowed to use warehouse(s): {0}. They are not in your cost centre.")
			.format(", ".join(sorted(bad))),
			title=frappe._("Warehouse not allowed"),
		)
