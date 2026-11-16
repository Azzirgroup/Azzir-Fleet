# Copyright (c) 2026, Azzir and contributors
# For license information, please see license.txt
"""Keeps azzir_is_sales_invoice as the exact opposite of is_return, so the list
view's standard filter bar can offer it as its own checkbox (see setup.py's
custom field and public/js/sales_invoice_list.js for the mutual-exclusion UI)."""

import frappe


def sync_is_sales_invoice(doc, method=None):
	if doc.meta.has_field("azzir_is_sales_invoice"):
		doc.azzir_is_sales_invoice = 0 if doc.is_return else 1


def backfill():
	"""One-time (also safe to re-run) correction for existing invoices."""
	if not frappe.db.has_column("Sales Invoice", "azzir_is_sales_invoice"):
		return
	rows = frappe.db.sql(
		"""
		select name, is_return from `tabSales Invoice`
		where ifnull(azzir_is_sales_invoice, -1) != if(is_return = 1, 0, 1)
		""",
		as_dict=True,
	)
	for i, r in enumerate(rows):
		frappe.db.set_value(
			"Sales Invoice", r.name, "azzir_is_sales_invoice", 0 if r.is_return else 1,
			update_modified=False,
		)
		if i % 500 == 0:
			frappe.db.commit()
	frappe.db.commit()
