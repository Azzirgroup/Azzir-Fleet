# Copyright (c) 2026, Azzir and contributors
# For license information, please see license.txt
"""Quotation helpers: validity default + a direct Quotation -> Sales Invoice
action (ERPNext only offers Quotation -> Sales Order -> Invoice)."""

import frappe
from frappe.model.mapper import get_mapped_doc
from frappe.utils import add_days, cint


@frappe.whitelist()
def make_sales_invoice(source_name: str, target_doc: str | None = None) -> dict:
	def set_missing_values(source, target):
		target.ignore_pricing_rule = 1  # keep the quotation's rates
		target.run_method("set_missing_values")
		target.run_method("calculate_taxes_and_totals")

	return get_mapped_doc(
		"Quotation",
		source_name,
		{
			"Quotation": {
				"doctype": "Sales Invoice",
				"field_map": {
					"name": "azzir_source_quotation",
					"party_name": "customer",
					"company": "company",
					"currency": "currency",
					"selling_price_list": "selling_price_list",
				},
				"validation": {"docstatus": ["=", 1]},
			},
			"Quotation Item": {
				"doctype": "Sales Invoice Item",
				"field_map": {
					"item_code": "item_code",
					"item_name": "item_name",
					"description": "description",
					"uom": "uom",
					"qty": "qty",
					"rate": "rate",
					"warehouse": "warehouse",
					"discount_percentage": "discount_percentage",
				},
			},
		},
		target_doc,
		set_missing_values,
	)


def set_quotation_validity(doc, method=None):
	# Respect a manually entered expiry.
	if doc.get("valid_till"):
		return

	txn_date = doc.get("transaction_date")
	if not txn_date:
		return

	if doc.doctype == "Quotation" and doc.get("quotation_to") == "Customer":
		party_type, party = "Customer", doc.get("party_name")
	elif doc.doctype == "Supplier Quotation":
		party_type, party = "Supplier", doc.get("supplier")
	else:
		return

	if not party:
		return

	days = cint(frappe.db.get_value(party_type, party, "azzir_quotation_validity_days"))
	if days > 0:
		doc.valid_till = add_days(txn_date, days)
