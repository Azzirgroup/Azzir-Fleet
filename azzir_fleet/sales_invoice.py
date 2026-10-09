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
		target.azzir_source_sales_invoice = source.name  # marks the reverse flow
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


def mark_quotation_invoiced(doc, method=None):
	"""On submit, flag the source Quotation as invoiced (hides its Create button)."""
	q = doc.get("azzir_source_quotation")
	if q and frappe.db.exists("Quotation", q):
		frappe.db.set_value("Quotation", q, "azzir_invoiced", 1, update_modified=False)


def unmark_quotation_invoiced(doc, method=None):
	"""On cancel, clear the flag unless another submitted invoice still points here."""
	q = doc.get("azzir_source_quotation")
	if not q or not frappe.db.exists("Quotation", q):
		return
	other = frappe.db.exists(
		"Sales Invoice",
		{"azzir_source_quotation": q, "docstatus": 1, "name": ["!=", doc.name]},
	)
	frappe.db.set_value("Quotation", q, "azzir_invoiced", 1 if other else 0, update_modified=False)


# All four Habili companies shared one Sales Invoice naming series setup, so every
# invoice was getting named HPL/INV/... regardless of which company it was actually
# for. Force the right prefix (matching each Company's own abbr) by company instead of
# relying on whoever creates the invoice to pick the correct one from the naming
# series dropdown themselves -- that's how this happened in the first place. Covers
# all four now, not just the two that have issued invoices so far, so this doesn't
# need revisiting the day HUL or HEL start invoicing too.
_COMPANY_NAMING_SERIES = {
	"HABILI AND COMPANY LIMITED": "HCL/INV/2026/001",
	"HABILI UNDERCARRIAGE LIMITED": "HUL/INV/2026/001",
	"HABILI EQUIPMENT LIMITED": "HEL/INV/2026/001",
	"HABILI PARTS LIMITED": "HPL/INV/2026/001",
}


def set_naming_series_by_company(doc, method=None):
	"""Sales Invoice before_insert."""
	series = _COMPANY_NAMING_SERIES.get(doc.company)
	if series:
		doc.naming_series = series
