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


def has_app_permission() -> bool:
	"""Who may open the /sales app: sales roles, accounts, or a manager."""
	roles = set(frappe.get_roles())
	allowed = {"Sales User", "Sales Manager", "Accounts User", "Accounts Manager", "System Manager"}
	return bool(roles & allowed)
