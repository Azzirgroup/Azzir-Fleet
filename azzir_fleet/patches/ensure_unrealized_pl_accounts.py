# Copyright (c) 2026, Azzir and contributors
# For license information, please see license.txt
"""One-time: give every company an Unrealized Profit / Loss Account (required for
intercompany transfers). Runs ONCE — afterwards you can change the accounts
freely; the app won't touch them again."""

import frappe


def execute():
	from azzir_fleet.setup import _ensure_unrealized_pl_accounts

	_ensure_unrealized_pl_accounts()
	frappe.db.commit()
