// Copyright (c) 2026, Azzir and contributors
// Apply VAT toggle — immediate UI feedback. The server (azzir_fleet.vat) is the
// source of truth on save; this mirrors it live when you tick/untick.

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
				frm.trigger("calculate_taxes_and_totals");
				return;
			}
			// VAT on: if nothing is there yet, auto-apply the VAT account.
			if ((frm.doc.taxes || []).length) return;
			frappe.call({
				method: "azzir_fleet.vat.get_vat_row",
				args: { company: frm.doc.company },
				callback(r) {
					if (!r.message || !r.message.account_head) {
						frappe.show_alert({
							message: __("No VAT account found for this company."),
							indicator: "orange",
						});
						return;
					}
					const row = frm.add_child("taxes", r.message);
					frm.refresh_field("taxes");
					frm.trigger("calculate_taxes_and_totals");
				},
			});
		},
	});
});
