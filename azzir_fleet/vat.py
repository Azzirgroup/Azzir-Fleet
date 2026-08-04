# Copyright (c) 2026, Azzir and contributors
# For license information, please see license.txt
"""'Apply VAT' checkbox — auto-apply/remove VAT per document.

- Checked (default) and no tax on the doc yet: auto-add a VAT tax row using the
  company account whose name starts with "VAT" (standard "On Net Total" charge).
  If the doc already has taxes (e.g. a template applied), they're respected.
- Unchecked: strip all taxes and recompute without VAT.

Runs on `validate` — AFTER ERPNext's controller has set/recalculated taxes, so
this is the final word (see AccountsController.set_taxes).
"""

import frappe
from frappe.utils import flt

VAT_PREFIX = "VAT"


def apply_vat_option(doc, method=None):
	if doc.get("azzir_apply_vat") is None:
		return
	if not doc.meta.has_field("taxes"):
		return

	if not doc.get("azzir_apply_vat"):
		_strip_vat(doc)
		return

	# VAT ON: if nothing has added taxes yet, apply the VAT account automatically.
	if doc.get("taxes"):
		return
	row = get_vat_row(doc.get("company"))
	if not row:
		return
	doc.append("taxes", row)
	if hasattr(doc, "calculate_taxes_and_totals"):
		doc.calculate_taxes_and_totals()


def _strip_vat(doc):
	had_taxes = bool(doc.get("taxes"))
	if had_taxes:
		doc.set("taxes", [])
	if doc.meta.has_field("taxes_and_charges") and doc.get("taxes_and_charges"):
		doc.taxes_and_charges = None
		had_taxes = True
	if had_taxes and hasattr(doc, "calculate_taxes_and_totals"):
		doc.calculate_taxes_and_totals()


@frappe.whitelist()
def get_vat_row(company: str) -> dict:
	"""The standard VAT tax row for `company`: the account whose name starts with
	VAT (Tax-type preferred) + its rate. Empty dict if none found."""
	account = _find_vat_account(company)
	if not account:
		return {}
	return {
		"charge_type": "On Net Total",
		"account_head": account,
		"description": frappe.db.get_value("Account", account, "account_name") or "VAT",
		"rate": _vat_rate(account),
	}


def _find_vat_account(company: str) -> str | None:
	if not company:
		return None
	accounts = frappe.get_all(
		"Account",
		filters={
			"company": company,
			"is_group": 0,
			"disabled": 0,
			"account_name": ["like", f"{VAT_PREFIX}%"],
		},
		fields=["name", "account_type"],
		order_by="name",
	)
	if not accounts:
		return None
	# Prefer a proper Tax-type account.
	tax = [a for a in accounts if a.account_type == "Tax"]
	return (tax[0] if tax else accounts[0]).name


def _vat_rate(account: str) -> float:
	# 1) the account's own tax_rate, else 2) a rate it has been used with before.
	rate = flt(frappe.db.get_value("Account", account, "tax_rate"))
	if rate:
		return rate
	return flt(
		frappe.db.get_value(
			"Sales Taxes and Charges", {"account_head": account, "rate": [">", 0]}, "rate"
		)
	)
