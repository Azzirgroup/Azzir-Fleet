# Copyright (c) 2026, Azzir and contributors
# For license information, please see license.txt
"""Enforce a globally-unique Supplier Invoice No on Purchase Invoice."""

import frappe
from frappe import _


def validate_unique_bill_no(doc, method=None):
	bill_no = (doc.get("bill_no") or "").strip()
	if not bill_no:
		return

	existing = frappe.db.get_value(
		"Purchase Invoice",
		{
			"bill_no": bill_no,
			"name": ["!=", doc.name or ""],
			"docstatus": ["<", 2],  # ignore cancelled invoices
		},
		"name",
	)
	if existing:
		frappe.throw(
			_("Supplier Invoice No <b>{0}</b> is already used on Purchase Invoice {1}.").format(
				bill_no, existing
			),
			title=_("Duplicate Supplier Invoice No"),
		)
