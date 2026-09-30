// Copyright (c) 2026, Azzir and contributors
// User.azzir_home_group_warehouse should be a GROUP warehouse (it auto-selects the
// Default Group Source Warehouse on a new Stock Entry) — filter the picker to groups only.

frappe.ui.form.on("User", {
	onload(frm) {
		if (frm.fields_dict.azzir_home_group_warehouse) {
			frm.set_query("azzir_home_group_warehouse", () => ({ filters: { is_group: 1 } }));
		}
	},
});
