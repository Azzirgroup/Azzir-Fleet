# Copyright (c) 2026, Azzir and contributors
# For license information, please see license.txt
"""Commission Report — pick a Commission Plan, a date range (defaults to the
plan's period) and optionally one sales person. Auto-calculates each person's
sales, tier reached, gross commission, expense share and net payable."""

import frappe
from frappe import _


def execute(filters=None):
	filters = frappe._dict(filters or {})
	columns = get_columns()
	if not filters.get("commission_plan"):
		return columns, []

	from azzir_fleet.azzir_fleet.doctype.commission_plan.commission_plan import compute_commission

	plan = frappe.get_doc("Commission Plan", filters.commission_plan)
	rows = compute_commission(plan, filters.get("from_date"), filters.get("to_date"))

	if filters.get("sales_person"):
		rows = [r for r in rows if r["sales_person"] == filters.sales_person]

	return columns, rows


def get_columns():
	return [
		{"label": _("Sales Person"), "fieldname": "sales_person", "fieldtype": "Link", "options": "Sales Person", "width": 180},
		{"label": _("Target"), "fieldname": "target", "fieldtype": "Currency", "width": 130},
		{"label": _("Actual Sales"), "fieldname": "actual_sales", "fieldtype": "Currency", "width": 130},
		{"label": _("% Reached"), "fieldname": "pct_reached", "fieldtype": "Percent", "width": 100},
		{"label": _("Commission %"), "fieldname": "commission_pct", "fieldtype": "Percent", "width": 110},
		{"label": _("Gross Commission"), "fieldname": "gross_commission", "fieldtype": "Currency", "width": 150},
		{"label": _("Expense Share"), "fieldname": "expense_share", "fieldtype": "Currency", "width": 130},
		{"label": _("Net Commission"), "fieldname": "net_commission", "fieldtype": "Currency", "width": 150},
	]
