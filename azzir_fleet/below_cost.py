# Copyright (c) 2026, Azzir and contributors
# For license information, please see license.txt
"""Flag a Sales Invoice when any line is sold below buying (valuation) price.

The flag (azzir_below_cost) drives the "Sales Below Cost Approval" workflow:
normal invoices submit directly; below-cost ones route to a manager for approval.
"""

import frappe
from frappe.utils import flt


def flag_below_cost(doc, method=None):
	below = False
	for row in doc.get("items") or []:
		code = row.get("item_code")
		if not code:
			continue
		buying = _buying_rate(code, row.get("warehouse"))
		if buying and flt(row.rate) < buying:
			below = True
			break
	doc.azzir_below_cost = 1 if below else 0


def set_previous_price(doc, method=None):
	"""Record each row's price list rate as 'Previous Price' so a lowered rate can
	be compared against the original list price."""
	for row in doc.get("items") or []:
		if flt(row.get("price_list_rate")):
			row.azzir_previous_price = flt(row.get("price_list_rate"))


def _buying_rate(item_code, warehouse=None):
	"""Best-available buying/cost price: last purchase rate, else stock valuation."""
	rate = flt(frappe.get_cached_value("Item", item_code, "last_purchase_rate"))
	if rate:
		return rate
	filters = {"item_code": item_code}
	if warehouse:
		filters["warehouse"] = warehouse
	rate = flt(frappe.db.get_value("Bin", filters, "valuation_rate"))
	if rate:
		return rate
	rate = flt(frappe.db.get_value("Bin", {"item_code": item_code}, "valuation_rate"))
	return rate or flt(frappe.get_cached_value("Item", item_code, "valuation_rate"))
