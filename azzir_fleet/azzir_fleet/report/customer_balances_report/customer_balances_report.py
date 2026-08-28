# Copyright (c) 2026, Azzir and contributors
# For license information, please see license.txt
"""Customer Balances Report — the outstanding (unpaid) balance each customer
owes, summed from submitted Sales Invoices. One row per customer. Filter by
company or a single customer; tick Show Zero Balances to include fully-paid
customers."""

import frappe
from frappe import _
from frappe.utils import flt


def execute(filters=None):
	filters = frappe._dict(filters or {})
	return get_columns(), get_rows(filters)


def get_rows(filters):
	conds = ["si.docstatus = 1"]
	vals = {}
	if filters.get("company"):
		conds.append("si.company = %(company)s")
		vals["company"] = filters.company
	if filters.get("customer"):
		conds.append("si.customer = %(customer)s")
		vals["customer"] = filters.customer

	having = "" if filters.get("show_zero") else "having outstanding > 0"

	rows = frappe.db.sql(
		"""
		select si.customer,
		       max(si.customer_name) as customer_name,
		       sum(si.outstanding_amount) as outstanding
		from `tabSales Invoice` si
		where {conds}
		group by si.customer
		{having}
		order by outstanding desc
		""".format(conds=" and ".join(conds), having=having),
		vals,
		as_dict=True,
	)
	for r in rows:
		r["outstanding"] = flt(r["outstanding"])
	return rows


def get_columns():
	return [
		{"label": _("Customer"), "fieldname": "customer", "fieldtype": "Link", "options": "Customer", "width": 240},
		{"label": _("Customer Name"), "fieldname": "customer_name", "fieldtype": "Data", "width": 240},
		{"label": _("Outstanding"), "fieldname": "outstanding", "fieldtype": "Currency", "width": 160},
	]
