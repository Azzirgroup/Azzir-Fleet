# Copyright (c) 2026, Azzir and contributors
# For license information, please see license.txt
"""Backend for the Azzir Sales frappe-ui frontend (/sales)."""

import frappe
from frappe.utils import flt, getdate, get_first_day, get_last_day, nowdate


@frappe.whitelist()
def get_defaults() -> dict:
	"""Company / currency / price list the Sales forms post against."""
	company = frappe.defaults.get_user_default("Company") or frappe.db.get_value("Company", {}, "name")
	currency = frappe.get_cached_value("Company", company, "default_currency") if company else None
	return {
		"company": company,
		"currency": currency,
		"selling_price_list": frappe.db.get_single_value("Selling Settings", "selling_price_list"),
		"user": frappe.session.user,
	}


@frappe.whitelist()
def dashboard_stats() -> dict:
	"""KPI counts for the Sales dashboard."""
	company = frappe.defaults.get_user_default("Company") or frappe.db.get_value("Company", {}, "name")
	start, end = get_first_day(nowdate()), get_last_day(nowdate())
	month_sales = frappe.db.sql(
		"""select coalesce(sum(base_grand_total), 0) from `tabSales Invoice`
		   where docstatus = 1 and company = %(c)s and posting_date between %(s)s and %(e)s""",
		{"c": company, "s": start, "e": end},
	)[0][0]
	return {
		"open_quotations": frappe.db.count("Quotation", {"status": "Open"}),
		"unpaid_invoices": frappe.db.count("Sales Invoice", {"status": "Unpaid"}),
		"draft_invoices": frappe.db.count("Sales Invoice", {"docstatus": 0}),
		"month_sales": flt(month_sales),
	}


@frappe.whitelist()
def item_details(item_code: str, customer: str | None = None, company: str | None = None,
                 price_list: str | None = None, qty: float = 1) -> dict:
	"""Rate + description for an item, the same way ERPNext auto-fills a sales row
	(price list rate, pricing rules, UOM)."""
	from erpnext.stock.get_item_details import get_item_details

	company = company or frappe.defaults.get_user_default("Company") or frappe.db.get_value("Company", {}, "name")
	price_list = price_list or frappe.db.get_single_value("Selling Settings", "selling_price_list")
	currency = frappe.get_cached_value("Company", company, "default_currency") if company else None
	ctx = frappe._dict({
		"item_code": item_code, "company": company, "customer": customer,
		"selling_price_list": price_list, "price_list": price_list,
		"currency": currency, "price_list_currency": currency,
		"conversion_rate": 1, "plc_conversion_rate": 1, "qty": qty or 1,
		"doctype": "Sales Invoice", "transaction_type": "selling",
		"is_pos": 0, "is_return": 0, "ignore_pricing_rule": 0, "update_stock": 0,
	})
	try:
		out = get_item_details(ctx)
	except Exception:
		return {}
	return {
		"rate": out.get("price_list_rate") or out.get("rate") or 0,
		"item_name": out.get("item_name"),
		"description": out.get("description"),
		"uom": out.get("stock_uom") or out.get("uom"),
	}


@frappe.whitelist()
def make_next(source_doctype: str, source_name: str, target: str) -> dict:
	"""Next document in the sales flow using ERPNext's own mappers. Sales Invoice /
	Delivery Note come back as PREFILLED data for review (the user confirms items /
	warehouses, then saves) — exactly how the desk opens a mapped doc. Payment Entry
	is inserted straight away and opened.
	Quotation -> Sales Invoice -> (Delivery Note / Payment Entry)."""
	if target == "Payment Entry" and source_doctype == "Sales Invoice":
		from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry
		doc = get_payment_entry("Sales Invoice", source_name)
		doc.insert(ignore_permissions=True)
		return {"mode": "open", "doctype": doc.doctype, "name": doc.name}

	if target == "Sales Invoice" and source_doctype == "Quotation":
		from azzir_fleet.quotation import make_sales_invoice
		doc = make_sales_invoice(source_name)
	elif target == "Delivery Note" and source_doctype == "Sales Invoice":
		from erpnext.accounts.doctype.sales_invoice.sales_invoice import make_delivery_note
		doc = make_delivery_note(source_name)
	else:
		frappe.throw(frappe._("Cannot create {0} from {1}.").format(target, source_doctype))

	return {
		"mode": "form",
		"doctype": target,
		"data": {
			"customer": doc.get("customer") or doc.get("party_name"),
			"items": [
				{"item_code": r.item_code, "qty": r.qty, "rate": r.rate, "warehouse": r.get("warehouse")}
				for r in (doc.get("items") or [])
			],
		},
	}


def has_app_permission() -> bool:
	"""Who may open the /sales app: sales roles, accounts, or a manager."""
	roles = set(frappe.get_roles())
	allowed = {"Sales User", "Sales Manager", "Accounts User", "Accounts Manager", "System Manager"}
	return bool(roles & allowed)
