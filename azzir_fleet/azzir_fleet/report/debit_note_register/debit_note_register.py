# Copyright (c) 2026, Azzir and contributors
# For license information, please see license.txt

import frappe
from frappe import _


def execute(filters=None):
	filters = filters or {}

	conditions = ["pi.is_return = 1", "pi.docstatus = 1"]
	values = {}
	if filters.get("company"):
		conditions.append("pi.company = %(company)s")
		values["company"] = filters["company"]
	if filters.get("from_date"):
		conditions.append("pi.posting_date >= %(from_date)s")
		values["from_date"] = filters["from_date"]
	if filters.get("to_date"):
		conditions.append("pi.posting_date <= %(to_date)s")
		values["to_date"] = filters["to_date"]
	if filters.get("supplier"):
		conditions.append("pi.supplier = %(supplier)s")
		values["supplier"] = filters["supplier"]

	where = " and ".join(conditions)
	data = frappe.db.sql(
		f"""
		select pi.name, pi.posting_date, pi.supplier, pi.supplier_name,
			pi.return_against, pi.currency, pi.grand_total
		from `tabPurchase Invoice` pi
		where {where}
		order by pi.posting_date desc, pi.name desc
		""",
		values,
		as_dict=True,
	)

	columns = [
		{"label": _("Debit Note"), "fieldname": "name", "fieldtype": "Link", "options": "Purchase Invoice", "width": 160},
		{"label": _("Date"), "fieldname": "posting_date", "fieldtype": "Date", "width": 100},
		{"label": _("Supplier"), "fieldname": "supplier", "fieldtype": "Link", "options": "Supplier", "width": 140},
		{"label": _("Supplier Name"), "fieldname": "supplier_name", "fieldtype": "Data", "width": 180},
		{"label": _("Against Invoice"), "fieldname": "return_against", "fieldtype": "Link", "options": "Purchase Invoice", "width": 160},
		{"label": _("Currency"), "fieldname": "currency", "fieldtype": "Link", "options": "Currency", "width": 80},
		{"label": _("Grand Total"), "fieldname": "grand_total", "fieldtype": "Currency", "options": "currency", "width": 140},
	]

	return columns, data
