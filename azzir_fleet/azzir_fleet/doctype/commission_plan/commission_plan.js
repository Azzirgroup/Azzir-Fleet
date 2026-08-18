// Copyright (c) 2026, Azzir and contributors
// For license information, please see license.txt
//
// The Commission Plan is config only — the numbers are produced by the
// "Commission Report" (Reports > Commission Report), which lets you pick a plan,
// a date range and (optionally) one sales person.

frappe.ui.form.on("Commission Plan", {
	refresh(frm) {
		if (!frm.is_new()) {
			frm.add_custom_button(__("Commission Report"), () => {
				frappe.set_route("query-report", "Commission Report", { commission_plan: frm.doc.name });
			});
		}
	},
});
