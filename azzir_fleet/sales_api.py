# Copyright (c) 2026, Azzir and contributors
# For license information, please see license.txt
"""Backend for the Azzir Sales frappe-ui frontend (/sales)."""

import frappe
from frappe.utils import flt, getdate, get_first_day, get_last_day, nowdate


SALES_DOCTYPES = {"Quotation", "Sales Invoice", "Delivery Note"}
SEE_ALL_ROLES = {"Azzir Sales Overseer", "Sales Manager", "System Manager"}


def _can_see_all() -> bool:
	"""Holders of an overseer role see everyone's sales; others see only their own."""
	return bool(set(frappe.get_roles()) & SEE_ALL_ROLES)


def get_permission_query_conditions(user: str | None = None) -> str:
	"""Desk list views / reports: a salesperson sees only the documents they
	created; overseers (Azzir Sales Overseer / Sales Manager / System Manager) see
	all. Same rule as the /sales app, now on the desk too."""
	if _can_see_all():
		return ""
	user = user or frappe.session.user
	return "`owner` = {user}".format(user=frappe.db.escape(user))


def has_permission(doc, ptype: str | None = None, user: str | None = None) -> bool:
	"""Block opening someone else's sales document by URL unless the user is an
	overseer or the creator."""
	if _can_see_all():
		return True
	user = user or frappe.session.user
	return (doc.owner == user) if getattr(doc, "owner", None) else True


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
		"can_see_all": _can_see_all(),
	}


@frappe.whitelist()
def sales_list(doctype: str, fields: list | str | None = None, filters: dict | str | None = None,
               order_by: str = "modified desc", limit_page_length: int = 100, limit_start: int = 0) -> list:
	"""List sales documents. A normal salesperson only sees the ones THEY created;
	holders of an overseer role (Azzir Sales Overseer / Sales Manager / System
	Manager) see all. Enforced on the server, not just hidden in the UI."""
	if doctype not in SALES_DOCTYPES:
		frappe.throw(frappe._("Not allowed."))
	filters = frappe.parse_json(filters) if isinstance(filters, str) else (filters or {})
	fields = frappe.parse_json(fields) if isinstance(fields, str) else (fields or ["name"])
	if not _can_see_all():
		filters["owner"] = frappe.session.user
	return frappe.get_list(
		doctype, fields=fields, filters=filters, order_by=order_by,
		limit_page_length=limit_page_length, limit_start=limit_start,
	)


@frappe.whitelist()
def dashboard_stats() -> dict:
	"""KPI counts for the Sales dashboard."""
	company = frappe.defaults.get_user_default("Company") or frappe.db.get_value("Company", {}, "name")
	start, end = get_first_day(nowdate()), get_last_day(nowdate())
	mine = not _can_see_all()
	owner = frappe.session.user

	def cnt(dt, f):
		return frappe.db.count(dt, {**f, "owner": owner} if mine else f)

	ms = frappe.db.sql(
		"""select coalesce(sum(base_grand_total), 0) from `tabSales Invoice`
		   where docstatus = 1 and company = %(c)s and posting_date between %(s)s and %(e)s
		   {owner}""".format(owner="and owner = %(o)s" if mine else ""),
		{"c": company, "s": start, "e": end, "o": owner},
	)[0][0]
	return {
		"open_quotations": cnt("Quotation", {"status": "Open"}),
		"unpaid_invoices": cnt("Sales Invoice", {"status": "Unpaid"}),
		"draft_invoices": cnt("Sales Invoice", {"docstatus": 0}),
		"month_sales": flt(ms),
	}


@frappe.whitelist()
def list_customers(company: str | None = None, txt: str | None = None) -> list:
	"""Customers for the sales forms. If the Customer doctype has a 'company'
	field, narrow to that company; otherwise show ALL customers (customers are
	not company-scoped in stock ERPNext, so filtering by company would wrongly
	hide everyone). Always returns data as long as customers exist."""
	like = "%%%s%%" % (txt or "")
	conds = "(c.name like %(t)s or c.customer_name like %(t)s) and c.disabled = 0"
	vals = {"t": like}
	if company and frappe.get_meta("Customer").has_field("company"):
		conds += " and c.company = %(co)s"
		vals["co"] = company
	return frappe.db.sql(
		"select c.name, c.customer_name from `tabCustomer` c where "
		+ conds
		+ " order by c.customer_name limit 25",
		vals,
		as_dict=True,
	)


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
	allowed = {"Sales User", "Sales Manager", "Accounts User", "Accounts Manager", "System Manager", "Sales Portal"}
	return bool(roles & allowed)
