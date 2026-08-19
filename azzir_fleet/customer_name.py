# Copyright (c) 2026, Azzir and contributors
# For license information, please see license.txt
"""Make the Customer Name editable and sticky on Quotation, Sales Invoice and
Delivery Note.

ERPNext re-fetches customer_name from the Customer master on every validate
(Quotation.set_customer_name / get_party_details), which would wipe a manual
edit. We capture the intended name in `before_validate` (before that re-fetch)
and restore it in `validate` (after it). The edited name also flows downstream:
Quotation -> Sales Invoice -> Delivery Note.
"""

import frappe

FLAG = "azzir_name_override"


def _master_name(doc):
	"""The name ERPNext would auto-fetch from the party master."""
	if doc.doctype == "Quotation":
		if doc.get("quotation_to") == "Customer" and doc.get("party_name"):
			return frappe.db.get_value("Customer", doc.party_name, "customer_name")
		if doc.get("quotation_to") == "Lead" and doc.get("party_name"):
			company_name, lead_name = frappe.db.get_value(
				"Lead", doc.party_name, ["company_name", "lead_name"]
			) or (None, None)
			return company_name or lead_name
		return doc.get("party_name")
	if doc.get("customer"):
		return frappe.db.get_value("Customer", doc.customer, "customer_name")
	return None


def _source_name(doc):
	"""The (possibly edited) name on the document this one was created from."""
	if doc.doctype == "Sales Invoice" and doc.get("azzir_source_quotation"):
		return frappe.db.get_value("Quotation", doc.azzir_source_quotation, "customer_name")
	if doc.doctype == "Delivery Note":
		for row in doc.get("items") or []:
			if row.get("against_sales_invoice"):
				return frappe.db.get_value(
					"Sales Invoice", row.against_sales_invoice, "customer_name"
				)
	return None


def capture_override(doc, method=None):
	"""before_validate: seed from the source doc if still on the master default,
	then remember any name that differs from the master (a deliberate edit)."""
	master = _master_name(doc)
	src = _source_name(doc)
	if src and (not doc.get("customer_name") or doc.customer_name == master):
		doc.customer_name = src
	if doc.get("customer_name") and master and doc.customer_name != master:
		doc.flags.azzir_name_override = doc.customer_name


def restore_override(doc, method=None):
	"""validate: put the edited name back after ERPNext re-fetched the master."""
	override = doc.flags.get(FLAG)
	if override:
		doc.customer_name = override
