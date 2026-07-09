// Copyright (c) 2026, Azzir and contributors
// For license information, please see license.txt

frappe.ui.form.on("Monthly Budget", {
	refresh(frm) {
		if (!frm.is_new()) {
			frm.add_custom_button(__("Refresh Actuals"), () => {
				frappe.call({
					method: "azzir_fleet.azzir_fleet.doctype.monthly_budget.monthly_budget.refresh_actuals",
					args: { name: frm.doc.name },
					freeze: true,
					callback: () => frm.reload_doc(),
				});
			});
		}
	},

	year(frm) {
		if (!frm.doc.year) frm.set_value("year", new Date().getFullYear());
	},
});

frappe.ui.form.on("Monthly Budget Account", {
	amount(frm) {
		let total = 0;
		(frm.doc.accounts || []).forEach((d) => (total += flt(d.amount)));
		frm.set_value("total_budget", total);
	},
});
