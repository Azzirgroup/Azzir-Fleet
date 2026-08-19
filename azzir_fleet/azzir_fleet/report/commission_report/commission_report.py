# Copyright (c) 2026, Azzir and contributors
# For license information, please see license.txt
"""Commission Report — pick a Commission Plan (or a Branch), a date range
(defaults to the plan's period) and optionally one sales person. Computes each
person's sales month-by-month, tier reached, commission, expense share and net
payable, carrying an unmet target into the next month."""

import frappe
from frappe import _


def execute(filters=None):
	filters = frappe._dict(filters or {})
	columns = get_columns()

	from azzir_fleet.azzir_fleet.doctype.commission_plan.commission_plan import compute_commission

	plans = _plans_for(filters)
	if not plans:
		return columns, []

	rows = []
	for plan_name in plans:
		plan = frappe.get_doc("Commission Plan", plan_name)
		rows += compute_commission(plan, filters.get("from_date"), filters.get("to_date"))

	if filters.get("branch"):
		rows = [r for r in rows if r["branch"] == filters.branch]
	if filters.get("sales_person"):
		rows = [r for r in rows if r["sales_person"] == filters.sales_person]

	return columns, rows


def _plans_for(filters):
	"""Which Commission Plan(s) to compute: the chosen plan, else every plan for
	the chosen branch."""
	if filters.get("commission_plan"):
		return [filters.commission_plan]
	if filters.get("branch"):
		return frappe.get_all(
			"Commission Plan", filters={"branch": filters.branch}, pluck="name", order_by="period_start"
		)
	return []


def get_columns():
	return [
		{"label": _("Month"), "fieldname": "month", "fieldtype": "Data", "width": 90},
		{"label": _("Branch"), "fieldname": "branch", "fieldtype": "Link", "options": "Branch", "width": 130},
		{"label": _("Sales Person"), "fieldname": "sales_person", "fieldtype": "Link", "options": "Sales Person", "width": 160},
		{"label": _("Monthly Target"), "fieldname": "monthly_target", "fieldtype": "Currency", "width": 120},
		{"label": _("Carried In"), "fieldname": "carried_in", "fieldtype": "Currency", "width": 110},
		{"label": _("Effective Target"), "fieldname": "effective_target", "fieldtype": "Currency", "width": 130},
		{"label": _("Actual Sales"), "fieldname": "actual_sales", "fieldtype": "Currency", "width": 120},
		{"label": _("% Reached"), "fieldname": "pct_reached", "fieldtype": "Percent", "width": 90},
		{"label": _("Comm %"), "fieldname": "commission_pct", "fieldtype": "Percent", "width": 90},
		{"label": _("Gross Commission"), "fieldname": "gross_commission", "fieldtype": "Currency", "width": 140},
		{"label": _("Expense Share"), "fieldname": "expense_share", "fieldtype": "Currency", "width": 120},
		{"label": _("Net Commission"), "fieldname": "net_commission", "fieldtype": "Currency", "width": 140},
		{"label": _("Carried Out"), "fieldname": "carried_out", "fieldtype": "Currency", "width": 110},
	]
