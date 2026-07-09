# Copyright (c) 2026, Azzir and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, get_first_day, get_last_day, getdate

MONTHS = [
	"January", "February", "March", "April", "May", "June",
	"July", "August", "September", "October", "November", "December",
]


class MonthlyBudget(Document):
	def validate(self):
		self.set_period()
		self.compute_actuals()

	def set_period(self):
		if self.month and self.year:
			m = MONTHS.index(self.month) + 1
			first = getdate(f"{int(self.year)}-{m:02d}-01")
			self.from_date = get_first_day(first)
			self.to_date = get_last_day(first)

	def compute_actuals(self):
		total_b = total_a = 0.0
		for row in self.accounts:
			actual = account_actual(row.account, self.company, self.from_date, self.to_date)
			row.actual_amount = actual
			row.balance = flt(row.amount) - flt(actual)
			total_b += flt(row.amount)
			total_a += flt(actual)
		self.total_budget = total_b
		self.total_actual = total_a
		self.total_balance = total_b - total_a


def account_actual(account, company, from_date, to_date):
	"""Net posted amount for an account in the period (positive = spend for
	expenses/assets, collection for income/liabilities)."""
	if not (account and company and from_date and to_date):
		return 0.0
	root = frappe.db.get_value("Account", account, "root_type")
	res = frappe.db.sql(
		"""select ifnull(sum(debit), 0), ifnull(sum(credit), 0) from `tabGL Entry`
		   where account = %s and company = %s and posting_date between %s and %s
		     and ifnull(is_cancelled, 0) = 0""",
		(account, company, from_date, to_date),
	)
	debit, credit = res[0]
	if root in ("Income", "Liability", "Equity"):
		return flt(credit) - flt(debit)
	return flt(debit) - flt(credit)


@frappe.whitelist()
def refresh_actuals(name):
	"""Re-pull actuals from the GL (works on draft or submitted budgets)."""
	doc = frappe.get_doc("Monthly Budget", name)
	total_b = total_a = 0.0
	for row in doc.accounts:
		actual = account_actual(row.account, doc.company, doc.from_date, doc.to_date)
		row.db_set("actual_amount", actual)
		row.db_set("balance", flt(row.amount) - flt(actual))
		total_b += flt(row.amount)
		total_a += flt(actual)
	doc.db_set("total_budget", total_b)
	doc.db_set("total_actual", total_a)
	doc.db_set("total_balance", total_b - total_a)
	return True


# --------------------------------------------------------------------------- #
# Budget control — Warn / Stop on transactions that would exceed a budget line.
# Registered on Journal Entry (which also covers our Expense Entry, since it
# posts through a Journal Entry).
# --------------------------------------------------------------------------- #
def check_journal_entry_budget(doc, method=None):
	posting_date = doc.get("posting_date")
	company = doc.get("company")
	if not posting_date or not company:
		return

	budgets = frappe.get_all(
		"Monthly Budget",
		filters={
			"company": company,
			"docstatus": 1,
			"from_date": ["<=", posting_date],
			"to_date": [">=", posting_date],
			"action_if_exceeded": ["in", ("Warn", "Stop")],
		},
		pluck="name",
	)
	if not budgets:
		return

	# Net amount this JE posts to each account (debit positive).
	je_amounts = {}
	for a in doc.get("accounts") or []:
		je_amounts[a.account] = je_amounts.get(a.account, 0) + flt(a.debit) - flt(a.credit)

	for bname in budgets:
		budget = frappe.get_doc("Monthly Budget", bname)
		for row in budget.accounts:
			if row.account not in je_amounts:
				continue
			root = frappe.db.get_value("Account", row.account, "root_type")
			contrib = je_amounts[row.account]
			if root in ("Income", "Liability", "Equity"):
				contrib = -contrib
			projected = account_actual(row.account, company, budget.from_date, budget.to_date) + contrib
			if projected > flt(row.amount):
				msg = _(
					"Monthly Budget {0}: account {1} would reach {2}, over its budget of {3}."
				).format(bname, row.account, frappe.format_value(projected, {"fieldtype": "Currency"}),
						 frappe.format_value(row.amount, {"fieldtype": "Currency"}))
				if budget.action_if_exceeded == "Stop":
					frappe.throw(msg, title=_("Budget Exceeded"))
				else:
					frappe.msgprint(msg, title=_("Budget Warning"), indicator="orange")
