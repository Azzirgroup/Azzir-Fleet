# Copyright (c) 2026, Azzir and contributors
# For license information, please see license.txt
"""Cost-center visibility driven by the Employee 'Cost Centers' table.

The table on an Employee is the single source of truth for what that
employee's linked user is allowed to see. We mirror it into Frappe User
Permissions for "Cost Center":

  * Add a cost center to the table  -> a User Permission is created.
  * Remove it                       -> the User Permission is removed.
  * Empty table                     -> no cost-center permission at all,
                                        so the user sees everything.

Because it rides on Frappe's User Permission system, the filtering applies
automatically anywhere a document has a cost center — sales, procurement,
accounting, reports, and the Azzir Sales frontend alike."""

import frappe


def _wanted_cost_centers(doc) -> set:
	return {r.cost_center for r in (doc.get("azzir_cost_centers") or []) if r.cost_center}


def _sync_for_user(user: str, wanted: set) -> None:
	"""Reconcile a user's Cost Center User Permissions to exactly `wanted`."""
	if not user:
		return
	existing = {
		p.for_value: p.name
		for p in frappe.get_all(
			"User Permission",
			filters={"user": user, "allow": "Cost Center"},
			fields=["name", "for_value"],
		)
	}
	for value, name in existing.items():
		if value not in wanted:
			frappe.delete_doc("User Permission", name, ignore_permissions=True)
	for value in wanted:
		if value not in existing:
			frappe.get_doc({
				"doctype": "User Permission",
				"user": user,
				"allow": "Cost Center",
				"for_value": value,
				"apply_to_all_doctypes": 1,
			}).insert(ignore_permissions=True)


def sync_cost_center_permissions(doc, method=None) -> None:
	"""On Employee save: mirror the Cost Centers table into User Permissions.
	If the employee's linked user changed, clear the previous user's set too."""
	before = doc.get_doc_before_save() if not doc.is_new() else None
	old_user = before.get("user_id") if before else None
	if old_user and old_user != doc.get("user_id"):
		_sync_for_user(old_user, set())
	_sync_for_user(doc.get("user_id"), _wanted_cost_centers(doc))


def clear_cost_center_permissions(doc, method=None) -> None:
	"""On Employee delete: drop the linked user's cost-center permissions."""
	_sync_for_user(doc.get("user_id"), set())
