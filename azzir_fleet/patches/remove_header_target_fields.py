# Copyright (c) 2026, Azzir and contributors
# For license information, please see license.txt
"""Purchase cycle moved to a per-row trigger (Purchase Order/Receipt/Invoice Item.
azzir_row_to_target). Remove the now-unused HEADER Target Company / Target Warehouse
defaults from Purchase Order, Purchase Receipt and Purchase Invoice."""

import frappe


def execute():
	names = []
	for dt in ("Purchase Order", "Purchase Receipt", "Purchase Invoice"):
		names += [f"{dt}-azzir_target_company", f"{dt}-azzir_target_warehouse"]
	for name in names:
		if frappe.db.exists("Custom Field", name):
			frappe.delete_doc("Custom Field", name, ignore_permissions=True, force=True)
