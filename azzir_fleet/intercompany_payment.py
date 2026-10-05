# Copyright (c) 2026, Azzir and contributors
# For license information, please see license.txt
"""Paid On Behalf Of Sister Company: a customer's cash lands in ONE company's bank, but
the invoice it's actually settling belongs to a SISTER company (e.g. bought from HPL,
paid into HCL).

Tick "Paid On Behalf Of Sister Company" on a Receive Payment Entry, pick the Sister
Company and their invoice. On submit:
  - THIS Payment Entry posts its cash against the Intercompany Clearing Account
    (configured per Company) instead of the customer's own ledger here — the customer
    owes this company nothing; the real debt sits on the sister's books.
  - A Journal Entry is auto-created IN THE SISTER COMPANY, crediting the customer's
    receivable there (settling their invoice) and debiting the sister's own clearing
    account (what the paying company now owes them).

Both companies need their Intercompany Clearing Account set (Company -> Accounts) —
a liability-type account works best: it's CREDITED on the company that collected cash
it doesn't own (increasing what it owes the sister), and DEBITED on the sister
(decreasing what the sister is owed, since their receivable from the customer closed).
"""

import frappe
from frappe import _
from frappe.utils import flt


def _clearing_account(company: str) -> str | None:
	return frappe.db.get_value("Company", company, "azzir_intercompany_clearing_account")


def before_validate(doc, method=None):
	"""Runs BEFORE ERPNext's own Payment Entry validate, so our override of paid_from
	(the account the cash is posted against) is in place before core computes anything
	against it (exchange rates, account currency, etc.) — not after, which would leave
	those stale."""
	if not doc.get("azzir_paid_on_behalf_of_sister"):
		return

	if doc.payment_type != "Receive" or doc.party_type != "Customer":
		frappe.throw(_(
			"'Paid On Behalf Of Sister Company' only applies to a Receive payment from a Customer."
		))
	if not doc.get("azzir_sister_company"):
		frappe.throw(_("Choose the Sister Company this payment is actually for."))
	if doc.azzir_sister_company == doc.company:
		frappe.throw(_("Sister Company must be different from this Payment Entry's own Company."))
	if not doc.get("azzir_sister_invoice"):
		frappe.throw(_("Choose the Sister Company's invoice this payment settles."))

	inv = frappe.db.get_value(
		"Sales Invoice", doc.azzir_sister_invoice,
		["company", "customer", "docstatus", "outstanding_amount", "debit_to"],
		as_dict=True,
	)
	if not inv:
		frappe.throw(_("Sales Invoice {0} not found.").format(doc.azzir_sister_invoice))
	if inv.company != doc.azzir_sister_company:
		frappe.throw(_("{0} does not belong to {1}.").format(
			doc.azzir_sister_invoice, frappe.bold(doc.azzir_sister_company)))
	if inv.customer != doc.party:
		frappe.throw(_("{0} is not an invoice for {1}.").format(doc.azzir_sister_invoice, doc.party))
	if inv.docstatus != 1:
		frappe.throw(_("{0} is not a submitted invoice.").format(doc.azzir_sister_invoice))
	if flt(inv.outstanding_amount) <= 0:
		frappe.throw(_("{0} has no outstanding balance to settle.").format(doc.azzir_sister_invoice))
	if flt(doc.paid_amount) > flt(inv.outstanding_amount) + 0.01:
		frappe.throw(_(
			"Paid Amount ({0}) is more than {1}'s outstanding balance ({2})."
		).format(doc.paid_amount, doc.azzir_sister_invoice, inv.outstanding_amount))

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

	# Post the cash against the clearing account, not the customer's own ledger in THIS
	# company — they owe this company nothing; the real debt is the sister's.
	doc.paid_from = our_clearing


def on_submit(doc, method=None):
	"""Settle the sister's invoice with a Journal Entry in the sister company."""
	if not doc.get("azzir_paid_on_behalf_of_sister"):
		return

	from azzir_fleet.intercompany_sale import _company_cost_center

	inv = frappe.get_doc("Sales Invoice", doc.azzir_sister_invoice)
	sister_clearing = _clearing_account(doc.azzir_sister_company)
	cost_center = _company_cost_center(doc.azzir_sister_company)

	je = frappe.new_doc("Journal Entry")
	je.voucher_type = "Journal Entry"
	je.company = doc.azzir_sister_company
	je.posting_date = doc.posting_date
	je.user_remark = _(
		"Settlement for {0}: paid into {1} on behalf of {2}, against invoice {3}."
	).format(doc.name, doc.company, doc.azzir_sister_company, doc.azzir_sister_invoice)
	je.append("accounts", {
		"account": inv.debit_to,
		"party_type": "Customer",
		"party": doc.party,
		"credit_in_account_currency": flt(doc.paid_amount),
		"reference_type": "Sales Invoice",
		"reference_name": doc.azzir_sister_invoice,
		"cost_center": cost_center,
	})
	je.append("accounts", {
		"account": sister_clearing,
		"debit_in_account_currency": flt(doc.paid_amount),
		"cost_center": cost_center,
	})
	je.flags.ignore_permissions = True
	je.insert()
	je.submit()

	doc.db_set("azzir_settlement_journal_entry", je.name, update_modified=False)


def on_cancel(doc, method=None):
	"""Cancel the linked settlement Journal Entry too, so cancelling the payment doesn't
	leave a dangling settlement behind."""
	if not doc.get("azzir_paid_on_behalf_of_sister"):
		return
	je_name = doc.get("azzir_settlement_journal_entry")
	if je_name and frappe.db.exists("Journal Entry", je_name):
		je = frappe.get_doc("Journal Entry", je_name)
		if je.docstatus == 1:
			je.flags.ignore_permissions = True
			je.cancel()
