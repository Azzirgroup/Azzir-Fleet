# Copyright (c) 2026, Azzir and contributors
# For license information, please see license.txt
"""Flag a Sales Invoice when any line is sold below its SELLING (list) price.

The flag (azzir_below_cost) drives the "Sales Below Cost Approval" workflow:
normal invoices submit directly; flagged ones route to a manager for approval.

Rule: a line is flagged when its rate is below the item's selling price (the
price-list rate). If the item has NO selling price, we fall back to the buying
(cost/valuation) price instead, so an item that isn't priced still can't be
dumped below cost without approval.
"""

import frappe
from frappe.utils import flt


def flag_below_cost(doc, method=None):
	below = False
	for row in doc.get("items") or []:
		code = row.get("item_code")
		if not code:
			continue
		selling = _selling_rate(row, doc)
		if selling:
			if flt(row.rate) < selling:
				below = True
				break
		else:
			# No selling price on record — fall back to the buying/cost price.
			buying = _buying_rate(code, row.get("warehouse"))
			if buying and flt(row.rate) < buying:
				below = True
				break
	doc.azzir_below_cost = 1 if below else 0


def _selling_rate(row, doc):
	"""The item's selling (list) price for this document: the row's own
	price_list_rate, else the Item Price for the doc's selling price list. 0 when
	the item has no selling price on record."""
	rate = flt(row.get("price_list_rate"))
	if rate:
		return rate
	pl = doc.get("selling_price_list")
	code = row.get("item_code")
	if pl and code:
		rate = flt(
			frappe.db.get_value(
				"Item Price", {"item_code": code, "price_list": pl, "selling": 1}, "price_list_rate"
			)
		)
	return rate


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
