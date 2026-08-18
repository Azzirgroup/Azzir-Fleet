# Copyright (c) 2026, Azzir and contributors
# For license information, please see license.txt
"""Payroll Component Summary.

For submitted Salary Slips in the period, summarise each EARNING and each
DEDUCTION component: its total amount and how many employees received it. Ends
with the overall employee count.
"""

import frappe
from frappe import _
from frappe.utils import flt


def execute(filters=None):
	filters = frappe._dict(filters or {})

	conds = ["ss.docstatus = 1"]
	vals = {}
	if filters.get("company"):
		conds.append("ss.company = %(company)s")
		vals["company"] = filters.company
	if filters.get("from_date"):
		conds.append("ss.start_date >= %(from_date)s")
		vals["from_date"] = filters.from_date
	if filters.get("to_date"):
		conds.append("ss.end_date <= %(to_date)s")
		vals["to_date"] = filters.to_date
	where = " and ".join(conds)

	rows = frappe.db.sql(
		f"""
		select sd.parentfield as section, sd.salary_component as component,
			sum(sd.amount) as total_amount, count(distinct ss.employee) as employees
		from `tabSalary Detail` sd
		join `tabSalary Slip` ss on ss.name = sd.parent
		where {where} and sd.amount != 0
		group by sd.parentfield, sd.salary_component
		order by sd.parentfield asc, sd.salary_component asc
		""",
		vals,
		as_dict=True,
	)

	data = []
	for r in rows:
		data.append(
			{
				"type": _("Earning") if r.section == "earnings" else _("Deduction"),
				"component": r.component,
				"employees": r.employees,
				"total_amount": flt(r.total_amount),
			}
		)

	# Overall distinct employees paid in the period.
	total_emp = frappe.db.sql(
		f"select count(distinct ss.employee) from `tabSalary Slip` ss where {where}", vals
	)
	total_employees = (total_emp[0][0] or 0) if total_emp else 0
	if data:
		data.append(
			{"type": _("TOTAL EMPLOYEES"), "component": "", "employees": total_employees, "total_amount": None}
		)

	columns = [
		{"label": _("Type"), "fieldname": "type", "fieldtype": "Data", "width": 130},
		{"label": _("Component"), "fieldname": "component", "fieldtype": "Link", "options": "Salary Component", "width": 220},
		{"label": _("No. of Employees"), "fieldname": "employees", "fieldtype": "Int", "width": 140},
		{"label": _("Total Amount"), "fieldname": "total_amount", "fieldtype": "Currency", "width": 160},
	]
	return columns, data
