// Copyright (c) 2026, Azzir and contributors
// Tax Inclusive/Exclusive live calc on Expense Entry & Journal Entry rows.
// Server (azzir_fleet.tax_calc) is the source of truth on save; this mirrors it.

frappe.provide("azzir_fleet");

azzir_fleet.split_tax = function (base, type, rate) {
	base = flt(base);
	rate = flt(rate);
	if (!type || !rate || !base) return [0, base];
	if (type === "Inclusive") {
		const net = base / (1 + rate / 100);
		return [flt(base - net), flt(net)];
	}
	return [flt((base * rate) / 100), flt(base)]; // Exclusive
};

function apply_calc(frm, cdt, cdn, base) {
	const r = locals[cdt][cdn];
	const [tax, net] = azzir_fleet.split_tax(base, r.azzir_tax_type, r.azzir_tax_rate);
	frappe.model.set_value(cdt, cdn, "azzir_tax_amount", tax);
	frappe.model.set_value(cdt, cdn, "azzir_net_amount", net);
}

frappe.ui.form.on("Expense Entry Account", {
	amount: (frm, cdt, cdn) => apply_calc(frm, cdt, cdn, locals[cdt][cdn].amount),
	azzir_tax_type: (frm, cdt, cdn) => apply_calc(frm, cdt, cdn, locals[cdt][cdn].amount),
	azzir_tax_rate: (frm, cdt, cdn) => apply_calc(frm, cdt, cdn, locals[cdt][cdn].amount),
});

function je_base(cdt, cdn) {
	const r = locals[cdt][cdn];
	return flt(r.debit_in_account_currency) || flt(r.credit_in_account_currency);
}
frappe.ui.form.on("Journal Entry Account", {
	debit_in_account_currency: (frm, cdt, cdn) => apply_calc(frm, cdt, cdn, je_base(cdt, cdn)),
	credit_in_account_currency: (frm, cdt, cdn) => apply_calc(frm, cdt, cdn, je_base(cdt, cdn)),
	azzir_tax_type: (frm, cdt, cdn) => apply_calc(frm, cdt, cdn, je_base(cdt, cdn)),
	azzir_tax_rate: (frm, cdt, cdn) => apply_calc(frm, cdt, cdn, je_base(cdt, cdn)),
});
