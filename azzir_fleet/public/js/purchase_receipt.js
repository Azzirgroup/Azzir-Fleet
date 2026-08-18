// Copyright (c) 2026, Azzir and contributors
// Purchase Receipt: when an item is selected and the row has no warehouse yet,
// auto-fill the warehouse the item was LAST stored in (from stock history) —
// even if that warehouse is now empty.

frappe.ui.form.on("Purchase Receipt Item", {
	item_code(frm, cdt, cdn) {
		const row = locals[cdt] && locals[cdt][cdn];
		if (!row || !row.item_code || row.warehouse) return;
		frappe.call({
			method: "azzir_fleet.stock_info.last_warehouse",
			args: { item_code: row.item_code, company: frm.doc.company },
			callback(r) {
				if (r.message && !locals[cdt][cdn].warehouse) {
					frappe.model.set_value(cdt, cdn, "warehouse", r.message);
				}
			},
		});
	},
});
