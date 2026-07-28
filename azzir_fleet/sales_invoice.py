# Copyright (c) 2026, Azzir and contributors
# For license information, please see license.txt
"""Create a Quotation from a Sales Invoice (re-quote a past sale).

This is the reverse of the standard sales cycle, so it's a convenience copy —
it does not link the two documents. Items, qty and rates are carried over; the
Quotation's validity is then applied by the usual per-customer rule.
"""

import frappe
from frappe.model.mapper import get_mapped_doc


@frappe.whitelist()
def make_quotation(source_name: str, target_doc: str | None = None) -> dict:
	def set_missing_values(source, target):
		target.quotation_to = "Customer"
		target.party_name = source.customer
		target.ignore_pricing_rule = 1  # keep the invoice's rates, don't re-price
		target.run_method("set_missing_values")
		target.run_method("calculate_taxes_and_totals")

	doc = get_mapped_doc(
		"Sales Invoice",
		source_name,
		{
			"Sales Invoice": {
				"doctype": "Quotation",
				"field_map": {
					"company": "company",
					"currency": "currency",
					"selling_price_list": "selling_price_list",
				},
			},
			"Sales Invoice Item": {
				"doctype": "Quotation Item",
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
				"postprocess": _reset_item_flags,
			},
		},
		target_doc,
		set_missing_values,
	)
	return doc


def _reset_item_flags(source, target, source_parent):
	# Drop invoice-only links so the Quotation row is clean.
	target.sales_invoice_item = None
	target.against_sales_invoice = None
