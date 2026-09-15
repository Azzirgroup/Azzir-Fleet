# Copyright (c) 2026, Azzir and contributors
# For license information, please see license.txt
"""Hide a Company everywhere with a single checkbox.

Tick `azzir_hidden` on a Company and it disappears from every Company list view,
link-field dropdown and report filter — for all users. System Managers (and the
Administrator) still see it so it can be un-hidden. This uses a permission query
condition, which only affects user-facing get_list / link searches / reports;
server-side `frappe.get_all` bypasses it, so internal logic and existing
documents that reference the company are unaffected.
"""

import frappe


def get_permission_query_conditions(user: str | None = None) -> str:
	user = user or frappe.session.user
	# Admins keep seeing hidden companies so they can un-hide them.
	if user == "Administrator" or "System Manager" in frappe.get_roles(user):
		return ""
	try:
		if not frappe.get_meta("Company").has_field("azzir_hidden"):
			return ""
	except Exception:
		return ""
	return "ifnull(`tabCompany`.`azzir_hidden`, 0) = 0"
