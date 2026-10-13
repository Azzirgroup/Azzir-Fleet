// Copyright (c) 2026, Azzir and contributors
// Intercompany Clearing Account: restrict the picker to this company's own Balance
// Sheet accounts (Asset / Liability) with NO specific Account Type set. A P&L account
// (Income/Expense) would need a Cost Center and throw on save; and ERPNext separately
// rejects ANY account whose Account Type isn't Receivable/Payable/Equity the moment a
// Party is attached to it (which this feature always does) -- e.g. "Fixed Asset",
// "Cash", "Accumulated Depreciation" all look like fine balance-sheet accounts but
// fail that check. Only a plain account with no Account Type set is actually safe.

frappe.ui.form.on("Company", {
	onload(frm) {
		frm.set_query("azzir_intercompany_clearing_account", function () {
			return {
				filters: [
					["Account", "company", "=", frm.doc.name],
					["Account", "is_group", "=", 0],
					["Account", "root_type", "in", ["Asset", "Liability"]],
					["Account", "account_type", "is", "not set"],
				],
			};
		});
	},
});
