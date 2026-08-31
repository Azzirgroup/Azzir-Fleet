# Copyright (c) 2026, Azzir and contributors
# For license information, please see license.txt
"""Dynamic intercompany receipt discount.

Each Company can set `azzir_intercompany_discount` (%). When that company
RECEIVES stock from a sister company (an internal-supplier Purchase Receipt /
Purchase Invoice), every line's rate is reduced by that percentage — so, e.g.,
HCL configured at 30% receives sister-company stock at 30% off. Fully dynamic:
change the % on the Company, no code change, works for any company.
"""

import frappe
from frappe.utils import flt


def apply_intercompany_discount(doc, method=None):
	# The sell-sister-stock flow already prices the receipt at the transfer rate —
	# don't discount it a second time.
	if doc.flags.get("azzir_intercompany_priced"):
		return
	# Only intercompany receipts (goods coming from a sister/internal supplier).
	if not doc.get("is_internal_supplier"):
		return
	disc = flt(frappe.db.get_value("Company", doc.company, "azzir_intercompany_discount"))
	if disc <= 0:
		return

	factor = 1 - disc / 100.0
	touched = False
	for row in doc.get("items") or []:
		if flt(row.get("rate")):
			row.rate = flt(row.rate) * factor
			row.discount_percentage = 0
			row.margin_rate_or_amount = 0
			touched = True

	if touched and callable(getattr(doc, "calculate_taxes_and_totals", None)):
		doc.calculate_taxes_and_totals()
