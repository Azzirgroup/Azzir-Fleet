// Copyright (c) 2026, Azzir and contributors
// For license information, please see license.txt

frappe.ui.form.on("Expense Entry", {
	refresh(frm) {
		calculate_total(frm);
	},
});

frappe.ui.form.on("Expense Entry Account", {
	amount: function (frm) {
		calculate_total(frm);
	},
	accounts_remove: function (frm) {
		calculate_total(frm);
	},
});

var calculate_total = function (frm) {
	let total = 0;
	$.each(frm.doc.accounts || [], function (i, d) {
		total += flt(d.amount);
	});
	frm.set_value("total_amount", total);
};
