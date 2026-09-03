# Copyright (c) 2026, Azzir and contributors
# For license information, please see license.txt
"""Buy-from-sister moved to a per-row trigger (Sales Invoice/Quotation Item.
azzir_row_from_sister). Remove the now-unused HEADER fields from Quotation and
Sales Invoice."""

import frappe


def execute():
	names = [
		"Quotation-azzir_buy_from_sister",
		"Quotation-azzir_supply_company",
		"Quotation-azzir_supply_warehouse",
		"Sales Invoice-azzir_buy_from_sister",
		"Sales Invoice-azzir_supply_company",
		"Sales Invoice-azzir_supply_warehouse",
	]
	for name in names:
		if frappe.db.exists("Custom Field", name):
			frappe.delete_doc("Custom Field", name, ignore_permissions=True, force=True)
