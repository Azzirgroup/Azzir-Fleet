# Copyright (c) 2026, Azzir and contributors
# For license information, please see license.txt
"""Tax Inclusive/Exclusive helper for Expense Entry and Journal Entry rows.

Per row you pick a Tax Type + rate:
  - Inclusive: the amount ALREADY contains tax -> we show the tax portion and the
    net (base) inside it.  e.g. 118 @ 18% -> tax 18, net 100.
  - Exclusive: the amount is the base -> tax is added on top.
    e.g. 100 @ 18% -> tax 18, net 100 (total 118).
These are computed/display fields; they don't change the posted GL amounts.
"""

import frappe
from frappe.utils import flt


def split_tax(base, tax_type, rate):
	base, rate = flt(base), flt(rate)
	if not tax_type or not rate or not base:
		return 0.0, base
	if tax_type == "Inclusive":
		net = base / (1 + rate / 100.0)
		return flt(base - net), flt(net)
	# Exclusive
	return flt(base * rate / 100.0), flt(base)


def compute_expense_entry_tax(doc, method=None):
	for row in doc.get("accounts") or []:
		tax, net = split_tax(row.get("amount"), row.get("azzir_tax_type"), row.get("azzir_tax_rate"))
		row.azzir_tax_amount = tax
		row.azzir_net_amount = net


def compute_journal_entry_tax(doc, method=None):
	for row in doc.get("accounts") or []:
		base = flt(row.get("debit_in_account_currency")) or flt(row.get("credit_in_account_currency"))
		tax, net = split_tax(base, row.get("azzir_tax_type"), row.get("azzir_tax_rate"))
		row.azzir_tax_amount = tax
		row.azzir_net_amount = net
