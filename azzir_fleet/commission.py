# Copyright (c) 2026, Azzir and contributors
# For license information, please see license.txt
"""Commission helpers — a Link-field query that limits a Commission Plan's
members to Sales People whose linked Employee belongs to the plan's Branch."""

import frappe


@frappe.whitelist()
def branch_sales_persons(
	doctype: str,
	txt: str,
	searchfield: str,
	start: int,
	page_len: int,
	filters: dict,
) -> list:
	"""Sales Persons for the plan's branch (via their Employee). When no branch is
	given, all enabled sales people are returned."""
	filters = filters or {}
	branch = filters.get("branch")
	like = "%%%s%%" % (txt or "")
	params = {"txt": like, "start": start, "page_len": page_len}
	branch_clause = ""
	if branch:
		branch_clause = "and emp.branch = %(branch)s"
		params["branch"] = branch
	return frappe.db.sql(
		"""
		select sp.name, sp.sales_person_name
		from `tabSales Person` sp
		left join `tabEmployee` emp on emp.name = sp.employee
		where sp.enabled = 1
		  and (sp.name like %(txt)s or sp.sales_person_name like %(txt)s)
		  {branch_clause}
		order by sp.name
		limit %(start)s, %(page_len)s
		""".format(branch_clause=branch_clause),
		params,
	)
