// Azzir Fleet — Item Codes child table behaviour.
// Only one row can be Primary; ticking one unticks the others. Saving with a new
// Primary renames the item (handled server-side).

frappe.ui.form.on("Item Code Entry", {
	is_primary(frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		if (!row.is_primary) return;
		(frm.doc.azzir_alias_codes || []).forEach((r) => {
			if (r.name !== cdn && r.is_primary) {
				frappe.model.set_value(r.doctype, r.name, "is_primary", 0);
			}
		});
		frm.refresh_field("azzir_alias_codes");
	},
});

frappe.ui.form.on("Item", {
	refresh(frm) {
		const grid = frm.get_field("azzir_alias_codes");
		if (grid) {
			grid.grid.set_column_disp && grid.grid.set_column_disp("source", true);
		}
	},
});
