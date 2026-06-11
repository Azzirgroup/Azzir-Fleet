# Copyright (c) 2026, Azzir and contributors
# For license information, please see license.txt
"""Item code management via a child table on Item (azzir_alias_codes).

Each Item carries a list of its codes. Exactly one row is the Primary (the live
item_code / document name); the rest are old codes that resolve to the item.

Rules enforced here:
- A code can never be reused: creating/renaming an item onto a code already held
  by another item (as its name OR as one of its old codes) is blocked.
- Setting a different row as Primary renames the item to that code; the previous
  primary becomes an alias automatically.
- Renames (manual or via the Change Tool) auto-add the new code as Primary and
  keep the old code as an alias row.
"""

import frappe
from frappe import _
from frappe.utils import now_datetime

CHILD_FIELD = "azzir_alias_codes"
CHILD_DT = "Item Code Entry"


# --------------------------------------------------------------------------- #
# Reservation helper
# --------------------------------------------------------------------------- #
def code_owner(code):
	"""Return the item that owns `code` (as its name or one of its codes), else None."""
	if not code:
		return None
	parent = frappe.db.get_value(CHILD_DT, {"code": code, "parenttype": "Item"}, "parent")
	if parent:
		return parent
	if frappe.db.exists("Item", code):
		return code
	return None


# --------------------------------------------------------------------------- #
# Item.validate
# --------------------------------------------------------------------------- #
def validate(doc, method=None):
	current = doc.name or doc.get("item_code")
	if not current:
		return

	# New item whose code already belongs to a live item.
	if doc.is_new() and frappe.db.exists("Item", current):
		frappe.throw(_("An item with code '{0}' already exists.").format(current))

	rows = doc.get(CHILD_FIELD) or []

	# Ensure at least the current code exists as the Primary row.
	if not rows:
		doc.append(
			CHILD_FIELD,
			{"code": current, "is_primary": 1, "source": "Initial", "changed_on": now_datetime()},
		)
		rows = doc.get(CHILD_FIELD)

	# Normalise + reject duplicates within the table.
	seen = set()
	for r in rows:
		c = (r.code or "").strip()
		if not c:
			frappe.throw(_("Code is required in the Item Codes table"))
		r.code = c
		key = c.lower()
		if key in seen:
			frappe.throw(_("Duplicate code '{0}' in the Item Codes table").format(c))
		seen.add(key)

	# Reservation: no code may belong to another item.
	for r in rows:
		owner = code_owner(r.code)
		if owner and owner != current:
			frappe.throw(
				_("Code '{0}' is already used by item {1}. Codes cannot be reused.").format(
					r.code, owner
				)
			)

	# Exactly one Primary.
	primaries = [r for r in rows if r.is_primary]
	if len(primaries) > 1:
		frappe.throw(_("Only one code can be marked Primary"))
	if not primaries:
		match = next((r for r in rows if r.code.lower() == current.lower()), None)
		(match or rows[0]).is_primary = 1

	# Never lose the current code — keep it as an alias row if Primary moved away.
	if current.lower() not in seen:
		doc.append(
			CHILD_FIELD,
			{"code": current, "is_primary": 0, "source": "Rename", "changed_on": now_datetime()},
		)


# --------------------------------------------------------------------------- #
# Item.on_update  — rename if the Primary code differs from the current name
# --------------------------------------------------------------------------- #
def on_update(doc, method=None):
	if doc.flags.get("azzir_in_rename"):
		return

	target = None
	for r in doc.get(CHILD_FIELD) or []:
		if r.is_primary:
			target = r.code
			break

	if target and target != doc.name:
		doc.flags.azzir_in_rename = True
		frappe.rename_doc(
			"Item", doc.name, target, force=True, show_alert=False, rebuild_search=False
		)


# --------------------------------------------------------------------------- #
# Item.after_rename — reconcile the child rows (single source of truth)
# --------------------------------------------------------------------------- #
def after_rename(doc, method=None, old=None, new=None, merge=False):
	if not old or not new or old == new:
		return

	# ERPNext's before_rename syncs item_name to the new code when item_name == old
	# code. Honour "rename the code only" — keep the descriptive Item Name unchanged.
	if not merge and frappe.db.get_value("Item", new, "item_name") == new:
		frappe.db.set_value("Item", new, "item_name", old, update_modified=False)

	now = now_datetime()
	# Rows moved to parent=new during rename. Demote all, then set new/old.
	frappe.db.sql(
		f"update `tab{CHILD_DT}` set is_primary=0 where parent=%s and parenttype='Item'",
		new,
	)
	_ensure_row(new, new, is_primary=1, source="Rename", now=now)
	_ensure_row(new, old, is_primary=0, source="Rename", now=now)


def _ensure_row(parent, code, is_primary, source, now):
	name = frappe.db.get_value(
		CHILD_DT, {"parent": parent, "parenttype": "Item", "code": code}, "name"
	)
	if name:
		frappe.db.set_value(
			CHILD_DT, name, {"is_primary": is_primary, "changed_on": now}, update_modified=False
		)
	else:
		row = frappe.get_doc(
			{
				"doctype": CHILD_DT,
				"parent": parent,
				"parenttype": "Item",
				"parentfield": CHILD_FIELD,
				"code": code,
				"is_primary": is_primary,
				"source": source,
				"changed_on": now,
			}
		)
		row.flags.ignore_permissions = True
		row.insert(ignore_permissions=True)
