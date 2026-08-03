# Copyright (c) 2026, Azzir and contributors
# For license information, please see license.txt
"""Make VAT optional per document via the 'Apply VAT' checkbox.

Runs on `validate` — AFTER ERPNext's controller has (re)applied the default tax
template (see AccountsController.set_taxes, which re-adds the company default on
a new doc with no taxes). Stripping earlier than that is why the toggle used to
do nothing. Here we clear the taxes last and recompute totals without VAT.
"""


def apply_vat_option(doc, method=None):
	# Field defaults to 1 (VAT applies as normal). Only act when explicitly off.
	if doc.get("azzir_apply_vat") is None:
		return
	if doc.get("azzir_apply_vat"):
		return

	# VAT is OFF: remove any tax rows (ERPNext may have just re-applied the
	# default template) and the linked template, then recompute the totals.
	had_taxes = bool(doc.get("taxes"))
	if had_taxes:
		doc.set("taxes", [])
	if doc.meta.has_field("taxes_and_charges") and doc.get("taxes_and_charges"):
		doc.taxes_and_charges = None
		had_taxes = True
	if had_taxes and hasattr(doc, "calculate_taxes_and_totals"):
		doc.calculate_taxes_and_totals()
