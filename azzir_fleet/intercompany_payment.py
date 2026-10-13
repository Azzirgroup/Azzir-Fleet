# Copyright (c) 2026, Azzir and contributors
# For license information, please see license.txt
"""Paid On Behalf Of Sister Company: this company's cash actually settles a SISTER
company's debt, not its own.

Receive: a customer's cash lands in ONE company's bank, but the invoice it's settling
belongs to a SISTER company (e.g. bought from HPL, paid into HCL).
Pay: this company pays a SUPPLIER, but the bill it's settling is actually the SISTER's
(the sister owes that supplier, not this company).

Tick "Paid On Behalf Of Sister Company", pick the Sister Company and their invoice
(a Sales Invoice for Receive, a Purchase Invoice for Pay). On submit:
  - THIS Payment Entry posts its cash against the Intercompany Clearing Account
    (configured per Company) instead of the real party's own ledger here — that party
    owes/is-owed nothing by THIS company; the real debt sits on the sister's books.
  - A Journal Entry is auto-created IN THE SISTER COMPANY, settling the real invoice
    there (crediting a receivable for Receive, debiting a payable for Pay) and moving
    the sister's own clearing account the opposite way.

Both companies need their Intercompany Clearing Account set (Company -> Accounts) —
a liability-type account works best. The SAME account is used for both directions: its
balance just nets whichever way the IOU currently runs between the two companies.
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
	"""Runs BEFORE ERPNext's own Payment Entry validate, so our override of the party
	account (paid_from for Receive, paid_to for Pay) is in place before core computes
	anything against it (exchange rates, account currency, etc.) — not after, which
	would leave those stale."""
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

	# A clearing account carrying a Party only passes ERPNext's own validation when its
	# Account Type is blank (or Receivable/Payable/Equity, which don't make sense here).
	# "Fixed Asset", "Cash", "Accumulated Depreciation" etc. all look like reasonable
	# balance-sheet accounts but fail that check with a confusing generic error -- catch
	# it here with a clear one instead.
	our_type = frappe.db.get_value("Account", our_clearing, "account_type")
	if our_type and our_type not in ("Receivable", "Payable", "Equity"):
		frappe.throw(_(
			"{0}'s Intercompany Clearing Account ({1}) has Account Type '{2}' set — pick "
			"a plain Balance Sheet account with NO Account Type instead (Company → Accounts)."
		).format(frappe.bold(doc.company), frappe.bold(our_clearing), our_type))

	# Post the cash against the clearing account, not the real party's own ledger in
	# THIS company — they owe/are-owed nothing here; the real debt is the sister's.
	setattr(doc, cfg["pe_account_field"], our_clearing)


def on_submit(doc, method=None):
	"""Settle the sister's invoice with a Journal Entry in the sister company."""
	if not doc.get("azzir_paid_on_behalf_of_sister"):
		return

	from azzir_fleet.intercompany_sale import _company_cost_center

	cfg = _DIRECTION[doc.payment_type]
	invoice_name = doc.get(cfg["invoice_field"])
	inv = frappe.get_doc(cfg["invoice_doctype"], invoice_name)
	sister_clearing = _clearing_account(doc.azzir_sister_company)
	cost_center = _company_cost_center(doc.azzir_sister_company)
	invoice_account = inv.get(cfg["invoice_account_field"])

	je = frappe.new_doc("Journal Entry")
	je.voucher_type = "Journal Entry"
	je.company = doc.azzir_sister_company
	je.posting_date = doc.posting_date
	je.user_remark = _(
		"Settlement for {0}: {1} on behalf of {2}, against {3} {4}."
	).format(
		doc.name,
		"received into {0}".format(doc.company) if doc.payment_type == "Receive"
		else "paid out of {0}".format(doc.company),
		doc.azzir_sister_company, cfg["invoice_doctype"], invoice_name,
	)

	party_row = {
		"account": invoice_account,
		"party_type": cfg["party_type"],
		"party": doc.party,
		"reference_type": cfg["invoice_doctype"],
		"reference_name": invoice_name,
		"cost_center": cost_center,
	}
	clearing_row = {"account": sister_clearing, "cost_center": cost_center}

	if doc.payment_type == "Receive":
		# Settling a receivable: credit it down. The sister's clearing account takes
		# the offsetting debit (they're now owed this cash back from us).
		party_row["credit_in_account_currency"] = flt(doc.paid_amount)
		clearing_row["debit_in_account_currency"] = flt(doc.paid_amount)
	else:
		# Settling a payable: debit it down. The sister's clearing account takes the
		# offsetting credit (they now owe this amount to us, since we paid their bill).
		party_row["debit_in_account_currency"] = flt(doc.paid_amount)
		clearing_row["credit_in_account_currency"] = flt(doc.paid_amount)

	je.append("accounts", party_row)
	je.append("accounts", clearing_row)
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
