# Copyright (c) 2026, Azzir and contributors
# For license information, please see license.txt
"""Auto-set a quotation's Valid Till from the party's default validity (days)."""

import frappe
from frappe.utils import add_days, cint


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
