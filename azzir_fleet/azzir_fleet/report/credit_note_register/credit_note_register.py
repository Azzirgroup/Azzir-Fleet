# Copyright (c) 2026, Azzir and contributors
# For license information, please see license.txt

import frappe
from frappe import _


def execute(filters=None):
	filters = filters or {}

	conditions = ["si.is_return = 1", "si.docstatus = 1"]
	values = {}
	if filters.get("company"):
		conditions.append("si.company = %(company)s")
		values["company"] = filters["company"]
	if filters.get("from_date"):
		conditions.append("si.posting_date >= %(from_date)s")
		values["from_date"] = filters["from_date"]
	if filters.get("to_date"):
		conditions.append("si.posting_date <= %(to_date)s")
		values["to_date"] = filters["to_date"]
	if filters.get("customer"):
		conditions.append("si.customer = %(customer)s")
		values["customer"] = filters["customer"]

	where = " and ".join(conditions)
	data = frappe.db.sql(
		f"""
		select si.name, si.posting_date, si.customer, si.customer_name,
			si.return_against, si.currency, si.grand_total
		from `tabSales Invoice` si
		where {where}
		order by si.posting_date desc, si.name desc
		""",
		values,
		as_dict=True,
	)

	columns = [
		{"label": _("Credit Note"), "fieldname": "name", "fieldtype": "Link", "options": "Sales Invoice", "width": 160},
		{"label": _("Date"), "fieldname": "posting_date", "fieldtype": "Date", "width": 100},
		{"label": _("Customer"), "fieldname": "customer", "fieldtype": "Link", "options": "Customer", "width": 140},
		{"label": _("Customer Name"), "fieldname": "customer_name", "fieldtype": "Data", "width": 180},
		{"label": _("Against Invoice"), "fieldname": "return_against", "fieldtype": "Link", "options": "Sales Invoice", "width": 160},
		{"label": _("Currency"), "fieldname": "currency", "fieldtype": "Link", "options": "Currency", "width": 80},
		{"label": _("Grand Total"), "fieldname": "grand_total", "fieldtype": "Currency", "options": "currency", "width": 140},
	]

	return columns, data
