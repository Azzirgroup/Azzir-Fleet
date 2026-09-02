# Copyright (c) 2026, Azzir and contributors
# For license information, please see license.txt
"""One-time: for every Employee already linked to a user, set that user's default
Company to the employee's company, so existing users immediately get their company
auto-filled on new Quotations / Sales Invoices (going forward the Employee on_update
hook keeps it in sync)."""

import frappe


def execute():
	for emp in frappe.get_all(
		"Employee",
		filters={"user_id": ["is", "set"], "company": ["is", "set"]},
		fields=["user_id", "company"],
	):
		user, company = emp.user_id, emp.company
		if not user or not company or user in ("Administrator", "Guest"):
			continue
		if frappe.defaults.get_user_default("company", user) != company:
			frappe.defaults.set_user_default("company", company, user)
