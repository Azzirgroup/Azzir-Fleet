# Copyright (c) 2026, Azzir and contributors
# For license information, please see license.txt
"""Make VAT optional per document via the 'Apply VAT' checkbox.

Runs on before_validate (before taxes are calculated) so unchecking it removes
the tax lines and the totals recompute without VAT.
"""


def apply_vat_option(doc, method=None):
	# Field defaults to 1 (VAT applies as normal). Only act when explicitly off.
	if doc.get("azzir_apply_vat") is None:
		return
	if not doc.get("azzir_apply_vat"):
		doc.set("taxes", [])
		if doc.meta.has_field("taxes_and_charges"):
			doc.taxes_and_charges = None
