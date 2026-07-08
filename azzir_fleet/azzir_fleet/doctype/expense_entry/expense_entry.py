# Copyright (c) 2026, Azzir and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class ExpenseEntry(Document):
	def validate(self):
		self.calculate_total_amount()

	def calculate_total_amount(self):
		self.total_amount = 0
		for d in self.accounts:
			self.total_amount += d.amount or 0

	def on_submit(self):
		if not self.accounts:
			frappe.throw(_("At least one account is required in the Accounts table."))

		je = frappe.new_doc("Journal Entry")
		je.posting_date = self.posting_date
		je.company = self.company
		je.voucher_type = "Journal Entry"
		je.multi_currency = 1
		je.title = "Expense Entry"
		je.remark = f"Journal Entry for Expense Entry {self.name}"

		# Debit each expense account.
		for d in self.accounts:
			if not d.account or not d.amount:
				continue
			je.append(
				"accounts",
				{
					"account": d.account,
					"debit_in_account_currency": d.amount,
					"user_remark": d.remark,
					"cost_center": d.cost_center,
					"project": d.project,
					"department": d.department,
				},
			)

		# Credit the cash / bank account with the total.
		if self.total_amount > 0:
			default_cost_center = self.accounts[0].cost_center if self.accounts else None
			default_project = self.accounts[0].project if self.accounts else None
			default_department = self.accounts[0].department if self.accounts else None

			je.append(
				"accounts",
				{
					"account": self.cash_account,
					"credit_in_account_currency": self.total_amount,
					"cost_center": default_cost_center,
					"project": default_project,
					"department": default_department,
				},
			)

			je.insert(ignore_permissions=True)
			je.submit()

			self.db_set("journal_entry", je.name)

	def on_cancel(self):
		if self.journal_entry:
			je = frappe.get_doc("Journal Entry", self.journal_entry)
			if je.docstatus == 1:
				je.cancel()
			self.db_set("journal_entry", None)
