# Copyright (c) 2026, Azzir and contributors
# For license information, please see license.txt
"""Paid On Behalf Of Sister Company, for Expense Entry: this company's cash/bank
account actually pays for something that belongs to a SISTER company, not one of
this company's own expenses.

Tick "Paid On Behalf Of Sister Company" and pick the Supplier and the Sister
Company. Two cases:
  - A Purchase Invoice is picked: this payment settles that specific outstanding
    invoice IN the sister company (debiting its payable there).
  - No Purchase Invoice (e.g. rent, fuel -- an operational expense with no invoice
    behind it): the amount posts directly as an expense in the sister company's own
    books, against the same expense account category chosen on each row here.

Either way, on submit:
  - Every row in the Accounts table is redirected to post against THIS company's own
    Intercompany Clearing Account instead of a real expense account -- this entry
    isn't an expense of ours, it's cash advanced on the sister's behalf. The
    Cash/Bank Account itself is left untouched (real money still leaves it).
  - A Journal Entry is auto-created IN THE SISTER COMPANY crediting their own
    clearing account (they now owe this amount back) against either their real
    payable (Purchase Invoice case) or their real expense account(s) (no-invoice
    case).

Mirrors azzir_fleet.intercompany_payment's Pay direction for Payment Entry. Both
companies need their Intercompany Clearing Account set (Company -> Accounts).
"""

import frappe
from frappe import _
from frappe.utils import flt


def _clearing_account(company: str) -> str | None:
	return frappe.db.get_value("Company", company, "azzir_intercompany_clearing_account")


def before_validate(doc, method=None):
	"""Runs BEFORE Expense Entry's own validate (which computes total_amount) and
	well before its on_submit (which builds the GL entries straight off the Accounts
	table), so the account redirect below is in place before either uses it."""
	if not doc.get("azzir_paid_on_behalf_of_sister"):
		return

	if not doc.get("supplier"):
		frappe.throw(_("Choose the Supplier this expense payment is actually for."))
	if not doc.get("azzir_sister_company"):
		frappe.throw(_("Choose the Sister Company this payment is actually for."))
	if doc.azzir_sister_company == doc.company:
		frappe.throw(_("Sister Company must be different from this Expense Entry's own Company."))

	if not doc.get("accounts"):
		frappe.throw(_("Add a row to Accounts with the amount being paid."))

	invoice_name = doc.get("azzir_sister_purchase_invoice")
	if invoice_name:
		inv = frappe.db.get_value(
			"Purchase Invoice", invoice_name,
			["company", "supplier", "docstatus", "outstanding_amount", "credit_to"],
			as_dict=True,
		)
		if not inv:
			frappe.throw(_("Purchase Invoice {0} not found.").format(invoice_name))
		if inv.company != doc.azzir_sister_company:
			frappe.throw(_("{0} does not belong to {1}.").format(
				invoice_name, frappe.bold(doc.azzir_sister_company)))
		if inv.supplier != doc.supplier:
			frappe.throw(_("{0} is not an invoice for {1}.").format(invoice_name, doc.supplier))
		if inv.docstatus != 1:
			frappe.throw(_("{0} is not a submitted invoice.").format(invoice_name))
		if flt(inv.outstanding_amount) <= 0:
			frappe.throw(_("{0} has no outstanding balance to settle.").format(invoice_name))

		total = sum(flt(d.amount) for d in doc.accounts)
		if total > flt(inv.outstanding_amount) + 0.01:
			frappe.throw(_(
				"Total Amount ({0}) is more than {1}'s outstanding balance ({2})."
			).format(total, invoice_name, inv.outstanding_amount))

	our_clearing = _clearing_account(doc.company)
	sister_clearing = _clearing_account(doc.azzir_sister_company)
	if not our_clearing:
		frappe.throw(_(
			"Set the Intercompany Clearing Account on company {0} (Company → Accounts) "
			"— it is required for 'Paid On Behalf Of Sister Company'."
		).format(frappe.bold(doc.company)))
	if not sister_clearing:
		frappe.throw(_(
			"Set the Intercompany Clearing Account on company {0} (Company → Accounts) "
			"— it is required for 'Paid On Behalf Of Sister Company'."
		).format(frappe.bold(doc.azzir_sister_company)))

	our_type = frappe.db.get_value("Account", our_clearing, "account_type")
	if our_type and our_type not in ("Receivable", "Payable", "Equity"):
		frappe.throw(_(
			"{0}'s Intercompany Clearing Account ({1}) has Account Type '{2}' set — pick "
			"a plain Balance Sheet account with NO Account Type instead (Company → Accounts)."
		).format(frappe.bold(doc.company), frappe.bold(our_clearing), our_type))

	# Every row posts against OUR clearing account, not a real expense account --
	# the Cash/Bank Account (cash_account) itself is left exactly as entered. Capture
	# each row's REAL account first -- on_submit needs it for the no-invoice
	# (operational expense) case, since by then `account` has been overwritten here.
	# before_validate runs on EVERY save/submit cycle, so only capture it the first
	# time -- otherwise a later pass would "capture" the already-redirected clearing
	# account instead of the real one.
	for row in doc.accounts:
		if not row.get("azzir_original_account"):
			row.azzir_original_account = row.account
		row.account = our_clearing


def on_submit(doc, method=None):
	"""Settle the sister's Purchase Invoice (or post a direct operational expense,
	when no invoice is linked) with a Journal Entry in the sister company. Runs
	after Expense Entry's own on_submit has already posted its Journal Entry
	(debiting our clearing account, crediting our cash_account)."""
	if not doc.get("azzir_paid_on_behalf_of_sister"):
		return

	from azzir_fleet.intercompany_sale import _company_cost_center

	invoice_name = doc.get("azzir_sister_purchase_invoice")
	sister_clearing = _clearing_account(doc.azzir_sister_company)
	cost_center = _company_cost_center(doc.azzir_sister_company)
	amount = sum(flt(d.amount) for d in doc.accounts)

	je = frappe.new_doc("Journal Entry")
	je.voucher_type = "Journal Entry"
	je.company = doc.azzir_sister_company
	je.posting_date = doc.posting_date

	if invoice_name:
		# Settling a payable: debit it down. The sister's clearing account takes
		# the offsetting credit (they now owe this amount to us, since we paid
		# their bill).
		inv = frappe.get_doc("Purchase Invoice", invoice_name)
		je.user_remark = _(
			"Settlement for {0}: paid out of {1} on behalf of {2}, against Purchase Invoice {3}."
		).format(doc.name, doc.company, doc.azzir_sister_company, invoice_name)
		je.append(
			"accounts",
			{
				"account": inv.credit_to,
				"party_type": "Supplier",
				"party": doc.supplier,
				"reference_type": "Purchase Invoice",
				"reference_name": invoice_name,
				"cost_center": cost_center,
				"debit_in_account_currency": amount,
			},
		)
	else:
		# No invoice -- a direct operational expense (rent, fuel, etc.). Debit each
		# row's REAL expense account (captured before it was redirected to our own
		# clearing account) so the sister's books show the correct expense category.
		je.user_remark = _(
			"Operational expense for {0}: paid out of {1} on behalf of {2} (Supplier {3}) -- "
			"no Purchase Invoice, posted directly as an expense."
		).format(doc.name, doc.company, doc.azzir_sister_company, doc.supplier)
		for row in doc.accounts:
			je.append(
				"accounts",
				{
					"account": row.azzir_original_account,
					"cost_center": row.cost_center or cost_center,
					"debit_in_account_currency": flt(row.amount),
				},
			)

	je.append(
		"accounts",
		{"account": sister_clearing, "cost_center": cost_center, "credit_in_account_currency": amount},
	)
	je.flags.ignore_permissions = True
	je.insert()
	je.submit()

	doc.db_set("azzir_settlement_journal_entry", je.name, update_modified=False)


def on_cancel(doc, method=None):
	"""Cancel the linked settlement Journal Entry too -- separate from Expense
	Entry's own controller, which only cancels its own `journal_entry`."""
	if not doc.get("azzir_paid_on_behalf_of_sister"):
		return
	je_name = doc.get("azzir_settlement_journal_entry")
	if je_name and frappe.db.exists("Journal Entry", je_name):
		je = frappe.get_doc("Journal Entry", je_name)
		if je.docstatus == 1:
			je.flags.ignore_permissions = True
			je.cancel()
