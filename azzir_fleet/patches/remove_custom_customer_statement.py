# Copyright (c) 2026, Azzir and contributors
"""Remove the old "Customer Statement" Report entirely.

It was tried first as a DB-only Custom Report, then as a file Script Report,
but the query-report loader is broken on Frappe 17-dev (getdoctype 500). The
statement now lives as the `customer-statement` desk page instead, so drop the
report so the dead /app/query-report/Customer Statement route stops existing.
Idempotent — a no-op once the report is gone."""

import frappe


def execute():
	if frappe.db.exists("Report", "Customer Statement"):
		frappe.delete_doc("Report", "Customer Statement", force=True, ignore_permissions=True)
