// Copyright (c) 2026, Azzir and contributors
// Apply VAT toggle — immediate UI feedback. The server (azzir_fleet.vat) is the
// source of truth on save; this just updates the form live when you tick/untick.

["Sales Invoice", "Sales Order", "Quotation", "Delivery Note"].forEach(function (dt) {
	frappe.ui.form.on(dt, {
		azzir_apply_vat(frm) {
			if (!frm.doc.azzir_apply_vat) {
				// VAT off: drop tax rows + template, recalc without tax.
				frm.clear_table("taxes");
				if (frm.fields_dict.taxes_and_charges) {
					frm.set_value("taxes_and_charges", null);
				}
				frm.refresh_field("taxes");
				frm.cscript && frm.cscript.calculate_taxes_and_totals
					? frm.cscript.calculate_taxes_and_totals()
					: frm.trigger("calculate_taxes_and_totals");
			} else {
				// VAT back on: re-apply the company default tax template.
				frm.trigger("taxes_and_charges");
			}
		},
	});
});
