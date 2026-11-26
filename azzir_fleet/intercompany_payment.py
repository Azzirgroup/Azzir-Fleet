# Copyright (c) 2026, Azzir and contributors
# For license information, please see license.txt
"""Paid On Behalf Of Sister Company: this company's cash actually settles a SISTER
company's debt, not its own.

Receive: a customer's cash lands in ONE company's bank, but the invoice it's settling
belongs to a SISTER company (e.g. bought from HPL, paid into HCL).
Pay: this company pays a SUPPLIER, but the bill it's settling is actually the SISTER's
(the sister owes that supplier, not this company).

Tick "Paid On Behalf Of Sister Company", pick the Sister Company and their invoice
(a Sales Invoice for Receive, a Purchase Invoice for Pay). The Payment Entry itself is
left completely normal -- paid_from/paid_to still go against the party's OWN real
account, exactly like any other payment, because ERPNext's own validate_party_details()
requires that account to match the party's natural type (Payable for a Supplier,
Receivable for a Customer) and throws "Account ... and Party Type ... have different
account types" otherwise. Redirecting it to a plain clearing account up front (an
earlier version of this file did that) collides with that check head-on.

Instead, on submit, TWO Journal Entries move the money into the clearing accounts after
the fact:
  - A LOCAL one, in THIS company, reclassifying the balance the Payment Entry just
    posted against the party's real account into our OWN Intercompany Clearing Account
    (that party doesn't really owe/is-owed anything here -- the real debt is the
    sister's, so it shouldn't sit on their account in our books either).
  - A SISTER one, in THE SISTER COMPANY, settling the real invoice there against the
    sister's OWN Intercompany Clearing Account.

Both companies need their Intercompany Clearing Account set (Company -> Accounts), with
NO Account Type (blank) -- neither settlement JE's clearing row carries a Party, and
ERPNext's Journal Entry validation requires one on any row posted to a Receivable/
Payable-type account. The SAME account is used for both directions: its balance just
nets whichever way the IOU currently runs between the two companies.
"""

import frappe
from frappe import _
from frappe.utils import flt

# Everything that differs between the two directions, keyed by Payment Entry type.
_DIRECTION = {
	"Receive": {
		"party_type": "Customer",
		"invoice_field": "azzir_sister_invoice",
		"invoice_doctype": "Sales Invoice",
		"invoice_party_field": "customer",
		"invoice_account_field": "debit_to",  # the invoice's own receivable account
		"pe_account_field": "paid_from",  # the field ERPNext treats as "the party's account" on a Receive
	},
	"Pay": {
		"party_type": "Supplier",
		"invoice_field": "azzir_sister_purchase_invoice",
		"invoice_doctype": "Purchase Invoice",
		"invoice_party_field": "supplier",
		"invoice_account_field": "credit_to",  # the invoice's own payable account
		"pe_account_field": "paid_to",  # the field ERPNext treats as "the party's account" on a Pay
	},
}


def _clearing_account(company: str) -> str | None:
	return frappe.db.get_value("Company", company, "azzir_intercompany_clearing_account")


def before_validate(doc, method=None):
	"""Just validates the setup -- paid_from/paid_to are left alone here. See the
	module docstring for why: redirecting them to the clearing account up front is
	what breaks ERPNext's own validate_party_details() check."""
	if not doc.get("azzir_paid_on_behalf_of_sister"):
		return

	cfg = _DIRECTION.get(doc.payment_type)
	if not cfg or doc.party_type != cfg["party_type"]:
		frappe.throw(_(
			"'Paid On Behalf Of Sister Company' only applies to a Receive payment from a "
			"Customer, or a Pay payment to a Supplier."
		))
	if not doc.get("azzir_sister_company"):
		frappe.throw(_("Choose the Sister Company this payment is actually for."))
	if doc.azzir_sister_company == doc.company:
		frappe.throw(_("Sister Company must be different from this Payment Entry's own Company."))

	invoice_name = doc.get(cfg["invoice_field"])
	if not invoice_name:
		frappe.throw(_("Choose the Sister Company's invoice this payment settles."))

	inv = frappe.db.get_value(
		cfg["invoice_doctype"], invoice_name,
		["company", cfg["invoice_party_field"], "docstatus", "outstanding_amount", cfg["invoice_account_field"]],
		as_dict=True,
	)
	if not inv:
		frappe.throw(_("{0} {1} not found.").format(cfg["invoice_doctype"], invoice_name))
	if inv.company != doc.azzir_sister_company:
		frappe.throw(_("{0} does not belong to {1}.").format(
			invoice_name, frappe.bold(doc.azzir_sister_company)))
	if inv.get(cfg["invoice_party_field"]) != doc.party:
		frappe.throw(_("{0} is not an invoice for {1}.").format(invoice_name, doc.party))
	if inv.docstatus != 1:
		frappe.throw(_("{0} is not a submitted invoice.").format(invoice_name))
	if flt(inv.outstanding_amount) <= 0:
		frappe.throw(_("{0} has no outstanding balance to settle.").format(invoice_name))
	if flt(doc.paid_amount) > flt(inv.outstanding_amount) + 0.01:
		frappe.throw(_(
			"Paid Amount ({0}) is more than {1}'s outstanding balance ({2})."
		).format(doc.paid_amount, invoice_name, inv.outstanding_amount))

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

	# Neither clearing row the two settlement Journal Entries post ever carries a Party
	# -- it's a plain intercompany IOU line, not a real customer/supplier balance.
	# ERPNext's own Journal Entry validation (validate_party) demands a Party on ANY row
	# posted against a Receivable/Payable-type account, and would otherwise only fail
	# later, confusingly, when on_submit() creates those JEs -- check both sides' clearing
	# accounts here, up front, with a clear message.
	for company, clearing in ((doc.company, our_clearing), (doc.azzir_sister_company, sister_clearing)):
		acc_type = frappe.db.get_value("Account", clearing, "account_type")
		if acc_type:
			frappe.throw(_(
				"{0}'s Intercompany Clearing Account ({1}) has Account Type '{2}' set — pick "
				"a plain Balance Sheet account with NO Account Type instead (Company → Accounts)."
			).format(frappe.bold(company), frappe.bold(clearing), acc_type))


def _make_je(company, posting_date, remark, rows):
	je = frappe.new_doc("Journal Entry")
	je.voucher_type = "Journal Entry"
	je.company = company
	je.posting_date = posting_date
	je.user_remark = remark
	for row in rows:
		je.append("accounts", row)
	je.flags.ignore_permissions = True
	je.insert()
	je.submit()
	return je.name


def on_submit(doc, method=None):
	"""Two Journal Entries move the money where it actually belongs:
	1. LOCAL (this company): reclassify the balance this Payment Entry just posted
	   against the party's own account into our clearing account.
	2. SISTER (the sister company): settle the real invoice there against the
	   sister's own clearing account.
	"""
	if not doc.get("azzir_paid_on_behalf_of_sister"):
		return

	from azzir_fleet.intercompany_sale import _company_cost_center

	cfg = _DIRECTION[doc.payment_type]
	invoice_name = doc.get(cfg["invoice_field"])
	inv = frappe.get_doc(cfg["invoice_doctype"], invoice_name)
	our_clearing = _clearing_account(doc.company)
	sister_clearing = _clearing_account(doc.azzir_sister_company)
	our_cost_center = _company_cost_center(doc.company)
	sister_cost_center = _company_cost_center(doc.azzir_sister_company)
	invoice_account = inv.get(cfg["invoice_account_field"])
	# The account the Payment Entry itself posted against the party with, in THIS
	# company -- left untouched (see module docstring), so it's exactly the party's
	# own real receivable/payable account.
	natural_party_account = doc.get(cfg["pe_account_field"])

	direction_note = (
		"received into {0}".format(doc.company) if doc.payment_type == "Receive"
		else "paid out of {0}".format(doc.company)
	)

	local_party_row = {
		"account": natural_party_account,
		"party_type": cfg["party_type"],
		"party": doc.party,
		"cost_center": our_cost_center,
	}
	local_clearing_row = {"account": our_clearing, "cost_center": our_cost_center}

	sister_party_row = {
		"account": invoice_account,
		"party_type": cfg["party_type"],
		"party": doc.party,
		"reference_type": cfg["invoice_doctype"],
		"reference_name": invoice_name,
		"cost_center": sister_cost_center,
	}
	sister_clearing_row = {"account": sister_clearing, "cost_center": sister_cost_center}

	if doc.payment_type == "Receive":
		# The Payment Entry CREDITED the party's receivable (an artificial balance --
		# this company isn't really owed anything by them). Reverse that locally, and
		# push the opposite into our own clearing account (we're now owed this cash
		# back from the sister).
		local_party_row["debit_in_account_currency"] = flt(doc.paid_amount)
		local_clearing_row["credit_in_account_currency"] = flt(doc.paid_amount)
		# Settling a receivable in the sister's books: credit it down. The sister's
		# clearing account takes the offsetting debit (they're now owed this cash
		# back from us).
		sister_party_row["credit_in_account_currency"] = flt(doc.paid_amount)
		sister_clearing_row["debit_in_account_currency"] = flt(doc.paid_amount)
	else:
		# The Payment Entry DEBITED the party's payable (artificial again -- this
		# company never owed them). Reverse that locally into our clearing account.
		local_party_row["credit_in_account_currency"] = flt(doc.paid_amount)
		local_clearing_row["debit_in_account_currency"] = flt(doc.paid_amount)
		# Settling a payable in the sister's books: debit it down. The sister's
		# clearing account takes the offsetting credit (they now owe this amount to
		# us, since we paid their bill).
		sister_party_row["debit_in_account_currency"] = flt(doc.paid_amount)
		sister_clearing_row["credit_in_account_currency"] = flt(doc.paid_amount)

	local_je = _make_je(
		doc.company, doc.posting_date,
		_("Local settlement for {0}: moves the balance against {1} into the "
			"Intercompany Clearing Account.").format(doc.name, doc.party),
		[local_party_row, local_clearing_row],
	)
	sister_je = _make_je(
		doc.azzir_sister_company, doc.posting_date,
		_("Settlement for {0}: {1} on behalf of {2}, against {3} {4}.").format(
			doc.name, direction_note, doc.azzir_sister_company, cfg["invoice_doctype"], invoice_name,
		),
		[sister_party_row, sister_clearing_row],
	)

	doc.db_set("azzir_local_settlement_journal_entry", local_je, update_modified=False)
	doc.db_set("azzir_settlement_journal_entry", sister_je, update_modified=False)


def on_cancel(doc, method=None):
	"""Cancel both linked settlement Journal Entries too, so cancelling the payment
	doesn't leave a dangling settlement behind.

	Must also CLEAR the fields afterward -- otherwise they keep pointing at now-
	cancelled JEs, and Amend copies those values verbatim onto the new doc, which
	Frappe's core link check then rejects with "Cannot link cancelled document"
	on save."""
	if not doc.get("azzir_paid_on_behalf_of_sister"):
		return
	for fieldname in ("azzir_settlement_journal_entry", "azzir_local_settlement_journal_entry"):
		je_name = doc.get(fieldname)
		if je_name and frappe.db.exists("Journal Entry", je_name):
			je = frappe.get_doc("Journal Entry", je_name)
			if je.docstatus == 1:
				je.flags.ignore_permissions = True
				je.cancel()
		doc.db_set(fieldname, None, update_modified=False)
